from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.classification import DataClassification
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

    async def classification_ceiling(self, **_kwargs: object) -> DataClassification:
        return DataClassification.RESTRICTED


class _CeilingAuthorizer:
    """Same as AllowAllAuthorizer but with a configurable ceiling, to prove
    classification-ceiling filtering (pass 29) applies to lexical matches exactly
    as it already does to vector matches."""

    def __init__(self, ceiling: DataClassification) -> None:
        self._ceiling = ceiling

    async def authorize(self, **_kwargs: object) -> None:
        return None

    async def classification_ceiling(self, **_kwargs: object) -> DataClassification:
        return self._ceiling


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
        query_vector=(1.0, 0.01, 0.0),
        organization_id=ORG,
        environment_id=ENV,
        top_k=2,
        max_classification=DataClassification.INTERNAL,
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
        query_vector=(1.0, 0.0, 0.0),
        organization_id=ORG,
        environment_id=ENV,
        top_k=5,
        max_classification=DataClassification.INTERNAL,
    )
    assert results == []


@pytest.mark.asyncio
async def test_in_memory_vector_index_excludes_restricted_records_below_ceiling() -> None:
    from atlas.modules.knowledge.domain.document_retrieval import DocumentKnowledgeVectorRecord

    index = InMemoryDocumentVectorIndex()
    await index.upsert(
        [
            DocumentKnowledgeVectorRecord(
                chunk_id="document-knowledge-chunk.internal",
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
                chunk_id="document-knowledge-chunk.restricted",
                knowledge_item_id="knowledge-item.a",
                organization_id=ORG,
                environment_id=ENV,
                classification="classification.restricted",
                content_digest="b" * 64,
                model_profile_id="fastembed.bge-small-en-v1.5",
                embedding=(1.0, 0.0, 0.0),
                created_at=NOW,
            ),
        ]
    )

    internal_ceiling_results = await index.search(
        query_vector=(1.0, 0.0, 0.0),
        organization_id=ORG,
        environment_id=ENV,
        top_k=5,
        max_classification=DataClassification.INTERNAL,
    )
    assert [item.chunk_id for item in internal_ceiling_results] == [
        "document-knowledge-chunk.internal"
    ]

    restricted_ceiling_results = await index.search(
        query_vector=(1.0, 0.0, 0.0),
        organization_id=ORG,
        environment_id=ENV,
        top_k=5,
        max_classification=DataClassification.RESTRICTED,
    )
    assert {item.chunk_id for item in restricted_ceiling_results} == {
        "document-knowledge-chunk.internal",
        "document-knowledge-chunk.restricted",
    }


@pytest.mark.asyncio
async def test_in_memory_vector_index_excludes_unparseable_classification() -> None:
    from atlas.modules.knowledge.domain.document_retrieval import DocumentKnowledgeVectorRecord

    index = InMemoryDocumentVectorIndex()
    await index.upsert(
        [
            DocumentKnowledgeVectorRecord(
                chunk_id="document-knowledge-chunk.unparseable",
                knowledge_item_id="knowledge-item.a",
                organization_id=ORG,
                environment_id=ENV,
                classification="classification.not-a-real-level",
                content_digest="a" * 64,
                model_profile_id="fastembed.bge-small-en-v1.5",
                embedding=(1.0, 0.0, 0.0),
                created_at=NOW,
            )
        ]
    )

    results = await index.search(
        query_vector=(1.0, 0.0, 0.0),
        organization_id=ORG,
        environment_id=ENV,
        top_k=5,
        max_classification=DataClassification.RESTRICTED,
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


def build_retrieval_service_with_ceiling(
    embedder: FastEmbedDocumentEmbedder, ceiling: DataClassification
) -> tuple[DocumentKnowledgeService, DocumentKnowledgeRetrievalService]:
    """Like build_retrieval_service, but the retrieval service's authorizer enforces
    a configurable classification ceiling instead of always permitting everything."""
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
        permission_authorizer=_CeilingAuthorizer(ceiling),
        audit_sink=_NullAuditSink(),
        clock=lambda: NOW,
    )
    return knowledge_service, retrieval_service


async def _approved_preparation(
    knowledge_service: DocumentKnowledgeService,
    *,
    content: bytes,
    classification: str = "classification.internal",
) -> DocumentKnowledgePublicationPreparation:
    draft = await knowledge_service.curate_draft(
        actor=_subject("subject.curator"),
        organization_id=ORG,
        environment_id=ENV,
        content=content,
        title="Storage Controller Runbook",
        draft_domain="domain.vendor",
        content_type="text/markdown",
        classification=classification,
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


# --- Hybrid (vector + lexical) retrieval -----------------------------------------


def test_tokenize_for_lexical_search_lowercases_dedupes_and_discards_order() -> None:
    from atlas.modules.knowledge.domain.document_retrieval import tokenize_for_lexical_search

    tokens = tokenize_for_lexical_search(
        "Warning: Warning! The Controller reported controller status."
    )

    assert tokens == frozenset({"warning", "the", "controller", "reported", "status"})


def test_reciprocal_rank_fusion_combines_signals_from_both_rankings() -> None:
    from atlas.modules.knowledge.domain.document_retrieval import reciprocal_rank_fusion

    vector_ranking = ["vector-best", "both", "vector-only-tail"]
    lexical_ranking = ["lexical-best", "both", "lexical-only-tail"]

    fused = reciprocal_rank_fusion([vector_ranking, lexical_ranking])

    # "both" is only second place on each individual signal, yet its fused score
    # sums contributions from both rankings -- so it outranks items that are
    # first place on exactly one signal alone. That is only possible if fusion
    # genuinely combines both rankings rather than just adopting one of them.
    assert fused["both"] > fused["vector-best"]
    assert fused["both"] > fused["lexical-best"]


def test_reciprocal_rank_fusion_never_errors_when_a_ranking_omits_an_item() -> None:
    from atlas.modules.knowledge.domain.document_retrieval import reciprocal_rank_fusion

    fused = reciprocal_rank_fusion([["only-in-vector"], []])

    assert fused == pytest.approx({"only-in-vector": 1.0 / 61.0})


@pytest.mark.asyncio
async def test_in_memory_vector_index_lexical_match_surfaces_document_weak_on_vector_alone() -> (
    None
):
    from atlas.modules.knowledge.domain.document_retrieval import DocumentKnowledgeVectorRecord

    index = InMemoryDocumentVectorIndex()
    await index.upsert(
        [
            DocumentKnowledgeVectorRecord(
                chunk_id="document-knowledge-chunk.vector-match",
                knowledge_item_id="knowledge-item.vector-match",
                organization_id=ORG,
                environment_id=ENV,
                classification="classification.internal",
                content_digest="a" * 64,
                model_profile_id="fastembed.bge-small-en-v1.5",
                embedding=(1.0, 0.0, 0.0),
                created_at=NOW,
                lexical_tokens=frozenset({"unrelated", "content"}),
            ),
            DocumentKnowledgeVectorRecord(
                chunk_id="document-knowledge-chunk.lexical-match",
                knowledge_item_id="knowledge-item.lexical-match",
                organization_id=ORG,
                environment_id=ENV,
                classification="classification.internal",
                content_digest="b" * 64,
                model_profile_id="fastembed.bge-small-en-v1.5",
                embedding=(0.0, 1.0, 0.0),
                created_at=NOW,
                lexical_tokens=frozenset({"xj9042zq", "firmware", "rollback"}),
            ),
        ]
    )

    # Pure vector similarity ranks "lexical-match" last -- it is orthogonal to the
    # query vector, so a vector-only search of top_k=1 never surfaces it.
    vector_only_results = await index.search(
        query_vector=(1.0, 0.0, 0.0),
        organization_id=ORG,
        environment_id=ENV,
        top_k=1,
        max_classification=DataClassification.INTERNAL,
    )
    assert [item.chunk_id for item in vector_only_results] == [
        "document-knowledge-chunk.vector-match"
    ]

    # A query matching only the distinctive lexical terms surfaces the same
    # document to the top despite its weak vector similarity -- concrete proof
    # hybrid retrieval is doing real lexical work, not just vector search with
    # unused plumbing.
    hybrid_results = await index.search(
        query_vector=(1.0, 0.0, 0.0),
        organization_id=ORG,
        environment_id=ENV,
        top_k=1,
        max_classification=DataClassification.INTERNAL,
        lexical_query=frozenset({"xj9042zq", "firmware", "rollback"}),
    )
    assert [item.chunk_id for item in hybrid_results] == ["document-knowledge-chunk.lexical-match"]


@pytest.mark.asyncio
async def test_in_memory_vector_index_rrf_fusion_combines_both_rankings() -> None:
    from atlas.modules.knowledge.domain.document_retrieval import DocumentKnowledgeVectorRecord

    index = InMemoryDocumentVectorIndex()
    await index.upsert(
        [
            DocumentKnowledgeVectorRecord(
                chunk_id="document-knowledge-chunk.vector-best",
                knowledge_item_id="knowledge-item.a",
                organization_id=ORG,
                environment_id=ENV,
                classification="classification.internal",
                content_digest="a" * 64,
                model_profile_id="fastembed.bge-small-en-v1.5",
                embedding=(1.0, 0.0, 0.0),
                created_at=NOW,
                lexical_tokens=frozenset(),
            ),
            DocumentKnowledgeVectorRecord(
                chunk_id="document-knowledge-chunk.balanced",
                knowledge_item_id="knowledge-item.b",
                organization_id=ORG,
                environment_id=ENV,
                classification="classification.internal",
                content_digest="b" * 64,
                model_profile_id="fastembed.bge-small-en-v1.5",
                embedding=(0.8, 0.2, 0.0),
                created_at=NOW,
                lexical_tokens=frozenset({"alpha", "beta"}),
            ),
            DocumentKnowledgeVectorRecord(
                chunk_id="document-knowledge-chunk.lexical-best",
                knowledge_item_id="knowledge-item.c",
                organization_id=ORG,
                environment_id=ENV,
                classification="classification.internal",
                content_digest="c" * 64,
                model_profile_id="fastembed.bge-small-en-v1.5",
                embedding=(0.0, 0.0, 1.0),
                created_at=NOW,
                lexical_tokens=frozenset({"alpha", "beta", "gamma"}),
            ),
        ]
    )

    results = await index.search(
        query_vector=(1.0, 0.0, 0.0),
        organization_id=ORG,
        environment_id=ENV,
        top_k=3,
        max_classification=DataClassification.INTERNAL,
        lexical_query=frozenset({"alpha", "beta", "gamma"}),
    )

    # vector-only ranking would be [vector-best, balanced, lexical-best].
    # lexical-only ranking would be [lexical-best, balanced] ("vector-best" has no
    # lexical tokens at all). The fused ranking below matches neither: "balanced"
    # (second place on both signals) outranks "vector-best" (first place on
    # vector alone, absent from lexical entirely) -- proof RRF genuinely combines
    # both rankings' scores rather than reflecting only one of them.
    assert [item.chunk_id for item in results] == [
        "document-knowledge-chunk.lexical-best",
        "document-knowledge-chunk.balanced",
        "document-knowledge-chunk.vector-best",
    ]


@pytest.mark.asyncio
async def test_in_memory_vector_index_lexical_matches_still_respect_classification_ceiling() -> (
    None
):
    from atlas.modules.knowledge.domain.document_retrieval import DocumentKnowledgeVectorRecord

    index = InMemoryDocumentVectorIndex()
    await index.upsert(
        [
            DocumentKnowledgeVectorRecord(
                chunk_id="document-knowledge-chunk.internal-lexical-match",
                knowledge_item_id="knowledge-item.a",
                organization_id=ORG,
                environment_id=ENV,
                classification="classification.internal",
                content_digest="a" * 64,
                model_profile_id="fastembed.bge-small-en-v1.5",
                embedding=(0.0, 1.0, 0.0),
                created_at=NOW,
                lexical_tokens=frozenset({"quarantine", "override"}),
            ),
            DocumentKnowledgeVectorRecord(
                chunk_id="document-knowledge-chunk.restricted-lexical-match",
                knowledge_item_id="knowledge-item.b",
                organization_id=ORG,
                environment_id=ENV,
                classification="classification.restricted",
                content_digest="b" * 64,
                model_profile_id="fastembed.bge-small-en-v1.5",
                embedding=(0.0, 1.0, 0.0),
                created_at=NOW,
                lexical_tokens=frozenset({"quarantine", "override"}),
            ),
        ]
    )

    # Both chunks are identical in embedding and lexical tokens -- the only
    # difference is classification -- so any exclusion is attributable purely to
    # the classification ceiling, exactly like the pre-existing vector-only test
    # of this behavior above.
    internal_ceiling_results = await index.search(
        query_vector=(0.0, 1.0, 0.0),
        organization_id=ORG,
        environment_id=ENV,
        top_k=5,
        max_classification=DataClassification.INTERNAL,
        lexical_query=frozenset({"quarantine", "override"}),
    )
    assert [item.chunk_id for item in internal_ceiling_results] == [
        "document-knowledge-chunk.internal-lexical-match"
    ]

    restricted_ceiling_results = await index.search(
        query_vector=(0.0, 1.0, 0.0),
        organization_id=ORG,
        environment_id=ENV,
        top_k=5,
        max_classification=DataClassification.RESTRICTED,
        lexical_query=frozenset({"quarantine", "override"}),
    )
    assert {item.chunk_id for item in restricted_ceiling_results} == {
        "document-knowledge-chunk.internal-lexical-match",
        "document-knowledge-chunk.restricted-lexical-match",
    }


@pytest.mark.asyncio
async def test_in_memory_vector_index_search_without_lexical_query_is_unchanged() -> None:
    """Backward compatibility: a caller that never passes lexical_query (as every
    caller did before hybrid retrieval existed) gets the exact original
    vector-only behavior and score, not an RRF-fused score."""
    from atlas.modules.knowledge.domain.document_retrieval import DocumentKnowledgeVectorRecord

    index = InMemoryDocumentVectorIndex()
    await index.upsert(
        [
            DocumentKnowledgeVectorRecord(
                chunk_id="document-knowledge-chunk.no-lexical-tokens",
                knowledge_item_id="knowledge-item.a",
                organization_id=ORG,
                environment_id=ENV,
                classification="classification.internal",
                content_digest="a" * 64,
                model_profile_id="fastembed.bge-small-en-v1.5",
                embedding=(1.0, 0.0, 0.0),
                created_at=NOW,
                # lexical_tokens omitted -- defaults to frozenset(), matching records
                # indexed before hybrid retrieval existed.
            ),
        ]
    )

    results = await index.search(
        query_vector=(1.0, 0.0, 0.0),
        organization_id=ORG,
        environment_id=ENV,
        top_k=1,
        max_classification=DataClassification.INTERNAL,
    )

    assert [item.chunk_id for item in results] == ["document-knowledge-chunk.no-lexical-tokens"]
    assert results[0].score == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_retrieve_classification_ceiling_still_excludes_restricted_lexical_matches(
    embedder: FastEmbedDocumentEmbedder,
) -> None:
    """End-to-end version of the classification-ceiling proof above, through the
    real service: a searcher whose ceiling is below the document's classification
    gets nothing back, even though the query's lexical terms are an exact,
    word-for-word match for the restricted document's real content."""
    knowledge_service, retrieval_service = build_retrieval_service_with_ceiling(
        embedder, DataClassification.INTERNAL
    )
    restricted_preparation = await _approved_preparation(
        knowledge_service,
        content=STORAGE_DOC.encode("utf-8"),
        classification="classification.restricted",
    )
    await retrieval_service.index_document(
        actor=_subject("subject.indexer"),
        organization_id=ORG,
        environment_id=ENV,
        preparation_id=restricted_preparation.preparation_id,
        correlation_id="cor_d1",
    )

    results = await retrieval_service.retrieve(
        actor=_subject("subject.searcher"),
        organization_id=ORG,
        environment_id=ENV,
        query="storage controller warning status escalation",
        top_k=3,
        correlation_id="cor_d2",
    )

    assert results == []
