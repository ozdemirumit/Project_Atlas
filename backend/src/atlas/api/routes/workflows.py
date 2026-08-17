from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn, cast

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_workflow_definition_read,
    authorize_workflow_physical_transport_credential_access_authorization_lease_read,
    authorize_workflow_physical_transport_credential_assignment_binding_bind,
    authorize_workflow_physical_transport_credential_assignment_binding_read,
    authorize_workflow_physical_transport_credential_assignment_freshness_admission_read,
    authorize_workflow_physical_transport_credential_materialization_read,
    authorize_workflow_physical_transport_endpoint_materialization_read,
    authorize_workflow_physical_transport_endpoint_resolution_authorization_lease_read,
    authorize_workflow_physical_transport_route_binding_read,
    authorize_workflow_physical_transport_route_freshness_admission_read,
    authorize_workflow_physical_transport_target_context_access_authorization_lease_read,
    authorize_workflow_physical_transport_target_context_artifact_opening_read,
    authorize_workflow_physical_transport_target_context_binding_read,
    authorize_workflow_physical_transport_target_context_capsule_consumer_binding_read,
    authorize_workflow_plan_cancel,
    authorize_workflow_plan_create,
    authorize_workflow_plan_read,
    authorize_workflow_protected_resident_context_access_authorization_read,
    authorize_workflow_protected_resident_context_access_consumption_read,
    authorize_workflow_protected_runtime_context_injection_authorization_read,
    authorize_workflow_protected_runtime_context_injection_consumption_read,
    authorize_workflow_protected_runtime_context_use_authorization_consumption_read,
    authorize_workflow_protected_runtime_context_use_authorization_read,
    authorize_workflow_protected_runtime_context_use_read,
    authorize_workflow_protected_runtime_start_authorization_read,
    authorize_workflow_target_context_capsule_handoff_authorization_lease_read,
    authorize_workflow_target_context_capsule_handoff_read,
    authorize_workflow_target_context_capsule_opening_authorization_lease_read,
    authorize_workflow_target_context_capsule_opening_read,
    authorize_workflow_transport_compatibility_admission_read,
    authorize_workflow_transport_credential_assignment_snapshot_read,
    authorize_workflow_transport_profile_read,
    authorize_workflow_transport_route_snapshot_read,
    browser_session_subject,
    workflow_outbox_publisher_subject,
    workflow_physical_transport_credential_accessor_subject,
    workflow_physical_transport_credential_assignment_freshness_admitter_subject,
    workflow_physical_transport_endpoint_resolver_subject,
    workflow_physical_transport_route_binder_subject,
    workflow_physical_transport_route_freshness_admitter_subject,
    workflow_physical_transport_target_context_accessor_subject,
    workflow_physical_transport_target_context_binder_subject,
    workflow_physical_transport_target_context_capsule_binder_subject,
    workflow_protected_transport_target_context_capsule_consumer_subject,
    workflow_transport_compatibility_admitter_subject,
    workflow_transport_credential_assignment_registry_subject,
    workflow_transport_profile_registry_subject,
    workflow_transport_route_registry_subject,
    workflow_worker_subject,
)
from atlas.api.workflow_schemas import (
    AcquireWorkflowOrchestrationLeaseInput,
    AcquireWorkflowOutboxPublicationLeaseInput,
    AdmitWorkflowEventTransportInput,
    BindWorkflowEventLogicalChannelInput,
    CancelWorkflowPlanInput,
    CreateEventPhysicalTransportCredentialAssignmentSnapshotInput,
    CreateEventPhysicalTransportProfileSnapshotInput,
    CreateEventPhysicalTransportRouteSnapshotInput,
    CreateWorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseInput,
    CreateWorkflowEventPhysicalTransportCredentialAssignmentBindingInput,
    CreateWorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionInput,
    CreateWorkflowEventPhysicalTransportCredentialMaterializationInput,
    CreateWorkflowEventPhysicalTransportEndpointMaterializationInput,
    CreateWorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseInput,
    CreateWorkflowEventPhysicalTransportRouteBindingInput,
    CreateWorkflowEventPhysicalTransportRouteFreshnessAdmissionInput,
    CreateWorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseInput,
    CreateWorkflowEventPhysicalTransportTargetContextArtifactOpeningInput,
    CreateWorkflowEventPhysicalTransportTargetContextBindingInput,
    CreateWorkflowEventTransportCompatibilityAdmissionInput,
    CreateWorkflowPlanInput,
    CreateWorkflowProtectedResidentContextAccessAuthorizationInput,
    CreateWorkflowProtectedResidentContextAccessConsumptionInput,
    CreateWorkflowProtectedRuntimeContextInjectionAuthorizationInput,
    CreateWorkflowProtectedRuntimeContextInjectionConsumptionInput,
    CreateWorkflowProtectedRuntimeContextUseAuthorizationConsumptionInput,
    CreateWorkflowProtectedRuntimeContextUseAuthorizationInput,
    CreateWorkflowProtectedRuntimeContextUseInput,
    CreateWorkflowProtectedRuntimeStartAuthorizationInput,
    CreateWorkflowProtectedTransportTargetContextCapsuleConsumerBindingInput,
    CreateWorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseInput,
    CreateWorkflowProtectedTransportTargetContextCapsuleHandoffInput,
    CreateWorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseInput,
    CreateWorkflowProtectedTransportTargetContextCapsuleOpeningInput,
    EventPhysicalTransportCredentialAssignmentSnapshotData,
    EventPhysicalTransportCredentialAssignmentSnapshotInventoryData,
    EventPhysicalTransportCredentialAssignmentSnapshotInventoryResponse,
    EventPhysicalTransportCredentialAssignmentSnapshotResponse,
    EventPhysicalTransportProfileSnapshotData,
    EventPhysicalTransportProfileSnapshotInventoryData,
    EventPhysicalTransportProfileSnapshotInventoryResponse,
    EventPhysicalTransportProfileSnapshotResponse,
    EventPhysicalTransportRouteSnapshotData,
    EventPhysicalTransportRouteSnapshotInventoryData,
    EventPhysicalTransportRouteSnapshotInventoryResponse,
    EventPhysicalTransportRouteSnapshotResponse,
    HeartbeatWorkflowOrchestrationLeaseInput,
    HeartbeatWorkflowOutboxPublicationLeaseInput,
    MaterializeWorkflowAttemptInput,
    MaterializeWorkflowEventByteArtifactInput,
    MaterializeWorkflowRunInput,
    PrepareWorkflowDispatchEventEnvelopeInput,
    ReleaseWorkflowOrchestrationLeaseInput,
    ReleaseWorkflowOutboxPublicationLeaseInput,
    StageWorkflowDispatchIntentInput,
    WorkflowAttemptInventoryData,
    WorkflowAttemptInventoryResponse,
    WorkflowDefinitionData,
    WorkflowDefinitionInventoryData,
    WorkflowDefinitionInventoryResponse,
    WorkflowDispatchEventEnvelopeData,
    WorkflowDispatchEventEnvelopeInventoryData,
    WorkflowDispatchEventEnvelopeInventoryResponse,
    WorkflowDispatchEventEnvelopeResponse,
    WorkflowDispatchIntentData,
    WorkflowDispatchIntentInventoryData,
    WorkflowDispatchIntentInventoryResponse,
    WorkflowDispatchIntentResponse,
    WorkflowDispatchOutboxEntryData,
    WorkflowDispatchOutboxInventoryData,
    WorkflowDispatchOutboxInventoryResponse,
    WorkflowEventByteArtifactData,
    WorkflowEventByteArtifactInventoryData,
    WorkflowEventByteArtifactInventoryResponse,
    WorkflowEventByteArtifactResponse,
    WorkflowEventLogicalChannelBindingData,
    WorkflowEventLogicalChannelBindingInventoryData,
    WorkflowEventLogicalChannelBindingInventoryResponse,
    WorkflowEventLogicalChannelBindingResponse,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseData,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseInventoryData,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseInventoryResponse,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseResponse,
    WorkflowEventPhysicalTransportCredentialAssignmentBindingData,
    WorkflowEventPhysicalTransportCredentialAssignmentBindingInventoryData,
    WorkflowEventPhysicalTransportCredentialAssignmentBindingInventoryResponse,
    WorkflowEventPhysicalTransportCredentialAssignmentBindingResponse,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionData,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionInventoryData,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionInventoryResponse,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionResponse,
    WorkflowEventPhysicalTransportCredentialMaterializationData,
    WorkflowEventPhysicalTransportCredentialMaterializationInventoryData,
    WorkflowEventPhysicalTransportCredentialMaterializationInventoryResponse,
    WorkflowEventPhysicalTransportCredentialMaterializationResponse,
    WorkflowEventPhysicalTransportEndpointMaterializationData,
    WorkflowEventPhysicalTransportEndpointMaterializationInventoryData,
    WorkflowEventPhysicalTransportEndpointMaterializationInventoryResponse,
    WorkflowEventPhysicalTransportEndpointMaterializationResponse,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseData,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseInventoryData,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseInventoryResponse,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResponse,
    WorkflowEventPhysicalTransportRouteBindingData,
    WorkflowEventPhysicalTransportRouteBindingInventoryData,
    WorkflowEventPhysicalTransportRouteBindingInventoryResponse,
    WorkflowEventPhysicalTransportRouteBindingResponse,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionData,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionInventoryData,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionInventoryResponse,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionResponse,
    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseData,
    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseInventoryData,
    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseInventoryResponse,
    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseResponse,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningData,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningInventoryData,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningInventoryItemData,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningInventoryResponse,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningResponse,
    WorkflowEventPhysicalTransportTargetContextBindingData,
    WorkflowEventPhysicalTransportTargetContextBindingInventoryData,
    WorkflowEventPhysicalTransportTargetContextBindingInventoryResponse,
    WorkflowEventPhysicalTransportTargetContextBindingResponse,
    WorkflowEventTransportAdmissionData,
    WorkflowEventTransportAdmissionInventoryData,
    WorkflowEventTransportAdmissionInventoryResponse,
    WorkflowEventTransportAdmissionResponse,
    WorkflowEventTransportCompatibilityAdmissionData,
    WorkflowEventTransportCompatibilityAdmissionInventoryData,
    WorkflowEventTransportCompatibilityAdmissionInventoryResponse,
    WorkflowEventTransportCompatibilityAdmissionResponse,
    WorkflowExecutionAttemptData,
    WorkflowExecutionAttemptResponse,
    WorkflowExecutionRunData,
    WorkflowExecutionRunResponse,
    WorkflowMaterializedRunStatusData,
    WorkflowMaterializedRunStatusResponse,
    WorkflowOrchestrationLeaseData,
    WorkflowOrchestrationLeaseResponse,
    WorkflowOrchestrationLeaseStatusData,
    WorkflowOrchestrationLeaseStatusResponse,
    WorkflowOutboxPublicationLeaseData,
    WorkflowOutboxPublicationLeaseInventoryData,
    WorkflowOutboxPublicationLeaseInventoryResponse,
    WorkflowOutboxPublicationLeaseResponse,
    WorkflowPlanInventoryData,
    WorkflowPlanInventoryResponse,
    WorkflowProtectedResidentContextAccessAuthorizationData,
    WorkflowProtectedResidentContextAccessAuthorizationInventoryData,
    WorkflowProtectedResidentContextAccessAuthorizationInventoryResponse,
    WorkflowProtectedResidentContextAccessAuthorizationResponse,
    WorkflowProtectedResidentContextAccessConsumptionData,
    WorkflowProtectedResidentContextAccessConsumptionInventoryData,
    WorkflowProtectedResidentContextAccessConsumptionInventoryResponse,
    WorkflowProtectedResidentContextAccessConsumptionResponse,
    WorkflowProtectedRuntimeContextInjectionAuthorizationData,
    WorkflowProtectedRuntimeContextInjectionAuthorizationInventoryData,
    WorkflowProtectedRuntimeContextInjectionAuthorizationInventoryResponse,
    WorkflowProtectedRuntimeContextInjectionAuthorizationResponse,
    WorkflowProtectedRuntimeContextInjectionConsumptionData,
    WorkflowProtectedRuntimeContextInjectionConsumptionInventoryData,
    WorkflowProtectedRuntimeContextInjectionConsumptionInventoryResponse,
    WorkflowProtectedRuntimeContextInjectionConsumptionResponse,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionData,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionInventoryData,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionInventoryResponse,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionResponse,
    WorkflowProtectedRuntimeContextUseAuthorizationData,
    WorkflowProtectedRuntimeContextUseAuthorizationInventoryData,
    WorkflowProtectedRuntimeContextUseAuthorizationInventoryResponse,
    WorkflowProtectedRuntimeContextUseAuthorizationResponse,
    WorkflowProtectedRuntimeContextUseData,
    WorkflowProtectedRuntimeContextUseInventoryData,
    WorkflowProtectedRuntimeContextUseInventoryResponse,
    WorkflowProtectedRuntimeContextUseResponse,
    WorkflowProtectedRuntimeStartAuthorizationData,
    WorkflowProtectedRuntimeStartAuthorizationInventoryData,
    WorkflowProtectedRuntimeStartAuthorizationInventoryResponse,
    WorkflowProtectedRuntimeStartAuthorizationResponse,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBindingData,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBindingInventoryData,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBindingInventoryItemData,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBindingInventoryResponse,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBindingResponse,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseData,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseInventoryData,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseInventoryResponse,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseResponse,
    WorkflowProtectedTransportTargetContextCapsuleHandoffData,
    WorkflowProtectedTransportTargetContextCapsuleHandoffInventoryData,
    WorkflowProtectedTransportTargetContextCapsuleHandoffInventoryResponse,
    WorkflowProtectedTransportTargetContextCapsuleHandoffResponse,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseData,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseInventoryData,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseInventoryResponse,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseResponse,
    WorkflowProtectedTransportTargetContextCapsuleOpeningData,
    WorkflowProtectedTransportTargetContextCapsuleOpeningInventoryData,
    WorkflowProtectedTransportTargetContextCapsuleOpeningInventoryResponse,
    WorkflowProtectedTransportTargetContextCapsuleOpeningResponse,
    WorkflowRunPlanData,
    WorkflowRunPlanResponse,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.conversations.application.ports import (
    ConversationTargetAccessRequest,
    ConversationTargetAccessSource,
)
from atlas.modules.conversations.domain.models import ConversationScope
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.workflows.application import (
    WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_BINDER_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLVER_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_BINDER_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_FRESHNESS_ADMITTER_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_TRANSPORT_COMPATIBILITY_ADMITTER_AUDIENCE,
    WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_AUDIENCE,
    WORKFLOW_TRANSPORT_PROFILE_REGISTRY_AUDIENCE,
    WORKFLOW_TRANSPORT_ROUTE_REGISTRY_AUDIENCE,
    WORKFLOW_WORKER_AUDIENCE,
    WorkflowAccessContext,
    WorkflowAttemptMaterializationError,
    WorkflowAttemptMaterializationRepository,
    WorkflowAttemptMaterializationService,
    WorkflowDispatchIntentStagingError,
    WorkflowDispatchIntentStagingRepository,
    WorkflowDispatchIntentStagingService,
    WorkflowEventByteArtifactError,
    WorkflowEventByteArtifactService,
    WorkflowEventLogicalChannelBindingError,
    WorkflowEventLogicalChannelBindingService,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseService,
    WorkflowEventPhysicalTransportCredentialAssignmentBindingService,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionService,
    WorkflowEventPhysicalTransportCredentialMaterializationError,
    WorkflowEventPhysicalTransportCredentialMaterializationService,
    WorkflowEventPhysicalTransportCredentialMaterializationUncertainError,
    WorkflowEventPhysicalTransportEndpointMaterializationError,
    WorkflowEventPhysicalTransportEndpointMaterializationService,
    WorkflowEventPhysicalTransportEndpointMaterializationUncertainError,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseService,
    WorkflowEventPhysicalTransportRouteBindingService,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionError,
    WorkflowEventPhysicalTransportRouteFreshnessAdmissionService,
    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseService,
    WorkflowEventPhysicalTransportTargetContextBindingError,
    WorkflowEventPhysicalTransportTargetContextBindingService,
    WorkflowEventTransportCompatibilityAdmissionService,
    WorkflowOrchestrationLeaseError,
    WorkflowOrchestrationLeaseRepository,
    WorkflowOrchestrationLeaseService,
    WorkflowOutboxPublicationLeaseError,
    WorkflowOutboxPublicationLeaseRepository,
    WorkflowOutboxPublicationLeaseService,
    WorkflowOutboxPublisherContext,
    WorkflowPhysicalTransportCredentialAccessorContext,
    WorkflowPhysicalTransportCredentialAssignmentFreshnessAdmitterContext,
    WorkflowPhysicalTransportCredentialBinderContext,
    WorkflowPhysicalTransportEndpointResolverContext,
    WorkflowPhysicalTransportRouteBinderContext,
    WorkflowPhysicalTransportRouteFreshnessAdmitterContext,
    WorkflowPhysicalTransportTargetContextAccessorContext,
    WorkflowPhysicalTransportTargetContextBinderContext,
    WorkflowPlanningError,
    WorkflowPlanningService,
    WorkflowProtectedResidentContextAccessAuthorizationError,
    WorkflowProtectedResidentContextAccessAuthorizationService,
    WorkflowProtectedResidentContextAccessConsumptionError,
    WorkflowProtectedResidentContextAccessConsumptionService,
    WorkflowProtectedRuntimeContextInjectionAuthorizationError,
    WorkflowProtectedRuntimeContextInjectionAuthorizationService,
    WorkflowProtectedRuntimeContextInjectionConsumptionError,
    WorkflowProtectedRuntimeContextInjectionConsumptionService,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionError,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionService,
    WorkflowProtectedRuntimeContextUseAuthorizationError,
    WorkflowProtectedRuntimeContextUseAuthorizationService,
    WorkflowProtectedRuntimeContextUseError,
    WorkflowProtectedRuntimeContextUseService,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseService,
    WorkflowProtectedTransportTargetContextCapsuleHandoffError,
    WorkflowProtectedTransportTargetContextCapsuleHandoffService,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseError,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseService,
    WorkflowProtectedTransportTargetContextCapsuleOpeningError,
    WorkflowProtectedTransportTargetContextCapsuleOpeningService,
    WorkflowRunMaterializationError,
    WorkflowRunMaterializationRepository,
    WorkflowRunMaterializationService,
    WorkflowTransportCompatibilityAdmitterContext,
    WorkflowTransportCredentialAssignmentRegistryContext,
    WorkflowTransportCredentialAssignmentSnapshotError,
    WorkflowTransportCredentialAssignmentSnapshotService,
    WorkflowTransportProfileRegistryContext,
    WorkflowTransportProfileSnapshotError,
    WorkflowTransportProfileSnapshotService,
    WorkflowTransportRouteRegistryContext,
    WorkflowTransportRouteSnapshotError,
    WorkflowTransportRouteSnapshotService,
    WorkflowWorkerContext,
    validate_workflow_transport_credential_assignment_snapshot,
)
from atlas.modules.workflows.application.credential_access_authorization_lease_ports import (
    WorkflowTransportCredentialAccessAuthorizationLeaseError,
)
from atlas.modules.workflows.application.credential_assignment_binding_ports import (
    WorkflowTransportCredentialAssignmentBindingError,
)
from atlas.modules.workflows.application.credential_assignment_freshness_admission_ports import (
    WorkflowTransportCredentialAssignmentFreshnessAdmissionError,
)
from atlas.modules.workflows.application.event_envelope_ports import (
    WorkflowDispatchEventEnvelopeError,
    WorkflowDispatchEventEnvelopeRepository,
)
from atlas.modules.workflows.application.event_envelopes import (
    WorkflowDispatchEventEnvelopeService,
)
from atlas.modules.workflows.application.physical_route_binding_ports import (
    WorkflowEventPhysicalTransportRouteBindingError,
)
from atlas.modules.workflows.application.protected_runtime_start_authorization_ports import (
    WorkflowProtectedRuntimeStartAuthorizationError,
)
from atlas.modules.workflows.application.protected_runtime_start_authorizations import (
    WorkflowProtectedRuntimeStartAuthorizationService,
)
from atlas.modules.workflows.application.target_context_access_authorization_lease_ports import (
    WorkflowTargetContextAccessAuthorizationLeaseError,
)
from atlas.modules.workflows.application.target_context_artifact_opening_ports import (
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningError,
)
from atlas.modules.workflows.application.target_context_artifact_openings import (
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningService,
)
from atlas.modules.workflows.application.target_context_capsule_consumer_binding_ports import (
    WorkflowProtectedTransportTargetContextCapsuleConsumerBindingError,
)
from atlas.modules.workflows.application.target_context_capsule_consumer_bindings import (
    WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_AUDIENCE,
    WorkflowProtectedTransportTargetContextCapsuleBinderContext,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBindingService,
)
from atlas.modules.workflows.application.transport_admission_ports import (
    WorkflowEventTransportAdmissionError,
)
from atlas.modules.workflows.application.transport_admissions import (
    WorkflowEventTransportAdmissionService,
)
from atlas.modules.workflows.application.transport_compatibility_admission_ports import (
    WorkflowEventTransportCompatibilityAdmissionError,
)
from atlas.modules.workflows.domain import (
    DeploymentEventTransportProfile,
    DeploymentEventTransportRoute,
    EventPhysicalTransportCredentialAssignmentSnapshot,
    EventPhysicalTransportProfileSnapshot,
    EventPhysicalTransportRouteSnapshot,
    WorkflowDispatchEventEnvelope,
    WorkflowDispatchIntent,
    WorkflowDispatchIntentState,
    WorkflowDispatchOutboxEntry,
    WorkflowDispatchOutboxState,
    WorkflowEventByteArtifact,
    WorkflowEventByteArtifactState,
    WorkflowEventLogicalChannelBinding,
    WorkflowEventLogicalChannelBindingState,
    WorkflowEventLogicalChannelPolicy,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease,
    WorkflowEventPhysicalTransportCredentialAssignmentBinding,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease,
    WorkflowEventPhysicalTransportRouteBinding,
    WorkflowEventPhysicalTransportRouteFreshnessAdmission,
    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult,
    WorkflowEventTransportAdmission,
    WorkflowEventTransportAdmissionPolicy,
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
    WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease,
    WorkflowRunPlan,
    WorkflowScope,
    canonical_digest,
)

router = APIRouter(prefix="/workflows", tags=["workflows"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _meta(request: Request) -> ResponseMeta:
    return ResponseMeta(
        correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
    )


def _no_store(response: Response) -> None:
    response.headers.update(
        {
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        }
    )


def _protected_runtime_context_use_error_is_unavailable(code: str) -> bool:
    return (
        "unavailable" in code
        or "repository" in code
        or "commit_uncertain" in code
        or "instruction_envelope_invalid" in code
        or code.endswith("durable_repository_required")
    )


async def _context(
    request: Request,
    subject: AuthenticatedSubject,
    decision: AuthorizationDecision,
) -> WorkflowAccessContext:
    settings = request.app.state.settings
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{settings.environment}",
        site_id="site.local",
    )
    source: ConversationTargetAccessSource = request.app.state.conversation_target_access_source
    try:
        targets = await source.authorized_storage_targets(
            ConversationTargetAccessRequest(
                subject_id=subject.subject_id,
                principal_ids=frozenset((*subject.role_ids, *subject.group_ids)),
                scope=ConversationScope(
                    organization_id=scope.organization_id,
                    environment_id=scope.environment_id,
                    site_id=scope.site_id,
                ),
            )
        )
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_target_authority_unavailable",
            title="Workflow target authority unavailable",
            detail="Authorized storage targets could not be resolved safely.",
            retryable=True,
        ) from error
    target_ids = tuple(target.target_id for target in targets)
    if len(target_ids) > 100 or len(target_ids) != len(set(target_ids)):
        raise AtlasError(
            status=503,
            code="workflow_target_authority_invalid",
            title="Workflow target authority invalid",
            detail="Authorized workflow targets did not satisfy the bounded contract.",
        )
    return WorkflowAccessContext(
        subject_id=subject.subject_id,
        role_ids=frozenset((*subject.role_ids, *subject.group_ids)),
        actor_type=subject.kind.value,
        authentication_method=subject.authentication_method.value,
        assurance_level=subject.assurance_level.value,
        scope=scope,
        authorized_target_ids=frozenset(target_ids),
        correlation_id=str(request.state.correlation_id),
        decision_id=decision.decision_id,
        requested_at=datetime.now(UTC),
    )


def _raise(error: WorkflowPlanningError) -> NoReturn:
    if error.code in {"workflow_plan_not_found", "workflow_target_unavailable"}:
        status, title = 404, "Workflow resource unavailable"
    elif error.code == "workflow_idempotency_conflict":
        status, title = 409, "Workflow plan conflict"
    elif error.code.endswith("_invalid") or error.code.endswith("_required"):
        status, title = 422, "Workflow request invalid"
    elif "repository" in error.code:
        status, title = 503, "Workflow service unavailable"
    else:
        status, title = 409, "Workflow operation unavailable"
    raise AtlasError(
        status=status,
        code=error.code,
        title=title,
        detail=error.detail,
        retryable=status == 503,
    ) from error


def _raise_lease(error: WorkflowOrchestrationLeaseError) -> NoReturn:
    if error.code.endswith("_invalid"):
        status = 422
    elif "repository" in error.code:
        status = 503
    elif error.code.endswith("_not_found"):
        status = 404
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=(
            "workflow_lease_request_invalid"
            if status == 422
            else "workflow_lease_service_unavailable"
            if status == 503
            else "workflow_resource_unavailable"
            if status == 404
            else "workflow_lease_conflict"
        ),
        title=(
            "Workflow lease request invalid"
            if status == 422
            else "Workflow lease service unavailable"
            if status == 503
            else "Workflow resource unavailable"
            if status == 404
            else "Workflow lease conflict"
        ),
        detail=(
            "The workflow lease request did not satisfy the bounded contract."
            if status == 422
            else "The workflow lease operation is unavailable."
        ),
        retryable=status == 503,
    ) from error


def _raise_materialization(error: WorkflowRunMaterializationError) -> NoReturn:
    if error.code.endswith("_invalid") or error.code.endswith("_required"):
        status = 422
    elif "repository" in error.code:
        status = 503
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=(
            "workflow_run_request_invalid"
            if status == 422
            else "workflow_run_service_unavailable"
            if status == 503
            else "workflow_run_conflict"
        ),
        title=(
            "Workflow run request invalid"
            if status == 422
            else "Workflow run service unavailable"
            if status == 503
            else "Workflow run conflict"
        ),
        detail=(
            "The workflow run request did not satisfy the bounded contract."
            if status == 422
            else "The workflow run operation is unavailable."
        ),
        retryable=status == 503,
    ) from error


def _raise_attempt(error: WorkflowAttemptMaterializationError) -> NoReturn:
    if error.code.endswith("_invalid") or error.code.endswith("_required"):
        status = 422
    elif "repository" in error.code:
        status = 503
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=(
            "workflow_attempt_request_invalid"
            if status == 422
            else "workflow_attempt_service_unavailable"
            if status == 503
            else "workflow_attempt_conflict"
        ),
        title=(
            "Workflow attempt request invalid"
            if status == 422
            else "Workflow attempt service unavailable"
            if status == 503
            else "Workflow attempt conflict"
        ),
        detail=(
            "The workflow attempt request did not satisfy the bounded contract."
            if status == 422
            else "The workflow attempt operation is unavailable."
        ),
        retryable=status == 503,
    ) from error


def _raise_dispatch_intent(error: WorkflowDispatchIntentStagingError) -> NoReturn:
    if error.code.endswith("_invalid") or error.code.endswith("_required"):
        status = 422
    elif "repository" in error.code:
        status = 503
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=(
            "workflow_dispatch_intent_request_invalid"
            if status == 422
            else "workflow_dispatch_intent_service_unavailable"
            if status == 503
            else "workflow_dispatch_intent_conflict"
        ),
        title=(
            "Workflow dispatch intent request invalid"
            if status == 422
            else "Workflow dispatch intent service unavailable"
            if status == 503
            else "Workflow dispatch intent conflict"
        ),
        detail=(
            "The dispatch intent request did not satisfy the bounded contract."
            if status == 422
            else "Workflow dispatch intent evidence is unavailable."
        ),
        retryable=status == 503,
    ) from error


def _raise_publication_lease(error: WorkflowOutboxPublicationLeaseError) -> NoReturn:
    if error.code.endswith("_invalid") or error.code.endswith("_required"):
        status = 422
    elif "repository" in error.code:
        status = 503
    elif error.code.endswith("_not_found"):
        status = 404
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=(
            "workflow_outbox_publication_lease_request_invalid"
            if status == 422
            else "workflow_outbox_publication_lease_service_unavailable"
            if status == 503
            else "workflow_resource_unavailable"
            if status == 404
            else "workflow_outbox_publication_lease_conflict"
        ),
        title=(
            "Workflow outbox publication lease request invalid"
            if status == 422
            else "Workflow outbox publication lease service unavailable"
            if status == 503
            else "Workflow resource unavailable"
            if status == 404
            else "Workflow outbox publication lease conflict"
        ),
        detail=(
            "The publication lease request did not satisfy the bounded contract."
            if status == 422
            else "Workflow outbox publication lease evidence is unavailable."
        ),
        retryable=status == 503,
    ) from error


def _raise_dispatch_event_envelope(error: WorkflowDispatchEventEnvelopeError) -> NoReturn:
    if error.code.endswith("_invalid") or error.code.endswith("_required"):
        status = 422
    elif "repository" in error.code:
        status = 503
    elif error.code.endswith("_not_found"):
        status = 404
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=(
            "workflow_dispatch_event_envelope_request_invalid"
            if status == 422
            else "workflow_dispatch_event_envelope_service_unavailable"
            if status == 503
            else "workflow_resource_unavailable"
            if status == 404
            else "workflow_dispatch_event_envelope_conflict"
        ),
        title=(
            "Workflow dispatch event envelope request invalid"
            if status == 422
            else "Workflow dispatch event envelope service unavailable"
            if status == 503
            else "Workflow resource unavailable"
            if status == 404
            else "Workflow dispatch event envelope conflict"
        ),
        detail=(
            "The event envelope request did not satisfy the bounded contract."
            if status == 422
            else "Workflow dispatch event envelope evidence is unavailable."
        ),
        retryable=status == 503,
    ) from error


def _raise_event_transport_admission(error: WorkflowEventTransportAdmissionError) -> NoReturn:
    if error.code.endswith("_invalid") or error.code.endswith("_required"):
        status = 422
    elif "repository" in error.code:
        status = 503
    elif error.code.endswith("_not_found"):
        status = 404
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=(
            "workflow_event_transport_admission_request_invalid"
            if status == 422
            else "workflow_event_transport_admission_service_unavailable"
            if status == 503
            else "workflow_resource_unavailable"
            if status == 404
            else "workflow_event_transport_admission_conflict"
        ),
        title=(
            "Workflow event transport admission request invalid"
            if status == 422
            else "Workflow event transport admission service unavailable"
            if status == 503
            else "Workflow resource unavailable"
            if status == 404
            else "Workflow event transport admission conflict"
        ),
        detail=(
            "The transport admission request did not satisfy the bounded contract."
            if status == 422
            else "Workflow event transport admission evidence is unavailable."
        ),
        retryable=status == 503,
    ) from error


def _raise_event_byte_artifact(error: WorkflowEventByteArtifactError) -> NoReturn:
    if error.code.endswith("_invalid") or error.code.endswith("_required"):
        status = 422
    elif "repository" in error.code:
        status = 503
    elif error.code.endswith("_not_found"):
        status = 404
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=(
            "workflow_event_byte_artifact_request_invalid"
            if status == 422
            else "workflow_event_byte_artifact_service_unavailable"
            if status == 503
            else "workflow_resource_unavailable"
            if status == 404
            else "workflow_event_byte_artifact_conflict"
        ),
        title=(
            "Workflow event byte artifact request invalid"
            if status == 422
            else "Workflow event byte artifact service unavailable"
            if status == 503
            else "Workflow resource unavailable"
            if status == 404
            else "Workflow event byte artifact conflict"
        ),
        detail=(
            "The byte artifact request did not satisfy the bounded contract."
            if status == 422
            else "Workflow event byte artifact evidence is unavailable."
        ),
        retryable=status == 503,
    ) from error


def _raise_event_logical_channel_binding(
    error: WorkflowEventLogicalChannelBindingError,
) -> NoReturn:
    if error.code.endswith("_invalid") or error.code.endswith("_required"):
        status = 422
    elif "repository" in error.code:
        status = 503
    elif error.code.endswith("_not_found"):
        status = 404
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=(
            "workflow_event_logical_channel_binding_request_invalid"
            if status == 422
            else "workflow_event_logical_channel_binding_service_unavailable"
            if status == 503
            else "workflow_resource_unavailable"
            if status == 404
            else "workflow_event_logical_channel_binding_conflict"
        ),
        title=(
            "Workflow event logical channel binding request invalid"
            if status == 422
            else "Workflow event logical channel binding service unavailable"
            if status == 503
            else "Workflow resource unavailable"
            if status == 404
            else "Workflow event logical channel binding conflict"
        ),
        detail=(
            "The logical channel binding request did not satisfy the bounded contract."
            if status == 422
            else "Workflow event logical channel binding evidence is unavailable."
        ),
        retryable=status == 503,
    ) from error


def _raise_transport_profile_snapshot(error: WorkflowTransportProfileSnapshotError) -> NoReturn:
    if error.code.endswith("_invalid") or error.code.endswith("_required"):
        status, title = 422, "Workflow transport profile snapshot request invalid"
    elif "repository" in error.code:
        status, title = 503, "Workflow transport profile snapshot service unavailable"
    elif error.code.endswith("_source_not_active"):
        status, title = 404, "Workflow transport profile source unavailable"
    else:
        status, title = 409, "Workflow transport profile snapshot unavailable"
    raise AtlasError(
        status=status,
        code=error.code,
        title=title,
        detail=error.detail,
        retryable=status == 503,
    ) from error


def _raise_transport_route_snapshot(error: WorkflowTransportRouteSnapshotError) -> NoReturn:
    if error.code.endswith("_invalid") or error.code.endswith("_required"):
        status, title = 422, "Workflow transport route snapshot request invalid"
    elif "repository" in error.code:
        status, title = 503, "Workflow transport route snapshot service unavailable"
    elif error.code.endswith("_source_not_active"):
        status, title = 404, "Workflow transport route source unavailable"
    else:
        status, title = 409, "Workflow transport route snapshot unavailable"
    raise AtlasError(
        status=status,
        code=error.code,
        title=title,
        detail=error.detail,
        retryable=status == 503,
    ) from error


def _raise_transport_credential_assignment_snapshot(
    error: WorkflowTransportCredentialAssignmentSnapshotError,
) -> NoReturn:
    if error.code.endswith("_invalid") or error.code.endswith("_required"):
        status, title = 422, "Workflow transport credential snapshot request invalid"
    elif "repository" in error.code or "audit" in error.code:
        status, title = 503, "Workflow transport credential snapshot service unavailable"
    elif error.code.endswith("_source_not_active"):
        status, title = 404, "Workflow transport credential assignment unavailable"
    else:
        status, title = 409, "Workflow transport credential snapshot unavailable"
    raise AtlasError(
        status=status,
        code=error.code,
        title=title,
        detail=error.detail,
        retryable=status == 503,
    ) from error


def _raise_physical_transport_route_binding(
    error: WorkflowEventPhysicalTransportRouteBindingError,
) -> NoReturn:
    if error.code.endswith("_invalid") or error.code.endswith("_required"):
        status, title = 422, "Workflow physical transport route binding request invalid"
    elif "repository" in error.code:
        status, title = 503, "Workflow physical transport route binding service unavailable"
    elif error.code.endswith("_not_found"):
        status, title = 404, "Workflow physical transport route binding evidence unavailable"
    else:
        status, title = 409, "Workflow physical transport route binding unavailable"
    raise AtlasError(
        status=status,
        code=error.code,
        title=title,
        detail=error.detail,
        retryable=status == 503,
    ) from error


def _raise_physical_transport_credential_assignment_binding(
    error: WorkflowTransportCredentialAssignmentBindingError,
) -> NoReturn:
    if error.code.endswith("_invalid") or error.code.endswith("_required"):
        status, title = 422, "Workflow transport credential binding request invalid"
    elif "repository" in error.code or "audit" in error.code:
        status, title = 503, "Workflow transport credential binding service unavailable"
    elif error.code.endswith("_not_found"):
        status, title = 404, "Workflow transport credential binding evidence unavailable"
    else:
        status, title = 409, "Workflow transport credential binding unavailable"
    raise AtlasError(
        status=status,
        code=error.code,
        title=title,
        detail=error.detail,
        retryable=status == 503,
    ) from error


def _raise_physical_transport_credential_assignment_freshness_admission(
    error: WorkflowTransportCredentialAssignmentFreshnessAdmissionError,
) -> NoReturn:
    if error.code.endswith("_invalid") or error.code.endswith("_required"):
        status, title = 422, "Workflow credential-assignment freshness request invalid"
    elif "repository" in error.code or "audit" in error.code or "unavailable" in error.code:
        status, title = 503, "Workflow credential-assignment freshness service unavailable"
    else:
        status, title = 409, "Workflow credential-assignment freshness admission unavailable"
    detail = {
        422: "The credential-assignment freshness request is invalid.",
        503: "The credential-assignment freshness service is temporarily unavailable.",
    }.get(status, "The current evidence could not support a freshness admission.")
    raise AtlasError(
        status=status,
        code=error.code,
        title=title,
        detail=detail,
        retryable=status == 503,
    ) from error


def _raise_physical_transport_credential_access_authorization_lease(
    error: WorkflowTransportCredentialAccessAuthorizationLeaseError,
) -> NoReturn:
    if error.code.endswith("_invalid") or error.code.endswith("_required"):
        status = 422
        code = "workflow_physical_transport_credential_access_authorization_request_invalid"
        title = "Workflow credential-access authorization request invalid"
        detail = "The credential-access authorization request is invalid."
    elif (
        "repository" in error.code
        or "audit" in error.code
        or "persistence" in error.code
        or "unavailable" in error.code
    ):
        status = 503
        code = "workflow_physical_transport_credential_access_authorization_service_unavailable"
        title = "Workflow credential-access authorization service unavailable"
        detail = "Credential-access authorization is temporarily unavailable."
    else:
        status = 409
        code = "workflow_physical_transport_credential_access_authorization_unavailable"
        title = "Workflow credential-access authorization unavailable"
        detail = "The current evidence could not support credential-access authorization."
    raise AtlasError(
        status=status,
        code=code,
        title=title,
        detail=detail,
        retryable=status == 503,
    ) from error


def _raise_physical_transport_target_context_access_authorization_lease(
    error: WorkflowTargetContextAccessAuthorizationLeaseError,
) -> NoReturn:
    if (
        "repository" in error.code
        or "audit" in error.code
        or "persistence" in error.code
        or "unavailable" in error.code
    ):
        status = 503
        code = "workflow_target_context_access_authorization_service_unavailable"
        title = "Workflow target-context access authorization service unavailable"
        detail = "Target-context access authorization is temporarily unavailable."
    elif error.code.endswith("_invalid") or error.code.endswith("_required"):
        status = 422
        code = "workflow_target_context_access_authorization_request_invalid"
        title = "Workflow target-context access authorization request invalid"
        detail = "The target-context access authorization request is invalid."
    else:
        status = 409
        code = "workflow_target_context_access_authorization_unavailable"
        title = "Workflow target-context access authorization unavailable"
        detail = "The current evidence could not support target-context access authorization."
    raise AtlasError(
        status=status,
        code=code,
        title=title,
        detail=detail,
        retryable=status == 503,
    ) from error


def _raise_physical_transport_target_context_artifact_opening(
    error: WorkflowEventPhysicalTransportTargetContextArtifactOpeningError,
) -> NoReturn:
    raise AtlasError(
        status=409,
        code="workflow_target_context_artifact_opening_unavailable",
        title="Workflow target-context artifact opening unavailable",
        detail="The target-context artifact opening request cannot be completed.",
        retryable=False,
    ) from error


def _raise_physical_transport_target_context_capsule_consumer_binding(
    error: WorkflowProtectedTransportTargetContextCapsuleConsumerBindingError,
) -> NoReturn:
    unavailable = "repository" in error.code or "durable" in error.code
    raise AtlasError(
        status=503 if unavailable else 409,
        code=(
            "workflow_target_context_capsule_consumer_binding_service_unavailable"
            if unavailable
            else "workflow_target_context_capsule_consumer_binding_unavailable"
        ),
        title=(
            "Workflow target-context capsule consumer binding service unavailable"
            if unavailable
            else "Workflow target-context capsule consumer binding unavailable"
        ),
        detail=("The target-context capsule consumer binding request cannot be completed."),
        retryable=unavailable,
    ) from error


def _raise_physical_transport_target_context_capsule_handoff_authorization_lease(
    error: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError,
) -> NoReturn:
    unavailable = any(
        marker in error.code
        for marker in ("repository", "durable", "attestor", "signature", "unavailable")
    )
    raise AtlasError(
        status=503 if unavailable else 409,
        code=(
            "workflow_target_context_capsule_handoff_authorization_service_unavailable"
            if unavailable
            else "workflow_target_context_capsule_handoff_authorization_unavailable"
        ),
        title=(
            "Workflow target-context capsule handoff authorization service unavailable"
            if unavailable
            else "Workflow target-context capsule handoff authorization unavailable"
        ),
        detail="The target-context capsule handoff authorization request cannot be completed.",
        retryable=unavailable,
    ) from error


def _raise_physical_transport_route_freshness_admission(
    error: WorkflowEventPhysicalTransportRouteFreshnessAdmissionError,
) -> NoReturn:
    if error.code.endswith("_invalid") or error.code.endswith("_required"):
        status, title = 422, "Workflow physical route freshness request invalid"
    elif "repository" in error.code:
        status, title = 503, "Workflow physical route freshness service unavailable"
    else:
        status, title = 409, "Workflow physical route freshness admission unavailable"
    raise AtlasError(
        status=status,
        code=error.code,
        title=title,
        detail=error.detail,
        retryable=status == 503,
    ) from error


def _raise_physical_transport_endpoint_resolution_authorization_lease(
    error: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError,
) -> NoReturn:
    if error.code.endswith("_invalid") or error.code.endswith("_required"):
        status, title = 422, "Workflow endpoint-resolution authorization request invalid"
    elif "repository" in error.code or "persistence" in error.code:
        status, title = 503, "Workflow endpoint-resolution authorization service unavailable"
    else:
        status, title = 409, "Workflow endpoint-resolution authorization unavailable"
    raise AtlasError(
        status=status,
        code=error.code,
        title=title,
        detail=error.detail,
        retryable=status == 503,
    ) from error


def _raise_physical_transport_endpoint_materialization(
    error: WorkflowEventPhysicalTransportEndpointMaterializationError,
) -> NoReturn:
    if error.code.endswith("_invalid") or error.code.endswith("_required"):
        status, title = 422, "Workflow endpoint materialization request invalid"
    elif "unavailable" in error.code or "persistence" in error.code:
        status, title = 503, "Workflow endpoint materialization service unavailable"
    else:
        status, title = 409, "Workflow endpoint materialization unavailable"
    raise AtlasError(
        status=status,
        code=error.code,
        title=title,
        detail=error.detail,
        retryable=(
            status == 503
            and not isinstance(
                error,
                WorkflowEventPhysicalTransportEndpointMaterializationUncertainError,
            )
        ),
    ) from error


def _raise_physical_transport_credential_materialization(
    error: WorkflowEventPhysicalTransportCredentialMaterializationError,
) -> NoReturn:
    raise AtlasError(
        status=409,
        code="workflow_credential_materialization_unavailable",
        title="Workflow credential materialization unavailable",
        detail="The credential materialization request cannot be completed.",
        retryable=False,
    ) from error


def _raise_physical_transport_target_context_binding(
    error: WorkflowEventPhysicalTransportTargetContextBindingError,
) -> NoReturn:
    if error.code.endswith("_invalid") or error.code.endswith("_required"):
        status = 422
        code = "workflow_physical_transport_target_context_binding_request_invalid"
        title = "Workflow target-context binding request invalid"
        detail = "The target-context binding request is invalid."
    elif any(marker in error.code for marker in ("repository", "persistence", "audit_unavailable")):
        status = 503
        code = "workflow_physical_transport_target_context_binding_service_unavailable"
        title = "Workflow target-context binding service unavailable"
        detail = "Target-context binding is temporarily unavailable."
    else:
        status = 409
        code = "workflow_physical_transport_target_context_binding_unavailable"
        title = "Workflow target-context binding unavailable"
        detail = "The current evidence could not support a target-context binding."
    raise AtlasError(
        status=status,
        code=code,
        title=title,
        detail=detail,
        retryable=status == 503,
    ) from error


def _raise_transport_compatibility_admission(
    error: WorkflowEventTransportCompatibilityAdmissionError,
) -> NoReturn:
    if error.code.endswith("_invalid") or error.code.endswith("_required"):
        status, title = 422, "Workflow transport compatibility admission request invalid"
    elif "repository" in error.code:
        status, title = 503, "Workflow transport compatibility admission service unavailable"
    elif error.code.endswith("_not_found"):
        status, title = 404, "Workflow transport compatibility evidence unavailable"
    else:
        status, title = 409, "Workflow transport compatibility admission unavailable"
    raise AtlasError(
        status=status,
        code=error.code,
        title=title,
        detail=error.detail,
        retryable=status == 503,
    ) from error


async def _worker_context(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    target_id: str,
) -> WorkflowWorkerContext:
    settings = request.app.state.settings
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{settings.environment}",
        site_id="site.local",
    )
    source: ConversationTargetAccessSource = request.app.state.conversation_target_access_source
    try:
        targets = await source.authorized_storage_targets(
            ConversationTargetAccessRequest(
                subject_id=subject.subject_id,
                principal_ids=frozenset((*subject.role_ids, *subject.group_ids)),
                scope=ConversationScope(
                    organization_id=scope.organization_id,
                    environment_id=scope.environment_id,
                    site_id=scope.site_id,
                ),
            )
        )
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_target_authority_unavailable",
            title="Workflow target authority unavailable",
            detail="Authorized workflow targets could not be resolved safely.",
            retryable=True,
        ) from error
    target_ids = tuple(target.target_id for target in targets)
    if (
        len(target_ids) > 100
        or len(target_ids) != len(set(target_ids))
        or target_id not in target_ids
    ):
        raise AtlasError(
            status=404,
            code="workflow_resource_unavailable",
            title="Workflow resource unavailable",
            detail="The requested workflow resource is unavailable.",
        )
    return WorkflowWorkerContext(
        subject_id=subject.subject_id,
        actor_type=subject.kind.value,
        authentication_method=subject.authentication_method.value,
        credential_audience=WORKFLOW_WORKER_AUDIENCE,
        scope=scope,
        authorized_target_ids=frozenset(target_ids),
        correlation_id=str(request.state.correlation_id),
        decision_id="decision.workflow-worker-authenticated",
        requested_at=datetime.now(UTC),
    )


async def _publisher_context(
    request: Request,
    subject: AuthenticatedSubject,
    *,
    target_id: str,
) -> WorkflowOutboxPublisherContext:
    settings = request.app.state.settings
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{settings.environment}",
        site_id="site.local",
    )
    source: ConversationTargetAccessSource = request.app.state.conversation_target_access_source
    try:
        targets = await source.authorized_storage_targets(
            ConversationTargetAccessRequest(
                subject_id=subject.subject_id,
                principal_ids=frozenset((*subject.role_ids, *subject.group_ids)),
                scope=ConversationScope(
                    organization_id=scope.organization_id,
                    environment_id=scope.environment_id,
                    site_id=scope.site_id,
                ),
            )
        )
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_target_authority_unavailable",
            title="Workflow target authority unavailable",
            detail="Authorized workflow targets could not be resolved safely.",
            retryable=True,
        ) from error
    target_ids = tuple(target.target_id for target in targets)
    if (
        len(target_ids) > 100
        or len(target_ids) != len(set(target_ids))
        or target_id not in target_ids
    ):
        raise AtlasError(
            status=404,
            code="workflow_resource_unavailable",
            title="Workflow resource unavailable",
            detail="The requested workflow resource is unavailable.",
        )
    return WorkflowOutboxPublisherContext(
        subject_id=subject.subject_id,
        actor_type=subject.kind.value,
        authentication_method=subject.authentication_method.value,
        credential_audience=WORKFLOW_OUTBOX_PUBLISHER_AUDIENCE,
        scope=scope,
        authorized_target_ids=frozenset(target_ids),
        correlation_id=str(request.state.correlation_id),
        decision_id="decision.workflow-outbox-publisher-authenticated",
        requested_at=datetime.now(UTC),
    )


def _lease_response(
    lease: WorkflowOrchestrationLease,
    request: Request,
    response: Response,
) -> WorkflowOrchestrationLeaseResponse:
    requested_at = datetime.now(UTC)
    _no_store(response)
    return WorkflowOrchestrationLeaseResponse(
        data=WorkflowOrchestrationLeaseData.from_domain(lease, requested_at=requested_at),
        meta=_meta(request),
    )


def _publication_lease_response(
    lease: WorkflowOutboxPublicationLease,
    request: Request,
    response: Response,
) -> WorkflowOutboxPublicationLeaseResponse:
    _no_store(response)
    return WorkflowOutboxPublicationLeaseResponse(
        data=WorkflowOutboxPublicationLeaseData.from_domain(
            lease,
            requested_at=datetime.now(UTC),
        ),
        meta=_meta(request),
    )


def _dispatch_event_envelope_response(
    envelope: WorkflowDispatchEventEnvelope,
    request: Request,
    response: Response,
) -> WorkflowDispatchEventEnvelopeResponse:
    _no_store(response)
    return WorkflowDispatchEventEnvelopeResponse(
        data=WorkflowDispatchEventEnvelopeData.from_domain(envelope),
        meta=_meta(request),
    )


def _event_transport_admission_response(
    admission: WorkflowEventTransportAdmission,
    request: Request,
    response: Response,
) -> WorkflowEventTransportAdmissionResponse:
    _no_store(response)
    return WorkflowEventTransportAdmissionResponse(
        data=WorkflowEventTransportAdmissionData.from_domain(admission),
        meta=_meta(request),
    )


def _run_response(
    run: WorkflowExecutionRun,
    request: Request,
    response: Response,
) -> WorkflowExecutionRunResponse:
    _no_store(response)
    return WorkflowExecutionRunResponse(
        data=WorkflowExecutionRunData.from_domain(run),
        meta=_meta(request),
    )


def _attempt_response(
    attempt: WorkflowExecutionAttempt,
    request: Request,
    response: Response,
) -> WorkflowExecutionAttemptResponse:
    _no_store(response)
    return WorkflowExecutionAttemptResponse(
        data=WorkflowExecutionAttemptData.from_domain(attempt),
        meta=_meta(request),
    )


def _dispatch_intent_response(
    intent: WorkflowDispatchIntent,
    request: Request,
    response: Response,
) -> WorkflowDispatchIntentResponse:
    _no_store(response)
    return WorkflowDispatchIntentResponse(
        data=WorkflowDispatchIntentData.from_domain(intent), meta=_meta(request)
    )


def _run_matches_plan(run: WorkflowExecutionRun, plan: WorkflowRunPlan) -> bool:
    return (
        run.plan_id == plan.plan_id
        and run.plan_digest == plan.canonical_digest
        and run.definition_id == plan.definition_id
        and run.definition_version == plan.definition_version
        and run.definition_digest == plan.definition_digest
        and run.scope == plan.scope
        and run.target_id == plan.target_id
        and run.target_type == plan.target_type
        and run.state is WorkflowExecutionRunState.CREATED
        and len(run.step_runs) == len(plan.steps)
        and all(
            step_run.run_id == run.run_id
            and step_run.step_id == plan_step.step_id
            and step_run.ordinal == plan_step.ordinal
            and step_run.kind == plan_step.kind
            and step_run.capability_class == plan_step.capability_class
            and step_run.state is WorkflowExecutionStepRunState.NOT_STARTED
            for step_run, plan_step in zip(run.step_runs, plan.steps, strict=True)
        )
        and not any(run.authority.canonical_value().values())
        and not run.grants_execution_authority
    )


def _attempt_matches_run(attempt: WorkflowExecutionAttempt, run: WorkflowExecutionRun) -> bool:
    step = next((item for item in run.step_runs if item.step_run_id == attempt.step_run_id), None)
    return bool(
        step is not None
        and attempt.run_id == run.run_id
        and attempt.run_digest == run.canonical_digest
        and attempt.step_run_digest == step.canonical_digest
        and attempt.step_id == step.step_id
        and attempt.plan_id == run.plan_id
        and attempt.plan_digest == run.plan_digest
        and attempt.definition_id == run.definition_id
        and attempt.definition_version == run.definition_version
        and attempt.definition_digest == run.definition_digest
        and attempt.scope == run.scope
        and attempt.target_id == run.target_id
        and attempt.target_type == run.target_type
        and attempt.lease_id == run.lease_id
        and attempt.fencing_token == run.fencing_token
        and attempt.attempt_number == 1
        and attempt.state is WorkflowExecutionAttemptState.CREATED
        and not any(attempt.authority.canonical_value().values())
        and not attempt.grants_execution_authority
    )


def _dispatch_intent_matches_attempt(
    intent: WorkflowDispatchIntent,
    attempt: WorkflowExecutionAttempt,
) -> bool:
    return bool(
        intent.plan_id == attempt.plan_id
        and intent.plan_digest == attempt.plan_digest
        and intent.run_id == attempt.run_id
        and intent.run_digest == attempt.run_digest
        and intent.step_run_id == attempt.step_run_id
        and intent.step_run_digest == attempt.step_run_digest
        and intent.step_id == attempt.step_id
        and intent.attempt_id == attempt.attempt_id
        and intent.attempt_digest == attempt.canonical_digest
        and intent.attempt_number == attempt.attempt_number
        and intent.scope == attempt.scope
        and intent.target_id == attempt.target_id
        and intent.target_type == attempt.target_type
        and intent.lease_id == attempt.lease_id
        and intent.fencing_token == attempt.fencing_token
        and intent.state is WorkflowDispatchIntentState.STAGED
        and not any(intent.authority.canonical_value().values())
        and not intent.grants_publication_authority
        and not intent.grants_delivery_authority
        and not intent.grants_dispatch_authority
        and not intent.grants_execution_authority
    )


def _outbox_entry_matches_intent(
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
        and entry.state is WorkflowDispatchOutboxState.PENDING_PUBLICATION
        and not any(entry.authority.canonical_value().values())
        and not entry.grants_publication_authority
        and not entry.grants_delivery_authority
        and not entry.grants_dispatch_authority
        and not entry.grants_execution_authority
    )


def _outbox_entry_matches_route(
    entry: WorkflowDispatchOutboxEntry,
    *,
    plan_id: str,
    run_id: str,
    attempt_id: str,
    dispatch_intent_id: str,
    outbox_entry_id: str,
) -> bool:
    return bool(
        entry.plan_id == plan_id
        and entry.run_id == run_id
        and entry.attempt_id == attempt_id
        and entry.dispatch_intent_id == dispatch_intent_id
        and entry.outbox_entry_id == outbox_entry_id
        and entry.state is WorkflowDispatchOutboxState.PENDING_PUBLICATION
        and not any(entry.authority.canonical_value().values())
        and not entry.grants_publication_authority
        and not entry.grants_delivery_authority
        and not entry.grants_dispatch_authority
        and not entry.grants_execution_authority
    )


def _publication_lease_matches_outbox(
    lease: WorkflowOutboxPublicationLease,
    entry: WorkflowDispatchOutboxEntry,
) -> bool:
    return bool(
        lease.outbox_entry_id == entry.outbox_entry_id
        and lease.outbox_entry_digest == entry.canonical_digest
        and lease.dispatch_intent_id == entry.dispatch_intent_id
        and lease.dispatch_intent_digest == entry.dispatch_intent_digest
        and lease.plan_id == entry.plan_id
        and lease.plan_digest == entry.plan_digest
        and lease.run_id == entry.run_id
        and lease.run_digest == entry.run_digest
        and lease.step_run_id == entry.step_run_id
        and lease.step_run_digest == entry.step_run_digest
        and lease.step_id == entry.step_id
        and lease.attempt_id == entry.attempt_id
        and lease.attempt_digest == entry.attempt_digest
        and lease.attempt_number == entry.attempt_number
        and lease.scope == entry.scope
        and lease.target_id == entry.target_id
        and lease.target_type == entry.target_type
        and lease.orchestration_lease_id == entry.lease_id
        and lease.orchestration_lease_digest == entry.lease_digest
        and lease.orchestration_fencing_token == entry.fencing_token
        and not any(lease.authority.canonical_value().values())
        and not lease.grants_publication_authority
        and not lease.grants_delivery_authority
        and not lease.grants_dispatch_authority
        and not lease.grants_execution_authority
    )


def _dispatch_event_envelope_matches_outbox(
    envelope: WorkflowDispatchEventEnvelope,
    entry: WorkflowDispatchOutboxEntry,
) -> bool:
    payload = envelope.payload
    return bool(
        payload.outbox_entry_id == entry.outbox_entry_id
        and payload.outbox_entry_digest == entry.canonical_digest
        and payload.dispatch_intent_id == entry.dispatch_intent_id
        and payload.dispatch_intent_digest == entry.dispatch_intent_digest
        and payload.plan_id == entry.plan_id
        and payload.plan_digest == entry.plan_digest
        and payload.run_id == entry.run_id
        and payload.run_digest == entry.run_digest
        and payload.step_run_id == entry.step_run_id
        and payload.step_run_digest == entry.step_run_digest
        and payload.step_id == entry.step_id
        and payload.attempt_id == entry.attempt_id
        and payload.attempt_digest == entry.attempt_digest
        and payload.attempt_number == entry.attempt_number
        and payload.scope == entry.scope
        and payload.target_id == entry.target_id
        and payload.target_type == entry.target_type
        and envelope.subject_id == entry.attempt_id
        and envelope.organization_id == entry.scope.organization_id
        and envelope.environment_id == entry.scope.environment_id
        and envelope.correlation_id == entry.run_id
        and envelope.causation_id == entry.dispatch_intent_id
        and envelope.workflow_id == entry.run_id
        and envelope.orchestration_lease_id == entry.lease_id
        and envelope.orchestration_lease_digest == entry.lease_digest
        and envelope.orchestration_fencing_token == entry.fencing_token
        and envelope.extensions == ()
        and not any(envelope.authority.canonical_value().values())
        and not envelope.grants_publication_authority
        and not envelope.grants_delivery_authority
        and not envelope.grants_dispatch_authority
        and not envelope.grants_execution_authority
    )


def _event_transport_admission_matches_envelope(
    admission: WorkflowEventTransportAdmission,
    envelope: WorkflowDispatchEventEnvelope,
    entry: WorkflowDispatchOutboxEntry,
    publication_lease: WorkflowOutboxPublicationLease,
    policy: WorkflowEventTransportAdmissionPolicy,
) -> bool:
    return bool(
        admission.policy_id == policy.policy_id
        and admission.policy_version == policy.policy_version
        and admission.policy_digest == policy.canonical_digest
        and admission.event_id == envelope.event_id
        and admission.event_digest == envelope.canonical_digest
        and admission.event_type == envelope.event_type
        and admission.event_version == envelope.event_version
        and admission.schema_uri == envelope.schema_uri
        and admission.data_classification == envelope.data_classification
        and admission.representation_name == policy.representation_name
        and admission.encoding == policy.encoding
        and admission.maximum_canonical_byte_count == policy.maximum_canonical_byte_count
        and 1 <= admission.canonical_byte_count <= policy.maximum_canonical_byte_count
        and admission.outbox_entry_id == entry.outbox_entry_id
        and admission.outbox_entry_digest == entry.canonical_digest
        and admission.dispatch_intent_id == entry.dispatch_intent_id
        and admission.dispatch_intent_digest == entry.dispatch_intent_digest
        and admission.plan_id == entry.plan_id
        and admission.plan_digest == entry.plan_digest
        and admission.run_id == entry.run_id
        and admission.run_digest == entry.run_digest
        and admission.step_run_id == entry.step_run_id
        and admission.step_run_digest == entry.step_run_digest
        and admission.step_id == entry.step_id
        and admission.attempt_id == entry.attempt_id
        and admission.attempt_digest == entry.attempt_digest
        and admission.attempt_number == entry.attempt_number
        and admission.scope == entry.scope
        and admission.target_id == entry.target_id
        and admission.target_type == entry.target_type
        and admission.orchestration_lease_id == envelope.orchestration_lease_id
        and admission.orchestration_lease_digest == envelope.orchestration_lease_digest
        and admission.orchestration_fencing_token == envelope.orchestration_fencing_token
        and admission.publication_lease_id == publication_lease.publication_lease_id
        and admission.publication_lease_digest == publication_lease.canonical_digest
        and admission.publication_fencing_token == publication_lease.publication_fencing_token
        and admission.publisher_subject_id == publication_lease.publisher_subject_id
        and admission.admitted_at >= envelope.prepared_at
        and admission.state is WorkflowEventTransportAdmissionState.ADMITTED
        and not any(admission.authority.canonical_value().values())
        and not admission.grants_publication_authority
        and not admission.grants_delivery_authority
        and not admission.grants_dispatch_authority
        and not admission.grants_execution_authority
    )


def _event_byte_artifact_response(
    artifact: WorkflowEventByteArtifact,
    request: Request,
    response: Response,
) -> WorkflowEventByteArtifactResponse:
    _no_store(response)
    return WorkflowEventByteArtifactResponse(
        data=WorkflowEventByteArtifactData.from_domain(artifact),
        meta=_meta(request),
    )


def _event_byte_artifact_matches_admission(
    artifact: WorkflowEventByteArtifact,
    admission: WorkflowEventTransportAdmission,
    envelope: WorkflowDispatchEventEnvelope,
    entry: WorkflowDispatchOutboxEntry,
    publication_lease: WorkflowOutboxPublicationLease,
) -> bool:
    return bool(
        artifact.admission_id == admission.admission_id
        and artifact.admission_digest == admission.canonical_digest
        and artifact.policy_id == admission.policy_id
        and artifact.policy_version == admission.policy_version
        and artifact.policy_digest == admission.policy_digest
        and artifact.event_id == envelope.event_id
        and artifact.event_digest == envelope.canonical_digest
        and artifact.event_type == envelope.event_type
        and artifact.event_version == envelope.event_version
        and artifact.schema_uri == envelope.schema_uri
        and artifact.data_classification == envelope.data_classification
        and artifact.representation_name == admission.representation_name
        and artifact.encoding == admission.encoding
        and artifact.canonical_byte_count == admission.canonical_byte_count
        and artifact.maximum_canonical_byte_count == admission.maximum_canonical_byte_count
        and artifact.outbox_entry_id == entry.outbox_entry_id
        and artifact.outbox_entry_digest == entry.canonical_digest
        and artifact.dispatch_intent_id == entry.dispatch_intent_id
        and artifact.dispatch_intent_digest == entry.dispatch_intent_digest
        and artifact.plan_id == entry.plan_id
        and artifact.plan_digest == entry.plan_digest
        and artifact.run_id == entry.run_id
        and artifact.run_digest == entry.run_digest
        and artifact.step_run_id == entry.step_run_id
        and artifact.step_run_digest == entry.step_run_digest
        and artifact.step_id == entry.step_id
        and artifact.attempt_id == entry.attempt_id
        and artifact.attempt_digest == entry.attempt_digest
        and artifact.attempt_number == entry.attempt_number
        and artifact.scope == entry.scope
        and artifact.target_id == entry.target_id
        and artifact.target_type == entry.target_type
        and artifact.orchestration_lease_id == admission.orchestration_lease_id
        and artifact.orchestration_lease_digest == admission.orchestration_lease_digest
        and artifact.orchestration_fencing_token == admission.orchestration_fencing_token
        and artifact.publication_lease_id == publication_lease.publication_lease_id
        and artifact.publication_lease_digest == publication_lease.canonical_digest
        and artifact.publication_fencing_token == publication_lease.publication_fencing_token
        and artifact.publisher_subject_id == publication_lease.publisher_subject_id
        and artifact.materialized_at >= admission.admitted_at
        and artifact.state is WorkflowEventByteArtifactState.MATERIALIZED
        and not any(artifact.authority.canonical_value().values())
        and not artifact.grants_publication_authority
        and not artifact.grants_delivery_authority
        and not artifact.grants_dispatch_authority
        and not artifact.grants_execution_authority
    )


def _event_logical_channel_binding_response(
    binding: WorkflowEventLogicalChannelBinding,
    request: Request,
    response: Response,
) -> WorkflowEventLogicalChannelBindingResponse:
    _no_store(response)
    return WorkflowEventLogicalChannelBindingResponse(
        data=WorkflowEventLogicalChannelBindingData.from_domain(binding),
        meta=_meta(request),
    )


def _transport_profile_snapshot_response(
    snapshot: EventPhysicalTransportProfileSnapshot,
    request: Request,
    response: Response,
) -> EventPhysicalTransportProfileSnapshotResponse:
    _no_store(response)
    return EventPhysicalTransportProfileSnapshotResponse(
        data=EventPhysicalTransportProfileSnapshotData.from_domain(snapshot),
        meta=_meta(request),
    )


def _transport_route_snapshot_response(
    snapshot: EventPhysicalTransportRouteSnapshot,
    request: Request,
    response: Response,
) -> EventPhysicalTransportRouteSnapshotResponse:
    _no_store(response)
    return EventPhysicalTransportRouteSnapshotResponse(
        data=EventPhysicalTransportRouteSnapshotData.from_domain(snapshot),
        meta=_meta(request),
    )


def _transport_credential_assignment_snapshot_response(
    snapshot: EventPhysicalTransportCredentialAssignmentSnapshot,
    request: Request,
    response: Response,
) -> EventPhysicalTransportCredentialAssignmentSnapshotResponse:
    _no_store(response)
    return EventPhysicalTransportCredentialAssignmentSnapshotResponse(
        data=EventPhysicalTransportCredentialAssignmentSnapshotData.from_domain(snapshot),
        meta=_meta(request),
    )


def _physical_transport_route_binding_response(
    binding: WorkflowEventPhysicalTransportRouteBinding,
    request: Request,
    response: Response,
) -> WorkflowEventPhysicalTransportRouteBindingResponse:
    _no_store(response)
    return WorkflowEventPhysicalTransportRouteBindingResponse(
        data=WorkflowEventPhysicalTransportRouteBindingData.from_domain(binding),
        meta=_meta(request),
    )


def _physical_transport_credential_assignment_binding_response(
    binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding,
    request: Request,
    response: Response,
) -> WorkflowEventPhysicalTransportCredentialAssignmentBindingResponse:
    _no_store(response)
    return WorkflowEventPhysicalTransportCredentialAssignmentBindingResponse(
        data=WorkflowEventPhysicalTransportCredentialAssignmentBindingData.from_domain(binding),
        meta=_meta(request),
    )


def _physical_transport_credential_assignment_freshness_admission_response(
    admission: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission,
    request: Request,
    response: Response,
) -> WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionResponse:
    _no_store(response)
    return WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionResponse(
        data=(
            WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionData.from_domain(
                admission
            )
        ),
        meta=_meta(request),
    )


def _physical_transport_credential_access_authorization_lease_response(
    lease: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease,
    request: Request,
    response: Response,
) -> WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseResponse:
    _no_store(response)
    return WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseResponse(
        data=WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseData.from_domain(
            lease,
            evaluated_at=lease.issued_at,
        ),
        meta=_meta(request),
    )


def _physical_transport_target_context_access_authorization_lease_response(
    lease: WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease,
    request: Request,
    response: Response,
) -> WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseResponse:
    _no_store(response)
    return WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseResponse(
        data=(
            WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseData.from_domain(
                lease,
                evaluated_at=lease.issued_at,
            )
        ),
        meta=_meta(request),
    )


def _physical_transport_target_context_artifact_opening_response(
    result: WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult,
    request: Request,
    response: Response,
) -> WorkflowEventPhysicalTransportTargetContextArtifactOpeningResponse:
    _no_store(response)
    return WorkflowEventPhysicalTransportTargetContextArtifactOpeningResponse(
        data=WorkflowEventPhysicalTransportTargetContextArtifactOpeningData.from_domain(result),
        meta=_meta(request),
    )


def _physical_transport_target_context_capsule_consumer_binding_response(
    binding: WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
    request: Request,
    response: Response,
) -> WorkflowProtectedTransportTargetContextCapsuleConsumerBindingResponse:
    _no_store(response)
    return WorkflowProtectedTransportTargetContextCapsuleConsumerBindingResponse(
        data=WorkflowProtectedTransportTargetContextCapsuleConsumerBindingData.from_domain(binding),
        meta=_meta(request),
    )


def _physical_transport_target_context_capsule_handoff_authorization_lease_response(
    lease: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease,
    request: Request,
    response: Response,
    *,
    evaluated_at: datetime,
) -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseResponse:
    _no_store(response)
    return WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseResponse(
        data=(
            WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseData.from_domain(
                lease,
                evaluated_at=evaluated_at,
            )
        ),
        meta=_meta(request),
    )


def _physical_transport_route_freshness_admission_response(
    admission: WorkflowEventPhysicalTransportRouteFreshnessAdmission,
    request: Request,
    response: Response,
) -> WorkflowEventPhysicalTransportRouteFreshnessAdmissionResponse:
    _no_store(response)
    return WorkflowEventPhysicalTransportRouteFreshnessAdmissionResponse(
        data=WorkflowEventPhysicalTransportRouteFreshnessAdmissionData.from_domain(admission),
        meta=_meta(request),
    )


def _physical_transport_endpoint_resolution_authorization_lease_response(
    lease: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease,
    request: Request,
    response: Response,
) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResponse:
    server_time = datetime.now(UTC)
    _no_store(response)
    return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResponse(
        data=(
            WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseData.from_domain(
                lease,
                evaluated_at=server_time,
            )
        ),
        meta=_meta(request),
    )


def _transport_compatibility_admission_response(
    admission: WorkflowEventTransportCompatibilityAdmission,
    request: Request,
    response: Response,
) -> WorkflowEventTransportCompatibilityAdmissionResponse:
    _no_store(response)
    return WorkflowEventTransportCompatibilityAdmissionResponse(
        data=WorkflowEventTransportCompatibilityAdmissionData.from_domain(admission),
        meta=_meta(request),
    )


def _transport_compatibility_admission_matches_request(
    admission: WorkflowEventTransportCompatibilityAdmission,
    *,
    logical_channel_binding_id: str,
    policy_id: str,
    policy_version: str,
    policy_digest: str,
    scope: WorkflowScope,
) -> bool:
    return bool(
        admission.compatibility_admission_id
        and admission.logical_channel_binding_id == logical_channel_binding_id
        and admission.policy_id == policy_id
        and admission.policy_version == policy_version
        and admission.policy_digest == policy_digest
        and admission.scope == scope
        and admission.state is WorkflowEventTransportCompatibilityAdmissionState.ADMITTED
        and not any(admission.authority.canonical_value().values())
        and admission.canonical_digest == canonical_digest(admission.digest_payload())
    )


def _transport_profile_snapshot_matches_source(
    snapshot: EventPhysicalTransportProfileSnapshot,
    source: DeploymentEventTransportProfile,
) -> bool:
    source_fields = (
        "transport_profile_id",
        "transport_profile_revision",
        "deployment_release_id",
        "deployment_profile",
        "scope",
        "transport_resource_id",
        "transport_resource_digest",
        "transport_implementation_id",
        "transport_implementation_version",
        "adapter_contract_id",
        "adapter_contract_version",
        "adapter_contract_digest",
        "supported_event_contracts",
        "supported_classifications",
        "supported_representations",
        "supported_encodings",
        "supported_delivery_semantics",
        "durable_delivery_supported",
        "supported_ordering_key_kinds",
        "supported_retention_classes",
        "maximum_message_byte_count",
        "transport_encryption_required",
        "restricted_network_supported",
    )
    return bool(
        snapshot.source_profile_digest == source.canonical_digest
        and all(getattr(snapshot, field) == getattr(source, field) for field in source_fields)
        and not any(snapshot.authority.canonical_value().values())
    )


def _transport_route_snapshot_matches_source(
    snapshot: EventPhysicalTransportRouteSnapshot,
    source: DeploymentEventTransportRoute,
) -> bool:
    source_fields = (
        "route_id",
        "route_revision",
        "route_set_id",
        "route_set_revision",
        "selection_epoch_id",
        "selection_epoch_revision",
        "deployment_release_id",
        "deployment_profile",
        "scope",
        "transport_profile_id",
        "transport_profile_revision",
        "transport_resource_id",
        "transport_resource_digest",
        "transport_implementation_id",
        "transport_implementation_version",
        "adapter_contract_id",
        "adapter_contract_version",
        "adapter_contract_digest",
        "route_kind",
        "endpoint_set_id",
        "endpoint_set_revision",
        "destination_id",
        "destination_revision",
        "routing_contract_id",
        "routing_contract_revision",
        "private_route_descriptor_commitment",
        "transport_security_policy_id",
        "transport_security_policy_version",
        "transport_security_policy_digest",
        "minimum_tls_version",
        "server_authentication_required",
        "client_authentication_required",
        "plaintext_fallback_prohibited",
        "network_policy_id",
        "network_policy_version",
        "network_policy_digest",
        "source_zone_class",
        "destination_zone_class",
        "restricted_network_enforced",
        "public_egress_prohibited",
        "proxy_mode",
        "credential_requirement_profile_id",
        "credential_requirement_profile_version",
        "credential_requirement_profile_digest",
        "authentication_mechanism_class",
        "principal_class",
    )
    return bool(
        snapshot.source_route_digest == source.canonical_digest
        and all(getattr(snapshot, field) == getattr(source, field) for field in source_fields)
        and not any(snapshot.authority.canonical_value().values())
    )


def _event_logical_channel_binding_matches_artifact(
    binding: WorkflowEventLogicalChannelBinding,
    artifact: WorkflowEventByteArtifact,
    policy: WorkflowEventLogicalChannelPolicy,
) -> bool:
    return bool(
        binding.artifact_id == artifact.artifact_id
        and binding.artifact_digest == artifact.canonical_digest
        and binding.content_sha256 == artifact.content_sha256
        and binding.canonical_byte_count == artifact.canonical_byte_count
        and binding.admission_id == artifact.admission_id
        and binding.admission_digest == artifact.admission_digest
        and binding.event_id == artifact.event_id
        and binding.event_digest == artifact.event_digest
        and binding.event_type == artifact.event_type
        and binding.event_version == artifact.event_version
        and binding.schema_uri == artifact.schema_uri
        and binding.outbox_entry_id == artifact.outbox_entry_id
        and binding.outbox_entry_digest == artifact.outbox_entry_digest
        and binding.dispatch_intent_id == artifact.dispatch_intent_id
        and binding.dispatch_intent_digest == artifact.dispatch_intent_digest
        and binding.plan_id == artifact.plan_id
        and binding.plan_digest == artifact.plan_digest
        and binding.run_id == artifact.run_id
        and binding.run_digest == artifact.run_digest
        and binding.step_run_id == artifact.step_run_id
        and binding.step_run_digest == artifact.step_run_digest
        and binding.step_id == artifact.step_id
        and binding.attempt_id == artifact.attempt_id
        and binding.attempt_digest == artifact.attempt_digest
        and binding.attempt_number == artifact.attempt_number
        and binding.scope == artifact.scope
        and binding.target_id == artifact.target_id
        and binding.target_type == artifact.target_type
        and binding.policy_id == policy.policy_id
        and binding.policy_version == policy.policy_version
        and binding.policy_digest == policy.canonical_digest
        and binding.logical_channel_id == policy.logical_channel_id
        and binding.logical_channel_version == policy.logical_channel_version
        and binding.event_type in policy.allowed_event_types
        and binding.event_version in policy.allowed_event_versions
        and binding.schema_uri in policy.allowed_schema_uris
        and binding.data_classification in policy.allowed_data_classifications
        and binding.data_classification == artifact.data_classification
        and binding.representation_name == policy.representation_name
        and binding.representation_name == artifact.representation_name
        and binding.encoding == policy.encoding
        and binding.encoding == artifact.encoding
        and binding.delivery_semantics == policy.delivery_semantics
        and binding.durability_required == policy.durability_required
        and binding.ordering_key_kind == policy.ordering_key_kind
        and binding.ordering_key_value == artifact.run_id
        and binding.retention_class == policy.retention_class
        and binding.maximum_canonical_byte_count == policy.maximum_canonical_byte_count
        and binding.canonical_byte_count <= binding.maximum_canonical_byte_count
        and binding.orchestration_lease_id == artifact.orchestration_lease_id
        and binding.orchestration_lease_digest == artifact.orchestration_lease_digest
        and binding.orchestration_fencing_token == artifact.orchestration_fencing_token
        and binding.publication_lease_id == artifact.publication_lease_id
        and binding.publication_lease_digest == artifact.publication_lease_digest
        and binding.publication_fencing_token == artifact.publication_fencing_token
        and binding.publisher_subject_id == artifact.publisher_subject_id
        and binding.bound_at >= artifact.materialized_at
        and binding.state is WorkflowEventLogicalChannelBindingState.BOUND
        and not any(binding.authority.canonical_value().values())
        and not binding.grants_publication_authority
        and not binding.grants_delivery_authority
        and not binding.grants_dispatch_authority
        and not binding.grants_execution_authority
    )


def _plan_response(
    plan: WorkflowRunPlan, request: Request, response: Response
) -> WorkflowRunPlanResponse:
    _no_store(response)
    return WorkflowRunPlanResponse(data=WorkflowRunPlanData.from_domain(plan), meta=_meta(request))


@router.get("/definitions", response_model=WorkflowDefinitionInventoryResponse)
async def list_workflow_definitions(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_workflow_definition_read)],
) -> WorkflowDefinitionInventoryResponse:
    service: WorkflowPlanningService = request.app.state.workflow_planning_service
    try:
        definitions = await service.list_definitions(
            context=await _context(request, subject, decision)
        )
    except WorkflowPlanningError as error:
        _raise(error)
    _no_store(response)
    return WorkflowDefinitionInventoryResponse(
        data=WorkflowDefinitionInventoryData(
            definitions=[WorkflowDefinitionData.from_domain(item) for item in definitions]
        ),
        meta=_meta(request),
    )


@router.post("/plans", response_model=WorkflowRunPlanResponse, status_code=201)
async def create_workflow_plan(
    payload: CreateWorkflowPlanInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_workflow_plan_create)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> WorkflowRunPlanResponse:
    service: WorkflowPlanningService = request.app.state.workflow_planning_service
    try:
        plan = await service.create_plan(
            definition_id=payload.definition_id,
            definition_version=payload.definition_version,
            target_id=payload.target_id,
            inputs=payload.inputs,
            idempotency_key=idempotency_key,
            context=await _context(request, subject, decision),
        )
    except WorkflowPlanningError as error:
        _raise(error)
    return _plan_response(plan, request, response)


@router.get("/plans", response_model=WorkflowPlanInventoryResponse)
async def list_workflow_plans(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_workflow_plan_read)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> WorkflowPlanInventoryResponse:
    service: WorkflowPlanningService = request.app.state.workflow_planning_service
    try:
        plans = await service.list_plans(
            context=await _context(request, subject, decision), limit=limit
        )
    except WorkflowPlanningError as error:
        _raise(error)
    _no_store(response)
    return WorkflowPlanInventoryResponse(
        data=WorkflowPlanInventoryData(
            plans=[WorkflowRunPlanData.from_domain(item) for item in plans],
            durable=service.durable,
            truncated=len(plans) == limit,
        ),
        meta=_meta(request),
    )


@router.post("/plans/{plan_id}/cancellation", response_model=WorkflowRunPlanResponse)
async def cancel_workflow_plan(
    plan_id: Annotated[str, SAFE_ID],
    payload: CancelWorkflowPlanInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_workflow_plan_cancel)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> WorkflowRunPlanResponse:
    service: WorkflowPlanningService = request.app.state.workflow_planning_service
    try:
        plan = await service.cancel_plan(
            plan_id=plan_id,
            reason=payload.reason,
            acknowledge_no_external_undo=payload.acknowledge_no_external_undo,
            idempotency_key=idempotency_key,
            context=await _context(request, subject, decision),
        )
    except WorkflowPlanningError as error:
        _raise(error)
    return _plan_response(plan, request, response)


@router.get(
    "/plans/{plan_id}/orchestration-lease",
    response_model=WorkflowOrchestrationLeaseStatusResponse,
)
async def get_workflow_orchestration_lease_status(
    plan_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_workflow_plan_read)],
) -> WorkflowOrchestrationLeaseStatusResponse:
    planning_service: WorkflowPlanningService = request.app.state.workflow_planning_service
    try:
        plan = await planning_service.get_plan(
            plan_id=plan_id,
            context=await _context(request, subject, decision),
        )
    except WorkflowPlanningError as error:
        _raise(error)
    repository: WorkflowOrchestrationLeaseRepository = (
        request.app.state.workflow_orchestration_lease_repository
    )
    try:
        lease = await repository.get_lease_by_plan_id(plan_id=plan.plan_id)
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_lease_service_unavailable",
            title="Workflow lease service unavailable",
            detail="The workflow lease status is unavailable.",
            retryable=True,
        ) from error
    if lease is not None and (
        lease.plan_id != plan.plan_id
        or lease.plan_digest != plan.canonical_digest
        or lease.scope != plan.scope
        or lease.target_id != plan.target_id
        or lease.target_type != plan.target_type
        or lease.grants_execution_authority
    ):
        raise AtlasError(
            status=503,
            code="workflow_lease_service_unavailable",
            title="Workflow lease service unavailable",
            detail="The workflow lease status is unavailable.",
            retryable=True,
        )
    server_time = datetime.now(UTC)
    _no_store(response)
    return WorkflowOrchestrationLeaseStatusResponse(
        data=WorkflowOrchestrationLeaseStatusData(
            plan_id=plan.plan_id,
            lease=(
                None
                if lease is None
                else WorkflowOrchestrationLeaseData.from_domain(
                    lease,
                    requested_at=server_time,
                )
            ),
            server_time=server_time,
            durable=repository.durable,
        ),
        meta=_meta(request),
    )


@router.get(
    "/plans/{plan_id}/materialized-run",
    response_model=WorkflowMaterializedRunStatusResponse,
)
async def get_workflow_materialized_run_status(
    plan_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_workflow_plan_read)],
) -> WorkflowMaterializedRunStatusResponse:
    planning_service: WorkflowPlanningService = request.app.state.workflow_planning_service
    try:
        plan = await planning_service.get_plan(
            plan_id=plan_id,
            context=await _context(request, subject, decision),
        )
    except WorkflowPlanningError as error:
        _raise(error)
    repository: WorkflowRunMaterializationRepository = (
        request.app.state.workflow_run_materialization_repository
    )
    try:
        run = await repository.get_materialized_run_by_plan_id(plan_id=plan.plan_id)
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_run_service_unavailable",
            title="Workflow run service unavailable",
            detail="The workflow run status is unavailable.",
            retryable=True,
        ) from error
    if run is not None and not _run_matches_plan(run, plan):
        raise AtlasError(
            status=503,
            code="workflow_run_service_unavailable",
            title="Workflow run service unavailable",
            detail="The workflow run status is unavailable.",
            retryable=True,
        )
    _no_store(response)
    return WorkflowMaterializedRunStatusResponse(
        data=WorkflowMaterializedRunStatusData(
            plan_id=plan.plan_id,
            run=None if run is None else WorkflowExecutionRunData.from_domain(run),
            server_time=datetime.now(UTC),
            durable=repository.durable,
        ),
        meta=_meta(request),
    )


@router.post(
    "/plans/{plan_id}/materialized-run",
    response_model=WorkflowExecutionRunResponse,
    status_code=201,
)
async def materialize_workflow_run(
    plan_id: Annotated[str, SAFE_ID],
    payload: MaterializeWorkflowRunInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(workflow_worker_subject)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> WorkflowExecutionRunResponse:
    service: WorkflowRunMaterializationService = (
        request.app.state.workflow_run_materialization_service
    )
    try:
        run = await service.materialize(
            plan_id=plan_id,
            plan_digest=payload.plan_digest,
            lease_id=payload.lease_id,
            lease_digest=payload.lease_digest,
            fencing_token=payload.fencing_token,
            idempotency_key=idempotency_key,
            context=await _worker_context(request, subject, target_id=payload.target_id),
        )
    except WorkflowRunMaterializationError as error:
        _raise_materialization(error)
    return _run_response(run, request, response)


@router.get(
    "/plans/{plan_id}/runs/{run_id}/attempts",
    response_model=WorkflowAttemptInventoryResponse,
)
async def list_workflow_attempts(
    plan_id: Annotated[str, SAFE_ID],
    run_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_workflow_plan_read)],
) -> WorkflowAttemptInventoryResponse:
    planning_service: WorkflowPlanningService = request.app.state.workflow_planning_service
    try:
        plan = await planning_service.get_plan(
            plan_id=plan_id,
            context=await _context(request, subject, decision),
        )
    except WorkflowPlanningError as error:
        _raise(error)
    run_repository: WorkflowRunMaterializationRepository = (
        request.app.state.workflow_run_materialization_repository
    )
    attempt_repository: WorkflowAttemptMaterializationRepository = (
        request.app.state.workflow_attempt_materialization_repository
    )
    try:
        run = await run_repository.get_materialized_run_by_plan_id(plan_id=plan.plan_id)
        if run is None or run.run_id != run_id or not _run_matches_plan(run, plan):
            raise AtlasError(
                status=404,
                code="workflow_resource_unavailable",
                title="Workflow resource unavailable",
                detail="The requested workflow resource is unavailable.",
            )
        attempts = await attempt_repository.list_attempts_by_run_id(run_id=run.run_id)
    except AtlasError:
        raise
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_attempt_service_unavailable",
            title="Workflow attempt service unavailable",
            detail="Workflow attempt evidence is unavailable.",
            retryable=True,
        ) from error
    if any(not _attempt_matches_run(attempt, run) for attempt in attempts) or len(
        {attempt.step_run_id for attempt in attempts}
    ) != len(attempts):
        raise AtlasError(
            status=503,
            code="workflow_attempt_service_unavailable",
            title="Workflow attempt service unavailable",
            detail="Workflow attempt evidence is unavailable.",
            retryable=True,
        )
    step_order = {step.step_run_id: step.ordinal for step in run.step_runs}
    attempts = tuple(sorted(attempts, key=lambda item: step_order[item.step_run_id]))
    _no_store(response)
    return WorkflowAttemptInventoryResponse(
        data=WorkflowAttemptInventoryData(
            run_id=run.run_id,
            attempts=[WorkflowExecutionAttemptData.from_domain(item) for item in attempts],
            server_time=datetime.now(UTC),
            durable=attempt_repository.durable,
        ),
        meta=_meta(request),
    )


@router.post(
    "/plans/{plan_id}/runs/{run_id}/steps/{step_run_id}/attempts",
    response_model=WorkflowExecutionAttemptResponse,
    status_code=201,
)
async def materialize_workflow_attempt(
    plan_id: Annotated[str, SAFE_ID],
    run_id: Annotated[str, SAFE_ID],
    step_run_id: Annotated[str, SAFE_ID],
    payload: MaterializeWorkflowAttemptInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(workflow_worker_subject)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> WorkflowExecutionAttemptResponse:
    service: WorkflowAttemptMaterializationService = (
        request.app.state.workflow_attempt_materialization_service
    )
    try:
        attempt = await service.materialize(
            plan_id=plan_id,
            plan_digest=payload.plan_digest,
            run_id=run_id,
            run_digest=payload.run_digest,
            step_run_id=step_run_id,
            step_run_digest=payload.step_run_digest,
            lease_id=payload.lease_id,
            lease_digest=payload.lease_digest,
            fencing_token=payload.fencing_token,
            idempotency_key=idempotency_key,
            context=await _worker_context(request, subject, target_id=payload.target_id),
        )
    except WorkflowAttemptMaterializationError as error:
        _raise_attempt(error)
    return _attempt_response(attempt, request, response)


@router.get(
    "/plans/{plan_id}/runs/{run_id}/attempts/{attempt_id}/dispatch-intents",
    response_model=WorkflowDispatchIntentInventoryResponse,
)
async def list_workflow_dispatch_intents(
    plan_id: Annotated[str, SAFE_ID],
    run_id: Annotated[str, SAFE_ID],
    attempt_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_workflow_plan_read)],
) -> WorkflowDispatchIntentInventoryResponse:
    planning_service: WorkflowPlanningService = request.app.state.workflow_planning_service
    try:
        plan = await planning_service.get_plan(
            plan_id=plan_id,
            context=await _context(request, subject, decision),
        )
    except WorkflowPlanningError as error:
        _raise(error)
    run_repository: WorkflowRunMaterializationRepository = (
        request.app.state.workflow_run_materialization_repository
    )
    attempt_repository: WorkflowAttemptMaterializationRepository = (
        request.app.state.workflow_attempt_materialization_repository
    )
    intent_repository: WorkflowDispatchIntentStagingRepository = (
        request.app.state.workflow_dispatch_intent_staging_repository
    )
    try:
        run = await run_repository.get_materialized_run_by_plan_id(plan_id=plan.plan_id)
        if run is None or run.run_id != run_id or not _run_matches_plan(run, plan):
            raise AtlasError(
                status=404,
                code="workflow_resource_unavailable",
                title="Workflow resource unavailable",
                detail="The requested workflow resource is unavailable.",
            )
        attempts = await attempt_repository.list_attempts_by_run_id(run_id=run.run_id)
        if any(not _attempt_matches_run(item, run) for item in attempts):
            raise RuntimeError("unsafe workflow attempt evidence")
        attempt = next((item for item in attempts if item.attempt_id == attempt_id), None)
        if attempt is None:
            raise AtlasError(
                status=404,
                code="workflow_resource_unavailable",
                title="Workflow resource unavailable",
                detail="The requested workflow resource is unavailable.",
            )
        all_intents = await intent_repository.list_dispatch_intents_by_run_id(run_id=run.run_id)
    except AtlasError:
        raise
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_dispatch_intent_service_unavailable",
            title="Workflow dispatch intent service unavailable",
            detail="Workflow dispatch intent evidence is unavailable.",
            retryable=True,
        ) from error
    attempt_by_id = {item.attempt_id: item for item in attempts}
    if (
        len({item.dispatch_intent_id for item in all_intents}) != len(all_intents)
        or len({item.attempt_id for item in all_intents}) != len(all_intents)
        or any(
            item.attempt_id not in attempt_by_id
            or not _dispatch_intent_matches_attempt(item, attempt_by_id[item.attempt_id])
            for item in all_intents
        )
    ):
        raise AtlasError(
            status=503,
            code="workflow_dispatch_intent_service_unavailable",
            title="Workflow dispatch intent service unavailable",
            detail="Workflow dispatch intent evidence is unavailable.",
            retryable=True,
        )
    intents = [item for item in all_intents if item.attempt_id == attempt.attempt_id]
    _no_store(response)
    return WorkflowDispatchIntentInventoryResponse(
        data=WorkflowDispatchIntentInventoryData(
            attempt_id=attempt.attempt_id,
            dispatch_intents=[WorkflowDispatchIntentData.from_domain(item) for item in intents],
            server_time=datetime.now(UTC),
            durable=intent_repository.durable,
        ),
        meta=_meta(request),
    )


@router.get(
    (
        "/plans/{plan_id}/runs/{run_id}/attempts/{attempt_id}/dispatch-intents/"
        "{dispatch_intent_id}/outbox"
    ),
    response_model=WorkflowDispatchOutboxInventoryResponse,
)
async def list_workflow_dispatch_outbox_entries(
    plan_id: Annotated[str, SAFE_ID],
    run_id: Annotated[str, SAFE_ID],
    attempt_id: Annotated[str, SAFE_ID],
    dispatch_intent_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_workflow_plan_read)],
) -> WorkflowDispatchOutboxInventoryResponse:
    planning_service: WorkflowPlanningService = request.app.state.workflow_planning_service
    try:
        plan = await planning_service.get_plan(
            plan_id=plan_id,
            context=await _context(request, subject, decision),
        )
    except WorkflowPlanningError as error:
        _raise(error)
    run_repository: WorkflowRunMaterializationRepository = (
        request.app.state.workflow_run_materialization_repository
    )
    attempt_repository: WorkflowAttemptMaterializationRepository = (
        request.app.state.workflow_attempt_materialization_repository
    )
    repository: WorkflowDispatchIntentStagingRepository = (
        request.app.state.workflow_dispatch_intent_staging_repository
    )
    try:
        run = await run_repository.get_materialized_run_by_plan_id(plan_id=plan.plan_id)
        if run is None or run.run_id != run_id or not _run_matches_plan(run, plan):
            raise AtlasError(
                status=404,
                code="workflow_resource_unavailable",
                title="Workflow resource unavailable",
                detail="The requested workflow resource is unavailable.",
            )
        attempts = await attempt_repository.list_attempts_by_run_id(run_id=run.run_id)
        if any(not _attempt_matches_run(item, run) for item in attempts):
            raise RuntimeError("unsafe workflow attempt evidence")
        attempt_by_id = {item.attempt_id: item for item in attempts}
        attempt = next((item for item in attempts if item.attempt_id == attempt_id), None)
        if attempt is None:
            raise AtlasError(
                status=404,
                code="workflow_resource_unavailable",
                title="Workflow resource unavailable",
                detail="The requested workflow resource is unavailable.",
            )
        intents = await repository.list_dispatch_intents_by_run_id(run_id=run.run_id)
        if (
            len({item.dispatch_intent_id for item in intents}) != len(intents)
            or len({item.attempt_id for item in intents}) != len(intents)
            or any(
                item.attempt_id not in attempt_by_id
                or not _dispatch_intent_matches_attempt(item, attempt_by_id[item.attempt_id])
                for item in intents
            )
        ):
            raise RuntimeError("unsafe workflow dispatch intent evidence")
        intent = next(
            (
                item
                for item in intents
                if item.dispatch_intent_id == dispatch_intent_id
                and item.attempt_id == attempt.attempt_id
            ),
            None,
        )
        if intent is None or not _dispatch_intent_matches_attempt(intent, attempt):
            raise AtlasError(
                status=404,
                code="workflow_resource_unavailable",
                title="Workflow resource unavailable",
                detail="The requested workflow resource is unavailable.",
            )
        all_entries = await repository.list_dispatch_outbox_entries_by_run_id(run_id=run.run_id)
    except AtlasError:
        raise
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_dispatch_outbox_service_unavailable",
            title="Workflow dispatch outbox service unavailable",
            detail="Workflow dispatch outbox evidence is unavailable.",
            retryable=True,
        ) from error
    intent_by_id = {item.dispatch_intent_id: item for item in intents}
    if (
        len(all_entries) != len(intents)
        or len({item.outbox_entry_id for item in all_entries}) != len(all_entries)
        or len({item.dispatch_intent_id for item in all_entries}) != len(all_entries)
        or any(
            item.dispatch_intent_id not in intent_by_id
            or not _outbox_entry_matches_intent(item, intent_by_id[item.dispatch_intent_id])
            for item in all_entries
        )
    ):
        raise AtlasError(
            status=503,
            code="workflow_dispatch_outbox_service_unavailable",
            title="Workflow dispatch outbox service unavailable",
            detail="Workflow dispatch outbox evidence is unavailable.",
            retryable=True,
        )
    entries = [item for item in all_entries if item.dispatch_intent_id == intent.dispatch_intent_id]
    if len(entries) != 1:
        raise AtlasError(
            status=503,
            code="workflow_dispatch_outbox_service_unavailable",
            title="Workflow dispatch outbox service unavailable",
            detail="Workflow dispatch outbox evidence is unavailable.",
            retryable=True,
        )
    _no_store(response)
    return WorkflowDispatchOutboxInventoryResponse(
        data=WorkflowDispatchOutboxInventoryData(
            dispatch_intent_id=intent.dispatch_intent_id,
            outbox_entries=[WorkflowDispatchOutboxEntryData.from_domain(item) for item in entries],
            server_time=datetime.now(UTC),
            durable=repository.durable,
        ),
        meta=_meta(request),
    )


@router.get(
    (
        "/plans/{plan_id}/runs/{run_id}/attempts/{attempt_id}/dispatch-intents/"
        "{dispatch_intent_id}/outbox/{outbox_entry_id}/publication-lease"
    ),
    response_model=WorkflowOutboxPublicationLeaseInventoryResponse,
)
async def get_workflow_outbox_publication_lease(
    plan_id: Annotated[str, SAFE_ID],
    run_id: Annotated[str, SAFE_ID],
    attempt_id: Annotated[str, SAFE_ID],
    dispatch_intent_id: Annotated[str, SAFE_ID],
    outbox_entry_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_workflow_plan_read)],
) -> WorkflowOutboxPublicationLeaseInventoryResponse:
    planning_service: WorkflowPlanningService = request.app.state.workflow_planning_service
    try:
        plan = await planning_service.get_plan(
            plan_id=plan_id,
            context=await _context(request, subject, decision),
        )
    except WorkflowPlanningError as error:
        _raise(error)
    repository: WorkflowOutboxPublicationLeaseRepository = (
        request.app.state.workflow_outbox_publication_lease_repository
    )
    try:
        entry = await repository.get_outbox_entry_by_id(outbox_entry_id=outbox_entry_id)
        lease = await repository.get_publication_lease_by_outbox_entry_id(
            outbox_entry_id=outbox_entry_id
        )
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_outbox_publication_lease_service_unavailable",
            title="Workflow outbox publication lease service unavailable",
            detail="Workflow outbox publication lease evidence is unavailable.",
            retryable=True,
        ) from error
    if (
        entry is None
        or not _outbox_entry_matches_route(
            entry,
            plan_id=plan_id,
            run_id=run_id,
            attempt_id=attempt_id,
            dispatch_intent_id=dispatch_intent_id,
            outbox_entry_id=outbox_entry_id,
        )
        or entry.plan_digest != plan.canonical_digest
        or entry.scope != plan.scope
        or entry.target_id != plan.target_id
        or entry.target_type != plan.target_type
    ):
        raise AtlasError(
            status=404,
            code="workflow_resource_unavailable",
            title="Workflow resource unavailable",
            detail="The requested workflow resource is unavailable.",
        )
    if lease is not None and not _publication_lease_matches_outbox(lease, entry):
        raise AtlasError(
            status=503,
            code="workflow_outbox_publication_lease_service_unavailable",
            title="Workflow outbox publication lease service unavailable",
            detail="Workflow outbox publication lease evidence is unavailable.",
            retryable=True,
        )
    server_time = datetime.now(UTC)
    if lease is not None and lease.effective_state(requested_at=server_time).value == "active":
        orchestration_repository: WorkflowOrchestrationLeaseRepository = (
            request.app.state.workflow_orchestration_lease_repository
        )
        try:
            orchestration_lease = await orchestration_repository.get_lease_by_plan_id(
                plan_id=plan.plan_id
            )
        except Exception as error:
            raise AtlasError(
                status=503,
                code="workflow_outbox_publication_lease_service_unavailable",
                title="Workflow outbox publication lease service unavailable",
                detail="Workflow outbox publication lease evidence is unavailable.",
                retryable=True,
            ) from error
        if (
            orchestration_lease is None
            or orchestration_lease.lease_id != lease.orchestration_lease_id
            or orchestration_lease.canonical_digest != lease.orchestration_lease_digest
            or orchestration_lease.fencing_token != lease.orchestration_fencing_token
            or orchestration_lease.effective_state(requested_at=server_time)
            is not WorkflowOrchestrationLeaseEffectiveState.ACTIVE
        ):
            raise AtlasError(
                status=503,
                code="workflow_outbox_publication_lease_service_unavailable",
                title="Workflow outbox publication lease service unavailable",
                detail="Workflow outbox publication lease evidence is unavailable.",
                retryable=True,
            )
    _no_store(response)
    return WorkflowOutboxPublicationLeaseInventoryResponse(
        data=WorkflowOutboxPublicationLeaseInventoryData(
            outbox_entry_id=entry.outbox_entry_id,
            publication_leases=(
                []
                if lease is None
                else [
                    WorkflowOutboxPublicationLeaseData.from_domain(
                        lease,
                        requested_at=server_time,
                    )
                ]
            ),
            server_time=server_time,
            durable=repository.durable,
        ),
        meta=_meta(request),
    )


async def _require_bound_publication_outbox(
    *,
    repository: WorkflowOutboxPublicationLeaseRepository,
    plan_id: str,
    run_id: str,
    attempt_id: str,
    dispatch_intent_id: str,
    outbox_entry_id: str,
) -> WorkflowDispatchOutboxEntry:
    try:
        entry = await repository.get_outbox_entry_by_id(outbox_entry_id=outbox_entry_id)
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_outbox_publication_lease_service_unavailable",
            title="Workflow outbox publication lease service unavailable",
            detail="Workflow outbox publication lease evidence is unavailable.",
            retryable=True,
        ) from error
    if entry is None or not _outbox_entry_matches_route(
        entry,
        plan_id=plan_id,
        run_id=run_id,
        attempt_id=attempt_id,
        dispatch_intent_id=dispatch_intent_id,
        outbox_entry_id=outbox_entry_id,
    ):
        raise AtlasError(
            status=404,
            code="workflow_resource_unavailable",
            title="Workflow resource unavailable",
            detail="The requested workflow resource is unavailable.",
        )
    return entry


@router.post(
    (
        "/plans/{plan_id}/runs/{run_id}/attempts/{attempt_id}/dispatch-intents/"
        "{dispatch_intent_id}/outbox/{outbox_entry_id}/publication-lease/acquisition"
    ),
    response_model=WorkflowOutboxPublicationLeaseResponse,
    status_code=201,
)
async def acquire_workflow_outbox_publication_lease(
    plan_id: Annotated[str, SAFE_ID],
    run_id: Annotated[str, SAFE_ID],
    attempt_id: Annotated[str, SAFE_ID],
    dispatch_intent_id: Annotated[str, SAFE_ID],
    outbox_entry_id: Annotated[str, SAFE_ID],
    payload: AcquireWorkflowOutboxPublicationLeaseInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(workflow_outbox_publisher_subject)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> WorkflowOutboxPublicationLeaseResponse:
    service: WorkflowOutboxPublicationLeaseService = (
        request.app.state.workflow_outbox_publication_lease_service
    )
    await _require_bound_publication_outbox(
        repository=service.repository,
        plan_id=plan_id,
        run_id=run_id,
        attempt_id=attempt_id,
        dispatch_intent_id=dispatch_intent_id,
        outbox_entry_id=outbox_entry_id,
    )
    try:
        lease = await service.acquire(
            outbox_entry_id=outbox_entry_id,
            outbox_entry_digest=payload.outbox_entry_digest,
            lease_seconds=payload.lease_duration_seconds,
            idempotency_key=idempotency_key,
            context=await _publisher_context(request, subject, target_id=payload.target_id),
        )
    except WorkflowOutboxPublicationLeaseError as error:
        _raise_publication_lease(error)
    return _publication_lease_response(lease, request, response)


@router.post(
    (
        "/plans/{plan_id}/runs/{run_id}/attempts/{attempt_id}/dispatch-intents/"
        "{dispatch_intent_id}/outbox/{outbox_entry_id}/publication-lease/"
        "{publication_lease_id}/heartbeat"
    ),
    response_model=WorkflowOutboxPublicationLeaseResponse,
)
async def heartbeat_workflow_outbox_publication_lease(
    plan_id: Annotated[str, SAFE_ID],
    run_id: Annotated[str, SAFE_ID],
    attempt_id: Annotated[str, SAFE_ID],
    dispatch_intent_id: Annotated[str, SAFE_ID],
    outbox_entry_id: Annotated[str, SAFE_ID],
    publication_lease_id: Annotated[str, SAFE_ID],
    payload: HeartbeatWorkflowOutboxPublicationLeaseInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(workflow_outbox_publisher_subject)],
) -> WorkflowOutboxPublicationLeaseResponse:
    service: WorkflowOutboxPublicationLeaseService = (
        request.app.state.workflow_outbox_publication_lease_service
    )
    await _require_bound_publication_outbox(
        repository=service.repository,
        plan_id=plan_id,
        run_id=run_id,
        attempt_id=attempt_id,
        dispatch_intent_id=dispatch_intent_id,
        outbox_entry_id=outbox_entry_id,
    )
    try:
        lease = await service.heartbeat(
            outbox_entry_id=outbox_entry_id,
            outbox_entry_digest=payload.outbox_entry_digest,
            publication_lease_id=publication_lease_id,
            publication_lease_digest=payload.publication_lease_digest,
            publication_fencing_token=payload.publication_fencing_token,
            lease_seconds=payload.lease_duration_seconds,
            context=await _publisher_context(request, subject, target_id=payload.target_id),
        )
    except WorkflowOutboxPublicationLeaseError as error:
        _raise_publication_lease(error)
    return _publication_lease_response(lease, request, response)


@router.post(
    (
        "/plans/{plan_id}/runs/{run_id}/attempts/{attempt_id}/dispatch-intents/"
        "{dispatch_intent_id}/outbox/{outbox_entry_id}/publication-lease/"
        "{publication_lease_id}/release"
    ),
    response_model=WorkflowOutboxPublicationLeaseResponse,
)
async def release_workflow_outbox_publication_lease(
    plan_id: Annotated[str, SAFE_ID],
    run_id: Annotated[str, SAFE_ID],
    attempt_id: Annotated[str, SAFE_ID],
    dispatch_intent_id: Annotated[str, SAFE_ID],
    outbox_entry_id: Annotated[str, SAFE_ID],
    publication_lease_id: Annotated[str, SAFE_ID],
    payload: ReleaseWorkflowOutboxPublicationLeaseInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(workflow_outbox_publisher_subject)],
) -> WorkflowOutboxPublicationLeaseResponse:
    service: WorkflowOutboxPublicationLeaseService = (
        request.app.state.workflow_outbox_publication_lease_service
    )
    await _require_bound_publication_outbox(
        repository=service.repository,
        plan_id=plan_id,
        run_id=run_id,
        attempt_id=attempt_id,
        dispatch_intent_id=dispatch_intent_id,
        outbox_entry_id=outbox_entry_id,
    )
    try:
        lease = await service.release(
            outbox_entry_id=outbox_entry_id,
            outbox_entry_digest=payload.outbox_entry_digest,
            publication_lease_id=publication_lease_id,
            publication_lease_digest=payload.publication_lease_digest,
            publication_fencing_token=payload.publication_fencing_token,
            context=await _publisher_context(request, subject, target_id=payload.target_id),
        )
    except WorkflowOutboxPublicationLeaseError as error:
        _raise_publication_lease(error)
    return _publication_lease_response(lease, request, response)


@router.get(
    (
        "/plans/{plan_id}/runs/{run_id}/attempts/{attempt_id}/dispatch-intents/"
        "{dispatch_intent_id}/outbox/{outbox_entry_id}/event-envelope"
    ),
    response_model=WorkflowDispatchEventEnvelopeInventoryResponse,
)
async def get_workflow_dispatch_event_envelope(
    plan_id: Annotated[str, SAFE_ID],
    run_id: Annotated[str, SAFE_ID],
    attempt_id: Annotated[str, SAFE_ID],
    dispatch_intent_id: Annotated[str, SAFE_ID],
    outbox_entry_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_workflow_plan_read)],
) -> WorkflowDispatchEventEnvelopeInventoryResponse:
    planning_service: WorkflowPlanningService = request.app.state.workflow_planning_service
    try:
        plan = await planning_service.get_plan(
            plan_id=plan_id,
            context=await _context(request, subject, decision),
        )
    except WorkflowPlanningError as error:
        _raise(error)
    repository: WorkflowDispatchEventEnvelopeRepository = (
        request.app.state.workflow_dispatch_event_envelope_repository
    )
    try:
        entry = await repository.get_outbox_entry_by_id(outbox_entry_id=outbox_entry_id)
        envelope = await repository.get_dispatch_event_envelope_by_outbox_entry_id(
            outbox_entry_id=outbox_entry_id
        )
        publication_lease = (
            None
            if envelope is None
            else await repository.get_publication_lease_by_outbox_entry_id(
                outbox_entry_id=outbox_entry_id
            )
        )
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_dispatch_event_envelope_service_unavailable",
            title="Workflow dispatch event envelope service unavailable",
            detail="Workflow dispatch event envelope evidence is unavailable.",
            retryable=True,
        ) from error
    if (
        entry is None
        or not _outbox_entry_matches_route(
            entry,
            plan_id=plan_id,
            run_id=run_id,
            attempt_id=attempt_id,
            dispatch_intent_id=dispatch_intent_id,
            outbox_entry_id=outbox_entry_id,
        )
        or entry.plan_digest != plan.canonical_digest
        or entry.scope != plan.scope
        or entry.target_id != plan.target_id
        or entry.target_type != plan.target_type
    ):
        raise AtlasError(
            status=404,
            code="workflow_resource_unavailable",
            title="Workflow resource unavailable",
            detail="The requested workflow resource is unavailable.",
        )
    if envelope is not None and (
        not _dispatch_event_envelope_matches_outbox(envelope, entry)
        or publication_lease is None
        or envelope.publication_lease_id != publication_lease.publication_lease_id
        or envelope.publication_lease_digest != publication_lease.canonical_digest
        or envelope.publication_fencing_token != publication_lease.publication_fencing_token
        or envelope.publisher_subject_id != publication_lease.publisher_subject_id
    ):
        raise AtlasError(
            status=503,
            code="workflow_dispatch_event_envelope_service_unavailable",
            title="Workflow dispatch event envelope service unavailable",
            detail="Workflow dispatch event envelope evidence is unavailable.",
            retryable=True,
        )
    _no_store(response)
    return WorkflowDispatchEventEnvelopeInventoryResponse(
        data=WorkflowDispatchEventEnvelopeInventoryData(
            outbox_entry_id=entry.outbox_entry_id,
            event_envelopes=(
                []
                if envelope is None
                else [WorkflowDispatchEventEnvelopeData.from_domain(envelope)]
            ),
            durable=repository.durable,
        ),
        meta=_meta(request),
    )


@router.post(
    (
        "/plans/{plan_id}/runs/{run_id}/attempts/{attempt_id}/dispatch-intents/"
        "{dispatch_intent_id}/outbox/{outbox_entry_id}/publication-lease/"
        "{publication_lease_id}/event-envelope/preparation"
    ),
    response_model=WorkflowDispatchEventEnvelopeResponse,
    status_code=201,
)
async def prepare_workflow_dispatch_event_envelope(
    plan_id: Annotated[str, SAFE_ID],
    run_id: Annotated[str, SAFE_ID],
    attempt_id: Annotated[str, SAFE_ID],
    dispatch_intent_id: Annotated[str, SAFE_ID],
    outbox_entry_id: Annotated[str, SAFE_ID],
    publication_lease_id: Annotated[str, SAFE_ID],
    payload: PrepareWorkflowDispatchEventEnvelopeInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(workflow_outbox_publisher_subject)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> WorkflowDispatchEventEnvelopeResponse:
    service: WorkflowDispatchEventEnvelopeService = (
        request.app.state.workflow_dispatch_event_envelope_service
    )
    entry = await _require_bound_publication_outbox(
        repository=cast(WorkflowOutboxPublicationLeaseRepository, service.repository),
        plan_id=plan_id,
        run_id=run_id,
        attempt_id=attempt_id,
        dispatch_intent_id=dispatch_intent_id,
        outbox_entry_id=outbox_entry_id,
    )
    try:
        envelope = await service.prepare(
            outbox_entry_id=outbox_entry_id,
            outbox_entry_digest=payload.outbox_entry_digest,
            publication_lease_id=publication_lease_id,
            publication_lease_digest=payload.publication_lease_digest,
            publication_fencing_token=payload.publication_fencing_token,
            idempotency_key=idempotency_key,
            context=await _publisher_context(request, subject, target_id=entry.target_id),
        )
    except WorkflowDispatchEventEnvelopeError as error:
        _raise_dispatch_event_envelope(error)
    return _dispatch_event_envelope_response(envelope, request, response)


@router.get(
    (
        "/plans/{plan_id}/runs/{run_id}/attempts/{attempt_id}/dispatch-intents/"
        "{dispatch_intent_id}/outbox/{outbox_entry_id}/event-envelope/{event_id}/"
        "transport-admission"
    ),
    response_model=WorkflowEventTransportAdmissionInventoryResponse,
)
async def get_workflow_event_transport_admission(
    plan_id: Annotated[str, SAFE_ID],
    run_id: Annotated[str, SAFE_ID],
    attempt_id: Annotated[str, SAFE_ID],
    dispatch_intent_id: Annotated[str, SAFE_ID],
    outbox_entry_id: Annotated[str, SAFE_ID],
    event_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_workflow_plan_read)],
) -> WorkflowEventTransportAdmissionInventoryResponse:
    planning_service: WorkflowPlanningService = request.app.state.workflow_planning_service
    try:
        plan = await planning_service.get_plan(
            plan_id=plan_id,
            context=await _context(request, subject, decision),
        )
    except WorkflowPlanningError as error:
        _raise(error)
    service: WorkflowEventTransportAdmissionService = (
        request.app.state.workflow_event_transport_admission_service
    )
    repository = service.repository
    try:
        entry = await repository.get_outbox_entry_by_id(outbox_entry_id=outbox_entry_id)
        envelope = await repository.get_dispatch_event_envelope_by_outbox_entry_id(
            outbox_entry_id=outbox_entry_id
        )
        publication_lease = await repository.get_publication_lease_by_outbox_entry_id(
            outbox_entry_id=outbox_entry_id
        )
        admission = await repository.get_event_transport_admission_by_event_id(event_id=event_id)
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_event_transport_admission_service_unavailable",
            title="Workflow event transport admission service unavailable",
            detail="Workflow event transport admission evidence is unavailable.",
            retryable=True,
        ) from error
    if (
        entry is None
        or envelope is None
        or envelope.event_id != event_id
        or not _outbox_entry_matches_route(
            entry,
            plan_id=plan_id,
            run_id=run_id,
            attempt_id=attempt_id,
            dispatch_intent_id=dispatch_intent_id,
            outbox_entry_id=outbox_entry_id,
        )
        or entry.plan_digest != plan.canonical_digest
        or entry.scope != plan.scope
        or entry.target_id != plan.target_id
        or entry.target_type != plan.target_type
    ):
        raise AtlasError(
            status=404,
            code="workflow_resource_unavailable",
            title="Workflow resource unavailable",
            detail="The requested workflow resource is unavailable.",
        )
    if (
        publication_lease is None
        or not _dispatch_event_envelope_matches_outbox(envelope, entry)
        or envelope.publication_lease_id != publication_lease.publication_lease_id
        or envelope.publication_lease_digest != publication_lease.canonical_digest
        or envelope.publication_fencing_token != publication_lease.publication_fencing_token
        or envelope.publisher_subject_id != publication_lease.publisher_subject_id
        or (
            admission is not None
            and not _event_transport_admission_matches_envelope(
                admission,
                envelope,
                entry,
                publication_lease,
                service.policy,
            )
        )
    ):
        raise AtlasError(
            status=503,
            code="workflow_event_transport_admission_service_unavailable",
            title="Workflow event transport admission service unavailable",
            detail="Workflow event transport admission evidence is unavailable.",
            retryable=True,
        )
    _no_store(response)
    return WorkflowEventTransportAdmissionInventoryResponse(
        data=WorkflowEventTransportAdmissionInventoryData(
            event_id=envelope.event_id,
            transport_admissions=(
                []
                if admission is None
                else [WorkflowEventTransportAdmissionData.from_domain(admission)]
            ),
            durable=service.durable,
        ),
        meta=_meta(request),
    )


@router.get(
    (
        "/plans/{plan_id}/runs/{run_id}/attempts/{attempt_id}/dispatch-intents/"
        "{dispatch_intent_id}/outbox/{outbox_entry_id}/event-envelope/{event_id}/"
        "transport-admission/{transport_admission_id}/byte-artifact"
    ),
    response_model=WorkflowEventByteArtifactInventoryResponse,
)
async def get_workflow_event_byte_artifact(
    plan_id: Annotated[str, SAFE_ID],
    run_id: Annotated[str, SAFE_ID],
    attempt_id: Annotated[str, SAFE_ID],
    dispatch_intent_id: Annotated[str, SAFE_ID],
    outbox_entry_id: Annotated[str, SAFE_ID],
    event_id: Annotated[str, SAFE_ID],
    transport_admission_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_workflow_plan_read)],
) -> WorkflowEventByteArtifactInventoryResponse:
    planning_service: WorkflowPlanningService = request.app.state.workflow_planning_service
    try:
        plan = await planning_service.get_plan(
            plan_id=plan_id,
            context=await _context(request, subject, decision),
        )
    except WorkflowPlanningError as error:
        _raise(error)
    service: WorkflowEventByteArtifactService = (
        request.app.state.workflow_event_byte_artifact_service
    )
    repository = service.repository
    try:
        entry = await repository.get_outbox_entry_by_id(outbox_entry_id=outbox_entry_id)
        envelope = await repository.get_dispatch_event_envelope_by_outbox_entry_id(
            outbox_entry_id=outbox_entry_id
        )
        publication_lease = await repository.get_publication_lease_by_outbox_entry_id(
            outbox_entry_id=outbox_entry_id
        )
        admission = await repository.get_event_transport_admission_by_event_id(event_id=event_id)
        artifact = await repository.get_event_byte_artifact_by_admission_id(
            admission_id=transport_admission_id
        )
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_event_byte_artifact_service_unavailable",
            title="Workflow event byte artifact service unavailable",
            detail="Workflow event byte artifact metadata is unavailable.",
            retryable=True,
        ) from error
    if (
        entry is None
        or envelope is None
        or admission is None
        or envelope.event_id != event_id
        or admission.admission_id != transport_admission_id
        or not _outbox_entry_matches_route(
            entry,
            plan_id=plan_id,
            run_id=run_id,
            attempt_id=attempt_id,
            dispatch_intent_id=dispatch_intent_id,
            outbox_entry_id=outbox_entry_id,
        )
        or entry.plan_digest != plan.canonical_digest
        or entry.scope != plan.scope
        or entry.target_id != plan.target_id
        or entry.target_type != plan.target_type
    ):
        raise AtlasError(
            status=404,
            code="workflow_resource_unavailable",
            title="Workflow resource unavailable",
            detail="The requested workflow resource is unavailable.",
        )
    if (
        publication_lease is None
        or not _dispatch_event_envelope_matches_outbox(envelope, entry)
        or not _event_transport_admission_matches_envelope(
            admission,
            envelope,
            entry,
            publication_lease,
            request.app.state.workflow_event_transport_admission_service.policy,
        )
        or (
            artifact is not None
            and not _event_byte_artifact_matches_admission(
                artifact,
                admission,
                envelope,
                entry,
                publication_lease,
            )
        )
    ):
        raise AtlasError(
            status=503,
            code="workflow_event_byte_artifact_service_unavailable",
            title="Workflow event byte artifact service unavailable",
            detail="Workflow event byte artifact metadata is unavailable.",
            retryable=True,
        )
    _no_store(response)
    return WorkflowEventByteArtifactInventoryResponse(
        data=WorkflowEventByteArtifactInventoryData(
            transport_admission_id=admission.admission_id,
            byte_artifacts=(
                [] if artifact is None else [WorkflowEventByteArtifactData.from_domain(artifact)]
            ),
            durable=service.durable,
        ),
        meta=_meta(request),
    )


@router.post(
    (
        "/plans/{plan_id}/runs/{run_id}/attempts/{attempt_id}/dispatch-intents/"
        "{dispatch_intent_id}/outbox/{outbox_entry_id}/publication-lease/"
        "{publication_lease_id}/event-envelope/{event_id}/transport-admission/"
        "{transport_admission_id}/byte-artifact"
    ),
    response_model=WorkflowEventByteArtifactResponse,
    status_code=201,
)
async def materialize_workflow_event_byte_artifact(
    plan_id: Annotated[str, SAFE_ID],
    run_id: Annotated[str, SAFE_ID],
    attempt_id: Annotated[str, SAFE_ID],
    dispatch_intent_id: Annotated[str, SAFE_ID],
    outbox_entry_id: Annotated[str, SAFE_ID],
    publication_lease_id: Annotated[str, SAFE_ID],
    event_id: Annotated[str, SAFE_ID],
    transport_admission_id: Annotated[str, SAFE_ID],
    payload: MaterializeWorkflowEventByteArtifactInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(workflow_outbox_publisher_subject)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> WorkflowEventByteArtifactResponse:
    service: WorkflowEventByteArtifactService = (
        request.app.state.workflow_event_byte_artifact_service
    )
    entry = await _require_bound_publication_outbox(
        repository=cast(WorkflowOutboxPublicationLeaseRepository, service.repository),
        plan_id=plan_id,
        run_id=run_id,
        attempt_id=attempt_id,
        dispatch_intent_id=dispatch_intent_id,
        outbox_entry_id=outbox_entry_id,
    )
    try:
        envelope = await service.repository.get_dispatch_event_envelope_by_outbox_entry_id(
            outbox_entry_id=outbox_entry_id
        )
        admission = await service.repository.get_event_transport_admission_by_event_id(
            event_id=event_id
        )
        publication_lease = await service.repository.get_publication_lease_by_outbox_entry_id(
            outbox_entry_id=outbox_entry_id
        )
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_event_byte_artifact_service_unavailable",
            title="Workflow event byte artifact service unavailable",
            detail="Workflow event byte artifact evidence is unavailable.",
            retryable=True,
        ) from error
    if (
        envelope is None
        or admission is None
        or envelope.event_id != event_id
        or admission.admission_id != transport_admission_id
    ):
        raise AtlasError(
            status=404,
            code="workflow_resource_unavailable",
            title="Workflow resource unavailable",
            detail="The requested workflow resource is unavailable.",
        )
    if (
        publication_lease is None
        or publication_lease.publication_lease_id != publication_lease_id
        or not _dispatch_event_envelope_matches_outbox(envelope, entry)
        or not _event_transport_admission_matches_envelope(
            admission,
            envelope,
            entry,
            publication_lease,
            request.app.state.workflow_event_transport_admission_service.policy,
        )
    ):
        raise AtlasError(
            status=503,
            code="workflow_event_byte_artifact_service_unavailable",
            title="Workflow event byte artifact service unavailable",
            detail="Workflow event byte artifact evidence is unavailable.",
            retryable=True,
        )
    try:
        artifact = await service.materialize(
            outbox_entry_id=outbox_entry_id,
            outbox_entry_digest=payload.outbox_entry_digest,
            event_id=event_id,
            event_digest=payload.event_digest,
            admission_id=transport_admission_id,
            admission_digest=payload.transport_admission_digest,
            policy_id=payload.policy_id,
            policy_version=payload.policy_version,
            policy_digest=payload.policy_digest,
            publication_lease_id=publication_lease_id,
            publication_lease_digest=payload.publication_lease_digest,
            publication_fencing_token=payload.publication_fencing_token,
            idempotency_key=idempotency_key,
            context=await _publisher_context(request, subject, target_id=entry.target_id),
        )
    except WorkflowEventByteArtifactError as error:
        _raise_event_byte_artifact(error)
    return _event_byte_artifact_response(artifact, request, response)


@router.get(
    (
        "/plans/{plan_id}/runs/{run_id}/attempts/{attempt_id}/dispatch-intents/"
        "{dispatch_intent_id}/outbox/{outbox_entry_id}/event-envelope/{event_id}/"
        "transport-admission/{transport_admission_id}/byte-artifact/{byte_artifact_id}/"
        "logical-channel-binding"
    ),
    response_model=WorkflowEventLogicalChannelBindingInventoryResponse,
)
async def get_workflow_event_logical_channel_binding(
    plan_id: Annotated[str, SAFE_ID],
    run_id: Annotated[str, SAFE_ID],
    attempt_id: Annotated[str, SAFE_ID],
    dispatch_intent_id: Annotated[str, SAFE_ID],
    outbox_entry_id: Annotated[str, SAFE_ID],
    event_id: Annotated[str, SAFE_ID],
    transport_admission_id: Annotated[str, SAFE_ID],
    byte_artifact_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_workflow_plan_read)],
) -> WorkflowEventLogicalChannelBindingInventoryResponse:
    planning_service: WorkflowPlanningService = request.app.state.workflow_planning_service
    try:
        plan = await planning_service.get_plan(
            plan_id=plan_id,
            context=await _context(request, subject, decision),
        )
    except WorkflowPlanningError as error:
        _raise(error)
    service: WorkflowEventLogicalChannelBindingService = (
        request.app.state.workflow_event_logical_channel_binding_service
    )
    repository = service.repository
    byte_artifact_repository = request.app.state.workflow_event_byte_artifact_service.repository
    try:
        entry = await repository.get_outbox_entry_by_id(outbox_entry_id=outbox_entry_id)
        envelope = await byte_artifact_repository.get_dispatch_event_envelope_by_outbox_entry_id(
            outbox_entry_id=outbox_entry_id
        )
        publication_lease = await repository.get_publication_lease_by_outbox_entry_id(
            outbox_entry_id=outbox_entry_id
        )
        admission = await repository.get_event_transport_admission_by_event_id(event_id=event_id)
        artifact = await repository.get_event_byte_artifact_by_id(artifact_id=byte_artifact_id)
        binding = await repository.get_event_logical_channel_binding_by_artifact_id(
            artifact_id=byte_artifact_id
        )
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_event_logical_channel_binding_service_unavailable",
            title="Workflow event logical channel binding service unavailable",
            detail="Workflow event logical channel binding metadata is unavailable.",
            retryable=True,
        ) from error
    if (
        entry is None
        or envelope is None
        or admission is None
        or artifact is None
        or envelope.event_id != event_id
        or admission.admission_id != transport_admission_id
        or artifact.artifact_id != byte_artifact_id
        or not _outbox_entry_matches_route(
            entry,
            plan_id=plan_id,
            run_id=run_id,
            attempt_id=attempt_id,
            dispatch_intent_id=dispatch_intent_id,
            outbox_entry_id=outbox_entry_id,
        )
        or entry.plan_digest != plan.canonical_digest
        or entry.scope != plan.scope
        or entry.target_id != plan.target_id
        or entry.target_type != plan.target_type
    ):
        raise AtlasError(
            status=404,
            code="workflow_resource_unavailable",
            title="Workflow resource unavailable",
            detail="The requested workflow resource is unavailable.",
        )
    if (
        publication_lease is None
        or not _dispatch_event_envelope_matches_outbox(envelope, entry)
        or not _event_transport_admission_matches_envelope(
            admission,
            envelope,
            entry,
            publication_lease,
            request.app.state.workflow_event_transport_admission_service.policy,
        )
        or not _event_byte_artifact_matches_admission(
            artifact,
            admission,
            envelope,
            entry,
            publication_lease,
        )
        or (
            binding is not None
            and not _event_logical_channel_binding_matches_artifact(
                binding,
                artifact,
                service.policy,
            )
        )
    ):
        raise AtlasError(
            status=503,
            code="workflow_event_logical_channel_binding_service_unavailable",
            title="Workflow event logical channel binding service unavailable",
            detail="Workflow event logical channel binding metadata is unavailable.",
            retryable=True,
        )
    _no_store(response)
    return WorkflowEventLogicalChannelBindingInventoryResponse(
        data=WorkflowEventLogicalChannelBindingInventoryData(
            byte_artifact_id=artifact.artifact_id,
            logical_channel_bindings=(
                []
                if binding is None
                else [WorkflowEventLogicalChannelBindingData.from_domain(binding)]
            ),
            durable=service.durable,
        ),
        meta=_meta(request),
    )


@router.post(
    (
        "/plans/{plan_id}/runs/{run_id}/attempts/{attempt_id}/dispatch-intents/"
        "{dispatch_intent_id}/outbox/{outbox_entry_id}/publication-lease/"
        "{publication_lease_id}/event-envelope/{event_id}/transport-admission/"
        "{transport_admission_id}/byte-artifact/{byte_artifact_id}/"
        "logical-channel-binding"
    ),
    response_model=WorkflowEventLogicalChannelBindingResponse,
    status_code=201,
)
async def bind_workflow_event_logical_channel(
    plan_id: Annotated[str, SAFE_ID],
    run_id: Annotated[str, SAFE_ID],
    attempt_id: Annotated[str, SAFE_ID],
    dispatch_intent_id: Annotated[str, SAFE_ID],
    outbox_entry_id: Annotated[str, SAFE_ID],
    publication_lease_id: Annotated[str, SAFE_ID],
    event_id: Annotated[str, SAFE_ID],
    transport_admission_id: Annotated[str, SAFE_ID],
    byte_artifact_id: Annotated[str, SAFE_ID],
    payload: BindWorkflowEventLogicalChannelInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(workflow_outbox_publisher_subject)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> WorkflowEventLogicalChannelBindingResponse:
    service: WorkflowEventLogicalChannelBindingService = (
        request.app.state.workflow_event_logical_channel_binding_service
    )
    entry = await _require_bound_publication_outbox(
        repository=cast(WorkflowOutboxPublicationLeaseRepository, service.repository),
        plan_id=plan_id,
        run_id=run_id,
        attempt_id=attempt_id,
        dispatch_intent_id=dispatch_intent_id,
        outbox_entry_id=outbox_entry_id,
    )
    byte_artifact_repository = request.app.state.workflow_event_byte_artifact_service.repository
    try:
        envelope = await byte_artifact_repository.get_dispatch_event_envelope_by_outbox_entry_id(
            outbox_entry_id=outbox_entry_id
        )
        admission = await service.repository.get_event_transport_admission_by_event_id(
            event_id=event_id
        )
        artifact = await service.repository.get_event_byte_artifact_by_id(
            artifact_id=byte_artifact_id
        )
        publication_lease = await service.repository.get_publication_lease_by_outbox_entry_id(
            outbox_entry_id=outbox_entry_id
        )
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_event_logical_channel_binding_service_unavailable",
            title="Workflow event logical channel binding service unavailable",
            detail="Workflow event logical channel binding evidence is unavailable.",
            retryable=True,
        ) from error
    if (
        envelope is None
        or admission is None
        or artifact is None
        or envelope.event_id != event_id
        or admission.admission_id != transport_admission_id
        or artifact.artifact_id != byte_artifact_id
    ):
        raise AtlasError(
            status=404,
            code="workflow_resource_unavailable",
            title="Workflow resource unavailable",
            detail="The requested workflow resource is unavailable.",
        )
    if (
        publication_lease is None
        or publication_lease.publication_lease_id != publication_lease_id
        or not _dispatch_event_envelope_matches_outbox(envelope, entry)
        or not _event_transport_admission_matches_envelope(
            admission,
            envelope,
            entry,
            publication_lease,
            request.app.state.workflow_event_transport_admission_service.policy,
        )
        or not _event_byte_artifact_matches_admission(
            artifact,
            admission,
            envelope,
            entry,
            publication_lease,
        )
    ):
        raise AtlasError(
            status=503,
            code="workflow_event_logical_channel_binding_service_unavailable",
            title="Workflow event logical channel binding service unavailable",
            detail="Workflow event logical channel binding evidence is unavailable.",
            retryable=True,
        )
    try:
        binding = await service.bind(
            artifact_id=byte_artifact_id,
            artifact_digest=payload.byte_artifact_digest,
            content_sha256=payload.content_sha256,
            canonical_byte_count=artifact.canonical_byte_count,
            admission_id=transport_admission_id,
            admission_digest=artifact.admission_digest,
            event_id=event_id,
            event_digest=artifact.event_digest,
            outbox_entry_id=outbox_entry_id,
            outbox_entry_digest=artifact.outbox_entry_digest,
            policy_id=payload.policy_id,
            policy_version=payload.policy_version,
            policy_digest=payload.policy_digest,
            logical_channel_id=service.policy.logical_channel_id,
            logical_channel_version=service.policy.logical_channel_version,
            publication_lease_id=publication_lease_id,
            publication_lease_digest=payload.publication_lease_digest,
            publication_fencing_token=payload.publication_fencing_token,
            idempotency_key=idempotency_key,
            context=await _publisher_context(request, subject, target_id=entry.target_id),
        )
    except WorkflowEventLogicalChannelBindingError as error:
        _raise_event_logical_channel_binding(error)
    return _event_logical_channel_binding_response(binding, request, response)


@router.post(
    (
        "/plans/{plan_id}/runs/{run_id}/attempts/{attempt_id}/dispatch-intents/"
        "{dispatch_intent_id}/outbox/{outbox_entry_id}/publication-lease/"
        "{publication_lease_id}/event-envelope/{event_id}/transport-admission"
    ),
    response_model=WorkflowEventTransportAdmissionResponse,
    status_code=201,
)
async def admit_workflow_event_transport(
    plan_id: Annotated[str, SAFE_ID],
    run_id: Annotated[str, SAFE_ID],
    attempt_id: Annotated[str, SAFE_ID],
    dispatch_intent_id: Annotated[str, SAFE_ID],
    outbox_entry_id: Annotated[str, SAFE_ID],
    publication_lease_id: Annotated[str, SAFE_ID],
    event_id: Annotated[str, SAFE_ID],
    payload: AdmitWorkflowEventTransportInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(workflow_outbox_publisher_subject)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> WorkflowEventTransportAdmissionResponse:
    service: WorkflowEventTransportAdmissionService = (
        request.app.state.workflow_event_transport_admission_service
    )
    entry = await _require_bound_publication_outbox(
        repository=cast(WorkflowOutboxPublicationLeaseRepository, service.repository),
        plan_id=plan_id,
        run_id=run_id,
        attempt_id=attempt_id,
        dispatch_intent_id=dispatch_intent_id,
        outbox_entry_id=outbox_entry_id,
    )
    try:
        envelope = await service.repository.get_dispatch_event_envelope_by_outbox_entry_id(
            outbox_entry_id=outbox_entry_id
        )
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_event_transport_admission_service_unavailable",
            title="Workflow event transport admission service unavailable",
            detail="Workflow event transport admission evidence is unavailable.",
            retryable=True,
        ) from error
    if envelope is None or envelope.event_id != event_id:
        raise AtlasError(
            status=404,
            code="workflow_resource_unavailable",
            title="Workflow resource unavailable",
            detail="The requested workflow resource is unavailable.",
        )
    if not _dispatch_event_envelope_matches_outbox(envelope, entry):
        raise AtlasError(
            status=503,
            code="workflow_event_transport_admission_service_unavailable",
            title="Workflow event transport admission service unavailable",
            detail="Workflow event transport admission evidence is unavailable.",
            retryable=True,
        )
    try:
        admission = await service.admit(
            outbox_entry_id=outbox_entry_id,
            outbox_entry_digest=payload.outbox_entry_digest,
            event_id=event_id,
            event_digest=payload.event_digest,
            policy_id=payload.policy_id,
            policy_version=payload.policy_version,
            policy_digest=payload.policy_digest,
            publication_lease_id=publication_lease_id,
            publication_lease_digest=payload.publication_lease_digest,
            publication_fencing_token=payload.publication_fencing_token,
            idempotency_key=idempotency_key,
            context=await _publisher_context(request, subject, target_id=entry.target_id),
        )
    except WorkflowEventTransportAdmissionError as error:
        _raise_event_transport_admission(error)
    return _event_transport_admission_response(admission, request, response)


@router.post(
    "/plans/{plan_id}/runs/{run_id}/attempts/{attempt_id}/dispatch-intents",
    response_model=WorkflowDispatchIntentResponse,
    status_code=201,
)
async def stage_workflow_dispatch_intent(
    plan_id: Annotated[str, SAFE_ID],
    run_id: Annotated[str, SAFE_ID],
    attempt_id: Annotated[str, SAFE_ID],
    payload: StageWorkflowDispatchIntentInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(workflow_worker_subject)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> WorkflowDispatchIntentResponse:
    service: WorkflowDispatchIntentStagingService = (
        request.app.state.workflow_dispatch_intent_staging_service
    )
    try:
        intent = await service.stage(
            plan_id=plan_id,
            plan_digest=payload.plan_digest,
            run_id=run_id,
            run_digest=payload.run_digest,
            step_run_id=payload.step_run_id,
            step_run_digest=payload.step_run_digest,
            attempt_id=attempt_id,
            attempt_digest=payload.attempt_digest,
            lease_id=payload.lease_id,
            lease_digest=payload.lease_digest,
            fencing_token=payload.fencing_token,
            idempotency_key=idempotency_key,
            context=await _worker_context(request, subject, target_id=payload.target_id),
        )
    except WorkflowDispatchIntentStagingError as error:
        _raise_dispatch_intent(error)
    return _dispatch_intent_response(intent, request, response)


@router.post(
    "/plans/{plan_id}/orchestration-lease/acquisition",
    response_model=WorkflowOrchestrationLeaseResponse,
    status_code=201,
)
async def acquire_workflow_orchestration_lease(
    plan_id: Annotated[str, SAFE_ID],
    payload: AcquireWorkflowOrchestrationLeaseInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(workflow_worker_subject)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> WorkflowOrchestrationLeaseResponse:
    service: WorkflowOrchestrationLeaseService = (
        request.app.state.workflow_orchestration_lease_service
    )
    try:
        lease = await service.acquire(
            plan_id=plan_id,
            plan_digest=payload.plan_digest,
            lease_seconds=payload.lease_duration_seconds,
            idempotency_key=idempotency_key,
            context=await _worker_context(request, subject, target_id=payload.target_id),
        )
    except WorkflowOrchestrationLeaseError as error:
        _raise_lease(error)
    return _lease_response(lease, request, response)


@router.post(
    "/plans/{plan_id}/orchestration-lease/{lease_id}/heartbeat",
    response_model=WorkflowOrchestrationLeaseResponse,
)
async def heartbeat_workflow_orchestration_lease(
    plan_id: Annotated[str, SAFE_ID],
    lease_id: Annotated[str, SAFE_ID],
    payload: HeartbeatWorkflowOrchestrationLeaseInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(workflow_worker_subject)],
) -> WorkflowOrchestrationLeaseResponse:
    service: WorkflowOrchestrationLeaseService = (
        request.app.state.workflow_orchestration_lease_service
    )
    try:
        lease = await service.heartbeat(
            plan_id=plan_id,
            plan_digest=payload.plan_digest,
            lease_id=lease_id,
            lease_digest=payload.lease_digest,
            fencing_token=payload.fencing_token,
            lease_seconds=payload.lease_duration_seconds,
            context=await _worker_context(request, subject, target_id=payload.target_id),
        )
    except WorkflowOrchestrationLeaseError as error:
        _raise_lease(error)
    return _lease_response(lease, request, response)


@router.post(
    "/plans/{plan_id}/orchestration-lease/{lease_id}/release",
    response_model=WorkflowOrchestrationLeaseResponse,
)
async def release_workflow_orchestration_lease(
    plan_id: Annotated[str, SAFE_ID],
    lease_id: Annotated[str, SAFE_ID],
    payload: ReleaseWorkflowOrchestrationLeaseInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(workflow_worker_subject)],
) -> WorkflowOrchestrationLeaseResponse:
    service: WorkflowOrchestrationLeaseService = (
        request.app.state.workflow_orchestration_lease_service
    )
    try:
        lease = await service.release(
            plan_id=plan_id,
            plan_digest=payload.plan_digest,
            lease_id=lease_id,
            lease_digest=payload.lease_digest,
            fencing_token=payload.fencing_token,
            context=await _worker_context(request, subject, target_id=payload.target_id),
        )
    except WorkflowOrchestrationLeaseError as error:
        _raise_lease(error)
    return _lease_response(lease, request, response)


@router.get("/plans/{plan_id}", response_model=WorkflowRunPlanResponse)
async def get_workflow_plan(
    plan_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_workflow_plan_read)],
) -> WorkflowRunPlanResponse:
    service: WorkflowPlanningService = request.app.state.workflow_planning_service
    try:
        plan = await service.get_plan(
            plan_id=plan_id, context=await _context(request, subject, decision)
        )
    except WorkflowPlanningError as error:
        _raise(error)
    return _plan_response(plan, request, response)


@router.get(
    "/transport-profile-snapshots",
    response_model=EventPhysicalTransportProfileSnapshotInventoryResponse,
)
async def list_workflow_transport_profile_snapshots(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_workflow_transport_profile_read)],
) -> EventPhysicalTransportProfileSnapshotInventoryResponse:
    del decision
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service: WorkflowTransportProfileSnapshotService = (
        request.app.state.workflow_transport_profile_snapshot_service
    )
    sources: tuple[DeploymentEventTransportProfile, ...] = (
        request.app.state.workflow_transport_profile_source_profiles
    )
    snapshots: list[EventPhysicalTransportProfileSnapshot] = []
    try:
        for source in sources:
            if source.scope != scope:
                continue
            snapshot = await service.repository.get_transport_profile_snapshot(
                transport_profile_id=source.transport_profile_id,
                transport_profile_revision=source.transport_profile_revision,
            )
            if snapshot is not None:
                if not _transport_profile_snapshot_matches_source(snapshot, source):
                    raise WorkflowTransportProfileSnapshotError(
                        "workflow_transport_profile_snapshot_repository_scope_violation",
                        "Stored transport profile snapshot metadata does not match its source.",
                    )
                snapshots.append(snapshot)
    except WorkflowTransportProfileSnapshotError as error:
        _raise_transport_profile_snapshot(error)
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_transport_profile_snapshot_repository_unavailable",
            title="Workflow transport profile snapshot service unavailable",
            detail="Transport profile snapshot metadata is unavailable.",
            retryable=True,
        ) from error
    _no_store(response)
    return EventPhysicalTransportProfileSnapshotInventoryResponse(
        data=EventPhysicalTransportProfileSnapshotInventoryData(
            transport_profile_snapshots=[
                EventPhysicalTransportProfileSnapshotData.from_domain(snapshot)
                for snapshot in sorted(
                    snapshots,
                    key=lambda value: (
                        value.transport_profile_id,
                        value.transport_profile_revision,
                    ),
                )
            ],
            durable=service.durable,
        ),
        meta=_meta(request),
    )


@router.post(
    "/transport-profile-snapshots",
    response_model=EventPhysicalTransportProfileSnapshotResponse,
    status_code=201,
)
async def create_workflow_transport_profile_snapshot(
    payload: CreateEventPhysicalTransportProfileSnapshotInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(workflow_transport_profile_registry_subject)],
) -> EventPhysicalTransportProfileSnapshotResponse:
    service: WorkflowTransportProfileSnapshotService = (
        request.app.state.workflow_transport_profile_snapshot_service
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    try:
        snapshot = await service.register(
            transport_profile_id=payload.source_profile_id,
            transport_profile_revision=payload.source_profile_revision,
            source_profile_digest=payload.source_profile_digest,
            idempotency_key=payload.idempotency_key,
            context=WorkflowTransportProfileRegistryContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=WORKFLOW_TRANSPORT_PROFILE_REGISTRY_AUDIENCE,
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id="decision.workflow-transport-profile-registry-authenticated",
                requested_at=datetime.now(UTC),
            ),
        )
    except WorkflowTransportProfileSnapshotError as error:
        _raise_transport_profile_snapshot(error)
    return _transport_profile_snapshot_response(snapshot, request, response)


@router.get(
    "/transport-route-snapshots",
    response_model=EventPhysicalTransportRouteSnapshotInventoryResponse,
)
async def list_workflow_transport_route_snapshots(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_workflow_transport_route_snapshot_read),
    ],
) -> EventPhysicalTransportRouteSnapshotInventoryResponse:
    del decision
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service: WorkflowTransportRouteSnapshotService = (
        request.app.state.workflow_transport_route_snapshot_service
    )
    sources: tuple[DeploymentEventTransportRoute, ...] = (
        request.app.state.workflow_transport_route_source_routes
    )
    snapshots: list[EventPhysicalTransportRouteSnapshot] = []
    try:
        for source in sources:
            if source.scope != scope:
                continue
            snapshot = await service.repository.get_transport_route_snapshot(
                route_id=source.route_id,
                route_revision=source.route_revision,
            )
            if snapshot is not None:
                if not _transport_route_snapshot_matches_source(snapshot, source):
                    raise WorkflowTransportRouteSnapshotError(
                        "workflow_transport_route_snapshot_repository_scope_violation",
                        "Stored transport route snapshot metadata does not match its source.",
                    )
                snapshots.append(snapshot)
    except WorkflowTransportRouteSnapshotError as error:
        _raise_transport_route_snapshot(error)
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_transport_route_snapshot_repository_unavailable",
            title="Workflow transport route snapshot service unavailable",
            detail="Transport route snapshot metadata is unavailable.",
            retryable=True,
        ) from error
    _no_store(response)
    return EventPhysicalTransportRouteSnapshotInventoryResponse(
        data=EventPhysicalTransportRouteSnapshotInventoryData(
            transport_route_snapshots=[
                EventPhysicalTransportRouteSnapshotData.from_domain(snapshot)
                for snapshot in sorted(
                    snapshots,
                    key=lambda value: (value.route_id, value.route_revision),
                )
            ],
            durable=service.durable,
        ),
        meta=_meta(request),
    )


@router.post(
    "/transport-route-snapshots",
    response_model=EventPhysicalTransportRouteSnapshotResponse,
    status_code=201,
)
async def create_workflow_transport_route_snapshot(
    payload: CreateEventPhysicalTransportRouteSnapshotInput,
    request: Request,
    response: Response,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(workflow_transport_route_registry_subject),
    ],
) -> EventPhysicalTransportRouteSnapshotResponse:
    service: WorkflowTransportRouteSnapshotService = (
        request.app.state.workflow_transport_route_snapshot_service
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    try:
        snapshot = await service.register(
            route_id=payload.source_route_id,
            route_revision=payload.source_route_revision,
            source_route_digest=payload.source_route_digest,
            idempotency_key=payload.idempotency_key,
            context=WorkflowTransportRouteRegistryContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=WORKFLOW_TRANSPORT_ROUTE_REGISTRY_AUDIENCE,
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id="decision.workflow-transport-route-registry-authenticated",
                requested_at=datetime.now(UTC),
            ),
        )
    except WorkflowTransportRouteSnapshotError as error:
        _raise_transport_route_snapshot(error)
    return _transport_route_snapshot_response(snapshot, request, response)


@router.get(
    "/transport-credential-assignment-snapshots",
    response_model=EventPhysicalTransportCredentialAssignmentSnapshotInventoryResponse,
)
async def list_workflow_transport_credential_assignment_snapshots(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_workflow_transport_credential_assignment_snapshot_read),
    ],
) -> EventPhysicalTransportCredentialAssignmentSnapshotInventoryResponse:
    del decision
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service: WorkflowTransportCredentialAssignmentSnapshotService = (
        request.app.state.workflow_transport_credential_assignment_snapshot_service
    )
    try:
        snapshots = await service.repository.list_credential_assignment_snapshots(
            scope=scope,
            limit=256,
        )
        for snapshot in snapshots:
            validate_workflow_transport_credential_assignment_snapshot(snapshot, scope=scope)
    except WorkflowTransportCredentialAssignmentSnapshotError as error:
        _raise_transport_credential_assignment_snapshot(error)
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_transport_credential_assignment_snapshot_repository_unavailable",
            title="Workflow transport credential snapshot service unavailable",
            detail="Transport credential assignment snapshot metadata is unavailable.",
            retryable=True,
        ) from error
    _no_store(response)
    return EventPhysicalTransportCredentialAssignmentSnapshotInventoryResponse(
        data=EventPhysicalTransportCredentialAssignmentSnapshotInventoryData(
            transport_credential_assignment_snapshots=[
                EventPhysicalTransportCredentialAssignmentSnapshotData.from_domain(snapshot)
                for snapshot in snapshots
            ],
            durable=service.durable,
        ),
        meta=_meta(request),
    )


@router.post(
    "/transport-credential-assignment-snapshots",
    response_model=EventPhysicalTransportCredentialAssignmentSnapshotResponse,
    status_code=201,
)
async def create_workflow_transport_credential_assignment_snapshot(
    payload: CreateEventPhysicalTransportCredentialAssignmentSnapshotInput,
    request: Request,
    response: Response,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(workflow_transport_credential_assignment_registry_subject),
    ],
) -> EventPhysicalTransportCredentialAssignmentSnapshotResponse:
    service: WorkflowTransportCredentialAssignmentSnapshotService = (
        request.app.state.workflow_transport_credential_assignment_snapshot_service
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    try:
        snapshot = await service.register(
            assignment_id=payload.assignment_id,
            assignment_revision=payload.assignment_revision,
            source_assignment_digest=payload.source_assignment_digest,
            idempotency_key=payload.idempotency_key,
            context=WorkflowTransportCredentialAssignmentRegistryContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=(WORKFLOW_TRANSPORT_CREDENTIAL_ASSIGNMENT_REGISTRY_AUDIENCE),
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id=(
                    "decision.workflow-transport-credential-assignment-registry-authenticated"
                ),
                requested_at=datetime.now(UTC),
            ),
        )
    except WorkflowTransportCredentialAssignmentSnapshotError as error:
        _raise_transport_credential_assignment_snapshot(error)
    return _transport_credential_assignment_snapshot_response(snapshot, request, response)


@router.get(
    "/physical-transport-route-bindings",
    response_model=WorkflowEventPhysicalTransportRouteBindingInventoryResponse,
)
async def list_workflow_physical_transport_route_bindings(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_workflow_physical_transport_route_binding_read),
    ],
) -> WorkflowEventPhysicalTransportRouteBindingInventoryResponse:
    del decision
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service: WorkflowEventPhysicalTransportRouteBindingService = (
        request.app.state.workflow_event_physical_transport_route_binding_service
    )
    try:
        bindings = await service.repository.list_physical_transport_route_bindings(
            scope=scope,
            limit=256,
        )
        if any(binding.scope != scope for binding in bindings):
            raise WorkflowEventPhysicalTransportRouteBindingError(
                "workflow_physical_transport_route_binding_repository_scope_violation",
                "Stored physical transport route binding metadata escaped its query scope.",
            )
    except WorkflowEventPhysicalTransportRouteBindingError as error:
        _raise_physical_transport_route_binding(error)
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_physical_transport_route_binding_repository_unavailable",
            title="Workflow physical transport route binding service unavailable",
            detail="Physical transport route binding metadata is unavailable.",
            retryable=True,
        ) from error
    _no_store(response)
    return WorkflowEventPhysicalTransportRouteBindingInventoryResponse(
        data=WorkflowEventPhysicalTransportRouteBindingInventoryData(
            physical_transport_route_bindings=[
                WorkflowEventPhysicalTransportRouteBindingData.from_domain(binding)
                for binding in sorted(bindings, key=lambda value: value.binding_id)
            ],
            durable=service.durable,
        ),
        meta=_meta(request),
    )


@router.post(
    "/physical-transport-route-bindings",
    response_model=WorkflowEventPhysicalTransportRouteBindingResponse,
    status_code=201,
)
async def create_workflow_physical_transport_route_binding(
    payload: CreateWorkflowEventPhysicalTransportRouteBindingInput,
    request: Request,
    response: Response,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(workflow_physical_transport_route_binder_subject),
    ],
) -> WorkflowEventPhysicalTransportRouteBindingResponse:
    service: WorkflowEventPhysicalTransportRouteBindingService = (
        request.app.state.workflow_event_physical_transport_route_binding_service
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    try:
        binding = await service.bind(
            logical_channel_binding_id=payload.logical_channel_binding_id,
            logical_channel_binding_digest=payload.logical_channel_binding_digest,
            transport_compatibility_admission_id=payload.compatibility_admission_id,
            transport_compatibility_admission_digest=payload.compatibility_admission_digest,
            transport_profile_snapshot_id=payload.transport_profile_snapshot_id,
            transport_profile_snapshot_digest=payload.transport_profile_snapshot_digest,
            transport_route_snapshot_id=payload.transport_route_snapshot_id,
            transport_route_snapshot_digest=payload.transport_route_snapshot_digest,
            policy_id=payload.policy_id,
            policy_version=payload.policy_version,
            policy_digest=payload.policy_digest,
            idempotency_key=payload.idempotency_key,
            context=WorkflowPhysicalTransportRouteBinderContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_BINDER_AUDIENCE,
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id="decision.workflow-physical-transport-route-binder-authenticated",
                requested_at=datetime.now(UTC),
            ),
        )
    except WorkflowEventPhysicalTransportRouteBindingError as error:
        _raise_physical_transport_route_binding(error)
    return _physical_transport_route_binding_response(binding, request, response)


@router.get(
    "/physical-transport-credential-assignment-bindings",
    response_model=WorkflowEventPhysicalTransportCredentialAssignmentBindingInventoryResponse,
)
async def list_workflow_physical_transport_credential_assignment_bindings(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_workflow_physical_transport_credential_assignment_binding_read),
    ],
) -> WorkflowEventPhysicalTransportCredentialAssignmentBindingInventoryResponse:
    del decision
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service: WorkflowEventPhysicalTransportCredentialAssignmentBindingService = (
        request.app.state.workflow_event_physical_transport_credential_assignment_binding_service
    )
    try:
        bindings = await service.repository.list_credential_assignment_bindings(
            scope=scope,
            limit=256,
        )
        if any(binding.scope != scope for binding in bindings):
            raise WorkflowTransportCredentialAssignmentBindingError(
                "workflow_transport_credential_assignment_binding_repository_scope_violation",
                "Stored credential-assignment binding metadata escaped its query scope.",
            )
    except WorkflowTransportCredentialAssignmentBindingError as error:
        _raise_physical_transport_credential_assignment_binding(error)
    except Exception as error:
        raise AtlasError(
            status=503,
            code=("workflow_transport_credential_assignment_binding_repository_unavailable"),
            title="Workflow transport credential binding service unavailable",
            detail="Physical transport credential-assignment binding metadata is unavailable.",
            retryable=True,
        ) from error
    _no_store(response)
    return WorkflowEventPhysicalTransportCredentialAssignmentBindingInventoryResponse(
        data=WorkflowEventPhysicalTransportCredentialAssignmentBindingInventoryData(
            physical_transport_credential_assignment_bindings=[
                WorkflowEventPhysicalTransportCredentialAssignmentBindingData.from_domain(binding)
                for binding in sorted(bindings, key=lambda value: value.binding_id)
            ],
            durable=service.durable,
        ),
        meta=_meta(request),
    )


@router.post(
    "/physical-transport-credential-assignment-bindings",
    response_model=WorkflowEventPhysicalTransportCredentialAssignmentBindingResponse,
    status_code=201,
)
async def create_workflow_physical_transport_credential_assignment_binding(
    payload: CreateWorkflowEventPhysicalTransportCredentialAssignmentBindingInput,
    request: Request,
    response: Response,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(authorize_workflow_physical_transport_credential_assignment_binding_bind),
    ],
) -> WorkflowEventPhysicalTransportCredentialAssignmentBindingResponse:
    service: WorkflowEventPhysicalTransportCredentialAssignmentBindingService = (
        request.app.state.workflow_event_physical_transport_credential_assignment_binding_service
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    policy = service.policy
    try:
        binding = await service.bind(
            physical_transport_route_binding_id=(payload.physical_transport_route_binding_id),
            physical_transport_route_binding_digest=(
                payload.physical_transport_route_binding_digest
            ),
            credential_assignment_snapshot_id=payload.credential_assignment_snapshot_id,
            credential_assignment_snapshot_digest=(payload.credential_assignment_snapshot_digest),
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            policy_digest=policy.canonical_digest,
            idempotency_key=payload.idempotency_key,
            context=WorkflowPhysicalTransportCredentialBinderContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=(WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_BINDER_AUDIENCE),
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id=(
                    "decision.workflow-physical-transport-credential-assignment-binding-bind"
                ),
                requested_at=datetime.now(UTC),
            ),
        )
    except WorkflowTransportCredentialAssignmentBindingError as error:
        _raise_physical_transport_credential_assignment_binding(error)
    return _physical_transport_credential_assignment_binding_response(binding, request, response)


@router.get(
    "/physical-transport-credential-assignment-freshness-admissions",
    response_model=(
        WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionInventoryResponse
    ),
)
async def list_workflow_physical_transport_credential_assignment_freshness_admissions(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[
        AuthorizationDecision,
        Depends(
            authorize_workflow_physical_transport_credential_assignment_freshness_admission_read
        ),
    ],
) -> WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionInventoryResponse:
    del decision
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service = cast(
        WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionService,
        getattr(  # noqa: B009 - state key intentionally mirrors the public dependency name.
            request.app.state,
            "workflow_event_physical_transport_credential_assignment_freshness_admission_service",
        ),
    )
    try:
        admissions = await service.list_admissions(scope=scope, limit=256)
    except WorkflowTransportCredentialAssignmentFreshnessAdmissionError as error:
        _raise_physical_transport_credential_assignment_freshness_admission(error)
    except Exception as error:
        raise AtlasError(
            status=503,
            code=(
                "workflow_physical_transport_credential_assignment_freshness_repository_unavailable"
            ),
            title="Workflow credential-assignment freshness service unavailable",
            detail="Credential-assignment freshness admission metadata is unavailable.",
            retryable=True,
        ) from error
    _no_store(response)
    return WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionInventoryResponse(
        data=WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionInventoryData(
            physical_transport_credential_assignment_freshness_admissions=[
                WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionData.from_domain(
                    admission
                )
                for admission in sorted(
                    admissions,
                    key=lambda value: (
                        -value.evaluated_at.timestamp(),
                        value.freshness_admission_id,
                    ),
                )
            ],
            durable=service.durable,
        ),
        meta=_meta(request),
    )


@router.post(
    "/physical-transport-credential-assignment-freshness-admissions",
    response_model=WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionResponse,
    status_code=201,
)
async def create_workflow_physical_transport_credential_assignment_freshness_admission(
    payload: CreateWorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionInput,
    request: Request,
    response: Response,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(workflow_physical_transport_credential_assignment_freshness_admitter_subject),
    ],
) -> WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionResponse:
    service = cast(
        WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionService,
        getattr(  # noqa: B009 - state key intentionally mirrors the public dependency name.
            request.app.state,
            "workflow_event_physical_transport_credential_assignment_freshness_admission_service",
        ),
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    try:
        admission = await service.admit(
            physical_transport_credential_assignment_binding_id=(
                payload.physical_transport_credential_assignment_binding_id
            ),
            physical_transport_credential_assignment_binding_digest=(
                payload.physical_transport_credential_assignment_binding_digest
            ),
            policy_id=payload.policy_id,
            policy_version=payload.policy_version,
            idempotency_key=payload.idempotency_key,
            context=WorkflowPhysicalTransportCredentialAssignmentFreshnessAdmitterContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=(
                    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ASSIGNMENT_FRESHNESS_ADMITTER_AUDIENCE
                ),
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id=(
                    "decision.workflow-physical-transport-credential-assignment-freshness-"
                    "admitter-authenticated"
                ),
                requested_at=datetime.now(UTC),
            ),
        )
    except WorkflowTransportCredentialAssignmentFreshnessAdmissionError as error:
        _raise_physical_transport_credential_assignment_freshness_admission(error)
    return _physical_transport_credential_assignment_freshness_admission_response(
        admission,
        request,
        response,
    )


@router.get(
    "/physical-transport-credential-access-authorization-leases",
    response_model=(
        WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseInventoryResponse
    ),
)
async def list_workflow_physical_transport_credential_access_authorization_leases(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_workflow_physical_transport_credential_access_authorization_lease_read),
    ],
) -> WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseInventoryResponse:
    del decision
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service = cast(
        WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseService,
        request.app.state.workflow_credential_access_authorization_lease_service,
    )
    try:
        server_time = await service.repository.get_authoritative_time()
        leases = await service.list_leases(scope=scope, limit=256)
        if server_time.tzinfo is None or any(lease.scope != scope for lease in leases):
            raise WorkflowTransportCredentialAccessAuthorizationLeaseError(
                "workflow_physical_transport_credential_access_authorization_repository_"
                "scope_violation",
                "Stored credential-access authorization metadata is invalid.",
            )
    except WorkflowTransportCredentialAccessAuthorizationLeaseError as error:
        _raise_physical_transport_credential_access_authorization_lease(error)
    except Exception as error:
        raise AtlasError(
            status=503,
            code=(
                "workflow_physical_transport_credential_access_authorization_service_unavailable"
            ),
            title="Workflow credential-access authorization service unavailable",
            detail="Credential-access authorization metadata is temporarily unavailable.",
            retryable=True,
        ) from error
    _no_store(response)
    return WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseInventoryResponse(
        data=WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseInventoryData(
            physical_transport_credential_access_authorization_leases=[
                WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseData.from_domain(
                    lease,
                    evaluated_at=server_time,
                )
                for lease in sorted(
                    leases,
                    key=lambda value: value.authorization_lease_id,
                )
            ],
            server_time=server_time,
            durable=service.durable,
        ),
        meta=_meta(request),
    )


@router.post(
    "/physical-transport-credential-access-authorization-leases",
    response_model=WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseResponse,
    status_code=201,
)
async def create_workflow_physical_transport_credential_access_authorization_lease(
    payload: CreateWorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseInput,
    request: Request,
    response: Response,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(workflow_physical_transport_credential_accessor_subject),
    ],
) -> WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseResponse:
    service = cast(
        WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseService,
        request.app.state.workflow_credential_access_authorization_lease_service,
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    try:
        lease = await service.authorize(
            freshness_admission_id=payload.freshness_admission_id,
            freshness_admission_digest=payload.freshness_admission_digest,
            policy_id=payload.policy_id,
            policy_version=payload.policy_version,
            idempotency_key=payload.idempotency_key,
            context=WorkflowPhysicalTransportCredentialAccessorContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_AUDIENCE,
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id=(
                    "decision.workflow-physical-transport-credential-accessor-authenticated"
                ),
                requested_at=datetime.now(UTC),
            ),
        )
    except WorkflowTransportCredentialAccessAuthorizationLeaseError as error:
        _raise_physical_transport_credential_access_authorization_lease(error)
    return _physical_transport_credential_access_authorization_lease_response(
        lease,
        request,
        response,
    )


@router.get(
    "/physical-transport-route-freshness-admissions",
    response_model=WorkflowEventPhysicalTransportRouteFreshnessAdmissionInventoryResponse,
)
async def list_workflow_physical_transport_route_freshness_admissions(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_workflow_physical_transport_route_freshness_admission_read),
    ],
) -> WorkflowEventPhysicalTransportRouteFreshnessAdmissionInventoryResponse:
    del decision
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service: WorkflowEventPhysicalTransportRouteFreshnessAdmissionService = (
        request.app.state.workflow_event_physical_transport_route_freshness_admission_service
    )
    try:
        admissions = await service.repository.list_route_freshness_admissions(
            scope=scope,
            limit=256,
        )
        if any(admission.scope != scope for admission in admissions):
            raise WorkflowEventPhysicalTransportRouteFreshnessAdmissionError(
                "workflow_physical_transport_route_freshness_repository_scope_violation",
                "Stored route freshness admission metadata escaped its query scope.",
            )
    except WorkflowEventPhysicalTransportRouteFreshnessAdmissionError as error:
        _raise_physical_transport_route_freshness_admission(error)
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_physical_transport_route_freshness_repository_unavailable",
            title="Workflow physical route freshness service unavailable",
            detail="Physical route freshness admission metadata is unavailable.",
            retryable=True,
        ) from error
    _no_store(response)
    return WorkflowEventPhysicalTransportRouteFreshnessAdmissionInventoryResponse(
        data=WorkflowEventPhysicalTransportRouteFreshnessAdmissionInventoryData(
            physical_transport_route_freshness_admissions=[
                WorkflowEventPhysicalTransportRouteFreshnessAdmissionData.from_domain(admission)
                for admission in sorted(
                    admissions,
                    key=lambda value: value.freshness_admission_id,
                )
            ],
            durable=service.durable,
        ),
        meta=_meta(request),
    )


@router.post(
    "/physical-transport-route-freshness-admissions",
    response_model=WorkflowEventPhysicalTransportRouteFreshnessAdmissionResponse,
    status_code=201,
)
async def create_workflow_physical_transport_route_freshness_admission(
    payload: CreateWorkflowEventPhysicalTransportRouteFreshnessAdmissionInput,
    request: Request,
    response: Response,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(workflow_physical_transport_route_freshness_admitter_subject),
    ],
) -> WorkflowEventPhysicalTransportRouteFreshnessAdmissionResponse:
    service: WorkflowEventPhysicalTransportRouteFreshnessAdmissionService = (
        request.app.state.workflow_event_physical_transport_route_freshness_admission_service
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    try:
        admission = await service.admit(
            physical_transport_route_binding_id=(payload.physical_transport_route_binding_id),
            physical_transport_route_binding_digest=(
                payload.physical_transport_route_binding_digest
            ),
            policy_id=payload.policy_id,
            policy_version=payload.policy_version,
            idempotency_key=payload.idempotency_key,
            context=WorkflowPhysicalTransportRouteFreshnessAdmitterContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=(WORKFLOW_PHYSICAL_TRANSPORT_ROUTE_FRESHNESS_ADMITTER_AUDIENCE),
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id=(
                    "decision.workflow-physical-transport-route-freshness-admitter-authenticated"
                ),
                requested_at=datetime.now(UTC),
            ),
        )
    except WorkflowEventPhysicalTransportRouteFreshnessAdmissionError as error:
        _raise_physical_transport_route_freshness_admission(error)
    return _physical_transport_route_freshness_admission_response(
        admission,
        request,
        response,
    )


@router.get(
    "/physical-transport-endpoint-resolution-authorization-leases",
    response_model=(
        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseInventoryResponse
    ),
)
async def list_workflow_physical_transport_endpoint_resolution_authorization_leases(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_workflow_physical_transport_endpoint_resolution_authorization_lease_read),
    ],
) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseInventoryResponse:
    del decision
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseService = (
        request.app.state.workflow_endpoint_resolution_authorization_lease_service
    )
    try:
        leases = await service.repository.list_endpoint_resolution_authorization_leases(
            scope=scope,
            limit=256,
        )
        if any(lease.scope != scope for lease in leases):
            raise WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError(
                "workflow_physical_transport_endpoint_resolution_authorization_repository_"
                "scope_violation",
                "Stored endpoint-resolution authorization lease metadata escaped its query scope.",
            )
    except WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError as error:
        _raise_physical_transport_endpoint_resolution_authorization_lease(error)
    except Exception as error:
        raise AtlasError(
            status=503,
            code=(
                "workflow_physical_transport_endpoint_resolution_authorization_repository_"
                "unavailable"
            ),
            title="Workflow endpoint-resolution authorization service unavailable",
            detail="Endpoint-resolution authorization lease metadata is unavailable.",
            retryable=True,
        ) from error
    server_time = datetime.now(UTC)
    materialization_service: WorkflowEventPhysicalTransportEndpointMaterializationService = (
        request.app.state.workflow_endpoint_materialization_service
    )
    materialization_repository = materialization_service.repository
    consumed_lease_ids: set[str] = set()
    try:
        for lease in leases:
            claim = await materialization_repository.get_endpoint_materialization_claim_by_lease(
                authorization_lease_id=lease.authorization_lease_id,
            )
            if claim is not None:
                consumed_lease_ids.add(lease.authorization_lease_id)
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_endpoint_materialization_inventory_unavailable",
            title="Workflow endpoint materialization service unavailable",
            detail="Endpoint materialization consumption metadata is unavailable.",
            retryable=True,
        ) from error
    _no_store(response)
    return WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseInventoryResponse(
        data=WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseInventoryData(
            endpoint_resolution_authorization_leases=[
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseData.from_domain(
                    lease,
                    evaluated_at=server_time,
                    consumed=lease.authorization_lease_id in consumed_lease_ids,
                )
                for lease in sorted(
                    leases,
                    key=lambda value: value.authorization_lease_id,
                )
            ],
            server_time=server_time,
            durable=service.durable,
        ),
        meta=_meta(request),
    )


@router.post(
    "/physical-transport-endpoint-resolution-authorization-leases",
    response_model=WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResponse,
    status_code=201,
)
async def create_workflow_physical_transport_endpoint_resolution_authorization_lease(
    payload: CreateWorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseInput,
    request: Request,
    response: Response,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(workflow_physical_transport_endpoint_resolver_subject),
    ],
) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResponse:
    service: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseService = (
        request.app.state.workflow_endpoint_resolution_authorization_lease_service
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    try:
        lease = await service.authorize(
            freshness_admission_id=payload.freshness_admission_id,
            freshness_admission_digest=payload.freshness_admission_digest,
            policy_id=payload.policy_id,
            policy_version=payload.policy_version,
            idempotency_key=payload.idempotency_key,
            context=WorkflowPhysicalTransportEndpointResolverContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLVER_AUDIENCE,
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id=(
                    "decision.workflow-physical-transport-endpoint-resolver-authenticated"
                ),
                requested_at=datetime.now(UTC),
            ),
        )
    except WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseError as error:
        _raise_physical_transport_endpoint_resolution_authorization_lease(error)
    return _physical_transport_endpoint_resolution_authorization_lease_response(
        lease,
        request,
        response,
    )


@router.get(
    "/physical-transport-endpoint-materializations",
    response_model=WorkflowEventPhysicalTransportEndpointMaterializationInventoryResponse,
)
async def list_workflow_physical_transport_endpoint_materializations(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_workflow_physical_transport_endpoint_materialization_read),
    ],
) -> WorkflowEventPhysicalTransportEndpointMaterializationInventoryResponse:
    del decision
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service: WorkflowEventPhysicalTransportEndpointMaterializationService = (
        request.app.state.workflow_endpoint_materialization_service
    )
    try:
        attempts = await service.repository.list_endpoint_materialization_attempts(
            scope=scope,
            limit=256,
        )
        presentations: list[WorkflowEventPhysicalTransportEndpointMaterializationData] = []
        for attempt in attempts:
            if attempt.scope != scope:
                raise WorkflowEventPhysicalTransportEndpointMaterializationError(
                    "endpoint_materialization_repository_scope_violation"
                )
            claim = await service.repository.get_endpoint_materialization_claim_by_lease(
                authorization_lease_id=attempt.authorization_lease_id
            )
            result = await service.repository.get_endpoint_materialization_result_by_lease(
                authorization_lease_id=attempt.authorization_lease_id
            )
            if (
                claim is None
                or claim.scope != scope
                or (result is not None and result.scope != scope)
            ):
                raise WorkflowEventPhysicalTransportEndpointMaterializationError(
                    "endpoint_materialization_repository_scope_violation"
                )
            presentations.append(
                WorkflowEventPhysicalTransportEndpointMaterializationData.from_domain(
                    claim=claim,
                    attempt=attempt,
                    result=result,
                )
            )
    except WorkflowEventPhysicalTransportEndpointMaterializationError as error:
        _raise_physical_transport_endpoint_materialization(error)
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_endpoint_materialization_repository_unavailable",
            title="Workflow endpoint materialization service unavailable",
            detail="Endpoint materialization metadata is unavailable.",
            retryable=True,
        ) from error
    _no_store(response)
    return WorkflowEventPhysicalTransportEndpointMaterializationInventoryResponse(
        data=WorkflowEventPhysicalTransportEndpointMaterializationInventoryData(
            physical_transport_endpoint_materializations=sorted(
                presentations,
                key=lambda value: value.materialization_id,
            ),
            server_time=datetime.now(UTC),
            durable=service.durable,
        ),
        meta=_meta(request),
    )


@router.post(
    "/physical-transport-endpoint-materializations",
    response_model=WorkflowEventPhysicalTransportEndpointMaterializationResponse,
    status_code=201,
)
async def create_workflow_physical_transport_endpoint_materialization(
    payload: CreateWorkflowEventPhysicalTransportEndpointMaterializationInput,
    request: Request,
    response: Response,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(workflow_physical_transport_endpoint_resolver_subject),
    ],
) -> WorkflowEventPhysicalTransportEndpointMaterializationResponse:
    service: WorkflowEventPhysicalTransportEndpointMaterializationService = (
        request.app.state.workflow_endpoint_materialization_service
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    try:
        result = await service.materialize(
            authorization_lease_id=payload.authorization_lease_id,
            authorization_lease_digest=payload.authorization_lease_digest,
            materialization_policy_id=payload.policy_id,
            materialization_policy_version=payload.policy_version,
            irreversible_consumption_acknowledged=(payload.irreversible_consumption_acknowledged),
            uncertain_outcome_requires_new_authorization_acknowledged=(
                payload.uncertain_outcome_requires_new_authorization_acknowledged
            ),
            idempotency_key=payload.idempotency_key,
            context=WorkflowPhysicalTransportEndpointResolverContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=WORKFLOW_PHYSICAL_TRANSPORT_ENDPOINT_RESOLVER_AUDIENCE,
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id=(
                    "decision.workflow-physical-transport-endpoint-resolver-authenticated"
                ),
                requested_at=datetime.now(UTC),
            ),
        )
        claim = await service.repository.get_endpoint_materialization_claim_by_lease(
            authorization_lease_id=result.authorization_lease_id
        )
        attempt = await service.repository.get_endpoint_materialization_attempt_by_lease(
            authorization_lease_id=result.authorization_lease_id
        )
        if claim is None or attempt is None:
            raise WorkflowEventPhysicalTransportEndpointMaterializationUncertainError(
                "endpoint_materialization_outcome_uncertain"
            )
    except WorkflowEventPhysicalTransportEndpointMaterializationError as error:
        _raise_physical_transport_endpoint_materialization(error)
    _no_store(response)
    return WorkflowEventPhysicalTransportEndpointMaterializationResponse(
        data=WorkflowEventPhysicalTransportEndpointMaterializationData.from_domain(
            claim=claim,
            attempt=attempt,
            result=result,
        ),
        meta=_meta(request),
    )


@router.get(
    "/physical-transport-credential-materializations",
    response_model=WorkflowEventPhysicalTransportCredentialMaterializationInventoryResponse,
)
async def list_workflow_physical_transport_credential_materializations(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_workflow_physical_transport_credential_materialization_read),
    ],
) -> WorkflowEventPhysicalTransportCredentialMaterializationInventoryResponse:
    del decision
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service: WorkflowEventPhysicalTransportCredentialMaterializationService = (
        request.app.state.workflow_credential_materialization_service
    )
    try:
        attempts = await service.repository.list_credential_materialization_attempts(
            scope=scope,
            limit=256,
        )
        presentations: list[WorkflowEventPhysicalTransportCredentialMaterializationData] = []
        for attempt in attempts:
            if attempt.scope != scope:
                raise WorkflowEventPhysicalTransportCredentialMaterializationError(
                    "credential_materialization_repository_scope_violation"
                )
            claim = await service.repository.get_credential_materialization_claim_by_lease(
                authorization_lease_id=attempt.authorization_lease_id
            )
            result = await service.repository.get_credential_materialization_result_by_lease(
                authorization_lease_id=attempt.authorization_lease_id
            )
            if (
                claim is None
                or claim.scope != scope
                or (result is not None and result.scope != scope)
            ):
                raise WorkflowEventPhysicalTransportCredentialMaterializationError(
                    "credential_materialization_repository_scope_violation"
                )
            presentations.append(
                WorkflowEventPhysicalTransportCredentialMaterializationData.from_domain(
                    claim=claim,
                    attempt=attempt,
                    result=result,
                )
            )
    except WorkflowEventPhysicalTransportCredentialMaterializationError as error:
        _raise_physical_transport_credential_materialization(error)
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_credential_materialization_repository_unavailable",
            title="Workflow credential materialization service unavailable",
            detail="Credential materialization metadata is unavailable.",
            retryable=True,
        ) from error
    _no_store(response)
    return WorkflowEventPhysicalTransportCredentialMaterializationInventoryResponse(
        data=WorkflowEventPhysicalTransportCredentialMaterializationInventoryData(
            physical_transport_credential_materializations=sorted(
                presentations,
                key=lambda value: value.materialization_id,
            ),
            server_time=datetime.now(UTC),
            durable=service.durable,
        ),
        meta=_meta(request),
    )


@router.post(
    "/physical-transport-credential-materializations",
    response_model=WorkflowEventPhysicalTransportCredentialMaterializationResponse,
    status_code=201,
)
async def create_workflow_physical_transport_credential_materialization(
    payload: CreateWorkflowEventPhysicalTransportCredentialMaterializationInput,
    request: Request,
    response: Response,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(workflow_physical_transport_credential_accessor_subject),
    ],
) -> WorkflowEventPhysicalTransportCredentialMaterializationResponse:
    service: WorkflowEventPhysicalTransportCredentialMaterializationService = (
        request.app.state.workflow_credential_materialization_service
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    try:
        result = await service.materialize(
            authorization_lease_id=payload.authorization_lease_id,
            authorization_lease_digest=payload.authorization_lease_digest,
            materialization_policy_id=payload.policy_id,
            materialization_policy_version=payload.policy_version,
            irreversible_consumption_acknowledged=(payload.irreversible_consumption_acknowledged),
            uncertain_outcome_requires_new_authorization_acknowledged=(
                payload.uncertain_outcome_requires_new_authorization_acknowledged
            ),
            idempotency_key=payload.idempotency_key,
            context=WorkflowPhysicalTransportCredentialAccessorContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_AUDIENCE,
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id="decision.workflow-physical-transport-credential-accessor-authenticated",
                requested_at=datetime.now(UTC),
            ),
        )
        claim = await service.repository.get_credential_materialization_claim_by_lease(
            authorization_lease_id=result.authorization_lease_id
        )
        attempt = await service.repository.get_credential_materialization_attempt_by_lease(
            authorization_lease_id=result.authorization_lease_id
        )
        if claim is None or attempt is None:
            raise WorkflowEventPhysicalTransportCredentialMaterializationUncertainError(
                "credential_materialization_outcome_uncertain"
            )
    except WorkflowEventPhysicalTransportCredentialMaterializationError as error:
        _raise_physical_transport_credential_materialization(error)
    _no_store(response)
    return WorkflowEventPhysicalTransportCredentialMaterializationResponse(
        data=WorkflowEventPhysicalTransportCredentialMaterializationData.from_domain(
            claim=claim,
            attempt=attempt,
            result=result,
        ),
        meta=_meta(request),
    )


@router.get(
    "/physical-transport-target-context-bindings",
    response_model=WorkflowEventPhysicalTransportTargetContextBindingInventoryResponse,
)
async def list_workflow_physical_transport_target_context_bindings(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_workflow_physical_transport_target_context_binding_read),
    ],
) -> WorkflowEventPhysicalTransportTargetContextBindingInventoryResponse:
    del decision
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service: WorkflowEventPhysicalTransportTargetContextBindingService = (
        request.app.state.workflow_target_context_binding_service
    )
    try:
        bindings = await service.repository.list_target_context_bindings(
            scope=scope,
            limit=256,
        )
        if any(binding.scope != scope for binding in bindings):
            raise WorkflowEventPhysicalTransportTargetContextBindingError(
                "workflow_target_context_binding_repository_scope_violation",
                "Stored target-context binding metadata escaped its query scope.",
            )
    except WorkflowEventPhysicalTransportTargetContextBindingError as error:
        _raise_physical_transport_target_context_binding(error)
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_physical_transport_target_context_binding_service_unavailable",
            title="Workflow target-context binding service unavailable",
            detail="Target-context binding metadata is temporarily unavailable.",
            retryable=True,
        ) from error
    server_time = datetime.now(UTC)
    _no_store(response)
    return WorkflowEventPhysicalTransportTargetContextBindingInventoryResponse(
        data=WorkflowEventPhysicalTransportTargetContextBindingInventoryData(
            physical_transport_target_context_bindings=[
                WorkflowEventPhysicalTransportTargetContextBindingData.from_domain(
                    binding,
                    evaluated_at=server_time,
                )
                for binding in sorted(bindings, key=lambda value: value.binding_id)
            ],
            server_time=server_time,
            durable=service.durable,
        ),
        meta=_meta(request),
    )


@router.post(
    "/physical-transport-target-context-bindings",
    response_model=WorkflowEventPhysicalTransportTargetContextBindingResponse,
    status_code=201,
)
async def create_workflow_physical_transport_target_context_binding(
    payload: CreateWorkflowEventPhysicalTransportTargetContextBindingInput,
    request: Request,
    response: Response,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(workflow_physical_transport_target_context_binder_subject),
    ],
) -> WorkflowEventPhysicalTransportTargetContextBindingResponse:
    service: WorkflowEventPhysicalTransportTargetContextBindingService = (
        request.app.state.workflow_target_context_binding_service
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    try:
        binding = await service.bind(
            endpoint_materialization_id=payload.endpoint_materialization_id,
            endpoint_materialization_digest=payload.endpoint_materialization_digest,
            credential_materialization_id=payload.credential_materialization_id,
            credential_materialization_digest=payload.credential_materialization_digest,
            policy_id=payload.policy_id,
            policy_version=payload.policy_version,
            policy_digest=service.policy.canonical_digest,
            idempotency_key=payload.idempotency_key,
            context=WorkflowPhysicalTransportTargetContextBinderContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_AUDIENCE,
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id=(
                    "decision.workflow-physical-transport-target-context-binder-authenticated"
                ),
                requested_at=datetime.now(UTC),
            ),
        )
    except WorkflowEventPhysicalTransportTargetContextBindingError as error:
        _raise_physical_transport_target_context_binding(error)
    _no_store(response)
    return WorkflowEventPhysicalTransportTargetContextBindingResponse(
        data=WorkflowEventPhysicalTransportTargetContextBindingData.from_domain(
            binding,
            evaluated_at=datetime.now(UTC),
        ),
        meta=_meta(request),
    )


@router.get(
    "/physical-transport-target-context-access-authorization-leases",
    response_model=(
        WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseInventoryResponse
    ),
)
async def list_workflow_physical_transport_target_context_access_authorization_leases(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[
        AuthorizationDecision,
        Depends(
            authorize_workflow_physical_transport_target_context_access_authorization_lease_read
        ),
    ],
) -> WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseInventoryResponse:
    del decision
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service = cast(
        WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseService,
        request.app.state.workflow_target_context_access_authorization_lease_service,
    )
    try:
        server_time = await service.repository.get_authoritative_time()
        leases = await service.list_leases(scope=scope, limit=256)
        if server_time.tzinfo is None or any(lease.scope != scope for lease in leases):
            raise WorkflowTargetContextAccessAuthorizationLeaseError(
                "workflow_target_context_access_repository_scope_violation",
                "Stored target-context access authorization metadata is invalid.",
            )
    except WorkflowTargetContextAccessAuthorizationLeaseError as error:
        _raise_physical_transport_target_context_access_authorization_lease(error)
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_target_context_access_authorization_service_unavailable",
            title="Workflow target-context access authorization service unavailable",
            detail="Target-context access authorization metadata is temporarily unavailable.",
            retryable=True,
        ) from error
    _no_store(response)
    return WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseInventoryResponse(
        data=WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseInventoryData(
            physical_transport_target_context_access_authorization_leases=[
                WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseData.from_domain(
                    lease,
                    evaluated_at=server_time,
                )
                for lease in sorted(
                    leases,
                    key=lambda value: value.authorization_lease_id,
                )
            ],
            server_time=server_time,
            durable=service.durable,
        ),
        meta=_meta(request),
    )


@router.post(
    "/physical-transport-target-context-access-authorization-leases",
    response_model=WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseResponse,
    status_code=201,
)
async def create_workflow_physical_transport_target_context_access_authorization_lease(
    payload: CreateWorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseInput,
    request: Request,
    response: Response,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(workflow_physical_transport_target_context_accessor_subject),
    ],
) -> WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseResponse:
    service = cast(
        WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseService,
        request.app.state.workflow_target_context_access_authorization_lease_service,
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    try:
        lease = await service.authorize(
            target_context_binding_id=payload.target_context_binding_id,
            target_context_binding_digest=payload.target_context_binding_digest,
            policy_id=payload.policy_id,
            policy_version=payload.policy_version,
            idempotency_key=payload.idempotency_key,
            context=WorkflowPhysicalTransportTargetContextAccessorContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_AUDIENCE,
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id=(
                    "decision.workflow-physical-transport-target-context-accessor-authenticated"
                ),
                requested_at=datetime.now(UTC),
            ),
        )
    except WorkflowTargetContextAccessAuthorizationLeaseError as error:
        _raise_physical_transport_target_context_access_authorization_lease(error)
    return _physical_transport_target_context_access_authorization_lease_response(
        lease,
        request,
        response,
    )


@router.get(
    "/physical-transport-target-context-artifact-openings",
    response_model=WorkflowEventPhysicalTransportTargetContextArtifactOpeningInventoryResponse,
)
async def list_workflow_physical_transport_target_context_artifact_openings(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_workflow_physical_transport_target_context_artifact_opening_read),
    ],
) -> WorkflowEventPhysicalTransportTargetContextArtifactOpeningInventoryResponse:
    del decision
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service = cast(
        WorkflowEventPhysicalTransportTargetContextArtifactOpeningService,
        request.app.state.workflow_target_context_artifact_opening_service,
    )
    try:
        server_time = await service.repository.get_authoritative_time()
        attempts = await service.list_attempts(scope=scope, limit=256)
        results = await service.get_results_for_opening_ids(
            scope=scope,
            opening_ids=tuple(attempt.opening_id for attempt in attempts),
        )
        results_by_opening_id = {result.opening_id: result for result in results}
        attempt_opening_ids = {attempt.opening_id for attempt in attempts}
        if (
            server_time.tzinfo is None
            or len(attempt_opening_ids) != len(attempts)
            or len(results_by_opening_id) != len(results)
            or not set(results_by_opening_id).issubset(attempt_opening_ids)
            or any(attempt.scope != scope for attempt in attempts)
            or any(result.scope != scope for result in results)
        ):
            raise WorkflowEventPhysicalTransportTargetContextArtifactOpeningError(
                "target_context_artifact_opening_repository_scope_violation"
            )
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_target_context_artifact_opening_service_unavailable",
            title="Workflow target-context artifact opening service unavailable",
            detail="Target-context artifact opening metadata is temporarily unavailable.",
            retryable=True,
        ) from error
    _no_store(response)
    return WorkflowEventPhysicalTransportTargetContextArtifactOpeningInventoryResponse(
        data=WorkflowEventPhysicalTransportTargetContextArtifactOpeningInventoryData(
            physical_transport_target_context_artifact_openings=[
                WorkflowEventPhysicalTransportTargetContextArtifactOpeningInventoryItemData.from_domain(
                    attempt,
                    results_by_opening_id.get(attempt.opening_id),
                )
                for attempt in sorted(attempts, key=lambda value: value.opening_id)
            ],
            server_time=server_time,
            durable=service.durable,
        ),
        meta=_meta(request),
    )


@router.post(
    "/physical-transport-target-context-artifact-openings",
    response_model=WorkflowEventPhysicalTransportTargetContextArtifactOpeningResponse,
    status_code=201,
)
async def create_workflow_physical_transport_target_context_artifact_opening(
    payload: CreateWorkflowEventPhysicalTransportTargetContextArtifactOpeningInput,
    request: Request,
    response: Response,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(workflow_physical_transport_target_context_accessor_subject),
    ],
) -> WorkflowEventPhysicalTransportTargetContextArtifactOpeningResponse:
    service = cast(
        WorkflowEventPhysicalTransportTargetContextArtifactOpeningService,
        request.app.state.workflow_target_context_artifact_opening_service,
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    try:
        result = await service.open_artifacts(
            authorization_lease_id=payload.authorization_lease_id,
            authorization_lease_digest=payload.authorization_lease_digest,
            policy_id=payload.policy_id,
            policy_version=payload.policy_version,
            irreversible_consumption_acknowledged=(payload.irreversible_consumption_acknowledged),
            uncertain_outcome_requires_new_authorization_acknowledged=(
                payload.uncertain_outcome_requires_new_authorization_acknowledged
            ),
            idempotency_key=payload.idempotency_key,
            context=WorkflowPhysicalTransportTargetContextAccessorContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_AUDIENCE,
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id=(
                    "decision.workflow-physical-transport-target-context-accessor-authenticated"
                ),
                requested_at=datetime.now(UTC),
            ),
        )
    except WorkflowEventPhysicalTransportTargetContextArtifactOpeningError as error:
        _raise_physical_transport_target_context_artifact_opening(error)
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_target_context_artifact_opening_service_unavailable",
            title="Workflow target-context artifact opening service unavailable",
            detail="The target-context artifact opening request cannot be completed.",
            retryable=True,
        ) from error
    return _physical_transport_target_context_artifact_opening_response(
        result,
        request,
        response,
    )


@router.get(
    "/physical-transport-target-context-capsule-consumer-bindings",
    response_model=(WorkflowProtectedTransportTargetContextCapsuleConsumerBindingInventoryResponse),
)
async def list_workflow_physical_transport_target_context_capsule_consumer_bindings(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_workflow_physical_transport_target_context_capsule_consumer_binding_read),
    ],
) -> WorkflowProtectedTransportTargetContextCapsuleConsumerBindingInventoryResponse:
    del decision
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service = cast(
        WorkflowProtectedTransportTargetContextCapsuleConsumerBindingService,
        request.app.state.workflow_target_context_capsule_consumer_binding_service,
    )
    try:
        bindings = await service.list_bindings(scope=scope, limit=256)
        server_time = datetime.now(UTC)
        binding_ids = {binding.binding_id for binding in bindings}
        if (
            len(binding_ids) != len(bindings)
            or any(binding.scope != scope for binding in bindings)
            or server_time.tzinfo is None
        ):
            raise WorkflowProtectedTransportTargetContextCapsuleConsumerBindingError(
                "target_context_capsule_consumer_binding_repository_scope_violation"
            )
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_target_context_capsule_consumer_binding_service_unavailable",
            title="Workflow target-context capsule consumer binding service unavailable",
            detail="Target-context capsule consumer binding metadata is temporarily unavailable.",
            retryable=True,
        ) from error
    _no_store(response)
    return WorkflowProtectedTransportTargetContextCapsuleConsumerBindingInventoryResponse(
        data=WorkflowProtectedTransportTargetContextCapsuleConsumerBindingInventoryData(
            physical_transport_target_context_capsule_consumer_bindings=[
                WorkflowProtectedTransportTargetContextCapsuleConsumerBindingInventoryItemData.from_domain(
                    binding
                )
                for binding in sorted(bindings, key=lambda value: value.binding_id)
            ],
            server_time=server_time,
            durable=service.durable,
        ),
        meta=_meta(request),
    )


@router.post(
    "/physical-transport-target-context-capsule-consumer-bindings",
    response_model=WorkflowProtectedTransportTargetContextCapsuleConsumerBindingResponse,
    status_code=201,
)
async def create_workflow_physical_transport_target_context_capsule_consumer_binding(
    payload: CreateWorkflowProtectedTransportTargetContextCapsuleConsumerBindingInput,
    request: Request,
    response: Response,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(workflow_physical_transport_target_context_capsule_binder_subject),
    ],
) -> WorkflowProtectedTransportTargetContextCapsuleConsumerBindingResponse:
    service = cast(
        WorkflowProtectedTransportTargetContextCapsuleConsumerBindingService,
        request.app.state.workflow_target_context_capsule_consumer_binding_service,
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    try:
        binding = await service.bind(
            opening_result_id=payload.opening_result_id,
            opening_result_digest=payload.opening_result_digest,
            policy_id=payload.policy_id,
            policy_version=payload.policy_version,
            idempotency_key=payload.idempotency_key,
            context=WorkflowProtectedTransportTargetContextCapsuleBinderContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=(
                    WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_AUDIENCE
                ),
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id=(
                    "decision.workflow-protected-transport-target-context-capsule-binder-"
                    "authenticated"
                ),
                requested_at=datetime.now(UTC),
            ),
        )
    except WorkflowProtectedTransportTargetContextCapsuleConsumerBindingError as error:
        _raise_physical_transport_target_context_capsule_consumer_binding(error)
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_target_context_capsule_consumer_binding_service_unavailable",
            title="Workflow target-context capsule consumer binding service unavailable",
            detail="The target-context capsule consumer binding request cannot be completed.",
            retryable=True,
        ) from error
    return _physical_transport_target_context_capsule_consumer_binding_response(
        binding,
        request,
        response,
    )


@router.get(
    "/physical-transport-target-context-capsule-handoff-authorization-leases",
    response_model=(
        WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseInventoryResponse
    ),
)
async def list_workflow_physical_transport_target_context_capsule_handoff_authorization_leases(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_workflow_target_context_capsule_handoff_authorization_lease_read),
    ],
) -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseInventoryResponse:
    del decision
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service = cast(
        WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseService,
        request.app.state.workflow_target_context_capsule_handoff_authorization_lease_service,
    )
    try:
        leases = await service.list_leases(scope=scope, limit=256)
        # Evaluate after the list snapshot so no returned lease can have an
        # issuance timestamp later than the response's authoritative time.
        server_time = await service.repository.get_authoritative_time()
        lease_ids = {lease.authorization_lease_id for lease in leases}
        if (
            server_time.tzinfo is None
            or len(lease_ids) != len(leases)
            or any(lease.scope != scope for lease in leases)
        ):
            raise WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError(
                "workflow_target_context_capsule_handoff_repository_scope_violation",
                "Stored target-context capsule handoff authorization metadata is invalid.",
            )
    except WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError as error:
        _raise_physical_transport_target_context_capsule_handoff_authorization_lease(error)
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_target_context_capsule_handoff_authorization_service_unavailable",
            title="Workflow target-context capsule handoff authorization service unavailable",
            detail=(
                "Target-context capsule handoff authorization metadata is temporarily unavailable."
            ),
            retryable=True,
        ) from error
    _no_store(response)
    return WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseInventoryResponse(
        data=(
            WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseInventoryData(
                physical_transport_target_context_capsule_handoff_authorization_leases=[
                    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseData.from_domain(
                        lease,
                        evaluated_at=server_time,
                    )
                    for lease in sorted(
                        leases,
                        key=lambda value: value.authorization_lease_id,
                    )
                ],
                server_time=server_time,
                durable=service.durable,
            )
        ),
        meta=_meta(request),
    )


@router.post(
    "/physical-transport-target-context-capsule-handoff-authorization-leases",
    response_model=WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseResponse,
    status_code=201,
)
async def create_workflow_physical_transport_target_context_capsule_handoff_authorization_lease(
    payload: CreateWorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseInput,
    request: Request,
    response: Response,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(workflow_protected_transport_target_context_capsule_consumer_subject),
    ],
) -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseResponse:
    service = cast(
        WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseService,
        request.app.state.workflow_target_context_capsule_handoff_authorization_lease_service,
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    try:
        lease = await service.authorize(
            consumer_binding_id=payload.consumer_binding_id,
            consumer_binding_digest=payload.consumer_binding_digest,
            policy_id=payload.policy_id,
            policy_version=payload.policy_version,
            idempotency_key=payload.idempotency_key,
            context=WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=(WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE),
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id=(
                    "decision.workflow-protected-transport-target-context-capsule-consumer-"
                    "authenticated"
                ),
                requested_at=datetime.now(UTC),
            ),
        )
        evaluated_at = await service.repository.get_authoritative_time()
        if evaluated_at.tzinfo is None:
            raise ValueError("repository time must be timezone-aware")
    except WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError as error:
        _raise_physical_transport_target_context_capsule_handoff_authorization_lease(error)
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_target_context_capsule_handoff_authorization_service_unavailable",
            title="Workflow target-context capsule handoff authorization service unavailable",
            detail="The target-context capsule handoff authorization request cannot be completed.",
            retryable=True,
        ) from error
    return _physical_transport_target_context_capsule_handoff_authorization_lease_response(
        lease,
        request,
        response,
        evaluated_at=evaluated_at,
    )


@router.get(
    "/physical-transport-target-context-capsule-handoffs",
    response_model=WorkflowProtectedTransportTargetContextCapsuleHandoffInventoryResponse,
)
async def list_workflow_physical_transport_target_context_capsule_handoffs(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_workflow_target_context_capsule_handoff_read),
    ],
) -> WorkflowProtectedTransportTargetContextCapsuleHandoffInventoryResponse:
    del decision
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service = cast(
        WorkflowProtectedTransportTargetContextCapsuleHandoffService,
        request.app.state.workflow_target_context_capsule_handoff_service,
    )
    try:
        presentations = await service.list_presentations(scope=scope, limit=256)
        server_time = await service.repository.get_authoritative_time()
        if (
            server_time.tzinfo is None
            or len({item.attempt.handoff_id for item in presentations}) != len(presentations)
            or any(item.attempt.scope != scope for item in presentations)
        ):
            raise WorkflowProtectedTransportTargetContextCapsuleHandoffError(
                "target_context_capsule_handoff_repository_scope_violation"
            )
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_target_context_capsule_handoff_service_unavailable",
            title="Workflow target-context capsule handoff service unavailable",
            detail="Target-context capsule handoff metadata is temporarily unavailable.",
            retryable=True,
        ) from error
    _no_store(response)
    return WorkflowProtectedTransportTargetContextCapsuleHandoffInventoryResponse(
        data=WorkflowProtectedTransportTargetContextCapsuleHandoffInventoryData(
            physical_transport_target_context_capsule_handoffs=[
                WorkflowProtectedTransportTargetContextCapsuleHandoffData.from_domain(
                    item.attempt,
                    item.result,
                    evaluated_at=server_time,
                )
                for item in sorted(
                    presentations,
                    key=lambda value: value.attempt.handoff_id,
                )
            ],
            server_time=server_time,
            durable=True,
        ),
        meta=_meta(request),
    )


@router.post(
    "/physical-transport-target-context-capsule-handoffs",
    response_model=WorkflowProtectedTransportTargetContextCapsuleHandoffResponse,
    status_code=201,
)
async def create_workflow_physical_transport_target_context_capsule_handoff(
    payload: CreateWorkflowProtectedTransportTargetContextCapsuleHandoffInput,
    request: Request,
    response: Response,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(workflow_protected_transport_target_context_capsule_consumer_subject),
    ],
) -> WorkflowProtectedTransportTargetContextCapsuleHandoffResponse:
    service = cast(
        WorkflowProtectedTransportTargetContextCapsuleHandoffService,
        request.app.state.workflow_target_context_capsule_handoff_service,
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    try:
        presentation = await service.handoff(
            authorization_lease_id=payload.authorization_lease_id,
            authorization_lease_digest=payload.authorization_lease_digest,
            policy_id=payload.policy_id,
            policy_version=payload.policy_version,
            irreversible_consumption_acknowledged=(payload.irreversible_consumption_acknowledged),
            uncertain_outcome_requires_new_authorization_acknowledged=(
                payload.uncertain_outcome_requires_new_authorization_acknowledged
            ),
            idempotency_key=payload.idempotency_key,
            context=WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id=(
                    "decision.workflow-protected-transport-target-context-capsule-consumer-"
                    "authenticated"
                ),
                requested_at=datetime.now(UTC),
            ),
        )
        server_time = await service.repository.get_authoritative_time()
    except WorkflowProtectedTransportTargetContextCapsuleHandoffError as error:
        unavailable = "unavailable" in error.code or error.code.endswith(
            "durable_repository_required"
        )
        conflict = any(
            marker in error.code for marker in ("conflict", "consumed", "uncertain", "expired")
        )
        raise AtlasError(
            status=503 if unavailable else 409 if conflict else 422,
            code=error.code,
            title="Workflow target-context capsule handoff rejected",
            detail="The sealed capsule handoff request did not satisfy its safety contract.",
            retryable=unavailable,
        ) from error
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_target_context_capsule_handoff_service_unavailable",
            title="Workflow target-context capsule handoff service unavailable",
            detail="The sealed capsule handoff request cannot be completed.",
            retryable=False,
        ) from error
    _no_store(response)
    return WorkflowProtectedTransportTargetContextCapsuleHandoffResponse(
        data=WorkflowProtectedTransportTargetContextCapsuleHandoffData.from_domain(
            presentation.attempt,
            presentation.result,
            evaluated_at=server_time,
        ),
        meta=_meta(request),
    )


@router.get(
    "/physical-transport-target-context-capsule-opening-authorization-leases",
    response_model=(
        WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseInventoryResponse
    ),
)
async def list_workflow_physical_transport_target_context_capsule_opening_authorization_leases(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_workflow_target_context_capsule_opening_authorization_lease_read),
    ],
) -> WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseInventoryResponse:
    del decision
    _no_store(response)
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service = cast(
        WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseService,
        request.app.state.workflow_target_context_capsule_opening_authorization_lease_service,
    )
    try:
        leases = await service.list_leases(scope=scope, limit=256)
        server_time = await service.repository.get_authoritative_time()
    except WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseError as error:
        raise AtlasError(
            status=503,
            code="workflow_target_context_capsule_opening_authorization_service_unavailable",
            title="Workflow target-context capsule opening authorization unavailable",
            detail="Opening authorization metadata is temporarily unavailable.",
            retryable=True,
        ) from error
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_target_context_capsule_opening_authorization_service_unavailable",
            title="Workflow target-context capsule opening authorization unavailable",
            detail="Opening authorization metadata is temporarily unavailable.",
            retryable=True,
        ) from error
    return WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseInventoryResponse(
        data=WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseInventoryData(
            physical_transport_target_context_capsule_opening_authorization_leases=[
                WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseData.from_domain(
                    lease, evaluated_at=server_time
                )
                for lease in leases
            ],
            server_time=server_time,
            durable=True,
        ),
        meta=_meta(request),
    )


@router.post(
    "/physical-transport-target-context-capsule-opening-authorization-leases",
    response_model=(
        WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseResponse
    ),
    status_code=201,
)
async def create_workflow_physical_transport_target_context_capsule_opening_authorization_lease(
    payload: CreateWorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseInput,
    request: Request,
    response: Response,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(workflow_protected_transport_target_context_capsule_consumer_subject),
    ],
) -> WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseResponse:
    _no_store(response)
    service = cast(
        WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseService,
        request.app.state.workflow_target_context_capsule_opening_authorization_lease_service,
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    try:
        lease = await service.authorize(
            handoff_result_id=payload.handoff_result_id,
            handoff_result_digest=payload.handoff_result_digest,
            policy_id=payload.policy_id,
            policy_version=payload.policy_version,
            idempotency_key=payload.idempotency_key,
            context=WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=(WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE),
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id=(
                    "decision.workflow-protected-transport-target-context-capsule-consumer-"
                    "authenticated"
                ),
                requested_at=datetime.now(UTC),
            ),
        )
        server_time = await service.repository.get_authoritative_time()
    except WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseError as error:
        unavailable = "unavailable" in error.code or error.code.endswith(
            "durable_repository_required"
        )
        conflict = "conflict" in error.code or "already_authorized" in error.code
        raise AtlasError(
            status=503 if unavailable else 409 if conflict else 422,
            code="authorization_denied",
            title="Request denied",
            detail="The current identity or evidence is not authorized for this operation.",
            retryable=unavailable,
        ) from error
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_target_context_capsule_opening_authorization_service_unavailable",
            title="Workflow target-context capsule opening authorization unavailable",
            detail="Opening authorization metadata is temporarily unavailable.",
            retryable=True,
        ) from error
    return WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseResponse(
        data=WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseData.from_domain(
            lease, evaluated_at=server_time
        ),
        meta=_meta(request),
    )


@router.get(
    "/protected-resident-context-access-authorizations",
    response_model=WorkflowProtectedResidentContextAccessAuthorizationInventoryResponse,
)
async def list_workflow_protected_resident_context_access_authorizations(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_workflow_protected_resident_context_access_authorization_read),
    ],
) -> WorkflowProtectedResidentContextAccessAuthorizationInventoryResponse:
    del decision
    _no_store(response)
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service = cast(
        WorkflowProtectedResidentContextAccessAuthorizationService,
        request.app.state.workflow_protected_resident_context_access_authorization_service,
    )
    try:
        presentations = await service.list_presentations(scope=scope, limit=256)
        server_time = (
            presentations[0].evaluated_at
            if presentations
            else await service.repository.get_authoritative_time()
        )
    except WorkflowProtectedResidentContextAccessAuthorizationError as error:
        raise AtlasError(
            status=503,
            code="workflow_protected_access_authorization_service_unavailable",
            title="Protected access authorization unavailable",
            detail="Authorization metadata is temporarily unavailable.",
            retryable=True,
        ) from error
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_protected_access_authorization_service_unavailable",
            title="Protected access authorization unavailable",
            detail="Authorization metadata is temporarily unavailable.",
            retryable=True,
        ) from error
    return WorkflowProtectedResidentContextAccessAuthorizationInventoryResponse(
        data=WorkflowProtectedResidentContextAccessAuthorizationInventoryData(
            authorizations=[
                WorkflowProtectedResidentContextAccessAuthorizationData.from_domain(
                    presentation.lease,
                    evaluated_at=presentation.evaluated_at,
                    consumed=presentation.consumed,
                )
                for presentation in presentations
            ],
            server_time=server_time,
            durable=True,
        ),
        meta=_meta(request),
    )


@router.post(
    "/protected-resident-context-access-authorizations",
    response_model=WorkflowProtectedResidentContextAccessAuthorizationResponse,
    status_code=201,
)
async def create_workflow_protected_resident_context_access_authorization(
    payload: CreateWorkflowProtectedResidentContextAccessAuthorizationInput,
    request: Request,
    response: Response,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(workflow_protected_transport_target_context_capsule_consumer_subject),
    ],
) -> WorkflowProtectedResidentContextAccessAuthorizationResponse:
    _no_store(response)
    service = cast(
        WorkflowProtectedResidentContextAccessAuthorizationService,
        request.app.state.workflow_protected_resident_context_access_authorization_service,
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    try:
        lease = await service.authorize(
            opening_result_id=payload.opening_result_id,
            opening_result_digest=payload.opening_result_digest,
            policy_id=payload.policy_id,
            policy_version=payload.policy_version,
            idempotency_key=payload.idempotency_key,
            context=WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id=("decision.workflow-protected-resident-context-consumer-authenticated"),
                requested_at=datetime.now(UTC),
            ),
        )
        presentation = await service.get_presentation(
            scope=scope,
            authorization_lease_id=lease.authorization_lease_id,
        )
        if presentation.lease.canonical_digest != lease.canonical_digest:
            raise RuntimeError("protected access authorization projection mismatch")
    except WorkflowProtectedResidentContextAccessAuthorizationError as error:
        unavailable = "unavailable" in error.code or error.code.endswith(
            "durable_repository_required"
        )
        raise AtlasError(
            status=503 if unavailable else 409,
            code=(
                "workflow_protected_access_authorization_service_unavailable"
                if unavailable
                else "authorization_denied"
            ),
            title=(
                "Protected access authorization unavailable" if unavailable else "Request denied"
            ),
            detail=(
                "Authorization metadata is temporarily unavailable."
                if unavailable
                else "The current identity or evidence is not authorized for this operation."
            ),
            retryable=unavailable,
        ) from error
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_protected_access_authorization_service_unavailable",
            title="Protected access authorization unavailable",
            detail="Authorization metadata is temporarily unavailable.",
            retryable=True,
        ) from error
    return WorkflowProtectedResidentContextAccessAuthorizationResponse(
        data=WorkflowProtectedResidentContextAccessAuthorizationData.from_domain(
            presentation.lease,
            evaluated_at=presentation.evaluated_at,
            consumed=presentation.consumed,
        ),
        meta=_meta(request),
    )


@router.get(
    "/protected-resident-context-access-consumptions",
    response_model=WorkflowProtectedResidentContextAccessConsumptionInventoryResponse,
)
async def list_workflow_protected_resident_context_access_consumptions(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_workflow_protected_resident_context_access_consumption_read),
    ],
) -> WorkflowProtectedResidentContextAccessConsumptionInventoryResponse:
    del decision
    _no_store(response)
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service = cast(
        WorkflowProtectedResidentContextAccessConsumptionService,
        request.app.state.workflow_protected_resident_context_access_consumption_service,
    )
    try:
        presentations = await service.list_presentations(scope=scope, limit=256)
        server_time = await service.repository.get_authoritative_time()
        access_ids = tuple(presentation.attempt.access_id for presentation in presentations)
        if len(access_ids) != len(set(access_ids)) or any(
            presentation.attempt.scope != scope for presentation in presentations
        ):
            raise RuntimeError("protected resident-context access consumption scope mismatch")
        items = [
            WorkflowProtectedResidentContextAccessConsumptionData.from_domain(
                presentation.attempt,
                presentation.result,
                evaluated_at=server_time,
            )
            for presentation in presentations
        ]
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_protected_resident_context_access_consumption_service_unavailable",
            title="Protected resident-context access consumption unavailable",
            detail="Access consumption metadata is temporarily unavailable.",
            retryable=True,
        ) from error
    return WorkflowProtectedResidentContextAccessConsumptionInventoryResponse(
        data=WorkflowProtectedResidentContextAccessConsumptionInventoryData(
            consumptions=items,
            server_time=server_time,
            durable=True,
        ),
        meta=_meta(request),
    )


@router.post(
    "/protected-resident-context-access-consumptions",
    response_model=WorkflowProtectedResidentContextAccessConsumptionResponse,
    status_code=201,
)
async def create_workflow_protected_resident_context_access_consumption(
    payload: CreateWorkflowProtectedResidentContextAccessConsumptionInput,
    request: Request,
    response: Response,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(workflow_protected_transport_target_context_capsule_consumer_subject),
    ],
) -> WorkflowProtectedResidentContextAccessConsumptionResponse:
    _no_store(response)
    service = cast(
        WorkflowProtectedResidentContextAccessConsumptionService,
        request.app.state.workflow_protected_resident_context_access_consumption_service,
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    try:
        presentation = await service.consume(
            authorization_lease_id=payload.authorization_lease_id,
            policy_id=payload.policy_id,
            policy_version=payload.policy_version,
            irreversible_consumption_acknowledged=(payload.irreversible_consumption_acknowledged),
            uncertain_outcome_requires_new_authorization_acknowledged=(
                payload.uncertain_outcome_requires_new_authorization_acknowledged
            ),
            idempotency_key=payload.idempotency_key,
            context=WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=(WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE),
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id=(
                    "decision.workflow-protected-resident-context-access-consumer-authenticated"
                ),
                requested_at=datetime.now(UTC),
            ),
        )
        server_time = await service.repository.get_authoritative_time()
        if presentation.attempt.scope != scope:
            raise RuntimeError("protected resident-context access consumption scope mismatch")
        data = WorkflowProtectedResidentContextAccessConsumptionData.from_domain(
            presentation.attempt,
            presentation.result,
            evaluated_at=server_time,
        )
    except WorkflowProtectedResidentContextAccessConsumptionError as error:
        unavailable = "unavailable" in error.code or error.code.endswith(
            "durable_repository_required"
        )
        raise AtlasError(
            status=503 if unavailable else 422,
            code=(
                "workflow_protected_resident_context_access_consumption_service_unavailable"
                if unavailable
                else "authorization_denied"
            ),
            title=(
                "Protected resident-context access consumption unavailable"
                if unavailable
                else "Request denied"
            ),
            detail=(
                "The protected access request cannot be completed."
                if unavailable
                else "The current identity or evidence is not authorized for this operation."
            ),
            retryable=unavailable,
        ) from error
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_protected_resident_context_access_consumption_service_unavailable",
            title="Protected resident-context access consumption unavailable",
            detail="The protected access request cannot be completed.",
            retryable=True,
        ) from error
    return WorkflowProtectedResidentContextAccessConsumptionResponse(
        data=data,
        meta=_meta(request),
    )


@router.get(
    "/protected-runtime-context-injection-authorizations",
    response_model=WorkflowProtectedRuntimeContextInjectionAuthorizationInventoryResponse,
)
async def list_workflow_protected_runtime_context_injection_authorizations(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_workflow_protected_runtime_context_injection_authorization_read),
    ],
) -> WorkflowProtectedRuntimeContextInjectionAuthorizationInventoryResponse:
    del decision
    _no_store(response)
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service = cast(
        WorkflowProtectedRuntimeContextInjectionAuthorizationService,
        request.app.state.workflow_protected_runtime_context_injection_authorization_service,
    )
    try:
        presentations = await service.list_presentations(scope=scope, limit=256)
        server_time = (
            presentations[0].evaluated_at
            if presentations
            else await service.repository.get_authoritative_time()
        )
        items = [
            WorkflowProtectedRuntimeContextInjectionAuthorizationData.from_domain(presentation)
            for presentation in presentations
        ]
    except Exception as error:
        raise AtlasError(
            status=503,
            code=("workflow_protected_runtime_context_injection_authorization_service_unavailable"),
            title="Protected runtime-context injection authorization unavailable",
            detail="Injection authorization metadata is temporarily unavailable.",
            retryable=True,
        ) from error
    return WorkflowProtectedRuntimeContextInjectionAuthorizationInventoryResponse(
        data=WorkflowProtectedRuntimeContextInjectionAuthorizationInventoryData(
            authorizations=items,
            server_time=server_time,
            durable=True,
        ),
        meta=_meta(request),
    )


@router.post(
    "/protected-runtime-context-injection-authorizations",
    response_model=WorkflowProtectedRuntimeContextInjectionAuthorizationResponse,
    status_code=201,
)
async def create_workflow_protected_runtime_context_injection_authorization(
    payload: CreateWorkflowProtectedRuntimeContextInjectionAuthorizationInput,
    request: Request,
    response: Response,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(workflow_protected_transport_target_context_capsule_consumer_subject),
    ],
) -> WorkflowProtectedRuntimeContextInjectionAuthorizationResponse:
    _no_store(response)
    service = cast(
        WorkflowProtectedRuntimeContextInjectionAuthorizationService,
        request.app.state.workflow_protected_runtime_context_injection_authorization_service,
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    try:
        lease = await service.authorize(
            access_result_id=payload.access_result_id,
            access_result_digest=payload.access_result_digest,
            policy_id=payload.policy_id,
            policy_version=payload.policy_version,
            idempotency_key=payload.idempotency_key,
            context=WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id=(
                    "decision.workflow-protected-runtime-context-injection-consumer-authenticated"
                ),
                requested_at=datetime.now(UTC),
            ),
        )
        presentation = await service.get_presentation(
            scope=scope,
            authorization_lease_id=lease.authorization_lease_id,
        )
        if presentation.lease.canonical_digest != lease.canonical_digest:
            raise RuntimeError("runtime-context injection authorization projection mismatch")
        data = WorkflowProtectedRuntimeContextInjectionAuthorizationData.from_domain(presentation)
    except WorkflowProtectedRuntimeContextInjectionAuthorizationError as error:
        unavailable = "unavailable" in error.code or error.code.endswith(
            "durable_repository_required"
        )
        raise AtlasError(
            status=503 if unavailable else 409,
            code=(
                "workflow_protected_runtime_context_injection_authorization_service_unavailable"
                if unavailable
                else "authorization_denied"
            ),
            title=(
                "Protected runtime-context injection authorization unavailable"
                if unavailable
                else "Request denied"
            ),
            detail=(
                "Injection authorization metadata is temporarily unavailable."
                if unavailable
                else "The current identity or evidence is not authorized for this operation."
            ),
            retryable=unavailable,
        ) from error
    except Exception as error:
        raise AtlasError(
            status=503,
            code=("workflow_protected_runtime_context_injection_authorization_service_unavailable"),
            title="Protected runtime-context injection authorization unavailable",
            detail="Injection authorization metadata is temporarily unavailable.",
            retryable=True,
        ) from error
    return WorkflowProtectedRuntimeContextInjectionAuthorizationResponse(
        data=data,
        meta=_meta(request),
    )


@router.get(
    "/protected-runtime-context-injection-consumptions",
    response_model=WorkflowProtectedRuntimeContextInjectionConsumptionInventoryResponse,
)
async def list_workflow_protected_runtime_context_injection_consumptions(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_workflow_protected_runtime_context_injection_consumption_read),
    ],
) -> WorkflowProtectedRuntimeContextInjectionConsumptionInventoryResponse:
    del decision
    _no_store(response)
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service = cast(
        WorkflowProtectedRuntimeContextInjectionConsumptionService,
        request.app.state.workflow_protected_runtime_context_injection_consumption_service,
    )
    try:
        presentations = await service.list_presentations(scope=scope, limit=256)
        server_time = await service.repository.get_authoritative_time()
        injection_ids = tuple(presentation.attempt.injection_id for presentation in presentations)
        if len(injection_ids) != len(set(injection_ids)) or any(
            presentation.attempt.scope != scope for presentation in presentations
        ):
            raise RuntimeError("protected runtime-context injection consumption scope mismatch")
        items = [
            WorkflowProtectedRuntimeContextInjectionConsumptionData.from_domain(
                presentation,
                evaluated_at=server_time,
            )
            for presentation in presentations
        ]
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_protected_runtime_context_injection_consumption_service_unavailable",
            title="Protected runtime-context injection consumption unavailable",
            detail="Injection consumption metadata is temporarily unavailable.",
            retryable=True,
        ) from error
    return WorkflowProtectedRuntimeContextInjectionConsumptionInventoryResponse(
        data=WorkflowProtectedRuntimeContextInjectionConsumptionInventoryData(
            consumptions=items,
            server_time=server_time,
            durable=True,
        ),
        meta=_meta(request),
    )


@router.post(
    "/protected-runtime-context-injection-consumptions",
    response_model=WorkflowProtectedRuntimeContextInjectionConsumptionResponse,
    status_code=201,
)
async def create_workflow_protected_runtime_context_injection_consumption(
    payload: CreateWorkflowProtectedRuntimeContextInjectionConsumptionInput,
    request: Request,
    response: Response,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(workflow_protected_transport_target_context_capsule_consumer_subject),
    ],
) -> WorkflowProtectedRuntimeContextInjectionConsumptionResponse:
    _no_store(response)
    service = cast(
        WorkflowProtectedRuntimeContextInjectionConsumptionService,
        request.app.state.workflow_protected_runtime_context_injection_consumption_service,
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    try:
        presentation = await service.consume(
            authorization_lease_id=payload.authorization_lease_id,
            policy_id=payload.policy_id,
            policy_version=payload.policy_version,
            irreversible_consumption_acknowledged=(payload.irreversible_consumption_acknowledged),
            uncertain_outcome_requires_new_authorization_acknowledged=(
                payload.uncertain_outcome_requires_new_authorization_acknowledged
            ),
            idempotency_key=payload.idempotency_key,
            context=WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id=(
                    "decision.workflow-protected-runtime-context-injection-consumer-authenticated"
                ),
                requested_at=datetime.now(UTC),
            ),
        )
        server_time = await service.repository.get_authoritative_time()
        if presentation.attempt.scope != scope:
            raise RuntimeError("protected runtime-context injection consumption scope mismatch")
        data = WorkflowProtectedRuntimeContextInjectionConsumptionData.from_domain(
            presentation,
            evaluated_at=server_time,
        )
    except WorkflowProtectedRuntimeContextInjectionConsumptionError as error:
        unavailable = "unavailable" in error.code or error.code.endswith(
            "durable_repository_required"
        )
        raise AtlasError(
            status=503 if unavailable else 409,
            code=(
                "workflow_protected_runtime_context_injection_consumption_service_unavailable"
                if unavailable
                else "authorization_denied"
            ),
            title=(
                "Protected runtime-context injection consumption unavailable"
                if unavailable
                else "Request denied"
            ),
            detail=(
                "The protected injection request cannot be completed."
                if unavailable
                else "The current identity or evidence is not authorized for this operation."
            ),
            retryable=unavailable,
        ) from error
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_protected_runtime_context_injection_consumption_service_unavailable",
            title="Protected runtime-context injection consumption unavailable",
            detail="The protected injection request cannot be completed.",
            retryable=True,
        ) from error
    return WorkflowProtectedRuntimeContextInjectionConsumptionResponse(
        data=data,
        meta=_meta(request),
    )


@router.get(
    "/protected-runtime-context-use-authorizations",
    response_model=WorkflowProtectedRuntimeContextUseAuthorizationInventoryResponse,
)
async def list_workflow_protected_runtime_context_use_authorizations(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_workflow_protected_runtime_context_use_authorization_read),
    ],
) -> WorkflowProtectedRuntimeContextUseAuthorizationInventoryResponse:
    del decision
    _no_store(response)
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service = cast(
        WorkflowProtectedRuntimeContextUseAuthorizationService,
        request.app.state.workflow_protected_runtime_context_use_authorization_service,
    )
    try:
        presentations = await service.list_presentations(scope=scope, limit=256)
        server_time = await service.repository.get_authoritative_time()
        if any(presentation.lease.scope != scope for presentation in presentations):
            raise RuntimeError("protected runtime-context use authorization scope mismatch")
        items = [
            WorkflowProtectedRuntimeContextUseAuthorizationData.from_domain(presentation)
            for presentation in presentations
        ]
        inventory_data = WorkflowProtectedRuntimeContextUseAuthorizationInventoryData(
            authorizations=items,
            server_time=server_time,
            durable=service.durable,
        )
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_protected_runtime_context_use_authorization_service_unavailable",
            title="Protected runtime-context use authorization unavailable",
            detail="Runtime-context use authorization metadata is temporarily unavailable.",
            retryable=True,
        ) from error
    return WorkflowProtectedRuntimeContextUseAuthorizationInventoryResponse(
        data=inventory_data,
        meta=_meta(request),
    )


@router.post(
    "/protected-runtime-context-use-authorizations",
    response_model=WorkflowProtectedRuntimeContextUseAuthorizationResponse,
    status_code=201,
)
async def create_workflow_protected_runtime_context_use_authorization(
    payload: CreateWorkflowProtectedRuntimeContextUseAuthorizationInput,
    request: Request,
    response: Response,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(workflow_protected_transport_target_context_capsule_consumer_subject),
    ],
) -> WorkflowProtectedRuntimeContextUseAuthorizationResponse:
    _no_store(response)
    service = cast(
        WorkflowProtectedRuntimeContextUseAuthorizationService,
        request.app.state.workflow_protected_runtime_context_use_authorization_service,
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    try:
        lease = await service.authorize(
            injection_result_id=payload.injection_result_id,
            injection_result_digest=payload.injection_result_digest,
            policy_id=payload.policy_id,
            policy_version=payload.policy_version,
            idempotency_key=payload.idempotency_key,
            context=WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id=(
                    "decision.workflow-protected-runtime-context-use-consumer-authenticated"
                ),
                requested_at=datetime.now(UTC),
            ),
        )
        presentations = await (
            service.repository.list_protected_runtime_context_use_authorization_presentations(
                scope=scope,
                authorization_lease_ids=(lease.authorization_lease_id,),
                limit=1,
            )
        )
        if len(presentations) != 1:
            raise RuntimeError("runtime-context use authorization projection unavailable")
        presentation = presentations[0]
        if presentation.lease.canonical_digest != lease.canonical_digest:
            raise RuntimeError("runtime-context use authorization projection mismatch")
        data = WorkflowProtectedRuntimeContextUseAuthorizationData.from_domain(presentation)
    except WorkflowProtectedRuntimeContextUseAuthorizationError as error:
        unavailable = "unavailable" in error.code or error.code.endswith(
            "durable_repository_required"
        )
        raise AtlasError(
            status=503 if unavailable else 409,
            code=(
                "workflow_protected_runtime_context_use_authorization_service_unavailable"
                if unavailable
                else "authorization_denied"
            ),
            title=(
                "Protected runtime-context use authorization unavailable"
                if unavailable
                else "Request denied"
            ),
            detail=(
                "Runtime-context use authorization metadata is temporarily unavailable."
                if unavailable
                else "The current identity or evidence is not authorized for this operation."
            ),
            retryable=unavailable,
        ) from error
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_protected_runtime_context_use_authorization_service_unavailable",
            title="Protected runtime-context use authorization unavailable",
            detail="Runtime-context use authorization metadata is temporarily unavailable.",
            retryable=True,
        ) from error
    return WorkflowProtectedRuntimeContextUseAuthorizationResponse(
        data=data,
        meta=_meta(request),
    )


@router.get(
    "/protected-runtime-start-authorizations",
    response_model=WorkflowProtectedRuntimeStartAuthorizationInventoryResponse,
)
async def list_workflow_protected_runtime_start_authorizations(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_workflow_protected_runtime_start_authorization_read),
    ],
) -> WorkflowProtectedRuntimeStartAuthorizationInventoryResponse:
    del decision
    _no_store(response)
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service = cast(
        WorkflowProtectedRuntimeStartAuthorizationService,
        request.app.state.workflow_protected_runtime_start_authorization_service,
    )
    try:
        presentations = await service.list_presentations(scope=scope, limit=256)
        server_time = await service.repository.get_authoritative_time()
        if any(presentation.lease.scope != scope for presentation in presentations):
            raise RuntimeError("protected runtime-start authorization scope mismatch")
        inventory_data = WorkflowProtectedRuntimeStartAuthorizationInventoryData(
            authorizations=[
                WorkflowProtectedRuntimeStartAuthorizationData.from_domain(presentation)
                for presentation in presentations
            ],
            server_time=server_time,
            durable=service.durable,
        )
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_protected_runtime_start_authorization_service_unavailable",
            title="Protected runtime-start authorization unavailable",
            detail="Runtime-start authorization metadata is temporarily unavailable.",
            retryable=True,
        ) from error
    return WorkflowProtectedRuntimeStartAuthorizationInventoryResponse(
        data=inventory_data,
        meta=_meta(request),
    )


@router.post(
    "/protected-runtime-start-authorizations",
    response_model=WorkflowProtectedRuntimeStartAuthorizationResponse,
    status_code=201,
)
async def create_workflow_protected_runtime_start_authorization(
    payload: CreateWorkflowProtectedRuntimeStartAuthorizationInput,
    request: Request,
    response: Response,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(workflow_protected_transport_target_context_capsule_consumer_subject),
    ],
) -> WorkflowProtectedRuntimeStartAuthorizationResponse:
    _no_store(response)
    service = cast(
        WorkflowProtectedRuntimeStartAuthorizationService,
        request.app.state.workflow_protected_runtime_start_authorization_service,
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    try:
        lease = await service.authorize(
            use_result_id=payload.use_result_id,
            use_result_digest=payload.use_result_digest,
            policy_id=payload.policy_id,
            policy_version=payload.policy_version,
            idempotency_key=payload.idempotency_key,
            context=WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id="decision.workflow-protected-runtime-start-consumer-authenticated",
                requested_at=datetime.now(UTC),
            ),
        )
        presentations = await (
            service.repository.list_protected_runtime_start_authorization_presentations(
                scope=scope,
                authorization_lease_ids=(lease.authorization_lease_id,),
                limit=1,
            )
        )
        if len(presentations) != 1:
            raise RuntimeError("runtime-start authorization projection unavailable")
        presentation = presentations[0]
        if presentation.lease.canonical_digest != lease.canonical_digest:
            raise RuntimeError("runtime-start authorization projection mismatch")
        data = WorkflowProtectedRuntimeStartAuthorizationData.from_domain(presentation)
    except WorkflowProtectedRuntimeStartAuthorizationError as error:
        conflict = any(
            marker in error.code
            for marker in (
                "already_authorized",
                "evidence_conflict",
                "idempotency_conflict",
                "policy_conflict",
            )
        )
        raise AtlasError(
            status=409 if conflict else 503,
            code=(
                "authorization_denied"
                if conflict
                else "workflow_protected_runtime_start_authorization_service_unavailable"
            ),
            title="Request denied"
            if conflict
            else "Protected runtime-start authorization unavailable",
            detail=(
                "The current identity or evidence is not authorized for this operation."
                if conflict
                else "Runtime-start authorization metadata is temporarily unavailable."
            ),
            retryable=not conflict,
        ) from error
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_protected_runtime_start_authorization_service_unavailable",
            title="Protected runtime-start authorization unavailable",
            detail="Runtime-start authorization metadata is temporarily unavailable.",
            retryable=True,
        ) from error
    return WorkflowProtectedRuntimeStartAuthorizationResponse(
        data=data,
        meta=_meta(request),
    )


@router.get(
    "/protected-runtime-context-use-authorization-consumptions",
    response_model=WorkflowProtectedRuntimeContextUseAuthorizationConsumptionInventoryResponse,
)
async def list_workflow_protected_runtime_context_use_authorization_consumptions(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_workflow_protected_runtime_context_use_authorization_consumption_read),
    ],
) -> WorkflowProtectedRuntimeContextUseAuthorizationConsumptionInventoryResponse:
    del decision
    _no_store(response)
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service = cast(
        WorkflowProtectedRuntimeContextUseAuthorizationConsumptionService,
        request.app.state.workflow_protected_runtime_context_use_authorization_consumption_service,
    )
    try:
        presentations = await service.list_presentations(scope=scope, limit=256)
        get_authoritative_time = getattr(service.repository, "get_authoritative_time", None)
        if not callable(get_authoritative_time):
            raise RuntimeError("authoritative repository time is unavailable")
        server_time = await get_authoritative_time()
        if not isinstance(server_time, datetime) or server_time.tzinfo is None:
            raise RuntimeError("authoritative repository time is invalid")
        consumption_ids = tuple(
            presentation.result.consumption_id for presentation in presentations
        )
        if len(consumption_ids) != len(set(consumption_ids)) or any(
            presentation.claim.scope != scope or presentation.result.scope != scope
            for presentation in presentations
        ):
            raise RuntimeError(
                "protected runtime-context use-authorization consumption scope mismatch"
            )
        items = [
            WorkflowProtectedRuntimeContextUseAuthorizationConsumptionData.from_domain(presentation)
            for presentation in presentations
        ]
        if any(item.consumed_at > server_time for item in items):
            raise RuntimeError(
                "protected runtime-context use-authorization consumption time mismatch"
            )
    except Exception as error:
        raise AtlasError(
            status=503,
            code=(
                "workflow_protected_runtime_context_use_authorization_consumption_"
                "service_unavailable"
            ),
            title="Protected runtime-context use-authorization consumption unavailable",
            detail=(
                "Runtime-context use-authorization consumption metadata is temporarily unavailable."
            ),
            retryable=True,
        ) from error
    return WorkflowProtectedRuntimeContextUseAuthorizationConsumptionInventoryResponse(
        data=WorkflowProtectedRuntimeContextUseAuthorizationConsumptionInventoryData(
            consumptions=items,
            server_time=server_time,
            durable=True,
        ),
        meta=_meta(request),
    )


@router.post(
    "/protected-runtime-context-use-authorization-consumptions",
    response_model=WorkflowProtectedRuntimeContextUseAuthorizationConsumptionResponse,
    status_code=201,
)
async def create_workflow_protected_runtime_context_use_authorization_consumption(
    payload: CreateWorkflowProtectedRuntimeContextUseAuthorizationConsumptionInput,
    request: Request,
    response: Response,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(workflow_protected_transport_target_context_capsule_consumer_subject),
    ],
) -> WorkflowProtectedRuntimeContextUseAuthorizationConsumptionResponse:
    _no_store(response)
    service = cast(
        WorkflowProtectedRuntimeContextUseAuthorizationConsumptionService,
        request.app.state.workflow_protected_runtime_context_use_authorization_consumption_service,
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    try:
        presentation = await service.consume(
            authorization_lease_id=payload.authorization_lease_id,
            policy_id=payload.policy_id,
            policy_version=payload.policy_version,
            irreversible_consumption_acknowledged=(payload.irreversible_consumption_acknowledged),
            idempotency_key=payload.idempotency_key,
            context=WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id=(
                    "decision.workflow-protected-runtime-context-use-authorization-"
                    "consumer-authenticated"
                ),
                requested_at=datetime.now(UTC),
            ),
        )
        if presentation.claim.scope != scope or presentation.result.scope != scope:
            raise RuntimeError(
                "protected runtime-context use-authorization consumption scope mismatch"
            )
        data = WorkflowProtectedRuntimeContextUseAuthorizationConsumptionData.from_domain(
            presentation
        )
    except WorkflowProtectedRuntimeContextUseAuthorizationConsumptionError as error:
        unavailable = "unavailable" in error.code or error.code.endswith(
            "durable_repository_required"
        )
        raise AtlasError(
            status=503 if unavailable else 409,
            code=(
                "workflow_protected_runtime_context_use_authorization_consumption_"
                "service_unavailable"
                if unavailable
                else "authorization_denied"
            ),
            title=(
                "Protected runtime-context use-authorization consumption unavailable"
                if unavailable
                else "Request denied"
            ),
            detail=(
                "The protected authorization-consumption request cannot be completed."
                if unavailable
                else "The current identity or evidence is not authorized for this operation."
            ),
            retryable=unavailable,
        ) from error
    except Exception as error:
        raise AtlasError(
            status=503,
            code=(
                "workflow_protected_runtime_context_use_authorization_consumption_"
                "service_unavailable"
            ),
            title="Protected runtime-context use-authorization consumption unavailable",
            detail="The protected authorization-consumption request cannot be completed.",
            retryable=True,
        ) from error
    return WorkflowProtectedRuntimeContextUseAuthorizationConsumptionResponse(
        data=data,
        meta=_meta(request),
    )


@router.get(
    "/protected-runtime-context-uses",
    response_model=WorkflowProtectedRuntimeContextUseInventoryResponse,
)
async def list_workflow_protected_runtime_context_uses(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_workflow_protected_runtime_context_use_read),
    ],
) -> WorkflowProtectedRuntimeContextUseInventoryResponse:
    del decision
    _no_store(response)
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service = cast(
        WorkflowProtectedRuntimeContextUseService,
        request.app.state.workflow_protected_runtime_context_use_service,
    )
    try:
        presentations = await service.list_presentations(scope=scope, limit=256)
        server_time = await service.repository.get_authoritative_time()
        use_ids = tuple(presentation.attempt.use_id for presentation in presentations)
        if len(use_ids) != len(set(use_ids)) or any(
            presentation.attempt.scope != scope for presentation in presentations
        ):
            raise RuntimeError("protected runtime-context use scope mismatch")
        items = [
            WorkflowProtectedRuntimeContextUseData.from_domain(
                presentation,
                evaluated_at=server_time,
            )
            for presentation in presentations
        ]
        if any(
            item.started_at > server_time
            or (item.completed_at is not None and item.completed_at > server_time)
            for item in items
        ):
            raise RuntimeError("protected runtime-context use time mismatch")
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_protected_runtime_context_use_service_unavailable",
            title="Protected runtime-context use unavailable",
            detail="Runtime-context use evidence is temporarily unavailable.",
            retryable=True,
        ) from error
    return WorkflowProtectedRuntimeContextUseInventoryResponse(
        data=WorkflowProtectedRuntimeContextUseInventoryData(
            uses=items,
            server_time=server_time,
            durable=True,
        ),
        meta=_meta(request),
    )


@router.post(
    "/protected-runtime-context-uses",
    response_model=WorkflowProtectedRuntimeContextUseResponse,
    status_code=201,
)
async def create_workflow_protected_runtime_context_use(
    payload: CreateWorkflowProtectedRuntimeContextUseInput,
    request: Request,
    response: Response,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(workflow_protected_transport_target_context_capsule_consumer_subject),
    ],
) -> WorkflowProtectedRuntimeContextUseResponse:
    _no_store(response)
    service = cast(
        WorkflowProtectedRuntimeContextUseService,
        request.app.state.workflow_protected_runtime_context_use_service,
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    try:
        presentation = await service.use(
            authorization_consumption_result_id=(payload.authorization_consumption_result_id),
            authorization_consumption_result_digest=(
                payload.authorization_consumption_result_digest
            ),
            policy_id=payload.policy_id,
            policy_version=payload.policy_version,
            irreversible_use_acknowledged=payload.irreversible_use_acknowledged,
            uncertainty_no_retry_acknowledged=payload.uncertainty_no_retry_acknowledged,
            idempotency_key=payload.idempotency_key,
            context=WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id="decision.workflow-protected-runtime-context-use-consumer-authenticated",
                requested_at=datetime.now(UTC),
            ),
        )
        server_time = await service.repository.get_authoritative_time()
        if presentation.attempt.scope != scope:
            raise RuntimeError("protected runtime-context use scope mismatch")
        data = WorkflowProtectedRuntimeContextUseData.from_domain(
            presentation,
            evaluated_at=server_time,
        )
    except WorkflowProtectedRuntimeContextUseError as error:
        unavailable = _protected_runtime_context_use_error_is_unavailable(error.code)
        raise AtlasError(
            status=503 if unavailable else 409,
            code=(
                "workflow_protected_runtime_context_use_service_unavailable"
                if unavailable
                else "authorization_denied"
            ),
            title=(
                "Protected runtime-context use unavailable" if unavailable else "Request denied"
            ),
            detail=(
                "The protected context-use request cannot be completed."
                if unavailable
                else "The current identity or evidence is not authorized for this operation."
            ),
            retryable=unavailable,
        ) from error
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_protected_runtime_context_use_service_unavailable",
            title="Protected runtime-context use unavailable",
            detail="The protected context-use request cannot be completed.",
            retryable=True,
        ) from error
    return WorkflowProtectedRuntimeContextUseResponse(data=data, meta=_meta(request))


@router.get(
    "/physical-transport-target-context-capsule-openings",
    response_model=WorkflowProtectedTransportTargetContextCapsuleOpeningInventoryResponse,
)
async def list_workflow_physical_transport_target_context_capsule_openings(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_workflow_target_context_capsule_opening_read),
    ],
) -> WorkflowProtectedTransportTargetContextCapsuleOpeningInventoryResponse:
    del decision
    _no_store(response)
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service = cast(
        WorkflowProtectedTransportTargetContextCapsuleOpeningService,
        request.app.state.workflow_target_context_capsule_opening_service,
    )
    try:
        presentations = await service.list_presentations(scope=scope, limit=256)
        server_time = await service.repository.get_authoritative_time()
        opening_ids = tuple(presentation.attempt.opening_id for presentation in presentations)
        if len(opening_ids) != len(set(opening_ids)) or any(
            presentation.attempt.scope != scope for presentation in presentations
        ):
            raise RuntimeError("target-context capsule opening scope mismatch")
        items = [
            WorkflowProtectedTransportTargetContextCapsuleOpeningData.from_domain(
                presentation.attempt,
                presentation.result,
                evaluated_at=server_time,
            )
            for presentation in presentations
        ]
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_target_context_capsule_opening_service_unavailable",
            title="Workflow target-context capsule opening unavailable",
            detail="Opening metadata is temporarily unavailable.",
            retryable=True,
        ) from error
    return WorkflowProtectedTransportTargetContextCapsuleOpeningInventoryResponse(
        data=WorkflowProtectedTransportTargetContextCapsuleOpeningInventoryData(
            physical_transport_target_context_capsule_openings=items,
            server_time=server_time,
            durable=True,
        ),
        meta=_meta(request),
    )


@router.post(
    "/physical-transport-target-context-capsule-openings",
    response_model=WorkflowProtectedTransportTargetContextCapsuleOpeningResponse,
    status_code=201,
)
async def create_workflow_physical_transport_target_context_capsule_opening(
    payload: CreateWorkflowProtectedTransportTargetContextCapsuleOpeningInput,
    request: Request,
    response: Response,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(workflow_protected_transport_target_context_capsule_consumer_subject),
    ],
) -> WorkflowProtectedTransportTargetContextCapsuleOpeningResponse:
    _no_store(response)
    service = cast(
        WorkflowProtectedTransportTargetContextCapsuleOpeningService,
        request.app.state.workflow_target_context_capsule_opening_service,
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    try:
        presentation = await service.open(
            authorization_lease_id=payload.authorization_lease_id,
            authorization_lease_digest=payload.authorization_lease_digest,
            policy_id=payload.policy_id,
            policy_version=payload.policy_version,
            irreversible_consumption_acknowledged=(payload.irreversible_consumption_acknowledged),
            uncertain_outcome_requires_new_authorization_acknowledged=(
                payload.uncertain_outcome_requires_new_authorization_acknowledged
            ),
            idempotency_key=payload.idempotency_key,
            context=WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=(WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE),
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id=(
                    "decision.workflow-protected-transport-target-context-capsule-consumer-"
                    "authenticated"
                ),
                requested_at=datetime.now(UTC),
            ),
        )
        server_time = await service.repository.get_authoritative_time()
        if presentation.attempt.scope != scope:
            raise RuntimeError("target-context capsule opening scope mismatch")
        data = WorkflowProtectedTransportTargetContextCapsuleOpeningData.from_domain(
            presentation.attempt,
            presentation.result,
            evaluated_at=server_time,
        )
    except WorkflowProtectedTransportTargetContextCapsuleOpeningError as error:
        unavailable = "unavailable" in error.code or error.code.endswith(
            "durable_repository_required"
        )
        raise AtlasError(
            status=503 if unavailable else 422,
            code=(
                "workflow_target_context_capsule_opening_service_unavailable"
                if unavailable
                else "authorization_denied"
            ),
            title=(
                "Workflow target-context capsule opening unavailable"
                if unavailable
                else "Request denied"
            ),
            detail=(
                "The sealed capsule opening request cannot be completed."
                if unavailable
                else "The current identity or evidence is not authorized for this operation."
            ),
            retryable=unavailable,
        ) from error
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_target_context_capsule_opening_service_unavailable",
            title="Workflow target-context capsule opening unavailable",
            detail="The sealed capsule opening request cannot be completed.",
            retryable=True,
        ) from error
    return WorkflowProtectedTransportTargetContextCapsuleOpeningResponse(
        data=data,
        meta=_meta(request),
    )


@router.get(
    "/transport-compatibility-admissions",
    response_model=WorkflowEventTransportCompatibilityAdmissionInventoryResponse,
)
async def get_workflow_transport_compatibility_admission(
    logical_channel_binding_id: Annotated[
        str, Query(min_length=3, max_length=128, pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")
    ],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_workflow_transport_compatibility_admission_read),
    ],
) -> WorkflowEventTransportCompatibilityAdmissionInventoryResponse:
    del decision
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    service: WorkflowEventTransportCompatibilityAdmissionService = (
        request.app.state.workflow_event_transport_compatibility_admission_service
    )
    try:
        admissions = await service.repository.list_transport_compatibility_admissions_by_binding(
            logical_channel_binding_id=logical_channel_binding_id
        )
    except Exception as error:
        raise AtlasError(
            status=503,
            code="workflow_transport_compatibility_admission_repository_unavailable",
            title="Workflow transport compatibility admission service unavailable",
            detail="Transport compatibility admission metadata is unavailable.",
            retryable=True,
        ) from error
    policy = service.policy
    if len(admissions) > 256 or any(
        not _transport_compatibility_admission_matches_request(
            admission,
            logical_channel_binding_id=logical_channel_binding_id,
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            policy_digest=policy.canonical_digest,
            scope=scope,
        )
        for admission in admissions
    ):
        raise AtlasError(
            status=503,
            code="workflow_transport_compatibility_admission_repository_scope_violation",
            title="Workflow transport compatibility admission service unavailable",
            detail="Transport compatibility admission metadata is unavailable.",
            retryable=True,
        )
    _no_store(response)
    return WorkflowEventTransportCompatibilityAdmissionInventoryResponse(
        data=WorkflowEventTransportCompatibilityAdmissionInventoryData(
            logical_channel_binding_id=logical_channel_binding_id,
            transport_compatibility_admissions=[
                WorkflowEventTransportCompatibilityAdmissionData.from_domain(admission)
                for admission in admissions
            ],
            durable=service.durable,
        ),
        meta=_meta(request),
    )


@router.post(
    "/transport-compatibility-admissions",
    response_model=WorkflowEventTransportCompatibilityAdmissionResponse,
    status_code=201,
)
async def create_workflow_transport_compatibility_admission(
    payload: CreateWorkflowEventTransportCompatibilityAdmissionInput,
    request: Request,
    response: Response,
    subject: Annotated[
        AuthenticatedSubject,
        Depends(workflow_transport_compatibility_admitter_subject),
    ],
) -> WorkflowEventTransportCompatibilityAdmissionResponse:
    service: WorkflowEventTransportCompatibilityAdmissionService = (
        request.app.state.workflow_event_transport_compatibility_admission_service
    )
    scope = WorkflowScope(
        organization_id=subject.organization_id,
        environment_id=f"environment.{request.app.state.settings.environment}",
        site_id="site.local",
    )
    try:
        admission = await service.admit(
            logical_channel_binding_id=payload.logical_channel_binding_id,
            logical_channel_binding_digest=payload.logical_channel_binding_digest,
            transport_profile_snapshot_id=payload.transport_profile_snapshot_id,
            transport_profile_snapshot_digest=payload.transport_profile_snapshot_digest,
            policy_id=payload.policy_id,
            policy_version=payload.policy_version,
            policy_digest=payload.policy_digest,
            idempotency_key=payload.idempotency_key,
            context=WorkflowTransportCompatibilityAdmitterContext(
                subject_id=subject.subject_id,
                actor_type=subject.kind.value,
                authentication_method=subject.authentication_method.value,
                credential_audience=WORKFLOW_TRANSPORT_COMPATIBILITY_ADMITTER_AUDIENCE,
                scope=scope,
                correlation_id=str(request.state.correlation_id),
                decision_id="decision.workflow-transport-compatibility-admitter-authenticated",
                requested_at=datetime.now(UTC),
            ),
        )
    except WorkflowEventTransportCompatibilityAdmissionError as error:
        _raise_transport_compatibility_admission(error)
    return _transport_compatibility_admission_response(admission, request, response)
