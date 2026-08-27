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
from atlas.modules.knowledge.adapters.document_chunking import ParagraphBoundedChunker
from atlas.modules.knowledge.adapters.document_embedding_fastembed import (
    VECTOR_DIMENSION,
    FastEmbedDocumentEmbedder,
)
from atlas.modules.knowledge.adapters.document_knowledge_memory import (
    InMemoryDocumentKnowledgeRepository,
)
from atlas.modules.knowledge.adapters.document_vector_index_memory import (
    InMemoryDocumentVectorIndex,
)
from atlas.modules.knowledge.application.document_knowledge import DocumentKnowledgeService
from atlas.modules.knowledge.application.document_retrieval import (
    DocumentKnowledgeRetrievalService,
)
from atlas.modules.knowledge.application.document_retrieval_ports import (
    DocumentKnowledgeRetrievalError,
)
from atlas.modules.knowledge.domain.document_knowledge import (
    REVIEW_DECISION_PASSED,
    DocumentKnowledgePublicationPreparation,
)

ORG = "organization.development"
ENV = "environment.test"
NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)

STORAGE_DOC = """# Storage Controller Runbook

When a storage controller reports a warning status, engineers should first confirm
the condition persists across two consecutive read-only health checks before taking
any action.

# Escalation Procedure

If the warning persists, open a change record and notify the on-call storage
engineer. Do not restart the controller without an approved change window.
"""

UNRELATED_DOC = """# Backup Policy

Backups run nightly at 02:00 local time. Retention is 30 days for daily backups
and 12 months for monthly backups.
"""


class AllowAllAuthorizer:
    async def authorize(self, **_kwargs: object) -> None:
        return None


class _NullAuditSink:
    async def record(self, event: object) -> None:
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


@pytest.fixture(scope="module")
def embedder() -> FastEmbedDocumentEmbedder:
    return FastEmbedDocumentEmbedder()


def test_paragraph_chunker_never_produces_empty_chunks() -> None:
    chunker = ParagraphBoundedChunker(maximum_chunk_characters=80)
    chunks = chunker.chunk(STORAGE_DOC)
    assert chunks
    assert all(chunk.strip() for chunk in chunks)
    assert all(len(chunk) <= 80 for chunk in chunks)


def test_paragraph_chunker_rejects_non_positive_bound() -> None:
    with pytest.raises(ValueError, match="positive"):
        ParagraphBoundedChunker(maximum_chunk_characters=0)


def test_fastembed_produces_a_real_384_dimension_vector(
    embedder: FastEmbedDocumentEmbedder,
) -> None:
    vectors = embedder.embed_passages(["Restart the read-only diagnostic collector."])
    assert len(vectors) == 1
    assert len(vectors[0]) == VECTOR_DIMENSION == 384
    assert any(value != 0.0 for value in vectors[0])


def test_fastembed_query_and_passage_embeddings_are_semantically_close(
    embedder: FastEmbedDocumentEmbedder,
) -> None:
    import math

    passage = embedder.embed_passages(["The storage controller reports a warning status."])[0]
    close_query = embedder.embed_query("controller warning")
    far_query = embedder.embed_query("nightly backup retention policy")

    def cosine(a: tuple[float, ...], b: tuple[float, ...]) -> float:
        dot = sum(x * y for x, y in zip(a, b, strict=True))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        return dot / (norm_a * norm_b)

    assert cosine(passage, close_query) > cosine(passage, far_query)


@pytest.mark.asyncio
async def test_in_memory_vector_index_ranks_by_cosine_similarity() -> None:
    from atlas.modules.knowledge.domain.document_retrieval import DocumentKnowledgeVectorRecord

    index = InMemoryDocumentVectorIndex()
    await index.upsert(
        [
            DocumentKnowledgeVectorRecord(
                chunk_id="document-knowledge-chunk.close",
                knowledge_item_id="knowledge-item.a",
                organization_id=ORG,
                environment_id=ENV,
                classification="classification.internal",
                content_digest="a" * 64,
                model_profile_id="fastembed.bge-small-en-v1.5",
                embedding=(1.0, 0.0, 0.0),
                created_at=NOW,
            ),
            DocumentKnowledgeVectorRecord(
                chunk_id="document-knowledge-chunk.far",
                knowledge_item_id="knowledge-item.a",
                organization_id=ORG,
                environment_id=ENV,
                classification="classification.internal",
                content_digest="b" * 64,
                model_profile_id="fastembed.bge-small-en-v1.5",
                embedding=(0.0, 1.0, 0.0),
                created_at=NOW,
            ),
        ]
    )

    results = await index.search(
        query_vector=(1.0, 0.01, 0.0), organization_id=ORG, environment_id=ENV, top_k=2
    )

    assert [item.chunk_id for item in results] == [
        "document-knowledge-chunk.close",
        "document-knowledge-chunk.far",
    ]
    assert results[0].score > results[1].score


@pytest.mark.asyncio
async def test_in_memory_vector_index_isolates_by_scope() -> None:
    from atlas.modules.knowledge.domain.document_retrieval import DocumentKnowledgeVectorRecord

    index = InMemoryDocumentVectorIndex()
    await index.upsert(
        [
            DocumentKnowledgeVectorRecord(
                chunk_id="document-knowledge-chunk.other-org",
                knowledge_item_id="knowledge-item.a",
                organization_id="organization.other",
                environment_id=ENV,
                classification="classification.internal",
                content_digest="a" * 64,
                model_profile_id="fastembed.bge-small-en-v1.5",
                embedding=(1.0, 0.0, 0.0),
                created_at=NOW,
            )
        ]
    )

    results = await index.search(
        query_vector=(1.0, 0.0, 0.0), organization_id=ORG, environment_id=ENV, top_k=5
    )
    assert results == []


def build_retrieval_service(
    embedder: FastEmbedDocumentEmbedder,
) -> tuple[DocumentKnowledgeService, DocumentKnowledgeRetrievalService]:
    repository = InMemoryDocumentKnowledgeRepository()
    protected_content = InMemoryProtectedContentStore()
    knowledge_service = DocumentKnowledgeService(
        repository=repository,
        protected_content=protected_content,
        permission_authorizer=AllowAllAuthorizer(),
        audit_sink=_NullAuditSink(),
        subject_salt="test-salt",
        clock=lambda: NOW,
    )
    retrieval_service = DocumentKnowledgeRetrievalService(
        repository=repository,
        protected_content=protected_content,
        chunker=ParagraphBoundedChunker(maximum_chunk_characters=200),
        embedder=embedder,
        vector_index=InMemoryDocumentVectorIndex(),
        permission_authorizer=AllowAllAuthorizer(),
        audit_sink=_NullAuditSink(),
        clock=lambda: NOW,
    )
    return knowledge_service, retrieval_service


async def _approved_preparation(
    knowledge_service: DocumentKnowledgeService, *, content: bytes
) -> DocumentKnowledgePublicationPreparation:
    draft = await knowledge_service.curate_draft(
        actor=_subject("subject.curator"),
        organization_id=ORG,
        environment_id=ENV,
        content=content,
        title="Storage Controller Runbook",
        draft_domain="domain.vendor",
        content_type="text/markdown",
        classification="classification.internal",
        access_policy_id="access-policy.default",
        retention_policy_id="retention-policy.default",
        purpose="A runbook used to validate the real retrieval pipeline end to end.",
        correlation_id="cor_1",
    )
    review = await knowledge_service.submit_review_decision(
        actor=_subject("subject.reviewer"),
        organization_id=ORG,
        environment_id=ENV,
        draft_id=draft.draft_id,
        decision=REVIEW_DECISION_PASSED,
        findings=("No issues found.",),
        correlation_id="cor_2",
    )
    approval = await knowledge_service.record_final_approval(
        actor=_subject("subject.approver"),
        organization_id=ORG,
        environment_id=ENV,
        review_id=review.review_id,
        decision="approved",
        rationale="Content is accurate and ready for indexing.",
        correlation_id="cor_3",
    )
    return await knowledge_service.prepare_publication(
        actor=_subject("subject.publisher"),
        organization_id=ORG,
        environment_id=ENV,
        approval_id=approval.approval_id,
        chunking_profile_digest="a" * 64,
        correlation_id="cor_4",
    )


@pytest.mark.asyncio
async def test_full_pipeline_indexes_and_retrieves_the_real_document(
    embedder: FastEmbedDocumentEmbedder,
) -> None:
    knowledge_service, retrieval_service = build_retrieval_service(embedder)
    preparation = await _approved_preparation(
        knowledge_service, content=STORAGE_DOC.encode("utf-8")
    )

    chunk_count = await retrieval_service.index_document(
        actor=_subject("subject.indexer"),
        organization_id=ORG,
        environment_id=ENV,
        preparation_id=preparation.preparation_id,
        correlation_id="cor_5",
    )
    assert chunk_count >= 1

    results = await retrieval_service.retrieve(
        actor=_subject("subject.searcher"),
        organization_id=ORG,
        environment_id=ENV,
        query="storage controller warning status escalation",
        top_k=3,
        correlation_id="cor_6",
    )

    assert results
    assert "controller" in results[0].excerpt.lower() or "escalation" in results[0].excerpt.lower()
    assert results[0].knowledge_item_id == preparation.knowledge_item_id


@pytest.mark.asyncio
async def test_retrieval_ranks_the_relevant_document_above_the_unrelated_one(
    embedder: FastEmbedDocumentEmbedder,
) -> None:
    knowledge_service, retrieval_service = build_retrieval_service(embedder)
    storage_preparation = await _approved_preparation(
        knowledge_service, content=STORAGE_DOC.encode("utf-8")
    )
    backup_draft = await knowledge_service.curate_draft(
        actor=_subject("subject.curator-2"),
        organization_id=ORG,
        environment_id=ENV,
        content=UNRELATED_DOC.encode("utf-8"),
        title="Backup Policy",
        draft_domain="domain.vendor",
        content_type="text/markdown",
        classification="classification.internal",
        access_policy_id="access-policy.default",
        retention_policy_id="retention-policy.default",
        purpose="An unrelated document used to prove ranking discriminates by topic.",
        correlation_id="cor_b1",
    )
    backup_review = await knowledge_service.submit_review_decision(
        actor=_subject("subject.reviewer"),
        organization_id=ORG,
        environment_id=ENV,
        draft_id=backup_draft.draft_id,
        decision=REVIEW_DECISION_PASSED,
        findings=("No issues found.",),
        correlation_id="cor_b2",
    )
    backup_approval = await knowledge_service.record_final_approval(
        actor=_subject("subject.approver"),
        organization_id=ORG,
        environment_id=ENV,
        review_id=backup_review.review_id,
        decision="approved",
        rationale="Content is accurate and ready for indexing.",
        correlation_id="cor_b3",
    )
    backup_preparation = await knowledge_service.prepare_publication(
        actor=_subject("subject.publisher"),
        organization_id=ORG,
        environment_id=ENV,
        approval_id=backup_approval.approval_id,
        chunking_profile_digest="a" * 64,
        correlation_id="cor_b4",
    )

    await retrieval_service.index_document(
        actor=_subject("subject.indexer"),
        organization_id=ORG,
        environment_id=ENV,
        preparation_id=storage_preparation.preparation_id,
        correlation_id="cor_c1",
    )
    await retrieval_service.index_document(
        actor=_subject("subject.indexer"),
        organization_id=ORG,
        environment_id=ENV,
        preparation_id=backup_preparation.preparation_id,
        correlation_id="cor_c2",
    )

    results = await retrieval_service.retrieve(
        actor=_subject("subject.searcher"),
        organization_id=ORG,
        environment_id=ENV,
        query="controller warning escalation change window",
        top_k=1,
        correlation_id="cor_c3",
    )

    assert results
    assert results[0].knowledge_item_id == storage_preparation.knowledge_item_id


@pytest.mark.asyncio
async def test_index_document_rejects_unknown_preparation(
    embedder: FastEmbedDocumentEmbedder,
) -> None:
    _, retrieval_service = build_retrieval_service(embedder)

    with pytest.raises(DocumentKnowledgeRetrievalError) as excinfo:
        await retrieval_service.index_document(
            actor=_subject("subject.indexer"),
            organization_id=ORG,
            environment_id=ENV,
            preparation_id="document-knowledge-preparation.does-not-exist",
            correlation_id="cor_1",
        )
    assert excinfo.value.code == "document_knowledge_preparation_not_found"


@pytest.mark.asyncio
async def test_retrieve_rejects_too_short_query(embedder: FastEmbedDocumentEmbedder) -> None:
    _, retrieval_service = build_retrieval_service(embedder)

    with pytest.raises(DocumentKnowledgeRetrievalError) as excinfo:
        await retrieval_service.retrieve(
            actor=_subject("subject.searcher"),
            organization_id=ORG,
            environment_id=ENV,
            query="ab",
            top_k=3,
            correlation_id="cor_1",
        )
    assert excinfo.value.code == "document_knowledge_query_invalid"
