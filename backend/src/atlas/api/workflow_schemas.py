from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
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
    WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAttempt,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease,
    WorkflowProtectedTransportTargetContextCapsuleHandoffResult,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAttempt,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease,
    WorkflowProtectedTransportTargetContextCapsuleOpeningResult,
    WorkflowRunPlan,
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
