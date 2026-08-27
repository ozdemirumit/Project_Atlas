from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from atlas.modules.knowledge.domain.document_retrieval import (
    DocumentKnowledgeSearchResult,
    DocumentKnowledgeVectorRecord,
)


class InMemoryDocumentVectorIndex:
    """Real cosine-similarity search, process-local. Not for production (no
    durability, no cross-process visibility) but not synthetic either: the
    embeddings and the distance computation are both genuinely real."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str], DocumentKnowledgeVectorRecord] = {}

    async def upsert(self, records: Sequence[DocumentKnowledgeVectorRecord]) -> None:
        for record in records:
            self._records[(record.organization_id, record.environment_id, record.chunk_id)] = record

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
        query = np.asarray(query_vector, dtype=np.float64)
        query_norm = float(np.linalg.norm(query))
        scored: list[tuple[float, DocumentKnowledgeVectorRecord]] = []
        for (org, env, _chunk_id), record in self._records.items():
            if org != organization_id or env != environment_id:
                continue
            vector = np.asarray(record.embedding, dtype=np.float64)
            denom = query_norm * float(np.linalg.norm(vector))
            score = float(np.dot(query, vector) / denom) if denom > 0 else 0.0
            scored.append((score, record))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [
            DocumentKnowledgeSearchResult(
                chunk_id=record.chunk_id,
                knowledge_item_id=record.knowledge_item_id,
                content_digest=record.content_digest,
                score=score,
                excerpt="",
            )
            for score, record in scored[:top_k]
        ]
