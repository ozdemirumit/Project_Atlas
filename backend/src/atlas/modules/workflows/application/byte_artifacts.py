from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.byte_artifact_ports import (
    WorkflowEventByteArtifactError,
    WorkflowEventByteArtifactRepository,
    WorkflowEventByteArtifactRequest,
    WorkflowEventByteArtifactStatus,
)
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
from atlas.modules.workflows.domain import (
    WorkflowDispatchEventEnvelope,
    WorkflowDispatchEventEnvelopeState,
    WorkflowDispatchOutboxEntry,
    WorkflowDispatchOutboxState,
    WorkflowEventByteArtifact,
    WorkflowEventByteArtifactAuthority,
    WorkflowEventByteArtifactState,
    WorkflowEventTransportAdmission,
    WorkflowEventTransportAdmissionPolicy,
    WorkflowEventTransportAdmissionState,
    WorkflowOrchestrationLease,
    WorkflowOrchestrationLeaseEffectiveState,
    WorkflowOutboxPublicationLease,
    WorkflowOutboxPublicationLeaseEffectiveState,
    WorkflowPlanState,
    WorkflowScope,
    canonical_digest,
    canonical_json_bytes,
    code_owned_workflow_event_transport_admission_policy,
)

WORKFLOW_EVENT_BYTE_ARTIFACT_PRODUCER = "project-atlas-workflow-event-control"


class WorkflowEventByteArtifactService:
    """Materializes admitted canonical bytes without selecting or invoking transport."""

    def __init__(
        self,
        *,
        plan_repository: WorkflowPlanRepository,
        orchestration_lease_repository: WorkflowOrchestrationLeaseRepository,
        byte_artifact_repository: WorkflowEventByteArtifactRepository,
        audit_sink: AuditSink,
        policy: WorkflowEventTransportAdmissionPolicy | None = None,
    ) -> None:
        self._plan_repository = plan_repository
        self._orchestration_lease_repository = orchestration_lease_repository
        self._byte_artifact_repository = byte_artifact_repository
        self._audit_sink = audit_sink
        self._policy = policy or code_owned_workflow_event_transport_admission_policy()

    @property
    def durable(self) -> bool:
        return self._byte_artifact_repository.durable

    @property
    def repository(self) -> WorkflowEventByteArtifactRepository:
        return self._byte_artifact_repository

    async def materialize(
        self,
        *,
        outbox_entry_id: str,
        outbox_entry_digest: str,
        event_id: str,
        event_digest: str,
        admission_id: str,
        admission_digest: str,
        policy_id: str,
        policy_version: str,
        policy_digest: str,
        publication_lease_id: str,
        publication_lease_digest: str,
        publication_fencing_token: int,
        idempotency_key: str,
        context: WorkflowOutboxPublisherContext,
    ) -> WorkflowEventByteArtifact:
        await self._require_publisher(context)
        try:
            normalized = {
                "outbox_entry_id": self._identifier(outbox_entry_id, "outbox_entry_id"),
                "outbox_entry_digest": self._digest(outbox_entry_digest, "outbox_entry_digest"),
                "event_id": self._identifier(event_id, "event_id"),
                "event_digest": self._digest(event_digest, "event_digest"),
                "admission_id": self._identifier(admission_id, "admission_id"),
                "admission_digest": self._digest(admission_digest, "admission_digest"),
                "policy_id": self._identifier(policy_id, "policy_id"),
                "policy_version": self._identifier(policy_version, "policy_version"),
                "policy_digest": self._digest(policy_digest, "policy_digest"),
                "publication_lease_id": self._identifier(
                    publication_lease_id, "publication_lease_id"
                ),
                "publication_lease_digest": self._digest(
                    publication_lease_digest, "publication_lease_digest"
                ),
            }
            if publication_fencing_token < 1:
                raise WorkflowEventByteArtifactError(
                    "workflow_event_byte_artifact_publication_fence_invalid",
                    "The publication fencing token is invalid.",
                )
            normalized_key = self._idempotency_key(idempotency_key)
        except WorkflowEventByteArtifactError as exc:
            await self._deny(context, result_code=exc.code)

        if (
            normalized["policy_id"] != self._policy.policy_id
            or normalized["policy_version"] != self._policy.policy_version
            or normalized["policy_digest"] != self._policy.canonical_digest
        ):
            await self._deny(
                context,
                result_code="workflow_event_byte_artifact_policy_conflict",
                idempotency_key=normalized_key,
            )

        (
            outbox,
            orchestration_lease,
            publication_lease,
            envelope,
            admission,
        ) = await self._require_current_evidence(
            outbox_entry_id=normalized["outbox_entry_id"],
            outbox_entry_digest=normalized["outbox_entry_digest"],
            event_id=normalized["event_id"],
            event_digest=normalized["event_digest"],
            admission_id=normalized["admission_id"],
            admission_digest=normalized["admission_digest"],
            publication_lease_id=normalized["publication_lease_id"],
            publication_lease_digest=normalized["publication_lease_digest"],
            publication_fencing_token=publication_fencing_token,
            context=context,
            idempotency_key=normalized_key,
        )
        canonical_bytes = canonical_json_bytes(envelope.canonical_value())
        content_sha256 = sha256(canonical_bytes).hexdigest()
        if (
            len(canonical_bytes) != admission.canonical_byte_count
            or len(canonical_bytes) > admission.maximum_canonical_byte_count
            or len(canonical_bytes) > self._policy.maximum_canonical_byte_count
        ):
            await self._deny(
                context,
                result_code="workflow_event_byte_artifact_canonical_size_conflict",
                idempotency_key=normalized_key,
                outbox=outbox,
                admission=admission,
            )

        fingerprint = canonical_digest(
            {
                "admission_digest": admission.canonical_digest,
                "admission_id": admission.admission_id,
                "content_sha256": content_sha256,
                "event_digest": envelope.canonical_digest,
                "event_id": envelope.event_id,
                "idempotency_key": normalized_key,
                "operation": "workflow.event-byte-artifact.materialize",
                "orchestration_fencing_token": orchestration_lease.fencing_token,
                "orchestration_lease_digest": orchestration_lease.canonical_digest,
                "orchestration_lease_id": orchestration_lease.lease_id,
                "outbox_entry_digest": outbox.canonical_digest,
                "outbox_entry_id": outbox.outbox_entry_id,
                "policy_digest": self._policy.canonical_digest,
                "publication_fencing_token": publication_lease.publication_fencing_token,
                "publication_lease_digest": publication_lease.canonical_digest,
                "publication_lease_id": publication_lease.publication_lease_id,
                "publisher_subject_id": context.subject_id,
                "scope": outbox.scope.canonical_value(),
                "target_id": outbox.target_id,
                "target_type": outbox.target_type,
            }
        )
        prior = await self._byte_artifact_repository.get_event_byte_artifact_request(
            scope=context.scope,
            publisher_subject_id=context.subject_id,
            idempotency_key=normalized_key,
        )
        if prior is not None:
            if prior.request_fingerprint != fingerprint:
                await self._deny(
                    context,
                    result_code="workflow_event_byte_artifact_idempotency_conflict",
                    idempotency_key=normalized_key,
                    outbox=outbox,
                    admission=admission,
                    artifact=prior.artifact,
                )
            await self._validate_or_deny(
                prior.artifact,
                canonical_bytes=canonical_bytes,
                admission=admission,
                envelope=envelope,
                outbox=outbox,
                orchestration_lease=orchestration_lease,
                publication_lease=publication_lease,
                context=context,
                idempotency_key=normalized_key,
            )
            await self._success(
                context,
                result_code="workflow_event_byte_artifact_replayed",
                idempotency_key=normalized_key,
                outbox=outbox,
                admission=admission,
                artifact=prior.artifact,
            )
            return prior.artifact

        current = await self._byte_artifact_repository.get_event_byte_artifact_by_admission_id(
            admission_id=admission.admission_id
        )
        if current is not None:
            await self._deny(
                context,
                result_code=(
                    "workflow_event_byte_artifact_competing_identity"
                    if current.publisher_subject_id != context.subject_id
                    else "workflow_event_byte_artifact_already_materialized"
                ),
                idempotency_key=normalized_key,
                outbox=outbox,
                admission=admission,
                artifact=current,
            )

        candidate = self._build_artifact(
            admission=admission,
            canonical_bytes=canonical_bytes,
            content_sha256=content_sha256,
            materialized_at=context.requested_at,
        )
        result = await self._byte_artifact_repository.materialize_event_byte_artifact(
            WorkflowEventByteArtifactRequest(
                expected_plan_digest=outbox.plan_digest,
                expected_outbox_entry_digest=outbox.canonical_digest,
                expected_event_id=envelope.event_id,
                expected_event_digest=envelope.canonical_digest,
                expected_admission_id=admission.admission_id,
                expected_admission_digest=admission.canonical_digest,
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
            WorkflowEventByteArtifactStatus.MATERIALIZED,
            WorkflowEventByteArtifactStatus.REPLAY,
        }:
            if result.artifact is None:
                raise WorkflowEventByteArtifactError(
                    "workflow_event_byte_artifact_repository_contract_violation",
                    "The repository returned an incomplete artifact result.",
                )
            await self._validate_or_deny(
                result.artifact,
                canonical_bytes=canonical_bytes,
                admission=admission,
                envelope=envelope,
                outbox=outbox,
                orchestration_lease=orchestration_lease,
                publication_lease=publication_lease,
                context=context,
                idempotency_key=normalized_key,
            )
            await self._success(
                context,
                result_code=(
                    "workflow_event_byte_artifact_replayed"
                    if result.status is WorkflowEventByteArtifactStatus.REPLAY
                    else "workflow_event_byte_artifact_materialized"
                ),
                idempotency_key=normalized_key,
                outbox=outbox,
                admission=admission,
                artifact=result.artifact,
            )
            return result.artifact
        code = {
            WorkflowEventByteArtifactStatus.IDEMPOTENCY_CONFLICT: (
                "workflow_event_byte_artifact_idempotency_conflict"
            ),
            WorkflowEventByteArtifactStatus.ALREADY_MATERIALIZED: (
                "workflow_event_byte_artifact_already_materialized"
            ),
        }.get(result.status, "workflow_event_byte_artifact_evidence_conflict")
        await self._deny(
            context,
            result_code=code,
            idempotency_key=normalized_key,
            outbox=outbox,
            admission=admission,
            artifact=result.artifact,
        )

    async def _require_current_evidence(
        self,
        *,
        outbox_entry_id: str,
        outbox_entry_digest: str,
        event_id: str,
        event_digest: str,
        admission_id: str,
        admission_digest: str,
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
        WorkflowEventTransportAdmission,
    ]:
        outbox = await self._byte_artifact_repository.get_outbox_entry_by_id(
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
                result_code="workflow_event_byte_artifact_outbox_not_found",
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
                result_code="workflow_event_byte_artifact_outbox_conflict",
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
                result_code="workflow_event_byte_artifact_plan_not_found",
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
                result_code="workflow_event_byte_artifact_plan_conflict",
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
                result_code="workflow_event_byte_artifact_orchestration_lease_conflict",
                idempotency_key=idempotency_key,
                outbox=outbox,
            )
        assert orchestration_lease is not None
        publication_lease = (
            await self._byte_artifact_repository.get_publication_lease_by_outbox_entry_id(
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
                result_code="workflow_event_byte_artifact_publication_lease_conflict",
                idempotency_key=idempotency_key,
                outbox=outbox,
            )
        assert publication_lease is not None
        envelope = (
            await self._byte_artifact_repository.get_dispatch_event_envelope_by_outbox_entry_id(
                outbox_entry_id=outbox.outbox_entry_id
            )
        )
        if envelope is None:
            await self._deny(
                context,
                result_code="workflow_event_byte_artifact_envelope_not_found",
                idempotency_key=idempotency_key,
                outbox=outbox,
            )
        assert envelope is not None
        if envelope.event_id != event_id or envelope.canonical_digest != event_digest:
            await self._deny(
                context,
                result_code="workflow_event_byte_artifact_envelope_conflict",
                idempotency_key=idempotency_key,
                outbox=outbox,
            )
        try:
            self._validate_envelope(
                envelope, outbox, orchestration_lease, publication_lease, context
            )
        except WorkflowEventByteArtifactError as exc:
            await self._deny(
                context,
                result_code=exc.code,
                idempotency_key=idempotency_key,
                outbox=outbox,
            )
        admission = await self._byte_artifact_repository.get_event_transport_admission_by_event_id(
            event_id=envelope.event_id
        )
        if admission is None:
            await self._deny(
                context,
                result_code="workflow_event_byte_artifact_admission_not_found",
                idempotency_key=idempotency_key,
                outbox=outbox,
            )
        assert admission is not None
        if admission.admission_id != admission_id or admission.canonical_digest != admission_digest:
            await self._deny(
                context,
                result_code="workflow_event_byte_artifact_admission_conflict",
                idempotency_key=idempotency_key,
                outbox=outbox,
                admission=admission,
            )
        try:
            self._validate_admission(
                admission,
                envelope=envelope,
                outbox=outbox,
                orchestration_lease=orchestration_lease,
                publication_lease=publication_lease,
                context=context,
            )
        except WorkflowEventByteArtifactError as exc:
            await self._deny(
                context,
                result_code=exc.code,
                idempotency_key=idempotency_key,
                outbox=outbox,
                admission=admission,
            )
        return outbox, orchestration_lease, publication_lease, envelope, admission

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
            or envelope.occurred_at != outbox.admitted_at
            or envelope.recorded_at != envelope.prepared_at
            or envelope.recorded_at < outbox.admitted_at
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
            raise WorkflowEventByteArtifactError(
                "workflow_event_byte_artifact_envelope_scope_violation",
                "The prepared event envelope is incorrectly bound.",
            )

    def _validate_admission(
        self,
        admission: WorkflowEventTransportAdmission,
        *,
        envelope: WorkflowDispatchEventEnvelope,
        outbox: WorkflowDispatchOutboxEntry,
        orchestration_lease: WorkflowOrchestrationLease,
        publication_lease: WorkflowOutboxPublicationLease,
        context: WorkflowOutboxPublisherContext,
    ) -> None:
        payload = envelope.payload
        expected_admission_id = (
            "workflow-event-transport-admission."
            + sha256(
                f"{envelope.event_id}:{envelope.canonical_digest}:{self._policy.canonical_digest}".encode()
            ).hexdigest()[:24]
        )
        fields = (
            "outbox_entry_id",
            "outbox_entry_digest",
            "dispatch_intent_id",
            "dispatch_intent_digest",
            "plan_id",
            "plan_digest",
            "run_id",
            "run_digest",
            "step_run_id",
            "step_run_digest",
            "step_id",
            "attempt_id",
            "attempt_digest",
            "attempt_number",
            "scope",
            "target_id",
            "target_type",
        )
        canonical_bytes = canonical_json_bytes(envelope.canonical_value())
        if (
            admission.admission_id != expected_admission_id
            or admission.policy_id != self._policy.policy_id
            or admission.policy_version != self._policy.policy_version
            or admission.policy_digest != self._policy.canonical_digest
            or admission.event_id != envelope.event_id
            or admission.event_digest != envelope.canonical_digest
            or admission.event_type != envelope.event_type
            or admission.event_version != envelope.event_version
            or admission.schema_uri != envelope.schema_uri
            or admission.data_classification != envelope.data_classification
            or admission.representation_name != self._policy.representation_name
            or admission.encoding != self._policy.encoding
            or admission.canonical_byte_count != len(canonical_bytes)
            or admission.maximum_canonical_byte_count != self._policy.maximum_canonical_byte_count
            or not all(getattr(admission, name) == getattr(payload, name) for name in fields)
            or admission.outbox_entry_id != outbox.outbox_entry_id
            or admission.outbox_entry_digest != outbox.canonical_digest
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
            raise WorkflowEventByteArtifactError(
                "workflow_event_byte_artifact_admission_scope_violation",
                "The transport admission is incorrectly bound.",
            )

    @staticmethod
    def _build_artifact(
        *,
        admission: WorkflowEventTransportAdmission,
        canonical_bytes: bytes,
        content_sha256: str,
        materialized_at: datetime,
    ) -> WorkflowEventByteArtifact:
        artifact_id = (
            "workflow-event-byte-artifact."
            + sha256(
                f"{admission.admission_id}:{admission.canonical_digest}:{content_sha256}".encode()
            ).hexdigest()[:24]
        )
        values: dict[str, object] = {
            "artifact_id": artifact_id,
            "admission_id": admission.admission_id,
            "admission_digest": admission.canonical_digest,
            "policy_id": admission.policy_id,
            "policy_version": admission.policy_version,
            "policy_digest": admission.policy_digest,
            "event_id": admission.event_id,
            "event_digest": admission.event_digest,
            "event_type": admission.event_type,
            "event_version": admission.event_version,
            "schema_uri": admission.schema_uri,
            "data_classification": admission.data_classification,
            "representation_name": admission.representation_name,
            "encoding": admission.encoding,
            "canonical_bytes": canonical_bytes,
            "canonical_byte_count": len(canonical_bytes),
            "content_sha256": content_sha256,
            "maximum_canonical_byte_count": admission.maximum_canonical_byte_count,
            "outbox_entry_id": admission.outbox_entry_id,
            "outbox_entry_digest": admission.outbox_entry_digest,
            "dispatch_intent_id": admission.dispatch_intent_id,
            "dispatch_intent_digest": admission.dispatch_intent_digest,
            "plan_id": admission.plan_id,
            "plan_digest": admission.plan_digest,
            "run_id": admission.run_id,
            "run_digest": admission.run_digest,
            "step_run_id": admission.step_run_id,
            "step_run_digest": admission.step_run_digest,
            "step_id": admission.step_id,
            "attempt_id": admission.attempt_id,
            "attempt_digest": admission.attempt_digest,
            "attempt_number": admission.attempt_number,
            "scope": admission.scope,
            "target_id": admission.target_id,
            "target_type": admission.target_type,
            "orchestration_lease_id": admission.orchestration_lease_id,
            "orchestration_lease_digest": admission.orchestration_lease_digest,
            "orchestration_fencing_token": admission.orchestration_fencing_token,
            "publication_lease_id": admission.publication_lease_id,
            "publication_lease_digest": admission.publication_lease_digest,
            "publication_fencing_token": admission.publication_fencing_token,
            "publisher_subject_id": admission.publisher_subject_id,
            "materialized_at": materialized_at,
            "state": WorkflowEventByteArtifactState.MATERIALIZED,
            "authority": WorkflowEventByteArtifactAuthority(),
        }
        digest_payload = {
            key: value.canonical_value()
            if isinstance(value, (WorkflowEventByteArtifactAuthority, WorkflowScope))
            else value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(value, WorkflowEventByteArtifactState)
            else value
            for key, value in values.items()
            if key != "canonical_bytes"
        }
        return WorkflowEventByteArtifact(
            **cast(Any, values), canonical_digest=canonical_digest(digest_payload)
        )

    async def _validate_or_deny(
        self,
        artifact: WorkflowEventByteArtifact,
        *,
        canonical_bytes: bytes,
        admission: WorkflowEventTransportAdmission,
        envelope: WorkflowDispatchEventEnvelope,
        outbox: WorkflowDispatchOutboxEntry,
        orchestration_lease: WorkflowOrchestrationLease,
        publication_lease: WorkflowOutboxPublicationLease,
        context: WorkflowOutboxPublisherContext,
        idempotency_key: str,
    ) -> None:
        try:
            self._validate_artifact(
                artifact,
                canonical_bytes=canonical_bytes,
                admission=admission,
                envelope=envelope,
                outbox=outbox,
                orchestration_lease=orchestration_lease,
                publication_lease=publication_lease,
                context=context,
            )
        except WorkflowEventByteArtifactError as exc:
            await self._deny(
                context,
                result_code=exc.code,
                idempotency_key=idempotency_key,
                outbox=outbox,
                admission=admission,
                artifact=artifact,
            )

    @staticmethod
    def _validate_artifact(
        artifact: WorkflowEventByteArtifact,
        *,
        canonical_bytes: bytes,
        admission: WorkflowEventTransportAdmission,
        envelope: WorkflowDispatchEventEnvelope,
        outbox: WorkflowDispatchOutboxEntry,
        orchestration_lease: WorkflowOrchestrationLease,
        publication_lease: WorkflowOutboxPublicationLease,
        context: WorkflowOutboxPublisherContext,
    ) -> None:
        content_sha256 = sha256(canonical_bytes).hexdigest()
        expected_artifact_id = (
            "workflow-event-byte-artifact."
            + sha256(
                f"{admission.admission_id}:{admission.canonical_digest}:{content_sha256}".encode()
            ).hexdigest()[:24]
        )
        admission_fields = (
            "policy_id",
            "policy_version",
            "policy_digest",
            "event_id",
            "event_digest",
            "event_type",
            "event_version",
            "schema_uri",
            "data_classification",
            "representation_name",
            "encoding",
            "maximum_canonical_byte_count",
            "outbox_entry_id",
            "outbox_entry_digest",
            "dispatch_intent_id",
            "dispatch_intent_digest",
            "plan_id",
            "plan_digest",
            "run_id",
            "run_digest",
            "step_run_id",
            "step_run_digest",
            "step_id",
            "attempt_id",
            "attempt_digest",
            "attempt_number",
            "scope",
            "target_id",
            "target_type",
            "orchestration_lease_id",
            "orchestration_lease_digest",
            "orchestration_fencing_token",
            "publication_lease_id",
            "publication_lease_digest",
            "publication_fencing_token",
            "publisher_subject_id",
        )
        if (
            artifact.artifact_id != expected_artifact_id
            or artifact.admission_id != admission.admission_id
            or artifact.admission_digest != admission.canonical_digest
            or not all(
                getattr(artifact, name) == getattr(admission, name) for name in admission_fields
            )
            or artifact.event_id != envelope.event_id
            or artifact.outbox_entry_id != outbox.outbox_entry_id
            or artifact.orchestration_lease_id != orchestration_lease.lease_id
            or artifact.orchestration_lease_digest != orchestration_lease.canonical_digest
            or artifact.orchestration_fencing_token != orchestration_lease.fencing_token
            or artifact.publication_lease_id != publication_lease.publication_lease_id
            or artifact.publication_lease_digest != publication_lease.canonical_digest
            or artifact.publication_fencing_token != publication_lease.publication_fencing_token
            or artifact.publisher_subject_id != context.subject_id
            or artifact.canonical_bytes != canonical_bytes
            or artifact.canonical_byte_count != len(canonical_bytes)
            or artifact.content_sha256 != content_sha256
            or artifact.materialized_at < admission.admitted_at
            or artifact.materialized_at > context.requested_at
            or artifact.state is not WorkflowEventByteArtifactState.MATERIALIZED
            or any(artifact.authority.canonical_value().values())
            or artifact.grants_publication_authority
            or artifact.grants_delivery_authority
            or artifact.grants_dispatch_authority
            or artifact.grants_execution_authority
        ):
            raise WorkflowEventByteArtifactError(
                "workflow_event_byte_artifact_repository_scope_violation",
                "The repository returned incorrectly bound byte artifact evidence.",
            )

    async def _require_publisher(self, context: WorkflowOutboxPublisherContext) -> None:
        if (
            context.actor_type != "service"
            or context.authentication_method != "workload_token"
            or context.credential_audience != WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE
        ):
            await self._deny(
                context,
                result_code="workflow_event_byte_artifact_publisher_identity_required",
            )

    async def _success(
        self,
        context: WorkflowOutboxPublisherContext,
        *,
        result_code: str,
        idempotency_key: str,
        outbox: WorkflowDispatchOutboxEntry,
        admission: WorkflowEventTransportAdmission,
        artifact: WorkflowEventByteArtifact,
    ) -> None:
        await self._audit(
            context,
            outcome="succeeded",
            result_code=result_code,
            idempotency_key=idempotency_key,
            outbox=outbox,
            admission=admission,
            artifact=artifact,
        )

    async def _deny(
        self,
        context: WorkflowOutboxPublisherContext,
        *,
        result_code: str,
        idempotency_key: str | None = None,
        outbox: WorkflowDispatchOutboxEntry | None = None,
        admission: WorkflowEventTransportAdmission | None = None,
        artifact: WorkflowEventByteArtifact | None = None,
    ) -> NoReturn:
        await self._audit(
            context,
            outcome="denied",
            result_code=result_code,
            idempotency_key=idempotency_key,
            outbox=outbox,
            admission=admission,
            artifact=artifact,
        )
        raise WorkflowEventByteArtifactError(
            result_code, "The workflow event byte artifact request was denied."
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
        artifact: WorkflowEventByteArtifact | None,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=(
                    "atlas.workflow.event-byte-artifact.succeeded"
                    if outcome == "succeeded"
                    else "atlas.workflow.event-byte-artifact.denied"
                ),
                schema_version="1.0",
                producer=WORKFLOW_EVENT_BYTE_ARTIFACT_PRODUCER,
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id="workflow.event-byte-artifact.materialize",
                resource_type="resource.workflow-event-byte-artifact",
                scope_reference="/".join(
                    (
                        context.scope.organization_id,
                        context.scope.environment_id,
                        context.scope.site_id,
                        "workflow-event-byte-artifact",
                    )
                ),
                decision_id=context.decision_id,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=(
                    ("outbox_entry_id", "none" if outbox is None else outbox.outbox_entry_id),
                    ("admission_id", "none" if admission is None else admission.admission_id),
                    ("artifact_id", "none" if artifact is None else artifact.artifact_id),
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
            raise WorkflowEventByteArtifactError(
                f"workflow_event_byte_artifact_{name}_invalid", f"{name} is invalid."
            )
        return normalized

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, "idempotency_key")
        if not 8 <= len(normalized) <= 128:
            raise WorkflowEventByteArtifactError(
                "workflow_event_byte_artifact_idempotency_key_invalid",
                "The idempotency key is invalid.",
            )
        return normalized

    @staticmethod
    def _digest(value: str, name: str) -> str:
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise WorkflowEventByteArtifactError(
                f"workflow_event_byte_artifact_{name}_invalid",
                f"{name} must be a SHA-256 digest.",
            )
        return value


__all__ = [
    "WORKFLOW_EVENT_BYTE_ARTIFACT_PRODUCER",
    "WorkflowEventByteArtifactService",
]
