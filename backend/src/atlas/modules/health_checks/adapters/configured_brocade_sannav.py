from __future__ import annotations

import re
from datetime import datetime

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
from atlas.modules.connectors.vendors.brocade_sannav.client import BrocadeSanNavClient
from atlas.modules.connectors.vendors.brocade_sannav.manifest import (
    FABRIC_HEALTH_CAPABILITY_ID,
    PACKAGE_ID,
)
from atlas.modules.health_checks.adapters.brocade_sannav import (
    FABRIC_HEALTH_DEFINITION_ID,
    BrocadeFabricHealthExecutor,
)
from atlas.modules.health_checks.application.ports import (
    HealthCheckExecutionResult,
    HealthCheckExecutor,
)
from atlas.modules.health_checks.domain.models import (
    HealthCheckDefinition,
    HealthCheckRunState,
)
from atlas.modules.inventory.application.ports import InventoryDeviceRepository
from atlas.modules.inventory.domain.devices import (
    InventoryDeviceLifecycle,
    InventoryDeviceType,
)

_FABRIC_WWN = re.compile(r"^[0-9A-Fa-f:]{8,64}$")


class ConfiguredBrocadeSanNavHealthExecutor:
    """Routes the fabric-status check to one configured Brocade SANnav MCP and keeps other checks
    separate by delegating to a fallback executor -- the same chain-of-responsibility shape as
    ConfiguredHitachiHealthExecutor, so both vendors' real executors can be composed together."""

    def __init__(
        self,
        *,
        configuration_repository: BundledConnectionConfigurationRepository,
        instance_repository: ConnectorInstanceRepository,
        inventory_repository: InventoryDeviceRepository,
        credential_materializer: ConnectorCredentialMaterializer,
        transport_factory: BrocadeConnectionTestTransportFactory,
        fallback_executor: HealthCheckExecutor,
        organization_id: str,
        environment_id: str,
        runtime_state_repository: BundledConnectorRuntimeStateRepository | None = None,
    ) -> None:
        self._configuration_repository = configuration_repository
        self._instance_repository = instance_repository
        self._inventory_repository = inventory_repository
        self._credential_materializer = credential_materializer
        self._transport_factory = transport_factory
        self._fallback_executor = fallback_executor
        self._organization_id = organization_id
        self._environment_id = environment_id
        self._runtime_state_repository = runtime_state_repository

    async def execute(
        self, definition: HealthCheckDefinition, *, started_at: datetime
    ) -> HealthCheckExecutionResult:
        if definition.definition_id != FABRIC_HEALTH_DEFINITION_ID:
            return await self._fallback_executor.execute(definition, started_at=started_at)

        configuration = await self._single_active_configuration()
        if configuration is None:
            return self._unavailable(
                started_at,
                "A single active configured Brocade SANnav MCP is required for this health check.",
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
                return self._unavailable(
                    started_at,
                    "The configured Brocade SANnav MCP must be enabled for read-only fabric "
                    "polling.",
                )
        fabric_wwns = await self._allowed_fabric_wwns(definition)
        if not fabric_wwns:
            return self._unavailable(
                started_at,
                "No active Brocade fabric principal switch WWN is allowlisted in inventory.",
            )

        try:
            async with self._credential_materializer.lease_authorization_header(
                secret_reference_id=configuration.secret_reference_id,
                maximum_lease_seconds=min(30, int(definition.limits.timeout_seconds) + 1),
            ) as lease:
                transport = self._transport_factory.create(
                    hostname=configuration.hostname,
                    port=configuration.port,
                    trust_profile_id=configuration.trust_profile_id,
                    authorization_header_provider=lease.authorization_header,
                    timeout_seconds=definition.limits.timeout_seconds,
                    maximum_response_bytes=1_048_576,
                )
                client = BrocadeSanNavClient(
                    transport=transport,
                    allowed_fabric_wwns=fabric_wwns,
                    maximum_fabrics=500,
                    maximum_switches_per_fabric=500,
                    maximum_response_bytes=1_048_576,
                )
                executor = BrocadeFabricHealthExecutor(
                    client=client, capability_id=FABRIC_HEALTH_CAPABILITY_ID
                )
                return await executor.execute(definition, started_at=started_at)
        except ConnectorConnectionTestError:
            return self._unavailable(
                started_at,
                "The Brocade SANnav credential reference is unavailable for this health check.",
            )
        except (TimeoutError, ValueError):
            return self._unavailable(
                started_at,
                "The configured Brocade SANnav health read failed safely.",
            )

    async def _single_active_configuration(
        self,
    ) -> BundledConnectionConfiguration | None:
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

    async def _allowed_fabric_wwns(self, definition: HealthCheckDefinition) -> frozenset[str]:
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
        return frozenset(tuple(identifiers)[: definition.limits.max_targets])

    @staticmethod
    def _unavailable(started_at: datetime, reason: str) -> HealthCheckExecutionResult:
        return HealthCheckExecutionResult(
            state=HealthCheckRunState.FAILED,
            completed_at=started_at,
            step_count=0,
            observations=(),
            findings=(),
            evidence=(),
            partial_reasons=(reason,),
            unknowns=("Fabric health remains unknown.",),
        )
