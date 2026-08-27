"""Compact document-sourced knowledge governance chain. See ADR-184.

Deliberately leaner than the ADR-042-052 operational-evidence chain: four
stages instead of eleven, and single-pass validation instead of repeated
cross-field digest reconstruction at every read. The load-bearing safety
properties are preserved: real content never appears in these records (only
digests returned by atlas.core.protected_content), every transition is bound
to the exact prior stage's id + digest, and separation of duties (curator !=
reviewer != approver) is enforced by the application service, not merely
documented.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_MEDIA_TYPE = re.compile(r"^[a-z]+/[a-z0-9.+-]+$")

DRAFT_CREATED_STATE = "document_knowledge_draft_created"
REVIEW_DECIDED_STATE = "document_knowledge_review_decided"
FINAL_APPROVED_STATE = "document_knowledge_final_approved"
PUBLICATION_PREPARED_STATE = "document_knowledge_publication_prepared"

REVIEW_DECISION_PASSED = "passed"
REVIEW_DECISION_CHANGES_REQUIRED = "changes_required"
REVIEW_DECISION_REJECTED = "rejected"
_REVIEW_DECISIONS = frozenset(
    {REVIEW_DECISION_PASSED, REVIEW_DECISION_CHANGES_REQUIRED, REVIEW_DECISION_REJECTED}
)

APPROVAL_APPROVED = "approved"
APPROVAL_REJECTED = "rejected"
_APPROVALS = frozenset({APPROVAL_APPROVED, APPROVAL_REJECTED})


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "document knowledge identifier")


def _digest_ok(*values: str) -> bool:
    return all(_DIGEST.fullmatch(value) is not None for value in values)


@dataclass(frozen=True, slots=True)
class DocumentKnowledgeDraft:
    draft_id: str
    organization_id: str
    environment_id: str
    knowledge_item_id: str
    title: str
    draft_domain: str
    content_type: str
    classification: str
    access_policy_id: str
    retention_policy_id: str
    protected_material_digest: str
    byte_count: int
    uploaded_by_subject_digest: str
    curated_by_subject_digest: str
    curation_adapter_id: str
    created_at: datetime
    instance_state: str
    purpose: str
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.draft_id,
            self.organization_id,
            self.environment_id,
            self.knowledge_item_id,
            self.draft_domain,
            self.classification,
            self.access_policy_id,
            self.retention_policy_id,
            self.curation_adapter_id,
            self.instance_state,
        )
        if (
            self.instance_state != DRAFT_CREATED_STATE
            or not 1 <= len(self.title.strip()) <= 200
            or not 20 <= len(self.purpose.strip()) <= 1000
            or _MEDIA_TYPE.fullmatch(self.content_type) is None
            or self.byte_count < 1
            or self.created_at.tzinfo is None
            or not _digest_ok(
                self.protected_material_digest,
                self.uploaded_by_subject_digest,
                self.curated_by_subject_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("document knowledge draft is invalid")


@dataclass(frozen=True, slots=True)
class DocumentKnowledgeReviewDecision:
    review_id: str
    draft_id: str
    draft_digest: str
    organization_id: str
    environment_id: str
    reviewer_subject_digest: str
    decision: str
    findings: tuple[str, ...]
    decided_at: datetime
    instance_state: str
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.review_id,
            self.draft_id,
            self.organization_id,
            self.environment_id,
            self.instance_state,
        )
        if (
            self.instance_state != REVIEW_DECIDED_STATE
            or self.decision not in _REVIEW_DECISIONS
            or not 1 <= len(self.findings) <= 20
            or any(not finding.strip() for finding in self.findings)
            or self.decided_at.tzinfo is None
            or not _digest_ok(
                self.draft_digest, self.reviewer_subject_digest, self.canonical_digest
            )
        ):
            raise ValueError("document knowledge review decision is invalid")


@dataclass(frozen=True, slots=True)
class DocumentKnowledgeFinalApproval:
    approval_id: str
    review_id: str
    review_digest: str
    draft_id: str
    organization_id: str
    environment_id: str
    approver_subject_digest: str
    decision: str
    rationale: str
    decided_at: datetime
    instance_state: str
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.approval_id,
            self.review_id,
            self.draft_id,
            self.organization_id,
            self.environment_id,
            self.instance_state,
        )
        if (
            self.instance_state != FINAL_APPROVED_STATE
            or self.decision not in _APPROVALS
            or not 20 <= len(self.rationale.strip()) <= 1000
            or self.decided_at.tzinfo is None
            or not _digest_ok(
                self.review_digest, self.approver_subject_digest, self.canonical_digest
            )
        ):
            raise ValueError("document knowledge final approval is invalid")


@dataclass(frozen=True, slots=True)
class DocumentKnowledgePublicationPreparation:
    preparation_id: str
    approval_id: str
    approval_digest: str
    draft_id: str
    knowledge_item_id: str
    organization_id: str
    environment_id: str
    classification: str
    access_policy_id: str
    retention_policy_id: str
    protected_material_digest: str
    chunking_profile_digest: str
    prepared_by_subject_digest: str
    prepared_at: datetime
    instance_state: str
    canonical_digest: str

    def __post_init__(self) -> None:
        _ids(
            self.preparation_id,
            self.approval_id,
            self.draft_id,
            self.knowledge_item_id,
            self.organization_id,
            self.environment_id,
            self.classification,
            self.access_policy_id,
            self.retention_policy_id,
            self.instance_state,
        )
        if (
            self.instance_state != PUBLICATION_PREPARED_STATE
            or self.prepared_at.tzinfo is None
            or not _digest_ok(
                self.approval_digest,
                self.protected_material_digest,
                self.chunking_profile_digest,
                self.prepared_by_subject_digest,
                self.canonical_digest,
            )
        ):
            raise ValueError("document knowledge publication preparation is invalid")
