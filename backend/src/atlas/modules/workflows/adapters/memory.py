from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, cast

from atlas.modules.workflows.application import (
    WorkflowAttemptMaterializationIdempotencyRecord,
    WorkflowAttemptMaterializationRequest,
    WorkflowAttemptMaterializationResult,
    WorkflowAttemptMaterializationStatus,
    WorkflowDispatchEventEnvelopePrepareIdempotencyRecord,
    WorkflowDispatchEventEnvelopePrepareRequest,
    WorkflowDispatchEventEnvelopePrepareResult,
    WorkflowDispatchEventEnvelopePrepareStatus,
    WorkflowDispatchIntentStagingIdempotencyRecord,
    WorkflowDispatchIntentStagingRequest,
    WorkflowDispatchIntentStagingResult,
    WorkflowDispatchIntentStagingStatus,
    WorkflowEventTransportAdmissionIdempotencyRecord,
    WorkflowEventTransportAdmissionRequest,
    WorkflowEventTransportAdmissionResult,
    WorkflowEventTransportAdmissionStatus,
    WorkflowLeaseAcquireIdempotencyRecord,
    WorkflowLeaseAcquireRequest,
    WorkflowLeaseAcquireResult,
    WorkflowLeaseAcquireStatus,
    WorkflowLeaseMutationRequest,
    WorkflowLeaseMutationResult,
    WorkflowLeaseMutationStatus,
    WorkflowPlanCancellationIdempotencyRecord,
    WorkflowPlanCancellationRequest,
    WorkflowPlanCancellationResult,
    WorkflowPlanCancellationStatus,
    WorkflowPlanIdempotencyRecord,
    WorkflowPlanMutationResult,
    WorkflowPlanMutationStatus,
    WorkflowRunMaterializationIdempotencyRecord,
    WorkflowRunMaterializationRequest,
    WorkflowRunMaterializationResult,
    WorkflowRunMaterializationStatus,
)
from atlas.modules.workflows.application.byte_artifact_ports import (
    WorkflowEventByteArtifactIdempotencyRecord,
    WorkflowEventByteArtifactRequest,
    WorkflowEventByteArtifactResult,
    WorkflowEventByteArtifactStatus,
)
from atlas.modules.workflows.application.credential_assignment_snapshot_ports import (
    WorkflowTransportCredentialAssignmentSnapshotError,
    WorkflowTransportCredentialAssignmentSnapshotIdempotencyRecord,
    WorkflowTransportCredentialAssignmentSnapshotRequest,
    WorkflowTransportCredentialAssignmentSnapshotResult,
    WorkflowTransportCredentialAssignmentSnapshotStatus,
    validate_workflow_transport_credential_assignment_snapshot_request,
)
from atlas.modules.workflows.application.endpoint_materialization_ports import (
    WorkflowEventPhysicalTransportEndpointMaterializationClaimRequest,
    WorkflowEventPhysicalTransportEndpointMaterializationClaimResult,
    WorkflowEventPhysicalTransportEndpointMaterializationClaimStatus,
    WorkflowEventPhysicalTransportEndpointMaterializationResultRequest,
    WorkflowEventPhysicalTransportEndpointMaterializationResultStatus,
    WorkflowEventPhysicalTransportEndpointMaterializationResultWrite,
)
from atlas.modules.workflows.application.endpoint_resolution_authorization_lease_ports import (
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseIdempotencyRecord,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRequest,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus,
)
from atlas.modules.workflows.application.logical_channel_binding_ports import (
    WorkflowEventLogicalChannelBindingIdempotencyRecord,
    WorkflowEventLogicalChannelBindingRequest,
    WorkflowEventLogicalChannelBindingResult,
    WorkflowEventLogicalChannelBindingStatus,
)
from atlas.modules.workflows.application.physical_route_binding_ports import (
    WorkflowEventPhysicalTransportRouteBindingIdempotencyRecord,
    WorkflowEventPhysicalTransportRouteBindingRequest,
    WorkflowEventPhysicalTransportRouteBindingResult,
    WorkflowEventPhysicalTransportRouteBindingStatus,
)
from atlas.modules.workflows.application.publication_lease_ports import (
    WorkflowOutboxPublicationLeaseAcquireIdempotencyRecord,
    WorkflowOutboxPublicationLeaseAcquireRequest,
    WorkflowOutboxPublicationLeaseAcquireResult,
    WorkflowOutboxPublicationLeaseAcquireStatus,
    WorkflowOutboxPublicationLeaseMutationRequest,
    WorkflowOutboxPublicationLeaseMutationResult,
    WorkflowOutboxPublicationLeaseMutationStatus,
)
from atlas.modules.workflows.application.route_freshness_admission_ports import (
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionError,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionIdempotencyRecord,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionRequest,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus,
)
from atlas.modules.workflows.application.transport_compatibility_admission_ports import (
    WorkflowEventTransportCompatibilityAdmissionIdempotencyRecord,
    WorkflowEventTransportCompatibilityAdmissionRequest,
    WorkflowEventTransportCompatibilityAdmissionResult,
    WorkflowEventTransportCompatibilityAdmissionStatus,
)
from atlas.modules.workflows.application.transport_profile_snapshot_ports import (
    WorkflowTransportProfileSnapshotIdempotencyRecord,
    WorkflowTransportProfileSnapshotRequest,
    WorkflowTransportProfileSnapshotResult,
    WorkflowTransportProfileSnapshotStatus,
)
from atlas.modules.workflows.application.transport_route_snapshot_ports import (
    WorkflowTransportRouteSnapshotIdempotencyRecord,
    WorkflowTransportRouteSnapshotRequest,
    WorkflowTransportRouteSnapshotResult,
    WorkflowTransportRouteSnapshotStatus,
)
from atlas.modules.workflows.domain import (
    DeploymentEventTransportRouteSelectionHead,
    DeploymentPhysicalTransportCredentialAssignment,
    EventPhysicalTransportCredentialAssignmentSnapshot,
    EventPhysicalTransportProfileSnapshot,
    EventPhysicalTransportProfileSnapshotState,
    EventPhysicalTransportRouteSnapshot,
    EventPhysicalTransportRouteSnapshotState,
    WorkflowDispatchEventEnvelope,
    WorkflowDispatchEventEnvelopeState,
    WorkflowDispatchIntent,
    WorkflowDispatchIntentState,
    WorkflowDispatchOutboxEntry,
    WorkflowDispatchOutboxState,
    WorkflowEventByteArtifact,
    WorkflowEventByteArtifactState,
    WorkflowEventLogicalChannelBinding,
    WorkflowEventLogicalChannelBindingState,
    WorkflowEventPhysicalTransportEndpointMaterializationAttempt,
    WorkflowEventPhysicalTransportEndpointMaterializationAttemptState,
    WorkflowEventPhysicalTransportEndpointMaterializationAuthority,
    WorkflowEventPhysicalTransportEndpointMaterializationResult,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseAuthority,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseState,
    WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaim,
    WorkflowEventPhysicalTransportRouteBinding,
    WorkflowEventPhysicalTransportRouteBindingState,
    WorkflowEventPhysicalTransportRouteFreshnessAdmission,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionState,
    WorkflowEventTransportAdmission,
    WorkflowEventTransportAdmissionState,
    WorkflowEventTransportCompatibilityAdmission,
    WorkflowEventTransportCompatibilityAdmissionState,
    WorkflowExecutionAttempt,
    WorkflowExecutionAttemptState,
    WorkflowExecutionRun,
    WorkflowExecutionRunState,
    WorkflowExecutionStepRunState,
    WorkflowOrchestrationLease,
    WorkflowOrchestrationLeaseEffectiveState,
    WorkflowOutboxPublicationLease,
    WorkflowOutboxPublicationLeaseEffectiveState,
    WorkflowPlanState,
    WorkflowRunPlan,
    WorkflowScope,
    canonical_digest,
    canonical_json_byte_count,
    canonical_json_bytes,
    code_owned_workflow_event_physical_transport_endpoint_materialization_policy,
    code_owned_workflow_event_physical_transport_endpoint_resolution_authorization_policy,
    code_owned_workflow_event_physical_transport_route_freshness_policy,
    select_deployment_physical_transport_credential_assignment_head,
)


class InMemoryWorkflowPlanRepository:
    """Explicit development-only, non-durable workflow plan repository."""

    def __init__(self) -> None:
        self._plans: dict[str, WorkflowRunPlan] = {}
        self._requests: dict[tuple[WorkflowScope, str, str], WorkflowPlanIdempotencyRecord] = {}
        self._cancellation_requests: dict[
            tuple[WorkflowScope, str, str], WorkflowPlanCancellationIdempotencyRecord
        ] = {}
        self._leases_by_plan: dict[str, WorkflowOrchestrationLease] = {}
        self._lease_acquire_requests: dict[
            tuple[WorkflowScope, str, str], WorkflowLeaseAcquireIdempotencyRecord
        ] = {}
        self._runs_by_plan: dict[str, WorkflowExecutionRun] = {}
        self._run_materialization_requests: dict[
            tuple[WorkflowScope, str, str], WorkflowRunMaterializationIdempotencyRecord
        ] = {}
        self._attempts_by_step_run: dict[str, WorkflowExecutionAttempt] = {}
        self._attempt_materialization_requests: dict[
            tuple[WorkflowScope, str, str], WorkflowAttemptMaterializationIdempotencyRecord
        ] = {}
        self._dispatch_intents_by_attempt: dict[str, WorkflowDispatchIntent] = {}
        self._dispatch_outbox_entries_by_intent: dict[str, WorkflowDispatchOutboxEntry] = {}
        self._dispatch_intent_staging_requests: dict[
            tuple[WorkflowScope, str, str], WorkflowDispatchIntentStagingIdempotencyRecord
        ] = {}
        self._publication_leases_by_outbox: dict[str, WorkflowOutboxPublicationLease] = {}
        self._publication_lease_acquire_requests: dict[
            tuple[WorkflowScope, str, str],
            WorkflowOutboxPublicationLeaseAcquireIdempotencyRecord,
        ] = {}
        self._dispatch_event_envelopes_by_outbox: dict[str, WorkflowDispatchEventEnvelope] = {}
        self._dispatch_event_envelope_prepare_requests: dict[
            tuple[WorkflowScope, str, str],
            WorkflowDispatchEventEnvelopePrepareIdempotencyRecord,
        ] = {}
        self._event_transport_admissions_by_event: dict[str, WorkflowEventTransportAdmission] = {}
        self._event_transport_admission_requests: dict[
            tuple[WorkflowScope, str, str],
            WorkflowEventTransportAdmissionIdempotencyRecord,
        ] = {}
        self._event_byte_artifacts_by_admission: dict[str, WorkflowEventByteArtifact] = {}
        self._event_byte_artifact_requests: dict[
            tuple[WorkflowScope, str, str], WorkflowEventByteArtifactIdempotencyRecord
        ] = {}
        self._event_logical_channel_bindings_by_artifact: dict[
            str, WorkflowEventLogicalChannelBinding
        ] = {}
        self._event_logical_channel_binding_requests: dict[
            tuple[WorkflowScope, str, str],
            WorkflowEventLogicalChannelBindingIdempotencyRecord,
        ] = {}
        self._transport_profile_snapshots: dict[
            tuple[str, str], EventPhysicalTransportProfileSnapshot
        ] = {}
        self._transport_profile_snapshot_requests: dict[
            tuple[WorkflowScope, str, str],
            WorkflowTransportProfileSnapshotIdempotencyRecord,
        ] = {}
        self._transport_route_snapshots: dict[
            tuple[str, str], EventPhysicalTransportRouteSnapshot
        ] = {}
        self._transport_route_snapshot_requests: dict[
            tuple[WorkflowScope, str, str],
            WorkflowTransportRouteSnapshotIdempotencyRecord,
        ] = {}
        self._credential_assignments: dict[
            tuple[str, str], DeploymentPhysicalTransportCredentialAssignment
        ] = {}
        self._credential_assignment_snapshots: dict[
            tuple[str, str], EventPhysicalTransportCredentialAssignmentSnapshot
        ] = {}
        self._credential_assignment_snapshot_requests: dict[
            tuple[WorkflowScope, str, str],
            WorkflowTransportCredentialAssignmentSnapshotIdempotencyRecord,
        ] = {}
        self._transport_compatibility_admissions: dict[
            str, WorkflowEventTransportCompatibilityAdmission
        ] = {}
        self._transport_compatibility_admission_pairs: dict[
            tuple[str, str, str], WorkflowEventTransportCompatibilityAdmission
        ] = {}
        self._transport_compatibility_admission_requests: dict[
            tuple[WorkflowScope, str, str],
            WorkflowEventTransportCompatibilityAdmissionIdempotencyRecord,
        ] = {}
        self._physical_transport_route_bindings: dict[
            str, WorkflowEventPhysicalTransportRouteBinding
        ] = {}
        self._physical_transport_route_binding_requests: dict[
            tuple[WorkflowScope, str, str],
            WorkflowEventPhysicalTransportRouteBindingIdempotencyRecord,
        ] = {}
        self._route_selection_heads: dict[
            tuple[WorkflowScope, str], DeploymentEventTransportRouteSelectionHead
        ] = {}
        self._route_freshness_admissions: dict[
            str, WorkflowEventPhysicalTransportRouteFreshnessAdmission
        ] = {}
        self._route_freshness_admission_requests: dict[
            tuple[WorkflowScope, str, str],
            WorkflowEventPhysicalTransportRouteFreshnessAdmissionIdempotencyRecord,
        ] = {}
        self._endpoint_resolution_authorization_leases: dict[
            str, WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease
        ] = {}
        self._endpoint_resolution_authorization_requests: dict[
            tuple[WorkflowScope, str, str],
            WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseIdempotencyRecord,
        ] = {}
        self._endpoint_materialization_claims: dict[
            str, WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaim
        ] = {}
        self._endpoint_materialization_attempts: dict[
            str, WorkflowEventPhysicalTransportEndpointMaterializationAttempt
        ] = {}
        self._endpoint_materialization_results: dict[
            str, WorkflowEventPhysicalTransportEndpointMaterializationResult
        ] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get_authoritative_time(self) -> datetime:
        return datetime.now(UTC)

    async def get_by_id(self, *, plan_id: str) -> WorkflowRunPlan | None:
        async with self._lock:
            return self._plans.get(plan_id)

    async def list_scoped(
        self,
        *,
        scope: WorkflowScope,
        authorized_target_ids: frozenset[str],
        limit: int,
    ) -> tuple[WorkflowRunPlan, ...]:
        async with self._lock:
            plans = sorted(
                (
                    plan
                    for plan in self._plans.values()
                    if plan.scope == scope and plan.target_id in authorized_target_ids
                ),
                key=lambda plan: (plan.created_at, plan.plan_id),
                reverse=True,
            )
            return tuple(plans[:limit])

    async def get_create_request(
        self,
        *,
        scope: WorkflowScope,
        creator_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowPlanIdempotencyRecord | None:
        async with self._lock:
            return self._requests.get((scope, creator_subject_id, idempotency_key))

    async def create(
        self,
        plan: WorkflowRunPlan,
        *,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> WorkflowPlanMutationResult:
        async with self._lock:
            key = (plan.scope, plan.creator_subject_id, idempotency_key)
            prior = self._requests.get(key)
            if prior is not None:
                status = (
                    WorkflowPlanMutationStatus.REPLAY
                    if prior.request_fingerprint == request_fingerprint
                    else WorkflowPlanMutationStatus.IDEMPOTENCY_CONFLICT
                )
                return WorkflowPlanMutationResult(status=status, plan=prior.plan)
            if plan.plan_id in self._plans:
                return WorkflowPlanMutationResult(
                    status=WorkflowPlanMutationStatus.IDEMPOTENCY_CONFLICT,
                    plan=None,
                )
            self._plans[plan.plan_id] = plan
            self._requests[key] = WorkflowPlanIdempotencyRecord(
                request_fingerprint=request_fingerprint,
                plan=plan,
            )
            return WorkflowPlanMutationResult(
                status=WorkflowPlanMutationStatus.CREATED,
                plan=plan,
            )

    async def get_cancellation_request(
        self,
        *,
        scope: WorkflowScope,
        actor_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowPlanCancellationIdempotencyRecord | None:
        async with self._lock:
            return self._cancellation_requests.get((scope, actor_subject_id, idempotency_key))

    async def cancel(
        self, request: WorkflowPlanCancellationRequest
    ) -> WorkflowPlanCancellationResult:
        async with self._lock:
            plan = request.cancelled_plan
            key = (plan.scope, request.actor_subject_id, request.idempotency_key)
            prior = self._cancellation_requests.get(key)
            if prior is not None:
                status = (
                    WorkflowPlanCancellationStatus.REPLAY
                    if prior.request_fingerprint == request.request_fingerprint
                    else WorkflowPlanCancellationStatus.IDEMPOTENCY_CONFLICT
                )
                return WorkflowPlanCancellationResult(status=status, plan=prior.plan)
            current = self._plans.get(plan.plan_id)
            if current is None:
                return WorkflowPlanCancellationResult(
                    status=WorkflowPlanCancellationStatus.NOT_FOUND, plan=None
                )
            if (
                current.canonical_digest != request.expected_plan_digest
                or current.state.value != "planned"
            ):
                return WorkflowPlanCancellationResult(
                    status=WorkflowPlanCancellationStatus.STATE_CONFLICT,
                    plan=current,
                )
            self._plans[plan.plan_id] = plan
            self._cancellation_requests[key] = WorkflowPlanCancellationIdempotencyRecord(
                request_fingerprint=request.request_fingerprint,
                plan=plan,
            )
            return WorkflowPlanCancellationResult(
                status=WorkflowPlanCancellationStatus.CANCELLED,
                plan=plan,
            )

    async def get_lease_by_plan_id(self, *, plan_id: str) -> WorkflowOrchestrationLease | None:
        async with self._lock:
            return self._leases_by_plan.get(plan_id)

    async def get_lease_acquire_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowLeaseAcquireIdempotencyRecord | None:
        async with self._lock:
            return self._lease_acquire_requests.get((scope, worker_subject_id, idempotency_key))

    async def get_materialized_run_by_plan_id(self, *, plan_id: str) -> WorkflowExecutionRun | None:
        async with self._lock:
            return self._runs_by_plan.get(plan_id)

    async def get_run_materialization_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowRunMaterializationIdempotencyRecord | None:
        async with self._lock:
            return self._run_materialization_requests.get(
                (scope, worker_subject_id, idempotency_key)
            )

    async def materialize_run(
        self, request: WorkflowRunMaterializationRequest
    ) -> WorkflowRunMaterializationResult:
        async with self._lock:
            run = request.candidate
            key = (run.scope, request.worker_subject_id, request.idempotency_key)
            prior = self._run_materialization_requests.get(key)
            if prior is not None:
                status = (
                    WorkflowRunMaterializationStatus.REPLAY
                    if prior.request_fingerprint == request.request_fingerprint
                    else WorkflowRunMaterializationStatus.IDEMPOTENCY_CONFLICT
                )
                return WorkflowRunMaterializationResult(status, prior.run)
            plan = self._plans.get(run.plan_id)
            lease = self._leases_by_plan.get(run.plan_id)
            if (
                plan is None
                or plan.state is not WorkflowPlanState.PLANNED
                or plan.canonical_digest != request.expected_plan_digest == run.plan_digest
                or plan.scope != run.scope
                or plan.target_id != run.target_id
                or plan.target_type != run.target_type
                or lease is None
                or lease.lease_id != request.expected_lease_id == run.lease_id
                or lease.canonical_digest != request.expected_lease_digest == run.lease_digest
                or lease.fencing_token != request.expected_fencing_token == run.fencing_token
                or lease.worker_subject_id != request.worker_subject_id
                or request.worker_subject_id != run.materialized_by_subject_id
                or lease.effective_state(requested_at=request.requested_at)
                is not WorkflowOrchestrationLeaseEffectiveState.ACTIVE
                or lease.grants_execution_authority
            ):
                return WorkflowRunMaterializationResult(
                    WorkflowRunMaterializationStatus.STATE_CONFLICT, None
                )
            current = self._runs_by_plan.get(run.plan_id)
            if current is not None:
                return WorkflowRunMaterializationResult(
                    WorkflowRunMaterializationStatus.STATE_CONFLICT, current
                )
            self._runs_by_plan[run.plan_id] = run
            self._run_materialization_requests[key] = WorkflowRunMaterializationIdempotencyRecord(
                request_fingerprint=request.request_fingerprint,
                run=run,
            )
            return WorkflowRunMaterializationResult(WorkflowRunMaterializationStatus.CREATED, run)

    async def list_attempts_by_run_id(self, *, run_id: str) -> tuple[WorkflowExecutionAttempt, ...]:
        async with self._lock:
            return tuple(
                sorted(
                    (
                        attempt
                        for attempt in self._attempts_by_step_run.values()
                        if attempt.run_id == run_id
                    ),
                    key=lambda item: (item.attempt_number, item.step_run_id),
                )
            )

    async def get_attempt_materialization_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowAttemptMaterializationIdempotencyRecord | None:
        async with self._lock:
            return self._attempt_materialization_requests.get(
                (scope, worker_subject_id, idempotency_key)
            )

    async def materialize_attempt(
        self, request: WorkflowAttemptMaterializationRequest
    ) -> WorkflowAttemptMaterializationResult:
        async with self._lock:
            attempt = request.candidate
            key = (attempt.scope, request.worker_subject_id, request.idempotency_key)
            prior = self._attempt_materialization_requests.get(key)
            if prior is not None:
                status = (
                    WorkflowAttemptMaterializationStatus.REPLAY
                    if prior.request_fingerprint == request.request_fingerprint
                    else WorkflowAttemptMaterializationStatus.IDEMPOTENCY_CONFLICT
                )
                return WorkflowAttemptMaterializationResult(status, prior.attempt)
            plan = self._plans.get(attempt.plan_id)
            run = self._runs_by_plan.get(attempt.plan_id)
            lease = self._leases_by_plan.get(attempt.plan_id)
            step = (
                None
                if run is None
                else next(
                    (item for item in run.step_runs if item.step_run_id == attempt.step_run_id),
                    None,
                )
            )
            if (
                plan is None
                or plan.state is not WorkflowPlanState.PLANNED
                or plan.canonical_digest != request.expected_plan_digest
                or request.expected_plan_digest != attempt.plan_digest
                or run is None
                or run.state is not WorkflowExecutionRunState.CREATED
                or run.canonical_digest != request.expected_run_digest
                or request.expected_run_digest != attempt.run_digest
                or run.scope != attempt.scope
                or run.target_id != attempt.target_id
                or run.target_type != attempt.target_type
                or step is None
                or step.state is not WorkflowExecutionStepRunState.NOT_STARTED
                or step.depends_on
                or step.canonical_digest != request.expected_step_run_digest
                or request.expected_step_run_digest != attempt.step_run_digest
                or step.step_id != attempt.step_id
                or lease is None
                or lease.lease_id != request.expected_lease_id
                or request.expected_lease_id != attempt.lease_id
                or lease.canonical_digest != request.expected_lease_digest
                or request.expected_lease_digest != attempt.lease_digest
                or lease.fencing_token != request.expected_fencing_token
                or request.expected_fencing_token != attempt.fencing_token
                or lease.worker_subject_id != request.worker_subject_id
                or request.worker_subject_id != attempt.materialized_by_subject_id
                or lease.effective_state(requested_at=request.requested_at)
                is not WorkflowOrchestrationLeaseEffectiveState.ACTIVE
                or lease.grants_execution_authority
                or attempt.attempt_number != 1
                or attempt.state is not WorkflowExecutionAttemptState.CREATED
                or attempt.grants_execution_authority
            ):
                return WorkflowAttemptMaterializationResult(
                    WorkflowAttemptMaterializationStatus.STATE_CONFLICT, None
                )
            current = self._attempts_by_step_run.get(step.step_run_id)
            if current is not None:
                return WorkflowAttemptMaterializationResult(
                    WorkflowAttemptMaterializationStatus.STATE_CONFLICT, current
                )
            self._attempts_by_step_run[step.step_run_id] = attempt
            self._attempt_materialization_requests[key] = (
                WorkflowAttemptMaterializationIdempotencyRecord(
                    request_fingerprint=request.request_fingerprint,
                    attempt=attempt,
                )
            )
            return WorkflowAttemptMaterializationResult(
                WorkflowAttemptMaterializationStatus.CREATED, attempt
            )

    async def list_dispatch_intents_by_run_id(
        self, *, run_id: str
    ) -> tuple[WorkflowDispatchIntent, ...]:
        async with self._lock:
            return tuple(
                sorted(
                    (
                        dispatch_intent
                        for dispatch_intent in self._dispatch_intents_by_attempt.values()
                        if dispatch_intent.run_id == run_id
                    ),
                    key=lambda item: (item.staged_at, item.dispatch_intent_id),
                )
            )

    async def list_dispatch_outbox_entries_by_run_id(
        self, *, run_id: str
    ) -> tuple[WorkflowDispatchOutboxEntry, ...]:
        async with self._lock:
            return tuple(
                sorted(
                    (
                        entry
                        for entry in self._dispatch_outbox_entries_by_intent.values()
                        if entry.run_id == run_id
                    ),
                    key=lambda item: (item.admitted_at, item.outbox_entry_id),
                )
            )

    async def get_outbox_entry_by_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowDispatchOutboxEntry | None:
        async with self._lock:
            return next(
                (
                    entry
                    for entry in self._dispatch_outbox_entries_by_intent.values()
                    if entry.outbox_entry_id == outbox_entry_id
                ),
                None,
            )

    async def get_publication_lease_by_outbox_entry_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowOutboxPublicationLease | None:
        async with self._lock:
            return self._publication_leases_by_outbox.get(outbox_entry_id)

    async def get_publication_lease_acquire_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowOutboxPublicationLeaseAcquireIdempotencyRecord | None:
        async with self._lock:
            return self._publication_lease_acquire_requests.get(
                (scope, publisher_subject_id, idempotency_key)
            )

    async def get_dispatch_event_envelope_by_outbox_entry_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowDispatchEventEnvelope | None:
        async with self._lock:
            return self._dispatch_event_envelopes_by_outbox.get(outbox_entry_id)

    async def get_dispatch_event_envelope_prepare_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowDispatchEventEnvelopePrepareIdempotencyRecord | None:
        async with self._lock:
            return self._dispatch_event_envelope_prepare_requests.get(
                (scope, publisher_subject_id, idempotency_key)
            )

    async def prepare_dispatch_event_envelope(
        self, request: WorkflowDispatchEventEnvelopePrepareRequest
    ) -> WorkflowDispatchEventEnvelopePrepareResult:
        async with self._lock:
            candidate = request.candidate
            key = (candidate.payload.scope, request.publisher_subject_id, request.idempotency_key)
            prior = self._dispatch_event_envelope_prepare_requests.get(key)
            if prior is not None:
                status = (
                    WorkflowDispatchEventEnvelopePrepareStatus.REPLAY
                    if prior.request_fingerprint == request.request_fingerprint
                    else WorkflowDispatchEventEnvelopePrepareStatus.IDEMPOTENCY_CONFLICT
                )
                return WorkflowDispatchEventEnvelopePrepareResult(status, prior.envelope)

            outbox = next(
                (
                    entry
                    for entry in self._dispatch_outbox_entries_by_intent.values()
                    if entry.outbox_entry_id == candidate.payload.outbox_entry_id
                ),
                None,
            )
            plan = self._plans.get(candidate.payload.plan_id)
            orchestration_lease = self._leases_by_plan.get(candidate.payload.plan_id)
            publication_lease = self._publication_leases_by_outbox.get(
                candidate.payload.outbox_entry_id
            )
            if not self._dispatch_event_evidence_matches(
                outbox=outbox,
                plan=plan,
                orchestration_lease=orchestration_lease,
                publication_lease=publication_lease,
                request=request,
            ):
                return WorkflowDispatchEventEnvelopePrepareResult(
                    WorkflowDispatchEventEnvelopePrepareStatus.EVIDENCE_CONFLICT, None
                )
            current = self._dispatch_event_envelopes_by_outbox.get(
                candidate.payload.outbox_entry_id
            )
            if current is not None:
                return WorkflowDispatchEventEnvelopePrepareResult(
                    WorkflowDispatchEventEnvelopePrepareStatus.ALREADY_PREPARED, current
                )
            self._dispatch_event_envelopes_by_outbox[candidate.payload.outbox_entry_id] = candidate
            self._dispatch_event_envelope_prepare_requests[key] = (
                WorkflowDispatchEventEnvelopePrepareIdempotencyRecord(
                    request_fingerprint=request.request_fingerprint,
                    envelope=candidate,
                )
            )
            return WorkflowDispatchEventEnvelopePrepareResult(
                WorkflowDispatchEventEnvelopePrepareStatus.PREPARED, candidate
            )

    async def get_event_transport_admission_by_event_id(
        self, *, event_id: str
    ) -> WorkflowEventTransportAdmission | None:
        async with self._lock:
            return self._event_transport_admissions_by_event.get(event_id)

    async def get_event_transport_admission_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventTransportAdmissionIdempotencyRecord | None:
        async with self._lock:
            return self._event_transport_admission_requests.get(
                (scope, publisher_subject_id, idempotency_key)
            )

    async def admit_event_transport(
        self, request: WorkflowEventTransportAdmissionRequest
    ) -> WorkflowEventTransportAdmissionResult:
        async with self._lock:
            candidate = request.candidate
            key = (candidate.scope, request.publisher_subject_id, request.idempotency_key)
            prior = self._event_transport_admission_requests.get(key)
            if prior is not None:
                status = (
                    WorkflowEventTransportAdmissionStatus.REPLAY
                    if prior.request_fingerprint == request.request_fingerprint
                    else WorkflowEventTransportAdmissionStatus.IDEMPOTENCY_CONFLICT
                )
                return WorkflowEventTransportAdmissionResult(status, prior.admission)

            outbox = next(
                (
                    entry
                    for entry in self._dispatch_outbox_entries_by_intent.values()
                    if entry.outbox_entry_id == candidate.outbox_entry_id
                ),
                None,
            )
            plan = self._plans.get(candidate.plan_id)
            orchestration_lease = self._leases_by_plan.get(candidate.plan_id)
            publication_lease = self._publication_leases_by_outbox.get(candidate.outbox_entry_id)
            envelope = self._dispatch_event_envelopes_by_outbox.get(candidate.outbox_entry_id)
            if not self._event_transport_admission_evidence_matches(
                outbox=outbox,
                plan=plan,
                orchestration_lease=orchestration_lease,
                publication_lease=publication_lease,
                envelope=envelope,
                request=request,
            ):
                return WorkflowEventTransportAdmissionResult(
                    WorkflowEventTransportAdmissionStatus.EVIDENCE_CONFLICT, None
                )
            current = self._event_transport_admissions_by_event.get(candidate.event_id)
            if current is not None:
                return WorkflowEventTransportAdmissionResult(
                    WorkflowEventTransportAdmissionStatus.ALREADY_ADMITTED, current
                )
            self._event_transport_admissions_by_event[candidate.event_id] = candidate
            self._event_transport_admission_requests[key] = (
                WorkflowEventTransportAdmissionIdempotencyRecord(
                    request_fingerprint=request.request_fingerprint,
                    admission=candidate,
                )
            )
            return WorkflowEventTransportAdmissionResult(
                WorkflowEventTransportAdmissionStatus.ADMITTED, candidate
            )

    async def get_event_byte_artifact_by_admission_id(
        self, *, admission_id: str
    ) -> WorkflowEventByteArtifact | None:
        async with self._lock:
            return self._event_byte_artifacts_by_admission.get(admission_id)

    async def get_event_byte_artifact_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventByteArtifactIdempotencyRecord | None:
        async with self._lock:
            return self._event_byte_artifact_requests.get(
                (scope, publisher_subject_id, idempotency_key)
            )

    async def materialize_event_byte_artifact(
        self, request: WorkflowEventByteArtifactRequest
    ) -> WorkflowEventByteArtifactResult:
        async with self._lock:
            candidate = request.candidate
            key = (candidate.scope, request.publisher_subject_id, request.idempotency_key)
            prior = self._event_byte_artifact_requests.get(key)
            if prior is not None:
                status = (
                    WorkflowEventByteArtifactStatus.REPLAY
                    if prior.request_fingerprint == request.request_fingerprint
                    else WorkflowEventByteArtifactStatus.IDEMPOTENCY_CONFLICT
                )
                return WorkflowEventByteArtifactResult(status, prior.artifact)

            outbox = next(
                (
                    entry
                    for entry in self._dispatch_outbox_entries_by_intent.values()
                    if entry.outbox_entry_id == candidate.outbox_entry_id
                ),
                None,
            )
            plan = self._plans.get(candidate.plan_id)
            orchestration_lease = self._leases_by_plan.get(candidate.plan_id)
            publication_lease = self._publication_leases_by_outbox.get(candidate.outbox_entry_id)
            envelope = self._dispatch_event_envelopes_by_outbox.get(candidate.outbox_entry_id)
            admission = self._event_transport_admissions_by_event.get(candidate.event_id)
            if not self._event_byte_artifact_evidence_matches(
                outbox=outbox,
                plan=plan,
                orchestration_lease=orchestration_lease,
                publication_lease=publication_lease,
                envelope=envelope,
                admission=admission,
                request=request,
            ):
                return WorkflowEventByteArtifactResult(
                    WorkflowEventByteArtifactStatus.EVIDENCE_CONFLICT, None
                )
            current = self._event_byte_artifacts_by_admission.get(candidate.admission_id)
            if current is not None:
                return WorkflowEventByteArtifactResult(
                    WorkflowEventByteArtifactStatus.ALREADY_MATERIALIZED, current
                )
            self._event_byte_artifacts_by_admission[candidate.admission_id] = candidate
            self._event_byte_artifact_requests[key] = WorkflowEventByteArtifactIdempotencyRecord(
                request_fingerprint=request.request_fingerprint,
                artifact=candidate,
            )
            return WorkflowEventByteArtifactResult(
                WorkflowEventByteArtifactStatus.MATERIALIZED, candidate
            )

    async def get_event_byte_artifact_by_id(
        self, *, artifact_id: str
    ) -> WorkflowEventByteArtifact | None:
        async with self._lock:
            return next(
                (
                    artifact
                    for artifact in self._event_byte_artifacts_by_admission.values()
                    if artifact.artifact_id == artifact_id
                ),
                None,
            )

    async def get_event_logical_channel_binding_by_artifact_id(
        self, *, artifact_id: str
    ) -> WorkflowEventLogicalChannelBinding | None:
        async with self._lock:
            return self._event_logical_channel_bindings_by_artifact.get(artifact_id)

    async def get_event_logical_channel_binding_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventLogicalChannelBindingIdempotencyRecord | None:
        async with self._lock:
            return self._event_logical_channel_binding_requests.get(
                (scope, publisher_subject_id, idempotency_key)
            )

    async def bind_event_logical_channel(
        self, request: WorkflowEventLogicalChannelBindingRequest
    ) -> WorkflowEventLogicalChannelBindingResult:
        async with self._lock:
            candidate = request.candidate
            key = (candidate.scope, request.publisher_subject_id, request.idempotency_key)
            prior = self._event_logical_channel_binding_requests.get(key)
            if prior is not None:
                status = (
                    WorkflowEventLogicalChannelBindingStatus.REPLAY
                    if prior.request_fingerprint == request.request_fingerprint
                    else WorkflowEventLogicalChannelBindingStatus.IDEMPOTENCY_CONFLICT
                )
                return WorkflowEventLogicalChannelBindingResult(status, prior.binding)

            outbox = next(
                (
                    entry
                    for entry in self._dispatch_outbox_entries_by_intent.values()
                    if entry.outbox_entry_id == candidate.outbox_entry_id
                ),
                None,
            )
            plan = self._plans.get(candidate.plan_id)
            orchestration_lease = self._leases_by_plan.get(candidate.plan_id)
            publication_lease = self._publication_leases_by_outbox.get(candidate.outbox_entry_id)
            admission = self._event_transport_admissions_by_event.get(candidate.event_id)
            artifact = self._event_byte_artifacts_by_admission.get(candidate.admission_id)
            if not self._event_logical_channel_binding_evidence_matches(
                outbox=outbox,
                plan=plan,
                orchestration_lease=orchestration_lease,
                publication_lease=publication_lease,
                admission=admission,
                artifact=artifact,
                request=request,
            ):
                return WorkflowEventLogicalChannelBindingResult(
                    WorkflowEventLogicalChannelBindingStatus.EVIDENCE_CONFLICT, None
                )
            current = self._event_logical_channel_bindings_by_artifact.get(candidate.artifact_id)
            if current is not None:
                return WorkflowEventLogicalChannelBindingResult(
                    WorkflowEventLogicalChannelBindingStatus.ALREADY_BOUND, current
                )
            self._event_logical_channel_bindings_by_artifact[candidate.artifact_id] = candidate
            self._event_logical_channel_binding_requests[key] = (
                WorkflowEventLogicalChannelBindingIdempotencyRecord(
                    request_fingerprint=request.request_fingerprint,
                    binding=candidate,
                )
            )
            return WorkflowEventLogicalChannelBindingResult(
                WorkflowEventLogicalChannelBindingStatus.BOUND, candidate
            )

    async def get_transport_profile_snapshot(
        self,
        *,
        transport_profile_id: str,
        transport_profile_revision: str,
    ) -> EventPhysicalTransportProfileSnapshot | None:
        async with self._lock:
            return self._transport_profile_snapshots.get(
                (transport_profile_id, transport_profile_revision)
            )

    async def get_transport_profile_snapshot_request(
        self,
        *,
        scope: WorkflowScope,
        snapshotter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowTransportProfileSnapshotIdempotencyRecord | None:
        async with self._lock:
            return self._transport_profile_snapshot_requests.get(
                (scope, snapshotter_subject_id, idempotency_key)
            )

    async def snapshot_transport_profile(
        self, request: WorkflowTransportProfileSnapshotRequest
    ) -> WorkflowTransportProfileSnapshotResult:
        async with self._lock:
            candidate = request.candidate
            key = (candidate.scope, request.snapshotter_subject_id, request.idempotency_key)
            prior = self._transport_profile_snapshot_requests.get(key)
            if prior is not None:
                status = (
                    WorkflowTransportProfileSnapshotStatus.REPLAY
                    if prior.request_fingerprint == request.request_fingerprint
                    else WorkflowTransportProfileSnapshotStatus.IDEMPOTENCY_CONFLICT
                )
                return WorkflowTransportProfileSnapshotResult(status, prior.snapshot)

            if not self._transport_profile_snapshot_evidence_matches(request):
                return WorkflowTransportProfileSnapshotResult(
                    WorkflowTransportProfileSnapshotStatus.SOURCE_CONFLICT, None
                )
            profile_key = (
                candidate.transport_profile_id,
                candidate.transport_profile_revision,
            )
            current = self._transport_profile_snapshots.get(profile_key)
            if current is not None:
                return WorkflowTransportProfileSnapshotResult(
                    WorkflowTransportProfileSnapshotStatus.ALREADY_SNAPSHOTTED, current
                )
            self._transport_profile_snapshots[profile_key] = candidate
            self._transport_profile_snapshot_requests[key] = (
                WorkflowTransportProfileSnapshotIdempotencyRecord(
                    request_fingerprint=request.request_fingerprint,
                    snapshot=candidate,
                )
            )
            return WorkflowTransportProfileSnapshotResult(
                WorkflowTransportProfileSnapshotStatus.SNAPSHOTTED, candidate
            )

    async def get_transport_route_snapshot(
        self,
        *,
        route_id: str,
        route_revision: str,
    ) -> EventPhysicalTransportRouteSnapshot | None:
        async with self._lock:
            return self._transport_route_snapshots.get((route_id, route_revision))

    async def get_transport_route_snapshot_request(
        self,
        *,
        scope: WorkflowScope,
        snapshotter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowTransportRouteSnapshotIdempotencyRecord | None:
        async with self._lock:
            return self._transport_route_snapshot_requests.get(
                (scope, snapshotter_subject_id, idempotency_key)
            )

    async def snapshot_transport_route(
        self, request: WorkflowTransportRouteSnapshotRequest
    ) -> WorkflowTransportRouteSnapshotResult:
        async with self._lock:
            candidate = request.candidate
            key = (candidate.scope, request.snapshotter_subject_id, request.idempotency_key)
            prior = self._transport_route_snapshot_requests.get(key)
            if prior is not None:
                status = (
                    WorkflowTransportRouteSnapshotStatus.REPLAY
                    if prior.request_fingerprint == request.request_fingerprint
                    else WorkflowTransportRouteSnapshotStatus.IDEMPOTENCY_CONFLICT
                )
                return WorkflowTransportRouteSnapshotResult(status, prior.snapshot)

            if not self._transport_route_snapshot_evidence_matches(request):
                return WorkflowTransportRouteSnapshotResult(
                    WorkflowTransportRouteSnapshotStatus.SOURCE_CONFLICT, None
                )
            route_key = (candidate.route_id, candidate.route_revision)
            current = self._transport_route_snapshots.get(route_key)
            if current is not None:
                return WorkflowTransportRouteSnapshotResult(
                    WorkflowTransportRouteSnapshotStatus.ALREADY_SNAPSHOTTED, current
                )
            self._transport_route_snapshots[route_key] = candidate
            self._transport_route_snapshot_requests[key] = (
                WorkflowTransportRouteSnapshotIdempotencyRecord(
                    request_fingerprint=request.request_fingerprint,
                    snapshot=candidate,
                )
            )
            return WorkflowTransportRouteSnapshotResult(
                WorkflowTransportRouteSnapshotStatus.SNAPSHOTTED, candidate
            )

    async def synchronize_credential_assignments(
        self, assignments: tuple[DeploymentPhysicalTransportCredentialAssignment, ...]
    ) -> None:
        async with self._lock:
            synchronized = dict(self._credential_assignments)
            for assignment in assignments:
                key = (assignment.assignment_id, assignment.assignment_revision)
                prior = synchronized.get(key)
                if prior is not None and prior != assignment:
                    raise WorkflowTransportCredentialAssignmentSnapshotError(
                        "workflow_transport_credential_assignment_registry_conflict",
                        "Credential-assignment registry evidence conflicts with history.",
                    )
                synchronized[key] = assignment
            for assignment_id in {key[0] for key in synchronized}:
                try:
                    select_deployment_physical_transport_credential_assignment_head(
                        tuple(
                            assignment
                            for (candidate_id, _), assignment in synchronized.items()
                            if candidate_id == assignment_id
                        )
                    )
                except ValueError as exc:
                    raise WorkflowTransportCredentialAssignmentSnapshotError(
                        "workflow_transport_credential_assignment_registry_conflict",
                        "Credential-assignment registry head evidence is ambiguous.",
                    ) from exc
            self._credential_assignments = synchronized

    async def get_active_credential_assignment(
        self,
        *,
        assignment_id: str,
        assignment_revision: str,
    ) -> DeploymentPhysicalTransportCredentialAssignment | None:
        async with self._lock:
            candidates = tuple(
                assignment
                for (candidate_id, _), assignment in self._credential_assignments.items()
                if candidate_id == assignment_id
            )
            try:
                assignment = select_deployment_physical_transport_credential_assignment_head(
                    candidates
                )
            except ValueError as exc:
                raise WorkflowTransportCredentialAssignmentSnapshotError(
                    "workflow_transport_credential_assignment_registry_contract_violation",
                    "Credential-assignment registry head evidence is ambiguous.",
                ) from exc
            now = datetime.now(UTC)
            if (
                assignment is None
                or assignment.assignment_revision != assignment_revision
                or not assignment.active
                or assignment.revoked
                or not assignment.activated_at <= now < assignment.expires_at
            ):
                return None
            return assignment

    async def get_credential_assignment_snapshot(
        self,
        *,
        assignment_id: str,
        assignment_revision: str,
    ) -> EventPhysicalTransportCredentialAssignmentSnapshot | None:
        async with self._lock:
            return self._credential_assignment_snapshots.get((assignment_id, assignment_revision))

    async def list_credential_assignment_snapshots(
        self,
        *,
        scope: WorkflowScope,
        limit: int = 256,
    ) -> tuple[EventPhysicalTransportCredentialAssignmentSnapshot, ...]:
        if not 1 <= limit <= 256:
            raise ValueError("credential-assignment snapshot limit is invalid")
        async with self._lock:
            matches = sorted(
                (
                    snapshot
                    for snapshot in self._credential_assignment_snapshots.values()
                    if snapshot.scope == scope
                ),
                key=lambda value: (value.assignment_id, value.assignment_revision),
            )
            return tuple(matches[:limit])

    async def get_credential_assignment_snapshot_request(
        self,
        *,
        scope: WorkflowScope,
        snapshotter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowTransportCredentialAssignmentSnapshotIdempotencyRecord | None:
        async with self._lock:
            return self._credential_assignment_snapshot_requests.get(
                (scope, snapshotter_subject_id, idempotency_key)
            )

    async def snapshot_credential_assignment(
        self,
        request: WorkflowTransportCredentialAssignmentSnapshotRequest,
    ) -> WorkflowTransportCredentialAssignmentSnapshotResult:
        validate_workflow_transport_credential_assignment_snapshot_request(request)
        candidate = request.candidate
        key = (request.scope, request.snapshotter_subject_id, request.idempotency_key)
        async with self._lock:
            prior = self._credential_assignment_snapshot_requests.get(key)
            if prior is not None:
                status = (
                    WorkflowTransportCredentialAssignmentSnapshotStatus.REPLAY
                    if prior.request_fingerprint == request.request_fingerprint
                    else WorkflowTransportCredentialAssignmentSnapshotStatus.IDEMPOTENCY_CONFLICT
                )
                return WorkflowTransportCredentialAssignmentSnapshotResult(status, prior.snapshot)
            try:
                source = select_deployment_physical_transport_credential_assignment_head(
                    tuple(
                        assignment
                        for (assignment_id, _), assignment in self._credential_assignments.items()
                        if assignment_id == request.expected_source_assignment_id
                    )
                )
            except ValueError as exc:
                raise WorkflowTransportCredentialAssignmentSnapshotError(
                    "workflow_transport_credential_assignment_registry_contract_violation",
                    "Credential-assignment registry head evidence is ambiguous.",
                ) from exc
            if (
                source is not None
                and source.assignment_revision != request.expected_source_assignment_revision
            ):
                source = None
            route = self._transport_route_snapshots.get(
                (candidate.route_id, candidate.route_revision)
            )
            if not self._credential_assignment_snapshot_evidence_matches(
                request=request,
                source=source,
                route=route,
                captured_at=datetime.now(UTC),
            ):
                return WorkflowTransportCredentialAssignmentSnapshotResult(
                    WorkflowTransportCredentialAssignmentSnapshotStatus.SOURCE_CONFLICT,
                    None,
                )
            snapshot_key = (candidate.assignment_id, candidate.assignment_revision)
            existing = self._credential_assignment_snapshots.get(snapshot_key)
            if existing is not None:
                return WorkflowTransportCredentialAssignmentSnapshotResult(
                    WorkflowTransportCredentialAssignmentSnapshotStatus.ALREADY_SNAPSHOTTED,
                    existing,
                )
            try:
                await request.required_precommit_audit()
            except Exception:
                return WorkflowTransportCredentialAssignmentSnapshotResult(
                    WorkflowTransportCredentialAssignmentSnapshotStatus.PRECOMMIT_AUDIT_FAILED,
                    None,
                )
            self._credential_assignment_snapshots[snapshot_key] = candidate
            self._credential_assignment_snapshot_requests[key] = (
                WorkflowTransportCredentialAssignmentSnapshotIdempotencyRecord(
                    request_fingerprint=request.request_fingerprint,
                    snapshot=candidate,
                )
            )
            return WorkflowTransportCredentialAssignmentSnapshotResult(
                WorkflowTransportCredentialAssignmentSnapshotStatus.SNAPSHOTTED,
                candidate,
            )

    async def get_event_logical_channel_binding_by_id(
        self, *, binding_id: str
    ) -> WorkflowEventLogicalChannelBinding | None:
        async with self._lock:
            return next(
                (
                    value
                    for value in self._event_logical_channel_bindings_by_artifact.values()
                    if value.binding_id == binding_id
                ),
                None,
            )

    async def get_transport_profile_snapshot_by_id(
        self, *, snapshot_id: str
    ) -> EventPhysicalTransportProfileSnapshot | None:
        async with self._lock:
            return next(
                (
                    value
                    for value in self._transport_profile_snapshots.values()
                    if value.snapshot_id == snapshot_id
                ),
                None,
            )

    async def get_transport_compatibility_admission(
        self,
        *,
        logical_channel_binding_id: str,
        transport_profile_snapshot_id: str,
        policy_digest: str,
    ) -> WorkflowEventTransportCompatibilityAdmission | None:
        async with self._lock:
            return self._transport_compatibility_admission_pairs.get(
                (
                    logical_channel_binding_id,
                    transport_profile_snapshot_id,
                    policy_digest,
                )
            )

    async def list_transport_compatibility_admissions_by_binding(
        self, *, logical_channel_binding_id: str
    ) -> tuple[WorkflowEventTransportCompatibilityAdmission, ...]:
        async with self._lock:
            return tuple(
                sorted(
                    (
                        admission
                        for admission in self._transport_compatibility_admissions.values()
                        if admission.logical_channel_binding_id == logical_channel_binding_id
                    ),
                    key=lambda admission: (
                        admission.transport_profile_snapshot_id,
                        admission.policy_digest,
                        admission.compatibility_admission_id,
                    ),
                )
            )

    async def get_transport_compatibility_admission_request(
        self,
        *,
        scope: WorkflowScope,
        admitter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventTransportCompatibilityAdmissionIdempotencyRecord | None:
        async with self._lock:
            return self._transport_compatibility_admission_requests.get(
                (scope, admitter_subject_id, idempotency_key)
            )

    async def admit_transport_compatibility(
        self, request: WorkflowEventTransportCompatibilityAdmissionRequest
    ) -> WorkflowEventTransportCompatibilityAdmissionResult:
        async with self._lock:
            candidate = request.candidate
            key = (candidate.scope, request.admitter_subject_id, request.idempotency_key)
            prior = self._transport_compatibility_admission_requests.get(key)
            if prior is not None:
                status = (
                    WorkflowEventTransportCompatibilityAdmissionStatus.REPLAY
                    if prior.request_fingerprint == request.request_fingerprint
                    else WorkflowEventTransportCompatibilityAdmissionStatus.IDEMPOTENCY_CONFLICT
                )
                return WorkflowEventTransportCompatibilityAdmissionResult(status, prior.admission)

            binding = next(
                (
                    value
                    for value in self._event_logical_channel_bindings_by_artifact.values()
                    if value.binding_id == candidate.logical_channel_binding_id
                ),
                None,
            )
            profile = next(
                (
                    value
                    for value in self._transport_profile_snapshots.values()
                    if value.snapshot_id == candidate.transport_profile_snapshot_id
                ),
                None,
            )
            if not self._transport_compatibility_admission_evidence_matches(
                binding=binding,
                profile=profile,
                request=request,
            ):
                return WorkflowEventTransportCompatibilityAdmissionResult(
                    WorkflowEventTransportCompatibilityAdmissionStatus.EVIDENCE_CONFLICT,
                    None,
                )

            pair_key = (
                candidate.logical_channel_binding_id,
                candidate.transport_profile_snapshot_id,
                candidate.policy_digest,
            )
            existing = self._transport_compatibility_admission_pairs.get(pair_key)
            if existing is not None:
                return WorkflowEventTransportCompatibilityAdmissionResult(
                    WorkflowEventTransportCompatibilityAdmissionStatus.ALREADY_ADMITTED,
                    existing,
                )
            if candidate.compatibility_admission_id in self._transport_compatibility_admissions:
                return WorkflowEventTransportCompatibilityAdmissionResult(
                    WorkflowEventTransportCompatibilityAdmissionStatus.EVIDENCE_CONFLICT,
                    None,
                )

            self._transport_compatibility_admissions[candidate.compatibility_admission_id] = (
                candidate
            )
            self._transport_compatibility_admission_pairs[pair_key] = candidate
            self._transport_compatibility_admission_requests[key] = (
                WorkflowEventTransportCompatibilityAdmissionIdempotencyRecord(
                    request_fingerprint=request.request_fingerprint,
                    admission=candidate,
                )
            )
            return WorkflowEventTransportCompatibilityAdmissionResult(
                WorkflowEventTransportCompatibilityAdmissionStatus.ADMITTED,
                candidate,
            )

    async def get_transport_compatibility_admission_by_id(
        self, *, admission_id: str
    ) -> WorkflowEventTransportCompatibilityAdmission | None:
        async with self._lock:
            return self._transport_compatibility_admissions.get(admission_id)

    async def get_transport_route_snapshot_by_id(
        self, *, snapshot_id: str
    ) -> EventPhysicalTransportRouteSnapshot | None:
        async with self._lock:
            return next(
                (
                    value
                    for value in self._transport_route_snapshots.values()
                    if value.snapshot_id == snapshot_id
                ),
                None,
            )

    async def get_physical_transport_route_binding(
        self, *, logical_channel_binding_id: str
    ) -> WorkflowEventPhysicalTransportRouteBinding | None:
        async with self._lock:
            return self._physical_transport_route_bindings.get(logical_channel_binding_id)

    async def list_physical_transport_route_bindings(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowEventPhysicalTransportRouteBinding, ...]:
        async with self._lock:
            return tuple(
                sorted(
                    (
                        binding
                        for binding in self._physical_transport_route_bindings.values()
                        if binding.scope == scope
                    ),
                    key=lambda binding: binding.binding_id,
                )[:limit]
            )

    async def get_physical_transport_route_binding_request(
        self,
        *,
        scope: WorkflowScope,
        binder_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventPhysicalTransportRouteBindingIdempotencyRecord | None:
        async with self._lock:
            return self._physical_transport_route_binding_requests.get(
                (scope, binder_subject_id, idempotency_key)
            )

    async def bind_physical_transport_route(
        self, request: WorkflowEventPhysicalTransportRouteBindingRequest
    ) -> WorkflowEventPhysicalTransportRouteBindingResult:
        async with self._lock:
            candidate = request.candidate
            key = (candidate.scope, request.binder_subject_id, request.idempotency_key)
            prior = self._physical_transport_route_binding_requests.get(key)
            if prior is not None:
                status = (
                    WorkflowEventPhysicalTransportRouteBindingStatus.REPLAY
                    if prior.request_fingerprint == request.request_fingerprint
                    else WorkflowEventPhysicalTransportRouteBindingStatus.IDEMPOTENCY_CONFLICT
                )
                return WorkflowEventPhysicalTransportRouteBindingResult(status, prior.binding)

            logical = next(
                (
                    value
                    for value in self._event_logical_channel_bindings_by_artifact.values()
                    if value.binding_id == candidate.logical_channel_binding_id
                ),
                None,
            )
            admission = self._transport_compatibility_admissions.get(
                candidate.transport_compatibility_admission_id
            )
            profile = next(
                (
                    value
                    for value in self._transport_profile_snapshots.values()
                    if value.snapshot_id == candidate.transport_profile_snapshot_id
                ),
                None,
            )
            route = next(
                (
                    value
                    for value in self._transport_route_snapshots.values()
                    if value.snapshot_id == candidate.transport_route_snapshot_id
                ),
                None,
            )
            if not self._physical_transport_route_binding_evidence_matches(
                logical=logical,
                admission=admission,
                profile=profile,
                route=route,
                request=request,
            ):
                return WorkflowEventPhysicalTransportRouteBindingResult(
                    WorkflowEventPhysicalTransportRouteBindingStatus.EVIDENCE_CONFLICT,
                    None,
                )

            current = self._physical_transport_route_bindings.get(
                candidate.logical_channel_binding_id
            )
            if current is not None:
                return WorkflowEventPhysicalTransportRouteBindingResult(
                    WorkflowEventPhysicalTransportRouteBindingStatus.ALREADY_BOUND,
                    current,
                )
            self._physical_transport_route_bindings[candidate.logical_channel_binding_id] = (
                candidate
            )
            self._physical_transport_route_binding_requests[key] = (
                WorkflowEventPhysicalTransportRouteBindingIdempotencyRecord(
                    request_fingerprint=request.request_fingerprint,
                    binding=candidate,
                )
            )
            return WorkflowEventPhysicalTransportRouteBindingResult(
                WorkflowEventPhysicalTransportRouteBindingStatus.BOUND,
                candidate,
            )

    async def synchronize_route_selection_heads(
        self, heads: tuple[DeploymentEventTransportRouteSelectionHead, ...]
    ) -> None:
        async with self._lock:
            if not heads:
                self._raise_route_selection_head_sync_conflict()
            unique: dict[tuple[WorkflowScope, str], DeploymentEventTransportRouteSelectionHead] = {}
            for head in heads:
                key = (head.scope, head.route_set_id)
                duplicate = unique.get(key)
                if duplicate is not None and duplicate != head:
                    self._raise_route_selection_head_sync_conflict()
                unique[key] = head
            authoritative_scopes = {head.scope for head in unique.values()}
            existing_keys = {
                key for key in self._route_selection_heads if key[0] in authoritative_scopes
            }
            if not existing_keys.issubset(unique):
                self._raise_route_selection_head_sync_conflict()
            replacements: dict[
                tuple[WorkflowScope, str], DeploymentEventTransportRouteSelectionHead
            ] = {}
            for key in sorted(
                unique,
                key=lambda value: (
                    value[0].organization_id,
                    value[0].environment_id,
                    value[0].site_id,
                    value[1],
                ),
            ):
                candidate = unique[key]
                current = self._route_selection_heads.get(key)
                if current == candidate:
                    continue
                if current is not None and (
                    candidate.generation <= current.generation
                    or candidate.fencing_token_digest == current.fencing_token_digest
                ):
                    self._raise_route_selection_head_sync_conflict()
                replacements[key] = candidate
            self._route_selection_heads.update(replacements)

    async def get_physical_transport_route_binding_by_id(
        self, *, binding_id: str
    ) -> WorkflowEventPhysicalTransportRouteBinding | None:
        async with self._lock:
            return next(
                (
                    binding
                    for binding in self._physical_transport_route_bindings.values()
                    if binding.binding_id == binding_id
                ),
                None,
            )

    async def get_current_route_selection_head(
        self, *, scope: WorkflowScope, route_set_id: str
    ) -> DeploymentEventTransportRouteSelectionHead | None:
        async with self._lock:
            return self._route_selection_heads.get((scope, route_set_id))

    async def get_route_freshness_admission(
        self, *, physical_transport_route_binding_id: str
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmission | None:
        async with self._lock:
            return self._route_freshness_admissions.get(physical_transport_route_binding_id)

    async def get_route_freshness_admission_by_id(
        self, *, freshness_admission_id: str
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmission | None:
        async with self._lock:
            return next(
                (
                    admission
                    for admission in self._route_freshness_admissions.values()
                    if admission.freshness_admission_id == freshness_admission_id
                ),
                None,
            )

    async def list_route_freshness_admissions(
        self, *, scope: WorkflowScope, limit: int
    ) -> tuple[WorkflowEventPhysicalTransportRouteFreshnessAdmission, ...]:
        capped = min(max(limit, 0), 256)
        async with self._lock:
            admissions = sorted(
                (
                    admission
                    for admission in self._route_freshness_admissions.values()
                    if admission.scope == scope
                ),
                key=lambda admission: admission.freshness_admission_id,
            )
            admissions.sort(key=lambda admission: admission.evaluated_at, reverse=True)
            return tuple(admissions[:capped])

    async def get_route_freshness_admission_request(
        self,
        *,
        scope: WorkflowScope,
        admitter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmissionIdempotencyRecord | None:
        async with self._lock:
            return self._route_freshness_admission_requests.get(
                (scope, admitter_subject_id, idempotency_key)
            )

    async def admit_physical_transport_route_freshness(
        self, request: WorkflowEventPhysicalTransportRouteFreshnessAdmissionRequest
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult:
        async with self._lock:
            candidate = request.candidate
            binding = next(
                (
                    value
                    for value in self._physical_transport_route_bindings.values()
                    if value.binding_id == candidate.physical_transport_route_binding_id
                ),
                None,
            )
            route = next(
                (
                    value
                    for value in self._transport_route_snapshots.values()
                    if value.snapshot_id == candidate.transport_route_snapshot_id
                ),
                None,
            )
            head = self._route_selection_heads.get((request.scope, request.expected_route_set_id))
            if not self._route_freshness_admission_evidence_matches(
                binding=binding,
                route=route,
                head=head,
                request=request,
            ):
                return WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult(
                    WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus.EVIDENCE_CONFLICT,
                    None,
                )

            key = (request.scope, request.admitter_subject_id, request.idempotency_key)
            prior = self._route_freshness_admission_requests.get(key)
            if prior is not None:
                if prior.request_fingerprint != request.request_fingerprint:
                    return WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult(
                        WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus.IDEMPOTENCY_CONFLICT,
                        prior.admission,
                    )
                if head is None or not self._route_freshness_admission_remains_current(
                    prior.admission, head=head, observed_at=request.evaluated_at
                ):
                    return WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult(
                        WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus.EVIDENCE_CONFLICT,
                        None,
                    )
                return WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult(
                    WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus.REPLAY,
                    prior.admission,
                )

            existing = self._route_freshness_admissions.get(
                candidate.physical_transport_route_binding_id
            )
            if existing is not None:
                return WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult(
                    WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus.ALREADY_ADMITTED,
                    existing,
                )
            self._route_freshness_admissions[candidate.physical_transport_route_binding_id] = (
                candidate
            )
            self._route_freshness_admission_requests[key] = (
                WorkflowEventPhysicalTransportRouteFreshnessAdmissionIdempotencyRecord(
                    request_fingerprint=request.request_fingerprint,
                    admission=candidate,
                )
            )
            return WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult(
                WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus.ADMITTED_CURRENT,
                candidate,
            )

    async def get_endpoint_resolution_authorization_lease(
        self, *, freshness_admission_id: str
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease | None:
        async with self._lock:
            return self._endpoint_resolution_authorization_leases.get(freshness_admission_id)

    async def get_endpoint_resolution_authorization_lease_by_id(
        self, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease | None:
        async with self._lock:
            return next(
                (
                    lease
                    for lease in self._endpoint_resolution_authorization_leases.values()
                    if lease.authorization_lease_id == authorization_lease_id
                ),
                None,
            )

    async def get_endpoint_materialization_claim_by_lease(
        self, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaim | None:
        async with self._lock:
            return self._endpoint_materialization_claims.get(authorization_lease_id)

    async def get_endpoint_materialization_attempt_by_lease(
        self, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationAttempt | None:
        async with self._lock:
            return self._endpoint_materialization_attempts.get(authorization_lease_id)

    async def list_endpoint_materialization_attempts(
        self, *, scope: WorkflowScope, limit: int
    ) -> tuple[WorkflowEventPhysicalTransportEndpointMaterializationAttempt, ...]:
        capped = min(max(limit, 0), 256)
        async with self._lock:
            attempts = sorted(
                (
                    attempt
                    for attempt in self._endpoint_materialization_attempts.values()
                    if attempt.scope == scope
                ),
                key=lambda attempt: (attempt.started_at, attempt.attempt_id),
                reverse=True,
            )
            return tuple(attempts[:capped])

    async def get_endpoint_materialization_result_by_lease(
        self, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationResult | None:
        async with self._lock:
            return self._endpoint_materialization_results.get(authorization_lease_id)

    async def list_endpoint_resolution_authorization_leases(
        self, *, scope: WorkflowScope, limit: int
    ) -> tuple[WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease, ...]:
        capped = min(max(limit, 0), 256)
        async with self._lock:
            leases = sorted(
                (
                    lease
                    for lease in self._endpoint_resolution_authorization_leases.values()
                    if lease.scope == scope
                ),
                key=lambda lease: lease.authorization_lease_id,
            )
            leases.sort(key=lambda lease: lease.issued_at, reverse=True)
            return tuple(leases[:capped])

    async def get_endpoint_resolution_authorization_lease_request(
        self,
        *,
        scope: WorkflowScope,
        resolver_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseIdempotencyRecord | None:
        async with self._lock:
            return self._endpoint_resolution_authorization_requests.get(
                (scope, resolver_subject_id, idempotency_key)
            )

    async def authorize_endpoint_resolution(
        self,
        request: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRequest,
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult:
        async with self._lock:
            observed_at = datetime.now(UTC)
            binding = next(
                (
                    value
                    for value in self._physical_transport_route_bindings.values()
                    if value.binding_id == request.expected_physical_transport_route_binding_id
                ),
                None,
            )
            route = next(
                (
                    value
                    for value in self._transport_route_snapshots.values()
                    if value.snapshot_id == request.expected_transport_route_snapshot_id
                ),
                None,
            )
            head = self._route_selection_heads.get((request.scope, request.expected_route_set_id))
            freshness = next(
                (
                    value
                    for value in self._route_freshness_admissions.values()
                    if value.freshness_admission_id == request.expected_freshness_admission_id
                ),
                None,
            )
            if not self._endpoint_resolution_authorization_evidence_matches(
                binding=binding,
                route=route,
                head=head,
                freshness=freshness,
                request=request,
                observed_at=observed_at,
            ):
                return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult(
                    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus.EVIDENCE_CONFLICT,
                    None,
                )

            key = (request.scope, request.resolver_subject_id, request.idempotency_key)
            prior = self._endpoint_resolution_authorization_requests.get(key)
            if prior is not None:
                if prior.request_fingerprint != request.request_fingerprint:
                    return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult(
                        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus.IDEMPOTENCY_CONFLICT,
                        prior.lease,
                    )
                if (
                    head is None
                    or freshness is None
                    or not (
                        observed_at < prior.lease.valid_until
                        and self._endpoint_resolution_authorization_remains_current(
                            prior.lease,
                            head=head,
                            freshness=freshness,
                            observed_at=observed_at,
                        )
                    )
                ):
                    return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult(
                        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus.EVIDENCE_CONFLICT,
                        None,
                    )
                return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult(
                    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus.REPLAY,
                    prior.lease,
                )

            assert freshness is not None
            if observed_at + timedelta(seconds=15) > freshness.valid_until:
                return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult(
                    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus.EVIDENCE_CONFLICT,
                    None,
                )
            existing = self._endpoint_resolution_authorization_leases.get(
                freshness.freshness_admission_id
            )
            if existing is not None:
                return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult(
                    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus.ALREADY_AUTHORIZED,
                    existing,
                )
            lease = self._endpoint_resolution_authorization_lease(
                request=request,
                freshness=freshness,
                issued_at=observed_at,
            )
            self._endpoint_resolution_authorization_leases[freshness.freshness_admission_id] = lease
            self._endpoint_resolution_authorization_requests[key] = (
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseIdempotencyRecord(
                    request_fingerprint=request.request_fingerprint,
                    lease=lease,
                )
            )
            return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult(
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus.AUTHORIZED,
                lease,
            )

    async def claim_endpoint_materialization(
        self,
        request: WorkflowEventPhysicalTransportEndpointMaterializationClaimRequest,
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationClaimResult:
        claim_status = WorkflowEventPhysicalTransportEndpointMaterializationClaimStatus
        async with self._lock:
            prior = self._endpoint_materialization_claims.get(request.authorization_lease_id)
            if prior is not None:
                attempt = self._endpoint_materialization_attempts.get(
                    request.authorization_lease_id
                )
                result = self._endpoint_materialization_results.get(request.authorization_lease_id)
                exact = bool(
                    prior.claim_id == request.claim_id
                    and prior.attempt_id == request.attempt_id
                    and prior.materialization_id == request.materialization_id
                    and prior.authorization_lease_digest == request.authorization_lease_digest
                    and prior.scope == request.scope
                    and prior.resolver_subject_id == request.resolver_subject_id
                    and prior.request_fingerprint == request.request_fingerprint
                    and prior.idempotency_digest == request.idempotency_digest
                )
                if exact:
                    status = claim_status.CLAIM_ONLY_UNCERTAIN
                    if result is not None:
                        status = claim_status.REPLAY_COMPLETED
                    return WorkflowEventPhysicalTransportEndpointMaterializationClaimResult(
                        status,
                        prior,
                        attempt,
                        result,
                    )
                status = claim_status.ALREADY_CONSUMED
                if prior.idempotency_digest == request.idempotency_digest:
                    status = claim_status.IDEMPOTENCY_CONFLICT
                return WorkflowEventPhysicalTransportEndpointMaterializationClaimResult(
                    status,
                    None,
                    None,
                    None,
                )
            if any(
                claim.idempotency_digest == request.idempotency_digest
                for claim in self._endpoint_materialization_claims.values()
            ):
                return WorkflowEventPhysicalTransportEndpointMaterializationClaimResult(
                    WorkflowEventPhysicalTransportEndpointMaterializationClaimStatus.IDEMPOTENCY_CONFLICT,
                    None,
                    None,
                    None,
                )

            observed_at = datetime.now(UTC)
            lease = next(
                (
                    value
                    for value in self._endpoint_resolution_authorization_leases.values()
                    if value.authorization_lease_id == request.authorization_lease_id
                ),
                None,
            )
            freshness = next(
                (
                    value
                    for value in self._route_freshness_admissions.values()
                    if value.freshness_admission_id == request.expected_freshness_admission_id
                ),
                None,
            )
            head = self._route_selection_heads.get((request.scope, request.expected_route_set_id))
            binding = next(
                (
                    value
                    for value in self._physical_transport_route_bindings.values()
                    if value.binding_id == request.expected_physical_transport_route_binding_id
                ),
                None,
            )
            route = next(
                (
                    value
                    for value in self._transport_route_snapshots.values()
                    if value.snapshot_id == request.expected_transport_route_snapshot_id
                ),
                None,
            )
            policy = code_owned_workflow_event_physical_transport_endpoint_materialization_policy()
            if not (
                lease is not None
                and freshness is not None
                and head is not None
                and binding is not None
                and route is not None
                and observed_at < lease.valid_until
                and observed_at < freshness.valid_until
                and lease.canonical_digest == request.authorization_lease_digest
                and lease.freshness_admission_id == freshness.freshness_admission_id
                and lease.freshness_admission_digest == freshness.canonical_digest
                and lease.physical_transport_route_binding_id == binding.binding_id
                and lease.physical_transport_route_binding_digest == binding.canonical_digest
                and lease.transport_route_snapshot_id == route.snapshot_id
                and lease.transport_route_snapshot_digest == route.canonical_digest
                and lease.current_selection_head_id == head.head_id
                and lease.current_selection_head_digest == head.canonical_digest
                and lease.current_selection_head_generation == head.generation
                and lease.current_selection_head_fencing_token_digest == head.fencing_token_digest
                and lease.scope == request.scope
                and lease.resolver_subject_id == request.resolver_subject_id
                and lease.route_set_id == request.expected_route_set_id
                and lease.route_set_revision == request.expected_route_set_revision
                and lease.selection_epoch_id == request.expected_selection_epoch_id
                and lease.selection_epoch_revision == request.expected_selection_epoch_revision
                and lease.selected_route_id == request.expected_selected_route_id
                and lease.selected_route_revision == request.expected_selected_route_revision
                and lease.selected_route_digest == request.expected_selected_route_digest
                and head.current
                and head.selection_active
                and head.selection_eligible
                and not head.selection_suspended
                and not head.selection_withdrawn
                and not head.selection_superseded
                and policy.policy_id == request.expected_materialization_policy_id
                and policy.policy_version == request.expected_materialization_policy_version
                and policy.canonical_digest == request.expected_materialization_policy_digest
                and request.irreversible_consumption_acknowledged
                and request.uncertain_outcome_requires_new_authorization_acknowledged
            ):
                return WorkflowEventPhysicalTransportEndpointMaterializationClaimResult(
                    WorkflowEventPhysicalTransportEndpointMaterializationClaimStatus.EVIDENCE_CONFLICT,
                    None,
                    None,
                    None,
                )
            claim = self._endpoint_materialization_claim(request, claimed_at=observed_at)
            attempt = self._endpoint_materialization_attempt(
                request,
                claim=claim,
                started_at=observed_at,
                lease_valid_until=lease.valid_until,
            )
            self._endpoint_materialization_claims[request.authorization_lease_id] = claim
            self._endpoint_materialization_attempts[request.authorization_lease_id] = attempt
            return WorkflowEventPhysicalTransportEndpointMaterializationClaimResult(
                WorkflowEventPhysicalTransportEndpointMaterializationClaimStatus.CLAIMED,
                claim,
                attempt,
                None,
            )

    async def record_endpoint_materialization_result(
        self,
        request: WorkflowEventPhysicalTransportEndpointMaterializationResultRequest,
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationResultWrite:
        result = request.result
        async with self._lock:
            prior = self._endpoint_materialization_results.get(result.authorization_lease_id)
            if prior is not None:
                status = (
                    WorkflowEventPhysicalTransportEndpointMaterializationResultStatus.REPLAY
                    if prior == result
                    else WorkflowEventPhysicalTransportEndpointMaterializationResultStatus.CONFLICT
                )
                return WorkflowEventPhysicalTransportEndpointMaterializationResultWrite(
                    status,
                    prior if prior == result else None,
                )
            claim = self._endpoint_materialization_claims.get(result.authorization_lease_id)
            attempt = self._endpoint_materialization_attempts.get(result.authorization_lease_id)
            lease = next(
                (
                    value
                    for value in self._endpoint_resolution_authorization_leases.values()
                    if value.authorization_lease_id == result.authorization_lease_id
                ),
                None,
            )
            freshness = (
                None
                if attempt is None
                else next(
                    (
                        value
                        for value in self._route_freshness_admissions.values()
                        if value.freshness_admission_id == attempt.freshness_admission_id
                    ),
                    None,
                )
            )
            head = (
                None
                if lease is None
                else self._route_selection_heads.get((lease.scope, lease.route_set_id))
            )
            observed_at = datetime.now(UTC)
            if not (
                claim is not None
                and attempt is not None
                and lease is not None
                and freshness is not None
                and head is not None
                and observed_at < freshness.valid_until
                and observed_at < lease.valid_until
                and result.completed_at < freshness.valid_until
                and result.completed_at < lease.valid_until
                and request.expected_lease_valid_until == lease.valid_until
                and request.expected_claim_digest == claim.canonical_digest
                and request.expected_attempt_digest == attempt.canonical_digest
                and result.consumption_claim_id == claim.claim_id
                and result.attempt_id == attempt.attempt_id
                and result.materialization_id == attempt.materialization_id
                and head.head_id == request.expected_current_selection_head_id
                and head.canonical_digest == request.expected_current_selection_head_digest
                and head.generation == request.expected_current_selection_head_generation
                and head.fencing_token_digest
                == request.expected_current_selection_head_fencing_token_digest
                and head.current
                and head.selection_active
                and head.selection_eligible
                and not head.selection_suspended
                and not head.selection_withdrawn
                and not head.selection_superseded
            ):
                return WorkflowEventPhysicalTransportEndpointMaterializationResultWrite(
                    WorkflowEventPhysicalTransportEndpointMaterializationResultStatus.CONFLICT,
                    None,
                )
            self._endpoint_materialization_results[result.authorization_lease_id] = result
            return WorkflowEventPhysicalTransportEndpointMaterializationResultWrite(
                WorkflowEventPhysicalTransportEndpointMaterializationResultStatus.RECORDED,
                result,
            )

    async def acquire_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseAcquireRequest
    ) -> WorkflowOutboxPublicationLeaseAcquireResult:
        async with self._lock:
            candidate = request.candidate
            key = (candidate.scope, candidate.publisher_subject_id, request.idempotency_key)
            prior = self._publication_lease_acquire_requests.get(key)
            if prior is not None:
                status = (
                    WorkflowOutboxPublicationLeaseAcquireStatus.REPLAY
                    if prior.request_fingerprint == request.request_fingerprint
                    else WorkflowOutboxPublicationLeaseAcquireStatus.IDEMPOTENCY_CONFLICT
                )
                return WorkflowOutboxPublicationLeaseAcquireResult(status, prior.lease)

            outbox = next(
                (
                    entry
                    for entry in self._dispatch_outbox_entries_by_intent.values()
                    if entry.outbox_entry_id == candidate.outbox_entry_id
                ),
                None,
            )
            plan = self._plans.get(candidate.plan_id)
            orchestration_lease = self._leases_by_plan.get(candidate.plan_id)
            if not self._publication_evidence_matches(
                outbox=outbox,
                plan=plan,
                orchestration_lease=orchestration_lease,
                request=request,
            ):
                return WorkflowOutboxPublicationLeaseAcquireResult(
                    WorkflowOutboxPublicationLeaseAcquireStatus.EVIDENCE_CONFLICT,
                    None,
                )

            current = self._publication_leases_by_outbox.get(candidate.outbox_entry_id)
            if not self._publication_acquire_generation_matches(
                current=current,
                request=request,
            ):
                return WorkflowOutboxPublicationLeaseAcquireResult(
                    WorkflowOutboxPublicationLeaseAcquireStatus.CONTENDED,
                    current,
                )
            self._publication_leases_by_outbox[candidate.outbox_entry_id] = candidate
            self._publication_lease_acquire_requests[key] = (
                WorkflowOutboxPublicationLeaseAcquireIdempotencyRecord(
                    request_fingerprint=request.request_fingerprint,
                    lease=candidate,
                )
            )
            return WorkflowOutboxPublicationLeaseAcquireResult(
                WorkflowOutboxPublicationLeaseAcquireStatus.ACQUIRED,
                candidate,
            )

    async def heartbeat_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseMutationRequest
    ) -> WorkflowOutboxPublicationLeaseMutationResult:
        return await self._mutate_publication_lease(request)

    async def release_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseMutationRequest
    ) -> WorkflowOutboxPublicationLeaseMutationResult:
        return await self._mutate_publication_lease(request)

    async def get_dispatch_intent_staging_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowDispatchIntentStagingIdempotencyRecord | None:
        async with self._lock:
            return self._dispatch_intent_staging_requests.get(
                (scope, worker_subject_id, idempotency_key)
            )

    async def stage_dispatch_intent(
        self, request: WorkflowDispatchIntentStagingRequest
    ) -> WorkflowDispatchIntentStagingResult:
        async with self._lock:
            dispatch_intent = request.candidate
            outbox_entry = request.outbox_entry
            key = (dispatch_intent.scope, request.worker_subject_id, request.idempotency_key)
            prior = self._dispatch_intent_staging_requests.get(key)
            if prior is not None:
                status = (
                    WorkflowDispatchIntentStagingStatus.REPLAY
                    if prior.request_fingerprint == request.request_fingerprint
                    else WorkflowDispatchIntentStagingStatus.IDEMPOTENCY_CONFLICT
                )
                return WorkflowDispatchIntentStagingResult(
                    status, prior.dispatch_intent, prior.outbox_entry
                )

            plan = self._plans.get(dispatch_intent.plan_id)
            run = self._runs_by_plan.get(dispatch_intent.plan_id)
            lease = self._leases_by_plan.get(dispatch_intent.plan_id)
            step = (
                None
                if run is None
                else next(
                    (
                        item
                        for item in run.step_runs
                        if item.step_run_id == dispatch_intent.step_run_id
                    ),
                    None,
                )
            )
            attempt = self._attempts_by_step_run.get(dispatch_intent.step_run_id)
            if (
                plan is None
                or plan.state is not WorkflowPlanState.PLANNED
                or plan.canonical_digest != request.expected_plan_digest
                or request.expected_plan_digest != dispatch_intent.plan_digest
                or plan.scope != dispatch_intent.scope
                or plan.target_id != dispatch_intent.target_id
                or plan.target_type != dispatch_intent.target_type
                or run is None
                or run.state is not WorkflowExecutionRunState.CREATED
                or run.canonical_digest != request.expected_run_digest
                or request.expected_run_digest != dispatch_intent.run_digest
                or run.run_id != dispatch_intent.run_id
                or step is None
                or step.state is not WorkflowExecutionStepRunState.NOT_STARTED
                or step.canonical_digest != request.expected_step_run_digest
                or request.expected_step_run_digest != dispatch_intent.step_run_digest
                or step.step_id != dispatch_intent.step_id
                or attempt is None
                or attempt.state is not WorkflowExecutionAttemptState.CREATED
                or attempt.canonical_digest != request.expected_attempt_digest
                or request.expected_attempt_digest != dispatch_intent.attempt_digest
                or attempt.attempt_id != dispatch_intent.attempt_id
                or attempt.attempt_number != dispatch_intent.attempt_number
                or attempt.run_id != run.run_id
                or attempt.step_run_id != step.step_run_id
                or attempt.grants_execution_authority
                or lease is None
                or lease.lease_id != request.expected_lease_id
                or request.expected_lease_id != dispatch_intent.lease_id
                or lease.canonical_digest != request.expected_lease_digest
                or request.expected_lease_digest != dispatch_intent.lease_digest
                or lease.fencing_token != request.expected_fencing_token
                or request.expected_fencing_token != dispatch_intent.fencing_token
                or lease.worker_subject_id != request.worker_subject_id
                or request.worker_subject_id != dispatch_intent.worker_subject_id
                or run.lease_id != lease.lease_id
                or run.fencing_token != lease.fencing_token
                or attempt.lease_id != lease.lease_id
                or attempt.fencing_token != lease.fencing_token
                or lease.effective_state(requested_at=request.requested_at)
                is not WorkflowOrchestrationLeaseEffectiveState.ACTIVE
                or lease.grants_execution_authority
                or dispatch_intent.state is not WorkflowDispatchIntentState.STAGED
                or any(dispatch_intent.authority.canonical_value().values())
                or dispatch_intent.grants_dispatch_authority
                or dispatch_intent.grants_execution_authority
                or outbox_entry is None
                or outbox_entry.dispatch_intent_id != dispatch_intent.dispatch_intent_id
                or outbox_entry.dispatch_intent_digest != dispatch_intent.canonical_digest
                or outbox_entry.plan_id != dispatch_intent.plan_id
                or outbox_entry.plan_digest != dispatch_intent.plan_digest
                or outbox_entry.run_id != dispatch_intent.run_id
                or outbox_entry.run_digest != dispatch_intent.run_digest
                or outbox_entry.step_run_id != dispatch_intent.step_run_id
                or outbox_entry.step_run_digest != dispatch_intent.step_run_digest
                or outbox_entry.step_id != dispatch_intent.step_id
                or outbox_entry.attempt_id != dispatch_intent.attempt_id
                or outbox_entry.attempt_digest != dispatch_intent.attempt_digest
                or outbox_entry.attempt_number != dispatch_intent.attempt_number
                or outbox_entry.scope != dispatch_intent.scope
                or outbox_entry.target_id != dispatch_intent.target_id
                or outbox_entry.target_type != dispatch_intent.target_type
                or outbox_entry.lease_id != lease.lease_id
                or outbox_entry.lease_digest != lease.canonical_digest
                or outbox_entry.fencing_token != lease.fencing_token
                or outbox_entry.worker_subject_id != request.worker_subject_id
                or outbox_entry.admitted_at != dispatch_intent.staged_at
                or outbox_entry.state is not WorkflowDispatchOutboxState.PENDING_PUBLICATION
                or any(outbox_entry.authority.canonical_value().values())
                or outbox_entry.grants_publication_authority
                or outbox_entry.grants_delivery_authority
                or outbox_entry.grants_dispatch_authority
                or outbox_entry.grants_execution_authority
            ):
                return WorkflowDispatchIntentStagingResult(
                    WorkflowDispatchIntentStagingStatus.STATE_CONFLICT, None
                )
            current = self._dispatch_intents_by_attempt.get(attempt.attempt_id)
            current_outbox = self._dispatch_outbox_entries_by_intent.get(
                dispatch_intent.dispatch_intent_id
            )
            if current is not None or current_outbox is not None:
                return WorkflowDispatchIntentStagingResult(
                    WorkflowDispatchIntentStagingStatus.STATE_CONFLICT,
                    current,
                    current_outbox,
                )
            self._dispatch_intents_by_attempt[attempt.attempt_id] = dispatch_intent
            self._dispatch_outbox_entries_by_intent[dispatch_intent.dispatch_intent_id] = (
                outbox_entry
            )
            self._dispatch_intent_staging_requests[key] = (
                WorkflowDispatchIntentStagingIdempotencyRecord(
                    request_fingerprint=request.request_fingerprint,
                    dispatch_intent=dispatch_intent,
                    outbox_entry=outbox_entry,
                )
            )
            return WorkflowDispatchIntentStagingResult(
                WorkflowDispatchIntentStagingStatus.STAGED,
                dispatch_intent,
                outbox_entry,
            )

    async def acquire_lease(
        self, request: WorkflowLeaseAcquireRequest
    ) -> WorkflowLeaseAcquireResult:
        """Atomically checks the exact plan and replaces only an expired lease."""
        async with self._lock:
            candidate = request.candidate
            key = (candidate.scope, candidate.worker_subject_id, request.idempotency_key)
            prior = self._lease_acquire_requests.get(key)
            if prior is not None:
                status = (
                    WorkflowLeaseAcquireStatus.REPLAY
                    if prior.request_fingerprint == request.request_fingerprint
                    else WorkflowLeaseAcquireStatus.IDEMPOTENCY_CONFLICT
                )
                return WorkflowLeaseAcquireResult(status=status, lease=prior.lease)
            plan = self._plans.get(candidate.plan_id)
            if (
                plan is None
                or plan.state is not WorkflowPlanState.PLANNED
                or plan.canonical_digest != request.expected_plan_digest
                or plan.canonical_digest != candidate.plan_digest
                or plan.scope != candidate.scope
                or plan.target_id != candidate.target_id
                or plan.target_type != candidate.target_type
            ):
                return WorkflowLeaseAcquireResult(
                    status=WorkflowLeaseAcquireStatus.PLAN_CONFLICT, lease=None
                )
            current = self._leases_by_plan.get(candidate.plan_id)
            if current is None:
                if (
                    request.expected_current_lease_digest is not None
                    or request.expected_current_fencing_token is not None
                    or candidate.fencing_token != 1
                ):
                    return WorkflowLeaseAcquireResult(
                        status=WorkflowLeaseAcquireStatus.CONTENDED, lease=None
                    )
            else:
                if (
                    current.canonical_digest != request.expected_current_lease_digest
                    or current.fencing_token != request.expected_current_fencing_token
                    or current.effective_state(requested_at=request.requested_at)
                    is WorkflowOrchestrationLeaseEffectiveState.ACTIVE
                    or candidate.fencing_token != current.fencing_token + 1
                ):
                    return WorkflowLeaseAcquireResult(
                        status=WorkflowLeaseAcquireStatus.CONTENDED, lease=current
                    )
            self._leases_by_plan[candidate.plan_id] = candidate
            self._lease_acquire_requests[key] = WorkflowLeaseAcquireIdempotencyRecord(
                request_fingerprint=request.request_fingerprint,
                lease=candidate,
            )
            return WorkflowLeaseAcquireResult(
                status=WorkflowLeaseAcquireStatus.ACQUIRED, lease=candidate
            )

    async def heartbeat_lease(
        self, request: WorkflowLeaseMutationRequest
    ) -> WorkflowLeaseMutationResult:
        return await self._mutate_lease(request)

    async def release_lease(
        self, request: WorkflowLeaseMutationRequest
    ) -> WorkflowLeaseMutationResult:
        return await self._mutate_lease(request)

    async def _mutate_lease(
        self, request: WorkflowLeaseMutationRequest
    ) -> WorkflowLeaseMutationResult:
        async with self._lock:
            updated = request.updated_lease
            plan = self._plans.get(updated.plan_id)
            if (
                plan is None
                or plan.state is not WorkflowPlanState.PLANNED
                or plan.canonical_digest != request.expected_plan_digest
                or plan.canonical_digest != updated.plan_digest
            ):
                return WorkflowLeaseMutationResult(
                    status=WorkflowLeaseMutationStatus.PLAN_CONFLICT, lease=None
                )
            current = self._leases_by_plan.get(updated.plan_id)
            if current is None:
                return WorkflowLeaseMutationResult(
                    status=WorkflowLeaseMutationStatus.NOT_FOUND, lease=None
                )
            if (
                current.lease_id != request.expected_lease_id
                or current.canonical_digest != request.expected_lease_digest
                or current.fencing_token != request.expected_fencing_token
                or current.worker_subject_id != request.worker_subject_id
                or current.effective_state(requested_at=request.requested_at)
                is not WorkflowOrchestrationLeaseEffectiveState.ACTIVE
                or updated.lease_id != current.lease_id
                or updated.plan_id != current.plan_id
                or updated.plan_digest != current.plan_digest
                or updated.scope != current.scope
                or updated.target_id != current.target_id
                or updated.target_type != current.target_type
                or updated.worker_subject_id != current.worker_subject_id
                or updated.fencing_token != current.fencing_token
            ):
                return WorkflowLeaseMutationResult(
                    status=WorkflowLeaseMutationStatus.LEASE_CONFLICT, lease=current
                )
            self._leases_by_plan[updated.plan_id] = updated
            return WorkflowLeaseMutationResult(
                status=WorkflowLeaseMutationStatus.UPDATED, lease=updated
            )

    async def _mutate_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseMutationRequest
    ) -> WorkflowOutboxPublicationLeaseMutationResult:
        async with self._lock:
            updated = request.updated_lease
            outbox = next(
                (
                    entry
                    for entry in self._dispatch_outbox_entries_by_intent.values()
                    if entry.outbox_entry_id == updated.outbox_entry_id
                ),
                None,
            )
            plan = self._plans.get(updated.plan_id)
            orchestration_lease = self._leases_by_plan.get(updated.plan_id)
            if not self._publication_mutation_evidence_matches(
                outbox=outbox,
                plan=plan,
                orchestration_lease=orchestration_lease,
                request=request,
            ):
                return WorkflowOutboxPublicationLeaseMutationResult(
                    WorkflowOutboxPublicationLeaseMutationStatus.EVIDENCE_CONFLICT,
                    None,
                )
            current = self._publication_leases_by_outbox.get(updated.outbox_entry_id)
            if current is None:
                return WorkflowOutboxPublicationLeaseMutationResult(
                    WorkflowOutboxPublicationLeaseMutationStatus.NOT_FOUND,
                    None,
                )
            if (
                current.publication_lease_id != request.expected_publication_lease_id
                or current.canonical_digest != request.expected_publication_lease_digest
                or current.publication_fencing_token != request.expected_publication_fencing_token
                or current.publisher_subject_id != request.publisher_subject_id
                or current.effective_state(requested_at=request.requested_at)
                is not WorkflowOutboxPublicationLeaseEffectiveState.ACTIVE
                or not self._same_publication_lease_generation(current, updated)
            ):
                return WorkflowOutboxPublicationLeaseMutationResult(
                    WorkflowOutboxPublicationLeaseMutationStatus.LEASE_CONFLICT,
                    current,
                )
            self._publication_leases_by_outbox[updated.outbox_entry_id] = updated
            return WorkflowOutboxPublicationLeaseMutationResult(
                WorkflowOutboxPublicationLeaseMutationStatus.UPDATED,
                updated,
            )

    @staticmethod
    def _publication_evidence_matches(
        *,
        outbox: WorkflowDispatchOutboxEntry | None,
        plan: WorkflowRunPlan | None,
        orchestration_lease: WorkflowOrchestrationLease | None,
        request: WorkflowOutboxPublicationLeaseAcquireRequest,
    ) -> bool:
        candidate = request.candidate
        return bool(
            outbox is not None
            and outbox.state is WorkflowDispatchOutboxState.PENDING_PUBLICATION
            and outbox.canonical_digest
            == request.expected_outbox_entry_digest
            == candidate.outbox_entry_digest
            and outbox.outbox_entry_id == candidate.outbox_entry_id
            and outbox.dispatch_intent_id == candidate.dispatch_intent_id
            and outbox.dispatch_intent_digest == candidate.dispatch_intent_digest
            and outbox.plan_id == candidate.plan_id
            and outbox.plan_digest == candidate.plan_digest
            and outbox.run_id == candidate.run_id
            and outbox.run_digest == candidate.run_digest
            and outbox.step_run_id == candidate.step_run_id
            and outbox.step_run_digest == candidate.step_run_digest
            and outbox.step_id == candidate.step_id
            and outbox.attempt_id == candidate.attempt_id
            and outbox.attempt_digest == candidate.attempt_digest
            and outbox.attempt_number == candidate.attempt_number
            and outbox.scope == candidate.scope
            and outbox.target_id == candidate.target_id
            and outbox.target_type == candidate.target_type
            and not any(outbox.authority.canonical_value().values())
            and not outbox.grants_publication_authority
            and plan is not None
            and plan.state is WorkflowPlanState.PLANNED
            and plan.canonical_digest == candidate.plan_digest
            and plan.scope == candidate.scope
            and plan.target_id == candidate.target_id
            and plan.target_type == candidate.target_type
            and orchestration_lease is not None
            and orchestration_lease.lease_id
            == request.expected_orchestration_lease_id
            == candidate.orchestration_lease_id
            == outbox.lease_id
            and orchestration_lease.canonical_digest
            == request.expected_orchestration_lease_digest
            == candidate.orchestration_lease_digest
            == outbox.lease_digest
            and orchestration_lease.fencing_token
            == request.expected_orchestration_fencing_token
            == candidate.orchestration_fencing_token
            == outbox.fencing_token
            and orchestration_lease.plan_id == candidate.plan_id
            and orchestration_lease.plan_digest == candidate.plan_digest
            and orchestration_lease.scope == candidate.scope
            and orchestration_lease.target_id == candidate.target_id
            and orchestration_lease.target_type == candidate.target_type
            and orchestration_lease.worker_subject_id == outbox.worker_subject_id
            and orchestration_lease.effective_state(requested_at=request.requested_at)
            is WorkflowOrchestrationLeaseEffectiveState.ACTIVE
            and not any(candidate.authority.canonical_value().values())
            and not candidate.grants_publication_authority
            and not candidate.grants_delivery_authority
            and not candidate.grants_dispatch_authority
            and not candidate.grants_execution_authority
        )

    @staticmethod
    def _dispatch_event_evidence_matches(
        *,
        outbox: WorkflowDispatchOutboxEntry | None,
        plan: WorkflowRunPlan | None,
        orchestration_lease: WorkflowOrchestrationLease | None,
        publication_lease: WorkflowOutboxPublicationLease | None,
        request: WorkflowDispatchEventEnvelopePrepareRequest,
    ) -> bool:
        candidate = request.candidate
        payload = candidate.payload
        return bool(
            outbox is not None
            and outbox.state is WorkflowDispatchOutboxState.PENDING_PUBLICATION
            and outbox.canonical_digest
            == request.expected_outbox_entry_digest
            == payload.outbox_entry_digest
            and outbox.outbox_entry_id == payload.outbox_entry_id
            and outbox.dispatch_intent_id == payload.dispatch_intent_id
            and outbox.dispatch_intent_digest == payload.dispatch_intent_digest
            and outbox.plan_id == payload.plan_id
            and outbox.plan_digest == request.expected_plan_digest == payload.plan_digest
            and outbox.run_id == payload.run_id
            and outbox.run_digest == payload.run_digest
            and outbox.step_run_id == payload.step_run_id
            and outbox.step_run_digest == payload.step_run_digest
            and outbox.step_id == payload.step_id
            and outbox.attempt_id == payload.attempt_id
            and outbox.attempt_digest == payload.attempt_digest
            and outbox.attempt_number == payload.attempt_number
            and outbox.scope == payload.scope
            and outbox.target_id == payload.target_id
            and outbox.target_type == payload.target_type
            and not any(outbox.authority.canonical_value().values())
            and not outbox.grants_publication_authority
            and not outbox.grants_delivery_authority
            and not outbox.grants_dispatch_authority
            and not outbox.grants_execution_authority
            and plan is not None
            and plan.state is WorkflowPlanState.PLANNED
            and plan.canonical_digest == request.expected_plan_digest
            and plan.scope == payload.scope
            and plan.target_id == payload.target_id
            and plan.target_type == payload.target_type
            and orchestration_lease is not None
            and orchestration_lease.lease_id
            == request.expected_orchestration_lease_id
            == candidate.orchestration_lease_id
            == outbox.lease_id
            and orchestration_lease.canonical_digest
            == request.expected_orchestration_lease_digest
            == candidate.orchestration_lease_digest
            == outbox.lease_digest
            and orchestration_lease.fencing_token
            == request.expected_orchestration_fencing_token
            == candidate.orchestration_fencing_token
            == outbox.fencing_token
            and orchestration_lease.scope == payload.scope
            and orchestration_lease.target_id == payload.target_id
            and orchestration_lease.target_type == payload.target_type
            and orchestration_lease.effective_state(requested_at=request.requested_at)
            is WorkflowOrchestrationLeaseEffectiveState.ACTIVE
            and publication_lease is not None
            and publication_lease.publication_lease_id
            == request.expected_publication_lease_id
            == candidate.publication_lease_id
            and publication_lease.canonical_digest
            == request.expected_publication_lease_digest
            == candidate.publication_lease_digest
            and publication_lease.publication_fencing_token
            == request.expected_publication_fencing_token
            == candidate.publication_fencing_token
            and publication_lease.outbox_entry_id == outbox.outbox_entry_id
            and publication_lease.outbox_entry_digest == outbox.canonical_digest
            and publication_lease.orchestration_lease_id == orchestration_lease.lease_id
            and publication_lease.orchestration_lease_digest == orchestration_lease.canonical_digest
            and publication_lease.orchestration_fencing_token == orchestration_lease.fencing_token
            and publication_lease.publisher_subject_id
            == request.publisher_subject_id
            == candidate.publisher_subject_id
            and publication_lease.effective_state(requested_at=request.requested_at)
            is WorkflowOutboxPublicationLeaseEffectiveState.ACTIVE
            and not any(publication_lease.authority.canonical_value().values())
            and not publication_lease.grants_publication_authority
            and not publication_lease.grants_delivery_authority
            and not publication_lease.grants_dispatch_authority
            and not publication_lease.grants_execution_authority
            and not candidate.extensions
            and not any(candidate.authority.canonical_value().values())
            and not candidate.grants_publication_authority
            and not candidate.grants_delivery_authority
            and not candidate.grants_dispatch_authority
            and not candidate.grants_execution_authority
        )

    @staticmethod
    def _event_transport_admission_evidence_matches(
        *,
        outbox: WorkflowDispatchOutboxEntry | None,
        plan: WorkflowRunPlan | None,
        orchestration_lease: WorkflowOrchestrationLease | None,
        publication_lease: WorkflowOutboxPublicationLease | None,
        envelope: WorkflowDispatchEventEnvelope | None,
        request: WorkflowEventTransportAdmissionRequest,
    ) -> bool:
        candidate = request.candidate
        return bool(
            outbox is not None
            and outbox.state is WorkflowDispatchOutboxState.PENDING_PUBLICATION
            and outbox.outbox_entry_id == candidate.outbox_entry_id
            and outbox.canonical_digest
            == request.expected_outbox_entry_digest
            == candidate.outbox_entry_digest
            and outbox.dispatch_intent_id == candidate.dispatch_intent_id
            and outbox.dispatch_intent_digest == candidate.dispatch_intent_digest
            and outbox.plan_id == candidate.plan_id
            and outbox.plan_digest == request.expected_plan_digest == candidate.plan_digest
            and outbox.run_id == candidate.run_id
            and outbox.run_digest == candidate.run_digest
            and outbox.step_run_id == candidate.step_run_id
            and outbox.step_run_digest == candidate.step_run_digest
            and outbox.step_id == candidate.step_id
            and outbox.attempt_id == candidate.attempt_id
            and outbox.attempt_digest == candidate.attempt_digest
            and outbox.attempt_number == candidate.attempt_number
            and outbox.scope == candidate.scope
            and outbox.target_id == candidate.target_id
            and outbox.target_type == candidate.target_type
            and not any(outbox.authority.canonical_value().values())
            and plan is not None
            and plan.state is WorkflowPlanState.PLANNED
            and plan.canonical_digest == request.expected_plan_digest
            and plan.scope == candidate.scope
            and plan.target_id == candidate.target_id
            and plan.target_type == candidate.target_type
            and orchestration_lease is not None
            and orchestration_lease.lease_id
            == request.expected_orchestration_lease_id
            == candidate.orchestration_lease_id
            == outbox.lease_id
            and orchestration_lease.canonical_digest
            == request.expected_orchestration_lease_digest
            == candidate.orchestration_lease_digest
            == outbox.lease_digest
            and orchestration_lease.fencing_token
            == request.expected_orchestration_fencing_token
            == candidate.orchestration_fencing_token
            == outbox.fencing_token
            and orchestration_lease.scope == candidate.scope
            and orchestration_lease.target_id == candidate.target_id
            and orchestration_lease.target_type == candidate.target_type
            and orchestration_lease.effective_state(requested_at=request.requested_at)
            is WorkflowOrchestrationLeaseEffectiveState.ACTIVE
            and publication_lease is not None
            and publication_lease.publication_lease_id
            == request.expected_publication_lease_id
            == candidate.publication_lease_id
            and publication_lease.canonical_digest
            == request.expected_publication_lease_digest
            == candidate.publication_lease_digest
            and publication_lease.publication_fencing_token
            == request.expected_publication_fencing_token
            == candidate.publication_fencing_token
            and publication_lease.outbox_entry_id == outbox.outbox_entry_id
            and publication_lease.outbox_entry_digest == outbox.canonical_digest
            and publication_lease.orchestration_lease_id == orchestration_lease.lease_id
            and publication_lease.orchestration_lease_digest == orchestration_lease.canonical_digest
            and publication_lease.orchestration_fencing_token == orchestration_lease.fencing_token
            and publication_lease.publisher_subject_id
            == request.publisher_subject_id
            == candidate.publisher_subject_id
            and publication_lease.effective_state(requested_at=request.requested_at)
            is WorkflowOutboxPublicationLeaseEffectiveState.ACTIVE
            and not any(publication_lease.authority.canonical_value().values())
            and envelope is not None
            and envelope.state is WorkflowDispatchEventEnvelopeState.PREPARED
            and envelope.event_id == request.expected_event_id == candidate.event_id
            and envelope.canonical_digest == request.expected_event_digest == candidate.event_digest
            and envelope.event_type == candidate.event_type
            and envelope.event_version == candidate.event_version
            and envelope.schema_uri == candidate.schema_uri
            and envelope.data_classification == candidate.data_classification
            and envelope.payload.outbox_entry_id == outbox.outbox_entry_id
            and envelope.payload.outbox_entry_digest == outbox.canonical_digest
            and envelope.payload.dispatch_intent_id == candidate.dispatch_intent_id
            and envelope.payload.dispatch_intent_digest == candidate.dispatch_intent_digest
            and envelope.payload.plan_id == candidate.plan_id
            and envelope.payload.plan_digest == candidate.plan_digest
            and envelope.payload.run_id == candidate.run_id
            and envelope.payload.run_digest == candidate.run_digest
            and envelope.payload.step_run_id == candidate.step_run_id
            and envelope.payload.step_run_digest == candidate.step_run_digest
            and envelope.payload.step_id == candidate.step_id
            and envelope.payload.attempt_id == candidate.attempt_id
            and envelope.payload.attempt_digest == candidate.attempt_digest
            and envelope.payload.attempt_number == candidate.attempt_number
            and envelope.payload.scope == candidate.scope
            and envelope.payload.target_id == candidate.target_id
            and envelope.payload.target_type == candidate.target_type
            and envelope.orchestration_lease_id == orchestration_lease.lease_id
            and envelope.orchestration_lease_digest == orchestration_lease.canonical_digest
            and envelope.orchestration_fencing_token == orchestration_lease.fencing_token
            and envelope.publication_lease_id == publication_lease.publication_lease_id
            and envelope.publication_lease_digest == publication_lease.canonical_digest
            and envelope.publication_fencing_token == publication_lease.publication_fencing_token
            and envelope.publisher_subject_id == publication_lease.publisher_subject_id
            and not envelope.extensions
            and not any(envelope.authority.canonical_value().values())
            and candidate.policy_digest == request.expected_policy_digest
            and candidate.representation_name == "canonical-json"
            and candidate.encoding == "utf-8"
            and candidate.canonical_byte_count
            == canonical_json_byte_count(envelope.canonical_value())
            and candidate.canonical_byte_count <= candidate.maximum_canonical_byte_count
            and candidate.state is WorkflowEventTransportAdmissionState.ADMITTED
            and not any(candidate.authority.canonical_value().values())
            and not candidate.grants_publication_authority
            and not candidate.grants_delivery_authority
            and not candidate.grants_dispatch_authority
            and not candidate.grants_execution_authority
        )

    @staticmethod
    def _event_byte_artifact_evidence_matches(
        *,
        outbox: WorkflowDispatchOutboxEntry | None,
        plan: WorkflowRunPlan | None,
        orchestration_lease: WorkflowOrchestrationLease | None,
        publication_lease: WorkflowOutboxPublicationLease | None,
        envelope: WorkflowDispatchEventEnvelope | None,
        admission: WorkflowEventTransportAdmission | None,
        request: WorkflowEventByteArtifactRequest,
    ) -> bool:
        candidate = request.candidate
        return bool(
            plan is not None
            and plan.state is WorkflowPlanState.PLANNED
            and plan.canonical_digest == request.expected_plan_digest == candidate.plan_digest
            and plan.plan_id == candidate.plan_id
            and plan.scope == candidate.scope
            and plan.target_id == candidate.target_id
            and plan.target_type == candidate.target_type
            and outbox is not None
            and outbox.state is WorkflowDispatchOutboxState.PENDING_PUBLICATION
            and outbox.outbox_entry_id == candidate.outbox_entry_id
            and outbox.canonical_digest
            == request.expected_outbox_entry_digest
            == candidate.outbox_entry_digest
            and outbox.dispatch_intent_id == candidate.dispatch_intent_id
            and outbox.dispatch_intent_digest == candidate.dispatch_intent_digest
            and outbox.plan_id == candidate.plan_id
            and outbox.plan_digest == candidate.plan_digest
            and outbox.run_id == candidate.run_id
            and outbox.run_digest == candidate.run_digest
            and outbox.step_run_id == candidate.step_run_id
            and outbox.step_run_digest == candidate.step_run_digest
            and outbox.step_id == candidate.step_id
            and outbox.attempt_id == candidate.attempt_id
            and outbox.attempt_digest == candidate.attempt_digest
            and outbox.attempt_number == candidate.attempt_number == 1
            and outbox.scope == candidate.scope
            and outbox.target_id == candidate.target_id
            and outbox.target_type == candidate.target_type
            and not any(outbox.authority.canonical_value().values())
            and orchestration_lease is not None
            and orchestration_lease.lease_id
            == request.expected_orchestration_lease_id
            == candidate.orchestration_lease_id
            == outbox.lease_id
            and orchestration_lease.canonical_digest
            == request.expected_orchestration_lease_digest
            == candidate.orchestration_lease_digest
            == outbox.lease_digest
            and orchestration_lease.fencing_token
            == request.expected_orchestration_fencing_token
            == candidate.orchestration_fencing_token
            == outbox.fencing_token
            and orchestration_lease.plan_id == candidate.plan_id
            and orchestration_lease.plan_digest == candidate.plan_digest
            and orchestration_lease.scope == candidate.scope
            and orchestration_lease.target_id == candidate.target_id
            and orchestration_lease.target_type == candidate.target_type
            and orchestration_lease.effective_state(requested_at=request.requested_at)
            is WorkflowOrchestrationLeaseEffectiveState.ACTIVE
            and publication_lease is not None
            and publication_lease.publication_lease_id
            == request.expected_publication_lease_id
            == candidate.publication_lease_id
            and publication_lease.canonical_digest
            == request.expected_publication_lease_digest
            == candidate.publication_lease_digest
            and publication_lease.publication_fencing_token
            == request.expected_publication_fencing_token
            == candidate.publication_fencing_token
            and publication_lease.outbox_entry_id == candidate.outbox_entry_id
            and publication_lease.outbox_entry_digest == candidate.outbox_entry_digest
            and publication_lease.orchestration_lease_id == candidate.orchestration_lease_id
            and publication_lease.orchestration_lease_digest == candidate.orchestration_lease_digest
            and publication_lease.orchestration_fencing_token
            == candidate.orchestration_fencing_token
            and publication_lease.publisher_subject_id
            == request.publisher_subject_id
            == candidate.publisher_subject_id
            and publication_lease.effective_state(requested_at=request.requested_at)
            is WorkflowOutboxPublicationLeaseEffectiveState.ACTIVE
            and not any(publication_lease.authority.canonical_value().values())
            and envelope is not None
            and envelope.state is WorkflowDispatchEventEnvelopeState.PREPARED
            and envelope.event_id == request.expected_event_id == candidate.event_id
            and envelope.canonical_digest == request.expected_event_digest == candidate.event_digest
            and envelope.event_type == candidate.event_type
            and envelope.event_version == candidate.event_version
            and envelope.schema_uri == candidate.schema_uri
            and envelope.data_classification == candidate.data_classification
            and envelope.payload.outbox_entry_id == candidate.outbox_entry_id
            and envelope.payload.plan_id == candidate.plan_id
            and envelope.orchestration_lease_id == candidate.orchestration_lease_id
            and envelope.orchestration_lease_digest == candidate.orchestration_lease_digest
            and envelope.orchestration_fencing_token == candidate.orchestration_fencing_token
            and envelope.publication_lease_id == candidate.publication_lease_id
            and envelope.publication_lease_digest == candidate.publication_lease_digest
            and envelope.publication_fencing_token == candidate.publication_fencing_token
            and envelope.publisher_subject_id == candidate.publisher_subject_id
            and not any(envelope.authority.canonical_value().values())
            and candidate.canonical_bytes == canonical_json_bytes(envelope.canonical_value())
            and admission is not None
            and admission.state is WorkflowEventTransportAdmissionState.ADMITTED
            and admission.admission_id == request.expected_admission_id == candidate.admission_id
            and admission.canonical_digest
            == request.expected_admission_digest
            == candidate.admission_digest
            and admission.policy_digest == request.expected_policy_digest == candidate.policy_digest
            and admission.policy_id == candidate.policy_id
            and admission.policy_version == candidate.policy_version
            and admission.event_id == candidate.event_id
            and admission.event_digest == candidate.event_digest
            and admission.outbox_entry_id == candidate.outbox_entry_id
            and admission.outbox_entry_digest == candidate.outbox_entry_digest
            and admission.dispatch_intent_id == candidate.dispatch_intent_id
            and admission.dispatch_intent_digest == candidate.dispatch_intent_digest
            and admission.plan_id == candidate.plan_id
            and admission.plan_digest == candidate.plan_digest
            and admission.run_id == candidate.run_id
            and admission.run_digest == candidate.run_digest
            and admission.step_run_id == candidate.step_run_id
            and admission.step_run_digest == candidate.step_run_digest
            and admission.step_id == candidate.step_id
            and admission.attempt_id == candidate.attempt_id
            and admission.attempt_digest == candidate.attempt_digest
            and admission.attempt_number == candidate.attempt_number
            and admission.scope == candidate.scope
            and admission.target_id == candidate.target_id
            and admission.target_type == candidate.target_type
            and admission.orchestration_lease_id == candidate.orchestration_lease_id
            and admission.orchestration_lease_digest == candidate.orchestration_lease_digest
            and admission.orchestration_fencing_token == candidate.orchestration_fencing_token
            and admission.publication_lease_id == candidate.publication_lease_id
            and admission.publication_lease_digest == candidate.publication_lease_digest
            and admission.publication_fencing_token == candidate.publication_fencing_token
            and admission.publisher_subject_id == candidate.publisher_subject_id
            and admission.representation_name == candidate.representation_name
            and admission.encoding == candidate.encoding
            and admission.canonical_byte_count == candidate.canonical_byte_count
            and admission.maximum_canonical_byte_count == candidate.maximum_canonical_byte_count
            and not any(admission.authority.canonical_value().values())
            and candidate.state is WorkflowEventByteArtifactState.MATERIALIZED
            and not any(candidate.authority.canonical_value().values())
            and not candidate.grants_publication_authority
            and not candidate.grants_delivery_authority
            and not candidate.grants_dispatch_authority
            and not candidate.grants_execution_authority
        )

    @staticmethod
    def _event_logical_channel_binding_evidence_matches(
        *,
        outbox: WorkflowDispatchOutboxEntry | None,
        plan: WorkflowRunPlan | None,
        orchestration_lease: WorkflowOrchestrationLease | None,
        publication_lease: WorkflowOutboxPublicationLease | None,
        admission: WorkflowEventTransportAdmission | None,
        artifact: WorkflowEventByteArtifact | None,
        request: WorkflowEventLogicalChannelBindingRequest,
    ) -> bool:
        candidate = request.candidate
        return bool(
            plan is not None
            and plan.state is WorkflowPlanState.PLANNED
            and plan.plan_id == candidate.plan_id
            and plan.canonical_digest == request.expected_plan_digest == candidate.plan_digest
            and plan.scope == candidate.scope
            and plan.target_id == candidate.target_id
            and plan.target_type == candidate.target_type
            and outbox is not None
            and outbox.state is WorkflowDispatchOutboxState.PENDING_PUBLICATION
            and outbox.outbox_entry_id == candidate.outbox_entry_id
            and outbox.canonical_digest
            == request.expected_outbox_entry_digest
            == candidate.outbox_entry_digest
            and outbox.dispatch_intent_id == candidate.dispatch_intent_id
            and outbox.dispatch_intent_digest == candidate.dispatch_intent_digest
            and outbox.plan_id == candidate.plan_id
            and outbox.plan_digest == candidate.plan_digest
            and outbox.run_id == candidate.run_id
            and outbox.run_digest == candidate.run_digest
            and outbox.step_run_id == candidate.step_run_id
            and outbox.step_run_digest == candidate.step_run_digest
            and outbox.step_id == candidate.step_id
            and outbox.attempt_id == candidate.attempt_id
            and outbox.attempt_digest == candidate.attempt_digest
            and outbox.attempt_number == candidate.attempt_number == 1
            and outbox.scope == candidate.scope
            and outbox.target_id == candidate.target_id
            and outbox.target_type == candidate.target_type
            and not any(outbox.authority.canonical_value().values())
            and orchestration_lease is not None
            and orchestration_lease.lease_id
            == request.expected_orchestration_lease_id
            == candidate.orchestration_lease_id
            == outbox.lease_id
            and orchestration_lease.canonical_digest
            == request.expected_orchestration_lease_digest
            == candidate.orchestration_lease_digest
            == outbox.lease_digest
            and orchestration_lease.fencing_token
            == request.expected_orchestration_fencing_token
            == candidate.orchestration_fencing_token
            == outbox.fencing_token
            and orchestration_lease.effective_state(requested_at=request.requested_at)
            is WorkflowOrchestrationLeaseEffectiveState.ACTIVE
            and publication_lease is not None
            and publication_lease.publication_lease_id
            == request.expected_publication_lease_id
            == candidate.publication_lease_id
            and publication_lease.canonical_digest
            == request.expected_publication_lease_digest
            == candidate.publication_lease_digest
            and publication_lease.publication_fencing_token
            == request.expected_publication_fencing_token
            == candidate.publication_fencing_token
            and publication_lease.outbox_entry_id == candidate.outbox_entry_id
            and publication_lease.outbox_entry_digest == candidate.outbox_entry_digest
            and publication_lease.publisher_subject_id
            == request.publisher_subject_id
            == candidate.publisher_subject_id
            and publication_lease.effective_state(requested_at=request.requested_at)
            is WorkflowOutboxPublicationLeaseEffectiveState.ACTIVE
            and not any(publication_lease.authority.canonical_value().values())
            and admission is not None
            and admission.state is WorkflowEventTransportAdmissionState.ADMITTED
            and admission.admission_id == request.expected_admission_id == candidate.admission_id
            and admission.canonical_digest
            == request.expected_admission_digest
            == candidate.admission_digest
            and admission.event_id == request.expected_event_id == candidate.event_id
            and admission.event_digest == request.expected_event_digest == candidate.event_digest
            and admission.outbox_entry_id == candidate.outbox_entry_id
            and admission.outbox_entry_digest == candidate.outbox_entry_digest
            and admission.publisher_subject_id == candidate.publisher_subject_id
            and not any(admission.authority.canonical_value().values())
            and artifact is not None
            and artifact.state is WorkflowEventByteArtifactState.MATERIALIZED
            and artifact.artifact_id == request.expected_artifact_id == candidate.artifact_id
            and artifact.canonical_digest
            == request.expected_artifact_digest
            == candidate.artifact_digest
            and artifact.content_sha256
            == request.expected_content_sha256
            == candidate.content_sha256
            and artifact.canonical_byte_count
            == request.expected_canonical_byte_count
            == candidate.canonical_byte_count
            and artifact.admission_id == candidate.admission_id
            and artifact.admission_digest == candidate.admission_digest
            and artifact.event_id == candidate.event_id
            and artifact.event_digest == candidate.event_digest
            and artifact.outbox_entry_id == candidate.outbox_entry_id
            and artifact.outbox_entry_digest == candidate.outbox_entry_digest
            and artifact.dispatch_intent_id == candidate.dispatch_intent_id
            and artifact.dispatch_intent_digest == candidate.dispatch_intent_digest
            and artifact.plan_id == candidate.plan_id
            and artifact.plan_digest == candidate.plan_digest
            and artifact.run_id == candidate.run_id == candidate.ordering_key_value
            and artifact.run_digest == candidate.run_digest
            and artifact.step_run_id == candidate.step_run_id
            and artifact.step_run_digest == candidate.step_run_digest
            and artifact.step_id == candidate.step_id
            and artifact.attempt_id == candidate.attempt_id
            and artifact.attempt_digest == candidate.attempt_digest
            and artifact.attempt_number == candidate.attempt_number
            and artifact.scope == candidate.scope
            and artifact.target_id == candidate.target_id
            and artifact.target_type == candidate.target_type
            and artifact.orchestration_lease_id == candidate.orchestration_lease_id
            and artifact.orchestration_lease_digest == candidate.orchestration_lease_digest
            and artifact.orchestration_fencing_token == candidate.orchestration_fencing_token
            and artifact.publication_lease_id == candidate.publication_lease_id
            and artifact.publication_lease_digest == candidate.publication_lease_digest
            and artifact.publication_fencing_token == candidate.publication_fencing_token
            and artifact.publisher_subject_id == candidate.publisher_subject_id
            and candidate.policy_digest == request.expected_policy_digest
            and candidate.state is WorkflowEventLogicalChannelBindingState.BOUND
            and not any(candidate.authority.canonical_value().values())
            and not candidate.grants_publication_authority
            and not candidate.grants_delivery_authority
            and not candidate.grants_dispatch_authority
            and not candidate.grants_execution_authority
        )

    @staticmethod
    def _transport_profile_snapshot_evidence_matches(
        request: WorkflowTransportProfileSnapshotRequest,
    ) -> bool:
        candidate = request.candidate
        return bool(
            candidate.transport_profile_id == request.expected_source_profile_id
            and candidate.transport_profile_revision == request.expected_source_profile_revision
            and candidate.source_profile_digest == request.expected_source_profile_digest
            and candidate.scope == request.scope
            and candidate.snapshotter_subject_id == request.snapshotter_subject_id
            and candidate.captured_at == request.requested_at
            and candidate.state is EventPhysicalTransportProfileSnapshotState.SNAPSHOTTED
            and not any(candidate.authority.canonical_value().values())
            and not candidate.grants_route_selection_authority
            and not candidate.grants_publication_authority
            and not candidate.grants_delivery_authority
            and not candidate.grants_dispatch_authority
            and not candidate.grants_execution_authority
        )

    @staticmethod
    def _transport_route_snapshot_evidence_matches(
        request: WorkflowTransportRouteSnapshotRequest,
    ) -> bool:
        candidate = request.candidate
        return bool(
            candidate.route_id == request.expected_source_route_id
            and candidate.route_revision == request.expected_source_route_revision
            and candidate.source_route_digest == request.expected_source_route_digest
            and candidate.scope == request.scope
            and candidate.snapshotter_subject_id == request.snapshotter_subject_id
            and candidate.captured_at == request.requested_at
            and candidate.state is EventPhysicalTransportRouteSnapshotState.SNAPSHOTTED
            and not any(candidate.authority.canonical_value().values())
        )

    @staticmethod
    def _credential_assignment_snapshot_evidence_matches(
        *,
        request: WorkflowTransportCredentialAssignmentSnapshotRequest,
        source: DeploymentPhysicalTransportCredentialAssignment | None,
        route: EventPhysicalTransportRouteSnapshot | None,
        captured_at: datetime,
    ) -> bool:
        if source is None or route is None:
            return False
        candidate = request.candidate
        return bool(
            candidate.assignment_id == request.expected_source_assignment_id
            and candidate.assignment_revision == request.expected_source_assignment_revision
            and candidate.source_assignment_digest
            == request.expected_source_assignment_digest
            == source.canonical_digest
            and candidate.scope == request.scope == source.scope == route.scope
            and candidate.snapshotter_subject_id == request.snapshotter_subject_id
            and candidate.captured_at == request.requested_at
            and source.active
            and not source.revoked
            and source.activated_at <= captured_at < source.expires_at
            and candidate.activated_at == source.activated_at
            and candidate.expires_at == source.expires_at
            and candidate.source_non_revoked
            and candidate.route_snapshot_id == route.snapshot_id
            and candidate.route_id == source.route_id == route.route_id
            and candidate.route_revision == source.route_revision == route.route_revision
            and candidate.source_route_digest
            == source.source_route_digest
            == route.source_route_digest
            and candidate.credential_requirement_profile_id
            == source.credential_requirement_profile_id
            == route.credential_requirement_profile_id
            and candidate.credential_requirement_profile_version
            == source.credential_requirement_profile_version
            == route.credential_requirement_profile_version
            and candidate.credential_requirement_profile_digest
            == source.credential_requirement_profile_digest
            == route.credential_requirement_profile_digest
            and candidate.credential_profile_id == source.credential_profile_id
            and candidate.credential_profile_version == source.credential_profile_version
            and candidate.credential_profile_digest == source.credential_profile_digest
            and candidate.authentication_mechanism_class
            == source.authentication_mechanism_class
            == route.authentication_mechanism_class
            and candidate.principal_class == source.principal_class == route.principal_class
            and candidate.privilege_class == source.privilege_class == "read-only"
            and candidate.target_scope_commitment == source.target_scope_commitment
            and candidate.credential_generation == source.credential_generation
            and candidate.rotation_epoch == source.rotation_epoch
            and candidate.broker_policy_id == source.broker_policy_id
            and candidate.broker_policy_version == source.broker_policy_version
            and candidate.broker_policy_digest == source.broker_policy_digest
            and not any(candidate.authority.canonical_value().values())
        )

    @staticmethod
    def _transport_compatibility_admission_evidence_matches(
        *,
        binding: WorkflowEventLogicalChannelBinding | None,
        profile: EventPhysicalTransportProfileSnapshot | None,
        request: WorkflowEventTransportCompatibilityAdmissionRequest,
    ) -> bool:
        if binding is None or profile is None:
            return False
        candidate = request.candidate
        event_contract = f"{binding.event_type}|{binding.event_version}|{binding.schema_uri}"
        return bool(
            binding.binding_id
            == request.expected_logical_channel_binding_id
            == candidate.logical_channel_binding_id
            and binding.canonical_digest
            == request.expected_logical_channel_binding_digest
            == candidate.logical_channel_binding_digest
            and binding.state is WorkflowEventLogicalChannelBindingState.BOUND
            and not any(binding.authority.canonical_value().values())
            and profile.snapshot_id
            == request.expected_transport_profile_snapshot_id
            == candidate.transport_profile_snapshot_id
            and profile.canonical_digest
            == request.expected_transport_profile_snapshot_digest
            == candidate.transport_profile_snapshot_digest
            and profile.state is EventPhysicalTransportProfileSnapshotState.SNAPSHOTTED
            and not any(profile.authority.canonical_value().values())
            and binding.scope == profile.scope == candidate.scope
            and profile.transport_profile_id == candidate.transport_profile_id
            and profile.transport_profile_revision == candidate.transport_profile_revision
            and candidate.policy_digest == request.expected_policy_digest
            and binding.event_type == candidate.event_type
            and binding.event_version == candidate.event_version
            and binding.schema_uri == candidate.schema_uri
            and binding.data_classification == candidate.data_classification
            and binding.representation_name == candidate.representation_name
            and binding.encoding == candidate.encoding
            and binding.delivery_semantics == candidate.delivery_semantics
            and binding.durability_required == candidate.durability_required
            and binding.ordering_key_kind == candidate.ordering_key_kind
            and binding.retention_class == candidate.retention_class
            and binding.maximum_canonical_byte_count == candidate.logical_maximum_byte_count
            and binding.canonical_byte_count == candidate.artifact_byte_count
            and profile.maximum_message_byte_count == candidate.profile_maximum_message_byte_count
            and event_contract in profile.supported_event_contracts
            and binding.data_classification in profile.supported_classifications
            and binding.representation_name in profile.supported_representations
            and binding.encoding in profile.supported_encodings
            and binding.delivery_semantics in profile.supported_delivery_semantics
            and (not binding.durability_required or profile.durable_delivery_supported)
            and binding.ordering_key_kind in profile.supported_ordering_key_kinds
            and binding.retention_class in profile.supported_retention_classes
            and binding.maximum_canonical_byte_count <= profile.maximum_message_byte_count
            and binding.canonical_byte_count <= profile.maximum_message_byte_count
            and candidate.admitter_subject_id == request.admitter_subject_id
            and candidate.admitted_at == request.requested_at
            and candidate.state is WorkflowEventTransportCompatibilityAdmissionState.ADMITTED
            and not any(candidate.authority.canonical_value().values())
        )

    @staticmethod
    def _physical_transport_route_binding_evidence_matches(
        *,
        logical: WorkflowEventLogicalChannelBinding | None,
        admission: WorkflowEventTransportCompatibilityAdmission | None,
        profile: EventPhysicalTransportProfileSnapshot | None,
        route: EventPhysicalTransportRouteSnapshot | None,
        request: WorkflowEventPhysicalTransportRouteBindingRequest,
    ) -> bool:
        if logical is None or admission is None or profile is None or route is None:
            return False
        candidate = request.candidate
        sources = (logical, admission, profile, route)
        return bool(
            all(
                canonical_digest(source.digest_payload()) == source.canonical_digest
                and source.scope == request.scope
                and not any(source.authority.canonical_value().values())
                for source in sources
            )
            and logical.state is WorkflowEventLogicalChannelBindingState.BOUND
            and logical.binding_id
            == request.expected_logical_channel_binding_id
            == candidate.logical_channel_binding_id
            and logical.canonical_digest
            == request.expected_logical_channel_binding_digest
            == candidate.logical_channel_binding_digest
            and admission.state is WorkflowEventTransportCompatibilityAdmissionState.ADMITTED
            and admission.compatibility_admission_id
            == request.expected_transport_compatibility_admission_id
            == candidate.transport_compatibility_admission_id
            and admission.canonical_digest
            == request.expected_transport_compatibility_admission_digest
            == candidate.transport_compatibility_admission_digest
            and admission.logical_channel_binding_id == logical.binding_id
            and admission.logical_channel_binding_digest == logical.canonical_digest
            and profile.state is EventPhysicalTransportProfileSnapshotState.SNAPSHOTTED
            and profile.snapshot_id
            == request.expected_transport_profile_snapshot_id
            == candidate.transport_profile_snapshot_id
            == admission.transport_profile_snapshot_id
            and profile.canonical_digest
            == request.expected_transport_profile_snapshot_digest
            == candidate.transport_profile_snapshot_digest
            == admission.transport_profile_snapshot_digest
            and route.state is EventPhysicalTransportRouteSnapshotState.SNAPSHOTTED
            and route.snapshot_id
            == request.expected_transport_route_snapshot_id
            == candidate.transport_route_snapshot_id
            and route.canonical_digest
            == request.expected_transport_route_snapshot_digest
            == candidate.transport_route_snapshot_digest
            and admission.transport_profile_id == profile.transport_profile_id
            and admission.transport_profile_revision == profile.transport_profile_revision
            and route.transport_profile_id == profile.transport_profile_id
            and route.transport_profile_revision == profile.transport_profile_revision
            and route.transport_resource_id == profile.transport_resource_id
            and route.transport_resource_digest == profile.transport_resource_digest
            and route.transport_implementation_id == profile.transport_implementation_id
            and route.transport_implementation_version == profile.transport_implementation_version
            and route.adapter_contract_id == profile.adapter_contract_id
            and route.adapter_contract_version == profile.adapter_contract_version
            and route.adapter_contract_digest == profile.adapter_contract_digest
            and route.deployment_release_id == profile.deployment_release_id
            and route.deployment_profile == profile.deployment_profile
            and logical.scope == admission.scope == profile.scope == route.scope == candidate.scope
            and profile.transport_encryption_required
            and profile.restricted_network_supported
            and route.minimum_tls_version == "1.3"
            and route.server_authentication_required
            and route.plaintext_fallback_prohibited
            and route.restricted_network_enforced
            and route.public_egress_prohibited
            and route.proxy_mode in {"deployment-managed", "prohibited"}
            and candidate.policy_digest == request.expected_policy_digest
            and candidate.binder_subject_id == request.binder_subject_id
            and candidate.bound_at == request.requested_at
            and candidate.state is WorkflowEventPhysicalTransportRouteBindingState.BOUND
            and canonical_digest(candidate.digest_payload()) == candidate.canonical_digest
            and not any(candidate.authority.canonical_value().values())
        )

    @classmethod
    def _endpoint_materialization_claim(
        cls,
        request: WorkflowEventPhysicalTransportEndpointMaterializationClaimRequest,
        *,
        claimed_at: datetime,
    ) -> WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaim:
        values: dict[str, Any] = {
            "claim_id": request.claim_id,
            "authorization_lease_id": request.authorization_lease_id,
            "authorization_lease_digest": request.authorization_lease_digest,
            "freshness_admission_id": request.expected_freshness_admission_id,
            "freshness_admission_digest": request.expected_freshness_admission_digest,
            "attempt_id": request.attempt_id,
            "materialization_id": request.materialization_id,
            "scope": request.scope,
            "resolver_subject_id": request.resolver_subject_id,
            "claimed_at": claimed_at,
            "request_fingerprint": request.request_fingerprint,
            "idempotency_digest": request.idempotency_digest,
            "authority": WorkflowEventPhysicalTransportEndpointMaterializationAuthority(),
        }
        return WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaim(
            **values,
            canonical_digest=canonical_digest(cls._endpoint_materialization_payload(values)),
        )

    @classmethod
    def _endpoint_materialization_attempt(
        cls,
        request: WorkflowEventPhysicalTransportEndpointMaterializationClaimRequest,
        *,
        claim: WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaim,
        started_at: datetime,
        lease_valid_until: datetime,
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationAttempt:
        values: dict[str, Any] = {
            "attempt_id": request.attempt_id,
            "materialization_id": request.materialization_id,
            "consumption_claim_id": claim.claim_id,
            "authorization_lease_id": request.authorization_lease_id,
            "authorization_lease_digest": request.authorization_lease_digest,
            "freshness_admission_id": request.expected_freshness_admission_id,
            "freshness_admission_digest": request.expected_freshness_admission_digest,
            "physical_transport_route_binding_id": (
                request.expected_physical_transport_route_binding_id
            ),
            "physical_transport_route_binding_digest": (
                request.expected_physical_transport_route_binding_digest
            ),
            "transport_route_snapshot_id": request.expected_transport_route_snapshot_id,
            "transport_route_snapshot_digest": (request.expected_transport_route_snapshot_digest),
            "current_selection_head_id": request.expected_current_selection_head_id,
            "current_selection_head_digest": request.expected_current_selection_head_digest,
            "current_selection_head_generation": (
                request.expected_current_selection_head_generation
            ),
            "current_selection_head_fencing_token_digest": (
                request.expected_current_selection_head_fencing_token_digest
            ),
            "scope": request.scope,
            "resolver_subject_id": request.resolver_subject_id,
            "policy_id": request.expected_materialization_policy_id,
            "policy_version": request.expected_materialization_policy_version,
            "policy_digest": request.expected_materialization_policy_digest,
            "started_at": started_at,
            "freshness_valid_until": request.expected_freshness_valid_until,
            "lease_valid_until": lease_valid_until,
            "state": (
                WorkflowEventPhysicalTransportEndpointMaterializationAttemptState.MATERIALIZATION_STARTED
            ),
            "authority": WorkflowEventPhysicalTransportEndpointMaterializationAuthority(),
        }
        return WorkflowEventPhysicalTransportEndpointMaterializationAttempt(
            **values,
            canonical_digest=canonical_digest(cls._endpoint_materialization_payload(values)),
        )

    @staticmethod
    def _endpoint_materialization_payload(values: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value.canonical_value()
            if isinstance(
                value,
                (WorkflowScope, WorkflowEventPhysicalTransportEndpointMaterializationAuthority),
            )
            else value.value
            if isinstance(value, Enum)
            else value.isoformat()
            if isinstance(value, datetime)
            else value
            for key, value in values.items()
        }

    @staticmethod
    def _endpoint_resolution_authorization_evidence_matches(
        *,
        binding: WorkflowEventPhysicalTransportRouteBinding | None,
        route: EventPhysicalTransportRouteSnapshot | None,
        head: DeploymentEventTransportRouteSelectionHead | None,
        freshness: WorkflowEventPhysicalTransportRouteFreshnessAdmission | None,
        request: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRequest,
        observed_at: datetime,
    ) -> bool:
        if binding is None or route is None or head is None or freshness is None:
            return False
        policy = (
            code_owned_workflow_event_physical_transport_endpoint_resolution_authorization_policy()
        )
        return bool(
            binding.state is WorkflowEventPhysicalTransportRouteBindingState.BOUND
            and route.state is EventPhysicalTransportRouteSnapshotState.SNAPSHOTTED
            and freshness.state
            is WorkflowEventPhysicalTransportRouteFreshnessAdmissionState.ADMITTED_CURRENT
            and binding.binding_id
            == freshness.physical_transport_route_binding_id
            == request.expected_physical_transport_route_binding_id
            and binding.canonical_digest
            == freshness.physical_transport_route_binding_digest
            == request.expected_physical_transport_route_binding_digest
            and binding.transport_route_snapshot_id
            == route.snapshot_id
            == freshness.transport_route_snapshot_id
            == request.expected_transport_route_snapshot_id
            and binding.transport_route_snapshot_digest
            == route.canonical_digest
            == freshness.transport_route_snapshot_digest
            == request.expected_transport_route_snapshot_digest
            and freshness.freshness_admission_id == request.expected_freshness_admission_id
            and freshness.canonical_digest == request.expected_freshness_admission_digest
            and freshness.valid_until == request.expected_freshness_admission_valid_until
            and head.head_id
            == freshness.current_selection_head_id
            == request.expected_current_selection_head_id
            and head.canonical_digest
            == freshness.current_selection_head_digest
            == request.expected_current_selection_head_digest
            and head.generation
            == freshness.current_selection_head_generation
            == request.expected_current_selection_head_generation
            and head.fencing_token_digest
            == freshness.current_selection_head_fencing_token_digest
            == request.expected_current_selection_head_fencing_token_digest
            and head.route_set_id
            == route.route_set_id
            == freshness.route_set_id
            == request.expected_route_set_id
            and head.route_set_revision
            == route.route_set_revision
            == freshness.route_set_revision
            == request.expected_route_set_revision
            and head.selection_epoch_id
            == route.selection_epoch_id
            == freshness.selection_epoch_id
            == request.expected_selection_epoch_id
            and head.selection_epoch_revision
            == route.selection_epoch_revision
            == freshness.selection_epoch_revision
            == request.expected_selection_epoch_revision
            and head.selected_route_id
            == route.route_id
            == freshness.selected_route_id
            == request.expected_selected_route_id
            and head.selected_route_revision
            == route.route_revision
            == freshness.selected_route_revision
            == request.expected_selected_route_revision
            and head.selected_route_digest
            == route.source_route_digest
            == freshness.selected_route_digest
            == request.expected_selected_route_digest
            and head.selection_active
            == freshness.selection_active
            == request.expected_selection_active
            is True
            and head.selection_eligible
            == freshness.selection_eligible
            == request.expected_selection_eligible
            is True
            and head.selection_suspended
            == freshness.selection_suspended
            == request.expected_selection_suspended
            is False
            and head.selection_withdrawn
            == freshness.selection_withdrawn
            == request.expected_selection_withdrawn
            is False
            and head.selection_superseded
            == freshness.selection_superseded
            == request.expected_selection_superseded
            is False
            and head.current
            and binding.scope == route.scope == head.scope == freshness.scope == request.scope
            and route.captured_at <= binding.bound_at <= freshness.evaluated_at <= observed_at
            and request.expected_policy_id == policy.policy_id
            and request.expected_policy_version == policy.policy_version
            and request.expected_policy_digest == policy.canonical_digest
            and request.expected_validity_window_seconds == policy.validity_window_seconds
            and canonical_digest(binding.digest_payload()) == binding.canonical_digest
            and canonical_digest(route.digest_payload()) == route.canonical_digest
            and canonical_digest(head.digest_payload()) == head.canonical_digest
            and canonical_digest(freshness.digest_payload()) == freshness.canonical_digest
            and not any(binding.authority.canonical_value().values())
            and not any(route.authority.canonical_value().values())
            and not any(freshness.authority.canonical_value().values())
        )

    @staticmethod
    def _endpoint_resolution_authorization_remains_current(
        lease: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease,
        *,
        head: DeploymentEventTransportRouteSelectionHead,
        freshness: WorkflowEventPhysicalTransportRouteFreshnessAdmission,
        observed_at: datetime,
    ) -> bool:
        return bool(
            observed_at < lease.valid_until
            and observed_at < freshness.valid_until
            and lease.freshness_admission_id == freshness.freshness_admission_id
            and lease.freshness_admission_digest == freshness.canonical_digest
            and lease.current_selection_head_id == head.head_id
            and lease.current_selection_head_digest == head.canonical_digest
            and lease.current_selection_head_generation == head.generation
            and lease.current_selection_head_fencing_token_digest == head.fencing_token_digest
            and lease.selected_route_id == head.selected_route_id
            and lease.selected_route_revision == head.selected_route_revision
            and lease.selected_route_digest == head.selected_route_digest
            and head.current
            and head.selection_active
            and head.selection_eligible
            and not head.selection_suspended
            and not head.selection_withdrawn
            and not head.selection_superseded
        )

    @staticmethod
    def _endpoint_resolution_authorization_lease(
        *,
        request: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRequest,
        freshness: WorkflowEventPhysicalTransportRouteFreshnessAdmission,
        issued_at: datetime,
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease:
        policy = (
            code_owned_workflow_event_physical_transport_endpoint_resolution_authorization_policy()
        )
        authority = WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseAuthority()
        lease_state = WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseState
        state = lease_state.AUTHORIZED_UNCONSUMED
        values: dict[str, object] = {
            "authorization_lease_id": request.authorization_lease_id,
            "freshness_admission_id": freshness.freshness_admission_id,
            "freshness_admission_digest": freshness.canonical_digest,
            "physical_transport_route_binding_id": freshness.physical_transport_route_binding_id,
            "physical_transport_route_binding_digest": (
                freshness.physical_transport_route_binding_digest
            ),
            "transport_route_snapshot_id": freshness.transport_route_snapshot_id,
            "transport_route_snapshot_digest": freshness.transport_route_snapshot_digest,
            "current_selection_head_id": freshness.current_selection_head_id,
            "current_selection_head_digest": freshness.current_selection_head_digest,
            "current_selection_head_generation": freshness.current_selection_head_generation,
            "current_selection_head_fencing_token_digest": (
                freshness.current_selection_head_fencing_token_digest
            ),
            "route_set_id": freshness.route_set_id,
            "route_set_revision": freshness.route_set_revision,
            "selection_epoch_id": freshness.selection_epoch_id,
            "selection_epoch_revision": freshness.selection_epoch_revision,
            "selected_route_id": freshness.selected_route_id,
            "selected_route_revision": freshness.selected_route_revision,
            "selected_route_digest": freshness.selected_route_digest,
            "selection_active": freshness.selection_active,
            "selection_eligible": freshness.selection_eligible,
            "selection_suspended": freshness.selection_suspended,
            "selection_withdrawn": freshness.selection_withdrawn,
            "selection_superseded": freshness.selection_superseded,
            "policy_id": policy.policy_id,
            "policy_version": policy.policy_version,
            "policy_digest": policy.canonical_digest,
            "scope": request.scope,
            "resolver_subject_id": request.resolver_subject_id,
            "issued_at": issued_at,
            "valid_until": issued_at + timedelta(seconds=policy.validity_window_seconds),
            "state": state,
            "authority": authority,
        }
        payload = {
            **values,
            "authority": authority.canonical_value(),
            "issued_at": issued_at.isoformat(),
            "scope": request.scope.canonical_value(),
            "state": state.value,
            "valid_until": (
                issued_at + timedelta(seconds=policy.validity_window_seconds)
            ).isoformat(),
        }
        return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease(
            **cast(Any, values),
            canonical_digest=canonical_digest(payload),
        )

    @staticmethod
    def _route_freshness_admission_evidence_matches(
        *,
        binding: WorkflowEventPhysicalTransportRouteBinding | None,
        route: EventPhysicalTransportRouteSnapshot | None,
        head: DeploymentEventTransportRouteSelectionHead | None,
        request: WorkflowEventPhysicalTransportRouteFreshnessAdmissionRequest,
    ) -> bool:
        if binding is None or route is None or head is None:
            return False
        candidate = request.candidate
        policy = code_owned_workflow_event_physical_transport_route_freshness_policy()
        return bool(
            canonical_digest(binding.digest_payload()) == binding.canonical_digest
            and canonical_digest(route.digest_payload()) == route.canonical_digest
            and canonical_digest(head.digest_payload()) == head.canonical_digest
            and binding.state is WorkflowEventPhysicalTransportRouteBindingState.BOUND
            and route.state is EventPhysicalTransportRouteSnapshotState.SNAPSHOTTED
            and binding.binding_id
            == request.expected_physical_transport_route_binding_id
            == candidate.physical_transport_route_binding_id
            and binding.canonical_digest
            == request.expected_physical_transport_route_binding_digest
            == candidate.physical_transport_route_binding_digest
            and binding.transport_route_snapshot_id
            == route.snapshot_id
            == request.expected_transport_route_snapshot_id
            == candidate.transport_route_snapshot_id
            and binding.transport_route_snapshot_digest
            == route.canonical_digest
            == request.expected_transport_route_snapshot_digest
            == candidate.transport_route_snapshot_digest
            and head.head_id
            == request.expected_current_selection_head_id
            == candidate.current_selection_head_id
            and head.canonical_digest
            == request.expected_current_selection_head_digest
            == candidate.current_selection_head_digest
            and head.generation
            == request.expected_current_selection_head_generation
            == candidate.current_selection_head_generation
            and head.fencing_token_digest
            == request.expected_current_selection_head_fencing_token_digest
            == candidate.current_selection_head_fencing_token_digest
            and head.route_set_id
            == route.route_set_id
            == request.expected_route_set_id
            == candidate.route_set_id
            and head.route_set_revision
            == route.route_set_revision
            == request.expected_route_set_revision
            == candidate.route_set_revision
            and head.selection_epoch_id
            == route.selection_epoch_id
            == request.expected_selection_epoch_id
            == candidate.selection_epoch_id
            and head.selection_epoch_revision
            == route.selection_epoch_revision
            == request.expected_selection_epoch_revision
            == candidate.selection_epoch_revision
            and head.selected_route_id
            == route.route_id
            == request.expected_selected_route_id
            == candidate.selected_route_id
            and head.selected_route_revision
            == route.route_revision
            == request.expected_selected_route_revision
            == candidate.selected_route_revision
            and head.selected_route_digest
            == route.source_route_digest
            == request.expected_selected_route_digest
            == candidate.selected_route_digest
            and head.selection_active
            == request.expected_selection_active
            == candidate.selection_active
            is True
            and head.selection_eligible
            == request.expected_selection_eligible
            == candidate.selection_eligible
            is True
            and head.selection_suspended
            == request.expected_selection_suspended
            == candidate.selection_suspended
            is False
            and head.selection_withdrawn
            == request.expected_selection_withdrawn
            == candidate.selection_withdrawn
            is False
            and head.selection_superseded
            == request.expected_selection_superseded
            == candidate.selection_superseded
            is False
            and head.current
            and binding.scope == route.scope == head.scope == candidate.scope == request.scope
            and route.captured_at <= binding.bound_at <= candidate.evaluated_at
            and candidate.policy_id == policy.policy_id
            and candidate.policy_version == policy.policy_version
            and candidate.policy_digest == request.expected_policy_digest == policy.canonical_digest
            and candidate.admitter_subject_id == request.admitter_subject_id
            and candidate.evaluated_at == request.evaluated_at
            and (candidate.valid_until - candidate.evaluated_at).total_seconds()
            == policy.validity_window_seconds
            and candidate.state
            is WorkflowEventPhysicalTransportRouteFreshnessAdmissionState.ADMITTED_CURRENT
            and canonical_digest(candidate.digest_payload()) == candidate.canonical_digest
            and not any(binding.authority.canonical_value().values())
            and not any(route.authority.canonical_value().values())
            and not any(candidate.authority.canonical_value().values())
        )

    @staticmethod
    def _route_freshness_admission_remains_current(
        admission: WorkflowEventPhysicalTransportRouteFreshnessAdmission,
        *,
        head: DeploymentEventTransportRouteSelectionHead,
        observed_at: datetime,
    ) -> bool:
        return bool(
            observed_at < admission.valid_until
            and admission.current_selection_head_id == head.head_id
            and admission.current_selection_head_digest == head.canonical_digest
            and admission.current_selection_head_generation == head.generation
            and admission.current_selection_head_fencing_token_digest == head.fencing_token_digest
            and admission.selected_route_id == head.selected_route_id
            and admission.selected_route_revision == head.selected_route_revision
            and admission.selected_route_digest == head.selected_route_digest
            and head.current
            and head.selection_active
            and head.selection_eligible
            and not head.selection_suspended
            and not head.selection_withdrawn
            and not head.selection_superseded
        )

    @staticmethod
    def _raise_route_selection_head_sync_conflict() -> None:
        raise WorkflowEventPhysicalTransportRouteFreshnessAdmissionError(
            "workflow_route_selection_head_synchronization_conflict",
            "The authoritative route selection head synchronization conflicted.",
        )

    @classmethod
    def _publication_mutation_evidence_matches(
        cls,
        *,
        outbox: WorkflowDispatchOutboxEntry | None,
        plan: WorkflowRunPlan | None,
        orchestration_lease: WorkflowOrchestrationLease | None,
        request: WorkflowOutboxPublicationLeaseMutationRequest,
    ) -> bool:
        candidate = request.updated_lease
        acquire_shape = WorkflowOutboxPublicationLeaseAcquireRequest(
            expected_outbox_entry_digest=request.expected_outbox_entry_digest,
            expected_orchestration_lease_id=request.expected_orchestration_lease_id,
            expected_orchestration_lease_digest=request.expected_orchestration_lease_digest,
            expected_orchestration_fencing_token=request.expected_orchestration_fencing_token,
            candidate=candidate,
            requested_at=request.requested_at,
            idempotency_key="mutation-validation",
            request_fingerprint="0" * 64,
            expected_current_lease_digest=request.expected_publication_lease_digest,
            expected_current_publication_fencing_token=(request.expected_publication_fencing_token),
        )
        return cls._publication_evidence_matches(
            outbox=outbox,
            plan=plan,
            orchestration_lease=orchestration_lease,
            request=acquire_shape,
        )

    @staticmethod
    def _publication_acquire_generation_matches(
        *,
        current: WorkflowOutboxPublicationLease | None,
        request: WorkflowOutboxPublicationLeaseAcquireRequest,
    ) -> bool:
        candidate = request.candidate
        if current is None:
            return bool(
                request.expected_current_lease_digest is None
                and request.expected_current_publication_fencing_token is None
                and candidate.publication_fencing_token == 1
            )
        return bool(
            current.canonical_digest == request.expected_current_lease_digest
            and current.publication_fencing_token
            == request.expected_current_publication_fencing_token
            and current.effective_state(requested_at=request.requested_at)
            is not WorkflowOutboxPublicationLeaseEffectiveState.ACTIVE
            and candidate.publication_fencing_token == current.publication_fencing_token + 1
        )

    @staticmethod
    def _same_publication_lease_generation(
        current: WorkflowOutboxPublicationLease,
        updated: WorkflowOutboxPublicationLease,
    ) -> bool:
        immutable_fields = (
            "publication_lease_id",
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
            "publisher_subject_id",
            "acquired_at",
            "publication_fencing_token",
            "authority",
        )
        return all(getattr(current, field) == getattr(updated, field) for field in immutable_fields)

    async def close(self) -> None:
        return None
