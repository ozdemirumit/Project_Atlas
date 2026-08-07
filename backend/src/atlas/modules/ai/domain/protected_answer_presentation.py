from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


def _ids(*values: str) -> bool:
    return all(3 <= len(value.strip()) <= 256 for value in values)


def _digests(*values: str) -> bool:
    return all(
        len(value) == 64 and all(char in "0123456789abcdef" for char in value) for value in values
    )


@dataclass(frozen=True, slots=True)
class ProtectedAnswerPresentationPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_adjudication_schema: str
    required_adjudication_state: str
    required_adjudication_outcome: str
    required_draft_schema: str
    required_presenter_id: str
    required_presenter_attestor_id: str
    required_receipt_schema: str
    media_type: str
    rendering_profile_digest: str
    prohibited_output_profile_digest: str
    browser_binding_key_digest: str
    classification_ceiling: str
    maximum_authentication_age_minutes: int
    maximum_summary_characters: int
    maximum_citation_count: int
    maximum_unknown_count: int
    maximum_output_bytes: int
    retention_minutes: int
    signed_by: str
    signature_verified: bool
    issued_at: datetime
    expires_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        if (
            self.version != 1
            or not _ids(
                self.policy_id,
                self.schema_version,
                self.organization_id,
                self.environment_id,
                self.required_adjudication_schema,
                self.required_adjudication_state,
                self.required_draft_schema,
                self.required_presenter_id,
                self.required_receipt_schema,
            )
            or self.required_adjudication_outcome != "adjudication-outcome.eligible"
            or self.media_type != "text/plain"
            or not _digests(
                self.rendering_profile_digest,
                self.prohibited_output_profile_digest,
                self.browser_binding_key_digest,
                self.canonical_digest,
            )
            or not 1 <= self.maximum_authentication_age_minutes <= 60
            or not 100 <= self.maximum_summary_characters <= 100_000
            or not 1 <= self.maximum_citation_count <= 1_000
            or not 1 <= self.maximum_unknown_count <= 1_000
            or not 256 <= self.maximum_output_bytes <= 1_000_000
            or not 1 <= self.retention_minutes <= 1_440
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.issued_at < self.expires_at
            or not self.signature_verified
        ):
            raise ValueError("Protected answer-presentation policy is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedAnswerPresentationInstruction:
    presentation_id: str
    adjudication_id: str
    adjudication_digest: str
    invocation_id: str
    invocation_digest: str
    context_id: str
    context_digest: str
    context_package_digest: str
    draft_digest: str
    report_digest: str
    organization_id: str
    environment_id: str
    consumer_subject_digest: str
    presentation_authorization_digest: str
    policy_id: str
    policy_digest: str
    rendering_profile_digest: str
    prohibited_output_profile_digest: str
    media_type: str
    maximum_summary_characters: int
    maximum_citation_count: int
    maximum_unknown_count: int
    maximum_output_bytes: int
    requested_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ProtectedPresentedAnswer:
    presentation_id: str
    summary: str
    citation_references: tuple[str, ...]
    unknowns: tuple[str, ...]
    media_type: str
    byte_count: int
    generated_at: datetime
    expires_at: datetime
    canonical_digest: str


@dataclass(frozen=True, slots=True)
class ProtectedAnswerPresentationReceipt:
    presentation_id: str
    schema_version: str
    version: int
    presenter_id: str
    attested_by: str
    adjudication_id: str
    adjudication_digest: str
    invocation_digest: str
    draft_digest: str
    report_digest: str
    presentation_authorization_digest: str
    policy_digest: str
    answer_digest: str
    citation_set_digest: str
    unknown_set_digest: str
    source_binding_digest: str
    rendering_digest: str
    cleanup_digest: str
    summary_character_count: int
    citation_count: int
    unknown_count: int
    byte_count: int
    presented_at: datetime
    expires_at: datetime
    source_verified: bool
    eligible_outcome_verified: bool
    content_verified: bool
    inert_rendering_verified: bool
    no_model_used: bool
    cleanup_verified: bool
    signature_verified: bool
    canonical_digest: str


@dataclass(frozen=True, slots=True)
class ProtectedAnswerPresentationClaim:
    claim_id: str
    schema_version: str
    version: int
    presentation_id: str
    adjudication_id: str
    claimed_by_subject_digest: str
    browser_session_binding_digest: str
    request_binding_digest: str
    idempotency_digest: str
    organization_id: str
    environment_id: str
    claimed_at: datetime
    canonical_digest: str


@dataclass(frozen=True, slots=True)
class ProtectedAnswerPresentationRecord:
    presentation_id: str
    schema_version: str
    version: int
    claim_id: str
    adjudication_id: str
    adjudication_digest: str
    invocation_id: str
    invocation_digest: str
    context_id: str
    context_digest: str
    context_package_digest: str
    organization_id: str
    environment_id: str
    classification: str
    consumer_subject_digest: str
    browser_session_binding_digest: str
    presentation_policy_id: str
    presentation_policy_digest: str
    presentation_policy_version: str
    presenter_id: str
    presentation_receipt_digest: str
    presentation_authorization_digest: str
    draft_digest: str
    report_digest: str
    answer_digest: str
    citation_set_digest: str
    unknown_set_digest: str
    source_binding_digest: str
    rendering_digest: str
    cleanup_digest: str
    summary_character_count: int
    citation_count: int
    unknown_count: int
    byte_count: int
    media_type: str
    presented_at: datetime
    expires_at: datetime
    instance_state: str
    purpose: str
    canonical_digest: str
    knowledge_retrieved: bool = True
    model_context_available: bool = True
    model_invoked: bool = True
    protected_draft_available: bool = True
    model_draft_adjudicated: bool = True
    answer_presented: bool = True
    recommendation_generated: bool = False
    graph_updated: bool = False
    scheduled: bool = False
    workflow_continued: bool = False
    execution_authorized: bool = False
    deployment_approved: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        later = (
            self.recommendation_generated,
            self.graph_updated,
            self.scheduled,
            self.workflow_continued,
            self.execution_authorized,
            self.deployment_approved,
            self.infrastructure_mutation_performed,
        )
        if (
            self.version != 1
            or self.instance_state != "protected_answer_presented"
            or not all(
                (
                    self.knowledge_retrieved,
                    self.model_context_available,
                    self.model_invoked,
                    self.protected_draft_available,
                    self.model_draft_adjudicated,
                    self.answer_presented,
                )
            )
            or any(later)
            or self.media_type != "text/plain"
            or self.summary_character_count < 1
            or self.citation_count < 1
            or self.unknown_count < 1
            or self.byte_count < 1
            or not 20 <= len(self.purpose.strip()) <= 1_000
            or self.presented_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.presented_at < self.expires_at
        ):
            raise ValueError("Protected answer-presentation record is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedAnswerPresentationManifest:
    presentation_id: str
    adjudication_id: str
    invocation_id: str
    context_id: str
    summary_character_count: int
    citation_count: int
    unknown_count: int
    byte_count: int
    media_type: str
    answer_digest: str
    citation_set_digest: str
    unknown_set_digest: str
    source_binding_digest: str
    rendering_digest: str
    cleanup_digest: str
    presented_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ProtectedAnswerPresentationResult:
    record: ProtectedAnswerPresentationRecord
    manifest: ProtectedAnswerPresentationManifest
    answer: ProtectedPresentedAnswer
