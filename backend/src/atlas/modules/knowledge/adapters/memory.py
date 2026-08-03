from __future__ import annotations

import re

from atlas.modules.knowledge.domain.models import (
    Citation,
    KnowledgeChunk,
    KnowledgeLifecycle,
    RetrievalHit,
    RetrievalRequest,
    RetrievalResult,
    RetrievalTrace,
)

_TOKEN = re.compile(r"[a-zA-Z0-9_.:-]+")
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "be",
        "how",
        "is",
        "of",
        "or",
        "should",
        "the",
        "to",
        "was",
    }
)


def _tokens(value: str) -> frozenset[str]:
    return frozenset(
        token
        for match in _TOKEN.finditer(value)
        if (token := match.group(0).lower()) not in _STOP_WORDS
    )


class InMemoryKnowledgeRetriever:
    def __init__(
        self,
        *,
        chunks: tuple[KnowledgeChunk, ...],
        index_version: str = "memory-lexical-v1",
        filter_policy_version: str = "knowledge-acl-v1",
    ) -> None:
        if len({chunk.chunk_id for chunk in chunks}) != len(chunks):
            raise ValueError("knowledge chunk identifiers must be unique")
        self._chunks = chunks
        self._index_version = index_version
        self._filter_policy_version = filter_policy_version

    @staticmethod
    def _authorized(chunk: KnowledgeChunk, request: RetrievalRequest) -> bool:
        return (
            chunk.organization_id == request.organization_id
            and chunk.environment_id == request.environment_id
            and chunk.lifecycle is KnowledgeLifecycle.ACTIVE
            and request.classification_ceiling.permits(chunk.classification)
            and not request.principals.isdisjoint(chunk.allowed_principals)
        )

    async def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        # ACL and classification filtering precede all relevance calculations.
        authorized = tuple(chunk for chunk in self._chunks if self._authorized(chunk, request))
        query_tokens = _tokens(request.query)
        ranked: list[tuple[int, KnowledgeChunk, tuple[str, ...]]] = []
        for chunk in authorized:
            content_tokens = _tokens(
                " ".join((chunk.title, chunk.excerpt, chunk.product, *chunk.keywords))
            )
            overlap = query_tokens & content_tokens
            if not overlap:
                continue
            basis = ["lexical_overlap"]
            score = len(overlap) * 10
            if request.query.lower() in chunk.excerpt.lower():
                basis.append("exact_phrase")
                score += 5
            ranked.append((score, chunk, tuple(basis)))
        ranked.sort(key=lambda item: (-item[0], item[1].chunk_id))

        hits: list[RetrievalHit] = []
        for _, chunk, rank_basis in ranked[: request.max_results]:
            # Current authoritative scope is revalidated after ranking.
            if not self._authorized(chunk, request):
                continue
            hits.append(
                RetrievalHit(
                    excerpt=chunk.excerpt,
                    citation=Citation(
                        reference=chunk.citation_reference,
                        item_id=chunk.item_id,
                        item_version=chunk.item_version,
                        chunk_id=chunk.chunk_id,
                        title=chunk.title,
                        source_class=chunk.source_class,
                        source_reference=chunk.source_reference,
                        location=chunk.section_path,
                        content_checksum=chunk.content_checksum,
                        observed_at=chunk.observed_at,
                        classification=chunk.classification,
                    ),
                    product=chunk.product,
                    applicable_versions=chunk.applicable_versions,
                    rank_basis=rank_basis,
                )
            )
        empty_reason = None if hits else "no_authorized_relevant_evidence"
        return RetrievalResult(
            hits=tuple(hits),
            trace=RetrievalTrace(
                query_id=request.query_id,
                index_version=self._index_version,
                authorized_candidate_count=len(authorized),
                returned_count=len(hits),
                filter_policy_version=self._filter_policy_version,
                empty_reason=empty_reason,
            ),
        )
