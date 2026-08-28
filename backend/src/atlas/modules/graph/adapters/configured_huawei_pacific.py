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
from atlas.modules.connectors.vendors.huawei_pacific.manifest import PACKAGE_ID
from atlas.modules.graph.domain.models import (
    EntityType,
    FreshnessState,
    GraphEntity,
    GraphEvidence,
    GraphSnapshot,
)
from atlas.modules.inventory.application.ports import InventoryDeviceRepository
from atlas.modules.inventory.domain.devices import InventoryDeviceLifecycle, InventoryDeviceType

_DATA_PROFILE = "configured_huawei_pacific_read_only"
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

_KNOWN_GAPS = (
    "This graph reflects only the single Huawei Pacific storage cluster read from the configured "
    "connector, represented as one storage system entity; no volume, datastore, virtual machine, "
    "or business-service mapping is available because no CMDB or hypervisor connector is "
    "configured in this environment.",
    "No confirmed cluster-level identifier field exists in this connector's source (only "
    "per-node identifiers), so the entity identity is derived from the sorted set of node "
    "identifiers rather than a vendor-issued cluster id.",
)


def _connector_failure_reason(exc: HuaweiPacificConnectorError) -> str:
    code = exc.code if exc.code in _SAFE_CONNECTOR_ERROR_CODES else "connector_error"
    return f"The Huawei Pacific read failed safely ({code})."


def _identity(*parts: str) -> str:
    normalized = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()[:20]


class ConfiguredHuaweiPacificGraphSnapshotProvider:
    """Serves a graph snapshot of the single storage cluster read from the configured, enabled
    Huawei Pacific MCP, represented as one storage_system entity. Entities-only, mirroring every
    other Configured<Vendor>GraphSnapshotProvider in this project: no relationship is fabricated.
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
                reason="A single active configured Huawei Pacific MCP is required to read the "
                "cluster graph."
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
                    reason="The configured Huawei Pacific MCP must be enabled for read-only "
                    "cluster polling."
                )
        if not await self._cluster_is_allowlisted():
            return self._unavailable_snapshot(
                reason="No active Huawei Pacific storage cluster is allowlisted in inventory."
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
        except ConnectorConnectionTestError:
            return self._unavailable_snapshot(
                reason="The Huawei Pacific credential reference is unavailable for this graph read."
            )
        except HuaweiPacificConnectorError as exc:
            return self._unavailable_snapshot(reason=_connector_failure_reason(exc))
        except (TimeoutError, ValueError):
            return self._unavailable_snapshot(
                reason="The configured Huawei Pacific graph read failed safely."
            )
        if not inventory.nodes:
            return self._unavailable_snapshot(
                reason="The configured Huawei Pacific cluster returned no nodes."
            )

        cluster_identity = _identity(*sorted(node.node_id for node in inventory.nodes))
        evidence_refs = tuple(
            f"evidence.graph.inventory.{reference}" for reference in inventory.evidence_references
        )
        evidence = tuple(
            GraphEvidence(
                reference=reference,
                source="Huawei Pacific cluster-node read",
                source_version=self._connector_version,
                observed_at=inventory.observed_at,
                freshness=FreshnessState.FRESH,
                trust_basis=(
                    "Digest-only evidence from an allowlisted C1 cluster-manager response "
                    f"({source_reference})"
                ),
                classification=DataClassification.INTERNAL,
            )
            for reference, source_reference in zip(
                evidence_refs, inventory.evidence_references, strict=True
            )
        )
        entity = GraphEntity(
            entity_id=f"asset.storage.{cluster_identity}",
            entity_type=EntityType.STORAGE_SYSTEM,
            display_name=f"Huawei Pacific cluster ({len(inventory.nodes)} node(s))",
            organization_id=self._organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
            domain_id="domain.storage_system",
            observed_at=inventory.observed_at,
            valid_from=inventory.observed_at,
            valid_to=None,
            freshness=FreshnessState.FRESH,
            confidence_basis=(
                "Read live from the configured Huawei Pacific cluster-node capability."
            ),
            evidence_references=evidence_refs,
            classification=DataClassification.INTERNAL,
            allowed_principals=frozenset({"role.development.operator"}),
            vendor="Huawei",
            product="Huawei Pacific configured storage cluster",
            model=inventory.nodes[0].model,
        )

        return GraphSnapshot(
            snapshot_id=f"snapshot.graph.{_identity(str(inventory.observed_at))}",
            schema_version="1.0",
            organization_id=self._organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
            generated_at=inventory.observed_at,
            freshness=FreshnessState.FRESH,
            completeness="partial",
            entities=(entity,),
            relationships=(),
            observations=(),
            evidence=evidence,
            known_gaps=_KNOWN_GAPS,
            data_profile=_DATA_PROFILE,
        )

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
