from __future__ import annotations

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
from atlas.modules.connectors.vendors.huawei_dorado.client import HuaweiDoradoClient
from atlas.modules.connectors.vendors.huawei_dorado.manifest import PACKAGE_ID
from atlas.modules.health_checks.adapters.huawei_dorado import (
    CAPACITY_DEFINITION_ID,
    CONTROLLER_DEFINITION_ID,
    HuaweiCapacityHealthExecutor,
    HuaweiControllerHealthExecutor,
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


class ConfiguredHuaweiDoradoHealthExecutor:
    """Routes controller and capacity checks to one configured Huawei Dorado MCP and keeps other
    checks separate by delegating to a fallback executor, the same chain-of-responsibility shape
    as ConfiguredHitachiHealthExecutor and ConfiguredBrocadeSanNavHealthExecutor."""

    def __init__(
        self,
        *,
        configuration_repository: BundledConnectionConfigurationRepository,
        instance_repository: ConnectorInstanceRepository,
        inventory_repository: InventoryDeviceRepository,
        credential_materializer: ConnectorCredentialMaterializer,
        transport_factory: HuaweiConnectionTestTransportFactory,
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
        if definition.definition_id not in {CONTROLLER_DEFINITION_ID, CAPACITY_DEFINITION_ID}:
            return await self._fallback_executor.execute(definition, started_at=started_at)

        configuration = await self._single_active_configuration()
        if configuration is None or configuration.system_id is None:
            return self._unavailable(
                started_at,
                "A single active configured Huawei Dorado MCP with a system identifier is "
                "required for this health check.",
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
                    "The configured Huawei Dorado MCP must be enabled for read-only health "
                    "polling.",
                )
        if not await self._system_is_allowlisted(configuration.system_id):
            return self._unavailable(
                started_at,
                "The configured Huawei Dorado system is not an active, allowlisted storage "
                "device in inventory.",
            )

        try:
            async with self._credential_materializer.lease_authorization_header(
                secret_reference_id=configuration.secret_reference_id,
                maximum_lease_seconds=min(30, int(definition.limits.timeout_seconds) + 1),
            ) as lease:
                transport = self._transport_factory.create(
                    hostname=configuration.hostname,
                    port=configuration.port,
                    system_id=configuration.system_id,
                    trust_profile_id=configuration.trust_profile_id,
                    credential_provider=lease.authorization_header,
                    timeout_seconds=definition.limits.timeout_seconds,
                    maximum_response_bytes=1_048_576,
                )
                client = HuaweiDoradoClient(
                    transport=transport,
                    system_id=configuration.system_id,
                    maximum_response_bytes=1_048_576,
                )
                executor = (
                    HuaweiControllerHealthExecutor(client=client)
                    if definition.definition_id == CONTROLLER_DEFINITION_ID
                    else HuaweiCapacityHealthExecutor(client=client)
                )
                return await executor.execute(definition, started_at=started_at)
        except ConnectorConnectionTestError:
            return self._unavailable(
                started_at,
                "The Huawei Dorado credential reference is unavailable for this health check.",
            )
        except (TimeoutError, ValueError):
            return self._unavailable(
                started_at,
                "The configured Huawei Dorado health read failed safely.",
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
            unknowns=("Storage health remains unknown.",),
        )
