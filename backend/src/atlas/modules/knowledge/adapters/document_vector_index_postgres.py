from __future__ import annotations

from collections.abc import Callable, Sequence

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from atlas.core.classification import DataClassification
from atlas.core.persistence.models import DocumentKnowledgeVectorModel
from atlas.modules.knowledge.domain.document_retrieval import (
    DocumentKnowledgeSearchResult,
    DocumentKnowledgeVectorRecord,
    reciprocal_rank_fusion,
)

# Candidate pool fetched independently for each ranking before fusion. Must be
# larger than top_k so a chunk that ranks outside the top_k on one signal but
# well inside it on the other still has a chance to be fused in.
_CANDIDATE_POOL_MULTIPLIER = 5
_MINIMUM_CANDIDATE_POOL = 50


class PgVectorDocumentVectorIndex:
    """Real pgvector-backed vector store. Requires the `vector` PostgreSQL extension
    (migration 20260827_0169) — not available on every host; see ADR-183."""

    def __init__(
        self,
        *,
        engine: AsyncEngine,
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self._engine = engine
        self._sessions = session_factory or async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PgVectorDocumentVectorIndex:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True))

    async def upsert(self, records: Sequence[DocumentKnowledgeVectorRecord]) -> None:
        if not records:
            return
        async with self._sessions() as session:
            for record in records:
                # Derived server-side from the same governance-safe token set as the
                # in-memory adapter uses directly -- never from raw chunk text, which
                # never reaches this adapter. NULL (no lexical contribution) when a
                # record carries no tokens, e.g. records indexed before hybrid
                # retrieval existed.
                lexical_text = " ".join(sorted(record.lexical_tokens))
                lexical_vector = func.to_tsvector("english", lexical_text) if lexical_text else None
                stmt = insert(DocumentKnowledgeVectorModel).values(
                    chunk_id=record.chunk_id,
                    knowledge_item_id=record.knowledge_item_id,
                    organization_id=record.organization_id,
                    environment_id=record.environment_id,
                    classification=record.classification,
                    content_digest=record.content_digest,
                    model_profile_id=record.model_profile_id,
                    embedding=list(record.embedding),
                    created_at=record.created_at,
                    lexical_search_vector=lexical_vector,
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=[DocumentKnowledgeVectorModel.chunk_id],
                    set_={
                        "content_digest": record.content_digest,
                        "model_profile_id": record.model_profile_id,
                        "embedding": list(record.embedding),
                        "created_at": record.created_at,
                        "lexical_search_vector": lexical_vector,
                    },
                )
                await session.execute(stmt)
            await session.commit()

    async def search(
        self,
        *,
        query_vector: Sequence[float],
        organization_id: str,
        environment_id: str,
        top_k: int,
        max_classification: DataClassification,
        lexical_query: frozenset[str] = frozenset(),
    ) -> list[DocumentKnowledgeSearchResult]:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        vector = list(query_vector)
        distance = DocumentKnowledgeVectorModel.embedding.cosine_distance(vector)
        allowed_classifications = [
            f"classification.{member.value}"
            for member in DataClassification
            if max_classification.permits(member)
        ]
        scope_filters = (
            DocumentKnowledgeVectorModel.organization_id == organization_id,
            DocumentKnowledgeVectorModel.environment_id == environment_id,
            DocumentKnowledgeVectorModel.classification.in_(allowed_classifications),
        )
        vector_stmt = (
            select(DocumentKnowledgeVectorModel, distance.label("distance"))
            .where(*scope_filters)
            .order_by(distance)
            .limit(top_k)
        )

        if not lexical_query:
            # Original vector-only behavior, unchanged: no lexical query means no
            # hybridization, so pre-hybrid-retrieval callers see identical results.
            async with self._sessions() as session:
                rows = (await session.execute(vector_stmt)).all()
            return [
                DocumentKnowledgeSearchResult(
                    chunk_id=row.DocumentKnowledgeVectorModel.chunk_id,
                    knowledge_item_id=row.DocumentKnowledgeVectorModel.knowledge_item_id,
                    content_digest=row.DocumentKnowledgeVectorModel.content_digest,
                    score=1.0 - float(row.distance),
                    excerpt="",
                )
                for row in rows
            ]

        candidate_pool = max(top_k * _CANDIDATE_POOL_MULTIPLIER, _MINIMUM_CANDIDATE_POOL)
        vector_stmt = vector_stmt.limit(candidate_pool)

        # plainto_tsquery does its own stopword/stemming normalization against the
        # same 'english' configuration used to build lexical_search_vector at
        # upsert time, so joining the already-tokenized query with spaces (order is
        # irrelevant -- plainto_tsquery ANDs lexemes together) reproduces the same
        # matching as querying with the raw query text would.
        tsquery = func.plainto_tsquery("english", " ".join(sorted(lexical_query)))
        lexical_rank = func.ts_rank_cd(DocumentKnowledgeVectorModel.lexical_search_vector, tsquery)
        lexical_stmt = (
            select(DocumentKnowledgeVectorModel, lexical_rank.label("rank"))
            .where(
                *scope_filters,
                DocumentKnowledgeVectorModel.lexical_search_vector.isnot(None),
                DocumentKnowledgeVectorModel.lexical_search_vector.op("@@")(tsquery),
            )
            .order_by(lexical_rank.desc())
            .limit(candidate_pool)
        )

        async with self._sessions() as session:
            vector_rows = (await session.execute(vector_stmt)).all()
            lexical_rows = (await session.execute(lexical_stmt)).all()

        metadata: dict[str, DocumentKnowledgeVectorModel] = {
            row.DocumentKnowledgeVectorModel.chunk_id: row.DocumentKnowledgeVectorModel
            for row in (*vector_rows, *lexical_rows)
        }
        vector_ranking = [row.DocumentKnowledgeVectorModel.chunk_id for row in vector_rows]
        lexical_ranking = [row.DocumentKnowledgeVectorModel.chunk_id for row in lexical_rows]
        fused_scores = reciprocal_rank_fusion([vector_ranking, lexical_ranking])
        fused_order = sorted(
            fused_scores, key=lambda chunk_id: fused_scores[chunk_id], reverse=True
        )
        return [
            DocumentKnowledgeSearchResult(
                chunk_id=chunk_id,
                knowledge_item_id=metadata[chunk_id].knowledge_item_id,
                content_digest=metadata[chunk_id].content_digest,
                score=fused_scores[chunk_id],
                excerpt="",
            )
            for chunk_id in fused_order[:top_k]
        ]

    async def close(self) -> None:
        await self._engine.dispose()
