from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any, NoReturn, cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.workflows.application.logical_channel_binding_ports import (
    WorkflowEventLogicalChannelBindingError,
    WorkflowEventLogicalChannelBindingRepository,
    WorkflowEventLogicalChannelBindingRequest,
    WorkflowEventLogicalChannelBindingStatus,
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
    WorkflowDispatchOutboxEntry,
    WorkflowDispatchOutboxState,
    WorkflowEventByteArtifact,
    WorkflowEventByteArtifactState,
    WorkflowEventLogicalChannelBinding,
    WorkflowEventLogicalChannelBindingAuthority,
    WorkflowEventLogicalChannelBindingState,
    WorkflowEventLogicalChannelPolicy,
    WorkflowEventTransportAdmission,
    WorkflowEventTransportAdmissionState,
    WorkflowOrchestrationLease,
    WorkflowOrchestrationLeaseEffectiveState,
    WorkflowOutboxPublicationLease,
    WorkflowOutboxPublicationLeaseEffectiveState,
    WorkflowPlanState,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_logical_channel_policy,
)

WORKFLOW_EVENT_LOGICAL_CHANNEL_BINDING_PRODUCER = "project-atlas-workflow-event-control"


class WorkflowEventLogicalChannelBindingService:
    """Binds exact event bytes to a logical channel without selecting transport."""

    def __init__(
        self,
        *,
        plan_repository: WorkflowPlanRepository,
        orchestration_lease_repository: WorkflowOrchestrationLeaseRepository,
        logical_channel_binding_repository: WorkflowEventLogicalChannelBindingRepository,
        audit_sink: AuditSink,
        policy: WorkflowEventLogicalChannelPolicy | None = None,
    ) -> None:
        self._plan_repository = plan_repository
        self._orchestration_lease_repository = orchestration_lease_repository
        self._repository = logical_channel_binding_repository
        self._audit_sink = audit_sink
        self._policy = policy or code_owned_workflow_event_logical_channel_policy()

    @property
    def durable(self) -> bool:
        return self._repository.durable

    @property
    def policy(self) -> WorkflowEventLogicalChannelPolicy:
        return self._policy

    @property
    def repository(self) -> WorkflowEventLogicalChannelBindingRepository:
        return self._repository

    async def bind(
        self,
        *,
        artifact_id: str,
        artifact_digest: str,
        content_sha256: str,
        canonical_byte_count: int,
        admission_id: str,
        admission_digest: str,
        event_id: str,
        event_digest: str,
        outbox_entry_id: str,
        outbox_entry_digest: str,
        policy_id: str,
        policy_version: str,
        policy_digest: str,
        logical_channel_id: str,
        logical_channel_version: str,
        publication_lease_id: str,
        publication_lease_digest: str,
        publication_fencing_token: int,
        idempotency_key: str,
        context: WorkflowOutboxPublisherContext,
    ) -> WorkflowEventLogicalChannelBinding:
        await self._require_publisher(context)
        try:
            normalized = {
                "artifact_id": self._identifier(artifact_id, "artifact_id"),
                "artifact_digest": self._digest(artifact_digest, "artifact_digest"),
                "content_sha256": self._digest(content_sha256, "content_sha256"),
                "admission_id": self._identifier(admission_id, "admission_id"),
                "admission_digest": self._digest(admission_digest, "admission_digest"),
                "event_id": self._identifier(event_id, "event_id"),
                "event_digest": self._digest(event_digest, "event_digest"),
                "outbox_entry_id": self._identifier(outbox_entry_id, "outbox_entry_id"),
                "outbox_entry_digest": self._digest(outbox_entry_digest, "outbox_entry_digest"),
                "policy_id": self._identifier(policy_id, "policy_id"),
                "policy_version": self._identifier(policy_version, "policy_version"),
                "policy_digest": self._digest(policy_digest, "policy_digest"),
                "logical_channel_id": self._identifier(logical_channel_id, "logical_channel_id"),
                "logical_channel_version": self._identifier(
                    logical_channel_version, "logical_channel_version"
                ),
                "publication_lease_id": self._identifier(
                    publication_lease_id, "publication_lease_id"
                ),
                "publication_lease_digest": self._digest(
                    publication_lease_digest, "publication_lease_digest"
                ),
            }
            if not 1 <= canonical_byte_count <= 65_536:
                raise WorkflowEventLogicalChannelBindingError(
                    "workflow_event_logical_channel_binding_byte_count_invalid",
                    "The canonical byte count is invalid.",
                )
            if publication_fencing_token < 1:
                raise WorkflowEventLogicalChannelBindingError(
                    "workflow_event_logical_channel_binding_publication_fence_invalid",
                    "The publication fencing token is invalid.",
                )
            normalized_key = self._idempotency_key(idempotency_key)
        except WorkflowEventLogicalChannelBindingError as exc:
            await self._deny(context, result_code=exc.code)

        if (
            normalized["policy_id"] != self._policy.policy_id
            or normalized["policy_version"] != self._policy.policy_version
            or normalized["policy_digest"] != self._policy.canonical_digest
            or normalized["logical_channel_id"] != self._policy.logical_channel_id
            or normalized["logical_channel_version"] != self._policy.logical_channel_version
        ):
            await self._deny(
                context,
                result_code="workflow_event_logical_channel_binding_policy_conflict",
                idempotency_key=normalized_key,
            )

        (
            outbox,
            orchestration_lease,
            publication_lease,
            admission,
            artifact,
        ) = await self._require_current_evidence(
            artifact_id=normalized["artifact_id"],
            artifact_digest=normalized["artifact_digest"],
            content_sha256=normalized["content_sha256"],
            canonical_byte_count=canonical_byte_count,
            admission_id=normalized["admission_id"],
            admission_digest=normalized["admission_digest"],
            event_id=normalized["event_id"],
            event_digest=normalized["event_digest"],
            outbox_entry_id=normalized["outbox_entry_id"],
            outbox_entry_digest=normalized["outbox_entry_digest"],
            publication_lease_id=normalized["publication_lease_id"],
            publication_lease_digest=normalized["publication_lease_digest"],
            publication_fencing_token=publication_fencing_token,
            context=context,
            idempotency_key=normalized_key,
        )
        fingerprint = canonical_digest(
            {
                "admission_digest": admission.canonical_digest,
                "admission_id": admission.admission_id,
                "artifact_digest": artifact.canonical_digest,
                "artifact_id": artifact.artifact_id,
                "canonical_byte_count": artifact.canonical_byte_count,
                "content_sha256": artifact.content_sha256,
                "event_digest": artifact.event_digest,
                "event_id": artifact.event_id,
                "idempotency_key": normalized_key,
                "logical_channel_id": self._policy.logical_channel_id,
                "logical_channel_version": self._policy.logical_channel_version,
                "operation": "workflow.event-logical-channel.bind",
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
        prior = await self._repository.get_event_logical_channel_binding_request(
            scope=context.scope,
            publisher_subject_id=context.subject_id,
            idempotency_key=normalized_key,
        )
        if prior is not None:
            if prior.request_fingerprint != fingerprint:
                await self._deny(
                    context,
                    result_code="workflow_event_logical_channel_binding_idempotency_conflict",
                    idempotency_key=normalized_key,
                    outbox=outbox,
                    artifact=artifact,
                    binding=prior.binding,
                )
            await self._validate_or_deny(
                prior.binding,
                artifact=artifact,
                outbox=outbox,
                orchestration_lease=orchestration_lease,
                publication_lease=publication_lease,
                context=context,
                idempotency_key=normalized_key,
            )
            await self._audit(
                context,
                outcome="succeeded",
                result_code="workflow_event_logical_channel_binding_replayed",
                idempotency_key=normalized_key,
                outbox=outbox,
                artifact=artifact,
                binding=prior.binding,
            )
            return prior.binding

        current = await self._repository.get_event_logical_channel_binding_by_artifact_id(
            artifact_id=artifact.artifact_id
        )
        if current is not None:
            await self._deny(
                context,
                result_code=(
                    "workflow_event_logical_channel_binding_competing_identity"
                    if current.publisher_subject_id != context.subject_id
                    else "workflow_event_logical_channel_binding_already_bound"
                ),
                idempotency_key=normalized_key,
                outbox=outbox,
                artifact=artifact,
                binding=current,
            )

        candidate = self._build_binding(artifact=artifact, bound_at=context.requested_at)
        await self._audit(
            context,
            outcome="succeeded",
            result_code="workflow_event_logical_channel_binding_authorized",
            idempotency_key=normalized_key,
            outbox=outbox,
            artifact=artifact,
            binding=candidate,
        )
        result = await self._repository.bind_event_logical_channel(
            WorkflowEventLogicalChannelBindingRequest(
                expected_plan_digest=outbox.plan_digest,
                expected_outbox_entry_digest=outbox.canonical_digest,
                expected_event_id=artifact.event_id,
                expected_event_digest=artifact.event_digest,
                expected_admission_id=artifact.admission_id,
                expected_admission_digest=artifact.admission_digest,
                expected_artifact_id=artifact.artifact_id,
                expected_artifact_digest=artifact.canonical_digest,
                expected_content_sha256=artifact.content_sha256,
                expected_canonical_byte_count=artifact.canonical_byte_count,
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
        if (
            result.status
            in {
                WorkflowEventLogicalChannelBindingStatus.BOUND,
                WorkflowEventLogicalChannelBindingStatus.REPLAY,
            }
            and result.binding is not None
        ):
            await self._validate_or_deny(
                result.binding,
                artifact=artifact,
                outbox=outbox,
                orchestration_lease=orchestration_lease,
                publication_lease=publication_lease,
                context=context,
                idempotency_key=normalized_key,
            )
            return result.binding

        result_code = {
            WorkflowEventLogicalChannelBindingStatus.IDEMPOTENCY_CONFLICT: (
                "workflow_event_logical_channel_binding_idempotency_conflict"
            ),
            WorkflowEventLogicalChannelBindingStatus.EVIDENCE_CONFLICT: (
                "workflow_event_logical_channel_binding_evidence_conflict"
            ),
            WorkflowEventLogicalChannelBindingStatus.ALREADY_BOUND: (
                "workflow_event_logical_channel_binding_already_bound"
            ),
        }.get(
            result.status,
            "workflow_event_logical_channel_binding_repository_contract_violation",
        )
        await self._deny(
            context,
            result_code=result_code,
            idempotency_key=normalized_key,
            outbox=outbox,
            artifact=artifact,
            binding=result.binding,
        )

    async def _require_current_evidence(
        self,
        *,
        artifact_id: str,
        artifact_digest: str,
        content_sha256: str,
        canonical_byte_count: int,
        admission_id: str,
        admission_digest: str,
        event_id: str,
        event_digest: str,
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
        WorkflowEventTransportAdmission,
        WorkflowEventByteArtifact,
    ]:
        outbox = await self._repository.get_outbox_entry_by_id(outbox_entry_id=outbox_entry_id)
        if outbox is None:
            await self._deny(
                context,
                result_code="workflow_event_logical_channel_binding_outbox_not_found",
                idempotency_key=idempotency_key,
            )
        if (
            outbox.canonical_digest != outbox_entry_digest
            or outbox.state is not WorkflowDispatchOutboxState.PENDING_PUBLICATION
            or outbox.scope != context.scope
            or any(outbox.authority.canonical_value().values())
        ):
            await self._deny(
                context,
                result_code="workflow_event_logical_channel_binding_outbox_conflict",
                idempotency_key=idempotency_key,
                outbox=outbox,
            )

        plan = await self._plan_repository.get_by_id(plan_id=outbox.plan_id)
        if plan is None:
            await self._deny(
                context,
                result_code="workflow_event_logical_channel_binding_plan_not_found",
                idempotency_key=idempotency_key,
                outbox=outbox,
            )
        if (
            plan.canonical_digest != outbox.plan_digest
            or plan.state is not WorkflowPlanState.PLANNED
            or plan.scope != outbox.scope
            or plan.target_id != outbox.target_id
            or plan.target_type != outbox.target_type
        ):
            await self._deny(
                context,
                result_code="workflow_event_logical_channel_binding_plan_conflict",
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
            or orchestration_lease.plan_digest != outbox.plan_digest
            or orchestration_lease.scope != outbox.scope
            or orchestration_lease.target_id != outbox.target_id
            or orchestration_lease.target_type != outbox.target_type
            or orchestration_lease.effective_state(requested_at=context.requested_at)
            is not WorkflowOrchestrationLeaseEffectiveState.ACTIVE
        ):
            await self._deny(
                context,
                result_code="workflow_event_logical_channel_binding_orchestration_lease_conflict",
                idempotency_key=idempotency_key,
                outbox=outbox,
            )

        publication_lease = await self._repository.get_publication_lease_by_outbox_entry_id(
            outbox_entry_id=outbox.outbox_entry_id
        )
        if (
            publication_lease is None
            or publication_lease.publication_lease_id != publication_lease_id
            or publication_lease.canonical_digest != publication_lease_digest
            or publication_lease.publication_fencing_token != publication_fencing_token
            or publication_lease.outbox_entry_digest != outbox.canonical_digest
            or publication_lease.orchestration_lease_id != orchestration_lease.lease_id
            or publication_lease.orchestration_lease_digest != orchestration_lease.canonical_digest
            or publication_lease.orchestration_fencing_token != orchestration_lease.fencing_token
            or publication_lease.publisher_subject_id != context.subject_id
            or publication_lease.scope != outbox.scope
            or publication_lease.target_id != outbox.target_id
            or publication_lease.target_type != outbox.target_type
            or publication_lease.effective_state(requested_at=context.requested_at)
            is not WorkflowOutboxPublicationLeaseEffectiveState.ACTIVE
            or any(publication_lease.authority.canonical_value().values())
        ):
            await self._deny(
                context,
                result_code="workflow_event_logical_channel_binding_publication_lease_conflict",
                idempotency_key=idempotency_key,
                outbox=outbox,
            )

        admission = await self._repository.get_event_transport_admission_by_event_id(
            event_id=event_id
        )
        if (
            admission is None
            or admission.admission_id != admission_id
            or admission.canonical_digest != admission_digest
            or admission.event_digest != event_digest
            or admission.outbox_entry_id != outbox.outbox_entry_id
            or admission.outbox_entry_digest != outbox.canonical_digest
            or admission.publisher_subject_id != context.subject_id
            or admission.state is not WorkflowEventTransportAdmissionState.ADMITTED
            or any(admission.authority.canonical_value().values())
        ):
            await self._deny(
                context,
                result_code="workflow_event_logical_channel_binding_admission_conflict",
                idempotency_key=idempotency_key,
                outbox=outbox,
            )

        artifact = await self._repository.get_event_byte_artifact_by_id(artifact_id=artifact_id)
        if artifact is None:
            await self._deny(
                context,
                result_code="workflow_event_logical_channel_binding_artifact_not_found",
                idempotency_key=idempotency_key,
                outbox=outbox,
            )
        try:
            self._validate_artifact(
                artifact,
                expected_artifact_digest=artifact_digest,
                expected_content_sha256=content_sha256,
                expected_canonical_byte_count=canonical_byte_count,
                admission=admission,
                outbox=outbox,
                orchestration_lease=orchestration_lease,
                publication_lease=publication_lease,
                context=context,
            )
        except WorkflowEventLogicalChannelBindingError as exc:
            await self._deny(
                context,
                result_code=exc.code,
                idempotency_key=idempotency_key,
                outbox=outbox,
                artifact=artifact,
            )
        return outbox, orchestration_lease, publication_lease, admission, artifact

    def _validate_artifact(
        self,
        artifact: WorkflowEventByteArtifact,
        *,
        expected_artifact_digest: str,
        expected_content_sha256: str,
        expected_canonical_byte_count: int,
        admission: WorkflowEventTransportAdmission,
        outbox: WorkflowDispatchOutboxEntry,
        orchestration_lease: WorkflowOrchestrationLease,
        publication_lease: WorkflowOutboxPublicationLease,
        context: WorkflowOutboxPublisherContext,
    ) -> None:
        if (
            artifact.canonical_digest != expected_artifact_digest
            or artifact.content_sha256 != expected_content_sha256
            or artifact.canonical_byte_count != expected_canonical_byte_count
            or artifact.canonical_byte_count > self._policy.maximum_canonical_byte_count
            or artifact.admission_id != admission.admission_id
            or artifact.admission_digest != admission.canonical_digest
            or artifact.event_id != admission.event_id
            or artifact.event_digest != admission.event_digest
            or artifact.event_type != admission.event_type
            or artifact.event_version != admission.event_version
            or artifact.schema_uri != admission.schema_uri
            or artifact.data_classification != admission.data_classification
            or artifact.representation_name != admission.representation_name
            or artifact.encoding != admission.encoding
            or artifact.canonical_byte_count != admission.canonical_byte_count
            or artifact.maximum_canonical_byte_count != admission.maximum_canonical_byte_count
            or artifact.outbox_entry_id != admission.outbox_entry_id
            or artifact.outbox_entry_digest != admission.outbox_entry_digest
            or artifact.dispatch_intent_id != admission.dispatch_intent_id
            or artifact.dispatch_intent_digest != admission.dispatch_intent_digest
            or artifact.plan_id != admission.plan_id
            or artifact.plan_digest != admission.plan_digest
            or artifact.run_id != admission.run_id
            or artifact.run_digest != admission.run_digest
            or artifact.step_run_id != admission.step_run_id
            or artifact.step_run_digest != admission.step_run_digest
            or artifact.step_id != admission.step_id
            or artifact.attempt_id != admission.attempt_id
            or artifact.attempt_digest != admission.attempt_digest
            or artifact.attempt_number != admission.attempt_number
            or artifact.scope != admission.scope
            or artifact.target_id != admission.target_id
            or artifact.target_type != admission.target_type
            or artifact.orchestration_lease_id != admission.orchestration_lease_id
            or artifact.orchestration_lease_digest != admission.orchestration_lease_digest
            or artifact.orchestration_fencing_token != admission.orchestration_fencing_token
            or artifact.publication_lease_id != admission.publication_lease_id
            or artifact.publication_lease_digest != admission.publication_lease_digest
            or artifact.publication_fencing_token != admission.publication_fencing_token
            or artifact.publisher_subject_id != admission.publisher_subject_id
            or artifact.outbox_entry_id != outbox.outbox_entry_id
            or artifact.orchestration_lease_id != orchestration_lease.lease_id
            or artifact.orchestration_lease_digest != orchestration_lease.canonical_digest
            or artifact.orchestration_fencing_token != orchestration_lease.fencing_token
            or artifact.publication_lease_id != publication_lease.publication_lease_id
            or artifact.publication_lease_digest != publication_lease.canonical_digest
            or artifact.publication_fencing_token != publication_lease.publication_fencing_token
            or artifact.publisher_subject_id != context.subject_id
            or artifact.event_type not in self._policy.allowed_event_types
            or artifact.event_version not in self._policy.allowed_event_versions
            or artifact.schema_uri not in self._policy.allowed_schema_uris
            or artifact.data_classification not in self._policy.allowed_data_classifications
            or artifact.representation_name != self._policy.representation_name
            or artifact.encoding != self._policy.encoding
            or artifact.state is not WorkflowEventByteArtifactState.MATERIALIZED
            or any(artifact.authority.canonical_value().values())
            or artifact.grants_publication_authority
            or artifact.grants_delivery_authority
            or artifact.grants_dispatch_authority
            or artifact.grants_execution_authority
        ):
            raise WorkflowEventLogicalChannelBindingError(
                "workflow_event_logical_channel_binding_artifact_scope_violation",
                "The materialized byte artifact is incorrectly bound.",
            )

    def _build_binding(
        self, *, artifact: WorkflowEventByteArtifact, bound_at: datetime
    ) -> WorkflowEventLogicalChannelBinding:
        binding_id = (
            "workflow-event-logical-channel-binding."
            + sha256(
                f"{artifact.artifact_id}:{artifact.canonical_digest}:"
                f"{self._policy.canonical_digest}".encode()
            ).hexdigest()[:24]
        )
        values: dict[str, object] = {
            "binding_id": binding_id,
            "artifact_id": artifact.artifact_id,
            "artifact_digest": artifact.canonical_digest,
            "content_sha256": artifact.content_sha256,
            "canonical_byte_count": artifact.canonical_byte_count,
            "admission_id": artifact.admission_id,
            "admission_digest": artifact.admission_digest,
            "event_id": artifact.event_id,
            "event_digest": artifact.event_digest,
            "event_type": artifact.event_type,
            "event_version": artifact.event_version,
            "schema_uri": artifact.schema_uri,
            "outbox_entry_id": artifact.outbox_entry_id,
            "outbox_entry_digest": artifact.outbox_entry_digest,
            "dispatch_intent_id": artifact.dispatch_intent_id,
            "dispatch_intent_digest": artifact.dispatch_intent_digest,
            "plan_id": artifact.plan_id,
            "plan_digest": artifact.plan_digest,
            "run_id": artifact.run_id,
            "run_digest": artifact.run_digest,
            "step_run_id": artifact.step_run_id,
            "step_run_digest": artifact.step_run_digest,
            "step_id": artifact.step_id,
            "attempt_id": artifact.attempt_id,
            "attempt_digest": artifact.attempt_digest,
            "attempt_number": artifact.attempt_number,
            "scope": artifact.scope,
            "target_id": artifact.target_id,
            "target_type": artifact.target_type,
            "policy_id": self._policy.policy_id,
            "policy_version": self._policy.policy_version,
            "policy_digest": self._policy.canonical_digest,
            "logical_channel_id": self._policy.logical_channel_id,
            "logical_channel_version": self._policy.logical_channel_version,
            "data_classification": artifact.data_classification,
            "representation_name": self._policy.representation_name,
            "encoding": self._policy.encoding,
            "delivery_semantics": self._policy.delivery_semantics,
            "durability_required": self._policy.durability_required,
            "ordering_key_kind": self._policy.ordering_key_kind,
            "ordering_key_value": artifact.run_id,
            "retention_class": self._policy.retention_class,
            "maximum_canonical_byte_count": self._policy.maximum_canonical_byte_count,
            "orchestration_lease_id": artifact.orchestration_lease_id,
            "orchestration_lease_digest": artifact.orchestration_lease_digest,
            "orchestration_fencing_token": artifact.orchestration_fencing_token,
            "publication_lease_id": artifact.publication_lease_id,
            "publication_lease_digest": artifact.publication_lease_digest,
            "publication_fencing_token": artifact.publication_fencing_token,
            "publisher_subject_id": artifact.publisher_subject_id,
            "bound_at": bound_at,
            "state": WorkflowEventLogicalChannelBindingState.BOUND,
            "authority": WorkflowEventLogicalChannelBindingAuthority(),
        }
        digest_payload = {
            key: value.canonical_value()
            if isinstance(value, (WorkflowEventLogicalChannelBindingAuthority, WorkflowScope))
            else value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(value, WorkflowEventLogicalChannelBindingState)
            else value
            for key, value in values.items()
        }
        return WorkflowEventLogicalChannelBinding(
            **cast(Any, values), canonical_digest=canonical_digest(digest_payload)
        )

    async def _validate_or_deny(
        self,
        binding: WorkflowEventLogicalChannelBinding,
        *,
        artifact: WorkflowEventByteArtifact,
        outbox: WorkflowDispatchOutboxEntry,
        orchestration_lease: WorkflowOrchestrationLease,
        publication_lease: WorkflowOutboxPublicationLease,
        context: WorkflowOutboxPublisherContext,
        idempotency_key: str,
    ) -> None:
        try:
            self._validate_binding(
                binding,
                artifact=artifact,
                outbox=outbox,
                orchestration_lease=orchestration_lease,
                publication_lease=publication_lease,
                context=context,
            )
        except WorkflowEventLogicalChannelBindingError as exc:
            await self._deny(
                context,
                result_code=exc.code,
                idempotency_key=idempotency_key,
                outbox=outbox,
                artifact=artifact,
                binding=binding,
            )

    def _validate_binding(
        self,
        binding: WorkflowEventLogicalChannelBinding,
        *,
        artifact: WorkflowEventByteArtifact,
        outbox: WorkflowDispatchOutboxEntry,
        orchestration_lease: WorkflowOrchestrationLease,
        publication_lease: WorkflowOutboxPublicationLease,
        context: WorkflowOutboxPublisherContext,
    ) -> None:
        expected_id = (
            "workflow-event-logical-channel-binding."
            + sha256(
                f"{artifact.artifact_id}:{artifact.canonical_digest}:"
                f"{self._policy.canonical_digest}".encode()
            ).hexdigest()[:24]
        )
        artifact_fields = (
            "artifact_id",
            "content_sha256",
            "canonical_byte_count",
            "admission_id",
            "admission_digest",
            "event_id",
            "event_digest",
            "event_type",
            "event_version",
            "schema_uri",
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
            "data_classification",
            "orchestration_lease_id",
            "orchestration_lease_digest",
            "orchestration_fencing_token",
            "publication_lease_id",
            "publication_lease_digest",
            "publication_fencing_token",
            "publisher_subject_id",
        )
        if (
            binding.binding_id != expected_id
            or binding.artifact_digest != artifact.canonical_digest
            or not all(
                getattr(binding, name) == getattr(artifact, name) for name in artifact_fields
            )
            or binding.outbox_entry_id != outbox.outbox_entry_id
            or binding.policy_id != self._policy.policy_id
            or binding.policy_version != self._policy.policy_version
            or binding.policy_digest != self._policy.canonical_digest
            or binding.logical_channel_id != self._policy.logical_channel_id
            or binding.logical_channel_version != self._policy.logical_channel_version
            or binding.representation_name != self._policy.representation_name
            or binding.encoding != self._policy.encoding
            or binding.delivery_semantics != self._policy.delivery_semantics
            or binding.durability_required != self._policy.durability_required
            or binding.ordering_key_kind != self._policy.ordering_key_kind
            or binding.ordering_key_value != artifact.run_id
            or binding.retention_class != self._policy.retention_class
            or binding.maximum_canonical_byte_count != self._policy.maximum_canonical_byte_count
            or binding.orchestration_lease_id != orchestration_lease.lease_id
            or binding.publication_lease_id != publication_lease.publication_lease_id
            or binding.publisher_subject_id != context.subject_id
            or binding.bound_at < artifact.materialized_at
            or binding.bound_at > context.requested_at
            or binding.state is not WorkflowEventLogicalChannelBindingState.BOUND
            or any(binding.authority.canonical_value().values())
            or binding.grants_publication_authority
            or binding.grants_delivery_authority
            or binding.grants_dispatch_authority
            or binding.grants_execution_authority
        ):
            raise WorkflowEventLogicalChannelBindingError(
                "workflow_event_logical_channel_binding_repository_scope_violation",
                "The repository returned incorrectly bound logical channel evidence.",
            )

    async def _require_publisher(self, context: WorkflowOutboxPublisherContext) -> None:
        if (
            context.actor_type != "service"
            or context.authentication_method != "workload_token"
            or context.credential_audience != WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE
        ):
            await self._deny(
                context,
                result_code="workflow_event_logical_channel_binding_publisher_identity_required",
            )

    async def _deny(
        self,
        context: WorkflowOutboxPublisherContext,
        *,
        result_code: str,
        idempotency_key: str | None = None,
        outbox: WorkflowDispatchOutboxEntry | None = None,
        artifact: WorkflowEventByteArtifact | None = None,
        binding: WorkflowEventLogicalChannelBinding | None = None,
    ) -> NoReturn:
        await self._audit(
            context,
            outcome="denied",
            result_code=result_code,
            idempotency_key=idempotency_key,
            outbox=outbox,
            artifact=artifact,
            binding=binding,
        )
        raise WorkflowEventLogicalChannelBindingError(
            result_code, "The workflow event logical channel binding request was denied."
        )

    async def _audit(
        self,
        context: WorkflowOutboxPublisherContext,
        *,
        outcome: str,
        result_code: str,
        idempotency_key: str | None,
        outbox: WorkflowDispatchOutboxEntry | None,
        artifact: WorkflowEventByteArtifact | None,
        binding: WorkflowEventLogicalChannelBinding | None,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=(
                    "atlas.workflow.event-logical-channel-binding.succeeded"
                    if outcome == "succeeded"
                    else "atlas.workflow.event-logical-channel-binding.denied"
                ),
                schema_version="1.0",
                producer=WORKFLOW_EVENT_LOGICAL_CHANNEL_BINDING_PRODUCER,
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level="workload",
                permission_id="workflow.event-logical-channel.bind",
                resource_type="resource.workflow-event-logical-channel-binding",
                scope_reference="/".join(
                    (
                        context.scope.organization_id,
                        context.scope.environment_id,
                        context.scope.site_id,
                        "workflow-event-logical-channel-binding",
                    )
                ),
                decision_id=context.decision_id,
                outcome=outcome,
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=(
                    ("outbox_entry_id", "none" if outbox is None else outbox.outbox_entry_id),
                    ("artifact_id", "none" if artifact is None else artifact.artifact_id),
                    ("binding_id", "none" if binding is None else binding.binding_id),
                    ("logical_channel_id", self._policy.logical_channel_id),
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
            raise WorkflowEventLogicalChannelBindingError(
                f"workflow_event_logical_channel_binding_{name}_invalid",
                f"{name} is invalid.",
            )
        return normalized

    @classmethod
    def _idempotency_key(cls, value: str) -> str:
        normalized = cls._identifier(value, "idempotency_key")
        if not 8 <= len(normalized) <= 128:
            raise WorkflowEventLogicalChannelBindingError(
                "workflow_event_logical_channel_binding_idempotency_key_invalid",
                "The idempotency key is invalid.",
            )
        return normalized

    @staticmethod
    def _digest(value: str, name: str) -> str:
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise WorkflowEventLogicalChannelBindingError(
                f"workflow_event_logical_channel_binding_{name}_invalid",
                f"{name} must be a SHA-256 digest.",
            )
        return value


__all__ = [
    "WORKFLOW_EVENT_LOGICAL_CHANNEL_BINDING_PRODUCER",
    "WorkflowEventLogicalChannelBindingService",
]
