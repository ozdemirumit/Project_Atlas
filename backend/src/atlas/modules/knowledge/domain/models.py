from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.core.classification import DataClassification

_SHA256 = re.compile(r"^[a-f0-9]{64}$")


class KnowledgeLifecycle(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    SUPERSEDED = "superseded"
    DELETED = "deleted"


@dataclass(frozen=True, slots=True)
class KnowledgeChunk:
    chunk_id: str
    item_id: str
    item_version: str
    organization_id: str
    environment_id: str
    title: str
    source_class: str
    source_reference: str
    section_path: str
    excerpt: str
    content_checksum: str
    classification: DataClassification
    access_policy_reference: str
    source_acl_version: str
    allowed_principals: frozenset[str]
    lifecycle: KnowledgeLifecycle
    observed_at: datetime
    product: str
    applicable_versions: tuple[str, ...]
    language: str
    keywords: tuple[str, ...]

    def __post_init__(self) -> None:
        required = (
            self.chunk_id,
            self.item_id,
            self.item_version,
            self.organization_id,
            self.environment_id,
            self.title,
            self.source_class,
            self.source_reference,
            self.section_path,
            self.excerpt,
            self.access_policy_reference,
            self.source_acl_version,
            self.product,
            self.language,
        )
        if not all(value.strip() for value in required):
            raise ValueError("knowledge chunk identity, scope, source, and content are required")
        if not _SHA256.fullmatch(self.content_checksum):
            raise ValueError("content_checksum must be a lowercase SHA-256 digest")
        if not self.allowed_principals:
            raise ValueError("knowledge chunks require an explicit non-empty ACL")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")

    @property
    def citation_reference(self) -> str:
        return f"knowledge://{self.item_id}/{self.item_version}/{self.chunk_id}"


@dataclass(frozen=True, slots=True)
class RetrievalRequest:
    query_id: str
    query: str
    purpose: str
    subject_id: str
    role_ids: frozenset[str]
    organization_id: str
    environment_id: str
    classification_ceiling: DataClassification
    max_results: int
    correlation_id: str

    def __post_init__(self) -> None:
        if not self.query_id or not self.query.strip() or not self.purpose.strip():
            raise ValueError("query identity, text, and purpose are required")
        if len(self.query) > 1000:
            raise ValueError("query exceeds the 1000-character limit")
        if not self.subject_id or not self.organization_id or not self.environment_id:
            raise ValueError("retrieval identity and scope are required")
        if not 1 <= self.max_results <= 10:
            raise ValueError("max_results must be between 1 and 10")

    @property
    def principals(self) -> frozenset[str]:
        return frozenset((self.subject_id, *self.role_ids))


@dataclass(frozen=True, slots=True)
class Citation:
    reference: str
    item_id: str
    item_version: str
    chunk_id: str
    title: str
    source_class: str
    source_reference: str
    location: str
    content_checksum: str
    observed_at: datetime
    classification: DataClassification


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    excerpt: str
    citation: Citation
    product: str
    applicable_versions: tuple[str, ...]
    rank_basis: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RetrievalTrace:
    query_id: str
    index_version: str
    authorized_candidate_count: int
    returned_count: int
    filter_policy_version: str
    empty_reason: str | None


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    hits: tuple[RetrievalHit, ...]
    trace: RetrievalTrace

    @property
    def citation_references(self) -> frozenset[str]:
        return frozenset(hit.citation.reference for hit in self.hits)
