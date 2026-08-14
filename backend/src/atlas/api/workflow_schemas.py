from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.workflows.domain import (
    WorkflowDefinition,
    WorkflowDispatchEventEnvelope,
    WorkflowDispatchIntent,
    WorkflowDispatchOutboxEntry,
    WorkflowEventTransportAdmission,
    WorkflowExecutionAttempt,
    WorkflowExecutionRun,
    WorkflowOrchestrationLease,
    WorkflowOutboxPublicationLease,
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
