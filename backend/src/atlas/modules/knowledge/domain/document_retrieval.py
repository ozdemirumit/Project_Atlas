"""Real chunking/embedding/vector-index/retrieval for document-sourced knowledge.

Deliberately separate from the ADR-042-058 Operational-chain RAG pipeline per the
2026-08-27 amendment to ADR-184: this path never touches Operational-chain code.
Chunk text lives only in atlas.core.protected_content, referenced here by digest;
only the embedding vector itself is real, queryable data in this module's own
dedicated vector store (never in ordinary application persistence).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_LEXICAL_TOKEN = re.compile(r"[a-z0-9]+")

# The standard default from Cormack, Clarke & Buettcher, "Reciprocal Rank Fusion
# Outperforms Condorcet and Individual Rank Learning Methods" (SIGIR 2009). The
# paper found k=60 to be a robust, tuning-free default across corpora, which is
# why it is used unchanged here rather than fitted to this corpus.
RECIPROCAL_RANK_FUSION_K = 60


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "document knowledge retrieval identifier")


def tokenize_for_lexical_search(text: str) -> frozenset[str]:
    """Derives a lossy, non-reversible lexical representation of ``text``.

    Lowercases, splits on non-alphanumeric boundaries, and collapses into a set --
    discarding word order, repetition, and case. This is deliberately *not*
    reversible to the original text, which is what makes it safe to persist
    directly alongside the embedding on the governed ``document_knowledge_vectors``
    row: it carries no more information than the classification-tagged metadata
    already stored there. ADR-184 established ``atlas.core.protected_content`` as
    the sole store for real, reversible chunk text -- it predates this function and
    says nothing about lexical search specifically, but its governance principle is
    what this token set is designed to stay inside of: raw chunk text is read once
    during indexing, tokenized into this lossy form, and never persisted anywhere
    new in recoverable form.

    Used identically to derive the lexical representation of an indexed chunk and
    of a search query, so the two sides of lexical matching are always comparable.
    """
    return frozenset(_LEXICAL_TOKEN.findall(text.lower()))


def reciprocal_rank_fusion(
    rankings: Sequence[Sequence[str]], *, k: int = RECIPROCAL_RANK_FUSION_K
) -> dict[str, float]:
    """Fuses independently-ranked id lists (best result first) into one score per id.

    score(d) = sum over each ranking r containing d of 1 / (k + rank_r(d))

    where rank_r(d) is the 1-based position of d within ranking r. An id absent
    from a given ranking simply contributes nothing for that ranking -- it is
    never an error for a ranking to be empty or to omit an id present in another
    ranking. This is Reciprocal Rank Fusion (RRF): a tuning-free way to combine
    rankings from different scoring systems (here: cosine similarity and lexical
    rank) without needing to normalize their scores onto a common scale.
    """
    scores: dict[str, float] = {}
    for ranking in rankings:
        for position, item_id in enumerate(ranking, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + position)
    return scores


@dataclass(frozen=True, slots=True)
class DocumentKnowledgeChunk:
    chunk_id: str
    preparation_id: str
    knowledge_item_id: str
    organization_id: str
    environment_id: str
    classification: str
    chunk_ordinal: int
    content_digest: str
    char_count: int
    created_at: datetime

    def __post_init__(self) -> None:
        _ids(
            self.chunk_id,
            self.preparation_id,
            self.knowledge_item_id,
            self.organization_id,
            self.environment_id,
            self.classification,
        )
        if (
            self.chunk_ordinal < 0
            or self.char_count < 1
            or self.created_at.tzinfo is None
            or _DIGEST.fullmatch(self.content_digest) is None
        ):
            raise ValueError("document knowledge chunk is invalid")


@dataclass(frozen=True, slots=True)
class DocumentKnowledgeVectorRecord:
    """The vector store's own real record. Never copied into ordinary persistence."""

    chunk_id: str
    knowledge_item_id: str
    organization_id: str
    environment_id: str
    classification: str
    content_digest: str
    model_profile_id: str
    embedding: tuple[float, ...]
    created_at: datetime
    lexical_tokens: frozenset[str] = field(default_factory=frozenset)
    """Governance-safe lexical representation of the chunk, from
    ``tokenize_for_lexical_search``. Never the raw chunk text -- see that
    function's docstring. Empty for records indexed before hybrid retrieval
    existed; such records simply do not participate in lexical ranking."""

    def __post_init__(self) -> None:
        _ids(
            self.chunk_id,
            self.knowledge_item_id,
            self.organization_id,
            self.environment_id,
            self.classification,
            self.model_profile_id,
        )
        if (
            not self.embedding
            or self.created_at.tzinfo is None
            or _DIGEST.fullmatch(self.content_digest) is None
            or any(not token for token in self.lexical_tokens)
        ):
            raise ValueError("document knowledge vector record is invalid")


@dataclass(frozen=True, slots=True)
class DocumentKnowledgeSearchResult:
    chunk_id: str
    knowledge_item_id: str
    content_digest: str
    score: float
    excerpt: str
