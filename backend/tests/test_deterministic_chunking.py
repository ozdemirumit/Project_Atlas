from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta

import pytest
from pydantic import ValidationError
from test_package_acquisition import CollectingAuditSink
from test_source_materialization import materialize, source_materialization_fixture
from test_target_session import target_session_operator

from atlas.api.deterministic_chunking_schemas import OperationalKnowledgeChunkingInput
from atlas.modules.identity.domain.models import AuthenticatedSubject, SubjectKind
from atlas.modules.knowledge.adapters.deterministic_chunking_memory import (
    InMemoryOperationalKnowledgeChunkingPolicySource,
    InMemoryOperationalKnowledgeChunkingRepository,
)
from atlas.modules.knowledge.adapters.deterministic_chunking_postgres import (
    PostgreSQLOperationalKnowledgeChunkingRepository,
)
from atlas.modules.knowledge.adapters.deterministic_chunking_synthetic import (
    SyntheticOperationalKnowledgeChunker,
)
from atlas.modules.knowledge.application.deterministic_chunking import (
    OperationalKnowledgeDeterministicChunkingService,
    build_development_operational_knowledge_chunking_policy,
)
from atlas.modules.knowledge.application.deterministic_chunking_ports import (
    OperationalKnowledgeChunkingError,
)
from atlas.modules.knowledge.domain.deterministic_chunking import (
    OperationalKnowledgeChunkingInstruction,
    OperationalKnowledgeChunkingPolicySnapshot,
    OperationalKnowledgeChunkingReceipt,
    OperationalKnowledgeChunkingRecord,
)
from atlas.modules.knowledge.domain.source_materialization import (
    OperationalKnowledgeSourceMaterializationRecord,
)


class RecordingChunkingPermissionAuthorizer:
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
            raise OperationalKnowledgeChunkingError(
                "operational_knowledge_chunking_permission_denied"
            )


class BlockingChunker(SyntheticOperationalKnowledgeChunker):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def chunk(
        self, instruction: OperationalKnowledgeChunkingInstruction
    ) -> OperationalKnowledgeChunkingReceipt:
        self.started.set()
        await self.release.wait()
        return await super().chunk(instruction)


class DriftingChunker(SyntheticOperationalKnowledgeChunker):
    async def chunk(
        self, instruction: OperationalKnowledgeChunkingInstruction
    ) -> OperationalKnowledgeChunkingReceipt:
        receipt = await super().chunk(instruction)
        return replace(receipt, protected_material_digest="f" * 64)


async def deterministic_chunking_fixture(
    *,
    chunker: SyntheticOperationalKnowledgeChunker | None = None,
    authorizer: RecordingChunkingPermissionAuthorizer | None = None,
) -> tuple[
    OperationalKnowledgeDeterministicChunkingService,
    InMemoryOperationalKnowledgeChunkingRepository,
    OperationalKnowledgeSourceMaterializationRecord,
    OperationalKnowledgeChunkingPolicySnapshot,
    AuthenticatedSubject,
    SyntheticOperationalKnowledgeChunker,
    RecordingChunkingPermissionAuthorizer,
    CollectingAuditSink,
]:
    (
        materialization_service,
        _,
        preparation,
        materialization_policy,
        materialization_actor,
        *_rest,
    ) = await source_materialization_fixture()
    materialization = await materialize(
        materialization_service,
        preparation,
        materialization_policy,
        materialization_actor,
    )
    policy = build_development_operational_knowledge_chunking_policy(
        organization_id=materialization.organization_id,
        environment_id=materialization.environment_id,
        issued_at=materialization.materialized_at - timedelta(hours=1),
        expires_at=materialization.materialized_at + timedelta(days=1),
    )
    resolved_chunker = chunker or SyntheticOperationalKnowledgeChunker()
    resolved_chunker._clock = lambda: materialization.materialized_at
    permission = authorizer or RecordingChunkingPermissionAuthorizer()
    repository = InMemoryOperationalKnowledgeChunkingRepository()
    audit = CollectingAuditSink()
    service = OperationalKnowledgeDeterministicChunkingService(
        repository=repository,
        materialization_source=materialization_service,
        preparation_source=materialization_service._preparation_source,
        lineage_source=materialization_service._lineage_source,
        policy_source=InMemoryOperationalKnowledgeChunkingPolicySource((policy,)),
        permission_authorizer=permission,
        chunker=resolved_chunker,
        audit_sink=audit,
        environment_id=materialization.environment_id,
        clock=lambda: materialization.materialized_at,
    )
    actor = target_session_operator("subject.knowledge-chunking-steward")
    return (
        service,
        repository,
        materialization,
        policy,
        actor,
        resolved_chunker,
        permission,
        audit,
    )


async def create_chunk_set(
    service: OperationalKnowledgeDeterministicChunkingService,
    materialization: OperationalKnowledgeSourceMaterializationRecord,
    policy: OperationalKnowledgeChunkingPolicySnapshot,
    actor: AuthenticatedSubject,
    *,
    idempotency_key: str = "knowledge-deterministic-chunking-001",
) -> OperationalKnowledgeChunkingRecord:
    return await service.create(
        actor=actor,
        materialization_id=materialization.materialization_id,
        materialization_digest=materialization.canonical_digest,
        chunking_policy_id=policy.policy_id,
        chunking_policy_digest=policy.canonical_digest,
        purpose="Create the deterministic protected chunk set for approved operational knowledge.",
        protected_boundary_acknowledged=True,
        immutable_profile_acknowledged=True,
        no_embedding_or_operational_authority_acknowledged=True,
        browser_session_id="session_knowledge_deterministic_chunking_001",
        idempotency_key=idempotency_key,
        correlation_id="cor_knowledge_deterministic_chunking",
    )


@pytest.mark.asyncio
async def test_chunking_rejects_non_human_actor() -> None:
    service, _, materialization, policy, actor, *_ = await deterministic_chunking_fixture()
    with pytest.raises(OperationalKnowledgeChunkingError, match="human_required"):
        await create_chunk_set(
            service,
            materialization,
            policy,
            replace(actor, kind=SubjectKind.SERVICE),
        )


@pytest.mark.asyncio
async def test_chunking_is_metadata_only_deterministic_and_idempotent() -> None:
    (
        service,
        repository,
        materialization,
        policy,
        actor,
        chunker,
        permission,
        audit,
    ) = await deterministic_chunking_fixture()
    record = await create_chunk_set(service, materialization, policy, actor)
    repeated = await create_chunk_set(service, materialization, policy, actor)
    replay = await service.get(
        actor=actor,
        chunk_set_id=record.chunk_set_id,
        browser_session_id="session_knowledge_deterministic_chunking_001",
        correlation_id="cor_knowledge_deterministic_chunking_read",
    )

    assert record.chunks_created and record.source_materialized
    assert not record.embeddings_created and not record.index_staged
    assert not record.index_validated and not record.knowledge_published
    assert not record.retrieval_published and not record.workflow_continued
    assert not record.execution_authorized and not record.infrastructure_mutation_performed
    assert repeated.reused and replay.reused and len(chunker.calls) == 1
    assert await repository.get(chunk_set_id=record.chunk_set_id) == record
    assert len(permission.calls) == 3
    raw = asdict(record)
    for forbidden in (
        "content",
        "excerpt",
        "section_path",
        "chunk_coordinate",
        "token_stream",
        "embedding",
    ):
        assert forbidden not in raw
    assert [item.result_code for item in audit.records] == [
        "operational_knowledge_chunking_requested",
        "operational_knowledge_chunking_claimed",
        "operational_knowledge_chunking_recorded",
        "operational_knowledge_chunking_read",
        "operational_knowledge_chunking_read",
    ]


@pytest.mark.asyncio
async def test_chunking_requires_separate_steward() -> None:
    service, repository, materialization, policy, *_ = await deterministic_chunking_fixture()
    actor = target_session_operator("subject.knowledge-materialization-steward")
    with pytest.raises(OperationalKnowledgeChunkingError, match="separation_required"):
        await create_chunk_set(service, materialization, policy, actor)
    assert (
        await repository.get_claim_by_materialization(
            materialization_id=materialization.materialization_id
        )
        is None
    )


@pytest.mark.asyncio
async def test_chunking_permission_denial_precedes_claim() -> None:
    permission = RecordingChunkingPermissionAuthorizer(deny=True)
    (
        service,
        repository,
        materialization,
        policy,
        actor,
        chunker,
        *_,
    ) = await deterministic_chunking_fixture(authorizer=permission)
    with pytest.raises(OperationalKnowledgeChunkingError, match="permission_denied"):
        await create_chunk_set(service, materialization, policy, actor)
    assert not chunker.calls
    assert (
        await repository.get_claim_by_materialization(
            materialization_id=materialization.materialization_id
        )
        is None
    )


@pytest.mark.asyncio
async def test_chunking_atomic_claim_blocks_concurrent_duplicate() -> None:
    blocker = BlockingChunker()
    service, repository, materialization, policy, actor, *_ = await deterministic_chunking_fixture(
        chunker=blocker
    )
    first = asyncio.create_task(create_chunk_set(service, materialization, policy, actor))
    await blocker.started.wait()
    with pytest.raises(OperationalKnowledgeChunkingError, match="already_claimed"):
        await create_chunk_set(service, materialization, policy, actor)
    blocker.release.set()
    record = await first
    assert await repository.get(chunk_set_id=record.chunk_set_id) == record


@pytest.mark.asyncio
async def test_chunking_rejects_drifted_receipt_and_keeps_claim() -> None:
    service, repository, materialization, policy, actor, *_ = await deterministic_chunking_fixture(
        chunker=DriftingChunker()
    )
    with pytest.raises(OperationalKnowledgeChunkingError, match="receipt_invalid"):
        await create_chunk_set(service, materialization, policy, actor)
    assert await repository.get_claim_by_materialization(
        materialization_id=materialization.materialization_id
    )
    with pytest.raises(OperationalKnowledgeChunkingError, match="already_claimed"):
        await create_chunk_set(service, materialization, policy, actor)


def test_chunking_postgres_mapping_is_metadata_only() -> None:
    fields = OperationalKnowledgeChunkingRecord.__dataclass_fields__
    for forbidden in (
        "content",
        "excerpt",
        "section_path",
        "chunk_coordinate",
        "token_stream",
        "embedding",
    ):
        assert forbidden not in fields
    assert hasattr(PostgreSQLOperationalKnowledgeChunkingRepository, "claim")
    assert hasattr(PostgreSQLOperationalKnowledgeChunkingRepository, "add")


def test_chunking_api_input_forbids_content_coordinates_and_parameters() -> None:
    payload = {
        "source_materialization_digest": "a" * 64,
        "chunking_policy_id": "operational-knowledge-chunking-policy.development",
        "chunking_policy_digest": "b" * 64,
        "purpose": "Create the deterministic protected chunk set for approved knowledge.",
        "acknowledged_protected_content_boundary": True,
        "acknowledged_immutable_chunking_profile": True,
        "acknowledged_no_embedding_or_operational_authority": True,
    }
    assert OperationalKnowledgeChunkingInput.model_validate(payload)
    for forbidden in (
        "steward_id",
        "content",
        "chunk_size",
        "overlap",
        "section_path",
        "index_id",
    ):
        with pytest.raises(ValidationError):
            OperationalKnowledgeChunkingInput.model_validate(
                {**payload, forbidden: "caller-selected"}
            )
