from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from atlas.core.classification import DataClassification
from atlas.modules.knowledge.domain.document_retrieval import (
    DocumentKnowledgeSearchResult,
    DocumentKnowledgeVectorRecord,
    reciprocal_rank_fusion,
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
        max_classification: DataClassification,
        lexical_query: frozenset[str] = frozenset(),
    ) -> list[DocumentKnowledgeSearchResult]:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        query = np.asarray(query_vector, dtype=np.float64)
        query_norm = float(np.linalg.norm(query))
        vector_scored: list[tuple[float, DocumentKnowledgeVectorRecord]] = []
        for (org, env, _chunk_id), record in self._records.items():
            if org != organization_id or env != environment_id:
                continue
            try:
                classification = DataClassification(
                    record.classification.removeprefix("classification.")
                )
            except ValueError:
                continue
            if not max_classification.permits(classification):
                continue
            vector = np.asarray(record.embedding, dtype=np.float64)
            denom = query_norm * float(np.linalg.norm(vector))
            score = float(np.dot(query, vector) / denom) if denom > 0 else 0.0
            vector_scored.append((score, record))
        vector_scored.sort(key=lambda item: item[0], reverse=True)

        if not lexical_query:
            # Original vector-only behavior, unchanged: no lexical query means no
            # hybridization, so pre-hybrid-retrieval callers see identical results.
            return [
                DocumentKnowledgeSearchResult(
                    chunk_id=record.chunk_id,
                    knowledge_item_id=record.knowledge_item_id,
                    content_digest=record.content_digest,
                    score=score,
                    excerpt="",
                )
                for score, record in vector_scored[:top_k]
            ]

        # Real token-overlap lexical scoring: the count of tokens shared between the
        # query's token set and each chunk's token set. A simple, dependency-free
        # TF-style relevance signal -- appropriately simpler than the Postgres
        # ts_rank_cd path, since this adapter's whole purpose is a reference
        # implementation with no external dependencies. Drawn only from records
        # that already passed the classification-ceiling filter above, so lexical
        # matches are gated identically to vector matches.
        lexical_scored = [
            (len(lexical_query & record.lexical_tokens), record)
            for _score, record in vector_scored
            if lexical_query & record.lexical_tokens
        ]
        lexical_scored.sort(key=lambda item: item[0], reverse=True)

        vector_ranking = [record.chunk_id for _score, record in vector_scored]
        lexical_ranking = [record.chunk_id for _overlap, record in lexical_scored]
        fused_scores = reciprocal_rank_fusion([vector_ranking, lexical_ranking])

        records_by_id = {record.chunk_id: record for _score, record in vector_scored}
        fused_order = sorted(
            fused_scores, key=lambda chunk_id: fused_scores[chunk_id], reverse=True
        )
        return [
            DocumentKnowledgeSearchResult(
                chunk_id=chunk_id,
                knowledge_item_id=records_by_id[chunk_id].knowledge_item_id,
                content_digest=records_by_id[chunk_id].content_digest,
                score=fused_scores[chunk_id],
                excerpt="",
            )
            for chunk_id in fused_order[:top_k]
        ]
