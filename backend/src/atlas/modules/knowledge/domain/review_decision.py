from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import AssuranceLevel, validate_stable_identifier

OPERATIONAL_KNOWLEDGE_TRACK_REVIEW_DECIDED = "operational_knowledge_track_review_decided"
TRACKS = frozenset(("review-track.domain", "review-track.security"))
DISPOSITIONS = frozenset(("review-disposition.passed", "review-disposition.changes-required"))
_DIGEST = re.compile(r"^[a-f0-9]{64}$")


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "operational knowledge review decision identifier")


def _digests(*values: str) -> bool:
    return all(_DIGEST.fullmatch(value) is not None for value in values)


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeTrackReviewDecisionPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_source_schema: str
    required_source_state: str
    required_attestor_id: str
    required_attestor_subject_id: str
    required_receipt_schema: str
    subject_digest_salt_digest: str
    maximum_authentication_age_minutes: int
    allowed_dispositions: tuple[str, ...]
    domain_basis_codes: tuple[str, ...]
    security_basis_codes: tuple[str, ...]
    maximum_basis_codes: int
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
            self.required_attestor_id,
            self.required_attestor_subject_id,
            self.required_receipt_schema,
            self.signed_by,
            *self.allowed_dispositions,
            *self.domain_basis_codes,
            *self.security_basis_codes,
        )
        if (
            self.version != 1
            or frozenset(self.allowed_dispositions) != DISPOSITIONS
            or len(set(self.domain_basis_codes)) != len(self.domain_basis_codes)
            or len(set(self.security_basis_codes)) != len(self.security_basis_codes)
            or not 1 <= self.maximum_basis_codes <= 8
            or not self.domain_basis_codes
            or not self.security_basis_codes
            or self.required_assurance_level
            not in {
                AssuranceLevel.SINGLE_FACTOR,
                AssuranceLevel.MULTI_FACTOR,
                AssuranceLevel.HARDWARE_BACKED,
            }
            or not self.signature_verified
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.issued_at
            or not _digests(self.subject_digest_salt_digest, self.canonical_digest)
        ):
            raise ValueError("Operational knowledge review decision policy is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeTrackReviewDecisionInstruction:
    decision_id: str
    organization_id: str
    environment_id: str
    source_finding_presentation_id: str
    source_finding_presentation_digest: str
    source_finding_packet_id: str
    source_finding_digest: str
    source_lease_id: str
    source_assignment_set_id: str
    review_request_id: str
    source_draft_id: str
    source_draft_digest: str
    knowledge_item_id: str
    draft_version_id: str
    track_code: str
    disposition_code: str
    basis_codes: tuple[str, ...]
    decision_policy_digest: str
    decided_by_subject_digest: str
    browser_session_binding_digest: str
    purpose_digest: str
    decided_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        _ids(
            self.decision_id,
            self.organization_id,
            self.environment_id,
            self.source_finding_presentation_id,
            self.source_finding_packet_id,
            self.source_lease_id,
            self.source_assignment_set_id,
            self.review_request_id,
            self.source_draft_id,
            self.knowledge_item_id,
            self.draft_version_id,
            self.track_code,
            self.disposition_code,
            *self.basis_codes,
        )
        if (
            self.track_code not in TRACKS
            or self.disposition_code not in DISPOSITIONS
            or not self.basis_codes
            or len(set(self.basis_codes)) != len(self.basis_codes)
            or self.decided_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.decided_at < self.expires_at
            or not _digests(
                self.source_finding_presentation_digest,
                self.source_finding_digest,
                self.source_draft_digest,
                self.decision_policy_digest,
                self.decided_by_subject_digest,
                self.browser_session_binding_digest,
                self.purpose_digest,
            )
        ):
            raise ValueError("Operational knowledge review decision instruction is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeTrackReviewDecisionReceipt:
    decision_id: str
    schema_version: str
    version: int
    attestor_id: str
    attested_by: str
    source_finding_presentation_id: str
    source_finding_presentation_digest: str
    track_code: str
    disposition_code: str
    basis_digest: str
    instruction_digest: str
    attested_at: datetime
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.decision_id,
            self.schema_version,
            self.attestor_id,
            self.attested_by,
            self.source_finding_presentation_id,
            self.track_code,
            self.disposition_code,
        )
        if (
            self.version != 1
            or self.track_code not in TRACKS
            or self.disposition_code not in DISPOSITIONS
            or self.attested_at.tzinfo is None
            or not self.signature_verified
            or not _digests(
                self.source_finding_presentation_digest,
                self.basis_digest,
                self.instruction_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge review decision receipt is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeTrackReviewDecisionClaim:
    claim_id: str
    schema_version: str
    version: int
    source_finding_presentation_id: str
    source_finding_presentation_digest: str
    decision_id: str
    organization_id: str
    environment_id: str
    track_code: str
    disposition_code: str
    basis_digest: str
    claimed_by_subject_digest: str
    browser_session_binding_digest: str
    purpose_digest: str
    claimed_at: datetime
    request_binding_digest: str
    idempotency_digest: str
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.claim_id,
            self.schema_version,
            self.source_finding_presentation_id,
            self.decision_id,
            self.organization_id,
            self.environment_id,
            self.track_code,
            self.disposition_code,
        )
        if (
            self.version != 1
            or self.track_code not in TRACKS
            or self.disposition_code not in DISPOSITIONS
            or self.claimed_at.tzinfo is None
            or not _digests(
                self.source_finding_presentation_digest,
                self.basis_digest,
                self.claimed_by_subject_digest,
                self.browser_session_binding_digest,
                self.purpose_digest,
                self.request_binding_digest,
                self.idempotency_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge review decision claim is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeTrackReviewDecisionRecord:
    decision_id: str
    schema_version: str
    version: int
    claim_id: str
    source_finding_presentation_id: str
    source_finding_presentation_digest: str
    source_finding_packet_id: str
    source_finding_digest: str
    source_lease_id: str
    source_lease_digest: str
    source_content_presentation_id: str
    source_assignment_set_id: str
    organization_id: str
    environment_id: str
    review_request_id: str
    source_review_request_digest: str
    source_draft_id: str
    source_draft_digest: str
    knowledge_item_id: str
    draft_version_id: str
    title: str
    classification: str
    access_policy_id: str
    retention_policy_id: str
    track_code: str
    disposition_code: str
    basis_codes: tuple[str, ...]
    basis_digest: str
    decided_by_subject_digest: str
    browser_session_binding_digest: str
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
    review_requested: bool = True
    reviewer_assigned: bool = True
    content_inspection_opened: bool = True
    content_disclosed: bool = True
    finding_recorded: bool = True
    finding_presented: bool = True
    exact_assignee_verified: bool = True
    browser_session_bound: bool = True
    domain_review_completed: bool = False
    security_review_completed: bool = False
    domain_review_passed: bool = False
    security_review_passed: bool = False
    correction_required: bool = False
    correction_created: bool = False
    knowledge_approved: bool = False
    knowledge_published: bool = False
    chunks_created: bool = False
    embeddings_created: bool = False
    retrieval_published: bool = False
    model_context_available: bool = False
    graph_updated: bool = False
    scheduled: bool = False
    workflow_continued: bool = False
    execution_authorized: bool = False
    deployment_approved: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        _ids(
            self.decision_id,
            self.schema_version,
            self.claim_id,
            self.source_finding_presentation_id,
            self.source_finding_packet_id,
            self.source_lease_id,
            self.source_content_presentation_id,
            self.source_assignment_set_id,
            self.organization_id,
            self.environment_id,
            self.review_request_id,
            self.source_draft_id,
            self.knowledge_item_id,
            self.draft_version_id,
            self.classification,
            self.access_policy_id,
            self.retention_policy_id,
            self.track_code,
            self.disposition_code,
            self.decision_policy_id,
            self.decision_policy_version,
            self.attestor_id,
            self.instance_state,
            *self.basis_codes,
        )
        domain_expected = self.track_code == "review-track.domain"
        passed = self.disposition_code == "review-disposition.passed"
        later_authority = (
            self.correction_created,
            self.knowledge_approved,
            self.knowledge_published,
            self.chunks_created,
            self.embeddings_created,
            self.retrieval_published,
            self.model_context_available,
            self.graph_updated,
            self.scheduled,
            self.workflow_continued,
            self.execution_authorized,
            self.deployment_approved,
            self.infrastructure_mutation_performed,
        )
        if (
            self.version != 1
            or self.instance_state != OPERATIONAL_KNOWLEDGE_TRACK_REVIEW_DECIDED
            or self.track_code not in TRACKS
            or self.disposition_code not in DISPOSITIONS
            or not 1 <= len(self.title.strip()) <= 200
            or not 20 <= len(self.purpose.strip()) <= 1000
            or not self.basis_codes
            or len(set(self.basis_codes)) != len(self.basis_codes)
            or self.decided_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.decided_at < self.expires_at
            or self.domain_review_completed is not domain_expected
            or self.security_review_completed is domain_expected
            or self.domain_review_passed is not (domain_expected and passed)
            or self.security_review_passed is not ((not domain_expected) and passed)
            or self.correction_required is not (not passed)
            or not all(
                (
                    self.review_requested,
                    self.reviewer_assigned,
                    self.content_inspection_opened,
                    self.content_disclosed,
                    self.finding_recorded,
                    self.finding_presented,
                    self.exact_assignee_verified,
                    self.browser_session_bound,
                )
            )
            or any(later_authority)
            or not _digests(
                self.source_finding_presentation_digest,
                self.source_finding_digest,
                self.source_lease_digest,
                self.source_review_request_digest,
                self.source_draft_digest,
                self.basis_digest,
                self.decided_by_subject_digest,
                self.browser_session_binding_digest,
                self.decision_policy_digest,
                self.attestation_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge review decision record is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeTrackDecisionBinding:
    track_code: str
    decision_id: str
    canonical_digest: str
    disposition_code: str

    def __post_init__(self) -> None:
        _ids(self.track_code, self.decision_id, self.disposition_code)
        if (
            self.track_code not in TRACKS
            or self.disposition_code not in DISPOSITIONS
            or not _digests(self.canonical_digest)
        ):
            raise ValueError("Operational knowledge track decision binding is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeTrackReviewDecisionGrant:
    record: OperationalKnowledgeTrackReviewDecisionRecord
    all_tracks_decided: bool
    all_tracks_passed: bool
    any_correction_required: bool
    track_decisions: tuple[OperationalKnowledgeTrackDecisionBinding, ...]

    def __post_init__(self) -> None:
        tracks = {item.track_code for item in self.track_decisions}
        if (
            len(tracks) != len(self.track_decisions)
            or self.record.track_code not in tracks
            or self.all_tracks_decided is not (tracks == TRACKS)
            or self.any_correction_required
            is not any(
                item.disposition_code == "review-disposition.changes-required"
                for item in self.track_decisions
            )
            or (
                self.all_tracks_passed
                and (not self.all_tracks_decided or self.any_correction_required)
            )
        ):
            raise ValueError("Operational knowledge review decision aggregate is invalid")
