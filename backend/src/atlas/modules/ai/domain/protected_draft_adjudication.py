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
class ProtectedDraftAdjudicationPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_invocation_schema: str
    required_invocation_state: str
    required_draft_schema: str
    required_adjudicator_id: str
    required_adjudicator_attestor_id: str
    required_receipt_schema: str
    protected_vault_id: str
    validation_profile_digest: str
    prohibited_output_profile_digest: str
    browser_binding_key_digest: str
    classification_ceiling: str
    maximum_authentication_age_minutes: int
    maximum_summary_characters: int
    minimum_citation_count: int
    minimum_unknown_count: int
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
                self.required_invocation_schema,
                self.required_invocation_state,
                self.required_draft_schema,
                self.required_adjudicator_id,
                self.required_receipt_schema,
                self.protected_vault_id,
            )
            or not _digests(
                self.validation_profile_digest,
                self.prohibited_output_profile_digest,
                self.browser_binding_key_digest,
                self.canonical_digest,
            )
            or not 1 <= self.maximum_authentication_age_minutes <= 60
            or not 100 <= self.maximum_summary_characters <= 100_000
            or not 0 <= self.minimum_citation_count <= 1_000
            or not 0 <= self.minimum_unknown_count <= 1_000
            or not 1 <= self.retention_minutes <= 1_440
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.issued_at < self.expires_at
            or not self.signature_verified
        ):
            raise ValueError("Protected draft-adjudication policy is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedDraftAdjudicationInstruction:
    adjudication_id: str
    invocation_id: str
    invocation_digest: str
    context_id: str
    context_digest: str
    context_package_digest: str
    draft_digest: str
    citation_set_digest: str
    output_safety_digest: str
    organization_id: str
    environment_id: str
    consumer_subject_digest: str
    adjudication_authorization_digest: str
    policy_id: str
    policy_digest: str
    validation_profile_digest: str
    prohibited_output_profile_digest: str
    minimum_citation_count: int
    minimum_unknown_count: int
    maximum_summary_characters: int
    requested_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ProtectedDraftAdjudicationReport:
    adjudication_id: str
    invocation_id: str
    draft_digest: str
    outcome: str
    check_codes: tuple[str, ...]
    citation_count: int
    unknown_count: int
    summary_character_count: int
    generated_at: datetime
    expires_at: datetime
    canonical_digest: str


@dataclass(frozen=True, slots=True)
class ProtectedDraftAdjudicationReceipt:
    adjudication_id: str
    schema_version: str
    version: int
    adjudicator_id: str
    attested_by: str
    invocation_id: str
    invocation_digest: str
    context_digest: str
    draft_digest: str
    adjudication_authorization_digest: str
    policy_digest: str
    protected_report_reference: str
    protected_report_digest: str
    report_digest: str
    check_set_digest: str
    citation_coverage_digest: str
    unknown_preservation_digest: str
    prohibited_output_digest: str
    check_count: int
    citation_count: int
    unknown_count: int
    outcome: str
    adjudicated_at: datetime
    expires_at: datetime
    schema_verified: bool
    citations_verified: bool
    unknowns_verified: bool
    prohibited_output_verified: bool
    no_model_used: bool
    protected_vault_write_verified: bool
    signature_verified: bool
    canonical_digest: str


@dataclass(frozen=True, slots=True)
class ProtectedDraftAdjudicationClaim:
    claim_id: str
    schema_version: str
    version: int
    adjudication_id: str
    invocation_id: str
    claimed_by_subject_digest: str
    browser_session_binding_digest: str
    request_binding_digest: str
    idempotency_digest: str
    organization_id: str
    environment_id: str
    claimed_at: datetime
    canonical_digest: str


@dataclass(frozen=True, slots=True)
class ProtectedDraftAdjudicationRecord:
    adjudication_id: str
    schema_version: str
    version: int
    claim_id: str
    invocation_id: str
    invocation_digest: str
    context_id: str
    context_digest: str
    organization_id: str
    environment_id: str
    classification: str
    consumer_subject_digest: str
    browser_session_binding_digest: str
    adjudication_policy_id: str
    adjudication_policy_digest: str
    adjudication_policy_version: str
    adjudicator_id: str
    adjudication_receipt_digest: str
    adjudication_authorization_digest: str
    draft_digest: str
    protected_report_reference: str
    protected_report_digest: str
    report_digest: str
    check_set_digest: str
    citation_coverage_digest: str
    unknown_preservation_digest: str
    prohibited_output_digest: str
    check_count: int
    citation_count: int
    unknown_count: int
    outcome: str
    adjudicated_at: datetime
    expires_at: datetime
    instance_state: str
    purpose: str
    canonical_digest: str
    knowledge_retrieved: bool = True
    model_context_available: bool = True
    model_invoked: bool = True
    protected_draft_available: bool = True
    model_draft_adjudicated: bool = True
    answer_generated: bool = False
    graph_updated: bool = False
    scheduled: bool = False
    workflow_continued: bool = False
    execution_authorized: bool = False
    deployment_approved: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        later = (
            self.answer_generated,
            self.graph_updated,
            self.scheduled,
            self.workflow_continued,
            self.execution_authorized,
            self.deployment_approved,
            self.infrastructure_mutation_performed,
        )
        if (
            self.version != 1
            or self.instance_state != "protected_model_draft_adjudicated"
            or self.outcome
            not in {"adjudication-outcome.eligible", "adjudication-outcome.rejected"}
            or not all(
                (
                    self.knowledge_retrieved,
                    self.model_context_available,
                    self.model_invoked,
                    self.protected_draft_available,
                    self.model_draft_adjudicated,
                )
            )
            or any(later)
            or self.check_count < 1
            or self.citation_count < 0
            or self.unknown_count < 0
            or not 20 <= len(self.purpose.strip()) <= 1_000
            or self.adjudicated_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.adjudicated_at < self.expires_at
        ):
            raise ValueError("Protected draft-adjudication record is invalid")


@dataclass(frozen=True, slots=True)
class ProtectedDraftAdjudicationManifest:
    adjudication_id: str
    invocation_id: str
    context_id: str
    outcome: str
    check_count: int
    citation_count: int
    unknown_count: int
    report_digest: str
    check_set_digest: str
    citation_coverage_digest: str
    unknown_preservation_digest: str
    prohibited_output_digest: str
    adjudicated_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class ProtectedDraftAdjudicationResult:
    record: ProtectedDraftAdjudicationRecord
    manifest: ProtectedDraftAdjudicationManifest
