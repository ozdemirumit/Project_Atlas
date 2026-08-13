from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta

import pytest
from pydantic import ValidationError
from test_deterministic_chunking import create_chunk_set, deterministic_chunking_fixture
from test_package_acquisition import CollectingAuditSink
from test_target_session import target_session_operator

from atlas.api.embedding_generation_schemas import (
    OperationalKnowledgeEmbeddingData,
    OperationalKnowledgeEmbeddingInput,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject, SubjectKind
from atlas.modules.knowledge.adapters.embedding_generation_memory import (
    InMemoryOperationalKnowledgeEmbeddingPolicySource,
    InMemoryOperationalKnowledgeEmbeddingRepository,
)
from atlas.modules.knowledge.adapters.embedding_generation_postgres import (
    PostgreSQLOperationalKnowledgeEmbeddingRepository,
)
from atlas.modules.knowledge.adapters.embedding_generation_synthetic import (
    SyntheticOperationalKnowledgeEmbedder,
    UnavailableOperationalKnowledgeEmbedder,
)
from atlas.modules.knowledge.application.embedding_generation import (
    OperationalKnowledgeEmbeddingGenerationService,
    build_development_operational_knowledge_embedding_policy,
)
from atlas.modules.knowledge.application.embedding_generation_ports import (
    OperationalKnowledgeEmbedder,
    OperationalKnowledgeEmbeddingError,
)
from atlas.modules.knowledge.domain.deterministic_chunking import (
    OperationalKnowledgeChunkingRecord,
)
from atlas.modules.knowledge.domain.embedding_generation import (
    OperationalKnowledgeEmbeddingInstruction,
    OperationalKnowledgeEmbeddingPolicySnapshot,
    OperationalKnowledgeEmbeddingReceipt,
    OperationalKnowledgeEmbeddingRecord,
)


class RecordingEmbeddingPermissionAuthorizer:
    def __init__(self, *, deny: bool = False) -> None:
        self.deny = deny
        self.calls: list[tuple[str, str]] = []

    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> None:
        del actor, correlation_id
        self.calls.append((organization_id, environment_id))
        if self.deny:
            raise OperationalKnowledgeEmbeddingError(
                "operational_knowledge_embedding_permission_denied"
            )


class BlockingEmbedder(SyntheticOperationalKnowledgeEmbedder):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def embed(
        self, instruction: OperationalKnowledgeEmbeddingInstruction
    ) -> OperationalKnowledgeEmbeddingReceipt:
        self.started.set()
        await self.release.wait()
        return await super().embed(instruction)


class DriftingEmbedder(SyntheticOperationalKnowledgeEmbedder):
    async def embed(
        self, instruction: OperationalKnowledgeEmbeddingInstruction
    ) -> OperationalKnowledgeEmbeddingReceipt:
        receipt = await super().embed(instruction)
        return replace(receipt, model_artifact_digest="f" * 64)


async def embedding_fixture(
    *,
    embedder: OperationalKnowledgeEmbedder | None = None,
    authorizer: RecordingEmbeddingPermissionAuthorizer | None = None,
) -> tuple[
    OperationalKnowledgeEmbeddingGenerationService,
    InMemoryOperationalKnowledgeEmbeddingRepository,
    OperationalKnowledgeChunkingRecord,
    OperationalKnowledgeEmbeddingPolicySnapshot,
    AuthenticatedSubject,
    OperationalKnowledgeEmbedder,
    RecordingEmbeddingPermissionAuthorizer,
    CollectingAuditSink,
]:
    (
        chunking_service,
        _,
        materialization,
        chunking_policy,
        chunking_actor,
        *_,
    ) = await deterministic_chunking_fixture()
    chunk = await create_chunk_set(
        chunking_service, materialization, chunking_policy, chunking_actor
    )
    policy = build_development_operational_knowledge_embedding_policy(
        organization_id=chunk.organization_id,
        environment_id=chunk.environment_id,
        issued_at=chunk.chunked_at - timedelta(hours=1),
        expires_at=chunk.chunked_at + timedelta(days=1),
    )
    resolved_embedder = embedder or SyntheticOperationalKnowledgeEmbedder()
    if isinstance(resolved_embedder, SyntheticOperationalKnowledgeEmbedder):
        resolved_embedder._clock = lambda: chunk.chunked_at
    permission = authorizer or RecordingEmbeddingPermissionAuthorizer()
    repository = InMemoryOperationalKnowledgeEmbeddingRepository()
    audit = CollectingAuditSink()
    service = OperationalKnowledgeEmbeddingGenerationService(
        repository=repository,
        chunk_source=chunking_service,
        policy_source=InMemoryOperationalKnowledgeEmbeddingPolicySource((policy,)),
        permission_authorizer=permission,
        embedder=resolved_embedder,
        audit_sink=audit,
        environment_id=chunk.environment_id,
        clock=lambda: chunk.chunked_at,
    )
    actor = target_session_operator("subject.knowledge-embedding-steward")
    return service, repository, chunk, policy, actor, resolved_embedder, permission, audit


async def create_embedding_set(
    service: OperationalKnowledgeEmbeddingGenerationService,
    chunk: OperationalKnowledgeChunkingRecord,
    policy: OperationalKnowledgeEmbeddingPolicySnapshot,
    actor: AuthenticatedSubject,
    *,
    idempotency_key: str = "knowledge-embedding-generation-001",
) -> OperationalKnowledgeEmbeddingRecord:
    return await service.create(
        actor=actor,
        chunk_set_id=chunk.chunk_set_id,
        chunk_set_digest=chunk.canonical_digest,
        embedding_policy_id=policy.policy_id,
        embedding_policy_digest=policy.canonical_digest,
        purpose="Create the governed local embedding set for approved operational knowledge.",
        protected_boundary_acknowledged=True,
        immutable_model_profile_acknowledged=True,
        no_index_or_operational_authority_acknowledged=True,
        browser_session_id="session_knowledge_embedding_generation_001",
        idempotency_key=idempotency_key,
        correlation_id="cor_knowledge_embedding_generation",
    )


@pytest.mark.asyncio
async def test_embedding_rejects_non_human_actor() -> None:
    service, _, chunk, policy, actor, *_ = await embedding_fixture()
    with pytest.raises(OperationalKnowledgeEmbeddingError, match="human_required"):
        await create_embedding_set(
            service,
            chunk,
            policy,
            replace(actor, kind=SubjectKind.SERVICE),
        )


@pytest.mark.asyncio
async def test_embedding_is_metadata_only_complete_and_idempotent() -> None:
    (
        service,
        repository,
        chunk,
        policy,
        actor,
        embedder,
        permission,
        audit,
    ) = await embedding_fixture()
    record = await create_embedding_set(service, chunk, policy, actor)
    repeated = await create_embedding_set(service, chunk, policy, actor)
    replay = await service.get(
        actor=actor,
        embedding_set_id=record.embedding_set_id,
        browser_session_id="session_knowledge_embedding_generation_001",
        correlation_id="cor_knowledge_embedding_generation_read",
    )

    assert record.embeddings_created and record.chunks_created
    assert record.embedding_count == chunk.chunk_count
    assert not record.index_staged and not record.index_validated
    assert not record.retrieval_published and not record.model_context_available
    assert not record.workflow_continued and not record.infrastructure_mutation_performed
    assert repeated.reused and replay.reused
    assert isinstance(embedder, SyntheticOperationalKnowledgeEmbedder)
    assert len(embedder.calls) == 1
    assert await repository.get(embedding_set_id=record.embedding_set_id) == record
    assert len(permission.calls) == 3
    raw = asdict(record)
    response_data = OperationalKnowledgeEmbeddingData.from_domain(record).model_dump()
    for forbidden in (
        "content",
        "excerpt",
        "chunk_coordinates",
        "chunk_id_map",
        "vector_values",
        "model_endpoint",
        "token_stream",
        "encryption_key",
    ):
        assert forbidden not in raw
        assert forbidden not in response_data
    for private_field in (
        "embedded_by_subject_digest",
        "chunking_steward_subject_digest",
        "materialization_steward_subject_digest",
        "publication_steward_subject_digest",
        "browser_session_binding_digest",
        "claim_id",
    ):
        assert private_field not in response_data
    assert [item.result_code for item in audit.records] == [
        "operational_knowledge_embedding_requested",
        "operational_knowledge_embedding_claimed",
        "operational_knowledge_embedding_recorded",
        "operational_knowledge_embedding_read",
        "operational_knowledge_embedding_read",
    ]


@pytest.mark.asyncio
async def test_embedding_requires_separate_steward() -> None:
    service, repository, chunk, policy, *_ = await embedding_fixture()
    actor = target_session_operator("subject.knowledge-chunking-steward")
    with pytest.raises(OperationalKnowledgeEmbeddingError, match="separation_required"):
        await create_embedding_set(service, chunk, policy, actor)
    assert await repository.get_claim_by_chunk_set(chunk_set_id=chunk.chunk_set_id) is None


@pytest.mark.asyncio
async def test_embedding_permission_denial_precedes_claim() -> None:
    permission = RecordingEmbeddingPermissionAuthorizer(deny=True)
    service, repository, chunk, policy, actor, embedder, *_ = await embedding_fixture(
        authorizer=permission
    )
    with pytest.raises(OperationalKnowledgeEmbeddingError, match="permission_denied"):
        await create_embedding_set(service, chunk, policy, actor)
    assert isinstance(embedder, SyntheticOperationalKnowledgeEmbedder)
    assert not embedder.calls
    assert await repository.get_claim_by_chunk_set(chunk_set_id=chunk.chunk_set_id) is None


@pytest.mark.asyncio
async def test_embedding_atomic_claim_blocks_concurrent_duplicate() -> None:
    blocker = BlockingEmbedder()
    service, repository, chunk, policy, actor, *_ = await embedding_fixture(embedder=blocker)
    first = asyncio.create_task(create_embedding_set(service, chunk, policy, actor))
    await blocker.started.wait()
    with pytest.raises(OperationalKnowledgeEmbeddingError, match="already_claimed"):
        await create_embedding_set(service, chunk, policy, actor)
    blocker.release.set()
    record = await first
    assert await repository.get(embedding_set_id=record.embedding_set_id) == record


@pytest.mark.asyncio
async def test_embedding_rejects_drifted_receipt_and_keeps_claim() -> None:
    service, repository, chunk, policy, actor, *_ = await embedding_fixture(
        embedder=DriftingEmbedder()
    )
    with pytest.raises(OperationalKnowledgeEmbeddingError, match="receipt_invalid"):
        await create_embedding_set(service, chunk, policy, actor)
    assert await repository.get_claim_by_chunk_set(chunk_set_id=chunk.chunk_set_id)
    with pytest.raises(OperationalKnowledgeEmbeddingError, match="already_claimed"):
        await create_embedding_set(service, chunk, policy, actor)


@pytest.mark.asyncio
async def test_production_embedder_fails_closed_after_claim() -> None:
    service, repository, chunk, policy, actor, *_ = await embedding_fixture(
        embedder=UnavailableOperationalKnowledgeEmbedder()
    )
    with pytest.raises(OperationalKnowledgeEmbeddingError, match="embedder_unavailable"):
        await create_embedding_set(service, chunk, policy, actor)
    assert await repository.get_claim_by_chunk_set(chunk_set_id=chunk.chunk_set_id)


def test_embedding_persistence_contract_is_metadata_only() -> None:
    fields = OperationalKnowledgeEmbeddingRecord.__dataclass_fields__
    for forbidden in (
        "content",
        "excerpt",
        "chunk_coordinates",
        "chunk_id_map",
        "vector_values",
        "model_endpoint",
        "token_stream",
        "encryption_key",
    ):
        assert forbidden not in fields
    assert hasattr(PostgreSQLOperationalKnowledgeEmbeddingRepository, "claim")
    assert hasattr(PostgreSQLOperationalKnowledgeEmbeddingRepository, "add")


def test_embedding_api_input_forbids_content_vectors_and_model_parameters() -> None:
    payload = {
        "chunk_set_digest": "a" * 64,
        "embedding_policy_id": "operational-knowledge-embedding-policy.development",
        "embedding_policy_digest": "b" * 64,
        "purpose": "Create the governed local embedding set for approved operational knowledge.",
        "acknowledged_protected_chunk_boundary": True,
        "acknowledged_immutable_model_profile": True,
        "acknowledged_no_index_or_operational_authority": True,
    }
    assert OperationalKnowledgeEmbeddingInput.model_validate(payload)
    for forbidden in (
        "steward_id",
        "content",
        "chunk_ids",
        "vector_values",
        "model_id",
        "model_endpoint",
        "dimension",
        "normalization",
        "index_id",
    ):
        with pytest.raises(ValidationError):
            OperationalKnowledgeEmbeddingInput.model_validate(
                {**payload, forbidden: "caller-selected"}
            )
