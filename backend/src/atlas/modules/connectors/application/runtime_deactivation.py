from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from hashlib import sha256
from typing import cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.connectors.application.runtime_deactivation_ports import (
    ConnectorRuntimeDeactivationActivationSource,
    ConnectorRuntimeDeactivationError,
    ConnectorRuntimeDeactivationRepository,
)
from atlas.modules.connectors.domain.runtime_activation import ConnectorRuntimeActivationRecord
from atlas.modules.connectors.domain.runtime_deactivation import (
    DISABLED_RUNTIME,
    ConnectorRuntimeDeactivationRecord,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject, SubjectKind

RUNTIME_DEACTIVATION_CREATE_PERMISSION = "connectors.runtime-activations.deactivate"
RUNTIME_DEACTIVATION_READ_PERMISSION = "connectors.runtime-activations.read"
RUNTIME_DEACTIVATION_SCHEMA = "atlas.connector-runtime-deactivation.v1"


class ConnectorRuntimeDeactivationService:
    def __init__(
        self,
        *,
        repository: ConnectorRuntimeDeactivationRepository,
        activation_source: ConnectorRuntimeDeactivationActivationSource,
        audit_sink: AuditSink,
        environment_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._activation_source = activation_source
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def repository(self) -> ConnectorRuntimeDeactivationRepository:
        return self._repository

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        activation_id: str,
        expected_activation_version: int | None,
        expected_activation_digest: str | None,
        reason: str,
        runtime_only_acknowledged: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ConnectorRuntimeDeactivationRecord:
        self._require_human(actor)
        reason = reason.strip()
        if not runtime_only_acknowledged:
            raise ConnectorRuntimeDeactivationError(
                "runtime_deactivation_acknowledgement_required"
            )
        if (
            (expected_activation_version is None and expected_activation_digest is None)
            or (expected_activation_version is not None and expected_activation_version < 1)
            or (expected_activation_digest is not None and len(expected_activation_digest) != 64)
            or not 20 <= len(reason) <= 1000
            or not 8 <= len(idempotency_key) <= 128
        ):
            raise ConnectorRuntimeDeactivationError("runtime_deactivation_request_invalid")
        fingerprint = self._digest(
            {
                "activation_id": activation_id,
                "expected_activation_version": expected_activation_version,
                "expected_activation_digest": expected_activation_digest,
                "reason": reason,
                "runtime_only_acknowledged": runtime_only_acknowledged,
            }
        )
        replay = await self._repository.get_by_create_key_in_scope(
            deactivated_by=actor.subject_id,
            idempotency_key=idempotency_key,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
        )
        if replay is not None:
            return self._reuse(replay, actor, fingerprint)

        activation = await self._activation_source.get_activation_for_deactivation(
            activation_id=activation_id,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
        )
        if activation is None:
            raise ConnectorRuntimeDeactivationError("runtime_deactivation_activation_not_found")
        if (
            (
                expected_activation_version is not None
                and activation.version != expected_activation_version
            )
            or (
                expected_activation_digest is not None
                and activation.canonical_digest != expected_activation_digest
            )
        ):
            raise ConnectorRuntimeDeactivationError("runtime_deactivation_activation_conflict")

        existing = await self._repository.get_by_activation_in_scope(
            activation_id=activation_id,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
        )
        if existing is not None:
            raise ConnectorRuntimeDeactivationError("runtime_already_deactivated")

        record = self._record(
            activation=activation,
            actor=actor,
            reason=reason,
            fingerprint=fingerprint,
            idempotency_key=idempotency_key,
        )
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            result_code="connector_runtime_deactivation_requested",
            scope_reference=activation_id,
            metadata=(("activation_version", str(activation.version)),),
        )
        try:
            added = await self._repository.add(record)
        except Exception as error:
            raise ConnectorRuntimeDeactivationError(
                "runtime_deactivation_persistence_uncertain"
            ) from error
        if not added:
            replay = await self._repository.get_by_create_key_in_scope(
                deactivated_by=actor.subject_id,
                idempotency_key=idempotency_key,
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
            )
            if replay is not None:
                return self._reuse(replay, actor, fingerprint)
            raise ConnectorRuntimeDeactivationError("runtime_already_deactivated")
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            result_code="connector_runtime_deactivated",
            scope_reference=activation_id,
            metadata=(("effective_runtime_state", DISABLED_RUNTIME),),
        )
        return record

    async def list_deactivations(
        self,
        *,
        actor: AuthenticatedSubject,
        activation_id: str | None,
        correlation_id: str,
    ) -> tuple[ConnectorRuntimeDeactivationRecord, ...]:
        self._require_human(actor)
        records = await self._repository.list_scope(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
        )
        visible = tuple(
            record
            for record in records
            if activation_id is None or record.activation_id == activation_id
        )
        for record in visible:
            self._verify_record(record)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            result_code="connector_runtime_deactivations_listed",
            scope_reference=activation_id or self._environment_id,
            metadata=(("count", str(len(visible))),),
            permission_id=RUNTIME_DEACTIVATION_READ_PERMISSION,
        )
        return visible

    async def close(self) -> None:
        await self._repository.close()

    def _record(
        self,
        *,
        activation: ConnectorRuntimeActivationRecord,
        actor: AuthenticatedSubject,
        reason: str,
        fingerprint: str,
        idempotency_key: str,
    ) -> ConnectorRuntimeDeactivationRecord:
        seed = self._digest(
            [activation.organization_id, activation.environment_id, activation.activation_id]
        )
        record = ConnectorRuntimeDeactivationRecord(
            deactivation_id=f"connector-runtime-deactivation.{seed[:24]}",
            schema_version=RUNTIME_DEACTIVATION_SCHEMA,
            version=1,
            activation_id=activation.activation_id,
            activation_version=activation.version,
            activation_digest=activation.canonical_digest,
            organization_id=activation.organization_id,
            environment_id=activation.environment_id,
            connector_id=activation.connector_id,
            instance_id=activation.instance_id,
            effective_runtime_state=DISABLED_RUNTIME,
            deactivated_by=actor.subject_id,
            reason=reason,
            deactivated_at=self._clock(),
            request_fingerprint=fingerprint,
            idempotency_digest=self._digest(
                [
                    activation.organization_id,
                    activation.environment_id,
                    actor.subject_id,
                    idempotency_key,
                ]
            ),
            canonical_digest="0" * 64,
        )
        return replace(record, canonical_digest=self._digest(self._record_payload(record)))

    def _reuse(
        self,
        record: ConnectorRuntimeDeactivationRecord,
        actor: AuthenticatedSubject,
        fingerprint: str,
    ) -> ConnectorRuntimeDeactivationRecord:
        self._verify_record(record)
        if record.deactivated_by != actor.subject_id or record.request_fingerprint != fingerprint:
            raise ConnectorRuntimeDeactivationError("runtime_deactivation_idempotency_conflict")
        return replace(record, reused=True)

    @classmethod
    def _verify_record(cls, record: ConnectorRuntimeDeactivationRecord) -> None:
        if cls._digest(cls._record_payload(record)) != record.canonical_digest:
            raise ConnectorRuntimeDeactivationError("runtime_deactivation_integrity_failed")

    @staticmethod
    def _record_payload(record: ConnectorRuntimeDeactivationRecord) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(record))
        payload.pop("canonical_digest")
        payload.pop("request_fingerprint")
        payload.pop("idempotency_digest")
        payload.pop("reused")
        payload["deactivated_at"] = record.deactivated_at.isoformat()
        return payload

    @staticmethod
    def _digest(payload: object) -> str:
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
                "ascii"
            )
        ).hexdigest()

    @staticmethod
    def _identifier_digest(value: str) -> str:
        return sha256(value.encode("ascii")).hexdigest()

    @staticmethod
    def _require_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise ConnectorRuntimeDeactivationError("runtime_deactivation_human_required")

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        scope_reference: str,
        metadata: tuple[tuple[str, str], ...],
        permission_id: str = RUNTIME_DEACTIVATION_CREATE_PERMISSION,
    ) -> None:
        try:
            await self._audit_sink.record(
                AuditRecord(
                    event_id=f"evt_{uuid4().hex}",
                    event_type="atlas.connector.runtime-deactivation",
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
                    resource_type="resource.connector.runtime-activation",
                    scope_reference=scope_reference,
                    decision_id=None,
                    outcome="succeeded",
                    result_code=result_code,
                    idempotency_key=None,
                    target_metadata=metadata,
                )
            )
        except Exception as error:
            raise ConnectorRuntimeDeactivationError("runtime_deactivation_audit_failed") from error
