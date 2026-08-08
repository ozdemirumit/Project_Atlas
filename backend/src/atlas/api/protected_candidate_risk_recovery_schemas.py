from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.ai.domain.protected_candidate_risk_recovery_completion import (
    ProtectedCandidateRiskRecoveryManifest,
    ProtectedCandidateRiskRecoveryRecord,
    ProtectedCandidateRiskRecoveryResult,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ProtectedCandidateRiskRecoveryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(
        default="atlas.protected-candidate-risk-recovery-input.v1",
        pattern=STABLE_ID,
    )
    impact_digest: str = Field(pattern=DIGEST)
    completion_policy_id: str = Field(pattern=STABLE_ID)
    completion_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_estimates_are_not_guarantees: bool
    acknowledged_unknowns_cannot_lower_risk: bool
    acknowledged_no_preference_or_operational_authority: bool


class ProtectedCandidateRiskRecoveryData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    completion_id: str
    schema_version: str
    version: int
    impact_analysis_id: str
    impact_digest: str
    candidate_set_id: str
    candidate_set_digest: str
    presentation_id: str
    answer_digest: str
    adjudication_id: str
    invocation_id: str
    context_id: str
    organization_id: str
    environment_id: str
    classification: str
    completion_policy_id: str
    completion_policy_digest: str
    completion_policy_version: str
    assessor_id: str
    completion_receipt_digest: str
    evidence_snapshot_id: str
    evidence_snapshot_digest: str
    evidence_snapshot_generated_at: datetime
    evidence_freshness: str
    evidence_completeness: str
    evidence_coverage_digest: str
    coverage_digest: str
    risk_digest: str
    duration_digest: str
    interruption_digest: str
    recovery_digest: str
    unknown_digest: str
    safety_digest: str
    cleanup_digest: str
    candidate_count: int
    evidence_item_count: int
    low_risk_count: int
    moderate_risk_count: int
    high_risk_count: int
    critical_risk_count: int
    unknown_risk_count: int
    maximum_risk: str
    interruption_possible_count: int
    recovery_feasible_count: int
    recovery_unknown_count: int
    recovery_blocked_count: int
    work_minimum_minutes: int
    work_maximum_minutes: int
    interruption_minimum_minutes: int
    interruption_maximum_minutes: int
    recovery_minimum_minutes: int
    recovery_maximum_minutes: int
    gap_count: int
    unknown_count: int
    byte_count: int
    completed_at: datetime
    expires_at: datetime
    instance_state: str
    purpose: str
    safety_notice: str
    canonical_digest: str
    service_impact_analyzed: bool
    impact_complete: bool
    outage_confirmed: bool
    interruption_established: bool
    duration_established: bool
    risk_completed: bool
    recovery_completed: bool
    recommendation_complete: bool
    recommendation_presented: bool
    recommendation_ready_for_review: bool
    recommendation_approved: bool
    workflow_created: bool
    execution_authorized: bool
    deployment_authorized: bool
    infrastructure_mutated: bool
    reused: bool

    @classmethod
    def from_domain(
        cls, record: ProtectedCandidateRiskRecoveryRecord
    ) -> ProtectedCandidateRiskRecoveryData:
        return cls.model_validate(record, from_attributes=True)


class ProtectedCandidateRiskRecoveryManifestData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    completion_id: str
    impact_analysis_id: str
    candidate_set_id: str
    presentation_id: str
    evidence_snapshot_id: str
    evidence_snapshot_digest: str
    evidence_snapshot_generated_at: datetime
    evidence_freshness: str
    evidence_completeness: str
    evidence_coverage_digest: str
    candidate_count: int
    evidence_item_count: int
    low_risk_count: int
    moderate_risk_count: int
    high_risk_count: int
    critical_risk_count: int
    unknown_risk_count: int
    maximum_risk: str
    interruption_possible_count: int
    recovery_feasible_count: int
    recovery_unknown_count: int
    recovery_blocked_count: int
    work_minimum_minutes: int
    work_maximum_minutes: int
    interruption_minimum_minutes: int
    interruption_maximum_minutes: int
    recovery_minimum_minutes: int
    recovery_maximum_minutes: int
    gap_count: int
    unknown_count: int
    coverage_digest: str
    risk_digest: str
    duration_digest: str
    interruption_digest: str
    recovery_digest: str
    unknown_digest: str
    safety_digest: str
    completed_at: datetime
    expires_at: datetime
    safety_notice: str

    @classmethod
    def from_domain(
        cls, manifest: ProtectedCandidateRiskRecoveryManifest
    ) -> ProtectedCandidateRiskRecoveryManifestData:
        return cls.model_validate(manifest, from_attributes=True)


class ProtectedCandidateRiskRecoveryResultData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    completion: ProtectedCandidateRiskRecoveryData
    manifest: ProtectedCandidateRiskRecoveryManifestData

    @classmethod
    def from_domain(
        cls, result: ProtectedCandidateRiskRecoveryResult
    ) -> ProtectedCandidateRiskRecoveryResultData:
        return cls(
            completion=ProtectedCandidateRiskRecoveryData.from_domain(result.record),
            manifest=ProtectedCandidateRiskRecoveryManifestData.from_domain(result.manifest),
        )


class ProtectedCandidateRiskRecoveryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: ProtectedCandidateRiskRecoveryResultData
    meta: ResponseMeta
