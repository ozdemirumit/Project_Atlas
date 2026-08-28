from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

from atlas.core.classification import DataClassification
from atlas.modules.connectors.application.bundled_connection_configuration_ports import (
    BundledConnectionConfigurationRepository,
)
from atlas.modules.connectors.application.bundled_runtime_state_ports import (
    BundledConnectorRuntimeStateRepository,
)
from atlas.modules.connectors.application.connection_test_ports import (
    BrocadeConnectionTestTransportFactory,
    ConnectorConnectionTestError,
    ConnectorCredentialMaterializer,
)
from atlas.modules.connectors.application.instance_creation_ports import (
    ConnectorInstanceRepository,
)
from atlas.modules.connectors.domain.bundled_connection_configuration import (
    BundledConnectionConfiguration,
)
from atlas.modules.connectors.domain.bundled_runtime_state import ENABLED_READ_ONLY
from atlas.modules.connectors.domain.instance_creation import DISABLED_UNCONFIGURED
from atlas.modules.connectors.vendors.brocade_sannav.client import (
    BrocadeConnectorError,
    BrocadeSanNavClient,
)
from atlas.modules.connectors.vendors.brocade_sannav.manifest import PACKAGE_ID
from atlas.modules.graph.domain.models import (
    EntityType,
    FreshnessState,
    GraphEntity,
    GraphEvidence,
    GraphSnapshot,
)
from atlas.modules.inventory.application.ports import InventoryDeviceRepository
from atlas.modules.inventory.domain.devices import InventoryDeviceLifecycle, InventoryDeviceType

_FABRIC_WWN = re.compile(r"^[0-9A-Fa-f:]{8,64}$")
_MAX_ALLOWED_FABRIC_TARGETS = 25
_DATA_PROFILE = "configured_brocade_sannav_read_only"
_SAFE_CONNECTOR_ERROR_CODES = frozenset(
    {
        "invalid_fabric_identifier",
        "malformed_vendor_response",
        "target_not_bound",
        "target_timeout",
        "target_unavailable",
        "vendor_permission_denied",
        "vendor_rate_limited",
        "vendor_response_limit_exceeded",
    }
)

_KNOWN_GAPS = (
    "This graph reflects only the SAN fabric switches read from the configured Brocade SANnav "
    "connector; no per-port, zoning, or firmware detail is available, and no relationship to "
    "storage systems or hosts is asserted because no shared identifier between this connector "
    "and the storage/hypervisor connectors is confirmed.",
    "Multipathing redundancy across fabrics is not represented; only switch presence within an "
    "allowlisted fabric is reported.",
)


def _connector_failure_reason(exc: BrocadeConnectorError) -> str:
    code = exc.code if exc.code in _SAFE_CONNECTOR_ERROR_CODES else "connector_error"
    return f"The Brocade SANnav read failed safely ({code})."


def _identity(*parts: str) -> str:
    normalized = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()[:20]


class ConfiguredBrocadeSanNavGraphSnapshotProvider:
    """Serves a graph snapshot of the SAN switches read from the single configured, enabled
    Brocade SANnav MCP. Deliberately entities-only: this connector exposes no zoning, port, or
    upstream/downstream relationship data, so no relationship is fabricated. See ATLAS-IMP-261.
    """

    def __init__(
        self,
        *,
        configuration_repository: BundledConnectionConfigurationRepository,
        instance_repository: ConnectorInstanceRepository,
        inventory_repository: InventoryDeviceRepository,
        credential_materializer: ConnectorCredentialMaterializer,
        transport_factory: BrocadeConnectionTestTransportFactory,
        organization_id: str,
        environment_id: str,
        site_id: str = "site.local",
        connector_version: str = "0.1.0",
        runtime_state_repository: BundledConnectorRuntimeStateRepository | None = None,
        max_targets: int = _MAX_ALLOWED_FABRIC_TARGETS,
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
        self._max_targets = max_targets
        self._timeout_seconds = timeout_seconds

    async def get_snapshot(self) -> GraphSnapshot:
        configuration = await self._single_active_configuration()
        if configuration is None:
            return self._unavailable_snapshot(
                reason="A single active configured Brocade SANnav MCP is required to read the "
                "fabric graph."
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
                    reason="The configured Brocade SANnav MCP must be enabled for read-only "
                    "fabric polling."
                )
        fabric_wwns = await self._allowed_fabric_wwns()
        if not fabric_wwns:
            return self._unavailable_snapshot(
                reason="No active Brocade fabric principal switch WWN is allowlisted in inventory."
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
                client = BrocadeSanNavClient(
                    transport=transport,
                    allowed_fabric_wwns=fabric_wwns,
                    maximum_fabrics=500,
                    maximum_switches_per_fabric=500,
                    maximum_response_bytes=1_048_576,
                )
                inventory = await client.read_inventory()
        except ConnectorConnectionTestError:
            return self._unavailable_snapshot(
                reason="The Brocade SANnav credential reference is unavailable for this graph read."
            )
        except BrocadeConnectorError as exc:
            return self._unavailable_snapshot(reason=_connector_failure_reason(exc))
        except (TimeoutError, ValueError):
            return self._unavailable_snapshot(
                reason="The configured Brocade SANnav graph read failed safely."
            )

        entities: list[GraphEntity] = []
        evidence: list[GraphEvidence] = []
        evidence_refs = tuple(
            f"evidence.graph.inventory.{reference}" for reference in inventory.evidence_references
        )
        for reference, source_reference in zip(
            evidence_refs, inventory.evidence_references, strict=True
        ):
            evidence.append(
                GraphEvidence(
                    reference=reference,
                    source="Brocade SANnav fabric-inventory read",
                    source_version=self._connector_version,
                    observed_at=inventory.observed_at,
                    freshness=FreshnessState.FRESH,
                    trust_basis=(
                        "Digest-only evidence from an allowlisted C1 HTTPS GET response "
                        f"({source_reference})"
                    ),
                    classification=DataClassification.INTERNAL,
                )
            )
        for switch in inventory.switches[: self._max_targets]:
            entities.append(
                GraphEntity(
                    entity_id=(
                        "asset.san_switch."
                        f"{_identity(switch.fabric_principal_switch_wwn, switch.ip_address)}"
                    ),
                    entity_type=EntityType.SAN_SWITCH,
                    display_name=f"SAN switch ({switch.ip_address})",
                    organization_id=self._organization_id,
                    environment_id=self._environment_id,
                    site_id=self._site_id,
                    domain_id="domain.san_switch",
                    observed_at=inventory.observed_at,
                    valid_from=inventory.observed_at,
                    valid_to=None,
                    freshness=FreshnessState.FRESH,
                    confidence_basis=(
                        "Read live from the configured Brocade SANnav fabric-inventory capability."
                    ),
                    evidence_references=evidence_refs,
                    classification=DataClassification.INTERNAL,
                    allowed_principals=frozenset({"role.development.operator"}),
                    vendor="Broadcom (Brocade)",
                    product="Brocade SANnav-discovered fabric switch",
                    model=None,
                )
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
            entities=tuple(entities),
            relationships=(),
            observations=(),
            evidence=tuple(evidence),
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

    async def _allowed_fabric_wwns(self) -> frozenset[str]:
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
            if device.device_type is InventoryDeviceType.SAN_SWITCH
            and "brocade" in device.vendor.lower()
            and device.serial_number is not None
            and _FABRIC_WWN.fullmatch(device.serial_number)
        )
        return frozenset(tuple(identifiers)[: self._max_targets])
