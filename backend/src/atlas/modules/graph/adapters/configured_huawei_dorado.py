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
from atlas.modules.connectors.vendors.huawei_dorado.manifest import PACKAGE_ID
from atlas.modules.graph.domain.models import (
    EntityType,
    FreshnessState,
    GraphEntity,
    GraphEvidence,
    GraphSnapshot,
)
from atlas.modules.inventory.application.ports import InventoryDeviceRepository
from atlas.modules.inventory.domain.devices import InventoryDeviceLifecycle, InventoryDeviceType

_DATA_PROFILE = "configured_huawei_dorado_read_only"
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
    "This graph reflects only the single Huawei Dorado storage system read from the configured "
    "connector; no volume, datastore, virtual machine, or business-service mapping is available "
    "because no CMDB or hypervisor connector is configured in this environment.",
    "Storage multipathing and SAN fabric redundancy are not represented by this connector.",
)


def _connector_failure_reason(exc: HuaweiConnectorError) -> str:
    code = exc.code if exc.code in _SAFE_CONNECTOR_ERROR_CODES else "connector_error"
    return f"The Huawei Dorado read failed safely ({code})."


def _identity(*parts: str) -> str:
    # Matches storage/adapters/configured_huawei_dorado._identity exactly, so a storage asset_id
    # and this graph entity_id agree for the same system_id.
    normalized = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()[:20]


class ConfiguredHuaweiDoradoGraphSnapshotProvider:
    """Serves a graph snapshot of the single storage system read from the configured, enabled
    Huawei Dorado MCP. Entities-only, mirroring ConfiguredHitachiGraphSnapshotProvider: this
    connector exposes no volume, datastore, virtual machine, or business-service data."""

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
        if configuration is None or configuration.system_id is None:
            return self._unavailable_snapshot(
                reason="A single active configured Huawei Dorado MCP with a system identifier "
                "is required to read the storage graph."
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
                    reason="The configured Huawei Dorado MCP must be enabled for read-only "
                    "storage polling."
                )
        if not await self._system_is_allowlisted(configuration.system_id):
            return self._unavailable_snapshot(
                reason="The configured Huawei Dorado system is not an active, allowlisted "
                "storage device in inventory."
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
                    maximum_response_bytes=1_048_576,
                )
                identity = await client.read_system_identity()
        except ConnectorConnectionTestError:
            return self._unavailable_snapshot(
                reason="The Huawei Dorado credential reference is unavailable for this graph read."
            )
        except HuaweiConnectorError as exc:
            return self._unavailable_snapshot(reason=_connector_failure_reason(exc))
        except (TimeoutError, ValueError):
            return self._unavailable_snapshot(
                reason="The configured Huawei Dorado graph read failed safely."
            )

        evidence_refs = tuple(
            f"evidence.graph.inventory.{reference}" for reference in identity.evidence_references
        )
        evidence = tuple(
            GraphEvidence(
                reference=reference,
                source="Huawei Dorado system-identity read",
                source_version=self._connector_version,
                observed_at=identity.observed_at,
                freshness=FreshnessState.FRESH,
                trust_basis=(
                    "Digest-only evidence from an allowlisted C1 DeviceManager response "
                    f"({source_reference})"
                ),
                classification=DataClassification.INTERNAL,
            )
            for reference, source_reference in zip(
                evidence_refs, identity.evidence_references, strict=True
            )
        )
        entity = GraphEntity(
            entity_id=f"asset.storage.{_identity(identity.system_id)}",
            entity_type=EntityType.STORAGE_SYSTEM,
            display_name=f"{identity.model} ({identity.system_id})",
            organization_id=self._organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
            domain_id="domain.storage_system",
            observed_at=identity.observed_at,
            valid_from=identity.observed_at,
            valid_to=None,
            freshness=FreshnessState.FRESH,
            confidence_basis=(
                "Read live from the configured Huawei Dorado system-identity capability."
            ),
            evidence_references=evidence_refs,
            classification=DataClassification.INTERNAL,
            allowed_principals=frozenset({"role.development.operator"}),
            vendor="Huawei",
            product="Huawei Dorado configured storage system",
            model=identity.model,
        )

        return GraphSnapshot(
            snapshot_id=f"snapshot.graph.{_identity(str(identity.observed_at))}",
            schema_version="1.0",
            organization_id=self._organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
            generated_at=identity.observed_at,
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
