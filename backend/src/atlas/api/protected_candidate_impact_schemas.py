from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.ai.domain.protected_candidate_impact_enrichment import (
    ProtectedCandidateImpactManifest,
    ProtectedCandidateImpactRecord,
    ProtectedCandidateImpactResult,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class ProtectedCandidateImpactInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(
        default="atlas.protected-candidate-impact-input.v1", pattern=STABLE_ID
    )
    candidate_set_digest: str = Field(pattern=DIGEST)
    impact_policy_id: str = Field(pattern=STABLE_ID)
    impact_policy_digest: str = Field(pattern=DIGEST)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_reachability_is_not_outage_evidence: bool
    acknowledged_impact_remains_provisional: bool
    acknowledged_no_recommendation_or_operational_authority: bool


class ProtectedCandidateImpactData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    impact_analysis_id: str
    schema_version: str
    version: int
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
    impact_policy_id: str
    impact_policy_digest: str
    impact_policy_version: str
    analyzer_id: str
    analysis_receipt_digest: str
    graph_snapshot_id: str
    graph_snapshot_digest: str
    graph_snapshot_generated_at: datetime
    graph_freshness: str
    graph_completeness: str
    graph_maturity: str
    coverage_digest: str
    graph_gap_digest: str
    unknown_digest: str
    safety_digest: str
    cleanup_digest: str
    candidate_count: int
    path_count: int
    modeled_entity_count: int
    technical_service_count: int
    business_service_count: int
    gap_count: int
    unknown_count: int
    byte_count: int
    analyzed_at: datetime
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
    def from_domain(cls, record: ProtectedCandidateImpactRecord) -> ProtectedCandidateImpactData:
        return cls.model_validate(record, from_attributes=True)


class ProtectedCandidateImpactManifestData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    impact_analysis_id: str
    candidate_set_id: str
    presentation_id: str
    graph_snapshot_id: str
    graph_snapshot_digest: str
    graph_snapshot_generated_at: datetime
    graph_freshness: str
    graph_completeness: str
    graph_maturity: str
    candidate_count: int
    path_count: int
    modeled_entity_count: int
    technical_service_count: int
    business_service_count: int
    gap_count: int
    unknown_count: int
    coverage_digest: str
    graph_gap_digest: str
    unknown_digest: str
    safety_digest: str
    analyzed_at: datetime
    expires_at: datetime
    safety_notice: str

    @classmethod
    def from_domain(
        cls, manifest: ProtectedCandidateImpactManifest
    ) -> ProtectedCandidateImpactManifestData:
        return cls.model_validate(manifest, from_attributes=True)


class ProtectedCandidateImpactResultData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    impact_analysis: ProtectedCandidateImpactData
    manifest: ProtectedCandidateImpactManifestData

    @classmethod
    def from_domain(
        cls, result: ProtectedCandidateImpactResult
    ) -> ProtectedCandidateImpactResultData:
        return cls(
            impact_analysis=ProtectedCandidateImpactData.from_domain(result.record),
            manifest=ProtectedCandidateImpactManifestData.from_domain(result.manifest),
        )


class ProtectedCandidateImpactResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data: ProtectedCandidateImpactResultData
    meta: ResponseMeta
