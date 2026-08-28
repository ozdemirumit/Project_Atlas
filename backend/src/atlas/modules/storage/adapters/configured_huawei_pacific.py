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
    HuaweiPacificConnectionTestTransportFactory,
)
from atlas.modules.connectors.application.instance_creation_ports import (
    ConnectorInstanceRepository,
)
from atlas.modules.connectors.domain.bundled_connection_configuration import (
    BundledConnectionConfiguration,
)
from atlas.modules.connectors.domain.bundled_runtime_state import ENABLED_READ_ONLY
from atlas.modules.connectors.domain.instance_creation import DISABLED_UNCONFIGURED
from atlas.modules.connectors.vendors.huawei_pacific.client import (
    HuaweiPacificClient,
    HuaweiPacificConnectorError,
)
from atlas.modules.connectors.vendors.huawei_pacific.domain import (
    HuaweiPacificClusterInventoryResult,
    HuaweiPacificNodeRunningStatus,
)
from atlas.modules.connectors.vendors.huawei_pacific.manifest import PACKAGE_ID
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

_DATA_PROFILE = "configured_huawei_pacific_read_only"
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
_ASSET_HEALTH_STATE: dict[HuaweiPacificNodeRunningStatus, StorageHealthState] = {
    HuaweiPacificNodeRunningStatus.ONLINE: StorageHealthState.HEALTHY,
    HuaweiPacificNodeRunningStatus.OFFLINE: StorageHealthState.CRITICAL,
    HuaweiPacificNodeRunningStatus.UNKNOWN: StorageHealthState.UNKNOWN,
}
_FINDING_SEVERITY: dict[HuaweiPacificNodeRunningStatus, FindingSeverity] = {
    HuaweiPacificNodeRunningStatus.OFFLINE: FindingSeverity.CRITICAL,
    HuaweiPacificNodeRunningStatus.UNKNOWN: FindingSeverity.UNKNOWN,
}


def _connector_failure_reason(exc: HuaweiPacificConnectorError) -> str:
    code = exc.code if exc.code in _SAFE_CONNECTOR_ERROR_CODES else "connector_error"
    return f"The Huawei Pacific read failed safely ({code})."


def _identity(*parts: str) -> str:
    # Matches the graph/health_checks Huawei Pacific adapters' identity scheme exactly.
    normalized = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()[:20]


class ConfiguredHuaweiPacificStorageProvider:
    """Serves the storage overview from the single configured, enabled Huawei Pacific MCP.

    Represents the whole cluster as one StorageAsset (mirroring the graph adapter's one
    storage_system entity), with per-node findings -- there is no confirmed cluster-level
    identifier, so identity is derived from the sorted set of node identifiers.
    """

    def __init__(
        self,
        *,
        configuration_repository: BundledConnectionConfigurationRepository,
        instance_repository: ConnectorInstanceRepository,
        inventory_repository: InventoryDeviceRepository,
        credential_materializer: ConnectorCredentialMaterializer,
        transport_factory: HuaweiPacificConnectionTestTransportFactory,
        organization_id: str,
        environment_id: str,
        site_id: str = "site.local",
        target_id: str = "target.huawei.pacific.configured",
        connector_version: str = "0.1.0",
        runtime_state_repository: BundledConnectorRuntimeStateRepository | None = None,
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
        self._timeout_seconds = timeout_seconds

    async def get_overview(self, *, requested_at: datetime) -> StorageOverview:
        configuration = await self._single_active_configuration()
        if configuration is None:
            return self._unavailable_overview(
                requested_at,
                reason="A single active configured Huawei Pacific MCP is required to read "
                "cluster inventory.",
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
                    reason="The configured Huawei Pacific MCP must be enabled for read-only "
                    "cluster polling.",
                )
        if not await self._cluster_is_allowlisted():
            return self._unavailable_overview(
                requested_at,
                reason="No active Huawei Pacific storage cluster is allowlisted in inventory.",
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
                    credential_provider=lease.authorization_header,
                    timeout_seconds=self._timeout_seconds,
                    maximum_response_bytes=1_048_576,
                )
                client = HuaweiPacificClient(transport=transport, maximum_response_bytes=1_048_576)
                inventory = await client.read_cluster_inventory()
                if not inventory.nodes:
                    return self._unavailable_overview(
                        requested_at,
                        reason="The configured Huawei Pacific cluster returned no nodes.",
                    )
                return self._build_overview(inventory=inventory, requested_at=requested_at)
        except ConnectorConnectionTestError:
            return self._unavailable_overview(
                requested_at,
                reason="The Huawei Pacific credential reference is unavailable for this storage "
                "read.",
            )
        except HuaweiPacificConnectorError as exc:
            return self._unavailable_overview(requested_at, reason=_connector_failure_reason(exc))
        except (TimeoutError, ValueError):
            return self._unavailable_overview(
                requested_at,
                reason="The configured Huawei Pacific storage read failed safely.",
            )

    def _build_overview(
        self,
        *,
        inventory: HuaweiPacificClusterInventoryResult,
        requested_at: datetime,
    ) -> StorageOverview:
        cluster_identity = _identity(*sorted(node.node_id for node in inventory.nodes))
        asset_id = f"asset.storage.{cluster_identity}"
        evidence = [
            EvidenceRecord(
                reference=reference,
                source="Huawei Pacific cluster-node read",
                source_version=self._connector_version,
                observed_at=inventory.observed_at,
                freshness=FreshnessState.CURRENT,
                trust_basis="Digest-only evidence from an allowlisted C1 cluster-manager response",
            )
            for reference in inventory.evidence_references
        ]
        findings: list[HealthFinding] = []
        worst_health = StorageHealthState.HEALTHY
        for node in inventory.nodes:
            health = _ASSET_HEALTH_STATE.get(node.running_status, StorageHealthState.UNKNOWN)
            if _health_rank(health) > _health_rank(worst_health):
                worst_health = health
            if node.running_status is HuaweiPacificNodeRunningStatus.ONLINE:
                continue
            findings.append(
                HealthFinding(
                    finding_id=f"finding.storage.{_identity(cluster_identity, node.node_id)}",
                    asset_id=asset_id,
                    severity=_FINDING_SEVERITY.get(node.running_status, FindingSeverity.UNKNOWN),
                    component=f"node:{node.node_id}",
                    summary=(
                        f"Node {node.node_id} ({node.name}) reports running status "
                        f"'{node.running_status.value}'."
                    ),
                    observed_at=inventory.observed_at,
                    evidence_references=tuple(item.reference for item in evidence),
                )
            )

        asset = StorageAsset(
            asset_id=asset_id,
            storage_device_id=cluster_identity,
            vendor="Huawei",
            model=inventory.nodes[0].model,
            serial_number=cluster_identity,
            health=worst_health,
            observed_at=inventory.observed_at,
            evidence_references=tuple(item.reference for item in evidence),
        )

        finding_count = len(findings)
        unknowns = (
            "No root cause or service-impact determination is made by this read-only check.",
            "No corroborating event-log or facility evidence is loaded in this scope.",
        )
        if finding_count:
            summary = (
                f"{finding_count} node finding(s) were observed across {len(inventory.nodes)} "
                "cluster node(s) in this scope."
            )
        else:
            summary = (
                f"No node findings were observed across {len(inventory.nodes)} cluster node(s) "
                "in this scope in the current read."
            )
        investigation_evidence = tuple(item.reference for item in evidence)
        investigation = StorageInvestigation(
            investigation_id=f"investigation.storage.{_identity(str(requested_at))}",
            title="Configured Huawei Pacific cluster read",
            state=InvestigationState.PROVISIONAL,
            summary=summary,
            hypotheses=(),
            unknowns=unknowns,
            next_checks=(
                "Repeat the read-only cluster-node check to confirm persistence of any open "
                "finding.",
                "Review an authorized storage event-log source for the same observation window.",
            ),
            evidence_references=investigation_evidence,
            updated_at=requested_at,
        )
        confirmed_facts = (
            f"The Huawei Pacific cluster ({len(inventory.nodes)} node(s)) was read via the "
            "configured connector.",
            f"{finding_count} node finding(s) at severity warning or higher were observed."
            if finding_count
            else "No node reported a non-normal running status.",
        )
        report = StorageReport(
            report_id=f"report.storage.{_identity(str(requested_at))}",
            title="Configured Huawei Pacific cluster assessment",
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
            "Cluster asset health is unknown because no read-only Huawei Pacific connector read "
            "completed.",
        )
        investigation = StorageInvestigation(
            investigation_id=f"investigation.storage.{_identity(reason, str(requested_at))}",
            title="Configured Huawei Pacific cluster read",
            state=InvestigationState.INCONCLUSIVE,
            summary=(
                "Cluster inventory and evidence could not be read from the configured Huawei "
                f"Pacific connector: {reason}"
            ),
            hypotheses=(),
            unknowns=unknowns,
            next_checks=(
                "Configure and enable exactly one read-only Huawei Pacific connector instance "
                "for this environment.",
                "Allowlist an active Huawei storage cluster device in inventory.",
            ),
            evidence_references=(meta_reference,),
            updated_at=requested_at,
        )
        report = StorageReport(
            report_id=f"report.storage.{_identity(reason, str(requested_at))}",
            title="Configured Huawei Pacific cluster assessment",
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

    async def _cluster_is_allowlisted(self) -> bool:
        devices = await self._inventory_repository.list_scope(
            organization_id=self._organization_id,
            environment_id=self._environment_id,
            lifecycle=InventoryDeviceLifecycle.ACTIVE,
            query=None,
            limit=500,
        )
        return any(
            device.device_type is InventoryDeviceType.STORAGE and "huawei" in device.vendor.lower()
            for device in devices
        )


def _health_rank(state: StorageHealthState) -> int:
    return {
        StorageHealthState.HEALTHY: 0,
        StorageHealthState.WARNING: 1,
        StorageHealthState.UNKNOWN: 2,
        StorageHealthState.CRITICAL: 3,
    }[state]
