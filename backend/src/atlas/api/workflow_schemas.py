from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from atlas.api.schemas import ResponseMeta
from atlas.modules.workflows.application.protected_runtime_context_injection_authorization_ports import (  # noqa: E501
    WorkflowProtectedRuntimeContextInjectionAuthorizationPresentation,
)
from atlas.modules.workflows.application.protected_runtime_context_injection_consumptions import (
    WorkflowProtectedRuntimeContextInjectionConsumptionPresentation,
)
from atlas.modules.workflows.application.protected_runtime_context_use_authorization_consumption_ports import (  # noqa: E501
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPresentation,
)
from atlas.modules.workflows.application.protected_runtime_context_use_authorization_ports import (
    WorkflowProtectedRuntimeContextUseAuthorizationPresentation,
)
from atlas.modules.workflows.application.protected_runtime_context_uses import (
    WorkflowProtectedRuntimeContextUsePresentation,
)
from atlas.modules.workflows.application.protected_runtime_process_creation_authorization_ports import (  # noqa: E501
    WorkflowProtectedRuntimeProcessCreationAuthorizationPresentation,
)
from atlas.modules.workflows.application.protected_runtime_process_creation_consumptions import (
    WorkflowProtectedRuntimeProcessCreationConsumptionPresentation,
)
from atlas.modules.workflows.application.protected_runtime_process_scheduling_consumptions import (
    WorkflowProtectedRuntimeProcessSchedulingConsumptionPresentation,
)
from atlas.modules.workflows.application.protected_runtime_readiness_authorization_ports import (
    WorkflowProtectedRuntimeReadinessAuthorizationPresentation,
)
from atlas.modules.workflows.application.protected_runtime_readiness_consumptions import (
    WorkflowProtectedRuntimeReadinessConsumptionPresentation,
)
from atlas.modules.workflows.application.protected_runtime_start_authorization_ports import (
    WorkflowProtectedRuntimeStartAuthorizationPresentation,
)
from atlas.modules.workflows.domain import (
    EventPhysicalTransportCredentialAssignmentSnapshot,
    EventPhysicalTransportProfileSnapshot,
    EventPhysicalTransportRouteSnapshot,
    WorkflowDefinition,
    WorkflowDispatchEventEnvelope,
    WorkflowDispatchIntent,
    WorkflowDispatchOutboxEntry,
    WorkflowEventByteArtifact,
    WorkflowEventLogicalChannelBinding,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease,
    WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaim,
    WorkflowEventPhysicalTransportCredentialAssignmentBinding,
    WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission,
    WorkflowEventPhysicalTransportCredentialMaterializationAttempt,
    WorkflowEventPhysicalTransportCredentialMaterializationResult,
    WorkflowEventPhysicalTransportCredentialMaterializationResultState,
    WorkflowEventPhysicalTransportEndpointMaterializationAttempt,
    WorkflowEventPhysicalTransportEndpointMaterializationResult,
    WorkflowEventPhysicalTransportEndpointMaterializationResultState,
    WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease,
    WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaim,
    WorkflowEventPhysicalTransportRouteBinding,
    WorkflowEventPhysicalTransportRouteFreshnessAdmission,
    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningAttempt,
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult,
    WorkflowEventPhysicalTransportTargetContextBinding,
    WorkflowEventTransportAdmission,
    WorkflowEventTransportCompatibilityAdmission,
    WorkflowExecutionAttempt,
    WorkflowExecutionRun,
    WorkflowOrchestrationLease,
    WorkflowOutboxPublicationLease,
    WorkflowProtectedResidentContextAccessAuthorizationLease,
    WorkflowProtectedResidentContextAccessConsumptionAttempt,
    WorkflowProtectedResidentContextAccessConsumptionResult,
    WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseState,
    WorkflowProtectedRuntimeContextInjectionConsumptionAttempt,
    WorkflowProtectedRuntimeContextInjectionConsumptionResult,
    WorkflowProtectedRuntimeContextUseAuthorizationLeaseState,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAttempt,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease,
    WorkflowProtectedTransportTargetContextCapsuleHandoffResult,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAttempt,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease,
    WorkflowProtectedTransportTargetContextCapsuleOpeningResult,
    WorkflowRunPlan,
    code_owned_workflow_protected_resident_context_access_authorization_policy,
    code_owned_workflow_protected_runtime_context_injection_authorization_policy,
    code_owned_workflow_protected_runtime_context_use_authorization_policy,
)
from atlas.modules.workflows.domain.protected_runtime_context_use_domain import (
    WorkflowProtectedRuntimeContextUseAttempt,
    WorkflowProtectedRuntimeContextUseResult,
)
from atlas.modules.workflows.domain.protected_runtime_context_use_domain import (
    WorkflowProtectedRuntimeContextUseResultState as UseResultState,
)
from atlas.modules.workflows.domain.protected_runtime_process_creation_authorization_domain import (
    WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseState,
    code_owned_workflow_protected_runtime_process_creation_authorization_policy,
)
from atlas.modules.workflows.domain.protected_runtime_readiness_authorization_domain import (
    WorkflowProtectedRuntimeReadinessAuthorizationLeaseState,
    code_owned_workflow_protected_runtime_readiness_authorization_policy,
)
from atlas.modules.workflows.domain.protected_runtime_start_authorization_domain import (
    WorkflowProtectedRuntimeStartAuthorizationLeaseState,
    code_owned_workflow_protected_runtime_start_authorization_policy,
)
from atlas.modules.workflows.domain.protected_runtime_start_consumption_domain import (
    WorkflowProtectedRuntimeStartConsumptionAttempt,
    WorkflowProtectedRuntimeStartConsumptionResult,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,239}$"


class CreateWorkflowPlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.workflow-run-plan-create-input.v1"]
    definition_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    definition_version: int = Field(ge=1)
    target_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    target_type: Literal["storage"]
    inputs: dict[str, object]
    acknowledged_planning_only_no_execution_authority: Literal[True]


class CancelWorkflowPlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.workflow-run-plan-cancellation-input.v1"]
    reason: str = Field(min_length=1, max_length=500)
    acknowledge_no_external_undo: Literal[True]


class AcquireWorkflowOrchestrationLeaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.workflow-orchestration-lease-acquire-input.v1"]
    plan_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    target_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    target_type: Literal["storage"]
    lease_duration_seconds: int = Field(ge=30, le=300)
    acknowledged_coordination_only_no_execution_authority: Literal[True]


class WorkflowOrchestrationLeaseMutationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    target_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    target_type: Literal["storage"]
    lease_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    fencing_token: int = Field(ge=1)
    acknowledged_coordination_only_no_execution_authority: Literal[True]


class HeartbeatWorkflowOrchestrationLeaseInput(WorkflowOrchestrationLeaseMutationInput):
    schema_version: Literal["atlas.workflow-orchestration-lease-heartbeat-input.v1"]
    lease_duration_seconds: int = Field(ge=30, le=300)


class ReleaseWorkflowOrchestrationLeaseInput(WorkflowOrchestrationLeaseMutationInput):
    schema_version: Literal["atlas.workflow-orchestration-lease-release-input.v1"]


class MaterializeWorkflowRunInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.workflow-run-materialization-input.v1"]
    plan_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    target_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    target_type: Literal["storage"]
    lease_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    lease_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    fencing_token: int = Field(ge=1)
    acknowledged_materialization_only_no_dispatch_authority: Literal[True]


class MaterializeWorkflowAttemptInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.workflow-attempt-materialization-input.v1"]
    plan_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    run_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    step_run_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    target_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    target_type: Literal["storage"]
    lease_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    lease_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    fencing_token: int = Field(ge=1)
    acknowledged_attempt_only_no_queue_dispatch_or_execution_authority: Literal[True]


class StageWorkflowDispatchIntentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.workflow-dispatch-intent-staging-input.v1"]
    plan_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    run_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    step_run_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    step_run_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    attempt_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    target_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    target_type: Literal["storage"]
    lease_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    lease_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    fencing_token: int = Field(ge=1)
    acknowledged_staging_only_no_publication_delivery_dispatch_or_execution_authority: Literal[True]


class AcquireWorkflowOutboxPublicationLeaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.workflow-outbox-publication-lease-acquire-input.v1"]
    outbox_entry_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    target_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    target_type: Literal["storage"]
    lease_duration_seconds: int = Field(ge=30, le=300)
    acknowledged_coordination_only_no_publication_delivery_dispatch_or_execution_authority: Literal[
        True
    ]


class WorkflowOutboxPublicationLeaseMutationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outbox_entry_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    target_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    target_type: Literal["storage"]
    publication_lease_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    publication_fencing_token: int = Field(ge=1)
    acknowledged_coordination_only_no_publication_delivery_dispatch_or_execution_authority: Literal[
        True
    ]


class HeartbeatWorkflowOutboxPublicationLeaseInput(WorkflowOutboxPublicationLeaseMutationInput):
    schema_version: Literal["atlas.workflow-outbox-publication-lease-heartbeat-input.v1"]
    lease_duration_seconds: int = Field(ge=30, le=300)


class ReleaseWorkflowOutboxPublicationLeaseInput(WorkflowOutboxPublicationLeaseMutationInput):
    schema_version: Literal["atlas.workflow-outbox-publication-lease-release-input.v1"]


class PrepareWorkflowDispatchEventEnvelopeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.workflow-dispatch-event-envelope-prepare-input.v1"]
    outbox_entry_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    publication_lease_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    publication_fencing_token: int = Field(ge=1)
    acknowledged_preparation_only_no_publication_delivery_dispatch_or_execution_authority: Literal[
        True
    ]


class AdmitWorkflowEventTransportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.workflow-event-transport-admission-input.v1"]
    outbox_entry_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    event_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    policy_id: Literal["policy.workflow-event-transport-admission"]
    policy_version: Literal["1.0"]
    policy_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    publication_lease_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    publication_fencing_token: int = Field(ge=1)
    acknowledged_admission_only_no_publication_delivery_dispatch_or_execution_authority: Literal[
        True
    ]


class MaterializeWorkflowEventByteArtifactInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.workflow-event-byte-artifact-materialization-input.v1"]
    outbox_entry_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    event_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    transport_admission_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    policy_id: Literal["policy.workflow-event-transport-admission"]
    policy_version: Literal["1.0"]
    policy_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    publication_lease_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    publication_fencing_token: int = Field(ge=1)
    acknowledged_materialization_only_no_publication_delivery_dispatch_or_execution_authority: (
        Literal[True]
    )


class BindWorkflowEventLogicalChannelInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.workflow-event-logical-channel-binding-input.v1"]
    byte_artifact_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    content_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    policy_id: Literal["policy.workflow-event-logical-channel"]
    policy_version: Literal["1.0"]
    policy_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    publication_lease_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    publication_fencing_token: int = Field(ge=1)
    acknowledged_binding_only_no_publication_delivery_dispatch_or_execution_authority: Literal[True]


class WorkflowStepDefinitionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    ordinal: int
    title: str
    kind: str
    capability_class: str
    timeout_seconds: int
    depends_on: list[str]


class WorkflowDefinitionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    definition_id: str
    version: int
    title: str
    purpose: str
    input_schema_version: str
    definition_digest: str
    steps: list[WorkflowStepDefinitionData]

    @classmethod
    def from_domain(cls, definition: WorkflowDefinition) -> WorkflowDefinitionData:
        return cls(
            definition_id=definition.definition_id,
            version=definition.version,
            title=definition.title,
            purpose=definition.purpose,
            input_schema_version=definition.input_schema_version,
            definition_digest=definition.definition_digest,
            steps=[
                WorkflowStepDefinitionData(
                    step_id=step.step_id,
                    ordinal=step.ordinal,
                    title=step.title,
                    kind=step.kind.value,
                    capability_class=step.capability_class.value,
                    timeout_seconds=step.timeout_seconds,
                    depends_on=list(step.depends_on),
                )
                for step in definition.steps
            ],
        )


class WorkflowPlanStepData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    ordinal: int
    kind: str
    capability_class: str
    state: Literal["not_started"]


class WorkflowPlanAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    worker_dispatch_authorized: Literal[False]
    connector_invocation_authorized: Literal[False]
    approval_creation_authorized: Literal[False]
    signal_delivery_authorized: Literal[False]
    retry_authorized: Literal[False]
    itsm_mutation_authorized: Literal[False]
    runbook_execution_authorized: Literal[False]
    infrastructure_change_authorized: Literal[False]


class WorkflowScopeData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: str
    environment_id: str
    site_id: str


class WorkflowOrchestrationLeaseData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lease_id: str
    plan_id: str
    plan_digest: str
    scope: WorkflowScopeData
    target_id: str
    target_type: Literal["storage"]
    worker_subject_id: str
    acquired_at: datetime
    last_heartbeat_at: datetime
    expires_at: datetime
    fencing_token: int
    state: Literal["active", "released"]
    effective_state: Literal["active", "expired", "released"]
    canonical_digest: str
    grants_execution_authority: Literal[False]

    @classmethod
    def from_domain(
        cls,
        lease: WorkflowOrchestrationLease,
        *,
        requested_at: datetime,
    ) -> WorkflowOrchestrationLeaseData:
        return cls.model_validate(
            lease.canonical_value()
            | {
                "effective_state": lease.effective_state(requested_at=requested_at).value,
                "grants_execution_authority": False,
            }
        )


class WorkflowOrchestrationLeaseStatusData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str
    lease: WorkflowOrchestrationLeaseData | None
    server_time: datetime
    durable: bool


class WorkflowOrchestrationLeaseResponse(BaseModel):
    data: WorkflowOrchestrationLeaseData
    meta: ResponseMeta


class WorkflowOrchestrationLeaseStatusResponse(BaseModel):
    data: WorkflowOrchestrationLeaseStatusData
    meta: ResponseMeta


class WorkflowOutboxPublicationLeaseData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    publication_lease_id: str
    outbox_entry_id: str
    outbox_entry_digest: str
    dispatch_intent_id: str
    dispatch_intent_digest: str
    plan_id: str
    plan_digest: str
    run_id: str
    run_digest: str
    step_run_id: str
    step_run_digest: str
    step_id: str
    attempt_id: str
    attempt_digest: str
    attempt_number: Literal[1]
    scope: WorkflowScopeData
    target_id: str
    target_type: Literal["storage"]
    orchestration_lease_id: str
    orchestration_lease_digest: str
    orchestration_fencing_token: int
    publisher_subject_id: str
    acquired_at: datetime
    last_heartbeat_at: datetime
    expires_at: datetime
    publication_fencing_token: int
    state: Literal["active", "released"]
    effective_state: Literal["active", "expired", "released"]
    authority: WorkflowPlanAuthorityData
    grants_publication_authority: Literal[False]
    grants_delivery_authority: Literal[False]
    grants_dispatch_authority: Literal[False]
    grants_execution_authority: Literal[False]
    canonical_digest: str

    @classmethod
    def from_domain(
        cls,
        lease: WorkflowOutboxPublicationLease,
        *,
        requested_at: datetime,
    ) -> WorkflowOutboxPublicationLeaseData:
        return cls.model_validate(
            lease.canonical_value()
            | {
                "effective_state": lease.effective_state(requested_at=requested_at).value,
                "grants_publication_authority": False,
                "grants_delivery_authority": False,
                "grants_dispatch_authority": False,
                "grants_execution_authority": False,
            }
        )


class WorkflowOutboxPublicationLeaseInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outbox_entry_id: str
    publication_leases: list[WorkflowOutboxPublicationLeaseData]
    server_time: datetime
    durable: bool


class WorkflowOutboxPublicationLeaseResponse(BaseModel):
    data: WorkflowOutboxPublicationLeaseData
    meta: ResponseMeta


class WorkflowOutboxPublicationLeaseInventoryResponse(BaseModel):
    data: WorkflowOutboxPublicationLeaseInventoryData
    meta: ResponseMeta


class WorkflowDispatchEventPayloadData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outbox_entry_id: str
    outbox_entry_digest: str
    dispatch_intent_id: str
    dispatch_intent_digest: str
    plan_id: str
    plan_digest: str
    run_id: str
    run_digest: str
    step_run_id: str
    step_run_digest: str
    step_id: str
    attempt_id: str
    attempt_digest: str
    attempt_number: Literal[1]
    scope: WorkflowScopeData
    target_id: str
    target_type: Literal["storage"]


class WorkflowDispatchEventAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]


class WorkflowDispatchEventEnvelopeData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: Literal["WorkflowStepDispatchRequested"]
    event_version: Literal["1.0"]
    occurred_at: datetime
    recorded_at: datetime
    producer: str
    producer_version: str
    subject_type: Literal["workflow-execution-attempt"]
    subject_id: str
    organization_id: str
    environment_id: str
    correlation_id: str
    causation_id: str
    workflow_id: str
    data_classification: Literal["internal"]
    schema_uri: Literal["urn:project-atlas:event:workflow-step-dispatch-requested:1.0"]
    payload: WorkflowDispatchEventPayloadData
    extensions: dict[str, str]
    orchestration_lease_id: str
    orchestration_lease_digest: str
    orchestration_fencing_token: int
    publication_lease_id: str
    publication_lease_digest: str
    publication_fencing_token: int
    publisher_subject_id: str
    prepared_at: datetime
    state: Literal["prepared"]
    authority: WorkflowDispatchEventAuthorityData
    grants_publication_authority: Literal[False]
    grants_delivery_authority: Literal[False]
    grants_dispatch_authority: Literal[False]
    grants_execution_authority: Literal[False]
    canonical_digest: str

    @classmethod
    def from_domain(
        cls, envelope: WorkflowDispatchEventEnvelope
    ) -> WorkflowDispatchEventEnvelopeData:
        return cls.model_validate(
            envelope.canonical_value()
            | {
                "grants_publication_authority": False,
                "grants_delivery_authority": False,
                "grants_dispatch_authority": False,
                "grants_execution_authority": False,
            }
        )


class WorkflowDispatchEventEnvelopeInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outbox_entry_id: str
    event_envelopes: list[WorkflowDispatchEventEnvelopeData] = Field(max_length=1)
    durable: bool


class WorkflowDispatchEventEnvelopeResponse(BaseModel):
    data: WorkflowDispatchEventEnvelopeData
    meta: ResponseMeta


class WorkflowDispatchEventEnvelopeInventoryResponse(BaseModel):
    data: WorkflowDispatchEventEnvelopeInventoryData
    meta: ResponseMeta


class WorkflowEventTransportAdmissionPolicyData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: str
    policy_version: Literal["1.0"]
    policy_digest: str
    allowed_event_type: Literal["WorkflowStepDispatchRequested"]
    allowed_event_version: Literal["1.0"]
    allowed_schema_uri: Literal["urn:project-atlas:event:workflow-step-dispatch-requested:1.0"]
    allowed_data_classification: Literal["internal"]
    representation_name: Literal["canonical-json"]
    encoding: Literal["utf-8"]
    maximum_canonical_byte_count: int = Field(ge=1, le=1_048_576)


class WorkflowEventTransportAdmissionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transport_admission_id: str
    event_id: str
    event_digest: str
    outbox_entry_id: str
    outbox_entry_digest: str
    dispatch_intent_id: str
    dispatch_intent_digest: str
    plan_id: str
    plan_digest: str
    run_id: str
    run_digest: str
    step_run_id: str
    step_run_digest: str
    step_id: str
    attempt_id: str
    attempt_digest: str
    attempt_number: Literal[1]
    scope: WorkflowScopeData
    target_id: str
    target_type: Literal["storage"]
    policy: WorkflowEventTransportAdmissionPolicyData
    canonical_byte_count: int = Field(ge=1)
    publisher_subject_id: str
    orchestration_lease_id: str
    orchestration_lease_digest: str
    orchestration_fencing_token: int = Field(ge=1)
    publication_lease_id: str
    publication_lease_digest: str
    publication_fencing_token: int = Field(ge=1)
    admitted_at: datetime
    state: Literal["admitted"]
    authority: WorkflowDispatchEventAuthorityData
    grants_publication_authority: Literal[False]
    grants_delivery_authority: Literal[False]
    grants_dispatch_authority: Literal[False]
    grants_execution_authority: Literal[False]
    canonical_digest: str

    @classmethod
    def from_domain(
        cls, admission: WorkflowEventTransportAdmission
    ) -> WorkflowEventTransportAdmissionData:
        return cls.model_validate(
            {
                "transport_admission_id": admission.admission_id,
                "event_id": admission.event_id,
                "event_digest": admission.event_digest,
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
                "scope": admission.scope.canonical_value(),
                "target_id": admission.target_id,
                "target_type": admission.target_type,
                "policy": {
                    "policy_id": admission.policy_id,
                    "policy_version": admission.policy_version,
                    "policy_digest": admission.policy_digest,
                    "allowed_event_type": admission.event_type,
                    "allowed_event_version": admission.event_version,
                    "allowed_schema_uri": admission.schema_uri,
                    "allowed_data_classification": admission.data_classification,
                    "representation_name": admission.representation_name,
                    "encoding": admission.encoding,
                    "maximum_canonical_byte_count": (admission.maximum_canonical_byte_count),
                },
                "canonical_byte_count": admission.canonical_byte_count,
                "publisher_subject_id": admission.publisher_subject_id,
                "orchestration_lease_id": admission.orchestration_lease_id,
                "orchestration_lease_digest": admission.orchestration_lease_digest,
                "orchestration_fencing_token": admission.orchestration_fencing_token,
                "publication_lease_id": admission.publication_lease_id,
                "publication_lease_digest": admission.publication_lease_digest,
                "publication_fencing_token": admission.publication_fencing_token,
                "admitted_at": admission.admitted_at,
                "state": admission.state.value,
                "authority": admission.authority.canonical_value(),
                "grants_publication_authority": False,
                "grants_delivery_authority": False,
                "grants_dispatch_authority": False,
                "grants_execution_authority": False,
                "canonical_digest": admission.canonical_digest,
            }
        )


class WorkflowEventTransportAdmissionInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    transport_admissions: list[WorkflowEventTransportAdmissionData] = Field(max_length=1)
    durable: bool


class WorkflowEventTransportAdmissionResponse(BaseModel):
    data: WorkflowEventTransportAdmissionData
    meta: ResponseMeta


class WorkflowEventTransportAdmissionInventoryResponse(BaseModel):
    data: WorkflowEventTransportAdmissionInventoryData
    meta: ResponseMeta


class WorkflowEventByteArtifactData(BaseModel):
    """Minimized artifact metadata; canonical bytes and event payload stay server-side."""

    model_config = ConfigDict(extra="forbid")

    byte_artifact_id: str
    transport_admission_id: str
    transport_admission_digest: str
    event_id: str
    event_digest: str
    outbox_entry_id: str
    outbox_entry_digest: str
    dispatch_intent_id: str
    dispatch_intent_digest: str
    plan_id: str
    plan_digest: str
    run_id: str
    run_digest: str
    step_run_id: str
    step_run_digest: str
    step_id: str
    attempt_id: str
    attempt_digest: str
    attempt_number: Literal[1]
    scope: WorkflowScopeData
    target_id: str
    target_type: Literal["storage"]
    policy_id: Literal["policy.workflow-event-transport-admission"]
    policy_version: Literal["1.0"]
    policy_digest: str
    representation_name: Literal["canonical-json"]
    encoding: Literal["utf-8"]
    media_type: Literal["application/json"]
    byte_count: int = Field(ge=1)
    content_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    publisher_subject_id: str
    orchestration_lease_id: str
    orchestration_lease_digest: str
    orchestration_fencing_token: int = Field(ge=1)
    publication_lease_id: str
    publication_lease_digest: str
    publication_fencing_token: int = Field(ge=1)
    materialized_at: datetime
    state: Literal["materialized"]
    authority: WorkflowDispatchEventAuthorityData
    grants_publication_authority: Literal[False]
    grants_delivery_authority: Literal[False]
    grants_dispatch_authority: Literal[False]
    grants_execution_authority: Literal[False]
    canonical_digest: str

    @classmethod
    def from_domain(cls, artifact: WorkflowEventByteArtifact) -> WorkflowEventByteArtifactData:
        return cls.model_validate(
            {
                "byte_artifact_id": artifact.artifact_id,
                "transport_admission_id": artifact.admission_id,
                "transport_admission_digest": artifact.admission_digest,
                "event_id": artifact.event_id,
                "event_digest": artifact.event_digest,
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
                "scope": artifact.scope.canonical_value(),
                "target_id": artifact.target_id,
                "target_type": artifact.target_type,
                "policy_id": artifact.policy_id,
                "policy_version": artifact.policy_version,
                "policy_digest": artifact.policy_digest,
                "representation_name": artifact.representation_name,
                "encoding": artifact.encoding,
                "media_type": "application/json",
                "byte_count": artifact.canonical_byte_count,
                "content_sha256": artifact.content_sha256,
                "publisher_subject_id": artifact.publisher_subject_id,
                "orchestration_lease_id": artifact.orchestration_lease_id,
                "orchestration_lease_digest": artifact.orchestration_lease_digest,
                "orchestration_fencing_token": artifact.orchestration_fencing_token,
                "publication_lease_id": artifact.publication_lease_id,
                "publication_lease_digest": artifact.publication_lease_digest,
                "publication_fencing_token": artifact.publication_fencing_token,
                "materialized_at": artifact.materialized_at,
                "state": artifact.state.value,
                "authority": artifact.authority.canonical_value(),
                "grants_publication_authority": False,
                "grants_delivery_authority": False,
                "grants_dispatch_authority": False,
                "grants_execution_authority": False,
                "canonical_digest": artifact.canonical_digest,
            }
        )


class WorkflowEventByteArtifactInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transport_admission_id: str
    byte_artifacts: list[WorkflowEventByteArtifactData] = Field(max_length=1)
    durable: bool


class WorkflowEventByteArtifactResponse(BaseModel):
    data: WorkflowEventByteArtifactData
    meta: ResponseMeta


class WorkflowEventByteArtifactInventoryResponse(BaseModel):
    data: WorkflowEventByteArtifactInventoryData
    meta: ResponseMeta


class WorkflowEventLogicalChannelBindingData(BaseModel):
    """Minimized logical contract metadata; physical transport stays unselected."""

    model_config = ConfigDict(extra="forbid")

    logical_channel_binding_id: str
    byte_artifact_id: str
    byte_artifact_digest: str
    content_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    byte_count: int = Field(ge=1, le=65_536)
    transport_admission_id: str
    transport_admission_digest: str
    event_id: str
    event_digest: str
    outbox_entry_id: str
    outbox_entry_digest: str
    dispatch_intent_id: str
    dispatch_intent_digest: str
    plan_id: str
    plan_digest: str
    run_id: str
    run_digest: str
    step_run_id: str
    step_run_digest: str
    step_id: str
    attempt_id: str
    attempt_digest: str
    attempt_number: Literal[1]
    scope: WorkflowScopeData
    target_id: str
    target_type: Literal["storage"]
    policy_id: Literal["policy.workflow-event-logical-channel"]
    policy_version: Literal["1.0"]
    policy_digest: str
    logical_channel_id: Literal["channel.workflow-dispatch.internal"]
    logical_channel_version: Literal["1.0"]
    delivery_semantics: Literal["at-least-once"]
    durability_required: Literal[True]
    ordering_key_kind: Literal["workflow-run"]
    ordering_key_value: str
    retention_class: Literal["workflow-operational"]
    publisher_subject_id: str
    orchestration_lease_id: str
    orchestration_lease_digest: str
    orchestration_fencing_token: int = Field(ge=1)
    publication_lease_id: str
    publication_lease_digest: str
    publication_fencing_token: int = Field(ge=1)
    bound_at: datetime
    state: Literal["bound"]
    authority: WorkflowDispatchEventAuthorityData
    grants_publication_authority: Literal[False]
    grants_delivery_authority: Literal[False]
    grants_dispatch_authority: Literal[False]
    grants_execution_authority: Literal[False]
    canonical_digest: str

    @classmethod
    def from_domain(
        cls, binding: WorkflowEventLogicalChannelBinding
    ) -> WorkflowEventLogicalChannelBindingData:
        return cls.model_validate(
            {
                "logical_channel_binding_id": binding.binding_id,
                "byte_artifact_id": binding.artifact_id,
                "byte_artifact_digest": binding.artifact_digest,
                "content_sha256": binding.content_sha256,
                "byte_count": binding.canonical_byte_count,
                "transport_admission_id": binding.admission_id,
                "transport_admission_digest": binding.admission_digest,
                "event_id": binding.event_id,
                "event_digest": binding.event_digest,
                "outbox_entry_id": binding.outbox_entry_id,
                "outbox_entry_digest": binding.outbox_entry_digest,
                "dispatch_intent_id": binding.dispatch_intent_id,
                "dispatch_intent_digest": binding.dispatch_intent_digest,
                "plan_id": binding.plan_id,
                "plan_digest": binding.plan_digest,
                "run_id": binding.run_id,
                "run_digest": binding.run_digest,
                "step_run_id": binding.step_run_id,
                "step_run_digest": binding.step_run_digest,
                "step_id": binding.step_id,
                "attempt_id": binding.attempt_id,
                "attempt_digest": binding.attempt_digest,
                "attempt_number": binding.attempt_number,
                "scope": binding.scope.canonical_value(),
                "target_id": binding.target_id,
                "target_type": binding.target_type,
                "policy_id": binding.policy_id,
                "policy_version": binding.policy_version,
                "policy_digest": binding.policy_digest,
                "logical_channel_id": binding.logical_channel_id,
                "logical_channel_version": binding.logical_channel_version,
                "delivery_semantics": binding.delivery_semantics,
                "durability_required": binding.durability_required,
                "ordering_key_kind": binding.ordering_key_kind,
                "ordering_key_value": binding.ordering_key_value,
                "retention_class": binding.retention_class,
                "publisher_subject_id": binding.publisher_subject_id,
                "orchestration_lease_id": binding.orchestration_lease_id,
                "orchestration_lease_digest": binding.orchestration_lease_digest,
                "orchestration_fencing_token": binding.orchestration_fencing_token,
                "publication_lease_id": binding.publication_lease_id,
                "publication_lease_digest": binding.publication_lease_digest,
                "publication_fencing_token": binding.publication_fencing_token,
                "bound_at": binding.bound_at,
                "state": binding.state.value,
                "authority": binding.authority.canonical_value(),
                "grants_publication_authority": False,
                "grants_delivery_authority": False,
                "grants_dispatch_authority": False,
                "grants_execution_authority": False,
                "canonical_digest": binding.canonical_digest,
            }
        )


class WorkflowEventLogicalChannelBindingInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    byte_artifact_id: str
    logical_channel_bindings: list[WorkflowEventLogicalChannelBindingData] = Field(max_length=1)
    durable: bool


class WorkflowEventLogicalChannelBindingResponse(BaseModel):
    data: WorkflowEventLogicalChannelBindingData
    meta: ResponseMeta


class WorkflowEventLogicalChannelBindingInventoryResponse(BaseModel):
    data: WorkflowEventLogicalChannelBindingInventoryData
    meta: ResponseMeta


class CreateEventPhysicalTransportProfileSnapshotInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_profile_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    source_profile_revision: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    source_profile_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class EventPhysicalTransportProfileSnapshotAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_selection_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]


class EventPhysicalTransportEventContractData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: Literal["WorkflowStepDispatchRequested"]
    event_version: Literal["1.0"]
    schema_uri: Literal["urn:project-atlas:event:workflow-step-dispatch-requested:1.0"]


class EventPhysicalTransportProfileSnapshotData(BaseModel):
    """Minimized deployment capability evidence without route or credential metadata."""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    transport_profile_id: str
    transport_profile_revision: str
    source_profile_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    deployment_release_id: str
    deployment_profile: Literal["developer", "lab", "enterprise-test", "production", "offline"]
    scope: WorkflowScopeData
    transport_resource_id: str
    transport_resource_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    transport_implementation_id: str
    transport_implementation_version: str
    adapter_contract_id: str
    adapter_contract_version: str
    adapter_contract_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    supported_event_contracts: list[EventPhysicalTransportEventContractData]
    supported_classifications: list[str]
    supported_representations: list[str]
    supported_encodings: list[str]
    supported_delivery_semantics: list[str]
    durable_delivery_supported: bool
    supported_ordering_key_kinds: list[str]
    supported_retention_classes: list[str]
    maximum_message_byte_count: int = Field(ge=1, le=16_777_216)
    transport_encryption_required: bool
    restricted_network_supported: bool
    snapshotter_subject_id: str
    captured_at: datetime
    state: Literal["snapshotted"]
    authority: EventPhysicalTransportProfileSnapshotAuthorityData
    canonical_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")

    @classmethod
    def from_domain(
        cls, snapshot: EventPhysicalTransportProfileSnapshot
    ) -> EventPhysicalTransportProfileSnapshotData:
        event_contracts = []
        for contract in snapshot.supported_event_contracts:
            event_type, event_version, schema_uri = contract.split("|", maxsplit=2)
            event_contracts.append(
                {
                    "event_type": event_type,
                    "event_version": event_version,
                    "schema_uri": schema_uri,
                }
            )
        return cls.model_validate(
            snapshot.canonical_value() | {"supported_event_contracts": event_contracts}
        )


class EventPhysicalTransportProfileSnapshotInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transport_profile_snapshots: list[EventPhysicalTransportProfileSnapshotData]
    durable: bool


class EventPhysicalTransportProfileSnapshotResponse(BaseModel):
    data: EventPhysicalTransportProfileSnapshotData
    meta: ResponseMeta


class EventPhysicalTransportProfileSnapshotInventoryResponse(BaseModel):
    data: EventPhysicalTransportProfileSnapshotInventoryData
    meta: ResponseMeta


class CreateEventPhysicalTransportRouteSnapshotInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_route_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    source_route_revision: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    source_route_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class EventPhysicalTransportRouteSnapshotAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint_resolution_authorized: Literal[False]
    route_selection_authorized: Literal[False]
    route_binding_authorized: Literal[False]
    credential_access_authorized: Literal[False]
    network_access_authorized: Literal[False]
    readiness_probe_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]


class EventPhysicalTransportRouteSnapshotData(BaseModel):
    """Minimized immutable route metadata without locator or operational authority."""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    route_id: str
    route_revision: str
    route_set_id: str
    route_set_revision: str
    selection_epoch_id: str
    selection_epoch_revision: str
    source_route_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    deployment_release_id: str
    deployment_profile: str
    scope: WorkflowScopeData
    transport_profile_id: str
    transport_profile_revision: str
    transport_resource_id: str
    transport_implementation_id: str
    transport_implementation_version: str
    adapter_contract_id: str
    adapter_contract_version: str
    route_kind: Literal["message-broker"]
    endpoint_set_id: str
    endpoint_set_revision: str
    destination_id: str
    destination_revision: str
    routing_contract_id: str
    routing_contract_revision: str
    transport_security_policy_id: str
    transport_security_policy_version: str
    minimum_tls_version: Literal["1.3"]
    server_authentication_required: Literal[True]
    client_authentication_required: bool
    plaintext_fallback_prohibited: Literal[True]
    network_policy_id: str
    network_policy_version: str
    source_zone_class: str
    destination_zone_class: str
    restricted_network_enforced: Literal[True]
    public_egress_prohibited: Literal[True]
    proxy_mode: Literal["prohibited", "deployment-managed"]
    credential_requirement_profile_id: str
    credential_requirement_profile_version: str
    authentication_mechanism_class: Literal["mutual-tls", "workload-token"]
    principal_class: Literal["service-workload"]
    snapshotter_subject_id: str
    captured_at: datetime
    state: Literal["snapshotted"]
    authority: EventPhysicalTransportRouteSnapshotAuthorityData
    canonical_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")

    @classmethod
    def from_domain(
        cls, snapshot: EventPhysicalTransportRouteSnapshot
    ) -> EventPhysicalTransportRouteSnapshotData:
        return cls.model_validate(
            {
                field_name: (
                    snapshot.scope.canonical_value()
                    if field_name == "scope"
                    else getattr(snapshot, field_name)
                )
                for field_name in cls.model_fields
                if field_name != "authority"
            }
            | {"authority": snapshot.authority.canonical_value()}
        )


class EventPhysicalTransportRouteSnapshotInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transport_route_snapshots: list[EventPhysicalTransportRouteSnapshotData] = Field(max_length=256)
    durable: bool


class EventPhysicalTransportRouteSnapshotResponse(BaseModel):
    data: EventPhysicalTransportRouteSnapshotData
    meta: ResponseMeta


class EventPhysicalTransportRouteSnapshotInventoryResponse(BaseModel):
    data: EventPhysicalTransportRouteSnapshotInventoryData
    meta: ResponseMeta


class CreateEventPhysicalTransportCredentialAssignmentSnapshotInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assignment_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    assignment_revision: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    source_assignment_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class EventPhysicalTransportCredentialAssignmentSnapshotAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint_resolution_authorized: Literal[False]
    protected_artifact_access_authorized: Literal[False]
    credential_selection_authorized: Literal[False]
    credential_access_authorized: Literal[False]
    credential_brokerage_authorized: Literal[False]
    credential_resolution_authorized: Literal[False]
    credential_delivery_authorized: Literal[False]
    network_access_authorized: Literal[False]
    readiness_probe_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_authorized: Literal[False]


class EventPhysicalTransportCredentialAssignmentSnapshotData(BaseModel):
    """Minimized assignment evidence without credential or target identity."""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    assignment_id: str
    assignment_revision: str
    state: Literal["snapshotted"]
    credential_generation: int = Field(ge=1)
    rotation_epoch: int = Field(ge=1)
    activated_at: datetime
    expires_at: datetime
    captured_at: datetime
    authority: EventPhysicalTransportCredentialAssignmentSnapshotAuthorityData

    @classmethod
    def from_domain(
        cls,
        snapshot: EventPhysicalTransportCredentialAssignmentSnapshot,
    ) -> EventPhysicalTransportCredentialAssignmentSnapshotData:
        return cls.model_validate(
            {
                "snapshot_id": snapshot.snapshot_id,
                "assignment_id": snapshot.assignment_id,
                "assignment_revision": snapshot.assignment_revision,
                "state": snapshot.state.value,
                "credential_generation": snapshot.credential_generation,
                "rotation_epoch": snapshot.rotation_epoch,
                "activated_at": snapshot.activated_at,
                "expires_at": snapshot.expires_at,
                "captured_at": snapshot.captured_at,
                "authority": snapshot.authority.canonical_value(),
            }
        )


class EventPhysicalTransportCredentialAssignmentSnapshotInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transport_credential_assignment_snapshots: list[
        EventPhysicalTransportCredentialAssignmentSnapshotData
    ] = Field(max_length=256)
    durable: bool


class EventPhysicalTransportCredentialAssignmentSnapshotResponse(BaseModel):
    data: EventPhysicalTransportCredentialAssignmentSnapshotData
    meta: ResponseMeta


class EventPhysicalTransportCredentialAssignmentSnapshotInventoryResponse(BaseModel):
    data: EventPhysicalTransportCredentialAssignmentSnapshotInventoryData
    meta: ResponseMeta


class CreateWorkflowEventPhysicalTransportRouteBindingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    logical_channel_binding_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    logical_channel_binding_digest: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    compatibility_admission_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    compatibility_admission_digest: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    transport_profile_snapshot_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    transport_profile_snapshot_digest: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    transport_route_snapshot_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    transport_route_snapshot_digest: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    policy_id: Literal["policy.workflow-event-physical-transport-route-binding"]
    policy_version: Literal["1.0"]
    policy_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowEventPhysicalTransportRouteBindingAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_selection_authorized: Literal[False]
    route_binding_authorized: Literal[False]
    endpoint_resolution_authorized: Literal[False]
    credential_access_authorized: Literal[False]
    network_access_authorized: Literal[False]
    readiness_probe_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]


class WorkflowEventPhysicalTransportRouteBindingData(BaseModel):
    """Human-safe immutable binding evidence without source or policy digests."""

    model_config = ConfigDict(extra="forbid")

    binding_id: str
    logical_channel_binding_id: str
    compatibility_admission_id: str
    transport_profile_snapshot_id: str
    transport_route_snapshot_id: str
    policy_id: str
    policy_version: str
    scope: WorkflowScopeData
    binder_subject_id: str
    bound_at: datetime
    state: Literal["bound"]
    authority: WorkflowEventPhysicalTransportRouteBindingAuthorityData
    integrity_reference: str = Field(min_length=3, max_length=256, pattern=STABLE_ID)

    @classmethod
    def from_domain(
        cls, binding: WorkflowEventPhysicalTransportRouteBinding
    ) -> WorkflowEventPhysicalTransportRouteBindingData:
        return cls(
            binding_id=binding.binding_id,
            logical_channel_binding_id=binding.logical_channel_binding_id,
            compatibility_admission_id=binding.transport_compatibility_admission_id,
            transport_profile_snapshot_id=binding.transport_profile_snapshot_id,
            transport_route_snapshot_id=binding.transport_route_snapshot_id,
            policy_id=binding.policy_id,
            policy_version=binding.policy_version,
            scope=WorkflowScopeData.model_validate(binding.scope.canonical_value()),
            binder_subject_id=binding.binder_subject_id,
            bound_at=binding.bound_at,
            state="bound",
            authority=WorkflowEventPhysicalTransportRouteBindingAuthorityData.model_validate(
                binding.authority.canonical_value()
            ),
            integrity_reference=f"integrity.{binding.binding_id}",
        )


class WorkflowEventPhysicalTransportRouteBindingInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    physical_transport_route_bindings: list[WorkflowEventPhysicalTransportRouteBindingData] = Field(
        max_length=256
    )
    durable: bool


class WorkflowEventPhysicalTransportRouteBindingResponse(BaseModel):
    data: WorkflowEventPhysicalTransportRouteBindingData
    meta: ResponseMeta


class WorkflowEventPhysicalTransportRouteBindingInventoryResponse(BaseModel):
    data: WorkflowEventPhysicalTransportRouteBindingInventoryData
    meta: ResponseMeta


class CreateWorkflowEventPhysicalTransportCredentialAssignmentBindingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    physical_transport_route_binding_id: str = Field(
        min_length=3, max_length=128, pattern=STABLE_ID
    )
    physical_transport_route_binding_digest: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    credential_assignment_snapshot_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    credential_assignment_snapshot_digest: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowEventPhysicalTransportCredentialAssignmentBindingData(BaseModel):
    """Minimized immutable relationship without credential or route details."""

    model_config = ConfigDict(extra="forbid")

    binding_id: str
    physical_transport_route_binding_id: str
    credential_assignment_snapshot_id: str
    state: Literal["bound"]
    bound_at: datetime
    integrity_reference: str = Field(min_length=3, max_length=256, pattern=STABLE_ID)

    @classmethod
    def from_domain(
        cls,
        binding: WorkflowEventPhysicalTransportCredentialAssignmentBinding,
    ) -> WorkflowEventPhysicalTransportCredentialAssignmentBindingData:
        return cls(
            binding_id=binding.binding_id,
            physical_transport_route_binding_id=(binding.physical_transport_route_binding_id),
            credential_assignment_snapshot_id=(binding.credential_assignment_snapshot_id),
            state="bound",
            bound_at=binding.bound_at,
            integrity_reference=f"integrity.{binding.binding_id}",
        )


class WorkflowEventPhysicalTransportCredentialAssignmentBindingInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    physical_transport_credential_assignment_bindings: list[
        WorkflowEventPhysicalTransportCredentialAssignmentBindingData
    ] = Field(max_length=256)
    durable: bool


class WorkflowEventPhysicalTransportCredentialAssignmentBindingResponse(BaseModel):
    data: WorkflowEventPhysicalTransportCredentialAssignmentBindingData
    meta: ResponseMeta


class WorkflowEventPhysicalTransportCredentialAssignmentBindingInventoryResponse(BaseModel):
    data: WorkflowEventPhysicalTransportCredentialAssignmentBindingInventoryData
    meta: ResponseMeta


class CreateWorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    physical_transport_credential_assignment_binding_id: str = Field(
        min_length=3, max_length=128, pattern=STABLE_ID
    )
    physical_transport_credential_assignment_binding_digest: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    policy_id: Literal["policy.workflow-event-physical-transport-credential-assignment-freshness"]
    policy_version: Literal["1.0"]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint_resolution_authorized: Literal[False]
    protected_artifact_access_authorized: Literal[False]
    route_selection_authorized: Literal[False]
    route_binding_authorized: Literal[False]
    credential_selection_authorized: Literal[False]
    credential_assignment_binding_authorized: Literal[False]
    credential_access_authorized: Literal[False]
    credential_brokerage_authorized: Literal[False]
    credential_resolution_authorized: Literal[False]
    credential_delivery_authorized: Literal[False]
    network_access_authorized: Literal[False]
    readiness_probe_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_authorized: Literal[False]


class WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionData(BaseModel):
    """Minimized point-in-time evidence without credential or private policy data."""

    model_config = ConfigDict(extra="forbid")

    freshness_admission_id: str
    physical_transport_credential_assignment_binding_id: str
    credential_assignment_snapshot_id: str
    assignment_id: str
    assignment_revision: str
    credential_generation: int = Field(ge=1)
    rotation_epoch: int = Field(ge=1)
    policy_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    policy_version: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    scope: WorkflowScopeData
    admitter_subject_id: str
    evaluated_at: datetime
    valid_until: datetime
    state: Literal["admitted_current"]
    authority: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionAuthorityData
    integrity_reference: str = Field(min_length=3, max_length=256, pattern=STABLE_ID)

    @classmethod
    def from_domain(
        cls,
        admission: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmission,
    ) -> WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionData:
        return cls(
            freshness_admission_id=admission.freshness_admission_id,
            physical_transport_credential_assignment_binding_id=(
                admission.physical_transport_credential_assignment_binding_id
            ),
            credential_assignment_snapshot_id=admission.credential_assignment_snapshot_id,
            assignment_id=admission.assignment_id,
            assignment_revision=admission.assignment_revision,
            credential_generation=admission.credential_generation,
            rotation_epoch=admission.rotation_epoch,
            policy_id=admission.policy_id,
            policy_version=admission.policy_version,
            scope=WorkflowScopeData.model_validate(admission.scope.canonical_value()),
            admitter_subject_id=admission.admitter_subject_id,
            evaluated_at=admission.evaluated_at,
            valid_until=admission.valid_until,
            state="admitted_current",
            authority=(
                WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionAuthorityData.model_validate(
                    admission.authority.canonical_value()
                )
            ),
            integrity_reference=f"integrity.{admission.freshness_admission_id}",
        )


class WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    physical_transport_credential_assignment_freshness_admissions: list[
        WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionData
    ] = Field(max_length=256)
    durable: bool


class WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionResponse(BaseModel):
    data: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionData
    meta: ResponseMeta


class WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionInventoryResponse(
    BaseModel
):
    data: WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionInventoryData
    meta: ResponseMeta


class CreateWorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    freshness_admission_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    freshness_admission_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    policy_id: Literal["policy.workflow-event-physical-transport-credential-access-authorization"]
    policy_version: Literal["1.0"]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint_resolution_authorized: Literal[False]
    protected_artifact_access_authorized: Literal[False]
    route_selection_authorized: Literal[False]
    route_binding_authorized: Literal[False]
    credential_selection_authorized: Literal[False]
    credential_assignment_binding_authorized: Literal[False]
    credential_access_authorized: Literal[True]
    credential_brokerage_authorized: Literal[False]
    credential_resolution_authorized: Literal[False]
    credential_delivery_authorized: Literal[False]
    network_access_authorized: Literal[False]
    readiness_probe_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_authorized: Literal[False]


class WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseData(BaseModel):
    """Human-safe authority evidence without credential, target or source material."""

    model_config = ConfigDict(extra="forbid")

    lease_id: str
    freshness_admission_id: str
    assignment_revision: str
    credential_generation: int = Field(ge=1)
    rotation_epoch: int = Field(ge=1)
    policy_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    policy_version: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    scope: WorkflowScopeData
    accessor_subject_id: str
    issued_at: datetime
    valid_until: datetime
    state: Literal["authorized_unconsumed"]
    effective_state: Literal["active", "expired"]
    single_use: Literal[True]
    renewable: Literal[False]
    authority: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseAuthorityData
    integrity_reference: str = Field(min_length=3, max_length=256, pattern=STABLE_ID)

    @classmethod
    def from_domain(
        cls,
        lease: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease,
        *,
        evaluated_at: datetime,
    ) -> WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseData:
        return cls(
            lease_id=lease.authorization_lease_id,
            freshness_admission_id=lease.freshness_admission_id,
            assignment_revision=lease.assignment_revision,
            credential_generation=lease.credential_generation,
            rotation_epoch=lease.rotation_epoch,
            policy_id=lease.policy_id,
            policy_version=lease.policy_version,
            scope=WorkflowScopeData.model_validate(lease.scope.canonical_value()),
            accessor_subject_id=lease.accessor_subject_id,
            issued_at=lease.issued_at,
            valid_until=lease.valid_until,
            state="authorized_unconsumed",
            effective_state=lease.effective_state(evaluated_at=evaluated_at).value,
            single_use=True,
            renewable=False,
            authority=(
                WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseAuthorityData.model_validate(
                    lease.authority.canonical_value()
                )
            ),
            integrity_reference=f"integrity.{lease.authorization_lease_id}",
        )


class WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    physical_transport_credential_access_authorization_leases: list[
        WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseData
    ] = Field(max_length=256)
    server_time: datetime
    durable: bool


class WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseResponse(BaseModel):
    data: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseData
    meta: ResponseMeta


class WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseInventoryResponse(BaseModel):
    data: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseInventoryData
    meta: ResponseMeta


class CreateWorkflowEventPhysicalTransportRouteFreshnessAdmissionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    physical_transport_route_binding_id: str = Field(
        min_length=3, max_length=128, pattern=STABLE_ID
    )
    physical_transport_route_binding_digest: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    policy_id: Literal["policy.workflow-event-physical-transport-route-freshness"]
    policy_version: Literal["1.0"]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowEventPhysicalTransportRouteFreshnessAdmissionAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_selection_authorized: Literal[False]
    route_binding_authorized: Literal[False]
    endpoint_resolution_authorized: Literal[False]
    credential_access_authorized: Literal[False]
    network_access_authorized: Literal[False]
    readiness_probe_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]


class WorkflowEventPhysicalTransportRouteFreshnessAdmissionData(BaseModel):
    """Human-safe point-in-time route freshness evidence without source digests."""

    model_config = ConfigDict(extra="forbid")

    freshness_admission_id: str
    physical_transport_route_binding_id: str
    transport_route_snapshot_id: str
    selection_head_id: str
    selection_generation: int = Field(ge=1)
    policy_id: str
    policy_version: str
    scope: WorkflowScopeData
    admitter_subject_id: str
    evaluated_at: datetime
    valid_until: datetime
    state: Literal["admitted_current"]
    authority: WorkflowEventPhysicalTransportRouteFreshnessAdmissionAuthorityData
    integrity_reference: str = Field(min_length=3, max_length=256, pattern=STABLE_ID)

    @classmethod
    def from_domain(
        cls, admission: WorkflowEventPhysicalTransportRouteFreshnessAdmission
    ) -> WorkflowEventPhysicalTransportRouteFreshnessAdmissionData:
        return cls(
            freshness_admission_id=admission.freshness_admission_id,
            physical_transport_route_binding_id=(admission.physical_transport_route_binding_id),
            transport_route_snapshot_id=admission.transport_route_snapshot_id,
            selection_head_id=admission.current_selection_head_id,
            selection_generation=admission.current_selection_head_generation,
            policy_id=admission.policy_id,
            policy_version=admission.policy_version,
            scope=WorkflowScopeData.model_validate(admission.scope.canonical_value()),
            admitter_subject_id=admission.admitter_subject_id,
            evaluated_at=admission.evaluated_at,
            valid_until=admission.valid_until,
            state="admitted_current",
            authority=(
                WorkflowEventPhysicalTransportRouteFreshnessAdmissionAuthorityData.model_validate(
                    admission.authority.canonical_value()
                )
            ),
            integrity_reference=f"integrity.{admission.freshness_admission_id}",
        )


class WorkflowEventPhysicalTransportRouteFreshnessAdmissionInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    physical_transport_route_freshness_admissions: list[
        WorkflowEventPhysicalTransportRouteFreshnessAdmissionData
    ] = Field(max_length=256)
    durable: bool


class WorkflowEventPhysicalTransportRouteFreshnessAdmissionResponse(BaseModel):
    data: WorkflowEventPhysicalTransportRouteFreshnessAdmissionData
    meta: ResponseMeta


class WorkflowEventPhysicalTransportRouteFreshnessAdmissionInventoryResponse(BaseModel):
    data: WorkflowEventPhysicalTransportRouteFreshnessAdmissionInventoryData
    meta: ResponseMeta


class CreateWorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    freshness_admission_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    freshness_admission_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    policy_id: Literal["policy.workflow-event-physical-transport-endpoint-resolution-authorization"]
    policy_version: Literal["1.0"]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_selection_authorized: Literal[False]
    route_binding_authorized: Literal[False]
    endpoint_resolution_authorized: Literal[True]
    credential_access_authorized: Literal[False]
    network_access_authorized: Literal[False]
    readiness_probe_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]


class WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseData(BaseModel):
    """Human-safe authorization evidence without endpoint or source material."""

    model_config = ConfigDict(extra="forbid")

    lease_id: str
    freshness_admission_id: str
    selection_generation: int = Field(ge=1)
    policy_id: str
    policy_version: str
    scope: WorkflowScopeData
    resolver_subject_id: str
    authorized_at: datetime
    expires_at: datetime
    state: Literal["authorized_unconsumed"]
    effective_state: Literal["active", "expired", "consumed"]
    single_use: Literal[True]
    renewable: Literal[False]
    authority: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseAuthorityData
    integrity_reference: str = Field(min_length=3, max_length=256, pattern=STABLE_ID)

    @classmethod
    def from_domain(
        cls,
        lease: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLease,
        *,
        evaluated_at: datetime,
        consumed: bool = False,
    ) -> WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseData:
        return cls(
            lease_id=lease.authorization_lease_id,
            freshness_admission_id=lease.freshness_admission_id,
            selection_generation=lease.current_selection_head_generation,
            policy_id=lease.policy_id,
            policy_version=lease.policy_version,
            scope=WorkflowScopeData.model_validate(lease.scope.canonical_value()),
            resolver_subject_id=lease.resolver_subject_id,
            authorized_at=lease.issued_at,
            expires_at=lease.valid_until,
            state="authorized_unconsumed",
            effective_state=(
                "consumed" if consumed else lease.effective_state(evaluated_at=evaluated_at).value
            ),
            single_use=True,
            renewable=False,
            authority=(
                WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseAuthorityData.model_validate(
                    lease.authority.canonical_value()
                )
            ),
            integrity_reference=f"integrity.{lease.authorization_lease_id}",
        )


class WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint_resolution_authorization_leases: list[
        WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseData
    ] = Field(max_length=256)
    server_time: datetime
    durable: bool


class WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseResponse(BaseModel):
    data: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseData
    meta: ResponseMeta


class WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseInventoryResponse(
    BaseModel
):
    data: WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseInventoryData
    meta: ResponseMeta


class CreateWorkflowEventPhysicalTransportEndpointMaterializationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorization_lease_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    authorization_lease_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    policy_id: Literal["policy.workflow-event-physical-transport-endpoint-materialization"]
    policy_version: Literal["1.0"]
    irreversible_consumption_acknowledged: Literal[True]
    uncertain_outcome_requires_new_authorization_acknowledged: Literal[True]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowEventPhysicalTransportEndpointMaterializationAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_selection_authorized: Literal[False]
    route_binding_authorized: Literal[False]
    endpoint_resolution_authorized: Literal[False]
    credential_access_authorized: Literal[False]
    network_access_authorized: Literal[False]
    readiness_probe_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]


class WorkflowEventPhysicalTransportEndpointMaterializationData(BaseModel):
    """Human-safe outcome metadata without protected artifact or endpoint material."""

    model_config = ConfigDict(extra="forbid")

    materialization_id: str
    lease_id: str
    freshness_admission_id: str
    selection_generation: int = Field(ge=1)
    policy_id: str
    policy_version: str
    scope: WorkflowScopeData
    resolver_subject_id: str
    consumed_at: datetime
    recorded_at: datetime | None
    outcome: Literal[
        "materialized_protected",
        "failed_closed_consumed",
        "uncertain_consumed",
    ]
    lease_consumed: Literal[True]
    protected_storage_verified: bool
    raw_endpoint_disclosed: Literal[False]
    authority: WorkflowEventPhysicalTransportEndpointMaterializationAuthorityData
    integrity_reference: str = Field(min_length=3, max_length=256, pattern=STABLE_ID)

    @classmethod
    def from_domain(
        cls,
        *,
        claim: WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaim,
        attempt: WorkflowEventPhysicalTransportEndpointMaterializationAttempt,
        result: WorkflowEventPhysicalTransportEndpointMaterializationResult | None,
    ) -> WorkflowEventPhysicalTransportEndpointMaterializationData:
        if result is None:
            outcome = "uncertain_consumed"
            recorded_at = None
            protected_storage_verified = False
        elif result.state is (
            WorkflowEventPhysicalTransportEndpointMaterializationResultState.MATERIALIZED_PROTECTED
        ):
            outcome = "materialized_protected"
            recorded_at = result.completed_at
            protected_storage_verified = True
        else:
            outcome = "failed_closed_consumed"
            recorded_at = result.completed_at
            protected_storage_verified = False
        return cls(
            materialization_id=attempt.materialization_id,
            lease_id=attempt.authorization_lease_id,
            freshness_admission_id=attempt.freshness_admission_id,
            selection_generation=attempt.current_selection_head_generation,
            policy_id=attempt.policy_id,
            policy_version=attempt.policy_version,
            scope=WorkflowScopeData.model_validate(attempt.scope.canonical_value()),
            resolver_subject_id=attempt.resolver_subject_id,
            consumed_at=claim.claimed_at,
            recorded_at=recorded_at,
            outcome=outcome,
            lease_consumed=True,
            protected_storage_verified=protected_storage_verified,
            raw_endpoint_disclosed=False,
            authority=(
                WorkflowEventPhysicalTransportEndpointMaterializationAuthorityData.model_validate(
                    attempt.authority.canonical_value()
                )
            ),
            integrity_reference=f"integrity.{attempt.materialization_id}",
        )


class WorkflowEventPhysicalTransportEndpointMaterializationInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    physical_transport_endpoint_materializations: list[
        WorkflowEventPhysicalTransportEndpointMaterializationData
    ] = Field(max_length=256)
    server_time: datetime
    durable: bool


class WorkflowEventPhysicalTransportEndpointMaterializationResponse(BaseModel):
    data: WorkflowEventPhysicalTransportEndpointMaterializationData
    meta: ResponseMeta


class WorkflowEventPhysicalTransportEndpointMaterializationInventoryResponse(BaseModel):
    data: WorkflowEventPhysicalTransportEndpointMaterializationInventoryData
    meta: ResponseMeta


class CreateWorkflowEventPhysicalTransportCredentialMaterializationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorization_lease_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    authorization_lease_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    policy_id: Literal["policy.workflow-event-physical-transport-credential-materialization"]
    policy_version: Literal["1.0"]
    irreversible_consumption_acknowledged: Literal[True]
    uncertain_outcome_requires_new_authorization_acknowledged: Literal[True]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowEventPhysicalTransportCredentialMaterializationAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint_resolution_authorized: Literal[False]
    protected_artifact_access_authorized: Literal[False]
    route_selection_authorized: Literal[False]
    route_binding_authorized: Literal[False]
    credential_selection_authorized: Literal[False]
    credential_assignment_binding_authorized: Literal[False]
    credential_access_authorized: Literal[False]
    credential_brokerage_authorized: Literal[False]
    credential_resolution_authorized: Literal[False]
    credential_delivery_authorized: Literal[False]
    network_access_authorized: Literal[False]
    readiness_probe_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_authorized: Literal[False]


class WorkflowEventPhysicalTransportCredentialMaterializationData(BaseModel):
    """Human-safe outcome metadata without credential or protected-artifact access data."""

    model_config = ConfigDict(extra="forbid")

    materialization_id: str
    lease_id: str
    freshness_admission_id: str
    assignment_revision: str
    credential_generation: int = Field(ge=1)
    rotation_epoch: int = Field(ge=1)
    policy_id: str
    policy_version: str
    scope: WorkflowScopeData
    accessor_subject_id: str
    consumed_at: datetime
    recorded_at: datetime | None
    outcome: Literal[
        "materialized_protected",
        "failed_closed_consumed",
        "uncertain_consumed",
    ]
    lease_consumed: Literal[True]
    protected_storage_verified: bool
    raw_credential_disclosed: Literal[False]
    authority: WorkflowEventPhysicalTransportCredentialMaterializationAuthorityData
    integrity_reference: str = Field(min_length=3, max_length=256, pattern=STABLE_ID)

    @classmethod
    def from_domain(
        cls,
        *,
        claim: WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaim,
        attempt: WorkflowEventPhysicalTransportCredentialMaterializationAttempt,
        result: WorkflowEventPhysicalTransportCredentialMaterializationResult | None,
    ) -> WorkflowEventPhysicalTransportCredentialMaterializationData:
        if result is None:
            outcome = "uncertain_consumed"
            recorded_at = None
            protected_storage_verified = False
        elif (
            result.state
            is (
                WorkflowEventPhysicalTransportCredentialMaterializationResultState
            ).MATERIALIZED_PROTECTED
        ):
            outcome = "materialized_protected"
            recorded_at = result.completed_at
            protected_storage_verified = True
        else:
            outcome = "failed_closed_consumed"
            recorded_at = result.completed_at
            protected_storage_verified = False
        return cls(
            materialization_id=attempt.materialization_id,
            lease_id=attempt.authorization_lease_id,
            freshness_admission_id=attempt.freshness_admission_id,
            assignment_revision=attempt.assignment_revision,
            credential_generation=attempt.credential_generation,
            rotation_epoch=attempt.rotation_epoch,
            policy_id=attempt.policy_id,
            policy_version=attempt.policy_version,
            scope=WorkflowScopeData.model_validate(attempt.scope.canonical_value()),
            accessor_subject_id=attempt.accessor_subject_id,
            consumed_at=claim.claimed_at,
            recorded_at=recorded_at,
            outcome=outcome,
            lease_consumed=True,
            protected_storage_verified=protected_storage_verified,
            raw_credential_disclosed=False,
            authority=(
                WorkflowEventPhysicalTransportCredentialMaterializationAuthorityData.model_validate(
                    attempt.authority.canonical_value()
                )
            ),
            integrity_reference=f"integrity.{attempt.materialization_id}",
        )


class WorkflowEventPhysicalTransportCredentialMaterializationInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    physical_transport_credential_materializations: list[
        WorkflowEventPhysicalTransportCredentialMaterializationData
    ] = Field(max_length=256)
    server_time: datetime
    durable: bool


class WorkflowEventPhysicalTransportCredentialMaterializationResponse(BaseModel):
    data: WorkflowEventPhysicalTransportCredentialMaterializationData
    meta: ResponseMeta


class WorkflowEventPhysicalTransportCredentialMaterializationInventoryResponse(BaseModel):
    data: WorkflowEventPhysicalTransportCredentialMaterializationInventoryData
    meta: ResponseMeta


class CreateWorkflowEventPhysicalTransportTargetContextBindingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint_materialization_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    endpoint_materialization_digest: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    credential_materialization_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    credential_materialization_digest: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    policy_id: Literal["policy.workflow-event-physical-transport-target-context-binding"]
    policy_version: Literal["1.0"]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowEventPhysicalTransportTargetContextBindingAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint_resolution_authorized: Literal[False]
    protected_artifact_access_authorized: Literal[False]
    route_selection_authorized: Literal[False]
    route_binding_authorized: Literal[False]
    credential_selection_authorized: Literal[False]
    credential_assignment_binding_authorized: Literal[False]
    credential_access_authorized: Literal[False]
    credential_brokerage_authorized: Literal[False]
    credential_resolution_authorized: Literal[False]
    credential_delivery_authorized: Literal[False]
    network_access_authorized: Literal[False]
    readiness_probe_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_authorized: Literal[False]


class WorkflowEventPhysicalTransportTargetContextBindingData(BaseModel):
    """Human-safe immutable binding evidence without protected target material."""

    model_config = ConfigDict(extra="forbid")

    binding_id: str
    endpoint_materialization_id: str
    credential_materialization_id: str
    state: Literal["bound"]
    effective_state: Literal["active", "expired"]
    scope: WorkflowScopeData
    binder_subject_id: str
    bound_at: datetime
    joint_usable_until: datetime
    policy_reference: str
    target_context_schema_reference: str
    authority: WorkflowEventPhysicalTransportTargetContextBindingAuthorityData

    @classmethod
    def from_domain(
        cls,
        binding: WorkflowEventPhysicalTransportTargetContextBinding,
        *,
        evaluated_at: datetime,
    ) -> WorkflowEventPhysicalTransportTargetContextBindingData:
        return cls(
            binding_id=binding.binding_id,
            endpoint_materialization_id=binding.endpoint_materialization_id,
            credential_materialization_id=binding.credential_materialization_id,
            state=binding.state.value,
            effective_state=binding.effective_state(evaluated_at=evaluated_at).value,
            scope=WorkflowScopeData.model_validate(binding.scope.canonical_value()),
            binder_subject_id=binding.binder_subject_id,
            bound_at=binding.bound_at,
            joint_usable_until=binding.joint_usable_until,
            policy_reference=f"{binding.policy_id}:{binding.policy_version}",
            target_context_schema_reference=(
                f"{binding.target_context_schema_id}:{binding.target_context_schema_version}"
            ),
            authority=(
                WorkflowEventPhysicalTransportTargetContextBindingAuthorityData.model_validate(
                    binding.authority.canonical_value()
                )
            ),
        )


class WorkflowEventPhysicalTransportTargetContextBindingInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    physical_transport_target_context_bindings: list[
        WorkflowEventPhysicalTransportTargetContextBindingData
    ] = Field(max_length=256)
    server_time: datetime
    durable: bool


class WorkflowEventPhysicalTransportTargetContextBindingResponse(BaseModel):
    data: WorkflowEventPhysicalTransportTargetContextBindingData
    meta: ResponseMeta


class WorkflowEventPhysicalTransportTargetContextBindingInventoryResponse(BaseModel):
    data: WorkflowEventPhysicalTransportTargetContextBindingInventoryData
    meta: ResponseMeta


class CreateWorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_context_binding_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    target_context_binding_digest: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    policy_id: Literal[
        "policy.workflow-event-physical-transport-target-context-access-authorization"
    ]
    policy_version: Literal["1.0"]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeasePolicyData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: Literal[
        "policy.workflow-event-physical-transport-target-context-access-authorization"
    ]
    policy_version: Literal["1.0"]


class WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint_resolution_authorized: Literal[False]
    protected_artifact_access_authorized: Literal[True]
    route_selection_authorized: Literal[False]
    route_binding_authorized: Literal[False]
    credential_selection_authorized: Literal[False]
    credential_assignment_binding_authorized: Literal[False]
    credential_access_authorized: Literal[False]
    credential_brokerage_authorized: Literal[False]
    credential_resolution_authorized: Literal[False]
    credential_delivery_authorized: Literal[False]
    network_access_authorized: Literal[False]
    readiness_probe_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_authorized: Literal[False]


class WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseData(BaseModel):
    """Human-safe lease evidence without binding, artifact or store internals."""

    model_config = ConfigDict(extra="forbid")

    authorization_lease_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    scope: WorkflowScopeData
    accessor_subject_id: Literal["service.workflow-protected-transport-context-accessor"]
    state: Literal["authorized_unconsumed"]
    effective_state: Literal["active", "expired"]
    issued_at: datetime
    valid_until: datetime
    single_use: Literal[True]
    renewable: Literal[False]
    transferable: Literal[False]
    policy: WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeasePolicyData
    authority: WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseAuthorityData
    integrity_reference: str = Field(min_length=3, max_length=256, pattern=STABLE_ID)

    @classmethod
    def from_domain(
        cls,
        lease: WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease,
        *,
        evaluated_at: datetime,
    ) -> WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseData:
        return cls(
            authorization_lease_id=lease.authorization_lease_id,
            scope=WorkflowScopeData.model_validate(lease.scope.canonical_value()),
            accessor_subject_id=lease.accessor_subject_id,
            state="authorized_unconsumed",
            effective_state=lease.effective_state(evaluated_at=evaluated_at).value,
            issued_at=lease.issued_at,
            valid_until=lease.valid_until,
            single_use=True,
            renewable=False,
            transferable=False,
            policy=(
                WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeasePolicyData(
                    policy_id=lease.policy_id,
                    policy_version=lease.policy_version,
                )
            ),
            authority=(
                WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseAuthorityData.model_validate(
                    lease.authority.canonical_value()
                )
            ),
            integrity_reference=f"integrity.{lease.authorization_lease_id}",
        )


class WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    physical_transport_target_context_access_authorization_leases: list[
        WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseData
    ] = Field(max_length=256)
    server_time: datetime
    durable: bool


class WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseResponse(BaseModel):
    data: WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseData
    meta: ResponseMeta


class WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseInventoryResponse(
    BaseModel
):
    data: WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseInventoryData
    meta: ResponseMeta


class CreateWorkflowEventPhysicalTransportTargetContextArtifactOpeningInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorization_lease_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    authorization_lease_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    policy_id: Literal["policy.workflow-event-physical-transport-target-context-artifact-opening"]
    policy_version: Literal["1.0"]
    irreversible_consumption_acknowledged: Literal[True]
    uncertain_outcome_requires_new_authorization_acknowledged: Literal[True]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowEventPhysicalTransportTargetContextArtifactOpeningAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_selection_authorized: Literal[False]
    route_binding_authorized: Literal[False]
    endpoint_resolution_authorized: Literal[False]
    protected_artifact_access_authorized: Literal[False]
    credential_selection_authorized: Literal[False]
    credential_assignment_binding_authorized: Literal[False]
    credential_access_authorized: Literal[False]
    credential_brokerage_authorized: Literal[False]
    credential_resolution_authorized: Literal[False]
    credential_delivery_authorized: Literal[False]
    network_access_authorized: Literal[False]
    readiness_probe_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_authorized: Literal[False]


class WorkflowEventPhysicalTransportTargetContextArtifactOpeningData(BaseModel):
    """Minimized opening outcome without protected material or bearer capability data."""

    model_config = ConfigDict(extra="forbid")

    opening_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    result_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    state: Literal["opened_protected", "opening_failed"]
    completed_at: datetime
    usable_until: datetime | None
    authority: WorkflowEventPhysicalTransportTargetContextArtifactOpeningAuthorityData

    @classmethod
    def from_domain(
        cls,
        result: WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult,
    ) -> WorkflowEventPhysicalTransportTargetContextArtifactOpeningData:
        return cls(
            opening_id=result.opening_id,
            result_digest=result.canonical_digest,
            state=result.state.value,
            completed_at=result.completed_at,
            usable_until=result.usable_until,
            authority=(
                WorkflowEventPhysicalTransportTargetContextArtifactOpeningAuthorityData.model_validate(
                    result.authority.canonical_value()
                )
            ),
        )


class WorkflowEventPhysicalTransportTargetContextArtifactOpeningPolicyData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: Literal["policy.workflow-event-physical-transport-target-context-artifact-opening"]
    policy_version: Literal["1.0"]


class WorkflowEventPhysicalTransportTargetContextArtifactOpeningInventoryItemData(BaseModel):
    """Human-safe attempt and optional result presentation without protected lineage."""

    model_config = ConfigDict(extra="forbid")

    opening_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    scope: WorkflowScopeData
    attempt_state: Literal["started", "completed"]
    result_state: Literal["pending", "opened_protected", "opening_failed", "outcome_uncertain"]
    started_at: datetime
    completed_at: datetime | None
    policy: WorkflowEventPhysicalTransportTargetContextArtifactOpeningPolicyData
    authority: WorkflowEventPhysicalTransportTargetContextArtifactOpeningAuthorityData
    integrity_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)

    @classmethod
    def from_domain(
        cls,
        attempt: WorkflowEventPhysicalTransportTargetContextArtifactOpeningAttempt,
        result: WorkflowEventPhysicalTransportTargetContextArtifactOpeningResult | None,
    ) -> WorkflowEventPhysicalTransportTargetContextArtifactOpeningInventoryItemData:
        if result is not None and (
            result.opening_id != attempt.opening_id
            or result.attempt_id != attempt.attempt_id
            or result.scope != attempt.scope
        ):
            raise ValueError("target context artifact opening presentation lineage mismatch")
        return cls(
            opening_id=attempt.opening_id,
            scope=WorkflowScopeData.model_validate(attempt.scope.canonical_value()),
            attempt_state="completed" if result is not None else "started",
            result_state=result.state.value if result is not None else "outcome_uncertain",
            started_at=attempt.started_at,
            completed_at=result.completed_at if result is not None else None,
            policy=WorkflowEventPhysicalTransportTargetContextArtifactOpeningPolicyData(
                policy_id=attempt.policy_id,
                policy_version=attempt.policy_version,
            ),
            authority=(
                WorkflowEventPhysicalTransportTargetContextArtifactOpeningAuthorityData.model_validate(
                    attempt.authority.canonical_value()
                )
            ),
            integrity_reference=(
                "integrity.workflow-target-context-opening."
                f"{sha256(attempt.opening_id.encode('utf-8')).hexdigest()[:24]}"
            ),
        )


class WorkflowEventPhysicalTransportTargetContextArtifactOpeningInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    physical_transport_target_context_artifact_openings: list[
        WorkflowEventPhysicalTransportTargetContextArtifactOpeningInventoryItemData
    ] = Field(max_length=256)
    server_time: datetime
    durable: bool


class WorkflowEventPhysicalTransportTargetContextArtifactOpeningResponse(BaseModel):
    data: WorkflowEventPhysicalTransportTargetContextArtifactOpeningData
    meta: ResponseMeta


class WorkflowEventPhysicalTransportTargetContextArtifactOpeningInventoryResponse(BaseModel):
    data: WorkflowEventPhysicalTransportTargetContextArtifactOpeningInventoryData
    meta: ResponseMeta


class CreateWorkflowProtectedTransportTargetContextCapsuleConsumerBindingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opening_result_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    opening_result_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    policy_id: Literal[
        "policy.workflow-protected-transport-target-context-capsule-consumer-binding"
    ]
    policy_version: Literal["1.0"]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowProtectedTransportTargetContextCapsuleConsumerBindingAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint_resolution_authorized: Literal[False]
    route_selection_authorized: Literal[False]
    route_binding_authorized: Literal[False]
    credential_selection_authorized: Literal[False]
    credential_assignment_binding_authorized: Literal[False]
    credential_access_authorized: Literal[False]
    credential_brokerage_authorized: Literal[False]
    credential_resolution_authorized: Literal[False]
    protected_artifact_access_authorized: Literal[False]
    credential_delivery_authorized: Literal[False]
    network_access_authorized: Literal[False]
    readiness_probe_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_authorized: Literal[False]


class WorkflowProtectedTransportTargetContextCapsuleConsumerBindingPolicyData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: Literal[
        "policy.workflow-protected-transport-target-context-capsule-consumer-binding"
    ]
    policy_version: Literal["1.0"]


class WorkflowProtectedTransportTargetContextCapsuleConsumerBindingData(BaseModel):
    """Minimized workload response without capsule or protected lineage."""

    model_config = ConfigDict(extra="forbid")

    binding_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    binding_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    state: Literal["bound"]
    bound_at: datetime
    effective_until: datetime
    policy: WorkflowProtectedTransportTargetContextCapsuleConsumerBindingPolicyData
    authority: WorkflowProtectedTransportTargetContextCapsuleConsumerBindingAuthorityData

    @classmethod
    def from_domain(
        cls,
        binding: WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
    ) -> WorkflowProtectedTransportTargetContextCapsuleConsumerBindingData:
        return cls(
            binding_id=binding.binding_id,
            binding_digest=binding.canonical_digest,
            state=binding.state.value,
            bound_at=binding.bound_at,
            effective_until=binding.effective_until,
            policy=WorkflowProtectedTransportTargetContextCapsuleConsumerBindingPolicyData(
                policy_id=binding.policy_id,
                policy_version=binding.policy_version,
            ),
            authority=(
                WorkflowProtectedTransportTargetContextCapsuleConsumerBindingAuthorityData.model_validate(
                    binding.authority.canonical_value()
                )
            ),
        )


class WorkflowProtectedTransportTargetContextCapsuleConsumerBindingInventoryItemData(BaseModel):
    """Human-safe immutable binding evidence without capsule or transport internals."""

    model_config = ConfigDict(extra="forbid")

    binding_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    scope: WorkflowScopeData
    state: Literal["bound"]
    bound_at: datetime
    effective_until: datetime
    consumer_contract_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    consumer_contract_version: str = Field(min_length=1, max_length=64)
    purpose_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    policy: WorkflowProtectedTransportTargetContextCapsuleConsumerBindingPolicyData
    authority: WorkflowProtectedTransportTargetContextCapsuleConsumerBindingAuthorityData
    integrity_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)

    @classmethod
    def from_domain(
        cls,
        binding: WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
    ) -> WorkflowProtectedTransportTargetContextCapsuleConsumerBindingInventoryItemData:
        return cls(
            binding_id=binding.binding_id,
            scope=WorkflowScopeData.model_validate(binding.scope.canonical_value()),
            state=binding.state.value,
            bound_at=binding.bound_at,
            effective_until=binding.effective_until,
            consumer_contract_id=binding.consumer_contract_id,
            consumer_contract_version=binding.consumer_contract_version,
            purpose_id=binding.purpose_id,
            policy=WorkflowProtectedTransportTargetContextCapsuleConsumerBindingPolicyData(
                policy_id=binding.policy_id,
                policy_version=binding.policy_version,
            ),
            authority=(
                WorkflowProtectedTransportTargetContextCapsuleConsumerBindingAuthorityData.model_validate(
                    binding.authority.canonical_value()
                )
            ),
            integrity_reference=(
                "integrity.workflow-target-context-capsule-consumer-binding."
                f"{sha256(binding.binding_id.encode('utf-8')).hexdigest()[:24]}"
            ),
        )


class WorkflowProtectedTransportTargetContextCapsuleConsumerBindingInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    physical_transport_target_context_capsule_consumer_bindings: list[
        WorkflowProtectedTransportTargetContextCapsuleConsumerBindingInventoryItemData
    ] = Field(max_length=256)
    server_time: datetime
    durable: bool


class WorkflowProtectedTransportTargetContextCapsuleConsumerBindingResponse(BaseModel):
    data: WorkflowProtectedTransportTargetContextCapsuleConsumerBindingData
    meta: ResponseMeta


class WorkflowProtectedTransportTargetContextCapsuleConsumerBindingInventoryResponse(BaseModel):
    data: WorkflowProtectedTransportTargetContextCapsuleConsumerBindingInventoryData
    meta: ResponseMeta


class CreateWorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consumer_binding_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    consumer_binding_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    policy_id: Literal[
        "policy.workflow-protected-transport-target-context-capsule-handoff-authorization"
    ]
    policy_version: Literal["1.0"]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeasePolicyData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: Literal[
        "policy.workflow-protected-transport-target-context-capsule-handoff-authorization"
    ]
    policy_version: Literal["1.0"]


class WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseAuthorityData(
    BaseModel
):
    model_config = ConfigDict(extra="forbid")

    target_context_capsule_handoff_authorized: Literal[True]
    endpoint_resolution_authorized: Literal[False]
    route_selection_authorized: Literal[False]
    route_binding_authorized: Literal[False]
    credential_selection_authorized: Literal[False]
    credential_assignment_binding_authorized: Literal[False]
    credential_access_authorized: Literal[False]
    credential_brokerage_authorized: Literal[False]
    credential_resolution_authorized: Literal[False]
    protected_artifact_access_authorized: Literal[False]
    credential_delivery_authorized: Literal[False]
    network_access_authorized: Literal[False]
    readiness_probe_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_authorized: Literal[False]


class WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseData(BaseModel):
    """Human-safe lease evidence without capsule, binding or attestation internals."""

    model_config = ConfigDict(extra="forbid")

    authorization_lease_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    scope: WorkflowScopeData
    consumer_contract_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    consumer_contract_version: str = Field(min_length=1, max_length=64)
    purpose_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    state: Literal["authorized_unconsumed"]
    effective_state: Literal["active", "expired"]
    issued_at: datetime
    valid_until: datetime
    single_use: Literal[True]
    renewable: Literal[False]
    transferable: Literal[False]
    lease_is_bearer_capability: Literal[False]
    policy: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeasePolicyData
    authority: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseAuthorityData
    integrity_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)

    @classmethod
    def from_domain(
        cls,
        lease: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease,
        *,
        evaluated_at: datetime,
    ) -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseData:
        return cls(
            authorization_lease_id=lease.authorization_lease_id,
            scope=WorkflowScopeData.model_validate(lease.scope.canonical_value()),
            consumer_contract_id=lease.consumer_contract_id,
            consumer_contract_version=lease.consumer_contract_version,
            purpose_id=lease.purpose_id,
            state=lease.state.value,
            effective_state=lease.effective_state(evaluated_at=evaluated_at).value,
            issued_at=lease.issued_at,
            valid_until=lease.valid_until,
            single_use=True,
            renewable=False,
            transferable=False,
            lease_is_bearer_capability=lease.lease_is_bearer_capability,
            policy=(
                WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeasePolicyData(
                    policy_id=lease.policy_id,
                    policy_version=lease.policy_version,
                )
            ),
            authority=(
                WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseAuthorityData.model_validate(
                    lease.authority.canonical_value()
                )
            ),
            integrity_reference=(
                "integrity.workflow-target-context-capsule-handoff-authorization-lease."
                f"{sha256(lease.authorization_lease_id.encode('utf-8')).hexdigest()[:24]}"
            ),
        )


class WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseInventoryData(
    BaseModel
):
    model_config = ConfigDict(extra="forbid")

    physical_transport_target_context_capsule_handoff_authorization_leases: list[
        WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseData
    ] = Field(max_length=256)
    server_time: datetime
    durable: Literal[True]


class WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseResponse(BaseModel):
    data: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseData
    meta: ResponseMeta


class WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseInventoryResponse(
    BaseModel
):
    data: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseInventoryData
    meta: ResponseMeta


class CreateWorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handoff_result_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    handoff_result_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    policy_id: Literal[
        "policy.workflow-protected-transport-target-context-capsule-opening-authorization"
    ]
    policy_version: Literal["1.0"]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseAuthorityData(
    BaseModel
):
    model_config = ConfigDict(extra="forbid")

    target_context_capsule_opening_authorized: Literal[True]
    target_context_capsule_handoff_authorized: Literal[False]
    endpoint_resolution_authorized: Literal[False]
    route_selection_authorized: Literal[False]
    route_binding_authorized: Literal[False]
    credential_selection_authorized: Literal[False]
    credential_assignment_binding_authorized: Literal[False]
    credential_access_authorized: Literal[False]
    credential_brokerage_authorized: Literal[False]
    credential_resolution_authorized: Literal[False]
    protected_artifact_access_authorized: Literal[False]
    credential_delivery_authorized: Literal[False]
    network_access_authorized: Literal[False]
    readiness_probe_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_authorized: Literal[False]


class WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseData(BaseModel):
    """Minimized, non-oracle opening authorization evidence."""

    model_config = ConfigDict(extra="forbid")

    authorization_lease_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    scope: WorkflowScopeData
    state: Literal["authorized_unconsumed"]
    effective_state: Literal["active", "expired"]
    issued_at: datetime
    valid_until: datetime
    single_use: Literal[True]
    renewable: Literal[False]
    transferable: Literal[False]
    lease_is_bearer_capability: Literal[False]
    consumer_contract_id: Literal[
        "contract.workflow-protected-transport-target-context-capsule-consumer"
    ]
    consumer_contract_version: Literal["1.0"]
    purpose_id: Literal[
        "purpose.workflow-protected-transport-target-context-capsule-opening-evaluation"
    ]
    destination_custody_profile_reference: str = Field(
        min_length=3, max_length=128, pattern=STABLE_ID
    )
    policy_id: Literal[
        "policy.workflow-protected-transport-target-context-capsule-opening-authorization"
    ]
    policy_version: Literal["1.0"]
    authority: WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseAuthorityData
    integrity_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)

    @classmethod
    def from_domain(
        cls,
        lease: WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease,
        *,
        evaluated_at: datetime,
    ) -> WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseData:
        custody_profile_input = "|".join(
            (
                lease.destination_boundary_id,
                lease.destination_deployment_id,
                lease.trusted_profile_digest,
            )
        )
        return cls(
            authorization_lease_id=lease.authorization_lease_id,
            scope=WorkflowScopeData.model_validate(lease.scope.canonical_value()),
            state=lease.state.value,
            effective_state=lease.effective_state(evaluated_at=evaluated_at).value,
            issued_at=lease.issued_at,
            valid_until=lease.valid_until,
            single_use=True,
            renewable=False,
            transferable=False,
            lease_is_bearer_capability=False,
            consumer_contract_id=lease.consumer_contract_id,
            consumer_contract_version=lease.consumer_contract_version,
            purpose_id=lease.purpose_id,
            destination_custody_profile_reference=(
                "integrity.workflow-target-context-capsule-destination-custody-profile."
                f"{sha256(custody_profile_input.encode()).hexdigest()[:24]}"
            ),
            policy_id=lease.policy_id,
            policy_version=lease.policy_version,
            authority=WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseAuthorityData.model_validate(
                lease.authority.canonical_value()
            ),
            integrity_reference=(
                "integrity.workflow-target-context-capsule-opening-authorization-lease."
                f"{sha256(lease.authorization_lease_id.encode()).hexdigest()[:24]}"
            ),
        )


class WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseInventoryData(
    BaseModel
):
    model_config = ConfigDict(extra="forbid")

    physical_transport_target_context_capsule_opening_authorization_leases: list[
        WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseData
    ] = Field(max_length=256)
    server_time: datetime
    durable: Literal[True]


class WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseResponse(BaseModel):
    data: WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseData
    meta: ResponseMeta


class WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseInventoryResponse(
    BaseModel
):
    data: WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseInventoryData
    meta: ResponseMeta


class CreateWorkflowProtectedResidentContextAccessAuthorizationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opening_result_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    opening_result_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    policy_id: Literal["policy.workflow-protected-resident-context-access-authorization"]
    policy_version: Literal["1.0"]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowProtectedResidentContextAccessAuthorizationAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protected_access_authority_granted: bool
    endpoint_resolution_authorized: Literal[False]
    route_selection_authorized: Literal[False]
    route_binding_authorized: Literal[False]
    credential_selection_authorized: Literal[False]
    credential_assignment_binding_authorized: Literal[False]
    credential_access_authorized: Literal[False]
    credential_brokerage_authorized: Literal[False]
    credential_resolution_authorized: Literal[False]
    protected_artifact_access_authorized: Literal[False]
    credential_delivery_authorized: Literal[False]
    network_access_authorized: Literal[False]
    readiness_probe_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_authorized: Literal[False]
    handoff_authorized: Literal[False]
    protected_opening_authorized: Literal[False]


class WorkflowProtectedResidentContextAccessAuthorizationData(BaseModel):
    """Minimized, non-oracle protected-access authorization evidence."""

    model_config = ConfigDict(extra="forbid")

    authorization_lease_id: str = Field(
        min_length=73,
        max_length=73,
        pattern=r"^workflow-protected-resident-context-access-lease\.[0-9a-f]{24}$",
    )
    state: Literal["authorized_unconsumed", "consumed"]
    effective_state: Literal["active", "expired", "consumed"]
    issued_at: datetime
    valid_until: datetime
    effective_until: datetime
    consumer_contract_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    consumer_contract_version: str = Field(min_length=1, max_length=32)
    purpose_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    policy_id: Literal["policy.workflow-protected-resident-context-access-authorization"]
    policy_version: Literal["1.0"]
    destination_profile_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    authority: WorkflowProtectedResidentContextAccessAuthorizationAuthorityData
    integrity_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)

    @model_validator(mode="after")
    def validate_consumption_projection(
        self,
    ) -> WorkflowProtectedResidentContextAccessAuthorizationData:
        consumed = self.state == "consumed"
        if (
            self.effective_state == "consumed"
        ) != consumed or self.authority.protected_access_authority_granted != (not consumed):
            raise ValueError("protected resident-context access projection is inconsistent")
        return self

    @classmethod
    def from_domain(
        cls,
        lease: WorkflowProtectedResidentContextAccessAuthorizationLease,
        *,
        evaluated_at: datetime,
        consumed: bool = False,
    ) -> WorkflowProtectedResidentContextAccessAuthorizationData:
        policy = code_owned_workflow_protected_resident_context_access_authorization_policy()
        profile_input = "|".join(
            (
                policy.destination_boundary_id,
                policy.destination_deployment_id,
                str(policy.destination_generation),
                policy.trusted_opener_profile_digest,
            )
        )
        return cls(
            authorization_lease_id=lease.authorization_lease_id,
            state="consumed" if consumed else lease.state.value,
            effective_state=(
                "consumed" if consumed else lease.effective_state(evaluated_at=evaluated_at).value
            ),
            issued_at=lease.issued_at,
            valid_until=lease.valid_until,
            effective_until=lease.effective_until,
            consumer_contract_id=lease.consumer_contract_id,
            consumer_contract_version=lease.consumer_contract_version,
            purpose_id=lease.purpose_id,
            policy_id=lease.policy_id,
            policy_version=lease.policy_version,
            destination_profile_reference=(
                "integrity.workflow-protected-destination-profile."
                f"{sha256(profile_input.encode('utf-8')).hexdigest()[:24]}"
            ),
            authority=WorkflowProtectedResidentContextAccessAuthorizationAuthorityData(
                protected_access_authority_granted=(
                    False if consumed else lease.protected_resident_context_access_authority_granted
                ),
                endpoint_resolution_authorized=lease.endpoint_resolution_authorized,
                route_selection_authorized=lease.route_selection_authorized,
                route_binding_authorized=lease.route_binding_authorized,
                credential_selection_authorized=lease.credential_selection_authorized,
                credential_assignment_binding_authorized=(
                    lease.credential_assignment_binding_authorized
                ),
                credential_access_authorized=lease.credential_access_authorized,
                credential_brokerage_authorized=lease.credential_brokerage_authorized,
                credential_resolution_authorized=lease.credential_resolution_authorized,
                protected_artifact_access_authorized=lease.protected_artifact_access_authorized,
                credential_delivery_authorized=lease.credential_delivery_authorized,
                network_access_authorized=lease.network_access_authorized,
                readiness_probe_authorized=lease.readiness_probe_authorized,
                publication_authorized=lease.publication_authorized,
                delivery_authorized=lease.delivery_authorized,
                dispatch_authorized=lease.dispatch_authorized,
                execution_authorized=lease.execution_authorized,
                infrastructure_mutation_authorized=lease.infrastructure_mutation_authorized,
                handoff_authorized=lease.target_context_capsule_handoff_authorized,
                protected_opening_authorized=lease.target_context_capsule_opening_authorized,
            ),
            integrity_reference=(
                "integrity.workflow-protected-access-authorization."
                f"{sha256(lease.authorization_lease_id.encode('utf-8')).hexdigest()[:24]}"
            ),
        )


class WorkflowProtectedResidentContextAccessAuthorizationInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorizations: list[WorkflowProtectedResidentContextAccessAuthorizationData] = Field(
        max_length=256
    )
    server_time: datetime
    durable: Literal[True]


class WorkflowProtectedResidentContextAccessAuthorizationResponse(BaseModel):
    data: WorkflowProtectedResidentContextAccessAuthorizationData
    meta: ResponseMeta


class WorkflowProtectedResidentContextAccessAuthorizationInventoryResponse(BaseModel):
    data: WorkflowProtectedResidentContextAccessAuthorizationInventoryData
    meta: ResponseMeta


class CreateWorkflowProtectedRuntimeContextInjectionAuthorizationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_result_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    access_result_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    policy_id: Literal["policy.workflow-protected-runtime-context-injection-authorization"]
    policy_version: Literal["1.0"]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowProtectedRuntimeContextInjectionAuthorizationAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protected_runtime_context_injection_authority_granted: bool
    protected_resident_context_access_authority_granted: Literal[False]
    target_context_capsule_opening_authorized: Literal[False]
    target_context_capsule_handoff_authorized: Literal[False]
    endpoint_resolution_authorized: Literal[False]
    route_selection_authorized: Literal[False]
    route_binding_authorized: Literal[False]
    credential_selection_authorized: Literal[False]
    credential_assignment_binding_authorized: Literal[False]
    credential_access_authorized: Literal[False]
    credential_brokerage_authorized: Literal[False]
    credential_resolution_authorized: Literal[False]
    protected_artifact_access_authorized: Literal[False]
    credential_delivery_authorized: Literal[False]
    network_access_authorized: Literal[False]
    readiness_probe_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_authorized: Literal[False]


class WorkflowProtectedRuntimeContextInjectionAuthorizationData(BaseModel):
    """Minimized future-request authorization with no runtime-handle lineage."""

    model_config = ConfigDict(extra="forbid")

    authorization_lease_id: str = Field(
        min_length=75,
        max_length=75,
        pattern=r"^workflow-protected-runtime-context-injection-lease\.[0-9a-f]{24}$",
    )
    state: Literal["authorized_unconsumed"]
    effective_state: Literal["active", "expired"]
    issued_at: datetime
    valid_until: datetime
    effective_until: datetime
    consumer_contract_id: Literal[
        "contract.workflow-protected-transport-target-context-capsule-consumer"
    ]
    consumer_contract_version: Literal["1.0"]
    purpose_id: Literal["purpose.workflow-protected-runtime-context-injection-evaluation"]
    policy_id: Literal["policy.workflow-protected-runtime-context-injection-authorization"]
    policy_version: Literal["1.0"]
    injector_profile_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    runtime_slot_profile_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    destination_profile_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    authority: WorkflowProtectedRuntimeContextInjectionAuthorizationAuthorityData
    integrity_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)

    @model_validator(mode="after")
    def validate_effective_authority(
        self,
    ) -> WorkflowProtectedRuntimeContextInjectionAuthorizationData:
        if self.authority.protected_runtime_context_injection_authority_granted != (
            self.effective_state == "active"
        ):
            raise ValueError("runtime-context injection authorization projection is inconsistent")
        return self

    @classmethod
    def from_domain(
        cls,
        presentation: WorkflowProtectedRuntimeContextInjectionAuthorizationPresentation,
    ) -> WorkflowProtectedRuntimeContextInjectionAuthorizationData:
        lease = presentation.lease
        policy = code_owned_workflow_protected_runtime_context_injection_authorization_policy()
        injector_profile = "|".join(
            (
                policy.required_injector_contract_id,
                policy.required_injector_contract_version,
                policy.approved_injector_id,
                policy.approved_injector_version,
            )
        )
        destination_profile = "|".join(
            (
                policy.destination_boundary_id,
                policy.destination_deployment_id,
                str(policy.destination_generation),
                policy.destination_fencing_token_digest,
            )
        )
        return cls(
            authorization_lease_id=lease.authorization_lease_id,
            state=WorkflowProtectedRuntimeContextInjectionAuthorizationLeaseState.AUTHORIZED_UNCONSUMED.value,
            effective_state=presentation.effective_state.value,
            issued_at=lease.issued_at,
            valid_until=lease.valid_until,
            effective_until=lease.effective_until,
            consumer_contract_id=lease.consumer_contract_id,
            consumer_contract_version=lease.consumer_contract_version,
            purpose_id=lease.purpose_id,
            policy_id=lease.policy_id,
            policy_version=lease.policy_version,
            injector_profile_reference=(
                "integrity.workflow-protected-runtime-context-injector-profile."
                f"{sha256(injector_profile.encode('utf-8')).hexdigest()[:24]}"
            ),
            runtime_slot_profile_reference=(
                "integrity.workflow-protected-runtime-slot-profile."
                f"{sha256(policy.runtime_slot_profile_digest.encode('utf-8')).hexdigest()[:24]}"
            ),
            destination_profile_reference=(
                "integrity.workflow-protected-destination-profile."
                f"{sha256(destination_profile.encode('utf-8')).hexdigest()[:24]}"
            ),
            authority=WorkflowProtectedRuntimeContextInjectionAuthorizationAuthorityData(
                protected_runtime_context_injection_authority_granted=(
                    presentation.protected_runtime_context_injection_authority_granted
                ),
                protected_resident_context_access_authority_granted=(
                    lease.protected_resident_context_access_authority_granted
                ),
                target_context_capsule_opening_authorized=(
                    lease.target_context_capsule_opening_authorized
                ),
                target_context_capsule_handoff_authorized=(
                    lease.target_context_capsule_handoff_authorized
                ),
                endpoint_resolution_authorized=lease.endpoint_resolution_authorized,
                route_selection_authorized=lease.route_selection_authorized,
                route_binding_authorized=lease.route_binding_authorized,
                credential_selection_authorized=lease.credential_selection_authorized,
                credential_assignment_binding_authorized=(
                    lease.credential_assignment_binding_authorized
                ),
                credential_access_authorized=lease.credential_access_authorized,
                credential_brokerage_authorized=lease.credential_brokerage_authorized,
                credential_resolution_authorized=lease.credential_resolution_authorized,
                protected_artifact_access_authorized=lease.protected_artifact_access_authorized,
                credential_delivery_authorized=lease.credential_delivery_authorized,
                network_access_authorized=lease.network_access_authorized,
                readiness_probe_authorized=lease.readiness_probe_authorized,
                publication_authorized=lease.publication_authorized,
                delivery_authorized=lease.delivery_authorized,
                dispatch_authorized=lease.dispatch_authorized,
                execution_authorized=lease.execution_authorized,
                infrastructure_mutation_authorized=lease.infrastructure_mutation_authorized,
            ),
            integrity_reference=(
                "integrity.workflow-protected-runtime-context-injection-authorization."
                f"{sha256(lease.authorization_lease_id.encode('utf-8')).hexdigest()[:24]}"
            ),
        )


class WorkflowProtectedRuntimeContextInjectionAuthorizationInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorizations: list[WorkflowProtectedRuntimeContextInjectionAuthorizationData] = Field(
        max_length=256
    )
    server_time: datetime
    durable: Literal[True]


class WorkflowProtectedRuntimeContextInjectionAuthorizationResponse(BaseModel):
    data: WorkflowProtectedRuntimeContextInjectionAuthorizationData
    meta: ResponseMeta


class WorkflowProtectedRuntimeContextInjectionAuthorizationInventoryResponse(BaseModel):
    data: WorkflowProtectedRuntimeContextInjectionAuthorizationInventoryData
    meta: ResponseMeta


class CreateWorkflowProtectedRuntimeContextUseAuthorizationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    injection_result_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    injection_result_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    policy_id: Literal["policy.workflow-protected-runtime-context-use-authorization"]
    policy_version: Literal["1.0"]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowProtectedRuntimeContextUseAuthorizationAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protected_runtime_context_use_authority_granted: bool
    runtime_use_authorized: Literal[False]
    runtime_start_authorized: Literal[False]
    runtime_resume_authorized: Literal[False]
    connector_activity_authorized: Literal[False]
    protected_runtime_context_injection_authority_granted: Literal[False]
    protected_resident_context_access_authority_granted: Literal[False]
    target_context_capsule_opening_authorized: Literal[False]
    target_context_capsule_handoff_authorized: Literal[False]
    endpoint_resolution_authorized: Literal[False]
    route_selection_authorized: Literal[False]
    route_binding_authorized: Literal[False]
    credential_selection_authorized: Literal[False]
    credential_assignment_binding_authorized: Literal[False]
    credential_access_authorized: Literal[False]
    credential_brokerage_authorized: Literal[False]
    credential_resolution_authorized: Literal[False]
    protected_artifact_access_authorized: Literal[False]
    credential_delivery_authorized: Literal[False]
    network_access_authorized: Literal[False]
    readiness_probe_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_authorized: Literal[False]


class WorkflowProtectedRuntimeContextUseAuthorizationData(BaseModel):
    """Minimized future-use-request authority without protected slot lineage."""

    model_config = ConfigDict(extra="forbid")

    authorization_lease_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    state: Literal["authorized_unconsumed"]
    effective_state: Literal["active", "expired"]
    issued_at: datetime
    valid_until: datetime
    effective_until: datetime
    consumer_contract_id: Literal[
        "contract.workflow-protected-transport-target-context-capsule-consumer"
    ]
    consumer_contract_version: Literal["1.0"]
    purpose_id: Literal["purpose.workflow-protected-runtime-context-use-evaluation"]
    policy_id: Literal["policy.workflow-protected-runtime-context-use-authorization"]
    policy_version: Literal["1.0"]
    use_profile_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    runtime_slot_profile_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    destination_profile_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    authority: WorkflowProtectedRuntimeContextUseAuthorizationAuthorityData
    integrity_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)

    @model_validator(mode="after")
    def validate_effective_authority(self) -> WorkflowProtectedRuntimeContextUseAuthorizationData:
        if self.authority.protected_runtime_context_use_authority_granted != (
            self.effective_state == "active"
        ):
            raise ValueError("runtime-context use authorization projection is inconsistent")
        return self

    @classmethod
    def from_domain(
        cls,
        presentation: WorkflowProtectedRuntimeContextUseAuthorizationPresentation,
    ) -> WorkflowProtectedRuntimeContextUseAuthorizationData:
        lease = presentation.lease
        policy = code_owned_workflow_protected_runtime_context_use_authorization_policy()
        destination_profile = "|".join(
            (
                lease.destination_boundary_id,
                lease.destination_deployment_id,
                str(lease.destination_generation),
                lease.destination_fencing_token_digest,
            )
        )
        authority = lease.authority
        return cls(
            authorization_lease_id=lease.authorization_lease_id,
            state=WorkflowProtectedRuntimeContextUseAuthorizationLeaseState.AUTHORIZED_UNCONSUMED.value,
            effective_state=presentation.effective_state.value,
            issued_at=lease.issued_at,
            valid_until=lease.valid_until,
            effective_until=lease.effective_until,
            consumer_contract_id=lease.consumer_contract_id,
            consumer_contract_version=lease.consumer_contract_version,
            purpose_id=lease.purpose_id,
            policy_id=lease.policy_id,
            policy_version=lease.policy_version,
            use_profile_reference=(
                "integrity.workflow-protected-runtime-context-use-profile."
                f"{sha256(policy.use_profile_digest.encode('utf-8')).hexdigest()[:24]}"
            ),
            runtime_slot_profile_reference=(
                "integrity.workflow-protected-runtime-slot-profile."
                f"{sha256(policy.runtime_slot_profile_digest.encode('utf-8')).hexdigest()[:24]}"
            ),
            destination_profile_reference=(
                "integrity.workflow-protected-destination-profile."
                f"{sha256(destination_profile.encode('utf-8')).hexdigest()[:24]}"
            ),
            authority=WorkflowProtectedRuntimeContextUseAuthorizationAuthorityData(
                protected_runtime_context_use_authority_granted=(
                    presentation.protected_runtime_context_use_authority_granted
                ),
                runtime_use_authorized=authority.runtime_use_authorized,
                runtime_start_authorized=authority.runtime_start_authorized,
                runtime_resume_authorized=authority.runtime_resume_authorized,
                connector_activity_authorized=authority.connector_activity_authorized,
                protected_runtime_context_injection_authority_granted=(
                    authority.protected_runtime_context_injection_authority_granted
                ),
                protected_resident_context_access_authority_granted=(
                    authority.protected_resident_context_access_authority_granted
                ),
                target_context_capsule_opening_authorized=(
                    authority.target_context_capsule_opening_authorized
                ),
                target_context_capsule_handoff_authorized=(
                    authority.target_context_capsule_handoff_authorized
                ),
                endpoint_resolution_authorized=authority.endpoint_resolution_authorized,
                route_selection_authorized=authority.route_selection_authorized,
                route_binding_authorized=authority.route_binding_authorized,
                credential_selection_authorized=authority.credential_selection_authorized,
                credential_assignment_binding_authorized=(
                    authority.credential_assignment_binding_authorized
                ),
                credential_access_authorized=authority.credential_access_authorized,
                credential_brokerage_authorized=authority.credential_brokerage_authorized,
                credential_resolution_authorized=authority.credential_resolution_authorized,
                protected_artifact_access_authorized=authority.protected_artifact_access_authorized,
                credential_delivery_authorized=authority.credential_delivery_authorized,
                network_access_authorized=authority.network_access_authorized,
                readiness_probe_authorized=authority.readiness_probe_authorized,
                publication_authorized=authority.publication_authorized,
                delivery_authorized=authority.delivery_authorized,
                dispatch_authorized=authority.dispatch_authorized,
                execution_authorized=authority.execution_authorized,
                infrastructure_mutation_authorized=authority.infrastructure_mutation_authorized,
            ),
            integrity_reference=(
                "integrity.workflow-protected-runtime-context-use-authorization."
                f"{sha256(lease.authorization_lease_id.encode('utf-8')).hexdigest()[:24]}"
            ),
        )


class WorkflowProtectedRuntimeContextUseAuthorizationInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorizations: list[WorkflowProtectedRuntimeContextUseAuthorizationData] = Field(
        max_length=256
    )
    server_time: datetime
    durable: bool

    @model_validator(mode="after")
    def validate_durable_inventory(
        self,
    ) -> WorkflowProtectedRuntimeContextUseAuthorizationInventoryData:
        if not self.durable:
            raise ValueError("runtime-context use authorization inventory must be durable")
        return self


class WorkflowProtectedRuntimeContextUseAuthorizationResponse(BaseModel):
    data: WorkflowProtectedRuntimeContextUseAuthorizationData
    meta: ResponseMeta


class WorkflowProtectedRuntimeContextUseAuthorizationInventoryResponse(BaseModel):
    data: WorkflowProtectedRuntimeContextUseAuthorizationInventoryData
    meta: ResponseMeta


class CreateWorkflowProtectedRuntimeStartAuthorizationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    use_result_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    use_result_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    policy_id: Literal["policy.workflow-protected-runtime-start-authorization"]
    policy_version: Literal["1.0"]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowProtectedRuntimeStartAuthorizationAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protected_runtime_start_authority_granted: bool
    runtime_use_authorized: Literal[False]
    runtime_start_authorized: Literal[False]
    runtime_resume_authorized: Literal[False]
    connector_activity_authorized: Literal[False]
    protected_runtime_context_use_authority_granted: Literal[False]
    protected_runtime_context_injection_authority_granted: Literal[False]
    protected_resident_context_access_authority_granted: Literal[False]
    target_context_capsule_opening_authorized: Literal[False]
    target_context_capsule_handoff_authorized: Literal[False]
    endpoint_resolution_authorized: Literal[False]
    route_selection_authorized: Literal[False]
    route_binding_authorized: Literal[False]
    credential_selection_authorized: Literal[False]
    credential_assignment_binding_authorized: Literal[False]
    credential_access_authorized: Literal[False]
    credential_brokerage_authorized: Literal[False]
    credential_resolution_authorized: Literal[False]
    protected_artifact_access_authorized: Literal[False]
    credential_delivery_authorized: Literal[False]
    network_access_authorized: Literal[False]
    readiness_probe_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_authorized: Literal[False]


class WorkflowProtectedRuntimeStartAuthorizationData(BaseModel):
    """Minimized future-start-request authority without protected lineage."""

    model_config = ConfigDict(extra="forbid")

    authorization_lease_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    state: Literal["authorized_unconsumed"]
    effective_state: Literal["active", "expired"]
    issued_at: datetime
    valid_until: datetime
    effective_until: datetime
    consumer_contract_id: Literal[
        "contract.workflow-protected-transport-target-context-capsule-consumer"
    ]
    consumer_contract_version: Literal["1.0"]
    purpose_id: Literal["purpose.workflow-protected-runtime-start-evaluation"]
    policy_id: Literal["policy.workflow-protected-runtime-start-authorization"]
    policy_version: Literal["1.0"]
    runtime_start_profile_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    destination_profile_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    authority: WorkflowProtectedRuntimeStartAuthorizationAuthorityData
    integrity_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)

    @model_validator(mode="after")
    def validate_effective_authority(self) -> WorkflowProtectedRuntimeStartAuthorizationData:
        if self.authority.protected_runtime_start_authority_granted != (
            self.effective_state == "active"
        ):
            raise ValueError("runtime-start authorization projection is inconsistent")
        return self

    @classmethod
    def from_domain(
        cls,
        presentation: WorkflowProtectedRuntimeStartAuthorizationPresentation,
    ) -> WorkflowProtectedRuntimeStartAuthorizationData:
        lease = presentation.lease
        policy = code_owned_workflow_protected_runtime_start_authorization_policy()
        destination_profile = "|".join(
            (
                lease.destination_deployment_id,
                str(lease.destination_generation),
                lease.destination_fencing_token_digest,
            )
        )
        authority = lease.authority
        return cls(
            authorization_lease_id=lease.authorization_lease_id,
            state=WorkflowProtectedRuntimeStartAuthorizationLeaseState.AUTHORIZED_UNCONSUMED.value,
            effective_state=presentation.effective_state.value,
            issued_at=lease.issued_at,
            valid_until=lease.valid_until,
            effective_until=lease.effective_until,
            consumer_contract_id=lease.consumer_contract_id,
            consumer_contract_version=lease.consumer_contract_version,
            purpose_id=lease.purpose_id,
            policy_id=lease.policy_id,
            policy_version=lease.policy_version,
            runtime_start_profile_reference=(
                "integrity.workflow-protected-runtime-start-profile."
                f"{sha256(policy.runtime_start_profile_digest.encode('utf-8')).hexdigest()[:24]}"
            ),
            destination_profile_reference=(
                "integrity.workflow-protected-destination-profile."
                f"{sha256(destination_profile.encode('utf-8')).hexdigest()[:24]}"
            ),
            authority=WorkflowProtectedRuntimeStartAuthorizationAuthorityData(
                protected_runtime_start_authority_granted=(
                    presentation.protected_runtime_start_authority_granted
                ),
                runtime_use_authorized=authority.runtime_use_authorized,
                runtime_start_authorized=authority.runtime_start_authorized,
                runtime_resume_authorized=authority.runtime_resume_authorized,
                connector_activity_authorized=authority.connector_activity_authorized,
                protected_runtime_context_use_authority_granted=(
                    authority.protected_runtime_context_use_authority_granted
                ),
                protected_runtime_context_injection_authority_granted=(
                    authority.protected_runtime_context_injection_authority_granted
                ),
                protected_resident_context_access_authority_granted=(
                    authority.protected_resident_context_access_authority_granted
                ),
                target_context_capsule_opening_authorized=(
                    authority.target_context_capsule_opening_authorized
                ),
                target_context_capsule_handoff_authorized=(
                    authority.target_context_capsule_handoff_authorized
                ),
                endpoint_resolution_authorized=authority.endpoint_resolution_authorized,
                route_selection_authorized=authority.route_selection_authorized,
                route_binding_authorized=authority.route_binding_authorized,
                credential_selection_authorized=authority.credential_selection_authorized,
                credential_assignment_binding_authorized=(
                    authority.credential_assignment_binding_authorized
                ),
                credential_access_authorized=authority.credential_access_authorized,
                credential_brokerage_authorized=authority.credential_brokerage_authorized,
                credential_resolution_authorized=authority.credential_resolution_authorized,
                protected_artifact_access_authorized=authority.protected_artifact_access_authorized,
                credential_delivery_authorized=authority.credential_delivery_authorized,
                network_access_authorized=authority.network_access_authorized,
                readiness_probe_authorized=authority.readiness_probe_authorized,
                publication_authorized=authority.publication_authorized,
                delivery_authorized=authority.delivery_authorized,
                dispatch_authorized=authority.dispatch_authorized,
                execution_authorized=authority.execution_authorized,
                infrastructure_mutation_authorized=authority.infrastructure_mutation_authorized,
            ),
            integrity_reference=(
                "integrity.workflow-protected-runtime-start-authorization."
                f"{sha256(lease.authorization_lease_id.encode('utf-8')).hexdigest()[:24]}"
            ),
        )


class WorkflowProtectedRuntimeStartAuthorizationInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorizations: list[WorkflowProtectedRuntimeStartAuthorizationData] = Field(max_length=256)
    server_time: datetime
    durable: bool

    @model_validator(mode="after")
    def validate_durable_inventory(
        self,
    ) -> WorkflowProtectedRuntimeStartAuthorizationInventoryData:
        if not self.durable:
            raise ValueError("runtime-start authorization inventory must be durable")
        return self


class WorkflowProtectedRuntimeStartAuthorizationResponse(BaseModel):
    data: WorkflowProtectedRuntimeStartAuthorizationData
    meta: ResponseMeta


class WorkflowProtectedRuntimeStartAuthorizationInventoryResponse(BaseModel):
    data: WorkflowProtectedRuntimeStartAuthorizationInventoryData
    meta: ResponseMeta


class CreateWorkflowProtectedRuntimeReadinessAuthorizationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_result_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    start_result_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    policy_id: Literal["policy.workflow-protected-runtime-readiness-authorization"]
    policy_version: Literal["1.0"]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowProtectedRuntimeReadinessAuthorizationAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protected_runtime_readiness_authority_granted: bool
    protected_runtime_start_authority_granted: Literal[False]
    protected_runtime_context_use_authority_granted: Literal[False]
    runtime_use_authorized: Literal[False]
    runtime_start_authorized: Literal[False]
    runtime_resume_authorized: Literal[False]
    connector_activity_authorized: Literal[False]
    protected_runtime_context_injection_authority_granted: Literal[False]
    protected_resident_context_access_authority_granted: Literal[False]
    target_context_capsule_opening_authorized: Literal[False]
    target_context_capsule_handoff_authorized: Literal[False]
    endpoint_resolution_authorized: Literal[False]
    route_selection_authorized: Literal[False]
    route_binding_authorized: Literal[False]
    credential_selection_authorized: Literal[False]
    credential_assignment_binding_authorized: Literal[False]
    credential_access_authorized: Literal[False]
    credential_brokerage_authorized: Literal[False]
    credential_resolution_authorized: Literal[False]
    protected_artifact_access_authorized: Literal[False]
    credential_delivery_authorized: Literal[False]
    network_access_authorized: Literal[False]
    readiness_probe_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_authorized: Literal[False]


class WorkflowProtectedRuntimeReadinessAuthorizationData(BaseModel):
    """Minimized future-readiness-request authority without protected lineage."""

    model_config = ConfigDict(extra="forbid")

    authorization_lease_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    state: Literal["authorized_unconsumed"]
    effective_state: Literal["active", "expired"]
    issued_at: datetime
    valid_until: datetime
    effective_until: datetime
    consumer_contract_id: Literal[
        "contract.workflow-protected-transport-target-context-capsule-consumer"
    ]
    consumer_contract_version: Literal["1.0"]
    purpose_id: Literal["purpose.workflow-protected-runtime-readiness-evaluation"]
    policy_id: Literal["policy.workflow-protected-runtime-readiness-authorization"]
    policy_version: Literal["1.0"]
    readiness_profile_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    authority: WorkflowProtectedRuntimeReadinessAuthorizationAuthorityData
    integrity_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)

    @model_validator(mode="after")
    def validate_effective_authority(
        self,
    ) -> WorkflowProtectedRuntimeReadinessAuthorizationData:
        if self.authority.protected_runtime_readiness_authority_granted != (
            self.effective_state == "active"
        ):
            raise ValueError("runtime-readiness authorization projection is inconsistent")
        return self

    @classmethod
    def from_domain(
        cls,
        presentation: WorkflowProtectedRuntimeReadinessAuthorizationPresentation,
    ) -> WorkflowProtectedRuntimeReadinessAuthorizationData:
        lease = presentation.lease
        policy = code_owned_workflow_protected_runtime_readiness_authorization_policy()
        authority = lease.authority
        return cls(
            authorization_lease_id=lease.authorization_lease_id,
            state=(
                WorkflowProtectedRuntimeReadinessAuthorizationLeaseState.AUTHORIZED_UNCONSUMED.value
            ),
            effective_state=presentation.effective_state.value,
            issued_at=lease.issued_at,
            valid_until=lease.valid_until,
            effective_until=lease.effective_until,
            consumer_contract_id=lease.consumer_contract_id,
            consumer_contract_version=lease.consumer_contract_version,
            purpose_id=lease.purpose_id,
            policy_id=lease.policy_id,
            policy_version=lease.policy_version,
            readiness_profile_reference=(
                "integrity.workflow-protected-runtime-readiness-profile."
                f"{sha256(policy.readiness_profile_digest.encode('utf-8')).hexdigest()[:24]}"
            ),
            authority=WorkflowProtectedRuntimeReadinessAuthorizationAuthorityData(
                **{
                    **authority.canonical_value(),
                    "protected_runtime_readiness_authority_granted": (
                        presentation.protected_runtime_readiness_authority_granted
                    ),
                }
            ),
            integrity_reference=(
                "integrity.workflow-protected-runtime-readiness-authorization."
                f"{sha256(lease.authorization_lease_id.encode('utf-8')).hexdigest()[:24]}"
            ),
        )


class WorkflowProtectedRuntimeReadinessAuthorizationInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorizations: list[WorkflowProtectedRuntimeReadinessAuthorizationData] = Field(max_length=256)
    server_time: datetime
    durable: bool

    @model_validator(mode="after")
    def validate_durable_inventory(
        self,
    ) -> WorkflowProtectedRuntimeReadinessAuthorizationInventoryData:
        if not self.durable:
            raise ValueError("runtime-readiness authorization inventory must be durable")
        return self


class WorkflowProtectedRuntimeReadinessAuthorizationResponse(BaseModel):
    data: WorkflowProtectedRuntimeReadinessAuthorizationData
    meta: ResponseMeta


class WorkflowProtectedRuntimeReadinessAuthorizationInventoryResponse(BaseModel):
    data: WorkflowProtectedRuntimeReadinessAuthorizationInventoryData
    meta: ResponseMeta


class CreateWorkflowProtectedRuntimeProcessCreationAuthorizationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    readiness_result_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    policy_id: Literal["policy.workflow-protected-runtime-process-creation-authorization"]
    policy_version: Literal["1.0"]
    single_use_nonrenewable_nontransferable_future_request_acknowledged: Literal[True]
    no_process_creation_or_scheduling_authority_acknowledged: Literal[True]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowProtectedRuntimeProcessCreationAuthorizationAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protected_runtime_process_creation_authority_granted: bool
    protected_runtime_readiness_authority_granted: Literal[False]
    protected_runtime_start_authority_granted: Literal[False]
    protected_runtime_context_use_authority_granted: Literal[False]
    runtime_use_authorized: Literal[False]
    runtime_start_authorized: Literal[False]
    runtime_resume_authorized: Literal[False]
    connector_activity_authorized: Literal[False]
    protected_runtime_context_injection_authority_granted: Literal[False]
    protected_resident_context_access_authority_granted: Literal[False]
    target_context_capsule_opening_authorized: Literal[False]
    target_context_capsule_handoff_authorized: Literal[False]
    endpoint_resolution_authorized: Literal[False]
    route_selection_authorized: Literal[False]
    route_binding_authorized: Literal[False]
    credential_selection_authorized: Literal[False]
    credential_assignment_binding_authorized: Literal[False]
    credential_access_authorized: Literal[False]
    credential_brokerage_authorized: Literal[False]
    credential_resolution_authorized: Literal[False]
    protected_artifact_access_authorized: Literal[False]
    credential_delivery_authorized: Literal[False]
    network_access_authorized: Literal[False]
    readiness_probe_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_authorized: Literal[False]


class WorkflowProtectedRuntimeProcessCreationAuthorizationData(BaseModel):
    """Minimized future process-creation request authority without protected lineage."""

    model_config = ConfigDict(extra="forbid")

    authorization_lease_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    readiness_result_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    state: Literal["authorized_unconsumed"]
    effective_state: Literal["active", "expired"]
    issued_at: datetime
    valid_until: datetime
    effective_until: datetime
    consumer_contract_id: Literal[
        "contract.workflow-protected-transport-target-context-capsule-consumer"
    ]
    consumer_contract_version: Literal["1.0"]
    purpose_id: Literal["purpose.workflow-protected-runtime-process-creation-request"]
    policy_id: Literal["policy.workflow-protected-runtime-process-creation-authorization"]
    policy_version: Literal["1.0"]
    process_creation_profile_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    authority: WorkflowProtectedRuntimeProcessCreationAuthorizationAuthorityData
    integrity_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)

    @model_validator(mode="after")
    def validate_effective_authority(
        self,
    ) -> WorkflowProtectedRuntimeProcessCreationAuthorizationData:
        if self.authority.protected_runtime_process_creation_authority_granted != (
            self.effective_state == "active"
        ):
            raise ValueError("runtime process-creation authorization projection is inconsistent")
        return self

    @classmethod
    def from_domain(
        cls,
        presentation: WorkflowProtectedRuntimeProcessCreationAuthorizationPresentation,
    ) -> WorkflowProtectedRuntimeProcessCreationAuthorizationData:
        lease = presentation.lease
        policy = code_owned_workflow_protected_runtime_process_creation_authorization_policy()
        authority = lease.authority
        return cls(
            authorization_lease_id=lease.authorization_lease_id,
            readiness_result_reference=(
                "integrity.workflow-protected-runtime-readiness-result."
                f"{sha256(lease.readiness_result_id.encode('utf-8')).hexdigest()[:24]}"
            ),
            state=(
                WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseState.AUTHORIZED_UNCONSUMED.value
            ),
            effective_state=presentation.effective_state.value,
            issued_at=lease.issued_at,
            valid_until=lease.valid_until,
            effective_until=lease.effective_until,
            consumer_contract_id=lease.consumer_contract_id,
            consumer_contract_version=lease.consumer_contract_version,
            purpose_id=lease.purpose_id,
            policy_id=lease.policy_id,
            policy_version=lease.policy_version,
            process_creation_profile_reference=(
                "integrity.workflow-protected-runtime-process-creation-profile."
                f"{sha256(policy.process_creation_profile_digest.encode('utf-8')).hexdigest()[:24]}"
            ),
            authority=WorkflowProtectedRuntimeProcessCreationAuthorizationAuthorityData(
                **{
                    **authority.canonical_value(),
                    "protected_runtime_process_creation_authority_granted": (
                        presentation.protected_runtime_process_creation_authority_granted
                    ),
                }
            ),
            integrity_reference=(
                "integrity.workflow-protected-runtime-process-creation-authorization."
                f"{sha256(lease.authorization_lease_id.encode('utf-8')).hexdigest()[:24]}"
            ),
        )


class WorkflowProtectedRuntimeProcessCreationAuthorizationInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorizations: list[WorkflowProtectedRuntimeProcessCreationAuthorizationData] = Field(
        max_length=256
    )
    server_time: datetime
    durable: bool

    @model_validator(mode="after")
    def validate_durable_inventory(
        self,
    ) -> WorkflowProtectedRuntimeProcessCreationAuthorizationInventoryData:
        if not self.durable:
            raise ValueError("runtime process-creation authorization inventory must be durable")
        return self


class WorkflowProtectedRuntimeProcessCreationAuthorizationResponse(BaseModel):
    data: WorkflowProtectedRuntimeProcessCreationAuthorizationData
    meta: ResponseMeta


class WorkflowProtectedRuntimeProcessCreationAuthorizationInventoryResponse(BaseModel):
    data: WorkflowProtectedRuntimeProcessCreationAuthorizationInventoryData
    meta: ResponseMeta


class CreateWorkflowProtectedRuntimeProcessSchedulingAuthorizationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    process_creation_result_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    policy_id: Literal["policy.workflow-protected-runtime-process-scheduling-authorization"]
    policy_version: Literal["1.0"]
    single_use_nonrenewable_nontransferable_future_request_acknowledged: Literal[True]
    no_scheduling_resume_dispatch_or_execution_authority_acknowledged: Literal[True]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowProtectedRuntimeProcessSchedulingAuthorizationAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protected_runtime_process_scheduling_authority_granted: bool
    protected_runtime_process_creation_authority_granted: Literal[False]
    protected_runtime_readiness_authority_granted: Literal[False]
    protected_runtime_start_authority_granted: Literal[False]
    protected_runtime_context_use_authority_granted: Literal[False]
    runtime_use_authorized: Literal[False]
    runtime_start_authorized: Literal[False]
    runtime_resume_authorized: Literal[False]
    connector_activity_authorized: Literal[False]
    protected_runtime_context_injection_authority_granted: Literal[False]
    protected_resident_context_access_authority_granted: Literal[False]
    target_context_capsule_opening_authorized: Literal[False]
    target_context_capsule_handoff_authorized: Literal[False]
    endpoint_resolution_authorized: Literal[False]
    route_selection_authorized: Literal[False]
    route_binding_authorized: Literal[False]
    credential_selection_authorized: Literal[False]
    credential_assignment_binding_authorized: Literal[False]
    credential_access_authorized: Literal[False]
    credential_brokerage_authorized: Literal[False]
    credential_resolution_authorized: Literal[False]
    protected_artifact_access_authorized: Literal[False]
    credential_delivery_authorized: Literal[False]
    network_access_authorized: Literal[False]
    readiness_probe_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_authorized: Literal[False]


class WorkflowProtectedRuntimeProcessSchedulingAuthorizationData(BaseModel):
    """Minimized future scheduling-request authority without protected process material."""

    model_config = ConfigDict(extra="forbid")

    authorization_lease_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    process_creation_result_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    state: Literal["authorized_unconsumed"]
    effective_state: Literal["active", "expired"]
    issued_at: datetime
    valid_until: datetime
    effective_until: datetime
    consumer_contract_id: Literal[
        "contract.workflow-protected-transport-target-context-capsule-consumer"
    ]
    consumer_contract_version: Literal["1.0"]
    purpose_id: Literal["purpose.workflow-protected-runtime-process-scheduling-request"]
    policy_id: Literal["policy.workflow-protected-runtime-process-scheduling-authorization"]
    policy_version: Literal["1.0"]
    authority: WorkflowProtectedRuntimeProcessSchedulingAuthorizationAuthorityData
    integrity_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)

    @model_validator(mode="after")
    def validate_effective_authority(
        self,
    ) -> WorkflowProtectedRuntimeProcessSchedulingAuthorizationData:
        if self.authority.protected_runtime_process_scheduling_authority_granted != (
            self.effective_state == "active"
        ):
            raise ValueError("runtime process-scheduling authorization projection is inconsistent")
        return self

    @classmethod
    def from_domain(
        cls,
        presentation: Any,
    ) -> WorkflowProtectedRuntimeProcessSchedulingAuthorizationData:
        lease = presentation.lease
        authority = lease.authority
        state = getattr(lease.state, "value", lease.state)
        effective_state = getattr(
            presentation.effective_state, "value", presentation.effective_state
        )
        return cls(
            authorization_lease_id=lease.authorization_lease_id,
            process_creation_result_reference=(
                "integrity.workflow-protected-runtime-process-creation-result."
                f"{sha256(lease.process_creation_result_id.encode('utf-8')).hexdigest()[:24]}"
            ),
            state=state,
            effective_state=effective_state,
            issued_at=lease.issued_at,
            valid_until=lease.valid_until,
            effective_until=lease.effective_until,
            consumer_contract_id=lease.consumer_contract_id,
            consumer_contract_version=lease.consumer_contract_version,
            purpose_id=lease.purpose_id,
            policy_id=lease.policy_id,
            policy_version=lease.policy_version,
            authority=WorkflowProtectedRuntimeProcessSchedulingAuthorizationAuthorityData(
                **{
                    **authority.canonical_value(),
                    "protected_runtime_process_scheduling_authority_granted": (
                        presentation.protected_runtime_process_scheduling_authority_granted
                    ),
                }
            ),
            integrity_reference=(
                "integrity.workflow-protected-runtime-process-scheduling-authorization."
                f"{sha256(lease.authorization_lease_id.encode('utf-8')).hexdigest()[:24]}"
            ),
        )


class WorkflowProtectedRuntimeProcessSchedulingAuthorizationInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorizations: list[WorkflowProtectedRuntimeProcessSchedulingAuthorizationData] = Field(
        max_length=256
    )
    server_time: datetime
    durable: Literal[True]


class WorkflowProtectedRuntimeProcessSchedulingAuthorizationResponse(BaseModel):
    data: WorkflowProtectedRuntimeProcessSchedulingAuthorizationData
    meta: ResponseMeta


class WorkflowProtectedRuntimeProcessSchedulingAuthorizationInventoryResponse(BaseModel):
    data: WorkflowProtectedRuntimeProcessSchedulingAuthorizationInventoryData
    meta: ResponseMeta


class CreateWorkflowProtectedRuntimeProcessCreationConsumptionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorization_lease_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    policy_id: Literal["policy.workflow-protected-runtime-process-creation-consumption"]
    policy_version: Literal["1.0"]
    irreversible_consumption_acknowledged: Literal[True]
    uncertainty_no_retry_acknowledged: Literal[True]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowProtectedRuntimeProcessCreationConsumptionData(BaseModel):
    """Minimized process-creation outcome without process or runtime material."""

    model_config = ConfigDict(extra="forbid")

    process_creation_id: str = Field(min_length=3, max_length=240, pattern=STABLE_ID)
    attempt_state: Literal["process_creation_attempt_started"]
    result_state: (
        Literal[
            "process_created_suspended_in_protected_boundary",
            "process_creation_rejected_without_creation",
            "process_creation_failed_without_creation",
            "process_creation_outcome_uncertain",
        ]
        | None
    )
    started_at: datetime
    completed_at: datetime | None
    recorded_at: datetime | None
    process_created: bool | None
    process_sealed: bool | None
    process_suspended: bool | None
    policy_reference: str = Field(min_length=1, max_length=240)
    process_creation_profile_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    primitive_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    integrity_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    effective_authority: Literal[False]

    @model_validator(mode="after")
    def validate_outcome(self) -> WorkflowProtectedRuntimeProcessCreationConsumptionData:
        pending = (
            self.result_state is None
            and self.completed_at is None
            and self.recorded_at is None
            and self.process_created is None
            and self.process_sealed is None
            and self.process_suspended is None
        )
        effective_uncertainty = (
            self.result_state == "process_creation_outcome_uncertain"
            and self.completed_at is None
            and self.recorded_at is not None
            and self.process_created is None
            and self.process_sealed is None
            and self.process_suspended is None
        )
        success = (
            self.result_state == "process_created_suspended_in_protected_boundary"
            and self.completed_at is not None
            and self.recorded_at is not None
            and self.process_created is True
            and self.process_sealed is True
            and self.process_suspended is True
        )
        known_without_creation = (
            self.result_state
            in {
                "process_creation_rejected_without_creation",
                "process_creation_failed_without_creation",
            }
            and self.completed_at is not None
            and self.recorded_at is not None
            and self.process_created is False
            and self.process_sealed is False
            and self.process_suspended is False
        )
        durable_uncertainty = (
            self.result_state == "process_creation_outcome_uncertain"
            and self.completed_at is not None
            and self.recorded_at is not None
            and self.process_created is None
            and self.process_sealed is None
            and self.process_suspended is None
        )
        if not (
            pending
            or effective_uncertainty
            or success
            or known_without_creation
            or durable_uncertainty
        ):
            raise ValueError("process-creation outcome projection is inconsistent")
        if self.recorded_at is not None and self.recorded_at < self.started_at:
            raise ValueError("process-creation outcome predates its attempt")
        if self.completed_at is not None and (
            self.completed_at < self.started_at
            or self.recorded_at is None
            or self.recorded_at < self.completed_at
        ):
            raise ValueError("process-creation completion projection is inconsistent")
        return self

    @classmethod
    def from_domain(
        cls,
        presentation: WorkflowProtectedRuntimeProcessCreationConsumptionPresentation,
        *,
        evaluated_at: datetime | None = None,
    ) -> WorkflowProtectedRuntimeProcessCreationConsumptionData:
        attempt = presentation.attempt
        result = presentation.result
        if result is not None and (
            result.attempt_id != attempt.attempt_id
            or result.attempt_digest != attempt.canonical_digest
            or result.consumption_id != attempt.consumption_id
            or result.scope != attempt.scope
        ):
            raise ValueError("process-creation attempt and outcome do not match")
        effective_uncertainty = (
            result is None
            and evaluated_at is not None
            and evaluated_at.tzinfo is not None
            and evaluated_at >= attempt.invocation_deadline
        )
        return cls(
            process_creation_id=attempt.consumption_id,
            attempt_state=attempt.state.value,
            result_state=(
                "process_creation_outcome_uncertain"
                if effective_uncertainty
                else (None if result is None else result.result_state.value)
            ),
            started_at=attempt.started_at,
            completed_at=None if result is None else result.completed_at,
            recorded_at=(
                evaluated_at
                if effective_uncertainty
                else (None if result is None else result.recorded_at)
            ),
            process_created=None if result is None else result.process_created,
            process_sealed=None if result is None else result.process_sealed,
            process_suspended=None if result is None else result.process_suspended,
            policy_reference=f"{attempt.policy_id}:{attempt.policy_version}",
            process_creation_profile_reference=(
                "integrity.workflow-protected-runtime-process-creation-profile."
                f"{sha256(attempt.process_creation_profile_digest.encode('utf-8')).hexdigest()[:24]}"
            ),
            primitive_reference=(
                "integrity.workflow-protected-runtime-process-creation-primitive."
                f"{sha256(attempt.primitive_digest.encode('utf-8')).hexdigest()[:24]}"
            ),
            integrity_reference=(
                "integrity.workflow-protected-runtime-process-creation-consumption."
                f"{sha256(attempt.canonical_digest.encode('utf-8')).hexdigest()[:24]}"
            ),
            effective_authority=False,
        )


class WorkflowProtectedRuntimeProcessCreationConsumptionInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    process_creations: list[WorkflowProtectedRuntimeProcessCreationConsumptionData] = Field(
        max_length=256
    )
    server_time: datetime
    durable: Literal[True]


class WorkflowProtectedRuntimeProcessCreationConsumptionResponse(BaseModel):
    data: WorkflowProtectedRuntimeProcessCreationConsumptionData
    meta: ResponseMeta


class WorkflowProtectedRuntimeProcessCreationConsumptionInventoryResponse(BaseModel):
    data: WorkflowProtectedRuntimeProcessCreationConsumptionInventoryData
    meta: ResponseMeta


class CreateWorkflowProtectedRuntimeProcessSchedulingConsumptionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorization_lease_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    policy_id: Literal["policy.workflow-protected-runtime-process-scheduling-consumption"]
    policy_version: Literal["1.0"]
    irreversible_consumption_acknowledged: Literal[True]
    uncertainty_no_retry_acknowledged: Literal[True]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowProtectedRuntimeProcessSchedulingConsumptionData(BaseModel):
    """Minimized scheduling outcome without process or scheduler material."""

    model_config = ConfigDict(extra="forbid")

    process_scheduling_id: str = Field(min_length=3, max_length=240, pattern=STABLE_ID)
    attempt_state: Literal["process_scheduling_attempt_started"]
    result_state: (
        Literal[
            "process_scheduled_suspended_in_protected_boundary",
            "process_scheduling_rejected_without_scheduling",
            "process_scheduling_failed_without_scheduling",
            "process_scheduling_outcome_uncertain",
        ]
        | None
    )
    started_at: datetime
    completed_at: datetime | None
    recorded_at: datetime | None
    process_scheduled: bool | None
    process_sealed: bool | None
    process_suspended: bool | None
    process_runnable: bool | None
    policy_reference: str = Field(min_length=1, max_length=240)
    scheduling_profile_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    primitive_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    integrity_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    effective_authority: Literal[False]

    @model_validator(mode="after")
    def validate_outcome(self) -> WorkflowProtectedRuntimeProcessSchedulingConsumptionData:
        pending = (
            self.result_state is None
            and self.completed_at is None
            and self.recorded_at is None
            and self.process_scheduled is None
            and self.process_sealed is None
            and self.process_suspended is None
            and self.process_runnable is None
        )
        effective_uncertainty = (
            self.result_state == "process_scheduling_outcome_uncertain"
            and self.completed_at is None
            and self.recorded_at is not None
            and self.process_scheduled is None
            and self.process_sealed is None
            and self.process_suspended is None
            and self.process_runnable is None
        )
        success = (
            self.result_state == "process_scheduled_suspended_in_protected_boundary"
            and self.completed_at is not None
            and self.recorded_at is not None
            and self.process_scheduled is True
            and self.process_sealed is True
            and self.process_suspended is True
            and self.process_runnable is False
        )
        known_without_scheduling = (
            self.result_state
            in {
                "process_scheduling_rejected_without_scheduling",
                "process_scheduling_failed_without_scheduling",
            }
            and self.completed_at is not None
            and self.recorded_at is not None
            and self.process_scheduled is False
            and self.process_sealed is True
            and self.process_suspended is True
            and self.process_runnable is False
        )
        durable_uncertainty = (
            self.result_state == "process_scheduling_outcome_uncertain"
            and self.completed_at is not None
            and self.recorded_at is not None
            and self.process_scheduled is None
            and self.process_sealed is None
            and self.process_suspended is None
            and self.process_runnable is None
        )
        if not (
            pending
            or effective_uncertainty
            or success
            or known_without_scheduling
            or durable_uncertainty
        ):
            raise ValueError("process-scheduling outcome projection is inconsistent")
        if self.recorded_at is not None and self.recorded_at < self.started_at:
            raise ValueError("process-scheduling outcome predates its attempt")
        if self.completed_at is not None and (
            self.completed_at < self.started_at
            or self.recorded_at is None
            or self.recorded_at < self.completed_at
        ):
            raise ValueError("process-scheduling completion projection is inconsistent")
        return self

    @classmethod
    def from_domain(
        cls,
        presentation: WorkflowProtectedRuntimeProcessSchedulingConsumptionPresentation,
        *,
        evaluated_at: datetime | None = None,
    ) -> WorkflowProtectedRuntimeProcessSchedulingConsumptionData:
        attempt = presentation.attempt
        result = presentation.result
        if result is not None and (
            result.attempt_id != attempt.attempt_id
            or result.attempt_digest != attempt.canonical_digest
            or result.consumption_id != attempt.consumption_id
            or result.scope != attempt.scope
        ):
            raise ValueError("process-scheduling attempt and outcome do not match")
        effective_uncertainty = (
            result is None
            and evaluated_at is not None
            and evaluated_at.tzinfo is not None
            and evaluated_at >= attempt.invocation_deadline
        )
        return cls(
            process_scheduling_id=attempt.consumption_id,
            attempt_state=attempt.state.value,
            result_state=(
                "process_scheduling_outcome_uncertain"
                if effective_uncertainty
                else (None if result is None else result.result_state.value)
            ),
            started_at=attempt.started_at,
            completed_at=None if result is None else result.completed_at,
            recorded_at=(
                evaluated_at
                if effective_uncertainty
                else (None if result is None else result.recorded_at)
            ),
            process_scheduled=None if result is None else result.process_scheduled,
            process_sealed=(
                None
                if result is None
                or result.result_state.value == "process_scheduling_outcome_uncertain"
                else True
            ),
            process_suspended=None if result is None else result.process_suspended,
            process_runnable=None if result is None else result.process_runnable,
            policy_reference=f"{attempt.policy_id}:{attempt.policy_version}",
            scheduling_profile_reference=(
                "integrity.workflow-protected-runtime-process-scheduling-profile."
                f"{sha256(attempt.scheduling_profile_digest.encode('utf-8')).hexdigest()[:24]}"
            ),
            primitive_reference=(
                "integrity.workflow-protected-runtime-process-scheduling-primitive."
                f"{sha256(attempt.primitive_digest.encode('utf-8')).hexdigest()[:24]}"
            ),
            integrity_reference=(
                "integrity.workflow-protected-runtime-process-scheduling-consumption."
                f"{sha256(attempt.canonical_digest.encode('utf-8')).hexdigest()[:24]}"
            ),
            effective_authority=False,
        )


class WorkflowProtectedRuntimeProcessSchedulingConsumptionInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    process_schedulings: list[WorkflowProtectedRuntimeProcessSchedulingConsumptionData] = Field(
        max_length=256
    )
    server_time: datetime
    durable: Literal[True]


class WorkflowProtectedRuntimeProcessSchedulingConsumptionResponse(BaseModel):
    data: WorkflowProtectedRuntimeProcessSchedulingConsumptionData
    meta: ResponseMeta


class WorkflowProtectedRuntimeProcessSchedulingConsumptionInventoryResponse(BaseModel):
    data: WorkflowProtectedRuntimeProcessSchedulingConsumptionInventoryData
    meta: ResponseMeta


class CreateWorkflowProtectedRuntimeReadinessConsumptionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorization_lease_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    policy_id: Literal["policy.workflow-protected-runtime-readiness-consumption"]
    policy_version: Literal["1.0"]
    irreversible_consumption_acknowledged: Literal[True]
    uncertainty_no_retry_acknowledged: Literal[True]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowProtectedRuntimeReadinessConsumptionData(BaseModel):
    """Minimized readiness outcome without protected invocation metadata."""

    model_config = ConfigDict(extra="forbid")

    readiness_id: str = Field(min_length=3, max_length=240, pattern=STABLE_ID)
    attempt_state: Literal["runtime_readiness_attempt_started"]
    result_state: (
        Literal[
            "runtime_ready_in_protected_boundary",
            "runtime_not_ready_in_protected_boundary",
            "runtime_readiness_failed_without_assessment",
            "runtime_readiness_outcome_uncertain",
        ]
        | None
    )
    started_at: datetime
    completed_at: datetime | None
    recorded_at: datetime | None
    runtime_ready: bool | None
    policy_reference: str = Field(min_length=1, max_length=240)
    readiness_profile_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    effective_authority: Literal[False]

    @model_validator(mode="after")
    def validate_outcome(self) -> WorkflowProtectedRuntimeReadinessConsumptionData:
        pending = (
            self.result_state is None
            and self.completed_at is None
            and self.recorded_at is None
            and self.runtime_ready is None
        )
        ready = (
            self.result_state == "runtime_ready_in_protected_boundary"
            and self.completed_at is not None
            and self.recorded_at is not None
            and self.runtime_ready is True
        )
        not_ready = (
            self.result_state == "runtime_not_ready_in_protected_boundary"
            and self.completed_at is not None
            and self.recorded_at is not None
            and self.runtime_ready is False
        )
        failed = (
            self.result_state == "runtime_readiness_failed_without_assessment"
            and self.completed_at is not None
            and self.recorded_at is not None
            and self.runtime_ready is None
        )
        uncertain = (
            self.result_state == "runtime_readiness_outcome_uncertain"
            and self.completed_at is None
            and self.recorded_at is not None
            and self.runtime_ready is None
        )
        if not (pending or ready or not_ready or failed or uncertain):
            raise ValueError("runtime-readiness outcome projection is inconsistent")
        if self.recorded_at is not None and self.recorded_at < self.started_at:
            raise ValueError("runtime-readiness outcome predates its attempt")
        if self.completed_at is not None and (
            self.completed_at < self.started_at
            or self.recorded_at is None
            or self.recorded_at < self.completed_at
        ):
            raise ValueError("runtime-readiness completion projection is inconsistent")
        return self

    @classmethod
    def from_domain(
        cls,
        presentation: WorkflowProtectedRuntimeReadinessConsumptionPresentation,
        *,
        evaluated_at: datetime | None = None,
    ) -> WorkflowProtectedRuntimeReadinessConsumptionData:
        attempt = presentation.attempt
        result = presentation.result
        if result is not None and (
            result.attempt_id != attempt.attempt_id
            or result.attempt_digest != attempt.canonical_digest
            or result.consumption_id != attempt.consumption_id
            or result.scope != attempt.scope
        ):
            raise ValueError("runtime-readiness attempt and outcome do not match")
        effective_uncertainty = (
            result is None
            and evaluated_at is not None
            and evaluated_at.tzinfo is not None
            and evaluated_at >= attempt.invocation_deadline
        )
        return cls(
            readiness_id=attempt.consumption_id,
            attempt_state=attempt.state.value,
            result_state=(
                "runtime_readiness_outcome_uncertain"
                if effective_uncertainty
                else (None if result is None else result.state.value)
            ),
            started_at=attempt.started_at,
            completed_at=None if result is None else result.completed_at,
            recorded_at=(
                evaluated_at
                if effective_uncertainty
                else (None if result is None else result.recorded_at)
            ),
            runtime_ready=None if result is None else result.runtime_ready,
            policy_reference=f"{attempt.policy_id}:{attempt.policy_version}",
            readiness_profile_reference=(
                "integrity.workflow-protected-runtime-readiness-profile."
                f"{sha256(attempt.readiness_profile_digest.encode('utf-8')).hexdigest()[:24]}"
            ),
            effective_authority=False,
        )


class WorkflowProtectedRuntimeReadinessConsumptionInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    readiness: list[WorkflowProtectedRuntimeReadinessConsumptionData] = Field(max_length=256)
    server_time: datetime
    durable: Literal[True]


class WorkflowProtectedRuntimeReadinessConsumptionResponse(BaseModel):
    data: WorkflowProtectedRuntimeReadinessConsumptionData
    meta: ResponseMeta


class WorkflowProtectedRuntimeReadinessConsumptionInventoryResponse(BaseModel):
    data: WorkflowProtectedRuntimeReadinessConsumptionInventoryData
    meta: ResponseMeta


class CreateWorkflowProtectedRuntimeStartConsumptionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorization_lease_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    policy_id: Literal["policy.workflow-protected-runtime-start"]
    policy_version: Literal["1.0"]
    irreversible_consumption_acknowledged: Literal[True]
    uncertainty_no_retry_acknowledged: Literal[True]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowProtectedRuntimeStartConsumptionData(BaseModel):
    """Minimized runtime-start outcome without protected invocation metadata."""

    model_config = ConfigDict(extra="forbid")

    start_id: str = Field(min_length=3, max_length=240, pattern=STABLE_ID)
    attempt_state: Literal["runtime_start_attempt_started"]
    result_state: (
        Literal[
            "runtime_started_in_protected_boundary",
            "runtime_start_failed_without_start",
            "runtime_start_outcome_uncertain",
        ]
        | None
    )
    started_at: datetime
    completed_at: datetime | None
    recorded_at: datetime | None
    runtime_started: bool | None
    policy_reference: str = Field(min_length=1, max_length=240)
    runtime_start_profile_reference: str = Field(
        min_length=3,
        max_length=128,
        pattern=STABLE_ID,
    )
    effective_authority: Literal[False]

    @model_validator(mode="after")
    def validate_outcome(self) -> WorkflowProtectedRuntimeStartConsumptionData:
        pending = (
            self.result_state is None
            and self.completed_at is None
            and self.recorded_at is None
            and self.runtime_started is None
        )
        success = (
            self.result_state == "runtime_started_in_protected_boundary"
            and self.completed_at is not None
            and self.recorded_at is not None
            and self.runtime_started is True
        )
        failed = (
            self.result_state == "runtime_start_failed_without_start"
            and self.completed_at is not None
            and self.recorded_at is not None
            and self.runtime_started is False
        )
        uncertain = (
            self.result_state == "runtime_start_outcome_uncertain"
            and self.completed_at is None
            and self.recorded_at is not None
            and self.runtime_started is None
        )
        if not (pending or success or failed or uncertain):
            raise ValueError("runtime-start outcome projection is inconsistent")
        if self.recorded_at is not None and self.recorded_at < self.started_at:
            raise ValueError("runtime-start outcome predates its attempt")
        if self.completed_at is not None and (
            self.completed_at < self.started_at
            or self.recorded_at is None
            or self.recorded_at < self.completed_at
        ):
            raise ValueError("runtime-start completion projection is inconsistent")
        return self

    @classmethod
    def from_domain(
        cls,
        attempt: WorkflowProtectedRuntimeStartConsumptionAttempt,
        result: WorkflowProtectedRuntimeStartConsumptionResult | None,
        *,
        evaluated_at: datetime | None = None,
    ) -> WorkflowProtectedRuntimeStartConsumptionData:
        if result is not None and (
            result.attempt_id != attempt.attempt_id
            or result.attempt_digest != attempt.canonical_digest
            or result.consumption_id != attempt.consumption_id
            or result.scope != attempt.scope
        ):
            raise ValueError("runtime-start attempt and outcome do not match")
        effective_uncertainty = (
            result is None
            and evaluated_at is not None
            and evaluated_at.tzinfo is not None
            and evaluated_at >= attempt.invocation_deadline
        )
        return cls(
            start_id=attempt.consumption_id,
            attempt_state=attempt.state.value,
            result_state=(
                "runtime_start_outcome_uncertain"
                if effective_uncertainty
                else (None if result is None else result.state.value)
            ),
            started_at=attempt.started_at,
            completed_at=None if result is None else result.completed_at,
            recorded_at=(
                evaluated_at
                if effective_uncertainty
                else (None if result is None else result.recorded_at)
            ),
            runtime_started=None if result is None else result.runtime_started,
            policy_reference=f"{attempt.policy_id}:{attempt.policy_version}",
            runtime_start_profile_reference=(
                "integrity.workflow-protected-runtime-start-profile."
                f"{sha256(attempt.runtime_start_profile_digest.encode('utf-8')).hexdigest()[:24]}"
            ),
            effective_authority=False,
        )


class WorkflowProtectedRuntimeStartConsumptionInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    starts: list[WorkflowProtectedRuntimeStartConsumptionData] = Field(max_length=256)
    server_time: datetime
    durable: Literal[True]


class WorkflowProtectedRuntimeStartConsumptionResponse(BaseModel):
    data: WorkflowProtectedRuntimeStartConsumptionData
    meta: ResponseMeta


class WorkflowProtectedRuntimeStartConsumptionInventoryResponse(BaseModel):
    data: WorkflowProtectedRuntimeStartConsumptionInventoryData
    meta: ResponseMeta


class CreateWorkflowProtectedRuntimeContextUseAuthorizationConsumptionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorization_lease_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    policy_id: Literal["policy.workflow-protected-runtime-context-use-authorization-consumption"]
    policy_version: Literal["1.0"]
    irreversible_consumption_acknowledged: Literal[True]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowProtectedRuntimeContextUseAuthorizationConsumptionAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protected_runtime_context_use_authority_granted: Literal[False]
    runtime_use_authorized: Literal[False]
    runtime_start_authorized: Literal[False]
    runtime_resume_authorized: Literal[False]
    connector_activity_authorized: Literal[False]
    protected_runtime_context_injection_authority_granted: Literal[False]
    protected_resident_context_access_authority_granted: Literal[False]
    target_context_capsule_opening_authorized: Literal[False]
    target_context_capsule_handoff_authorized: Literal[False]
    endpoint_resolution_authorized: Literal[False]
    route_selection_authorized: Literal[False]
    route_binding_authorized: Literal[False]
    credential_selection_authorized: Literal[False]
    credential_assignment_binding_authorized: Literal[False]
    credential_access_authorized: Literal[False]
    credential_brokerage_authorized: Literal[False]
    credential_resolution_authorized: Literal[False]
    protected_artifact_access_authorized: Literal[False]
    credential_delivery_authorized: Literal[False]
    network_access_authorized: Literal[False]
    readiness_probe_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_authorized: Literal[False]


class WorkflowProtectedRuntimeContextUseAuthorizationConsumptionData(BaseModel):
    """Terminal lease-consumption evidence without protected lineage or authority."""

    model_config = ConfigDict(extra="forbid")

    consumption_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    state: Literal["authorization_consumed_without_runtime_use"]
    consumed_at: datetime
    consumer_contract_id: Literal[
        "contract.workflow-protected-transport-target-context-capsule-consumer"
    ]
    consumer_contract_version: Literal["1.0"]
    purpose_id: Literal["purpose.workflow-protected-runtime-context-use-authorization-consumption"]
    policy_id: Literal["policy.workflow-protected-runtime-context-use-authorization-consumption"]
    policy_version: Literal["1.0"]
    lease_consumed: Literal[True]
    protected_runtime_context_use_authority_granted: Literal[False]
    authority: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionAuthorityData
    integrity_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)

    @classmethod
    def from_domain(
        cls,
        presentation: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPresentation,
    ) -> WorkflowProtectedRuntimeContextUseAuthorizationConsumptionData:
        result = presentation.result
        return cls(
            consumption_id=result.consumption_id,
            state=result.state.value,
            consumed_at=result.consumed_at,
            consumer_contract_id=result.consumer_contract_id,
            consumer_contract_version=result.consumer_contract_version,
            purpose_id=result.purpose_id,
            policy_id=result.policy_id,
            policy_version=result.policy_version,
            lease_consumed=result.authorization_lease_consumed,
            protected_runtime_context_use_authority_granted=(
                result.authority.protected_runtime_context_use_authority_granted
            ),
            authority=(
                WorkflowProtectedRuntimeContextUseAuthorizationConsumptionAuthorityData.model_validate(
                    result.authority.canonical_value()
                )
            ),
            integrity_reference=(
                "integrity.workflow-protected-runtime-context-use-authorization-consumption."
                f"{sha256(result.consumption_id.encode('utf-8')).hexdigest()[:24]}"
            ),
        )


class WorkflowProtectedRuntimeContextUseAuthorizationConsumptionInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consumptions: list[WorkflowProtectedRuntimeContextUseAuthorizationConsumptionData] = Field(
        max_length=256
    )
    server_time: datetime
    durable: Literal[True]


class WorkflowProtectedRuntimeContextUseAuthorizationConsumptionResponse(BaseModel):
    data: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionData
    meta: ResponseMeta


class WorkflowProtectedRuntimeContextUseAuthorizationConsumptionInventoryResponse(BaseModel):
    data: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionInventoryData
    meta: ResponseMeta


class CreateWorkflowProtectedRuntimeContextUseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorization_consumption_result_id: str = Field(
        min_length=3, max_length=128, pattern=STABLE_ID
    )
    authorization_consumption_result_digest: str = Field(
        min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$"
    )
    policy_id: Literal["policy.workflow-protected-runtime-context-use"]
    policy_version: Literal["1.0"]
    irreversible_use_acknowledged: Literal[True]
    uncertainty_no_retry_acknowledged: Literal[True]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowProtectedRuntimeContextUseAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protected_runtime_context_use_authority_granted: Literal[False]
    runtime_use_authorized: Literal[False]
    runtime_start_authorized: Literal[False]
    runtime_resume_authorized: Literal[False]
    connector_activity_authorized: Literal[False]
    protected_runtime_context_injection_authority_granted: Literal[False]
    protected_resident_context_access_authority_granted: Literal[False]
    target_context_capsule_opening_authorized: Literal[False]
    target_context_capsule_handoff_authorized: Literal[False]
    endpoint_resolution_authorized: Literal[False]
    route_selection_authorized: Literal[False]
    route_binding_authorized: Literal[False]
    credential_selection_authorized: Literal[False]
    credential_assignment_binding_authorized: Literal[False]
    credential_access_authorized: Literal[False]
    credential_brokerage_authorized: Literal[False]
    credential_resolution_authorized: Literal[False]
    protected_artifact_access_authorized: Literal[False]
    credential_delivery_authorized: Literal[False]
    network_access_authorized: Literal[False]
    readiness_probe_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_authorized: Literal[False]


class WorkflowProtectedRuntimeContextUseData(BaseModel):
    """Minimized protected-side adoption evidence without protected material."""

    model_config = ConfigDict(extra="forbid")

    use_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    attempt_state: Literal["started", "completed"]
    result_state: Literal[
        "use_pending",
        "context_used_once_in_protected_boundary",
        "context_use_failed_without_use",
        "context_use_outcome_uncertain",
    ]
    started_at: datetime
    completed_at: datetime | None
    context_use_performed: bool | None
    policy_id: Literal["policy.workflow-protected-runtime-context-use"]
    policy_version: Literal["1.0"]
    use_profile_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    authority: WorkflowProtectedRuntimeContextUseAuthorityData
    integrity_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)

    @classmethod
    def from_domain(
        cls,
        presentation: WorkflowProtectedRuntimeContextUsePresentation,
        *,
        evaluated_at: datetime,
    ) -> WorkflowProtectedRuntimeContextUseData:
        if evaluated_at.tzinfo is None:
            raise ValueError("runtime context use presentation time must be timezone-aware")
        attempt: WorkflowProtectedRuntimeContextUseAttempt = presentation.attempt
        result: WorkflowProtectedRuntimeContextUseResult | None = presentation.result
        result_state = (
            result.state.value
            if result is not None
            else "use_pending"
            if evaluated_at < attempt.use_deadline
            else "context_use_outcome_uncertain"
        )
        context_use_performed: bool | None = None
        completed_at: datetime | None = None
        if result is not None:
            completed_at = result.completed_at or result.recorded_at
            success_state = UseResultState.CONTEXT_USED_ONCE_IN_PROTECTED_BOUNDARY
            if result.state is success_state:
                context_use_performed = True
            elif result.state is UseResultState.CONTEXT_USE_FAILED_WITHOUT_USE:
                context_use_performed = False
        authority = attempt.authority if result is None else result.authority
        return cls(
            use_id=attempt.use_id,
            attempt_state="started" if result is None else "completed",
            result_state=result_state,
            started_at=attempt.started_at,
            completed_at=completed_at,
            context_use_performed=context_use_performed,
            policy_id=attempt.policy_id,
            policy_version=attempt.policy_version,
            use_profile_reference=(
                "integrity.workflow-protected-runtime-context-use-profile."
                f"{sha256(attempt.use_profile_digest.encode('utf-8')).hexdigest()[:24]}"
            ),
            authority=WorkflowProtectedRuntimeContextUseAuthorityData.model_validate(
                authority.canonical_value()
            ),
            integrity_reference=(
                "integrity.workflow-protected-runtime-context-use."
                f"{sha256(attempt.use_id.encode('utf-8')).hexdigest()[:24]}"
            ),
        )


class WorkflowProtectedRuntimeContextUseInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uses: list[WorkflowProtectedRuntimeContextUseData] = Field(max_length=256)
    server_time: datetime
    durable: Literal[True]


class WorkflowProtectedRuntimeContextUseResponse(BaseModel):
    data: WorkflowProtectedRuntimeContextUseData
    meta: ResponseMeta


class WorkflowProtectedRuntimeContextUseInventoryResponse(BaseModel):
    data: WorkflowProtectedRuntimeContextUseInventoryData
    meta: ResponseMeta


class CreateWorkflowProtectedRuntimeContextInjectionConsumptionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorization_lease_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    policy_id: Literal["policy.workflow-protected-runtime-context-injection-consumption"]
    policy_version: Literal["1.0"]
    irreversible_consumption_acknowledged: Literal[True]
    uncertain_outcome_requires_new_authorization_acknowledged: Literal[True]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowProtectedRuntimeContextInjectionConsumptionData(BaseModel):
    """Minimized injection outcome with no handle or runtime-slot locator."""

    model_config = ConfigDict(extra="forbid")

    injection_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    attempt_state: Literal["started", "completed"]
    result_state: Literal[
        "injection_pending",
        "injected_into_protected_runtime_slot",
        "injection_failed",
        "injection_outcome_uncertain",
    ]
    started_at: datetime
    completed_at: datetime | None
    policy_id: Literal["policy.workflow-protected-runtime-context-injection-consumption"]
    policy_version: Literal["1.0"]
    injector_profile_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    runtime_slot_profile_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    integrity_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)

    @classmethod
    def from_domain(
        cls,
        presentation: WorkflowProtectedRuntimeContextInjectionConsumptionPresentation,
        *,
        evaluated_at: datetime,
    ) -> WorkflowProtectedRuntimeContextInjectionConsumptionData:
        if evaluated_at.tzinfo is None:
            raise ValueError("runtime context injection presentation time must be timezone-aware")
        attempt: WorkflowProtectedRuntimeContextInjectionConsumptionAttempt = presentation.attempt
        result: WorkflowProtectedRuntimeContextInjectionConsumptionResult | None = (
            presentation.result
        )
        result_state = (
            result.state.value
            if result is not None
            else "injection_pending"
            if evaluated_at < attempt.injection_deadline
            else "injection_outcome_uncertain"
        )
        terminal = result is not None and result.completed_at is not None
        return cls(
            injection_id=attempt.injection_id,
            attempt_state="completed" if terminal else "started",
            result_state=result_state,
            started_at=attempt.started_at,
            completed_at=None if result is None else result.completed_at,
            policy_id=attempt.policy_id,
            policy_version=attempt.policy_version,
            injector_profile_reference=(
                "integrity.workflow-protected-runtime-context-injector-profile."
                f"{sha256(f'{attempt.approved_injector_id}|{attempt.approved_injector_version}'.encode()).hexdigest()[:24]}"
            ),
            runtime_slot_profile_reference=(
                "integrity.workflow-protected-runtime-slot-profile."
                f"{sha256(attempt.runtime_slot_profile_digest.encode('utf-8')).hexdigest()[:24]}"
            ),
            integrity_reference=(
                "integrity.workflow-protected-runtime-context-injection-consumption."
                f"{sha256(attempt.injection_id.encode('utf-8')).hexdigest()[:24]}"
            ),
        )


class WorkflowProtectedRuntimeContextInjectionConsumptionInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consumptions: list[WorkflowProtectedRuntimeContextInjectionConsumptionData] = Field(
        max_length=256
    )
    server_time: datetime
    durable: Literal[True]


class WorkflowProtectedRuntimeContextInjectionConsumptionResponse(BaseModel):
    data: WorkflowProtectedRuntimeContextInjectionConsumptionData
    meta: ResponseMeta


class WorkflowProtectedRuntimeContextInjectionConsumptionInventoryResponse(BaseModel):
    data: WorkflowProtectedRuntimeContextInjectionConsumptionInventoryData
    meta: ResponseMeta


class CreateWorkflowProtectedResidentContextAccessConsumptionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorization_lease_id: str = Field(
        min_length=73,
        max_length=73,
        pattern=r"^workflow-protected-resident-context-access-lease\.[0-9a-f]{24}$",
    )
    policy_id: Literal["policy.workflow-protected-resident-context-access-consumption"]
    policy_version: Literal["1.0"]
    irreversible_consumption_acknowledged: Literal[True]
    uncertain_outcome_requires_new_authorization_acknowledged: Literal[True]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowProtectedResidentContextAccessConsumptionAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protected_resident_context_access_authority_granted: Literal[False]
    target_context_capsule_opening_authorized: Literal[False]
    target_context_capsule_handoff_authorized: Literal[False]
    endpoint_resolution_authorized: Literal[False]
    route_selection_authorized: Literal[False]
    route_binding_authorized: Literal[False]
    credential_selection_authorized: Literal[False]
    credential_assignment_binding_authorized: Literal[False]
    credential_access_authorized: Literal[False]
    credential_brokerage_authorized: Literal[False]
    credential_resolution_authorized: Literal[False]
    protected_artifact_access_authorized: Literal[False]
    credential_delivery_authorized: Literal[False]
    network_access_authorized: Literal[False]
    readiness_probe_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_authorized: Literal[False]


class WorkflowProtectedResidentContextAccessConsumptionData(BaseModel):
    """Minimized access outcome with no resident-context or handle identity."""

    model_config = ConfigDict(extra="forbid")

    access_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    attempt_state: Literal["started", "completed"]
    result_state: Literal[
        "access_pending",
        "handle_established_in_protected_boundary",
        "resident_context_access_failed",
        "access_outcome_uncertain",
    ]
    started_at: datetime
    completed_at: datetime | None
    consumer_contract_id: Literal[
        "contract.workflow-protected-transport-target-context-capsule-consumer"
    ]
    consumer_contract_version: Literal["1.0"]
    purpose_id: Literal["purpose.workflow-protected-resident-context-access-consumption"]
    accessor_contract_id: Literal["contract.workflow-protected-resident-context-accessor"]
    accessor_contract_version: Literal["1.0"]
    accessor_profile_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    runtime_profile_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    policy_id: Literal["policy.workflow-protected-resident-context-access-consumption"]
    policy_version: Literal["1.0"]
    authority: WorkflowProtectedResidentContextAccessConsumptionAuthorityData
    integrity_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)

    @classmethod
    def from_domain(
        cls,
        attempt: WorkflowProtectedResidentContextAccessConsumptionAttempt,
        result: WorkflowProtectedResidentContextAccessConsumptionResult | None,
        *,
        evaluated_at: datetime,
    ) -> WorkflowProtectedResidentContextAccessConsumptionData:
        if evaluated_at.tzinfo is None:
            raise ValueError("resident context access presentation time must be timezone-aware")
        result_state = (
            result.state.value
            if result is not None
            else "access_pending"
            if evaluated_at < attempt.access_deadline
            else "access_outcome_uncertain"
        )
        terminal = result is not None and result.completed_at is not None
        return cls(
            access_id=attempt.access_id,
            attempt_state="completed" if terminal else "started",
            result_state=result_state,
            started_at=attempt.started_at,
            completed_at=None if result is None else result.completed_at,
            consumer_contract_id=attempt.consumer_contract_id,
            consumer_contract_version=attempt.consumer_contract_version,
            purpose_id=attempt.purpose_id,
            accessor_contract_id=attempt.required_accessor_contract_id,
            accessor_contract_version=attempt.required_accessor_contract_version,
            accessor_profile_reference=(
                "integrity.workflow-protected-resident-context-accessor-profile."
                f"{sha256(f'{attempt.approved_accessor_id}|{attempt.approved_accessor_version}'.encode()).hexdigest()[:24]}"
            ),
            runtime_profile_reference=(
                "integrity.workflow-protected-runtime-context-profile."
                f"{sha256(attempt.runtime_handle_profile_digest.encode('utf-8')).hexdigest()[:24]}"
            ),
            policy_id=attempt.policy_id,
            policy_version=attempt.policy_version,
            authority=WorkflowProtectedResidentContextAccessConsumptionAuthorityData.model_validate(
                attempt.authority.canonical_value()
            ),
            integrity_reference=(
                "integrity.workflow-protected-resident-context-access-consumption."
                f"{sha256(attempt.access_id.encode('utf-8')).hexdigest()[:24]}"
            ),
        )


class WorkflowProtectedResidentContextAccessConsumptionInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consumptions: list[WorkflowProtectedResidentContextAccessConsumptionData] = Field(
        max_length=256
    )
    server_time: datetime
    durable: Literal[True]


class WorkflowProtectedResidentContextAccessConsumptionResponse(BaseModel):
    data: WorkflowProtectedResidentContextAccessConsumptionData
    meta: ResponseMeta


class WorkflowProtectedResidentContextAccessConsumptionInventoryResponse(BaseModel):
    data: WorkflowProtectedResidentContextAccessConsumptionInventoryData
    meta: ResponseMeta


class CreateWorkflowProtectedTransportTargetContextCapsuleOpeningInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorization_lease_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    authorization_lease_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    policy_id: Literal[
        "policy.workflow-protected-transport-target-context-capsule-opening-consumption"
    ]
    policy_version: Literal["1.0"]
    irreversible_consumption_acknowledged: Literal[True]
    uncertain_outcome_requires_new_authorization_acknowledged: Literal[True]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    endpoint_resolution_authorized: Literal[False]
    route_selection_authorized: Literal[False]
    route_binding_authorized: Literal[False]
    credential_selection_authorized: Literal[False]
    credential_assignment_binding_authorized: Literal[False]
    credential_access_authorized: Literal[False]
    credential_brokerage_authorized: Literal[False]
    credential_resolution_authorized: Literal[False]
    protected_artifact_access_authorized: Literal[False]
    credential_delivery_authorized: Literal[False]
    network_access_authorized: Literal[False]
    readiness_probe_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_authorized: Literal[False]
    target_context_capsule_handoff_authorized: Literal[False]
    target_context_capsule_opening_authorized: Literal[False]


class WorkflowProtectedTransportTargetContextCapsuleOpeningData(BaseModel):
    """Minimized opening evidence without protected capsule or context lineage."""

    model_config = ConfigDict(extra="forbid")

    opening_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    scope: WorkflowScopeData
    attempt_state: Literal["started", "completed"]
    result_state: Literal[
        "pending",
        "opened_in_protected_consumer_boundary",
        "opening_failed",
        "opening_outcome_uncertain",
    ]
    started_at: datetime
    completed_at: datetime | None
    consumer_contract_id: Literal[
        "contract.workflow-protected-transport-target-context-capsule-consumer"
    ]
    consumer_contract_version: Literal["1.0"]
    purpose_id: Literal[
        "purpose.workflow-protected-transport-target-context-capsule-opening-evaluation"
    ]
    opener_contract_id: Literal[
        "contract.workflow-protected-target-context-capsule-consumer-boundary-opener"
    ]
    opener_contract_version: Literal["1.0"]
    resident_context_profile_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    capsule_opened_in_protected_boundary: bool
    target_context_pair_verified: bool
    resident_context_is_bearer_capability: Literal[False]
    policy_id: Literal[
        "policy.workflow-protected-transport-target-context-capsule-opening-consumption"
    ]
    policy_version: Literal["1.0"]
    authority: WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorityData
    integrity_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)

    @classmethod
    def from_domain(
        cls,
        attempt: WorkflowProtectedTransportTargetContextCapsuleOpeningAttempt,
        result: WorkflowProtectedTransportTargetContextCapsuleOpeningResult | None,
        *,
        evaluated_at: datetime,
    ) -> WorkflowProtectedTransportTargetContextCapsuleOpeningData:
        if evaluated_at.tzinfo is None:
            raise ValueError("capsule opening presentation time must be timezone-aware")
        result_state = (
            result.state.value
            if result is not None
            else "pending"
            if evaluated_at < attempt.opening_deadline
            else "opening_outcome_uncertain"
        )
        terminal = result is not None and result.completed_at is not None
        return cls(
            opening_id=attempt.opening_id,
            scope=WorkflowScopeData.model_validate(attempt.scope.canonical_value()),
            attempt_state="completed" if terminal else "started",
            result_state=result_state,
            started_at=attempt.started_at,
            completed_at=None if result is None else result.completed_at,
            consumer_contract_id=attempt.consumer_contract_id,
            consumer_contract_version=attempt.consumer_contract_version,
            purpose_id=attempt.purpose_id,
            opener_contract_id=attempt.required_opener_contract_id,
            opener_contract_version=attempt.required_opener_contract_version,
            resident_context_profile_reference=(
                "integrity.workflow-target-context-capsule-resident-context-profile."
                f"{sha256(attempt.trusted_opener_profile_digest.encode('utf-8')).hexdigest()[:24]}"
            ),
            capsule_opened_in_protected_boundary=(
                False if result is None else result.capsule_opened_in_protected_boundary
            ),
            target_context_pair_verified=(
                False if result is None else result.target_context_pair_verified
            ),
            resident_context_is_bearer_capability=False,
            policy_id=attempt.policy_id,
            policy_version=attempt.policy_version,
            authority=WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorityData.model_validate(
                attempt.authority.canonical_value()
            ),
            integrity_reference=(
                "integrity.workflow-target-context-capsule-opening."
                f"{sha256(attempt.opening_id.encode('utf-8')).hexdigest()[:24]}"
            ),
        )


class WorkflowProtectedTransportTargetContextCapsuleOpeningInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    physical_transport_target_context_capsule_openings: list[
        WorkflowProtectedTransportTargetContextCapsuleOpeningData
    ] = Field(max_length=256)
    server_time: datetime
    durable: Literal[True]


class WorkflowProtectedTransportTargetContextCapsuleOpeningResponse(BaseModel):
    data: WorkflowProtectedTransportTargetContextCapsuleOpeningData
    meta: ResponseMeta


class WorkflowProtectedTransportTargetContextCapsuleOpeningInventoryResponse(BaseModel):
    data: WorkflowProtectedTransportTargetContextCapsuleOpeningInventoryData
    meta: ResponseMeta


class CreateWorkflowProtectedTransportTargetContextCapsuleHandoffInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authorization_lease_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    authorization_lease_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    policy_id: Literal[
        "policy.workflow-protected-transport-target-context-capsule-handoff-consumption"
    ]
    policy_version: Literal["1.0"]
    irreversible_consumption_acknowledged: Literal[True]
    uncertain_outcome_requires_new_authorization_acknowledged: Literal[True]
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowProtectedTransportTargetContextCapsuleHandoffPolicyData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: Literal[
        "policy.workflow-protected-transport-target-context-capsule-handoff-consumption"
    ]
    policy_version: Literal["1.0"]


class WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_context_capsule_handoff_authorized: Literal[False]
    endpoint_resolution_authorized: Literal[False]
    route_selection_authorized: Literal[False]
    route_binding_authorized: Literal[False]
    credential_selection_authorized: Literal[False]
    credential_assignment_binding_authorized: Literal[False]
    credential_access_authorized: Literal[False]
    credential_brokerage_authorized: Literal[False]
    credential_resolution_authorized: Literal[False]
    protected_artifact_access_authorized: Literal[False]
    credential_delivery_authorized: Literal[False]
    network_access_authorized: Literal[False]
    readiness_probe_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_authorized: Literal[False]


class WorkflowProtectedTransportTargetContextCapsuleHandoffData(BaseModel):
    """Minimized non-bearer handoff presentation without protected lineage."""

    model_config = ConfigDict(extra="forbid")

    handoff_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    scope: WorkflowScopeData
    attempt_state: Literal["started", "completed"]
    result_state: Literal[
        "pending",
        "handed_off_sealed",
        "handoff_failed",
        "handoff_outcome_uncertain",
    ]
    started_at: datetime
    completed_at: datetime | None
    consumer_contract_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    consumer_contract_version: str = Field(min_length=1, max_length=64)
    purpose_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    adapter_contract_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    adapter_contract_version: str = Field(min_length=1, max_length=64)
    sealed_capsule_handed_off: bool
    consumer_receipt_is_bearer_capability: Literal[False]
    policy: WorkflowProtectedTransportTargetContextCapsuleHandoffPolicyData
    authority: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorityData
    integrity_reference: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)

    @classmethod
    def from_domain(
        cls,
        attempt: WorkflowProtectedTransportTargetContextCapsuleHandoffAttempt,
        result: WorkflowProtectedTransportTargetContextCapsuleHandoffResult | None,
        *,
        evaluated_at: datetime,
    ) -> WorkflowProtectedTransportTargetContextCapsuleHandoffData:
        if evaluated_at.tzinfo is None:
            raise ValueError("handoff presentation time must be timezone-aware")
        result_state = (
            result.state.value
            if result is not None
            else "pending"
            if evaluated_at < attempt.handoff_deadline
            else "handoff_outcome_uncertain"
        )
        return cls(
            handoff_id=attempt.handoff_id,
            scope=WorkflowScopeData.model_validate(attempt.scope.canonical_value()),
            attempt_state="completed" if result is not None else "started",
            result_state=result_state,
            started_at=attempt.started_at,
            completed_at=None if result is None else result.completed_at,
            consumer_contract_id=attempt.consumer_contract_id,
            consumer_contract_version=attempt.consumer_contract_version,
            purpose_id=attempt.purpose_id,
            adapter_contract_id=attempt.adapter_contract_id,
            adapter_contract_version=attempt.adapter_contract_version,
            sealed_capsule_handed_off=(
                False if result is None else result.sealed_capsule_handed_off
            ),
            consumer_receipt_is_bearer_capability=False,
            policy=WorkflowProtectedTransportTargetContextCapsuleHandoffPolicyData(
                policy_id=attempt.policy_id,
                policy_version=attempt.policy_version,
            ),
            authority=WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorityData.model_validate(
                attempt.authority.canonical_value()
            ),
            integrity_reference=(
                "integrity.workflow-target-context-capsule-handoff."
                f"{sha256(attempt.handoff_id.encode('utf-8')).hexdigest()[:24]}"
            ),
        )


class WorkflowProtectedTransportTargetContextCapsuleHandoffInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    physical_transport_target_context_capsule_handoffs: list[
        WorkflowProtectedTransportTargetContextCapsuleHandoffData
    ] = Field(max_length=256)
    server_time: datetime
    durable: Literal[True]


class WorkflowProtectedTransportTargetContextCapsuleHandoffResponse(BaseModel):
    data: WorkflowProtectedTransportTargetContextCapsuleHandoffData
    meta: ResponseMeta


class WorkflowProtectedTransportTargetContextCapsuleHandoffInventoryResponse(BaseModel):
    data: WorkflowProtectedTransportTargetContextCapsuleHandoffInventoryData
    meta: ResponseMeta


class CreateWorkflowEventTransportCompatibilityAdmissionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    logical_channel_binding_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    logical_channel_binding_digest: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    transport_profile_snapshot_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    transport_profile_snapshot_digest: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    policy_id: Literal["policy.workflow-event-transport-compatibility"]
    policy_version: Literal["1.0"]
    policy_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class WorkflowEventTransportCompatibilityAdmissionAuthorityData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_selection_authorized: Literal[False]
    route_binding_authorized: Literal[False]
    credential_access_authorized: Literal[False]
    publication_authorized: Literal[False]
    delivery_authorized: Literal[False]
    dispatch_authorized: Literal[False]
    execution_authorized: Literal[False]


class WorkflowEventTransportCompatibilityAdmissionData(BaseModel):
    """Minimized immutable contract comparison without route or readiness claims."""

    model_config = ConfigDict(extra="forbid")

    compatibility_admission_id: str
    logical_channel_binding_id: str
    logical_channel_binding_digest: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    transport_profile_snapshot_id: str
    transport_profile_snapshot_digest: str = Field(
        min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$"
    )
    transport_profile_id: str
    transport_profile_revision: str
    policy_id: Literal["policy.workflow-event-transport-compatibility"]
    policy_version: Literal["1.0"]
    policy_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    scope: WorkflowScopeData
    event_type: Literal["WorkflowStepDispatchRequested"]
    event_version: Literal["1.0"]
    schema_uri: Literal["urn:project-atlas:event:workflow-step-dispatch-requested:1.0"]
    data_classification: Literal["internal"]
    representation_name: Literal["canonical-json"]
    encoding: Literal["utf-8"]
    delivery_semantics: Literal["at-least-once"]
    durability_required: Literal[True]
    ordering_key_kind: Literal["workflow-run"]
    retention_class: Literal["workflow-operational"]
    logical_maximum_byte_count: Literal[65_536]
    artifact_byte_count: int = Field(ge=1, le=65_536)
    profile_maximum_message_byte_count: int = Field(ge=65_536, le=16_777_216)
    admitter_subject_id: str
    admitted_at: datetime
    state: Literal["admitted"]
    authority: WorkflowEventTransportCompatibilityAdmissionAuthorityData
    canonical_digest: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")

    @classmethod
    def from_domain(
        cls, admission: WorkflowEventTransportCompatibilityAdmission
    ) -> WorkflowEventTransportCompatibilityAdmissionData:
        return cls.model_validate(admission.canonical_value())


class WorkflowEventTransportCompatibilityAdmissionInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    logical_channel_binding_id: str
    transport_compatibility_admissions: list[WorkflowEventTransportCompatibilityAdmissionData] = (
        Field(max_length=256)
    )
    durable: bool


class WorkflowEventTransportCompatibilityAdmissionResponse(BaseModel):
    data: WorkflowEventTransportCompatibilityAdmissionData
    meta: ResponseMeta


class WorkflowEventTransportCompatibilityAdmissionInventoryResponse(BaseModel):
    data: WorkflowEventTransportCompatibilityAdmissionInventoryData
    meta: ResponseMeta


class WorkflowExecutionStepRunData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_run_id: str
    run_id: str
    step_id: str
    ordinal: int
    kind: str
    capability_class: str
    timeout_seconds: int
    depends_on: list[str]
    state: Literal["not_started"]
    canonical_digest: str


class WorkflowExecutionRunData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    plan_id: str
    plan_digest: str
    definition_id: str
    definition_version: int
    definition_digest: str
    scope: WorkflowScopeData
    target_id: str
    target_type: Literal["storage"]
    lease_id: str
    lease_digest: str
    fencing_token: int
    materialized_by_subject_id: str
    created_at: datetime
    state: Literal["created"]
    step_runs: list[WorkflowExecutionStepRunData]
    authority: WorkflowPlanAuthorityData
    grants_execution_authority: Literal[False]
    canonical_digest: str

    @classmethod
    def from_domain(cls, run: WorkflowExecutionRun) -> WorkflowExecutionRunData:
        return cls.model_validate(run.canonical_value() | {"grants_execution_authority": False})


class WorkflowMaterializedRunStatusData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str
    run: WorkflowExecutionRunData | None
    server_time: datetime
    durable: bool


class WorkflowExecutionRunResponse(BaseModel):
    data: WorkflowExecutionRunData
    meta: ResponseMeta


class WorkflowMaterializedRunStatusResponse(BaseModel):
    data: WorkflowMaterializedRunStatusData
    meta: ResponseMeta


class WorkflowExecutionAttemptData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_id: str
    run_id: str
    run_digest: str
    step_run_id: str
    step_run_digest: str
    step_id: str
    attempt_number: Literal[1]
    plan_id: str
    plan_digest: str
    definition_id: str
    definition_version: int
    definition_digest: str
    scope: WorkflowScopeData
    target_id: str
    target_type: Literal["storage"]
    lease_id: str
    lease_digest: str
    fencing_token: int
    materialized_by_subject_id: str
    created_at: datetime
    state: Literal["created"]
    authority: WorkflowPlanAuthorityData
    grants_execution_authority: Literal[False]
    canonical_digest: str

    @classmethod
    def from_domain(cls, attempt: WorkflowExecutionAttempt) -> WorkflowExecutionAttemptData:
        return cls.model_validate(attempt.canonical_value() | {"grants_execution_authority": False})


class WorkflowAttemptInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    attempts: list[WorkflowExecutionAttemptData]
    server_time: datetime
    durable: bool


class WorkflowExecutionAttemptResponse(BaseModel):
    data: WorkflowExecutionAttemptData
    meta: ResponseMeta


class WorkflowAttemptInventoryResponse(BaseModel):
    data: WorkflowAttemptInventoryData
    meta: ResponseMeta


class WorkflowDispatchIntentData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dispatch_intent_id: str
    plan_id: str
    plan_digest: str
    run_id: str
    run_digest: str
    step_run_id: str
    step_run_digest: str
    step_id: str
    attempt_id: str
    attempt_digest: str
    attempt_number: Literal[1]
    scope: WorkflowScopeData
    target_id: str
    target_type: Literal["storage"]
    lease_id: str
    lease_digest: str
    fencing_token: int
    worker_subject_id: str
    staged_at: datetime
    state: Literal["staged"]
    authority: WorkflowPlanAuthorityData
    grants_publication_authority: Literal[False]
    grants_delivery_authority: Literal[False]
    grants_dispatch_authority: Literal[False]
    grants_execution_authority: Literal[False]
    canonical_digest: str

    @classmethod
    def from_domain(cls, intent: WorkflowDispatchIntent) -> WorkflowDispatchIntentData:
        return cls.model_validate(
            intent.canonical_value()
            | {
                "grants_publication_authority": intent.grants_publication_authority,
                "grants_delivery_authority": intent.grants_delivery_authority,
                "grants_dispatch_authority": intent.grants_dispatch_authority,
                "grants_execution_authority": intent.grants_execution_authority,
            }
        )


class WorkflowDispatchIntentInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attempt_id: str
    dispatch_intents: list[WorkflowDispatchIntentData]
    server_time: datetime
    durable: bool


class WorkflowDispatchIntentResponse(BaseModel):
    data: WorkflowDispatchIntentData
    meta: ResponseMeta


class WorkflowDispatchIntentInventoryResponse(BaseModel):
    data: WorkflowDispatchIntentInventoryData
    meta: ResponseMeta


class WorkflowDispatchOutboxEntryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outbox_entry_id: str
    dispatch_intent_id: str
    dispatch_intent_digest: str
    plan_id: str
    plan_digest: str
    run_id: str
    run_digest: str
    step_run_id: str
    step_run_digest: str
    step_id: str
    attempt_id: str
    attempt_digest: str
    attempt_number: Literal[1]
    scope: WorkflowScopeData
    target_id: str
    target_type: Literal["storage"]
    lease_id: str
    lease_digest: str
    fencing_token: int
    worker_subject_id: str
    admitted_at: datetime
    state: Literal["pending_publication"]
    authority: WorkflowPlanAuthorityData
    grants_publication_authority: Literal[False]
    grants_delivery_authority: Literal[False]
    grants_dispatch_authority: Literal[False]
    grants_execution_authority: Literal[False]
    canonical_digest: str

    @classmethod
    def from_domain(cls, entry: WorkflowDispatchOutboxEntry) -> WorkflowDispatchOutboxEntryData:
        return cls.model_validate(
            entry.canonical_value()
            | {
                "grants_publication_authority": entry.grants_publication_authority,
                "grants_delivery_authority": entry.grants_delivery_authority,
                "grants_dispatch_authority": entry.grants_dispatch_authority,
                "grants_execution_authority": entry.grants_execution_authority,
            }
        )


class WorkflowDispatchOutboxInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dispatch_intent_id: str
    outbox_entries: list[WorkflowDispatchOutboxEntryData] = Field(min_length=1, max_length=1)
    server_time: datetime
    durable: bool


class WorkflowDispatchOutboxInventoryResponse(BaseModel):
    data: WorkflowDispatchOutboxInventoryData
    meta: ResponseMeta


class WorkflowPlanTransitionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transition_id: str
    prior_state: Literal["planned"]
    new_state: Literal["cancelled"]
    actor_subject_id: str
    scope: WorkflowScopeData
    target_id: str
    target_type: Literal["storage"]
    reason: str
    reason_digest: str
    correlation_id: str
    occurred_at: datetime
    canonical_digest: str


class WorkflowRunPlanData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str
    definition_id: str
    definition_version: int
    definition_digest: str
    scope: WorkflowScopeData
    target_id: str
    target_type: Literal["storage"]
    canonical_input_digest: str
    creator_subject_id: str
    created_at: datetime
    state: Literal["planned", "cancelled"]
    steps: list[WorkflowPlanStepData]
    durable: bool
    authority: WorkflowPlanAuthorityData
    safety_notice: str
    canonical_digest: str
    transition_history: list[WorkflowPlanTransitionData]

    @classmethod
    def from_domain(cls, plan: WorkflowRunPlan) -> WorkflowRunPlanData:
        payload = plan.digest_payload() | {"canonical_digest": plan.canonical_digest}
        payload.setdefault("transition_history", [])
        return cls.model_validate(payload)


class WorkflowDefinitionInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    definitions: list[WorkflowDefinitionData]


class WorkflowPlanInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plans: list[WorkflowRunPlanData]
    durable: bool
    truncated: bool


class WorkflowDefinitionInventoryResponse(BaseModel):
    data: WorkflowDefinitionInventoryData
    meta: ResponseMeta


class WorkflowPlanInventoryResponse(BaseModel):
    data: WorkflowPlanInventoryData
    meta: ResponseMeta


class WorkflowRunPlanResponse(BaseModel):
    data: WorkflowRunPlanData
    meta: ResponseMeta
