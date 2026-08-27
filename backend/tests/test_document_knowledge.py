from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.protected_content import InMemoryProtectedContentStore
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.knowledge.adapters.document_knowledge_memory import (
    InMemoryDocumentKnowledgeRepository,
)
from atlas.modules.knowledge.application.document_knowledge import DocumentKnowledgeService
from atlas.modules.knowledge.application.document_knowledge_ports import DocumentKnowledgeError
from atlas.modules.knowledge.domain.document_knowledge import (
    REVIEW_DECISION_CHANGES_REQUIRED,
    REVIEW_DECISION_PASSED,
    DocumentKnowledgeDraft,
)

ORG = "organization.development"
ENV = "environment.test"
NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)


class AllowAllAuthorizer:
    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        permission_id: str,
        correlation_id: str,
    ) -> None:
        return None


def _subject(subject_id: str) -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id=subject_id,
        display_name=subject_id,
        kind=SubjectKind.HUMAN,
        provider_id="provider.development",
        organization_id=ORG,
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.SINGLE_FACTOR,
        authenticated_at=NOW,
        role_ids=(),
    )


def build_service() -> DocumentKnowledgeService:
    return DocumentKnowledgeService(
        repository=InMemoryDocumentKnowledgeRepository(),
        protected_content=InMemoryProtectedContentStore(),
        permission_authorizer=AllowAllAuthorizer(),
        audit_sink=_NullAuditSink(),
        subject_salt="test-salt",
        clock=lambda: NOW,
    )


class _NullAuditSink:
    def __init__(self) -> None:
        self.records: list[object] = []

    async def record(self, event: object) -> None:
        self.records.append(event)


@pytest.mark.asyncio
async def test_curate_draft_stores_real_content_and_returns_digest_only_record() -> None:
    service = build_service()
    content = b"# Vendor Runbook\n\nRestart the read-only diagnostic collector.\n"

    draft = await service.curate_draft(
        actor=_subject("subject.curator"),
        organization_id=ORG,
        environment_id=ENV,
        content=content,
        title="Vendor Runbook",
        draft_domain="domain.vendor",
        content_type="text/markdown",
        classification="classification.internal",
        access_policy_id="access-policy.default",
        retention_policy_id="retention-policy.default",
        purpose="Vendor-provided runbook for storage controller diagnostics.",
        correlation_id="cor_1",
    )

    assert draft.byte_count == len(content)
    assert draft.draft_domain == "domain.vendor"
    retrieved = await service._protected_content.retrieve(
        organization_id=ORG, environment_id=ENV, digest=draft.protected_material_digest
    )
    assert retrieved == content


@pytest.mark.asyncio
async def test_curate_draft_rejects_empty_content() -> None:
    service = build_service()
    with pytest.raises(DocumentKnowledgeError) as excinfo:
        await service.curate_draft(
            actor=_subject("subject.curator"),
            organization_id=ORG,
            environment_id=ENV,
            content=b"",
            title="Empty",
            draft_domain="domain.vendor",
            content_type="text/markdown",
            classification="classification.internal",
            access_policy_id="access-policy.default",
            retention_policy_id="retention-policy.default",
            purpose="An empty document should never be accepted for curation.",
            correlation_id="cor_1",
        )
    assert excinfo.value.code == "document_knowledge_content_invalid"


async def _curated_draft(
    service: DocumentKnowledgeService, *, curator: str = "subject.curator"
) -> DocumentKnowledgeDraft:
    return await service.curate_draft(
        actor=_subject(curator),
        organization_id=ORG,
        environment_id=ENV,
        content=b"content",
        title="Doc",
        draft_domain="domain.vendor",
        content_type="text/plain",
        classification="classification.internal",
        access_policy_id="access-policy.default",
        retention_policy_id="retention-policy.default",
        purpose="A document used to validate the review workflow end to end.",
        correlation_id="cor_1",
    )


@pytest.mark.asyncio
async def test_review_by_curator_is_rejected_for_separation_of_duties() -> None:
    service = build_service()
    draft = await _curated_draft(service)

    with pytest.raises(DocumentKnowledgeError) as excinfo:
        await service.submit_review_decision(
            actor=_subject("subject.curator"),
            organization_id=ORG,
            environment_id=ENV,
            draft_id=draft.draft_id,
            decision=REVIEW_DECISION_PASSED,
            findings=("No issues found.",),
            correlation_id="cor_2",
        )
    assert excinfo.value.code == "document_knowledge_separation_of_duties_required"


@pytest.mark.asyncio
async def test_review_decision_is_idempotent_per_draft() -> None:
    service = build_service()
    draft = await _curated_draft(service)

    first = await service.submit_review_decision(
        actor=_subject("subject.reviewer"),
        organization_id=ORG,
        environment_id=ENV,
        draft_id=draft.draft_id,
        decision=REVIEW_DECISION_PASSED,
        findings=("No issues found.",),
        correlation_id="cor_2",
    )
    second = await service.submit_review_decision(
        actor=_subject("subject.reviewer"),
        organization_id=ORG,
        environment_id=ENV,
        draft_id=draft.draft_id,
        decision=REVIEW_DECISION_PASSED,
        findings=("No issues found.",),
        correlation_id="cor_3",
    )
    assert first.review_id == second.review_id


@pytest.mark.asyncio
async def test_final_approval_requires_passed_review_and_distinct_approver() -> None:
    service = build_service()
    draft = await _curated_draft(service)
    review = await service.submit_review_decision(
        actor=_subject("subject.reviewer"),
        organization_id=ORG,
        environment_id=ENV,
        draft_id=draft.draft_id,
        decision=REVIEW_DECISION_CHANGES_REQUIRED,
        findings=("Needs a source citation.",),
        correlation_id="cor_2",
    )

    with pytest.raises(DocumentKnowledgeError) as excinfo:
        await service.record_final_approval(
            actor=_subject("subject.approver"),
            organization_id=ORG,
            environment_id=ENV,
            review_id=review.review_id,
            decision="approved",
            rationale="Approving despite changes-required for this test scenario.",
            correlation_id="cor_3",
        )
    assert excinfo.value.code == "document_knowledge_review_not_passed"

    passed_review = await service.submit_review_decision(
        actor=_subject("subject.reviewer"),
        organization_id=ORG,
        environment_id=ENV,
        draft_id=(await _curated_draft(service, curator="subject.curator-2")).draft_id,
        decision=REVIEW_DECISION_PASSED,
        findings=("No issues found.",),
        correlation_id="cor_4",
    )
    with pytest.raises(DocumentKnowledgeError) as excinfo:
        await service.record_final_approval(
            actor=_subject("subject.reviewer"),
            organization_id=ORG,
            environment_id=ENV,
            review_id=passed_review.review_id,
            decision="approved",
            rationale="An approver must not be the same subject as the reviewer.",
            correlation_id="cor_5",
        )
    assert excinfo.value.code == "document_knowledge_separation_of_duties_required"


@pytest.mark.asyncio
async def test_full_chain_reaches_publication_preparation() -> None:
    service = build_service()
    draft = await _curated_draft(service)
    review = await service.submit_review_decision(
        actor=_subject("subject.reviewer"),
        organization_id=ORG,
        environment_id=ENV,
        draft_id=draft.draft_id,
        decision=REVIEW_DECISION_PASSED,
        findings=("No issues found.",),
        correlation_id="cor_2",
    )
    approval = await service.record_final_approval(
        actor=_subject("subject.approver"),
        organization_id=ORG,
        environment_id=ENV,
        review_id=review.review_id,
        decision="approved",
        rationale="Content is accurate and ready for publication preparation.",
        correlation_id="cor_3",
    )
    preparation = await service.prepare_publication(
        actor=_subject("subject.publisher"),
        organization_id=ORG,
        environment_id=ENV,
        approval_id=approval.approval_id,
        chunking_profile_digest="a" * 64,
        correlation_id="cor_4",
    )

    assert preparation.draft_id == draft.draft_id
    assert preparation.protected_material_digest == draft.protected_material_digest
    assert preparation.knowledge_item_id == draft.knowledge_item_id
