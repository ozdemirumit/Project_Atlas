from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from atlas.core.classification import DataClassification
from atlas.modules.connectors.application.bundled_connection_configuration_ports import (
    BundledConnectionConfigurationRepository,
)
from atlas.modules.connectors.application.bundled_runtime_state_ports import (
    BundledConnectorRuntimeStateRepository,
)
from atlas.modules.connectors.application.connection_test_ports import (
    ConnectorConnectionTestError,
    ConnectorCredentialMaterializer,
    VCenterConnectionTestTransportFactory,
)
from atlas.modules.connectors.application.instance_creation_ports import (
    ConnectorInstanceRepository,
)
from atlas.modules.connectors.domain.bundled_connection_configuration import (
    BundledConnectionConfiguration,
)
from atlas.modules.connectors.domain.bundled_runtime_state import ENABLED_READ_ONLY
from atlas.modules.connectors.domain.instance_creation import DISABLED_UNCONFIGURED
from atlas.modules.connectors.vendors.vcenter.client import VCenterClient, VCenterConnectorError
from atlas.modules.connectors.vendors.vcenter.domain import (
    VCenterClusterInventoryResult,
    VCenterHostInventoryResult,
    VCenterVmInventoryResult,
)
from atlas.modules.connectors.vendors.vcenter.manifest import PACKAGE_ID
from atlas.modules.graph.domain.models import (
    EntityType,
    FreshnessState,
    GraphEntity,
    GraphEvidence,
    GraphSnapshot,
)
from atlas.modules.inventory.application.ports import InventoryDeviceRepository
from atlas.modules.inventory.domain.devices import InventoryDeviceLifecycle, InventoryDeviceType

_DATA_PROFILE = "configured_vcenter_read_only"
_SAFE_CONNECTOR_ERROR_CODES = frozenset(
    {
        "malformed_vendor_response",
        "target_timeout",
        "target_unavailable",
        "vendor_permission_denied",
        "vendor_rate_limited",
        "vendor_response_limit_exceeded",
    }
)
_KNOWN_GAPS = (
    "This graph reflects only the hosts, clusters, and virtual machines read from the configured "
    "vCenter connector; no host-to-cluster membership or VM-to-host placement relationship is "
    "asserted, because vCenter's confirmed list responses (GET /api/vcenter/host, "
    "/api/vcenter/cluster, /api/vcenter/vm) carry no parent-cluster or running-host field on "
    "each summary item -- only per-item filter parameters, which this first pass does not yet "
    "call per-entity to resolve.",
    "No datastore, network, or resource-pool entity or relationship is represented; only host, "
    "cluster, and virtual machine inventory is read.",
    "No relationship to storage systems or SAN fabrics is asserted because no shared identifier "
    "between this connector and the storage/fabric connectors is confirmed.",
)


def _connector_failure_reason(exc: VCenterConnectorError) -> str:
    code = exc.code if exc.code in _SAFE_CONNECTOR_ERROR_CODES else "connector_error"
    return f"The vCenter read failed safely ({code})."


def _identity(*parts: str) -> str:
    normalized = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()[:20]


class ConfiguredVCenterGraphSnapshotProvider:
    """Serves a graph snapshot of the hosts, clusters, and virtual machines read from the single
    configured, enabled vCenter MCP. Deliberately entities-only, mirroring
    ConfiguredBrocadeSanNavGraphSnapshotProvider's precedent: this first pass exposes no confirmed
    cross-entity relationship field, so none is fabricated. See ATLAS-IMP-266.
    """

    def __init__(
        self,
        *,
        configuration_repository: BundledConnectionConfigurationRepository,
        instance_repository: ConnectorInstanceRepository,
        inventory_repository: InventoryDeviceRepository,
        credential_materializer: ConnectorCredentialMaterializer,
        transport_factory: VCenterConnectionTestTransportFactory,
        organization_id: str,
        environment_id: str,
        site_id: str = "site.local",
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
        self._connector_version = connector_version
        self._runtime_state_repository = runtime_state_repository
        self._timeout_seconds = timeout_seconds

    async def get_snapshot(self) -> GraphSnapshot:
        configuration = await self._single_active_configuration()
        if configuration is None:
            return self._unavailable_snapshot(
                reason="A single active configured vCenter MCP is required to read the "
                "hypervisor graph."
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
                return self._unavailable_snapshot(
                    reason="The configured vCenter MCP must be enabled for read-only "
                    "hypervisor polling."
                )
        if not await self._vcenter_is_allowlisted():
            return self._unavailable_snapshot(
                reason="No active vCenter Server is allowlisted in inventory."
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
                client = VCenterClient(transport=transport, maximum_response_bytes=1_048_576)
                hosts = await client.read_host_inventory()
                clusters = await client.read_cluster_inventory()
                vms = await client.read_vm_inventory()
        except ConnectorConnectionTestError:
            return self._unavailable_snapshot(
                reason="The vCenter credential reference is unavailable for this graph read."
            )
        except VCenterConnectorError as exc:
            return self._unavailable_snapshot(reason=_connector_failure_reason(exc))
        except (TimeoutError, ValueError):
            return self._unavailable_snapshot(
                reason="The configured vCenter graph read failed safely."
            )

        observed_at = hosts.observed_at
        evidence = self._build_evidence(hosts, clusters, vms)
        evidence_refs = tuple(item.reference for item in evidence)

        entities: list[GraphEntity] = []
        entities.extend(self._host_entities(hosts, evidence_refs))
        entities.extend(self._cluster_entities(clusters, evidence_refs))
        entities.extend(self._vm_entities(vms, evidence_refs))

        return GraphSnapshot(
            snapshot_id=f"snapshot.graph.{_identity(str(observed_at))}",
            schema_version="1.0",
            organization_id=self._organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
            generated_at=observed_at,
            freshness=FreshnessState.FRESH,
            completeness="partial",
            entities=tuple(entities),
            relationships=(),
            observations=(),
            evidence=tuple(evidence),
            known_gaps=_KNOWN_GAPS,
            data_profile=_DATA_PROFILE,
        )

    def _build_evidence(
        self,
        hosts: VCenterHostInventoryResult,
        clusters: VCenterClusterInventoryResult,
        vms: VCenterVmInventoryResult,
    ) -> list[GraphEvidence]:
        evidence: list[GraphEvidence] = []
        for kind, result in (
            ("host", hosts),
            ("cluster", clusters),
            ("vm", vms),
        ):
            for source_reference in result.evidence_references:
                evidence.append(
                    GraphEvidence(
                        reference=f"evidence.graph.{kind}.{source_reference}",
                        source=f"vCenter {kind} inventory read",
                        source_version=self._connector_version,
                        observed_at=result.observed_at,
                        freshness=FreshnessState.FRESH,
                        trust_basis=(
                            "Digest-only evidence from an allowlisted C1 vSphere Automation API "
                            f"response ({source_reference})"
                        ),
                        classification=DataClassification.INTERNAL,
                    )
                )
        return evidence

    def _host_entities(
        self, hosts: VCenterHostInventoryResult, evidence_refs: tuple[str, ...]
    ) -> list[GraphEntity]:
        host_evidence_refs = tuple(
            ref for ref in evidence_refs if ref.startswith("evidence.graph.host.")
        )
        return [
            GraphEntity(
                entity_id=f"asset.hypervisor_host.{_identity(host.host_id)}",
                entity_type=EntityType.HYPERVISOR_HOST,
                display_name=host.name,
                organization_id=self._organization_id,
                environment_id=self._environment_id,
                site_id=self._site_id,
                domain_id="domain.hypervisor_host",
                observed_at=hosts.observed_at,
                valid_from=hosts.observed_at,
                valid_to=None,
                freshness=FreshnessState.FRESH,
                confidence_basis="Read live from the configured vCenter host-inventory capability.",
                evidence_references=host_evidence_refs,
                classification=DataClassification.INTERNAL,
                allowed_principals=frozenset({"role.development.operator"}),
                vendor="VMware",
                product="ESXi host",
                model=None,
                lifecycle_state=(
                    "active" if host.connection_state.value == "CONNECTED" else "degraded"
                ),
            )
            for host in hosts.hosts
        ]

    def _cluster_entities(
        self, clusters: VCenterClusterInventoryResult, evidence_refs: tuple[str, ...]
    ) -> list[GraphEntity]:
        cluster_evidence_refs = tuple(
            ref for ref in evidence_refs if ref.startswith("evidence.graph.cluster.")
        )
        return [
            GraphEntity(
                entity_id=f"asset.hypervisor_cluster.{_identity(cluster.cluster_id)}",
                entity_type=EntityType.HYPERVISOR_CLUSTER,
                display_name=cluster.name,
                organization_id=self._organization_id,
                environment_id=self._environment_id,
                site_id=self._site_id,
                domain_id="domain.hypervisor_cluster",
                observed_at=clusters.observed_at,
                valid_from=clusters.observed_at,
                valid_to=None,
                freshness=FreshnessState.FRESH,
                confidence_basis=(
                    "Read live from the configured vCenter cluster-inventory capability."
                ),
                evidence_references=cluster_evidence_refs,
                classification=DataClassification.INTERNAL,
                allowed_principals=frozenset({"role.development.operator"}),
                vendor="VMware",
                product="vSphere compute cluster",
                model=None,
            )
            for cluster in clusters.clusters
        ]

    def _vm_entities(
        self, vms: VCenterVmInventoryResult, evidence_refs: tuple[str, ...]
    ) -> list[GraphEntity]:
        vm_evidence_refs = tuple(
            ref for ref in evidence_refs if ref.startswith("evidence.graph.vm.")
        )
        return [
            GraphEntity(
                entity_id=f"asset.virtual_machine.{_identity(vm.vm_id)}",
                entity_type=EntityType.VIRTUAL_MACHINE,
                display_name=vm.name,
                organization_id=self._organization_id,
                environment_id=self._environment_id,
                site_id=self._site_id,
                domain_id="domain.virtual_machine",
                observed_at=vms.observed_at,
                valid_from=vms.observed_at,
                valid_to=None,
                freshness=FreshnessState.FRESH,
                confidence_basis="Read live from the configured vCenter VM-inventory capability.",
                evidence_references=vm_evidence_refs,
                classification=DataClassification.INTERNAL,
                allowed_principals=frozenset({"role.development.operator"}),
                vendor="VMware",
                product="virtual machine",
                model=None,
                lifecycle_state=("active" if vm.power_state.value == "POWERED_ON" else "inactive"),
            )
            for vm in vms.virtual_machines
        ]

    def _unavailable_snapshot(self, *, reason: str) -> GraphSnapshot:
        requested_at = datetime.now(UTC)
        return GraphSnapshot(
            snapshot_id=f"snapshot.graph.{_identity(reason, requested_at.isoformat())}",
            schema_version="1.0",
            organization_id=self._organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
            generated_at=requested_at,
            freshness=FreshnessState.UNKNOWN,
            completeness="unavailable",
            entities=(),
            relationships=(),
            observations=(),
            evidence=(),
            known_gaps=(reason, *_KNOWN_GAPS),
            data_profile=_DATA_PROFILE,
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

    async def _vcenter_is_allowlisted(self) -> bool:
        devices = await self._inventory_repository.list_scope(
            organization_id=self._organization_id,
            environment_id=self._environment_id,
            lifecycle=InventoryDeviceLifecycle.ACTIVE,
            query=None,
            limit=500,
        )
        return any(
            device.device_type is InventoryDeviceType.VIRTUALIZATION
            and "vmware" in device.vendor.lower()
            for device in devices
        )
