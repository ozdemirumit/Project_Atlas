from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
from hashlib import sha256
from typing import Any, NoReturn, cast

from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from atlas.core.persistence.models import (
    DeploymentEventTransportCredentialAssignmentModel,
    DeploymentEventTransportRouteSelectionHeadModel,
    EventPhysicalTransportCredentialAssignmentSnapshotClaimModel,
    EventPhysicalTransportCredentialAssignmentSnapshotModel,
    EventPhysicalTransportProfileSnapshotClaimModel,
    EventPhysicalTransportProfileSnapshotModel,
    EventPhysicalTransportRouteSnapshotClaimModel,
    EventPhysicalTransportRouteSnapshotModel,
    WorkflowAttemptMaterializationClaimModel,
    WorkflowDispatchEventEnvelopeModel,
    WorkflowDispatchEventEnvelopePreparationClaimModel,
    WorkflowDispatchIntentModel,
    WorkflowDispatchIntentStagingClaimModel,
    WorkflowDispatchOutboxEntryModel,
    WorkflowEventByteArtifactClaimModel,
    WorkflowEventByteArtifactModel,
    WorkflowEventLogicalChannelBindingClaimModel,
    WorkflowEventLogicalChannelBindingModel,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationClaimModel,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel,
    WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaimModel,
    WorkflowEventPhysicalTransportCredentialAssignmentBindingClaimModel,
    WorkflowEventPhysicalTransportCredentialAssignmentBindingModel,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessClaimModel,
    WorkflowEventPhysicalTransportCredentialMaterializationAttemptModel,
    WorkflowEventPhysicalTransportCredentialMaterializationResultModel,
    WorkflowEventPhysicalTransportEndpointMaterializationAttemptModel,
    WorkflowEventPhysicalTransportEndpointMaterializationResultModel,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseClaimModel,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel,
    WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaimModel,
    WorkflowEventPhysicalTransportRouteBindingClaimModel,
    WorkflowEventPhysicalTransportRouteBindingModel,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionClaimModel,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel,
    WorkflowEventPhysicalTransportTargetContextBindingClaimModel,
    WorkflowEventPhysicalTransportTargetContextBindingModel,
    WorkflowEventTransportAdmissionClaimModel,
    WorkflowEventTransportAdmissionModel,
    WorkflowEventTransportCompatibilityAdmissionClaimModel,
    WorkflowEventTransportCompatibilityAdmissionModel,
    WorkflowExecutionAttemptModel,
    WorkflowExecutionRunModel,
    WorkflowExecutionStepRunModel,
    WorkflowIdempotencyModel,
    WorkflowLeaseIdempotencyModel,
    WorkflowOrchestrationLeaseModel,
    WorkflowOutboxPublicationLeaseAcquireClaimModel,
    WorkflowOutboxPublicationLeaseModel,
    WorkflowPlanTransitionModel,
    WorkflowRunMaterializationClaimModel,
    WorkflowRunPlanModel,
)
from atlas.modules.workflows.application import (
    WorkflowAttemptMaterializationError,
    WorkflowAttemptMaterializationIdempotencyRecord,
    WorkflowAttemptMaterializationRequest,
    WorkflowAttemptMaterializationResult,
    WorkflowAttemptMaterializationStatus,
    WorkflowLeaseAcquireIdempotencyRecord,
    WorkflowLeaseAcquireRequest,
    WorkflowLeaseAcquireResult,
    WorkflowLeaseAcquireStatus,
    WorkflowLeaseMutationRequest,
    WorkflowLeaseMutationResult,
    WorkflowLeaseMutationStatus,
    WorkflowOrchestrationLeaseError,
    WorkflowPlanCancellationIdempotencyRecord,
    WorkflowPlanCancellationRequest,
    WorkflowPlanCancellationResult,
    WorkflowPlanCancellationStatus,
    WorkflowPlanIdempotencyRecord,
    WorkflowPlanMutationResult,
    WorkflowPlanMutationStatus,
    WorkflowPlanningError,
    WorkflowRunMaterializationIdempotencyRecord,
    WorkflowRunMaterializationRequest,
    WorkflowRunMaterializationResult,
    WorkflowRunMaterializationStatus,
)
from atlas.modules.workflows.application.byte_artifact_ports import (
    WorkflowEventByteArtifactError,
    WorkflowEventByteArtifactIdempotencyRecord,
    WorkflowEventByteArtifactRequest,
    WorkflowEventByteArtifactResult,
    WorkflowEventByteArtifactStatus,
)
from atlas.modules.workflows.application.credential_access_authorization_lease_ports import (
    WorkflowTransportCredentialAccessAuthorizationLeaseError,
    WorkflowTransportCredentialAccessAuthorizationLeaseIdempotencyRecord,
    WorkflowTransportCredentialAccessAuthorizationLeaseRequest,
    WorkflowTransportCredentialAccessAuthorizationLeaseResult,
    WorkflowTransportCredentialAccessAuthorizationLeaseStatus,
    validate_workflow_transport_credential_access_authorization_request,
)
from atlas.modules.workflows.application.credential_assignment_binding_ports import (
    WorkflowTransportCredentialAssignmentBindingError,
    WorkflowTransportCredentialAssignmentBindingIdempotencyRecord,
    WorkflowTransportCredentialAssignmentBindingRequest,
    WorkflowTransportCredentialAssignmentBindingResult,
    WorkflowTransportCredentialAssignmentBindingStatus,
)
from atlas.modules.workflows.application.credential_assignment_freshness_admission_ports import (
    WorkflowTransportCredentialAssignmentFreshnessAdmissionError,
    WorkflowTransportCredentialAssignmentFreshnessAdmissionIdempotencyRecord,
    WorkflowTransportCredentialAssignmentFreshnessAdmissionRequest,
    WorkflowTransportCredentialAssignmentFreshnessAdmissionResult,
    WorkflowTransportCredentialAssignmentFreshnessAdmissionStatus,
    validate_workflow_transport_credential_assignment_freshness_request,
)
from atlas.modules.workflows.application.credential_assignment_snapshot_ports import (
    WorkflowTransportCredentialAssignmentSnapshotError,
    WorkflowTransportCredentialAssignmentSnapshotIdempotencyRecord,
    WorkflowTransportCredentialAssignmentSnapshotRequest,
    WorkflowTransportCredentialAssignmentSnapshotResult,
    WorkflowTransportCredentialAssignmentSnapshotStatus,
    validate_workflow_transport_credential_assignment_snapshot_request,
)
from atlas.modules.workflows.application.credential_materialization_ports import (
    WorkflowEventPhysicalTransportCredentialMaterializationClaimRequest,
    WorkflowEventPhysicalTransportCredentialMaterializationClaimResult,
    WorkflowEventPhysicalTransportCredentialMaterializationClaimStatus,
    WorkflowEventPhysicalTransportCredentialMaterializationError,
    WorkflowEventPhysicalTransportCredentialMaterializationResultRequest,
    WorkflowEventPhysicalTransportCredentialMaterializationResultStatus,
    WorkflowEventPhysicalTransportCredentialMaterializationResultWrite,
)
from atlas.modules.workflows.application.dispatch_intent_ports import (
    WorkflowDispatchIntentStagingError,
    WorkflowDispatchIntentStagingIdempotencyRecord,
    WorkflowDispatchIntentStagingRequest,
    WorkflowDispatchIntentStagingResult,
    WorkflowDispatchIntentStagingStatus,
)
from atlas.modules.workflows.application.endpoint_materialization_ports import (
    WorkflowEventPhysicalTransportEndpointMaterializationClaimRequest,
    WorkflowEventPhysicalTransportEndpointMaterializationClaimResult,
    WorkflowEventPhysicalTransportEndpointMaterializationClaimStatus,
    WorkflowEventPhysicalTransportEndpointMaterializationError,
    WorkflowEventPhysicalTransportEndpointMaterializationResultRequest,
    WorkflowEventPhysicalTransportEndpointMaterializationResultStatus,
    WorkflowEventPhysicalTransportEndpointMaterializationResultWrite,
)
from atlas.modules.workflows.application.endpoint_resolution_authorization_lease_ports import (
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseIdempotencyRecord,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRequest,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus,
)
from atlas.modules.workflows.application.event_envelope_ports import (
    WorkflowDispatchEventEnvelopeError,
    WorkflowDispatchEventEnvelopePrepareIdempotencyRecord,
    WorkflowDispatchEventEnvelopePrepareRequest,
    WorkflowDispatchEventEnvelopePrepareResult,
    WorkflowDispatchEventEnvelopePrepareStatus,
)
from atlas.modules.workflows.application.logical_channel_binding_ports import (
    WorkflowEventLogicalChannelBindingError,
    WorkflowEventLogicalChannelBindingIdempotencyRecord,
    WorkflowEventLogicalChannelBindingRequest,
    WorkflowEventLogicalChannelBindingResult,
    WorkflowEventLogicalChannelBindingStatus,
)
from atlas.modules.workflows.application.physical_route_binding_ports import (
    WorkflowEventPhysicalTransportRouteBindingError,
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
    WorkflowOutboxPublicationLeaseError,
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
from atlas.modules.workflows.application.target_context_binding_ports import (
    WorkflowEventPhysicalTransportTargetContextBindingError,
    WorkflowEventPhysicalTransportTargetContextBindingRequest,
    WorkflowEventPhysicalTransportTargetContextBindingResult,
    WorkflowEventPhysicalTransportTargetContextBindingStatus,
)
from atlas.modules.workflows.application.transport_admission_ports import (
    WorkflowEventTransportAdmissionError,
    WorkflowEventTransportAdmissionIdempotencyRecord,
    WorkflowEventTransportAdmissionRequest,
    WorkflowEventTransportAdmissionResult,
    WorkflowEventTransportAdmissionStatus,
)
from atlas.modules.workflows.application.transport_compatibility_admission_ports import (
    WorkflowEventTransportCompatibilityAdmissionError,
    WorkflowEventTransportCompatibilityAdmissionIdempotencyRecord,
    WorkflowEventTransportCompatibilityAdmissionRequest,
    WorkflowEventTransportCompatibilityAdmissionResult,
    WorkflowEventTransportCompatibilityAdmissionStatus,
)
from atlas.modules.workflows.application.transport_profile_snapshot_ports import (
    WorkflowTransportProfileSnapshotError,
    WorkflowTransportProfileSnapshotIdempotencyRecord,
    WorkflowTransportProfileSnapshotRequest,
    WorkflowTransportProfileSnapshotResult,
    WorkflowTransportProfileSnapshotStatus,
)
from atlas.modules.workflows.application.transport_route_snapshot_ports import (
    WorkflowTransportRouteSnapshotError,
    WorkflowTransportRouteSnapshotIdempotencyRecord,
    WorkflowTransportRouteSnapshotRequest,
    WorkflowTransportRouteSnapshotResult,
    WorkflowTransportRouteSnapshotStatus,
)
from atlas.modules.workflows.domain import (
    DeploymentEventTransportRouteSelectionHead,
    DeploymentPhysicalTransportCredentialAssignment,
    EventPhysicalTransportCredentialAssignmentSnapshot,
    EventPhysicalTransportCredentialAssignmentSnapshotAuthority,
    EventPhysicalTransportCredentialAssignmentSnapshotState,
    EventPhysicalTransportProfileSnapshot,
    EventPhysicalTransportProfileSnapshotAuthority,
    EventPhysicalTransportProfileSnapshotState,
    EventPhysicalTransportRouteSnapshot,
    EventPhysicalTransportRouteSnapshotAuthority,
    EventPhysicalTransportRouteSnapshotState,
    WorkflowCapabilityClass,
    WorkflowDispatchEventAuthority,
    WorkflowDispatchEventEnvelope,
    WorkflowDispatchEventEnvelopeState,
    WorkflowDispatchEventPayload,
    WorkflowDispatchIntent,
    WorkflowDispatchIntentState,
    WorkflowDispatchOutboxEntry,
    WorkflowDispatchOutboxState,
    WorkflowEventByteArtifact,
    WorkflowEventByteArtifactAuthority,
    WorkflowEventByteArtifactState,
    WorkflowEventLogicalChannelBinding,
    WorkflowEventLogicalChannelBindingAuthority,
    WorkflowEventLogicalChannelBindingState,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseAuthority,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseState,
    WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaim,
    WorkflowEventPhysicalTransportCredentialAssignmentBinding,
    WorkflowEventPhysicalTransportCredentialAssignmentBindingAuthority,
    WorkflowEventPhysicalTransportCredentialAssignmentBindingState,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionAuthority,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionState,
    WorkflowEventPhysicalTransportCredentialMaterializationAttempt,
    WorkflowEventPhysicalTransportCredentialMaterializationAttemptState,
    WorkflowEventPhysicalTransportCredentialMaterializationAuthority,
    WorkflowEventPhysicalTransportCredentialMaterializationFailureClass,
    WorkflowEventPhysicalTransportCredentialMaterializationResult,
    WorkflowEventPhysicalTransportCredentialMaterializationResultState,
    WorkflowEventPhysicalTransportEndpointMaterializationAttempt,
    WorkflowEventPhysicalTransportEndpointMaterializationAttemptState,
    WorkflowEventPhysicalTransportEndpointMaterializationAuthority,
    WorkflowEventPhysicalTransportEndpointMaterializationFailureClass,
    WorkflowEventPhysicalTransportEndpointMaterializationResult,
    WorkflowEventPhysicalTransportEndpointMaterializationResultState,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseAuthority,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseState,
    WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaim,
    WorkflowEventPhysicalTransportRouteBinding,
    WorkflowEventPhysicalTransportRouteBindingAuthority,
    WorkflowEventPhysicalTransportRouteBindingState,
    WorkflowEventPhysicalTransportRouteFreshnessAdmission,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionAuthority,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionState,
    WorkflowEventPhysicalTransportTargetContextBinding,
    WorkflowEventPhysicalTransportTargetContextBindingAuthority,
    WorkflowEventPhysicalTransportTargetContextBindingState,
    WorkflowEventTransportAdmission,
    WorkflowEventTransportAdmissionAuthority,
    WorkflowEventTransportAdmissionState,
    WorkflowEventTransportCompatibilityAdmission,
    WorkflowEventTransportCompatibilityAdmissionAuthority,
    WorkflowEventTransportCompatibilityAdmissionState,
    WorkflowExecutionAttempt,
    WorkflowExecutionAttemptState,
    WorkflowExecutionRun,
    WorkflowExecutionRunState,
    WorkflowExecutionStepRun,
    WorkflowExecutionStepRunState,
    WorkflowOrchestrationLease,
    WorkflowOrchestrationLeaseEffectiveState,
    WorkflowOrchestrationLeaseState,
    WorkflowOutboxPublicationLease,
    WorkflowOutboxPublicationLeaseEffectiveState,
    WorkflowOutboxPublicationLeaseState,
    WorkflowPlanAuthority,
    WorkflowPlanState,
    WorkflowPlanStep,
    WorkflowPlanStepState,
    WorkflowPlanTransition,
    WorkflowRunPlan,
    WorkflowScope,
    WorkflowStepKind,
    canonical_digest,
    canonical_json_byte_count,
    canonical_json_bytes,
    code_owned_workflow_event_logical_channel_policy,
    code_owned_workflow_event_physical_transport_credential_assignment_binding_policy,
    code_owned_workflow_event_physical_transport_credential_materialization_policy,
    code_owned_workflow_event_physical_transport_endpoint_materialization_policy,
    code_owned_workflow_event_physical_transport_endpoint_resolution_authorization_policy,
    code_owned_workflow_event_physical_transport_route_freshness_policy,
    code_owned_workflow_event_physical_transport_target_context_binding_policy,
    code_owned_workflow_event_transport_admission_policy,
    select_deployment_physical_transport_credential_assignment_head,
)


@dataclass(frozen=True, slots=True)
class _TargetContextLockedSources:
    route_binding: WorkflowEventPhysicalTransportRouteBindingModel
    route_snapshot: EventPhysicalTransportRouteSnapshotModel
    endpoint_freshness: WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel
    endpoint_lease: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel
    endpoint_claim: WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaimModel
    endpoint_attempt: WorkflowEventPhysicalTransportEndpointMaterializationAttemptModel
    endpoint_result: WorkflowEventPhysicalTransportEndpointMaterializationResultModel
    credential_binding: WorkflowEventPhysicalTransportCredentialAssignmentBindingModel
    credential_snapshot: EventPhysicalTransportCredentialAssignmentSnapshotModel
    credential_freshness: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel
    credential_lease: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel
    credential_claim: WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaimModel
    credential_attempt: WorkflowEventPhysicalTransportCredentialMaterializationAttemptModel
    credential_result: WorkflowEventPhysicalTransportCredentialMaterializationResultModel
    existing_bindings: tuple[WorkflowEventPhysicalTransportTargetContextBindingModel, ...]
    idempotency_claim: WorkflowEventPhysicalTransportTargetContextBindingClaimModel | None


class PostgreSQLWorkflowPlanRepository:
    def __init__(
        self,
        *,
        engine: AsyncEngine,
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self._engine = engine
        self._sessions = session_factory or async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLWorkflowPlanRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get_authoritative_time(self) -> datetime:
        async with self._sessions() as session:
            return cast(datetime, await session.scalar(select(func.now())))

    async def get_by_id(self, *, plan_id: str) -> WorkflowRunPlan | None:
        async with self._sessions() as session:
            row = await session.get(WorkflowRunPlanModel, plan_id)
            if row is None:
                return None
            transitions = await self._load_transitions(session, (plan_id,))
            return self._plan_from_row(row, transitions.get(plan_id, ()))

    async def list_scoped(
        self,
        *,
        scope: WorkflowScope,
        authorized_target_ids: frozenset[str],
        limit: int,
    ) -> tuple[WorkflowRunPlan, ...]:
        if not authorized_target_ids:
            return ()
        statement = (
            select(WorkflowRunPlanModel)
            .where(
                WorkflowRunPlanModel.organization_id == scope.organization_id,
                WorkflowRunPlanModel.environment_id == scope.environment_id,
                WorkflowRunPlanModel.site_id == scope.site_id,
                WorkflowRunPlanModel.target_id.in_(authorized_target_ids),
            )
            .order_by(WorkflowRunPlanModel.created_at.desc(), WorkflowRunPlanModel.plan_id.desc())
            .limit(limit)
        )
        async with self._sessions() as session:
            rows = tuple((await session.scalars(statement)).all())
            transitions = await self._load_transitions(session, tuple(row.plan_id for row in rows))
            return tuple(self._plan_from_row(row, transitions.get(row.plan_id, ())) for row in rows)

    async def get_create_request(
        self,
        *,
        scope: WorkflowScope,
        creator_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowPlanIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_claim(
                session,
                operation="create",
                scope=scope,
                subject_id=creator_subject_id,
                idempotency_key=idempotency_key,
            )
            if claim is None:
                return None
            return WorkflowPlanIdempotencyRecord(
                request_fingerprint=claim.request_fingerprint,
                plan=self._plan_from_claim(claim, expected_operation="create"),
            )

    async def create(
        self,
        plan: WorkflowRunPlan,
        *,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> WorkflowPlanMutationResult:
        async with self._sessions() as session:
            prior = await self._replay_result(
                session,
                plan=plan,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
            )
            if prior is not None:
                return prior
            try:
                session.add(self._plan_model(plan))
                session.add(
                    self._idempotency_model(
                        plan,
                        idempotency_key=idempotency_key,
                        request_fingerprint=request_fingerprint,
                    )
                )
                await session.commit()
                return WorkflowPlanMutationResult(WorkflowPlanMutationStatus.CREATED, plan)
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            replay = await self._replay_result(
                session,
                plan=plan,
                idempotency_key=idempotency_key,
                request_fingerprint=request_fingerprint,
            )
            if replay is not None:
                return replay
            return WorkflowPlanMutationResult(
                WorkflowPlanMutationStatus.IDEMPOTENCY_CONFLICT,
                None,
            )

    async def get_cancellation_request(
        self,
        *,
        scope: WorkflowScope,
        actor_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowPlanCancellationIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_claim(
                session,
                operation="cancel",
                scope=scope,
                subject_id=actor_subject_id,
                idempotency_key=idempotency_key,
            )
            if claim is None:
                return None
            return WorkflowPlanCancellationIdempotencyRecord(
                request_fingerprint=claim.request_fingerprint,
                plan=self._plan_from_claim(claim, expected_operation="cancel"),
            )

    async def cancel(
        self, request: WorkflowPlanCancellationRequest
    ) -> WorkflowPlanCancellationResult:
        candidate = request.cancelled_plan
        operation = "cancel"
        scope_id = self._idempotency_scope(candidate.scope, request.actor_subject_id)
        async with self._sessions() as session:
            prior = await self._cancellation_replay_result(session, request=request)
            if prior is not None:
                return prior

            row = cast(
                WorkflowRunPlanModel | None,
                await session.scalar(
                    select(WorkflowRunPlanModel)
                    .where(WorkflowRunPlanModel.plan_id == candidate.plan_id)
                    .with_for_update()
                ),
            )
            if row is None:
                await session.rollback()
                return WorkflowPlanCancellationResult(
                    WorkflowPlanCancellationStatus.NOT_FOUND, None
                )

            # A competing cancellation may have completed while this transaction waited.
            prior = await self._cancellation_replay_result(session, request=request)
            if prior is not None:
                await session.rollback()
                return prior

            transitions = await self._load_transitions(session, (candidate.plan_id,))
            current = self._plan_from_row(row, transitions.get(candidate.plan_id, ()))
            if (
                current.state is not WorkflowPlanState.PLANNED
                or current.canonical_digest != request.expected_plan_digest
                or not self._valid_cancellation(
                    current=current,
                    candidate=candidate,
                    actor_subject_id=request.actor_subject_id,
                )
            ):
                await session.rollback()
                return WorkflowPlanCancellationResult(
                    WorkflowPlanCancellationStatus.STATE_CONFLICT, current
                )

            transition = candidate.transition_history[-1]
            try:
                result = cast(
                    CursorResult[Any],
                    await session.execute(
                        update(WorkflowRunPlanModel)
                        .where(
                            WorkflowRunPlanModel.plan_id == candidate.plan_id,
                            WorkflowRunPlanModel.state == WorkflowPlanState.PLANNED.value,
                            WorkflowRunPlanModel.canonical_digest == request.expected_plan_digest,
                            WorkflowRunPlanModel.state_version == row.state_version,
                        )
                        .values(
                            state=candidate.state.value,
                            updated_at=transition.occurred_at,
                            state_version=row.state_version + 1,
                            canonical_digest=candidate.canonical_digest,
                            payload=self._plan_payload(candidate),
                        )
                    ),
                )
                if result.rowcount != 1:
                    await session.rollback()
                    latest = await self.get_by_id(plan_id=candidate.plan_id)
                    return WorkflowPlanCancellationResult(
                        WorkflowPlanCancellationStatus.STATE_CONFLICT, latest
                    )
                session.add(self._transition_model(candidate.plan_id, transition, sequence=1))
                session.add(
                    self._cancellation_idempotency_model(
                        request,
                        operation=operation,
                        scope_id=scope_id,
                    )
                )
                await session.commit()
                return WorkflowPlanCancellationResult(
                    WorkflowPlanCancellationStatus.CANCELLED, candidate
                )
            except IntegrityError:
                await session.rollback()

        return await self._cancellation_result_after_integrity_conflict(request=request)

    async def get_lease_by_plan_id(self, *, plan_id: str) -> WorkflowOrchestrationLease | None:
        async with self._sessions() as session:
            row = cast(
                WorkflowOrchestrationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOrchestrationLeaseModel).where(
                        WorkflowOrchestrationLeaseModel.plan_id == plan_id
                    )
                ),
            )
            return None if row is None else self._lease_from_row(row)

    async def get_materialized_run_by_plan_id(self, *, plan_id: str) -> WorkflowExecutionRun | None:
        async with self._sessions() as session:
            row = cast(
                WorkflowExecutionRunModel | None,
                await session.scalar(
                    select(WorkflowExecutionRunModel).where(
                        WorkflowExecutionRunModel.plan_id == plan_id
                    )
                ),
            )
            return None if row is None else self._materialized_run_from_row(row)

    async def get_run_materialization_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowRunMaterializationIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_materialization_claim(
                session,
                scope=scope,
                worker_subject_id=worker_subject_id,
                idempotency_key=idempotency_key,
            )
            if claim is None:
                return None
            return WorkflowRunMaterializationIdempotencyRecord(
                request_fingerprint=claim.request_fingerprint,
                run=self._materialized_run_from_claim(claim),
            )

    async def materialize_run(
        self, request: WorkflowRunMaterializationRequest
    ) -> WorkflowRunMaterializationResult:
        self._validate_materialization_request(request)
        run = request.candidate
        async with self._sessions() as session:
            replay = await self._materialization_replay(session, request=request)
            if replay is not None:
                return replay

            plan_row = cast(
                WorkflowRunPlanModel | None,
                await session.scalar(
                    select(WorkflowRunPlanModel)
                    .where(WorkflowRunPlanModel.plan_id == run.plan_id)
                    .with_for_update()
                ),
            )
            lease_row = cast(
                WorkflowOrchestrationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOrchestrationLeaseModel)
                    .where(WorkflowOrchestrationLeaseModel.plan_id == run.plan_id)
                    .with_for_update()
                ),
            )
            if not self._materialization_sources_match(
                plan_row=plan_row,
                lease_row=lease_row,
                request=request,
            ):
                await session.rollback()
                return WorkflowRunMaterializationResult(
                    WorkflowRunMaterializationStatus.STATE_CONFLICT,
                    None,
                )

            existing = cast(
                WorkflowExecutionRunModel | None,
                await session.scalar(
                    select(WorkflowExecutionRunModel)
                    .where(WorkflowExecutionRunModel.plan_id == run.plan_id)
                    .with_for_update()
                ),
            )
            if existing is not None:
                await session.rollback()
                return WorkflowRunMaterializationResult(
                    WorkflowRunMaterializationStatus.STATE_CONFLICT,
                    self._materialized_run_from_row(existing),
                )

            try:
                session.add(self._materialized_run_model(run))
                for step in run.step_runs:
                    session.add(self._materialized_step_model(step))
                session.add(self._materialization_claim_model(request))
                await session.commit()
                return WorkflowRunMaterializationResult(
                    WorkflowRunMaterializationStatus.CREATED,
                    run,
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            replay = await self._materialization_replay(session, request=request)
            if replay is not None:
                return replay
        return WorkflowRunMaterializationResult(
            WorkflowRunMaterializationStatus.STATE_CONFLICT,
            None,
        )

    async def list_attempts_by_run_id(self, *, run_id: str) -> tuple[WorkflowExecutionAttempt, ...]:
        statement = (
            select(WorkflowExecutionAttemptModel)
            .where(WorkflowExecutionAttemptModel.run_id == run_id)
            .order_by(
                WorkflowExecutionAttemptModel.created_at,
                WorkflowExecutionAttemptModel.attempt_id,
            )
        )
        async with self._sessions() as session:
            rows = tuple((await session.scalars(statement)).all())
            return tuple(self._attempt_from_row(row) for row in rows)

    async def get_attempt_materialization_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowAttemptMaterializationIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_attempt_materialization_claim(
                session,
                scope=scope,
                worker_subject_id=worker_subject_id,
                idempotency_key=idempotency_key,
            )
            if claim is None:
                return None
            return WorkflowAttemptMaterializationIdempotencyRecord(
                request_fingerprint=claim.request_fingerprint,
                attempt=self._attempt_from_claim(claim),
            )

    async def materialize_attempt(
        self, request: WorkflowAttemptMaterializationRequest
    ) -> WorkflowAttemptMaterializationResult:
        self._validate_attempt_materialization_request(request)
        attempt = request.candidate
        async with self._sessions() as session:
            replay = await self._attempt_materialization_replay(session, request=request)
            if replay is not None:
                return replay

            plan_row = cast(
                WorkflowRunPlanModel | None,
                await session.scalar(
                    select(WorkflowRunPlanModel)
                    .where(WorkflowRunPlanModel.plan_id == attempt.plan_id)
                    .with_for_update()
                ),
            )
            lease_row = cast(
                WorkflowOrchestrationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOrchestrationLeaseModel)
                    .where(WorkflowOrchestrationLeaseModel.plan_id == attempt.plan_id)
                    .with_for_update()
                ),
            )
            run_row = cast(
                WorkflowExecutionRunModel | None,
                await session.scalar(
                    select(WorkflowExecutionRunModel)
                    .where(WorkflowExecutionRunModel.run_id == attempt.run_id)
                    .with_for_update()
                ),
            )
            step_row = cast(
                WorkflowExecutionStepRunModel | None,
                await session.scalar(
                    select(WorkflowExecutionStepRunModel)
                    .where(WorkflowExecutionStepRunModel.step_run_id == attempt.step_run_id)
                    .with_for_update()
                ),
            )
            if not self._attempt_materialization_sources_match(
                plan_row=plan_row,
                lease_row=lease_row,
                run_row=run_row,
                step_row=step_row,
                request=request,
            ):
                await session.rollback()
                return WorkflowAttemptMaterializationResult(
                    WorkflowAttemptMaterializationStatus.STATE_CONFLICT,
                    None,
                )

            existing = cast(
                WorkflowExecutionAttemptModel | None,
                await session.scalar(
                    select(WorkflowExecutionAttemptModel)
                    .where(WorkflowExecutionAttemptModel.step_run_id == attempt.step_run_id)
                    .with_for_update()
                ),
            )
            if existing is not None:
                await session.rollback()
                return WorkflowAttemptMaterializationResult(
                    WorkflowAttemptMaterializationStatus.STATE_CONFLICT,
                    self._attempt_from_row(existing),
                )

            try:
                session.add(self._attempt_model(attempt))
                session.add(self._attempt_materialization_claim_model(request))
                await session.commit()
                return WorkflowAttemptMaterializationResult(
                    WorkflowAttemptMaterializationStatus.CREATED,
                    attempt,
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            replay = await self._attempt_materialization_replay(session, request=request)
            if replay is not None:
                return replay
        return WorkflowAttemptMaterializationResult(
            WorkflowAttemptMaterializationStatus.STATE_CONFLICT,
            None,
        )

    async def list_dispatch_intents_by_run_id(
        self, *, run_id: str
    ) -> tuple[WorkflowDispatchIntent, ...]:
        statement = (
            select(WorkflowDispatchIntentModel)
            .where(WorkflowDispatchIntentModel.run_id == run_id)
            .order_by(
                WorkflowDispatchIntentModel.staged_at,
                WorkflowDispatchIntentModel.dispatch_intent_id,
            )
        )
        async with self._sessions() as session:
            rows = tuple((await session.scalars(statement)).all())
            return tuple(self._dispatch_intent_from_row(row) for row in rows)

    async def list_dispatch_outbox_entries_by_run_id(
        self, *, run_id: str
    ) -> tuple[WorkflowDispatchOutboxEntry, ...]:
        statement = (
            select(WorkflowDispatchOutboxEntryModel)
            .where(WorkflowDispatchOutboxEntryModel.run_id == run_id)
            .order_by(
                WorkflowDispatchOutboxEntryModel.admitted_at,
                WorkflowDispatchOutboxEntryModel.outbox_entry_id,
            )
        )
        async with self._sessions() as session:
            rows = tuple((await session.scalars(statement)).all())
            return tuple(self._dispatch_outbox_from_row(row) for row in rows)

    async def get_outbox_entry_by_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowDispatchOutboxEntry | None:
        async with self._sessions() as session:
            row = await session.get(WorkflowDispatchOutboxEntryModel, outbox_entry_id)
            return None if row is None else self._dispatch_outbox_from_row(row)

    async def get_publication_lease_by_outbox_entry_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowOutboxPublicationLease | None:
        async with self._sessions() as session:
            row = cast(
                WorkflowOutboxPublicationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOutboxPublicationLeaseModel).where(
                        WorkflowOutboxPublicationLeaseModel.outbox_entry_id == outbox_entry_id
                    )
                ),
            )
            return None if row is None else self._publication_lease_from_row(row)

    async def get_publication_lease_acquire_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowOutboxPublicationLeaseAcquireIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_publication_lease_claim(
                session,
                scope=scope,
                publisher_subject_id=publisher_subject_id,
                idempotency_key=idempotency_key,
            )
            return None if claim is None else self._publication_lease_record_from_claim(claim)

    async def acquire_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseAcquireRequest
    ) -> WorkflowOutboxPublicationLeaseAcquireResult:
        self._validate_publication_lease_acquire_request(request)
        candidate = request.candidate
        async with self._sessions() as session:
            replay = await self._publication_lease_acquire_replay(session, request=request)
            if replay is not None:
                return replay

            outbox_row = cast(
                WorkflowDispatchOutboxEntryModel | None,
                await session.scalar(
                    select(WorkflowDispatchOutboxEntryModel)
                    .where(
                        WorkflowDispatchOutboxEntryModel.outbox_entry_id
                        == candidate.outbox_entry_id
                    )
                    .with_for_update()
                ),
            )
            plan_row = cast(
                WorkflowRunPlanModel | None,
                await session.scalar(
                    select(WorkflowRunPlanModel)
                    .where(WorkflowRunPlanModel.plan_id == candidate.plan_id)
                    .with_for_update()
                ),
            )
            orchestration_lease_row = cast(
                WorkflowOrchestrationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOrchestrationLeaseModel)
                    .where(WorkflowOrchestrationLeaseModel.plan_id == candidate.plan_id)
                    .with_for_update()
                ),
            )
            current_row = cast(
                WorkflowOutboxPublicationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOutboxPublicationLeaseModel)
                    .where(
                        WorkflowOutboxPublicationLeaseModel.outbox_entry_id
                        == candidate.outbox_entry_id
                    )
                    .with_for_update()
                ),
            )
            if not self._publication_lease_evidence_matches(
                outbox_row=outbox_row,
                plan_row=plan_row,
                orchestration_lease_row=orchestration_lease_row,
                request=request,
            ):
                await session.rollback()
                return WorkflowOutboxPublicationLeaseAcquireResult(
                    WorkflowOutboxPublicationLeaseAcquireStatus.EVIDENCE_CONFLICT,
                    None,
                )

            current = None if current_row is None else self._publication_lease_from_row(current_row)
            if not self._publication_lease_acquire_generation_matches(
                current=current,
                request=request,
            ):
                await session.rollback()
                return WorkflowOutboxPublicationLeaseAcquireResult(
                    WorkflowOutboxPublicationLeaseAcquireStatus.CONTENDED,
                    current,
                )

            try:
                if current_row is None:
                    session.add(self._publication_lease_model(candidate, version=1))
                else:
                    result = cast(
                        CursorResult[Any],
                        await session.execute(
                            update(WorkflowOutboxPublicationLeaseModel)
                            .where(
                                WorkflowOutboxPublicationLeaseModel.outbox_entry_id
                                == candidate.outbox_entry_id,
                                WorkflowOutboxPublicationLeaseModel.version == current_row.version,
                                WorkflowOutboxPublicationLeaseModel.canonical_digest
                                == current_row.canonical_digest,
                                WorkflowOutboxPublicationLeaseModel.publication_fencing_token
                                == current_row.publication_fencing_token,
                            )
                            .values(
                                **self._publication_lease_values(
                                    candidate,
                                    version=current_row.version + 1,
                                )
                            )
                        ),
                    )
                    if result.rowcount != 1:
                        await session.rollback()
                        return WorkflowOutboxPublicationLeaseAcquireResult(
                            WorkflowOutboxPublicationLeaseAcquireStatus.CONTENDED,
                            current,
                        )
                session.add(self._publication_lease_claim_model(request))
                await session.commit()
                return WorkflowOutboxPublicationLeaseAcquireResult(
                    WorkflowOutboxPublicationLeaseAcquireStatus.ACQUIRED,
                    candidate,
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            replay = await self._publication_lease_acquire_replay(session, request=request)
            if replay is not None:
                return replay
        return WorkflowOutboxPublicationLeaseAcquireResult(
            WorkflowOutboxPublicationLeaseAcquireStatus.CONTENDED,
            None,
        )

    async def heartbeat_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseMutationRequest
    ) -> WorkflowOutboxPublicationLeaseMutationResult:
        return await self._mutate_publication_lease(request)

    async def release_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseMutationRequest
    ) -> WorkflowOutboxPublicationLeaseMutationResult:
        return await self._mutate_publication_lease(request)

    async def get_dispatch_event_envelope_by_outbox_entry_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowDispatchEventEnvelope | None:
        async with self._sessions() as session:
            row = cast(
                WorkflowDispatchEventEnvelopeModel | None,
                await session.scalar(
                    select(WorkflowDispatchEventEnvelopeModel).where(
                        WorkflowDispatchEventEnvelopeModel.outbox_entry_id == outbox_entry_id
                    )
                ),
            )
            return None if row is None else self._dispatch_event_envelope_from_row(row)

    async def get_dispatch_event_envelope_prepare_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowDispatchEventEnvelopePrepareIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_dispatch_event_envelope_claim(
                session,
                scope=scope,
                publisher_subject_id=publisher_subject_id,
                idempotency_key=idempotency_key,
            )
            return None if claim is None else self._dispatch_event_envelope_record_from_claim(claim)

    async def prepare_dispatch_event_envelope(
        self, request: WorkflowDispatchEventEnvelopePrepareRequest
    ) -> WorkflowDispatchEventEnvelopePrepareResult:
        self._validate_dispatch_event_envelope_preparation_request(request)
        candidate = request.candidate
        async with self._sessions() as session:
            replay = await self._dispatch_event_envelope_preparation_replay(
                session,
                request=request,
            )
            if replay is not None:
                return replay

            plan_row = cast(
                WorkflowRunPlanModel | None,
                await session.scalar(
                    select(WorkflowRunPlanModel)
                    .where(WorkflowRunPlanModel.plan_id == candidate.payload.plan_id)
                    .with_for_update()
                ),
            )
            outbox_row = cast(
                WorkflowDispatchOutboxEntryModel | None,
                await session.scalar(
                    select(WorkflowDispatchOutboxEntryModel)
                    .where(
                        WorkflowDispatchOutboxEntryModel.outbox_entry_id
                        == candidate.payload.outbox_entry_id
                    )
                    .with_for_update()
                ),
            )
            orchestration_lease_row = cast(
                WorkflowOrchestrationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOrchestrationLeaseModel)
                    .where(WorkflowOrchestrationLeaseModel.plan_id == candidate.payload.plan_id)
                    .with_for_update()
                ),
            )
            publication_lease_row = cast(
                WorkflowOutboxPublicationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOutboxPublicationLeaseModel)
                    .where(
                        WorkflowOutboxPublicationLeaseModel.outbox_entry_id
                        == candidate.payload.outbox_entry_id
                    )
                    .with_for_update()
                ),
            )
            if not self._dispatch_event_envelope_evidence_matches(
                plan_row=plan_row,
                outbox_row=outbox_row,
                orchestration_lease_row=orchestration_lease_row,
                publication_lease_row=publication_lease_row,
                request=request,
            ):
                await session.rollback()
                return WorkflowDispatchEventEnvelopePrepareResult(
                    WorkflowDispatchEventEnvelopePrepareStatus.EVIDENCE_CONFLICT,
                    None,
                )

            existing = cast(
                WorkflowDispatchEventEnvelopeModel | None,
                await session.scalar(
                    select(WorkflowDispatchEventEnvelopeModel).where(
                        WorkflowDispatchEventEnvelopeModel.outbox_entry_id
                        == candidate.payload.outbox_entry_id
                    )
                ),
            )
            if existing is not None:
                await session.rollback()
                return WorkflowDispatchEventEnvelopePrepareResult(
                    WorkflowDispatchEventEnvelopePrepareStatus.ALREADY_PREPARED,
                    self._dispatch_event_envelope_from_row(existing),
                )

            try:
                session.add(self._dispatch_event_envelope_model(candidate))
                session.add(self._dispatch_event_envelope_claim_model(request))
                await session.commit()
                return WorkflowDispatchEventEnvelopePrepareResult(
                    WorkflowDispatchEventEnvelopePrepareStatus.PREPARED,
                    candidate,
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            replay = await self._dispatch_event_envelope_preparation_replay(
                session,
                request=request,
            )
            if replay is not None:
                return replay
        return WorkflowDispatchEventEnvelopePrepareResult(
            WorkflowDispatchEventEnvelopePrepareStatus.EVIDENCE_CONFLICT,
            None,
        )

    async def get_event_transport_admission_by_event_id(
        self, *, event_id: str
    ) -> WorkflowEventTransportAdmission | None:
        async with self._sessions() as session:
            row = cast(
                WorkflowEventTransportAdmissionModel | None,
                await session.scalar(
                    select(WorkflowEventTransportAdmissionModel).where(
                        WorkflowEventTransportAdmissionModel.event_id == event_id
                    )
                ),
            )
            return None if row is None else self._event_transport_admission_from_row(row)

    async def get_event_transport_admission_by_outbox_entry_id(
        self, *, outbox_entry_id: str
    ) -> WorkflowEventTransportAdmission | None:
        async with self._sessions() as session:
            row = cast(
                WorkflowEventTransportAdmissionModel | None,
                await session.scalar(
                    select(WorkflowEventTransportAdmissionModel).where(
                        WorkflowEventTransportAdmissionModel.outbox_entry_id == outbox_entry_id
                    )
                ),
            )
            return None if row is None else self._event_transport_admission_from_row(row)

    async def get_event_transport_admission_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventTransportAdmissionIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_event_transport_admission_claim(
                session,
                scope=scope,
                publisher_subject_id=publisher_subject_id,
                idempotency_key=idempotency_key,
            )
            return (
                None if claim is None else self._event_transport_admission_record_from_claim(claim)
            )

    async def admit_event_transport(
        self, request: WorkflowEventTransportAdmissionRequest
    ) -> WorkflowEventTransportAdmissionResult:
        self._validate_event_transport_admission_request(request)
        candidate = request.candidate
        async with self._sessions() as session:
            replay = await self._event_transport_admission_replay(session, request=request)
            if replay is not None:
                return replay

            plan_row = cast(
                WorkflowRunPlanModel | None,
                await session.scalar(
                    select(WorkflowRunPlanModel)
                    .where(WorkflowRunPlanModel.plan_id == candidate.plan_id)
                    .with_for_update()
                ),
            )
            outbox_row = cast(
                WorkflowDispatchOutboxEntryModel | None,
                await session.scalar(
                    select(WorkflowDispatchOutboxEntryModel)
                    .where(
                        WorkflowDispatchOutboxEntryModel.outbox_entry_id
                        == candidate.outbox_entry_id
                    )
                    .with_for_update()
                ),
            )
            orchestration_lease_row = cast(
                WorkflowOrchestrationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOrchestrationLeaseModel)
                    .where(WorkflowOrchestrationLeaseModel.plan_id == candidate.plan_id)
                    .with_for_update()
                ),
            )
            publication_lease_row = cast(
                WorkflowOutboxPublicationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOutboxPublicationLeaseModel)
                    .where(
                        WorkflowOutboxPublicationLeaseModel.outbox_entry_id
                        == candidate.outbox_entry_id
                    )
                    .with_for_update()
                ),
            )
            envelope_row = cast(
                WorkflowDispatchEventEnvelopeModel | None,
                await session.scalar(
                    select(WorkflowDispatchEventEnvelopeModel)
                    .where(WorkflowDispatchEventEnvelopeModel.event_id == candidate.event_id)
                    .with_for_update()
                ),
            )
            if not self._event_transport_admission_evidence_matches(
                plan_row=plan_row,
                outbox_row=outbox_row,
                orchestration_lease_row=orchestration_lease_row,
                publication_lease_row=publication_lease_row,
                envelope_row=envelope_row,
                request=request,
            ):
                await session.rollback()
                return WorkflowEventTransportAdmissionResult(
                    WorkflowEventTransportAdmissionStatus.EVIDENCE_CONFLICT,
                    None,
                )

            existing = cast(
                WorkflowEventTransportAdmissionModel | None,
                await session.scalar(
                    select(WorkflowEventTransportAdmissionModel).where(
                        or_(
                            WorkflowEventTransportAdmissionModel.event_id == candidate.event_id,
                            WorkflowEventTransportAdmissionModel.outbox_entry_id
                            == candidate.outbox_entry_id,
                        )
                    )
                ),
            )
            if existing is not None:
                await session.rollback()
                return WorkflowEventTransportAdmissionResult(
                    WorkflowEventTransportAdmissionStatus.ALREADY_ADMITTED,
                    self._event_transport_admission_from_row(existing),
                )

            try:
                session.add(self._event_transport_admission_model(candidate))
                session.add(self._event_transport_admission_claim_model(request))
                await session.commit()
                return WorkflowEventTransportAdmissionResult(
                    WorkflowEventTransportAdmissionStatus.ADMITTED,
                    candidate,
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            replay = await self._event_transport_admission_replay(session, request=request)
            if replay is not None:
                return replay
        return WorkflowEventTransportAdmissionResult(
            WorkflowEventTransportAdmissionStatus.EVIDENCE_CONFLICT,
            None,
        )

    async def get_event_byte_artifact_by_admission_id(
        self, *, admission_id: str
    ) -> WorkflowEventByteArtifact | None:
        async with self._sessions() as session:
            row = cast(
                WorkflowEventByteArtifactModel | None,
                await session.scalar(
                    select(WorkflowEventByteArtifactModel).where(
                        WorkflowEventByteArtifactModel.admission_id == admission_id
                    )
                ),
            )
            return None if row is None else self._event_byte_artifact_from_row(row)

    async def get_event_byte_artifact_by_id(
        self, *, artifact_id: str
    ) -> WorkflowEventByteArtifact | None:
        async with self._sessions() as session:
            row = await session.get(WorkflowEventByteArtifactModel, artifact_id)
            return None if row is None else self._event_byte_artifact_from_row(row)

    async def get_event_byte_artifact_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventByteArtifactIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_event_byte_artifact_claim(
                session,
                scope=scope,
                publisher_subject_id=publisher_subject_id,
                idempotency_key=idempotency_key,
            )
            if claim is None:
                return None
            artifact_row = await session.get(WorkflowEventByteArtifactModel, claim.artifact_id)
            return self._event_byte_artifact_record_from_claim(claim, artifact_row)

    async def materialize_event_byte_artifact(
        self, request: WorkflowEventByteArtifactRequest
    ) -> WorkflowEventByteArtifactResult:
        self._validate_event_byte_artifact_request(request)
        candidate = request.candidate
        async with self._sessions() as session:
            replay = await self._event_byte_artifact_replay(session, request=request)
            if replay is not None:
                return replay

            plan_row = cast(
                WorkflowRunPlanModel | None,
                await session.scalar(
                    select(WorkflowRunPlanModel)
                    .where(WorkflowRunPlanModel.plan_id == candidate.plan_id)
                    .with_for_update()
                ),
            )
            outbox_row = cast(
                WorkflowDispatchOutboxEntryModel | None,
                await session.scalar(
                    select(WorkflowDispatchOutboxEntryModel)
                    .where(
                        WorkflowDispatchOutboxEntryModel.outbox_entry_id
                        == candidate.outbox_entry_id
                    )
                    .with_for_update()
                ),
            )
            orchestration_lease_row = cast(
                WorkflowOrchestrationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOrchestrationLeaseModel)
                    .where(WorkflowOrchestrationLeaseModel.plan_id == candidate.plan_id)
                    .with_for_update()
                ),
            )
            publication_lease_row = cast(
                WorkflowOutboxPublicationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOutboxPublicationLeaseModel)
                    .where(
                        WorkflowOutboxPublicationLeaseModel.outbox_entry_id
                        == candidate.outbox_entry_id
                    )
                    .with_for_update()
                ),
            )
            envelope_row = cast(
                WorkflowDispatchEventEnvelopeModel | None,
                await session.scalar(
                    select(WorkflowDispatchEventEnvelopeModel)
                    .where(WorkflowDispatchEventEnvelopeModel.event_id == candidate.event_id)
                    .with_for_update()
                ),
            )
            admission_row = cast(
                WorkflowEventTransportAdmissionModel | None,
                await session.scalar(
                    select(WorkflowEventTransportAdmissionModel)
                    .where(
                        WorkflowEventTransportAdmissionModel.admission_id == candidate.admission_id
                    )
                    .with_for_update()
                ),
            )
            if not self._event_byte_artifact_evidence_matches(
                plan_row=plan_row,
                outbox_row=outbox_row,
                orchestration_lease_row=orchestration_lease_row,
                publication_lease_row=publication_lease_row,
                envelope_row=envelope_row,
                admission_row=admission_row,
                request=request,
            ):
                await session.rollback()
                return WorkflowEventByteArtifactResult(
                    WorkflowEventByteArtifactStatus.EVIDENCE_CONFLICT, None
                )

            existing = cast(
                WorkflowEventByteArtifactModel | None,
                await session.scalar(
                    select(WorkflowEventByteArtifactModel).where(
                        or_(
                            WorkflowEventByteArtifactModel.admission_id == candidate.admission_id,
                            WorkflowEventByteArtifactModel.event_id == candidate.event_id,
                            WorkflowEventByteArtifactModel.outbox_entry_id
                            == candidate.outbox_entry_id,
                        )
                    )
                ),
            )
            if existing is not None:
                await session.rollback()
                return WorkflowEventByteArtifactResult(
                    WorkflowEventByteArtifactStatus.ALREADY_MATERIALIZED,
                    self._event_byte_artifact_from_row(existing),
                )

            try:
                session.add(self._event_byte_artifact_model(candidate))
                session.add(self._event_byte_artifact_claim_model(request))
                await session.commit()
                return WorkflowEventByteArtifactResult(
                    WorkflowEventByteArtifactStatus.MATERIALIZED, candidate
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            replay = await self._event_byte_artifact_replay(session, request=request)
            if replay is not None:
                return replay
        return WorkflowEventByteArtifactResult(
            WorkflowEventByteArtifactStatus.EVIDENCE_CONFLICT, None
        )

    async def get_event_logical_channel_binding_by_artifact_id(
        self, *, artifact_id: str
    ) -> WorkflowEventLogicalChannelBinding | None:
        async with self._sessions() as session:
            row = cast(
                WorkflowEventLogicalChannelBindingModel | None,
                await session.scalar(
                    select(WorkflowEventLogicalChannelBindingModel).where(
                        WorkflowEventLogicalChannelBindingModel.artifact_id == artifact_id
                    )
                ),
            )
            return None if row is None else self._event_logical_channel_binding_from_row(row)

    async def get_event_logical_channel_binding_request(
        self,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventLogicalChannelBindingIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_event_logical_channel_binding_claim(
                session,
                scope=scope,
                publisher_subject_id=publisher_subject_id,
                idempotency_key=idempotency_key,
            )
            if claim is None:
                return None
            binding_row = await session.get(
                WorkflowEventLogicalChannelBindingModel, claim.binding_id
            )
            return self._event_logical_channel_binding_record_from_claim(claim, binding_row)

    async def bind_event_logical_channel(
        self, request: WorkflowEventLogicalChannelBindingRequest
    ) -> WorkflowEventLogicalChannelBindingResult:
        self._validate_event_logical_channel_binding_request(request)
        candidate = request.candidate
        async with self._sessions() as session:
            replay = await self._event_logical_channel_binding_replay(session, request=request)
            if replay is not None:
                return replay

            plan_row = cast(
                WorkflowRunPlanModel | None,
                await session.scalar(
                    select(WorkflowRunPlanModel)
                    .where(WorkflowRunPlanModel.plan_id == candidate.plan_id)
                    .with_for_update()
                ),
            )
            outbox_row = cast(
                WorkflowDispatchOutboxEntryModel | None,
                await session.scalar(
                    select(WorkflowDispatchOutboxEntryModel)
                    .where(
                        WorkflowDispatchOutboxEntryModel.outbox_entry_id
                        == candidate.outbox_entry_id
                    )
                    .with_for_update()
                ),
            )
            orchestration_lease_row = cast(
                WorkflowOrchestrationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOrchestrationLeaseModel)
                    .where(WorkflowOrchestrationLeaseModel.plan_id == candidate.plan_id)
                    .with_for_update()
                ),
            )
            publication_lease_row = cast(
                WorkflowOutboxPublicationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOutboxPublicationLeaseModel)
                    .where(
                        WorkflowOutboxPublicationLeaseModel.outbox_entry_id
                        == candidate.outbox_entry_id
                    )
                    .with_for_update()
                ),
            )
            envelope_row = cast(
                WorkflowDispatchEventEnvelopeModel | None,
                await session.scalar(
                    select(WorkflowDispatchEventEnvelopeModel)
                    .where(WorkflowDispatchEventEnvelopeModel.event_id == candidate.event_id)
                    .with_for_update()
                ),
            )
            admission_row = cast(
                WorkflowEventTransportAdmissionModel | None,
                await session.scalar(
                    select(WorkflowEventTransportAdmissionModel)
                    .where(
                        WorkflowEventTransportAdmissionModel.admission_id == candidate.admission_id
                    )
                    .with_for_update()
                ),
            )
            artifact_row = cast(
                WorkflowEventByteArtifactModel | None,
                await session.scalar(
                    select(WorkflowEventByteArtifactModel)
                    .where(WorkflowEventByteArtifactModel.artifact_id == candidate.artifact_id)
                    .with_for_update()
                ),
            )
            if not self._event_logical_channel_binding_evidence_matches(
                plan_row=plan_row,
                outbox_row=outbox_row,
                orchestration_lease_row=orchestration_lease_row,
                publication_lease_row=publication_lease_row,
                envelope_row=envelope_row,
                admission_row=admission_row,
                artifact_row=artifact_row,
                request=request,
            ):
                await session.rollback()
                return WorkflowEventLogicalChannelBindingResult(
                    WorkflowEventLogicalChannelBindingStatus.EVIDENCE_CONFLICT, None
                )

            existing = cast(
                WorkflowEventLogicalChannelBindingModel | None,
                await session.scalar(
                    select(WorkflowEventLogicalChannelBindingModel).where(
                        WorkflowEventLogicalChannelBindingModel.artifact_id == candidate.artifact_id
                    )
                ),
            )
            if existing is not None:
                await session.rollback()
                return WorkflowEventLogicalChannelBindingResult(
                    WorkflowEventLogicalChannelBindingStatus.ALREADY_BOUND,
                    self._event_logical_channel_binding_from_row(existing),
                )

            try:
                session.add(self._event_logical_channel_binding_model(candidate))
                session.add(self._event_logical_channel_binding_claim_model(request))
                await session.commit()
                return WorkflowEventLogicalChannelBindingResult(
                    WorkflowEventLogicalChannelBindingStatus.BOUND, candidate
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            replay = await self._event_logical_channel_binding_replay(session, request=request)
            if replay is not None:
                return replay
        return WorkflowEventLogicalChannelBindingResult(
            WorkflowEventLogicalChannelBindingStatus.EVIDENCE_CONFLICT, None
        )

    async def get_transport_profile_snapshot(
        self,
        *,
        transport_profile_id: str,
        transport_profile_revision: str,
    ) -> EventPhysicalTransportProfileSnapshot | None:
        async with self._sessions() as session:
            row = cast(
                EventPhysicalTransportProfileSnapshotModel | None,
                await session.scalar(
                    select(EventPhysicalTransportProfileSnapshotModel).where(
                        EventPhysicalTransportProfileSnapshotModel.transport_profile_id
                        == transport_profile_id,
                        EventPhysicalTransportProfileSnapshotModel.transport_profile_revision
                        == transport_profile_revision,
                    )
                ),
            )
            return None if row is None else self._transport_profile_snapshot_from_row(row)

    async def get_transport_profile_snapshot_request(
        self,
        *,
        scope: WorkflowScope,
        snapshotter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowTransportProfileSnapshotIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_transport_profile_snapshot_claim(
                session,
                scope=scope,
                snapshotter_subject_id=snapshotter_subject_id,
                idempotency_key=idempotency_key,
            )
            if claim is None:
                return None
            snapshot_row = await session.get(
                EventPhysicalTransportProfileSnapshotModel, claim.snapshot_id
            )
            return self._transport_profile_snapshot_record_from_claim(claim, snapshot_row)

    async def snapshot_transport_profile(
        self, request: WorkflowTransportProfileSnapshotRequest
    ) -> WorkflowTransportProfileSnapshotResult:
        self._validate_transport_profile_snapshot_request(request)
        candidate = request.candidate
        async with self._sessions() as session:
            replay = await self._transport_profile_snapshot_replay(session, request=request)
            if replay is not None:
                return replay

            existing = cast(
                EventPhysicalTransportProfileSnapshotModel | None,
                await session.scalar(
                    select(EventPhysicalTransportProfileSnapshotModel)
                    .where(
                        EventPhysicalTransportProfileSnapshotModel.transport_profile_id
                        == candidate.transport_profile_id,
                        EventPhysicalTransportProfileSnapshotModel.transport_profile_revision
                        == candidate.transport_profile_revision,
                    )
                    .with_for_update()
                ),
            )
            if existing is not None:
                await session.rollback()
                return WorkflowTransportProfileSnapshotResult(
                    WorkflowTransportProfileSnapshotStatus.ALREADY_SNAPSHOTTED,
                    self._transport_profile_snapshot_from_row(existing),
                )

            if not self._transport_profile_snapshot_evidence_matches(request):
                await session.rollback()
                return WorkflowTransportProfileSnapshotResult(
                    WorkflowTransportProfileSnapshotStatus.SOURCE_CONFLICT, None
                )

            try:
                session.add(self._transport_profile_snapshot_model(candidate))
                session.add(self._transport_profile_snapshot_claim_model(request))
                await session.commit()
                return WorkflowTransportProfileSnapshotResult(
                    WorkflowTransportProfileSnapshotStatus.SNAPSHOTTED, candidate
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            replay = await self._transport_profile_snapshot_replay(session, request=request)
            if replay is not None:
                return replay
            existing = cast(
                EventPhysicalTransportProfileSnapshotModel | None,
                await session.scalar(
                    select(EventPhysicalTransportProfileSnapshotModel).where(
                        EventPhysicalTransportProfileSnapshotModel.transport_profile_id
                        == candidate.transport_profile_id,
                        EventPhysicalTransportProfileSnapshotModel.transport_profile_revision
                        == candidate.transport_profile_revision,
                    )
                ),
            )
            if existing is not None:
                return WorkflowTransportProfileSnapshotResult(
                    WorkflowTransportProfileSnapshotStatus.ALREADY_SNAPSHOTTED,
                    self._transport_profile_snapshot_from_row(existing),
                )
        return WorkflowTransportProfileSnapshotResult(
            WorkflowTransportProfileSnapshotStatus.SOURCE_CONFLICT, None
        )

    async def get_transport_route_snapshot(
        self,
        *,
        route_id: str,
        route_revision: str,
    ) -> EventPhysicalTransportRouteSnapshot | None:
        async with self._sessions() as session:
            row = cast(
                EventPhysicalTransportRouteSnapshotModel | None,
                await session.scalar(
                    select(EventPhysicalTransportRouteSnapshotModel).where(
                        EventPhysicalTransportRouteSnapshotModel.route_id == route_id,
                        EventPhysicalTransportRouteSnapshotModel.route_revision == route_revision,
                    )
                ),
            )
            return None if row is None else self._transport_route_snapshot_from_row(row)

    async def get_transport_route_snapshot_request(
        self,
        *,
        scope: WorkflowScope,
        snapshotter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowTransportRouteSnapshotIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_transport_route_snapshot_claim(
                session,
                scope=scope,
                snapshotter_subject_id=snapshotter_subject_id,
                idempotency_key=idempotency_key,
            )
            if claim is None:
                return None
            snapshot_row = await session.get(
                EventPhysicalTransportRouteSnapshotModel, claim.snapshot_id
            )
            return self._transport_route_snapshot_record_from_claim(claim, snapshot_row)

    async def snapshot_transport_route(
        self, request: WorkflowTransportRouteSnapshotRequest
    ) -> WorkflowTransportRouteSnapshotResult:
        self._validate_transport_route_snapshot_request(request)
        candidate = request.candidate
        async with self._sessions() as session:
            replay = await self._transport_route_snapshot_replay(session, request=request)
            if replay is not None:
                return replay

            existing = cast(
                EventPhysicalTransportRouteSnapshotModel | None,
                await session.scalar(
                    select(EventPhysicalTransportRouteSnapshotModel)
                    .where(
                        EventPhysicalTransportRouteSnapshotModel.route_id == candidate.route_id,
                        EventPhysicalTransportRouteSnapshotModel.route_revision
                        == candidate.route_revision,
                    )
                    .with_for_update()
                ),
            )
            if existing is not None:
                await session.rollback()
                return WorkflowTransportRouteSnapshotResult(
                    WorkflowTransportRouteSnapshotStatus.ALREADY_SNAPSHOTTED,
                    self._transport_route_snapshot_from_row(existing),
                )

            if not self._transport_route_snapshot_evidence_matches(request):
                await session.rollback()
                return WorkflowTransportRouteSnapshotResult(
                    WorkflowTransportRouteSnapshotStatus.SOURCE_CONFLICT, None
                )

            try:
                session.add(self._transport_route_snapshot_model(candidate))
                session.add(self._transport_route_snapshot_claim_model(request))
                await session.commit()
                return WorkflowTransportRouteSnapshotResult(
                    WorkflowTransportRouteSnapshotStatus.SNAPSHOTTED, candidate
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            replay = await self._transport_route_snapshot_replay(session, request=request)
            if replay is not None:
                return replay
            existing = cast(
                EventPhysicalTransportRouteSnapshotModel | None,
                await session.scalar(
                    select(EventPhysicalTransportRouteSnapshotModel).where(
                        EventPhysicalTransportRouteSnapshotModel.route_id == candidate.route_id,
                        EventPhysicalTransportRouteSnapshotModel.route_revision
                        == candidate.route_revision,
                    )
                ),
            )
            if existing is not None:
                return WorkflowTransportRouteSnapshotResult(
                    WorkflowTransportRouteSnapshotStatus.ALREADY_SNAPSHOTTED,
                    self._transport_route_snapshot_from_row(existing),
                )
        return WorkflowTransportRouteSnapshotResult(
            WorkflowTransportRouteSnapshotStatus.SOURCE_CONFLICT, None
        )

    async def synchronize_credential_assignments(
        self, assignments: tuple[DeploymentPhysicalTransportCredentialAssignment, ...]
    ) -> None:
        """Append exact deployment-owned revisions without replacing history."""

        if not assignments:
            return
        async with self._sessions() as session:
            for assignment_id in sorted({assignment.assignment_id for assignment in assignments}):
                await session.scalar(
                    select(
                        func.pg_advisory_xact_lock(
                            self._credential_assignment_registry_lock_id(assignment_id)
                        )
                    )
                )
            for assignment in assignments:
                existing = await session.get(
                    DeploymentEventTransportCredentialAssignmentModel,
                    (assignment.assignment_id, assignment.assignment_revision),
                )
                if existing is not None:
                    if self._credential_assignment_from_row(existing) != assignment:
                        await session.rollback()
                        self._credential_assignment_contract_violation()
                    continue
                session.add(self._credential_assignment_model(assignment))
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise WorkflowTransportCredentialAssignmentSnapshotError(
                    "workflow_transport_credential_assignment_registry_conflict",
                    "Credential-assignment registry evidence conflicts with durable history.",
                ) from exc

    async def get_active_credential_assignment(
        self,
        *,
        assignment_id: str,
        assignment_revision: str,
    ) -> DeploymentPhysicalTransportCredentialAssignment | None:
        async with self._sessions() as session:
            rows = tuple(
                (
                    await session.scalars(
                        select(DeploymentEventTransportCredentialAssignmentModel).where(
                            DeploymentEventTransportCredentialAssignmentModel.assignment_id
                            == assignment_id
                        )
                    )
                ).all()
            )
            try:
                assignment = select_deployment_physical_transport_credential_assignment_head(
                    tuple(self._credential_assignment_from_row(row) for row in rows)
                )
            except ValueError:
                self._credential_assignment_contract_violation()
            now = cast(datetime, await session.scalar(select(func.clock_timestamp())))
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
        async with self._sessions() as session:
            row = cast(
                EventPhysicalTransportCredentialAssignmentSnapshotModel | None,
                await session.scalar(
                    select(EventPhysicalTransportCredentialAssignmentSnapshotModel).where(
                        EventPhysicalTransportCredentialAssignmentSnapshotModel.assignment_id
                        == assignment_id,
                        EventPhysicalTransportCredentialAssignmentSnapshotModel.assignment_revision
                        == assignment_revision,
                    )
                ),
            )
            return None if row is None else self._credential_assignment_snapshot_from_row(row)

    async def get_credential_assignment_snapshot_by_id(
        self, *, snapshot_id: str
    ) -> EventPhysicalTransportCredentialAssignmentSnapshot | None:
        async with self._sessions() as session:
            row = await session.get(
                EventPhysicalTransportCredentialAssignmentSnapshotModel, snapshot_id
            )
            return None if row is None else self._credential_assignment_snapshot_from_row(row)

    async def list_credential_assignment_snapshots(
        self,
        *,
        scope: WorkflowScope,
        limit: int = 256,
    ) -> tuple[EventPhysicalTransportCredentialAssignmentSnapshot, ...]:
        if not 1 <= limit <= 256:
            raise ValueError("credential-assignment snapshot limit is invalid")
        async with self._sessions() as session:
            rows = tuple(
                (
                    await session.scalars(
                        select(EventPhysicalTransportCredentialAssignmentSnapshotModel)
                        .where(
                            EventPhysicalTransportCredentialAssignmentSnapshotModel.organization_id
                            == scope.organization_id,
                            EventPhysicalTransportCredentialAssignmentSnapshotModel.environment_id
                            == scope.environment_id,
                            EventPhysicalTransportCredentialAssignmentSnapshotModel.site_id
                            == scope.site_id,
                        )
                        .order_by(
                            EventPhysicalTransportCredentialAssignmentSnapshotModel.assignment_id,
                            EventPhysicalTransportCredentialAssignmentSnapshotModel.assignment_revision,
                        )
                        .limit(limit)
                    )
                ).all()
            )
            return tuple(self._credential_assignment_snapshot_from_row(row) for row in rows)

    async def get_credential_assignment_snapshot_request(
        self,
        *,
        scope: WorkflowScope,
        snapshotter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowTransportCredentialAssignmentSnapshotIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_credential_assignment_snapshot_claim(
                session,
                scope=scope,
                snapshotter_subject_id=snapshotter_subject_id,
                idempotency_key=idempotency_key,
            )
            if claim is None:
                return None
            snapshot_row = await session.get(
                EventPhysicalTransportCredentialAssignmentSnapshotModel,
                claim.snapshot_id,
            )
            return self._credential_assignment_snapshot_record_from_claim(claim, snapshot_row)

    async def snapshot_credential_assignment(
        self,
        request: WorkflowTransportCredentialAssignmentSnapshotRequest,
    ) -> WorkflowTransportCredentialAssignmentSnapshotResult:
        validate_workflow_transport_credential_assignment_snapshot_request(request)
        candidate = request.candidate
        async with self._sessions() as session:
            replay = await self._credential_assignment_snapshot_replay(session, request=request)
            if replay is not None:
                return replay

            await session.scalar(
                select(
                    func.pg_advisory_xact_lock(
                        self._credential_assignment_registry_lock_id(
                            request.expected_source_assignment_id
                        )
                    )
                )
            )
            source_rows = tuple(
                (
                    await session.scalars(
                        select(DeploymentEventTransportCredentialAssignmentModel)
                        .where(
                            DeploymentEventTransportCredentialAssignmentModel.assignment_id
                            == request.expected_source_assignment_id
                        )
                        .with_for_update()
                    )
                ).all()
            )
            try:
                source_head = select_deployment_physical_transport_credential_assignment_head(
                    tuple(self._credential_assignment_from_row(row) for row in source_rows)
                )
            except ValueError:
                self._credential_assignment_contract_violation()
            source_row = next(
                (
                    row
                    for row in source_rows
                    if source_head is not None
                    and source_head.assignment_revision
                    == request.expected_source_assignment_revision
                    and row.assignment_revision == source_head.assignment_revision
                ),
                None,
            )
            route_row = cast(
                EventPhysicalTransportRouteSnapshotModel | None,
                await session.scalar(
                    select(EventPhysicalTransportRouteSnapshotModel)
                    .where(
                        EventPhysicalTransportRouteSnapshotModel.snapshot_id
                        == candidate.route_snapshot_id
                    )
                    .with_for_update()
                ),
            )
            replay = await self._credential_assignment_snapshot_replay(session, request=request)
            if replay is not None:
                await session.rollback()
                return replay
            captured_at = cast(datetime, await session.scalar(select(func.clock_timestamp())))
            if not self._credential_assignment_snapshot_evidence_matches(
                request=request,
                source_row=source_row,
                route_row=route_row,
                captured_at=captured_at,
            ):
                await session.rollback()
                return WorkflowTransportCredentialAssignmentSnapshotResult(
                    WorkflowTransportCredentialAssignmentSnapshotStatus.SOURCE_CONFLICT,
                    None,
                )

            existing = cast(
                EventPhysicalTransportCredentialAssignmentSnapshotModel | None,
                await session.scalar(
                    select(EventPhysicalTransportCredentialAssignmentSnapshotModel).where(
                        EventPhysicalTransportCredentialAssignmentSnapshotModel.assignment_id
                        == candidate.assignment_id,
                        EventPhysicalTransportCredentialAssignmentSnapshotModel.assignment_revision
                        == candidate.assignment_revision,
                    )
                ),
            )
            if existing is not None:
                await session.rollback()
                return WorkflowTransportCredentialAssignmentSnapshotResult(
                    WorkflowTransportCredentialAssignmentSnapshotStatus.ALREADY_SNAPSHOTTED,
                    self._credential_assignment_snapshot_from_row(existing),
                )

            try:
                await request.required_precommit_audit()
            except Exception:
                await session.rollback()
                return WorkflowTransportCredentialAssignmentSnapshotResult(
                    WorkflowTransportCredentialAssignmentSnapshotStatus.PRECOMMIT_AUDIT_FAILED,
                    None,
                )
            try:
                session.add(self._credential_assignment_snapshot_model(candidate))
                await session.flush()
                session.add(self._credential_assignment_snapshot_claim_model(request))
                await session.commit()
                return WorkflowTransportCredentialAssignmentSnapshotResult(
                    WorkflowTransportCredentialAssignmentSnapshotStatus.SNAPSHOTTED,
                    candidate,
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            replay = await self._credential_assignment_snapshot_replay(session, request=request)
            if replay is not None:
                return replay
            existing = cast(
                EventPhysicalTransportCredentialAssignmentSnapshotModel | None,
                await session.scalar(
                    select(EventPhysicalTransportCredentialAssignmentSnapshotModel).where(
                        EventPhysicalTransportCredentialAssignmentSnapshotModel.assignment_id
                        == candidate.assignment_id,
                        EventPhysicalTransportCredentialAssignmentSnapshotModel.assignment_revision
                        == candidate.assignment_revision,
                    )
                ),
            )
            if existing is not None:
                return WorkflowTransportCredentialAssignmentSnapshotResult(
                    WorkflowTransportCredentialAssignmentSnapshotStatus.ALREADY_SNAPSHOTTED,
                    self._credential_assignment_snapshot_from_row(existing),
                )
        return WorkflowTransportCredentialAssignmentSnapshotResult(
            WorkflowTransportCredentialAssignmentSnapshotStatus.SOURCE_CONFLICT,
            None,
        )

    async def get_event_logical_channel_binding_by_id(
        self, *, binding_id: str
    ) -> WorkflowEventLogicalChannelBinding | None:
        async with self._sessions() as session:
            row = await session.get(WorkflowEventLogicalChannelBindingModel, binding_id)
            return None if row is None else self._event_logical_channel_binding_from_row(row)

    async def get_transport_profile_snapshot_by_id(
        self, *, snapshot_id: str
    ) -> EventPhysicalTransportProfileSnapshot | None:
        async with self._sessions() as session:
            row = await session.get(EventPhysicalTransportProfileSnapshotModel, snapshot_id)
            return None if row is None else self._transport_profile_snapshot_from_row(row)

    async def get_transport_compatibility_admission(
        self,
        *,
        logical_channel_binding_id: str,
        transport_profile_snapshot_id: str,
        policy_digest: str,
    ) -> WorkflowEventTransportCompatibilityAdmission | None:
        async with self._sessions() as session:
            row = cast(
                WorkflowEventTransportCompatibilityAdmissionModel | None,
                await session.scalar(
                    select(WorkflowEventTransportCompatibilityAdmissionModel).where(
                        WorkflowEventTransportCompatibilityAdmissionModel.logical_channel_binding_id
                        == logical_channel_binding_id,
                        WorkflowEventTransportCompatibilityAdmissionModel.transport_profile_snapshot_id
                        == transport_profile_snapshot_id,
                        WorkflowEventTransportCompatibilityAdmissionModel.policy_digest
                        == policy_digest,
                    )
                ),
            )
            return None if row is None else self._transport_compatibility_admission_from_row(row)

    async def list_transport_compatibility_admissions_by_binding(
        self, *, logical_channel_binding_id: str
    ) -> tuple[WorkflowEventTransportCompatibilityAdmission, ...]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(WorkflowEventTransportCompatibilityAdmissionModel)
                    .where(
                        WorkflowEventTransportCompatibilityAdmissionModel.logical_channel_binding_id
                        == logical_channel_binding_id
                    )
                    .order_by(
                        WorkflowEventTransportCompatibilityAdmissionModel.transport_profile_snapshot_id,
                        WorkflowEventTransportCompatibilityAdmissionModel.policy_digest,
                        WorkflowEventTransportCompatibilityAdmissionModel.compatibility_admission_id,
                    )
                )
            ).all()
            return tuple(self._transport_compatibility_admission_from_row(row) for row in rows)

    async def get_transport_compatibility_admission_request(
        self,
        *,
        scope: WorkflowScope,
        admitter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventTransportCompatibilityAdmissionIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_transport_compatibility_admission_claim(
                session,
                scope=scope,
                admitter_subject_id=admitter_subject_id,
                idempotency_key=idempotency_key,
            )
            if claim is None:
                return None
            admission_row = await session.get(
                WorkflowEventTransportCompatibilityAdmissionModel,
                claim.compatibility_admission_id,
            )
            return self._transport_compatibility_admission_record_from_claim(claim, admission_row)

    async def admit_transport_compatibility(
        self, request: WorkflowEventTransportCompatibilityAdmissionRequest
    ) -> WorkflowEventTransportCompatibilityAdmissionResult:
        self._validate_transport_compatibility_admission_request(request)
        candidate = request.candidate
        async with self._sessions() as session:
            replay = await self._transport_compatibility_admission_replay(session, request=request)
            if replay is not None:
                return replay

            # Every caller locks the two immutable source types in this fixed
            # order, preventing inverse lock acquisition across competing pairs.
            binding_row = cast(
                WorkflowEventLogicalChannelBindingModel | None,
                await session.scalar(
                    select(WorkflowEventLogicalChannelBindingModel)
                    .where(
                        WorkflowEventLogicalChannelBindingModel.binding_id
                        == candidate.logical_channel_binding_id
                    )
                    .with_for_update()
                ),
            )
            profile_row = cast(
                EventPhysicalTransportProfileSnapshotModel | None,
                await session.scalar(
                    select(EventPhysicalTransportProfileSnapshotModel)
                    .where(
                        EventPhysicalTransportProfileSnapshotModel.snapshot_id
                        == candidate.transport_profile_snapshot_id
                    )
                    .with_for_update()
                ),
            )
            if not self._transport_compatibility_admission_evidence_matches(
                binding_row=binding_row,
                profile_row=profile_row,
                request=request,
            ):
                await session.rollback()
                return WorkflowEventTransportCompatibilityAdmissionResult(
                    WorkflowEventTransportCompatibilityAdmissionStatus.EVIDENCE_CONFLICT,
                    None,
                )

            existing = cast(
                WorkflowEventTransportCompatibilityAdmissionModel | None,
                await session.scalar(
                    select(WorkflowEventTransportCompatibilityAdmissionModel).where(
                        WorkflowEventTransportCompatibilityAdmissionModel.logical_channel_binding_id
                        == candidate.logical_channel_binding_id,
                        WorkflowEventTransportCompatibilityAdmissionModel.transport_profile_snapshot_id
                        == candidate.transport_profile_snapshot_id,
                        WorkflowEventTransportCompatibilityAdmissionModel.policy_digest
                        == candidate.policy_digest,
                    )
                ),
            )
            if existing is not None:
                await session.rollback()
                return WorkflowEventTransportCompatibilityAdmissionResult(
                    WorkflowEventTransportCompatibilityAdmissionStatus.ALREADY_ADMITTED,
                    self._transport_compatibility_admission_from_row(existing),
                )

            try:
                session.add(self._transport_compatibility_admission_model(candidate))
                session.add(self._transport_compatibility_admission_claim_model(request))
                await session.commit()
                return WorkflowEventTransportCompatibilityAdmissionResult(
                    WorkflowEventTransportCompatibilityAdmissionStatus.ADMITTED,
                    candidate,
                )
            except IntegrityError:
                await session.rollback()

        # A competing transaction may have committed either the same scoped
        # request or another immutable identity while this transaction waited.
        async with self._sessions() as session:
            replay = await self._transport_compatibility_admission_replay(session, request=request)
            if replay is not None:
                return replay
            existing = cast(
                WorkflowEventTransportCompatibilityAdmissionModel | None,
                await session.scalar(
                    select(WorkflowEventTransportCompatibilityAdmissionModel).where(
                        WorkflowEventTransportCompatibilityAdmissionModel.logical_channel_binding_id
                        == candidate.logical_channel_binding_id,
                        WorkflowEventTransportCompatibilityAdmissionModel.transport_profile_snapshot_id
                        == candidate.transport_profile_snapshot_id,
                        WorkflowEventTransportCompatibilityAdmissionModel.policy_digest
                        == candidate.policy_digest,
                    )
                ),
            )
            if existing is not None:
                return WorkflowEventTransportCompatibilityAdmissionResult(
                    WorkflowEventTransportCompatibilityAdmissionStatus.ALREADY_ADMITTED,
                    self._transport_compatibility_admission_from_row(existing),
                )
        return WorkflowEventTransportCompatibilityAdmissionResult(
            WorkflowEventTransportCompatibilityAdmissionStatus.EVIDENCE_CONFLICT,
            None,
        )

    async def get_transport_compatibility_admission_by_id(
        self, *, admission_id: str
    ) -> WorkflowEventTransportCompatibilityAdmission | None:
        async with self._sessions() as session:
            row = await session.get(WorkflowEventTransportCompatibilityAdmissionModel, admission_id)
            return None if row is None else self._transport_compatibility_admission_from_row(row)

    async def get_transport_route_snapshot_by_id(
        self, *, snapshot_id: str
    ) -> EventPhysicalTransportRouteSnapshot | None:
        async with self._sessions() as session:
            row = await session.get(EventPhysicalTransportRouteSnapshotModel, snapshot_id)
            return None if row is None else self._transport_route_snapshot_from_row(row)

    async def get_physical_transport_route_binding(
        self, *, logical_channel_binding_id: str
    ) -> WorkflowEventPhysicalTransportRouteBinding | None:
        async with self._sessions() as session:
            row = cast(
                WorkflowEventPhysicalTransportRouteBindingModel | None,
                await session.scalar(
                    select(WorkflowEventPhysicalTransportRouteBindingModel).where(
                        WorkflowEventPhysicalTransportRouteBindingModel.logical_channel_binding_id
                        == logical_channel_binding_id
                    )
                ),
            )
            return None if row is None else self._physical_transport_route_binding_from_row(row)

    async def list_physical_transport_route_bindings(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowEventPhysicalTransportRouteBinding, ...]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(WorkflowEventPhysicalTransportRouteBindingModel)
                    .where(
                        WorkflowEventPhysicalTransportRouteBindingModel.organization_id
                        == scope.organization_id,
                        WorkflowEventPhysicalTransportRouteBindingModel.environment_id
                        == scope.environment_id,
                        WorkflowEventPhysicalTransportRouteBindingModel.site_id == scope.site_id,
                    )
                    .order_by(WorkflowEventPhysicalTransportRouteBindingModel.binding_id)
                    .limit(limit)
                )
            ).all()
            return tuple(self._physical_transport_route_binding_from_row(row) for row in rows)

    async def get_physical_transport_route_binding_request(
        self,
        *,
        scope: WorkflowScope,
        binder_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventPhysicalTransportRouteBindingIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_physical_transport_route_binding_claim(
                session,
                scope=scope,
                binder_subject_id=binder_subject_id,
                idempotency_key=idempotency_key,
            )
            if claim is None:
                return None
            binding_row = await session.get(
                WorkflowEventPhysicalTransportRouteBindingModel, claim.binding_id
            )
            return self._physical_transport_route_binding_record_from_claim(claim, binding_row)

    async def bind_physical_transport_route(
        self, request: WorkflowEventPhysicalTransportRouteBindingRequest
    ) -> WorkflowEventPhysicalTransportRouteBindingResult:
        self._validate_physical_transport_route_binding_request(request)
        candidate = request.candidate
        async with self._sessions() as session:
            replay = await self._physical_transport_route_binding_replay(session, request=request)
            if replay is not None:
                return replay

            # This order is part of the repository contract. Every physical
            # binding transaction acquires these exact immutable rows in the
            # same sequence to avoid inverse lock-order deadlocks.
            logical_row = cast(
                WorkflowEventLogicalChannelBindingModel | None,
                await session.scalar(
                    select(WorkflowEventLogicalChannelBindingModel)
                    .where(
                        WorkflowEventLogicalChannelBindingModel.binding_id
                        == candidate.logical_channel_binding_id
                    )
                    .with_for_update()
                ),
            )
            profile_row = cast(
                EventPhysicalTransportProfileSnapshotModel | None,
                await session.scalar(
                    select(EventPhysicalTransportProfileSnapshotModel)
                    .where(
                        EventPhysicalTransportProfileSnapshotModel.snapshot_id
                        == candidate.transport_profile_snapshot_id
                    )
                    .with_for_update()
                ),
            )
            admission_row = cast(
                WorkflowEventTransportCompatibilityAdmissionModel | None,
                await session.scalar(
                    select(WorkflowEventTransportCompatibilityAdmissionModel)
                    .where(
                        WorkflowEventTransportCompatibilityAdmissionModel.compatibility_admission_id
                        == candidate.transport_compatibility_admission_id
                    )
                    .with_for_update()
                ),
            )
            route_row = cast(
                EventPhysicalTransportRouteSnapshotModel | None,
                await session.scalar(
                    select(EventPhysicalTransportRouteSnapshotModel)
                    .where(
                        EventPhysicalTransportRouteSnapshotModel.snapshot_id
                        == candidate.transport_route_snapshot_id
                    )
                    .with_for_update()
                ),
            )
            if not self._physical_transport_route_binding_evidence_matches(
                logical_row=logical_row,
                profile_row=profile_row,
                admission_row=admission_row,
                route_row=route_row,
                request=request,
            ):
                await session.rollback()
                return WorkflowEventPhysicalTransportRouteBindingResult(
                    WorkflowEventPhysicalTransportRouteBindingStatus.EVIDENCE_CONFLICT,
                    None,
                )

            # A concurrent exact request may have committed its claim while
            # this transaction waited on the fixed-order source locks.
            replay = await self._physical_transport_route_binding_replay(session, request=request)
            if replay is not None:
                await session.rollback()
                return replay

            existing = cast(
                WorkflowEventPhysicalTransportRouteBindingModel | None,
                await session.scalar(
                    select(WorkflowEventPhysicalTransportRouteBindingModel).where(
                        WorkflowEventPhysicalTransportRouteBindingModel.logical_channel_binding_id
                        == candidate.logical_channel_binding_id
                    )
                ),
            )
            if existing is not None:
                await session.rollback()
                return WorkflowEventPhysicalTransportRouteBindingResult(
                    WorkflowEventPhysicalTransportRouteBindingStatus.ALREADY_BOUND,
                    self._physical_transport_route_binding_from_row(existing),
                )

            try:
                session.add(self._physical_transport_route_binding_model(candidate))
                await session.flush()
                session.add(self._physical_transport_route_binding_claim_model(request))
                await session.commit()
                return WorkflowEventPhysicalTransportRouteBindingResult(
                    WorkflowEventPhysicalTransportRouteBindingStatus.BOUND,
                    candidate,
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            replay = await self._physical_transport_route_binding_replay(session, request=request)
            if replay is not None:
                return replay
            existing = cast(
                WorkflowEventPhysicalTransportRouteBindingModel | None,
                await session.scalar(
                    select(WorkflowEventPhysicalTransportRouteBindingModel).where(
                        WorkflowEventPhysicalTransportRouteBindingModel.logical_channel_binding_id
                        == candidate.logical_channel_binding_id
                    )
                ),
            )
            if existing is not None:
                return WorkflowEventPhysicalTransportRouteBindingResult(
                    WorkflowEventPhysicalTransportRouteBindingStatus.ALREADY_BOUND,
                    self._physical_transport_route_binding_from_row(existing),
                )
        return WorkflowEventPhysicalTransportRouteBindingResult(
            WorkflowEventPhysicalTransportRouteBindingStatus.EVIDENCE_CONFLICT,
            None,
        )

    async def get_physical_transport_route_binding_by_id(
        self, *, binding_id: str
    ) -> WorkflowEventPhysicalTransportRouteBinding | None:
        async with self._sessions() as session:
            row = await session.get(WorkflowEventPhysicalTransportRouteBindingModel, binding_id)
            return None if row is None else self._physical_transport_route_binding_from_row(row)

    async def get_credential_assignment_binding(
        self,
        *,
        physical_transport_route_binding_id: str,
        credential_assignment_snapshot_id: str,
    ) -> WorkflowEventPhysicalTransportCredentialAssignmentBinding | None:
        async with self._sessions() as session:
            row = cast(
                WorkflowEventPhysicalTransportCredentialAssignmentBindingModel | None,
                await session.scalar(
                    select(WorkflowEventPhysicalTransportCredentialAssignmentBindingModel).where(
                        WorkflowEventPhysicalTransportCredentialAssignmentBindingModel.physical_transport_route_binding_id
                        == physical_transport_route_binding_id,
                        WorkflowEventPhysicalTransportCredentialAssignmentBindingModel.credential_assignment_snapshot_id
                        == credential_assignment_snapshot_id,
                    )
                ),
            )
            return None if row is None else self._credential_assignment_binding_from_row(row)

    async def list_credential_assignment_bindings(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowEventPhysicalTransportCredentialAssignmentBinding, ...]:
        if not 1 <= limit <= 256:
            raise ValueError("credential-assignment binding limit is invalid")
        async with self._sessions() as session:
            rows = tuple(
                (
                    await session.scalars(
                        select(WorkflowEventPhysicalTransportCredentialAssignmentBindingModel)
                        .where(
                            WorkflowEventPhysicalTransportCredentialAssignmentBindingModel.organization_id
                            == scope.organization_id,
                            WorkflowEventPhysicalTransportCredentialAssignmentBindingModel.environment_id
                            == scope.environment_id,
                            WorkflowEventPhysicalTransportCredentialAssignmentBindingModel.site_id
                            == scope.site_id,
                        )
                        .order_by(
                            WorkflowEventPhysicalTransportCredentialAssignmentBindingModel.bound_at.desc(),
                            WorkflowEventPhysicalTransportCredentialAssignmentBindingModel.binding_id,
                        )
                        .limit(limit)
                    )
                ).all()
            )
            return tuple(self._credential_assignment_binding_from_row(row) for row in rows)

    async def get_credential_assignment_binding_request(
        self,
        *,
        scope: WorkflowScope,
        binder_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowTransportCredentialAssignmentBindingIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_credential_assignment_binding_claim(
                session,
                scope=scope,
                binder_subject_id=binder_subject_id,
                idempotency_key=idempotency_key,
            )
            if claim is None:
                return None
            binding_row = await session.get(
                WorkflowEventPhysicalTransportCredentialAssignmentBindingModel,
                claim.binding_id,
            )
            return self._credential_assignment_binding_record_from_claim(claim, binding_row)

    async def bind_credential_assignment(
        self,
        request: WorkflowTransportCredentialAssignmentBindingRequest,
    ) -> WorkflowTransportCredentialAssignmentBindingResult:
        self._validate_credential_assignment_binding_request(request)
        candidate = request.candidate
        async with self._sessions() as session:
            replay = await self._credential_assignment_binding_replay(session, request=request)
            if replay is not None:
                return replay

            # Fixed order: workflow route binding, its exact route snapshot,
            # then the exact credential-assignment snapshot.
            route_binding_row = cast(
                WorkflowEventPhysicalTransportRouteBindingModel | None,
                await session.scalar(
                    select(WorkflowEventPhysicalTransportRouteBindingModel)
                    .where(
                        WorkflowEventPhysicalTransportRouteBindingModel.binding_id
                        == candidate.physical_transport_route_binding_id
                    )
                    .with_for_update()
                ),
            )
            route_snapshot_row = cast(
                EventPhysicalTransportRouteSnapshotModel | None,
                await session.scalar(
                    select(EventPhysicalTransportRouteSnapshotModel)
                    .where(
                        EventPhysicalTransportRouteSnapshotModel.snapshot_id
                        == candidate.transport_route_snapshot_id
                    )
                    .with_for_update()
                ),
            )
            assignment_snapshot_row = cast(
                EventPhysicalTransportCredentialAssignmentSnapshotModel | None,
                await session.scalar(
                    select(EventPhysicalTransportCredentialAssignmentSnapshotModel)
                    .where(
                        EventPhysicalTransportCredentialAssignmentSnapshotModel.snapshot_id
                        == candidate.credential_assignment_snapshot_id
                    )
                    .with_for_update()
                ),
            )
            if not self._credential_assignment_binding_evidence_matches(
                route_binding_row=route_binding_row,
                route_snapshot_row=route_snapshot_row,
                assignment_snapshot_row=assignment_snapshot_row,
                request=request,
            ):
                await session.rollback()
                return WorkflowTransportCredentialAssignmentBindingResult(
                    WorkflowTransportCredentialAssignmentBindingStatus.EVIDENCE_CONFLICT,
                    None,
                )

            replay = await self._credential_assignment_binding_replay(session, request=request)
            if replay is not None:
                await session.rollback()
                return replay

            existing = cast(
                WorkflowEventPhysicalTransportCredentialAssignmentBindingModel | None,
                await session.scalar(
                    select(WorkflowEventPhysicalTransportCredentialAssignmentBindingModel).where(
                        WorkflowEventPhysicalTransportCredentialAssignmentBindingModel.physical_transport_route_binding_id
                        == candidate.physical_transport_route_binding_id,
                        WorkflowEventPhysicalTransportCredentialAssignmentBindingModel.credential_assignment_snapshot_id
                        == candidate.credential_assignment_snapshot_id,
                    )
                ),
            )
            if existing is not None:
                await session.rollback()
                return WorkflowTransportCredentialAssignmentBindingResult(
                    WorkflowTransportCredentialAssignmentBindingStatus.ALREADY_BOUND,
                    self._credential_assignment_binding_from_row(existing),
                )

            try:
                await request.required_precommit_audit()
            except Exception:
                await session.rollback()
                return WorkflowTransportCredentialAssignmentBindingResult(
                    WorkflowTransportCredentialAssignmentBindingStatus.PRECOMMIT_AUDIT_FAILED,
                    None,
                )

            try:
                session.add(self._credential_assignment_binding_model(candidate))
                await session.flush()
                session.add(self._credential_assignment_binding_claim_model(request))
                await session.commit()
                return WorkflowTransportCredentialAssignmentBindingResult(
                    WorkflowTransportCredentialAssignmentBindingStatus.BOUND,
                    candidate,
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            replay = await self._credential_assignment_binding_replay(session, request=request)
            if replay is not None:
                return replay
            existing = cast(
                WorkflowEventPhysicalTransportCredentialAssignmentBindingModel | None,
                await session.scalar(
                    select(WorkflowEventPhysicalTransportCredentialAssignmentBindingModel).where(
                        WorkflowEventPhysicalTransportCredentialAssignmentBindingModel.physical_transport_route_binding_id
                        == candidate.physical_transport_route_binding_id,
                        WorkflowEventPhysicalTransportCredentialAssignmentBindingModel.credential_assignment_snapshot_id
                        == candidate.credential_assignment_snapshot_id,
                    )
                ),
            )
            if existing is not None:
                return WorkflowTransportCredentialAssignmentBindingResult(
                    WorkflowTransportCredentialAssignmentBindingStatus.ALREADY_BOUND,
                    self._credential_assignment_binding_from_row(existing),
                )
        return WorkflowTransportCredentialAssignmentBindingResult(
            WorkflowTransportCredentialAssignmentBindingStatus.EVIDENCE_CONFLICT,
            None,
        )

    async def get_credential_assignment_binding_by_id(
        self,
        *,
        binding_id: str,
    ) -> WorkflowEventPhysicalTransportCredentialAssignmentBinding | None:
        async with self._sessions() as session:
            row = await session.get(
                WorkflowEventPhysicalTransportCredentialAssignmentBindingModel,
                binding_id,
            )
            return None if row is None else self._credential_assignment_binding_from_row(row)

    async def get_current_credential_assignment_head(
        self,
        *,
        assignment_id: str,
    ) -> DeploymentPhysicalTransportCredentialAssignment | None:
        async with self._sessions() as session:
            rows = tuple(
                (
                    await session.scalars(
                        select(DeploymentEventTransportCredentialAssignmentModel)
                        .where(
                            DeploymentEventTransportCredentialAssignmentModel.assignment_id
                            == assignment_id
                        )
                        .order_by(
                            DeploymentEventTransportCredentialAssignmentModel.rotation_epoch,
                            DeploymentEventTransportCredentialAssignmentModel.credential_generation,
                            DeploymentEventTransportCredentialAssignmentModel.assignment_revision,
                        )
                    )
                ).all()
            )
            try:
                return select_deployment_physical_transport_credential_assignment_head(
                    tuple(self._credential_assignment_from_row(row) for row in rows)
                )
            except (ValueError, WorkflowTransportCredentialAssignmentSnapshotError) as exc:
                raise WorkflowTransportCredentialAssignmentFreshnessAdmissionError(
                    "workflow_transport_credential_assignment_freshness_registry_conflict",
                    "Credential-assignment registry head evidence is ambiguous or invalid.",
                ) from exc

    async def list_credential_assignment_freshness_admissions(
        self,
        *,
        scope: WorkflowScope,
        limit: int = 256,
    ) -> tuple[WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission, ...]:
        if not 1 <= limit <= 256:
            raise ValueError("credential-assignment freshness admission limit is invalid")
        async with self._sessions() as session:
            rows = tuple(
                (
                    await session.scalars(
                        select(
                            WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel
                        )
                        .where(
                            WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel.organization_id
                            == scope.organization_id,
                            WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel.environment_id
                            == scope.environment_id,
                            WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel.site_id
                            == scope.site_id,
                        )
                        .order_by(
                            WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel.evaluated_at.desc(),
                            WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel.freshness_admission_id,
                        )
                        .limit(limit)
                    )
                ).all()
            )
            return tuple(
                self._credential_assignment_freshness_admission_from_row(row) for row in rows
            )

    async def get_credential_assignment_freshness_admission_by_id(
        self, *, freshness_admission_id: str
    ) -> WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission | None:
        async with self._sessions() as session:
            row = await session.get(
                WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel,
                freshness_admission_id,
            )
            return (
                None
                if row is None
                else self._credential_assignment_freshness_admission_from_row(row)
            )

    async def get_credential_assignment_freshness_admission_request(
        self,
        *,
        scope: WorkflowScope,
        admitter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowTransportCredentialAssignmentFreshnessAdmissionIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_credential_assignment_freshness_claim(
                session,
                scope=scope,
                admitter_subject_id=admitter_subject_id,
                idempotency_key=idempotency_key,
            )
            if claim is None:
                return None
            admission_row = await session.get(
                WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel,
                claim.freshness_admission_id,
            )
            return self._credential_assignment_freshness_record_from_claim(
                claim,
                admission_row,
            )

    async def admit_credential_assignment_freshness(
        self,
        request: WorkflowTransportCredentialAssignmentFreshnessAdmissionRequest,
    ) -> WorkflowTransportCredentialAssignmentFreshnessAdmissionResult:
        validate_workflow_transport_credential_assignment_freshness_request(request)
        candidate = request.candidate
        async with self._sessions() as session:
            (
                binding_row,
                snapshot_row,
                head,
                observed_at,
            ) = await self._lock_credential_assignment_freshness_sources(
                session,
                request=request,
            )
            if not self._credential_assignment_freshness_evidence_matches(
                binding_row=binding_row,
                snapshot_row=snapshot_row,
                head=head,
                observed_at=observed_at,
                request=request,
            ):
                await session.rollback()
                return WorkflowTransportCredentialAssignmentFreshnessAdmissionResult(
                    WorkflowTransportCredentialAssignmentFreshnessAdmissionStatus.EVIDENCE_CONFLICT,
                    None,
                )
            replay = await self._credential_assignment_freshness_replay(
                session,
                request=request,
                head=head,
                observed_at=observed_at,
            )
            if replay is not None:
                await session.rollback()
                return replay
            try:
                await request.required_precommit_audit()
            except Exception:
                await session.rollback()
                return WorkflowTransportCredentialAssignmentFreshnessAdmissionResult(
                    WorkflowTransportCredentialAssignmentFreshnessAdmissionStatus.PRECOMMIT_AUDIT_FAILED,
                    None,
                )
            commit_observed_at = cast(
                datetime,
                await session.scalar(select(func.clock_timestamp())),
            )
            if not self._credential_assignment_freshness_evidence_matches(
                binding_row=binding_row,
                snapshot_row=snapshot_row,
                head=head,
                observed_at=commit_observed_at,
                request=request,
            ):
                await session.rollback()
                return WorkflowTransportCredentialAssignmentFreshnessAdmissionResult(
                    WorkflowTransportCredentialAssignmentFreshnessAdmissionStatus.EVIDENCE_CONFLICT,
                    None,
                )
            try:
                session.add(self._credential_assignment_freshness_admission_model(candidate))
                await session.flush()
                session.add(self._credential_assignment_freshness_claim_model(request))
                await session.commit()
                return WorkflowTransportCredentialAssignmentFreshnessAdmissionResult(
                    WorkflowTransportCredentialAssignmentFreshnessAdmissionStatus.ADMITTED_CURRENT,
                    candidate,
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            (
                binding_row,
                snapshot_row,
                head,
                observed_at,
            ) = await self._lock_credential_assignment_freshness_sources(
                session,
                request=request,
            )
            if not self._credential_assignment_freshness_evidence_matches(
                binding_row=binding_row,
                snapshot_row=snapshot_row,
                head=head,
                observed_at=observed_at,
                request=request,
            ):
                await session.rollback()
                return WorkflowTransportCredentialAssignmentFreshnessAdmissionResult(
                    WorkflowTransportCredentialAssignmentFreshnessAdmissionStatus.EVIDENCE_CONFLICT,
                    None,
                )
            replay = await self._credential_assignment_freshness_replay(
                session,
                request=request,
                head=head,
                observed_at=observed_at,
            )
            await session.rollback()
            if replay is not None:
                return replay
        return WorkflowTransportCredentialAssignmentFreshnessAdmissionResult(
            WorkflowTransportCredentialAssignmentFreshnessAdmissionStatus.EVIDENCE_CONFLICT,
            None,
        )

    async def list_credential_access_authorization_leases(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease, ...]:
        if not 1 <= limit <= 256:
            raise ValueError("credential-access authorization lease limit is invalid")
        async with self._sessions() as session:
            rows = tuple(
                (
                    await session.scalars(
                        select(
                            WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel
                        )
                        .where(
                            WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel.organization_id
                            == scope.organization_id,
                            WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel.environment_id
                            == scope.environment_id,
                            WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel.site_id
                            == scope.site_id,
                        )
                        .order_by(
                            WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel.issued_at.desc(),
                            WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel.authorization_lease_id,
                        )
                        .limit(limit)
                    )
                ).all()
            )
            return tuple(self._credential_access_lease_from_row(row) for row in rows)

    async def authorize_credential_access(
        self, request: WorkflowTransportCredentialAccessAuthorizationLeaseRequest
    ) -> WorkflowTransportCredentialAccessAuthorizationLeaseResult:
        validate_workflow_transport_credential_access_authorization_request(request)
        async with self._sessions() as session:
            (
                binding_row,
                snapshot_row,
                head,
                admission_row,
                observed_at,
            ) = await self._lock_credential_access_authorization_sources(session, request=request)
            replay = await self._credential_access_authorization_replay(
                session,
                request=request,
                binding_row=binding_row,
                snapshot_row=snapshot_row,
                head=head,
                admission_row=admission_row,
                observed_at=observed_at,
            )
            if replay is not None:
                await session.rollback()
                return replay
            if not self._credential_access_authorization_evidence_matches(
                binding_row=binding_row,
                snapshot_row=snapshot_row,
                head=head,
                admission_row=admission_row,
                observed_at=observed_at,
                request=request,
            ):
                await session.rollback()
                return WorkflowTransportCredentialAccessAuthorizationLeaseResult(
                    WorkflowTransportCredentialAccessAuthorizationLeaseStatus.EVIDENCE_CONFLICT,
                    None,
                )
            existing = cast(
                WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel | None,
                await session.scalar(
                    select(
                        WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel
                    ).where(
                        WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel.freshness_admission_id
                        == request.expected_freshness_admission_id
                    )
                ),
            )
            if existing is not None:
                await session.rollback()
                return WorkflowTransportCredentialAccessAuthorizationLeaseResult(
                    WorkflowTransportCredentialAccessAuthorizationLeaseStatus.ALREADY_AUTHORIZED,
                    self._credential_access_lease_from_row(existing),
                )
            try:
                await request.required_precommit_audit()
            except Exception:
                await session.rollback()
                return WorkflowTransportCredentialAccessAuthorizationLeaseResult(
                    WorkflowTransportCredentialAccessAuthorizationLeaseStatus.PRECOMMIT_AUDIT_FAILED,
                    None,
                )
            commit_observed_at = cast(
                datetime, await session.scalar(select(func.clock_timestamp()))
            )
            if not self._credential_access_authorization_evidence_matches(
                binding_row=binding_row,
                snapshot_row=snapshot_row,
                head=head,
                admission_row=admission_row,
                observed_at=commit_observed_at,
                request=request,
            ):
                await session.rollback()
                return WorkflowTransportCredentialAccessAuthorizationLeaseResult(
                    WorkflowTransportCredentialAccessAuthorizationLeaseStatus.EVIDENCE_CONFLICT,
                    None,
                )
            try:
                session.add(self._credential_access_lease_model(request.candidate))
                await session.flush()
                session.add(self._credential_access_claim_model(request))
                await session.commit()
                return WorkflowTransportCredentialAccessAuthorizationLeaseResult(
                    WorkflowTransportCredentialAccessAuthorizationLeaseStatus.AUTHORIZED,
                    request.candidate,
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            (
                binding_row,
                snapshot_row,
                head,
                admission_row,
                observed_at,
            ) = await self._lock_credential_access_authorization_sources(session, request=request)
            replay = await self._credential_access_authorization_replay(
                session,
                request=request,
                binding_row=binding_row,
                snapshot_row=snapshot_row,
                head=head,
                admission_row=admission_row,
                observed_at=observed_at,
            )
            if replay is not None:
                await session.rollback()
                return replay
            existing = cast(
                WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel | None,
                await session.scalar(
                    select(
                        WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel
                    ).where(
                        WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel.freshness_admission_id
                        == request.expected_freshness_admission_id
                    )
                ),
            )
            await session.rollback()
            if existing is not None:
                return WorkflowTransportCredentialAccessAuthorizationLeaseResult(
                    WorkflowTransportCredentialAccessAuthorizationLeaseStatus.ALREADY_AUTHORIZED,
                    self._credential_access_lease_from_row(existing),
                )
        return WorkflowTransportCredentialAccessAuthorizationLeaseResult(
            WorkflowTransportCredentialAccessAuthorizationLeaseStatus.EVIDENCE_CONFLICT,
            None,
        )

    async def get_credential_access_authorization_lease_by_id(
        self, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease | None:
        async with self._sessions() as session:
            row = await session.get(
                WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel,
                authorization_lease_id,
            )
            return None if row is None else self._credential_access_lease_from_row(row)

    async def get_credential_materialization_claim_by_lease(
        self, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaim | None:
        async with self._sessions() as session:
            row = await self._load_credential_materialization_claim_row(
                session, authorization_lease_id=authorization_lease_id
            )
            return None if row is None else self._credential_materialization_claim_from_row(row)

    async def get_credential_materialization_attempt_by_lease(
        self, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationAttempt | None:
        async with self._sessions() as session:
            row = await self._load_credential_materialization_attempt_row(
                session, authorization_lease_id=authorization_lease_id
            )
            return None if row is None else self._credential_materialization_attempt_from_row(row)

    async def list_credential_materialization_attempts(
        self, *, scope: WorkflowScope, limit: int
    ) -> tuple[WorkflowEventPhysicalTransportCredentialMaterializationAttempt, ...]:
        capped = min(max(limit, 0), 256)
        if capped == 0:
            return ()
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(WorkflowEventPhysicalTransportCredentialMaterializationAttemptModel)
                    .where(
                        WorkflowEventPhysicalTransportCredentialMaterializationAttemptModel.organization_id
                        == scope.organization_id,
                        WorkflowEventPhysicalTransportCredentialMaterializationAttemptModel.environment_id
                        == scope.environment_id,
                        WorkflowEventPhysicalTransportCredentialMaterializationAttemptModel.site_id
                        == scope.site_id,
                    )
                    .order_by(
                        WorkflowEventPhysicalTransportCredentialMaterializationAttemptModel.started_at.desc(),
                        WorkflowEventPhysicalTransportCredentialMaterializationAttemptModel.attempt_id,
                    )
                    .limit(capped)
                )
            ).all()
            return tuple(self._credential_materialization_attempt_from_row(row) for row in rows)

    async def get_credential_materialization_result_by_lease(
        self, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationResult | None:
        async with self._sessions() as session:
            row = await self._load_credential_materialization_result_row(
                session, authorization_lease_id=authorization_lease_id
            )
            return None if row is None else self._credential_materialization_result_from_row(row)

    async def claim_credential_materialization(
        self,
        request: WorkflowEventPhysicalTransportCredentialMaterializationClaimRequest,
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationClaimResult:
        self._validate_credential_materialization_claim_request(request)
        statuses = WorkflowEventPhysicalTransportCredentialMaterializationClaimStatus
        async with self._sessions() as session:
            locked = await self._lock_credential_materialization_sources(session, request=request)
            observed_at = cast(datetime, await session.scalar(select(func.clock_timestamp())))
            replay = await self._credential_materialization_claim_replay(session, request=request)
            if replay is not None:
                await session.rollback()
                return replay
            if not self._credential_materialization_evidence_matches(
                *locked, request=request, observed_at=observed_at
            ):
                await session.rollback()
                return WorkflowEventPhysicalTransportCredentialMaterializationClaimResult(
                    statuses.EVIDENCE_CONFLICT, None, None, None
                )
            try:
                await request.required_precommit_audit()
            except Exception:
                await session.rollback()
                return WorkflowEventPhysicalTransportCredentialMaterializationClaimResult(
                    statuses.PRECOMMIT_AUDIT_FAILED, None, None, None
                )
            commit_observed_at = cast(
                datetime, await session.scalar(select(func.clock_timestamp()))
            )
            if not self._credential_materialization_evidence_matches(
                *locked, request=request, observed_at=commit_observed_at
            ):
                await session.rollback()
                return WorkflowEventPhysicalTransportCredentialMaterializationClaimResult(
                    statuses.EVIDENCE_CONFLICT, None, None, None
                )
            lease_row = locked[4]
            assert lease_row is not None
            claim = self._credential_materialization_claim(request, claimed_at=commit_observed_at)
            attempt = self._credential_materialization_attempt(
                request,
                claim=claim,
                started_at=commit_observed_at,
                lease_valid_until=lease_row.valid_until,
            )
            try:
                session.add(self._credential_materialization_claim_model(claim))
                await session.flush()
                session.add(self._credential_materialization_attempt_model(attempt))
                await session.commit()
                return WorkflowEventPhysicalTransportCredentialMaterializationClaimResult(
                    statuses.CLAIMED, claim, attempt, None
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            await self._lock_credential_materialization_sources(session, request=request)
            await session.scalar(select(func.clock_timestamp()))
            replay = await self._credential_materialization_claim_replay(session, request=request)
            await session.rollback()
            if replay is not None:
                return replay
        return WorkflowEventPhysicalTransportCredentialMaterializationClaimResult(
            statuses.EVIDENCE_CONFLICT, None, None, None
        )

    async def record_credential_materialization_result(
        self,
        request: WorkflowEventPhysicalTransportCredentialMaterializationResultRequest,
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationResultWrite:
        self._validate_credential_materialization_result_request(request)
        statuses = WorkflowEventPhysicalTransportCredentialMaterializationResultStatus
        result = request.result
        async with self._sessions() as session:
            attempt_seed = await self._load_credential_materialization_attempt_row(
                session, authorization_lease_id=result.authorization_lease_id
            )
            lease_seed = await session.get(
                WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel,
                result.authorization_lease_id,
            )
            if attempt_seed is None or lease_seed is None:
                return WorkflowEventPhysicalTransportCredentialMaterializationResultWrite(
                    statuses.CONFLICT, None
                )
            locked = await self._lock_credential_materialization_result_sources(
                session, attempt_seed=attempt_seed, lease_seed=lease_seed
            )
            observed_at = cast(datetime, await session.scalar(select(func.clock_timestamp())))
            existing = await self._load_credential_materialization_result_row(
                session, authorization_lease_id=result.authorization_lease_id
            )
            if existing is not None:
                stored = self._credential_materialization_result_from_row(existing)
                await session.rollback()
                return WorkflowEventPhysicalTransportCredentialMaterializationResultWrite(
                    statuses.REPLAY if stored == result else statuses.CONFLICT,
                    stored if stored == result else None,
                )
            claim_row = await self._load_credential_materialization_claim_row(
                session, authorization_lease_id=result.authorization_lease_id
            )
            attempt_row = await self._load_credential_materialization_attempt_row(
                session, authorization_lease_id=result.authorization_lease_id
            )
            if not self._credential_materialization_result_evidence_matches(
                *locked,
                claim_row=claim_row,
                attempt_row=attempt_row,
                request=request,
                observed_at=observed_at,
            ):
                await session.rollback()
                return WorkflowEventPhysicalTransportCredentialMaterializationResultWrite(
                    statuses.CONFLICT, None
                )
            try:
                session.add(self._credential_materialization_result_model(result))
                await session.commit()
                return WorkflowEventPhysicalTransportCredentialMaterializationResultWrite(
                    statuses.RECORDED, result
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            existing = await self._load_credential_materialization_result_row(
                session, authorization_lease_id=result.authorization_lease_id
            )
            if existing is not None:
                stored = self._credential_materialization_result_from_row(existing)
                if stored == result:
                    return WorkflowEventPhysicalTransportCredentialMaterializationResultWrite(
                        statuses.REPLAY, stored
                    )
        return WorkflowEventPhysicalTransportCredentialMaterializationResultWrite(
            statuses.CONFLICT, None
        )

    async def synchronize_route_selection_heads(
        self, heads: tuple[DeploymentEventTransportRouteSelectionHead, ...]
    ) -> None:
        if not heads:
            self._route_selection_head_sync_conflict()
        unique: dict[tuple[str, str, str, str], DeploymentEventTransportRouteSelectionHead] = {}
        for head in heads:
            self._validate_route_selection_head(head)
            key = (
                head.scope.organization_id,
                head.scope.environment_id,
                head.scope.site_id,
                head.route_set_id,
            )
            prior = unique.get(key)
            if prior is not None and prior != head:
                self._route_selection_head_sync_conflict()
            unique[key] = head

        try:
            async with self._sessions() as session:
                await session.execute(
                    text("SELECT set_config('atlas.route_head_sync', 'enabled', true)")
                )
                await session.execute(
                    text(
                        "SELECT pg_advisory_xact_lock("
                        "hashtextextended('atlas.route_selection_heads.authoritative_set', 0))"
                    )
                )
                scopes = {head.scope for head in unique.values()}
                existing_rows = (
                    await session.scalars(
                        select(DeploymentEventTransportRouteSelectionHeadModel)
                        .where(
                            or_(
                                *(
                                    and_(
                                        DeploymentEventTransportRouteSelectionHeadModel.organization_id
                                        == scope.organization_id,
                                        DeploymentEventTransportRouteSelectionHeadModel.environment_id
                                        == scope.environment_id,
                                        DeploymentEventTransportRouteSelectionHeadModel.site_id
                                        == scope.site_id,
                                    )
                                    for scope in scopes
                                )
                            )
                        )
                        .with_for_update()
                    )
                ).all()
                existing_keys = {
                    (
                        row.organization_id,
                        row.environment_id,
                        row.site_id,
                        row.route_set_id,
                    )
                    for row in existing_rows
                }
                if not existing_keys.issubset(unique):
                    self._route_selection_head_sync_conflict()
                for key in sorted(unique):
                    candidate = unique[key]
                    lock_key = "/".join(key)
                    await session.execute(
                        text("SELECT pg_advisory_xact_lock(hashtextextended(:lock_key, 0))"),
                        {"lock_key": lock_key},
                    )
                    rows = (
                        await session.scalars(
                            select(DeploymentEventTransportRouteSelectionHeadModel)
                            .where(
                                DeploymentEventTransportRouteSelectionHeadModel.organization_id
                                == candidate.scope.organization_id,
                                DeploymentEventTransportRouteSelectionHeadModel.environment_id
                                == candidate.scope.environment_id,
                                DeploymentEventTransportRouteSelectionHeadModel.site_id
                                == candidate.scope.site_id,
                                DeploymentEventTransportRouteSelectionHeadModel.route_set_id
                                == candidate.route_set_id,
                            )
                            .with_for_update()
                        )
                    ).all()
                    if len(rows) > 1:
                        self._route_selection_head_sync_conflict()
                    if not rows:
                        session.add(self._route_selection_head_model(candidate))
                        await session.flush()
                        continue

                    row = rows[0]
                    current = self._route_selection_head_from_row(row)
                    if current == candidate:
                        continue
                    if candidate.generation <= current.generation:
                        self._route_selection_head_sync_conflict()
                    if candidate.fencing_token_digest == current.fencing_token_digest:
                        self._route_selection_head_sync_conflict()
                    self._assign_route_selection_head_row(row, candidate)
                    await session.flush()
                await session.commit()
        except IntegrityError as exc:
            raise WorkflowEventPhysicalTransportRouteFreshnessAdmissionError(
                "workflow_route_selection_head_synchronization_conflict",
                "The authoritative route selection head synchronization conflicted.",
            ) from exc

    async def get_current_route_selection_head(
        self, *, scope: WorkflowScope, route_set_id: str
    ) -> DeploymentEventTransportRouteSelectionHead | None:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(DeploymentEventTransportRouteSelectionHeadModel)
                    .where(
                        DeploymentEventTransportRouteSelectionHeadModel.organization_id
                        == scope.organization_id,
                        DeploymentEventTransportRouteSelectionHeadModel.environment_id
                        == scope.environment_id,
                        DeploymentEventTransportRouteSelectionHeadModel.site_id == scope.site_id,
                        DeploymentEventTransportRouteSelectionHeadModel.route_set_id
                        == route_set_id,
                        DeploymentEventTransportRouteSelectionHeadModel.current.is_(True),
                    )
                    .limit(2)
                )
            ).all()
            if not rows:
                return None
            if len(rows) != 1:
                self._route_freshness_admission_contract_violation()
            return self._route_selection_head_from_row(rows[0])

    async def get_route_freshness_admission(
        self, *, physical_transport_route_binding_id: str
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmission | None:
        async with self._sessions() as session:
            row = cast(
                WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel | None,
                await session.scalar(
                    select(WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel).where(
                        WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel.physical_transport_route_binding_id
                        == physical_transport_route_binding_id
                    )
                ),
            )
            return None if row is None else self._route_freshness_admission_from_row(row)

    async def get_route_freshness_admission_by_id(
        self, *, freshness_admission_id: str
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmission | None:
        async with self._sessions() as session:
            row = await session.get(
                WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel,
                freshness_admission_id,
            )
            return None if row is None else self._route_freshness_admission_from_row(row)

    async def list_route_freshness_admissions(
        self, *, scope: WorkflowScope, limit: int
    ) -> tuple[WorkflowEventPhysicalTransportRouteFreshnessAdmission, ...]:
        capped = min(max(limit, 0), 256)
        if capped == 0:
            return ()
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel)
                    .where(
                        WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel.organization_id
                        == scope.organization_id,
                        WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel.environment_id
                        == scope.environment_id,
                        WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel.site_id
                        == scope.site_id,
                    )
                    .order_by(
                        WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel.evaluated_at.desc(),
                        WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel.freshness_admission_id,
                    )
                    .limit(capped)
                )
            ).all()
            return tuple(self._route_freshness_admission_from_row(row) for row in rows)

    async def get_route_freshness_admission_request(
        self,
        *,
        scope: WorkflowScope,
        admitter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmissionIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_route_freshness_admission_claim(
                session,
                scope=scope,
                admitter_subject_id=admitter_subject_id,
                idempotency_key=idempotency_key,
            )
            if claim is None:
                return None
            row = await session.get(
                WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel,
                claim.freshness_admission_id,
            )
            return self._route_freshness_admission_record_from_claim(claim, row)

    async def admit_physical_transport_route_freshness(
        self, request: WorkflowEventPhysicalTransportRouteFreshnessAdmissionRequest
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult:
        self._validate_route_freshness_admission_request(request)
        candidate = request.candidate
        async with self._sessions() as session:
            binding_row, route_row, head_row = await self._lock_route_freshness_sources(
                session, request=request
            )
            if not self._route_freshness_admission_evidence_matches(
                binding_row=binding_row,
                route_row=route_row,
                head_row=head_row,
                request=request,
            ):
                await session.rollback()
                return WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult(
                    WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus.EVIDENCE_CONFLICT,
                    None,
                )

            observed_at = cast(datetime, await session.scalar(select(func.now())))
            if observed_at >= candidate.valid_until:
                await session.rollback()
                return WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult(
                    WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus.EVIDENCE_CONFLICT,
                    None,
                )
            replay = await self._route_freshness_admission_replay(
                session,
                request=request,
                head_row=head_row,
                observed_at=observed_at,
            )
            if replay is not None:
                await session.rollback()
                return replay

            existing = cast(
                WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel | None,
                await session.scalar(
                    select(WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel).where(
                        WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel.physical_transport_route_binding_id
                        == candidate.physical_transport_route_binding_id
                    )
                ),
            )
            if existing is not None:
                await session.rollback()
                return WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult(
                    WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus.ALREADY_ADMITTED,
                    self._route_freshness_admission_from_row(existing),
                )

            try:
                session.add(self._route_freshness_admission_model(candidate))
                await session.flush()
                session.add(self._route_freshness_admission_claim_model(request))
                await session.commit()
                return WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult(
                    WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus.ADMITTED_CURRENT,
                    candidate,
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            _, _, head_row = await self._lock_route_freshness_sources(session, request=request)
            observed_at = cast(datetime, await session.scalar(select(func.now())))
            if observed_at >= candidate.valid_until:
                await session.rollback()
                return WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult(
                    WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus.EVIDENCE_CONFLICT,
                    None,
                )
            replay = await self._route_freshness_admission_replay(
                session,
                request=request,
                head_row=head_row,
                observed_at=observed_at,
            )
            if replay is not None:
                await session.rollback()
                return replay
            existing = cast(
                WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel | None,
                await session.scalar(
                    select(WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel).where(
                        WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel.physical_transport_route_binding_id
                        == candidate.physical_transport_route_binding_id
                    )
                ),
            )
            await session.rollback()
            if existing is not None:
                return WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult(
                    WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus.ALREADY_ADMITTED,
                    self._route_freshness_admission_from_row(existing),
                )
        return WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult(
            WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus.EVIDENCE_CONFLICT,
            None,
        )

    async def get_endpoint_resolution_authorization_lease(
        self, *, freshness_admission_id: str
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease | None:
        async with self._sessions() as session:
            row = cast(
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel | None,
                await session.scalar(
                    select(
                        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel
                    ).where(
                        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel.freshness_admission_id
                        == freshness_admission_id
                    )
                ),
            )
            return (
                None if row is None else self._endpoint_resolution_authorization_lease_from_row(row)
            )

    async def list_endpoint_resolution_authorization_leases(
        self, *, scope: WorkflowScope, limit: int
    ) -> tuple[WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease, ...]:
        capped = min(max(limit, 0), 256)
        if capped == 0:
            return ()
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel)
                    .where(
                        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel.organization_id
                        == scope.organization_id,
                        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel.environment_id
                        == scope.environment_id,
                        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel.site_id
                        == scope.site_id,
                    )
                    .order_by(
                        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel.issued_at.desc(),
                        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel.authorization_lease_id,
                    )
                    .limit(capped)
                )
            ).all()
            return tuple(
                self._endpoint_resolution_authorization_lease_from_row(row) for row in rows
            )

    async def get_endpoint_resolution_authorization_lease_request(
        self,
        *,
        scope: WorkflowScope,
        resolver_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_endpoint_resolution_authorization_lease_claim(
                session,
                scope=scope,
                resolver_subject_id=resolver_subject_id,
                idempotency_key=idempotency_key,
            )
            if claim is None:
                return None
            row = await session.get(
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel,
                claim.authorization_lease_id,
            )
            return self._endpoint_resolution_authorization_lease_record_from_claim(claim, row)

    async def get_endpoint_resolution_authorization_lease_by_id(
        self, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease | None:
        async with self._sessions() as session:
            row = await session.get(
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel,
                authorization_lease_id,
            )
            return (
                None if row is None else self._endpoint_resolution_authorization_lease_from_row(row)
            )

    async def get_endpoint_materialization_claim_by_lease(
        self, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaim | None:
        async with self._sessions() as session:
            row = await self._load_endpoint_materialization_claim_row(
                session, authorization_lease_id=authorization_lease_id
            )
            return None if row is None else self._endpoint_materialization_claim_from_row(row)

    async def get_endpoint_materialization_attempt_by_lease(
        self, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationAttempt | None:
        async with self._sessions() as session:
            row = await self._load_endpoint_materialization_attempt_row(
                session, authorization_lease_id=authorization_lease_id
            )
            return None if row is None else self._endpoint_materialization_attempt_from_row(row)

    async def list_endpoint_materialization_attempts(
        self, *, scope: WorkflowScope, limit: int
    ) -> tuple[WorkflowEventPhysicalTransportEndpointMaterializationAttempt, ...]:
        capped = min(max(limit, 0), 256)
        if capped == 0:
            return ()
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(WorkflowEventPhysicalTransportEndpointMaterializationAttemptModel)
                    .where(
                        WorkflowEventPhysicalTransportEndpointMaterializationAttemptModel.organization_id
                        == scope.organization_id,
                        WorkflowEventPhysicalTransportEndpointMaterializationAttemptModel.environment_id
                        == scope.environment_id,
                        WorkflowEventPhysicalTransportEndpointMaterializationAttemptModel.site_id
                        == scope.site_id,
                    )
                    .order_by(
                        WorkflowEventPhysicalTransportEndpointMaterializationAttemptModel.started_at.desc(),
                        WorkflowEventPhysicalTransportEndpointMaterializationAttemptModel.attempt_id,
                    )
                    .limit(capped)
                )
            ).all()
            return tuple(self._endpoint_materialization_attempt_from_row(row) for row in rows)

    async def get_endpoint_materialization_result_by_lease(
        self, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationResult | None:
        async with self._sessions() as session:
            row = await self._load_endpoint_materialization_result_row(
                session, authorization_lease_id=authorization_lease_id
            )
            return None if row is None else self._endpoint_materialization_result_from_row(row)

    async def authorize_endpoint_resolution(
        self,
        request: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRequest,
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult:
        self._validate_endpoint_resolution_authorization_request(request)
        async with self._sessions() as session:
            (
                binding_row,
                route_row,
                head_row,
                freshness_row,
            ) = await self._lock_endpoint_resolution_authorization_sources(session, request=request)
            observed_at = cast(datetime, await session.scalar(select(func.now())))
            if not self._endpoint_resolution_authorization_evidence_matches(
                binding_row=binding_row,
                route_row=route_row,
                head_row=head_row,
                freshness_row=freshness_row,
                request=request,
                observed_at=observed_at,
            ):
                await session.rollback()
                return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult(
                    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus.EVIDENCE_CONFLICT,
                    None,
                )

            replay = await self._endpoint_resolution_authorization_replay(
                session,
                request=request,
                head_row=head_row,
                freshness_row=freshness_row,
                observed_at=observed_at,
            )
            if replay is not None:
                await session.rollback()
                return replay

            assert freshness_row is not None
            if observed_at + timedelta(seconds=15) > freshness_row.valid_until:
                await session.rollback()
                return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult(
                    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus.EVIDENCE_CONFLICT,
                    None,
                )

            existing = cast(
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel | None,
                await session.scalar(
                    select(
                        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel
                    ).where(
                        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel.freshness_admission_id
                        == request.expected_freshness_admission_id
                    )
                ),
            )
            if existing is not None:
                await session.rollback()
                return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult(
                    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus.ALREADY_AUTHORIZED,
                    self._endpoint_resolution_authorization_lease_from_row(existing),
                )

            freshness = self._route_freshness_admission_from_row(freshness_row)
            lease = self._endpoint_resolution_authorization_lease(
                request=request,
                freshness=freshness,
                issued_at=observed_at,
            )
            try:
                session.add(self._endpoint_resolution_authorization_lease_model(lease))
                await session.flush()
                session.add(
                    self._endpoint_resolution_authorization_lease_claim_model(request, lease)
                )
                await session.commit()
                return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult(
                    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus.AUTHORIZED,
                    lease,
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            (
                _,
                _,
                head_row,
                freshness_row,
            ) = await self._lock_endpoint_resolution_authorization_sources(session, request=request)
            observed_at = cast(datetime, await session.scalar(select(func.now())))
            replay = await self._endpoint_resolution_authorization_replay(
                session,
                request=request,
                head_row=head_row,
                freshness_row=freshness_row,
                observed_at=observed_at,
            )
            if replay is not None:
                await session.rollback()
                return replay
            if (
                freshness_row is None
                or observed_at + timedelta(seconds=15) > freshness_row.valid_until
            ):
                await session.rollback()
                return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult(
                    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus.EVIDENCE_CONFLICT,
                    None,
                )
            existing = cast(
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel | None,
                await session.scalar(
                    select(
                        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel
                    ).where(
                        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel.freshness_admission_id
                        == request.expected_freshness_admission_id
                    )
                ),
            )
            await session.rollback()
            if existing is not None:
                return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult(
                    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus.ALREADY_AUTHORIZED,
                    self._endpoint_resolution_authorization_lease_from_row(existing),
                )
        return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult(
            WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus.EVIDENCE_CONFLICT,
            None,
        )

    async def claim_endpoint_materialization(
        self,
        request: WorkflowEventPhysicalTransportEndpointMaterializationClaimRequest,
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationClaimResult:
        self._validate_endpoint_materialization_claim_request(request)
        async with self._sessions() as session:
            locked = await self._lock_endpoint_materialization_sources(session, request=request)
            observed_at = cast(datetime, await session.scalar(select(func.clock_timestamp())))
            replay = await self._endpoint_materialization_claim_replay(session, request=request)
            if replay is not None:
                await session.rollback()
                return replay
            if not self._endpoint_materialization_evidence_matches(
                *locked, request=request, observed_at=observed_at
            ):
                await session.rollback()
                return WorkflowEventPhysicalTransportEndpointMaterializationClaimResult(
                    WorkflowEventPhysicalTransportEndpointMaterializationClaimStatus.EVIDENCE_CONFLICT,
                    None,
                    None,
                    None,
                )
            claim = self._endpoint_materialization_claim(request, claimed_at=observed_at)
            lease_row = locked[4]
            assert lease_row is not None
            attempt = self._endpoint_materialization_attempt(
                request,
                claim=claim,
                started_at=observed_at,
                lease_valid_until=lease_row.valid_until,
            )
            try:
                session.add(self._endpoint_materialization_claim_model(claim))
                await session.flush()
                session.add(self._endpoint_materialization_attempt_model(attempt))
                await session.commit()
                return WorkflowEventPhysicalTransportEndpointMaterializationClaimResult(
                    WorkflowEventPhysicalTransportEndpointMaterializationClaimStatus.CLAIMED,
                    claim,
                    attempt,
                    None,
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            await self._lock_endpoint_materialization_sources(session, request=request)
            await session.scalar(select(func.clock_timestamp()))
            replay = await self._endpoint_materialization_claim_replay(session, request=request)
            await session.rollback()
            if replay is not None:
                return replay
        return WorkflowEventPhysicalTransportEndpointMaterializationClaimResult(
            WorkflowEventPhysicalTransportEndpointMaterializationClaimStatus.EVIDENCE_CONFLICT,
            None,
            None,
            None,
        )

    async def record_endpoint_materialization_result(
        self,
        request: WorkflowEventPhysicalTransportEndpointMaterializationResultRequest,
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationResultWrite:
        self._validate_endpoint_materialization_result_request(request)
        result = request.result
        async with self._sessions() as session:
            seed = await self._load_endpoint_materialization_attempt_row(
                session, authorization_lease_id=result.authorization_lease_id
            )
            lease_seed = await session.get(
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel,
                result.authorization_lease_id,
            )
            if seed is None or lease_seed is None:
                return WorkflowEventPhysicalTransportEndpointMaterializationResultWrite(
                    WorkflowEventPhysicalTransportEndpointMaterializationResultStatus.CONFLICT,
                    None,
                )
            locked = await self._lock_endpoint_materialization_result_sources(
                session, attempt_seed=seed, lease_seed=lease_seed
            )
            observed_at = cast(datetime, await session.scalar(select(func.clock_timestamp())))
            existing = await self._load_endpoint_materialization_result_row(
                session, authorization_lease_id=result.authorization_lease_id
            )
            if existing is not None:
                stored = self._endpoint_materialization_result_from_row(existing)
                await session.rollback()
                if stored == result:
                    return WorkflowEventPhysicalTransportEndpointMaterializationResultWrite(
                        WorkflowEventPhysicalTransportEndpointMaterializationResultStatus.REPLAY,
                        stored,
                    )
                return WorkflowEventPhysicalTransportEndpointMaterializationResultWrite(
                    WorkflowEventPhysicalTransportEndpointMaterializationResultStatus.CONFLICT,
                    None,
                )
            claim_row = await self._load_endpoint_materialization_claim_row(
                session, authorization_lease_id=result.authorization_lease_id
            )
            attempt_row = await self._load_endpoint_materialization_attempt_row(
                session, authorization_lease_id=result.authorization_lease_id
            )
            if not self._endpoint_materialization_result_evidence_matches(
                *locked,
                claim_row=claim_row,
                attempt_row=attempt_row,
                request=request,
                observed_at=observed_at,
            ):
                await session.rollback()
                return WorkflowEventPhysicalTransportEndpointMaterializationResultWrite(
                    WorkflowEventPhysicalTransportEndpointMaterializationResultStatus.CONFLICT,
                    None,
                )
            try:
                session.add(self._endpoint_materialization_result_model(result))
                await session.commit()
                return WorkflowEventPhysicalTransportEndpointMaterializationResultWrite(
                    WorkflowEventPhysicalTransportEndpointMaterializationResultStatus.RECORDED,
                    result,
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            existing = await self._load_endpoint_materialization_result_row(
                session, authorization_lease_id=result.authorization_lease_id
            )
            if existing is not None:
                stored = self._endpoint_materialization_result_from_row(existing)
                if stored == result:
                    return WorkflowEventPhysicalTransportEndpointMaterializationResultWrite(
                        WorkflowEventPhysicalTransportEndpointMaterializationResultStatus.REPLAY,
                        stored,
                    )
        return WorkflowEventPhysicalTransportEndpointMaterializationResultWrite(
            WorkflowEventPhysicalTransportEndpointMaterializationResultStatus.CONFLICT,
            None,
        )

    async def bind_target_context(
        self,
        request: WorkflowEventPhysicalTransportTargetContextBindingRequest,
    ) -> WorkflowEventPhysicalTransportTargetContextBindingResult:
        self._validate_target_context_binding_request(request)
        statuses = WorkflowEventPhysicalTransportTargetContextBindingStatus
        async with self._sessions() as session:
            locked = await self._lock_target_context_sources(session, request=request)
            if locked is None:
                await session.rollback()
                return WorkflowEventPhysicalTransportTargetContextBindingResult(
                    statuses.EVIDENCE_CONFLICT, None
                )
            observed_at = cast(datetime, await session.scalar(select(func.clock_timestamp())))
            replay = self._target_context_binding_replay(
                locked, request=request, observed_at=observed_at
            )
            if replay is not None:
                await session.rollback()
                return replay
            if locked.existing_bindings:
                await session.rollback()
                return WorkflowEventPhysicalTransportTargetContextBindingResult(
                    statuses.ALREADY_BOUND, None
                )
            evidence = self._target_context_binding_evidence(
                locked, request=request, observed_at=observed_at, require_live_overlap=True
            )
            if evidence is None:
                await session.rollback()
                return WorkflowEventPhysicalTransportTargetContextBindingResult(
                    statuses.EVIDENCE_CONFLICT, None
                )
            try:
                await request.required_precommit_audit()
            except Exception:
                await session.rollback()
                return WorkflowEventPhysicalTransportTargetContextBindingResult(
                    statuses.PRECOMMIT_AUDIT_FAILED, None
                )

            committed_at = cast(datetime, await session.scalar(select(func.clock_timestamp())))
            evidence = self._target_context_binding_evidence(
                locked, request=request, observed_at=committed_at, require_live_overlap=True
            )
            if evidence is None:
                await session.rollback()
                return WorkflowEventPhysicalTransportTargetContextBindingResult(
                    statuses.EVIDENCE_CONFLICT, None
                )
            binding = self._target_context_binding(
                request=request,
                evidence=evidence,
                bound_at=committed_at,
            )
            try:
                session.add(self._target_context_binding_model(binding))
                await session.flush()
                session.add(self._target_context_binding_claim_model(request, binding=binding))
                await session.commit()
                return WorkflowEventPhysicalTransportTargetContextBindingResult(
                    statuses.BOUND, binding
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            locked = await self._lock_target_context_sources(session, request=request)
            if locked is None:
                await session.rollback()
                return WorkflowEventPhysicalTransportTargetContextBindingResult(
                    statuses.EVIDENCE_CONFLICT, None
                )
            observed_at = cast(datetime, await session.scalar(select(func.clock_timestamp())))
            replay = self._target_context_binding_replay(
                locked, request=request, observed_at=observed_at
            )
            if replay is not None:
                await session.rollback()
                return replay
            already_bound = bool(locked.existing_bindings)
            await session.rollback()
            return WorkflowEventPhysicalTransportTargetContextBindingResult(
                statuses.ALREADY_BOUND if already_bound else statuses.EVIDENCE_CONFLICT,
                None,
            )

    async def list_target_context_bindings(
        self,
        *,
        scope: WorkflowScope,
        limit: int = 256,
    ) -> tuple[WorkflowEventPhysicalTransportTargetContextBinding, ...]:
        capped = max(1, min(limit, 256))
        async with self._sessions() as session:
            rows = tuple(
                (
                    await session.scalars(
                        select(WorkflowEventPhysicalTransportTargetContextBindingModel)
                        .where(
                            WorkflowEventPhysicalTransportTargetContextBindingModel.organization_id
                            == scope.organization_id,
                            WorkflowEventPhysicalTransportTargetContextBindingModel.environment_id
                            == scope.environment_id,
                            WorkflowEventPhysicalTransportTargetContextBindingModel.site_id
                            == scope.site_id,
                        )
                        .order_by(
                            WorkflowEventPhysicalTransportTargetContextBindingModel.bound_at.desc(),
                            WorkflowEventPhysicalTransportTargetContextBindingModel.binding_id,
                        )
                        .limit(capped)
                    )
                ).all()
            )
        return tuple(self._target_context_binding_from_row(row) for row in rows)

    async def _lock_target_context_sources(
        self,
        session: AsyncSession,
        *,
        request: WorkflowEventPhysicalTransportTargetContextBindingRequest,
    ) -> _TargetContextLockedSources | None:
        endpoint_result_seed = await session.get(
            WorkflowEventPhysicalTransportEndpointMaterializationResultModel,
            request.expected_endpoint_materialization_id,
        )
        credential_result_seed = await session.get(
            WorkflowEventPhysicalTransportCredentialMaterializationResultModel,
            request.expected_credential_materialization_id,
        )
        if endpoint_result_seed is None or credential_result_seed is None:
            return None
        endpoint_attempt_seed = await session.get(
            WorkflowEventPhysicalTransportEndpointMaterializationAttemptModel,
            endpoint_result_seed.attempt_id,
        )
        credential_attempt_seed = await session.get(
            WorkflowEventPhysicalTransportCredentialMaterializationAttemptModel,
            credential_result_seed.attempt_id,
        )
        if endpoint_attempt_seed is None or credential_attempt_seed is None:
            return None
        scope_id = self._target_context_binding_idempotency_scope(
            request.scope, request.binder_subject_id
        )
        claim_seed = cast(
            WorkflowEventPhysicalTransportTargetContextBindingClaimModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportTargetContextBindingClaimModel).where(
                    WorkflowEventPhysicalTransportTargetContextBindingClaimModel.idempotency_scope_id
                    == scope_id,
                    WorkflowEventPhysicalTransportTargetContextBindingClaimModel.idempotency_key
                    == request.idempotency_key,
                )
            ),
        )

        route_binding = cast(
            WorkflowEventPhysicalTransportRouteBindingModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportRouteBindingModel)
                .where(
                    WorkflowEventPhysicalTransportRouteBindingModel.binding_id
                    == endpoint_attempt_seed.physical_transport_route_binding_id
                )
                .with_for_update()
            ),
        )
        route_snapshot = cast(
            EventPhysicalTransportRouteSnapshotModel | None,
            await session.scalar(
                select(EventPhysicalTransportRouteSnapshotModel)
                .where(
                    EventPhysicalTransportRouteSnapshotModel.snapshot_id
                    == endpoint_attempt_seed.transport_route_snapshot_id
                )
                .with_for_update()
            ),
        )
        endpoint_freshness = cast(
            WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel)
                .where(
                    WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel.freshness_admission_id
                    == endpoint_result_seed.freshness_admission_id
                )
                .with_for_update()
            ),
        )
        endpoint_lease = cast(
            WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel)
                .where(
                    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel.authorization_lease_id
                    == endpoint_result_seed.authorization_lease_id
                )
                .with_for_update()
            ),
        )
        endpoint_claim = cast(
            WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaimModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaimModel)
                .where(
                    WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaimModel.claim_id
                    == endpoint_result_seed.consumption_claim_id
                )
                .with_for_update()
            ),
        )
        endpoint_attempt = cast(
            WorkflowEventPhysicalTransportEndpointMaterializationAttemptModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportEndpointMaterializationAttemptModel)
                .where(
                    WorkflowEventPhysicalTransportEndpointMaterializationAttemptModel.attempt_id
                    == endpoint_result_seed.attempt_id
                )
                .with_for_update()
            ),
        )
        endpoint_result = cast(
            WorkflowEventPhysicalTransportEndpointMaterializationResultModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportEndpointMaterializationResultModel)
                .where(
                    WorkflowEventPhysicalTransportEndpointMaterializationResultModel.materialization_id
                    == request.expected_endpoint_materialization_id
                )
                .with_for_update()
            ),
        )
        credential_binding = cast(
            WorkflowEventPhysicalTransportCredentialAssignmentBindingModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportCredentialAssignmentBindingModel)
                .where(
                    WorkflowEventPhysicalTransportCredentialAssignmentBindingModel.binding_id
                    == credential_attempt_seed.physical_transport_credential_assignment_binding_id
                )
                .with_for_update()
            ),
        )
        credential_snapshot = cast(
            EventPhysicalTransportCredentialAssignmentSnapshotModel | None,
            await session.scalar(
                select(EventPhysicalTransportCredentialAssignmentSnapshotModel)
                .where(
                    EventPhysicalTransportCredentialAssignmentSnapshotModel.snapshot_id
                    == credential_attempt_seed.credential_assignment_snapshot_id
                )
                .with_for_update()
            ),
        )
        credential_freshness = cast(
            WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel)
                .where(
                    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel.freshness_admission_id
                    == credential_result_seed.freshness_admission_id
                )
                .with_for_update()
            ),
        )
        credential_lease = cast(
            WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel)
                .where(
                    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel.authorization_lease_id
                    == credential_result_seed.authorization_lease_id
                )
                .with_for_update()
            ),
        )
        credential_claim = cast(
            WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaimModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaimModel)
                .where(
                    WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaimModel.claim_id
                    == credential_result_seed.consumption_claim_id
                )
                .with_for_update()
            ),
        )
        credential_attempt = cast(
            WorkflowEventPhysicalTransportCredentialMaterializationAttemptModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportCredentialMaterializationAttemptModel)
                .where(
                    WorkflowEventPhysicalTransportCredentialMaterializationAttemptModel.attempt_id
                    == credential_result_seed.attempt_id
                )
                .with_for_update()
            ),
        )
        credential_result = cast(
            WorkflowEventPhysicalTransportCredentialMaterializationResultModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportCredentialMaterializationResultModel)
                .where(
                    WorkflowEventPhysicalTransportCredentialMaterializationResultModel.materialization_id
                    == request.expected_credential_materialization_id
                )
                .with_for_update()
            ),
        )
        required = (
            route_binding,
            route_snapshot,
            endpoint_freshness,
            endpoint_lease,
            endpoint_claim,
            endpoint_attempt,
            endpoint_result,
            credential_binding,
            credential_snapshot,
            credential_freshness,
            credential_lease,
            credential_claim,
            credential_attempt,
            credential_result,
        )
        if any(row is None for row in required):
            return None

        binding_conditions = [
            WorkflowEventPhysicalTransportTargetContextBindingModel.endpoint_materialization_id
            == request.expected_endpoint_materialization_id,
            WorkflowEventPhysicalTransportTargetContextBindingModel.credential_materialization_id
            == request.expected_credential_materialization_id,
        ]
        if claim_seed is not None:
            binding_conditions.append(
                WorkflowEventPhysicalTransportTargetContextBindingModel.binding_id
                == claim_seed.binding_id
            )
        existing_bindings = tuple(
            (
                await session.scalars(
                    select(WorkflowEventPhysicalTransportTargetContextBindingModel)
                    .where(or_(*binding_conditions))
                    .order_by(WorkflowEventPhysicalTransportTargetContextBindingModel.binding_id)
                    .with_for_update()
                )
            ).all()
        )
        idempotency_claim = cast(
            WorkflowEventPhysicalTransportTargetContextBindingClaimModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportTargetContextBindingClaimModel)
                .where(
                    WorkflowEventPhysicalTransportTargetContextBindingClaimModel.idempotency_scope_id
                    == scope_id,
                    WorkflowEventPhysicalTransportTargetContextBindingClaimModel.idempotency_key
                    == request.idempotency_key,
                )
                .with_for_update()
            ),
        )
        return _TargetContextLockedSources(
            route_binding=cast(WorkflowEventPhysicalTransportRouteBindingModel, route_binding),
            route_snapshot=cast(EventPhysicalTransportRouteSnapshotModel, route_snapshot),
            endpoint_freshness=cast(
                WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel, endpoint_freshness
            ),
            endpoint_lease=cast(
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel,
                endpoint_lease,
            ),
            endpoint_claim=cast(
                WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaimModel,
                endpoint_claim,
            ),
            endpoint_attempt=cast(
                WorkflowEventPhysicalTransportEndpointMaterializationAttemptModel,
                endpoint_attempt,
            ),
            endpoint_result=cast(
                WorkflowEventPhysicalTransportEndpointMaterializationResultModel, endpoint_result
            ),
            credential_binding=cast(
                WorkflowEventPhysicalTransportCredentialAssignmentBindingModel,
                credential_binding,
            ),
            credential_snapshot=cast(
                EventPhysicalTransportCredentialAssignmentSnapshotModel, credential_snapshot
            ),
            credential_freshness=cast(
                WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel,
                credential_freshness,
            ),
            credential_lease=cast(
                WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel,
                credential_lease,
            ),
            credential_claim=cast(
                WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaimModel,
                credential_claim,
            ),
            credential_attempt=cast(
                WorkflowEventPhysicalTransportCredentialMaterializationAttemptModel,
                credential_attempt,
            ),
            credential_result=cast(
                WorkflowEventPhysicalTransportCredentialMaterializationResultModel,
                credential_result,
            ),
            existing_bindings=existing_bindings,
            idempotency_claim=idempotency_claim,
        )

    def _target_context_binding_replay(
        self,
        locked: _TargetContextLockedSources,
        *,
        request: WorkflowEventPhysicalTransportTargetContextBindingRequest,
        observed_at: datetime,
    ) -> WorkflowEventPhysicalTransportTargetContextBindingResult | None:
        claim = locked.idempotency_claim
        if claim is None:
            return None
        binding_row = next(
            (row for row in locked.existing_bindings if row.binding_id == claim.binding_id),
            None,
        )
        if binding_row is None:
            self._target_context_binding_contract_violation()
        binding = self._target_context_binding_from_claim(claim, binding_row=binding_row)
        exact = (
            claim.request_fingerprint == request.request_fingerprint
            and binding.endpoint_materialization_id == request.expected_endpoint_materialization_id
            and binding.endpoint_materialization_digest
            == request.expected_endpoint_materialization_digest
            and binding.credential_materialization_id
            == request.expected_credential_materialization_id
            and binding.credential_materialization_digest
            == request.expected_credential_materialization_digest
            and binding.policy_id == request.expected_policy_id
            and binding.policy_version == request.expected_policy_version
            and binding.policy_digest == request.expected_policy_digest
            and binding.scope == request.scope
            and binding.binder_subject_id == request.binder_subject_id
        )
        if exact:
            evidence = self._target_context_binding_evidence(
                locked,
                request=request,
                observed_at=observed_at,
                require_live_overlap=False,
            )
            if evidence is None:
                self._target_context_binding_contract_violation()
        status = (
            WorkflowEventPhysicalTransportTargetContextBindingStatus.REPLAY
            if exact
            else WorkflowEventPhysicalTransportTargetContextBindingStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowEventPhysicalTransportTargetContextBindingResult(
            status, binding if exact else None
        )

    def _target_context_binding_evidence(
        self,
        locked: _TargetContextLockedSources,
        *,
        request: WorkflowEventPhysicalTransportTargetContextBindingRequest,
        observed_at: datetime,
        require_live_overlap: bool,
    ) -> dict[str, Any] | None:
        try:
            route_binding = self._physical_transport_route_binding_from_row(locked.route_binding)
            route_snapshot = self._transport_route_snapshot_from_row(locked.route_snapshot)
            endpoint_freshness = self._route_freshness_admission_from_row(locked.endpoint_freshness)
            endpoint_lease = self._endpoint_resolution_authorization_lease_from_row(
                locked.endpoint_lease
            )
            endpoint_claim = self._endpoint_materialization_claim_from_row(locked.endpoint_claim)
            endpoint_attempt = self._endpoint_materialization_attempt_from_row(
                locked.endpoint_attempt
            )
            endpoint_result = self._endpoint_materialization_result_from_row(locked.endpoint_result)
            credential_binding = self._credential_assignment_binding_from_row(
                locked.credential_binding
            )
            credential_snapshot = self._credential_assignment_snapshot_from_row(
                locked.credential_snapshot
            )
            credential_freshness = self._credential_assignment_freshness_admission_from_row(
                locked.credential_freshness
            )
            credential_lease = self._credential_access_lease_from_row(locked.credential_lease)
            credential_claim = self._credential_materialization_claim_from_row(
                locked.credential_claim
            )
            credential_attempt = self._credential_materialization_attempt_from_row(
                locked.credential_attempt
            )
            credential_result = self._credential_materialization_result_from_row(
                locked.credential_result
            )
        except Exception as exc:
            raise WorkflowEventPhysicalTransportTargetContextBindingError(
                "workflow_target_context_binding_repository_contract_violation",
                "Target-context source evidence is invalid.",
            ) from exc

        scope = request.scope
        objects = (
            route_binding,
            route_snapshot,
            endpoint_freshness,
            endpoint_lease,
            endpoint_claim,
            endpoint_attempt,
            endpoint_result,
            credential_binding,
            credential_snapshot,
            credential_freshness,
            credential_lease,
            credential_claim,
            credential_attempt,
            credential_result,
        )
        if any(item.scope != scope for item in objects):
            return None
        zero_authority_objects = (
            route_binding,
            route_snapshot,
            endpoint_freshness,
            endpoint_claim,
            endpoint_attempt,
            endpoint_result,
            credential_binding,
            credential_snapshot,
            credential_freshness,
            credential_claim,
            credential_attempt,
            credential_result,
        )
        if any(any(item.authority.canonical_value().values()) for item in zero_authority_objects):
            return None

        if (
            endpoint_result.materialization_id != request.expected_endpoint_materialization_id
            or endpoint_result.canonical_digest != request.expected_endpoint_materialization_digest
            or endpoint_result.state.value != "materialized_protected"
            or endpoint_result.failure_class is not None
            or endpoint_result.protected_artifact_id is None
            or endpoint_result.protected_artifact_digest is None
            or endpoint_result.usable_until is None
            or endpoint_result.protected_artifact_revoked is not False
            or endpoint_result.cleanup_confirmed is not True
            or credential_result.materialization_id
            != request.expected_credential_materialization_id
            or credential_result.canonical_digest
            != request.expected_credential_materialization_digest
            or credential_result.state.value != "materialized_protected"
            or credential_result.failure_class is not None
            or credential_result.protected_artifact_id is None
            or credential_result.protected_artifact_digest is None
            or credential_result.usable_until is None
            or credential_result.protected_artifact_revoked is not False
            or credential_result.cleanup_confirmed is not True
        ):
            return None
        if require_live_overlap and not (
            observed_at < endpoint_result.usable_until
            and observed_at < credential_result.usable_until
        ):
            return None

        endpoint_chain_matches = (
            route_binding.transport_route_snapshot_id == route_snapshot.snapshot_id
            and route_binding.transport_route_snapshot_digest == route_snapshot.canonical_digest
            and endpoint_freshness.physical_transport_route_binding_id == route_binding.binding_id
            and endpoint_freshness.physical_transport_route_binding_digest
            == route_binding.canonical_digest
            and endpoint_freshness.transport_route_snapshot_id == route_snapshot.snapshot_id
            and endpoint_freshness.transport_route_snapshot_digest
            == route_snapshot.canonical_digest
            and endpoint_lease.freshness_admission_id == endpoint_freshness.freshness_admission_id
            and endpoint_lease.freshness_admission_digest == endpoint_freshness.canonical_digest
            and endpoint_lease.physical_transport_route_binding_id == route_binding.binding_id
            and endpoint_lease.physical_transport_route_binding_digest
            == route_binding.canonical_digest
            and endpoint_lease.transport_route_snapshot_id == route_snapshot.snapshot_id
            and endpoint_lease.transport_route_snapshot_digest == route_snapshot.canonical_digest
            and endpoint_claim.authorization_lease_id == endpoint_lease.authorization_lease_id
            and endpoint_claim.authorization_lease_digest == endpoint_lease.canonical_digest
            and endpoint_claim.freshness_admission_id == endpoint_freshness.freshness_admission_id
            and endpoint_claim.freshness_admission_digest == endpoint_freshness.canonical_digest
            and endpoint_attempt.consumption_claim_id == endpoint_claim.claim_id
            and endpoint_attempt.authorization_lease_id == endpoint_lease.authorization_lease_id
            and endpoint_attempt.authorization_lease_digest == endpoint_lease.canonical_digest
            and endpoint_attempt.freshness_admission_id == endpoint_freshness.freshness_admission_id
            and endpoint_attempt.freshness_admission_digest == endpoint_freshness.canonical_digest
            and endpoint_attempt.physical_transport_route_binding_id == route_binding.binding_id
            and endpoint_attempt.physical_transport_route_binding_digest
            == route_binding.canonical_digest
            and endpoint_attempt.transport_route_snapshot_id == route_snapshot.snapshot_id
            and endpoint_attempt.transport_route_snapshot_digest == route_snapshot.canonical_digest
            and endpoint_attempt.attempt_id == endpoint_claim.attempt_id
            and endpoint_attempt.materialization_id == endpoint_claim.materialization_id
            and endpoint_result.attempt_id == endpoint_attempt.attempt_id
            and endpoint_result.attempt_digest == endpoint_attempt.canonical_digest
            and endpoint_result.consumption_claim_id == endpoint_claim.claim_id
            and endpoint_result.consumption_claim_digest == endpoint_claim.canonical_digest
            and endpoint_result.authorization_lease_id == endpoint_lease.authorization_lease_id
            and endpoint_result.authorization_lease_digest == endpoint_lease.canonical_digest
            and endpoint_result.freshness_admission_id == endpoint_freshness.freshness_admission_id
            and endpoint_result.freshness_admission_digest == endpoint_freshness.canonical_digest
            and endpoint_result.transport_route_snapshot_id == route_snapshot.snapshot_id
            and endpoint_result.transport_route_snapshot_digest == route_snapshot.canonical_digest
            and endpoint_result.resolver_subject_id == endpoint_lease.resolver_subject_id
        )
        credential_chain_matches = (
            credential_binding.physical_transport_route_binding_id == route_binding.binding_id
            and credential_binding.physical_transport_route_binding_digest
            == route_binding.canonical_digest
            and credential_binding.transport_route_snapshot_id == route_snapshot.snapshot_id
            and credential_binding.transport_route_snapshot_digest
            == route_snapshot.canonical_digest
            and credential_binding.credential_assignment_snapshot_id
            == credential_snapshot.snapshot_id
            and credential_binding.credential_assignment_snapshot_digest
            == credential_snapshot.canonical_digest
            and credential_snapshot.route_snapshot_id == route_snapshot.snapshot_id
            and credential_snapshot.route_id == route_snapshot.route_id
            and credential_snapshot.route_revision == route_snapshot.route_revision
            and credential_snapshot.source_route_digest == route_snapshot.source_route_digest
            and credential_snapshot.credential_requirement_profile_id
            == route_snapshot.credential_requirement_profile_id
            and credential_snapshot.credential_requirement_profile_version
            == route_snapshot.credential_requirement_profile_version
            and credential_snapshot.credential_requirement_profile_digest
            == route_snapshot.credential_requirement_profile_digest
            and credential_snapshot.authentication_mechanism_class
            == route_snapshot.authentication_mechanism_class
            and credential_snapshot.principal_class == route_snapshot.principal_class
            and credential_freshness.physical_transport_credential_assignment_binding_id
            == credential_binding.binding_id
            and credential_freshness.physical_transport_credential_assignment_binding_digest
            == credential_binding.canonical_digest
            and credential_freshness.credential_assignment_snapshot_id
            == credential_snapshot.snapshot_id
            and credential_freshness.credential_assignment_snapshot_digest
            == credential_snapshot.canonical_digest
            and credential_lease.freshness_admission_id
            == credential_freshness.freshness_admission_id
            and credential_lease.freshness_admission_digest == credential_freshness.canonical_digest
            and credential_lease.physical_transport_credential_assignment_binding_id
            == credential_binding.binding_id
            and credential_lease.physical_transport_credential_assignment_binding_digest
            == credential_binding.canonical_digest
            and credential_lease.credential_assignment_snapshot_id
            == credential_snapshot.snapshot_id
            and credential_lease.credential_assignment_snapshot_digest
            == credential_snapshot.canonical_digest
            and credential_claim.authorization_lease_id == credential_lease.authorization_lease_id
            and credential_claim.authorization_lease_digest == credential_lease.canonical_digest
            and credential_claim.freshness_admission_id
            == credential_freshness.freshness_admission_id
            and credential_claim.freshness_admission_digest == credential_freshness.canonical_digest
            and credential_attempt.consumption_claim_id == credential_claim.claim_id
            and credential_attempt.authorization_lease_id == credential_lease.authorization_lease_id
            and credential_attempt.authorization_lease_digest == credential_lease.canonical_digest
            and credential_attempt.freshness_admission_id
            == credential_freshness.freshness_admission_id
            and credential_attempt.freshness_admission_digest
            == credential_freshness.canonical_digest
            and credential_attempt.physical_transport_credential_assignment_binding_id
            == credential_binding.binding_id
            and credential_attempt.physical_transport_credential_assignment_binding_digest
            == credential_binding.canonical_digest
            and credential_attempt.credential_assignment_snapshot_id
            == credential_snapshot.snapshot_id
            and credential_attempt.credential_assignment_snapshot_digest
            == credential_snapshot.canonical_digest
            and credential_attempt.attempt_id == credential_claim.attempt_id
            and credential_attempt.materialization_id == credential_claim.materialization_id
            and credential_result.attempt_id == credential_attempt.attempt_id
            and credential_result.attempt_digest == credential_attempt.canonical_digest
            and credential_result.consumption_claim_id == credential_claim.claim_id
            and credential_result.consumption_claim_digest == credential_claim.canonical_digest
            and credential_result.authorization_lease_id == credential_lease.authorization_lease_id
            and credential_result.authorization_lease_digest == credential_lease.canonical_digest
            and credential_result.freshness_admission_id
            == credential_freshness.freshness_admission_id
            and credential_result.freshness_admission_digest
            == credential_freshness.canonical_digest
            and credential_result.credential_assignment_snapshot_id
            == credential_snapshot.snapshot_id
            and credential_result.credential_assignment_snapshot_digest
            == credential_snapshot.canonical_digest
            and credential_result.assignment_id == credential_snapshot.assignment_id
            and credential_result.assignment_revision == credential_snapshot.assignment_revision
            and credential_result.credential_generation == credential_snapshot.credential_generation
            and credential_result.rotation_epoch == credential_snapshot.rotation_epoch
            and credential_result.accessor_subject_id == credential_lease.accessor_subject_id
        )
        if not endpoint_chain_matches or not credential_chain_matches:
            return None
        return {
            "route_binding": route_binding,
            "route_snapshot": route_snapshot,
            "endpoint_result": endpoint_result,
            "credential_binding": credential_binding,
            "credential_snapshot": credential_snapshot,
            "credential_result": credential_result,
        }

    @classmethod
    def _target_context_binding(
        cls,
        *,
        request: WorkflowEventPhysicalTransportTargetContextBindingRequest,
        evidence: dict[str, Any],
        bound_at: datetime,
    ) -> WorkflowEventPhysicalTransportTargetContextBinding:
        policy = code_owned_workflow_event_physical_transport_target_context_binding_policy()
        route_binding = evidence["route_binding"]
        route_snapshot = evidence["route_snapshot"]
        endpoint_result = evidence["endpoint_result"]
        credential_binding = evidence["credential_binding"]
        credential_snapshot = evidence["credential_snapshot"]
        credential_result = evidence["credential_result"]
        commitment = cls._target_context_commitment(evidence=evidence, policy=policy)
        identity_digest = canonical_digest(
            {
                "binder_subject_id": request.binder_subject_id,
                "request_fingerprint": request.request_fingerprint,
                "target_context_commitment": commitment,
            }
        )
        values: dict[str, object] = {
            "binding_id": f"workflow-target-context-binding.{identity_digest[:48]}",
            "physical_transport_route_binding_id": route_binding.binding_id,
            "physical_transport_route_binding_digest": route_binding.canonical_digest,
            "transport_route_snapshot_id": route_snapshot.snapshot_id,
            "transport_route_snapshot_digest": route_snapshot.canonical_digest,
            "endpoint_materialization_id": endpoint_result.materialization_id,
            "endpoint_materialization_digest": endpoint_result.canonical_digest,
            "physical_transport_credential_assignment_binding_id": credential_binding.binding_id,
            "physical_transport_credential_assignment_binding_digest": (
                credential_binding.canonical_digest
            ),
            "credential_assignment_snapshot_id": credential_snapshot.snapshot_id,
            "credential_assignment_snapshot_digest": credential_snapshot.canonical_digest,
            "credential_materialization_id": credential_result.materialization_id,
            "credential_materialization_digest": credential_result.canonical_digest,
            "resolver_subject_id": endpoint_result.resolver_subject_id,
            "accessor_subject_id": credential_result.accessor_subject_id,
            "target_context_schema_id": policy.target_context_schema_id,
            "target_context_schema_version": policy.target_context_schema_version,
            "target_context_commitment": commitment,
            "scope": request.scope,
            "binder_subject_id": request.binder_subject_id,
            "bound_at": bound_at,
            "joint_usable_until": min(endpoint_result.usable_until, credential_result.usable_until),
            "policy_id": policy.policy_id,
            "policy_version": policy.policy_version,
            "policy_digest": policy.canonical_digest,
            "state": WorkflowEventPhysicalTransportTargetContextBindingState.BOUND,
            "authority": WorkflowEventPhysicalTransportTargetContextBindingAuthority(),
        }
        payload = cls._target_context_binding_payload_values(values)
        return WorkflowEventPhysicalTransportTargetContextBinding(
            **cast(Any, values), canonical_digest=canonical_digest(payload)
        )

    @staticmethod
    def _target_context_commitment(*, evidence: dict[str, Any], policy: Any) -> str:
        route_binding = evidence["route_binding"]
        route_snapshot = evidence["route_snapshot"]
        endpoint_result = evidence["endpoint_result"]
        credential_binding = evidence["credential_binding"]
        credential_snapshot = evidence["credential_snapshot"]
        credential_result = evidence["credential_result"]
        return canonical_digest(
            {
                "credential_assignment_binding": {
                    "digest": credential_binding.canonical_digest,
                    "id": credential_binding.binding_id,
                },
                "credential_assignment_snapshot": {
                    "digest": credential_snapshot.canonical_digest,
                    "id": credential_snapshot.snapshot_id,
                    "target_scope_commitment": credential_snapshot.target_scope_commitment,
                },
                "credential_materialization": {
                    "digest": credential_result.canonical_digest,
                    "id": credential_result.materialization_id,
                },
                "destination": {
                    "id": route_snapshot.destination_id,
                    "revision": route_snapshot.destination_revision,
                },
                "endpoint_materialization": {
                    "digest": endpoint_result.canonical_digest,
                    "id": endpoint_result.materialization_id,
                },
                "endpoint_set": {
                    "id": route_snapshot.endpoint_set_id,
                    "revision": route_snapshot.endpoint_set_revision,
                },
                "physical_transport_route_binding": {
                    "digest": route_binding.canonical_digest,
                    "id": route_binding.binding_id,
                },
                "routing_contract": {
                    "id": route_snapshot.routing_contract_id,
                    "revision": route_snapshot.routing_contract_revision,
                },
                "schema_id": policy.target_context_schema_id,
                "schema_version": policy.target_context_schema_version,
                "scope": route_binding.scope.canonical_value(),
                "transport_route_snapshot": {
                    "digest": route_snapshot.canonical_digest,
                    "id": route_snapshot.snapshot_id,
                    "route_id": route_snapshot.route_id,
                    "route_revision": route_snapshot.route_revision,
                    "source_route_digest": route_snapshot.source_route_digest,
                },
            }
        )

    @staticmethod
    def _target_context_binding_payload_values(values: dict[str, object]) -> dict[str, object]:
        return {
            key: (
                value.canonical_value()
                if isinstance(
                    value,
                    (
                        WorkflowScope,
                        WorkflowEventPhysicalTransportTargetContextBindingAuthority,
                    ),
                )
                else value.isoformat()
                if isinstance(value, datetime)
                else value.value
                if isinstance(value, Enum)
                else value
            )
            for key, value in values.items()
        }

    @staticmethod
    def _target_context_binding_payload(
        binding: WorkflowEventPhysicalTransportTargetContextBinding,
    ) -> dict[str, object]:
        return binding.canonical_value()

    @classmethod
    def _target_context_binding_model(
        cls, binding: WorkflowEventPhysicalTransportTargetContextBinding
    ) -> WorkflowEventPhysicalTransportTargetContextBindingModel:
        authority = binding.authority
        return WorkflowEventPhysicalTransportTargetContextBindingModel(
            binding_id=binding.binding_id,
            physical_transport_route_binding_id=binding.physical_transport_route_binding_id,
            physical_transport_route_binding_digest=(
                binding.physical_transport_route_binding_digest
            ),
            transport_route_snapshot_id=binding.transport_route_snapshot_id,
            transport_route_snapshot_digest=binding.transport_route_snapshot_digest,
            endpoint_materialization_id=binding.endpoint_materialization_id,
            endpoint_materialization_digest=binding.endpoint_materialization_digest,
            physical_transport_credential_assignment_binding_id=(
                binding.physical_transport_credential_assignment_binding_id
            ),
            physical_transport_credential_assignment_binding_digest=(
                binding.physical_transport_credential_assignment_binding_digest
            ),
            credential_assignment_snapshot_id=binding.credential_assignment_snapshot_id,
            credential_assignment_snapshot_digest=binding.credential_assignment_snapshot_digest,
            credential_materialization_id=binding.credential_materialization_id,
            credential_materialization_digest=binding.credential_materialization_digest,
            resolver_subject_id=binding.resolver_subject_id,
            accessor_subject_id=binding.accessor_subject_id,
            target_context_schema_id=binding.target_context_schema_id,
            target_context_schema_version=binding.target_context_schema_version,
            target_context_commitment=binding.target_context_commitment,
            organization_id=binding.scope.organization_id,
            environment_id=binding.scope.environment_id,
            site_id=binding.scope.site_id,
            binder_subject_id=binding.binder_subject_id,
            bound_at=binding.bound_at,
            joint_usable_until=binding.joint_usable_until,
            policy_id=binding.policy_id,
            policy_version=binding.policy_version,
            policy_digest=binding.policy_digest,
            state=binding.state.value,
            endpoint_resolution_authority_granted=authority.endpoint_resolution_authorized,
            protected_artifact_access_authority_granted=(
                authority.protected_artifact_access_authorized
            ),
            route_selection_authority_granted=authority.route_selection_authorized,
            route_binding_authority_granted=authority.route_binding_authorized,
            credential_selection_authority_granted=authority.credential_selection_authorized,
            credential_assignment_binding_authority_granted=(
                authority.credential_assignment_binding_authorized
            ),
            credential_access_authority_granted=authority.credential_access_authorized,
            credential_brokerage_authority_granted=authority.credential_brokerage_authorized,
            credential_resolution_authority_granted=authority.credential_resolution_authorized,
            credential_delivery_authority_granted=authority.credential_delivery_authorized,
            network_access_authority_granted=authority.network_access_authorized,
            readiness_probe_authority_granted=authority.readiness_probe_authorized,
            publication_authority_granted=authority.publication_authorized,
            delivery_authority_granted=authority.delivery_authorized,
            dispatch_authority_granted=authority.dispatch_authorized,
            execution_authority_granted=authority.execution_authorized,
            infrastructure_mutation_authority_granted=(
                authority.infrastructure_mutation_authorized
            ),
            canonical_digest=binding.canonical_digest,
            payload=cls._target_context_binding_payload(binding),
        )

    @classmethod
    def _target_context_binding_from_row(
        cls, row: WorkflowEventPhysicalTransportTargetContextBindingModel
    ) -> WorkflowEventPhysicalTransportTargetContextBinding:
        raw = dict(row.payload)
        try:
            raw["scope"] = WorkflowScope(**cast(Any, raw["scope"]))
            raw["bound_at"] = datetime.fromisoformat(str(raw["bound_at"]))
            raw["joint_usable_until"] = datetime.fromisoformat(str(raw["joint_usable_until"]))
            raw["state"] = WorkflowEventPhysicalTransportTargetContextBindingState(
                str(raw["state"])
            )
            raw["authority"] = WorkflowEventPhysicalTransportTargetContextBindingAuthority(
                **cast(Any, raw["authority"])
            )
            binding = WorkflowEventPhysicalTransportTargetContextBinding(**cast(Any, raw))
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowEventPhysicalTransportTargetContextBindingError(
                "workflow_target_context_binding_repository_contract_violation",
                "The target-context binding record is invalid.",
            ) from exc
        authority = binding.authority
        if (
            row.binding_id != binding.binding_id
            or row.physical_transport_route_binding_id
            != binding.physical_transport_route_binding_id
            or row.physical_transport_route_binding_digest
            != binding.physical_transport_route_binding_digest
            or row.transport_route_snapshot_id != binding.transport_route_snapshot_id
            or row.transport_route_snapshot_digest != binding.transport_route_snapshot_digest
            or row.endpoint_materialization_id != binding.endpoint_materialization_id
            or row.endpoint_materialization_digest != binding.endpoint_materialization_digest
            or row.physical_transport_credential_assignment_binding_id
            != binding.physical_transport_credential_assignment_binding_id
            or row.physical_transport_credential_assignment_binding_digest
            != binding.physical_transport_credential_assignment_binding_digest
            or row.credential_assignment_snapshot_id != binding.credential_assignment_snapshot_id
            or row.credential_assignment_snapshot_digest
            != binding.credential_assignment_snapshot_digest
            or row.credential_materialization_id != binding.credential_materialization_id
            or row.credential_materialization_digest != binding.credential_materialization_digest
            or row.resolver_subject_id != binding.resolver_subject_id
            or row.accessor_subject_id != binding.accessor_subject_id
            or row.target_context_schema_id != binding.target_context_schema_id
            or row.target_context_schema_version != binding.target_context_schema_version
            or row.target_context_commitment != binding.target_context_commitment
            or row.organization_id != binding.scope.organization_id
            or row.environment_id != binding.scope.environment_id
            or row.site_id != binding.scope.site_id
            or row.binder_subject_id != binding.binder_subject_id
            or row.bound_at != binding.bound_at
            or row.joint_usable_until != binding.joint_usable_until
            or row.policy_id != binding.policy_id
            or row.policy_version != binding.policy_version
            or row.policy_digest != binding.policy_digest
            or row.state != binding.state.value
            or row.endpoint_resolution_authority_granted != authority.endpoint_resolution_authorized
            or row.protected_artifact_access_authority_granted
            != authority.protected_artifact_access_authorized
            or row.route_selection_authority_granted != authority.route_selection_authorized
            or row.route_binding_authority_granted != authority.route_binding_authorized
            or row.credential_selection_authority_granted
            != authority.credential_selection_authorized
            or row.credential_assignment_binding_authority_granted
            != authority.credential_assignment_binding_authorized
            or row.credential_access_authority_granted != authority.credential_access_authorized
            or row.credential_brokerage_authority_granted
            != authority.credential_brokerage_authorized
            or row.credential_resolution_authority_granted
            != authority.credential_resolution_authorized
            or row.credential_delivery_authority_granted != authority.credential_delivery_authorized
            or row.network_access_authority_granted != authority.network_access_authorized
            or row.readiness_probe_authority_granted != authority.readiness_probe_authorized
            or row.publication_authority_granted != authority.publication_authorized
            or row.delivery_authority_granted != authority.delivery_authorized
            or row.dispatch_authority_granted != authority.dispatch_authorized
            or row.execution_authority_granted != authority.execution_authorized
            or row.infrastructure_mutation_authority_granted
            != authority.infrastructure_mutation_authorized
            or row.canonical_digest != binding.canonical_digest
            or row.payload != cls._target_context_binding_payload(binding)
            or any(authority.canonical_value().values())
        ):
            cls._target_context_binding_contract_violation()
        return binding

    @classmethod
    def _target_context_binding_claim_model(
        cls,
        request: WorkflowEventPhysicalTransportTargetContextBindingRequest,
        *,
        binding: WorkflowEventPhysicalTransportTargetContextBinding,
    ) -> WorkflowEventPhysicalTransportTargetContextBindingClaimModel:
        scope_id = cls._target_context_binding_idempotency_scope(
            request.scope, request.binder_subject_id
        )
        payload = cls._target_context_binding_claim_payload(
            request=request, binding=binding, scope_id=scope_id
        )
        claim_digest = canonical_digest(payload)
        return WorkflowEventPhysicalTransportTargetContextBindingClaimModel(
            claim_id=f"workflow-target-context-binding-claim.{claim_digest[:48]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=binding.canonical_digest,
            binding_id=binding.binding_id,
            physical_transport_route_binding_id=binding.physical_transport_route_binding_id,
            transport_route_snapshot_id=binding.transport_route_snapshot_id,
            endpoint_materialization_id=binding.endpoint_materialization_id,
            physical_transport_credential_assignment_binding_id=(
                binding.physical_transport_credential_assignment_binding_id
            ),
            credential_assignment_snapshot_id=binding.credential_assignment_snapshot_id,
            credential_materialization_id=binding.credential_materialization_id,
            target_context_schema_id=binding.target_context_schema_id,
            target_context_schema_version=binding.target_context_schema_version,
            policy_id=binding.policy_id,
            policy_version=binding.policy_version,
            policy_digest=binding.policy_digest,
            organization_id=binding.scope.organization_id,
            environment_id=binding.scope.environment_id,
            site_id=binding.scope.site_id,
            binder_subject_id=binding.binder_subject_id,
            created_at=binding.bound_at,
            canonical_digest=claim_digest,
            payload=payload,
        )

    @classmethod
    def _target_context_binding_claim_payload(
        cls,
        *,
        request: WorkflowEventPhysicalTransportTargetContextBindingRequest,
        binding: WorkflowEventPhysicalTransportTargetContextBinding,
        scope_id: str,
    ) -> dict[str, object]:
        return {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_binding": cls._target_context_binding_payload(binding),
            "result_digest": binding.canonical_digest,
        }

    @classmethod
    def _target_context_binding_from_claim(
        cls,
        claim: WorkflowEventPhysicalTransportTargetContextBindingClaimModel,
        *,
        binding_row: WorkflowEventPhysicalTransportTargetContextBindingModel,
    ) -> WorkflowEventPhysicalTransportTargetContextBinding:
        binding = cls._target_context_binding_from_row(binding_row)
        scope_id = cls._target_context_binding_idempotency_scope(
            binding.scope, binding.binder_subject_id
        )
        request = WorkflowEventPhysicalTransportTargetContextBindingRequest(
            expected_endpoint_materialization_id=binding.endpoint_materialization_id,
            expected_endpoint_materialization_digest=binding.endpoint_materialization_digest,
            expected_credential_materialization_id=binding.credential_materialization_id,
            expected_credential_materialization_digest=binding.credential_materialization_digest,
            expected_policy_id=binding.policy_id,
            expected_policy_version=binding.policy_version,
            expected_policy_digest=binding.policy_digest,
            scope=binding.scope,
            binder_subject_id=binding.binder_subject_id,
            requested_at=binding.bound_at,
            idempotency_key=claim.idempotency_key,
            request_fingerprint=claim.request_fingerprint,
            required_precommit_audit=cast(Any, None),
        )
        payload = cls._target_context_binding_claim_payload(
            request=request, binding=binding, scope_id=scope_id
        )
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != binding.canonical_digest
            or claim.binding_id != binding.binding_id
            or claim.physical_transport_route_binding_id
            != binding.physical_transport_route_binding_id
            or claim.transport_route_snapshot_id != binding.transport_route_snapshot_id
            or claim.endpoint_materialization_id != binding.endpoint_materialization_id
            or claim.physical_transport_credential_assignment_binding_id
            != binding.physical_transport_credential_assignment_binding_id
            or claim.credential_assignment_snapshot_id != binding.credential_assignment_snapshot_id
            or claim.credential_materialization_id != binding.credential_materialization_id
            or claim.target_context_schema_id != binding.target_context_schema_id
            or claim.target_context_schema_version != binding.target_context_schema_version
            or claim.policy_id != binding.policy_id
            or claim.policy_version != binding.policy_version
            or claim.policy_digest != binding.policy_digest
            or claim.organization_id != binding.scope.organization_id
            or claim.environment_id != binding.scope.environment_id
            or claim.site_id != binding.scope.site_id
            or claim.binder_subject_id != binding.binder_subject_id
            or claim.created_at.tzinfo is None
            or claim.created_at != binding.bound_at
            or claim.payload != payload
            or claim.canonical_digest != canonical_digest(payload)
        ):
            cls._target_context_binding_contract_violation()
        return binding

    @staticmethod
    def _target_context_binding_idempotency_scope(
        scope: WorkflowScope, binder_subject_id: str
    ) -> str:
        return canonical_digest(
            {
                "binder_subject_id": binder_subject_id,
                "operation": "bind-workflow-physical-transport-target-context",
                "scope": scope.canonical_value(),
            }
        )

    @staticmethod
    def _validate_target_context_binding_request(
        request: WorkflowEventPhysicalTransportTargetContextBindingRequest,
    ) -> None:
        policy = code_owned_workflow_event_physical_transport_target_context_binding_policy()
        identifiers = (
            request.expected_endpoint_materialization_id,
            request.expected_credential_materialization_id,
            request.expected_policy_id,
            request.expected_policy_version,
            request.binder_subject_id,
            request.idempotency_key,
        )
        digests = (
            request.expected_endpoint_materialization_digest,
            request.expected_credential_materialization_digest,
            request.expected_policy_digest,
            request.request_fingerprint,
        )
        if (
            any(not value or value != value.strip() or len(value) > 240 for value in identifiers)
            or len(request.idempotency_key) > 128
            or any(len(value) != 64 for value in digests)
            or request.requested_at.tzinfo is None
            or request.expected_policy_id != policy.policy_id
            or request.expected_policy_version != policy.policy_version
            or request.expected_policy_digest != policy.canonical_digest
        ):
            raise ValueError("target-context binding request is invalid")

    @staticmethod
    def _target_context_binding_contract_violation() -> NoReturn:
        raise WorkflowEventPhysicalTransportTargetContextBindingError(
            "workflow_target_context_binding_repository_contract_violation",
            "The target-context binding does not match durable evidence.",
        )

    async def get_dispatch_intent_staging_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowDispatchIntentStagingIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_dispatch_intent_staging_claim(
                session,
                scope=scope,
                worker_subject_id=worker_subject_id,
                idempotency_key=idempotency_key,
            )
            if claim is None:
                return None
            intent, outbox_entry = self._dispatch_pair_from_claim(claim)
            return WorkflowDispatchIntentStagingIdempotencyRecord(
                request_fingerprint=claim.request_fingerprint,
                dispatch_intent=intent,
                outbox_entry=outbox_entry,
            )

    async def stage_dispatch_intent(
        self, request: WorkflowDispatchIntentStagingRequest
    ) -> WorkflowDispatchIntentStagingResult:
        self._validate_dispatch_intent_staging_request(request)
        intent = request.candidate
        outbox_entry = request.outbox_entry
        if outbox_entry is None:
            raise ValueError("workflow dispatch outbox entry is required")
        async with self._sessions() as session:
            replay = await self._dispatch_intent_staging_replay(session, request=request)
            if replay is not None:
                return replay

            plan_row = cast(
                WorkflowRunPlanModel | None,
                await session.scalar(
                    select(WorkflowRunPlanModel)
                    .where(WorkflowRunPlanModel.plan_id == intent.plan_id)
                    .with_for_update()
                ),
            )
            lease_row = cast(
                WorkflowOrchestrationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOrchestrationLeaseModel)
                    .where(WorkflowOrchestrationLeaseModel.plan_id == intent.plan_id)
                    .with_for_update()
                ),
            )
            run_row = cast(
                WorkflowExecutionRunModel | None,
                await session.scalar(
                    select(WorkflowExecutionRunModel)
                    .where(WorkflowExecutionRunModel.run_id == intent.run_id)
                    .with_for_update()
                ),
            )
            step_row = cast(
                WorkflowExecutionStepRunModel | None,
                await session.scalar(
                    select(WorkflowExecutionStepRunModel)
                    .where(WorkflowExecutionStepRunModel.step_run_id == intent.step_run_id)
                    .with_for_update()
                ),
            )
            attempt_row = cast(
                WorkflowExecutionAttemptModel | None,
                await session.scalar(
                    select(WorkflowExecutionAttemptModel)
                    .where(WorkflowExecutionAttemptModel.attempt_id == intent.attempt_id)
                    .with_for_update()
                ),
            )
            if not self._dispatch_intent_sources_match(
                plan_row=plan_row,
                lease_row=lease_row,
                run_row=run_row,
                step_row=step_row,
                attempt_row=attempt_row,
                request=request,
            ):
                await session.rollback()
                return WorkflowDispatchIntentStagingResult(
                    status=WorkflowDispatchIntentStagingStatus.STATE_CONFLICT,
                    dispatch_intent=None,
                    outbox_entry=None,
                )

            existing = cast(
                WorkflowDispatchIntentModel | None,
                await session.scalar(
                    select(WorkflowDispatchIntentModel)
                    .where(WorkflowDispatchIntentModel.attempt_id == intent.attempt_id)
                    .with_for_update()
                ),
            )
            if existing is not None:
                existing_outbox = cast(
                    WorkflowDispatchOutboxEntryModel | None,
                    await session.scalar(
                        select(WorkflowDispatchOutboxEntryModel)
                        .where(
                            WorkflowDispatchOutboxEntryModel.dispatch_intent_id
                            == existing.dispatch_intent_id
                        )
                        .with_for_update()
                    ),
                )
                await session.rollback()
                return WorkflowDispatchIntentStagingResult(
                    status=WorkflowDispatchIntentStagingStatus.STATE_CONFLICT,
                    dispatch_intent=self._dispatch_intent_from_row(existing),
                    outbox_entry=(
                        None
                        if existing_outbox is None
                        else self._dispatch_outbox_from_row(existing_outbox)
                    ),
                )

            try:
                session.add(self._dispatch_intent_model(intent))
                session.add(self._dispatch_outbox_model(outbox_entry))
                session.add(self._dispatch_intent_staging_claim_model(request))
                await session.commit()
                return WorkflowDispatchIntentStagingResult(
                    status=WorkflowDispatchIntentStagingStatus.STAGED,
                    dispatch_intent=intent,
                    outbox_entry=outbox_entry,
                )
            except IntegrityError:
                await session.rollback()

        async with self._sessions() as session:
            replay = await self._dispatch_intent_staging_replay(session, request=request)
            if replay is not None:
                return replay
        return WorkflowDispatchIntentStagingResult(
            status=WorkflowDispatchIntentStagingStatus.STATE_CONFLICT,
            dispatch_intent=None,
            outbox_entry=None,
        )

    async def _mutate_publication_lease(
        self, request: WorkflowOutboxPublicationLeaseMutationRequest
    ) -> WorkflowOutboxPublicationLeaseMutationResult:
        self._validate_publication_lease_mutation_request(request)
        updated = request.updated_lease
        async with self._sessions() as session:
            outbox_row = cast(
                WorkflowDispatchOutboxEntryModel | None,
                await session.scalar(
                    select(WorkflowDispatchOutboxEntryModel)
                    .where(
                        WorkflowDispatchOutboxEntryModel.outbox_entry_id == updated.outbox_entry_id
                    )
                    .with_for_update()
                ),
            )
            plan_row = cast(
                WorkflowRunPlanModel | None,
                await session.scalar(
                    select(WorkflowRunPlanModel)
                    .where(WorkflowRunPlanModel.plan_id == updated.plan_id)
                    .with_for_update()
                ),
            )
            orchestration_lease_row = cast(
                WorkflowOrchestrationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOrchestrationLeaseModel)
                    .where(WorkflowOrchestrationLeaseModel.plan_id == updated.plan_id)
                    .with_for_update()
                ),
            )
            current_row = cast(
                WorkflowOutboxPublicationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOutboxPublicationLeaseModel)
                    .where(
                        WorkflowOutboxPublicationLeaseModel.outbox_entry_id
                        == updated.outbox_entry_id
                    )
                    .with_for_update()
                ),
            )
            if not self._publication_lease_mutation_evidence_matches(
                outbox_row=outbox_row,
                plan_row=plan_row,
                orchestration_lease_row=orchestration_lease_row,
                request=request,
            ):
                await session.rollback()
                return WorkflowOutboxPublicationLeaseMutationResult(
                    WorkflowOutboxPublicationLeaseMutationStatus.EVIDENCE_CONFLICT,
                    None,
                )
            if current_row is None:
                await session.rollback()
                return WorkflowOutboxPublicationLeaseMutationResult(
                    WorkflowOutboxPublicationLeaseMutationStatus.NOT_FOUND,
                    None,
                )
            current = self._publication_lease_from_row(current_row)
            if (
                current.publication_lease_id != request.expected_publication_lease_id
                or current.canonical_digest != request.expected_publication_lease_digest
                or current.publication_fencing_token != request.expected_publication_fencing_token
                or current.publisher_subject_id != request.publisher_subject_id
                or current.effective_state(requested_at=request.requested_at)
                is not WorkflowOutboxPublicationLeaseEffectiveState.ACTIVE
                or not self._same_publication_lease_generation(current, updated)
            ):
                await session.rollback()
                return WorkflowOutboxPublicationLeaseMutationResult(
                    WorkflowOutboxPublicationLeaseMutationStatus.LEASE_CONFLICT,
                    current,
                )
            result = cast(
                CursorResult[Any],
                await session.execute(
                    update(WorkflowOutboxPublicationLeaseModel)
                    .where(
                        WorkflowOutboxPublicationLeaseModel.outbox_entry_id
                        == updated.outbox_entry_id,
                        WorkflowOutboxPublicationLeaseModel.publication_lease_id
                        == request.expected_publication_lease_id,
                        WorkflowOutboxPublicationLeaseModel.canonical_digest
                        == request.expected_publication_lease_digest,
                        WorkflowOutboxPublicationLeaseModel.publication_fencing_token
                        == request.expected_publication_fencing_token,
                        WorkflowOutboxPublicationLeaseModel.publisher_subject_id
                        == request.publisher_subject_id,
                        WorkflowOutboxPublicationLeaseModel.version == current_row.version,
                        WorkflowOutboxPublicationLeaseModel.state
                        == WorkflowOutboxPublicationLeaseState.ACTIVE.value,
                        WorkflowOutboxPublicationLeaseModel.expires_at > request.requested_at,
                    )
                    .values(
                        **self._publication_lease_values(
                            updated,
                            version=current_row.version + 1,
                        )
                    )
                ),
            )
            if result.rowcount != 1:
                await session.rollback()
                return WorkflowOutboxPublicationLeaseMutationResult(
                    WorkflowOutboxPublicationLeaseMutationStatus.LEASE_CONFLICT,
                    current,
                )
            await session.commit()
            return WorkflowOutboxPublicationLeaseMutationResult(
                WorkflowOutboxPublicationLeaseMutationStatus.UPDATED,
                updated,
            )

    async def get_lease_acquire_request(
        self,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowLeaseAcquireIdempotencyRecord | None:
        async with self._sessions() as session:
            claim = await self._load_lease_claim(
                session,
                operation="acquire",
                scope=scope,
                worker_subject_id=worker_subject_id,
                idempotency_key=idempotency_key,
            )
            return None if claim is None else self._lease_record_from_claim(claim)

    async def acquire_lease(
        self, request: WorkflowLeaseAcquireRequest
    ) -> WorkflowLeaseAcquireResult:
        candidate = request.candidate
        async with self._sessions() as session:
            replay = await self._lease_acquire_replay(session, request=request)
            if replay is not None:
                return replay
            plan_row = cast(
                WorkflowRunPlanModel | None,
                await session.scalar(
                    select(WorkflowRunPlanModel)
                    .where(WorkflowRunPlanModel.plan_id == candidate.plan_id)
                    .with_for_update()
                ),
            )
            if not self._lease_plan_matches(plan_row, candidate, request.expected_plan_digest):
                await session.rollback()
                return WorkflowLeaseAcquireResult(WorkflowLeaseAcquireStatus.PLAN_CONFLICT, None)

            row = cast(
                WorkflowOrchestrationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOrchestrationLeaseModel)
                    .where(WorkflowOrchestrationLeaseModel.plan_id == candidate.plan_id)
                    .with_for_update()
                ),
            )
            current = None if row is None else self._lease_from_row(row)
            if not self._valid_lease_takeover(current, candidate, request):
                await session.rollback()
                return WorkflowLeaseAcquireResult(WorkflowLeaseAcquireStatus.CONTENDED, current)

            try:
                if row is None:
                    session.add(self._lease_model(candidate, version=1))
                else:
                    result = cast(
                        CursorResult[Any],
                        await session.execute(
                            update(WorkflowOrchestrationLeaseModel)
                            .where(
                                WorkflowOrchestrationLeaseModel.plan_id == candidate.plan_id,
                                WorkflowOrchestrationLeaseModel.version == row.version,
                                WorkflowOrchestrationLeaseModel.canonical_digest
                                == request.expected_current_lease_digest,
                                WorkflowOrchestrationLeaseModel.fencing_token
                                == request.expected_current_fencing_token,
                                or_(
                                    WorkflowOrchestrationLeaseModel.expires_at
                                    <= request.requested_at,
                                    WorkflowOrchestrationLeaseModel.state
                                    == WorkflowOrchestrationLeaseState.RELEASED.value,
                                ),
                            )
                            .values(**self._lease_values(candidate, version=row.version + 1))
                        ),
                    )
                    if result.rowcount != 1:
                        await session.rollback()
                        latest = await self.get_lease_by_plan_id(plan_id=candidate.plan_id)
                        return WorkflowLeaseAcquireResult(
                            WorkflowLeaseAcquireStatus.CONTENDED, latest
                        )
                session.add(self._lease_claim_model(request))
                await session.commit()
                return WorkflowLeaseAcquireResult(WorkflowLeaseAcquireStatus.ACQUIRED, candidate)
            except IntegrityError:
                await session.rollback()
        return await self._lease_acquire_after_integrity(request=request)

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
        candidate = request.updated_lease
        async with self._sessions() as session:
            plan_row = cast(
                WorkflowRunPlanModel | None,
                await session.scalar(
                    select(WorkflowRunPlanModel)
                    .where(WorkflowRunPlanModel.plan_id == candidate.plan_id)
                    .with_for_update()
                ),
            )
            if not self._lease_plan_matches(plan_row, candidate, request.expected_plan_digest):
                await session.rollback()
                return WorkflowLeaseMutationResult(WorkflowLeaseMutationStatus.PLAN_CONFLICT, None)
            row = cast(
                WorkflowOrchestrationLeaseModel | None,
                await session.scalar(
                    select(WorkflowOrchestrationLeaseModel)
                    .where(WorkflowOrchestrationLeaseModel.plan_id == candidate.plan_id)
                    .with_for_update()
                ),
            )
            if row is None:
                await session.rollback()
                return WorkflowLeaseMutationResult(WorkflowLeaseMutationStatus.NOT_FOUND, None)
            current = self._lease_from_row(row)
            if not self._valid_lease_mutation(current, candidate, request):
                await session.rollback()
                return WorkflowLeaseMutationResult(
                    WorkflowLeaseMutationStatus.LEASE_CONFLICT, current
                )
            result = cast(
                CursorResult[Any],
                await session.execute(
                    update(WorkflowOrchestrationLeaseModel)
                    .where(
                        WorkflowOrchestrationLeaseModel.plan_id == candidate.plan_id,
                        WorkflowOrchestrationLeaseModel.lease_id == request.expected_lease_id,
                        WorkflowOrchestrationLeaseModel.canonical_digest
                        == request.expected_lease_digest,
                        WorkflowOrchestrationLeaseModel.fencing_token
                        == request.expected_fencing_token,
                        WorkflowOrchestrationLeaseModel.worker_subject_id
                        == request.worker_subject_id,
                        WorkflowOrchestrationLeaseModel.version == row.version,
                        WorkflowOrchestrationLeaseModel.state
                        == WorkflowOrchestrationLeaseState.ACTIVE.value,
                        WorkflowOrchestrationLeaseModel.expires_at > request.requested_at,
                    )
                    .values(**self._lease_values(candidate, version=row.version + 1))
                ),
            )
            if result.rowcount != 1:
                await session.rollback()
                latest = await self.get_lease_by_plan_id(plan_id=candidate.plan_id)
                return WorkflowLeaseMutationResult(
                    WorkflowLeaseMutationStatus.LEASE_CONFLICT, latest
                )
            await session.commit()
            return WorkflowLeaseMutationResult(WorkflowLeaseMutationStatus.UPDATED, candidate)

    async def close(self) -> None:
        await self._engine.dispose()

    async def _materialization_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowRunMaterializationRequest,
    ) -> WorkflowRunMaterializationResult | None:
        run = request.candidate
        scope_id = self._materialization_scope_id(run)
        claim = cast(
            WorkflowRunMaterializationClaimModel | None,
            await session.scalar(
                select(WorkflowRunMaterializationClaimModel).where(
                    WorkflowRunMaterializationClaimModel.idempotency_scope_id == scope_id,
                    WorkflowRunMaterializationClaimModel.idempotency_key == request.idempotency_key,
                    WorkflowRunMaterializationClaimModel.organization_id
                    == run.scope.organization_id,
                    WorkflowRunMaterializationClaimModel.environment_id == run.scope.environment_id,
                    WorkflowRunMaterializationClaimModel.site_id == run.scope.site_id,
                    WorkflowRunMaterializationClaimModel.worker_subject_id
                    == run.materialized_by_subject_id,
                )
            ),
        )
        if claim is None:
            return None
        result = self._materialized_run_from_claim(claim)
        status = (
            WorkflowRunMaterializationStatus.REPLAY
            if claim.request_fingerprint == request.request_fingerprint
            else WorkflowRunMaterializationStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowRunMaterializationResult(status, result)

    @classmethod
    async def _load_materialization_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowRunMaterializationClaimModel | None:
        scope_id = canonical_digest(
            {
                "scope": scope.canonical_value(),
                "worker_subject_id": worker_subject_id,
            }
        )
        return cast(
            WorkflowRunMaterializationClaimModel | None,
            await session.scalar(
                select(WorkflowRunMaterializationClaimModel).where(
                    WorkflowRunMaterializationClaimModel.idempotency_scope_id == scope_id,
                    WorkflowRunMaterializationClaimModel.idempotency_key == idempotency_key,
                    WorkflowRunMaterializationClaimModel.organization_id == scope.organization_id,
                    WorkflowRunMaterializationClaimModel.environment_id == scope.environment_id,
                    WorkflowRunMaterializationClaimModel.site_id == scope.site_id,
                    WorkflowRunMaterializationClaimModel.worker_subject_id == worker_subject_id,
                )
            ),
        )

    @classmethod
    def _materialized_run_from_row(cls, row: WorkflowExecutionRunModel) -> WorkflowExecutionRun:
        try:
            run = cls._execution_run_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowPlanningError(
                "workflow_run_materialization_repository_contract_violation",
                "The workflow run repository contains an invalid run.",
            ) from exc
        if (
            row.run_id != run.run_id
            or row.plan_id != run.plan_id
            or row.plan_digest != run.plan_digest
            or row.definition_id != run.definition_id
            or row.definition_version != run.definition_version
            or row.definition_digest != run.definition_digest
            or row.organization_id != run.scope.organization_id
            or row.environment_id != run.scope.environment_id
            or row.site_id != run.scope.site_id
            or row.target_type != run.target_type
            or row.target_id != run.target_id
            or row.lease_id != run.lease_id
            or row.lease_digest != run.lease_digest
            or row.lease_fencing_token != run.fencing_token
            or row.materialized_by_subject_id != run.materialized_by_subject_id
            or row.created_at != run.created_at
            or row.state != run.state.value
            or row.canonical_digest != run.canonical_digest
        ):
            cls._materialization_contract_violation()
        return run

    @classmethod
    def _materialized_run_from_claim(
        cls, claim: WorkflowRunMaterializationClaimModel
    ) -> WorkflowExecutionRun:
        raw = claim.payload.get("result_run")
        if not isinstance(raw, dict):
            cls._materialization_contract_violation()
        try:
            run = cls._execution_run_to_domain(cast(dict[str, Any], raw))
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowPlanningError(
                "workflow_run_materialization_repository_contract_violation",
                "The workflow run repository contains an invalid idempotency result.",
            ) from exc
        run_payload = cls._execution_run_payload(run)
        scope_id = cls._materialization_scope_id(run)
        expected: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_digest": run.canonical_digest,
            "result_run": run_payload,
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != run.canonical_digest
            or claim.run_id != run.run_id
            or claim.plan_id != run.plan_id
            or claim.organization_id != run.scope.organization_id
            or claim.environment_id != run.scope.environment_id
            or claim.site_id != run.scope.site_id
            or claim.worker_subject_id != run.materialized_by_subject_id
            or claim.payload != expected
            or claim.canonical_digest != canonical_digest(expected)
        ):
            cls._materialization_contract_violation()
        return run

    @classmethod
    def _materialized_run_model(cls, run: WorkflowExecutionRun) -> WorkflowExecutionRunModel:
        return WorkflowExecutionRunModel(
            run_id=run.run_id,
            plan_id=run.plan_id,
            plan_digest=run.plan_digest,
            definition_id=run.definition_id,
            definition_version=run.definition_version,
            definition_digest=run.definition_digest,
            organization_id=run.scope.organization_id,
            environment_id=run.scope.environment_id,
            site_id=run.scope.site_id,
            target_type=run.target_type,
            target_id=run.target_id,
            lease_id=run.lease_id,
            lease_digest=run.lease_digest,
            lease_fencing_token=run.fencing_token,
            materialized_by_subject_id=run.materialized_by_subject_id,
            created_at=run.created_at,
            state=run.state.value,
            canonical_digest=run.canonical_digest,
            payload=cls._execution_run_payload(run),
        )

    @staticmethod
    def _materialized_step_model(step: WorkflowExecutionStepRun) -> WorkflowExecutionStepRunModel:
        return WorkflowExecutionStepRunModel(
            step_run_id=step.step_run_id,
            run_id=step.run_id,
            step_id=step.step_id,
            ordinal=step.ordinal,
            kind=step.kind.value,
            capability_class=step.capability_class.value,
            timeout_seconds=step.timeout_seconds,
            depends_on=list(step.depends_on),
            state=step.state.value,
            canonical_digest=step.canonical_digest,
            payload=cast(dict[str, Any], step.canonical_value()),
        )

    @classmethod
    def _materialization_claim_model(
        cls, request: WorkflowRunMaterializationRequest
    ) -> WorkflowRunMaterializationClaimModel:
        run = request.candidate
        run_payload = cls._execution_run_payload(run)
        scope_id = cls._materialization_scope_id(run)
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_digest": run.canonical_digest,
            "result_run": run_payload,
        }
        digest = canonical_digest(payload)
        return WorkflowRunMaterializationClaimModel(
            claim_id=f"workflow_run_mat_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=run.canonical_digest,
            run_id=run.run_id,
            plan_id=run.plan_id,
            organization_id=run.scope.organization_id,
            environment_id=run.scope.environment_id,
            site_id=run.scope.site_id,
            worker_subject_id=run.materialized_by_subject_id,
            created_at=request.requested_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _validate_materialization_request(cls, request: WorkflowRunMaterializationRequest) -> None:
        run = request.candidate
        if run.state is not WorkflowExecutionRunState.CREATED or run.grants_execution_authority:
            raise ValueError("workflow run materialization payload is unsafe")
        if len(request.idempotency_key) > 128 or not request.idempotency_key:
            raise ValueError("workflow run materialization idempotency key is invalid")
        if len(request.request_fingerprint) != 64:
            raise ValueError("workflow run materialization request fingerprint is invalid")
        if request.requested_at.tzinfo is None:
            raise ValueError("workflow run materialization time must be timezone-aware")

    @staticmethod
    def _materialization_sources_match(
        *,
        plan_row: WorkflowRunPlanModel | None,
        lease_row: WorkflowOrchestrationLeaseModel | None,
        request: WorkflowRunMaterializationRequest,
    ) -> bool:
        run = request.candidate
        return bool(
            plan_row is not None
            and lease_row is not None
            and plan_row.state == WorkflowPlanState.PLANNED.value
            and plan_row.canonical_digest == request.expected_plan_digest == run.plan_digest
            and plan_row.definition_id == run.definition_id
            and plan_row.definition_version == run.definition_version
            and plan_row.definition_digest == run.definition_digest
            and plan_row.organization_id == run.scope.organization_id
            and plan_row.environment_id == run.scope.environment_id
            and plan_row.site_id == run.scope.site_id
            and plan_row.target_type == run.target_type
            and plan_row.target_id == run.target_id
            and lease_row.plan_id == run.plan_id
            and lease_row.plan_digest == run.plan_digest
            and lease_row.organization_id == run.scope.organization_id
            and lease_row.environment_id == run.scope.environment_id
            and lease_row.site_id == run.scope.site_id
            and lease_row.target_type == run.target_type
            and lease_row.target_id == run.target_id
            and lease_row.lease_id == request.expected_lease_id == run.lease_id
            and lease_row.canonical_digest == request.expected_lease_digest == run.lease_digest
            and lease_row.fencing_token == request.expected_fencing_token == run.fencing_token
            and lease_row.worker_subject_id
            == request.worker_subject_id
            == run.materialized_by_subject_id
            and lease_row.state == WorkflowOrchestrationLeaseState.ACTIVE.value
            and lease_row.expires_at > request.requested_at
        )

    @staticmethod
    def _materialization_scope_id(run: WorkflowExecutionRun) -> str:
        return canonical_digest(
            {
                "scope": run.scope.canonical_value(),
                "worker_subject_id": run.materialized_by_subject_id,
            }
        )

    @staticmethod
    def _execution_run_payload(run: WorkflowExecutionRun) -> dict[str, Any]:
        return cast(dict[str, Any], run.canonical_value())

    @staticmethod
    def _execution_run_to_domain(raw: dict[str, Any]) -> WorkflowExecutionRun:
        payload = dict(raw)
        payload["scope"] = WorkflowScope(**cast(Any, payload["scope"]))
        payload["created_at"] = datetime.fromisoformat(str(payload["created_at"]))
        payload["state"] = WorkflowExecutionRunState(str(payload["state"]))
        payload["step_runs"] = tuple(
            WorkflowExecutionStepRun(
                step_run_id=str(item["step_run_id"]),
                run_id=str(item["run_id"]),
                step_id=str(item["step_id"]),
                ordinal=int(item["ordinal"]),
                kind=WorkflowStepKind(str(item["kind"])),
                capability_class=WorkflowCapabilityClass(str(item["capability_class"])),
                timeout_seconds=int(item["timeout_seconds"]),
                depends_on=tuple(str(value) for value in item["depends_on"]),
                state=WorkflowExecutionStepRunState(str(item["state"])),
                canonical_digest=str(item["canonical_digest"]),
            )
            for item in payload["step_runs"]
        )
        payload["authority"] = WorkflowPlanAuthority(**cast(Any, payload["authority"]))
        return WorkflowExecutionRun(**cast(Any, payload))

    @staticmethod
    def _materialization_contract_violation() -> None:
        raise WorkflowPlanningError(
            "workflow_run_materialization_repository_contract_violation",
            "The workflow run materialization record does not match its canonical payload.",
        )

    async def _attempt_materialization_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowAttemptMaterializationRequest,
    ) -> WorkflowAttemptMaterializationResult | None:
        attempt = request.candidate
        claim = cast(
            WorkflowAttemptMaterializationClaimModel | None,
            await session.scalar(
                select(WorkflowAttemptMaterializationClaimModel).where(
                    WorkflowAttemptMaterializationClaimModel.idempotency_scope_id
                    == self._attempt_materialization_scope_id(attempt),
                    WorkflowAttemptMaterializationClaimModel.idempotency_key
                    == request.idempotency_key,
                    WorkflowAttemptMaterializationClaimModel.organization_id
                    == attempt.scope.organization_id,
                    WorkflowAttemptMaterializationClaimModel.environment_id
                    == attempt.scope.environment_id,
                    WorkflowAttemptMaterializationClaimModel.site_id == attempt.scope.site_id,
                    WorkflowAttemptMaterializationClaimModel.worker_subject_id
                    == attempt.materialized_by_subject_id,
                )
            ),
        )
        if claim is None:
            return None
        result = self._attempt_from_claim(claim)
        status = (
            WorkflowAttemptMaterializationStatus.REPLAY
            if claim.request_fingerprint == request.request_fingerprint
            else WorkflowAttemptMaterializationStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowAttemptMaterializationResult(status, result)

    @classmethod
    async def _load_attempt_materialization_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowAttemptMaterializationClaimModel | None:
        scope_id = canonical_digest(
            {
                "scope": scope.canonical_value(),
                "worker_subject_id": worker_subject_id,
            }
        )
        return cast(
            WorkflowAttemptMaterializationClaimModel | None,
            await session.scalar(
                select(WorkflowAttemptMaterializationClaimModel).where(
                    WorkflowAttemptMaterializationClaimModel.idempotency_scope_id == scope_id,
                    WorkflowAttemptMaterializationClaimModel.idempotency_key == idempotency_key,
                    WorkflowAttemptMaterializationClaimModel.organization_id
                    == scope.organization_id,
                    WorkflowAttemptMaterializationClaimModel.environment_id == scope.environment_id,
                    WorkflowAttemptMaterializationClaimModel.site_id == scope.site_id,
                    WorkflowAttemptMaterializationClaimModel.worker_subject_id == worker_subject_id,
                )
            ),
        )

    @classmethod
    def _attempt_from_row(cls, row: WorkflowExecutionAttemptModel) -> WorkflowExecutionAttempt:
        try:
            attempt = cls._attempt_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowAttemptMaterializationError(
                "workflow_attempt_materialization_repository_contract_violation",
                "The workflow attempt repository contains an invalid attempt.",
            ) from exc
        if (
            row.attempt_id != attempt.attempt_id
            or row.run_id != attempt.run_id
            or row.run_digest != attempt.run_digest
            or row.step_run_id != attempt.step_run_id
            or row.step_run_digest != attempt.step_run_digest
            or row.step_id != attempt.step_id
            or row.attempt_number != attempt.attempt_number
            or row.plan_id != attempt.plan_id
            or row.plan_digest != attempt.plan_digest
            or row.definition_id != attempt.definition_id
            or row.definition_version != attempt.definition_version
            or row.definition_digest != attempt.definition_digest
            or row.organization_id != attempt.scope.organization_id
            or row.environment_id != attempt.scope.environment_id
            or row.site_id != attempt.scope.site_id
            or row.target_type != attempt.target_type
            or row.target_id != attempt.target_id
            or row.lease_id != attempt.lease_id
            or row.lease_digest != attempt.lease_digest
            or row.lease_fencing_token != attempt.fencing_token
            or row.materialized_by_subject_id != attempt.materialized_by_subject_id
            or row.created_at != attempt.created_at
            or row.state != attempt.state.value
            or row.canonical_digest != attempt.canonical_digest
        ):
            cls._attempt_contract_violation()
        return attempt

    @classmethod
    def _attempt_from_claim(
        cls, claim: WorkflowAttemptMaterializationClaimModel
    ) -> WorkflowExecutionAttempt:
        raw = claim.payload.get("result_attempt")
        if not isinstance(raw, dict):
            cls._attempt_contract_violation()
        try:
            attempt = cls._attempt_to_domain(cast(dict[str, Any], raw))
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowAttemptMaterializationError(
                "workflow_attempt_materialization_repository_contract_violation",
                "The workflow attempt repository contains an invalid idempotency result.",
            ) from exc
        attempt_payload = cls._attempt_payload(attempt)
        scope_id = cls._attempt_materialization_scope_id(attempt)
        expected: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_attempt": attempt_payload,
            "result_digest": attempt.canonical_digest,
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != attempt.canonical_digest
            or claim.attempt_id != attempt.attempt_id
            or claim.run_id != attempt.run_id
            or claim.plan_id != attempt.plan_id
            or claim.organization_id != attempt.scope.organization_id
            or claim.environment_id != attempt.scope.environment_id
            or claim.site_id != attempt.scope.site_id
            or claim.worker_subject_id != attempt.materialized_by_subject_id
            or claim.payload != expected
            or claim.canonical_digest != canonical_digest(expected)
        ):
            cls._attempt_contract_violation()
        return attempt

    @classmethod
    def _attempt_model(cls, attempt: WorkflowExecutionAttempt) -> WorkflowExecutionAttemptModel:
        return WorkflowExecutionAttemptModel(
            attempt_id=attempt.attempt_id,
            run_id=attempt.run_id,
            run_digest=attempt.run_digest,
            step_run_id=attempt.step_run_id,
            step_run_digest=attempt.step_run_digest,
            step_id=attempt.step_id,
            attempt_number=attempt.attempt_number,
            plan_id=attempt.plan_id,
            plan_digest=attempt.plan_digest,
            definition_id=attempt.definition_id,
            definition_version=attempt.definition_version,
            definition_digest=attempt.definition_digest,
            organization_id=attempt.scope.organization_id,
            environment_id=attempt.scope.environment_id,
            site_id=attempt.scope.site_id,
            target_type=attempt.target_type,
            target_id=attempt.target_id,
            lease_id=attempt.lease_id,
            lease_digest=attempt.lease_digest,
            lease_fencing_token=attempt.fencing_token,
            materialized_by_subject_id=attempt.materialized_by_subject_id,
            created_at=attempt.created_at,
            state=attempt.state.value,
            canonical_digest=attempt.canonical_digest,
            payload=cls._attempt_payload(attempt),
        )

    @classmethod
    def _attempt_materialization_claim_model(
        cls, request: WorkflowAttemptMaterializationRequest
    ) -> WorkflowAttemptMaterializationClaimModel:
        attempt = request.candidate
        scope_id = cls._attempt_materialization_scope_id(attempt)
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_attempt": cls._attempt_payload(attempt),
            "result_digest": attempt.canonical_digest,
        }
        digest = canonical_digest(payload)
        return WorkflowAttemptMaterializationClaimModel(
            claim_id=f"workflow_attempt_mat_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=attempt.canonical_digest,
            attempt_id=attempt.attempt_id,
            run_id=attempt.run_id,
            plan_id=attempt.plan_id,
            organization_id=attempt.scope.organization_id,
            environment_id=attempt.scope.environment_id,
            site_id=attempt.scope.site_id,
            worker_subject_id=attempt.materialized_by_subject_id,
            created_at=request.requested_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _validate_attempt_materialization_request(
        cls, request: WorkflowAttemptMaterializationRequest
    ) -> None:
        attempt = request.candidate
        if (
            attempt.state is not WorkflowExecutionAttemptState.CREATED
            or attempt.attempt_number != 1
            or attempt.grants_execution_authority
        ):
            raise ValueError("workflow attempt materialization payload is unsafe")
        if len(request.idempotency_key) > 128 or not request.idempotency_key:
            raise ValueError("workflow attempt materialization idempotency key is invalid")
        if len(request.request_fingerprint) != 64:
            raise ValueError("workflow attempt materialization request fingerprint is invalid")
        if request.requested_at.tzinfo is None:
            raise ValueError("workflow attempt materialization time must be timezone-aware")

    @classmethod
    def _attempt_materialization_sources_match(
        cls,
        *,
        plan_row: WorkflowRunPlanModel | None,
        lease_row: WorkflowOrchestrationLeaseModel | None,
        run_row: WorkflowExecutionRunModel | None,
        step_row: WorkflowExecutionStepRunModel | None,
        request: WorkflowAttemptMaterializationRequest,
    ) -> bool:
        if plan_row is None or lease_row is None or run_row is None or step_row is None:
            return False
        attempt = request.candidate
        try:
            run = cls._materialized_run_from_row(run_row)
            step = cls._materialized_step_from_row(step_row)
        except (WorkflowAttemptMaterializationError, WorkflowPlanningError) as exc:
            raise WorkflowAttemptMaterializationError(
                "workflow_attempt_materialization_repository_contract_violation",
                "Workflow run evidence is inconsistent during attempt materialization.",
            ) from exc
        return bool(
            plan_row.plan_id == attempt.plan_id
            and plan_row.state == WorkflowPlanState.PLANNED.value
            and plan_row.canonical_digest == request.expected_plan_digest == attempt.plan_digest
            and plan_row.definition_id == attempt.definition_id
            and plan_row.definition_version == attempt.definition_version
            and plan_row.definition_digest == attempt.definition_digest
            and plan_row.organization_id == attempt.scope.organization_id
            and plan_row.environment_id == attempt.scope.environment_id
            and plan_row.site_id == attempt.scope.site_id
            and plan_row.target_type == attempt.target_type
            and plan_row.target_id == attempt.target_id
            and run.run_id == attempt.run_id
            and run.canonical_digest == request.expected_run_digest == attempt.run_digest
            and run.plan_id == attempt.plan_id
            and run.plan_digest == attempt.plan_digest
            and run.definition_id == attempt.definition_id
            and run.definition_version == attempt.definition_version
            and run.definition_digest == attempt.definition_digest
            and run.scope == attempt.scope
            and run.target_type == attempt.target_type
            and run.target_id == attempt.target_id
            and run.lease_id == attempt.lease_id
            and run.fencing_token == attempt.fencing_token
            and run.materialized_by_subject_id == attempt.materialized_by_subject_id
            and run.state is WorkflowExecutionRunState.CREATED
            and not run.grants_execution_authority
            and step in run.step_runs
            and step.step_run_id == attempt.step_run_id
            and step.canonical_digest == request.expected_step_run_digest == attempt.step_run_digest
            and step.run_id == attempt.run_id
            and step.step_id == attempt.step_id
            and step.state is WorkflowExecutionStepRunState.NOT_STARTED
            and not step.depends_on
            and lease_row.plan_id == attempt.plan_id
            and lease_row.plan_digest == attempt.plan_digest
            and lease_row.organization_id == attempt.scope.organization_id
            and lease_row.environment_id == attempt.scope.environment_id
            and lease_row.site_id == attempt.scope.site_id
            and lease_row.target_type == attempt.target_type
            and lease_row.target_id == attempt.target_id
            and lease_row.lease_id == request.expected_lease_id == attempt.lease_id
            and lease_row.canonical_digest == request.expected_lease_digest == attempt.lease_digest
            and lease_row.fencing_token == request.expected_fencing_token == attempt.fencing_token
            and lease_row.worker_subject_id
            == request.worker_subject_id
            == attempt.materialized_by_subject_id
            and lease_row.state == WorkflowOrchestrationLeaseState.ACTIVE.value
            and lease_row.expires_at > request.requested_at
        )

    @staticmethod
    def _attempt_materialization_scope_id(attempt: WorkflowExecutionAttempt) -> str:
        return canonical_digest(
            {
                "scope": attempt.scope.canonical_value(),
                "worker_subject_id": attempt.materialized_by_subject_id,
            }
        )

    @staticmethod
    def _attempt_payload(attempt: WorkflowExecutionAttempt) -> dict[str, Any]:
        return cast(dict[str, Any], attempt.canonical_value())

    @staticmethod
    def _attempt_to_domain(raw: dict[str, Any]) -> WorkflowExecutionAttempt:
        payload = dict(raw)
        payload["scope"] = WorkflowScope(**cast(Any, payload["scope"]))
        payload["created_at"] = datetime.fromisoformat(str(payload["created_at"]))
        payload["state"] = WorkflowExecutionAttemptState(str(payload["state"]))
        payload["authority"] = WorkflowPlanAuthority(**cast(Any, payload["authority"]))
        return WorkflowExecutionAttempt(**cast(Any, payload))

    @staticmethod
    def _materialized_step_from_row(
        row: WorkflowExecutionStepRunModel,
    ) -> WorkflowExecutionStepRun:
        try:
            raw = row.payload
            step = WorkflowExecutionStepRun(
                step_run_id=str(raw["step_run_id"]),
                run_id=str(raw["run_id"]),
                step_id=str(raw["step_id"]),
                ordinal=int(raw["ordinal"]),
                kind=WorkflowStepKind(str(raw["kind"])),
                capability_class=WorkflowCapabilityClass(str(raw["capability_class"])),
                timeout_seconds=int(raw["timeout_seconds"]),
                depends_on=tuple(str(value) for value in raw["depends_on"]),
                state=WorkflowExecutionStepRunState(str(raw["state"])),
                canonical_digest=str(raw["canonical_digest"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowAttemptMaterializationError(
                "workflow_attempt_materialization_repository_contract_violation",
                "The workflow step-run repository contains invalid materialization evidence.",
            ) from exc
        if (
            row.step_run_id != step.step_run_id
            or row.run_id != step.run_id
            or row.step_id != step.step_id
            or row.ordinal != step.ordinal
            or row.kind != step.kind.value
            or row.capability_class != step.capability_class.value
            or row.timeout_seconds != step.timeout_seconds
            or row.depends_on != list(step.depends_on)
            or row.state != step.state.value
            or row.canonical_digest != step.canonical_digest
        ):
            PostgreSQLWorkflowPlanRepository._attempt_contract_violation()
        return step

    @staticmethod
    def _attempt_contract_violation() -> None:
        raise WorkflowAttemptMaterializationError(
            "workflow_attempt_materialization_repository_contract_violation",
            "The workflow attempt materialization record does not match its canonical payload.",
        )

    async def _dispatch_intent_staging_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowDispatchIntentStagingRequest,
    ) -> WorkflowDispatchIntentStagingResult | None:
        intent = request.candidate
        claim = cast(
            WorkflowDispatchIntentStagingClaimModel | None,
            await session.scalar(
                select(WorkflowDispatchIntentStagingClaimModel).where(
                    WorkflowDispatchIntentStagingClaimModel.idempotency_scope_id
                    == self._dispatch_intent_staging_scope_id(intent),
                    WorkflowDispatchIntentStagingClaimModel.idempotency_key
                    == request.idempotency_key,
                    WorkflowDispatchIntentStagingClaimModel.organization_id
                    == intent.scope.organization_id,
                    WorkflowDispatchIntentStagingClaimModel.environment_id
                    == intent.scope.environment_id,
                    WorkflowDispatchIntentStagingClaimModel.site_id == intent.scope.site_id,
                    WorkflowDispatchIntentStagingClaimModel.worker_subject_id
                    == intent.worker_subject_id,
                )
            ),
        )
        if claim is None:
            return None
        intent, outbox_entry = self._dispatch_pair_from_claim(claim)
        status = (
            WorkflowDispatchIntentStagingStatus.REPLAY
            if claim.request_fingerprint == request.request_fingerprint
            else WorkflowDispatchIntentStagingStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowDispatchIntentStagingResult(
            status=status,
            dispatch_intent=intent,
            outbox_entry=outbox_entry,
        )

    @classmethod
    async def _load_dispatch_intent_staging_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowDispatchIntentStagingClaimModel | None:
        scope_id = canonical_digest(
            {
                "scope": scope.canonical_value(),
                "worker_subject_id": worker_subject_id,
            }
        )
        return cast(
            WorkflowDispatchIntentStagingClaimModel | None,
            await session.scalar(
                select(WorkflowDispatchIntentStagingClaimModel).where(
                    WorkflowDispatchIntentStagingClaimModel.idempotency_scope_id == scope_id,
                    WorkflowDispatchIntentStagingClaimModel.idempotency_key == idempotency_key,
                    WorkflowDispatchIntentStagingClaimModel.organization_id
                    == scope.organization_id,
                    WorkflowDispatchIntentStagingClaimModel.environment_id == scope.environment_id,
                    WorkflowDispatchIntentStagingClaimModel.site_id == scope.site_id,
                    WorkflowDispatchIntentStagingClaimModel.worker_subject_id == worker_subject_id,
                )
            ),
        )

    @classmethod
    def _dispatch_intent_from_row(cls, row: WorkflowDispatchIntentModel) -> WorkflowDispatchIntent:
        try:
            intent = cls._dispatch_intent_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowDispatchIntentStagingError(
                "workflow_dispatch_intent_repository_contract_violation",
                "The workflow dispatch-intent repository contains an invalid intent.",
            ) from exc
        if (
            row.dispatch_intent_id != intent.dispatch_intent_id
            or row.plan_id != intent.plan_id
            or row.plan_digest != intent.plan_digest
            or row.run_id != intent.run_id
            or row.run_digest != intent.run_digest
            or row.step_run_id != intent.step_run_id
            or row.step_run_digest != intent.step_run_digest
            or row.step_id != intent.step_id
            or row.attempt_id != intent.attempt_id
            or row.attempt_digest != intent.attempt_digest
            or row.attempt_number != intent.attempt_number
            or row.organization_id != intent.scope.organization_id
            or row.environment_id != intent.scope.environment_id
            or row.site_id != intent.scope.site_id
            or row.target_type != intent.target_type
            or row.target_id != intent.target_id
            or row.lease_id != intent.lease_id
            or row.lease_digest != intent.lease_digest
            or row.lease_fencing_token != intent.fencing_token
            or row.worker_subject_id != intent.worker_subject_id
            or row.staged_at != intent.staged_at
            or row.state != intent.state.value
            or row.canonical_digest != intent.canonical_digest
        ):
            cls._dispatch_intent_contract_violation()
        return intent

    @classmethod
    def _dispatch_intent_from_claim(
        cls, claim: WorkflowDispatchIntentStagingClaimModel
    ) -> WorkflowDispatchIntent:
        return cls._dispatch_pair_from_claim(claim)[0]

    @classmethod
    def _dispatch_pair_from_claim(
        cls, claim: WorkflowDispatchIntentStagingClaimModel
    ) -> tuple[WorkflowDispatchIntent, WorkflowDispatchOutboxEntry]:
        raw = claim.payload.get("result_dispatch_intent")
        raw_outbox = claim.payload.get("result_outbox_entry")
        if not isinstance(raw, dict) or not isinstance(raw_outbox, dict):
            cls._dispatch_intent_contract_violation()
        try:
            intent = cls._dispatch_intent_to_domain(cast(dict[str, Any], raw))
            outbox_entry = cls._dispatch_outbox_to_domain(cast(dict[str, Any], raw_outbox))
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowDispatchIntentStagingError(
                "workflow_dispatch_intent_repository_contract_violation",
                "The dispatch-intent repository contains an invalid idempotency result.",
            ) from exc
        intent_payload = cls._dispatch_intent_payload(intent)
        outbox_payload = cls._dispatch_outbox_payload(outbox_entry)
        scope_id = cls._dispatch_intent_staging_scope_id(intent)
        expected: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_dispatch_intent": intent_payload,
            "result_digest": intent.canonical_digest,
            "result_outbox_digest": outbox_entry.canonical_digest,
            "result_outbox_entry": outbox_payload,
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != intent.canonical_digest
            or claim.result_outbox_digest != outbox_entry.canonical_digest
            or claim.dispatch_intent_id != intent.dispatch_intent_id
            or claim.outbox_entry_id != outbox_entry.outbox_entry_id
            or claim.attempt_id != intent.attempt_id
            or claim.run_id != intent.run_id
            or claim.plan_id != intent.plan_id
            or claim.organization_id != intent.scope.organization_id
            or claim.environment_id != intent.scope.environment_id
            or claim.site_id != intent.scope.site_id
            or claim.worker_subject_id != intent.worker_subject_id
            or claim.payload != expected
            or claim.canonical_digest != canonical_digest(expected)
            or not cls._dispatch_outbox_matches_intent(outbox_entry, intent)
        ):
            cls._dispatch_intent_contract_violation()
        return intent, outbox_entry

    @classmethod
    def _dispatch_intent_model(cls, intent: WorkflowDispatchIntent) -> WorkflowDispatchIntentModel:
        return WorkflowDispatchIntentModel(
            dispatch_intent_id=intent.dispatch_intent_id,
            plan_id=intent.plan_id,
            plan_digest=intent.plan_digest,
            run_id=intent.run_id,
            run_digest=intent.run_digest,
            step_run_id=intent.step_run_id,
            step_run_digest=intent.step_run_digest,
            step_id=intent.step_id,
            attempt_id=intent.attempt_id,
            attempt_digest=intent.attempt_digest,
            attempt_number=intent.attempt_number,
            organization_id=intent.scope.organization_id,
            environment_id=intent.scope.environment_id,
            site_id=intent.scope.site_id,
            target_type=intent.target_type,
            target_id=intent.target_id,
            lease_id=intent.lease_id,
            lease_digest=intent.lease_digest,
            lease_fencing_token=intent.fencing_token,
            worker_subject_id=intent.worker_subject_id,
            staged_at=intent.staged_at,
            state=intent.state.value,
            canonical_digest=intent.canonical_digest,
            payload=cls._dispatch_intent_payload(intent),
        )

    @classmethod
    def _dispatch_outbox_model(
        cls, entry: WorkflowDispatchOutboxEntry
    ) -> WorkflowDispatchOutboxEntryModel:
        return WorkflowDispatchOutboxEntryModel(
            outbox_entry_id=entry.outbox_entry_id,
            dispatch_intent_id=entry.dispatch_intent_id,
            dispatch_intent_digest=entry.dispatch_intent_digest,
            plan_id=entry.plan_id,
            plan_digest=entry.plan_digest,
            run_id=entry.run_id,
            run_digest=entry.run_digest,
            step_run_id=entry.step_run_id,
            step_run_digest=entry.step_run_digest,
            step_id=entry.step_id,
            attempt_id=entry.attempt_id,
            attempt_digest=entry.attempt_digest,
            attempt_number=entry.attempt_number,
            organization_id=entry.scope.organization_id,
            environment_id=entry.scope.environment_id,
            site_id=entry.scope.site_id,
            target_type=entry.target_type,
            target_id=entry.target_id,
            lease_id=entry.lease_id,
            lease_digest=entry.lease_digest,
            lease_fencing_token=entry.fencing_token,
            worker_subject_id=entry.worker_subject_id,
            admitted_at=entry.admitted_at,
            state=entry.state.value,
            publication_authority_granted=entry.grants_publication_authority,
            delivery_authority_granted=entry.grants_delivery_authority,
            dispatch_authority_granted=entry.grants_dispatch_authority,
            execution_authority_granted=entry.grants_execution_authority,
            canonical_digest=entry.canonical_digest,
            payload=cls._dispatch_outbox_payload(entry),
        )

    @classmethod
    def _dispatch_outbox_from_row(
        cls, row: WorkflowDispatchOutboxEntryModel
    ) -> WorkflowDispatchOutboxEntry:
        try:
            entry = cls._dispatch_outbox_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowDispatchIntentStagingError(
                "workflow_dispatch_outbox_repository_contract_violation",
                "The workflow dispatch outbox repository contains an invalid entry.",
            ) from exc
        if (
            row.outbox_entry_id != entry.outbox_entry_id
            or row.dispatch_intent_id != entry.dispatch_intent_id
            or row.dispatch_intent_digest != entry.dispatch_intent_digest
            or row.plan_id != entry.plan_id
            or row.plan_digest != entry.plan_digest
            or row.run_id != entry.run_id
            or row.run_digest != entry.run_digest
            or row.step_run_id != entry.step_run_id
            or row.step_run_digest != entry.step_run_digest
            or row.step_id != entry.step_id
            or row.attempt_id != entry.attempt_id
            or row.attempt_digest != entry.attempt_digest
            or row.attempt_number != entry.attempt_number
            or row.organization_id != entry.scope.organization_id
            or row.environment_id != entry.scope.environment_id
            or row.site_id != entry.scope.site_id
            or row.target_type != entry.target_type
            or row.target_id != entry.target_id
            or row.lease_id != entry.lease_id
            or row.lease_digest != entry.lease_digest
            or row.lease_fencing_token != entry.fencing_token
            or row.worker_subject_id != entry.worker_subject_id
            or row.admitted_at != entry.admitted_at
            or row.state != entry.state.value
            or row.publication_authority_granted != entry.grants_publication_authority
            or row.delivery_authority_granted != entry.grants_delivery_authority
            or row.dispatch_authority_granted != entry.grants_dispatch_authority
            or row.execution_authority_granted != entry.grants_execution_authority
            or row.canonical_digest != entry.canonical_digest
        ):
            cls._dispatch_outbox_contract_violation()
        return entry

    @classmethod
    def _dispatch_intent_staging_claim_model(
        cls, request: WorkflowDispatchIntentStagingRequest
    ) -> WorkflowDispatchIntentStagingClaimModel:
        intent = request.candidate
        outbox_entry = request.outbox_entry
        if outbox_entry is None:
            raise ValueError("workflow dispatch outbox entry is required")
        scope_id = cls._dispatch_intent_staging_scope_id(intent)
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_dispatch_intent": cls._dispatch_intent_payload(intent),
            "result_digest": intent.canonical_digest,
            "result_outbox_digest": outbox_entry.canonical_digest,
            "result_outbox_entry": cls._dispatch_outbox_payload(outbox_entry),
        }
        digest = canonical_digest(payload)
        return WorkflowDispatchIntentStagingClaimModel(
            claim_id=f"workflow_dispatch_intent_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=intent.canonical_digest,
            result_outbox_digest=outbox_entry.canonical_digest,
            dispatch_intent_id=intent.dispatch_intent_id,
            outbox_entry_id=outbox_entry.outbox_entry_id,
            attempt_id=intent.attempt_id,
            run_id=intent.run_id,
            plan_id=intent.plan_id,
            organization_id=intent.scope.organization_id,
            environment_id=intent.scope.environment_id,
            site_id=intent.scope.site_id,
            worker_subject_id=intent.worker_subject_id,
            created_at=request.requested_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _validate_dispatch_intent_staging_request(
        cls, request: WorkflowDispatchIntentStagingRequest
    ) -> None:
        intent = request.candidate
        outbox_entry = request.outbox_entry
        if outbox_entry is None:
            raise ValueError("workflow dispatch outbox entry is required")
        if (
            intent.state is not WorkflowDispatchIntentState.STAGED
            or intent.attempt_number != 1
            or intent.grants_dispatch_authority
            or intent.grants_execution_authority
            or outbox_entry.state is not WorkflowDispatchOutboxState.PENDING_PUBLICATION
            or outbox_entry.grants_publication_authority
            or outbox_entry.grants_delivery_authority
            or outbox_entry.grants_dispatch_authority
            or outbox_entry.grants_execution_authority
            or not cls._dispatch_outbox_matches_intent(outbox_entry, intent)
        ):
            raise ValueError("workflow dispatch-intent staging payload is unsafe")
        if len(request.idempotency_key) > 128 or not request.idempotency_key:
            raise ValueError("workflow dispatch-intent idempotency key is invalid")
        if len(request.request_fingerprint) != 64:
            raise ValueError("workflow dispatch-intent request fingerprint is invalid")
        if request.requested_at.tzinfo is None:
            raise ValueError("workflow dispatch-intent staging time must be timezone-aware")

    @classmethod
    def _dispatch_intent_sources_match(
        cls,
        *,
        plan_row: WorkflowRunPlanModel | None,
        lease_row: WorkflowOrchestrationLeaseModel | None,
        run_row: WorkflowExecutionRunModel | None,
        step_row: WorkflowExecutionStepRunModel | None,
        attempt_row: WorkflowExecutionAttemptModel | None,
        request: WorkflowDispatchIntentStagingRequest,
    ) -> bool:
        if any(item is None for item in (plan_row, lease_row, run_row, step_row, attempt_row)):
            return False
        assert plan_row is not None
        assert lease_row is not None
        assert run_row is not None
        assert step_row is not None
        assert attempt_row is not None
        intent = request.candidate
        try:
            run = cls._materialized_run_from_row(run_row)
            step = cls._materialized_step_from_row(step_row)
            attempt = cls._attempt_from_row(attempt_row)
        except (
            WorkflowAttemptMaterializationError,
            WorkflowPlanningError,
        ) as exc:
            raise WorkflowDispatchIntentStagingError(
                "workflow_dispatch_intent_repository_contract_violation",
                "Workflow execution evidence is inconsistent during dispatch-intent staging.",
            ) from exc
        return bool(
            plan_row.plan_id == intent.plan_id
            and plan_row.state == WorkflowPlanState.PLANNED.value
            and plan_row.canonical_digest == request.expected_plan_digest == intent.plan_digest
            and plan_row.organization_id == intent.scope.organization_id
            and plan_row.environment_id == intent.scope.environment_id
            and plan_row.site_id == intent.scope.site_id
            and plan_row.target_type == intent.target_type
            and plan_row.target_id == intent.target_id
            and run.run_id == intent.run_id
            and run.canonical_digest == request.expected_run_digest == intent.run_digest
            and run.plan_id == intent.plan_id
            and run.plan_digest == intent.plan_digest
            and run.scope == intent.scope
            and run.target_type == intent.target_type
            and run.target_id == intent.target_id
            and run.lease_id == intent.lease_id
            and run.fencing_token == intent.fencing_token
            and run.materialized_by_subject_id == intent.worker_subject_id
            and run.state is WorkflowExecutionRunState.CREATED
            and not run.grants_execution_authority
            and step in run.step_runs
            and step.step_run_id == intent.step_run_id
            and step.canonical_digest == request.expected_step_run_digest == intent.step_run_digest
            and step.run_id == intent.run_id
            and step.step_id == intent.step_id
            and step.state is WorkflowExecutionStepRunState.NOT_STARTED
            and not step.depends_on
            and attempt.attempt_id == intent.attempt_id
            and attempt.canonical_digest == request.expected_attempt_digest == intent.attempt_digest
            and attempt.run_id == intent.run_id
            and attempt.run_digest == intent.run_digest
            and attempt.step_run_id == intent.step_run_id
            and attempt.step_run_digest == intent.step_run_digest
            and attempt.step_id == intent.step_id
            and attempt.attempt_number == intent.attempt_number == 1
            and attempt.plan_id == intent.plan_id
            and attempt.plan_digest == intent.plan_digest
            and attempt.scope == intent.scope
            and attempt.target_type == intent.target_type
            and attempt.target_id == intent.target_id
            and attempt.lease_id == intent.lease_id
            and attempt.fencing_token == intent.fencing_token
            and attempt.materialized_by_subject_id == intent.worker_subject_id
            and attempt.state is WorkflowExecutionAttemptState.CREATED
            and not attempt.grants_execution_authority
            and lease_row.plan_id == intent.plan_id
            and lease_row.plan_digest == intent.plan_digest
            and lease_row.organization_id == intent.scope.organization_id
            and lease_row.environment_id == intent.scope.environment_id
            and lease_row.site_id == intent.scope.site_id
            and lease_row.target_type == intent.target_type
            and lease_row.target_id == intent.target_id
            and lease_row.lease_id == request.expected_lease_id == intent.lease_id
            and lease_row.canonical_digest == request.expected_lease_digest == intent.lease_digest
            and lease_row.fencing_token == request.expected_fencing_token == intent.fencing_token
            and lease_row.worker_subject_id == request.worker_subject_id == intent.worker_subject_id
            and lease_row.state == WorkflowOrchestrationLeaseState.ACTIVE.value
            and lease_row.expires_at > request.requested_at
        )

    @staticmethod
    def _dispatch_intent_staging_scope_id(intent: WorkflowDispatchIntent) -> str:
        return canonical_digest(
            {
                "scope": intent.scope.canonical_value(),
                "worker_subject_id": intent.worker_subject_id,
            }
        )

    @staticmethod
    def _dispatch_intent_payload(intent: WorkflowDispatchIntent) -> dict[str, Any]:
        return cast(dict[str, Any], intent.canonical_value())

    @staticmethod
    def _dispatch_intent_to_domain(raw: dict[str, Any]) -> WorkflowDispatchIntent:
        payload = dict(raw)
        payload["scope"] = WorkflowScope(**cast(Any, payload["scope"]))
        payload["staged_at"] = datetime.fromisoformat(str(payload["staged_at"]))
        payload["state"] = WorkflowDispatchIntentState(str(payload["state"]))
        payload["authority"] = WorkflowPlanAuthority(**cast(Any, payload["authority"]))
        return WorkflowDispatchIntent(**cast(Any, payload))

    @staticmethod
    def _dispatch_outbox_payload(entry: WorkflowDispatchOutboxEntry) -> dict[str, Any]:
        return cast(dict[str, Any], entry.canonical_value())

    @staticmethod
    def _dispatch_outbox_to_domain(raw: dict[str, Any]) -> WorkflowDispatchOutboxEntry:
        payload = dict(raw)
        payload["scope"] = WorkflowScope(**cast(Any, payload["scope"]))
        payload["admitted_at"] = datetime.fromisoformat(str(payload["admitted_at"]))
        payload["state"] = WorkflowDispatchOutboxState(str(payload["state"]))
        payload["authority"] = WorkflowPlanAuthority(**cast(Any, payload["authority"]))
        return WorkflowDispatchOutboxEntry(**cast(Any, payload))

    @staticmethod
    def _dispatch_outbox_matches_intent(
        entry: WorkflowDispatchOutboxEntry,
        intent: WorkflowDispatchIntent,
    ) -> bool:
        return bool(
            entry.dispatch_intent_id == intent.dispatch_intent_id
            and entry.dispatch_intent_digest == intent.canonical_digest
            and entry.plan_id == intent.plan_id
            and entry.plan_digest == intent.plan_digest
            and entry.run_id == intent.run_id
            and entry.run_digest == intent.run_digest
            and entry.step_run_id == intent.step_run_id
            and entry.step_run_digest == intent.step_run_digest
            and entry.step_id == intent.step_id
            and entry.attempt_id == intent.attempt_id
            and entry.attempt_digest == intent.attempt_digest
            and entry.attempt_number == intent.attempt_number
            and entry.scope == intent.scope
            and entry.target_id == intent.target_id
            and entry.target_type == intent.target_type
            and entry.lease_id == intent.lease_id
            and entry.lease_digest == intent.lease_digest
            and entry.fencing_token == intent.fencing_token
            and entry.worker_subject_id == intent.worker_subject_id
            and entry.admitted_at == intent.staged_at
        )

    @staticmethod
    def _dispatch_outbox_contract_violation() -> None:
        raise WorkflowDispatchIntentStagingError(
            "workflow_dispatch_outbox_repository_contract_violation",
            "The workflow dispatch outbox entry does not match its canonical payload.",
        )

    @staticmethod
    def _dispatch_intent_contract_violation() -> None:
        raise WorkflowDispatchIntentStagingError(
            "workflow_dispatch_intent_repository_contract_violation",
            "The workflow dispatch-intent record does not match its canonical payload.",
        )

    async def _dispatch_event_envelope_preparation_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowDispatchEventEnvelopePrepareRequest,
    ) -> WorkflowDispatchEventEnvelopePrepareResult | None:
        envelope = request.candidate
        claim = await self._load_dispatch_event_envelope_claim(
            session,
            scope=envelope.payload.scope,
            publisher_subject_id=envelope.publisher_subject_id,
            idempotency_key=request.idempotency_key,
        )
        if claim is None:
            return None
        record = self._dispatch_event_envelope_record_from_claim(claim)
        status = (
            WorkflowDispatchEventEnvelopePrepareStatus.REPLAY
            if record.request_fingerprint == request.request_fingerprint
            else WorkflowDispatchEventEnvelopePrepareStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowDispatchEventEnvelopePrepareResult(status, record.envelope)

    @classmethod
    async def _load_dispatch_event_envelope_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowDispatchEventEnvelopePreparationClaimModel | None:
        scope_id = cls._dispatch_event_envelope_idempotency_scope(
            scope,
            publisher_subject_id,
        )
        return cast(
            WorkflowDispatchEventEnvelopePreparationClaimModel | None,
            await session.scalar(
                select(WorkflowDispatchEventEnvelopePreparationClaimModel).where(
                    WorkflowDispatchEventEnvelopePreparationClaimModel.idempotency_scope_id
                    == scope_id,
                    WorkflowDispatchEventEnvelopePreparationClaimModel.idempotency_key
                    == idempotency_key,
                    WorkflowDispatchEventEnvelopePreparationClaimModel.organization_id
                    == scope.organization_id,
                    WorkflowDispatchEventEnvelopePreparationClaimModel.environment_id
                    == scope.environment_id,
                    WorkflowDispatchEventEnvelopePreparationClaimModel.site_id == scope.site_id,
                    WorkflowDispatchEventEnvelopePreparationClaimModel.publisher_subject_id
                    == publisher_subject_id,
                )
            ),
        )

    @classmethod
    def _dispatch_event_envelope_record_from_claim(
        cls,
        claim: WorkflowDispatchEventEnvelopePreparationClaimModel,
    ) -> WorkflowDispatchEventEnvelopePrepareIdempotencyRecord:
        raw = claim.payload.get("result_envelope")
        if not isinstance(raw, dict):
            cls._dispatch_event_envelope_contract_violation()
        try:
            envelope = cls._dispatch_event_envelope_to_domain(cast(dict[str, Any], raw))
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowDispatchEventEnvelopeError(
                "workflow_dispatch_event_envelope_repository_contract_violation",
                "The dispatch-event envelope repository contains an invalid idempotency result.",
            ) from exc
        scope_id = cls._dispatch_event_envelope_idempotency_scope(
            envelope.payload.scope,
            envelope.publisher_subject_id,
        )
        expected: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_digest": envelope.canonical_digest,
            "result_envelope": cls._dispatch_event_envelope_payload(envelope),
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != envelope.canonical_digest
            or claim.event_id != envelope.event_id
            or claim.outbox_entry_id != envelope.payload.outbox_entry_id
            or claim.plan_id != envelope.payload.plan_id
            or claim.organization_id != envelope.payload.scope.organization_id
            or claim.environment_id != envelope.payload.scope.environment_id
            or claim.site_id != envelope.payload.scope.site_id
            or claim.publisher_subject_id != envelope.publisher_subject_id
            or claim.payload != expected
            or claim.canonical_digest != canonical_digest(expected)
        ):
            cls._dispatch_event_envelope_contract_violation()
        return WorkflowDispatchEventEnvelopePrepareIdempotencyRecord(
            claim.request_fingerprint,
            envelope,
        )

    @classmethod
    def _dispatch_event_envelope_from_row(
        cls,
        row: WorkflowDispatchEventEnvelopeModel,
    ) -> WorkflowDispatchEventEnvelope:
        try:
            envelope = cls._dispatch_event_envelope_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowDispatchEventEnvelopeError(
                "workflow_dispatch_event_envelope_repository_contract_violation",
                "The dispatch-event envelope repository contains an invalid envelope.",
            ) from exc
        payload = envelope.payload
        if (
            row.event_id != envelope.event_id
            or row.event_type != envelope.event_type
            or row.event_version != envelope.event_version
            or row.occurred_at != envelope.occurred_at
            or row.recorded_at != envelope.recorded_at
            or row.producer != envelope.producer
            or row.producer_version != envelope.producer_version
            or row.subject_type != envelope.subject_type
            or row.subject_id != envelope.subject_id
            or row.organization_id != envelope.organization_id
            or row.environment_id != envelope.environment_id
            or row.site_id != payload.scope.site_id
            or row.correlation_id != envelope.correlation_id
            or row.causation_id != envelope.causation_id
            or row.workflow_id != envelope.workflow_id
            or row.data_classification != envelope.data_classification
            or row.schema_uri != envelope.schema_uri
            or row.outbox_entry_id != payload.outbox_entry_id
            or row.outbox_entry_digest != payload.outbox_entry_digest
            or row.dispatch_intent_id != payload.dispatch_intent_id
            or row.dispatch_intent_digest != payload.dispatch_intent_digest
            or row.plan_id != payload.plan_id
            or row.plan_digest != payload.plan_digest
            or row.run_id != payload.run_id
            or row.run_digest != payload.run_digest
            or row.step_run_id != payload.step_run_id
            or row.step_run_digest != payload.step_run_digest
            or row.step_id != payload.step_id
            or row.attempt_id != payload.attempt_id
            or row.attempt_digest != payload.attempt_digest
            or row.attempt_number != payload.attempt_number
            or row.target_type != payload.target_type
            or row.target_id != payload.target_id
            or row.orchestration_lease_id != envelope.orchestration_lease_id
            or row.orchestration_lease_digest != envelope.orchestration_lease_digest
            or row.orchestration_fencing_token != envelope.orchestration_fencing_token
            or row.publication_lease_id != envelope.publication_lease_id
            or row.publication_lease_digest != envelope.publication_lease_digest
            or row.publication_fencing_token != envelope.publication_fencing_token
            or row.publisher_subject_id != envelope.publisher_subject_id
            or row.prepared_at != envelope.prepared_at
            or row.state != envelope.state.value
            or row.publication_authority_granted != envelope.grants_publication_authority
            or row.delivery_authority_granted != envelope.grants_delivery_authority
            or row.dispatch_authority_granted != envelope.grants_dispatch_authority
            or row.execution_authority_granted != envelope.grants_execution_authority
            or row.canonical_digest != envelope.canonical_digest
        ):
            cls._dispatch_event_envelope_contract_violation()
        return envelope

    @classmethod
    def _dispatch_event_envelope_model(
        cls,
        envelope: WorkflowDispatchEventEnvelope,
    ) -> WorkflowDispatchEventEnvelopeModel:
        payload = envelope.payload
        return WorkflowDispatchEventEnvelopeModel(
            event_id=envelope.event_id,
            event_type=envelope.event_type,
            event_version=envelope.event_version,
            occurred_at=envelope.occurred_at,
            recorded_at=envelope.recorded_at,
            producer=envelope.producer,
            producer_version=envelope.producer_version,
            subject_type=envelope.subject_type,
            subject_id=envelope.subject_id,
            organization_id=envelope.organization_id,
            environment_id=envelope.environment_id,
            site_id=payload.scope.site_id,
            correlation_id=envelope.correlation_id,
            causation_id=envelope.causation_id,
            workflow_id=envelope.workflow_id,
            data_classification=envelope.data_classification,
            schema_uri=envelope.schema_uri,
            outbox_entry_id=payload.outbox_entry_id,
            outbox_entry_digest=payload.outbox_entry_digest,
            dispatch_intent_id=payload.dispatch_intent_id,
            dispatch_intent_digest=payload.dispatch_intent_digest,
            plan_id=payload.plan_id,
            plan_digest=payload.plan_digest,
            run_id=payload.run_id,
            run_digest=payload.run_digest,
            step_run_id=payload.step_run_id,
            step_run_digest=payload.step_run_digest,
            step_id=payload.step_id,
            attempt_id=payload.attempt_id,
            attempt_digest=payload.attempt_digest,
            attempt_number=payload.attempt_number,
            target_type=payload.target_type,
            target_id=payload.target_id,
            orchestration_lease_id=envelope.orchestration_lease_id,
            orchestration_lease_digest=envelope.orchestration_lease_digest,
            orchestration_fencing_token=envelope.orchestration_fencing_token,
            publication_lease_id=envelope.publication_lease_id,
            publication_lease_digest=envelope.publication_lease_digest,
            publication_fencing_token=envelope.publication_fencing_token,
            publisher_subject_id=envelope.publisher_subject_id,
            prepared_at=envelope.prepared_at,
            state=envelope.state.value,
            publication_authority_granted=envelope.grants_publication_authority,
            delivery_authority_granted=envelope.grants_delivery_authority,
            dispatch_authority_granted=envelope.grants_dispatch_authority,
            execution_authority_granted=envelope.grants_execution_authority,
            canonical_digest=envelope.canonical_digest,
            payload=cls._dispatch_event_envelope_payload(envelope),
        )

    @classmethod
    def _dispatch_event_envelope_claim_model(
        cls,
        request: WorkflowDispatchEventEnvelopePrepareRequest,
    ) -> WorkflowDispatchEventEnvelopePreparationClaimModel:
        envelope = request.candidate
        scope = envelope.payload.scope
        scope_id = cls._dispatch_event_envelope_idempotency_scope(
            scope,
            envelope.publisher_subject_id,
        )
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_digest": envelope.canonical_digest,
            "result_envelope": cls._dispatch_event_envelope_payload(envelope),
        }
        digest = canonical_digest(payload)
        return WorkflowDispatchEventEnvelopePreparationClaimModel(
            claim_id=f"workflow_dispatch_event_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=envelope.canonical_digest,
            event_id=envelope.event_id,
            outbox_entry_id=envelope.payload.outbox_entry_id,
            plan_id=envelope.payload.plan_id,
            organization_id=scope.organization_id,
            environment_id=scope.environment_id,
            site_id=scope.site_id,
            publisher_subject_id=envelope.publisher_subject_id,
            created_at=request.requested_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _dispatch_event_envelope_evidence_matches(
        cls,
        *,
        plan_row: WorkflowRunPlanModel | None,
        outbox_row: WorkflowDispatchOutboxEntryModel | None,
        orchestration_lease_row: WorkflowOrchestrationLeaseModel | None,
        publication_lease_row: WorkflowOutboxPublicationLeaseModel | None,
        request: WorkflowDispatchEventEnvelopePrepareRequest,
    ) -> bool:
        if any(
            item is None
            for item in (
                plan_row,
                outbox_row,
                orchestration_lease_row,
                publication_lease_row,
            )
        ):
            return False
        assert plan_row is not None
        assert outbox_row is not None
        assert orchestration_lease_row is not None
        assert publication_lease_row is not None
        candidate = request.candidate
        payload = candidate.payload
        try:
            outbox = cls._dispatch_outbox_from_row(outbox_row)
            orchestration_lease = cls._lease_from_row(orchestration_lease_row)
            publication_lease = cls._publication_lease_from_row(publication_lease_row)
        except (
            WorkflowDispatchIntentStagingError,
            WorkflowOrchestrationLeaseError,
            WorkflowOutboxPublicationLeaseError,
        ) as exc:
            raise WorkflowDispatchEventEnvelopeError(
                "workflow_dispatch_event_envelope_repository_contract_violation",
                "Workflow evidence is inconsistent during event-envelope preparation.",
            ) from exc
        return bool(
            plan_row.plan_id == payload.plan_id
            and plan_row.state == WorkflowPlanState.PLANNED.value
            and plan_row.canonical_digest == request.expected_plan_digest == payload.plan_digest
            and plan_row.organization_id == payload.scope.organization_id
            and plan_row.environment_id == payload.scope.environment_id
            and plan_row.site_id == payload.scope.site_id
            and plan_row.target_type == payload.target_type
            and plan_row.target_id == payload.target_id
            and outbox.state is WorkflowDispatchOutboxState.PENDING_PUBLICATION
            and outbox.canonical_digest
            == request.expected_outbox_entry_digest
            == payload.outbox_entry_digest
            and outbox.outbox_entry_id == payload.outbox_entry_id
            and outbox.dispatch_intent_id == payload.dispatch_intent_id
            and outbox.dispatch_intent_digest == payload.dispatch_intent_digest
            and outbox.plan_id == payload.plan_id
            and outbox.plan_digest == payload.plan_digest
            and outbox.run_id == payload.run_id
            and outbox.run_digest == payload.run_digest
            and outbox.step_run_id == payload.step_run_id
            and outbox.step_run_digest == payload.step_run_digest
            and outbox.step_id == payload.step_id
            and outbox.attempt_id == payload.attempt_id
            and outbox.attempt_digest == payload.attempt_digest
            and outbox.attempt_number == payload.attempt_number == 1
            and outbox.scope == payload.scope
            and outbox.target_id == payload.target_id
            and outbox.target_type == payload.target_type
            and not any(outbox.authority.canonical_value().values())
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
            and orchestration_lease.plan_id == payload.plan_id
            and orchestration_lease.plan_digest == payload.plan_digest
            and orchestration_lease.scope == payload.scope
            and orchestration_lease.target_id == payload.target_id
            and orchestration_lease.target_type == payload.target_type
            and orchestration_lease.effective_state(requested_at=request.requested_at)
            is WorkflowOrchestrationLeaseEffectiveState.ACTIVE
            and publication_lease.publication_lease_id
            == request.expected_publication_lease_id
            == candidate.publication_lease_id
            and publication_lease.canonical_digest
            == request.expected_publication_lease_digest
            == candidate.publication_lease_digest
            and publication_lease.publication_fencing_token
            == request.expected_publication_fencing_token
            == candidate.publication_fencing_token
            and publication_lease.outbox_entry_id == payload.outbox_entry_id
            and publication_lease.outbox_entry_digest == payload.outbox_entry_digest
            and publication_lease.dispatch_intent_id == payload.dispatch_intent_id
            and publication_lease.dispatch_intent_digest == payload.dispatch_intent_digest
            and publication_lease.plan_id == payload.plan_id
            and publication_lease.plan_digest == payload.plan_digest
            and publication_lease.run_id == payload.run_id
            and publication_lease.run_digest == payload.run_digest
            and publication_lease.step_run_id == payload.step_run_id
            and publication_lease.step_run_digest == payload.step_run_digest
            and publication_lease.step_id == payload.step_id
            and publication_lease.attempt_id == payload.attempt_id
            and publication_lease.attempt_digest == payload.attempt_digest
            and publication_lease.attempt_number == payload.attempt_number
            and publication_lease.scope == payload.scope
            and publication_lease.target_id == payload.target_id
            and publication_lease.target_type == payload.target_type
            and publication_lease.orchestration_lease_id == candidate.orchestration_lease_id
            and publication_lease.orchestration_lease_digest == candidate.orchestration_lease_digest
            and publication_lease.orchestration_fencing_token
            == candidate.orchestration_fencing_token
            and publication_lease.publisher_subject_id == candidate.publisher_subject_id
            and publication_lease.publisher_subject_id == request.publisher_subject_id
            and publication_lease.effective_state(requested_at=request.requested_at)
            is WorkflowOutboxPublicationLeaseEffectiveState.ACTIVE
            and not any(candidate.authority.canonical_value().values())
            and not candidate.grants_publication_authority
            and not candidate.grants_delivery_authority
            and not candidate.grants_dispatch_authority
            and not candidate.grants_execution_authority
        )

    @staticmethod
    def _dispatch_event_envelope_idempotency_scope(
        scope: WorkflowScope,
        publisher_subject_id: str,
    ) -> str:
        return canonical_digest(
            {
                "publisher_subject_id": publisher_subject_id,
                "scope": scope.canonical_value(),
            }
        )

    @staticmethod
    def _dispatch_event_envelope_payload(
        envelope: WorkflowDispatchEventEnvelope,
    ) -> dict[str, Any]:
        return cast(dict[str, Any], envelope.canonical_value())

    @staticmethod
    def _dispatch_event_envelope_to_domain(
        raw: dict[str, Any],
    ) -> WorkflowDispatchEventEnvelope:
        values = dict(raw)
        event_payload = dict(cast(dict[str, Any], values["payload"]))
        event_payload["scope"] = WorkflowScope(**cast(Any, event_payload["scope"]))
        values["payload"] = WorkflowDispatchEventPayload(**cast(Any, event_payload))
        values["occurred_at"] = datetime.fromisoformat(str(values["occurred_at"]))
        values["recorded_at"] = datetime.fromisoformat(str(values["recorded_at"]))
        values["prepared_at"] = datetime.fromisoformat(str(values["prepared_at"]))
        values["extensions"] = tuple(sorted(cast(dict[str, str], values["extensions"]).items()))
        values["state"] = WorkflowDispatchEventEnvelopeState(str(values["state"]))
        values["authority"] = WorkflowDispatchEventAuthority(**cast(Any, values["authority"]))
        return WorkflowDispatchEventEnvelope(**cast(Any, values))

    @staticmethod
    def _validate_dispatch_event_envelope_preparation_request(
        request: WorkflowDispatchEventEnvelopePrepareRequest,
    ) -> None:
        candidate = request.candidate
        if (
            candidate.state is not WorkflowDispatchEventEnvelopeState.PREPARED
            or candidate.payload.attempt_number != 1
            or candidate.publisher_subject_id != request.publisher_subject_id
            or candidate.grants_publication_authority
            or candidate.grants_delivery_authority
            or candidate.grants_dispatch_authority
            or candidate.grants_execution_authority
        ):
            raise ValueError("workflow dispatch-event envelope preparation payload is unsafe")
        if not request.idempotency_key or len(request.idempotency_key) > 128:
            raise ValueError("workflow dispatch-event envelope idempotency key is invalid")
        if len(request.request_fingerprint) != 64:
            raise ValueError("workflow dispatch-event envelope request fingerprint is invalid")
        if request.requested_at.tzinfo is None:
            raise ValueError("workflow dispatch-event envelope preparation time must be aware")

    @staticmethod
    def _dispatch_event_envelope_contract_violation() -> None:
        raise WorkflowDispatchEventEnvelopeError(
            "workflow_dispatch_event_envelope_repository_contract_violation",
            "The workflow dispatch-event envelope does not match its canonical payload.",
        )

    async def _event_transport_admission_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowEventTransportAdmissionRequest,
    ) -> WorkflowEventTransportAdmissionResult | None:
        candidate = request.candidate
        claim = await self._load_event_transport_admission_claim(
            session,
            scope=candidate.scope,
            publisher_subject_id=candidate.publisher_subject_id,
            idempotency_key=request.idempotency_key,
        )
        if claim is None:
            return None
        record = self._event_transport_admission_record_from_claim(claim)
        status = (
            WorkflowEventTransportAdmissionStatus.REPLAY
            if record.request_fingerprint == request.request_fingerprint
            else WorkflowEventTransportAdmissionStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowEventTransportAdmissionResult(status, record.admission)

    @classmethod
    async def _load_event_transport_admission_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventTransportAdmissionClaimModel | None:
        scope_id = cls._event_transport_admission_idempotency_scope(
            scope,
            publisher_subject_id,
        )
        return cast(
            WorkflowEventTransportAdmissionClaimModel | None,
            await session.scalar(
                select(WorkflowEventTransportAdmissionClaimModel).where(
                    WorkflowEventTransportAdmissionClaimModel.idempotency_scope_id == scope_id,
                    WorkflowEventTransportAdmissionClaimModel.idempotency_key == idempotency_key,
                    WorkflowEventTransportAdmissionClaimModel.organization_id
                    == scope.organization_id,
                    WorkflowEventTransportAdmissionClaimModel.environment_id
                    == scope.environment_id,
                    WorkflowEventTransportAdmissionClaimModel.site_id == scope.site_id,
                    WorkflowEventTransportAdmissionClaimModel.publisher_subject_id
                    == publisher_subject_id,
                )
            ),
        )

    @classmethod
    def _event_transport_admission_record_from_claim(
        cls,
        claim: WorkflowEventTransportAdmissionClaimModel,
    ) -> WorkflowEventTransportAdmissionIdempotencyRecord:
        raw = claim.payload.get("result_admission")
        if not isinstance(raw, dict):
            cls._event_transport_admission_contract_violation()
        try:
            admission = cls._event_transport_admission_to_domain(cast(dict[str, Any], raw))
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowEventTransportAdmissionError(
                "workflow_event_transport_admission_repository_contract_violation",
                "The transport-admission repository contains an invalid idempotency result.",
            ) from exc
        scope_id = cls._event_transport_admission_idempotency_scope(
            admission.scope,
            admission.publisher_subject_id,
        )
        expected: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_digest": admission.canonical_digest,
            "result_admission": cls._event_transport_admission_payload(admission),
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != admission.canonical_digest
            or claim.admission_id != admission.admission_id
            or claim.event_id != admission.event_id
            or claim.outbox_entry_id != admission.outbox_entry_id
            or claim.plan_id != admission.plan_id
            or claim.organization_id != admission.scope.organization_id
            or claim.environment_id != admission.scope.environment_id
            or claim.site_id != admission.scope.site_id
            or claim.publisher_subject_id != admission.publisher_subject_id
            or claim.payload != expected
            or claim.canonical_digest != canonical_digest(expected)
        ):
            cls._event_transport_admission_contract_violation()
        return WorkflowEventTransportAdmissionIdempotencyRecord(
            claim.request_fingerprint,
            admission,
        )

    @classmethod
    def _event_transport_admission_from_row(
        cls,
        row: WorkflowEventTransportAdmissionModel,
    ) -> WorkflowEventTransportAdmission:
        try:
            admission = cls._event_transport_admission_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowEventTransportAdmissionError(
                "workflow_event_transport_admission_repository_contract_violation",
                "The transport-admission repository contains an invalid admission.",
            ) from exc
        if (
            row.admission_id != admission.admission_id
            or row.event_id != admission.event_id
            or row.event_digest != admission.event_digest
            or row.outbox_entry_id != admission.outbox_entry_id
            or row.outbox_entry_digest != admission.outbox_entry_digest
            or row.dispatch_intent_id != admission.dispatch_intent_id
            or row.dispatch_intent_digest != admission.dispatch_intent_digest
            or row.plan_id != admission.plan_id
            or row.plan_digest != admission.plan_digest
            or row.run_id != admission.run_id
            or row.run_digest != admission.run_digest
            or row.step_run_id != admission.step_run_id
            or row.step_run_digest != admission.step_run_digest
            or row.step_id != admission.step_id
            or row.attempt_id != admission.attempt_id
            or row.attempt_digest != admission.attempt_digest
            or row.attempt_number != admission.attempt_number
            or row.organization_id != admission.scope.organization_id
            or row.environment_id != admission.scope.environment_id
            or row.site_id != admission.scope.site_id
            or row.target_type != admission.target_type
            or row.target_id != admission.target_id
            or row.policy_id != admission.policy_id
            or row.policy_version != admission.policy_version
            or row.policy_digest != admission.policy_digest
            or row.event_type != admission.event_type
            or row.event_version != admission.event_version
            or row.schema_uri != admission.schema_uri
            or row.data_classification != admission.data_classification
            or row.representation_name != admission.representation_name
            or row.encoding != admission.encoding
            or row.maximum_canonical_byte_count != admission.maximum_canonical_byte_count
            or row.canonical_byte_count != admission.canonical_byte_count
            or row.orchestration_lease_id != admission.orchestration_lease_id
            or row.orchestration_lease_digest != admission.orchestration_lease_digest
            or row.orchestration_fencing_token != admission.orchestration_fencing_token
            or row.publication_lease_id != admission.publication_lease_id
            or row.publication_lease_digest != admission.publication_lease_digest
            or row.publication_fencing_token != admission.publication_fencing_token
            or row.publisher_subject_id != admission.publisher_subject_id
            or row.admitted_at != admission.admitted_at
            or row.state != admission.state.value
            or row.publication_authority_granted != admission.grants_publication_authority
            or row.delivery_authority_granted != admission.grants_delivery_authority
            or row.dispatch_authority_granted != admission.grants_dispatch_authority
            or row.execution_authority_granted != admission.grants_execution_authority
            or row.canonical_digest != admission.canonical_digest
        ):
            cls._event_transport_admission_contract_violation()
        return admission

    @classmethod
    def _event_transport_admission_model(
        cls,
        admission: WorkflowEventTransportAdmission,
    ) -> WorkflowEventTransportAdmissionModel:
        return WorkflowEventTransportAdmissionModel(
            admission_id=admission.admission_id,
            event_id=admission.event_id,
            event_digest=admission.event_digest,
            outbox_entry_id=admission.outbox_entry_id,
            outbox_entry_digest=admission.outbox_entry_digest,
            dispatch_intent_id=admission.dispatch_intent_id,
            dispatch_intent_digest=admission.dispatch_intent_digest,
            plan_id=admission.plan_id,
            plan_digest=admission.plan_digest,
            run_id=admission.run_id,
            run_digest=admission.run_digest,
            step_run_id=admission.step_run_id,
            step_run_digest=admission.step_run_digest,
            step_id=admission.step_id,
            attempt_id=admission.attempt_id,
            attempt_digest=admission.attempt_digest,
            attempt_number=admission.attempt_number,
            organization_id=admission.scope.organization_id,
            environment_id=admission.scope.environment_id,
            site_id=admission.scope.site_id,
            target_type=admission.target_type,
            target_id=admission.target_id,
            policy_id=admission.policy_id,
            policy_version=admission.policy_version,
            policy_digest=admission.policy_digest,
            event_type=admission.event_type,
            event_version=admission.event_version,
            schema_uri=admission.schema_uri,
            data_classification=admission.data_classification,
            representation_name=admission.representation_name,
            encoding=admission.encoding,
            maximum_canonical_byte_count=admission.maximum_canonical_byte_count,
            canonical_byte_count=admission.canonical_byte_count,
            orchestration_lease_id=admission.orchestration_lease_id,
            orchestration_lease_digest=admission.orchestration_lease_digest,
            orchestration_fencing_token=admission.orchestration_fencing_token,
            publication_lease_id=admission.publication_lease_id,
            publication_lease_digest=admission.publication_lease_digest,
            publication_fencing_token=admission.publication_fencing_token,
            publisher_subject_id=admission.publisher_subject_id,
            admitted_at=admission.admitted_at,
            state=admission.state.value,
            publication_authority_granted=admission.grants_publication_authority,
            delivery_authority_granted=admission.grants_delivery_authority,
            dispatch_authority_granted=admission.grants_dispatch_authority,
            execution_authority_granted=admission.grants_execution_authority,
            canonical_digest=admission.canonical_digest,
            payload=cls._event_transport_admission_payload(admission),
        )

    @classmethod
    def _event_transport_admission_claim_model(
        cls,
        request: WorkflowEventTransportAdmissionRequest,
    ) -> WorkflowEventTransportAdmissionClaimModel:
        admission = request.candidate
        scope_id = cls._event_transport_admission_idempotency_scope(
            admission.scope,
            admission.publisher_subject_id,
        )
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_digest": admission.canonical_digest,
            "result_admission": cls._event_transport_admission_payload(admission),
        }
        digest = canonical_digest(payload)
        return WorkflowEventTransportAdmissionClaimModel(
            claim_id=f"workflow_event_transport_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=admission.canonical_digest,
            admission_id=admission.admission_id,
            event_id=admission.event_id,
            outbox_entry_id=admission.outbox_entry_id,
            plan_id=admission.plan_id,
            organization_id=admission.scope.organization_id,
            environment_id=admission.scope.environment_id,
            site_id=admission.scope.site_id,
            publisher_subject_id=admission.publisher_subject_id,
            created_at=request.requested_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _event_transport_admission_evidence_matches(
        cls,
        *,
        plan_row: WorkflowRunPlanModel | None,
        outbox_row: WorkflowDispatchOutboxEntryModel | None,
        orchestration_lease_row: WorkflowOrchestrationLeaseModel | None,
        publication_lease_row: WorkflowOutboxPublicationLeaseModel | None,
        envelope_row: WorkflowDispatchEventEnvelopeModel | None,
        request: WorkflowEventTransportAdmissionRequest,
    ) -> bool:
        if any(
            item is None
            for item in (
                plan_row,
                outbox_row,
                orchestration_lease_row,
                publication_lease_row,
                envelope_row,
            )
        ):
            return False
        assert plan_row is not None
        assert outbox_row is not None
        assert orchestration_lease_row is not None
        assert publication_lease_row is not None
        assert envelope_row is not None
        candidate = request.candidate
        policy = code_owned_workflow_event_transport_admission_policy()
        try:
            outbox = cls._dispatch_outbox_from_row(outbox_row)
            orchestration_lease = cls._lease_from_row(orchestration_lease_row)
            publication_lease = cls._publication_lease_from_row(publication_lease_row)
            envelope = cls._dispatch_event_envelope_from_row(envelope_row)
        except (
            WorkflowDispatchIntentStagingError,
            WorkflowOrchestrationLeaseError,
            WorkflowOutboxPublicationLeaseError,
            WorkflowDispatchEventEnvelopeError,
        ) as exc:
            raise WorkflowEventTransportAdmissionError(
                "workflow_event_transport_admission_repository_contract_violation",
                "Workflow evidence is inconsistent during transport admission.",
            ) from exc
        event_payload = envelope.payload
        return bool(
            plan_row.plan_id == candidate.plan_id
            and plan_row.state == WorkflowPlanState.PLANNED.value
            and plan_row.canonical_digest == request.expected_plan_digest == candidate.plan_digest
            and plan_row.organization_id == candidate.scope.organization_id
            and plan_row.environment_id == candidate.scope.environment_id
            and plan_row.site_id == candidate.scope.site_id
            and plan_row.target_type == candidate.target_type
            and plan_row.target_id == candidate.target_id
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
            and publication_lease.dispatch_intent_id == candidate.dispatch_intent_id
            and publication_lease.dispatch_intent_digest == candidate.dispatch_intent_digest
            and publication_lease.plan_id == candidate.plan_id
            and publication_lease.plan_digest == candidate.plan_digest
            and publication_lease.run_id == candidate.run_id
            and publication_lease.run_digest == candidate.run_digest
            and publication_lease.step_run_id == candidate.step_run_id
            and publication_lease.step_run_digest == candidate.step_run_digest
            and publication_lease.step_id == candidate.step_id
            and publication_lease.attempt_id == candidate.attempt_id
            and publication_lease.attempt_digest == candidate.attempt_digest
            and publication_lease.attempt_number == candidate.attempt_number
            and publication_lease.scope == candidate.scope
            and publication_lease.target_id == candidate.target_id
            and publication_lease.target_type == candidate.target_type
            and publication_lease.orchestration_lease_id == candidate.orchestration_lease_id
            and publication_lease.orchestration_lease_digest == candidate.orchestration_lease_digest
            and publication_lease.orchestration_fencing_token
            == candidate.orchestration_fencing_token
            and publication_lease.publisher_subject_id
            == request.publisher_subject_id
            == candidate.publisher_subject_id
            and publication_lease.effective_state(requested_at=request.requested_at)
            is WorkflowOutboxPublicationLeaseEffectiveState.ACTIVE
            and envelope.state is WorkflowDispatchEventEnvelopeState.PREPARED
            and envelope.event_id == request.expected_event_id == candidate.event_id
            and envelope.canonical_digest == request.expected_event_digest == candidate.event_digest
            and envelope.event_type == candidate.event_type
            and envelope.event_version == candidate.event_version
            and envelope.schema_uri == candidate.schema_uri
            and envelope.data_classification == candidate.data_classification
            and event_payload.outbox_entry_id == candidate.outbox_entry_id
            and event_payload.outbox_entry_digest == candidate.outbox_entry_digest
            and event_payload.dispatch_intent_id == candidate.dispatch_intent_id
            and event_payload.dispatch_intent_digest == candidate.dispatch_intent_digest
            and event_payload.plan_id == candidate.plan_id
            and event_payload.plan_digest == candidate.plan_digest
            and event_payload.run_id == candidate.run_id
            and event_payload.run_digest == candidate.run_digest
            and event_payload.step_run_id == candidate.step_run_id
            and event_payload.step_run_digest == candidate.step_run_digest
            and event_payload.step_id == candidate.step_id
            and event_payload.attempt_id == candidate.attempt_id
            and event_payload.attempt_digest == candidate.attempt_digest
            and event_payload.attempt_number == candidate.attempt_number
            and event_payload.scope == candidate.scope
            and event_payload.target_id == candidate.target_id
            and event_payload.target_type == candidate.target_type
            and envelope.orchestration_lease_id == candidate.orchestration_lease_id
            and envelope.orchestration_lease_digest == candidate.orchestration_lease_digest
            and envelope.orchestration_fencing_token == candidate.orchestration_fencing_token
            and envelope.publication_lease_id == candidate.publication_lease_id
            and envelope.publication_lease_digest == candidate.publication_lease_digest
            and envelope.publication_fencing_token == candidate.publication_fencing_token
            and envelope.publisher_subject_id == candidate.publisher_subject_id
            and candidate.canonical_byte_count
            == canonical_json_byte_count(envelope.canonical_value())
            and candidate.policy_id == policy.policy_id
            and candidate.policy_version == policy.policy_version
            and candidate.policy_digest == request.expected_policy_digest == policy.canonical_digest
            and candidate.event_type in policy.allowed_event_types
            and candidate.event_version in policy.allowed_event_versions
            and candidate.schema_uri in policy.allowed_schema_uris
            and candidate.data_classification in policy.allowed_data_classifications
            and candidate.representation_name == policy.representation_name
            and candidate.encoding == policy.encoding
            and candidate.maximum_canonical_byte_count == policy.maximum_canonical_byte_count
            and candidate.canonical_byte_count <= candidate.maximum_canonical_byte_count
            and not any(envelope.authority.canonical_value().values())
            and not any(candidate.authority.canonical_value().values())
            and not candidate.grants_publication_authority
            and not candidate.grants_delivery_authority
            and not candidate.grants_dispatch_authority
            and not candidate.grants_execution_authority
        )

    @staticmethod
    def _event_transport_admission_idempotency_scope(
        scope: WorkflowScope,
        publisher_subject_id: str,
    ) -> str:
        return canonical_digest(
            {
                "publisher_subject_id": publisher_subject_id,
                "scope": scope.canonical_value(),
            }
        )

    @staticmethod
    def _event_transport_admission_payload(
        admission: WorkflowEventTransportAdmission,
    ) -> dict[str, Any]:
        return cast(dict[str, Any], admission.canonical_value())

    @staticmethod
    def _event_transport_admission_to_domain(
        raw: dict[str, Any],
    ) -> WorkflowEventTransportAdmission:
        values = dict(raw)
        values["scope"] = WorkflowScope(**cast(Any, values["scope"]))
        values["admitted_at"] = datetime.fromisoformat(str(values["admitted_at"]))
        values["state"] = WorkflowEventTransportAdmissionState(str(values["state"]))
        values["authority"] = WorkflowEventTransportAdmissionAuthority(
            **cast(Any, values["authority"])
        )
        return WorkflowEventTransportAdmission(**cast(Any, values))

    @staticmethod
    def _validate_event_transport_admission_request(
        request: WorkflowEventTransportAdmissionRequest,
    ) -> None:
        candidate = request.candidate
        if (
            candidate.state is not WorkflowEventTransportAdmissionState.ADMITTED
            or candidate.attempt_number != 1
            or candidate.publisher_subject_id != request.publisher_subject_id
            or candidate.grants_publication_authority
            or candidate.grants_delivery_authority
            or candidate.grants_dispatch_authority
            or candidate.grants_execution_authority
        ):
            raise ValueError("workflow event transport admission payload is unsafe")
        if not request.idempotency_key or len(request.idempotency_key) > 128:
            raise ValueError("workflow event transport admission idempotency key is invalid")
        if len(request.request_fingerprint) != 64:
            raise ValueError("workflow event transport admission request fingerprint is invalid")
        if request.requested_at.tzinfo is None:
            raise ValueError("workflow event transport admission time must be aware")

    @staticmethod
    def _event_transport_admission_contract_violation() -> None:
        raise WorkflowEventTransportAdmissionError(
            "workflow_event_transport_admission_repository_contract_violation",
            "The workflow event transport admission does not match its canonical payload.",
        )

    async def _event_byte_artifact_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowEventByteArtifactRequest,
    ) -> WorkflowEventByteArtifactResult | None:
        candidate = request.candidate
        claim = await self._load_event_byte_artifact_claim(
            session,
            scope=candidate.scope,
            publisher_subject_id=candidate.publisher_subject_id,
            idempotency_key=request.idempotency_key,
        )
        if claim is None:
            return None
        artifact_row = await session.get(WorkflowEventByteArtifactModel, claim.artifact_id)
        record = self._event_byte_artifact_record_from_claim(claim, artifact_row)
        status = (
            WorkflowEventByteArtifactStatus.REPLAY
            if record.request_fingerprint == request.request_fingerprint
            else WorkflowEventByteArtifactStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowEventByteArtifactResult(status, record.artifact)

    @classmethod
    async def _load_event_byte_artifact_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventByteArtifactClaimModel | None:
        scope_id = cls._event_byte_artifact_idempotency_scope(scope, publisher_subject_id)
        return cast(
            WorkflowEventByteArtifactClaimModel | None,
            await session.scalar(
                select(WorkflowEventByteArtifactClaimModel).where(
                    WorkflowEventByteArtifactClaimModel.idempotency_scope_id == scope_id,
                    WorkflowEventByteArtifactClaimModel.idempotency_key == idempotency_key,
                    WorkflowEventByteArtifactClaimModel.organization_id == scope.organization_id,
                    WorkflowEventByteArtifactClaimModel.environment_id == scope.environment_id,
                    WorkflowEventByteArtifactClaimModel.site_id == scope.site_id,
                    WorkflowEventByteArtifactClaimModel.publisher_subject_id
                    == publisher_subject_id,
                )
            ),
        )

    @classmethod
    def _event_byte_artifact_record_from_claim(
        cls,
        claim: WorkflowEventByteArtifactClaimModel,
        artifact_row: WorkflowEventByteArtifactModel | None,
    ) -> WorkflowEventByteArtifactIdempotencyRecord:
        if artifact_row is None:
            cls._event_byte_artifact_contract_violation()
        assert artifact_row is not None
        artifact = cls._event_byte_artifact_from_row(artifact_row)
        scope_id = cls._event_byte_artifact_idempotency_scope(
            artifact.scope, artifact.publisher_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_artifact": cls._event_byte_artifact_payload(artifact),
            "result_digest": artifact.canonical_digest,
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != artifact.canonical_digest
            or claim.artifact_id != artifact.artifact_id
            or claim.admission_id != artifact.admission_id
            or claim.event_id != artifact.event_id
            or claim.outbox_entry_id != artifact.outbox_entry_id
            or claim.plan_id != artifact.plan_id
            or claim.organization_id != artifact.scope.organization_id
            or claim.environment_id != artifact.scope.environment_id
            or claim.site_id != artifact.scope.site_id
            or claim.publisher_subject_id != artifact.publisher_subject_id
            or claim.payload != payload
            or claim.canonical_digest != canonical_digest(payload)
        ):
            cls._event_byte_artifact_contract_violation()
        return WorkflowEventByteArtifactIdempotencyRecord(
            request_fingerprint=claim.request_fingerprint,
            artifact=artifact,
        )

    @classmethod
    def _event_byte_artifact_from_row(
        cls, row: WorkflowEventByteArtifactModel
    ) -> WorkflowEventByteArtifact:
        try:
            artifact = cls._event_byte_artifact_to_domain(row.payload, row.canonical_bytes)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowEventByteArtifactError(
                "workflow_event_byte_artifact_repository_contract_violation",
                "The byte-artifact repository contains an invalid artifact.",
            ) from exc
        if (
            row.artifact_id != artifact.artifact_id
            or row.admission_id != artifact.admission_id
            or row.admission_digest != artifact.admission_digest
            or row.event_id != artifact.event_id
            or row.event_digest != artifact.event_digest
            or row.event_type != artifact.event_type
            or row.event_version != artifact.event_version
            or row.schema_uri != artifact.schema_uri
            or row.data_classification != artifact.data_classification
            or row.outbox_entry_id != artifact.outbox_entry_id
            or row.outbox_entry_digest != artifact.outbox_entry_digest
            or row.dispatch_intent_id != artifact.dispatch_intent_id
            or row.dispatch_intent_digest != artifact.dispatch_intent_digest
            or row.plan_id != artifact.plan_id
            or row.plan_digest != artifact.plan_digest
            or row.run_id != artifact.run_id
            or row.run_digest != artifact.run_digest
            or row.step_run_id != artifact.step_run_id
            or row.step_run_digest != artifact.step_run_digest
            or row.step_id != artifact.step_id
            or row.attempt_id != artifact.attempt_id
            or row.attempt_digest != artifact.attempt_digest
            or row.attempt_number != artifact.attempt_number
            or row.organization_id != artifact.scope.organization_id
            or row.environment_id != artifact.scope.environment_id
            or row.site_id != artifact.scope.site_id
            or row.target_type != artifact.target_type
            or row.target_id != artifact.target_id
            or row.policy_id != artifact.policy_id
            or row.policy_version != artifact.policy_version
            or row.policy_digest != artifact.policy_digest
            or row.representation_name != artifact.representation_name
            or row.encoding != artifact.encoding
            or row.maximum_canonical_byte_count != artifact.maximum_canonical_byte_count
            or row.canonical_byte_count != artifact.canonical_byte_count
            or row.content_sha256 != artifact.content_sha256
            or row.orchestration_lease_id != artifact.orchestration_lease_id
            or row.orchestration_lease_digest != artifact.orchestration_lease_digest
            or row.orchestration_fencing_token != artifact.orchestration_fencing_token
            or row.publication_lease_id != artifact.publication_lease_id
            or row.publication_lease_digest != artifact.publication_lease_digest
            or row.publication_fencing_token != artifact.publication_fencing_token
            or row.publisher_subject_id != artifact.publisher_subject_id
            or row.materialized_at != artifact.materialized_at
            or row.state != artifact.state.value
            or row.publication_authority_granted != artifact.authority.publication_authorized
            or row.delivery_authority_granted != artifact.authority.delivery_authorized
            or row.dispatch_authority_granted != artifact.authority.dispatch_authorized
            or row.execution_authority_granted != artifact.authority.execution_authorized
            or row.canonical_digest != artifact.canonical_digest
            or row.canonical_bytes != artifact.canonical_bytes
            or row.payload != cls._event_byte_artifact_payload(artifact)
        ):
            cls._event_byte_artifact_contract_violation()
        return artifact

    @classmethod
    def _event_byte_artifact_model(
        cls, artifact: WorkflowEventByteArtifact
    ) -> WorkflowEventByteArtifactModel:
        return WorkflowEventByteArtifactModel(
            artifact_id=artifact.artifact_id,
            admission_id=artifact.admission_id,
            admission_digest=artifact.admission_digest,
            event_id=artifact.event_id,
            event_digest=artifact.event_digest,
            event_type=artifact.event_type,
            event_version=artifact.event_version,
            schema_uri=artifact.schema_uri,
            data_classification=artifact.data_classification,
            outbox_entry_id=artifact.outbox_entry_id,
            outbox_entry_digest=artifact.outbox_entry_digest,
            dispatch_intent_id=artifact.dispatch_intent_id,
            dispatch_intent_digest=artifact.dispatch_intent_digest,
            plan_id=artifact.plan_id,
            plan_digest=artifact.plan_digest,
            run_id=artifact.run_id,
            run_digest=artifact.run_digest,
            step_run_id=artifact.step_run_id,
            step_run_digest=artifact.step_run_digest,
            step_id=artifact.step_id,
            attempt_id=artifact.attempt_id,
            attempt_digest=artifact.attempt_digest,
            attempt_number=artifact.attempt_number,
            organization_id=artifact.scope.organization_id,
            environment_id=artifact.scope.environment_id,
            site_id=artifact.scope.site_id,
            target_type=artifact.target_type,
            target_id=artifact.target_id,
            policy_id=artifact.policy_id,
            policy_version=artifact.policy_version,
            policy_digest=artifact.policy_digest,
            representation_name=artifact.representation_name,
            encoding=artifact.encoding,
            maximum_canonical_byte_count=artifact.maximum_canonical_byte_count,
            canonical_byte_count=artifact.canonical_byte_count,
            content_sha256=artifact.content_sha256,
            orchestration_lease_id=artifact.orchestration_lease_id,
            orchestration_lease_digest=artifact.orchestration_lease_digest,
            orchestration_fencing_token=artifact.orchestration_fencing_token,
            publication_lease_id=artifact.publication_lease_id,
            publication_lease_digest=artifact.publication_lease_digest,
            publication_fencing_token=artifact.publication_fencing_token,
            publisher_subject_id=artifact.publisher_subject_id,
            materialized_at=artifact.materialized_at,
            state=artifact.state.value,
            publication_authority_granted=artifact.authority.publication_authorized,
            delivery_authority_granted=artifact.authority.delivery_authorized,
            dispatch_authority_granted=artifact.authority.dispatch_authorized,
            execution_authority_granted=artifact.authority.execution_authorized,
            canonical_digest=artifact.canonical_digest,
            canonical_bytes=artifact.canonical_bytes,
            payload=cls._event_byte_artifact_payload(artifact),
        )

    @classmethod
    def _event_byte_artifact_claim_model(
        cls, request: WorkflowEventByteArtifactRequest
    ) -> WorkflowEventByteArtifactClaimModel:
        artifact = request.candidate
        scope_id = cls._event_byte_artifact_idempotency_scope(
            artifact.scope, artifact.publisher_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_artifact": cls._event_byte_artifact_payload(artifact),
            "result_digest": artifact.canonical_digest,
        }
        digest = canonical_digest(payload)
        return WorkflowEventByteArtifactClaimModel(
            claim_id=f"workflow_event_byte_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=artifact.canonical_digest,
            artifact_id=artifact.artifact_id,
            admission_id=artifact.admission_id,
            event_id=artifact.event_id,
            outbox_entry_id=artifact.outbox_entry_id,
            plan_id=artifact.plan_id,
            organization_id=artifact.scope.organization_id,
            environment_id=artifact.scope.environment_id,
            site_id=artifact.scope.site_id,
            publisher_subject_id=artifact.publisher_subject_id,
            created_at=request.requested_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _event_byte_artifact_evidence_matches(
        cls,
        *,
        plan_row: WorkflowRunPlanModel | None,
        outbox_row: WorkflowDispatchOutboxEntryModel | None,
        orchestration_lease_row: WorkflowOrchestrationLeaseModel | None,
        publication_lease_row: WorkflowOutboxPublicationLeaseModel | None,
        envelope_row: WorkflowDispatchEventEnvelopeModel | None,
        admission_row: WorkflowEventTransportAdmissionModel | None,
        request: WorkflowEventByteArtifactRequest,
    ) -> bool:
        if any(
            row is None
            for row in (
                plan_row,
                outbox_row,
                orchestration_lease_row,
                publication_lease_row,
                envelope_row,
                admission_row,
            )
        ):
            return False
        assert plan_row is not None
        assert outbox_row is not None
        assert orchestration_lease_row is not None
        assert publication_lease_row is not None
        assert envelope_row is not None
        assert admission_row is not None
        try:
            envelope = cls._dispatch_event_envelope_from_row(envelope_row)
            admission = cls._event_transport_admission_from_row(admission_row)
        except (WorkflowDispatchEventEnvelopeError, WorkflowEventTransportAdmissionError) as exc:
            raise WorkflowEventByteArtifactError(
                "workflow_event_byte_artifact_repository_contract_violation",
                "Workflow evidence is inconsistent during byte materialization.",
            ) from exc
        transport_request = WorkflowEventTransportAdmissionRequest(
            expected_plan_digest=request.expected_plan_digest,
            expected_outbox_entry_digest=request.expected_outbox_entry_digest,
            expected_event_id=request.expected_event_id,
            expected_event_digest=request.expected_event_digest,
            expected_policy_digest=request.expected_policy_digest,
            expected_orchestration_lease_id=request.expected_orchestration_lease_id,
            expected_orchestration_lease_digest=request.expected_orchestration_lease_digest,
            expected_orchestration_fencing_token=request.expected_orchestration_fencing_token,
            expected_publication_lease_id=request.expected_publication_lease_id,
            expected_publication_lease_digest=request.expected_publication_lease_digest,
            expected_publication_fencing_token=request.expected_publication_fencing_token,
            publisher_subject_id=request.publisher_subject_id,
            requested_at=request.requested_at,
            candidate=admission,
            idempotency_key="byte-artifact-evidence-validation",
            request_fingerprint="0" * 64,
        )
        if not cls._event_transport_admission_evidence_matches(
            plan_row=plan_row,
            outbox_row=outbox_row,
            orchestration_lease_row=orchestration_lease_row,
            publication_lease_row=publication_lease_row,
            envelope_row=envelope_row,
            request=transport_request,
        ):
            return False
        candidate = request.candidate
        shared_fields = (
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
            "canonical_byte_count",
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
        return bool(
            admission.admission_id == request.expected_admission_id == candidate.admission_id
            and admission.canonical_digest
            == request.expected_admission_digest
            == candidate.admission_digest
            and all(
                getattr(admission, field) == getattr(candidate, field) for field in shared_fields
            )
            and candidate.canonical_bytes == canonical_json_bytes(envelope.canonical_value())
            and candidate.state is WorkflowEventByteArtifactState.MATERIALIZED
            and not any(admission.authority.canonical_value().values())
            and not any(candidate.authority.canonical_value().values())
            and not candidate.grants_publication_authority
            and not candidate.grants_delivery_authority
            and not candidate.grants_dispatch_authority
            and not candidate.grants_execution_authority
        )

    @staticmethod
    def _event_byte_artifact_idempotency_scope(
        scope: WorkflowScope, publisher_subject_id: str
    ) -> str:
        return canonical_digest(
            {"publisher_subject_id": publisher_subject_id, "scope": scope.canonical_value()}
        )

    @staticmethod
    def _event_byte_artifact_payload(artifact: WorkflowEventByteArtifact) -> dict[str, Any]:
        return cast(dict[str, Any], artifact.canonical_value())

    @staticmethod
    def _event_byte_artifact_to_domain(
        raw: dict[str, Any], canonical_bytes_value: bytes
    ) -> WorkflowEventByteArtifact:
        values = dict(raw)
        values["canonical_bytes"] = bytes(canonical_bytes_value)
        values["scope"] = WorkflowScope(**cast(Any, values["scope"]))
        values["materialized_at"] = datetime.fromisoformat(str(values["materialized_at"]))
        values["state"] = WorkflowEventByteArtifactState(str(values["state"]))
        values["authority"] = WorkflowEventByteArtifactAuthority(**cast(Any, values["authority"]))
        return WorkflowEventByteArtifact(**cast(Any, values))

    @staticmethod
    def _validate_event_byte_artifact_request(
        request: WorkflowEventByteArtifactRequest,
    ) -> None:
        candidate = request.candidate
        if (
            candidate.state is not WorkflowEventByteArtifactState.MATERIALIZED
            or candidate.attempt_number != 1
            or candidate.publisher_subject_id != request.publisher_subject_id
            or candidate.grants_publication_authority
            or candidate.grants_delivery_authority
            or candidate.grants_dispatch_authority
            or candidate.grants_execution_authority
        ):
            raise ValueError("workflow event byte artifact payload is unsafe")
        if not request.idempotency_key or len(request.idempotency_key) > 128:
            raise ValueError("workflow event byte artifact idempotency key is invalid")
        if len(request.request_fingerprint) != 64:
            raise ValueError("workflow event byte artifact request fingerprint is invalid")
        if request.requested_at.tzinfo is None:
            raise ValueError("workflow event byte artifact time must be aware")

    @staticmethod
    def _event_byte_artifact_contract_violation() -> NoReturn:
        raise WorkflowEventByteArtifactError(
            "workflow_event_byte_artifact_repository_contract_violation",
            "The workflow event byte artifact does not match its durable evidence.",
        )

    async def _event_logical_channel_binding_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowEventLogicalChannelBindingRequest,
    ) -> WorkflowEventLogicalChannelBindingResult | None:
        candidate = request.candidate
        claim = await self._load_event_logical_channel_binding_claim(
            session,
            scope=candidate.scope,
            publisher_subject_id=candidate.publisher_subject_id,
            idempotency_key=request.idempotency_key,
        )
        if claim is None:
            return None
        binding_row = await session.get(WorkflowEventLogicalChannelBindingModel, claim.binding_id)
        record = self._event_logical_channel_binding_record_from_claim(claim, binding_row)
        status = (
            WorkflowEventLogicalChannelBindingStatus.REPLAY
            if record.request_fingerprint == request.request_fingerprint
            else WorkflowEventLogicalChannelBindingStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowEventLogicalChannelBindingResult(status, record.binding)

    @classmethod
    async def _load_event_logical_channel_binding_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventLogicalChannelBindingClaimModel | None:
        scope_id = cls._event_logical_channel_binding_idempotency_scope(scope, publisher_subject_id)
        return cast(
            WorkflowEventLogicalChannelBindingClaimModel | None,
            await session.scalar(
                select(WorkflowEventLogicalChannelBindingClaimModel).where(
                    WorkflowEventLogicalChannelBindingClaimModel.idempotency_scope_id == scope_id,
                    WorkflowEventLogicalChannelBindingClaimModel.idempotency_key == idempotency_key,
                    WorkflowEventLogicalChannelBindingClaimModel.organization_id
                    == scope.organization_id,
                    WorkflowEventLogicalChannelBindingClaimModel.environment_id
                    == scope.environment_id,
                    WorkflowEventLogicalChannelBindingClaimModel.site_id == scope.site_id,
                    WorkflowEventLogicalChannelBindingClaimModel.publisher_subject_id
                    == publisher_subject_id,
                )
            ),
        )

    @classmethod
    def _event_logical_channel_binding_record_from_claim(
        cls,
        claim: WorkflowEventLogicalChannelBindingClaimModel,
        binding_row: WorkflowEventLogicalChannelBindingModel | None,
    ) -> WorkflowEventLogicalChannelBindingIdempotencyRecord:
        if binding_row is None:
            cls._event_logical_channel_binding_contract_violation()
        assert binding_row is not None
        binding = cls._event_logical_channel_binding_from_row(binding_row)
        scope_id = cls._event_logical_channel_binding_idempotency_scope(
            binding.scope, binding.publisher_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_binding": cls._event_logical_channel_binding_payload(binding),
            "result_digest": binding.canonical_digest,
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != binding.canonical_digest
            or claim.binding_id != binding.binding_id
            or claim.artifact_id != binding.artifact_id
            or claim.admission_id != binding.admission_id
            or claim.event_id != binding.event_id
            or claim.outbox_entry_id != binding.outbox_entry_id
            or claim.plan_id != binding.plan_id
            or claim.organization_id != binding.scope.organization_id
            or claim.environment_id != binding.scope.environment_id
            or claim.site_id != binding.scope.site_id
            or claim.publisher_subject_id != binding.publisher_subject_id
            or claim.created_at.tzinfo is None
            or claim.created_at != binding.bound_at
            or claim.payload != payload
            or claim.canonical_digest != canonical_digest(payload)
        ):
            cls._event_logical_channel_binding_contract_violation()
        return WorkflowEventLogicalChannelBindingIdempotencyRecord(
            request_fingerprint=claim.request_fingerprint,
            binding=binding,
        )

    @classmethod
    def _event_logical_channel_binding_from_row(
        cls, row: WorkflowEventLogicalChannelBindingModel
    ) -> WorkflowEventLogicalChannelBinding:
        try:
            binding = cls._event_logical_channel_binding_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowEventLogicalChannelBindingError(
                "workflow_event_logical_channel_binding_repository_contract_violation",
                "The logical-channel repository contains an invalid binding.",
            ) from exc
        if (
            row.binding_id != binding.binding_id
            or row.artifact_id != binding.artifact_id
            or row.artifact_digest != binding.artifact_digest
            or row.content_sha256 != binding.content_sha256
            or row.canonical_byte_count != binding.canonical_byte_count
            or row.admission_id != binding.admission_id
            or row.admission_digest != binding.admission_digest
            or row.event_id != binding.event_id
            or row.event_digest != binding.event_digest
            or row.event_type != binding.event_type
            or row.event_version != binding.event_version
            or row.schema_uri != binding.schema_uri
            or row.outbox_entry_id != binding.outbox_entry_id
            or row.outbox_entry_digest != binding.outbox_entry_digest
            or row.dispatch_intent_id != binding.dispatch_intent_id
            or row.dispatch_intent_digest != binding.dispatch_intent_digest
            or row.plan_id != binding.plan_id
            or row.plan_digest != binding.plan_digest
            or row.run_id != binding.run_id
            or row.run_digest != binding.run_digest
            or row.step_run_id != binding.step_run_id
            or row.step_run_digest != binding.step_run_digest
            or row.step_id != binding.step_id
            or row.attempt_id != binding.attempt_id
            or row.attempt_digest != binding.attempt_digest
            or row.attempt_number != binding.attempt_number
            or row.organization_id != binding.scope.organization_id
            or row.environment_id != binding.scope.environment_id
            or row.site_id != binding.scope.site_id
            or row.target_type != binding.target_type
            or row.target_id != binding.target_id
            or row.policy_id != binding.policy_id
            or row.policy_version != binding.policy_version
            or row.policy_digest != binding.policy_digest
            or row.logical_channel_id != binding.logical_channel_id
            or row.logical_channel_version != binding.logical_channel_version
            or row.data_classification != binding.data_classification
            or row.representation_name != binding.representation_name
            or row.encoding != binding.encoding
            or row.delivery_semantics != binding.delivery_semantics
            or row.durability_required != binding.durability_required
            or row.ordering_key_kind != binding.ordering_key_kind
            or row.ordering_key_value != binding.ordering_key_value
            or row.retention_class != binding.retention_class
            or row.maximum_canonical_byte_count != binding.maximum_canonical_byte_count
            or row.orchestration_lease_id != binding.orchestration_lease_id
            or row.orchestration_lease_digest != binding.orchestration_lease_digest
            or row.orchestration_fencing_token != binding.orchestration_fencing_token
            or row.publication_lease_id != binding.publication_lease_id
            or row.publication_lease_digest != binding.publication_lease_digest
            or row.publication_fencing_token != binding.publication_fencing_token
            or row.publisher_subject_id != binding.publisher_subject_id
            or row.bound_at != binding.bound_at
            or row.state != binding.state.value
            or row.publication_authority_granted != binding.authority.publication_authorized
            or row.delivery_authority_granted != binding.authority.delivery_authorized
            or row.dispatch_authority_granted != binding.authority.dispatch_authorized
            or row.execution_authority_granted != binding.authority.execution_authorized
            or row.canonical_digest != binding.canonical_digest
            or row.payload != cls._event_logical_channel_binding_payload(binding)
        ):
            cls._event_logical_channel_binding_contract_violation()
        return binding

    @classmethod
    def _event_logical_channel_binding_model(
        cls, binding: WorkflowEventLogicalChannelBinding
    ) -> WorkflowEventLogicalChannelBindingModel:
        return WorkflowEventLogicalChannelBindingModel(
            binding_id=binding.binding_id,
            artifact_id=binding.artifact_id,
            artifact_digest=binding.artifact_digest,
            content_sha256=binding.content_sha256,
            canonical_byte_count=binding.canonical_byte_count,
            admission_id=binding.admission_id,
            admission_digest=binding.admission_digest,
            event_id=binding.event_id,
            event_digest=binding.event_digest,
            event_type=binding.event_type,
            event_version=binding.event_version,
            schema_uri=binding.schema_uri,
            outbox_entry_id=binding.outbox_entry_id,
            outbox_entry_digest=binding.outbox_entry_digest,
            dispatch_intent_id=binding.dispatch_intent_id,
            dispatch_intent_digest=binding.dispatch_intent_digest,
            plan_id=binding.plan_id,
            plan_digest=binding.plan_digest,
            run_id=binding.run_id,
            run_digest=binding.run_digest,
            step_run_id=binding.step_run_id,
            step_run_digest=binding.step_run_digest,
            step_id=binding.step_id,
            attempt_id=binding.attempt_id,
            attempt_digest=binding.attempt_digest,
            attempt_number=binding.attempt_number,
            organization_id=binding.scope.organization_id,
            environment_id=binding.scope.environment_id,
            site_id=binding.scope.site_id,
            target_type=binding.target_type,
            target_id=binding.target_id,
            policy_id=binding.policy_id,
            policy_version=binding.policy_version,
            policy_digest=binding.policy_digest,
            logical_channel_id=binding.logical_channel_id,
            logical_channel_version=binding.logical_channel_version,
            data_classification=binding.data_classification,
            representation_name=binding.representation_name,
            encoding=binding.encoding,
            delivery_semantics=binding.delivery_semantics,
            durability_required=binding.durability_required,
            ordering_key_kind=binding.ordering_key_kind,
            ordering_key_value=binding.ordering_key_value,
            retention_class=binding.retention_class,
            maximum_canonical_byte_count=binding.maximum_canonical_byte_count,
            orchestration_lease_id=binding.orchestration_lease_id,
            orchestration_lease_digest=binding.orchestration_lease_digest,
            orchestration_fencing_token=binding.orchestration_fencing_token,
            publication_lease_id=binding.publication_lease_id,
            publication_lease_digest=binding.publication_lease_digest,
            publication_fencing_token=binding.publication_fencing_token,
            publisher_subject_id=binding.publisher_subject_id,
            bound_at=binding.bound_at,
            state=binding.state.value,
            publication_authority_granted=binding.authority.publication_authorized,
            delivery_authority_granted=binding.authority.delivery_authorized,
            dispatch_authority_granted=binding.authority.dispatch_authorized,
            execution_authority_granted=binding.authority.execution_authorized,
            canonical_digest=binding.canonical_digest,
            payload=cls._event_logical_channel_binding_payload(binding),
        )

    @classmethod
    def _event_logical_channel_binding_claim_model(
        cls, request: WorkflowEventLogicalChannelBindingRequest
    ) -> WorkflowEventLogicalChannelBindingClaimModel:
        binding = request.candidate
        scope_id = cls._event_logical_channel_binding_idempotency_scope(
            binding.scope, binding.publisher_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_binding": cls._event_logical_channel_binding_payload(binding),
            "result_digest": binding.canonical_digest,
        }
        digest = canonical_digest(payload)
        return WorkflowEventLogicalChannelBindingClaimModel(
            claim_id=f"workflow_event_channel_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=binding.canonical_digest,
            binding_id=binding.binding_id,
            artifact_id=binding.artifact_id,
            admission_id=binding.admission_id,
            event_id=binding.event_id,
            outbox_entry_id=binding.outbox_entry_id,
            plan_id=binding.plan_id,
            organization_id=binding.scope.organization_id,
            environment_id=binding.scope.environment_id,
            site_id=binding.scope.site_id,
            publisher_subject_id=binding.publisher_subject_id,
            created_at=request.requested_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _event_logical_channel_binding_evidence_matches(
        cls,
        *,
        plan_row: WorkflowRunPlanModel | None,
        outbox_row: WorkflowDispatchOutboxEntryModel | None,
        orchestration_lease_row: WorkflowOrchestrationLeaseModel | None,
        publication_lease_row: WorkflowOutboxPublicationLeaseModel | None,
        envelope_row: WorkflowDispatchEventEnvelopeModel | None,
        admission_row: WorkflowEventTransportAdmissionModel | None,
        artifact_row: WorkflowEventByteArtifactModel | None,
        request: WorkflowEventLogicalChannelBindingRequest,
    ) -> bool:
        if any(
            row is None
            for row in (
                plan_row,
                outbox_row,
                orchestration_lease_row,
                publication_lease_row,
                envelope_row,
                admission_row,
                artifact_row,
            )
        ):
            return False
        assert plan_row is not None
        assert outbox_row is not None
        assert orchestration_lease_row is not None
        assert publication_lease_row is not None
        assert envelope_row is not None
        assert admission_row is not None
        assert artifact_row is not None
        try:
            admission = cls._event_transport_admission_from_row(admission_row)
            artifact = cls._event_byte_artifact_from_row(artifact_row)
        except (WorkflowEventTransportAdmissionError, WorkflowEventByteArtifactError) as exc:
            raise WorkflowEventLogicalChannelBindingError(
                "workflow_event_logical_channel_binding_repository_contract_violation",
                "Workflow evidence is inconsistent during logical-channel binding.",
            ) from exc
        artifact_request = WorkflowEventByteArtifactRequest(
            expected_plan_digest=request.expected_plan_digest,
            expected_outbox_entry_digest=request.expected_outbox_entry_digest,
            expected_event_id=request.expected_event_id,
            expected_event_digest=request.expected_event_digest,
            expected_admission_id=request.expected_admission_id,
            expected_admission_digest=request.expected_admission_digest,
            expected_policy_digest=artifact.policy_digest,
            expected_orchestration_lease_id=request.expected_orchestration_lease_id,
            expected_orchestration_lease_digest=request.expected_orchestration_lease_digest,
            expected_orchestration_fencing_token=request.expected_orchestration_fencing_token,
            expected_publication_lease_id=request.expected_publication_lease_id,
            expected_publication_lease_digest=request.expected_publication_lease_digest,
            expected_publication_fencing_token=request.expected_publication_fencing_token,
            publisher_subject_id=request.publisher_subject_id,
            requested_at=request.requested_at,
            candidate=artifact,
            idempotency_key="logical-channel-evidence-validation",
            request_fingerprint="0" * 64,
        )
        if not cls._event_byte_artifact_evidence_matches(
            plan_row=plan_row,
            outbox_row=outbox_row,
            orchestration_lease_row=orchestration_lease_row,
            publication_lease_row=publication_lease_row,
            envelope_row=envelope_row,
            admission_row=admission_row,
            request=artifact_request,
        ):
            return False
        candidate = request.candidate
        policy = code_owned_workflow_event_logical_channel_policy()
        return bool(
            artifact.artifact_id == request.expected_artifact_id == candidate.artifact_id
            and artifact.canonical_digest
            == request.expected_artifact_digest
            == candidate.artifact_digest
            and artifact.content_sha256
            == request.expected_content_sha256
            == candidate.content_sha256
            and artifact.canonical_byte_count
            == request.expected_canonical_byte_count
            == candidate.canonical_byte_count
            and artifact.admission_id == candidate.admission_id == admission.admission_id
            and artifact.admission_digest
            == candidate.admission_digest
            == admission.canonical_digest
            and artifact.event_id == candidate.event_id
            and artifact.event_digest == candidate.event_digest
            and artifact.event_type == candidate.event_type
            and artifact.event_version == candidate.event_version
            and artifact.schema_uri == candidate.schema_uri
            and artifact.outbox_entry_id == candidate.outbox_entry_id
            and artifact.outbox_entry_digest == candidate.outbox_entry_digest
            and artifact.dispatch_intent_id == candidate.dispatch_intent_id
            and artifact.dispatch_intent_digest == candidate.dispatch_intent_digest
            and artifact.plan_id == candidate.plan_id
            and artifact.plan_digest == candidate.plan_digest
            and artifact.run_id == candidate.run_id
            and artifact.run_digest == candidate.run_digest
            and artifact.step_run_id == candidate.step_run_id
            and artifact.step_run_digest == candidate.step_run_digest
            and artifact.step_id == candidate.step_id
            and artifact.attempt_id == candidate.attempt_id
            and artifact.attempt_digest == candidate.attempt_digest
            and artifact.attempt_number == candidate.attempt_number == 1
            and artifact.scope == candidate.scope
            and artifact.target_id == candidate.target_id
            and artifact.target_type == candidate.target_type
            and artifact.data_classification == candidate.data_classification
            and artifact.representation_name == candidate.representation_name
            and artifact.encoding == candidate.encoding
            and artifact.maximum_canonical_byte_count
            == candidate.maximum_canonical_byte_count
            == policy.maximum_canonical_byte_count
            and artifact.orchestration_lease_id == candidate.orchestration_lease_id
            and artifact.orchestration_lease_digest == candidate.orchestration_lease_digest
            and artifact.orchestration_fencing_token == candidate.orchestration_fencing_token
            and artifact.publication_lease_id == candidate.publication_lease_id
            and artifact.publication_lease_digest == candidate.publication_lease_digest
            and artifact.publication_fencing_token == candidate.publication_fencing_token
            and artifact.publisher_subject_id
            == request.publisher_subject_id
            == candidate.publisher_subject_id
            and candidate.policy_id == policy.policy_id
            and candidate.policy_version == policy.policy_version
            and candidate.policy_digest == request.expected_policy_digest == policy.canonical_digest
            and candidate.logical_channel_id == policy.logical_channel_id
            and candidate.logical_channel_version == policy.logical_channel_version
            and candidate.event_type in policy.allowed_event_types
            and candidate.event_version in policy.allowed_event_versions
            and candidate.schema_uri in policy.allowed_schema_uris
            and candidate.data_classification in policy.allowed_data_classifications
            and candidate.representation_name == policy.representation_name
            and candidate.encoding == policy.encoding
            and candidate.delivery_semantics == policy.delivery_semantics
            and candidate.durability_required == policy.durability_required
            and candidate.ordering_key_kind == policy.ordering_key_kind
            and candidate.ordering_key_value == candidate.run_id
            and candidate.retention_class == policy.retention_class
            and candidate.state is WorkflowEventLogicalChannelBindingState.BOUND
            and not any(artifact.authority.canonical_value().values())
            and not any(candidate.authority.canonical_value().values())
            and not candidate.grants_publication_authority
            and not candidate.grants_delivery_authority
            and not candidate.grants_dispatch_authority
            and not candidate.grants_execution_authority
        )

    @staticmethod
    def _event_logical_channel_binding_idempotency_scope(
        scope: WorkflowScope, publisher_subject_id: str
    ) -> str:
        return canonical_digest(
            {"publisher_subject_id": publisher_subject_id, "scope": scope.canonical_value()}
        )

    @staticmethod
    def _event_logical_channel_binding_payload(
        binding: WorkflowEventLogicalChannelBinding,
    ) -> dict[str, Any]:
        return cast(dict[str, Any], binding.canonical_value())

    @staticmethod
    def _event_logical_channel_binding_to_domain(
        raw: dict[str, Any],
    ) -> WorkflowEventLogicalChannelBinding:
        values = dict(raw)
        values["scope"] = WorkflowScope(**cast(Any, values["scope"]))
        values["bound_at"] = datetime.fromisoformat(str(values["bound_at"]))
        values["state"] = WorkflowEventLogicalChannelBindingState(str(values["state"]))
        values["authority"] = WorkflowEventLogicalChannelBindingAuthority(
            **cast(Any, values["authority"])
        )
        return WorkflowEventLogicalChannelBinding(**cast(Any, values))

    @staticmethod
    def _validate_event_logical_channel_binding_request(
        request: WorkflowEventLogicalChannelBindingRequest,
    ) -> None:
        candidate = request.candidate
        if (
            candidate.state is not WorkflowEventLogicalChannelBindingState.BOUND
            or candidate.attempt_number != 1
            or candidate.publisher_subject_id != request.publisher_subject_id
            or candidate.bound_at != request.requested_at
            or candidate.grants_publication_authority
            or candidate.grants_delivery_authority
            or candidate.grants_dispatch_authority
            or candidate.grants_execution_authority
        ):
            raise ValueError("workflow event logical-channel binding payload is unsafe")
        if not request.idempotency_key or len(request.idempotency_key) > 128:
            raise ValueError("workflow event logical-channel binding idempotency key is invalid")
        if len(request.request_fingerprint) != 64:
            raise ValueError(
                "workflow event logical-channel binding request fingerprint is invalid"
            )
        if request.requested_at.tzinfo is None:
            raise ValueError("workflow event logical-channel binding time must be aware")

    @staticmethod
    def _event_logical_channel_binding_contract_violation() -> NoReturn:
        raise WorkflowEventLogicalChannelBindingError(
            "workflow_event_logical_channel_binding_repository_contract_violation",
            "The workflow event logical-channel binding does not match its durable evidence.",
        )

    async def _transport_profile_snapshot_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowTransportProfileSnapshotRequest,
    ) -> WorkflowTransportProfileSnapshotResult | None:
        candidate = request.candidate
        claim = await self._load_transport_profile_snapshot_claim(
            session,
            scope=candidate.scope,
            snapshotter_subject_id=candidate.snapshotter_subject_id,
            idempotency_key=request.idempotency_key,
        )
        if claim is None:
            return None
        snapshot_row = await session.get(
            EventPhysicalTransportProfileSnapshotModel, claim.snapshot_id
        )
        record = self._transport_profile_snapshot_record_from_claim(claim, snapshot_row)
        status = (
            WorkflowTransportProfileSnapshotStatus.REPLAY
            if record.request_fingerprint == request.request_fingerprint
            else WorkflowTransportProfileSnapshotStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowTransportProfileSnapshotResult(status, record.snapshot)

    @classmethod
    async def _load_transport_profile_snapshot_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        snapshotter_subject_id: str,
        idempotency_key: str,
    ) -> EventPhysicalTransportProfileSnapshotClaimModel | None:
        scope_id = cls._transport_profile_snapshot_idempotency_scope(scope, snapshotter_subject_id)
        return cast(
            EventPhysicalTransportProfileSnapshotClaimModel | None,
            await session.scalar(
                select(EventPhysicalTransportProfileSnapshotClaimModel).where(
                    EventPhysicalTransportProfileSnapshotClaimModel.idempotency_scope_id
                    == scope_id,
                    EventPhysicalTransportProfileSnapshotClaimModel.idempotency_key
                    == idempotency_key,
                    EventPhysicalTransportProfileSnapshotClaimModel.organization_id
                    == scope.organization_id,
                    EventPhysicalTransportProfileSnapshotClaimModel.environment_id
                    == scope.environment_id,
                    EventPhysicalTransportProfileSnapshotClaimModel.site_id == scope.site_id,
                    EventPhysicalTransportProfileSnapshotClaimModel.snapshotter_subject_id
                    == snapshotter_subject_id,
                )
            ),
        )

    @classmethod
    def _transport_profile_snapshot_record_from_claim(
        cls,
        claim: EventPhysicalTransportProfileSnapshotClaimModel,
        snapshot_row: EventPhysicalTransportProfileSnapshotModel | None,
    ) -> WorkflowTransportProfileSnapshotIdempotencyRecord:
        if snapshot_row is None:
            cls._transport_profile_snapshot_contract_violation()
        assert snapshot_row is not None
        snapshot = cls._transport_profile_snapshot_from_row(snapshot_row)
        scope_id = cls._transport_profile_snapshot_idempotency_scope(
            snapshot.scope, snapshot.snapshotter_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_digest": snapshot.canonical_digest,
            "result_snapshot": cls._transport_profile_snapshot_payload(snapshot),
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != snapshot.canonical_digest
            or claim.snapshot_id != snapshot.snapshot_id
            or claim.transport_profile_id != snapshot.transport_profile_id
            or claim.transport_profile_revision != snapshot.transport_profile_revision
            or claim.source_profile_digest != snapshot.source_profile_digest
            or claim.organization_id != snapshot.scope.organization_id
            or claim.environment_id != snapshot.scope.environment_id
            or claim.site_id != snapshot.scope.site_id
            or claim.snapshotter_subject_id != snapshot.snapshotter_subject_id
            or claim.created_at.tzinfo is None
            or claim.created_at != snapshot.captured_at
            or claim.payload != payload
            or claim.canonical_digest != canonical_digest(payload)
        ):
            cls._transport_profile_snapshot_contract_violation()
        return WorkflowTransportProfileSnapshotIdempotencyRecord(
            request_fingerprint=claim.request_fingerprint,
            snapshot=snapshot,
        )

    @classmethod
    def _transport_profile_snapshot_from_row(
        cls, row: EventPhysicalTransportProfileSnapshotModel
    ) -> EventPhysicalTransportProfileSnapshot:
        try:
            snapshot = cls._transport_profile_snapshot_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowTransportProfileSnapshotError(
                "workflow_transport_profile_snapshot_repository_contract_violation",
                "The transport profile snapshot repository contains an invalid record.",
            ) from exc
        if (
            row.snapshot_id != snapshot.snapshot_id
            or row.transport_profile_id != snapshot.transport_profile_id
            or row.transport_profile_revision != snapshot.transport_profile_revision
            or row.source_profile_digest != snapshot.source_profile_digest
            or row.deployment_release_id != snapshot.deployment_release_id
            or row.deployment_profile != snapshot.deployment_profile
            or row.organization_id != snapshot.scope.organization_id
            or row.environment_id != snapshot.scope.environment_id
            or row.site_id != snapshot.scope.site_id
            or row.transport_resource_id != snapshot.transport_resource_id
            or row.transport_resource_digest != snapshot.transport_resource_digest
            or row.transport_implementation_id != snapshot.transport_implementation_id
            or row.transport_implementation_version != snapshot.transport_implementation_version
            or row.adapter_contract_id != snapshot.adapter_contract_id
            or row.adapter_contract_version != snapshot.adapter_contract_version
            or row.adapter_contract_digest != snapshot.adapter_contract_digest
            or row.supported_event_contracts != list(snapshot.supported_event_contracts)
            or row.supported_classifications != list(snapshot.supported_classifications)
            or row.supported_representations != list(snapshot.supported_representations)
            or row.supported_encodings != list(snapshot.supported_encodings)
            or row.supported_delivery_semantics != list(snapshot.supported_delivery_semantics)
            or row.durable_delivery_supported != snapshot.durable_delivery_supported
            or row.supported_ordering_key_kinds != list(snapshot.supported_ordering_key_kinds)
            or row.supported_retention_classes != list(snapshot.supported_retention_classes)
            or row.maximum_message_byte_count != snapshot.maximum_message_byte_count
            or row.transport_encryption_required != snapshot.transport_encryption_required
            or row.restricted_network_supported != snapshot.restricted_network_supported
            or row.snapshotter_subject_id != snapshot.snapshotter_subject_id
            or row.captured_at != snapshot.captured_at
            or row.state != snapshot.state.value
            or row.route_selection_authority_granted
            != snapshot.authority.route_selection_authorized
            or row.publication_authority_granted != snapshot.authority.publication_authorized
            or row.delivery_authority_granted != snapshot.authority.delivery_authorized
            or row.dispatch_authority_granted != snapshot.authority.dispatch_authorized
            or row.execution_authority_granted != snapshot.authority.execution_authorized
            or row.canonical_digest != snapshot.canonical_digest
            or row.payload != cls._transport_profile_snapshot_payload(snapshot)
        ):
            cls._transport_profile_snapshot_contract_violation()
        return snapshot

    @classmethod
    def _transport_profile_snapshot_model(
        cls, snapshot: EventPhysicalTransportProfileSnapshot
    ) -> EventPhysicalTransportProfileSnapshotModel:
        return EventPhysicalTransportProfileSnapshotModel(
            snapshot_id=snapshot.snapshot_id,
            transport_profile_id=snapshot.transport_profile_id,
            transport_profile_revision=snapshot.transport_profile_revision,
            source_profile_digest=snapshot.source_profile_digest,
            deployment_release_id=snapshot.deployment_release_id,
            deployment_profile=snapshot.deployment_profile,
            organization_id=snapshot.scope.organization_id,
            environment_id=snapshot.scope.environment_id,
            site_id=snapshot.scope.site_id,
            transport_resource_id=snapshot.transport_resource_id,
            transport_resource_digest=snapshot.transport_resource_digest,
            transport_implementation_id=snapshot.transport_implementation_id,
            transport_implementation_version=snapshot.transport_implementation_version,
            adapter_contract_id=snapshot.adapter_contract_id,
            adapter_contract_version=snapshot.adapter_contract_version,
            adapter_contract_digest=snapshot.adapter_contract_digest,
            supported_event_contracts=list(snapshot.supported_event_contracts),
            supported_classifications=list(snapshot.supported_classifications),
            supported_representations=list(snapshot.supported_representations),
            supported_encodings=list(snapshot.supported_encodings),
            supported_delivery_semantics=list(snapshot.supported_delivery_semantics),
            durable_delivery_supported=snapshot.durable_delivery_supported,
            supported_ordering_key_kinds=list(snapshot.supported_ordering_key_kinds),
            supported_retention_classes=list(snapshot.supported_retention_classes),
            maximum_message_byte_count=snapshot.maximum_message_byte_count,
            transport_encryption_required=snapshot.transport_encryption_required,
            restricted_network_supported=snapshot.restricted_network_supported,
            snapshotter_subject_id=snapshot.snapshotter_subject_id,
            captured_at=snapshot.captured_at,
            state=snapshot.state.value,
            route_selection_authority_granted=(snapshot.authority.route_selection_authorized),
            publication_authority_granted=snapshot.authority.publication_authorized,
            delivery_authority_granted=snapshot.authority.delivery_authorized,
            dispatch_authority_granted=snapshot.authority.dispatch_authorized,
            execution_authority_granted=snapshot.authority.execution_authorized,
            canonical_digest=snapshot.canonical_digest,
            payload=cls._transport_profile_snapshot_payload(snapshot),
        )

    @classmethod
    def _transport_profile_snapshot_claim_model(
        cls, request: WorkflowTransportProfileSnapshotRequest
    ) -> EventPhysicalTransportProfileSnapshotClaimModel:
        snapshot = request.candidate
        scope_id = cls._transport_profile_snapshot_idempotency_scope(
            snapshot.scope, snapshot.snapshotter_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_digest": snapshot.canonical_digest,
            "result_snapshot": cls._transport_profile_snapshot_payload(snapshot),
        }
        digest = canonical_digest(payload)
        return EventPhysicalTransportProfileSnapshotClaimModel(
            claim_id=f"event_transport_profile_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=snapshot.canonical_digest,
            snapshot_id=snapshot.snapshot_id,
            transport_profile_id=snapshot.transport_profile_id,
            transport_profile_revision=snapshot.transport_profile_revision,
            source_profile_digest=snapshot.source_profile_digest,
            organization_id=snapshot.scope.organization_id,
            environment_id=snapshot.scope.environment_id,
            site_id=snapshot.scope.site_id,
            snapshotter_subject_id=snapshot.snapshotter_subject_id,
            created_at=request.requested_at,
            canonical_digest=digest,
            payload=payload,
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
    def _transport_profile_snapshot_idempotency_scope(
        scope: WorkflowScope, snapshotter_subject_id: str
    ) -> str:
        return canonical_digest(
            {
                "scope": scope.canonical_value(),
                "snapshotter_subject_id": snapshotter_subject_id,
            }
        )

    @staticmethod
    def _transport_profile_snapshot_payload(
        snapshot: EventPhysicalTransportProfileSnapshot,
    ) -> dict[str, Any]:
        payload = cast(dict[str, Any], snapshot.canonical_value())
        for field in (
            "supported_event_contracts",
            "supported_classifications",
            "supported_representations",
            "supported_encodings",
            "supported_delivery_semantics",
            "supported_ordering_key_kinds",
            "supported_retention_classes",
        ):
            payload[field] = list(cast(tuple[str, ...], payload[field]))
        return payload

    @staticmethod
    def _transport_profile_snapshot_to_domain(
        raw: dict[str, Any],
    ) -> EventPhysicalTransportProfileSnapshot:
        values = dict(raw)
        values["scope"] = WorkflowScope(**cast(Any, values["scope"]))
        values["captured_at"] = datetime.fromisoformat(str(values["captured_at"]))
        values["state"] = EventPhysicalTransportProfileSnapshotState(str(values["state"]))
        values["authority"] = EventPhysicalTransportProfileSnapshotAuthority(
            **cast(Any, values["authority"])
        )
        for field in (
            "supported_event_contracts",
            "supported_classifications",
            "supported_representations",
            "supported_encodings",
            "supported_delivery_semantics",
            "supported_ordering_key_kinds",
            "supported_retention_classes",
        ):
            values[field] = tuple(cast(list[str] | tuple[str, ...], values[field]))
        return EventPhysicalTransportProfileSnapshot(**cast(Any, values))

    @staticmethod
    def _validate_transport_profile_snapshot_request(
        request: WorkflowTransportProfileSnapshotRequest,
    ) -> None:
        candidate = request.candidate
        if not PostgreSQLWorkflowPlanRepository._transport_profile_snapshot_evidence_matches(
            request
        ):
            raise ValueError("event transport profile snapshot payload is unsafe")
        if not request.idempotency_key or len(request.idempotency_key) > 128:
            raise ValueError("event transport profile snapshot idempotency key is invalid")
        if len(request.request_fingerprint) != 64:
            raise ValueError("event transport profile snapshot request fingerprint is invalid")
        if request.requested_at.tzinfo is None or candidate.captured_at.tzinfo is None:
            raise ValueError("event transport profile snapshot time must be aware")

    @staticmethod
    def _transport_profile_snapshot_contract_violation() -> NoReturn:
        raise WorkflowTransportProfileSnapshotError(
            "workflow_transport_profile_snapshot_repository_contract_violation",
            "The event transport profile snapshot does not match its durable evidence.",
        )

    async def _transport_route_snapshot_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowTransportRouteSnapshotRequest,
    ) -> WorkflowTransportRouteSnapshotResult | None:
        candidate = request.candidate
        claim = await self._load_transport_route_snapshot_claim(
            session,
            scope=candidate.scope,
            snapshotter_subject_id=candidate.snapshotter_subject_id,
            idempotency_key=request.idempotency_key,
        )
        if claim is None:
            return None
        snapshot_row = await session.get(
            EventPhysicalTransportRouteSnapshotModel, claim.snapshot_id
        )
        record = self._transport_route_snapshot_record_from_claim(claim, snapshot_row)
        status = (
            WorkflowTransportRouteSnapshotStatus.REPLAY
            if record.request_fingerprint == request.request_fingerprint
            else WorkflowTransportRouteSnapshotStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowTransportRouteSnapshotResult(status, record.snapshot)

    @classmethod
    async def _load_transport_route_snapshot_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        snapshotter_subject_id: str,
        idempotency_key: str,
    ) -> EventPhysicalTransportRouteSnapshotClaimModel | None:
        scope_id = cls._transport_route_snapshot_idempotency_scope(scope, snapshotter_subject_id)
        return cast(
            EventPhysicalTransportRouteSnapshotClaimModel | None,
            await session.scalar(
                select(EventPhysicalTransportRouteSnapshotClaimModel).where(
                    EventPhysicalTransportRouteSnapshotClaimModel.idempotency_scope_id == scope_id,
                    EventPhysicalTransportRouteSnapshotClaimModel.idempotency_key
                    == idempotency_key,
                    EventPhysicalTransportRouteSnapshotClaimModel.organization_id
                    == scope.organization_id,
                    EventPhysicalTransportRouteSnapshotClaimModel.environment_id
                    == scope.environment_id,
                    EventPhysicalTransportRouteSnapshotClaimModel.site_id == scope.site_id,
                    EventPhysicalTransportRouteSnapshotClaimModel.snapshotter_subject_id
                    == snapshotter_subject_id,
                )
            ),
        )

    @classmethod
    def _transport_route_snapshot_record_from_claim(
        cls,
        claim: EventPhysicalTransportRouteSnapshotClaimModel,
        snapshot_row: EventPhysicalTransportRouteSnapshotModel | None,
    ) -> WorkflowTransportRouteSnapshotIdempotencyRecord:
        if snapshot_row is None:
            cls._transport_route_snapshot_contract_violation()
        snapshot = cls._transport_route_snapshot_from_row(snapshot_row)
        scope_id = cls._transport_route_snapshot_idempotency_scope(
            snapshot.scope, snapshot.snapshotter_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_digest": snapshot.canonical_digest,
            "result_snapshot": cls._transport_route_snapshot_payload(snapshot),
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != snapshot.canonical_digest
            or claim.snapshot_id != snapshot.snapshot_id
            or claim.route_id != snapshot.route_id
            or claim.route_revision != snapshot.route_revision
            or claim.source_route_digest != snapshot.source_route_digest
            or claim.organization_id != snapshot.scope.organization_id
            or claim.environment_id != snapshot.scope.environment_id
            or claim.site_id != snapshot.scope.site_id
            or claim.snapshotter_subject_id != snapshot.snapshotter_subject_id
            or claim.canonical_digest != canonical_digest(payload)
            or claim.payload != payload
        ):
            cls._transport_route_snapshot_contract_violation()
        return WorkflowTransportRouteSnapshotIdempotencyRecord(
            request_fingerprint=claim.request_fingerprint,
            snapshot=snapshot,
        )

    @classmethod
    def _transport_route_snapshot_from_row(
        cls, row: EventPhysicalTransportRouteSnapshotModel
    ) -> EventPhysicalTransportRouteSnapshot:
        try:
            snapshot = cls._transport_route_snapshot_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowTransportRouteSnapshotError(
                "workflow_transport_route_snapshot_repository_contract_violation",
                "The event transport route snapshot does not match its durable evidence.",
            ) from exc
        authority = snapshot.authority
        if (
            row.snapshot_id != snapshot.snapshot_id
            or row.route_id != snapshot.route_id
            or row.route_revision != snapshot.route_revision
            or row.route_set_id != snapshot.route_set_id
            or row.route_set_revision != snapshot.route_set_revision
            or row.selection_epoch_id != snapshot.selection_epoch_id
            or row.selection_epoch_revision != snapshot.selection_epoch_revision
            or row.source_route_digest != snapshot.source_route_digest
            or row.deployment_release_id != snapshot.deployment_release_id
            or row.deployment_profile != snapshot.deployment_profile
            or row.organization_id != snapshot.scope.organization_id
            or row.environment_id != snapshot.scope.environment_id
            or row.site_id != snapshot.scope.site_id
            or row.transport_profile_id != snapshot.transport_profile_id
            or row.transport_profile_revision != snapshot.transport_profile_revision
            or row.transport_resource_id != snapshot.transport_resource_id
            or row.transport_resource_digest != snapshot.transport_resource_digest
            or row.transport_implementation_id != snapshot.transport_implementation_id
            or row.transport_implementation_version != snapshot.transport_implementation_version
            or row.adapter_contract_id != snapshot.adapter_contract_id
            or row.adapter_contract_version != snapshot.adapter_contract_version
            or row.adapter_contract_digest != snapshot.adapter_contract_digest
            or row.route_kind != snapshot.route_kind
            or row.endpoint_set_id != snapshot.endpoint_set_id
            or row.endpoint_set_revision != snapshot.endpoint_set_revision
            or row.destination_id != snapshot.destination_id
            or row.destination_revision != snapshot.destination_revision
            or row.routing_contract_id != snapshot.routing_contract_id
            or row.routing_contract_revision != snapshot.routing_contract_revision
            or row.private_route_descriptor_commitment
            != snapshot.private_route_descriptor_commitment
            or row.transport_security_policy_id != snapshot.transport_security_policy_id
            or row.transport_security_policy_version != snapshot.transport_security_policy_version
            or row.transport_security_policy_digest != snapshot.transport_security_policy_digest
            or row.minimum_tls_version != snapshot.minimum_tls_version
            or row.server_authentication_required != snapshot.server_authentication_required
            or row.client_authentication_required != snapshot.client_authentication_required
            or row.plaintext_fallback_prohibited != snapshot.plaintext_fallback_prohibited
            or row.network_policy_id != snapshot.network_policy_id
            or row.network_policy_version != snapshot.network_policy_version
            or row.network_policy_digest != snapshot.network_policy_digest
            or row.source_zone_class != snapshot.source_zone_class
            or row.destination_zone_class != snapshot.destination_zone_class
            or row.restricted_network_enforced != snapshot.restricted_network_enforced
            or row.public_egress_prohibited != snapshot.public_egress_prohibited
            or row.proxy_mode != snapshot.proxy_mode
            or row.credential_requirement_profile_id != snapshot.credential_requirement_profile_id
            or row.credential_requirement_profile_version
            != snapshot.credential_requirement_profile_version
            or row.credential_requirement_profile_digest
            != snapshot.credential_requirement_profile_digest
            or row.authentication_mechanism_class != snapshot.authentication_mechanism_class
            or row.principal_class != snapshot.principal_class
            or row.snapshotter_subject_id != snapshot.snapshotter_subject_id
            or row.captured_at != snapshot.captured_at
            or row.state != snapshot.state.value
            or row.route_selection_authority_granted != authority.route_selection_authorized
            or row.route_binding_authority_granted != authority.route_binding_authorized
            or row.endpoint_resolution_authority_granted != authority.endpoint_resolution_authorized
            or row.credential_access_authority_granted != authority.credential_access_authorized
            or row.network_access_authority_granted != authority.network_access_authorized
            or row.readiness_probe_authority_granted != authority.readiness_probe_authorized
            or row.publication_authority_granted != authority.publication_authorized
            or row.delivery_authority_granted != authority.delivery_authorized
            or row.dispatch_authority_granted != authority.dispatch_authorized
            or row.execution_authority_granted != authority.execution_authorized
            or row.canonical_digest != snapshot.canonical_digest
            or row.payload != cls._transport_route_snapshot_payload(snapshot)
        ):
            cls._transport_route_snapshot_contract_violation()
        return snapshot

    @classmethod
    def _transport_route_snapshot_model(
        cls, snapshot: EventPhysicalTransportRouteSnapshot
    ) -> EventPhysicalTransportRouteSnapshotModel:
        authority = snapshot.authority
        return EventPhysicalTransportRouteSnapshotModel(
            snapshot_id=snapshot.snapshot_id,
            route_id=snapshot.route_id,
            route_revision=snapshot.route_revision,
            route_set_id=snapshot.route_set_id,
            route_set_revision=snapshot.route_set_revision,
            selection_epoch_id=snapshot.selection_epoch_id,
            selection_epoch_revision=snapshot.selection_epoch_revision,
            source_route_digest=snapshot.source_route_digest,
            deployment_release_id=snapshot.deployment_release_id,
            deployment_profile=snapshot.deployment_profile,
            organization_id=snapshot.scope.organization_id,
            environment_id=snapshot.scope.environment_id,
            site_id=snapshot.scope.site_id,
            transport_profile_id=snapshot.transport_profile_id,
            transport_profile_revision=snapshot.transport_profile_revision,
            transport_resource_id=snapshot.transport_resource_id,
            transport_resource_digest=snapshot.transport_resource_digest,
            transport_implementation_id=snapshot.transport_implementation_id,
            transport_implementation_version=snapshot.transport_implementation_version,
            adapter_contract_id=snapshot.adapter_contract_id,
            adapter_contract_version=snapshot.adapter_contract_version,
            adapter_contract_digest=snapshot.adapter_contract_digest,
            route_kind=snapshot.route_kind,
            endpoint_set_id=snapshot.endpoint_set_id,
            endpoint_set_revision=snapshot.endpoint_set_revision,
            destination_id=snapshot.destination_id,
            destination_revision=snapshot.destination_revision,
            routing_contract_id=snapshot.routing_contract_id,
            routing_contract_revision=snapshot.routing_contract_revision,
            private_route_descriptor_commitment=snapshot.private_route_descriptor_commitment,
            transport_security_policy_id=snapshot.transport_security_policy_id,
            transport_security_policy_version=snapshot.transport_security_policy_version,
            transport_security_policy_digest=snapshot.transport_security_policy_digest,
            minimum_tls_version=snapshot.minimum_tls_version,
            server_authentication_required=snapshot.server_authentication_required,
            client_authentication_required=snapshot.client_authentication_required,
            plaintext_fallback_prohibited=snapshot.plaintext_fallback_prohibited,
            network_policy_id=snapshot.network_policy_id,
            network_policy_version=snapshot.network_policy_version,
            network_policy_digest=snapshot.network_policy_digest,
            source_zone_class=snapshot.source_zone_class,
            destination_zone_class=snapshot.destination_zone_class,
            restricted_network_enforced=snapshot.restricted_network_enforced,
            public_egress_prohibited=snapshot.public_egress_prohibited,
            proxy_mode=snapshot.proxy_mode,
            credential_requirement_profile_id=snapshot.credential_requirement_profile_id,
            credential_requirement_profile_version=(
                snapshot.credential_requirement_profile_version
            ),
            credential_requirement_profile_digest=snapshot.credential_requirement_profile_digest,
            authentication_mechanism_class=snapshot.authentication_mechanism_class,
            principal_class=snapshot.principal_class,
            snapshotter_subject_id=snapshot.snapshotter_subject_id,
            captured_at=snapshot.captured_at,
            state=snapshot.state.value,
            route_selection_authority_granted=authority.route_selection_authorized,
            route_binding_authority_granted=authority.route_binding_authorized,
            endpoint_resolution_authority_granted=authority.endpoint_resolution_authorized,
            credential_access_authority_granted=authority.credential_access_authorized,
            network_access_authority_granted=authority.network_access_authorized,
            readiness_probe_authority_granted=authority.readiness_probe_authorized,
            publication_authority_granted=authority.publication_authorized,
            delivery_authority_granted=authority.delivery_authorized,
            dispatch_authority_granted=authority.dispatch_authorized,
            execution_authority_granted=authority.execution_authorized,
            canonical_digest=snapshot.canonical_digest,
            payload=cls._transport_route_snapshot_payload(snapshot),
        )

    @classmethod
    def _transport_route_snapshot_claim_model(
        cls, request: WorkflowTransportRouteSnapshotRequest
    ) -> EventPhysicalTransportRouteSnapshotClaimModel:
        snapshot = request.candidate
        scope_id = cls._transport_route_snapshot_idempotency_scope(
            snapshot.scope, snapshot.snapshotter_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_digest": snapshot.canonical_digest,
            "result_snapshot": cls._transport_route_snapshot_payload(snapshot),
        }
        digest = canonical_digest(payload)
        return EventPhysicalTransportRouteSnapshotClaimModel(
            claim_id=f"event_transport_route_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=snapshot.canonical_digest,
            snapshot_id=snapshot.snapshot_id,
            route_id=snapshot.route_id,
            route_revision=snapshot.route_revision,
            source_route_digest=snapshot.source_route_digest,
            organization_id=snapshot.scope.organization_id,
            environment_id=snapshot.scope.environment_id,
            site_id=snapshot.scope.site_id,
            snapshotter_subject_id=snapshot.snapshotter_subject_id,
            created_at=request.requested_at,
            canonical_digest=digest,
            payload=payload,
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
    def _transport_route_snapshot_idempotency_scope(
        scope: WorkflowScope, snapshotter_subject_id: str
    ) -> str:
        return canonical_digest(
            {
                "scope": scope.canonical_value(),
                "snapshotter_subject_id": snapshotter_subject_id,
            }
        )

    @staticmethod
    def _transport_route_snapshot_payload(
        snapshot: EventPhysicalTransportRouteSnapshot,
    ) -> dict[str, Any]:
        return cast(dict[str, Any], snapshot.canonical_value())

    @staticmethod
    def _transport_route_snapshot_to_domain(
        raw: dict[str, Any],
    ) -> EventPhysicalTransportRouteSnapshot:
        values = dict(raw)
        values["scope"] = WorkflowScope(**cast(Any, values["scope"]))
        values["captured_at"] = datetime.fromisoformat(str(values["captured_at"]))
        values["state"] = EventPhysicalTransportRouteSnapshotState(str(values["state"]))
        values["authority"] = EventPhysicalTransportRouteSnapshotAuthority(
            **cast(Any, values["authority"])
        )
        return EventPhysicalTransportRouteSnapshot(**cast(Any, values))

    @staticmethod
    def _validate_transport_route_snapshot_request(
        request: WorkflowTransportRouteSnapshotRequest,
    ) -> None:
        candidate = request.candidate
        if not PostgreSQLWorkflowPlanRepository._transport_route_snapshot_evidence_matches(request):
            raise ValueError("event transport route snapshot payload is unsafe")
        if not request.idempotency_key or len(request.idempotency_key) > 128:
            raise ValueError("event transport route snapshot idempotency key is invalid")
        if len(request.request_fingerprint) != 64:
            raise ValueError("event transport route snapshot request fingerprint is invalid")
        if request.requested_at.tzinfo is None or candidate.captured_at.tzinfo is None:
            raise ValueError("event transport route snapshot time must be aware")

    @staticmethod
    def _transport_route_snapshot_contract_violation() -> NoReturn:
        raise WorkflowTransportRouteSnapshotError(
            "workflow_transport_route_snapshot_repository_contract_violation",
            "The event transport route snapshot does not match its durable evidence.",
        )

    @classmethod
    def _credential_assignment_model(
        cls, assignment: DeploymentPhysicalTransportCredentialAssignment
    ) -> DeploymentEventTransportCredentialAssignmentModel:
        payload = cast(dict[str, Any], assignment.canonical_value())
        return DeploymentEventTransportCredentialAssignmentModel(
            assignment_id=assignment.assignment_id,
            assignment_revision=assignment.assignment_revision,
            source_assignment_digest=assignment.canonical_digest,
            organization_id=assignment.scope.organization_id,
            environment_id=assignment.scope.environment_id,
            site_id=assignment.scope.site_id,
            route_id=assignment.route_id,
            route_revision=assignment.route_revision,
            source_route_digest=assignment.source_route_digest,
            credential_requirement_profile_id=assignment.credential_requirement_profile_id,
            credential_requirement_profile_version=(
                assignment.credential_requirement_profile_version
            ),
            credential_requirement_profile_digest=(
                assignment.credential_requirement_profile_digest
            ),
            credential_profile_id=assignment.credential_profile_id,
            credential_profile_version=assignment.credential_profile_version,
            credential_profile_digest=assignment.credential_profile_digest,
            authentication_mechanism_class=assignment.authentication_mechanism_class,
            principal_class=assignment.principal_class,
            privilege_class=assignment.privilege_class,
            target_scope_commitment=assignment.target_scope_commitment,
            credential_generation=assignment.credential_generation,
            rotation_epoch=assignment.rotation_epoch,
            activated_at=assignment.activated_at,
            expires_at=assignment.expires_at,
            revoked=assignment.revoked,
            broker_policy_id=assignment.broker_policy_id,
            broker_policy_version=assignment.broker_policy_version,
            broker_policy_digest=assignment.broker_policy_digest,
            active=assignment.active,
            canonical_digest=assignment.canonical_digest,
            payload=payload,
        )

    @classmethod
    def _credential_assignment_from_row(
        cls, row: DeploymentEventTransportCredentialAssignmentModel
    ) -> DeploymentPhysicalTransportCredentialAssignment:
        try:
            assignment = cls._credential_assignment_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowTransportCredentialAssignmentSnapshotError(
                "workflow_transport_credential_assignment_registry_contract_violation",
                "Credential-assignment registry evidence is invalid.",
            ) from exc
        if (
            row.assignment_id != assignment.assignment_id
            or row.assignment_revision != assignment.assignment_revision
            or row.source_assignment_digest != assignment.canonical_digest
            or row.organization_id != assignment.scope.organization_id
            or row.environment_id != assignment.scope.environment_id
            or row.site_id != assignment.scope.site_id
            or row.route_id != assignment.route_id
            or row.route_revision != assignment.route_revision
            or row.source_route_digest != assignment.source_route_digest
            or row.credential_requirement_profile_id != assignment.credential_requirement_profile_id
            or row.credential_requirement_profile_version
            != assignment.credential_requirement_profile_version
            or row.credential_requirement_profile_digest
            != assignment.credential_requirement_profile_digest
            or row.credential_profile_id != assignment.credential_profile_id
            or row.credential_profile_version != assignment.credential_profile_version
            or row.credential_profile_digest != assignment.credential_profile_digest
            or row.authentication_mechanism_class != assignment.authentication_mechanism_class
            or row.principal_class != assignment.principal_class
            or row.privilege_class != assignment.privilege_class
            or row.target_scope_commitment != assignment.target_scope_commitment
            or row.credential_generation != assignment.credential_generation
            or row.rotation_epoch != assignment.rotation_epoch
            or row.activated_at != assignment.activated_at
            or row.expires_at != assignment.expires_at
            or row.revoked != assignment.revoked
            or row.active != assignment.active
            or row.broker_policy_id != assignment.broker_policy_id
            or row.broker_policy_version != assignment.broker_policy_version
            or row.broker_policy_digest != assignment.broker_policy_digest
            or row.canonical_digest != assignment.canonical_digest
            or row.payload != cast(dict[str, Any], assignment.canonical_value())
        ):
            cls._credential_assignment_contract_violation()
        return assignment

    @staticmethod
    def _credential_assignment_to_domain(
        raw: dict[str, Any],
    ) -> DeploymentPhysicalTransportCredentialAssignment:
        values = dict(raw)
        values["scope"] = WorkflowScope(**cast(Any, values["scope"]))
        values["activated_at"] = datetime.fromisoformat(str(values["activated_at"]))
        values["expires_at"] = datetime.fromisoformat(str(values["expires_at"]))
        return DeploymentPhysicalTransportCredentialAssignment(**cast(Any, values))

    async def _credential_assignment_snapshot_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowTransportCredentialAssignmentSnapshotRequest,
    ) -> WorkflowTransportCredentialAssignmentSnapshotResult | None:
        claim = await self._load_credential_assignment_snapshot_claim(
            session,
            scope=request.scope,
            snapshotter_subject_id=request.snapshotter_subject_id,
            idempotency_key=request.idempotency_key,
        )
        if claim is None:
            return None
        snapshot_row = await session.get(
            EventPhysicalTransportCredentialAssignmentSnapshotModel,
            claim.snapshot_id,
        )
        record = self._credential_assignment_snapshot_record_from_claim(claim, snapshot_row)
        status = (
            WorkflowTransportCredentialAssignmentSnapshotStatus.REPLAY
            if record.request_fingerprint == request.request_fingerprint
            else WorkflowTransportCredentialAssignmentSnapshotStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowTransportCredentialAssignmentSnapshotResult(status, record.snapshot)

    @classmethod
    async def _load_credential_assignment_snapshot_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        snapshotter_subject_id: str,
        idempotency_key: str,
    ) -> EventPhysicalTransportCredentialAssignmentSnapshotClaimModel | None:
        scope_id = cls._credential_assignment_snapshot_idempotency_scope(
            scope, snapshotter_subject_id
        )
        return cast(
            EventPhysicalTransportCredentialAssignmentSnapshotClaimModel | None,
            await session.scalar(
                select(EventPhysicalTransportCredentialAssignmentSnapshotClaimModel).where(
                    EventPhysicalTransportCredentialAssignmentSnapshotClaimModel.idempotency_scope_id
                    == scope_id,
                    EventPhysicalTransportCredentialAssignmentSnapshotClaimModel.idempotency_key
                    == idempotency_key,
                    EventPhysicalTransportCredentialAssignmentSnapshotClaimModel.organization_id
                    == scope.organization_id,
                    EventPhysicalTransportCredentialAssignmentSnapshotClaimModel.environment_id
                    == scope.environment_id,
                    EventPhysicalTransportCredentialAssignmentSnapshotClaimModel.site_id
                    == scope.site_id,
                    EventPhysicalTransportCredentialAssignmentSnapshotClaimModel.snapshotter_subject_id
                    == snapshotter_subject_id,
                )
            ),
        )

    @classmethod
    def _credential_assignment_snapshot_record_from_claim(
        cls,
        claim: EventPhysicalTransportCredentialAssignmentSnapshotClaimModel,
        snapshot_row: EventPhysicalTransportCredentialAssignmentSnapshotModel | None,
    ) -> WorkflowTransportCredentialAssignmentSnapshotIdempotencyRecord:
        if snapshot_row is None:
            cls._credential_assignment_snapshot_contract_violation()
        snapshot = cls._credential_assignment_snapshot_from_row(snapshot_row)
        scope_id = cls._credential_assignment_snapshot_idempotency_scope(
            snapshot.scope, snapshot.snapshotter_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_digest": snapshot.canonical_digest,
            "result_snapshot": cls._credential_assignment_snapshot_payload(snapshot),
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != snapshot.canonical_digest
            or claim.snapshot_id != snapshot.snapshot_id
            or claim.assignment_id != snapshot.assignment_id
            or claim.assignment_revision != snapshot.assignment_revision
            or claim.source_assignment_digest != snapshot.source_assignment_digest
            or claim.organization_id != snapshot.scope.organization_id
            or claim.environment_id != snapshot.scope.environment_id
            or claim.site_id != snapshot.scope.site_id
            or claim.snapshotter_subject_id != snapshot.snapshotter_subject_id
            or claim.canonical_digest != canonical_digest(payload)
            or claim.payload != payload
        ):
            cls._credential_assignment_snapshot_contract_violation()
        return WorkflowTransportCredentialAssignmentSnapshotIdempotencyRecord(
            request_fingerprint=claim.request_fingerprint,
            snapshot=snapshot,
        )

    @classmethod
    def _credential_assignment_snapshot_from_row(
        cls, row: EventPhysicalTransportCredentialAssignmentSnapshotModel
    ) -> EventPhysicalTransportCredentialAssignmentSnapshot:
        try:
            snapshot = cls._credential_assignment_snapshot_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowTransportCredentialAssignmentSnapshotError(
                "workflow_transport_credential_assignment_snapshot_repository_contract_violation",
                "Credential-assignment snapshot evidence is invalid.",
            ) from exc
        authority = snapshot.authority
        if (
            row.snapshot_id != snapshot.snapshot_id
            or row.assignment_id != snapshot.assignment_id
            or row.assignment_revision != snapshot.assignment_revision
            or row.source_assignment_digest != snapshot.source_assignment_digest
            or row.organization_id != snapshot.scope.organization_id
            or row.environment_id != snapshot.scope.environment_id
            or row.site_id != snapshot.scope.site_id
            or row.route_snapshot_id != snapshot.route_snapshot_id
            or row.route_id != snapshot.route_id
            or row.route_revision != snapshot.route_revision
            or row.source_route_digest != snapshot.source_route_digest
            or row.credential_requirement_profile_id != snapshot.credential_requirement_profile_id
            or row.credential_requirement_profile_version
            != snapshot.credential_requirement_profile_version
            or row.credential_requirement_profile_digest
            != snapshot.credential_requirement_profile_digest
            or row.credential_profile_id != snapshot.credential_profile_id
            or row.credential_profile_version != snapshot.credential_profile_version
            or row.credential_profile_digest != snapshot.credential_profile_digest
            or row.authentication_mechanism_class != snapshot.authentication_mechanism_class
            or row.principal_class != snapshot.principal_class
            or row.privilege_class != snapshot.privilege_class
            or row.target_scope_commitment != snapshot.target_scope_commitment
            or row.credential_generation != snapshot.credential_generation
            or row.rotation_epoch != snapshot.rotation_epoch
            or row.activated_at != snapshot.activated_at
            or row.expires_at != snapshot.expires_at
            or row.source_non_revoked != snapshot.source_non_revoked
            or row.broker_policy_id != snapshot.broker_policy_id
            or row.broker_policy_version != snapshot.broker_policy_version
            or row.broker_policy_digest != snapshot.broker_policy_digest
            or row.snapshotter_subject_id != snapshot.snapshotter_subject_id
            or row.captured_at != snapshot.captured_at
            or row.state != snapshot.state.value
            or row.endpoint_resolution_authority_granted != authority.endpoint_resolution_authorized
            or row.protected_artifact_access_authority_granted
            != authority.protected_artifact_access_authorized
            or row.credential_selection_authority_granted
            != authority.credential_selection_authorized
            or row.credential_access_authority_granted != authority.credential_access_authorized
            or row.credential_brokerage_authority_granted
            != authority.credential_brokerage_authorized
            or row.credential_resolution_authority_granted
            != authority.credential_resolution_authorized
            or row.credential_delivery_authority_granted != authority.credential_delivery_authorized
            or row.network_access_authority_granted != authority.network_access_authorized
            or row.readiness_probe_authority_granted != authority.readiness_probe_authorized
            or row.publication_authority_granted != authority.publication_authorized
            or row.delivery_authority_granted != authority.delivery_authorized
            or row.dispatch_authority_granted != authority.dispatch_authorized
            or row.execution_authority_granted != authority.execution_authorized
            or row.infrastructure_mutation_authority_granted
            != authority.infrastructure_mutation_authorized
            or row.canonical_digest != snapshot.canonical_digest
            or row.payload != cls._credential_assignment_snapshot_payload(snapshot)
        ):
            cls._credential_assignment_snapshot_contract_violation()
        return snapshot

    @classmethod
    def _credential_assignment_snapshot_model(
        cls, snapshot: EventPhysicalTransportCredentialAssignmentSnapshot
    ) -> EventPhysicalTransportCredentialAssignmentSnapshotModel:
        authority = snapshot.authority
        return EventPhysicalTransportCredentialAssignmentSnapshotModel(
            snapshot_id=snapshot.snapshot_id,
            assignment_id=snapshot.assignment_id,
            assignment_revision=snapshot.assignment_revision,
            source_assignment_digest=snapshot.source_assignment_digest,
            organization_id=snapshot.scope.organization_id,
            environment_id=snapshot.scope.environment_id,
            site_id=snapshot.scope.site_id,
            route_snapshot_id=snapshot.route_snapshot_id,
            route_id=snapshot.route_id,
            route_revision=snapshot.route_revision,
            source_route_digest=snapshot.source_route_digest,
            credential_requirement_profile_id=snapshot.credential_requirement_profile_id,
            credential_requirement_profile_version=(
                snapshot.credential_requirement_profile_version
            ),
            credential_requirement_profile_digest=(snapshot.credential_requirement_profile_digest),
            credential_profile_id=snapshot.credential_profile_id,
            credential_profile_version=snapshot.credential_profile_version,
            credential_profile_digest=snapshot.credential_profile_digest,
            authentication_mechanism_class=snapshot.authentication_mechanism_class,
            principal_class=snapshot.principal_class,
            privilege_class=snapshot.privilege_class,
            target_scope_commitment=snapshot.target_scope_commitment,
            credential_generation=snapshot.credential_generation,
            rotation_epoch=snapshot.rotation_epoch,
            activated_at=snapshot.activated_at,
            expires_at=snapshot.expires_at,
            source_non_revoked=snapshot.source_non_revoked,
            broker_policy_id=snapshot.broker_policy_id,
            broker_policy_version=snapshot.broker_policy_version,
            broker_policy_digest=snapshot.broker_policy_digest,
            snapshotter_subject_id=snapshot.snapshotter_subject_id,
            captured_at=snapshot.captured_at,
            state=snapshot.state.value,
            endpoint_resolution_authority_granted=authority.endpoint_resolution_authorized,
            protected_artifact_access_authority_granted=(
                authority.protected_artifact_access_authorized
            ),
            credential_selection_authority_granted=authority.credential_selection_authorized,
            credential_access_authority_granted=authority.credential_access_authorized,
            credential_brokerage_authority_granted=authority.credential_brokerage_authorized,
            credential_resolution_authority_granted=authority.credential_resolution_authorized,
            credential_delivery_authority_granted=authority.credential_delivery_authorized,
            network_access_authority_granted=authority.network_access_authorized,
            readiness_probe_authority_granted=authority.readiness_probe_authorized,
            publication_authority_granted=authority.publication_authorized,
            delivery_authority_granted=authority.delivery_authorized,
            dispatch_authority_granted=authority.dispatch_authorized,
            execution_authority_granted=authority.execution_authorized,
            infrastructure_mutation_authority_granted=(
                authority.infrastructure_mutation_authorized
            ),
            canonical_digest=snapshot.canonical_digest,
            payload=cls._credential_assignment_snapshot_payload(snapshot),
        )

    @classmethod
    def _credential_assignment_snapshot_claim_model(
        cls, request: WorkflowTransportCredentialAssignmentSnapshotRequest
    ) -> EventPhysicalTransportCredentialAssignmentSnapshotClaimModel:
        snapshot = request.candidate
        scope_id = cls._credential_assignment_snapshot_idempotency_scope(
            snapshot.scope, snapshot.snapshotter_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_digest": snapshot.canonical_digest,
            "result_snapshot": cls._credential_assignment_snapshot_payload(snapshot),
        }
        digest = canonical_digest(payload)
        return EventPhysicalTransportCredentialAssignmentSnapshotClaimModel(
            claim_id=f"event_transport_credential_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=snapshot.canonical_digest,
            snapshot_id=snapshot.snapshot_id,
            assignment_id=snapshot.assignment_id,
            assignment_revision=snapshot.assignment_revision,
            source_assignment_digest=snapshot.source_assignment_digest,
            organization_id=snapshot.scope.organization_id,
            environment_id=snapshot.scope.environment_id,
            site_id=snapshot.scope.site_id,
            snapshotter_subject_id=snapshot.snapshotter_subject_id,
            created_at=request.requested_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _credential_assignment_snapshot_evidence_matches(
        cls,
        *,
        request: WorkflowTransportCredentialAssignmentSnapshotRequest,
        source_row: DeploymentEventTransportCredentialAssignmentModel | None,
        route_row: EventPhysicalTransportRouteSnapshotModel | None,
        captured_at: datetime,
    ) -> bool:
        if source_row is None or route_row is None:
            return False
        source = cls._credential_assignment_from_row(source_row)
        route = cls._transport_route_snapshot_from_row(route_row)
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
            and candidate.state
            is EventPhysicalTransportCredentialAssignmentSnapshotState.SNAPSHOTTED
            and not any(candidate.authority.canonical_value().values())
        )

    @staticmethod
    def _credential_assignment_snapshot_idempotency_scope(
        scope: WorkflowScope, snapshotter_subject_id: str
    ) -> str:
        return canonical_digest(
            {
                "scope": scope.canonical_value(),
                "snapshotter_subject_id": snapshotter_subject_id,
            }
        )

    @staticmethod
    def _credential_assignment_snapshot_payload(
        snapshot: EventPhysicalTransportCredentialAssignmentSnapshot,
    ) -> dict[str, Any]:
        return cast(dict[str, Any], snapshot.canonical_value())

    @staticmethod
    def _credential_assignment_registry_lock_id(assignment_id: str) -> int:
        return int.from_bytes(
            sha256(f"workflow-transport-credential-assignment:{assignment_id}".encode()).digest()[
                :8
            ],
            byteorder="big",
            signed=True,
        )

    @staticmethod
    def _credential_assignment_snapshot_to_domain(
        raw: dict[str, Any],
    ) -> EventPhysicalTransportCredentialAssignmentSnapshot:
        values = dict(raw)
        values["scope"] = WorkflowScope(**cast(Any, values["scope"]))
        values["activated_at"] = datetime.fromisoformat(str(values["activated_at"]))
        values["expires_at"] = datetime.fromisoformat(str(values["expires_at"]))
        values["captured_at"] = datetime.fromisoformat(str(values["captured_at"]))
        values["state"] = EventPhysicalTransportCredentialAssignmentSnapshotState(
            str(values["state"])
        )
        values["authority"] = EventPhysicalTransportCredentialAssignmentSnapshotAuthority(
            **cast(Any, values["authority"])
        )
        return EventPhysicalTransportCredentialAssignmentSnapshot(**cast(Any, values))

    @staticmethod
    def _credential_assignment_contract_violation() -> NoReturn:
        raise WorkflowTransportCredentialAssignmentSnapshotError(
            "workflow_transport_credential_assignment_registry_contract_violation",
            "Credential-assignment registry evidence conflicts with durable history.",
        )

    @staticmethod
    def _credential_assignment_snapshot_contract_violation() -> NoReturn:
        raise WorkflowTransportCredentialAssignmentSnapshotError(
            "workflow_transport_credential_assignment_snapshot_repository_contract_violation",
            "Credential-assignment snapshot does not match its durable evidence.",
        )

    async def _transport_compatibility_admission_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowEventTransportCompatibilityAdmissionRequest,
    ) -> WorkflowEventTransportCompatibilityAdmissionResult | None:
        candidate = request.candidate
        claim = await self._load_transport_compatibility_admission_claim(
            session,
            scope=candidate.scope,
            admitter_subject_id=candidate.admitter_subject_id,
            idempotency_key=request.idempotency_key,
        )
        if claim is None:
            return None
        admission_row = await session.get(
            WorkflowEventTransportCompatibilityAdmissionModel,
            claim.compatibility_admission_id,
        )
        record = self._transport_compatibility_admission_record_from_claim(claim, admission_row)
        status = (
            WorkflowEventTransportCompatibilityAdmissionStatus.REPLAY
            if record.request_fingerprint == request.request_fingerprint
            else WorkflowEventTransportCompatibilityAdmissionStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowEventTransportCompatibilityAdmissionResult(status, record.admission)

    @classmethod
    async def _load_transport_compatibility_admission_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        admitter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventTransportCompatibilityAdmissionClaimModel | None:
        scope_id = cls._transport_compatibility_admission_idempotency_scope(
            scope, admitter_subject_id
        )
        return cast(
            WorkflowEventTransportCompatibilityAdmissionClaimModel | None,
            await session.scalar(
                select(WorkflowEventTransportCompatibilityAdmissionClaimModel).where(
                    WorkflowEventTransportCompatibilityAdmissionClaimModel.idempotency_scope_id
                    == scope_id,
                    WorkflowEventTransportCompatibilityAdmissionClaimModel.idempotency_key
                    == idempotency_key,
                    WorkflowEventTransportCompatibilityAdmissionClaimModel.organization_id
                    == scope.organization_id,
                    WorkflowEventTransportCompatibilityAdmissionClaimModel.environment_id
                    == scope.environment_id,
                    WorkflowEventTransportCompatibilityAdmissionClaimModel.site_id == scope.site_id,
                    WorkflowEventTransportCompatibilityAdmissionClaimModel.admitter_subject_id
                    == admitter_subject_id,
                )
            ),
        )

    @classmethod
    def _transport_compatibility_admission_record_from_claim(
        cls,
        claim: WorkflowEventTransportCompatibilityAdmissionClaimModel,
        admission_row: WorkflowEventTransportCompatibilityAdmissionModel | None,
    ) -> WorkflowEventTransportCompatibilityAdmissionIdempotencyRecord:
        if admission_row is None:
            cls._transport_compatibility_admission_contract_violation()
        assert admission_row is not None
        admission = cls._transport_compatibility_admission_from_row(admission_row)
        scope_id = cls._transport_compatibility_admission_idempotency_scope(
            admission.scope, admission.admitter_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_admission": cls._transport_compatibility_admission_payload(admission),
            "result_digest": admission.canonical_digest,
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != admission.canonical_digest
            or claim.compatibility_admission_id != admission.compatibility_admission_id
            or claim.logical_channel_binding_id != admission.logical_channel_binding_id
            or claim.transport_profile_snapshot_id != admission.transport_profile_snapshot_id
            or claim.policy_digest != admission.policy_digest
            or claim.organization_id != admission.scope.organization_id
            or claim.environment_id != admission.scope.environment_id
            or claim.site_id != admission.scope.site_id
            or claim.admitter_subject_id != admission.admitter_subject_id
            or claim.created_at.tzinfo is None
            or claim.created_at != admission.admitted_at
            or claim.payload != payload
            or claim.canonical_digest != canonical_digest(payload)
        ):
            cls._transport_compatibility_admission_contract_violation()
        return WorkflowEventTransportCompatibilityAdmissionIdempotencyRecord(
            request_fingerprint=claim.request_fingerprint,
            admission=admission,
        )

    @classmethod
    def _transport_compatibility_admission_from_row(
        cls, row: WorkflowEventTransportCompatibilityAdmissionModel
    ) -> WorkflowEventTransportCompatibilityAdmission:
        try:
            admission = cls._transport_compatibility_admission_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowEventTransportCompatibilityAdmissionError(
                "workflow_transport_compatibility_admission_repository_contract_violation",
                "The workflow transport compatibility repository contains an invalid record.",
            ) from exc
        authority = admission.authority
        if (
            row.compatibility_admission_id != admission.compatibility_admission_id
            or row.logical_channel_binding_id != admission.logical_channel_binding_id
            or row.logical_channel_binding_digest != admission.logical_channel_binding_digest
            or row.transport_profile_snapshot_id != admission.transport_profile_snapshot_id
            or row.transport_profile_snapshot_digest != admission.transport_profile_snapshot_digest
            or row.transport_profile_id != admission.transport_profile_id
            or row.transport_profile_revision != admission.transport_profile_revision
            or row.policy_id != admission.policy_id
            or row.policy_version != admission.policy_version
            or row.policy_digest != admission.policy_digest
            or row.organization_id != admission.scope.organization_id
            or row.environment_id != admission.scope.environment_id
            or row.site_id != admission.scope.site_id
            or row.event_type != admission.event_type
            or row.event_version != admission.event_version
            or row.schema_uri != admission.schema_uri
            or row.data_classification != admission.data_classification
            or row.representation_name != admission.representation_name
            or row.encoding != admission.encoding
            or row.delivery_semantics != admission.delivery_semantics
            or row.durability_required != admission.durability_required
            or row.ordering_key_kind != admission.ordering_key_kind
            or row.retention_class != admission.retention_class
            or row.logical_maximum_byte_count != admission.logical_maximum_byte_count
            or row.artifact_byte_count != admission.artifact_byte_count
            or row.profile_maximum_message_byte_count
            != admission.profile_maximum_message_byte_count
            or row.admitter_subject_id != admission.admitter_subject_id
            or row.admitted_at != admission.admitted_at
            or row.state != admission.state.value
            or row.route_selection_authority_granted != authority.route_selection_authorized
            or row.route_binding_authority_granted != authority.route_binding_authorized
            or row.credential_access_authority_granted != authority.credential_access_authorized
            or row.publication_authority_granted != authority.publication_authorized
            or row.delivery_authority_granted != authority.delivery_authorized
            or row.dispatch_authority_granted != authority.dispatch_authorized
            or row.execution_authority_granted != authority.execution_authorized
            or row.canonical_digest != admission.canonical_digest
            or row.payload != cls._transport_compatibility_admission_payload(admission)
        ):
            cls._transport_compatibility_admission_contract_violation()
        return admission

    @classmethod
    def _transport_compatibility_admission_model(
        cls, admission: WorkflowEventTransportCompatibilityAdmission
    ) -> WorkflowEventTransportCompatibilityAdmissionModel:
        authority = admission.authority
        return WorkflowEventTransportCompatibilityAdmissionModel(
            compatibility_admission_id=admission.compatibility_admission_id,
            logical_channel_binding_id=admission.logical_channel_binding_id,
            logical_channel_binding_digest=admission.logical_channel_binding_digest,
            transport_profile_snapshot_id=admission.transport_profile_snapshot_id,
            transport_profile_snapshot_digest=admission.transport_profile_snapshot_digest,
            transport_profile_id=admission.transport_profile_id,
            transport_profile_revision=admission.transport_profile_revision,
            policy_id=admission.policy_id,
            policy_version=admission.policy_version,
            policy_digest=admission.policy_digest,
            organization_id=admission.scope.organization_id,
            environment_id=admission.scope.environment_id,
            site_id=admission.scope.site_id,
            event_type=admission.event_type,
            event_version=admission.event_version,
            schema_uri=admission.schema_uri,
            data_classification=admission.data_classification,
            representation_name=admission.representation_name,
            encoding=admission.encoding,
            delivery_semantics=admission.delivery_semantics,
            durability_required=admission.durability_required,
            ordering_key_kind=admission.ordering_key_kind,
            retention_class=admission.retention_class,
            logical_maximum_byte_count=admission.logical_maximum_byte_count,
            artifact_byte_count=admission.artifact_byte_count,
            profile_maximum_message_byte_count=admission.profile_maximum_message_byte_count,
            admitter_subject_id=admission.admitter_subject_id,
            admitted_at=admission.admitted_at,
            state=admission.state.value,
            route_selection_authority_granted=authority.route_selection_authorized,
            route_binding_authority_granted=authority.route_binding_authorized,
            credential_access_authority_granted=authority.credential_access_authorized,
            publication_authority_granted=authority.publication_authorized,
            delivery_authority_granted=authority.delivery_authorized,
            dispatch_authority_granted=authority.dispatch_authorized,
            execution_authority_granted=authority.execution_authorized,
            canonical_digest=admission.canonical_digest,
            payload=cls._transport_compatibility_admission_payload(admission),
        )

    @classmethod
    def _transport_compatibility_admission_claim_model(
        cls, request: WorkflowEventTransportCompatibilityAdmissionRequest
    ) -> WorkflowEventTransportCompatibilityAdmissionClaimModel:
        admission = request.candidate
        scope_id = cls._transport_compatibility_admission_idempotency_scope(
            admission.scope, admission.admitter_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_admission": cls._transport_compatibility_admission_payload(admission),
            "result_digest": admission.canonical_digest,
        }
        digest = canonical_digest(payload)
        return WorkflowEventTransportCompatibilityAdmissionClaimModel(
            claim_id=f"wf_transport_compat_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=admission.canonical_digest,
            compatibility_admission_id=admission.compatibility_admission_id,
            logical_channel_binding_id=admission.logical_channel_binding_id,
            transport_profile_snapshot_id=admission.transport_profile_snapshot_id,
            policy_digest=admission.policy_digest,
            organization_id=admission.scope.organization_id,
            environment_id=admission.scope.environment_id,
            site_id=admission.scope.site_id,
            admitter_subject_id=admission.admitter_subject_id,
            created_at=request.requested_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _transport_compatibility_admission_evidence_matches(
        cls,
        *,
        binding_row: WorkflowEventLogicalChannelBindingModel | None,
        profile_row: EventPhysicalTransportProfileSnapshotModel | None,
        request: WorkflowEventTransportCompatibilityAdmissionRequest,
    ) -> bool:
        if binding_row is None or profile_row is None:
            return False
        binding = cls._event_logical_channel_binding_from_row(binding_row)
        profile = cls._transport_profile_snapshot_from_row(profile_row)
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
    def _transport_compatibility_admission_idempotency_scope(
        scope: WorkflowScope, admitter_subject_id: str
    ) -> str:
        return canonical_digest(
            {
                "admitter_subject_id": admitter_subject_id,
                "scope": scope.canonical_value(),
            }
        )

    @staticmethod
    def _transport_compatibility_admission_payload(
        admission: WorkflowEventTransportCompatibilityAdmission,
    ) -> dict[str, Any]:
        return cast(dict[str, Any], admission.canonical_value())

    @staticmethod
    def _transport_compatibility_admission_to_domain(
        raw: dict[str, Any],
    ) -> WorkflowEventTransportCompatibilityAdmission:
        values = dict(raw)
        values["scope"] = WorkflowScope(**cast(Any, values["scope"]))
        values["admitted_at"] = datetime.fromisoformat(str(values["admitted_at"]))
        values["state"] = WorkflowEventTransportCompatibilityAdmissionState(str(values["state"]))
        values["authority"] = WorkflowEventTransportCompatibilityAdmissionAuthority(
            **cast(Any, values["authority"])
        )
        return WorkflowEventTransportCompatibilityAdmission(**cast(Any, values))

    @staticmethod
    def _validate_transport_compatibility_admission_request(
        request: WorkflowEventTransportCompatibilityAdmissionRequest,
    ) -> None:
        candidate = request.candidate
        if candidate.scope != request.scope:
            raise ValueError("workflow transport compatibility scope is invalid")
        if candidate.admitter_subject_id != request.admitter_subject_id:
            raise ValueError("workflow transport compatibility admitter is invalid")
        if candidate.admitted_at != request.requested_at:
            raise ValueError("workflow transport compatibility time is invalid")
        if candidate.state is not WorkflowEventTransportCompatibilityAdmissionState.ADMITTED:
            raise ValueError("workflow transport compatibility state is invalid")
        if any(candidate.authority.canonical_value().values()):
            raise ValueError("workflow transport compatibility authority is unsafe")
        if not request.idempotency_key or len(request.idempotency_key) > 128:
            raise ValueError("workflow transport compatibility idempotency key is invalid")
        if len(request.request_fingerprint) != 64:
            raise ValueError("workflow transport compatibility request fingerprint is invalid")
        if request.requested_at.tzinfo is None or candidate.admitted_at.tzinfo is None:
            raise ValueError("workflow transport compatibility time must be aware")

    @staticmethod
    def _transport_compatibility_admission_contract_violation() -> NoReturn:
        raise WorkflowEventTransportCompatibilityAdmissionError(
            "workflow_transport_compatibility_admission_repository_contract_violation",
            "The workflow transport compatibility admission does not match its durable evidence.",
        )

    async def _credential_assignment_binding_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowTransportCredentialAssignmentBindingRequest,
    ) -> WorkflowTransportCredentialAssignmentBindingResult | None:
        claim = await self._load_credential_assignment_binding_claim(
            session,
            scope=request.scope,
            binder_subject_id=request.binder_subject_id,
            idempotency_key=request.idempotency_key,
        )
        if claim is None:
            return None
        binding_row = await session.get(
            WorkflowEventPhysicalTransportCredentialAssignmentBindingModel,
            claim.binding_id,
        )
        record = self._credential_assignment_binding_record_from_claim(claim, binding_row)
        status = (
            WorkflowTransportCredentialAssignmentBindingStatus.REPLAY
            if claim.request_fingerprint == request.request_fingerprint
            else WorkflowTransportCredentialAssignmentBindingStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowTransportCredentialAssignmentBindingResult(status, record.binding)

    @classmethod
    async def _load_credential_assignment_binding_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        binder_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventPhysicalTransportCredentialAssignmentBindingClaimModel | None:
        return cast(
            WorkflowEventPhysicalTransportCredentialAssignmentBindingClaimModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportCredentialAssignmentBindingClaimModel).where(
                    WorkflowEventPhysicalTransportCredentialAssignmentBindingClaimModel.idempotency_scope_id
                    == cls._credential_assignment_binding_idempotency_scope(
                        scope, binder_subject_id
                    ),
                    WorkflowEventPhysicalTransportCredentialAssignmentBindingClaimModel.idempotency_key
                    == idempotency_key,
                    WorkflowEventPhysicalTransportCredentialAssignmentBindingClaimModel.organization_id
                    == scope.organization_id,
                    WorkflowEventPhysicalTransportCredentialAssignmentBindingClaimModel.environment_id
                    == scope.environment_id,
                    WorkflowEventPhysicalTransportCredentialAssignmentBindingClaimModel.site_id
                    == scope.site_id,
                    WorkflowEventPhysicalTransportCredentialAssignmentBindingClaimModel.binder_subject_id
                    == binder_subject_id,
                )
            ),
        )

    @classmethod
    def _credential_assignment_binding_record_from_claim(
        cls,
        claim: WorkflowEventPhysicalTransportCredentialAssignmentBindingClaimModel,
        binding_row: WorkflowEventPhysicalTransportCredentialAssignmentBindingModel | None,
    ) -> WorkflowTransportCredentialAssignmentBindingIdempotencyRecord:
        if binding_row is None:
            cls._credential_assignment_binding_contract_violation()
        assert binding_row is not None
        binding = cls._credential_assignment_binding_from_row(binding_row)
        scope_id = cls._credential_assignment_binding_idempotency_scope(
            binding.scope, binding.binder_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_binding": cls._credential_assignment_binding_payload(binding),
            "result_digest": binding.canonical_digest,
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != binding.canonical_digest
            or claim.binding_id != binding.binding_id
            or claim.physical_transport_route_binding_id
            != binding.physical_transport_route_binding_id
            or claim.transport_route_snapshot_id != binding.transport_route_snapshot_id
            or claim.credential_assignment_snapshot_id != binding.credential_assignment_snapshot_id
            or claim.policy_digest != binding.policy_digest
            or claim.organization_id != binding.scope.organization_id
            or claim.environment_id != binding.scope.environment_id
            or claim.site_id != binding.scope.site_id
            or claim.binder_subject_id != binding.binder_subject_id
            or claim.created_at.tzinfo is None
            or claim.created_at != binding.bound_at
            or claim.payload != payload
            or claim.canonical_digest != canonical_digest(payload)
        ):
            cls._credential_assignment_binding_contract_violation()
        return WorkflowTransportCredentialAssignmentBindingIdempotencyRecord(
            request_fingerprint=claim.request_fingerprint,
            binding=binding,
        )

    @classmethod
    def _credential_assignment_binding_from_row(
        cls,
        row: WorkflowEventPhysicalTransportCredentialAssignmentBindingModel,
    ) -> WorkflowEventPhysicalTransportCredentialAssignmentBinding:
        try:
            binding = cls._credential_assignment_binding_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowTransportCredentialAssignmentBindingError(
                "workflow_transport_credential_assignment_binding_repository_contract_violation",
                "The workflow credential-assignment binding record is invalid.",
            ) from exc
        authority = binding.authority
        if (
            row.binding_id != binding.binding_id
            or row.physical_transport_route_binding_id
            != binding.physical_transport_route_binding_id
            or row.physical_transport_route_binding_digest
            != binding.physical_transport_route_binding_digest
            or row.transport_route_snapshot_id != binding.transport_route_snapshot_id
            or row.transport_route_snapshot_digest != binding.transport_route_snapshot_digest
            or row.credential_assignment_snapshot_id != binding.credential_assignment_snapshot_id
            or row.credential_assignment_snapshot_digest
            != binding.credential_assignment_snapshot_digest
            or row.policy_id != binding.policy_id
            or row.policy_version != binding.policy_version
            or row.policy_digest != binding.policy_digest
            or row.organization_id != binding.scope.organization_id
            or row.environment_id != binding.scope.environment_id
            or row.site_id != binding.scope.site_id
            or row.binder_subject_id != binding.binder_subject_id
            or row.bound_at != binding.bound_at
            or row.state != binding.state.value
            or row.route_selection_authority_granted != authority.route_selection_authorized
            or row.route_binding_authority_granted != authority.route_binding_authorized
            or row.endpoint_resolution_authority_granted != authority.endpoint_resolution_authorized
            or row.protected_artifact_access_authority_granted
            != authority.protected_artifact_access_authorized
            or row.credential_selection_authority_granted
            != authority.credential_selection_authorized
            or row.credential_assignment_binding_authority_granted
            != authority.credential_assignment_binding_authorized
            or row.credential_access_authority_granted != authority.credential_access_authorized
            or row.credential_brokerage_authority_granted
            != authority.credential_brokerage_authorized
            or row.credential_resolution_authority_granted
            != authority.credential_resolution_authorized
            or row.credential_delivery_authority_granted != authority.credential_delivery_authorized
            or row.network_access_authority_granted != authority.network_access_authorized
            or row.readiness_probe_authority_granted != authority.readiness_probe_authorized
            or row.publication_authority_granted != authority.publication_authorized
            or row.delivery_authority_granted != authority.delivery_authorized
            or row.dispatch_authority_granted != authority.dispatch_authorized
            or row.execution_authority_granted != authority.execution_authorized
            or row.infrastructure_mutation_authority_granted
            != authority.infrastructure_mutation_authorized
            or row.canonical_digest != binding.canonical_digest
            or row.payload != cls._credential_assignment_binding_payload(binding)
        ):
            cls._credential_assignment_binding_contract_violation()
        return binding

    @classmethod
    def _credential_assignment_binding_model(
        cls,
        binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding,
    ) -> WorkflowEventPhysicalTransportCredentialAssignmentBindingModel:
        authority = binding.authority
        return WorkflowEventPhysicalTransportCredentialAssignmentBindingModel(
            binding_id=binding.binding_id,
            physical_transport_route_binding_id=binding.physical_transport_route_binding_id,
            physical_transport_route_binding_digest=(
                binding.physical_transport_route_binding_digest
            ),
            transport_route_snapshot_id=binding.transport_route_snapshot_id,
            transport_route_snapshot_digest=binding.transport_route_snapshot_digest,
            credential_assignment_snapshot_id=binding.credential_assignment_snapshot_id,
            credential_assignment_snapshot_digest=(binding.credential_assignment_snapshot_digest),
            policy_id=binding.policy_id,
            policy_version=binding.policy_version,
            policy_digest=binding.policy_digest,
            organization_id=binding.scope.organization_id,
            environment_id=binding.scope.environment_id,
            site_id=binding.scope.site_id,
            binder_subject_id=binding.binder_subject_id,
            bound_at=binding.bound_at,
            state=binding.state.value,
            route_selection_authority_granted=authority.route_selection_authorized,
            route_binding_authority_granted=authority.route_binding_authorized,
            endpoint_resolution_authority_granted=authority.endpoint_resolution_authorized,
            protected_artifact_access_authority_granted=(
                authority.protected_artifact_access_authorized
            ),
            credential_selection_authority_granted=authority.credential_selection_authorized,
            credential_assignment_binding_authority_granted=(
                authority.credential_assignment_binding_authorized
            ),
            credential_access_authority_granted=authority.credential_access_authorized,
            credential_brokerage_authority_granted=authority.credential_brokerage_authorized,
            credential_resolution_authority_granted=authority.credential_resolution_authorized,
            credential_delivery_authority_granted=authority.credential_delivery_authorized,
            network_access_authority_granted=authority.network_access_authorized,
            readiness_probe_authority_granted=authority.readiness_probe_authorized,
            publication_authority_granted=authority.publication_authorized,
            delivery_authority_granted=authority.delivery_authorized,
            dispatch_authority_granted=authority.dispatch_authorized,
            execution_authority_granted=authority.execution_authorized,
            infrastructure_mutation_authority_granted=(
                authority.infrastructure_mutation_authorized
            ),
            canonical_digest=binding.canonical_digest,
            payload=cls._credential_assignment_binding_payload(binding),
        )

    @classmethod
    def _credential_assignment_binding_claim_model(
        cls,
        request: WorkflowTransportCredentialAssignmentBindingRequest,
    ) -> WorkflowEventPhysicalTransportCredentialAssignmentBindingClaimModel:
        binding = request.candidate
        scope_id = cls._credential_assignment_binding_idempotency_scope(
            binding.scope, binding.binder_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_binding": cls._credential_assignment_binding_payload(binding),
            "result_digest": binding.canonical_digest,
        }
        digest = canonical_digest(payload)
        return WorkflowEventPhysicalTransportCredentialAssignmentBindingClaimModel(
            claim_id=f"wf_transport_credential_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=binding.canonical_digest,
            binding_id=binding.binding_id,
            physical_transport_route_binding_id=binding.physical_transport_route_binding_id,
            transport_route_snapshot_id=binding.transport_route_snapshot_id,
            credential_assignment_snapshot_id=binding.credential_assignment_snapshot_id,
            policy_digest=binding.policy_digest,
            organization_id=binding.scope.organization_id,
            environment_id=binding.scope.environment_id,
            site_id=binding.scope.site_id,
            binder_subject_id=binding.binder_subject_id,
            created_at=request.requested_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _credential_assignment_binding_evidence_matches(
        cls,
        *,
        route_binding_row: WorkflowEventPhysicalTransportRouteBindingModel | None,
        route_snapshot_row: EventPhysicalTransportRouteSnapshotModel | None,
        assignment_snapshot_row: EventPhysicalTransportCredentialAssignmentSnapshotModel | None,
        request: WorkflowTransportCredentialAssignmentBindingRequest,
    ) -> bool:
        if (
            route_binding_row is None
            or route_snapshot_row is None
            or assignment_snapshot_row is None
        ):
            return False
        try:
            route_binding = cls._physical_transport_route_binding_from_row(route_binding_row)
            route_snapshot = cls._transport_route_snapshot_from_row(route_snapshot_row)
            assignment_snapshot = cls._credential_assignment_snapshot_from_row(
                assignment_snapshot_row
            )
        except (
            WorkflowEventPhysicalTransportRouteBindingError,
            WorkflowTransportRouteSnapshotError,
            WorkflowTransportCredentialAssignmentSnapshotError,
        ):
            return False
        candidate = request.candidate
        policy = code_owned_workflow_event_physical_transport_credential_assignment_binding_policy()
        sources = (route_binding, route_snapshot, assignment_snapshot)
        return bool(
            all(
                canonical_digest(source.digest_payload()) == source.canonical_digest
                and source.scope == request.scope
                and not any(source.authority.canonical_value().values())
                for source in sources
            )
            and route_binding.state is WorkflowEventPhysicalTransportRouteBindingState.BOUND
            and route_binding.binding_id
            == request.expected_physical_transport_route_binding_id
            == candidate.physical_transport_route_binding_id
            and route_binding.canonical_digest
            == request.expected_physical_transport_route_binding_digest
            == candidate.physical_transport_route_binding_digest
            and route_binding.transport_route_snapshot_id
            == route_snapshot.snapshot_id
            == request.expected_transport_route_snapshot_id
            == candidate.transport_route_snapshot_id
            and route_binding.transport_route_snapshot_digest
            == route_snapshot.canonical_digest
            == request.expected_transport_route_snapshot_digest
            == candidate.transport_route_snapshot_digest
            and route_snapshot.state is EventPhysicalTransportRouteSnapshotState.SNAPSHOTTED
            and assignment_snapshot.state
            is EventPhysicalTransportCredentialAssignmentSnapshotState.SNAPSHOTTED
            and assignment_snapshot.snapshot_id
            == request.expected_credential_assignment_snapshot_id
            == candidate.credential_assignment_snapshot_id
            and assignment_snapshot.canonical_digest
            == request.expected_credential_assignment_snapshot_digest
            == candidate.credential_assignment_snapshot_digest
            and assignment_snapshot.route_snapshot_id == route_snapshot.snapshot_id
            and assignment_snapshot.route_id == route_snapshot.route_id
            and assignment_snapshot.route_revision == route_snapshot.route_revision
            and assignment_snapshot.source_route_digest == route_snapshot.source_route_digest
            and assignment_snapshot.credential_requirement_profile_id
            == route_snapshot.credential_requirement_profile_id
            and assignment_snapshot.credential_requirement_profile_version
            == route_snapshot.credential_requirement_profile_version
            and assignment_snapshot.credential_requirement_profile_digest
            == route_snapshot.credential_requirement_profile_digest
            and assignment_snapshot.authentication_mechanism_class
            == route_snapshot.authentication_mechanism_class
            and assignment_snapshot.principal_class == route_snapshot.principal_class
            and assignment_snapshot.privilege_class == policy.required_privilege_class
            and assignment_snapshot.credential_generation > 0
            and assignment_snapshot.rotation_epoch > 0
            and route_binding.scope
            == route_snapshot.scope
            == assignment_snapshot.scope
            == candidate.scope
            and route_snapshot.captured_at <= route_binding.bound_at <= candidate.bound_at
            and assignment_snapshot.captured_at <= candidate.bound_at
            and candidate.policy_id == policy.policy_id
            and candidate.policy_version == policy.policy_version
            and candidate.policy_digest == request.expected_policy_digest == policy.canonical_digest
            and candidate.binder_subject_id == request.binder_subject_id
            and candidate.bound_at == request.requested_at
            and candidate.state
            is WorkflowEventPhysicalTransportCredentialAssignmentBindingState.BOUND
            and canonical_digest(candidate.digest_payload()) == candidate.canonical_digest
            and not any(candidate.authority.canonical_value().values())
        )

    @staticmethod
    def _credential_assignment_binding_idempotency_scope(
        scope: WorkflowScope,
        binder_subject_id: str,
    ) -> str:
        return canonical_digest(
            {"binder_subject_id": binder_subject_id, "scope": scope.canonical_value()}
        )

    @staticmethod
    def _credential_assignment_binding_payload(
        binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding,
    ) -> dict[str, Any]:
        return cast(dict[str, Any], binding.canonical_value())

    @staticmethod
    def _credential_assignment_binding_to_domain(
        raw: dict[str, Any],
    ) -> WorkflowEventPhysicalTransportCredentialAssignmentBinding:
        values = dict(raw)
        values["scope"] = WorkflowScope(**cast(Any, values["scope"]))
        values["bound_at"] = datetime.fromisoformat(str(values["bound_at"]))
        values["state"] = WorkflowEventPhysicalTransportCredentialAssignmentBindingState(
            str(values["state"])
        )
        values["authority"] = WorkflowEventPhysicalTransportCredentialAssignmentBindingAuthority(
            **cast(Any, values["authority"])
        )
        return WorkflowEventPhysicalTransportCredentialAssignmentBinding(**cast(Any, values))

    @staticmethod
    def _validate_credential_assignment_binding_request(
        request: WorkflowTransportCredentialAssignmentBindingRequest,
    ) -> None:
        candidate = request.candidate
        if (
            candidate.physical_transport_route_binding_id
            != request.expected_physical_transport_route_binding_id
            or candidate.physical_transport_route_binding_digest
            != request.expected_physical_transport_route_binding_digest
            or candidate.transport_route_snapshot_id != request.expected_transport_route_snapshot_id
            or candidate.transport_route_snapshot_digest
            != request.expected_transport_route_snapshot_digest
            or candidate.credential_assignment_snapshot_id
            != request.expected_credential_assignment_snapshot_id
            or candidate.credential_assignment_snapshot_digest
            != request.expected_credential_assignment_snapshot_digest
            or candidate.policy_digest != request.expected_policy_digest
            or candidate.scope != request.scope
            or candidate.binder_subject_id != request.binder_subject_id
            or candidate.bound_at != request.requested_at
            or candidate.state
            is not WorkflowEventPhysicalTransportCredentialAssignmentBindingState.BOUND
            or any(candidate.authority.canonical_value().values())
        ):
            raise ValueError("workflow credential-assignment binding request is unsafe")
        if not 8 <= len(request.idempotency_key) <= 128:
            raise ValueError("credential-assignment binding idempotency key is invalid")
        if len(request.request_fingerprint) != 64 or any(
            character not in "0123456789abcdef" for character in request.request_fingerprint
        ):
            raise ValueError("credential-assignment binding fingerprint is invalid")
        if request.requested_at.tzinfo is None:
            raise ValueError("credential-assignment binding time must be aware")

    @staticmethod
    def _credential_assignment_binding_contract_violation() -> NoReturn:
        raise WorkflowTransportCredentialAssignmentBindingError(
            "workflow_transport_credential_assignment_binding_repository_contract_violation",
            "The workflow credential-assignment binding does not match durable evidence.",
        )

    async def _lock_credential_assignment_freshness_sources(
        self,
        session: AsyncSession,
        *,
        request: WorkflowTransportCredentialAssignmentFreshnessAdmissionRequest,
    ) -> tuple[
        WorkflowEventPhysicalTransportCredentialAssignmentBindingModel | None,
        EventPhysicalTransportCredentialAssignmentSnapshotModel | None,
        DeploymentPhysicalTransportCredentialAssignment | None,
        datetime,
    ]:
        binding_row = cast(
            WorkflowEventPhysicalTransportCredentialAssignmentBindingModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportCredentialAssignmentBindingModel)
                .where(
                    WorkflowEventPhysicalTransportCredentialAssignmentBindingModel.binding_id
                    == request.expected_credential_assignment_binding_id
                )
                .with_for_update()
            ),
        )
        snapshot_row = cast(
            EventPhysicalTransportCredentialAssignmentSnapshotModel | None,
            await session.scalar(
                select(EventPhysicalTransportCredentialAssignmentSnapshotModel)
                .where(
                    EventPhysicalTransportCredentialAssignmentSnapshotModel.snapshot_id
                    == request.expected_credential_assignment_snapshot_id
                )
                .with_for_update()
            ),
        )
        await session.scalar(
            select(
                func.pg_advisory_xact_lock(
                    self._credential_assignment_registry_lock_id(request.expected_assignment_id)
                )
            )
        )
        assignment_rows = tuple(
            (
                await session.scalars(
                    select(DeploymentEventTransportCredentialAssignmentModel)
                    .where(
                        DeploymentEventTransportCredentialAssignmentModel.assignment_id
                        == request.expected_assignment_id
                    )
                    .order_by(
                        DeploymentEventTransportCredentialAssignmentModel.rotation_epoch,
                        DeploymentEventTransportCredentialAssignmentModel.credential_generation,
                        DeploymentEventTransportCredentialAssignmentModel.assignment_revision,
                    )
                    .with_for_update()
                )
            ).all()
        )
        try:
            head = select_deployment_physical_transport_credential_assignment_head(
                tuple(self._credential_assignment_from_row(row) for row in assignment_rows)
            )
        except (ValueError, WorkflowTransportCredentialAssignmentSnapshotError):
            head = None
        observed_at = cast(datetime, await session.scalar(select(func.clock_timestamp())))
        return binding_row, snapshot_row, head, observed_at

    async def _credential_assignment_freshness_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowTransportCredentialAssignmentFreshnessAdmissionRequest,
        head: DeploymentPhysicalTransportCredentialAssignment | None,
        observed_at: datetime,
    ) -> WorkflowTransportCredentialAssignmentFreshnessAdmissionResult | None:
        claim = await self._load_credential_assignment_freshness_claim(
            session,
            scope=request.scope,
            admitter_subject_id=request.admitter_subject_id,
            idempotency_key=request.idempotency_key,
        )
        if claim is None:
            return None
        admission_row = await session.get(
            WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel,
            claim.freshness_admission_id,
        )
        record = self._credential_assignment_freshness_record_from_claim(
            claim,
            admission_row,
        )
        if claim.request_fingerprint != request.request_fingerprint:
            return WorkflowTransportCredentialAssignmentFreshnessAdmissionResult(
                WorkflowTransportCredentialAssignmentFreshnessAdmissionStatus.IDEMPOTENCY_CONFLICT,
                record.admission,
            )
        if head is None or not self._credential_assignment_freshness_remains_current(
            record.admission,
            head=head,
            observed_at=observed_at,
        ):
            return WorkflowTransportCredentialAssignmentFreshnessAdmissionResult(
                WorkflowTransportCredentialAssignmentFreshnessAdmissionStatus.EVIDENCE_CONFLICT,
                record.admission,
            )
        return WorkflowTransportCredentialAssignmentFreshnessAdmissionResult(
            WorkflowTransportCredentialAssignmentFreshnessAdmissionStatus.REPLAY,
            record.admission,
        )

    @classmethod
    async def _load_credential_assignment_freshness_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        admitter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventPhysicalTransportCredentialAssignmentFreshnessClaimModel | None:
        return cast(
            WorkflowEventPhysicalTransportCredentialAssignmentFreshnessClaimModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportCredentialAssignmentFreshnessClaimModel).where(
                    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessClaimModel.idempotency_scope_id
                    == cls._credential_assignment_freshness_idempotency_scope(
                        scope,
                        admitter_subject_id,
                    ),
                    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessClaimModel.idempotency_key
                    == idempotency_key,
                    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessClaimModel.organization_id
                    == scope.organization_id,
                    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessClaimModel.environment_id
                    == scope.environment_id,
                    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessClaimModel.site_id
                    == scope.site_id,
                    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessClaimModel.admitter_subject_id
                    == admitter_subject_id,
                )
            ),
        )

    @classmethod
    def _credential_assignment_freshness_record_from_claim(
        cls,
        claim: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessClaimModel,
        admission_row: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel
        | None,
    ) -> WorkflowTransportCredentialAssignmentFreshnessAdmissionIdempotencyRecord:
        if admission_row is None:
            cls._credential_assignment_freshness_contract_violation()
        assert admission_row is not None
        admission = cls._credential_assignment_freshness_admission_from_row(admission_row)
        scope_id = cls._credential_assignment_freshness_idempotency_scope(
            admission.scope,
            admission.admitter_subject_id,
        )
        payload: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_admission": cls._credential_assignment_freshness_payload(admission),
            "result_digest": admission.canonical_digest,
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != admission.canonical_digest
            or claim.freshness_admission_id != admission.freshness_admission_id
            or claim.credential_assignment_binding_id
            != admission.physical_transport_credential_assignment_binding_id
            or claim.credential_assignment_snapshot_id
            != admission.credential_assignment_snapshot_id
            or claim.assignment_id != admission.assignment_id
            or claim.assignment_revision != admission.assignment_revision
            or claim.policy_digest != admission.policy_digest
            or claim.organization_id != admission.scope.organization_id
            or claim.environment_id != admission.scope.environment_id
            or claim.site_id != admission.scope.site_id
            or claim.admitter_subject_id != admission.admitter_subject_id
            or claim.created_at.tzinfo is None
            or claim.created_at != admission.evaluated_at
            or claim.payload != payload
            or claim.canonical_digest != canonical_digest(payload)
        ):
            cls._credential_assignment_freshness_contract_violation()
        return WorkflowTransportCredentialAssignmentFreshnessAdmissionIdempotencyRecord(
            request_fingerprint=claim.request_fingerprint,
            admission=admission,
        )

    @classmethod
    def _credential_assignment_freshness_admission_from_row(
        cls,
        row: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel,
    ) -> WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission:
        try:
            admission = cls._credential_assignment_freshness_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowTransportCredentialAssignmentFreshnessAdmissionError(
                "workflow_transport_credential_assignment_freshness_repository_contract_violation",
                "The credential-assignment freshness admission record is invalid.",
            ) from exc
        authority = admission.authority
        if (
            row.freshness_admission_id != admission.freshness_admission_id
            or row.credential_assignment_binding_id
            != admission.physical_transport_credential_assignment_binding_id
            or row.credential_assignment_binding_digest
            != admission.physical_transport_credential_assignment_binding_digest
            or row.credential_assignment_snapshot_id != admission.credential_assignment_snapshot_id
            or row.credential_assignment_snapshot_digest
            != admission.credential_assignment_snapshot_digest
            or row.assignment_id != admission.assignment_id
            or row.assignment_revision != admission.assignment_revision
            or row.source_assignment_digest != admission.source_assignment_digest
            or row.credential_generation != admission.credential_generation
            or row.rotation_epoch != admission.rotation_epoch
            or row.assignment_activated_at != admission.assignment_activated_at
            or row.assignment_expires_at != admission.assignment_expires_at
            or row.assignment_active != admission.assignment_active
            or row.assignment_non_revoked != admission.assignment_non_revoked
            or row.policy_id != admission.policy_id
            or row.policy_version != admission.policy_version
            or row.policy_digest != admission.policy_digest
            or row.organization_id != admission.scope.organization_id
            or row.environment_id != admission.scope.environment_id
            or row.site_id != admission.scope.site_id
            or row.admitter_subject_id != admission.admitter_subject_id
            or row.evaluated_at != admission.evaluated_at
            or row.valid_until != admission.valid_until
            or row.state != admission.state.value
            or row.route_selection_authority_granted != authority.route_selection_authorized
            or row.route_binding_authority_granted != authority.route_binding_authorized
            or row.endpoint_resolution_authority_granted != authority.endpoint_resolution_authorized
            or row.protected_artifact_access_authority_granted
            != authority.protected_artifact_access_authorized
            or row.credential_selection_authority_granted
            != authority.credential_selection_authorized
            or row.credential_assignment_binding_authority_granted
            != authority.credential_assignment_binding_authorized
            or row.credential_access_authority_granted != authority.credential_access_authorized
            or row.credential_brokerage_authority_granted
            != authority.credential_brokerage_authorized
            or row.credential_resolution_authority_granted
            != authority.credential_resolution_authorized
            or row.credential_delivery_authority_granted != authority.credential_delivery_authorized
            or row.network_access_authority_granted != authority.network_access_authorized
            or row.readiness_probe_authority_granted != authority.readiness_probe_authorized
            or row.publication_authority_granted != authority.publication_authorized
            or row.delivery_authority_granted != authority.delivery_authorized
            or row.dispatch_authority_granted != authority.dispatch_authorized
            or row.execution_authority_granted != authority.execution_authorized
            or row.infrastructure_mutation_authority_granted
            != authority.infrastructure_mutation_authorized
            or row.canonical_digest != admission.canonical_digest
            or row.payload != cls._credential_assignment_freshness_payload(admission)
        ):
            cls._credential_assignment_freshness_contract_violation()
        return admission

    @classmethod
    def _credential_assignment_freshness_admission_model(
        cls,
        admission: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission,
    ) -> WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel:
        authority = admission.authority
        return WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel(
            freshness_admission_id=admission.freshness_admission_id,
            credential_assignment_binding_id=(
                admission.physical_transport_credential_assignment_binding_id
            ),
            credential_assignment_binding_digest=(
                admission.physical_transport_credential_assignment_binding_digest
            ),
            credential_assignment_snapshot_id=admission.credential_assignment_snapshot_id,
            credential_assignment_snapshot_digest=(admission.credential_assignment_snapshot_digest),
            assignment_id=admission.assignment_id,
            assignment_revision=admission.assignment_revision,
            source_assignment_digest=admission.source_assignment_digest,
            credential_generation=admission.credential_generation,
            rotation_epoch=admission.rotation_epoch,
            assignment_activated_at=admission.assignment_activated_at,
            assignment_expires_at=admission.assignment_expires_at,
            assignment_active=admission.assignment_active,
            assignment_non_revoked=admission.assignment_non_revoked,
            policy_id=admission.policy_id,
            policy_version=admission.policy_version,
            policy_digest=admission.policy_digest,
            organization_id=admission.scope.organization_id,
            environment_id=admission.scope.environment_id,
            site_id=admission.scope.site_id,
            admitter_subject_id=admission.admitter_subject_id,
            evaluated_at=admission.evaluated_at,
            valid_until=admission.valid_until,
            state=admission.state.value,
            route_selection_authority_granted=authority.route_selection_authorized,
            route_binding_authority_granted=authority.route_binding_authorized,
            endpoint_resolution_authority_granted=authority.endpoint_resolution_authorized,
            protected_artifact_access_authority_granted=(
                authority.protected_artifact_access_authorized
            ),
            credential_selection_authority_granted=authority.credential_selection_authorized,
            credential_assignment_binding_authority_granted=(
                authority.credential_assignment_binding_authorized
            ),
            credential_access_authority_granted=authority.credential_access_authorized,
            credential_brokerage_authority_granted=authority.credential_brokerage_authorized,
            credential_resolution_authority_granted=authority.credential_resolution_authorized,
            credential_delivery_authority_granted=authority.credential_delivery_authorized,
            network_access_authority_granted=authority.network_access_authorized,
            readiness_probe_authority_granted=authority.readiness_probe_authorized,
            publication_authority_granted=authority.publication_authorized,
            delivery_authority_granted=authority.delivery_authorized,
            dispatch_authority_granted=authority.dispatch_authorized,
            execution_authority_granted=authority.execution_authorized,
            infrastructure_mutation_authority_granted=(
                authority.infrastructure_mutation_authorized
            ),
            canonical_digest=admission.canonical_digest,
            payload=cls._credential_assignment_freshness_payload(admission),
        )

    @classmethod
    def _credential_assignment_freshness_claim_model(
        cls,
        request: WorkflowTransportCredentialAssignmentFreshnessAdmissionRequest,
    ) -> WorkflowEventPhysicalTransportCredentialAssignmentFreshnessClaimModel:
        admission = request.candidate
        scope_id = cls._credential_assignment_freshness_idempotency_scope(
            admission.scope,
            admission.admitter_subject_id,
        )
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_admission": cls._credential_assignment_freshness_payload(admission),
            "result_digest": admission.canonical_digest,
        }
        digest = canonical_digest(payload)
        return WorkflowEventPhysicalTransportCredentialAssignmentFreshnessClaimModel(
            claim_id=f"wf_cred_fresh_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=admission.canonical_digest,
            freshness_admission_id=admission.freshness_admission_id,
            credential_assignment_binding_id=(
                admission.physical_transport_credential_assignment_binding_id
            ),
            credential_assignment_snapshot_id=admission.credential_assignment_snapshot_id,
            assignment_id=admission.assignment_id,
            assignment_revision=admission.assignment_revision,
            policy_digest=admission.policy_digest,
            organization_id=admission.scope.organization_id,
            environment_id=admission.scope.environment_id,
            site_id=admission.scope.site_id,
            admitter_subject_id=admission.admitter_subject_id,
            created_at=admission.evaluated_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _credential_assignment_freshness_evidence_matches(
        cls,
        *,
        binding_row: WorkflowEventPhysicalTransportCredentialAssignmentBindingModel | None,
        snapshot_row: EventPhysicalTransportCredentialAssignmentSnapshotModel | None,
        head: DeploymentPhysicalTransportCredentialAssignment | None,
        observed_at: datetime,
        request: WorkflowTransportCredentialAssignmentFreshnessAdmissionRequest,
    ) -> bool:
        if binding_row is None or snapshot_row is None or head is None:
            return False
        try:
            binding = cls._credential_assignment_binding_from_row(binding_row)
            snapshot = cls._credential_assignment_snapshot_from_row(snapshot_row)
        except (
            WorkflowTransportCredentialAssignmentBindingError,
            WorkflowTransportCredentialAssignmentSnapshotError,
        ):
            return False
        candidate = request.candidate
        return bool(
            binding.binding_id
            == request.expected_credential_assignment_binding_id
            == candidate.physical_transport_credential_assignment_binding_id
            and binding.canonical_digest
            == request.expected_credential_assignment_binding_digest
            == candidate.physical_transport_credential_assignment_binding_digest
            and binding.state
            is WorkflowEventPhysicalTransportCredentialAssignmentBindingState.BOUND
            and binding.credential_assignment_snapshot_id
            == snapshot.snapshot_id
            == request.expected_credential_assignment_snapshot_id
            == candidate.credential_assignment_snapshot_id
            and binding.credential_assignment_snapshot_digest
            == snapshot.canonical_digest
            == request.expected_credential_assignment_snapshot_digest
            == candidate.credential_assignment_snapshot_digest
            and snapshot.state
            is EventPhysicalTransportCredentialAssignmentSnapshotState.SNAPSHOTTED
            and head.assignment_id
            == snapshot.assignment_id
            == request.expected_assignment_id
            == candidate.assignment_id
            and head.assignment_revision
            == snapshot.assignment_revision
            == request.expected_assignment_revision
            == candidate.assignment_revision
            and head.canonical_digest
            == snapshot.source_assignment_digest
            == request.expected_source_assignment_digest
            == candidate.source_assignment_digest
            and head.scope == snapshot.scope == binding.scope == request.scope == candidate.scope
            and head.route_id == snapshot.route_id
            and head.route_revision == snapshot.route_revision
            and head.source_route_digest == snapshot.source_route_digest
            and head.credential_requirement_profile_id == snapshot.credential_requirement_profile_id
            and head.credential_requirement_profile_version
            == snapshot.credential_requirement_profile_version
            and head.credential_requirement_profile_digest
            == snapshot.credential_requirement_profile_digest
            and head.credential_profile_id == snapshot.credential_profile_id
            and head.credential_profile_version == snapshot.credential_profile_version
            and head.credential_profile_digest == snapshot.credential_profile_digest
            and head.authentication_mechanism_class == snapshot.authentication_mechanism_class
            and head.principal_class == snapshot.principal_class
            and head.privilege_class == snapshot.privilege_class == "read-only"
            and head.target_scope_commitment == snapshot.target_scope_commitment
            and head.credential_generation
            == snapshot.credential_generation
            == request.expected_credential_generation
            == candidate.credential_generation
            and head.rotation_epoch
            == snapshot.rotation_epoch
            == request.expected_rotation_epoch
            == candidate.rotation_epoch
            and head.activated_at
            == snapshot.activated_at
            == request.expected_assignment_activated_at
            == candidate.assignment_activated_at
            and head.expires_at
            == snapshot.expires_at
            == request.expected_assignment_expires_at
            == candidate.assignment_expires_at
            and head.broker_policy_id == snapshot.broker_policy_id
            and head.broker_policy_version == snapshot.broker_policy_version
            and head.broker_policy_digest == snapshot.broker_policy_digest
            and head.active == request.expected_assignment_active == candidate.assignment_active
            and head.revoked == request.expected_assignment_revoked
            and candidate.assignment_non_revoked == (not head.revoked)
            and head.active
            and not head.revoked
            and head.activated_at <= observed_at < head.expires_at
            and candidate.evaluated_at == request.requested_at <= observed_at
            and observed_at < candidate.valid_until
            and candidate.valid_until
            == min(request.requested_at + timedelta(seconds=60), head.expires_at)
            and candidate.policy_digest == request.expected_policy_digest
            and candidate.admitter_subject_id == request.admitter_subject_id
            and candidate.state.value == "admitted_current"
            and canonical_digest(binding.digest_payload()) == binding.canonical_digest
            and canonical_digest(snapshot.digest_payload()) == snapshot.canonical_digest
            and canonical_digest(head.digest_payload()) == head.canonical_digest
            and canonical_digest(candidate.digest_payload()) == candidate.canonical_digest
            and not any(binding.authority.canonical_value().values())
            and not any(snapshot.authority.canonical_value().values())
            and not any(candidate.authority.canonical_value().values())
        )

    @staticmethod
    def _credential_assignment_freshness_remains_current(
        admission: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission,
        *,
        head: DeploymentPhysicalTransportCredentialAssignment,
        observed_at: datetime,
    ) -> bool:
        return (
            observed_at < admission.valid_until
            and head.assignment_id == admission.assignment_id
            and head.assignment_revision == admission.assignment_revision
            and head.canonical_digest == admission.source_assignment_digest
            and head.credential_generation == admission.credential_generation
            and head.rotation_epoch == admission.rotation_epoch
            and head.activated_at == admission.assignment_activated_at
            and head.expires_at == admission.assignment_expires_at
            and head.active
            and not head.revoked
            and head.activated_at <= observed_at < head.expires_at
        )

    @staticmethod
    def _credential_assignment_freshness_idempotency_scope(
        scope: WorkflowScope,
        admitter_subject_id: str,
    ) -> str:
        return canonical_digest(
            {"admitter_subject_id": admitter_subject_id, "scope": scope.canonical_value()}
        )

    @staticmethod
    def _credential_assignment_freshness_payload(
        admission: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission,
    ) -> dict[str, Any]:
        return cast(dict[str, Any], admission.canonical_value())

    @staticmethod
    def _credential_assignment_freshness_to_domain(
        raw: dict[str, Any],
    ) -> WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission:
        values = dict(raw)
        values["scope"] = WorkflowScope(**cast(Any, values["scope"]))
        for name in (
            "assignment_activated_at",
            "assignment_expires_at",
            "evaluated_at",
            "valid_until",
        ):
            values[name] = datetime.fromisoformat(str(values[name]))
        values["state"] = WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionState(
            str(values["state"])
        )
        values["authority"] = (
            WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionAuthority(
                **cast(Any, values["authority"])
            )
        )
        return WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission(
            **cast(Any, values)
        )

    @staticmethod
    def _credential_assignment_freshness_contract_violation() -> NoReturn:
        raise WorkflowTransportCredentialAssignmentFreshnessAdmissionError(
            "workflow_transport_credential_assignment_freshness_repository_contract_violation",
            "Credential-assignment freshness evidence does not match durable state.",
        )

    async def _lock_credential_access_authorization_sources(
        self,
        session: AsyncSession,
        *,
        request: WorkflowTransportCredentialAccessAuthorizationLeaseRequest,
    ) -> tuple[
        WorkflowEventPhysicalTransportCredentialAssignmentBindingModel | None,
        EventPhysicalTransportCredentialAssignmentSnapshotModel | None,
        DeploymentPhysicalTransportCredentialAssignment | None,
        WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel | None,
        datetime,
    ]:
        binding_row = cast(
            WorkflowEventPhysicalTransportCredentialAssignmentBindingModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportCredentialAssignmentBindingModel)
                .where(
                    WorkflowEventPhysicalTransportCredentialAssignmentBindingModel.binding_id
                    == request.expected_credential_assignment_binding_id
                )
                .with_for_update()
            ),
        )
        snapshot_row = cast(
            EventPhysicalTransportCredentialAssignmentSnapshotModel | None,
            await session.scalar(
                select(EventPhysicalTransportCredentialAssignmentSnapshotModel)
                .where(
                    EventPhysicalTransportCredentialAssignmentSnapshotModel.snapshot_id
                    == request.expected_credential_assignment_snapshot_id
                )
                .with_for_update()
            ),
        )
        await session.scalar(
            select(
                func.pg_advisory_xact_lock(
                    self._credential_assignment_registry_lock_id(request.expected_assignment_id)
                )
            )
        )
        assignment_rows = tuple(
            (
                await session.scalars(
                    select(DeploymentEventTransportCredentialAssignmentModel)
                    .where(
                        DeploymentEventTransportCredentialAssignmentModel.assignment_id
                        == request.expected_assignment_id
                    )
                    .order_by(
                        DeploymentEventTransportCredentialAssignmentModel.rotation_epoch,
                        DeploymentEventTransportCredentialAssignmentModel.credential_generation,
                        DeploymentEventTransportCredentialAssignmentModel.assignment_revision,
                    )
                    .with_for_update()
                )
            ).all()
        )
        try:
            head = select_deployment_physical_transport_credential_assignment_head(
                tuple(self._credential_assignment_from_row(row) for row in assignment_rows)
            )
        except (ValueError, WorkflowTransportCredentialAssignmentSnapshotError):
            head = None
        admission_row = cast(
            WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel)
                .where(
                    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel.freshness_admission_id
                    == request.expected_freshness_admission_id
                )
                .with_for_update()
            ),
        )
        observed_at = cast(datetime, await session.scalar(select(func.clock_timestamp())))
        return binding_row, snapshot_row, head, admission_row, observed_at

    async def _credential_access_authorization_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowTransportCredentialAccessAuthorizationLeaseRequest,
        binding_row: WorkflowEventPhysicalTransportCredentialAssignmentBindingModel | None,
        snapshot_row: EventPhysicalTransportCredentialAssignmentSnapshotModel | None,
        head: DeploymentPhysicalTransportCredentialAssignment | None,
        admission_row: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel
        | None,
        observed_at: datetime,
    ) -> WorkflowTransportCredentialAccessAuthorizationLeaseResult | None:
        claim = await self._load_credential_access_claim(
            session,
            scope=request.scope,
            accessor_subject_id=request.accessor_subject_id,
            idempotency_key=request.idempotency_key,
        )
        if claim is None:
            return None
        lease_row = await session.get(
            WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel,
            claim.authorization_lease_id,
        )
        record = self._credential_access_record_from_claim(claim, lease_row)
        if claim.request_fingerprint != request.request_fingerprint:
            return WorkflowTransportCredentialAccessAuthorizationLeaseResult(
                WorkflowTransportCredentialAccessAuthorizationLeaseStatus.IDEMPOTENCY_CONFLICT,
                record.lease,
            )
        if not self._credential_access_authorization_remains_current(
            record.lease,
            binding_row=binding_row,
            snapshot_row=snapshot_row,
            head=head,
            admission_row=admission_row,
            observed_at=observed_at,
            expected_policy_digest=request.expected_policy_digest,
        ):
            return WorkflowTransportCredentialAccessAuthorizationLeaseResult(
                WorkflowTransportCredentialAccessAuthorizationLeaseStatus.EVIDENCE_CONFLICT,
                None,
            )
        return WorkflowTransportCredentialAccessAuthorizationLeaseResult(
            WorkflowTransportCredentialAccessAuthorizationLeaseStatus.REPLAY,
            record.lease,
        )

    @classmethod
    async def _load_credential_access_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        accessor_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventPhysicalTransportCredentialAccessAuthorizationClaimModel | None:
        return cast(
            WorkflowEventPhysicalTransportCredentialAccessAuthorizationClaimModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportCredentialAccessAuthorizationClaimModel).where(
                    WorkflowEventPhysicalTransportCredentialAccessAuthorizationClaimModel.idempotency_scope_id
                    == cls._credential_access_idempotency_scope(scope, accessor_subject_id),
                    WorkflowEventPhysicalTransportCredentialAccessAuthorizationClaimModel.idempotency_key
                    == idempotency_key,
                    WorkflowEventPhysicalTransportCredentialAccessAuthorizationClaimModel.organization_id
                    == scope.organization_id,
                    WorkflowEventPhysicalTransportCredentialAccessAuthorizationClaimModel.environment_id
                    == scope.environment_id,
                    WorkflowEventPhysicalTransportCredentialAccessAuthorizationClaimModel.site_id
                    == scope.site_id,
                    WorkflowEventPhysicalTransportCredentialAccessAuthorizationClaimModel.accessor_subject_id
                    == accessor_subject_id,
                )
            ),
        )

    @classmethod
    def _credential_access_record_from_claim(
        cls,
        claim: WorkflowEventPhysicalTransportCredentialAccessAuthorizationClaimModel,
        lease_row: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel | None,
    ) -> WorkflowTransportCredentialAccessAuthorizationLeaseIdempotencyRecord:
        if lease_row is None:
            cls._credential_access_contract_violation()
        assert lease_row is not None
        lease = cls._credential_access_lease_from_row(lease_row)
        scope_id = cls._credential_access_idempotency_scope(lease.scope, lease.accessor_subject_id)
        payload: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_digest": lease.canonical_digest,
            "result_lease": cls._credential_access_payload(lease),
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != lease.canonical_digest
            or claim.authorization_lease_id != lease.authorization_lease_id
            or claim.freshness_admission_id != lease.freshness_admission_id
            or claim.assignment_id != lease.assignment_id
            or claim.assignment_revision != lease.assignment_revision
            or claim.policy_digest != lease.policy_digest
            or claim.organization_id != lease.scope.organization_id
            or claim.environment_id != lease.scope.environment_id
            or claim.site_id != lease.scope.site_id
            or claim.accessor_subject_id != lease.accessor_subject_id
            or claim.created_at != lease.issued_at
            or claim.created_at.tzinfo is None
            or claim.payload != payload
            or claim.canonical_digest != canonical_digest(payload)
        ):
            cls._credential_access_contract_violation()
        return WorkflowTransportCredentialAccessAuthorizationLeaseIdempotencyRecord(
            request_fingerprint=claim.request_fingerprint,
            lease=lease,
        )

    @classmethod
    def _credential_access_lease_from_row(
        cls,
        row: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel,
    ) -> WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease:
        try:
            lease = cls._credential_access_to_domain(row.payload)
            expected = cls._credential_access_lease_model(lease)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowTransportCredentialAccessAuthorizationLeaseError(
                "workflow_transport_credential_access_authorization_repository_contract_violation",
                "The credential-access authorization lease record is invalid.",
            ) from exc
        for name in (
            "authorization_lease_id",
            "freshness_admission_id",
            "freshness_admission_digest",
            "credential_assignment_binding_id",
            "credential_assignment_binding_digest",
            "credential_assignment_snapshot_id",
            "credential_assignment_snapshot_digest",
            "assignment_id",
            "assignment_revision",
            "source_assignment_digest",
            "credential_generation",
            "rotation_epoch",
            "assignment_activated_at",
            "assignment_expires_at",
            "assignment_active",
            "assignment_non_revoked",
            "policy_id",
            "policy_version",
            "policy_digest",
            "organization_id",
            "environment_id",
            "site_id",
            "accessor_subject_id",
            "issued_at",
            "valid_until",
            "state",
            "endpoint_resolution_authority_granted",
            "protected_artifact_access_authority_granted",
            "route_selection_authority_granted",
            "route_binding_authority_granted",
            "credential_selection_authority_granted",
            "credential_assignment_binding_authority_granted",
            "credential_access_authority_granted",
            "credential_brokerage_authority_granted",
            "credential_resolution_authority_granted",
            "credential_delivery_authority_granted",
            "network_access_authority_granted",
            "readiness_probe_authority_granted",
            "publication_authority_granted",
            "delivery_authority_granted",
            "dispatch_authority_granted",
            "execution_authority_granted",
            "infrastructure_mutation_authority_granted",
            "canonical_digest",
            "payload",
        ):
            if getattr(row, name) != getattr(expected, name):
                cls._credential_access_contract_violation()
        return lease

    @classmethod
    def _credential_access_lease_model(
        cls, lease: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease
    ) -> WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel:
        authority = lease.authority
        return WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel(
            authorization_lease_id=lease.authorization_lease_id,
            freshness_admission_id=lease.freshness_admission_id,
            freshness_admission_digest=lease.freshness_admission_digest,
            credential_assignment_binding_id=(
                lease.physical_transport_credential_assignment_binding_id
            ),
            credential_assignment_binding_digest=(
                lease.physical_transport_credential_assignment_binding_digest
            ),
            credential_assignment_snapshot_id=lease.credential_assignment_snapshot_id,
            credential_assignment_snapshot_digest=lease.credential_assignment_snapshot_digest,
            assignment_id=lease.assignment_id,
            assignment_revision=lease.assignment_revision,
            source_assignment_digest=lease.source_assignment_digest,
            credential_generation=lease.credential_generation,
            rotation_epoch=lease.rotation_epoch,
            assignment_activated_at=lease.assignment_activated_at,
            assignment_expires_at=lease.assignment_expires_at,
            assignment_active=lease.assignment_active,
            assignment_non_revoked=lease.assignment_non_revoked,
            policy_id=lease.policy_id,
            policy_version=lease.policy_version,
            policy_digest=lease.policy_digest,
            organization_id=lease.scope.organization_id,
            environment_id=lease.scope.environment_id,
            site_id=lease.scope.site_id,
            accessor_subject_id=lease.accessor_subject_id,
            issued_at=lease.issued_at,
            valid_until=lease.valid_until,
            state=lease.state.value,
            endpoint_resolution_authority_granted=authority.endpoint_resolution_authorized,
            protected_artifact_access_authority_granted=(
                authority.protected_artifact_access_authorized
            ),
            route_selection_authority_granted=authority.route_selection_authorized,
            route_binding_authority_granted=authority.route_binding_authorized,
            credential_selection_authority_granted=authority.credential_selection_authorized,
            credential_assignment_binding_authority_granted=(
                authority.credential_assignment_binding_authorized
            ),
            credential_access_authority_granted=authority.credential_access_authorized,
            credential_brokerage_authority_granted=authority.credential_brokerage_authorized,
            credential_resolution_authority_granted=authority.credential_resolution_authorized,
            credential_delivery_authority_granted=authority.credential_delivery_authorized,
            network_access_authority_granted=authority.network_access_authorized,
            readiness_probe_authority_granted=authority.readiness_probe_authorized,
            publication_authority_granted=authority.publication_authorized,
            delivery_authority_granted=authority.delivery_authorized,
            dispatch_authority_granted=authority.dispatch_authorized,
            execution_authority_granted=authority.execution_authorized,
            infrastructure_mutation_authority_granted=(
                authority.infrastructure_mutation_authorized
            ),
            canonical_digest=lease.canonical_digest,
            payload=cls._credential_access_payload(lease),
        )

    @classmethod
    def _credential_access_claim_model(
        cls, request: WorkflowTransportCredentialAccessAuthorizationLeaseRequest
    ) -> WorkflowEventPhysicalTransportCredentialAccessAuthorizationClaimModel:
        lease = request.candidate
        scope_id = cls._credential_access_idempotency_scope(lease.scope, lease.accessor_subject_id)
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_digest": lease.canonical_digest,
            "result_lease": cls._credential_access_payload(lease),
        }
        digest = canonical_digest(payload)
        return WorkflowEventPhysicalTransportCredentialAccessAuthorizationClaimModel(
            claim_id=f"wf_cred_access_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=lease.canonical_digest,
            authorization_lease_id=lease.authorization_lease_id,
            freshness_admission_id=lease.freshness_admission_id,
            assignment_id=lease.assignment_id,
            assignment_revision=lease.assignment_revision,
            policy_digest=lease.policy_digest,
            organization_id=lease.scope.organization_id,
            environment_id=lease.scope.environment_id,
            site_id=lease.scope.site_id,
            accessor_subject_id=lease.accessor_subject_id,
            created_at=lease.issued_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _credential_access_authorization_evidence_matches(
        cls,
        *,
        binding_row: WorkflowEventPhysicalTransportCredentialAssignmentBindingModel | None,
        snapshot_row: EventPhysicalTransportCredentialAssignmentSnapshotModel | None,
        head: DeploymentPhysicalTransportCredentialAssignment | None,
        admission_row: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel
        | None,
        observed_at: datetime,
        request: WorkflowTransportCredentialAccessAuthorizationLeaseRequest,
    ) -> bool:
        if binding_row is None or snapshot_row is None or head is None or admission_row is None:
            return False
        try:
            binding = cls._credential_assignment_binding_from_row(binding_row)
            snapshot = cls._credential_assignment_snapshot_from_row(snapshot_row)
            admission = cls._credential_assignment_freshness_admission_from_row(admission_row)
        except (
            WorkflowTransportCredentialAssignmentBindingError,
            WorkflowTransportCredentialAssignmentSnapshotError,
            WorkflowTransportCredentialAssignmentFreshnessAdmissionError,
        ):
            return False
        candidate = request.candidate
        return bool(
            canonical_digest(head.digest_payload()) == head.canonical_digest
            and canonical_digest(candidate.digest_payload()) == candidate.canonical_digest
            and admission.freshness_admission_id
            == request.expected_freshness_admission_id
            == candidate.freshness_admission_id
            and admission.canonical_digest
            == request.expected_freshness_admission_digest
            == candidate.freshness_admission_digest
            and admission.valid_until == request.expected_freshness_admission_valid_until
            and admission.state.value == "admitted_current"
            and binding.binding_id
            == admission.physical_transport_credential_assignment_binding_id
            == request.expected_credential_assignment_binding_id
            == candidate.physical_transport_credential_assignment_binding_id
            and binding.canonical_digest
            == admission.physical_transport_credential_assignment_binding_digest
            == request.expected_credential_assignment_binding_digest
            == candidate.physical_transport_credential_assignment_binding_digest
            and binding.state
            is WorkflowEventPhysicalTransportCredentialAssignmentBindingState.BOUND
            and snapshot.snapshot_id
            == binding.credential_assignment_snapshot_id
            == admission.credential_assignment_snapshot_id
            == request.expected_credential_assignment_snapshot_id
            == candidate.credential_assignment_snapshot_id
            and snapshot.canonical_digest
            == binding.credential_assignment_snapshot_digest
            == admission.credential_assignment_snapshot_digest
            == request.expected_credential_assignment_snapshot_digest
            == candidate.credential_assignment_snapshot_digest
            and snapshot.state
            is EventPhysicalTransportCredentialAssignmentSnapshotState.SNAPSHOTTED
            and head.assignment_id
            == snapshot.assignment_id
            == admission.assignment_id
            == request.expected_assignment_id
            == candidate.assignment_id
            and head.assignment_revision
            == snapshot.assignment_revision
            == admission.assignment_revision
            == request.expected_assignment_revision
            == candidate.assignment_revision
            and head.canonical_digest
            == snapshot.source_assignment_digest
            == admission.source_assignment_digest
            == request.expected_source_assignment_digest
            == candidate.source_assignment_digest
            and head.credential_generation
            == snapshot.credential_generation
            == admission.credential_generation
            == request.expected_credential_generation
            == candidate.credential_generation
            and head.rotation_epoch
            == snapshot.rotation_epoch
            == admission.rotation_epoch
            == request.expected_rotation_epoch
            == candidate.rotation_epoch
            and head.activated_at
            == snapshot.activated_at
            == admission.assignment_activated_at
            == request.expected_assignment_activated_at
            == candidate.assignment_activated_at
            and head.expires_at
            == snapshot.expires_at
            == admission.assignment_expires_at
            == request.expected_assignment_expires_at
            == candidate.assignment_expires_at
            and head.scope
            == snapshot.scope
            == binding.scope
            == admission.scope
            == request.scope
            == candidate.scope
            and head.route_id == snapshot.route_id
            and head.route_revision == snapshot.route_revision
            and head.source_route_digest == snapshot.source_route_digest
            and head.credential_requirement_profile_id == snapshot.credential_requirement_profile_id
            and head.credential_requirement_profile_version
            == snapshot.credential_requirement_profile_version
            and head.credential_requirement_profile_digest
            == snapshot.credential_requirement_profile_digest
            and head.credential_profile_id == snapshot.credential_profile_id
            and head.credential_profile_version == snapshot.credential_profile_version
            and head.credential_profile_digest == snapshot.credential_profile_digest
            and head.authentication_mechanism_class == snapshot.authentication_mechanism_class
            and head.principal_class == snapshot.principal_class
            and head.privilege_class == snapshot.privilege_class == "read-only"
            and head.target_scope_commitment == snapshot.target_scope_commitment
            and head.broker_policy_id == snapshot.broker_policy_id
            and head.broker_policy_version == snapshot.broker_policy_version
            and head.broker_policy_digest == snapshot.broker_policy_digest
            and head.active
            == request.expected_assignment_active
            == admission.assignment_active
            == candidate.assignment_active
            is True
            and head.revoked == request.expected_assignment_revoked is False
            and admission.assignment_non_revoked is True
            and candidate.assignment_non_revoked is True
            and head.activated_at <= observed_at < candidate.valid_until <= head.expires_at
            and candidate.valid_until <= admission.valid_until
            and candidate.issued_at == request.requested_at
            and candidate.valid_until - candidate.issued_at
            == timedelta(seconds=request.expected_validity_window_seconds)
            and candidate.policy_digest == request.expected_policy_digest
            and candidate.accessor_subject_id == request.accessor_subject_id
            and candidate.state.value == "authorized_unconsumed"
            and not any(
                value is not False for value in admission.authority.canonical_value().values()
            )
            and not any(
                value is not False for value in binding.authority.canonical_value().values()
            )
            and not any(
                value is not False for value in snapshot.authority.canonical_value().values()
            )
            and candidate.authority.credential_access_authorized is True
            and not any(
                value is not False
                for name, value in candidate.authority.canonical_value().items()
                if name != "credential_access_authorized"
            )
        )

    @classmethod
    def _credential_access_authorization_remains_current(
        cls,
        lease: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease,
        *,
        binding_row: WorkflowEventPhysicalTransportCredentialAssignmentBindingModel | None,
        snapshot_row: EventPhysicalTransportCredentialAssignmentSnapshotModel | None,
        head: DeploymentPhysicalTransportCredentialAssignment | None,
        admission_row: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel
        | None,
        observed_at: datetime,
        expected_policy_digest: str,
    ) -> bool:
        if binding_row is None or snapshot_row is None or head is None or admission_row is None:
            return False
        try:
            binding = cls._credential_assignment_binding_from_row(binding_row)
            snapshot = cls._credential_assignment_snapshot_from_row(snapshot_row)
            admission = cls._credential_assignment_freshness_admission_from_row(admission_row)
        except (
            WorkflowTransportCredentialAssignmentBindingError,
            WorkflowTransportCredentialAssignmentSnapshotError,
            WorkflowTransportCredentialAssignmentFreshnessAdmissionError,
        ):
            return False
        return bool(
            canonical_digest(lease.digest_payload()) == lease.canonical_digest
            and lease.policy_digest == expected_policy_digest
            and lease.freshness_admission_id == admission.freshness_admission_id
            and lease.freshness_admission_digest == admission.canonical_digest
            and lease.physical_transport_credential_assignment_binding_id == binding.binding_id
            and lease.physical_transport_credential_assignment_binding_digest
            == binding.canonical_digest
            and lease.credential_assignment_snapshot_id == snapshot.snapshot_id
            and lease.credential_assignment_snapshot_digest == snapshot.canonical_digest
            and lease.assignment_id == head.assignment_id == admission.assignment_id
            and lease.assignment_revision
            == head.assignment_revision
            == admission.assignment_revision
            and lease.source_assignment_digest
            == head.canonical_digest
            == admission.source_assignment_digest
            and lease.credential_generation
            == head.credential_generation
            == admission.credential_generation
            and lease.rotation_epoch == head.rotation_epoch == admission.rotation_epoch
            and lease.assignment_activated_at == head.activated_at
            and lease.assignment_expires_at == head.expires_at
            and head.active
            and not head.revoked
            and head.activated_at <= lease.issued_at <= observed_at < lease.valid_until
            and observed_at < admission.valid_until
            and lease.valid_until <= head.expires_at
            and lease.scope == admission.scope == binding.scope == snapshot.scope == head.scope
            and lease.authority.credential_access_authorized is True
            and not any(
                value is not False
                for name, value in lease.authority.canonical_value().items()
                if name != "credential_access_authorized"
            )
        )

    @staticmethod
    def _credential_access_payload(
        lease: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease,
    ) -> dict[str, Any]:
        return cast(dict[str, Any], lease.canonical_value())

    @staticmethod
    def _credential_access_to_domain(
        raw: dict[str, Any],
    ) -> WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease:
        values = dict(raw)
        values["scope"] = WorkflowScope(**cast(Any, values["scope"]))
        for name in (
            "assignment_activated_at",
            "assignment_expires_at",
            "issued_at",
            "valid_until",
        ):
            values[name] = datetime.fromisoformat(str(values[name]))
        values["state"] = WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseState(
            str(values["state"])
        )
        values["authority"] = (
            WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseAuthority(
                **cast(Any, values["authority"])
            )
        )
        return WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease(**cast(Any, values))

    @staticmethod
    def _credential_access_idempotency_scope(scope: WorkflowScope, accessor_subject_id: str) -> str:
        return canonical_digest(
            {"accessor_subject_id": accessor_subject_id, "scope": scope.canonical_value()}
        )

    @staticmethod
    def _credential_access_contract_violation() -> NoReturn:
        raise WorkflowTransportCredentialAccessAuthorizationLeaseError(
            "workflow_transport_credential_access_authorization_repository_contract_violation",
            "Credential-access authorization evidence does not match durable state.",
        )

    async def _physical_transport_route_binding_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowEventPhysicalTransportRouteBindingRequest,
    ) -> WorkflowEventPhysicalTransportRouteBindingResult | None:
        claim = await self._load_physical_transport_route_binding_claim(
            session,
            scope=request.scope,
            binder_subject_id=request.binder_subject_id,
            idempotency_key=request.idempotency_key,
        )
        if claim is None:
            return None
        binding_row = await session.get(
            WorkflowEventPhysicalTransportRouteBindingModel, claim.binding_id
        )
        record = self._physical_transport_route_binding_record_from_claim(claim, binding_row)
        status = (
            WorkflowEventPhysicalTransportRouteBindingStatus.REPLAY
            if claim.request_fingerprint == request.request_fingerprint
            else WorkflowEventPhysicalTransportRouteBindingStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowEventPhysicalTransportRouteBindingResult(status, record.binding)

    @classmethod
    async def _load_physical_transport_route_binding_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        binder_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventPhysicalTransportRouteBindingClaimModel | None:
        return cast(
            WorkflowEventPhysicalTransportRouteBindingClaimModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportRouteBindingClaimModel).where(
                    WorkflowEventPhysicalTransportRouteBindingClaimModel.idempotency_scope_id
                    == cls._physical_transport_route_binding_idempotency_scope(
                        scope, binder_subject_id
                    ),
                    WorkflowEventPhysicalTransportRouteBindingClaimModel.idempotency_key
                    == idempotency_key,
                    WorkflowEventPhysicalTransportRouteBindingClaimModel.organization_id
                    == scope.organization_id,
                    WorkflowEventPhysicalTransportRouteBindingClaimModel.environment_id
                    == scope.environment_id,
                    WorkflowEventPhysicalTransportRouteBindingClaimModel.site_id == scope.site_id,
                    WorkflowEventPhysicalTransportRouteBindingClaimModel.binder_subject_id
                    == binder_subject_id,
                )
            ),
        )

    @classmethod
    def _physical_transport_route_binding_record_from_claim(
        cls,
        claim: WorkflowEventPhysicalTransportRouteBindingClaimModel,
        binding_row: WorkflowEventPhysicalTransportRouteBindingModel | None,
    ) -> WorkflowEventPhysicalTransportRouteBindingIdempotencyRecord:
        if binding_row is None:
            cls._physical_transport_route_binding_contract_violation()
        assert binding_row is not None
        binding = cls._physical_transport_route_binding_from_row(binding_row)
        scope_id = cls._physical_transport_route_binding_idempotency_scope(
            binding.scope, binding.binder_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_binding": cls._physical_transport_route_binding_payload(binding),
            "result_digest": binding.canonical_digest,
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != binding.canonical_digest
            or claim.binding_id != binding.binding_id
            or claim.logical_channel_binding_id != binding.logical_channel_binding_id
            or claim.transport_compatibility_admission_id
            != binding.transport_compatibility_admission_id
            or claim.transport_profile_snapshot_id != binding.transport_profile_snapshot_id
            or claim.transport_route_snapshot_id != binding.transport_route_snapshot_id
            or claim.policy_digest != binding.policy_digest
            or claim.organization_id != binding.scope.organization_id
            or claim.environment_id != binding.scope.environment_id
            or claim.site_id != binding.scope.site_id
            or claim.binder_subject_id != binding.binder_subject_id
            or claim.created_at.tzinfo is None
            or claim.created_at != binding.bound_at
            or claim.payload != payload
            or claim.canonical_digest != canonical_digest(payload)
        ):
            cls._physical_transport_route_binding_contract_violation()
        return WorkflowEventPhysicalTransportRouteBindingIdempotencyRecord(
            request_fingerprint=claim.request_fingerprint,
            binding=binding,
        )

    @classmethod
    def _physical_transport_route_binding_from_row(
        cls, row: WorkflowEventPhysicalTransportRouteBindingModel
    ) -> WorkflowEventPhysicalTransportRouteBinding:
        try:
            binding = cls._physical_transport_route_binding_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowEventPhysicalTransportRouteBindingError(
                "workflow_physical_transport_route_binding_repository_contract_violation",
                "The workflow physical transport route binding record is invalid.",
            ) from exc
        authority = binding.authority
        if (
            row.binding_id != binding.binding_id
            or row.logical_channel_binding_id != binding.logical_channel_binding_id
            or row.logical_channel_binding_digest != binding.logical_channel_binding_digest
            or row.transport_compatibility_admission_id
            != binding.transport_compatibility_admission_id
            or row.transport_compatibility_admission_digest
            != binding.transport_compatibility_admission_digest
            or row.transport_profile_snapshot_id != binding.transport_profile_snapshot_id
            or row.transport_profile_snapshot_digest != binding.transport_profile_snapshot_digest
            or row.transport_route_snapshot_id != binding.transport_route_snapshot_id
            or row.transport_route_snapshot_digest != binding.transport_route_snapshot_digest
            or row.policy_id != binding.policy_id
            or row.policy_version != binding.policy_version
            or row.policy_digest != binding.policy_digest
            or row.organization_id != binding.scope.organization_id
            or row.environment_id != binding.scope.environment_id
            or row.site_id != binding.scope.site_id
            or row.binder_subject_id != binding.binder_subject_id
            or row.bound_at != binding.bound_at
            or row.state != binding.state.value
            or row.endpoint_resolution_authority_granted != authority.endpoint_resolution_authorized
            or row.route_selection_authority_granted != authority.route_selection_authorized
            or row.route_binding_authority_granted != authority.route_binding_authorized
            or row.credential_access_authority_granted != authority.credential_access_authorized
            or row.network_access_authority_granted != authority.network_access_authorized
            or row.readiness_probe_authority_granted != authority.readiness_probe_authorized
            or row.publication_authority_granted != authority.publication_authorized
            or row.delivery_authority_granted != authority.delivery_authorized
            or row.dispatch_authority_granted != authority.dispatch_authorized
            or row.execution_authority_granted != authority.execution_authorized
            or row.canonical_digest != binding.canonical_digest
            or row.payload != cls._physical_transport_route_binding_payload(binding)
        ):
            cls._physical_transport_route_binding_contract_violation()
        return binding

    @classmethod
    def _physical_transport_route_binding_model(
        cls, binding: WorkflowEventPhysicalTransportRouteBinding
    ) -> WorkflowEventPhysicalTransportRouteBindingModel:
        authority = binding.authority
        return WorkflowEventPhysicalTransportRouteBindingModel(
            binding_id=binding.binding_id,
            logical_channel_binding_id=binding.logical_channel_binding_id,
            logical_channel_binding_digest=binding.logical_channel_binding_digest,
            transport_compatibility_admission_id=binding.transport_compatibility_admission_id,
            transport_compatibility_admission_digest=(
                binding.transport_compatibility_admission_digest
            ),
            transport_profile_snapshot_id=binding.transport_profile_snapshot_id,
            transport_profile_snapshot_digest=binding.transport_profile_snapshot_digest,
            transport_route_snapshot_id=binding.transport_route_snapshot_id,
            transport_route_snapshot_digest=binding.transport_route_snapshot_digest,
            policy_id=binding.policy_id,
            policy_version=binding.policy_version,
            policy_digest=binding.policy_digest,
            organization_id=binding.scope.organization_id,
            environment_id=binding.scope.environment_id,
            site_id=binding.scope.site_id,
            binder_subject_id=binding.binder_subject_id,
            bound_at=binding.bound_at,
            state=binding.state.value,
            endpoint_resolution_authority_granted=authority.endpoint_resolution_authorized,
            route_selection_authority_granted=authority.route_selection_authorized,
            route_binding_authority_granted=authority.route_binding_authorized,
            credential_access_authority_granted=authority.credential_access_authorized,
            network_access_authority_granted=authority.network_access_authorized,
            readiness_probe_authority_granted=authority.readiness_probe_authorized,
            publication_authority_granted=authority.publication_authorized,
            delivery_authority_granted=authority.delivery_authorized,
            dispatch_authority_granted=authority.dispatch_authorized,
            execution_authority_granted=authority.execution_authorized,
            canonical_digest=binding.canonical_digest,
            payload=cls._physical_transport_route_binding_payload(binding),
        )

    @classmethod
    def _physical_transport_route_binding_claim_model(
        cls, request: WorkflowEventPhysicalTransportRouteBindingRequest
    ) -> WorkflowEventPhysicalTransportRouteBindingClaimModel:
        binding = request.candidate
        scope_id = cls._physical_transport_route_binding_idempotency_scope(
            binding.scope, binding.binder_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_binding": cls._physical_transport_route_binding_payload(binding),
            "result_digest": binding.canonical_digest,
        }
        digest = canonical_digest(payload)
        return WorkflowEventPhysicalTransportRouteBindingClaimModel(
            claim_id=f"wf_physical_route_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=binding.canonical_digest,
            binding_id=binding.binding_id,
            logical_channel_binding_id=binding.logical_channel_binding_id,
            transport_compatibility_admission_id=(binding.transport_compatibility_admission_id),
            transport_profile_snapshot_id=binding.transport_profile_snapshot_id,
            transport_route_snapshot_id=binding.transport_route_snapshot_id,
            policy_digest=binding.policy_digest,
            organization_id=binding.scope.organization_id,
            environment_id=binding.scope.environment_id,
            site_id=binding.scope.site_id,
            binder_subject_id=binding.binder_subject_id,
            created_at=request.requested_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _physical_transport_route_binding_evidence_matches(
        cls,
        *,
        logical_row: WorkflowEventLogicalChannelBindingModel | None,
        profile_row: EventPhysicalTransportProfileSnapshotModel | None,
        admission_row: WorkflowEventTransportCompatibilityAdmissionModel | None,
        route_row: EventPhysicalTransportRouteSnapshotModel | None,
        request: WorkflowEventPhysicalTransportRouteBindingRequest,
    ) -> bool:
        if logical_row is None or profile_row is None or admission_row is None or route_row is None:
            return False
        logical = cls._event_logical_channel_binding_from_row(logical_row)
        profile = cls._transport_profile_snapshot_from_row(profile_row)
        admission = cls._transport_compatibility_admission_from_row(admission_row)
        route = cls._transport_route_snapshot_from_row(route_row)
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
            and profile.state is EventPhysicalTransportProfileSnapshotState.SNAPSHOTTED
            and profile.snapshot_id
            == request.expected_transport_profile_snapshot_id
            == candidate.transport_profile_snapshot_id
            and profile.canonical_digest
            == request.expected_transport_profile_snapshot_digest
            == candidate.transport_profile_snapshot_digest
            and admission.state is WorkflowEventTransportCompatibilityAdmissionState.ADMITTED
            and admission.compatibility_admission_id
            == request.expected_transport_compatibility_admission_id
            == candidate.transport_compatibility_admission_id
            and admission.canonical_digest
            == request.expected_transport_compatibility_admission_digest
            == candidate.transport_compatibility_admission_digest
            and admission.logical_channel_binding_id == logical.binding_id
            and admission.logical_channel_binding_digest == logical.canonical_digest
            and admission.transport_profile_snapshot_id == profile.snapshot_id
            and admission.transport_profile_snapshot_digest == profile.canonical_digest
            and admission.transport_profile_id == profile.transport_profile_id
            and admission.transport_profile_revision == profile.transport_profile_revision
            and route.state is EventPhysicalTransportRouteSnapshotState.SNAPSHOTTED
            and route.snapshot_id
            == request.expected_transport_route_snapshot_id
            == candidate.transport_route_snapshot_id
            and route.canonical_digest
            == request.expected_transport_route_snapshot_digest
            == candidate.transport_route_snapshot_digest
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

    @staticmethod
    def _physical_transport_route_binding_idempotency_scope(
        scope: WorkflowScope, binder_subject_id: str
    ) -> str:
        return canonical_digest(
            {"binder_subject_id": binder_subject_id, "scope": scope.canonical_value()}
        )

    @staticmethod
    def _physical_transport_route_binding_payload(
        binding: WorkflowEventPhysicalTransportRouteBinding,
    ) -> dict[str, Any]:
        return cast(dict[str, Any], binding.canonical_value())

    @staticmethod
    def _physical_transport_route_binding_to_domain(
        raw: dict[str, Any],
    ) -> WorkflowEventPhysicalTransportRouteBinding:
        values = dict(raw)
        values["scope"] = WorkflowScope(**cast(Any, values["scope"]))
        values["bound_at"] = datetime.fromisoformat(str(values["bound_at"]))
        values["state"] = WorkflowEventPhysicalTransportRouteBindingState(str(values["state"]))
        values["authority"] = WorkflowEventPhysicalTransportRouteBindingAuthority(
            **cast(Any, values["authority"])
        )
        return WorkflowEventPhysicalTransportRouteBinding(**cast(Any, values))

    @staticmethod
    def _validate_physical_transport_route_binding_request(
        request: WorkflowEventPhysicalTransportRouteBindingRequest,
    ) -> None:
        candidate = request.candidate
        if candidate.scope != request.scope:
            raise ValueError("workflow physical transport route binding scope is invalid")
        if candidate.binder_subject_id != request.binder_subject_id:
            raise ValueError("workflow physical transport route binding actor is invalid")
        if candidate.bound_at != request.requested_at:
            raise ValueError("workflow physical transport route binding time is invalid")
        if candidate.state is not WorkflowEventPhysicalTransportRouteBindingState.BOUND:
            raise ValueError("workflow physical transport route binding state is invalid")
        if any(candidate.authority.canonical_value().values()):
            raise ValueError("workflow physical transport route binding authority is unsafe")
        if not request.idempotency_key or len(request.idempotency_key) > 128:
            raise ValueError("workflow physical transport route binding idempotency key is invalid")
        if len(request.request_fingerprint) != 64:
            raise ValueError("workflow physical transport route binding fingerprint is invalid")
        if request.requested_at.tzinfo is None or candidate.bound_at.tzinfo is None:
            raise ValueError("workflow physical transport route binding time must be aware")

    @staticmethod
    def _physical_transport_route_binding_contract_violation() -> NoReturn:
        raise WorkflowEventPhysicalTransportRouteBindingError(
            "workflow_physical_transport_route_binding_repository_contract_violation",
            "The workflow physical transport route binding does not match durable evidence.",
        )

    async def _lock_credential_materialization_sources(
        self,
        session: AsyncSession,
        *,
        request: WorkflowEventPhysicalTransportCredentialMaterializationClaimRequest,
    ) -> tuple[
        WorkflowEventPhysicalTransportCredentialAssignmentBindingModel | None,
        EventPhysicalTransportCredentialAssignmentSnapshotModel | None,
        DeploymentPhysicalTransportCredentialAssignment | None,
        WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel | None,
        WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel | None,
    ]:
        binding_row = cast(
            WorkflowEventPhysicalTransportCredentialAssignmentBindingModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportCredentialAssignmentBindingModel)
                .where(
                    WorkflowEventPhysicalTransportCredentialAssignmentBindingModel.binding_id
                    == request.expected_credential_assignment_binding_id
                )
                .with_for_update()
            ),
        )
        snapshot_row = cast(
            EventPhysicalTransportCredentialAssignmentSnapshotModel | None,
            await session.scalar(
                select(EventPhysicalTransportCredentialAssignmentSnapshotModel)
                .where(
                    EventPhysicalTransportCredentialAssignmentSnapshotModel.snapshot_id
                    == request.expected_credential_assignment_snapshot_id
                )
                .with_for_update()
            ),
        )
        await session.scalar(
            select(
                func.pg_advisory_xact_lock(
                    self._credential_assignment_registry_lock_id(request.expected_assignment_id)
                )
            )
        )
        assignment_rows = tuple(
            (
                await session.scalars(
                    select(DeploymentEventTransportCredentialAssignmentModel)
                    .where(
                        DeploymentEventTransportCredentialAssignmentModel.assignment_id
                        == request.expected_assignment_id
                    )
                    .order_by(
                        DeploymentEventTransportCredentialAssignmentModel.rotation_epoch,
                        DeploymentEventTransportCredentialAssignmentModel.credential_generation,
                        DeploymentEventTransportCredentialAssignmentModel.assignment_revision,
                    )
                    .with_for_update()
                )
            ).all()
        )
        try:
            head = select_deployment_physical_transport_credential_assignment_head(
                tuple(self._credential_assignment_from_row(row) for row in assignment_rows)
            )
        except (ValueError, WorkflowTransportCredentialAssignmentSnapshotError):
            head = None
        freshness_row = cast(
            WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel)
                .where(
                    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel.freshness_admission_id
                    == request.expected_freshness_admission_id
                )
                .with_for_update()
            ),
        )
        lease_row = cast(
            WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel)
                .where(
                    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel.authorization_lease_id
                    == request.authorization_lease_id
                )
                .with_for_update()
            ),
        )
        return binding_row, snapshot_row, head, freshness_row, lease_row

    async def _lock_credential_materialization_result_sources(
        self,
        session: AsyncSession,
        *,
        attempt_seed: WorkflowEventPhysicalTransportCredentialMaterializationAttemptModel,
        lease_seed: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel,
    ) -> tuple[
        WorkflowEventPhysicalTransportCredentialAssignmentBindingModel | None,
        EventPhysicalTransportCredentialAssignmentSnapshotModel | None,
        DeploymentPhysicalTransportCredentialAssignment | None,
        WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel | None,
        WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel | None,
    ]:
        binding_row = cast(
            WorkflowEventPhysicalTransportCredentialAssignmentBindingModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportCredentialAssignmentBindingModel)
                .where(
                    WorkflowEventPhysicalTransportCredentialAssignmentBindingModel.binding_id
                    == attempt_seed.physical_transport_credential_assignment_binding_id
                )
                .with_for_update()
            ),
        )
        snapshot_row = cast(
            EventPhysicalTransportCredentialAssignmentSnapshotModel | None,
            await session.scalar(
                select(EventPhysicalTransportCredentialAssignmentSnapshotModel)
                .where(
                    EventPhysicalTransportCredentialAssignmentSnapshotModel.snapshot_id
                    == attempt_seed.credential_assignment_snapshot_id
                )
                .with_for_update()
            ),
        )
        await session.scalar(
            select(
                func.pg_advisory_xact_lock(
                    self._credential_assignment_registry_lock_id(attempt_seed.assignment_id)
                )
            )
        )
        assignment_rows = tuple(
            (
                await session.scalars(
                    select(DeploymentEventTransportCredentialAssignmentModel)
                    .where(
                        DeploymentEventTransportCredentialAssignmentModel.assignment_id
                        == attempt_seed.assignment_id
                    )
                    .order_by(
                        DeploymentEventTransportCredentialAssignmentModel.rotation_epoch,
                        DeploymentEventTransportCredentialAssignmentModel.credential_generation,
                        DeploymentEventTransportCredentialAssignmentModel.assignment_revision,
                    )
                    .with_for_update()
                )
            ).all()
        )
        try:
            head = select_deployment_physical_transport_credential_assignment_head(
                tuple(self._credential_assignment_from_row(row) for row in assignment_rows)
            )
        except (ValueError, WorkflowTransportCredentialAssignmentSnapshotError):
            head = None
        freshness_row = cast(
            WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel)
                .where(
                    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel.freshness_admission_id
                    == attempt_seed.freshness_admission_id
                )
                .with_for_update()
            ),
        )
        lease_row = cast(
            WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel)
                .where(
                    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel.authorization_lease_id
                    == lease_seed.authorization_lease_id
                )
                .with_for_update()
            ),
        )
        return binding_row, snapshot_row, head, freshness_row, lease_row

    async def _credential_materialization_claim_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowEventPhysicalTransportCredentialMaterializationClaimRequest,
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationClaimResult | None:
        statuses = WorkflowEventPhysicalTransportCredentialMaterializationClaimStatus
        row = await self._load_credential_materialization_claim_row(
            session, authorization_lease_id=request.authorization_lease_id
        )
        if row is None:
            idempotency_row = cast(
                WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaimModel | None,
                await session.scalar(
                    select(
                        WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaimModel
                    ).where(
                        WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaimModel.idempotency_digest
                        == request.idempotency_digest
                    )
                ),
            )
            if idempotency_row is None:
                return None
            return WorkflowEventPhysicalTransportCredentialMaterializationClaimResult(
                statuses.IDEMPOTENCY_CONFLICT, None, None, None
            )
        claim = self._credential_materialization_claim_from_row(row)
        attempt_row = await self._load_credential_materialization_attempt_row(
            session, authorization_lease_id=request.authorization_lease_id
        )
        attempt = (
            None
            if attempt_row is None
            else self._credential_materialization_attempt_from_row(attempt_row)
        )
        result_row = await self._load_credential_materialization_result_row(
            session, authorization_lease_id=request.authorization_lease_id
        )
        result = (
            None
            if result_row is None
            else self._credential_materialization_result_from_row(result_row)
        )
        exact = bool(
            claim.claim_id == request.claim_id
            and claim.attempt_id == request.attempt_id
            and claim.materialization_id == request.materialization_id
            and claim.authorization_lease_digest == request.authorization_lease_digest
            and claim.scope == request.scope
            and claim.accessor_subject_id == request.accessor_subject_id
            and claim.request_fingerprint == request.request_fingerprint
            and claim.idempotency_digest == request.idempotency_digest
        )
        if exact:
            return WorkflowEventPhysicalTransportCredentialMaterializationClaimResult(
                statuses.REPLAY_COMPLETED if result is not None else statuses.CLAIM_ONLY_UNCERTAIN,
                claim,
                attempt,
                result,
            )
        status = (
            statuses.IDEMPOTENCY_CONFLICT
            if claim.idempotency_digest == request.idempotency_digest
            else statuses.ALREADY_CONSUMED
        )
        return WorkflowEventPhysicalTransportCredentialMaterializationClaimResult(
            status, None, None, None
        )

    @staticmethod
    async def _load_credential_materialization_claim_row(
        session: AsyncSession, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaimModel | None:
        return cast(
            WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaimModel | None,
            await session.scalar(
                select(
                    WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaimModel
                ).where(
                    WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaimModel.authorization_lease_id
                    == authorization_lease_id
                )
            ),
        )

    @staticmethod
    async def _load_credential_materialization_attempt_row(
        session: AsyncSession, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationAttemptModel | None:
        return cast(
            WorkflowEventPhysicalTransportCredentialMaterializationAttemptModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportCredentialMaterializationAttemptModel).where(
                    WorkflowEventPhysicalTransportCredentialMaterializationAttemptModel.authorization_lease_id
                    == authorization_lease_id
                )
            ),
        )

    @staticmethod
    async def _load_credential_materialization_result_row(
        session: AsyncSession, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationResultModel | None:
        return cast(
            WorkflowEventPhysicalTransportCredentialMaterializationResultModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportCredentialMaterializationResultModel).where(
                    WorkflowEventPhysicalTransportCredentialMaterializationResultModel.authorization_lease_id
                    == authorization_lease_id
                )
            ),
        )

    @classmethod
    def _credential_materialization_evidence_matches(
        cls,
        binding_row: WorkflowEventPhysicalTransportCredentialAssignmentBindingModel | None,
        snapshot_row: EventPhysicalTransportCredentialAssignmentSnapshotModel | None,
        head: DeploymentPhysicalTransportCredentialAssignment | None,
        freshness_row: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel
        | None,
        lease_row: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel | None,
        *,
        request: WorkflowEventPhysicalTransportCredentialMaterializationClaimRequest,
        observed_at: datetime,
    ) -> bool:
        if any(
            value is None for value in (binding_row, snapshot_row, head, freshness_row, lease_row)
        ):
            return False
        assert binding_row is not None
        assert snapshot_row is not None
        assert head is not None
        assert freshness_row is not None
        assert lease_row is not None
        try:
            binding = cls._credential_assignment_binding_from_row(binding_row)
            snapshot = cls._credential_assignment_snapshot_from_row(snapshot_row)
            freshness = cls._credential_assignment_freshness_admission_from_row(freshness_row)
            lease = cls._credential_access_lease_from_row(lease_row)
        except Exception:
            return False
        policy = code_owned_workflow_event_physical_transport_credential_materialization_policy()
        return bool(
            lease.issued_at <= observed_at < lease.valid_until
            and freshness.evaluated_at <= observed_at < freshness.valid_until
            and lease.authorization_lease_id == request.authorization_lease_id
            and lease.canonical_digest == request.authorization_lease_digest
            and lease.freshness_admission_id
            == freshness.freshness_admission_id
            == request.expected_freshness_admission_id
            and lease.freshness_admission_digest
            == freshness.canonical_digest
            == request.expected_freshness_admission_digest
            and freshness.valid_until == request.expected_freshness_valid_until
            and lease.physical_transport_credential_assignment_binding_id
            == freshness.physical_transport_credential_assignment_binding_id
            == binding.binding_id
            == request.expected_credential_assignment_binding_id
            and lease.physical_transport_credential_assignment_binding_digest
            == freshness.physical_transport_credential_assignment_binding_digest
            == binding.canonical_digest
            == request.expected_credential_assignment_binding_digest
            and lease.credential_assignment_snapshot_id
            == freshness.credential_assignment_snapshot_id
            == binding.credential_assignment_snapshot_id
            == snapshot.snapshot_id
            == request.expected_credential_assignment_snapshot_id
            and lease.credential_assignment_snapshot_digest
            == freshness.credential_assignment_snapshot_digest
            == binding.credential_assignment_snapshot_digest
            == snapshot.canonical_digest
            == request.expected_credential_assignment_snapshot_digest
            and lease.assignment_id
            == freshness.assignment_id
            == snapshot.assignment_id
            == head.assignment_id
            == request.expected_assignment_id
            and lease.assignment_revision
            == freshness.assignment_revision
            == snapshot.assignment_revision
            == head.assignment_revision
            == request.expected_assignment_revision
            and lease.source_assignment_digest
            == freshness.source_assignment_digest
            == snapshot.source_assignment_digest
            == head.canonical_digest
            == request.expected_source_assignment_digest
            and lease.credential_generation
            == freshness.credential_generation
            == snapshot.credential_generation
            == head.credential_generation
            == request.expected_credential_generation
            and lease.rotation_epoch
            == freshness.rotation_epoch
            == snapshot.rotation_epoch
            == head.rotation_epoch
            == request.expected_rotation_epoch
            and lease.assignment_activated_at
            == freshness.assignment_activated_at
            == snapshot.activated_at
            == head.activated_at
            == request.expected_assignment_activated_at
            and lease.assignment_expires_at
            == freshness.assignment_expires_at
            == snapshot.expires_at
            == head.expires_at
            == request.expected_assignment_expires_at
            and lease.assignment_active
            == freshness.assignment_active
            == head.active
            == request.expected_assignment_active
            is True
            and lease.assignment_non_revoked
            == freshness.assignment_non_revoked
            == snapshot.source_non_revoked
            is True
            and head.revoked == request.expected_assignment_revoked is False
            and lease.scope
            == freshness.scope
            == binding.scope
            == snapshot.scope
            == head.scope
            == request.scope
            and lease.accessor_subject_id == request.accessor_subject_id
            and lease.state.value == request.expected_lease_state == "authorized_unconsumed"
            and lease.authority.credential_access_authorized
            == request.expected_credential_access_authorized
            is True
            and not any(
                value is not False
                for name, value in lease.authority.canonical_value().items()
                if name != "credential_access_authorized"
            )
            and not any(
                value is not False for value in freshness.authority.canonical_value().values()
            )
            and not any(
                value is not False for value in binding.authority.canonical_value().values()
            )
            and not any(
                value is not False for value in snapshot.authority.canonical_value().values()
            )
            and policy.policy_id == request.expected_materialization_policy_id
            and policy.policy_version == request.expected_materialization_policy_version
            and policy.canonical_digest == request.expected_materialization_policy_digest
            and request.irreversible_consumption_acknowledged
            and request.uncertain_outcome_requires_new_authorization_acknowledged
        )

    @classmethod
    def _credential_materialization_result_evidence_matches(
        cls,
        binding_row: WorkflowEventPhysicalTransportCredentialAssignmentBindingModel | None,
        snapshot_row: EventPhysicalTransportCredentialAssignmentSnapshotModel | None,
        head: DeploymentPhysicalTransportCredentialAssignment | None,
        freshness_row: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel
        | None,
        lease_row: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel | None,
        *,
        claim_row: WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaimModel | None,
        attempt_row: WorkflowEventPhysicalTransportCredentialMaterializationAttemptModel | None,
        request: WorkflowEventPhysicalTransportCredentialMaterializationResultRequest,
        observed_at: datetime,
    ) -> bool:
        if any(
            value is None
            for value in (
                binding_row,
                snapshot_row,
                head,
                freshness_row,
                lease_row,
                claim_row,
                attempt_row,
            )
        ):
            return False
        assert binding_row is not None
        assert snapshot_row is not None
        assert head is not None
        assert freshness_row is not None
        assert lease_row is not None
        assert claim_row is not None
        assert attempt_row is not None
        try:
            binding = cls._credential_assignment_binding_from_row(binding_row)
            snapshot = cls._credential_assignment_snapshot_from_row(snapshot_row)
            freshness = cls._credential_assignment_freshness_admission_from_row(freshness_row)
            lease = cls._credential_access_lease_from_row(lease_row)
            claim = cls._credential_materialization_claim_from_row(claim_row)
            attempt = cls._credential_materialization_attempt_from_row(attempt_row)
        except Exception:
            return False
        result = request.result
        policy = code_owned_workflow_event_physical_transport_credential_materialization_policy()
        return bool(
            lease.issued_at <= result.completed_at < lease.valid_until
            and freshness.evaluated_at <= result.completed_at < freshness.valid_until
            and result.completed_at < lease.valid_until
            and result.completed_at < freshness.valid_until
            and (result.usable_until is None or result.usable_until <= lease.valid_until)
            and request.expected_lease_valid_until == lease.valid_until
            and claim.canonical_digest == request.expected_claim_digest
            and attempt.canonical_digest == request.expected_attempt_digest
            and result.consumption_claim_id == claim.claim_id == attempt.consumption_claim_id
            and result.consumption_claim_digest == claim.canonical_digest
            and result.attempt_id == attempt.attempt_id
            and result.attempt_digest == attempt.canonical_digest
            and result.materialization_id == claim.materialization_id == attempt.materialization_id
            and result.authorization_lease_id
            == claim.authorization_lease_id
            == attempt.authorization_lease_id
            == lease.authorization_lease_id
            and result.authorization_lease_digest
            == claim.authorization_lease_digest
            == attempt.authorization_lease_digest
            == lease.canonical_digest
            and result.freshness_admission_id
            == claim.freshness_admission_id
            == attempt.freshness_admission_id
            == freshness.freshness_admission_id
            and result.freshness_admission_digest
            == claim.freshness_admission_digest
            == attempt.freshness_admission_digest
            == freshness.canonical_digest
            and attempt.physical_transport_credential_assignment_binding_id == binding.binding_id
            and attempt.physical_transport_credential_assignment_binding_digest
            == binding.canonical_digest
            and result.credential_assignment_snapshot_id
            == attempt.credential_assignment_snapshot_id
            == snapshot.snapshot_id
            and result.credential_assignment_snapshot_digest
            == attempt.credential_assignment_snapshot_digest
            == snapshot.canonical_digest
            and result.assignment_id
            == attempt.assignment_id
            == head.assignment_id
            == request.expected_assignment_id
            and result.assignment_revision
            == attempt.assignment_revision
            == head.assignment_revision
            == request.expected_assignment_revision
            and attempt.source_assignment_digest
            == head.canonical_digest
            == request.expected_source_assignment_digest
            and result.credential_generation
            == attempt.credential_generation
            == head.credential_generation
            == request.expected_credential_generation
            and result.rotation_epoch
            == attempt.rotation_epoch
            == head.rotation_epoch
            == request.expected_rotation_epoch
            and head.active
            and not head.revoked
            and head.activated_at <= observed_at < head.expires_at
            and result.scope
            == claim.scope
            == attempt.scope
            == lease.scope
            == freshness.scope
            == binding.scope
            == snapshot.scope
            == head.scope
            and result.accessor_subject_id
            == claim.accessor_subject_id
            == attempt.accessor_subject_id
            == lease.accessor_subject_id
            and result.policy_id == attempt.policy_id == policy.policy_id
            and result.policy_version == attempt.policy_version == policy.policy_version
            and result.policy_digest == attempt.policy_digest == policy.canonical_digest
            and not any(value is not False for value in result.authority.canonical_value().values())
        )

    async def _lock_endpoint_materialization_sources(
        self,
        session: AsyncSession,
        *,
        request: WorkflowEventPhysicalTransportEndpointMaterializationClaimRequest,
    ) -> tuple[
        WorkflowEventPhysicalTransportRouteBindingModel | None,
        EventPhysicalTransportRouteSnapshotModel | None,
        DeploymentEventTransportRouteSelectionHeadModel | None,
        WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel | None,
        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel | None,
    ]:
        binding_row = cast(
            WorkflowEventPhysicalTransportRouteBindingModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportRouteBindingModel)
                .where(
                    WorkflowEventPhysicalTransportRouteBindingModel.binding_id
                    == request.expected_physical_transport_route_binding_id
                )
                .with_for_update()
            ),
        )
        route_row = cast(
            EventPhysicalTransportRouteSnapshotModel | None,
            await session.scalar(
                select(EventPhysicalTransportRouteSnapshotModel)
                .where(
                    EventPhysicalTransportRouteSnapshotModel.snapshot_id
                    == request.expected_transport_route_snapshot_id
                )
                .with_for_update()
            ),
        )
        head_rows = (
            await session.scalars(
                select(DeploymentEventTransportRouteSelectionHeadModel)
                .where(
                    DeploymentEventTransportRouteSelectionHeadModel.organization_id
                    == request.scope.organization_id,
                    DeploymentEventTransportRouteSelectionHeadModel.environment_id
                    == request.scope.environment_id,
                    DeploymentEventTransportRouteSelectionHeadModel.site_id
                    == request.scope.site_id,
                    DeploymentEventTransportRouteSelectionHeadModel.route_set_id
                    == request.expected_route_set_id,
                    DeploymentEventTransportRouteSelectionHeadModel.current.is_(True),
                )
                .limit(2)
                .with_for_update()
            )
        ).all()
        head_row = head_rows[0] if len(head_rows) == 1 else None
        freshness_row = cast(
            WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel)
                .where(
                    WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel.freshness_admission_id
                    == request.expected_freshness_admission_id
                )
                .with_for_update()
            ),
        )
        lease_row = cast(
            WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel)
                .where(
                    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel.authorization_lease_id
                    == request.authorization_lease_id
                )
                .with_for_update()
            ),
        )
        return binding_row, route_row, head_row, freshness_row, lease_row

    async def _lock_endpoint_materialization_result_sources(
        self,
        session: AsyncSession,
        *,
        attempt_seed: WorkflowEventPhysicalTransportEndpointMaterializationAttemptModel,
        lease_seed: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel,
    ) -> tuple[
        WorkflowEventPhysicalTransportRouteBindingModel | None,
        EventPhysicalTransportRouteSnapshotModel | None,
        DeploymentEventTransportRouteSelectionHeadModel | None,
        WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel | None,
        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel | None,
    ]:
        binding_row = cast(
            WorkflowEventPhysicalTransportRouteBindingModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportRouteBindingModel)
                .where(
                    WorkflowEventPhysicalTransportRouteBindingModel.binding_id
                    == attempt_seed.physical_transport_route_binding_id
                )
                .with_for_update()
            ),
        )
        route_row = cast(
            EventPhysicalTransportRouteSnapshotModel | None,
            await session.scalar(
                select(EventPhysicalTransportRouteSnapshotModel)
                .where(
                    EventPhysicalTransportRouteSnapshotModel.snapshot_id
                    == attempt_seed.transport_route_snapshot_id
                )
                .with_for_update()
            ),
        )
        head_rows = (
            await session.scalars(
                select(DeploymentEventTransportRouteSelectionHeadModel)
                .where(
                    DeploymentEventTransportRouteSelectionHeadModel.organization_id
                    == attempt_seed.organization_id,
                    DeploymentEventTransportRouteSelectionHeadModel.environment_id
                    == attempt_seed.environment_id,
                    DeploymentEventTransportRouteSelectionHeadModel.site_id == attempt_seed.site_id,
                    DeploymentEventTransportRouteSelectionHeadModel.route_set_id
                    == lease_seed.route_set_id,
                    DeploymentEventTransportRouteSelectionHeadModel.current.is_(True),
                )
                .limit(2)
                .with_for_update()
            )
        ).all()
        head_row = head_rows[0] if len(head_rows) == 1 else None
        freshness_row = cast(
            WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel)
                .where(
                    WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel.freshness_admission_id
                    == attempt_seed.freshness_admission_id
                )
                .with_for_update()
            ),
        )
        lease_row = cast(
            WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel)
                .where(
                    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel.authorization_lease_id
                    == attempt_seed.authorization_lease_id
                )
                .with_for_update()
            ),
        )
        return binding_row, route_row, head_row, freshness_row, lease_row

    async def _endpoint_materialization_claim_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowEventPhysicalTransportEndpointMaterializationClaimRequest,
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationClaimResult | None:
        claim_status = WorkflowEventPhysicalTransportEndpointMaterializationClaimStatus
        row = await self._load_endpoint_materialization_claim_row(
            session, authorization_lease_id=request.authorization_lease_id
        )
        if row is None:
            idempotency_row = cast(
                WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaimModel | None,
                await session.scalar(
                    select(
                        WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaimModel
                    ).where(
                        WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaimModel.idempotency_digest
                        == request.idempotency_digest
                    )
                ),
            )
            if idempotency_row is None:
                return None
            return WorkflowEventPhysicalTransportEndpointMaterializationClaimResult(
                WorkflowEventPhysicalTransportEndpointMaterializationClaimStatus.IDEMPOTENCY_CONFLICT,
                None,
                None,
                None,
            )
        claim = self._endpoint_materialization_claim_from_row(row)
        attempt_row = await self._load_endpoint_materialization_attempt_row(
            session, authorization_lease_id=request.authorization_lease_id
        )
        attempt = (
            None
            if attempt_row is None
            else self._endpoint_materialization_attempt_from_row(attempt_row)
        )
        result_row = await self._load_endpoint_materialization_result_row(
            session, authorization_lease_id=request.authorization_lease_id
        )
        result = (
            None
            if result_row is None
            else self._endpoint_materialization_result_from_row(result_row)
        )
        exact = bool(
            claim.claim_id == request.claim_id
            and claim.attempt_id == request.attempt_id
            and claim.materialization_id == request.materialization_id
            and claim.authorization_lease_digest == request.authorization_lease_digest
            and claim.scope == request.scope
            and claim.resolver_subject_id == request.resolver_subject_id
            and claim.request_fingerprint == request.request_fingerprint
            and claim.idempotency_digest == request.idempotency_digest
        )
        if exact:
            status = claim_status.CLAIM_ONLY_UNCERTAIN
            if result is not None:
                status = claim_status.REPLAY_COMPLETED
            return WorkflowEventPhysicalTransportEndpointMaterializationClaimResult(
                status,
                claim,
                attempt,
                result,
            )
        status = (
            WorkflowEventPhysicalTransportEndpointMaterializationClaimStatus.IDEMPOTENCY_CONFLICT
            if claim.idempotency_digest == request.idempotency_digest
            else WorkflowEventPhysicalTransportEndpointMaterializationClaimStatus.ALREADY_CONSUMED
        )
        return WorkflowEventPhysicalTransportEndpointMaterializationClaimResult(
            status,
            None,
            None,
            None,
        )

    @staticmethod
    async def _load_endpoint_materialization_claim_row(
        session: AsyncSession, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaimModel | None:
        return cast(
            WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaimModel | None,
            await session.scalar(
                select(
                    WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaimModel
                ).where(
                    WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaimModel.authorization_lease_id
                    == authorization_lease_id
                )
            ),
        )

    @staticmethod
    async def _load_endpoint_materialization_attempt_row(
        session: AsyncSession, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationAttemptModel | None:
        return cast(
            WorkflowEventPhysicalTransportEndpointMaterializationAttemptModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportEndpointMaterializationAttemptModel).where(
                    WorkflowEventPhysicalTransportEndpointMaterializationAttemptModel.authorization_lease_id
                    == authorization_lease_id
                )
            ),
        )

    @staticmethod
    async def _load_endpoint_materialization_result_row(
        session: AsyncSession, *, authorization_lease_id: str
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationResultModel | None:
        return cast(
            WorkflowEventPhysicalTransportEndpointMaterializationResultModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportEndpointMaterializationResultModel).where(
                    WorkflowEventPhysicalTransportEndpointMaterializationResultModel.authorization_lease_id
                    == authorization_lease_id
                )
            ),
        )

    @classmethod
    def _endpoint_materialization_evidence_matches(
        cls,
        binding_row: WorkflowEventPhysicalTransportRouteBindingModel | None,
        route_row: EventPhysicalTransportRouteSnapshotModel | None,
        head_row: DeploymentEventTransportRouteSelectionHeadModel | None,
        freshness_row: WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel | None,
        lease_row: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel | None,
        *,
        request: WorkflowEventPhysicalTransportEndpointMaterializationClaimRequest,
        observed_at: datetime,
    ) -> bool:
        if any(row is None for row in (binding_row, route_row, head_row, freshness_row, lease_row)):
            return False
        assert binding_row is not None
        assert route_row is not None
        assert head_row is not None
        assert freshness_row is not None
        assert lease_row is not None
        try:
            binding = cls._physical_transport_route_binding_from_row(binding_row)
            route = cls._transport_route_snapshot_from_row(route_row)
            head = cls._route_selection_head_from_row(head_row)
            freshness = cls._route_freshness_admission_from_row(freshness_row)
            lease = cls._endpoint_resolution_authorization_lease_from_row(lease_row)
        except Exception:
            return False
        policy = code_owned_workflow_event_physical_transport_endpoint_materialization_policy()
        return bool(
            observed_at < freshness.valid_until
            and observed_at < lease.valid_until
            and freshness.valid_until == request.expected_freshness_valid_until
            and lease.authorization_lease_id == request.authorization_lease_id
            and lease.canonical_digest == request.authorization_lease_digest
            and lease.freshness_admission_id
            == freshness.freshness_admission_id
            == request.expected_freshness_admission_id
            and lease.freshness_admission_digest
            == freshness.canonical_digest
            == request.expected_freshness_admission_digest
            and lease.physical_transport_route_binding_id
            == binding.binding_id
            == request.expected_physical_transport_route_binding_id
            and lease.physical_transport_route_binding_digest
            == binding.canonical_digest
            == request.expected_physical_transport_route_binding_digest
            and lease.transport_route_snapshot_id
            == route.snapshot_id
            == request.expected_transport_route_snapshot_id
            and lease.transport_route_snapshot_digest
            == route.canonical_digest
            == request.expected_transport_route_snapshot_digest
            and lease.current_selection_head_id
            == head.head_id
            == request.expected_current_selection_head_id
            and lease.current_selection_head_digest
            == head.canonical_digest
            == request.expected_current_selection_head_digest
            and lease.current_selection_head_generation
            == head.generation
            == request.expected_current_selection_head_generation
            and lease.current_selection_head_fencing_token_digest
            == head.fencing_token_digest
            == request.expected_current_selection_head_fencing_token_digest
            and lease.route_set_id
            == route.route_set_id
            == head.route_set_id
            == request.expected_route_set_id
            and lease.route_set_revision
            == route.route_set_revision
            == head.route_set_revision
            == request.expected_route_set_revision
            and lease.selection_epoch_id
            == route.selection_epoch_id
            == head.selection_epoch_id
            == request.expected_selection_epoch_id
            and lease.selection_epoch_revision
            == route.selection_epoch_revision
            == head.selection_epoch_revision
            == request.expected_selection_epoch_revision
            and lease.selected_route_id
            == route.route_id
            == head.selected_route_id
            == request.expected_selected_route_id
            and lease.selected_route_revision
            == route.route_revision
            == head.selected_route_revision
            == request.expected_selected_route_revision
            and lease.selected_route_digest
            == route.source_route_digest
            == head.selected_route_digest
            == request.expected_selected_route_digest
            and head.current
            and lease.selection_active
            == head.selection_active
            == request.expected_selection_active
            is True
            and lease.selection_eligible
            == head.selection_eligible
            == request.expected_selection_eligible
            is True
            and lease.selection_suspended
            == head.selection_suspended
            == request.expected_selection_suspended
            is False
            and lease.selection_withdrawn
            == head.selection_withdrawn
            == request.expected_selection_withdrawn
            is False
            and lease.selection_superseded
            == head.selection_superseded
            == request.expected_selection_superseded
            is False
            and lease.state.value == request.expected_lease_state == "authorized_unconsumed"
            and lease.authority.endpoint_resolution_authorized
            == request.expected_endpoint_resolution_authorized
            is True
            and not any(
                value
                for key, value in lease.authority.canonical_value().items()
                if key != "endpoint_resolution_authorized"
            )
            and binding.scope
            == route.scope
            == head.scope
            == freshness.scope
            == lease.scope
            == request.scope
            and lease.resolver_subject_id == request.resolver_subject_id
            and policy.policy_id == request.expected_materialization_policy_id
            and policy.policy_version == request.expected_materialization_policy_version
            and policy.canonical_digest == request.expected_materialization_policy_digest
            and request.irreversible_consumption_acknowledged
            and request.uncertain_outcome_requires_new_authorization_acknowledged
        )

    @classmethod
    def _endpoint_materialization_result_evidence_matches(
        cls,
        binding_row: WorkflowEventPhysicalTransportRouteBindingModel | None,
        route_row: EventPhysicalTransportRouteSnapshotModel | None,
        head_row: DeploymentEventTransportRouteSelectionHeadModel | None,
        freshness_row: WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel | None,
        lease_row: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel | None,
        *,
        claim_row: WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaimModel
        | None,
        attempt_row: WorkflowEventPhysicalTransportEndpointMaterializationAttemptModel | None,
        request: WorkflowEventPhysicalTransportEndpointMaterializationResultRequest,
        observed_at: datetime,
    ) -> bool:
        if any(
            row is None
            for row in (
                binding_row,
                route_row,
                head_row,
                freshness_row,
                lease_row,
                claim_row,
                attempt_row,
            )
        ):
            return False
        assert binding_row is not None
        assert route_row is not None
        assert head_row is not None
        assert freshness_row is not None
        assert lease_row is not None
        assert claim_row is not None
        assert attempt_row is not None
        try:
            binding = cls._physical_transport_route_binding_from_row(binding_row)
            route = cls._transport_route_snapshot_from_row(route_row)
            head = cls._route_selection_head_from_row(head_row)
            freshness = cls._route_freshness_admission_from_row(freshness_row)
            lease = cls._endpoint_resolution_authorization_lease_from_row(lease_row)
            claim = cls._endpoint_materialization_claim_from_row(claim_row)
            attempt = cls._endpoint_materialization_attempt_from_row(attempt_row)
        except Exception:
            return False
        result = request.result
        return bool(
            observed_at < freshness.valid_until
            and observed_at < lease.valid_until
            and result.completed_at < freshness.valid_until
            and result.completed_at < lease.valid_until
            and request.expected_lease_valid_until == lease.valid_until
            and claim.canonical_digest == request.expected_claim_digest
            and attempt.canonical_digest == request.expected_attempt_digest
            and result.consumption_claim_id == claim.claim_id == attempt.consumption_claim_id
            and result.consumption_claim_digest == claim.canonical_digest
            and result.attempt_id == attempt.attempt_id
            and result.attempt_digest == attempt.canonical_digest
            and result.materialization_id == claim.materialization_id == attempt.materialization_id
            and result.authorization_lease_id
            == claim.authorization_lease_id
            == attempt.authorization_lease_id
            == lease.authorization_lease_id
            and result.authorization_lease_digest == lease.canonical_digest
            and result.freshness_admission_id
            == attempt.freshness_admission_id
            == freshness.freshness_admission_id
            and result.freshness_admission_digest == freshness.canonical_digest
            and result.transport_route_snapshot_id == attempt.transport_route_snapshot_id
            and result.transport_route_snapshot_digest == attempt.transport_route_snapshot_digest
            and attempt.physical_transport_route_binding_id == binding.binding_id
            and attempt.physical_transport_route_binding_digest == binding.canonical_digest
            and attempt.transport_route_snapshot_id == route.snapshot_id
            and attempt.transport_route_snapshot_digest == route.canonical_digest
            and result.scope == claim.scope == attempt.scope == lease.scope
            and result.resolver_subject_id
            == claim.resolver_subject_id
            == attempt.resolver_subject_id
            == lease.resolver_subject_id
            and result.policy_id == attempt.policy_id
            and result.policy_version == attempt.policy_version
            and result.policy_digest == attempt.policy_digest
            and head.head_id
            == attempt.current_selection_head_id
            == lease.current_selection_head_id
            == request.expected_current_selection_head_id
            and head.canonical_digest
            == attempt.current_selection_head_digest
            == lease.current_selection_head_digest
            == request.expected_current_selection_head_digest
            and head.generation
            == attempt.current_selection_head_generation
            == lease.current_selection_head_generation
            == request.expected_current_selection_head_generation
            and head.fencing_token_digest
            == attempt.current_selection_head_fencing_token_digest
            == lease.current_selection_head_fencing_token_digest
            == request.expected_current_selection_head_fencing_token_digest
            and head.current
            and head.selection_active
            and head.selection_eligible
            and not head.selection_suspended
            and not head.selection_withdrawn
            and not head.selection_superseded
            and route.route_set_id == head.route_set_id == lease.route_set_id
            and route.route_set_revision == head.route_set_revision == lease.route_set_revision
            and route.selection_epoch_id == head.selection_epoch_id == lease.selection_epoch_id
            and route.selection_epoch_revision
            == head.selection_epoch_revision
            == lease.selection_epoch_revision
            and route.route_id == head.selected_route_id == lease.selected_route_id
            and route.route_revision
            == head.selected_route_revision
            == lease.selected_route_revision
            and route.source_route_digest
            == head.selected_route_digest
            == lease.selected_route_digest
        )

    @classmethod
    def _credential_materialization_claim(
        cls,
        request: WorkflowEventPhysicalTransportCredentialMaterializationClaimRequest,
        *,
        claimed_at: datetime,
    ) -> WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaim:
        values: dict[str, Any] = {
            "claim_id": request.claim_id,
            "authorization_lease_id": request.authorization_lease_id,
            "authorization_lease_digest": request.authorization_lease_digest,
            "freshness_admission_id": request.expected_freshness_admission_id,
            "freshness_admission_digest": request.expected_freshness_admission_digest,
            "attempt_id": request.attempt_id,
            "materialization_id": request.materialization_id,
            "scope": request.scope,
            "accessor_subject_id": request.accessor_subject_id,
            "claimed_at": claimed_at,
            "request_fingerprint": request.request_fingerprint,
            "idempotency_digest": request.idempotency_digest,
            "authority": WorkflowEventPhysicalTransportCredentialMaterializationAuthority(),
        }
        payload = cls._credential_materialization_digest_payload(values)
        return WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaim(
            **values, canonical_digest=canonical_digest(payload)
        )

    @classmethod
    def _credential_materialization_attempt(
        cls,
        request: WorkflowEventPhysicalTransportCredentialMaterializationClaimRequest,
        *,
        claim: WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaim,
        started_at: datetime,
        lease_valid_until: datetime,
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationAttempt:
        values: dict[str, Any] = {
            "attempt_id": request.attempt_id,
            "materialization_id": request.materialization_id,
            "consumption_claim_id": claim.claim_id,
            "authorization_lease_id": request.authorization_lease_id,
            "authorization_lease_digest": request.authorization_lease_digest,
            "freshness_admission_id": request.expected_freshness_admission_id,
            "freshness_admission_digest": request.expected_freshness_admission_digest,
            "physical_transport_credential_assignment_binding_id": (
                request.expected_credential_assignment_binding_id
            ),
            "physical_transport_credential_assignment_binding_digest": (
                request.expected_credential_assignment_binding_digest
            ),
            "credential_assignment_snapshot_id": request.expected_credential_assignment_snapshot_id,
            "credential_assignment_snapshot_digest": (
                request.expected_credential_assignment_snapshot_digest
            ),
            "assignment_id": request.expected_assignment_id,
            "assignment_revision": request.expected_assignment_revision,
            "source_assignment_digest": request.expected_source_assignment_digest,
            "credential_generation": request.expected_credential_generation,
            "rotation_epoch": request.expected_rotation_epoch,
            "scope": request.scope,
            "accessor_subject_id": request.accessor_subject_id,
            "policy_id": request.expected_materialization_policy_id,
            "policy_version": request.expected_materialization_policy_version,
            "policy_digest": request.expected_materialization_policy_digest,
            "started_at": started_at,
            "freshness_valid_until": request.expected_freshness_valid_until,
            "lease_valid_until": lease_valid_until,
            "state": (
                WorkflowEventPhysicalTransportCredentialMaterializationAttemptState
            ).MATERIALIZATION_STARTED,
            "authority": WorkflowEventPhysicalTransportCredentialMaterializationAuthority(),
        }
        payload = cls._credential_materialization_digest_payload(values)
        return WorkflowEventPhysicalTransportCredentialMaterializationAttempt(
            **values, canonical_digest=canonical_digest(payload)
        )

    @staticmethod
    def _credential_materialization_digest_payload(values: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value.canonical_value()
            if isinstance(
                value,
                (WorkflowScope, WorkflowEventPhysicalTransportCredentialMaterializationAuthority),
            )
            else value.value
            if isinstance(value, Enum)
            else value.isoformat()
            if isinstance(value, datetime)
            else value
            for key, value in values.items()
        }

    @staticmethod
    def _credential_materialization_payload(
        evidence: WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaim
        | WorkflowEventPhysicalTransportCredentialMaterializationAttempt
        | WorkflowEventPhysicalTransportCredentialMaterializationResult,
    ) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            {**evidence.digest_payload(), "canonical_digest": evidence.canonical_digest},
        )

    @staticmethod
    def _credential_materialization_authority_columns(
        authority: WorkflowEventPhysicalTransportCredentialMaterializationAuthority,
    ) -> dict[str, bool]:
        return {
            f"{name.removesuffix('_authorized')}_authority_granted": value
            for name, value in authority.canonical_value().items()
        }

    @classmethod
    def _credential_materialization_claim_model(
        cls, claim: WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaim
    ) -> WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaimModel:
        return WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaimModel(
            claim_id=claim.claim_id,
            authorization_lease_id=claim.authorization_lease_id,
            authorization_lease_digest=claim.authorization_lease_digest,
            freshness_admission_id=claim.freshness_admission_id,
            freshness_admission_digest=claim.freshness_admission_digest,
            attempt_id=claim.attempt_id,
            materialization_id=claim.materialization_id,
            organization_id=claim.scope.organization_id,
            environment_id=claim.scope.environment_id,
            site_id=claim.scope.site_id,
            accessor_subject_id=claim.accessor_subject_id,
            claimed_at=claim.claimed_at,
            request_fingerprint=claim.request_fingerprint,
            idempotency_digest=claim.idempotency_digest,
            **cls._credential_materialization_authority_columns(claim.authority),
            canonical_digest=claim.canonical_digest,
            payload=cls._credential_materialization_payload(claim),
        )

    @classmethod
    def _credential_materialization_attempt_model(
        cls, attempt: WorkflowEventPhysicalTransportCredentialMaterializationAttempt
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationAttemptModel:
        return WorkflowEventPhysicalTransportCredentialMaterializationAttemptModel(
            attempt_id=attempt.attempt_id,
            materialization_id=attempt.materialization_id,
            consumption_claim_id=attempt.consumption_claim_id,
            authorization_lease_id=attempt.authorization_lease_id,
            authorization_lease_digest=attempt.authorization_lease_digest,
            freshness_admission_id=attempt.freshness_admission_id,
            freshness_admission_digest=attempt.freshness_admission_digest,
            physical_transport_credential_assignment_binding_id=(
                attempt.physical_transport_credential_assignment_binding_id
            ),
            physical_transport_credential_assignment_binding_digest=(
                attempt.physical_transport_credential_assignment_binding_digest
            ),
            credential_assignment_snapshot_id=attempt.credential_assignment_snapshot_id,
            credential_assignment_snapshot_digest=attempt.credential_assignment_snapshot_digest,
            assignment_id=attempt.assignment_id,
            assignment_revision=attempt.assignment_revision,
            source_assignment_digest=attempt.source_assignment_digest,
            credential_generation=attempt.credential_generation,
            rotation_epoch=attempt.rotation_epoch,
            organization_id=attempt.scope.organization_id,
            environment_id=attempt.scope.environment_id,
            site_id=attempt.scope.site_id,
            accessor_subject_id=attempt.accessor_subject_id,
            policy_id=attempt.policy_id,
            policy_version=attempt.policy_version,
            policy_digest=attempt.policy_digest,
            started_at=attempt.started_at,
            freshness_valid_until=attempt.freshness_valid_until,
            lease_valid_until=attempt.lease_valid_until,
            state=attempt.state.value,
            **cls._credential_materialization_authority_columns(attempt.authority),
            canonical_digest=attempt.canonical_digest,
            payload=cls._credential_materialization_payload(attempt),
        )

    @classmethod
    def _credential_materialization_result_model(
        cls, result: WorkflowEventPhysicalTransportCredentialMaterializationResult
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationResultModel:
        return WorkflowEventPhysicalTransportCredentialMaterializationResultModel(
            materialization_id=result.materialization_id,
            attempt_id=result.attempt_id,
            attempt_digest=result.attempt_digest,
            consumption_claim_id=result.consumption_claim_id,
            consumption_claim_digest=result.consumption_claim_digest,
            authorization_lease_id=result.authorization_lease_id,
            authorization_lease_digest=result.authorization_lease_digest,
            freshness_admission_id=result.freshness_admission_id,
            freshness_admission_digest=result.freshness_admission_digest,
            credential_assignment_snapshot_id=result.credential_assignment_snapshot_id,
            credential_assignment_snapshot_digest=result.credential_assignment_snapshot_digest,
            assignment_id=result.assignment_id,
            assignment_revision=result.assignment_revision,
            credential_generation=result.credential_generation,
            rotation_epoch=result.rotation_epoch,
            organization_id=result.scope.organization_id,
            environment_id=result.scope.environment_id,
            site_id=result.scope.site_id,
            accessor_subject_id=result.accessor_subject_id,
            policy_id=result.policy_id,
            policy_version=result.policy_version,
            policy_digest=result.policy_digest,
            materializer_id=result.materializer_id,
            materializer_version=result.materializer_version,
            materialization_receipt_digest=result.materialization_receipt_digest,
            state=result.state.value,
            failure_class=None if result.failure_class is None else result.failure_class.value,
            protected_artifact_id=result.protected_artifact_id,
            protected_artifact_digest=result.protected_artifact_digest,
            protected_artifact_schema_id=result.protected_artifact_schema_id,
            protected_artifact_schema_version=result.protected_artifact_schema_version,
            protected_artifact_profile_digest=result.protected_artifact_profile_digest,
            completed_at=result.completed_at,
            usable_until=result.usable_until,
            protected_artifact_revoked=result.protected_artifact_revoked,
            cleanup_confirmed=result.cleanup_confirmed,
            **cls._credential_materialization_authority_columns(result.authority),
            canonical_digest=result.canonical_digest,
            payload=cls._credential_materialization_payload(result),
        )

    @classmethod
    def _credential_materialization_claim_from_row(
        cls, row: WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaimModel
    ) -> WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaim:
        raw = dict(row.payload)
        try:
            raw["scope"] = WorkflowScope(**cast(Any, raw["scope"]))
            raw["claimed_at"] = datetime.fromisoformat(str(raw["claimed_at"]))
            raw["authority"] = WorkflowEventPhysicalTransportCredentialMaterializationAuthority(
                **cast(Any, raw["authority"])
            )
            claim = WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaim(
                **cast(Any, raw)
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowEventPhysicalTransportCredentialMaterializationError(
                "credential_materialization_repository_contract_violation"
            ) from exc
        cls._credential_materialization_assert_row_matches(
            row, cls._credential_materialization_claim_model(claim)
        )
        return claim

    @classmethod
    def _credential_materialization_attempt_from_row(
        cls, row: WorkflowEventPhysicalTransportCredentialMaterializationAttemptModel
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationAttempt:
        raw = dict(row.payload)
        try:
            raw["scope"] = WorkflowScope(**cast(Any, raw["scope"]))
            for key in ("started_at", "freshness_valid_until", "lease_valid_until"):
                raw[key] = datetime.fromisoformat(str(raw[key]))
            raw["state"] = WorkflowEventPhysicalTransportCredentialMaterializationAttemptState(
                str(raw["state"])
            )
            raw["authority"] = WorkflowEventPhysicalTransportCredentialMaterializationAuthority(
                **cast(Any, raw["authority"])
            )
            attempt = WorkflowEventPhysicalTransportCredentialMaterializationAttempt(
                **cast(Any, raw)
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowEventPhysicalTransportCredentialMaterializationError(
                "credential_materialization_repository_contract_violation"
            ) from exc
        cls._credential_materialization_assert_row_matches(
            row, cls._credential_materialization_attempt_model(attempt)
        )
        return attempt

    @classmethod
    def _credential_materialization_result_from_row(
        cls, row: WorkflowEventPhysicalTransportCredentialMaterializationResultModel
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationResult:
        raw = dict(row.payload)
        try:
            raw["scope"] = WorkflowScope(**cast(Any, raw["scope"]))
            raw["completed_at"] = datetime.fromisoformat(str(raw["completed_at"]))
            if raw["usable_until"] is not None:
                raw["usable_until"] = datetime.fromisoformat(str(raw["usable_until"]))
            raw["state"] = WorkflowEventPhysicalTransportCredentialMaterializationResultState(
                str(raw["state"])
            )
            if raw["failure_class"] is not None:
                raw["failure_class"] = (
                    WorkflowEventPhysicalTransportCredentialMaterializationFailureClass(
                        str(raw["failure_class"])
                    )
                )
            raw["authority"] = WorkflowEventPhysicalTransportCredentialMaterializationAuthority(
                **cast(Any, raw["authority"])
            )
            result = WorkflowEventPhysicalTransportCredentialMaterializationResult(**cast(Any, raw))
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowEventPhysicalTransportCredentialMaterializationError(
                "credential_materialization_repository_contract_violation"
            ) from exc
        cls._credential_materialization_assert_row_matches(
            row, cls._credential_materialization_result_model(result)
        )
        return result

    @classmethod
    def _credential_materialization_assert_row_matches(cls, row: Any, expected: Any) -> None:
        if any(
            getattr(row, column.name) != getattr(expected, column.name)
            for column in row.__table__.columns
        ):
            cls._credential_materialization_contract_violation()

    @staticmethod
    def _validate_credential_materialization_claim_request(
        request: WorkflowEventPhysicalTransportCredentialMaterializationClaimRequest,
    ) -> None:
        policy = code_owned_workflow_event_physical_transport_credential_materialization_policy()
        identifiers = (
            request.claim_id,
            request.attempt_id,
            request.materialization_id,
            request.authorization_lease_id,
            request.expected_freshness_admission_id,
            request.expected_credential_assignment_binding_id,
            request.expected_credential_assignment_snapshot_id,
            request.expected_assignment_id,
            request.expected_assignment_revision,
            request.accessor_subject_id,
            request.idempotency_key,
        )
        digests = (
            request.authorization_lease_digest,
            request.expected_freshness_admission_digest,
            request.expected_credential_assignment_binding_digest,
            request.expected_credential_assignment_snapshot_digest,
            request.expected_source_assignment_digest,
            request.expected_materialization_policy_digest,
            request.idempotency_digest,
            request.request_fingerprint,
        )
        if (
            any(not value for value in identifiers)
            or any(
                len(value) != 64 or any(character not in "0123456789abcdef" for character in value)
                for value in digests
            )
            or any(
                value.tzinfo is None
                for value in (
                    request.expected_freshness_valid_until,
                    request.expected_assignment_activated_at,
                    request.expected_assignment_expires_at,
                )
            )
            or request.expected_credential_generation < 1
            or request.expected_rotation_epoch < 1
            or request.expected_assignment_active is not True
            or request.expected_assignment_revoked is not False
            or request.expected_lease_state != "authorized_unconsumed"
            or request.expected_credential_access_authorized is not True
            or request.expected_materialization_policy_id != policy.policy_id
            or request.expected_materialization_policy_version != policy.policy_version
            or request.expected_materialization_policy_digest != policy.canonical_digest
            or request.irreversible_consumption_acknowledged is not True
            or request.uncertain_outcome_requires_new_authorization_acknowledged is not True
            or not callable(request.required_precommit_audit)
        ):
            raise WorkflowEventPhysicalTransportCredentialMaterializationError(
                "credential_materialization_request_invalid"
            )

    @staticmethod
    def _validate_credential_materialization_result_request(
        request: WorkflowEventPhysicalTransportCredentialMaterializationResultRequest,
    ) -> None:
        result = request.result
        digests = (
            request.expected_claim_digest,
            request.expected_attempt_digest,
            request.expected_source_assignment_digest,
            result.canonical_digest,
        )
        if (
            any(
                len(value) != 64 or any(character not in "0123456789abcdef" for character in value)
                for value in digests
            )
            or request.expected_lease_valid_until.tzinfo is None
            or result.assignment_id != request.expected_assignment_id
            or result.assignment_revision != request.expected_assignment_revision
            or result.credential_generation != request.expected_credential_generation
            or result.rotation_epoch != request.expected_rotation_epoch
            or any(value is not False for value in result.authority.canonical_value().values())
        ):
            raise WorkflowEventPhysicalTransportCredentialMaterializationError(
                "credential_materialization_result_invalid"
            )

    @staticmethod
    def _credential_materialization_contract_violation() -> NoReturn:
        raise WorkflowEventPhysicalTransportCredentialMaterializationError(
            "credential_materialization_repository_contract_violation"
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
        payload = cls._endpoint_materialization_digest_payload(values)
        return WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaim(
            **values, canonical_digest=canonical_digest(payload)
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
        payload = cls._endpoint_materialization_digest_payload(values)
        return WorkflowEventPhysicalTransportEndpointMaterializationAttempt(
            **values, canonical_digest=canonical_digest(payload)
        )

    @staticmethod
    def _endpoint_materialization_digest_payload(values: dict[str, Any]) -> dict[str, Any]:
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
    def _endpoint_materialization_payload(
        evidence: WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaim
        | WorkflowEventPhysicalTransportEndpointMaterializationAttempt
        | WorkflowEventPhysicalTransportEndpointMaterializationResult,
    ) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            {**evidence.digest_payload(), "canonical_digest": evidence.canonical_digest},
        )

    @classmethod
    def _endpoint_materialization_claim_model(
        cls, claim: WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaim
    ) -> WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaimModel:
        authority = claim.authority
        return WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaimModel(
            claim_id=claim.claim_id,
            authorization_lease_id=claim.authorization_lease_id,
            authorization_lease_digest=claim.authorization_lease_digest,
            freshness_admission_id=claim.freshness_admission_id,
            freshness_admission_digest=claim.freshness_admission_digest,
            attempt_id=claim.attempt_id,
            materialization_id=claim.materialization_id,
            organization_id=claim.scope.organization_id,
            environment_id=claim.scope.environment_id,
            site_id=claim.scope.site_id,
            resolver_subject_id=claim.resolver_subject_id,
            claimed_at=claim.claimed_at,
            request_fingerprint=claim.request_fingerprint,
            idempotency_digest=claim.idempotency_digest,
            endpoint_resolution_authority_granted=authority.endpoint_resolution_authorized,
            route_selection_authority_granted=authority.route_selection_authorized,
            route_binding_authority_granted=authority.route_binding_authorized,
            credential_access_authority_granted=authority.credential_access_authorized,
            network_access_authority_granted=authority.network_access_authorized,
            readiness_probe_authority_granted=authority.readiness_probe_authorized,
            publication_authority_granted=authority.publication_authorized,
            delivery_authority_granted=authority.delivery_authorized,
            dispatch_authority_granted=authority.dispatch_authorized,
            execution_authority_granted=authority.execution_authorized,
            canonical_digest=claim.canonical_digest,
            payload=cls._endpoint_materialization_payload(claim),
        )

    @classmethod
    def _endpoint_materialization_attempt_model(
        cls, attempt: WorkflowEventPhysicalTransportEndpointMaterializationAttempt
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationAttemptModel:
        authority = attempt.authority
        return WorkflowEventPhysicalTransportEndpointMaterializationAttemptModel(
            attempt_id=attempt.attempt_id,
            materialization_id=attempt.materialization_id,
            consumption_claim_id=attempt.consumption_claim_id,
            authorization_lease_id=attempt.authorization_lease_id,
            authorization_lease_digest=attempt.authorization_lease_digest,
            freshness_admission_id=attempt.freshness_admission_id,
            freshness_admission_digest=attempt.freshness_admission_digest,
            physical_transport_route_binding_id=attempt.physical_transport_route_binding_id,
            physical_transport_route_binding_digest=(
                attempt.physical_transport_route_binding_digest
            ),
            transport_route_snapshot_id=attempt.transport_route_snapshot_id,
            transport_route_snapshot_digest=attempt.transport_route_snapshot_digest,
            current_selection_head_id=attempt.current_selection_head_id,
            current_selection_head_digest=attempt.current_selection_head_digest,
            current_selection_head_generation=attempt.current_selection_head_generation,
            current_selection_head_fencing_token_digest=(
                attempt.current_selection_head_fencing_token_digest
            ),
            policy_id=attempt.policy_id,
            policy_version=attempt.policy_version,
            policy_digest=attempt.policy_digest,
            organization_id=attempt.scope.organization_id,
            environment_id=attempt.scope.environment_id,
            site_id=attempt.scope.site_id,
            resolver_subject_id=attempt.resolver_subject_id,
            started_at=attempt.started_at,
            freshness_valid_until=attempt.freshness_valid_until,
            lease_valid_until=attempt.lease_valid_until,
            state=attempt.state.value,
            endpoint_resolution_authority_granted=authority.endpoint_resolution_authorized,
            route_selection_authority_granted=authority.route_selection_authorized,
            route_binding_authority_granted=authority.route_binding_authorized,
            credential_access_authority_granted=authority.credential_access_authorized,
            network_access_authority_granted=authority.network_access_authorized,
            readiness_probe_authority_granted=authority.readiness_probe_authorized,
            publication_authority_granted=authority.publication_authorized,
            delivery_authority_granted=authority.delivery_authorized,
            dispatch_authority_granted=authority.dispatch_authorized,
            execution_authority_granted=authority.execution_authorized,
            canonical_digest=attempt.canonical_digest,
            payload=cls._endpoint_materialization_payload(attempt),
        )

    @classmethod
    def _endpoint_materialization_result_model(
        cls, result: WorkflowEventPhysicalTransportEndpointMaterializationResult
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationResultModel:
        authority = result.authority
        return WorkflowEventPhysicalTransportEndpointMaterializationResultModel(
            materialization_id=result.materialization_id,
            attempt_id=result.attempt_id,
            attempt_digest=result.attempt_digest,
            consumption_claim_id=result.consumption_claim_id,
            consumption_claim_digest=result.consumption_claim_digest,
            authorization_lease_id=result.authorization_lease_id,
            authorization_lease_digest=result.authorization_lease_digest,
            freshness_admission_id=result.freshness_admission_id,
            freshness_admission_digest=result.freshness_admission_digest,
            transport_route_snapshot_id=result.transport_route_snapshot_id,
            transport_route_snapshot_digest=result.transport_route_snapshot_digest,
            policy_id=result.policy_id,
            policy_version=result.policy_version,
            policy_digest=result.policy_digest,
            organization_id=result.scope.organization_id,
            environment_id=result.scope.environment_id,
            site_id=result.scope.site_id,
            resolver_subject_id=result.resolver_subject_id,
            materializer_id=result.materializer_id,
            materializer_version=result.materializer_version,
            materialization_receipt_digest=result.materialization_receipt_digest,
            state=result.state.value,
            failure_class=(None if result.failure_class is None else result.failure_class.value),
            protected_artifact_id=result.protected_artifact_id,
            protected_artifact_digest=result.protected_artifact_digest,
            normalized_endpoint_set_digest=result.normalized_endpoint_set_digest,
            endpoint_count=result.endpoint_count,
            protected_artifact_schema_id=result.protected_artifact_schema_id,
            protected_artifact_schema_version=result.protected_artifact_schema_version,
            protected_artifact_profile_digest=result.protected_artifact_profile_digest,
            completed_at=result.completed_at,
            usable_until=result.usable_until,
            protected_artifact_revoked=result.protected_artifact_revoked,
            cleanup_confirmed=result.cleanup_confirmed,
            endpoint_resolution_authority_granted=authority.endpoint_resolution_authorized,
            route_selection_authority_granted=authority.route_selection_authorized,
            route_binding_authority_granted=authority.route_binding_authorized,
            credential_access_authority_granted=authority.credential_access_authorized,
            network_access_authority_granted=authority.network_access_authorized,
            readiness_probe_authority_granted=authority.readiness_probe_authorized,
            publication_authority_granted=authority.publication_authorized,
            delivery_authority_granted=authority.delivery_authorized,
            dispatch_authority_granted=authority.dispatch_authorized,
            execution_authority_granted=authority.execution_authorized,
            canonical_digest=result.canonical_digest,
            payload=cls._endpoint_materialization_payload(result),
        )

    @classmethod
    def _endpoint_materialization_claim_from_row(
        cls,
        row: WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaimModel,
    ) -> WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaim:
        raw = dict(row.payload)
        raw["scope"] = WorkflowScope(**cast(Any, raw["scope"]))
        raw["claimed_at"] = datetime.fromisoformat(str(raw["claimed_at"]))
        raw["authority"] = WorkflowEventPhysicalTransportEndpointMaterializationAuthority(
            **cast(Any, raw["authority"])
        )
        try:
            claim = WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaim(
                **cast(Any, raw)
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowEventPhysicalTransportEndpointMaterializationError(
                "endpoint_materialization_repository_contract_violation"
            ) from exc
        if (
            row.claim_id != claim.claim_id
            or row.authorization_lease_id != claim.authorization_lease_id
            or row.authorization_lease_digest != claim.authorization_lease_digest
            or row.freshness_admission_id != claim.freshness_admission_id
            or row.freshness_admission_digest != claim.freshness_admission_digest
            or row.attempt_id != claim.attempt_id
            or row.materialization_id != claim.materialization_id
            or row.organization_id != claim.scope.organization_id
            or row.environment_id != claim.scope.environment_id
            or row.site_id != claim.scope.site_id
            or row.resolver_subject_id != claim.resolver_subject_id
            or row.claimed_at != claim.claimed_at
            or row.request_fingerprint != claim.request_fingerprint
            or row.idempotency_digest != claim.idempotency_digest
            or row.canonical_digest != claim.canonical_digest
            or not cls._endpoint_materialization_authority_row_matches(row, claim.authority)
            or row.payload != cls._endpoint_materialization_payload(claim)
        ):
            cls._endpoint_materialization_contract_violation()
        return claim

    @classmethod
    def _endpoint_materialization_attempt_from_row(
        cls, row: WorkflowEventPhysicalTransportEndpointMaterializationAttemptModel
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationAttempt:
        raw = dict(row.payload)
        raw["scope"] = WorkflowScope(**cast(Any, raw["scope"]))
        for key in ("started_at", "freshness_valid_until", "lease_valid_until"):
            raw[key] = datetime.fromisoformat(str(raw[key]))
        raw["state"] = WorkflowEventPhysicalTransportEndpointMaterializationAttemptState(
            str(raw["state"])
        )
        raw["authority"] = WorkflowEventPhysicalTransportEndpointMaterializationAuthority(
            **cast(Any, raw["authority"])
        )
        try:
            attempt = WorkflowEventPhysicalTransportEndpointMaterializationAttempt(**cast(Any, raw))
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowEventPhysicalTransportEndpointMaterializationError(
                "endpoint_materialization_repository_contract_violation"
            ) from exc
        if (
            row.attempt_id != attempt.attempt_id
            or row.materialization_id != attempt.materialization_id
            or row.consumption_claim_id != attempt.consumption_claim_id
            or row.authorization_lease_id != attempt.authorization_lease_id
            or row.authorization_lease_digest != attempt.authorization_lease_digest
            or row.freshness_admission_id != attempt.freshness_admission_id
            or row.freshness_admission_digest != attempt.freshness_admission_digest
            or row.physical_transport_route_binding_id
            != attempt.physical_transport_route_binding_id
            or row.physical_transport_route_binding_digest
            != attempt.physical_transport_route_binding_digest
            or row.transport_route_snapshot_id != attempt.transport_route_snapshot_id
            or row.transport_route_snapshot_digest != attempt.transport_route_snapshot_digest
            or row.current_selection_head_id != attempt.current_selection_head_id
            or row.current_selection_head_digest != attempt.current_selection_head_digest
            or row.current_selection_head_generation != attempt.current_selection_head_generation
            or row.current_selection_head_fencing_token_digest
            != attempt.current_selection_head_fencing_token_digest
            or row.organization_id != attempt.scope.organization_id
            or row.environment_id != attempt.scope.environment_id
            or row.site_id != attempt.scope.site_id
            or row.resolver_subject_id != attempt.resolver_subject_id
            or row.policy_id != attempt.policy_id
            or row.policy_version != attempt.policy_version
            or row.policy_digest != attempt.policy_digest
            or row.started_at != attempt.started_at
            or row.freshness_valid_until != attempt.freshness_valid_until
            or row.lease_valid_until != attempt.lease_valid_until
            or row.state != attempt.state.value
            or row.canonical_digest != attempt.canonical_digest
            or not cls._endpoint_materialization_authority_row_matches(row, attempt.authority)
            or row.payload != cls._endpoint_materialization_payload(attempt)
        ):
            cls._endpoint_materialization_contract_violation()
        return attempt

    @classmethod
    def _endpoint_materialization_result_from_row(
        cls, row: WorkflowEventPhysicalTransportEndpointMaterializationResultModel
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationResult:
        raw = dict(row.payload)
        raw["scope"] = WorkflowScope(**cast(Any, raw["scope"]))
        raw["completed_at"] = datetime.fromisoformat(str(raw["completed_at"]))
        if raw["usable_until"] is not None:
            raw["usable_until"] = datetime.fromisoformat(str(raw["usable_until"]))
        raw["state"] = WorkflowEventPhysicalTransportEndpointMaterializationResultState(
            str(raw["state"])
        )
        if raw["failure_class"] is not None:
            raw["failure_class"] = (
                WorkflowEventPhysicalTransportEndpointMaterializationFailureClass(
                    str(raw["failure_class"])
                )
            )
        raw["authority"] = WorkflowEventPhysicalTransportEndpointMaterializationAuthority(
            **cast(Any, raw["authority"])
        )
        try:
            result = WorkflowEventPhysicalTransportEndpointMaterializationResult(**cast(Any, raw))
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowEventPhysicalTransportEndpointMaterializationError(
                "endpoint_materialization_repository_contract_violation"
            ) from exc
        if (
            row.materialization_id != result.materialization_id
            or row.attempt_id != result.attempt_id
            or row.attempt_digest != result.attempt_digest
            or row.consumption_claim_id != result.consumption_claim_id
            or row.consumption_claim_digest != result.consumption_claim_digest
            or row.authorization_lease_id != result.authorization_lease_id
            or row.authorization_lease_digest != result.authorization_lease_digest
            or row.freshness_admission_id != result.freshness_admission_id
            or row.freshness_admission_digest != result.freshness_admission_digest
            or row.transport_route_snapshot_id != result.transport_route_snapshot_id
            or row.transport_route_snapshot_digest != result.transport_route_snapshot_digest
            or row.organization_id != result.scope.organization_id
            or row.environment_id != result.scope.environment_id
            or row.site_id != result.scope.site_id
            or row.resolver_subject_id != result.resolver_subject_id
            or row.policy_id != result.policy_id
            or row.policy_version != result.policy_version
            or row.policy_digest != result.policy_digest
            or row.materializer_id != result.materializer_id
            or row.materializer_version != result.materializer_version
            or row.materialization_receipt_digest != result.materialization_receipt_digest
            or row.state != result.state.value
            or row.failure_class
            != (None if result.failure_class is None else result.failure_class.value)
            or row.protected_artifact_id != result.protected_artifact_id
            or row.protected_artifact_digest != result.protected_artifact_digest
            or row.normalized_endpoint_set_digest != result.normalized_endpoint_set_digest
            or row.endpoint_count != result.endpoint_count
            or row.protected_artifact_schema_id != result.protected_artifact_schema_id
            or row.protected_artifact_schema_version != result.protected_artifact_schema_version
            or row.protected_artifact_profile_digest != result.protected_artifact_profile_digest
            or row.completed_at != result.completed_at
            or row.usable_until != result.usable_until
            or row.protected_artifact_revoked != result.protected_artifact_revoked
            or row.cleanup_confirmed != result.cleanup_confirmed
            or row.canonical_digest != result.canonical_digest
            or not cls._endpoint_materialization_authority_row_matches(row, result.authority)
            or row.payload != cls._endpoint_materialization_payload(result)
        ):
            cls._endpoint_materialization_contract_violation()
        return result

    @staticmethod
    def _endpoint_materialization_authority_row_matches(
        row: Any,
        authority: WorkflowEventPhysicalTransportEndpointMaterializationAuthority,
    ) -> bool:
        return bool(
            row.endpoint_resolution_authority_granted == authority.endpoint_resolution_authorized
            and row.route_selection_authority_granted == authority.route_selection_authorized
            and row.route_binding_authority_granted == authority.route_binding_authorized
            and row.credential_access_authority_granted == authority.credential_access_authorized
            and row.network_access_authority_granted == authority.network_access_authorized
            and row.readiness_probe_authority_granted == authority.readiness_probe_authorized
            and row.publication_authority_granted == authority.publication_authorized
            and row.delivery_authority_granted == authority.delivery_authorized
            and row.dispatch_authority_granted == authority.dispatch_authorized
            and row.execution_authority_granted == authority.execution_authorized
        )

    @staticmethod
    def _validate_endpoint_materialization_claim_request(
        request: WorkflowEventPhysicalTransportEndpointMaterializationClaimRequest,
    ) -> None:
        identifiers = (
            request.claim_id,
            request.attempt_id,
            request.materialization_id,
            request.authorization_lease_id,
            request.resolver_subject_id,
            request.idempotency_key,
        )
        digests = (
            request.authorization_lease_digest,
            request.expected_freshness_admission_digest,
            request.expected_physical_transport_route_binding_digest,
            request.expected_transport_route_snapshot_digest,
            request.expected_current_selection_head_digest,
            request.expected_current_selection_head_fencing_token_digest,
            request.expected_selected_route_digest,
            request.expected_materialization_policy_digest,
            request.idempotency_digest,
            request.request_fingerprint,
        )
        if (
            any(not value or value != value.strip() or len(value) > 240 for value in identifiers)
            or any(len(value) != 64 for value in digests)
            or request.expected_freshness_valid_until.tzinfo is None
            or request.expected_current_selection_head_generation < 1
            or request.irreversible_consumption_acknowledged is not True
            or request.uncertain_outcome_requires_new_authorization_acknowledged is not True
        ):
            raise ValueError("endpoint materialization claim request is invalid")

    @staticmethod
    def _validate_endpoint_materialization_result_request(
        request: WorkflowEventPhysicalTransportEndpointMaterializationResultRequest,
    ) -> None:
        if (
            len(request.expected_claim_digest) != 64
            or len(request.expected_attempt_digest) != 64
            or len(request.expected_current_selection_head_digest) != 64
            or len(request.expected_current_selection_head_fencing_token_digest) != 64
            or request.expected_current_selection_head_generation < 1
            or request.expected_lease_valid_until.tzinfo is None
            or request.result.completed_at.tzinfo is None
        ):
            raise ValueError("endpoint materialization result request is invalid")

    @staticmethod
    def _endpoint_materialization_contract_violation() -> NoReturn:
        raise WorkflowEventPhysicalTransportEndpointMaterializationError(
            "endpoint_materialization_repository_contract_violation"
        )

    async def _lock_endpoint_resolution_authorization_sources(
        self,
        session: AsyncSession,
        *,
        request: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRequest,
    ) -> tuple[
        WorkflowEventPhysicalTransportRouteBindingModel | None,
        EventPhysicalTransportRouteSnapshotModel | None,
        DeploymentEventTransportRouteSelectionHeadModel | None,
        WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel | None,
    ]:
        binding_row = cast(
            WorkflowEventPhysicalTransportRouteBindingModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportRouteBindingModel)
                .where(
                    WorkflowEventPhysicalTransportRouteBindingModel.binding_id
                    == request.expected_physical_transport_route_binding_id
                )
                .with_for_update()
            ),
        )
        route_row = cast(
            EventPhysicalTransportRouteSnapshotModel | None,
            await session.scalar(
                select(EventPhysicalTransportRouteSnapshotModel)
                .where(
                    EventPhysicalTransportRouteSnapshotModel.snapshot_id
                    == request.expected_transport_route_snapshot_id
                )
                .with_for_update()
            ),
        )
        head_rows = (
            await session.scalars(
                select(DeploymentEventTransportRouteSelectionHeadModel)
                .where(
                    DeploymentEventTransportRouteSelectionHeadModel.organization_id
                    == request.scope.organization_id,
                    DeploymentEventTransportRouteSelectionHeadModel.environment_id
                    == request.scope.environment_id,
                    DeploymentEventTransportRouteSelectionHeadModel.site_id
                    == request.scope.site_id,
                    DeploymentEventTransportRouteSelectionHeadModel.route_set_id
                    == request.expected_route_set_id,
                    DeploymentEventTransportRouteSelectionHeadModel.current.is_(True),
                )
                .limit(2)
                .with_for_update()
            )
        ).all()
        head_row = head_rows[0] if len(head_rows) == 1 else None
        freshness_row = cast(
            WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel)
                .where(
                    WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel.freshness_admission_id
                    == request.expected_freshness_admission_id
                )
                .with_for_update()
            ),
        )
        return binding_row, route_row, head_row, freshness_row

    async def _endpoint_resolution_authorization_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRequest,
        head_row: DeploymentEventTransportRouteSelectionHeadModel | None,
        freshness_row: WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel | None,
        observed_at: datetime,
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult | None:
        claim = await self._load_endpoint_resolution_authorization_lease_claim(
            session,
            scope=request.scope,
            resolver_subject_id=request.resolver_subject_id,
            idempotency_key=request.idempotency_key,
        )
        if claim is None:
            return None
        lease_row = await session.get(
            WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel,
            claim.authorization_lease_id,
        )
        record = self._endpoint_resolution_authorization_lease_record_from_claim(claim, lease_row)
        if claim.request_fingerprint != request.request_fingerprint:
            return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult(
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus.IDEMPOTENCY_CONFLICT,
                record.lease,
            )
        if (
            head_row is None
            or freshness_row is None
            or not self._endpoint_resolution_authorization_remains_current(
                record.lease,
                head_row=head_row,
                freshness_row=freshness_row,
                observed_at=observed_at,
            )
        ):
            return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult(
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus.EVIDENCE_CONFLICT,
                None,
            )
        return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResult(
            WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseStatus.REPLAY,
            record.lease,
        )

    @classmethod
    async def _load_endpoint_resolution_authorization_lease_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        resolver_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseClaimModel | None:
        return cast(
            WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseClaimModel | None,
            await session.scalar(
                select(
                    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseClaimModel
                ).where(
                    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseClaimModel.idempotency_scope_id
                    == cls._endpoint_resolution_authorization_idempotency_scope(
                        scope, resolver_subject_id
                    ),
                    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseClaimModel.idempotency_key
                    == idempotency_key,
                    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseClaimModel.organization_id
                    == scope.organization_id,
                    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseClaimModel.environment_id
                    == scope.environment_id,
                    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseClaimModel.site_id
                    == scope.site_id,
                    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseClaimModel.resolver_subject_id
                    == resolver_subject_id,
                )
            ),
        )

    @classmethod
    def _endpoint_resolution_authorization_lease_record_from_claim(
        cls,
        claim: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseClaimModel,
        lease_row: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel | None,
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseIdempotencyRecord:
        if lease_row is None:
            cls._endpoint_resolution_authorization_contract_violation()
        assert lease_row is not None
        lease = cls._endpoint_resolution_authorization_lease_from_row(lease_row)
        scope_id = cls._endpoint_resolution_authorization_idempotency_scope(
            lease.scope, lease.resolver_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_digest": lease.canonical_digest,
            "result_lease": cls._endpoint_resolution_authorization_lease_payload(lease),
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != lease.canonical_digest
            or claim.authorization_lease_id != lease.authorization_lease_id
            or claim.freshness_admission_id != lease.freshness_admission_id
            or claim.physical_transport_route_binding_id
            != lease.physical_transport_route_binding_id
            or claim.transport_route_snapshot_id != lease.transport_route_snapshot_id
            or claim.current_selection_head_id != lease.current_selection_head_id
            or claim.current_selection_head_generation != lease.current_selection_head_generation
            or claim.current_selection_head_fencing_token_digest
            != lease.current_selection_head_fencing_token_digest
            or claim.policy_digest != lease.policy_digest
            or claim.organization_id != lease.scope.organization_id
            or claim.environment_id != lease.scope.environment_id
            or claim.site_id != lease.scope.site_id
            or claim.resolver_subject_id != lease.resolver_subject_id
            or claim.created_at.tzinfo is None
            or claim.created_at != lease.issued_at
            or claim.payload != payload
            or claim.canonical_digest != canonical_digest(payload)
        ):
            cls._endpoint_resolution_authorization_contract_violation()
        return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseIdempotencyRecord(
            request_fingerprint=claim.request_fingerprint,
            lease=lease,
        )

    async def _lock_route_freshness_sources(
        self,
        session: AsyncSession,
        *,
        request: WorkflowEventPhysicalTransportRouteFreshnessAdmissionRequest,
    ) -> tuple[
        WorkflowEventPhysicalTransportRouteBindingModel | None,
        EventPhysicalTransportRouteSnapshotModel | None,
        DeploymentEventTransportRouteSelectionHeadModel | None,
    ]:
        binding_row = cast(
            WorkflowEventPhysicalTransportRouteBindingModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportRouteBindingModel)
                .where(
                    WorkflowEventPhysicalTransportRouteBindingModel.binding_id
                    == request.expected_physical_transport_route_binding_id
                )
                .with_for_update()
            ),
        )
        route_row = cast(
            EventPhysicalTransportRouteSnapshotModel | None,
            await session.scalar(
                select(EventPhysicalTransportRouteSnapshotModel)
                .where(
                    EventPhysicalTransportRouteSnapshotModel.snapshot_id
                    == request.expected_transport_route_snapshot_id
                )
                .with_for_update()
            ),
        )
        head_rows = (
            await session.scalars(
                select(DeploymentEventTransportRouteSelectionHeadModel)
                .where(
                    DeploymentEventTransportRouteSelectionHeadModel.organization_id
                    == request.scope.organization_id,
                    DeploymentEventTransportRouteSelectionHeadModel.environment_id
                    == request.scope.environment_id,
                    DeploymentEventTransportRouteSelectionHeadModel.site_id
                    == request.scope.site_id,
                    DeploymentEventTransportRouteSelectionHeadModel.route_set_id
                    == request.expected_route_set_id,
                    DeploymentEventTransportRouteSelectionHeadModel.current.is_(True),
                )
                .limit(2)
                .with_for_update()
            )
        ).all()
        head_row = head_rows[0] if len(head_rows) == 1 else None
        return binding_row, route_row, head_row

    async def _route_freshness_admission_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowEventPhysicalTransportRouteFreshnessAdmissionRequest,
        head_row: DeploymentEventTransportRouteSelectionHeadModel | None,
        observed_at: datetime,
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult | None:
        claim = await self._load_route_freshness_admission_claim(
            session,
            scope=request.scope,
            admitter_subject_id=request.admitter_subject_id,
            idempotency_key=request.idempotency_key,
        )
        if claim is None:
            return None
        admission_row = await session.get(
            WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel,
            claim.freshness_admission_id,
        )
        record = self._route_freshness_admission_record_from_claim(claim, admission_row)
        if claim.request_fingerprint != request.request_fingerprint:
            return WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult(
                WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus.IDEMPOTENCY_CONFLICT,
                record.admission,
            )
        if head_row is None or not self._route_freshness_admission_remains_current(
            record.admission, head_row=head_row, observed_at=observed_at
        ):
            return WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult(
                WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus.EVIDENCE_CONFLICT,
                None,
            )
        return WorkflowEventPhysicalTransportRouteFreshnessAdmissionResult(
            WorkflowEventPhysicalTransportRouteFreshnessAdmissionStatus.REPLAY,
            record.admission,
        )

    @classmethod
    async def _load_route_freshness_admission_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        admitter_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmissionClaimModel | None:
        return cast(
            WorkflowEventPhysicalTransportRouteFreshnessAdmissionClaimModel | None,
            await session.scalar(
                select(WorkflowEventPhysicalTransportRouteFreshnessAdmissionClaimModel).where(
                    WorkflowEventPhysicalTransportRouteFreshnessAdmissionClaimModel.idempotency_scope_id
                    == cls._route_freshness_admission_idempotency_scope(scope, admitter_subject_id),
                    WorkflowEventPhysicalTransportRouteFreshnessAdmissionClaimModel.idempotency_key
                    == idempotency_key,
                    WorkflowEventPhysicalTransportRouteFreshnessAdmissionClaimModel.organization_id
                    == scope.organization_id,
                    WorkflowEventPhysicalTransportRouteFreshnessAdmissionClaimModel.environment_id
                    == scope.environment_id,
                    WorkflowEventPhysicalTransportRouteFreshnessAdmissionClaimModel.site_id
                    == scope.site_id,
                    WorkflowEventPhysicalTransportRouteFreshnessAdmissionClaimModel.admitter_subject_id
                    == admitter_subject_id,
                )
            ),
        )

    @classmethod
    def _route_freshness_admission_record_from_claim(
        cls,
        claim: WorkflowEventPhysicalTransportRouteFreshnessAdmissionClaimModel,
        admission_row: WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel | None,
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmissionIdempotencyRecord:
        if admission_row is None:
            cls._route_freshness_admission_contract_violation()
        assert admission_row is not None
        admission = cls._route_freshness_admission_from_row(admission_row)
        scope_id = cls._route_freshness_admission_idempotency_scope(
            admission.scope, admission.admitter_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_admission": cls._route_freshness_admission_payload(admission),
            "result_digest": admission.canonical_digest,
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != admission.canonical_digest
            or claim.freshness_admission_id != admission.freshness_admission_id
            or claim.physical_transport_route_binding_id
            != admission.physical_transport_route_binding_id
            or claim.transport_route_snapshot_id != admission.transport_route_snapshot_id
            or claim.current_selection_head_id != admission.current_selection_head_id
            or claim.current_selection_head_generation
            != admission.current_selection_head_generation
            or claim.current_selection_head_fencing_token_digest
            != admission.current_selection_head_fencing_token_digest
            or claim.policy_digest != admission.policy_digest
            or claim.organization_id != admission.scope.organization_id
            or claim.environment_id != admission.scope.environment_id
            or claim.site_id != admission.scope.site_id
            or claim.admitter_subject_id != admission.admitter_subject_id
            or claim.created_at.tzinfo is None
            or claim.created_at != admission.evaluated_at
            or claim.payload != payload
            or claim.canonical_digest != canonical_digest(payload)
        ):
            cls._route_freshness_admission_contract_violation()
        return WorkflowEventPhysicalTransportRouteFreshnessAdmissionIdempotencyRecord(
            request_fingerprint=claim.request_fingerprint,
            admission=admission,
        )

    @classmethod
    def _route_selection_head_from_row(
        cls, row: DeploymentEventTransportRouteSelectionHeadModel
    ) -> DeploymentEventTransportRouteSelectionHead:
        try:
            head = cls._route_selection_head_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowEventPhysicalTransportRouteFreshnessAdmissionError(
                "workflow_route_selection_head_repository_contract_violation",
                "The authoritative route selection head record is invalid.",
            ) from exc
        if (
            row.head_id != head.head_id
            or row.generation != head.generation
            or row.route_set_id != head.route_set_id
            or row.route_set_revision != head.route_set_revision
            or row.selection_epoch_id != head.selection_epoch_id
            or row.selection_epoch_revision != head.selection_epoch_revision
            or row.selected_route_id != head.selected_route_id
            or row.selected_route_revision != head.selected_route_revision
            or row.selected_route_digest != head.selected_route_digest
            or row.fencing_token_digest != head.fencing_token_digest
            or row.selection_active != head.selection_active
            or row.selection_eligible != head.selection_eligible
            or row.selection_suspended != head.selection_suspended
            or row.selection_withdrawn != head.selection_withdrawn
            or row.selection_superseded != head.selection_superseded
            or row.organization_id != head.scope.organization_id
            or row.environment_id != head.scope.environment_id
            or row.site_id != head.scope.site_id
            or row.current != head.current
            or row.canonical_digest != head.canonical_digest
            or row.payload != cls._route_selection_head_payload(head)
        ):
            cls._route_freshness_admission_contract_violation()
        return head

    @classmethod
    def _route_selection_head_model(
        cls, head: DeploymentEventTransportRouteSelectionHead
    ) -> DeploymentEventTransportRouteSelectionHeadModel:
        return DeploymentEventTransportRouteSelectionHeadModel(
            head_id=head.head_id,
            generation=head.generation,
            route_set_id=head.route_set_id,
            route_set_revision=head.route_set_revision,
            selection_epoch_id=head.selection_epoch_id,
            selection_epoch_revision=head.selection_epoch_revision,
            selected_route_id=head.selected_route_id,
            selected_route_revision=head.selected_route_revision,
            selected_route_digest=head.selected_route_digest,
            fencing_token_digest=head.fencing_token_digest,
            selection_active=head.selection_active,
            selection_eligible=head.selection_eligible,
            selection_suspended=head.selection_suspended,
            selection_withdrawn=head.selection_withdrawn,
            selection_superseded=head.selection_superseded,
            organization_id=head.scope.organization_id,
            environment_id=head.scope.environment_id,
            site_id=head.scope.site_id,
            current=head.current,
            canonical_digest=head.canonical_digest,
            payload=cls._route_selection_head_payload(head),
        )

    @classmethod
    def _assign_route_selection_head_row(
        cls,
        row: DeploymentEventTransportRouteSelectionHeadModel,
        head: DeploymentEventTransportRouteSelectionHead,
    ) -> None:
        replacement = cls._route_selection_head_model(head)
        for attribute in (
            "head_id",
            "generation",
            "route_set_revision",
            "selection_epoch_id",
            "selection_epoch_revision",
            "selected_route_id",
            "selected_route_revision",
            "selected_route_digest",
            "fencing_token_digest",
            "selection_active",
            "selection_eligible",
            "selection_suspended",
            "selection_withdrawn",
            "selection_superseded",
            "current",
            "canonical_digest",
            "payload",
        ):
            setattr(row, attribute, getattr(replacement, attribute))

    @classmethod
    def _endpoint_resolution_authorization_lease_from_row(
        cls, row: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease:
        try:
            lease = cls._endpoint_resolution_authorization_lease_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError(
                "workflow_endpoint_resolution_authorization_repository_contract_violation",
                "The endpoint-resolution authorization lease record is invalid.",
            ) from exc
        authority = lease.authority
        if (
            row.authorization_lease_id != lease.authorization_lease_id
            or row.freshness_admission_id != lease.freshness_admission_id
            or row.freshness_admission_digest != lease.freshness_admission_digest
            or row.physical_transport_route_binding_id != lease.physical_transport_route_binding_id
            or row.physical_transport_route_binding_digest
            != lease.physical_transport_route_binding_digest
            or row.transport_route_snapshot_id != lease.transport_route_snapshot_id
            or row.transport_route_snapshot_digest != lease.transport_route_snapshot_digest
            or row.current_selection_head_id != lease.current_selection_head_id
            or row.current_selection_head_digest != lease.current_selection_head_digest
            or row.current_selection_head_generation != lease.current_selection_head_generation
            or row.current_selection_head_fencing_token_digest
            != lease.current_selection_head_fencing_token_digest
            or row.route_set_id != lease.route_set_id
            or row.route_set_revision != lease.route_set_revision
            or row.selection_epoch_id != lease.selection_epoch_id
            or row.selection_epoch_revision != lease.selection_epoch_revision
            or row.selected_route_id != lease.selected_route_id
            or row.selected_route_revision != lease.selected_route_revision
            or row.selected_route_digest != lease.selected_route_digest
            or row.selection_active != lease.selection_active
            or row.selection_eligible != lease.selection_eligible
            or row.selection_suspended != lease.selection_suspended
            or row.selection_withdrawn != lease.selection_withdrawn
            or row.selection_superseded != lease.selection_superseded
            or row.policy_id != lease.policy_id
            or row.policy_version != lease.policy_version
            or row.policy_digest != lease.policy_digest
            or row.organization_id != lease.scope.organization_id
            or row.environment_id != lease.scope.environment_id
            or row.site_id != lease.scope.site_id
            or row.resolver_subject_id != lease.resolver_subject_id
            or row.issued_at != lease.issued_at
            or row.valid_until != lease.valid_until
            or row.state != lease.state.value
            or row.endpoint_resolution_authority_granted != authority.endpoint_resolution_authorized
            or row.route_selection_authority_granted != authority.route_selection_authorized
            or row.route_binding_authority_granted != authority.route_binding_authorized
            or row.credential_access_authority_granted != authority.credential_access_authorized
            or row.network_access_authority_granted != authority.network_access_authorized
            or row.readiness_probe_authority_granted != authority.readiness_probe_authorized
            or row.publication_authority_granted != authority.publication_authorized
            or row.delivery_authority_granted != authority.delivery_authorized
            or row.dispatch_authority_granted != authority.dispatch_authorized
            or row.execution_authority_granted != authority.execution_authorized
            or row.canonical_digest != lease.canonical_digest
            or row.payload != cls._endpoint_resolution_authorization_lease_payload(lease)
        ):
            cls._endpoint_resolution_authorization_contract_violation()
        return lease

    @classmethod
    def _endpoint_resolution_authorization_lease_model(
        cls, lease: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel:
        authority = lease.authority
        return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel(
            authorization_lease_id=lease.authorization_lease_id,
            freshness_admission_id=lease.freshness_admission_id,
            freshness_admission_digest=lease.freshness_admission_digest,
            physical_transport_route_binding_id=lease.physical_transport_route_binding_id,
            physical_transport_route_binding_digest=lease.physical_transport_route_binding_digest,
            transport_route_snapshot_id=lease.transport_route_snapshot_id,
            transport_route_snapshot_digest=lease.transport_route_snapshot_digest,
            current_selection_head_id=lease.current_selection_head_id,
            current_selection_head_digest=lease.current_selection_head_digest,
            current_selection_head_generation=lease.current_selection_head_generation,
            current_selection_head_fencing_token_digest=(
                lease.current_selection_head_fencing_token_digest
            ),
            route_set_id=lease.route_set_id,
            route_set_revision=lease.route_set_revision,
            selection_epoch_id=lease.selection_epoch_id,
            selection_epoch_revision=lease.selection_epoch_revision,
            selected_route_id=lease.selected_route_id,
            selected_route_revision=lease.selected_route_revision,
            selected_route_digest=lease.selected_route_digest,
            selection_active=lease.selection_active,
            selection_eligible=lease.selection_eligible,
            selection_suspended=lease.selection_suspended,
            selection_withdrawn=lease.selection_withdrawn,
            selection_superseded=lease.selection_superseded,
            policy_id=lease.policy_id,
            policy_version=lease.policy_version,
            policy_digest=lease.policy_digest,
            organization_id=lease.scope.organization_id,
            environment_id=lease.scope.environment_id,
            site_id=lease.scope.site_id,
            resolver_subject_id=lease.resolver_subject_id,
            issued_at=lease.issued_at,
            valid_until=lease.valid_until,
            state=lease.state.value,
            endpoint_resolution_authority_granted=authority.endpoint_resolution_authorized,
            route_selection_authority_granted=authority.route_selection_authorized,
            route_binding_authority_granted=authority.route_binding_authorized,
            credential_access_authority_granted=authority.credential_access_authorized,
            network_access_authority_granted=authority.network_access_authorized,
            readiness_probe_authority_granted=authority.readiness_probe_authorized,
            publication_authority_granted=authority.publication_authorized,
            delivery_authority_granted=authority.delivery_authorized,
            dispatch_authority_granted=authority.dispatch_authorized,
            execution_authority_granted=authority.execution_authorized,
            canonical_digest=lease.canonical_digest,
            payload=cls._endpoint_resolution_authorization_lease_payload(lease),
        )

    @classmethod
    def _endpoint_resolution_authorization_lease_claim_model(
        cls,
        request: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRequest,
        lease: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease,
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseClaimModel:
        scope_id = cls._endpoint_resolution_authorization_idempotency_scope(
            lease.scope, lease.resolver_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_digest": lease.canonical_digest,
            "result_lease": cls._endpoint_resolution_authorization_lease_payload(lease),
        }
        digest = canonical_digest(payload)
        return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseClaimModel(
            claim_id=f"wf_endpoint_res_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=lease.canonical_digest,
            authorization_lease_id=lease.authorization_lease_id,
            freshness_admission_id=lease.freshness_admission_id,
            physical_transport_route_binding_id=lease.physical_transport_route_binding_id,
            transport_route_snapshot_id=lease.transport_route_snapshot_id,
            current_selection_head_id=lease.current_selection_head_id,
            current_selection_head_generation=lease.current_selection_head_generation,
            current_selection_head_fencing_token_digest=(
                lease.current_selection_head_fencing_token_digest
            ),
            policy_digest=lease.policy_digest,
            organization_id=lease.scope.organization_id,
            environment_id=lease.scope.environment_id,
            site_id=lease.scope.site_id,
            resolver_subject_id=lease.resolver_subject_id,
            created_at=lease.issued_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _endpoint_resolution_authorization_evidence_matches(
        cls,
        *,
        binding_row: WorkflowEventPhysicalTransportRouteBindingModel | None,
        route_row: EventPhysicalTransportRouteSnapshotModel | None,
        head_row: DeploymentEventTransportRouteSelectionHeadModel | None,
        freshness_row: WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel | None,
        request: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRequest,
        observed_at: datetime,
    ) -> bool:
        if (
            binding_row is None
            or route_row is None
            or head_row is None
            or freshness_row is None
            or not head_row.current
            or not head_row.selection_active
            or not head_row.selection_eligible
            or head_row.selection_suspended
            or head_row.selection_withdrawn
            or head_row.selection_superseded
        ):
            return False
        try:
            binding = cls._physical_transport_route_binding_from_row(binding_row)
            route = cls._transport_route_snapshot_from_row(route_row)
            head = cls._route_selection_head_from_row(head_row)
            freshness = cls._route_freshness_admission_from_row(freshness_row)
        except (
            WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError,
            WorkflowEventPhysicalTransportRouteBindingError,
            WorkflowEventPhysicalTransportRouteFreshnessAdmissionError,
            WorkflowTransportRouteSnapshotError,
        ):
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
            and binding.scope == route.scope == head.scope == freshness.scope == request.scope
            and route.captured_at <= binding.bound_at <= freshness.evaluated_at <= observed_at
            and request.expected_policy_id == policy.policy_id
            and request.expected_policy_version == policy.policy_version
            and request.expected_policy_digest == policy.canonical_digest
            and request.expected_validity_window_seconds == policy.validity_window_seconds
            and not any(binding.authority.canonical_value().values())
            and not any(route.authority.canonical_value().values())
            and not any(freshness.authority.canonical_value().values())
        )

    @classmethod
    def _endpoint_resolution_authorization_remains_current(
        cls,
        lease: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease,
        *,
        head_row: DeploymentEventTransportRouteSelectionHeadModel,
        freshness_row: WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel,
        observed_at: datetime,
    ) -> bool:
        if observed_at >= lease.valid_until:
            return False
        try:
            head = cls._route_selection_head_from_row(head_row)
            freshness = cls._route_freshness_admission_from_row(freshness_row)
        except WorkflowEventPhysicalTransportRouteFreshnessAdmissionError:
            return False
        return bool(
            observed_at < freshness.valid_until
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
        values: dict[str, Any] = {
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
            "state": (
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
            ),
            "authority": (
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseAuthority()
            ),
        }
        payload = {
            key: value.canonical_value()
            if isinstance(
                value,
                (
                    WorkflowScope,
                    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseAuthority,
                ),
            )
            else value.value
            if isinstance(value, Enum)
            else value.isoformat()
            if isinstance(value, datetime)
            else value
            for key, value in values.items()
        }
        return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease(
            **values, canonical_digest=canonical_digest(payload)
        )

    @staticmethod
    def _endpoint_resolution_authorization_lease_payload(
        lease: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease,
    ) -> dict[str, Any]:
        return cast(dict[str, Any], lease.canonical_value())

    @staticmethod
    def _endpoint_resolution_authorization_lease_to_domain(
        raw: dict[str, Any],
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease:
        values = dict(raw)
        values["scope"] = WorkflowScope(**cast(Any, values["scope"]))
        values["issued_at"] = datetime.fromisoformat(str(values["issued_at"]))
        values["valid_until"] = datetime.fromisoformat(str(values["valid_until"]))
        values["state"] = WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseState(
            str(values["state"])
        )
        values["authority"] = (
            WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseAuthority(
                **cast(Any, values["authority"])
            )
        )
        return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease(
            **cast(Any, values)
        )

    @staticmethod
    def _endpoint_resolution_authorization_idempotency_scope(
        scope: WorkflowScope, resolver_subject_id: str
    ) -> str:
        return canonical_digest(
            {"resolver_subject_id": resolver_subject_id, "scope": scope.canonical_value()}
        )

    @staticmethod
    def _validate_endpoint_resolution_authorization_request(
        request: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseRequest,
    ) -> None:
        if not request.authorization_lease_id or len(request.authorization_lease_id) > 128:
            raise ValueError("endpoint-resolution authorization lease id is invalid")
        if not request.resolver_subject_id or len(request.resolver_subject_id) > 240:
            raise ValueError("endpoint-resolution authorization resolver is invalid")
        if not request.idempotency_key or len(request.idempotency_key) > 128:
            raise ValueError("endpoint-resolution authorization idempotency key is invalid")
        if len(request.request_fingerprint) != 64:
            raise ValueError("endpoint-resolution authorization fingerprint is invalid")
        if request.expected_freshness_admission_valid_until.tzinfo is None:
            raise ValueError("endpoint-resolution freshness expiry must be timezone-aware")
        if request.expected_current_selection_head_generation < 1:
            raise ValueError("endpoint-resolution authorization head generation is invalid")

    @staticmethod
    def _endpoint_resolution_authorization_contract_violation() -> NoReturn:
        raise WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError(
            "workflow_endpoint_resolution_authorization_repository_contract_violation",
            "Endpoint-resolution authorization evidence does not match durable storage.",
        )

    @classmethod
    def _route_freshness_admission_from_row(
        cls, row: WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmission:
        try:
            admission = cls._route_freshness_admission_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowEventPhysicalTransportRouteFreshnessAdmissionError(
                "workflow_route_freshness_admission_repository_contract_violation",
                "The workflow route freshness admission record is invalid.",
            ) from exc
        authority = admission.authority
        if (
            row.freshness_admission_id != admission.freshness_admission_id
            or row.physical_transport_route_binding_id
            != admission.physical_transport_route_binding_id
            or row.physical_transport_route_binding_digest
            != admission.physical_transport_route_binding_digest
            or row.transport_route_snapshot_id != admission.transport_route_snapshot_id
            or row.transport_route_snapshot_digest != admission.transport_route_snapshot_digest
            or row.current_selection_head_id != admission.current_selection_head_id
            or row.current_selection_head_digest != admission.current_selection_head_digest
            or row.current_selection_head_generation != admission.current_selection_head_generation
            or row.current_selection_head_fencing_token_digest
            != admission.current_selection_head_fencing_token_digest
            or row.route_set_id != admission.route_set_id
            or row.route_set_revision != admission.route_set_revision
            or row.selection_epoch_id != admission.selection_epoch_id
            or row.selection_epoch_revision != admission.selection_epoch_revision
            or row.selected_route_id != admission.selected_route_id
            or row.selected_route_revision != admission.selected_route_revision
            or row.selected_route_digest != admission.selected_route_digest
            or row.selection_active != admission.selection_active
            or row.selection_eligible != admission.selection_eligible
            or row.selection_suspended != admission.selection_suspended
            or row.selection_withdrawn != admission.selection_withdrawn
            or row.selection_superseded != admission.selection_superseded
            or row.policy_id != admission.policy_id
            or row.policy_version != admission.policy_version
            or row.policy_digest != admission.policy_digest
            or row.organization_id != admission.scope.organization_id
            or row.environment_id != admission.scope.environment_id
            or row.site_id != admission.scope.site_id
            or row.admitter_subject_id != admission.admitter_subject_id
            or row.evaluated_at != admission.evaluated_at
            or row.valid_until != admission.valid_until
            or row.state != admission.state.value
            or row.endpoint_resolution_authority_granted != authority.endpoint_resolution_authorized
            or row.route_selection_authority_granted != authority.route_selection_authorized
            or row.route_binding_authority_granted != authority.route_binding_authorized
            or row.credential_access_authority_granted != authority.credential_access_authorized
            or row.network_access_authority_granted != authority.network_access_authorized
            or row.readiness_probe_authority_granted != authority.readiness_probe_authorized
            or row.publication_authority_granted != authority.publication_authorized
            or row.delivery_authority_granted != authority.delivery_authorized
            or row.dispatch_authority_granted != authority.dispatch_authorized
            or row.execution_authority_granted != authority.execution_authorized
            or row.canonical_digest != admission.canonical_digest
            or row.payload != cls._route_freshness_admission_payload(admission)
        ):
            cls._route_freshness_admission_contract_violation()
        return admission

    @classmethod
    def _route_freshness_admission_model(
        cls, admission: WorkflowEventPhysicalTransportRouteFreshnessAdmission
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel:
        authority = admission.authority
        return WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel(
            freshness_admission_id=admission.freshness_admission_id,
            physical_transport_route_binding_id=admission.physical_transport_route_binding_id,
            physical_transport_route_binding_digest=(
                admission.physical_transport_route_binding_digest
            ),
            transport_route_snapshot_id=admission.transport_route_snapshot_id,
            transport_route_snapshot_digest=admission.transport_route_snapshot_digest,
            current_selection_head_id=admission.current_selection_head_id,
            current_selection_head_digest=admission.current_selection_head_digest,
            current_selection_head_generation=admission.current_selection_head_generation,
            current_selection_head_fencing_token_digest=(
                admission.current_selection_head_fencing_token_digest
            ),
            route_set_id=admission.route_set_id,
            route_set_revision=admission.route_set_revision,
            selection_epoch_id=admission.selection_epoch_id,
            selection_epoch_revision=admission.selection_epoch_revision,
            selected_route_id=admission.selected_route_id,
            selected_route_revision=admission.selected_route_revision,
            selected_route_digest=admission.selected_route_digest,
            selection_active=admission.selection_active,
            selection_eligible=admission.selection_eligible,
            selection_suspended=admission.selection_suspended,
            selection_withdrawn=admission.selection_withdrawn,
            selection_superseded=admission.selection_superseded,
            policy_id=admission.policy_id,
            policy_version=admission.policy_version,
            policy_digest=admission.policy_digest,
            organization_id=admission.scope.organization_id,
            environment_id=admission.scope.environment_id,
            site_id=admission.scope.site_id,
            admitter_subject_id=admission.admitter_subject_id,
            evaluated_at=admission.evaluated_at,
            valid_until=admission.valid_until,
            state=admission.state.value,
            endpoint_resolution_authority_granted=authority.endpoint_resolution_authorized,
            route_selection_authority_granted=authority.route_selection_authorized,
            route_binding_authority_granted=authority.route_binding_authorized,
            credential_access_authority_granted=authority.credential_access_authorized,
            network_access_authority_granted=authority.network_access_authorized,
            readiness_probe_authority_granted=authority.readiness_probe_authorized,
            publication_authority_granted=authority.publication_authorized,
            delivery_authority_granted=authority.delivery_authorized,
            dispatch_authority_granted=authority.dispatch_authorized,
            execution_authority_granted=authority.execution_authorized,
            canonical_digest=admission.canonical_digest,
            payload=cls._route_freshness_admission_payload(admission),
        )

    @classmethod
    def _route_freshness_admission_claim_model(
        cls, request: WorkflowEventPhysicalTransportRouteFreshnessAdmissionRequest
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmissionClaimModel:
        admission = request.candidate
        scope_id = cls._route_freshness_admission_idempotency_scope(
            admission.scope, admission.admitter_subject_id
        )
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_admission": cls._route_freshness_admission_payload(admission),
            "result_digest": admission.canonical_digest,
        }
        digest = canonical_digest(payload)
        return WorkflowEventPhysicalTransportRouteFreshnessAdmissionClaimModel(
            claim_id=f"wf_route_fresh_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=admission.canonical_digest,
            freshness_admission_id=admission.freshness_admission_id,
            physical_transport_route_binding_id=(admission.physical_transport_route_binding_id),
            transport_route_snapshot_id=admission.transport_route_snapshot_id,
            current_selection_head_id=admission.current_selection_head_id,
            current_selection_head_generation=admission.current_selection_head_generation,
            current_selection_head_fencing_token_digest=(
                admission.current_selection_head_fencing_token_digest
            ),
            policy_digest=admission.policy_digest,
            organization_id=admission.scope.organization_id,
            environment_id=admission.scope.environment_id,
            site_id=admission.scope.site_id,
            admitter_subject_id=admission.admitter_subject_id,
            created_at=admission.evaluated_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _route_freshness_admission_evidence_matches(
        cls,
        *,
        binding_row: WorkflowEventPhysicalTransportRouteBindingModel | None,
        route_row: EventPhysicalTransportRouteSnapshotModel | None,
        head_row: DeploymentEventTransportRouteSelectionHeadModel | None,
        request: WorkflowEventPhysicalTransportRouteFreshnessAdmissionRequest,
    ) -> bool:
        if binding_row is None or route_row is None or head_row is None:
            return False
        if (
            not head_row.selection_active
            or not head_row.selection_eligible
            or head_row.selection_suspended
            or head_row.selection_withdrawn
            or head_row.selection_superseded
            or not head_row.current
        ):
            return False
        try:
            binding = cls._physical_transport_route_binding_from_row(binding_row)
            route = cls._transport_route_snapshot_from_row(route_row)
            head = cls._route_selection_head_from_row(head_row)
        except (
            WorkflowEventPhysicalTransportRouteBindingError,
            WorkflowTransportRouteSnapshotError,
            WorkflowEventPhysicalTransportRouteFreshnessAdmissionError,
        ):
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
            and binding.scope == route.scope == head.scope == candidate.scope == request.scope
            and route.captured_at <= binding.bound_at <= candidate.evaluated_at
            and candidate.policy_id == policy.policy_id
            and candidate.policy_version == policy.policy_version
            and candidate.policy_digest == request.expected_policy_digest == policy.canonical_digest
            and candidate.admitter_subject_id == request.admitter_subject_id
            and candidate.evaluated_at == request.evaluated_at
            and candidate.valid_until
            == request.evaluated_at + timedelta(seconds=policy.validity_window_seconds)
            and candidate.state
            is WorkflowEventPhysicalTransportRouteFreshnessAdmissionState.ADMITTED_CURRENT
            and canonical_digest(candidate.digest_payload()) == candidate.canonical_digest
            and not any(binding.authority.canonical_value().values())
            and not any(route.authority.canonical_value().values())
            and not any(candidate.authority.canonical_value().values())
        )

    @classmethod
    def _route_freshness_admission_remains_current(
        cls,
        admission: WorkflowEventPhysicalTransportRouteFreshnessAdmission,
        *,
        head_row: DeploymentEventTransportRouteSelectionHeadModel,
        observed_at: datetime,
    ) -> bool:
        if (
            observed_at >= admission.valid_until
            or not head_row.current
            or not head_row.selection_active
            or not head_row.selection_eligible
            or head_row.selection_suspended
            or head_row.selection_withdrawn
            or head_row.selection_superseded
        ):
            return False
        try:
            head = cls._route_selection_head_from_row(head_row)
        except WorkflowEventPhysicalTransportRouteFreshnessAdmissionError:
            return False
        return bool(
            admission.current_selection_head_id == head.head_id
            and admission.current_selection_head_digest == head.canonical_digest
            and admission.current_selection_head_generation == head.generation
            and admission.current_selection_head_fencing_token_digest == head.fencing_token_digest
            and admission.route_set_id == head.route_set_id
            and admission.route_set_revision == head.route_set_revision
            and admission.selection_epoch_id == head.selection_epoch_id
            and admission.selection_epoch_revision == head.selection_epoch_revision
            and admission.selected_route_id == head.selected_route_id
            and admission.selected_route_revision == head.selected_route_revision
            and admission.selected_route_digest == head.selected_route_digest
        )

    @staticmethod
    def _route_selection_head_payload(
        head: DeploymentEventTransportRouteSelectionHead,
    ) -> dict[str, Any]:
        return cast(dict[str, Any], head.canonical_value())

    @staticmethod
    def _route_selection_head_to_domain(
        raw: dict[str, Any],
    ) -> DeploymentEventTransportRouteSelectionHead:
        values = dict(raw)
        values["scope"] = WorkflowScope(**cast(Any, values["scope"]))
        return DeploymentEventTransportRouteSelectionHead(**cast(Any, values))

    @staticmethod
    def _route_freshness_admission_payload(
        admission: WorkflowEventPhysicalTransportRouteFreshnessAdmission,
    ) -> dict[str, Any]:
        return cast(dict[str, Any], admission.canonical_value())

    @staticmethod
    def _route_freshness_admission_to_domain(
        raw: dict[str, Any],
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmission:
        values = dict(raw)
        values["scope"] = WorkflowScope(**cast(Any, values["scope"]))
        values["evaluated_at"] = datetime.fromisoformat(str(values["evaluated_at"]))
        values["valid_until"] = datetime.fromisoformat(str(values["valid_until"]))
        values["state"] = WorkflowEventPhysicalTransportRouteFreshnessAdmissionState(
            str(values["state"])
        )
        values["authority"] = WorkflowEventPhysicalTransportRouteFreshnessAdmissionAuthority(
            **cast(Any, values["authority"])
        )
        return WorkflowEventPhysicalTransportRouteFreshnessAdmission(**cast(Any, values))

    @staticmethod
    def _route_freshness_admission_idempotency_scope(
        scope: WorkflowScope, admitter_subject_id: str
    ) -> str:
        return canonical_digest(
            {"admitter_subject_id": admitter_subject_id, "scope": scope.canonical_value()}
        )

    @staticmethod
    def _validate_route_selection_head(head: DeploymentEventTransportRouteSelectionHead) -> None:
        if (
            not head.current
            or canonical_digest(head.digest_payload()) != head.canonical_digest
            or len(head.fencing_token_digest) != 64
        ):
            raise ValueError("authoritative route selection head is invalid")

    @staticmethod
    def _validate_route_freshness_admission_request(
        request: WorkflowEventPhysicalTransportRouteFreshnessAdmissionRequest,
    ) -> None:
        candidate = request.candidate
        if candidate.scope != request.scope:
            raise ValueError("workflow route freshness admission scope is invalid")
        if candidate.admitter_subject_id != request.admitter_subject_id:
            raise ValueError("workflow route freshness admission actor is invalid")
        if candidate.evaluated_at != request.evaluated_at:
            raise ValueError("workflow route freshness admission time is invalid")
        if (
            candidate.state
            is not WorkflowEventPhysicalTransportRouteFreshnessAdmissionState.ADMITTED_CURRENT
        ):
            raise ValueError("workflow route freshness admission state is invalid")
        if any(candidate.authority.canonical_value().values()):
            raise ValueError("workflow route freshness admission authority is unsafe")
        if not request.idempotency_key or len(request.idempotency_key) > 128:
            raise ValueError("workflow route freshness admission idempotency key is invalid")
        if len(request.request_fingerprint) != 64:
            raise ValueError("workflow route freshness admission fingerprint is invalid")
        if request.evaluated_at.tzinfo is None or candidate.valid_until.tzinfo is None:
            raise ValueError("workflow route freshness admission time must be aware")

    @staticmethod
    def _route_selection_head_sync_conflict() -> NoReturn:
        raise WorkflowEventPhysicalTransportRouteFreshnessAdmissionError(
            "workflow_route_selection_head_synchronization_conflict",
            "The authoritative route selection head synchronization conflicted.",
        )

    @staticmethod
    def _route_freshness_admission_contract_violation() -> NoReturn:
        raise WorkflowEventPhysicalTransportRouteFreshnessAdmissionError(
            "workflow_route_freshness_admission_repository_contract_violation",
            "The workflow route freshness admission does not match durable evidence.",
        )

    async def _publication_lease_acquire_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowOutboxPublicationLeaseAcquireRequest,
    ) -> WorkflowOutboxPublicationLeaseAcquireResult | None:
        candidate = request.candidate
        claim = await self._load_publication_lease_claim(
            session,
            scope=candidate.scope,
            publisher_subject_id=candidate.publisher_subject_id,
            idempotency_key=request.idempotency_key,
        )
        if claim is None:
            return None
        record = self._publication_lease_record_from_claim(claim)
        status = (
            WorkflowOutboxPublicationLeaseAcquireStatus.REPLAY
            if claim.request_fingerprint == request.request_fingerprint
            else WorkflowOutboxPublicationLeaseAcquireStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowOutboxPublicationLeaseAcquireResult(status, record.lease)

    @classmethod
    async def _load_publication_lease_claim(
        cls,
        session: AsyncSession,
        *,
        scope: WorkflowScope,
        publisher_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowOutboxPublicationLeaseAcquireClaimModel | None:
        return cast(
            WorkflowOutboxPublicationLeaseAcquireClaimModel | None,
            await session.scalar(
                select(WorkflowOutboxPublicationLeaseAcquireClaimModel).where(
                    WorkflowOutboxPublicationLeaseAcquireClaimModel.idempotency_scope_id
                    == cls._publication_lease_idempotency_scope(
                        scope,
                        publisher_subject_id,
                    ),
                    WorkflowOutboxPublicationLeaseAcquireClaimModel.idempotency_key
                    == idempotency_key,
                    WorkflowOutboxPublicationLeaseAcquireClaimModel.organization_id
                    == scope.organization_id,
                    WorkflowOutboxPublicationLeaseAcquireClaimModel.environment_id
                    == scope.environment_id,
                    WorkflowOutboxPublicationLeaseAcquireClaimModel.site_id == scope.site_id,
                    WorkflowOutboxPublicationLeaseAcquireClaimModel.publisher_subject_id
                    == publisher_subject_id,
                )
            ),
        )

    @classmethod
    def _publication_lease_record_from_claim(
        cls,
        claim: WorkflowOutboxPublicationLeaseAcquireClaimModel,
    ) -> WorkflowOutboxPublicationLeaseAcquireIdempotencyRecord:
        raw = claim.payload.get("result_lease")
        if not isinstance(raw, dict):
            cls._publication_lease_contract_violation()
        try:
            lease = cls._publication_lease_to_domain(cast(dict[str, Any], raw))
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowOutboxPublicationLeaseError(
                "workflow_outbox_publication_lease_repository_contract_violation",
                "The publication lease repository contains an invalid idempotency result.",
            ) from exc
        scope_id = cls._publication_lease_idempotency_scope(
            lease.scope,
            lease.publisher_subject_id,
        )
        expected: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": claim.request_fingerprint,
            "result_digest": lease.canonical_digest,
            "result_lease": cls._publication_lease_payload(lease),
        }
        if (
            claim.idempotency_scope_id != scope_id
            or claim.result_digest != lease.canonical_digest
            or claim.publication_lease_id != lease.publication_lease_id
            or claim.outbox_entry_id != lease.outbox_entry_id
            or claim.plan_id != lease.plan_id
            or claim.organization_id != lease.scope.organization_id
            or claim.environment_id != lease.scope.environment_id
            or claim.site_id != lease.scope.site_id
            or claim.publisher_subject_id != lease.publisher_subject_id
            or claim.payload != expected
            or claim.canonical_digest != canonical_digest(expected)
        ):
            cls._publication_lease_contract_violation()
        return WorkflowOutboxPublicationLeaseAcquireIdempotencyRecord(
            claim.request_fingerprint,
            lease,
        )

    @classmethod
    def _publication_lease_from_row(
        cls,
        row: WorkflowOutboxPublicationLeaseModel,
    ) -> WorkflowOutboxPublicationLease:
        try:
            lease = cls._publication_lease_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowOutboxPublicationLeaseError(
                "workflow_outbox_publication_lease_repository_contract_violation",
                "The publication lease repository contains an invalid lease.",
            ) from exc
        if (
            row.publication_lease_id != lease.publication_lease_id
            or row.outbox_entry_id != lease.outbox_entry_id
            or row.outbox_entry_digest != lease.outbox_entry_digest
            or row.dispatch_intent_id != lease.dispatch_intent_id
            or row.dispatch_intent_digest != lease.dispatch_intent_digest
            or row.plan_id != lease.plan_id
            or row.plan_digest != lease.plan_digest
            or row.run_id != lease.run_id
            or row.run_digest != lease.run_digest
            or row.step_run_id != lease.step_run_id
            or row.step_run_digest != lease.step_run_digest
            or row.step_id != lease.step_id
            or row.attempt_id != lease.attempt_id
            or row.attempt_digest != lease.attempt_digest
            or row.attempt_number != lease.attempt_number
            or row.organization_id != lease.scope.organization_id
            or row.environment_id != lease.scope.environment_id
            or row.site_id != lease.scope.site_id
            or row.target_type != lease.target_type
            or row.target_id != lease.target_id
            or row.orchestration_lease_id != lease.orchestration_lease_id
            or row.orchestration_lease_digest != lease.orchestration_lease_digest
            or row.orchestration_fencing_token != lease.orchestration_fencing_token
            or row.publisher_subject_id != lease.publisher_subject_id
            or row.acquired_at != lease.acquired_at
            or row.last_heartbeat_at != lease.last_heartbeat_at
            or row.expires_at != lease.expires_at
            or row.publication_fencing_token != lease.publication_fencing_token
            or row.state != lease.state.value
            or row.version < 1
            or row.canonical_digest != lease.canonical_digest
        ):
            cls._publication_lease_contract_violation()
        return lease

    @classmethod
    def _publication_lease_model(
        cls,
        lease: WorkflowOutboxPublicationLease,
        *,
        version: int,
    ) -> WorkflowOutboxPublicationLeaseModel:
        return WorkflowOutboxPublicationLeaseModel(
            **cls._publication_lease_values(lease, version=version)
        )

    @classmethod
    def _publication_lease_values(
        cls,
        lease: WorkflowOutboxPublicationLease,
        *,
        version: int,
    ) -> dict[str, Any]:
        return {
            "publication_lease_id": lease.publication_lease_id,
            "outbox_entry_id": lease.outbox_entry_id,
            "outbox_entry_digest": lease.outbox_entry_digest,
            "dispatch_intent_id": lease.dispatch_intent_id,
            "dispatch_intent_digest": lease.dispatch_intent_digest,
            "plan_id": lease.plan_id,
            "plan_digest": lease.plan_digest,
            "run_id": lease.run_id,
            "run_digest": lease.run_digest,
            "step_run_id": lease.step_run_id,
            "step_run_digest": lease.step_run_digest,
            "step_id": lease.step_id,
            "attempt_id": lease.attempt_id,
            "attempt_digest": lease.attempt_digest,
            "attempt_number": lease.attempt_number,
            "organization_id": lease.scope.organization_id,
            "environment_id": lease.scope.environment_id,
            "site_id": lease.scope.site_id,
            "target_type": lease.target_type,
            "target_id": lease.target_id,
            "orchestration_lease_id": lease.orchestration_lease_id,
            "orchestration_lease_digest": lease.orchestration_lease_digest,
            "orchestration_fencing_token": lease.orchestration_fencing_token,
            "publisher_subject_id": lease.publisher_subject_id,
            "acquired_at": lease.acquired_at,
            "last_heartbeat_at": lease.last_heartbeat_at,
            "expires_at": lease.expires_at,
            "publication_fencing_token": lease.publication_fencing_token,
            "state": lease.state.value,
            "version": version,
            "canonical_digest": lease.canonical_digest,
            "payload": cls._publication_lease_payload(lease),
        }

    @classmethod
    def _publication_lease_claim_model(
        cls,
        request: WorkflowOutboxPublicationLeaseAcquireRequest,
    ) -> WorkflowOutboxPublicationLeaseAcquireClaimModel:
        lease = request.candidate
        scope_id = cls._publication_lease_idempotency_scope(
            lease.scope,
            lease.publisher_subject_id,
        )
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "request_fingerprint": request.request_fingerprint,
            "result_digest": lease.canonical_digest,
            "result_lease": cls._publication_lease_payload(lease),
        }
        digest = canonical_digest(payload)
        return WorkflowOutboxPublicationLeaseAcquireClaimModel(
            claim_id=f"workflow_outbox_publication_claim_{sha256(digest.encode()).hexdigest()[:32]}",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=lease.canonical_digest,
            publication_lease_id=lease.publication_lease_id,
            outbox_entry_id=lease.outbox_entry_id,
            plan_id=lease.plan_id,
            organization_id=lease.scope.organization_id,
            environment_id=lease.scope.environment_id,
            site_id=lease.scope.site_id,
            publisher_subject_id=lease.publisher_subject_id,
            created_at=request.requested_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _publication_lease_evidence_matches(
        cls,
        *,
        outbox_row: WorkflowDispatchOutboxEntryModel | None,
        plan_row: WorkflowRunPlanModel | None,
        orchestration_lease_row: WorkflowOrchestrationLeaseModel | None,
        request: WorkflowOutboxPublicationLeaseAcquireRequest,
    ) -> bool:
        if outbox_row is None or plan_row is None or orchestration_lease_row is None:
            return False
        candidate = request.candidate
        try:
            outbox = cls._dispatch_outbox_from_row(outbox_row)
            orchestration_lease = cls._lease_from_row(orchestration_lease_row)
        except (WorkflowDispatchIntentStagingError, WorkflowOrchestrationLeaseError) as exc:
            raise WorkflowOutboxPublicationLeaseError(
                "workflow_outbox_publication_lease_repository_contract_violation",
                "Workflow evidence is inconsistent during publication lease acquisition.",
            ) from exc
        return bool(
            outbox.state is WorkflowDispatchOutboxState.PENDING_PUBLICATION
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
            and plan_row.state == WorkflowPlanState.PLANNED.value
            and plan_row.canonical_digest == candidate.plan_digest
            and plan_row.organization_id == candidate.scope.organization_id
            and plan_row.environment_id == candidate.scope.environment_id
            and plan_row.site_id == candidate.scope.site_id
            and plan_row.target_type == candidate.target_type
            and plan_row.target_id == candidate.target_id
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

    @classmethod
    def _publication_lease_mutation_evidence_matches(
        cls,
        *,
        outbox_row: WorkflowDispatchOutboxEntryModel | None,
        plan_row: WorkflowRunPlanModel | None,
        orchestration_lease_row: WorkflowOrchestrationLeaseModel | None,
        request: WorkflowOutboxPublicationLeaseMutationRequest,
    ) -> bool:
        acquire_shape = WorkflowOutboxPublicationLeaseAcquireRequest(
            expected_outbox_entry_digest=request.expected_outbox_entry_digest,
            expected_orchestration_lease_id=request.expected_orchestration_lease_id,
            expected_orchestration_lease_digest=request.expected_orchestration_lease_digest,
            expected_orchestration_fencing_token=request.expected_orchestration_fencing_token,
            candidate=request.updated_lease,
            requested_at=request.requested_at,
            idempotency_key="mutation-validation",
            request_fingerprint="0" * 64,
            expected_current_lease_digest=request.expected_publication_lease_digest,
            expected_current_publication_fencing_token=(request.expected_publication_fencing_token),
        )
        return cls._publication_lease_evidence_matches(
            outbox_row=outbox_row,
            plan_row=plan_row,
            orchestration_lease_row=orchestration_lease_row,
            request=acquire_shape,
        )

    @staticmethod
    def _publication_lease_acquire_generation_matches(
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

    @staticmethod
    def _publication_lease_idempotency_scope(
        scope: WorkflowScope,
        publisher_subject_id: str,
    ) -> str:
        return canonical_digest(
            {
                "publisher_subject_id": publisher_subject_id,
                "scope": scope.canonical_value(),
            }
        )

    @staticmethod
    def _publication_lease_payload(
        lease: WorkflowOutboxPublicationLease,
    ) -> dict[str, Any]:
        return cast(dict[str, Any], lease.canonical_value())

    @staticmethod
    def _publication_lease_to_domain(raw: dict[str, Any]) -> WorkflowOutboxPublicationLease:
        payload = dict(raw)
        payload["scope"] = WorkflowScope(**cast(Any, payload["scope"]))
        payload["acquired_at"] = datetime.fromisoformat(str(payload["acquired_at"]))
        payload["last_heartbeat_at"] = datetime.fromisoformat(str(payload["last_heartbeat_at"]))
        payload["expires_at"] = datetime.fromisoformat(str(payload["expires_at"]))
        payload["state"] = WorkflowOutboxPublicationLeaseState(str(payload["state"]))
        payload["authority"] = WorkflowPlanAuthority(**cast(Any, payload["authority"]))
        return WorkflowOutboxPublicationLease(**cast(Any, payload))

    @staticmethod
    def _validate_publication_lease_acquire_request(
        request: WorkflowOutboxPublicationLeaseAcquireRequest,
    ) -> None:
        candidate = request.candidate
        if (
            candidate.state is not WorkflowOutboxPublicationLeaseState.ACTIVE
            or candidate.grants_publication_authority
            or candidate.grants_delivery_authority
            or candidate.grants_dispatch_authority
            or candidate.grants_execution_authority
        ):
            raise ValueError("workflow outbox publication lease acquisition payload is unsafe")
        if not request.idempotency_key or len(request.idempotency_key) > 128:
            raise ValueError("workflow publication lease idempotency key is invalid")
        if len(request.request_fingerprint) != 64:
            raise ValueError("workflow publication lease request fingerprint is invalid")
        if request.requested_at.tzinfo is None:
            raise ValueError("workflow publication lease acquisition time must be timezone-aware")

    @staticmethod
    def _validate_publication_lease_mutation_request(
        request: WorkflowOutboxPublicationLeaseMutationRequest,
    ) -> None:
        candidate = request.updated_lease
        if (
            candidate.grants_publication_authority
            or candidate.grants_delivery_authority
            or candidate.grants_dispatch_authority
            or candidate.grants_execution_authority
        ):
            raise ValueError("workflow outbox publication lease mutation payload is unsafe")
        if request.requested_at.tzinfo is None:
            raise ValueError("workflow publication lease mutation time must be timezone-aware")

    @staticmethod
    def _publication_lease_contract_violation() -> None:
        raise WorkflowOutboxPublicationLeaseError(
            "workflow_outbox_publication_lease_repository_contract_violation",
            "The workflow outbox publication lease does not match its canonical payload.",
        )

    async def _lease_acquire_after_integrity(
        self, *, request: WorkflowLeaseAcquireRequest
    ) -> WorkflowLeaseAcquireResult:
        async with self._sessions() as session:
            replay = await self._lease_acquire_replay(session, request=request)
            if replay is not None:
                return replay
        latest = await self.get_lease_by_plan_id(plan_id=request.candidate.plan_id)
        return WorkflowLeaseAcquireResult(WorkflowLeaseAcquireStatus.CONTENDED, latest)

    async def _lease_acquire_replay(
        self,
        session: AsyncSession,
        *,
        request: WorkflowLeaseAcquireRequest,
    ) -> WorkflowLeaseAcquireResult | None:
        candidate = request.candidate
        claim = await self._load_lease_claim(
            session,
            operation="acquire",
            scope=candidate.scope,
            worker_subject_id=candidate.worker_subject_id,
            idempotency_key=request.idempotency_key,
        )
        if claim is None:
            return None
        record = self._lease_record_from_claim(claim)
        status = (
            WorkflowLeaseAcquireStatus.REPLAY
            if claim.request_fingerprint == request.request_fingerprint
            else WorkflowLeaseAcquireStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowLeaseAcquireResult(status, record.lease)

    @classmethod
    async def _load_lease_claim(
        cls,
        session: AsyncSession,
        *,
        operation: str,
        scope: WorkflowScope,
        worker_subject_id: str,
        idempotency_key: str,
    ) -> WorkflowLeaseIdempotencyModel | None:
        return cast(
            WorkflowLeaseIdempotencyModel | None,
            await session.scalar(
                select(WorkflowLeaseIdempotencyModel).where(
                    WorkflowLeaseIdempotencyModel.operation == operation,
                    WorkflowLeaseIdempotencyModel.idempotency_scope_id
                    == cls._lease_idempotency_scope(scope, worker_subject_id),
                    WorkflowLeaseIdempotencyModel.idempotency_key == idempotency_key,
                    WorkflowLeaseIdempotencyModel.organization_id == scope.organization_id,
                    WorkflowLeaseIdempotencyModel.environment_id == scope.environment_id,
                    WorkflowLeaseIdempotencyModel.site_id == scope.site_id,
                    WorkflowLeaseIdempotencyModel.worker_subject_id == worker_subject_id,
                )
            ),
        )

    @classmethod
    def _lease_record_from_claim(
        cls, claim: WorkflowLeaseIdempotencyModel
    ) -> WorkflowLeaseAcquireIdempotencyRecord:
        raw = claim.payload.get("result_lease")
        if not isinstance(raw, dict):
            cls._lease_contract_violation()
        try:
            lease = cls._lease_to_domain(cast(dict[str, Any], raw))
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowOrchestrationLeaseError(
                "workflow_lease_repository_contract_violation",
                "The workflow lease repository contains an invalid idempotency result.",
            ) from exc
        expected_payload: dict[str, Any] = {
            "idempotency_key": claim.idempotency_key,
            "idempotency_scope_id": claim.idempotency_scope_id,
            "operation": claim.operation,
            "request_fingerprint": claim.request_fingerprint,
            "result_digest": claim.result_digest,
            "result_lease": cls._lease_payload(lease),
        }
        if (
            claim.operation != "acquire"
            or claim.lease_id != lease.lease_id
            or claim.plan_id != lease.plan_id
            or claim.result_digest != lease.canonical_digest
            or claim.organization_id != lease.scope.organization_id
            or claim.environment_id != lease.scope.environment_id
            or claim.site_id != lease.scope.site_id
            or claim.worker_subject_id != lease.worker_subject_id
            or claim.idempotency_scope_id
            != cls._lease_idempotency_scope(lease.scope, lease.worker_subject_id)
            or claim.payload != expected_payload
            or claim.canonical_digest != canonical_digest(expected_payload)
        ):
            cls._lease_contract_violation()
        return WorkflowLeaseAcquireIdempotencyRecord(claim.request_fingerprint, lease)

    @classmethod
    def _lease_from_row(cls, row: WorkflowOrchestrationLeaseModel) -> WorkflowOrchestrationLease:
        try:
            lease = cls._lease_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowOrchestrationLeaseError(
                "workflow_lease_repository_contract_violation",
                "The workflow lease repository contains an invalid lease.",
            ) from exc
        if (
            row.lease_id != lease.lease_id
            or row.plan_id != lease.plan_id
            or row.plan_digest != lease.plan_digest
            or row.organization_id != lease.scope.organization_id
            or row.environment_id != lease.scope.environment_id
            or row.site_id != lease.scope.site_id
            or row.target_type != lease.target_type
            or row.target_id != lease.target_id
            or row.worker_subject_id != lease.worker_subject_id
            or row.acquired_at != lease.acquired_at
            or row.last_heartbeat_at != lease.last_heartbeat_at
            or row.expires_at != lease.expires_at
            or row.fencing_token != lease.fencing_token
            or row.state != lease.state.value
            or row.version < 1
            or row.canonical_digest != lease.canonical_digest
        ):
            cls._lease_contract_violation()
        return lease

    @staticmethod
    def _lease_contract_violation() -> None:
        raise WorkflowOrchestrationLeaseError(
            "workflow_lease_repository_contract_violation",
            "The workflow lease record does not match its canonical payload.",
        )

    @classmethod
    def _lease_model(
        cls, lease: WorkflowOrchestrationLease, *, version: int
    ) -> WorkflowOrchestrationLeaseModel:
        return WorkflowOrchestrationLeaseModel(**cls._lease_values(lease, version=version))

    @classmethod
    def _lease_values(cls, lease: WorkflowOrchestrationLease, *, version: int) -> dict[str, Any]:
        return {
            "lease_id": lease.lease_id,
            "plan_id": lease.plan_id,
            "plan_digest": lease.plan_digest,
            "organization_id": lease.scope.organization_id,
            "environment_id": lease.scope.environment_id,
            "site_id": lease.scope.site_id,
            "target_type": lease.target_type,
            "target_id": lease.target_id,
            "worker_subject_id": lease.worker_subject_id,
            "acquired_at": lease.acquired_at,
            "last_heartbeat_at": lease.last_heartbeat_at,
            "expires_at": lease.expires_at,
            "fencing_token": lease.fencing_token,
            "state": lease.state.value,
            "version": version,
            "canonical_digest": lease.canonical_digest,
            "payload": cls._lease_payload(lease),
        }

    @classmethod
    def _lease_claim_model(
        cls, request: WorkflowLeaseAcquireRequest
    ) -> WorkflowLeaseIdempotencyModel:
        lease = request.candidate
        scope_id = cls._lease_idempotency_scope(lease.scope, lease.worker_subject_id)
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "operation": "acquire",
            "request_fingerprint": request.request_fingerprint,
            "result_digest": lease.canonical_digest,
            "result_lease": cls._lease_payload(lease),
        }
        digest = canonical_digest(payload)
        return WorkflowLeaseIdempotencyModel(
            record_id=f"workflow_lease_idem_{sha256(digest.encode()).hexdigest()[:32]}",
            operation="acquire",
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=lease.canonical_digest,
            lease_id=lease.lease_id,
            plan_id=lease.plan_id,
            organization_id=lease.scope.organization_id,
            environment_id=lease.scope.environment_id,
            site_id=lease.scope.site_id,
            worker_subject_id=lease.worker_subject_id,
            created_at=request.requested_at,
            canonical_digest=digest,
            payload=payload,
        )

    @staticmethod
    def _lease_idempotency_scope(scope: WorkflowScope, worker_subject_id: str) -> str:
        return canonical_digest(
            {"scope": scope.canonical_value(), "worker_subject_id": worker_subject_id}
        )

    @staticmethod
    def _lease_plan_matches(
        row: WorkflowRunPlanModel | None,
        candidate: WorkflowOrchestrationLease,
        expected_plan_digest: str,
    ) -> bool:
        return bool(
            row is not None
            and row.state == WorkflowPlanState.PLANNED.value
            and row.canonical_digest == expected_plan_digest == candidate.plan_digest
            and row.organization_id == candidate.scope.organization_id
            and row.environment_id == candidate.scope.environment_id
            and row.site_id == candidate.scope.site_id
            and row.target_type == candidate.target_type
            and row.target_id == candidate.target_id
        )

    @staticmethod
    def _valid_lease_takeover(
        current: WorkflowOrchestrationLease | None,
        candidate: WorkflowOrchestrationLease,
        request: WorkflowLeaseAcquireRequest,
    ) -> bool:
        if current is None:
            return (
                request.expected_current_lease_digest is None
                and request.expected_current_fencing_token is None
                and candidate.fencing_token == 1
            )
        return (
            current.canonical_digest == request.expected_current_lease_digest
            and current.fencing_token == request.expected_current_fencing_token
            and current.effective_state(requested_at=request.requested_at)
            is not WorkflowOrchestrationLeaseEffectiveState.ACTIVE
            and candidate.fencing_token == current.fencing_token + 1
        )

    @staticmethod
    def _valid_lease_mutation(
        current: WorkflowOrchestrationLease,
        candidate: WorkflowOrchestrationLease,
        request: WorkflowLeaseMutationRequest,
    ) -> bool:
        return (
            current.lease_id == request.expected_lease_id
            and current.canonical_digest == request.expected_lease_digest
            and current.fencing_token == request.expected_fencing_token
            and current.worker_subject_id == request.worker_subject_id
            and current.effective_state(requested_at=request.requested_at)
            is WorkflowOrchestrationLeaseEffectiveState.ACTIVE
            and candidate.lease_id == current.lease_id
            and candidate.plan_id == current.plan_id
            and candidate.plan_digest == current.plan_digest
            and candidate.scope == current.scope
            and candidate.target_id == current.target_id
            and candidate.target_type == current.target_type
            and candidate.worker_subject_id == current.worker_subject_id
            and candidate.acquired_at == current.acquired_at
            and candidate.fencing_token == current.fencing_token
        )

    @classmethod
    def _lease_payload(cls, lease: WorkflowOrchestrationLease) -> dict[str, Any]:
        return cast(dict[str, Any], cls._normalize(lease.canonical_value()))

    @staticmethod
    def _lease_to_domain(raw: dict[str, Any]) -> WorkflowOrchestrationLease:
        payload = dict(raw)
        payload["scope"] = WorkflowScope(**cast(Any, payload["scope"]))
        payload["acquired_at"] = datetime.fromisoformat(str(payload["acquired_at"]))
        payload["last_heartbeat_at"] = datetime.fromisoformat(str(payload["last_heartbeat_at"]))
        payload["expires_at"] = datetime.fromisoformat(str(payload["expires_at"]))
        payload["state"] = WorkflowOrchestrationLeaseState(str(payload["state"]))
        return WorkflowOrchestrationLease(**cast(Any, payload))

    async def _cancellation_result_after_integrity_conflict(
        self,
        *,
        request: WorkflowPlanCancellationRequest,
    ) -> WorkflowPlanCancellationResult:
        async with self._sessions() as session:
            replay = await self._cancellation_replay_result(session, request=request)
            if replay is not None:
                return replay
        current = await self.get_by_id(plan_id=request.cancelled_plan.plan_id)
        return WorkflowPlanCancellationResult(
            WorkflowPlanCancellationStatus.STATE_CONFLICT
            if current is not None
            else WorkflowPlanCancellationStatus.NOT_FOUND,
            current,
        )

    async def _cancellation_replay_result(
        self,
        session: AsyncSession,
        *,
        request: WorkflowPlanCancellationRequest,
    ) -> WorkflowPlanCancellationResult | None:
        candidate = request.cancelled_plan
        claim = await self._load_claim(
            session,
            operation="cancel",
            scope=candidate.scope,
            subject_id=request.actor_subject_id,
            idempotency_key=request.idempotency_key,
        )
        if claim is None:
            return None
        plan = self._plan_from_claim(claim, expected_operation="cancel")
        status = (
            WorkflowPlanCancellationStatus.REPLAY
            if claim.request_fingerprint == request.request_fingerprint
            else WorkflowPlanCancellationStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowPlanCancellationResult(status, plan)

    async def _replay_result(
        self,
        session: AsyncSession,
        *,
        plan: WorkflowRunPlan,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> WorkflowPlanMutationResult | None:
        claim = await self._load_claim(
            session,
            operation="create",
            scope=plan.scope,
            subject_id=plan.creator_subject_id,
            idempotency_key=idempotency_key,
        )
        if claim is None:
            return None
        claimed_plan = self._plan_from_claim(claim, expected_operation="create")
        status = (
            WorkflowPlanMutationStatus.REPLAY
            if claim.request_fingerprint == request_fingerprint
            else WorkflowPlanMutationStatus.IDEMPOTENCY_CONFLICT
        )
        return WorkflowPlanMutationResult(status, claimed_plan)

    @classmethod
    async def _load_claim(
        cls,
        session: AsyncSession,
        *,
        operation: str,
        scope: WorkflowScope,
        subject_id: str,
        idempotency_key: str,
    ) -> WorkflowIdempotencyModel | None:
        return cast(
            WorkflowIdempotencyModel | None,
            await session.scalar(
                select(WorkflowIdempotencyModel).where(
                    WorkflowIdempotencyModel.operation == operation,
                    WorkflowIdempotencyModel.idempotency_scope_id
                    == cls._idempotency_scope(scope, subject_id),
                    WorkflowIdempotencyModel.idempotency_key == idempotency_key,
                    WorkflowIdempotencyModel.organization_id == scope.organization_id,
                    WorkflowIdempotencyModel.environment_id == scope.environment_id,
                    WorkflowIdempotencyModel.site_id == scope.site_id,
                    WorkflowIdempotencyModel.creator_subject_id == subject_id,
                )
            ),
        )

    @classmethod
    def _plan_from_claim(
        cls,
        claim: WorkflowIdempotencyModel,
        *,
        expected_operation: str,
    ) -> WorkflowRunPlan:
        raw = claim.payload.get("result_plan")
        if not isinstance(raw, dict):
            cls._contract_violation()
        try:
            plan = cls._to_domain(cast(dict[str, Any], raw))
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowPlanningError(
                "workflow_repository_contract_violation",
                "The workflow repository contains an invalid idempotency result.",
            ) from exc
        if (
            claim.operation != expected_operation
            or claim.plan_id != plan.plan_id
            or claim.result_digest != plan.canonical_digest
            or claim.organization_id != plan.scope.organization_id
            or claim.environment_id != plan.scope.environment_id
            or claim.site_id != plan.scope.site_id
            or claim.creator_subject_id
            != (
                plan.creator_subject_id
                if expected_operation == "create"
                else plan.transition_history[-1].actor_subject_id
            )
            or claim.idempotency_scope_id
            != cls._idempotency_scope(
                plan.scope,
                plan.creator_subject_id
                if expected_operation == "create"
                else plan.transition_history[-1].actor_subject_id,
            )
        ):
            cls._contract_violation()
        return plan

    @classmethod
    def _plan_from_row(
        cls,
        row: WorkflowRunPlanModel,
        transitions: tuple[WorkflowPlanTransition, ...],
    ) -> WorkflowRunPlan:
        try:
            plan = cls._to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowPlanningError(
                "workflow_repository_contract_violation",
                "The workflow repository contains an invalid run plan.",
            ) from exc
        if (
            row.plan_id != plan.plan_id
            or row.state != plan.state.value
            or row.definition_id != plan.definition_id
            or row.definition_version != plan.definition_version
            or row.definition_digest != plan.definition_digest
            or row.organization_id != plan.scope.organization_id
            or row.environment_id != plan.scope.environment_id
            or row.site_id != plan.scope.site_id
            or row.creator_subject_id != plan.creator_subject_id
            or row.target_type != plan.target_type
            or row.target_id != plan.target_id
            or row.canonical_input_digest != plan.canonical_input_digest
            or row.created_at != plan.created_at
            or row.canonical_digest != plan.canonical_digest
            or plan.transition_history != transitions
            or row.state_version != len(transitions) + 1
            or row.updated_at != (transitions[-1].occurred_at if transitions else plan.created_at)
        ):
            cls._contract_violation()
        return plan

    @staticmethod
    def _contract_violation() -> None:
        raise WorkflowPlanningError(
            "workflow_repository_contract_violation",
            "The workflow repository record does not match its canonical payload.",
        )

    @classmethod
    def _plan_model(cls, plan: WorkflowRunPlan) -> WorkflowRunPlanModel:
        updated_at = (
            plan.transition_history[-1].occurred_at if plan.transition_history else plan.created_at
        )
        return WorkflowRunPlanModel(
            plan_id=plan.plan_id,
            state=plan.state.value,
            definition_id=plan.definition_id,
            definition_version=plan.definition_version,
            definition_digest=plan.definition_digest,
            organization_id=plan.scope.organization_id,
            environment_id=plan.scope.environment_id,
            site_id=plan.scope.site_id,
            creator_subject_id=plan.creator_subject_id,
            target_type=plan.target_type,
            target_id=plan.target_id,
            canonical_input_digest=plan.canonical_input_digest,
            created_at=plan.created_at,
            updated_at=updated_at,
            state_version=len(plan.transition_history) + 1,
            canonical_digest=plan.canonical_digest,
            payload=cls._plan_payload(plan),
        )

    @classmethod
    def _transition_model(
        cls,
        plan_id: str,
        transition: WorkflowPlanTransition,
        *,
        sequence: int,
    ) -> WorkflowPlanTransitionModel:
        return WorkflowPlanTransitionModel(
            transition_id=transition.transition_id,
            plan_id=plan_id,
            sequence=sequence,
            from_state=transition.prior_state.value,
            to_state=transition.new_state.value,
            actor_subject_id=transition.actor_subject_id,
            organization_id=transition.scope.organization_id,
            environment_id=transition.scope.environment_id,
            site_id=transition.scope.site_id,
            target_type=transition.target_type,
            target_id=transition.target_id,
            reason_digest=transition.reason_digest,
            correlation_id=transition.correlation_id,
            occurred_at=transition.occurred_at,
            canonical_digest=transition.canonical_digest,
            payload=cast(dict[str, Any], cls._normalize(asdict(transition))),
        )

    @classmethod
    def _cancellation_idempotency_model(
        cls,
        request: WorkflowPlanCancellationRequest,
        *,
        operation: str,
        scope_id: str,
    ) -> WorkflowIdempotencyModel:
        plan = request.cancelled_plan
        transition = plan.transition_history[-1]
        payload: dict[str, Any] = {
            "idempotency_key": request.idempotency_key,
            "idempotency_scope_id": scope_id,
            "operation": operation,
            "request_fingerprint": request.request_fingerprint,
            "result_digest": plan.canonical_digest,
            "result_plan": cls._plan_payload(plan),
            "transition_digest": transition.canonical_digest,
        }
        digest = canonical_digest(payload)
        return WorkflowIdempotencyModel(
            record_id=f"workflow_idem_{sha256(digest.encode()).hexdigest()[:32]}",
            operation=operation,
            idempotency_scope_id=scope_id,
            idempotency_key=request.idempotency_key,
            request_fingerprint=request.request_fingerprint,
            result_digest=plan.canonical_digest,
            plan_id=plan.plan_id,
            organization_id=plan.scope.organization_id,
            environment_id=plan.scope.environment_id,
            site_id=plan.scope.site_id,
            creator_subject_id=request.actor_subject_id,
            created_at=transition.occurred_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _idempotency_model(
        cls,
        plan: WorkflowRunPlan,
        *,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> WorkflowIdempotencyModel:
        scope_id = cls._idempotency_scope(plan.scope, plan.creator_subject_id)
        payload: dict[str, Any] = {
            "idempotency_key": idempotency_key,
            "idempotency_scope_id": scope_id,
            "operation": "create",
            "request_fingerprint": request_fingerprint,
            "result_digest": plan.canonical_digest,
            "result_plan": cls._plan_payload(plan),
        }
        digest = canonical_digest(payload)
        return WorkflowIdempotencyModel(
            record_id=f"workflow_idem_{sha256(digest.encode()).hexdigest()[:32]}",
            operation="create",
            idempotency_scope_id=scope_id,
            idempotency_key=idempotency_key,
            request_fingerprint=request_fingerprint,
            result_digest=plan.canonical_digest,
            plan_id=plan.plan_id,
            organization_id=plan.scope.organization_id,
            environment_id=plan.scope.environment_id,
            site_id=plan.scope.site_id,
            creator_subject_id=plan.creator_subject_id,
            created_at=plan.created_at,
            canonical_digest=digest,
            payload=payload,
        )

    @classmethod
    def _plan_payload(cls, plan: WorkflowRunPlan) -> dict[str, Any]:
        return cast(dict[str, Any], cls._normalize(asdict(plan)))

    @staticmethod
    def _idempotency_scope(scope: WorkflowScope, creator_subject_id: str) -> str:
        return canonical_digest(
            {"creator_subject_id": creator_subject_id, "scope": scope.canonical_value()}
        )

    @staticmethod
    def _valid_cancellation(
        *,
        current: WorkflowRunPlan,
        candidate: WorkflowRunPlan,
        actor_subject_id: str,
    ) -> bool:
        if (
            candidate.state is not WorkflowPlanState.CANCELLED
            or len(candidate.transition_history) != 1
        ):
            return False
        transition = candidate.transition_history[0]
        return (
            transition.actor_subject_id == actor_subject_id
            and transition.prior_state is WorkflowPlanState.PLANNED
            and transition.new_state is WorkflowPlanState.CANCELLED
            and current.plan_id == candidate.plan_id
            and current.definition_id == candidate.definition_id
            and current.definition_version == candidate.definition_version
            and current.definition_digest == candidate.definition_digest
            and current.scope == candidate.scope
            and current.target_id == candidate.target_id
            and current.target_type == candidate.target_type
            and current.canonical_input_digest == candidate.canonical_input_digest
            and current.creator_subject_id == candidate.creator_subject_id
            and current.created_at == candidate.created_at
            and current.steps == candidate.steps
            and current.durable == candidate.durable
            and current.authority == candidate.authority
            and current.safety_notice == candidate.safety_notice
            and not current.transition_history
        )

    @classmethod
    async def _load_transitions(
        cls,
        session: AsyncSession,
        plan_ids: tuple[str, ...],
    ) -> dict[str, tuple[WorkflowPlanTransition, ...]]:
        if not plan_ids:
            return {}
        rows = (
            await session.scalars(
                select(WorkflowPlanTransitionModel)
                .where(WorkflowPlanTransitionModel.plan_id.in_(plan_ids))
                .order_by(
                    WorkflowPlanTransitionModel.plan_id,
                    WorkflowPlanTransitionModel.sequence,
                )
            )
        ).all()
        grouped: dict[str, list[WorkflowPlanTransition]] = {}
        for row in rows:
            grouped.setdefault(row.plan_id, []).append(cls._transition_from_row(row))
        return {plan_id: tuple(items) for plan_id, items in grouped.items()}

    @classmethod
    def _transition_from_row(cls, row: WorkflowPlanTransitionModel) -> WorkflowPlanTransition:
        try:
            transition = cls._transition_to_domain(row.payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkflowPlanningError(
                "workflow_repository_contract_violation",
                "The workflow repository contains an invalid transition.",
            ) from exc
        if (
            row.transition_id != transition.transition_id
            or row.sequence != 1
            or row.from_state != transition.prior_state.value
            or row.to_state != transition.new_state.value
            or row.actor_subject_id != transition.actor_subject_id
            or row.organization_id != transition.scope.organization_id
            or row.environment_id != transition.scope.environment_id
            or row.site_id != transition.scope.site_id
            or row.target_type != transition.target_type
            or row.target_id != transition.target_id
            or row.reason_digest != transition.reason_digest
            or row.correlation_id != transition.correlation_id
            or row.occurred_at != transition.occurred_at
            or row.canonical_digest != transition.canonical_digest
        ):
            cls._contract_violation()
        return transition

    @staticmethod
    def _normalize(value: object) -> object:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, dict):
            return {
                str(key): PostgreSQLWorkflowPlanRepository._normalize(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [PostgreSQLWorkflowPlanRepository._normalize(item) for item in value]
        return value

    @staticmethod
    def _to_domain(raw: dict[str, Any]) -> WorkflowRunPlan:
        payload = dict(raw)
        payload["scope"] = WorkflowScope(**cast(Any, payload["scope"]))
        payload["created_at"] = datetime.fromisoformat(str(payload["created_at"]))
        payload["state"] = WorkflowPlanState(str(payload["state"]))
        payload["steps"] = tuple(
            WorkflowPlanStep(
                step_id=str(item["step_id"]),
                ordinal=int(item["ordinal"]),
                kind=WorkflowStepKind(str(item["kind"])),
                capability_class=WorkflowCapabilityClass(str(item["capability_class"])),
                state=WorkflowPlanStepState(str(item["state"])),
            )
            for item in payload["steps"]
        )
        payload["authority"] = WorkflowPlanAuthority(**cast(Any, payload["authority"]))
        payload["transition_history"] = tuple(
            PostgreSQLWorkflowPlanRepository._transition_to_domain(cast(dict[str, Any], item))
            for item in payload.get("transition_history", ())
        )
        return WorkflowRunPlan(**cast(Any, payload))

    @staticmethod
    def _transition_to_domain(raw: dict[str, Any]) -> WorkflowPlanTransition:
        payload = dict(raw)
        payload["prior_state"] = WorkflowPlanState(str(payload["prior_state"]))
        payload["new_state"] = WorkflowPlanState(str(payload["new_state"]))
        payload["scope"] = WorkflowScope(**cast(Any, payload["scope"]))
        payload["occurred_at"] = datetime.fromisoformat(str(payload["occurred_at"]))
        return WorkflowPlanTransition(**cast(Any, payload))
