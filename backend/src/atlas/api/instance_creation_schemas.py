from __future__ import annotations

from datetime import datetime
from typing import Literal

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
    ConnectorUpgradeEvidenceReceipt,
    ConnectorUpgradeEvidenceReceiptVerification,
    ConnectorUpgradeHandoffReadinessAssessment,
)
from atlas.modules.connectors.domain.upgrade_evidence_authenticity import (
    ConnectorUpgradeEvidenceSignature,
    ConnectorUpgradeEvidenceSigningKeyTrust,
    ConnectorUpgradeEvidenceSigningKeyTrustInventory,
    ConnectorUpgradeSignedEvidenceReceipt,
    ConnectorUpgradeSignedEvidenceReceiptVerification,
    ConnectorUpgradeSigningProviderConformanceAssessment,
    ConnectorUpgradeSigningProviderOnboardingReadiness,
    ConnectorUpgradeSigningProviderOnboardingRequirement,
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
    audit_readiness_evidence_id: str | None
    audit_readiness_evidence_digest: str | None
    itsm_change_evidence_id: str | None
    itsm_change_evidence_digest: str | None
    maintenance_window_evidence_id: str | None
    maintenance_window_evidence_digest: str | None
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
    audit_readiness_evidence_current: bool
    itsm_change_evidence_current: bool
    maintenance_window_evidence_current: bool
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


class ConnectorUpgradeEvidenceReceiptInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.connector-upgrade-evidence-receipt-input.v1", pattern=STABLE_ID
    )
    expected_readiness_digest: str = Field(pattern=DIGEST)
    acknowledged_receipt_is_non_executable_and_grants_no_handoff_authority: bool


class ConnectorUpgradeEvidenceReceiptData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    receipt_id: str
    schema_version: Literal["atlas.connector-upgrade-evidence-receipt.v1"]
    version: Literal[1]
    assessment_id: str
    assessment_digest: str
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
    created_by: str
    audit_readiness_evidence_id: str
    audit_readiness_evidence_digest: str
    itsm_change_evidence_id: str
    itsm_change_evidence_digest: str
    maintenance_window_evidence_id: str
    maintenance_window_evidence_digest: str
    required_check_ids: tuple[str, ...]
    satisfied_check_ids: tuple[str, ...]
    not_applicable_check_ids: tuple[str, ...]
    created_at: datetime
    valid_until: datetime
    canonical_digest: str
    evidence_receipt_only: Literal[True]
    runtime_acceptable: Literal[False]
    approval_consumed: Literal[False]
    handoff_ready: Literal[False]
    handoff_artifact_issued: Literal[False]
    target_contacted: Literal[False]
    package_rebound: Literal[False]
    configuration_changed: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_domain(
        cls, receipt: ConnectorUpgradeEvidenceReceipt
    ) -> ConnectorUpgradeEvidenceReceiptData:
        return cls(**{field: getattr(receipt, field) for field in cls.model_fields})

    def to_domain(self) -> ConnectorUpgradeEvidenceReceipt:
        return ConnectorUpgradeEvidenceReceipt(**self.model_dump())


class ConnectorUpgradeEvidenceReceiptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorUpgradeEvidenceReceiptData
    meta: ResponseMeta


class ConnectorUpgradeEvidenceReceiptVerificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.connector-upgrade-evidence-receipt-verification-input.v1"] = (
        "atlas.connector-upgrade-evidence-receipt-verification-input.v1"
    )
    receipt: ConnectorUpgradeEvidenceReceiptData
    acknowledged_digest_integrity_is_not_authenticity_or_execution_authority: Literal[True]


class ConnectorUpgradeEvidenceReceiptVerificationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verification_id: str
    schema_version: Literal["atlas.connector-upgrade-evidence-receipt-verification.v1"]
    receipt_id: str
    receipt_digest: str
    request_id: str
    organization_id: str
    environment_id: str
    verified_by: str
    verified_at: datetime
    receipt_valid_until: datetime
    verification_state: Literal["current", "stale", "expired", "unverifiable"]
    reason_codes: tuple[str, ...]
    canonical_digest: str
    integrity_valid: Literal[True]
    current_state_compared: bool
    current_state_matches: bool
    receipt_expired: bool
    authenticity_proven: Literal[False]
    evidence_receipt_only: Literal[True]
    approval_consumed: Literal[False]
    handoff_ready: Literal[False]
    handoff_artifact_issued: Literal[False]
    target_contacted: Literal[False]
    package_rebound: Literal[False]
    configuration_changed: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_domain(
        cls, verification: ConnectorUpgradeEvidenceReceiptVerification
    ) -> ConnectorUpgradeEvidenceReceiptVerificationData:
        return cls(**{field: getattr(verification, field) for field in cls.model_fields})


class ConnectorUpgradeEvidenceReceiptVerificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorUpgradeEvidenceReceiptVerificationData
    meta: ResponseMeta


class ConnectorUpgradeEvidenceSignatureData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key_id: str = Field(pattern=STABLE_ID)
    key_version: str = Field(pattern=STABLE_ID)
    signer_profile_id: str = Field(pattern=STABLE_ID)
    signer_workload_id: str = Field(pattern=STABLE_ID)
    algorithm: Literal["algorithm.hmac-sha256-nonproduction"]
    signed_payload_digest: str = Field(pattern=DIGEST)
    signature_value: str = Field(min_length=43, max_length=512, pattern=r"^[A-Za-z0-9_-]+$")
    signature_digest: str = Field(pattern=DIGEST)
    issued_at: datetime
    expires_at: datetime

    @classmethod
    def from_domain(
        cls, signature: ConnectorUpgradeEvidenceSignature
    ) -> ConnectorUpgradeEvidenceSignatureData:
        return cls(**{field: getattr(signature, field) for field in cls.model_fields})

    def to_domain(self) -> ConnectorUpgradeEvidenceSignature:
        return ConnectorUpgradeEvidenceSignature(**self.model_dump())


class ConnectorUpgradeEvidenceSigningKeyTrustData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key_id: str = Field(pattern=STABLE_ID)
    key_version: str = Field(pattern=STABLE_ID)
    signer_profile_id: str = Field(pattern=STABLE_ID)
    signer_workload_id: str = Field(pattern=STABLE_ID)
    algorithm: str = Field(pattern=STABLE_ID)
    configured_state: Literal["active", "disabled", "revoked"]
    effective_state: Literal["active", "not_yet_valid", "expired", "disabled", "revoked"]
    not_before: datetime
    expires_at: datetime
    signing_eligible: bool
    verification_trusted: bool
    reason_codes: tuple[str, ...]

    @classmethod
    def from_domain(
        cls, trust: ConnectorUpgradeEvidenceSigningKeyTrust
    ) -> ConnectorUpgradeEvidenceSigningKeyTrustData:
        return cls(**{field: getattr(trust, field) for field in cls.model_fields})


class ConnectorUpgradeEvidenceSigningKeyTrustInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.connector-upgrade-signing-key-trust-inventory.v1"]
    organization_id: str = Field(pattern=STABLE_ID)
    environment_id: str = Field(pattern=STABLE_ID)
    provider_class: str = Field(pattern=STABLE_ID)
    provider_state: Literal["available", "unavailable"]
    generated_at: datetime
    keys: tuple[ConnectorUpgradeEvidenceSigningKeyTrustData, ...]
    canonical_digest: str = Field(pattern=DIGEST)
    provider_available: bool
    production_approved: bool
    key_management_authorized: Literal[False]
    signing_authorized: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_domain(
        cls, inventory: ConnectorUpgradeEvidenceSigningKeyTrustInventory
    ) -> ConnectorUpgradeEvidenceSigningKeyTrustInventoryData:
        payload = {field: getattr(inventory, field) for field in cls.model_fields}
        payload["keys"] = tuple(
            ConnectorUpgradeEvidenceSigningKeyTrustData.from_domain(key) for key in inventory.keys
        )
        return cls(**payload)


class ConnectorUpgradeEvidenceSigningKeyTrustInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorUpgradeEvidenceSigningKeyTrustInventoryData
    meta: ResponseMeta


class ConnectorUpgradeSigningProviderConformanceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.connector-upgrade-signing-provider-conformance-input.v1"] = (
        "atlas.connector-upgrade-signing-provider-conformance-input.v1"
    )
    acknowledged_diagnostic_grants_no_key_receipt_or_execution_authority: Literal[True]


class ConnectorUpgradeSigningProviderConformanceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assessment_id: str = Field(pattern=STABLE_ID)
    schema_version: Literal["atlas.connector-upgrade-signing-provider-conformance-assessment.v1"]
    version: Literal[1]
    organization_id: str = Field(pattern=STABLE_ID)
    environment_id: str = Field(pattern=STABLE_ID)
    assessed_by: str = Field(pattern=STABLE_ID)
    provider_class: str = Field(pattern=STABLE_ID)
    production_approved: bool
    key_id: str | None = Field(default=None, pattern=STABLE_ID)
    key_version: str | None = Field(default=None, pattern=STABLE_ID)
    algorithm: str | None = Field(default=None, pattern=STABLE_ID)
    challenge_digest: str = Field(pattern=DIGEST)
    policy_id: str = Field(pattern=STABLE_ID)
    policy_version: str = Field(pattern=STABLE_ID)
    observed_at: datetime
    valid_until: datetime
    state: Literal[
        "conformant",
        "unavailable",
        "ineligible_key",
        "sign_failed",
        "verify_failed",
        "policy_blocked",
    ]
    reason_codes: tuple[str, ...]
    request_fingerprint: str = Field(pattern=DIGEST)
    canonical_digest: str = Field(pattern=DIGEST)
    diagnostic_only: Literal[True]
    signing_provider_conformant: bool
    key_management_authorized: Literal[False]
    receipt_signing_authorized: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_performed: Literal[False]
    reused: bool

    @classmethod
    def from_domain(
        cls, assessment: ConnectorUpgradeSigningProviderConformanceAssessment
    ) -> ConnectorUpgradeSigningProviderConformanceData:
        return cls(**{field: getattr(assessment, field) for field in cls.model_fields})


class ConnectorUpgradeSigningProviderConformanceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorUpgradeSigningProviderConformanceData
    meta: ResponseMeta


class ConnectorUpgradeSigningProviderOnboardingRequirementData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requirement_id: str = Field(pattern=STABLE_ID)
    state: Literal["satisfied", "blocked"]
    reason_code: str = Field(pattern=STABLE_ID)
    evidence_reference: str | None = Field(default=None, pattern=STABLE_ID)

    @classmethod
    def from_domain(
        cls, requirement: ConnectorUpgradeSigningProviderOnboardingRequirement
    ) -> ConnectorUpgradeSigningProviderOnboardingRequirementData:
        return cls(**{field: getattr(requirement, field) for field in cls.model_fields})


class ConnectorUpgradeSigningProviderOnboardingReadinessData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dossier_id: str = Field(pattern=STABLE_ID)
    schema_version: Literal["atlas.connector-upgrade-signing-provider-onboarding-readiness.v1"]
    version: Literal[1]
    organization_id: str = Field(pattern=STABLE_ID)
    environment_id: str = Field(pattern=STABLE_ID)
    provider_class: str = Field(pattern=STABLE_ID)
    key_id: str | None = Field(default=None, pattern=STABLE_ID)
    key_version: str | None = Field(default=None, pattern=STABLE_ID)
    algorithm: str | None = Field(default=None, pattern=STABLE_ID)
    provider_trust_digest: str = Field(pattern=DIGEST)
    conformance_assessment_id: str | None = Field(default=None, pattern=STABLE_ID)
    conformance_digest: str | None = Field(default=None, pattern=DIGEST)
    policy_id: str = Field(pattern=STABLE_ID)
    policy_version: str = Field(pattern=STABLE_ID)
    evaluated_at: datetime
    readiness_state: Literal["ready", "blocked"]
    requirements: tuple[ConnectorUpgradeSigningProviderOnboardingRequirementData, ...]
    required_external_inputs: tuple[str, ...]
    canonical_digest: str = Field(pattern=DIGEST)
    provider_onboarding_ready: bool
    evidence_only: Literal[True]
    provider_configuration_authorized: Literal[False]
    key_management_authorized: Literal[False]
    receipt_signing_authorized: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_domain(
        cls, dossier: ConnectorUpgradeSigningProviderOnboardingReadiness
    ) -> ConnectorUpgradeSigningProviderOnboardingReadinessData:
        payload = {field: getattr(dossier, field) for field in cls.model_fields}
        payload["requirements"] = tuple(
            ConnectorUpgradeSigningProviderOnboardingRequirementData.from_domain(requirement)
            for requirement in dossier.requirements
        )
        return cls(**payload)


class ConnectorUpgradeSigningProviderOnboardingReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorUpgradeSigningProviderOnboardingReadinessData
    meta: ResponseMeta


class ConnectorUpgradeSignedEvidenceReceiptData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signed_receipt_id: str = Field(pattern=STABLE_ID)
    schema_version: Literal["atlas.connector-upgrade-signed-evidence-receipt.v1"]
    version: Literal[1]
    receipt: ConnectorUpgradeEvidenceReceiptData
    signature: ConnectorUpgradeEvidenceSignatureData
    organization_id: str = Field(pattern=STABLE_ID)
    environment_id: str = Field(pattern=STABLE_ID)
    request_id: str = Field(pattern=STABLE_ID)
    canonical_digest: str = Field(pattern=DIGEST)
    evidence_receipt_only: Literal[True]
    authenticity_claimed: Literal[True]
    runtime_acceptable: Literal[False]
    approval_consumed: Literal[False]
    handoff_ready: Literal[False]
    handoff_artifact_issued: Literal[False]
    target_contacted: Literal[False]
    package_rebound: Literal[False]
    configuration_changed: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_domain(
        cls, signed: ConnectorUpgradeSignedEvidenceReceipt
    ) -> ConnectorUpgradeSignedEvidenceReceiptData:
        payload = {field: getattr(signed, field) for field in cls.model_fields}
        payload["receipt"] = ConnectorUpgradeEvidenceReceiptData.from_domain(signed.receipt)
        payload["signature"] = ConnectorUpgradeEvidenceSignatureData.from_domain(signed.signature)
        return cls(**payload)

    def to_domain(self) -> ConnectorUpgradeSignedEvidenceReceipt:
        payload = self.model_dump(exclude={"receipt", "signature"})
        return ConnectorUpgradeSignedEvidenceReceipt(
            **payload,
            receipt=self.receipt.to_domain(),
            signature=self.signature.to_domain(),
        )


class ConnectorUpgradeSignedEvidenceReceiptInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.connector-upgrade-signed-evidence-receipt-input.v1"] = (
        "atlas.connector-upgrade-signed-evidence-receipt-input.v1"
    )
    receipt: ConnectorUpgradeEvidenceReceiptData
    acknowledged_signature_authenticates_origin_but_grants_no_authority: Literal[True]


class ConnectorUpgradeSignedEvidenceReceiptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorUpgradeSignedEvidenceReceiptData
    meta: ResponseMeta


class ConnectorUpgradeSignedEvidenceReceiptVerificationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[
        "atlas.connector-upgrade-signed-evidence-receipt-verification-input.v1"
    ] = "atlas.connector-upgrade-signed-evidence-receipt-verification-input.v1"
    signed_receipt: ConnectorUpgradeSignedEvidenceReceiptData
    acknowledged_signature_is_not_approval_or_execution_authority: Literal[True]


class ConnectorUpgradeSignedEvidenceReceiptVerificationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verification_id: str = Field(pattern=STABLE_ID)
    schema_version: Literal["atlas.connector-upgrade-signed-evidence-receipt-verification.v1"]
    signed_receipt_id: str = Field(pattern=STABLE_ID)
    signed_receipt_digest: str = Field(pattern=DIGEST)
    receipt_id: str = Field(pattern=STABLE_ID)
    receipt_digest: str = Field(pattern=DIGEST)
    request_id: str = Field(pattern=STABLE_ID)
    organization_id: str = Field(pattern=STABLE_ID)
    environment_id: str = Field(pattern=STABLE_ID)
    verified_by: str = Field(pattern=STABLE_ID)
    verified_at: datetime
    key_id: str = Field(pattern=STABLE_ID)
    key_version: str = Field(pattern=STABLE_ID)
    signer_workload_id: str = Field(pattern=STABLE_ID)
    algorithm: Literal["algorithm.hmac-sha256-nonproduction"]
    authenticity_state: Literal["authentic", "invalid", "expired", "revoked", "unverifiable"]
    receipt_verification_state: Literal[
        "current", "stale", "expired", "unverifiable", "not_compared"
    ]
    reason_codes: tuple[str, ...]
    canonical_digest: str = Field(pattern=DIGEST)
    integrity_valid: Literal[True]
    authenticity_proven: bool
    current_state_matches: bool
    evidence_receipt_only: Literal[True]
    approval_consumed: Literal[False]
    handoff_ready: Literal[False]
    handoff_artifact_issued: Literal[False]
    target_contacted: Literal[False]
    package_rebound: Literal[False]
    configuration_changed: Literal[False]
    execution_authorized: Literal[False]
    infrastructure_mutation_performed: Literal[False]

    @classmethod
    def from_domain(
        cls, verification: ConnectorUpgradeSignedEvidenceReceiptVerification
    ) -> ConnectorUpgradeSignedEvidenceReceiptVerificationData:
        return cls(**{field: getattr(verification, field) for field in cls.model_fields})


class ConnectorUpgradeSignedEvidenceReceiptVerificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ConnectorUpgradeSignedEvidenceReceiptVerificationData
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
