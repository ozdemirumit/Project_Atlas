from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from atlas.modules.ai.domain.protected_recommendation_presentation import (
    PresentedRecommendationOption,
)


def _aware(*values: datetime) -> bool:
    return all(value.tzinfo is not None for value in values)


@dataclass(frozen=True, slots=True)
class RecommendationPromotionPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_presentation_schema: str
    required_presentation_state: str
    required_promoter_id: str
    required_promoter_attestor_id: str
    required_receipt_schema: str
    artifact_schema: str
    maximum_option_count: int
    maximum_output_bytes: int
    retention_minutes: int
    browser_binding_key_digest: str
    promotion_profile_digest: str
    prohibited_content_profile_digest: str
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            self.version != 1
            or not _aware(self.issued_at, self.expires_at)
            or self.expires_at <= self.issued_at
            or min(
                self.maximum_option_count,
                self.maximum_output_bytes,
                self.retention_minutes,
            )
            < 1
        ):
            raise ValueError("invalid recommendation promotion policy")


@dataclass(frozen=True, slots=True)
class RecommendationPromotionInstruction:
    promotion_id: str
    recommendation_id: str
    presentation_id: str
    presentation_digest: str
    recommendation_digest: str
    organization_id: str
    environment_id: str
    consumer_subject_digest: str
    promotion_authorization_digest: str
    policy_id: str
    policy_digest: str
    artifact_schema: str
    maximum_option_count: int
    maximum_output_bytes: int
    promotion_profile_digest: str
    prohibited_content_profile_digest: str
    requested_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        if not _aware(self.requested_at, self.expires_at) or self.expires_at <= self.requested_at:
            raise ValueError("invalid recommendation promotion instruction")


@dataclass(frozen=True, slots=True)
class RecommendationPromotionReceipt:
    promotion_id: str
    schema_version: str
    version: int
    promoter_id: str
    attested_by: str
    presentation_id: str
    presentation_digest: str
    policy_digest: str
    promotion_authorization_digest: str
    artifact_digest: str
    source_binding_digest: str
    outcome: str
    option_count: int
    preferred_count: int
    byte_count: int
    promoted_at: datetime
    expires_at: datetime
    source_verified: bool
    outcome_preserved: bool
    safe_content_verified: bool
    no_model_used: bool
    no_network_used: bool
    no_operational_authority: bool
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            self.version != 1
            or self.outcome not in {"preferred", "tie", "no_support"}
            or self.option_count < 1
            or self.preferred_count not in {0, 1}
            or (self.outcome == "preferred") != (self.preferred_count == 1)
            or self.byte_count < 1
            or not _aware(self.promoted_at, self.expires_at)
            or not all(
                (
                    self.source_verified,
                    self.outcome_preserved,
                    self.safe_content_verified,
                    self.no_model_used,
                    self.no_network_used,
                    self.no_operational_authority,
                    self.signature_verified,
                )
            )
        ):
            raise ValueError("invalid recommendation promotion receipt")


@dataclass(frozen=True, slots=True)
class RecommendationPromotionClaim:
    claim_id: str
    schema_version: str
    version: int
    promotion_id: str
    recommendation_id: str
    presentation_id: str
    claimed_by_subject_digest: str
    browser_session_binding_digest: str
    request_binding_digest: str
    idempotency_digest: str
    organization_id: str
    environment_id: str
    claimed_at: datetime
    canonical_digest: str


@dataclass(frozen=True, slots=True)
class PromotedRecommendationArtifact:
    promotion_id: str
    recommendation_id: str
    schema_version: str
    version: int
    claim_id: str
    presentation_id: str
    presentation_digest: str
    adjudication_id: str
    organization_id: str
    environment_id: str
    classification: str
    consumer_subject_digest: str
    browser_session_binding_digest: str
    promotion_policy_id: str
    promotion_policy_digest: str
    promotion_policy_version: str
    promoter_id: str
    promotion_receipt_digest: str
    promotion_authorization_digest: str
    source_binding_digest: str
    outcome: str
    headline: str
    safety_notice: str
    options: tuple[PresentedRecommendationOption, ...]
    evidence_needs: tuple[str, ...]
    state: str
    promoted_at: datetime
    expires_at: datetime
    purpose: str
    byte_count: int
    canonical_digest: str
    recommendation_promoted: bool = True
    recommendation_ready_for_review: bool = False
    human_review_completed: bool = False
    recommendation_approved: bool = False
    workflow_created: bool = False
    itsm_record_created: bool = False
    execution_authorized: bool = False
    deployment_authorized: bool = False
    infrastructure_mutated: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        if (
            self.version != 1
            or self.outcome not in {"preferred", "tie", "no_support"}
            or self.state != "draft"
            or not self.options
            or self.byte_count < 1
            or not _aware(self.promoted_at, self.expires_at)
            or self.expires_at <= self.promoted_at
            or not self.recommendation_promoted
            or (self.outcome == "preferred")
            != any(option.role == "preferred" for option in self.options)
            or (self.outcome == "tie" and not all(option.role == "tied" for option in self.options))
            or (
                self.outcome == "no_support"
                and not all(option.role == "unsupported" for option in self.options)
            )
            or any(
                (
                    self.recommendation_ready_for_review,
                    self.human_review_completed,
                    self.recommendation_approved,
                    self.workflow_created,
                    self.itsm_record_created,
                    self.execution_authorized,
                    self.deployment_authorized,
                    self.infrastructure_mutated,
                )
            )
        ):
            raise ValueError("invalid promoted recommendation artifact")


@dataclass(frozen=True, slots=True)
class RecommendationPromotionManifest:
    promotion_id: str
    recommendation_id: str
    presentation_id: str
    adjudication_id: str
    outcome: str
    option_count: int
    preferred_count: int
    state: str
    source_binding_digest: str
    promoted_at: datetime
    expires_at: datetime
    safety_notice: str


@dataclass(frozen=True, slots=True)
class RecommendationPromotionResult:
    artifact: PromotedRecommendationArtifact
    manifest: RecommendationPromotionManifest
