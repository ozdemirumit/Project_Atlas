from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.connectors.application.bundled_connection_configuration_ports import (
    BundledConnectionConfigurationRepository,
)
from atlas.modules.connectors.application.bundled_runtime_state_ports import (
    BundledConnectorRuntimeStateError,
    BundledConnectorRuntimeStateRepository,
)
from atlas.modules.connectors.application.connection_test_ports import (
    ConnectorConnectionTestResultRepository,
)
from atlas.modules.connectors.application.instance_creation_ports import (
    ConnectorInstanceRepository,
)
from atlas.modules.connectors.domain.bundled_runtime_state import (
    DISABLED,
    ENABLED_READ_ONLY,
    BundledConnectorRuntimeState,
)
from atlas.modules.connectors.domain.instance_creation import DISABLED_UNCONFIGURED
from atlas.modules.connectors.vendors.hitachi_ops_center.manifest import PACKAGE_ID
from atlas.modules.identity.domain.models import AuthenticatedSubject, SubjectKind

RUNTIME_STATE_CREATE_PERMISSION = "connectors.target-sessions.create"
RUNTIME_STATE_READ_PERMISSION = "connectors.target-sessions.read"


class BundledConnectorRuntimeStateService:
    def __init__(
        self,
        *,
        repository: BundledConnectorRuntimeStateRepository,
        configuration_repository: BundledConnectionConfigurationRepository,
        connection_test_repository: ConnectorConnectionTestResultRepository,
        instance_repository: ConnectorInstanceRepository,
        audit_sink: AuditSink,
        environment_id: str,
        deployment_environment: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._configuration_repository = configuration_repository
        self._connection_test_repository = connection_test_repository
        self._instance_repository = instance_repository
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._development_enabled = deployment_environment == "development"
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    async def current(
        self,
        *,
        actor: AuthenticatedSubject,
        instance_id: str,
        correlation_id: str,
    ) -> BundledConnectorRuntimeState:
        self._require_development_human(actor)
        await self._require_instance(actor=actor, instance_id=instance_id)
        record = await self._repository.get(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            instance_id=instance_id,
        )
        result = record or self._initial_state(actor.organization_id, instance_id)
        await self._audit(
            actor,
            correlation_id,
            RUNTIME_STATE_READ_PERMISSION,
            "bundled_runtime_state_read",
            result,
        )
        return result

    async def enable(
        self,
        *,
        actor: AuthenticatedSubject,
        instance_id: str,
        acknowledged_read_only_operation: bool,
        correlation_id: str,
    ) -> BundledConnectorRuntimeState:
        self._require_development_human(actor)
        if not acknowledged_read_only_operation:
            raise BundledConnectorRuntimeStateError(
                "bundled_runtime_enable_acknowledgement_required"
            )
        await self._require_instance(actor=actor, instance_id=instance_id)
        configuration = await self._configuration_repository.get(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            instance_id=instance_id,
        )
        latest_test = await self._connection_test_repository.get_latest(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            instance_id=instance_id,
        )
        if configuration is None:
            raise BundledConnectorRuntimeStateError("bundled_runtime_configuration_not_found")
        if (
            latest_test is None
            or latest_test.outcome != "passed"
            or latest_test.checked_at < configuration.configured_at
        ):
            raise BundledConnectorRuntimeStateError("bundled_runtime_passing_test_required")

        async with self._mutation_lock:
            current = await self._repository.get(
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
                instance_id=instance_id,
            )
            if (
                current is not None
                and current.state == ENABLED_READ_ONLY
                and current.configuration_id == configuration.configuration_id
                and current.connection_test_id == latest_test.test_id
            ):
                return current
            version = current.version if current is not None else 0
            record = BundledConnectorRuntimeState(
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
                connector_id=PACKAGE_ID,
                instance_id=instance_id,
                state=ENABLED_READ_ONLY,
                version=version + 1,
                changed_at=self._clock(),
                changed_by=actor.subject_id,
                reason="Enable bounded read-only inventory and health polling for this MCP.",
                configuration_id=configuration.configuration_id,
                connection_test_id=latest_test.test_id,
            )
            await self._audit(
                actor,
                correlation_id,
                RUNTIME_STATE_CREATE_PERMISSION,
                "bundled_runtime_enabled_read_only",
                record,
            )
            if not await self._repository.put(record, expected_version=version):
                raise BundledConnectorRuntimeStateError("bundled_runtime_state_conflict")
        return record

    async def disable(
        self,
        *,
        actor: AuthenticatedSubject,
        instance_id: str,
        reason: str,
        acknowledged_runtime_stop: bool,
        correlation_id: str,
    ) -> BundledConnectorRuntimeState:
        self._require_development_human(actor)
        reason = reason.strip()
        if not acknowledged_runtime_stop:
            raise BundledConnectorRuntimeStateError(
                "bundled_runtime_disable_acknowledgement_required"
            )
        if not 20 <= len(reason) <= 1000:
            raise BundledConnectorRuntimeStateError("bundled_runtime_disable_reason_invalid")
        await self._require_instance(actor=actor, instance_id=instance_id)
        async with self._mutation_lock:
            current = await self._repository.get(
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
                instance_id=instance_id,
            )
            if current is None or current.state != ENABLED_READ_ONLY:
                raise BundledConnectorRuntimeStateError("bundled_runtime_not_enabled")
            record = BundledConnectorRuntimeState(
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
                connector_id=PACKAGE_ID,
                instance_id=instance_id,
                state=DISABLED,
                version=current.version + 1,
                changed_at=self._clock(),
                changed_by=actor.subject_id,
                reason=reason,
                configuration_id=current.configuration_id,
                connection_test_id=current.connection_test_id,
            )
            await self._audit(
                actor,
                correlation_id,
                RUNTIME_STATE_CREATE_PERMISSION,
                "bundled_runtime_disabled",
                record,
            )
            if not await self._repository.put(record, expected_version=current.version):
                raise BundledConnectorRuntimeStateError("bundled_runtime_state_conflict")
        return record

    def _initial_state(
        self, organization_id: str, instance_id: str
    ) -> BundledConnectorRuntimeState:
        return BundledConnectorRuntimeState(
            organization_id=organization_id,
            environment_id=self._environment_id,
            connector_id=PACKAGE_ID,
            instance_id=instance_id,
            state=DISABLED,
            version=0,
            changed_at=None,
            changed_by=None,
            reason=None,
            configuration_id=None,
            connection_test_id=None,
        )

    def _require_development_human(self, actor: AuthenticatedSubject) -> None:
        if not self._development_enabled:
            raise BundledConnectorRuntimeStateError("bundled_runtime_development_only")
        if actor.kind is not SubjectKind.HUMAN:
            raise BundledConnectorRuntimeStateError("bundled_runtime_human_required")

    async def _require_instance(self, *, actor: AuthenticatedSubject, instance_id: str) -> None:
        records = await self._instance_repository.list_scope(
            organization_id=actor.organization_id, environment_id=self._environment_id
        )
        matches = tuple(record for record in records if record.instance_id == instance_id)
        if len(matches) != 1:
            raise BundledConnectorRuntimeStateError("bundled_runtime_instance_not_found")
        record = matches[0]
        if record.connector_id != PACKAGE_ID or record.instance_state != DISABLED_UNCONFIGURED:
            raise BundledConnectorRuntimeStateError("bundled_runtime_instance_invalid")

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        record: BundledConnectorRuntimeState,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.bundled-runtime-state",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id=permission_id,
                resource_type="resource.connector.bundled-runtime-state",
                scope_reference=record.instance_id,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=(
                    ("state", record.state),
                    ("managed_infrastructure_contacted", "false"),
                    ("infrastructure_mutation_performed", "false"),
                ),
            )
        )
