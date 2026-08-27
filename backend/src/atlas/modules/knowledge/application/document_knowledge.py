from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from hashlib import sha256
from typing import cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.core.protected_content import ProtectedContentStore, content_digest
from atlas.modules.identity.domain.models import AuthenticatedSubject, SubjectKind
from atlas.modules.knowledge.application.document_knowledge_ports import (
    DocumentKnowledgeError,
    DocumentKnowledgePermissionAuthorizer,
    DocumentKnowledgeRepository,
)
from atlas.modules.knowledge.domain.document_knowledge import (
    DRAFT_CREATED_STATE,
    FINAL_APPROVED_STATE,
    PUBLICATION_PREPARED_STATE,
    REVIEW_DECIDED_STATE,
    REVIEW_DECISION_PASSED,
    DocumentKnowledgeDraft,
    DocumentKnowledgeFinalApproval,
    DocumentKnowledgePublicationPreparation,
    DocumentKnowledgeReviewDecision,
)

_KNOWLEDGE_DOCUMENT_DRAFT_CREATE = "knowledge.document-draft.create"
_KNOWLEDGE_DOCUMENT_REVIEW_CREATE = "knowledge.document-review.create"
_KNOWLEDGE_DOCUMENT_APPROVAL_CREATE = "knowledge.document-approval.create"
_KNOWLEDGE_DOCUMENT_PUBLICATION_PREPARATION_CREATE = (
    "knowledge.document-publication-preparation.create"
)


def _digest(payload: object) -> str:
    return sha256(
        json.dumps(_normalize(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _normalize(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def _canonical_payload(value: object) -> dict[str, object]:
    payload = cast(dict[str, object], asdict(value))  # type: ignore[call-overload]
    payload.pop("canonical_digest", None)
    return payload


def subject_digest(actor: AuthenticatedSubject, *, salt: str) -> str:
    return _digest([salt, actor.subject_id])


class DocumentKnowledgeService:
    """Orchestrates the compact document-sourced knowledge chain. See ADR-184."""

    def __init__(
        self,
        *,
        repository: DocumentKnowledgeRepository,
        protected_content: ProtectedContentStore,
        permission_authorizer: DocumentKnowledgePermissionAuthorizer,
        audit_sink: AuditSink,
        subject_salt: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._protected_content = protected_content
        self._permission_authorizer = permission_authorizer
        self._audit_sink = audit_sink
        self._subject_salt = subject_salt
        self._clock = clock or (lambda: datetime.now(UTC))

    def _subject_digest(self, actor: AuthenticatedSubject) -> str:
        return subject_digest(actor, salt=self._subject_salt)

    @staticmethod
    def _require_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise DocumentKnowledgeError(
                "document_knowledge_human_required", "Only a human actor may perform this action."
            )

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        scope_reference: str,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.knowledge.document-governance",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id=permission_id,
                resource_type="resource.knowledge.document-governance",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=(),
            )
        )

    async def curate_draft(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        content: bytes,
        title: str,
        draft_domain: str,
        content_type: str,
        classification: str,
        access_policy_id: str,
        retention_policy_id: str,
        purpose: str,
        correlation_id: str,
    ) -> DocumentKnowledgeDraft:
        self._require_human(actor)
        if actor.organization_id != organization_id:
            raise DocumentKnowledgeError(
                "document_knowledge_scope_mismatch", "Actor is outside the requested scope."
            )
        if not content or len(content) > 50_000_000:
            raise DocumentKnowledgeError(
                "document_knowledge_content_invalid", "Document content is empty or too large."
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            permission_id=_KNOWLEDGE_DOCUMENT_DRAFT_CREATE,
            correlation_id=correlation_id,
        )
        protected_digest = await self._protected_content.store(
            organization_id=organization_id, environment_id=environment_id, content=content
        )
        if protected_digest != content_digest(content):
            raise DocumentKnowledgeError(
                "document_knowledge_storage_uncertain",
                "The protected-content store did not confirm the expected content digest.",
            )
        curator_digest = self._subject_digest(actor)
        seed = _digest([organization_id, environment_id, protected_digest, curator_digest, title])
        draft_id = f"document-knowledge-draft.{seed[:24]}"
        now = self._clock()
        draft = DocumentKnowledgeDraft(
            draft_id=draft_id,
            organization_id=organization_id,
            environment_id=environment_id,
            knowledge_item_id=f"knowledge-item.{seed[:24]}",
            title=title.strip(),
            draft_domain=draft_domain,
            content_type=content_type,
            classification=classification,
            access_policy_id=access_policy_id,
            retention_policy_id=retention_policy_id,
            protected_material_digest=protected_digest,
            byte_count=len(content),
            uploaded_by_subject_digest=curator_digest,
            curated_by_subject_digest=curator_digest,
            curation_adapter_id="document-knowledge-curator.v1",
            created_at=now,
            instance_state=DRAFT_CREATED_STATE,
            purpose=purpose.strip(),
            canonical_digest="0" * 64,
        )
        draft = replace(draft, canonical_digest=_digest(_canonical_payload(draft)))
        if not await self._repository.add_draft(draft):
            raise DocumentKnowledgeError(
                "document_knowledge_draft_persistence_uncertain",
                "The draft could not be confirmed persisted.",
            )
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=_KNOWLEDGE_DOCUMENT_DRAFT_CREATE,
            result_code="document_knowledge_draft_created",
            scope_reference=draft_id,
        )
        return draft

    async def submit_review_decision(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        draft_id: str,
        decision: str,
        findings: tuple[str, ...],
        correlation_id: str,
    ) -> DocumentKnowledgeReviewDecision:
        self._require_human(actor)
        draft = await self._repository.get_draft(
            draft_id=draft_id, organization_id=organization_id, environment_id=environment_id
        )
        if draft is None:
            raise DocumentKnowledgeError(
                "document_knowledge_draft_not_found", "The referenced draft does not exist."
            )
        reviewer_digest = self._subject_digest(actor)
        if reviewer_digest == draft.curated_by_subject_digest:
            raise DocumentKnowledgeError(
                "document_knowledge_separation_of_duties_required",
                "A reviewer must be a different subject than the draft's curator.",
            )
        existing = await self._repository.get_review_by_draft(
            draft_id=draft_id, organization_id=organization_id, environment_id=environment_id
        )
        if existing is not None:
            return existing
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            permission_id=_KNOWLEDGE_DOCUMENT_REVIEW_CREATE,
            correlation_id=correlation_id,
        )
        seed = _digest([draft_id, draft.canonical_digest, reviewer_digest, decision])
        review = DocumentKnowledgeReviewDecision(
            review_id=f"document-knowledge-review.{seed[:24]}",
            draft_id=draft_id,
            draft_digest=draft.canonical_digest,
            organization_id=organization_id,
            environment_id=environment_id,
            reviewer_subject_digest=reviewer_digest,
            decision=decision,
            findings=findings,
            decided_at=self._clock(),
            instance_state=REVIEW_DECIDED_STATE,
            canonical_digest="0" * 64,
        )
        review = replace(review, canonical_digest=_digest(_canonical_payload(review)))
        if not await self._repository.add_review(review):
            raise DocumentKnowledgeError(
                "document_knowledge_review_persistence_uncertain",
                "The review decision could not be confirmed persisted.",
            )
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=_KNOWLEDGE_DOCUMENT_REVIEW_CREATE,
            result_code="document_knowledge_review_decided",
            scope_reference=review.review_id,
        )
        return review

    async def record_final_approval(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        review_id: str,
        decision: str,
        rationale: str,
        correlation_id: str,
    ) -> DocumentKnowledgeFinalApproval:
        self._require_human(actor)
        review = await self._repository.get_review(
            review_id=review_id, organization_id=organization_id, environment_id=environment_id
        )
        if review is None:
            raise DocumentKnowledgeError(
                "document_knowledge_review_not_found", "The referenced review does not exist."
            )
        if review.decision != REVIEW_DECISION_PASSED:
            raise DocumentKnowledgeError(
                "document_knowledge_review_not_passed",
                "Final approval requires a passed review decision.",
            )
        approver_digest = self._subject_digest(actor)
        draft = await self._repository.get_draft(
            draft_id=review.draft_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if draft is None:
            raise DocumentKnowledgeError(
                "document_knowledge_draft_not_found", "The referenced draft does not exist."
            )
        if approver_digest in (draft.curated_by_subject_digest, review.reviewer_subject_digest):
            raise DocumentKnowledgeError(
                "document_knowledge_separation_of_duties_required",
                "An approver must differ from both the curator and the reviewer.",
            )
        existing = await self._repository.get_approval_by_review(
            review_id=review_id, organization_id=organization_id, environment_id=environment_id
        )
        if existing is not None:
            return existing
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            permission_id=_KNOWLEDGE_DOCUMENT_APPROVAL_CREATE,
            correlation_id=correlation_id,
        )
        seed = _digest([review_id, review.canonical_digest, approver_digest, decision])
        approval = DocumentKnowledgeFinalApproval(
            approval_id=f"document-knowledge-approval.{seed[:24]}",
            review_id=review_id,
            review_digest=review.canonical_digest,
            draft_id=review.draft_id,
            organization_id=organization_id,
            environment_id=environment_id,
            approver_subject_digest=approver_digest,
            decision=decision,
            rationale=rationale.strip(),
            decided_at=self._clock(),
            instance_state=FINAL_APPROVED_STATE,
            canonical_digest="0" * 64,
        )
        approval = replace(approval, canonical_digest=_digest(_canonical_payload(approval)))
        if not await self._repository.add_approval(approval):
            raise DocumentKnowledgeError(
                "document_knowledge_approval_persistence_uncertain",
                "The approval could not be confirmed persisted.",
            )
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=_KNOWLEDGE_DOCUMENT_APPROVAL_CREATE,
            result_code="document_knowledge_final_approved",
            scope_reference=approval.approval_id,
        )
        return approval

    async def prepare_publication(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        approval_id: str,
        chunking_profile_digest: str,
        correlation_id: str,
    ) -> DocumentKnowledgePublicationPreparation:
        self._require_human(actor)
        approval = await self._repository.get_approval(
            approval_id=approval_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if approval is None:
            raise DocumentKnowledgeError(
                "document_knowledge_approval_not_found", "The referenced approval does not exist."
            )
        if approval.decision != "approved":
            raise DocumentKnowledgeError(
                "document_knowledge_approval_not_granted",
                "Publication preparation requires a granted final approval.",
            )
        draft = await self._repository.get_draft(
            draft_id=approval.draft_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if draft is None:
            raise DocumentKnowledgeError(
                "document_knowledge_draft_not_found", "The referenced draft does not exist."
            )
        existing = await self._repository.get_preparation_by_approval(
            approval_id=approval_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if existing is not None:
            return existing
        preparer_digest = self._subject_digest(actor)
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            permission_id=_KNOWLEDGE_DOCUMENT_PUBLICATION_PREPARATION_CREATE,
            correlation_id=correlation_id,
        )
        seed = _digest([approval_id, approval.canonical_digest, preparer_digest])
        preparation = DocumentKnowledgePublicationPreparation(
            preparation_id=f"document-knowledge-preparation.{seed[:24]}",
            approval_id=approval_id,
            approval_digest=approval.canonical_digest,
            draft_id=draft.draft_id,
            knowledge_item_id=draft.knowledge_item_id,
            organization_id=organization_id,
            environment_id=environment_id,
            classification=draft.classification,
            access_policy_id=draft.access_policy_id,
            retention_policy_id=draft.retention_policy_id,
            protected_material_digest=draft.protected_material_digest,
            chunking_profile_digest=chunking_profile_digest,
            prepared_by_subject_digest=preparer_digest,
            prepared_at=self._clock(),
            instance_state=PUBLICATION_PREPARED_STATE,
            canonical_digest="0" * 64,
        )
        preparation = replace(
            preparation, canonical_digest=_digest(_canonical_payload(preparation))
        )
        if not await self._repository.add_preparation(preparation):
            raise DocumentKnowledgeError(
                "document_knowledge_preparation_persistence_uncertain",
                "The publication preparation could not be confirmed persisted.",
            )
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=_KNOWLEDGE_DOCUMENT_PUBLICATION_PREPARATION_CREATE,
            result_code="document_knowledge_publication_prepared",
            scope_reference=preparation.preparation_id,
        )
        return preparation

    async def close(self) -> None:
        await self._repository.close()
