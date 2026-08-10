from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier
from atlas.modules.recommendations.domain.reviewer_assignment import (
    SERVICE_IMPACT_TRACK,
    TECHNICAL_TRACK,
)

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
TRACKS = frozenset({TECHNICAL_TRACK, SERVICE_IMPACT_TRACK})
RECOMMENDATION_PROTECTED_INSPECTION_LEASED = "recommendation_protected_inspection_leased"


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "recommendation protected inspection identifier")


def _digests(*values: str) -> bool:
    return all(_DIGEST.fullmatch(value) is not None for value in values)


@dataclass(frozen=True, slots=True)
class RecommendationProtectedInspectionPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_source_schema: str
    required_source_state: str
    required_broker_id: str
    required_broker_attestor_id: str
    required_receipt_schema: str
    subject_digest_salt_id: str
    subject_digest_salt_digest: str
    browser_binding_key_id: str
    browser_binding_key_digest: str
    maximum_source_age_minutes: int
    maximum_authentication_age_minutes: int
    lease_ttl_minutes: int
    maximum_concurrent_leases: int
    require_browser_session_binding: bool
    require_exact_assignee: bool
    required_assurance_level: AssuranceLevel
    signed_by: str
    signature_verified: bool
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.policy_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.policy_version,
            self.required_source_schema,
            self.required_source_state,
            self.required_broker_id,
            self.required_broker_attestor_id,
            self.required_receipt_schema,
            self.subject_digest_salt_id,
            self.browser_binding_key_id,
            self.signed_by,
        )
        if (
            self.version != 1
            or not 1 <= self.maximum_source_age_minutes <= 10_080
            or not 1 <= self.maximum_authentication_age_minutes <= 60
            or not 1 <= self.lease_ttl_minutes <= 10
            or self.maximum_concurrent_leases != 1
            or not self.require_browser_session_binding
            or not self.require_exact_assignee
            or self.required_assurance_level is not AssuranceLevel.HARDWARE_BACKED
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or not _digests(
                self.subject_digest_salt_digest,
                self.browser_binding_key_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Recommendation protected inspection policy is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationProtectedInspectionInstruction:
    lease_id: str
    organization_id: str
    environment_id: str
    assignment_set_id: str
    assignment_set_digest: str
    review_request_id: str
    recommendation_id: str
    readiness_assessment_id: str
    promotion_id: str
    track_code: str
    opaque_assignment_id: str
    assigned_reviewer_subject_digest: str
    current_subject_digest: str
    browser_session_binding_digest: str
    lease_ttl_minutes: int
    inspection_policy_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.lease_id,
            self.organization_id,
            self.environment_id,
            self.assignment_set_id,
            self.review_request_id,
            self.recommendation_id,
            self.readiness_assessment_id,
            self.promotion_id,
            self.track_code,
            self.opaque_assignment_id,
        )
        if (
            self.track_code not in TRACKS
            or self.assigned_reviewer_subject_digest != self.current_subject_digest
            or not 1 <= self.lease_ttl_minutes <= 10
            or not _digests(
                self.assignment_set_digest,
                self.assigned_reviewer_subject_digest,
                self.current_subject_digest,
                self.browser_session_binding_digest,
                self.inspection_policy_digest,
            )
        ):
            raise ValueError("Recommendation protected inspection instruction is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationProtectedInspectionReceipt:
    lease_id: str
    schema_version: str
    version: int
    broker_id: str
    attested_by: str
    assignment_set_id: str
    assignment_set_digest: str
    track_code: str
    opaque_assignment_id: str
    lease_holder_subject_digest: str
    browser_session_binding_digest: str
    lease_secret_digest: str
    lease_digest: str
    assignment_binding_digest: str
    policy_binding_digest: str
    cleanup_digest: str
    issued_at: datetime
    expires_at: datetime
    exact_assignee_verified: bool
    assignment_current: bool
    browser_session_bound: bool
    non_transferable: bool
    refresh_disabled: bool
    immutable_lease_confirmed: bool
    plaintext_secret_buffer_erased: bool
    broker_channel_closed: bool
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.lease_id,
            self.schema_version,
            self.broker_id,
            self.attested_by,
            self.assignment_set_id,
            self.track_code,
            self.opaque_assignment_id,
        )
        if (
            self.version != 1
            or self.track_code not in TRACKS
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or not all(
                (
                    self.exact_assignee_verified,
                    self.assignment_current,
                    self.browser_session_bound,
                    self.non_transferable,
                    self.refresh_disabled,
                    self.immutable_lease_confirmed,
                    self.plaintext_secret_buffer_erased,
                    self.broker_channel_closed,
                    self.signature_verified,
                )
            )
            or not _digests(
                self.assignment_set_digest,
                self.lease_holder_subject_digest,
                self.browser_session_binding_digest,
                self.lease_secret_digest,
                self.lease_digest,
                self.assignment_binding_digest,
                self.policy_binding_digest,
                self.cleanup_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Recommendation protected inspection receipt is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationProtectedInspectionClaim:
    claim_id: str
    schema_version: str
    version: int
    source_assignment_set_id: str
    source_assignment_set_digest: str
    track_code: str
    lease_id: str
    organization_id: str
    environment_id: str
    claimed_by_subject_digest: str
    purpose: str
    claimed_at: datetime
    browser_session_binding_digest: str
    request_binding_digest: str
    idempotency_digest: str
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.claim_id,
            self.schema_version,
            self.source_assignment_set_id,
            self.track_code,
            self.lease_id,
            self.organization_id,
            self.environment_id,
        )
        if (
            self.version != 1
            or self.track_code not in TRACKS
            or not 20 <= len(self.purpose.strip()) <= 1000
            or self.claimed_at.tzinfo is None
            or not _digests(
                self.source_assignment_set_digest,
                self.claimed_by_subject_digest,
                self.browser_session_binding_digest,
                self.request_binding_digest,
                self.idempotency_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Recommendation protected inspection claim is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationProtectedInspectionRecord:
    lease_id: str
    schema_version: str
    version: int
    claim_id: str
    source_assignment_set_id: str
    source_assignment_set_digest: str
    recommendation_id: str
    review_request_id: str
    readiness_assessment_id: str
    promotion_id: str
    organization_id: str
    environment_id: str
    classification: str
    source_outcome: str
    option_count: int
    preferred_count: int
    track_code: str
    opaque_assignment_id: str
    lease_holder_subject_digest: str
    browser_session_binding_digest: str
    lease_secret_digest: str
    lease_digest: str
    assignment_binding_digest: str
    policy_binding_digest: str
    cleanup_digest: str
    inspection_policy_id: str
    inspection_policy_digest: str
    inspection_policy_version: str
    lease_broker_id: str
    issued_at: datetime
    expires_at: datetime
    state: str
    purpose: str
    canonical_digest: str
    review_requested: bool = True
    reviewer_assigned: bool = True
    content_inspection_opened: bool = True
    content_disclosed: bool = False
    protected_content_bytes_returned: int = 0
    exact_assignee_verified: bool = True
    browser_session_bound: bool = True
    non_transferable: bool = True
    refresh_disabled: bool = True
    plaintext_secret_buffer_erased: bool = True
    broker_channel_closed: bool = True
    human_review_completed: bool = False
    recommendation_approved: bool = False
    workflow_created: bool = False
    itsm_record_created: bool = False
    execution_authorized: bool = False
    deployment_authorized: bool = False
    infrastructure_mutated: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        _ids(
            self.lease_id,
            self.schema_version,
            self.claim_id,
            self.source_assignment_set_id,
            self.recommendation_id,
            self.review_request_id,
            self.readiness_assessment_id,
            self.promotion_id,
            self.organization_id,
            self.environment_id,
            self.classification,
            self.track_code,
            self.opaque_assignment_id,
            self.inspection_policy_id,
            self.inspection_policy_version,
            self.lease_broker_id,
            self.state,
        )
        if (
            self.version != 1
            or self.state != RECOMMENDATION_PROTECTED_INSPECTION_LEASED
            or self.track_code not in TRACKS
            or self.source_outcome not in {"preferred", "tie", "no_support"}
            or self.option_count < 1
            or self.preferred_count not in {0, 1}
            or (self.source_outcome == "preferred") != (self.preferred_count == 1)
            or not 20 <= len(self.purpose.strip()) <= 1000
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or self.content_disclosed
            or self.protected_content_bytes_returned != 0
            or not all(
                (
                    self.review_requested,
                    self.reviewer_assigned,
                    self.content_inspection_opened,
                    self.exact_assignee_verified,
                    self.browser_session_bound,
                    self.non_transferable,
                    self.refresh_disabled,
                    self.plaintext_secret_buffer_erased,
                    self.broker_channel_closed,
                )
            )
            or any(
                (
                    self.human_review_completed,
                    self.recommendation_approved,
                    self.workflow_created,
                    self.itsm_record_created,
                    self.execution_authorized,
                    self.deployment_authorized,
                    self.infrastructure_mutated,
                )
            )
            or not _digests(
                self.source_assignment_set_digest,
                self.lease_holder_subject_digest,
                self.browser_session_binding_digest,
                self.lease_secret_digest,
                self.lease_digest,
                self.assignment_binding_digest,
                self.policy_binding_digest,
                self.cleanup_digest,
                self.inspection_policy_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Recommendation protected inspection record is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationProtectedInspectionGrant:
    record: RecommendationProtectedInspectionRecord
    lease_secret: str | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.lease_secret is not None and not 43 <= len(self.lease_secret) <= 256:
            raise ValueError("Recommendation protected inspection secret is invalid")


@dataclass(frozen=True, slots=True)
class RecommendationProtectedInspectionBrokerGrant:
    receipt: RecommendationProtectedInspectionReceipt
    lease_secret: str = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if not 43 <= len(self.lease_secret) <= 256:
            raise ValueError("Recommendation protected inspection broker secret is invalid")
