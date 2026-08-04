from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.platform.application.bootstrap_state_ports import BootstrapStateRepository
from atlas.modules.platform.domain.bootstrap_state import (
    BootstrapCheckpointState,
    BootstrapMutationResult,
    BootstrapRunIdentity,
    BootstrapStateView,
)


class BootstrapStateScopeError(RuntimeError):
    pass


class BootstrapStateService:
    def __init__(
        self,
        *,
        repository: BootstrapStateRepository,
        environment_id: str,
        site_id: str,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._environment_id = environment_id
        self._site_id = site_id
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def repository(self) -> BootstrapStateRepository:
        return self._repository

    async def close(self) -> None:
        await self._repository.close()

    async def current(
        self,
        *,
        actor: AuthenticatedSubject,
        lease_holder_id: str | None,
        correlation_id: str,
    ) -> BootstrapStateView:
        now = self._clock()
        record = await self._repository.get_current(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
        )
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            event_type="atlas.platform.bootstrap-state.read",
            permission_id="platform.bootstrap-state.read",
            result_code="bootstrap_state_present"
            if record is not None
            else "bootstrap_state_empty",
            target_metadata=(("run_id", record.run_id),) if record is not None else (),
        )
        active = record is not None and record.lease_is_active(now)
        return BootstrapStateView(
            record=record,
            durable=self._repository.durable,
            lease_available=not active,
            lease_held_by_current_actor=(
                active and record is not None and record.lease_holder_id == lease_holder_id
            ),
        )

    async def claim(
        self,
        *,
        actor: AuthenticatedSubject,
        lease_holder_id: str,
        identity: BootstrapRunIdentity,
        lease_duration: timedelta,
        idempotency_key: str,
        correlation_id: str,
        justification: str | None = None,
    ) -> BootstrapMutationResult:
        await self._require_scope(actor, identity, correlation_id)
        fingerprint = self._fingerprint(
            {
                "operation": "claim",
                "identity": self._identity_payload(identity),
                "lease_seconds": int(lease_duration.total_seconds()),
                "justification": justification,
            }
        )
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            event_type="atlas.platform.bootstrap-state.claim",
            permission_id="platform.bootstrap-state.manage",
            result_code="bootstrap_state_claim_authorized",
            idempotency_key=idempotency_key,
            target_metadata=(
                ("plan_digest", identity.plan_digest),
                *(
                    (
                        (
                            "justification_digest",
                            self._fingerprint({"justification": justification}),
                        ),
                    )
                    if justification is not None
                    else ()
                ),
            ),
        )
        return await self._repository.claim(
            identity=identity,
            lease_holder_id=lease_holder_id,
            lease_duration=lease_duration,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            now=self._clock(),
        )

    async def checkpoint(
        self,
        *,
        actor: AuthenticatedSubject,
        lease_holder_id: str,
        run_id: str,
        plan_digest: str,
        resume_key: str,
        phase_id: str,
        state: BootstrapCheckpointState,
        safe_output_references: tuple[str, ...],
        expected_version: int,
        idempotency_key: str,
        correlation_id: str,
    ) -> BootstrapMutationResult:
        await self._require_run_scope(actor, run_id, correlation_id)
        fingerprint = self._fingerprint(
            {
                "operation": "checkpoint",
                "run_id": run_id,
                "plan_digest": plan_digest,
                "resume_key": resume_key,
                "phase_id": phase_id,
                "state": state.value,
                "safe_output_references": safe_output_references,
                "expected_version": expected_version,
            }
        )
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            event_type="atlas.platform.bootstrap-state.checkpoint",
            permission_id="platform.bootstrap-state.manage",
            result_code="bootstrap_checkpoint_authorized",
            idempotency_key=idempotency_key,
            target_metadata=(("run_id", run_id), ("phase_id", phase_id)),
        )
        return await self._repository.checkpoint(
            run_id=run_id,
            plan_digest=plan_digest,
            resume_key=resume_key,
            phase_id=phase_id,
            state=state,
            safe_output_references=safe_output_references,
            lease_holder_id=lease_holder_id,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            now=self._clock(),
        )

    async def release(
        self,
        *,
        actor: AuthenticatedSubject,
        lease_holder_id: str,
        run_id: str,
        expected_version: int,
        idempotency_key: str,
        correlation_id: str,
    ) -> BootstrapMutationResult:
        await self._require_run_scope(actor, run_id, correlation_id)
        fingerprint = self._fingerprint(
            {
                "operation": "release",
                "run_id": run_id,
                "expected_version": expected_version,
            }
        )
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            event_type="atlas.platform.bootstrap-state.release",
            permission_id="platform.bootstrap-state.manage",
            result_code="bootstrap_lease_release_authorized",
            idempotency_key=idempotency_key,
            target_metadata=(("run_id", run_id),),
        )
        return await self._repository.release(
            run_id=run_id,
            lease_holder_id=lease_holder_id,
            expected_version=expected_version,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            now=self._clock(),
        )

    async def rebase(
        self,
        *,
        actor: AuthenticatedSubject,
        lease_holder_id: str,
        run_id: str,
        candidate: BootstrapRunIdentity,
        expected_version: int,
        preview_source_version: int,
        justification: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> BootstrapMutationResult:
        await self._require_scope(actor, candidate, correlation_id)
        await self._require_run_scope(actor, run_id, correlation_id)
        fingerprint = self._fingerprint(
            {
                "operation": "rebase",
                "run_id": run_id,
                "candidate": self._identity_payload(candidate),
                "expected_version": expected_version,
                "preview_source_version": preview_source_version,
                "justification": justification,
            }
        )
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            event_type="atlas.platform.bootstrap-state.rebase",
            permission_id="platform.bootstrap-state.manage",
            result_code="bootstrap_rebase_authorized",
            idempotency_key=idempotency_key,
            target_metadata=(
                ("run_id", run_id),
                ("candidate_plan_digest", candidate.plan_digest),
                ("justification_digest", self._fingerprint({"justification": justification})),
            ),
        )
        return await self._repository.rebase(
            run_id=run_id,
            candidate=candidate,
            lease_holder_id=lease_holder_id,
            expected_version=expected_version,
            preview_source_version=preview_source_version,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            now=self._clock(),
        )

    async def _require_scope(
        self,
        actor: AuthenticatedSubject,
        identity: BootstrapRunIdentity,
        correlation_id: str,
    ) -> None:
        if (
            identity.organization_id != actor.organization_id
            or identity.environment_id != self._environment_id
            or identity.site_id != self._site_id
        ):
            await self._audit_scope_denial(actor, correlation_id)
            raise BootstrapStateScopeError("bootstrap state scope does not match actor")

    async def _require_run_scope(
        self, actor: AuthenticatedSubject, run_id: str, correlation_id: str
    ) -> None:
        record = await self._repository.get_current(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
        )
        if record is None or record.run_id != run_id:
            await self._audit_scope_denial(actor, correlation_id)
            raise BootstrapStateScopeError("bootstrap state scope does not match actor")

    @staticmethod
    def _identity_payload(identity: BootstrapRunIdentity) -> dict[str, object]:
        return {
            "release_id": identity.release_id,
            "profile": identity.profile.value,
            "organization_id": identity.organization_id,
            "environment_id": identity.environment_id,
            "site_id": identity.site_id,
            "plan_digest": identity.plan_digest,
            "resume_key": identity.resume_key,
            "configuration_digest": identity.configuration_digest,
            "phase_ids": identity.phase_ids,
        }

    @staticmethod
    def _fingerprint(payload: dict[str, object]) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return sha256(encoded).hexdigest()

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        event_type: str,
        permission_id: str,
        result_code: str,
        target_metadata: tuple[tuple[str, str], ...],
        idempotency_key: str | None = None,
    ) -> None:
        capability = "C0" if permission_id.endswith(".read") else "C2"
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=event_type,
                schema_version="1.0",
                producer="atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id=permission_id,
                resource_type="resource.platform.bootstrap-state",
                scope_reference=f"{actor.organization_id}/{self._environment_id}/{self._site_id}/domain.platform/resource.platform.bootstrap-state/{capability}",
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=target_metadata,
            )
        )

    async def _audit_scope_denial(self, actor: AuthenticatedSubject, correlation_id: str) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.platform.bootstrap-state.denied",
                schema_version="1.0",
                producer="atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id="platform.bootstrap-state.manage",
                resource_type="resource.platform.bootstrap-state",
                scope_reference="scope.redacted",
                decision_id=None,
                outcome="denied",
                result_code="bootstrap_state_scope_mismatch",
            )
        )
