from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.event_envelope_ports import (
    WorkflowDispatchEventEnvelopeError,
    WorkflowDispatchEventEnvelopePrepareRequest,
    WorkflowDispatchEventEnvelopePrepareStatus,
    WorkflowDispatchEventEnvelopeRepository,
)
from atlas.modules.workflows.application.orchestration_ports import (
    WorkflowOrchestrationLeaseRepository,
)
from atlas.modules.workflows.application.ports import WorkflowPlanRepository
from atlas.modules.workflows.application.publication_leases import (
    WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE,
    WorkflowOutboxPublisherContext,
)
from atlas.modules.workflows.domain import (
    WorkflowDispatchEventAuthority,
    WorkflowDispatchEventEnvelope,
    WorkflowDispatchEventEnvelopeState,
    WorkflowDispatchEventPayload,
    WorkflowDispatchOutboxEntry,
    WorkflowDispatchOutboxState,
    WorkflowOrchestrationLease,
    WorkflowOrchestrationLeaseEffectiveState,
    WorkflowOutboxPublicationLease,
    WorkflowOutboxPublicationLeaseEffectiveState,
    WorkflowPlanState,
    canonical_digest,
)

WORKFLOW_DISPATCH_EVENT_TYPE = "WorkflowStepDispatchRequested"
WORKFLOW_DISPATCH_EVENT_VERSION = "1.0"
WORKFLOW_DISPATCH_EVENT_SCHEMA_URI = "urn:project-atlas:event:workflow-step-dispatch-requested:1.0"
WORKFLOW_DISPATCH_EVENT_PRODUCER = "project-atlas-workflow-event-control"


class WorkflowDispatchEventEnvelopeService:
    """Prepares canonical event evidence without transport or execution authority."""

    def __init__(
        self,
        *,
        plan_repository: WorkflowPlanRepository,
        orchestration_lease_repository: WorkflowOrchestrationLeaseRepository,
        event_envelope_repository: WorkflowDispatchEventEnvelopeRepository,
        audit_sink: AuditSink,
    ) -> None:
        self._plan_repository = plan_repository
        self._orchestration_lease_repository = orchestration_lease_repository
        self._event_envelope_repository = event_envelope_repository
        self._audit_sink = audit_sink

    @property
    def durable(self) -> bool:
        return self._event_envelope_repository.durable

    @property
    def repository(self) -> WorkflowDispatchEventEnvelopeRepository:
        return self._event_envelope_repository

    async def prepare(
        self,
        *,
        outbox_entry_id: str,
        outbox_entry_digest: str,
        publication_lease_id: str,
        publication_lease_digest: str,
        publication_fencing_token: int,
        idempotency_key: str,
        context: WorkflowOutboxPublisherContext,
    ) -> WorkflowDispatchEventEnvelope:
        await self._require_publisher(context)
        try:
            normalized_outbox_id = self._identifier(outbox_entry_id, "outbox_entry_id")
            normalized_outbox_digest = self._digest(outbox_entry_digest, "outbox_entry_digest")
            normalized_publication_lease_id = self._identifier(
                publication_lease_id, "publication_lease_id"
            )
            normalized_publication_lease_digest = self._digest(
                publication_lease_digest, "publication_lease_digest"
            )
            if publication_fencing_token < 1:
                raise WorkflowDispatchEventEnvelopeError(
                    "workflow_dispatch_event_publication_fence_invalid",
                    "The publication fencing token is invalid.",
                )
            normalized_key = self._idempotency_key(idempotency_key)
        except WorkflowDispatchEventEnvelopeError as exc:
            await self._deny(context, result_code=exc.code)
            raise

        outbox, orchestration_lease, publication_lease = await self._require_current_evidence(
            outbox_entry_id=normalized_outbox_id,
            outbox_entry_digest=normalized_outbox_digest,
            publication_lease_id=normalized_publication_lease_id,
            publication_lease_digest=normalized_publication_lease_digest,
            publication_fencing_token=publication_fencing_token,
            context=context,
            idempotency_key=normalized_key,
        )
        fingerprint = canonical_digest(
            {
                "idempotency_key": normalized_key,
                "operation": "workflow.dispatch-event-envelope.prepare",
                "orchestration_fencing_token": orchestration_lease.fencing_token,
                "orchestration_lease_digest": orchestration_lease.canonical_digest,
                "orchestration_lease_id": orchestration_lease.lease_id,
                "outbox_entry_digest": outbox.canonical_digest,
                "outbox_entry_id": outbox.outbox_entry_id,
                "publication_fencing_token": publication_lease.publication_fencing_token,
                "publication_lease_digest": publication_lease.canonical_digest,
                "publication_lease_id": publication_lease.publication_lease_id,
                "publisher_subject_id": context.subject_id,
                "scope": outbox.scope.canonical_value(),
                "target_id": outbox.target_id,
                "target_type": outbox.target_type,
            }
        )
        prior = await self._event_envelope_repository.get_dispatch_event_envelope_prepare_request(
            scope=context.scope,
            publisher_subject_id=context.subject_id,
            idempotency_key=normalized_key,
        )
        if prior is not None:
            if prior.request_fingerprint != fingerprint:
                await self._deny(
                    context,
                    result_code="workflow_dispatch_event_envelope_idempotency_conflict",
                    idempotency_key=normalized_key,
                    outbox=outbox,
                    envelope=prior.envelope,
                )
            self._validate_envelope(
                prior.envelope, outbox, orchestration_lease, publication_lease, context
            )
            await self._success(
                context,
                result_code="workflow_dispatch_event_envelope_preparation_replayed",
                idempotency_key=normalized_key,
                outbox=outbox,
                envelope=prior.envelope,
            )
            return prior.envelope

        current = (
            await self._event_envelope_repository.get_dispatch_event_envelope_by_outbox_entry_id(
                outbox_entry_id=outbox.outbox_entry_id
            )
        )
        if current is not None:
            code = (
                "workflow_dispatch_event_envelope_competing_identity"
                if current.publisher_subject_id != context.subject_id
                else "workflow_dispatch_event_envelope_already_prepared"
            )
            await self._deny(
                context,
                result_code=code,
                idempotency_key=normalized_key,
                outbox=outbox,
                envelope=current,
            )

        candidate = self._build_envelope(
            outbox=outbox,
            orchestration_lease=orchestration_lease,
            publication_lease=publication_lease,
            prepared_at=context.requested_at,
        )
        result = await self._event_envelope_repository.prepare_dispatch_event_envelope(
            WorkflowDispatchEventEnvelopePrepareRequest(
                expected_outbox_entry_digest=outbox.canonical_digest,
                expected_plan_digest=outbox.plan_digest,
                expected_orchestration_lease_id=orchestration_lease.lease_id,
                expected_orchestration_lease_digest=orchestration_lease.canonical_digest,
                expected_orchestration_fencing_token=orchestration_lease.fencing_token,
                expected_publication_lease_id=publication_lease.publication_lease_id,
                expected_publication_lease_digest=publication_lease.canonical_digest,
                expected_publication_fencing_token=publication_lease.publication_fencing_token,
                publisher_subject_id=context.subject_id,
                requested_at=context.requested_at,
                candidate=candidate,
                idempotency_key=normalized_key,
                request_fingerprint=fingerprint,
            )
        )
        if result.status in {
            WorkflowDispatchEventEnvelopePrepareStatus.PREPARED,
            WorkflowDispatchEventEnvelopePrepareStatus.REPLAY,
        }:
            if result.envelope is None:
                raise WorkflowDispatchEventEnvelopeError(
                    "workflow_dispatch_event_envelope_repository_contract_violation",
                    "The repository returned an incomplete preparation result.",
                )
            self._validate_envelope(
                result.envelope, outbox, orchestration_lease, publication_lease, context
            )
            replayed = result.status is WorkflowDispatchEventEnvelopePrepareStatus.REPLAY
            await self._success(
                context,
                result_code=(
                    "workflow_dispatch_event_envelope_preparation_replayed"
                    if replayed
                    else "workflow_dispatch_event_envelope_prepared"
                ),
                idempotency_key=normalized_key,
                outbox=outbox,
                envelope=result.envelope,
            )
            return result.envelope
        code = {
            WorkflowDispatchEventEnvelopePrepareStatus.IDEMPOTENCY_CONFLICT: (
                "workflow_dispatch_event_envelope_idempotency_conflict"
            ),
            WorkflowDispatchEventEnvelopePrepareStatus.ALREADY_PREPARED: (
                "workflow_dispatch_event_envelope_already_prepared"
            ),
        }.get(
            result.status,
            "workflow_dispatch_event_envelope_evidence_conflict",
        )
        await self._deny(
            context,
            result_code=code,
            idempotency_key=normalized_key,
            outbox=outbox,
            envelope=result.envelope,
        )

    async def _require_current_evidence(
        self,
        *,
        outbox_entry_id: str,
        outbox_entry_digest: str,
        publication_lease_id: str,
        publication_lease_digest: str,
        publication_fencing_token: int,
        context: WorkflowOutboxPublisherContext,
        idempotency_key: str,
    ) -> tuple[
        WorkflowDispatchOutboxEntry,
        WorkflowOrchestrationLease,
        WorkflowOutboxPublicationLease,
    ]:
        outbox = await self._event_envelope_repository.get_outbox_entry_by_id(
            outbox_entry_id=outbox_entry_id
        )
        if (
            outbox is None
            or outbox.scope != context.scope
            or outbox.target_id not in context.authorized_target_ids
            or outbox.target_type != "storage"
        ):
            await self._deny(
                context,
                result_code="workflow_dispatch_event_outbox_not_found",
                idempotency_key=idempotency_key,
            )
        assert outbox is not None
        if (
            outbox.canonical_digest != outbox_entry_digest
            or outbox.state is not WorkflowDispatchOutboxState.PENDING_PUBLICATION
            or any(outbox.authority.canonical_value().values())
        ):
            await self._deny(
                context,
                result_code="workflow_dispatch_event_outbox_conflict",
                idempotency_key=idempotency_key,
                outbox=outbox,
            )
        plan = await self._plan_repository.get_by_id(plan_id=outbox.plan_id)
        if (
            plan is None
            or plan.scope != outbox.scope
            or plan.target_id != outbox.target_id
            or plan.target_type != outbox.target_type
        ):
            await self._deny(
                context,
                result_code="workflow_dispatch_event_plan_not_found",
                idempotency_key=idempotency_key,
                outbox=outbox,
            )
        assert plan is not None
        if (
            plan.state is not WorkflowPlanState.PLANNED
            or plan.canonical_digest != outbox.plan_digest
        ):
            await self._deny(
                context,
                result_code="workflow_dispatch_event_plan_conflict",
                idempotency_key=idempotency_key,
                outbox=outbox,
            )
        orchestration_lease = await self._orchestration_lease_repository.get_lease_by_plan_id(
            plan_id=outbox.plan_id
        )
        if (
            orchestration_lease is None
            or orchestration_lease.lease_id != outbox.lease_id
            or orchestration_lease.canonical_digest != outbox.lease_digest
            or orchestration_lease.fencing_token != outbox.fencing_token
            or orchestration_lease.scope != outbox.scope
            or orchestration_lease.target_id != outbox.target_id
            or orchestration_lease.target_type != outbox.target_type
            or orchestration_lease.effective_state(requested_at=context.requested_at)
            is not WorkflowOrchestrationLeaseEffectiveState.ACTIVE
        ):
            await self._deny(
                context,
                result_code="workflow_dispatch_event_orchestration_lease_conflict",
                idempotency_key=idempotency_key,
                outbox=outbox,
            )
        assert orchestration_lease is not None
        publication_lease = (
            await self._event_envelope_repository.get_publication_lease_by_outbox_entry_id(
                outbox_entry_id=outbox.outbox_entry_id
            )
        )
        if (
            publication_lease is None
            or publication_lease.publication_lease_id != publication_lease_id
            or publication_lease.canonical_digest != publication_lease_digest
            or publication_lease.publication_fencing_token != publication_fencing_token
            or publication_lease.publisher_subject_id != context.subject_id
            or publication_lease.effective_state(requested_at=context.requested_at)
            is not WorkflowOutboxPublicationLeaseEffectiveState.ACTIVE
            or not self._publication_lease_matches(publication_lease, outbox, orchestration_lease)
        ):
            await self._deny(
                context,
                result_code="workflow_dispatch_event_publication_lease_conflict",
                idempotency_key=idempotency_key,
                outbox=outbox,
            )
        assert publication_lease is not None
        return outbox, orchestration_lease, publication_lease

    @staticmethod
    def _build_envelope(
        *,
        outbox: WorkflowDispatchOutboxEntry,
        orchestration_lease: WorkflowOrchestrationLease,
        publication_lease: WorkflowOutboxPublicationLease,
        prepared_at: datetime,
    ) -> WorkflowDispatchEventEnvelope:
        event_id = (
            "workflow-dispatch-event."
            + sha256(
                (
                    f"{outbox.outbox_entry_id}:{outbox.canonical_digest}:"
                    f"{WORKFLOW_DISPATCH_EVENT_TYPE}:{WORKFLOW_DISPATCH_EVENT_VERSION}"
                ).encode()
            ).hexdigest()[:24]
        )
        payload = WorkflowDispatchEventPayload(
            outbox_entry_id=outbox.outbox_entry_id,
            outbox_entry_digest=outbox.canonical_digest,
            dispatch_intent_id=outbox.dispatch_intent_id,
            dispatch_intent_digest=outbox.dispatch_intent_digest,
            plan_id=outbox.plan_id,
            plan_digest=outbox.plan_digest,
            run_id=outbox.run_id,
            run_digest=outbox.run_digest,
            step_run_id=outbox.step_run_id,
            step_run_digest=outbox.step_run_digest,
            step_id=outbox.step_id,
            attempt_id=outbox.attempt_id,
            attempt_digest=outbox.attempt_digest,
            attempt_number=outbox.attempt_number,
            scope=outbox.scope,
            target_id=outbox.target_id,
            target_type=outbox.target_type,
        )
        values: dict[str, object] = {
            "event_id": event_id,
            "event_type": WORKFLOW_DISPATCH_EVENT_TYPE,
            "event_version": WORKFLOW_DISPATCH_EVENT_VERSION,
            "occurred_at": outbox.admitted_at,
            "recorded_at": prepared_at,
            "producer": WORKFLOW_DISPATCH_EVENT_PRODUCER,
            "producer_version": __version__,
            "subject_type": "workflow-execution-attempt",
            "subject_id": outbox.attempt_id,
            "organization_id": outbox.scope.organization_id,
            "environment_id": outbox.scope.environment_id,
            "correlation_id": outbox.run_id,
            "causation_id": outbox.dispatch_intent_id,
            "workflow_id": outbox.run_id,
            "data_classification": "internal",
            "schema_uri": WORKFLOW_DISPATCH_EVENT_SCHEMA_URI,
            "payload": payload,
            "extensions": (),
            "orchestration_lease_id": orchestration_lease.lease_id,
            "orchestration_lease_digest": orchestration_lease.canonical_digest,
            "orchestration_fencing_token": orchestration_lease.fencing_token,
            "publication_lease_id": publication_lease.publication_lease_id,
            "publication_lease_digest": publication_lease.canonical_digest,
            "publication_fencing_token": publication_lease.publication_fencing_token,
            "publisher_subject_id": publication_lease.publisher_subject_id,
            "prepared_at": prepared_at,
            "state": WorkflowDispatchEventEnvelopeState.PREPARED,
            "authority": WorkflowDispatchEventAuthority(),
        }
        digest_payload = {
            key: value.canonical_value()
            if isinstance(value, (WorkflowDispatchEventPayload, WorkflowDispatchEventAuthority))
            else value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(value, WorkflowDispatchEventEnvelopeState)
            else {}
            if key == "extensions"
            else value
            for key, value in values.items()
        }
        return WorkflowDispatchEventEnvelope(
            **cast(Any, values), canonical_digest=canonical_digest(digest_payload)
        )

    @staticmethod
    def _publication_lease_matches(
        lease: WorkflowOutboxPublicationLease,
        outbox: WorkflowDispatchOutboxEntry,
        orchestration_lease: WorkflowOrchestrationLease,
    ) -> bool:
        return (
            lease.outbox_entry_id == outbox.outbox_entry_id
            and lease.outbox_entry_digest == outbox.canonical_digest
            and lease.dispatch_intent_id == outbox.dispatch_intent_id
            and lease.dispatch_intent_digest == outbox.dispatch_intent_digest
            and lease.plan_id == outbox.plan_id
            and lease.plan_digest == outbox.plan_digest
            and lease.run_id == outbox.run_id
            and lease.run_digest == outbox.run_digest
            and lease.step_run_id == outbox.step_run_id
            and lease.step_run_digest == outbox.step_run_digest
            and lease.step_id == outbox.step_id
            and lease.attempt_id == outbox.attempt_id
            and lease.attempt_digest == outbox.attempt_digest
            and lease.attempt_number == outbox.attempt_number
            and lease.scope == outbox.scope
            and lease.target_id == outbox.target_id
            and lease.target_type == outbox.target_type
            and lease.orchestration_lease_id == orchestration_lease.lease_id
            and lease.orchestration_lease_digest == orchestration_lease.canonical_digest
            and lease.orchestration_fencing_token == orchestration_lease.fencing_token
            and not any(lease.authority.canonical_value().values())
            and not lease.grants_publication_authority
            and not lease.grants_delivery_authority
            and not lease.grants_dispatch_authority
            and not lease.grants_execution_authority
        )

    @classmethod
    def _validate_envelope(
        cls,
        envelope: WorkflowDispatchEventEnvelope,
        outbox: WorkflowDispatchOutboxEntry,
        orchestration_lease: WorkflowOrchestrationLease,
        publication_lease: WorkflowOutboxPublicationLease,
        context: WorkflowOutboxPublisherContext,
    ) -> None:
        expected_event_id = (
            "workflow-dispatch-event."
            + sha256(
                (
                    f"{outbox.outbox_entry_id}:{outbox.canonical_digest}:"
                    f"{WORKFLOW_DISPATCH_EVENT_TYPE}:{WORKFLOW_DISPATCH_EVENT_VERSION}"
                ).encode()
            ).hexdigest()[:24]
        )
        payload = envelope.payload
        if (
            envelope.event_id != expected_event_id
            or envelope.event_type != WORKFLOW_DISPATCH_EVENT_TYPE
            or envelope.event_version != WORKFLOW_DISPATCH_EVENT_VERSION
            or envelope.occurred_at != outbox.admitted_at
            or envelope.recorded_at != envelope.prepared_at
            or envelope.recorded_at < outbox.admitted_at
            or envelope.producer != WORKFLOW_DISPATCH_EVENT_PRODUCER
            or envelope.producer_version != __version__
            or envelope.subject_type != "workflow-execution-attempt"
            or envelope.subject_id != outbox.attempt_id
            or envelope.organization_id != outbox.scope.organization_id
            or envelope.environment_id != outbox.scope.environment_id
            or envelope.correlation_id != outbox.run_id
            or envelope.causation_id != outbox.dispatch_intent_id
            or envelope.workflow_id != outbox.run_id
            or envelope.data_classification != "internal"
            or envelope.schema_uri != WORKFLOW_DISPATCH_EVENT_SCHEMA_URI
            or envelope.publisher_subject_id != context.subject_id
            or payload.outbox_entry_id != outbox.outbox_entry_id
            or payload.outbox_entry_digest != outbox.canonical_digest
            or payload.dispatch_intent_id != outbox.dispatch_intent_id
            or payload.dispatch_intent_digest != outbox.dispatch_intent_digest
            or payload.plan_id != outbox.plan_id
            or payload.plan_digest != outbox.plan_digest
            or payload.run_id != outbox.run_id
            or payload.run_digest != outbox.run_digest
            or payload.step_run_id != outbox.step_run_id
            or payload.step_run_digest != outbox.step_run_digest
            or payload.step_id != outbox.step_id
            or payload.attempt_id != outbox.attempt_id
            or payload.attempt_digest != outbox.attempt_digest
            or payload.attempt_number != outbox.attempt_number
            or payload.scope != outbox.scope
            or payload.target_id != outbox.target_id
            or payload.target_type != outbox.target_type
            or envelope.orchestration_lease_id != orchestration_lease.lease_id
            or envelope.orchestration_lease_digest != orchestration_lease.canonical_digest
            or envelope.orchestration_fencing_token != orchestration_lease.fencing_token
            or envelope.publication_lease_id != publication_lease.publication_lease_id
            or envelope.publication_lease_digest != publication_lease.canonical_digest
            or envelope.publication_fencing_token != publication_lease.publication_fencing_token
            or envelope.state is not WorkflowDispatchEventEnvelopeState.PREPARED
            or envelope.extensions
            or any(envelope.authority.canonical_value().values())
            or envelope.grants_publication_authority
            or envelope.grants_delivery_authority
            or envelope.grants_dispatch_authority
            or envelope.grants_execution_authority
        ):
            raise WorkflowDispatchEventEnvelopeError(
                "workflow_dispatch_event_envelope_repository_scope_violation",
                "The repository returned an incorrectly bound event envelope.",
            )

    async def _require_publisher(self, context: WorkflowOutboxPublisherContext) -> None:
        if (
            context.actor_type != "service"
            or context.authentication_method != "workload_token"
            or context.credential_audience != WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE
        ):
            await self._deny(
                context, result_code="workflow_dispatch_event_publisher_identity_required"
            )

    async def _success(
        self,
        context: WorkflowOutboxPublisherContext,
        *,
        result_code: str,
        idempotency_key: str,
        outbox: WorkflowDispatchOutboxEntry,
        envelope: WorkflowDispatchEventEnvelope,
    ) -> None:
        await self._audit(
            context,
            outcome="succeeded",
            result_code=result_code,
            idempotency_key=idempotency_key,
            outbox=outbox,
            envelope=envelope,
        )

    async def _deny(
        self,
        context: WorkflowOutboxPublisherContext,
        *,
        result_code: str,
        idempotency_key: str | None = None,
        outbox: WorkflowDispatchOutboxEntry | None = None,
        envelope: WorkflowDispatchEventEnvelope | None = None,
    ) -> NoReturn:
        await self._audit(
            context,
            outcome="denied",
            result_code=result_code,
            idempotency_key=idempotency_key,
            outbox=outbox,
            envelope=envelope,
        )
        raise WorkflowDispatchEventEnvelopeError(
            result_code, "The workflow dispatch event envelope request was denied."
        )

    async def _audit(
        self,
        context: WorkflowOutboxPublisherContext,
        *,
        outcome: str,
        result_code: str,
        idempotency_key: str | None,
        outbox: WorkflowDispatchOutboxEntry | None,
        envelope: WorkflowDispatchEventEnvelope | None,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=(
                    "atlas.workflow.dispatch-event-envelope.preparation.succeeded"
                    if outcome == "succeeded"
                    else "atlas.workflow.dispatch-event-envelope.preparation.denied"
                ),
                schema_version="1.0",
                producer=WORKFLOW_DISPATCH_EVENT_PRODUCER,
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id="workflow.dispatch-event-envelope.prepare",
                resource_type="resource.workflow-dispatch-event-envelope",
                scope_reference="/".join(
                    (
                        context.scope.organization_id,
                        context.scope.environment_id,
                        context.scope.site_id,
                        "workflow-dispatch-event-envelope",
                    )
                ),
                decision_id=context.decision_id,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=(
                    ("outbox_entry_id", "none" if outbox is None else outbox.outbox_entry_id),
                    ("event_id", "none" if envelope is None else envelope.event_id),
                    ("publication_authority", "false"),
                    ("delivery_authority", "false"),
                    ("dispatch_authority", "false"),
                    ("execution_authority", "false"),
                ),
            )
        )

    @staticmethod
    def _identifier(value: str, name: str) -> str:
        normalized = value.strip()
        if not normalized or len(normalized) > 240 or any(char.isspace() for char in normalized):
            raise WorkflowDispatchEventEnvelopeError(
                f"workflow_dispatch_event_{name}_invalid", f"{name} is invalid."
            )
        return normalized

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, "idempotency_key")
        if not 8 <= len(normalized) <= 128:
            raise WorkflowDispatchEventEnvelopeError(
                "workflow_dispatch_event_idempotency_key_invalid",
                "The idempotency key is invalid.",
            )
        return normalized

    @staticmethod
    def _digest(value: str, name: str) -> str:
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise WorkflowDispatchEventEnvelopeError(
                f"workflow_dispatch_event_{name}_invalid",
                f"{name} must be a SHA-256 digest.",
            )
        return value


__all__ = [
    "WORKFLOW_DISPATCH_EVENT_PRODUCER",
    "WORKFLOW_DISPATCH_EVENT_SCHEMA_URI",
    "WORKFLOW_DISPATCH_EVENT_TYPE",
    "WORKFLOW_DISPATCH_EVENT_VERSION",
    "WorkflowDispatchEventEnvelopeService",
]
