from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.connectors.domain.instance_creation import (
    ConnectorInstanceCreationPolicySnapshot,
    ConnectorInstanceRecord,
)
from atlas.modules.connectors.domain.upgrade_approval import (
    ConnectorUpgradeApprovalDecision,
    ConnectorUpgradeApprovalRecord,
    ConnectorUpgradeApprovalRequest,
    ConnectorUpgradeApprovalRevalidation,
    ConnectorUpgradeChangeContextDraft,
    ConnectorUpgradeHandoffReadinessAssessment,
)
from atlas.modules.connectors.domain.upgrade_readiness import (
    ConnectorCapabilityChange,
    ConnectorUpgradeCandidate,
    ConnectorUpgradePlan,
    ConnectorUpgradePlanStep,
    ConnectorUpgradeReadiness,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ConnectorInstanceCreationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-instance-creation-input.v1", pattern=STABLE_ID
    )
    source_installation_receipt_id: str = Field(pattern=STABLE_ID)
    source_installation_receipt_digest: str = Field(pattern=DIGEST)
    package_digest: str = Field(pattern=DIGEST)
    instance_key: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    display_name: str = Field(min_length=3, max_length=200)
    instance_policy_id: str = Field(pattern=STABLE_ID)
    instance_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_instance_is_disabled_and_grants_no_target_or_runtime_authority: bool


class ConnectorInstanceRetirementInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-instance-retirement-input.v1", pattern=STABLE_ID
    )
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=20, max_length=1000)
    acknowledged_retirement_preserves_history_and_performs_no_runtime_action: bool


class ConnectorInstanceCreationPolicyData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    allowed_sdk_profiles: tuple[str, ...]
    allowed_capability_classes: tuple[str, ...]
    required_initial_state: str
    maximum_instance_key_length: int
    maximum_display_name_length: int
    expires_at: datetime
    canonical_digest: str

    @classmethod
    def from_domain(
        cls, policy: ConnectorInstanceCreationPolicySnapshot
    ) -> ConnectorInstanceCreationPolicyData:
        return cls(**{field: getattr(policy, field) for field in cls.model_fields})


class ConnectorInstanceRecordData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str
    schema_version: str
    version: int
    source_installation_receipt_id: str
    source_installation_receipt_digest: str
    organization_id: str
    environment_id: str
    package_digest: str
    connector_id: str
    release_version: str
    manifest_digest: str
    sdk_profile: str
    instance_policy_id: str
    instance_policy_digest: str
    instance_policy_version: str
    instance_id: str
    instance_key: str
    display_name: str
    instance_state: str
    owner_id: str
    support_group_id: str
    created_by: str
    purpose: str
    created_at: datetime
    canonical_digest: str
    package_published: bool
    connector_registered: bool
    package_installed: bool
    instance_created: bool
    eligible_for_configuration_governance: bool
    promotion_blocked: bool
    target_configured: bool
    credentials_resolved: bool
    connector_enabled: bool
    runtime_trust_granted: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool
    reused: bool
    retired_by: str | None
    retired_at: datetime | None
    retirement_reason: str | None

    @classmethod
    def from_domain(cls, record: ConnectorInstanceRecord) -> ConnectorInstanceRecordData:
        return cls(**{field: getattr(record, field) for field in cls.model_fields})


class ConnectorInstanceCreationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorInstanceRecordData
    meta: ResponseMeta


class ConnectorInstanceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorInstanceRecordData, ...]
    meta: ResponseMeta


class ConnectorInstanceCreationPolicyListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: tuple[ConnectorInstanceCreationPolicyData, ...]
    meta: ResponseMeta


class ConnectorCapabilityChangeData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_id: str
    change_type: str
    current_class: str | None
    candidate_class: str | None
    current_permission: str | None
    candidate_permission: str | None

    @classmethod
    def from_domain(cls, change: ConnectorCapabilityChange) -> ConnectorCapabilityChangeData:
        return cls(**{field: getattr(change, field) for field in cls.model_fields})


class ConnectorUpgradeCandidateData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receipt_id: str
    receipt_digest: str
    package_digest: str
    manifest_digest: str
    release_version: str
    publisher_id: str
    sdk_profile: str
    installed_at: datetime
    upgrade_class: str
    risk_level: str
    capability_changes: tuple[ConnectorCapabilityChangeData, ...]
    target_products_added: tuple[str, ...]
    target_products_removed: tuple[str, ...]
    network_destinations_added: tuple[str, ...]
    network_destinations_removed: tuple[str, ...]
    configuration_key_delta: int
    secret_reference_delta: int
    policy_review_required: bool
    configuration_migration_required: bool
    rollback_receipt_id: str
    rollback_receipt_digest: str
    review_eligible: bool
    blockers: tuple[str, ...]
    canonical_digest: str
    execution_authorized: bool
    infrastructure_mutation_performed: bool

    @classmethod
    def from_domain(cls, candidate: ConnectorUpgradeCandidate) -> ConnectorUpgradeCandidateData:
        return cls(
            **{
                field: getattr(candidate, field)
                for field in cls.model_fields
                if field != "capability_changes"
            },
            capability_changes=tuple(
                ConnectorCapabilityChangeData.from_domain(item)
                for item in candidate.capability_changes
            ),
        )


class ConnectorUpgradeReadinessData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    source_record_id: str
    source_record_version: int
    instance_id: str
    instance_key: str
    connector_id: str
    current_release_version: str
    current_package_digest: str
    current_manifest_digest: str
    current_receipt_id: str
    current_receipt_digest: str
    target_configured: bool
    candidates: tuple[ConnectorUpgradeCandidateData, ...]
    generated_at: datetime
    canonical_digest: str
    decision_support_only: bool
    execution_authorized: bool
    infrastructure_mutation_performed: bool

    @classmethod
    def from_domain(cls, readiness: ConnectorUpgradeReadiness) -> ConnectorUpgradeReadinessData:
        return cls(
            **{
                field: getattr(readiness, field)
                for field in cls.model_fields
                if field != "candidates"
            },
            candidates=tuple(
                ConnectorUpgradeCandidateData.from_domain(item) for item in readiness.candidates
            ),
        )


class ConnectorUpgradeReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorUpgradeReadinessData
    meta: ResponseMeta


class ConnectorUpgradePlanStepData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str
    sequence: int
    phase: str
    expected_minutes: int
    requires_service_interruption: bool
    rollback_boundary: bool

    @classmethod
    def from_domain(cls, step: ConnectorUpgradePlanStep) -> ConnectorUpgradePlanStepData:
        return cls(**{field: getattr(step, field) for field in cls.model_fields})


class ConnectorUpgradePlanData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str
    schema_version: str
    source_record_id: str
    source_record_version: int
    instance_id: str
    connector_id: str
    current_release_version: str
    current_receipt_id: str
    current_receipt_digest: str
    candidate_release_version: str
    candidate_receipt_id: str
    candidate_receipt_digest: str
    readiness_digest: str
    candidate_digest: str
    risk_level: str
    target_configured: bool
    target_id: str | None
    site_id: str | None
    target_product: str | None
    plan_state: str
    plan_eligible: bool
    prerequisite_ids: tuple[str, ...]
    steps: tuple[ConnectorUpgradePlanStepData, ...]
    validation_check_ids: tuple[str, ...]
    stop_condition_ids: tuple[str, ...]
    rollback_step_ids: tuple[str, ...]
    blockers: tuple[str, ...]
    unknowns: tuple[str, ...]
    estimated_interruption_min_minutes: int | None
    estimated_interruption_max_minutes: int | None
    rollback_window_minutes: int
    generated_at: datetime
    expires_at: datetime
    canonical_digest: str
    approval_required: bool
    decision_support_only: bool
    execution_authorized: bool
    infrastructure_mutation_performed: bool

    @classmethod
    def from_domain(cls, plan: ConnectorUpgradePlan) -> ConnectorUpgradePlanData:
        return cls(
            **{field: getattr(plan, field) for field in cls.model_fields if field != "steps"},
            steps=tuple(ConnectorUpgradePlanStepData.from_domain(item) for item in plan.steps),
        )


class ConnectorUpgradePlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorUpgradePlanData
    meta: ResponseMeta


class ConnectorUpgradeApprovalCreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-upgrade-approval-create-input.v1", pattern=STABLE_ID
    )
    source_plan_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_request_is_not_approval_and_grants_no_execution_authority: bool


class ConnectorUpgradeApprovalRequestData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    schema_version: str
    version: int
    source_record_id: str
    source_record_version: int
    instance_id: str
    connector_id: str
    plan_id: str
    plan_digest: str
    readiness_digest: str
    current_release_version: str
    current_receipt_id: str
    current_receipt_digest: str
    candidate_release_version: str
    candidate_receipt_id: str
    candidate_receipt_digest: str
    candidate_digest: str
    risk_level: str
    organization_id: str
    environment_id: str
    requested_by: str
    purpose: str
    approval_policy_id: str
    approval_policy_digest: str
    approval_policy_version: str
    created_at: datetime
    expires_at: datetime
    state: str
    canonical_digest: str
    separation_of_duties_required: bool
    approval_granted: bool
    decision_recorded: bool
    execution_authorized: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(
        cls, request: ConnectorUpgradeApprovalRequest
    ) -> ConnectorUpgradeApprovalRequestData:
        return cls(**{field: getattr(request, field) for field in cls.model_fields})


class ConnectorUpgradeApprovalResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorUpgradeApprovalRequestData
    meta: ResponseMeta


class ConnectorUpgradeApprovalDecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-upgrade-approval-decision-input.v1", pattern=STABLE_ID
    )
    expected_request_version: int = Field(ge=1)
    expected_request_digest: str = Field(pattern=DIGEST)
    outcome: str = Field(pattern=r"^(approve|reject|needs_evidence|defer)$")
    rationale: str = Field(min_length=20, max_length=1000)
    acknowledged_decision_grants_no_execution_authority: bool


class ConnectorUpgradeApprovalDecisionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_id: str
    schema_version: str
    version: int
    request_id: str
    request_version: int
    request_digest: str
    plan_id: str
    plan_digest: str
    outcome: str
    decided_by: str
    rationale: str
    organization_id: str
    environment_id: str
    approval_policy_id: str
    approval_policy_digest: str
    decided_at: datetime
    canonical_digest: str
    execution_authorized: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(
        cls, decision: ConnectorUpgradeApprovalDecision
    ) -> ConnectorUpgradeApprovalDecisionData:
        return cls(**{field: getattr(decision, field) for field in cls.model_fields})


class ConnectorUpgradeApprovalRevalidationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-upgrade-approval-revalidation-input.v1", pattern=STABLE_ID
    )
    expected_request_digest: str = Field(pattern=DIGEST)
    expected_decision_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_revalidation_grants_no_handoff_or_execution_authority: bool


class ConnectorUpgradeApprovalRevalidationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revalidation_id: str
    schema_version: str
    version: int
    source_record_id: str
    source_record_version: int
    instance_id: str
    connector_id: str
    request_id: str
    request_version: int
    request_digest: str
    decision_id: str
    decision_version: int
    decision_digest: str
    plan_id: str
    plan_digest: str
    readiness_digest: str
    current_receipt_id: str
    current_receipt_digest: str
    candidate_receipt_id: str
    candidate_receipt_digest: str
    approval_policy_id: str
    approval_policy_version: str
    approval_policy_digest: str
    organization_id: str
    environment_id: str
    requester_id: str
    approver_id: str
    revalidated_by: str
    purpose: str
    check_ids: tuple[str, ...]
    revalidated_at: datetime
    valid_until: datetime
    canonical_digest: str
    approval_current_at_revalidation: bool
    governance_ready: bool
    handoff_ready: bool
    target_configured: bool
    package_rebound: bool
    configuration_changed: bool
    target_contacted: bool
    handoff_artifact_issued: bool
    execution_authorized: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(
        cls, revalidation: ConnectorUpgradeApprovalRevalidation
    ) -> ConnectorUpgradeApprovalRevalidationData:
        return cls(**{field: getattr(revalidation, field) for field in cls.model_fields})


class ConnectorUpgradeApprovalRevalidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorUpgradeApprovalRevalidationData
    meta: ResponseMeta


class ConnectorUpgradeHandoffReadinessData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_id: str
    schema_version: str
    source_record_id: str
    source_record_version: int
    instance_id: str
    connector_id: str
    request_id: str
    request_digest: str
    decision_id: str
    decision_digest: str
    revalidation_id: str
    revalidation_digest: str
    plan_id: str
    plan_digest: str
    organization_id: str
    environment_id: str
    assessed_by: str
    applicability_policy_id: str
    applicability_policy_version: str
    applicability_policy_digest: str
    required_check_ids: tuple[str, ...]
    satisfied_check_ids: tuple[str, ...]
    not_applicable_check_ids: tuple[str, ...]
    blocker_ids: tuple[str, ...]
    assessed_at: datetime
    evidence_valid_until: datetime
    canonical_digest: str
    assessment_state: str
    approval_current: bool
    revalidation_current: bool
    handoff_ready: bool
    handoff_artifact_issued: bool
    approval_consumed: bool
    target_contacted: bool
    package_rebound: bool
    configuration_changed: bool
    execution_authorized: bool
    infrastructure_mutation_performed: bool

    @classmethod
    def from_domain(
        cls, assessment: ConnectorUpgradeHandoffReadinessAssessment
    ) -> ConnectorUpgradeHandoffReadinessData:
        return cls(**{field: getattr(assessment, field) for field in cls.model_fields})


class ConnectorUpgradeHandoffReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorUpgradeHandoffReadinessData
    meta: ResponseMeta


class ConnectorUpgradeChangeContextDraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-upgrade-change-context-draft-input.v1", pattern=STABLE_ID
    )
    expected_readiness_digest: str = Field(pattern=DIGEST)
    proposed_window_start: datetime
    proposed_window_end: datetime
    justification: str = Field(min_length=20, max_length=1000)
    acknowledged_draft_grants_no_dispatch_approval_handoff_or_execution_authority: bool


class ConnectorUpgradeChangeContextDraftData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: str
    schema_version: str
    source_record_id: str
    source_record_version: int
    instance_id: str
    connector_id: str
    request_id: str
    request_digest: str
    decision_digest: str
    revalidation_id: str
    revalidation_digest: str
    readiness_digest: str
    organization_id: str
    environment_id: str
    created_by: str
    justification: str
    proposed_window_start: datetime
    proposed_window_end: datetime
    itsm_draft_title: str
    itsm_draft_digest: str
    created_at: datetime
    valid_until: datetime
    canonical_digest: str
    state: str
    itsm_dispatched: bool
    window_approved: bool
    handoff_ready: bool
    handoff_artifact_issued: bool
    approval_consumed: bool
    target_contacted: bool
    package_rebound: bool
    configuration_changed: bool
    execution_authorized: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_domain(
        cls, draft: ConnectorUpgradeChangeContextDraft
    ) -> ConnectorUpgradeChangeContextDraftData:
        return cls(**{field: getattr(draft, field) for field in cls.model_fields})


class ConnectorUpgradeChangeContextDraftResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: ConnectorUpgradeChangeContextDraftData
    meta: ResponseMeta


class ConnectorUpgradeApprovalRecordData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: ConnectorUpgradeApprovalRequestData
    decision: ConnectorUpgradeApprovalDecisionData | None
    state: str
    approval_valid: bool
    approval_granted: bool
    decision_recorded: bool
    separation_of_duties_enforced: bool
    package_rebound: bool
    configuration_changed: bool
    target_contacted: bool
    execution_authorized: bool
    infrastructure_mutation_performed: bool

    @classmethod
    def from_domain(
        cls, record: ConnectorUpgradeApprovalRecord
    ) -> ConnectorUpgradeApprovalRecordData:
        return cls(
            request=ConnectorUpgradeApprovalRequestData.from_domain(record.request),
            decision=(
                ConnectorUpgradeApprovalDecisionData.from_domain(record.decision)
                if record.decision
                else None
            ),
            **{
                field: getattr(record, field)
                for field in cls.model_fields
                if field not in {"request", "decision"}
            },
        )


class ConnectorUpgradeApprovalRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorUpgradeApprovalRecordData
    meta: ResponseMeta
