from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from atlas.modules.knowledge.domain.document_retrieval import (
    DocumentKnowledgeSearchResult,
    DocumentKnowledgeVectorRecord,
)


class DocumentKnowledgeRetrievalError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code


class DocumentKnowledgeChunker(Protocol):
    def chunk(self, text: str) -> list[str]:
        """Splits real document text into bounded, non-empty chunk strings."""
        ...


class DocumentKnowledgeEmbedder(Protocol):
    def embed_passages(self, texts: Sequence[str]) -> list[tuple[float, ...]]: ...

    def embed_query(self, text: str) -> tuple[float, ...]: ...

    @property
    def model_profile_id(self) -> str: ...


class DocumentKnowledgeVectorIndex(Protocol):
    async def upsert(self, records: Sequence[DocumentKnowledgeVectorRecord]) -> None: ...

    async def search(
        self,
        *,
        query_vector: Sequence[float],
        organization_id: str,
        environment_id: str,
        top_k: int,
    ) -> list[DocumentKnowledgeSearchResult]: ...
