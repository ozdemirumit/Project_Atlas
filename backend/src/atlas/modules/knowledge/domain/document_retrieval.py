"""Real chunking/embedding/vector-index/retrieval for document-sourced knowledge.

Deliberately separate from the ADR-042-058 Operational-chain RAG pipeline per the
2026-08-27 amendment to ADR-184: this path never touches Operational-chain code.
Chunk text lives only in atlas.core.protected_content, referenced here by digest;
only the embedding vector itself is real, queryable data in this module's own
dedicated vector store (never in ordinary application persistence).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")


def _ids(*values: str) -> None:
    for value in values:
        validate_stable_identifier(value, "document knowledge retrieval identifier")


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
        ):
            raise ValueError("document knowledge vector record is invalid")


@dataclass(frozen=True, slots=True)
class DocumentKnowledgeSearchResult:
    chunk_id: str
    knowledge_item_id: str
    content_digest: str
    score: float
    excerpt: str
