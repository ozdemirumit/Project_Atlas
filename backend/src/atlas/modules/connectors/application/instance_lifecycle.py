from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.connectors.application.instance_creation import (
    INSTANCE_READ_PERMISSION,
    ConnectorInstanceCreationService,
)
from atlas.modules.connectors.application.instance_creation_ports import (
    ConnectorInstanceCreationError,
    ConnectorInstanceRepository,
)
from atlas.modules.connectors.application.target_configuration_ports import (
    ConnectorTargetConfigurationRepository,
)
from atlas.modules.connectors.domain.instance_creation import (
    DISABLED_UNCONFIGURED,
    RETIRED,
    ConnectorInstanceRecord,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)

INSTANCE_RETIRE_PERMISSION = "connectors.instances.retire"


class ConnectorInstanceLifecycleService:
    def __init__(
        self,
        *,
        repository: ConnectorInstanceRepository,
        target_repository: ConnectorTargetConfigurationRepository,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._target_repository = target_repository
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()

    async def list(
        self,
        *,
        actor: AuthenticatedSubject,
        lifecycle: str,
        query: str,
        correlation_id: str,
    ) -> tuple[ConnectorInstanceRecord, ...]:
        self._require_enterprise_human(actor)
        if lifecycle not in {"active", RETIRED, "all"} or len(query) > 200:
            raise ConnectorInstanceCreationError("connector_instance_list_request_invalid")
        records = await self._repository.list_scope(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
        )
        normalized_query = query.strip().casefold()
        visible: list[ConnectorInstanceRecord] = []
        for record in records:
            ConnectorInstanceCreationService._verify_record(record)
            self._require_scope(actor, record)
            if lifecycle == "active" and record.instance_state == RETIRED:
                continue
            if lifecycle == RETIRED and record.instance_state != RETIRED:
                continue
            if (
                normalized_query
                and normalized_query
                not in " ".join(
                    (
                        record.display_name,
                        record.instance_key,
                        record.connector_id,
                        record.release_version,
                        record.publisher_id,
                    )
                ).casefold()
            ):
                continue
            visible.append(record)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            result_code="connector_instances_listed",
            scope_reference=self._environment_id,
            idempotency_key=None,
            metadata=(("count", str(len(visible))), ("lifecycle", lifecycle)),
            permission_id=INSTANCE_READ_PERMISSION,
        )
        return tuple(visible)

    async def retire(
        self,
        *,
        actor: AuthenticatedSubject,
        record_id: str,
        expected_version: int,
        reason: str,
        acknowledged_retirement_preserves_history_and_performs_no_runtime_action: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorInstanceRecord:
        self._require_enterprise_human(actor)
        reason = reason.strip()
        if not acknowledged_retirement_preserves_history_and_performs_no_runtime_action:
            raise ConnectorInstanceCreationError(
                "connector_instance_retirement_acknowledgement_required"
            )
        if (
            expected_version < 1
            or not 20 <= len(reason) <= 1000
            or not 8 <= len(idempotency_key) <= 128
        ):
            raise ConnectorInstanceCreationError("connector_instance_retirement_request_invalid")
        fingerprint = ConnectorInstanceCreationService._digest(
            {
                "record_id": record_id,
                "expected_version": expected_version,
                "reason": reason,
            }
        )
        replay = await self._repository.get_by_retirement_key(
            retired_by=actor.subject_id,
            idempotency_key=idempotency_key,
        )
        if replay is not None:
            return self._reuse_retirement(replay, actor, fingerprint)

        async with self._mutation_lock:
            record = await self._repository.get(record_id=record_id)
            if record is None:
                raise ConnectorInstanceCreationError("connector_instance_record_not_found")
            ConnectorInstanceCreationService._verify_record(record)
            self._require_scope(actor, record)
            if record.instance_state == RETIRED:
                raise ConnectorInstanceCreationError("connector_instance_already_retired")
            if record.instance_state != DISABLED_UNCONFIGURED:
                raise ConnectorInstanceCreationError("connector_instance_retirement_state_invalid")
            if record.version != expected_version:
                raise ConnectorInstanceCreationError("connector_instance_version_conflict")
            target = await self._target_repository.get_by_instance(
                source_instance_record_id=record.record_id
            )
            if target is not None:
                raise ConnectorInstanceCreationError(
                    "connector_instance_retirement_requires_decommissioning"
                )
            now = self._clock()
            retired = replace(
                record,
                version=record.version + 1,
                instance_state=RETIRED,
                eligible_for_configuration_governance=False,
                retired_by=actor.subject_id,
                retired_at=now,
                retirement_reason=reason,
                retirement_request_fingerprint=fingerprint,
                retirement_idempotency_key=idempotency_key,
                canonical_digest="0" * 64,
                reused=False,
            )
            retired = replace(
                retired,
                canonical_digest=ConnectorInstanceCreationService._digest(
                    ConnectorInstanceCreationService._record_payload(retired)
                ),
            )
            await self._audit(
                actor=actor,
                correlation_id=correlation_id,
                result_code="connector_instance_retirement_requested",
                scope_reference=record.instance_id,
                idempotency_key=idempotency_key,
                metadata=(("expected_version", str(expected_version)),),
            )
            if not await self._repository.update(retired, expected_version=expected_version):
                raced = await self._repository.get_by_retirement_key(
                    retired_by=actor.subject_id,
                    idempotency_key=idempotency_key,
                )
                if raced is None:
                    raise ConnectorInstanceCreationError("connector_instance_version_conflict")
                return self._reuse_retirement(raced, actor, fingerprint)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            result_code="connector_instance_retired",
            scope_reference=retired.instance_id,
            idempotency_key=idempotency_key,
            metadata=(("version", str(retired.version)),),
        )
        return retired

    def _reuse_retirement(
        self,
        record: ConnectorInstanceRecord,
        actor: AuthenticatedSubject,
        fingerprint: str,
    ) -> ConnectorInstanceRecord:
        ConnectorInstanceCreationService._verify_record(record)
        self._require_scope(actor, record)
        if (
            record.retired_by != actor.subject_id
            or record.retirement_request_fingerprint != fingerprint
        ):
            raise ConnectorInstanceCreationError(
                "connector_instance_retirement_idempotency_conflict"
            )
        return replace(record, reused=True)

    def _require_scope(self, actor: AuthenticatedSubject, record: ConnectorInstanceRecord) -> None:
        if (
            actor.organization_id != record.organization_id
            or self._environment_id != record.environment_id
        ):
            raise ConnectorInstanceCreationError("connector_instance_record_not_found")

    @staticmethod
    def _require_enterprise_human(actor: AuthenticatedSubject) -> None:
        if (
            actor.kind is not SubjectKind.HUMAN
            or actor.authentication_method is AuthenticationMethod.DEVELOPMENT
            or actor.assurance_level
            not in {AssuranceLevel.MULTI_FACTOR, AssuranceLevel.HARDWARE_BACKED}
        ):
            raise ConnectorInstanceCreationError("connector_instance_enterprise_human_mfa_required")

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        idempotency_key: str | None,
        metadata: tuple[tuple[str, str], ...],
        permission_id: str = INSTANCE_RETIRE_PERMISSION,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.connector.instance-lifecycle",
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
                resource_type="resource.connector.instance",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=metadata,
            )
        )
