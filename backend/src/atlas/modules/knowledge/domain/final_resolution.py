from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import validate_stable_identifier

FINAL_APPROVED = "final-resolution.approved"
FINAL_REJECTED = "final-resolution.rejected"
FINAL_DISPOSITIONS = frozenset({FINAL_APPROVED, FINAL_REJECTED})
FINAL_APPROVED_STATE = "operational_knowledge_final_approved"
FINAL_REJECTED_STATE = "operational_knowledge_final_rejected"
_DIGEST = re.compile(r"^[a-f0-9]{64}$")


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "operational knowledge final resolution identifier")


def _digests(*values: str) -> None:
    if not all(_DIGEST.fullmatch(value) is not None for value in values):
        raise ValueError("Operational knowledge final resolution digest is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeFinalResolutionPolicySnapshot:
    policy_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    policy_version: str
    required_decision_schema: str
    required_decision_state: str
    required_request_schema: str
    required_request_state: str
    required_draft_schema: str
    required_draft_state: str
    allowed_dispositions: tuple[str, ...]
    allowed_basis_codes: tuple[str, ...]
    maximum_authentication_age_minutes: int
    subject_digest_salt_digest: str
    browser_binding_key_digest: str
    required_attestor_id: str
    signed_by: str
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
            self.required_decision_schema,
            self.required_decision_state,
            self.required_request_schema,
            self.required_request_state,
            self.required_draft_schema,
            self.required_draft_state,
            self.required_attestor_id,
            self.signed_by,
            *self.allowed_dispositions,
            *self.allowed_basis_codes,
        )
        if (
            self.version != 1
            or set(self.allowed_dispositions) != FINAL_DISPOSITIONS
            or not self.allowed_basis_codes
            or len(set(self.allowed_basis_codes)) != len(self.allowed_basis_codes)
            or not 1 <= self.maximum_authentication_age_minutes <= 60
            or self.issued_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or not self.issued_at < self.expires_at
            or not _all_digests(
                self.subject_digest_salt_digest,
                self.browser_binding_key_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge final resolution policy is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeFinalResolutionInstruction:
    resolution_id: str
    organization_id: str
    environment_id: str
    review_request_id: str
    review_request_digest: str
    source_draft_id: str
    source_draft_digest: str
    assignment_set_id: str
    decision_aggregate_digest: str
    knowledge_item_id: str
    draft_version_id: str
    approver_subject_digest: str
    browser_session_binding_digest: str
    disposition_code: str
    basis_codes: tuple[str, ...]
    basis_digest: str
    policy_id: str
    policy_digest: str
    purpose: str
    requested_at: datetime

    def __post_init__(self) -> None:
        _ids(
            self.resolution_id,
            self.organization_id,
            self.environment_id,
            self.review_request_id,
            self.source_draft_id,
            self.assignment_set_id,
            self.knowledge_item_id,
            self.draft_version_id,
            self.disposition_code,
            self.policy_id,
            *self.basis_codes,
        )
        if (
            self.disposition_code not in FINAL_DISPOSITIONS
            or not self.basis_codes
            or len(set(self.basis_codes)) != len(self.basis_codes)
            or not 20 <= len(self.purpose.strip()) <= 1000
            or self.requested_at.tzinfo is None
            or not _all_digests(
                self.review_request_digest,
                self.source_draft_digest,
                self.decision_aggregate_digest,
                self.approver_subject_digest,
                self.browser_session_binding_digest,
                self.basis_digest,
                self.policy_digest,
            )
        ):
            raise ValueError("Operational knowledge final resolution instruction is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeFinalResolutionReceipt:
    resolution_id: str
    schema_version: str
    version: int
    attestor_id: str
    attested_by: str
    disposition_code: str
    instruction_digest: str
    attested_at: datetime
    signature_verified: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.resolution_id,
            self.schema_version,
            self.attestor_id,
            self.attested_by,
            self.disposition_code,
        )
        if (
            self.version != 1
            or self.disposition_code not in FINAL_DISPOSITIONS
            or self.attested_at.tzinfo is None
            or not self.signature_verified
            or not _all_digests(self.instruction_digest, self.canonical_digest)
        ):
            raise ValueError("Operational knowledge final resolution receipt is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeFinalResolutionClaim:
    claim_id: str
    schema_version: str
    version: int
    review_request_id: str
    resolution_id: str
    claimed_by_subject_digest: str
    browser_session_binding_digest: str
    request_binding_digest: str
    idempotency_digest: str
    organization_id: str
    environment_id: str
    claimed_at: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.claim_id,
            self.schema_version,
            self.review_request_id,
            self.resolution_id,
            self.organization_id,
            self.environment_id,
        )
        if (
            self.version != 1
            or self.claimed_at.tzinfo is None
            or not _all_digests(
                self.claimed_by_subject_digest,
                self.browser_session_binding_digest,
                self.request_binding_digest,
                self.idempotency_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge final resolution claim is invalid")


@dataclass(frozen=True, slots=True)
class OperationalKnowledgeFinalResolutionRecord:
    resolution_id: str
    schema_version: str
    version: int
    claim_id: str
    review_request_id: str
    review_request_digest: str
    source_draft_id: str
    source_draft_digest: str
    source_assignment_set_id: str
    decision_ids: tuple[str, str]
    decision_digests: tuple[str, str]
    decision_aggregate_digest: str
    organization_id: str
    environment_id: str
    knowledge_item_id: str
    draft_version_id: str
    title: str
    classification: str
    access_policy_id: str
    retention_policy_id: str
    disposition_code: str
    basis_codes: tuple[str, ...]
    basis_digest: str
    approved_by_subject_digest: str
    browser_session_binding_digest: str
    resolution_policy_id: str
    resolution_policy_digest: str
    resolution_policy_version: str
    attestor_id: str
    attestation_digest: str
    resolved_at: datetime
    instance_state: str
    purpose: str
    canonical_digest: str
    domain_review_completed: bool = True
    security_review_completed: bool = True
    domain_review_passed: bool = True
    security_review_passed: bool = True
    correction_required: bool = False
    correction_created: bool = False
    knowledge_approved: bool = False
    publication_ready: bool = False
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
            self.resolution_id,
            self.schema_version,
            self.claim_id,
            self.review_request_id,
            self.source_draft_id,
            self.source_assignment_set_id,
            self.organization_id,
            self.environment_id,
            self.knowledge_item_id,
            self.draft_version_id,
            self.classification,
            self.access_policy_id,
            self.retention_policy_id,
            self.disposition_code,
            self.resolution_policy_id,
            self.resolution_policy_version,
            self.attestor_id,
            self.instance_state,
            *self.decision_ids,
            *self.basis_codes,
        )
        approved = self.disposition_code == FINAL_APPROVED
        later_authority = (
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
            or self.disposition_code not in FINAL_DISPOSITIONS
            or self.instance_state != (FINAL_APPROVED_STATE if approved else FINAL_REJECTED_STATE)
            or self.knowledge_approved is not approved
            or self.publication_ready is not approved
            or not all(
                (
                    self.domain_review_completed,
                    self.security_review_completed,
                    self.domain_review_passed,
                    self.security_review_passed,
                )
            )
            or self.correction_required
            or self.correction_created
            or any(later_authority)
            or len(set(self.decision_ids)) != 2
            or len(set(self.decision_digests)) != 2
            or not self.basis_codes
            or not 1 <= len(self.title.strip()) <= 200
            or not 20 <= len(self.purpose.strip()) <= 1000
            or self.resolved_at.tzinfo is None
            or not _all_digests(
                self.review_request_digest,
                self.source_draft_digest,
                *self.decision_digests,
                self.decision_aggregate_digest,
                self.basis_digest,
                self.approved_by_subject_digest,
                self.browser_session_binding_digest,
                self.resolution_policy_digest,
                self.attestation_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("Operational knowledge final resolution record is invalid")


def _all_digests(*values: str) -> bool:
    try:
        _digests(*values)
    except ValueError:
        return False
    return True
