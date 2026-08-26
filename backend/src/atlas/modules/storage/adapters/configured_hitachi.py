from __future__ import annotations

import hashlib
import re
from datetime import datetime

from atlas.modules.connectors.application.bundled_connection_configuration_ports import (
    BundledConnectionConfigurationRepository,
)
from atlas.modules.connectors.application.bundled_runtime_state_ports import (
    BundledConnectorRuntimeStateRepository,
)
from atlas.modules.connectors.application.connection_test_ports import (
    ConnectorConnectionTestError,
    ConnectorCredentialMaterializer,
    HitachiConnectionTestTransportFactory,
)
from atlas.modules.connectors.application.instance_creation_ports import (
    ConnectorInstanceRepository,
)
from atlas.modules.connectors.domain.bundled_connection_configuration import (
    BundledConnectionConfiguration,
)
from atlas.modules.connectors.domain.bundled_runtime_state import ENABLED_READ_ONLY
from atlas.modules.connectors.domain.instance_creation import DISABLED_UNCONFIGURED
from atlas.modules.connectors.vendors.hitachi_ops_center.client import (
    HitachiConnectorError,
    HitachiOpsCenterClient,
)
from atlas.modules.connectors.vendors.hitachi_ops_center.domain import (
    HealthSeverity,
    HitachiHealthResult,
    HitachiInventoryResult,
)
from atlas.modules.connectors.vendors.hitachi_ops_center.manifest import PACKAGE_ID
from atlas.modules.inventory.application.ports import InventoryDeviceRepository
from atlas.modules.inventory.domain.devices import (
    InventoryDeviceLifecycle,
    InventoryDeviceType,
)
from atlas.modules.storage.domain.models import (
    EvidenceRecord,
    FindingSeverity,
    FreshnessState,
    HealthFinding,
    InvestigationState,
    StorageAsset,
    StorageHealthState,
    StorageInvestigation,
    StorageOverview,
    StorageReport,
)

_STORAGE_DEVICE_ID = re.compile(r"^[A-Za-z0-9]{6,32}$")
_MAX_ALLOWED_STORAGE_TARGETS = 25
_DATA_PROFILE = "configured_hitachi_read_only"
_SAFETY_NOTICE = (
    "Decision support only. No infrastructure change or service-impacting action is authorized."
)
_SAFE_CONNECTOR_ERROR_CODES = frozenset(
    {
        "invalid_storage_device_id",
        "malformed_vendor_response",
        "target_not_bound",
        "target_timeout",
        "target_unavailable",
        "unsupported_vendor_version",
        "vendor_permission_denied",
        "vendor_rate_limited",
        "vendor_response_limit_exceeded",
    }
)
_ASSET_HEALTH_STATE: dict[HealthSeverity, StorageHealthState] = {
    HealthSeverity.NORMAL: StorageHealthState.HEALTHY,
    HealthSeverity.WARNING: StorageHealthState.WARNING,
    HealthSeverity.DEGRADED: StorageHealthState.WARNING,
    HealthSeverity.CRITICAL: StorageHealthState.CRITICAL,
    HealthSeverity.UNKNOWN: StorageHealthState.UNKNOWN,
}
_FINDING_SEVERITY: dict[HealthSeverity, FindingSeverity] = {
    HealthSeverity.WARNING: FindingSeverity.WARNING,
    HealthSeverity.DEGRADED: FindingSeverity.WARNING,
    HealthSeverity.CRITICAL: FindingSeverity.CRITICAL,
    HealthSeverity.UNKNOWN: FindingSeverity.UNKNOWN,
}


def _connector_failure_reason(exc: HitachiConnectorError) -> str:
    code = exc.code if exc.code in _SAFE_CONNECTOR_ERROR_CODES else "connector_error"
    return f"The Hitachi read failed safely ({code})."


def _identity(*parts: str) -> str:
    normalized = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()[:20]


class ConfiguredHitachiStorageProvider:
    """Serves the storage overview from the single configured, enabled Hitachi MCP."""

    def __init__(
        self,
        *,
        configuration_repository: BundledConnectionConfigurationRepository,
        instance_repository: ConnectorInstanceRepository,
        inventory_repository: InventoryDeviceRepository,
        credential_materializer: ConnectorCredentialMaterializer,
        transport_factory: HitachiConnectionTestTransportFactory,
        organization_id: str,
        environment_id: str,
        site_id: str = "site.local",
        target_id: str = "target.hitachi.opscenter.configured",
        connector_version: str = "0.1.0",
        runtime_state_repository: BundledConnectorRuntimeStateRepository | None = None,
        max_targets: int = _MAX_ALLOWED_STORAGE_TARGETS,
        timeout_seconds: float = 20.0,
    ) -> None:
        self._configuration_repository = configuration_repository
        self._instance_repository = instance_repository
        self._inventory_repository = inventory_repository
        self._credential_materializer = credential_materializer
        self._transport_factory = transport_factory
        self._organization_id = organization_id
        self._environment_id = environment_id
        self._site_id = site_id
        self._target_id = target_id
        self._connector_version = connector_version
        self._runtime_state_repository = runtime_state_repository
        self._max_targets = max_targets
        self._timeout_seconds = timeout_seconds

    async def get_overview(self, *, requested_at: datetime) -> StorageOverview:
        configuration = await self._single_active_configuration()
        if configuration is None:
            return self._unavailable_overview(
                requested_at,
                reason="A single active configured Hitachi MCP is required to read storage "
                "inventory.",
            )
        if self._runtime_state_repository is not None:
            runtime_state = await self._runtime_state_repository.get(
                organization_id=self._organization_id,
                environment_id=self._environment_id,
                instance_id=configuration.instance_id,
            )
            if (
                runtime_state is None
                or runtime_state.state != ENABLED_READ_ONLY
                or runtime_state.configuration_id != configuration.configuration_id
            ):
                return self._unavailable_overview(
                    requested_at,
                    reason="The configured Hitachi MCP must be enabled for read-only storage "
                    "polling.",
                )
        storage_ids = await self._allowed_storage_ids()
        if not storage_ids:
            return self._unavailable_overview(
                requested_at,
                reason="No active Hitachi storage serial number is allowlisted in inventory.",
            )

        try:
            async with self._credential_materializer.lease_authorization_header(
                secret_reference_id=configuration.secret_reference_id,
                maximum_lease_seconds=min(30, int(self._timeout_seconds) + 1),
            ) as lease:
                transport = self._transport_factory.create(
                    hostname=configuration.hostname,
                    port=configuration.port,
                    trust_profile_id=configuration.trust_profile_id,
                    authorization_header_provider=lease.authorization_header,
                    timeout_seconds=self._timeout_seconds,
                    maximum_response_bytes=1_048_576,
                )
                client = HitachiOpsCenterClient(
                    transport=transport,
                    allowed_storage_device_ids=storage_ids,
                    maximum_arrays=500,
                    maximum_components=5_000,
                    maximum_response_bytes=1_048_576,
                )
                inventory = await client.read_inventory()
                return await self._build_overview(
                    client=client,
                    inventory=inventory,
                    requested_at=requested_at,
                )
        except ConnectorConnectionTestError:
            return self._unavailable_overview(
                requested_at,
                reason="The Hitachi credential reference is unavailable for this storage read.",
            )
        except HitachiConnectorError as exc:
            return self._unavailable_overview(requested_at, reason=_connector_failure_reason(exc))
        except (TimeoutError, ValueError):
            return self._unavailable_overview(
                requested_at,
                reason="The configured Hitachi storage read failed safely.",
            )

    async def _build_overview(
        self,
        *,
        client: HitachiOpsCenterClient,
        inventory: HitachiInventoryResult,
        requested_at: datetime,
    ) -> StorageOverview:
        evidence: list[EvidenceRecord] = [
            EvidenceRecord(
                reference=reference,
                source="Hitachi Ops Center inventory read",
                source_version=self._connector_version,
                observed_at=inventory.observed_at,
                freshness=FreshnessState.CURRENT,
                trust_basis="Digest-only evidence from an allowlisted C1 HTTPS GET response",
            )
            for reference in inventory.evidence_references
        ]
        assets: list[StorageAsset] = []
        findings: list[HealthFinding] = []
        failed_reads = 0
        warnings_present = False

        for array in inventory.arrays[: self._max_targets]:
            try:
                health = await client.read_hardware_health(array.storage_device_id)
            except HitachiConnectorError:
                failed_reads += 1
                assets.append(
                    StorageAsset(
                        asset_id=f"asset.storage.{_identity(array.storage_device_id)}",
                        storage_device_id=array.storage_device_id,
                        vendor="Hitachi Vantara",
                        model=array.model,
                        serial_number=array.serial_number,
                        health=StorageHealthState.UNKNOWN,
                        observed_at=inventory.observed_at,
                        evidence_references=tuple(inventory.evidence_references),
                    )
                )
                continue

            health_evidence = tuple(
                EvidenceRecord(
                    reference=reference,
                    source="Hitachi Ops Center hardware-health read",
                    source_version=self._connector_version,
                    observed_at=health.observed_at,
                    freshness=FreshnessState.CURRENT,
                    trust_basis="Digest-only evidence from an allowlisted C1 HTTPS GET response",
                )
                for reference in health.evidence_references
            )
            evidence.extend(health_evidence)
            asset_evidence = tuple(inventory.evidence_references) + tuple(
                item.reference for item in health_evidence
            )
            assets.append(
                StorageAsset(
                    asset_id=f"asset.storage.{_identity(array.storage_device_id)}",
                    storage_device_id=array.storage_device_id,
                    vendor="Hitachi Vantara",
                    model=array.model,
                    serial_number=array.serial_number,
                    health=_ASSET_HEALTH_STATE[health.overall_severity],
                    observed_at=health.observed_at,
                    evidence_references=asset_evidence,
                )
            )
            if health.warnings:
                warnings_present = True
            findings.extend(
                self._map_findings(
                    health=health,
                    evidence_references=tuple(item.reference for item in health_evidence),
                )
            )

        asset_count = len(assets)
        finding_count = len(findings)
        unknowns = [
            "No root cause or service-impact determination is made by this read-only check.",
            "No corroborating event-log or facility evidence is loaded in this scope.",
        ]
        if failed_reads:
            unknowns.append(
                f"Component health could not be read for {failed_reads} of {asset_count} "
                "allowlisted storage array(s); their health is reported as unknown."
            )
        if warnings_present:
            unknowns.append(
                "Vendor component health could not be fully normalized for one or more storage "
                "arrays; some component states may be incomplete."
            )
        unknowns_tuple = tuple(unknowns)

        if finding_count:
            summary = (
                f"{finding_count} hardware finding(s) were observed across {asset_count} "
                "allowlisted Hitachi storage array(s) in this scope."
            )
        else:
            summary = (
                f"No hardware findings were observed across {asset_count} allowlisted Hitachi "
                "storage array(s) in this scope in the current read."
            )
        investigation_evidence = tuple(item.reference for item in evidence)
        investigation = StorageInvestigation(
            investigation_id=f"investigation.storage.{_identity(str(requested_at))}",
            title="Configured Hitachi storage hardware read",
            state=InvestigationState.PROVISIONAL,
            summary=summary,
            hypotheses=(),
            unknowns=unknowns_tuple,
            next_checks=(
                "Repeat the read-only hardware-health check to confirm persistence of any open "
                "finding.",
                "Review an authorized storage event-log source for the same observation window.",
            ),
            evidence_references=investigation_evidence,
            updated_at=requested_at,
        )
        if finding_count:
            confirmed_facts = (
                f"{asset_count} allowlisted Hitachi storage array(s) were read via the "
                "configured Hitachi Ops Center connector.",
                f"{finding_count} controller/component finding(s) at severity warning or "
                "higher were observed.",
            )
        else:
            confirmed_facts = (
                f"{asset_count} allowlisted Hitachi storage array(s) were read via the "
                "configured Hitachi Ops Center connector.",
                "No component reported a severity above normal.",
            )
        report = StorageReport(
            report_id=f"report.storage.{_identity(str(requested_at))}",
            title="Configured Hitachi storage hardware assessment",
            generated_at=requested_at,
            executive_summary=summary,
            confirmed_facts=confirmed_facts,
            provisional_findings=tuple(finding.summary for finding in findings),
            unknowns=unknowns_tuple,
            evidence_references=investigation_evidence,
            safety_notice=_SAFETY_NOTICE,
        )

        return StorageOverview(
            snapshot_id=f"snapshot.storage.{_identity(str(requested_at))}",
            organization_id=self._organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
            target_id=self._target_id,
            data_profile=_DATA_PROFILE,
            generated_at=requested_at,
            assets=tuple(assets),
            findings=tuple(findings),
            evidence=tuple(evidence),
            investigation=investigation,
            report=report,
        )

    @staticmethod
    def _map_findings(
        *,
        health: HitachiHealthResult,
        evidence_references: tuple[str, ...],
    ) -> list[HealthFinding]:
        findings: list[HealthFinding] = []
        for index, component in enumerate(health.components):
            if component.severity is HealthSeverity.NORMAL:
                continue
            identity = _identity(
                health.storage_device_id, component.category, component.location, str(index)
            )
            findings.append(
                HealthFinding(
                    finding_id=f"finding.storage.{identity}",
                    asset_id=f"asset.storage.{_identity(health.storage_device_id)}",
                    severity=_FINDING_SEVERITY[component.severity],
                    component=f"{component.category}:{component.location}",
                    summary=(
                        f"{component.category} at {component.location} reports vendor status "
                        f"'{component.vendor_status}'."
                    ),
                    observed_at=health.observed_at,
                    evidence_references=evidence_references,
                )
            )
        return findings

    def _unavailable_overview(self, requested_at: datetime, *, reason: str) -> StorageOverview:
        meta_reference = (
            f"atlas-config://{self._organization_id}/{self._environment_id}"
            f"#{_identity(reason, requested_at.isoformat())}"
        )
        evidence = (
            EvidenceRecord(
                reference=meta_reference,
                source="Atlas connector configuration and inventory state",
                source_version=self._connector_version,
                observed_at=requested_at,
                freshness=FreshnessState.UNKNOWN,
                trust_basis=(
                    "Live query of Atlas connector configuration, runtime state, and "
                    "inventory repositories"
                ),
            ),
        )
        unknowns = (
            reason,
            "Storage asset health is unknown because no read-only Hitachi connector read "
            "completed.",
        )
        investigation = StorageInvestigation(
            investigation_id=f"investigation.storage.{_identity(reason, str(requested_at))}",
            title="Configured Hitachi storage hardware read",
            state=InvestigationState.INCONCLUSIVE,
            summary=(
                "Storage inventory and evidence could not be read from the configured Hitachi "
                f"Ops Center connector: {reason}"
            ),
            hypotheses=(),
            unknowns=unknowns,
            next_checks=(
                "Configure and enable exactly one read-only Hitachi Ops Center connector "
                "instance for this environment.",
                "Allowlist at least one active Hitachi storage device with a valid serial "
                "number in inventory.",
            ),
            evidence_references=(meta_reference,),
            updated_at=requested_at,
        )
        report = StorageReport(
            report_id=f"report.storage.{_identity(reason, str(requested_at))}",
            title="Configured Hitachi storage hardware assessment",
            generated_at=requested_at,
            executive_summary=investigation.summary,
            confirmed_facts=(),
            provisional_findings=(),
            unknowns=unknowns,
            evidence_references=(meta_reference,),
            safety_notice=_SAFETY_NOTICE,
        )
        return StorageOverview(
            snapshot_id=f"snapshot.storage.{_identity(reason, str(requested_at))}",
            organization_id=self._organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
            target_id=self._target_id,
            data_profile=_DATA_PROFILE,
            generated_at=requested_at,
            assets=(),
            findings=(),
            evidence=evidence,
            investigation=investigation,
            report=report,
        )

    async def _single_active_configuration(self) -> BundledConnectionConfiguration | None:
        instances = await self._instance_repository.list_scope(
            organization_id=self._organization_id,
            environment_id=self._environment_id,
        )
        active_ids = {
            instance.instance_id
            for instance in instances
            if instance.connector_id == PACKAGE_ID
            and instance.instance_state == DISABLED_UNCONFIGURED
        }
        configurations = await self._configuration_repository.list_scope(
            organization_id=self._organization_id,
            environment_id=self._environment_id,
        )
        candidates = tuple(
            item
            for item in configurations
            if item.connector_id == PACKAGE_ID and item.instance_id in active_ids
        )
        return candidates[0] if len(candidates) == 1 else None

    async def _allowed_storage_ids(self) -> frozenset[str]:
        devices = await self._inventory_repository.list_scope(
            organization_id=self._organization_id,
            environment_id=self._environment_id,
            lifecycle=InventoryDeviceLifecycle.ACTIVE,
            query=None,
            limit=500,
        )
        identifiers = (
            device.serial_number
            for device in devices
            if device.device_type is InventoryDeviceType.STORAGE
            and "hitachi" in device.vendor.lower()
            and device.serial_number is not None
            and _STORAGE_DEVICE_ID.fullmatch(device.serial_number)
        )
        return frozenset(tuple(identifiers)[: self._max_targets])
