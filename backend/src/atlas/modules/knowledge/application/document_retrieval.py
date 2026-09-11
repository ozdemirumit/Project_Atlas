from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.core.protected_content import ProtectedContentStore, content_digest
from atlas.modules.identity.domain.models import AuthenticatedSubject, SubjectKind
from atlas.modules.knowledge.application.document_knowledge_lifecycle_ports import (
    DocumentKnowledgeLifecycleReader,
)
from atlas.modules.knowledge.application.document_knowledge_ports import (
    DocumentKnowledgeError,
    DocumentKnowledgePermissionAuthorizer,
    DocumentKnowledgeRepository,
)
from atlas.modules.knowledge.application.document_retrieval_ports import (
    DocumentKnowledgeChunker,
    DocumentKnowledgeEmbedder,
    DocumentKnowledgeRetrievalError,
    DocumentKnowledgeVectorIndex,
)
from atlas.modules.knowledge.domain.document_retrieval import (
    DocumentKnowledgeSearchResult,
    DocumentKnowledgeVectorRecord,
    tokenize_for_lexical_search,
)

_KNOWLEDGE_DOCUMENT_INDEXING_CREATE = "knowledge.document-indexing.create"
_KNOWLEDGE_DOCUMENT_RETRIEVAL_CREATE = "knowledge.document-retrieval.create"


class DocumentKnowledgeRetrievalService:
    """Chunks, embeds, indexes, and retrieves document-sourced knowledge.

    Deliberately independent of the ADR-042-058 Operational-chain RAG pipeline — see the
    2026-08-27 amendment to ADR-184. A document's own
    DocumentKnowledgeDraft.protected_material_digest is treated as already-materialized
    content; this service reads it, chunks it, embeds each chunk (ADR-183: fastembed),
    and indexes the real vectors.
    """

    def __init__(
        self,
        *,
        repository: DocumentKnowledgeRepository,
        protected_content: ProtectedContentStore,
        chunker: DocumentKnowledgeChunker,
        embedder: DocumentKnowledgeEmbedder,
        vector_index: DocumentKnowledgeVectorIndex,
        permission_authorizer: DocumentKnowledgePermissionAuthorizer,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
        lifecycle_reader: DocumentKnowledgeLifecycleReader | None = None,
    ) -> None:
        self._repository = repository
        self._protected_content = protected_content
        self._chunker = chunker
        self._embedder = embedder
        self._vector_index = vector_index
        self._permission_authorizer = permission_authorizer
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))
        # Optional so every pre-existing caller (tests, and any composition root built before
        # SS8/SS21 lifecycle tracking existed) keeps its exact original, unfiltered behavior --
        # `None` means "no lifecycle information available", which is indistinguishable from
        # "every item is ACTIVE" since that is the default state for an item with no record
        # anyway. The real app wiring (atlas.api.app) always passes a real reader, so real
        # retrieval traffic is always genuinely filtered -- see `retrieve()` below.
        self._lifecycle_reader = lifecycle_reader

    @staticmethod
    def _require_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise DocumentKnowledgeError(
                "document_knowledge_human_required", "Only a human actor may perform this action."
            )

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        scope_reference: str,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.knowledge.document-retrieval",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id=permission_id,
                resource_type="resource.knowledge.document-retrieval",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_metadata=(),
            )
        )

    async def index_document(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        preparation_id: str,
        correlation_id: str,
    ) -> int:
        """Chunks, embeds, and indexes the approved document. Returns the chunk count."""
        self._require_human(actor)
        preparation = await self._repository.get_preparation(
            preparation_id=preparation_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if preparation is None:
            raise DocumentKnowledgeRetrievalError(
                "document_knowledge_preparation_not_found",
                "The referenced publication preparation does not exist.",
            )
        draft = await self._repository.get_draft(
            draft_id=preparation.draft_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if draft is None:
            raise DocumentKnowledgeRetrievalError(
                "document_knowledge_draft_not_found", "The referenced draft does not exist."
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            permission_id=_KNOWLEDGE_DOCUMENT_INDEXING_CREATE,
            correlation_id=correlation_id,
        )
        content = await self._protected_content.retrieve(
            organization_id=organization_id,
            environment_id=environment_id,
            digest=draft.protected_material_digest,
        )
        if content is None:
            raise DocumentKnowledgeRetrievalError(
                "document_knowledge_content_not_found",
                "The protected content referenced by this draft is not available.",
            )
        text = content.decode("utf-8", errors="replace")
        chunk_texts = self._chunker.chunk(text)
        if not chunk_texts:
            raise DocumentKnowledgeRetrievalError(
                "document_knowledge_chunking_produced_no_chunks",
                "Chunking the document produced no non-empty chunks.",
            )
        vectors = self._embedder.embed_passages(chunk_texts)
        now = self._clock()
        records: list[DocumentKnowledgeVectorRecord] = []
        for ordinal, (chunk_text, vector) in enumerate(zip(chunk_texts, vectors, strict=True)):
            chunk_digest = await self._protected_content.store(
                organization_id=organization_id,
                environment_id=environment_id,
                content=chunk_text.encode("utf-8"),
            )
            if chunk_digest != content_digest(chunk_text.encode("utf-8")):
                raise DocumentKnowledgeRetrievalError(
                    "document_knowledge_storage_uncertain",
                    "The protected-content store did not confirm the expected chunk digest.",
                )
            chunk_seed = sha256(
                f"{preparation.preparation_id}:{ordinal}:{chunk_digest}".encode()
            ).hexdigest()
            records.append(
                DocumentKnowledgeVectorRecord(
                    chunk_id=f"document-knowledge-chunk.{chunk_seed[:24]}",
                    knowledge_item_id=draft.knowledge_item_id,
                    organization_id=organization_id,
                    environment_id=environment_id,
                    classification=draft.classification,
                    content_digest=chunk_digest,
                    model_profile_id=self._embedder.model_profile_id,
                    embedding=vector,
                    created_at=now,
                    # Derived from the real chunk_text while it is still in scope,
                    # here and only here -- never re-fetched or re-derived from the
                    # protected-content store. Governance-safe: see
                    # tokenize_for_lexical_search's docstring.
                    lexical_tokens=tokenize_for_lexical_search(chunk_text),
                )
            )
        await self._vector_index.upsert(records)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=_KNOWLEDGE_DOCUMENT_INDEXING_CREATE,
            result_code="document_knowledge_indexed",
            scope_reference=preparation_id,
        )
        return len(records)

    async def retrieve(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        query: str,
        top_k: int,
        correlation_id: str,
    ) -> list[DocumentKnowledgeSearchResult]:
        self._require_human(actor)
        if not 3 <= len(query.strip()) <= 4000:
            raise DocumentKnowledgeRetrievalError(
                "document_knowledge_query_invalid",
                "The query must be between 3 and 4000 characters.",
            )
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            permission_id=_KNOWLEDGE_DOCUMENT_RETRIEVAL_CREATE,
            correlation_id=correlation_id,
        )
        ceiling = await self._permission_authorizer.classification_ceiling(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            correlation_id=correlation_id,
        )
        stripped_query = query.strip()
        query_vector = self._embedder.embed_query(stripped_query)
        raw_results = await self._vector_index.search(
            query_vector=query_vector,
            organization_id=organization_id,
            environment_id=environment_id,
            top_k=top_k,
            max_classification=ceiling,
            # Same real query text, tokenized the same way as indexed chunks were --
            # this is what makes the hybrid retrieval real rather than vector-only
            # search with unused lexical plumbing.
            lexical_query=tokenize_for_lexical_search(stripped_query),
        )
        if self._lifecycle_reader is not None and raw_results:
            # SS13: filtering happens at the one point where leakage would otherwise start.
            # Excluded here, before any excerpt is ever fetched for it, so a suspended or
            # superseded item's content never reaches this method's caller -- not bookkeeping
            # nobody reads, a real gate on every real search result.
            active_item_ids = await self._lifecycle_reader.get_active_states(
                knowledge_item_ids=tuple({result.knowledge_item_id for result in raw_results}),
                organization_id=organization_id,
                environment_id=environment_id,
            )
            raw_results = [
                result for result in raw_results if result.knowledge_item_id in active_item_ids
            ]
        results: list[DocumentKnowledgeSearchResult] = []
        for result in raw_results:
            excerpt_bytes = await self._protected_content.retrieve(
                organization_id=organization_id,
                environment_id=environment_id,
                digest=result.content_digest,
            )
            excerpt = excerpt_bytes.decode("utf-8", errors="replace") if excerpt_bytes else ""
            results.append(
                DocumentKnowledgeSearchResult(
                    chunk_id=result.chunk_id,
                    knowledge_item_id=result.knowledge_item_id,
                    content_digest=result.content_digest,
                    score=result.score,
                    excerpt=excerpt,
                )
            )
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=_KNOWLEDGE_DOCUMENT_RETRIEVAL_CREATE,
            result_code="document_knowledge_retrieved",
            scope_reference=f"query.{sha256(query.strip().encode()).hexdigest()[:24]}",
        )
        return results
