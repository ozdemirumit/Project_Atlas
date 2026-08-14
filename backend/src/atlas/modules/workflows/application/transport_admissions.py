from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.event_envelopes import (
    WORKFLOW_DISPATCH_EVENT_PRODUCER,
    WORKFLOW_DISPATCH_EVENT_SCHEMA_URI,
    WORKFLOW_DISPATCH_EVENT_TYPE,
    WORKFLOW_DISPATCH_EVENT_VERSION,
)
from atlas.modules.workflows.application.orchestration_ports import (
    WorkflowOrchestrationLeaseRepository,
)
from atlas.modules.workflows.application.ports import WorkflowPlanRepository
from atlas.modules.workflows.application.publication_leases import (
    WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE,
    WorkflowOutboxPublisherContext,
)
from atlas.modules.workflows.application.transport_admission_ports import (
    WorkflowEventTransportAdmissionError,
    WorkflowEventTransportAdmissionRepository,
    WorkflowEventTransportAdmissionRequest,
    WorkflowEventTransportAdmissionStatus,
)
from atlas.modules.workflows.domain import (
    WorkflowDispatchEventEnvelope,
    WorkflowDispatchEventEnvelopeState,
    WorkflowDispatchOutboxEntry,
    WorkflowDispatchOutboxState,
    WorkflowEventTransportAdmission,
    WorkflowEventTransportAdmissionAuthority,
    WorkflowEventTransportAdmissionPolicy,
    WorkflowEventTransportAdmissionState,
    WorkflowOrchestrationLease,
    WorkflowOrchestrationLeaseEffectiveState,
    WorkflowOutboxPublicationLease,
    WorkflowOutboxPublicationLeaseEffectiveState,
    WorkflowPlanState,
    WorkflowScope,
    canonical_digest,
    canonical_json_byte_count,
    code_owned_workflow_event_transport_admission_policy,
)

WORKFLOW_EVENT_TRANSPORT_ADMISSION_PRODUCER = "project-atlas-workflow-event-control"


class WorkflowEventTransportAdmissionService:
    """Records policy eligibility while granting no operational authority."""

    def __init__(
        self,
        *,
        plan_repository: WorkflowPlanRepository,
        orchestration_lease_repository: WorkflowOrchestrationLeaseRepository,
        transport_admission_repository: WorkflowEventTransportAdmissionRepository,
        audit_sink: AuditSink,
        policy: WorkflowEventTransportAdmissionPolicy | None = None,
    ) -> None:
        self._plan_repository = plan_repository
        self._orchestration_lease_repository = orchestration_lease_repository
        self._transport_admission_repository = transport_admission_repository
        self._audit_sink = audit_sink
        self._policy = policy or code_owned_workflow_event_transport_admission_policy()

    @property
    def durable(self) -> bool:
        return self._transport_admission_repository.durable

    @property
    def policy(self) -> WorkflowEventTransportAdmissionPolicy:
        return self._policy

    @property
    def repository(self) -> WorkflowEventTransportAdmissionRepository:
        return self._transport_admission_repository

    async def admit(
        self,
        *,
        outbox_entry_id: str,
        outbox_entry_digest: str,
        event_id: str,
        event_digest: str,
        policy_id: str,
        policy_version: str,
        policy_digest: str,
        publication_lease_id: str,
        publication_lease_digest: str,
        publication_fencing_token: int,
        idempotency_key: str,
        context: WorkflowOutboxPublisherContext,
    ) -> WorkflowEventTransportAdmission:
        await self._require_publisher(context)
        try:
            normalized_outbox_id = self._identifier(outbox_entry_id, "outbox_entry_id")
            normalized_outbox_digest = self._digest(outbox_entry_digest, "outbox_entry_digest")
            normalized_event_id = self._identifier(event_id, "event_id")
            normalized_event_digest = self._digest(event_digest, "event_digest")
            normalized_policy_id = self._identifier(policy_id, "policy_id")
            normalized_policy_version = self._identifier(policy_version, "policy_version")
            normalized_policy_digest = self._digest(policy_digest, "policy_digest")
            normalized_publication_lease_id = self._identifier(
                publication_lease_id, "publication_lease_id"
            )
            normalized_publication_lease_digest = self._digest(
                publication_lease_digest, "publication_lease_digest"
            )
            if publication_fencing_token < 1:
                raise WorkflowEventTransportAdmissionError(
                    "workflow_event_transport_admission_publication_fence_invalid",
                    "The publication fencing token is invalid.",
                )
            normalized_key = self._idempotency_key(idempotency_key)
        except WorkflowEventTransportAdmissionError as exc:
            await self._deny(context, result_code=exc.code)
            raise

        if (
            normalized_policy_id != self._policy.policy_id
            or normalized_policy_version != self._policy.policy_version
            or normalized_policy_digest != self._policy.canonical_digest
        ):
            await self._deny(
                context,
                result_code="workflow_event_transport_admission_policy_conflict",
                idempotency_key=normalized_key,
            )

        (
            outbox,
            orchestration_lease,
            publication_lease,
            envelope,
        ) = await self._require_current_evidence(
            outbox_entry_id=normalized_outbox_id,
            outbox_entry_digest=normalized_outbox_digest,
            event_id=normalized_event_id,
            event_digest=normalized_event_digest,
            publication_lease_id=normalized_publication_lease_id,
            publication_lease_digest=normalized_publication_lease_digest,
            publication_fencing_token=publication_fencing_token,
            context=context,
            idempotency_key=normalized_key,
        )
        try:
            canonical_byte_count = self._evaluate_policy(envelope)
        except WorkflowEventTransportAdmissionError as exc:
            await self._deny(
                context,
                result_code=exc.code,
                idempotency_key=normalized_key,
                outbox=outbox,
            )
        fingerprint = canonical_digest(
            {
                "event_digest": envelope.canonical_digest,
                "event_id": envelope.event_id,
                "idempotency_key": normalized_key,
                "operation": "workflow.event-transport-admission.admit",
                "orchestration_fencing_token": orchestration_lease.fencing_token,
                "orchestration_lease_digest": orchestration_lease.canonical_digest,
                "orchestration_lease_id": orchestration_lease.lease_id,
                "outbox_entry_digest": outbox.canonical_digest,
                "outbox_entry_id": outbox.outbox_entry_id,
                "policy_digest": self._policy.canonical_digest,
                "policy_id": self._policy.policy_id,
                "policy_version": self._policy.policy_version,
                "publication_fencing_token": publication_lease.publication_fencing_token,
                "publication_lease_digest": publication_lease.canonical_digest,
                "publication_lease_id": publication_lease.publication_lease_id,
                "publisher_subject_id": context.subject_id,
                "scope": outbox.scope.canonical_value(),
                "target_id": outbox.target_id,
                "target_type": outbox.target_type,
            }
        )
        prior = await self._transport_admission_repository.get_event_transport_admission_request(
            scope=context.scope,
            publisher_subject_id=context.subject_id,
            idempotency_key=normalized_key,
        )
        if prior is not None:
            if prior.request_fingerprint != fingerprint:
                await self._deny(
                    context,
                    result_code="workflow_event_transport_admission_idempotency_conflict",
                    idempotency_key=normalized_key,
                    outbox=outbox,
                    admission=prior.admission,
                )
            try:
                self._validate_admission(
                    prior.admission,
                    policy=self._policy,
                    envelope=envelope,
                    outbox=outbox,
                    orchestration_lease=orchestration_lease,
                    publication_lease=publication_lease,
                    canonical_byte_count=canonical_byte_count,
                    context=context,
                )
            except WorkflowEventTransportAdmissionError as exc:
                await self._deny(
                    context,
                    result_code=exc.code,
                    idempotency_key=normalized_key,
                    outbox=outbox,
                    admission=prior.admission,
                )
            await self._success(
                context,
                result_code="workflow_event_transport_admission_replayed",
                idempotency_key=normalized_key,
                outbox=outbox,
                admission=prior.admission,
            )
            return prior.admission

        current = (
            await self._transport_admission_repository.get_event_transport_admission_by_event_id(
                event_id=envelope.event_id
            )
        )
        if current is not None:
            await self._deny(
                context,
                result_code=(
                    "workflow_event_transport_admission_competing_identity"
                    if current.publisher_subject_id != context.subject_id
                    else "workflow_event_transport_admission_already_admitted"
                ),
                idempotency_key=normalized_key,
                outbox=outbox,
                admission=current,
            )

        candidate = self._build_admission(
            policy=self._policy,
            envelope=envelope,
            canonical_byte_count=canonical_byte_count,
            admitted_at=context.requested_at,
        )
        result = await self._transport_admission_repository.admit_event_transport(
            WorkflowEventTransportAdmissionRequest(
                expected_plan_digest=outbox.plan_digest,
                expected_outbox_entry_digest=outbox.canonical_digest,
                expected_event_id=envelope.event_id,
                expected_event_digest=envelope.canonical_digest,
                expected_policy_digest=self._policy.canonical_digest,
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
            WorkflowEventTransportAdmissionStatus.ADMITTED,
            WorkflowEventTransportAdmissionStatus.REPLAY,
        }:
            if result.admission is None:
                raise WorkflowEventTransportAdmissionError(
                    "workflow_event_transport_admission_repository_contract_violation",
                    "The repository returned an incomplete admission result.",
                )
            try:
                self._validate_admission(
                    result.admission,
                    policy=self._policy,
                    envelope=envelope,
                    outbox=outbox,
                    orchestration_lease=orchestration_lease,
                    publication_lease=publication_lease,
                    canonical_byte_count=canonical_byte_count,
                    context=context,
                )
            except WorkflowEventTransportAdmissionError as exc:
                await self._deny(
                    context,
                    result_code=exc.code,
                    idempotency_key=normalized_key,
                    outbox=outbox,
                    admission=result.admission,
                )
            await self._success(
                context,
                result_code=(
                    "workflow_event_transport_admission_replayed"
                    if result.status is WorkflowEventTransportAdmissionStatus.REPLAY
                    else "workflow_event_transport_admitted"
                ),
                idempotency_key=normalized_key,
                outbox=outbox,
                admission=result.admission,
            )
            return result.admission
        code = {
            WorkflowEventTransportAdmissionStatus.IDEMPOTENCY_CONFLICT: (
                "workflow_event_transport_admission_idempotency_conflict"
            ),
            WorkflowEventTransportAdmissionStatus.ALREADY_ADMITTED: (
                "workflow_event_transport_admission_already_admitted"
            ),
        }.get(result.status, "workflow_event_transport_admission_evidence_conflict")
        await self._deny(
            context,
            result_code=code,
            idempotency_key=normalized_key,
            outbox=outbox,
            admission=result.admission,
        )

    async def _require_current_evidence(
        self,
        *,
        outbox_entry_id: str,
        outbox_entry_digest: str,
        event_id: str,
        event_digest: str,
        publication_lease_id: str,
        publication_lease_digest: str,
        publication_fencing_token: int,
        context: WorkflowOutboxPublisherContext,
        idempotency_key: str,
    ) -> tuple[
        WorkflowDispatchOutboxEntry,
        WorkflowOrchestrationLease,
        WorkflowOutboxPublicationLease,
        WorkflowDispatchEventEnvelope,
    ]:
        outbox = await self._transport_admission_repository.get_outbox_entry_by_id(
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
                result_code="workflow_event_transport_admission_outbox_not_found",
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
                result_code="workflow_event_transport_admission_outbox_conflict",
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
                result_code="workflow_event_transport_admission_plan_not_found",
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
                result_code="workflow_event_transport_admission_plan_conflict",
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
                result_code="workflow_event_transport_admission_orchestration_lease_conflict",
                idempotency_key=idempotency_key,
                outbox=outbox,
            )
        assert orchestration_lease is not None
        publication_lease = (
            await self._transport_admission_repository.get_publication_lease_by_outbox_entry_id(
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
                result_code="workflow_event_transport_admission_publication_lease_conflict",
                idempotency_key=idempotency_key,
                outbox=outbox,
            )
        assert publication_lease is not None
        envelope = await (
            self._transport_admission_repository.get_dispatch_event_envelope_by_outbox_entry_id(
                outbox_entry_id=outbox.outbox_entry_id
            )
        )
        if envelope is None:
            await self._deny(
                context,
                result_code="workflow_event_transport_admission_envelope_not_found",
                idempotency_key=idempotency_key,
                outbox=outbox,
            )
        assert envelope is not None
        if envelope.event_id != event_id or envelope.canonical_digest != event_digest:
            await self._deny(
                context,
                result_code="workflow_event_transport_admission_envelope_conflict",
                idempotency_key=idempotency_key,
                outbox=outbox,
            )
        try:
            self._validate_envelope(
                envelope, outbox, orchestration_lease, publication_lease, context
            )
        except WorkflowEventTransportAdmissionError as exc:
            await self._deny(
                context,
                result_code=exc.code,
                idempotency_key=idempotency_key,
                outbox=outbox,
            )
        return outbox, orchestration_lease, publication_lease, envelope

    def _evaluate_policy(self, envelope: WorkflowDispatchEventEnvelope) -> int:
        policy = self._policy
        if (
            envelope.event_type not in policy.allowed_event_types
            or envelope.event_version not in policy.allowed_event_versions
            or envelope.schema_uri not in policy.allowed_schema_uris
            or envelope.data_classification not in policy.allowed_data_classifications
        ):
            raise WorkflowEventTransportAdmissionError(
                "workflow_event_transport_admission_policy_rejected",
                "The prepared event envelope is not supported by the active policy.",
            )
        byte_count = canonical_json_byte_count(envelope.canonical_value())
        if byte_count > policy.maximum_canonical_byte_count:
            raise WorkflowEventTransportAdmissionError(
                "workflow_event_transport_admission_canonical_size_exceeded",
                "The prepared event envelope exceeds the active canonical byte limit.",
            )
        return byte_count

    @staticmethod
    def _build_admission(
        *,
        policy: WorkflowEventTransportAdmissionPolicy,
        envelope: WorkflowDispatchEventEnvelope,
        canonical_byte_count: int,
        admitted_at: datetime,
    ) -> WorkflowEventTransportAdmission:
        payload = envelope.payload
        admission_id = (
            "workflow-event-transport-admission."
            + sha256(
                f"{envelope.event_id}:{envelope.canonical_digest}:{policy.canonical_digest}".encode()
            ).hexdigest()[:24]
        )
        values: dict[str, object] = {
            "admission_id": admission_id,
            "policy_id": policy.policy_id,
            "policy_version": policy.policy_version,
            "policy_digest": policy.canonical_digest,
            "event_id": envelope.event_id,
            "event_digest": envelope.canonical_digest,
            "event_type": envelope.event_type,
            "event_version": envelope.event_version,
            "schema_uri": envelope.schema_uri,
            "data_classification": envelope.data_classification,
            "representation_name": policy.representation_name,
            "encoding": policy.encoding,
            "canonical_byte_count": canonical_byte_count,
            "maximum_canonical_byte_count": policy.maximum_canonical_byte_count,
            "outbox_entry_id": payload.outbox_entry_id,
            "outbox_entry_digest": payload.outbox_entry_digest,
            "dispatch_intent_id": payload.dispatch_intent_id,
            "dispatch_intent_digest": payload.dispatch_intent_digest,
            "plan_id": payload.plan_id,
            "plan_digest": payload.plan_digest,
            "run_id": payload.run_id,
            "run_digest": payload.run_digest,
            "step_run_id": payload.step_run_id,
            "step_run_digest": payload.step_run_digest,
            "step_id": payload.step_id,
            "attempt_id": payload.attempt_id,
            "attempt_digest": payload.attempt_digest,
            "attempt_number": payload.attempt_number,
            "scope": payload.scope,
            "target_id": payload.target_id,
            "target_type": payload.target_type,
            "orchestration_lease_id": envelope.orchestration_lease_id,
            "orchestration_lease_digest": envelope.orchestration_lease_digest,
            "orchestration_fencing_token": envelope.orchestration_fencing_token,
            "publication_lease_id": envelope.publication_lease_id,
            "publication_lease_digest": envelope.publication_lease_digest,
            "publication_fencing_token": envelope.publication_fencing_token,
            "publisher_subject_id": envelope.publisher_subject_id,
            "admitted_at": admitted_at,
            "state": WorkflowEventTransportAdmissionState.ADMITTED,
            "authority": WorkflowEventTransportAdmissionAuthority(),
        }
        digest_payload = {
            key: value.canonical_value()
            if isinstance(value, (WorkflowEventTransportAdmissionAuthority, WorkflowScope))
            else value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(value, WorkflowEventTransportAdmissionState)
            else value
            for key, value in values.items()
        }
        return WorkflowEventTransportAdmission(
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

    @staticmethod
    def _validate_envelope(
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
            or envelope.schema_uri != WORKFLOW_DISPATCH_EVENT_SCHEMA_URI
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
            or envelope.state is not WorkflowDispatchEventEnvelopeState.PREPARED
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
            or envelope.extensions
            or any(envelope.authority.canonical_value().values())
            or envelope.grants_publication_authority
            or envelope.grants_delivery_authority
            or envelope.grants_dispatch_authority
            or envelope.grants_execution_authority
        ):
            raise WorkflowEventTransportAdmissionError(
                "workflow_event_transport_admission_envelope_scope_violation",
                "The repository returned an incorrectly bound prepared event envelope.",
            )

    @staticmethod
    def _validate_admission(
        admission: WorkflowEventTransportAdmission,
        *,
        policy: WorkflowEventTransportAdmissionPolicy,
        envelope: WorkflowDispatchEventEnvelope,
        outbox: WorkflowDispatchOutboxEntry,
        orchestration_lease: WorkflowOrchestrationLease,
        publication_lease: WorkflowOutboxPublicationLease,
        canonical_byte_count: int,
        context: WorkflowOutboxPublisherContext,
    ) -> None:
        payload = envelope.payload
        expected_admission_id = (
            "workflow-event-transport-admission."
            + sha256(
                f"{envelope.event_id}:{envelope.canonical_digest}:{policy.canonical_digest}".encode()
            ).hexdigest()[:24]
        )
        if (
            admission.admission_id != expected_admission_id
            or admission.policy_id != policy.policy_id
            or admission.policy_version != policy.policy_version
            or admission.policy_digest != policy.canonical_digest
            or admission.event_id != envelope.event_id
            or admission.event_digest != envelope.canonical_digest
            or admission.event_type != envelope.event_type
            or admission.event_version != envelope.event_version
            or admission.schema_uri != envelope.schema_uri
            or admission.data_classification != envelope.data_classification
            or admission.representation_name != policy.representation_name
            or admission.encoding != policy.encoding
            or admission.canonical_byte_count != canonical_byte_count
            or admission.maximum_canonical_byte_count != policy.maximum_canonical_byte_count
            or admission.outbox_entry_id != outbox.outbox_entry_id
            or admission.outbox_entry_digest != outbox.canonical_digest
            or admission.dispatch_intent_id != payload.dispatch_intent_id
            or admission.dispatch_intent_digest != payload.dispatch_intent_digest
            or admission.plan_id != payload.plan_id
            or admission.plan_digest != payload.plan_digest
            or admission.run_id != payload.run_id
            or admission.run_digest != payload.run_digest
            or admission.step_run_id != payload.step_run_id
            or admission.step_run_digest != payload.step_run_digest
            or admission.step_id != payload.step_id
            or admission.attempt_id != payload.attempt_id
            or admission.attempt_digest != payload.attempt_digest
            or admission.attempt_number != payload.attempt_number
            or admission.scope != payload.scope
            or admission.target_id != payload.target_id
            or admission.target_type != payload.target_type
            or admission.orchestration_lease_id != orchestration_lease.lease_id
            or admission.orchestration_lease_digest != orchestration_lease.canonical_digest
            or admission.orchestration_fencing_token != orchestration_lease.fencing_token
            or admission.publication_lease_id != publication_lease.publication_lease_id
            or admission.publication_lease_digest != publication_lease.canonical_digest
            or admission.publication_fencing_token != publication_lease.publication_fencing_token
            or admission.publisher_subject_id != context.subject_id
            or admission.admitted_at < envelope.prepared_at
            or admission.admitted_at > context.requested_at
            or admission.state is not WorkflowEventTransportAdmissionState.ADMITTED
            or any(admission.authority.canonical_value().values())
            or admission.grants_publication_authority
            or admission.grants_delivery_authority
            or admission.grants_dispatch_authority
            or admission.grants_execution_authority
        ):
            raise WorkflowEventTransportAdmissionError(
                "workflow_event_transport_admission_repository_scope_violation",
                "The repository returned incorrectly bound transport admission evidence.",
            )

    async def _require_publisher(self, context: WorkflowOutboxPublisherContext) -> None:
        if (
            context.actor_type != "service"
            or context.authentication_method != "workload_token"
            or context.credential_audience != WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE
        ):
            await self._deny(
                context,
                result_code="workflow_event_transport_admission_publisher_identity_required",
            )

    async def _success(
        self,
        context: WorkflowOutboxPublisherContext,
        *,
        result_code: str,
        idempotency_key: str,
        outbox: WorkflowDispatchOutboxEntry,
        admission: WorkflowEventTransportAdmission,
    ) -> None:
        await self._audit(
            context,
            outcome="succeeded",
            result_code=result_code,
            idempotency_key=idempotency_key,
            outbox=outbox,
            admission=admission,
        )

    async def _deny(
        self,
        context: WorkflowOutboxPublisherContext,
        *,
        result_code: str,
        idempotency_key: str | None = None,
        outbox: WorkflowDispatchOutboxEntry | None = None,
        admission: WorkflowEventTransportAdmission | None = None,
    ) -> NoReturn:
        await self._audit(
            context,
            outcome="denied",
            result_code=result_code,
            idempotency_key=idempotency_key,
            outbox=outbox,
            admission=admission,
        )
        raise WorkflowEventTransportAdmissionError(
            result_code, "The workflow event transport admission request was denied."
        )

    async def _audit(
        self,
        context: WorkflowOutboxPublisherContext,
        *,
        outcome: str,
        result_code: str,
        idempotency_key: str | None,
        outbox: WorkflowDispatchOutboxEntry | None,
        admission: WorkflowEventTransportAdmission | None,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=(
                    "atlas.workflow.event-transport-admission.succeeded"
                    if outcome == "succeeded"
                    else "atlas.workflow.event-transport-admission.denied"
                ),
                schema_version="1.0",
                producer=WORKFLOW_EVENT_TRANSPORT_ADMISSION_PRODUCER,
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id="workflow.event-transport-admission.admit",
                resource_type="resource.workflow-event-transport-admission",
                scope_reference="/".join(
                    (
                        context.scope.organization_id,
                        context.scope.environment_id,
                        context.scope.site_id,
                        "workflow-event-transport-admission",
                    )
                ),
                decision_id=context.decision_id,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=(
                    ("outbox_entry_id", "none" if outbox is None else outbox.outbox_entry_id),
                    ("admission_id", "none" if admission is None else admission.admission_id),
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
            raise WorkflowEventTransportAdmissionError(
                f"workflow_event_transport_admission_{name}_invalid", f"{name} is invalid."
            )
        return normalized

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, "idempotency_key")
        if not 8 <= len(normalized) <= 128:
            raise WorkflowEventTransportAdmissionError(
                "workflow_event_transport_admission_idempotency_key_invalid",
                "The idempotency key is invalid.",
            )
        return normalized

    @staticmethod
    def _digest(value: str, name: str) -> str:
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise WorkflowEventTransportAdmissionError(
                f"workflow_event_transport_admission_{name}_invalid",
                f"{name} must be a SHA-256 digest.",
            )
        return value


__all__ = [
    "WORKFLOW_EVENT_TRANSPORT_ADMISSION_PRODUCER",
    "WorkflowEventTransportAdmissionService",
]
