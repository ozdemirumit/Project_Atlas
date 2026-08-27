from __future__ import annotations

from collections.abc import Callable, Sequence

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from atlas.core.persistence.models import DocumentKnowledgeVectorModel
from atlas.modules.knowledge.domain.document_retrieval import (
    DocumentKnowledgeSearchResult,
    DocumentKnowledgeVectorRecord,
)


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
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=[DocumentKnowledgeVectorModel.chunk_id],
                    set_={
                        "content_digest": record.content_digest,
                        "model_profile_id": record.model_profile_id,
                        "embedding": list(record.embedding),
                        "created_at": record.created_at,
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
    ) -> list[DocumentKnowledgeSearchResult]:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        vector = list(query_vector)
        distance = DocumentKnowledgeVectorModel.embedding.cosine_distance(vector)
        stmt = (
            select(DocumentKnowledgeVectorModel, distance.label("distance"))
            .where(
                DocumentKnowledgeVectorModel.organization_id == organization_id,
                DocumentKnowledgeVectorModel.environment_id == environment_id,
            )
            .order_by(distance)
            .limit(top_k)
        )
        async with self._sessions() as session:
            rows = (await session.execute(stmt)).all()
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

    async def close(self) -> None:
        await self._engine.dispose()
