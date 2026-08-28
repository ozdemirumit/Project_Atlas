from __future__ import annotations

import hashlib
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
    HuaweiConnectionTestTransportFactory,
)
from atlas.modules.connectors.application.instance_creation_ports import (
    ConnectorInstanceRepository,
)
from atlas.modules.connectors.domain.bundled_connection_configuration import (
    BundledConnectionConfiguration,
)
from atlas.modules.connectors.domain.bundled_runtime_state import ENABLED_READ_ONLY
from atlas.modules.connectors.domain.instance_creation import DISABLED_UNCONFIGURED
from atlas.modules.connectors.vendors.huawei_dorado.client import (
    HuaweiConnectorError,
    HuaweiDoradoClient,
)
from atlas.modules.connectors.vendors.huawei_dorado.domain import (
    HuaweiControllerHealth,
    HuaweiHealthStatus,
    HuaweiSystemIdentity,
)
from atlas.modules.connectors.vendors.huawei_dorado.manifest import PACKAGE_ID
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

_DATA_PROFILE = "configured_huawei_dorado_read_only"
_SAFETY_NOTICE = (
    "Decision support only. No infrastructure change or service-impacting action is authorized."
)
_SAFE_CONNECTOR_ERROR_CODES = frozenset(
    {
        "malformed_vendor_response",
        "target_timeout",
        "target_unavailable",
        "vendor_error_response",
        "vendor_permission_denied",
        "vendor_rate_limited",
        "vendor_response_limit_exceeded",
    }
)
_ASSET_HEALTH_STATE: dict[HuaweiHealthStatus, StorageHealthState] = {
    HuaweiHealthStatus.NORMAL: StorageHealthState.HEALTHY,
    HuaweiHealthStatus.FAULTY: StorageHealthState.CRITICAL,
    HuaweiHealthStatus.UNKNOWN: StorageHealthState.UNKNOWN,
}
_FINDING_SEVERITY: dict[HuaweiHealthStatus, FindingSeverity] = {
    HuaweiHealthStatus.FAULTY: FindingSeverity.CRITICAL,
    HuaweiHealthStatus.UNKNOWN: FindingSeverity.UNKNOWN,
}


def _connector_failure_reason(exc: HuaweiConnectorError) -> str:
    code = exc.code if exc.code in _SAFE_CONNECTOR_ERROR_CODES else "connector_error"
    return f"The Huawei Dorado read failed safely ({code})."


def _identity(*parts: str) -> str:
    # Matches the graph/health_checks Huawei adapters' identity scheme exactly, so a storage
    # asset_id agrees with the same real system's graph entity_id and health target_id.
    normalized = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()[:20]


class ConfiguredHuaweiDoradoStorageProvider:
    """Serves the storage overview from the single configured, enabled Huawei Dorado MCP.

    One configured instance manages exactly one Dorado system (see huawei_dorado/ports.py), so
    there is no multi-target allowlist to filter here -- the configuration's own `system_id` is
    the target, cross-checked against an active, allowlisted inventory device as a second gate.
    """

    def __init__(
        self,
        *,
        configuration_repository: BundledConnectionConfigurationRepository,
        instance_repository: ConnectorInstanceRepository,
        inventory_repository: InventoryDeviceRepository,
        credential_materializer: ConnectorCredentialMaterializer,
        transport_factory: HuaweiConnectionTestTransportFactory,
        organization_id: str,
        environment_id: str,
        site_id: str = "site.local",
        target_id: str = "target.huawei.dorado.configured",
        connector_version: str = "0.1.0",
        runtime_state_repository: BundledConnectorRuntimeStateRepository | None = None,
        max_controllers: int = 64,
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
        self._max_controllers = max_controllers
        self._timeout_seconds = timeout_seconds

    async def get_overview(self, *, requested_at: datetime) -> StorageOverview:
        configuration = await self._single_active_configuration()
        if configuration is None or configuration.system_id is None:
            return self._unavailable_overview(
                requested_at,
                reason="A single active configured Huawei Dorado MCP with a system identifier "
                "is required to read storage inventory.",
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
                    reason="The configured Huawei Dorado MCP must be enabled for read-only "
                    "storage polling.",
                )
        if not await self._system_is_allowlisted(configuration.system_id):
            return self._unavailable_overview(
                requested_at,
                reason="The configured Huawei Dorado system is not an active, allowlisted "
                "storage device in inventory.",
            )

        try:
            async with self._credential_materializer.lease_authorization_header(
                secret_reference_id=configuration.secret_reference_id,
                maximum_lease_seconds=min(30, int(self._timeout_seconds) + 1),
            ) as lease:
                transport = self._transport_factory.create(
                    hostname=configuration.hostname,
                    port=configuration.port,
                    system_id=configuration.system_id,
                    trust_profile_id=configuration.trust_profile_id,
                    credential_provider=lease.authorization_header,
                    timeout_seconds=self._timeout_seconds,
                    maximum_response_bytes=1_048_576,
                )
                client = HuaweiDoradoClient(
                    transport=transport,
                    system_id=configuration.system_id,
                    maximum_controllers=self._max_controllers,
                    maximum_response_bytes=1_048_576,
                )
                identity = await client.read_system_identity()
                controllers = await client.read_controller_health()
                return self._build_overview(
                    identity=identity,
                    controllers=controllers,
                    requested_at=requested_at,
                )
        except ConnectorConnectionTestError:
            return self._unavailable_overview(
                requested_at,
                reason="The Huawei Dorado credential reference is unavailable for this storage "
                "read.",
            )
        except HuaweiConnectorError as exc:
            return self._unavailable_overview(requested_at, reason=_connector_failure_reason(exc))
        except (TimeoutError, ValueError):
            return self._unavailable_overview(
                requested_at,
                reason="The configured Huawei Dorado storage read failed safely.",
            )

    def _build_overview(
        self,
        *,
        identity: HuaweiSystemIdentity,
        controllers: tuple[HuaweiControllerHealth, ...],
        requested_at: datetime,
    ) -> StorageOverview:
        asset_id = f"asset.storage.{_identity(identity.system_id)}"
        evidence: list[EvidenceRecord] = [
            EvidenceRecord(
                reference=reference,
                source="Huawei Dorado system-identity read",
                source_version=self._connector_version,
                observed_at=identity.observed_at,
                freshness=FreshnessState.CURRENT,
                trust_basis="Digest-only evidence from an allowlisted C1 DeviceManager response",
            )
            for reference in identity.evidence_references
        ]
        findings: list[HealthFinding] = []
        for controller in controllers:
            controller_evidence = tuple(
                EvidenceRecord(
                    reference=reference,
                    source="Huawei Dorado controller-health read",
                    source_version=self._connector_version,
                    observed_at=controller.observed_at,
                    freshness=FreshnessState.CURRENT,
                    trust_basis="Digest-only evidence from an allowlisted C1 DeviceManager "
                    "response",
                )
                for reference in controller.evidence_references
            )
            evidence.extend(controller_evidence)
            if controller.health_status is HuaweiHealthStatus.NORMAL:
                continue
            findings.append(
                HealthFinding(
                    finding_id=(
                        f"finding.storage.{_identity(identity.system_id, controller.controller_id)}"
                    ),
                    asset_id=asset_id,
                    severity=_FINDING_SEVERITY.get(
                        controller.health_status, FindingSeverity.UNKNOWN
                    ),
                    component=f"controller:{controller.controller_id}",
                    summary=(
                        f"Controller {controller.controller_id} ({controller.role}) reports "
                        f"health status '{controller.health_status.value}'."
                    ),
                    observed_at=controller.observed_at,
                    evidence_references=tuple(item.reference for item in controller_evidence),
                )
            )

        asset = StorageAsset(
            asset_id=asset_id,
            storage_device_id=identity.system_id,
            vendor="Huawei",
            model=identity.model,
            serial_number=identity.system_id,
            health=_ASSET_HEALTH_STATE.get(identity.health_status, StorageHealthState.UNKNOWN),
            observed_at=identity.observed_at,
            evidence_references=tuple(item.reference for item in evidence),
        )

        finding_count = len(findings)
        unknowns = (
            "No root cause or service-impact determination is made by this read-only check.",
            "No corroborating event-log or facility evidence is loaded in this scope.",
        )
        if finding_count:
            summary = (
                f"{finding_count} controller finding(s) were observed for {identity.model} in "
                "this scope."
            )
        else:
            summary = (
                f"No controller findings were observed for {identity.model} in this scope in the "
                "current read."
            )
        investigation_evidence = tuple(item.reference for item in evidence)
        investigation = StorageInvestigation(
            investigation_id=f"investigation.storage.{_identity(str(requested_at))}",
            title="Configured Huawei Dorado storage hardware read",
            state=InvestigationState.PROVISIONAL,
            summary=summary,
            hypotheses=(),
            unknowns=unknowns,
            next_checks=(
                "Repeat the read-only controller-health check to confirm persistence of any "
                "open finding.",
                "Review an authorized storage event-log source for the same observation window.",
            ),
            evidence_references=investigation_evidence,
            updated_at=requested_at,
        )
        confirmed_facts = (
            f"The Huawei Dorado system {identity.system_id} ({identity.model}) was read via the "
            "configured connector.",
            f"{finding_count} controller finding(s) at severity warning or higher were observed."
            if finding_count
            else "No controller reported a non-normal health status.",
        )
        report = StorageReport(
            report_id=f"report.storage.{_identity(str(requested_at))}",
            title="Configured Huawei Dorado storage hardware assessment",
            generated_at=requested_at,
            executive_summary=summary,
            confirmed_facts=confirmed_facts,
            provisional_findings=tuple(finding.summary for finding in findings),
            unknowns=unknowns,
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
            assets=(asset,),
            findings=tuple(findings),
            evidence=tuple(evidence),
            investigation=investigation,
            report=report,
        )

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
            "Storage asset health is unknown because no read-only Huawei Dorado connector read "
            "completed.",
        )
        investigation = StorageInvestigation(
            investigation_id=f"investigation.storage.{_identity(reason, str(requested_at))}",
            title="Configured Huawei Dorado storage hardware read",
            state=InvestigationState.INCONCLUSIVE,
            summary=(
                "Storage inventory and evidence could not be read from the configured Huawei "
                f"Dorado connector: {reason}"
            ),
            hypotheses=(),
            unknowns=unknowns,
            next_checks=(
                "Configure and enable exactly one read-only Huawei Dorado connector instance "
                "for this environment, including its system identifier.",
                "Allowlist the configured system as an active Huawei storage device in inventory.",
            ),
            evidence_references=(meta_reference,),
            updated_at=requested_at,
        )
        report = StorageReport(
            report_id=f"report.storage.{_identity(reason, str(requested_at))}",
            title="Configured Huawei Dorado storage hardware assessment",
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

    async def _system_is_allowlisted(self, system_id: str) -> bool:
        devices = await self._inventory_repository.list_scope(
            organization_id=self._organization_id,
            environment_id=self._environment_id,
            lifecycle=InventoryDeviceLifecycle.ACTIVE,
            query=None,
            limit=500,
        )
        return any(
            device.device_type is InventoryDeviceType.STORAGE
            and "huawei" in device.vendor.lower()
            and device.serial_number == system_id
            for device in devices
        )
