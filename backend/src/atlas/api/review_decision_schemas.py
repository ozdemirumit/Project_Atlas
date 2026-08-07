from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.knowledge.domain.review_decision import (
    OperationalKnowledgeTrackReviewDecisionGrant,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class OperationalKnowledgeTrackReviewDecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.operational-knowledge-track-review-decision-input.v1",
        pattern=STABLE_ID,
    )
    source_finding_presentation_digest: str = Field(pattern=DIGEST)
    decision_policy_id: str = Field(pattern=STABLE_ID)
    decision_policy_digest: str = Field(pattern=DIGEST)
    disposition_code: str = Field(pattern=STABLE_ID)
    basis_codes: tuple[str, ...] = Field(min_length=1, max_length=4)
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_exact_findings_reviewed: bool
    acknowledged_human_track_decision: bool
    acknowledged_no_approval_or_operational_authority: bool


class OperationalKnowledgeTrackReviewDecisionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_id: str
    schema_version: str
    version: int
    source_finding_presentation_id: str
    source_finding_presentation_digest: str
    source_finding_packet_id: str
    source_lease_id: str
    source_content_presentation_id: str
    source_assignment_set_id: str
    organization_id: str
    environment_id: str
    review_request_id: str
    source_draft_id: str
    knowledge_item_id: str
    draft_version_id: str
    title: str
    classification: str
    track_code: str
    disposition_code: str
    basis_codes: tuple[str, ...]
    decision_policy_id: str
    decision_policy_digest: str
    decision_policy_version: str
    attestor_id: str
    attestation_digest: str
    decided_at: datetime
    expires_at: datetime
    instance_state: str
    purpose: str
    canonical_digest: str
    domain_review_completed: bool
    security_review_completed: bool
    domain_review_passed: bool
    security_review_passed: bool
    correction_required: bool
    correction_created: bool
    all_tracks_decided: bool
    all_tracks_passed: bool
    any_correction_required: bool
    knowledge_approved: bool
    knowledge_published: bool
    retrieval_published: bool
    model_context_available: bool
    workflow_continued: bool
    execution_authorized: bool
    deployment_approved: bool
    infrastructure_mutation_performed: bool
    reused: bool

    @classmethod
    def from_grant(
        cls, grant: OperationalKnowledgeTrackReviewDecisionGrant
    ) -> OperationalKnowledgeTrackReviewDecisionData:
        values = {
            field: getattr(grant.record, field)
            for field in cls.model_fields
            if field not in {"all_tracks_decided", "all_tracks_passed", "any_correction_required"}
        }
        values.update(
            all_tracks_decided=grant.all_tracks_decided,
            all_tracks_passed=grant.all_tracks_passed,
            any_correction_required=grant.any_correction_required,
        )
        return cls.model_validate(values)


class OperationalKnowledgeTrackReviewDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: OperationalKnowledgeTrackReviewDecisionData
    meta: ResponseMeta
