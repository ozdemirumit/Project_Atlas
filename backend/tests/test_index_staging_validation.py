from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta

import pytest
from pydantic import ValidationError
from test_embedding_generation import create_embedding_set, embedding_fixture
from test_package_acquisition import CollectingAuditSink
from test_target_session import target_session_operator

from atlas.api.index_staging_validation_schemas import (
    OperationalKnowledgeIndexData,
    OperationalKnowledgeIndexInput,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject, SubjectKind
from atlas.modules.knowledge.adapters.index_staging_validation_memory import (
    InMemoryOperationalKnowledgeIndexPolicySource,
    InMemoryOperationalKnowledgeIndexRepository,
)
from atlas.modules.knowledge.adapters.index_staging_validation_postgres import (
    PostgreSQLOperationalKnowledgeIndexRepository,
)
from atlas.modules.knowledge.adapters.index_staging_validation_synthetic import (
    SyntheticOperationalKnowledgeIndexer,
    UnavailableOperationalKnowledgeIndexer,
)
from atlas.modules.knowledge.application.index_staging_validation import (
    OperationalKnowledgeIndexStagingValidationService,
    build_development_operational_knowledge_index_policy,
)
from atlas.modules.knowledge.application.index_staging_validation_ports import (
    OperationalKnowledgeIndexer,
    OperationalKnowledgeIndexError,
)
from atlas.modules.knowledge.domain.embedding_generation import (
    OperationalKnowledgeEmbeddingRecord,
)
from atlas.modules.knowledge.domain.index_staging_validation import (
    OperationalKnowledgeIndexInstruction,
    OperationalKnowledgeIndexPolicySnapshot,
    OperationalKnowledgeIndexReceipt,
    OperationalKnowledgeIndexRecord,
)


class RecordingIndexPermissionAuthorizer:
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
            raise OperationalKnowledgeIndexError("operational_knowledge_index_permission_denied")


class BlockingIndexer(SyntheticOperationalKnowledgeIndexer):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def stage_and_validate(
        self, instruction: OperationalKnowledgeIndexInstruction
    ) -> OperationalKnowledgeIndexReceipt:
        self.started.set()
        await self.release.wait()
        return await super().stage_and_validate(instruction)


class DriftingIndexer(SyntheticOperationalKnowledgeIndexer):
    async def stage_and_validate(
        self, instruction: OperationalKnowledgeIndexInstruction
    ) -> OperationalKnowledgeIndexReceipt:
        receipt = await super().stage_and_validate(instruction)
        return replace(receipt, staged_point_count=receipt.staged_point_count + 1)


async def index_fixture(
    *,
    indexer: OperationalKnowledgeIndexer | None = None,
    authorizer: RecordingIndexPermissionAuthorizer | None = None,
) -> tuple[
    OperationalKnowledgeIndexStagingValidationService,
    InMemoryOperationalKnowledgeIndexRepository,
    OperationalKnowledgeEmbeddingRecord,
    OperationalKnowledgeIndexPolicySnapshot,
    AuthenticatedSubject,
    OperationalKnowledgeIndexer,
    RecordingIndexPermissionAuthorizer,
    CollectingAuditSink,
]:
    embedding_service, _, chunk, embedding_policy, embedding_actor, *_ = await embedding_fixture()
    embedding = await create_embedding_set(
        embedding_service, chunk, embedding_policy, embedding_actor
    )
    policy = build_development_operational_knowledge_index_policy(
        organization_id=embedding.organization_id,
        environment_id=embedding.environment_id,
        issued_at=embedding.embedded_at - timedelta(hours=1),
        expires_at=embedding.embedded_at + timedelta(days=1),
        embedding_policy=embedding_policy,
    )
    resolved_indexer = indexer or SyntheticOperationalKnowledgeIndexer()
    if isinstance(resolved_indexer, SyntheticOperationalKnowledgeIndexer):
        resolved_indexer._clock = lambda: embedding.embedded_at
    permission = authorizer or RecordingIndexPermissionAuthorizer()
    repository = InMemoryOperationalKnowledgeIndexRepository()
    audit = CollectingAuditSink()
    service = OperationalKnowledgeIndexStagingValidationService(
        repository=repository,
        embedding_source=embedding_service,
        policy_source=InMemoryOperationalKnowledgeIndexPolicySource((policy,)),
        permission_authorizer=permission,
        indexer=resolved_indexer,
        audit_sink=audit,
        environment_id=embedding.environment_id,
        clock=lambda: embedding.embedded_at,
    )
    actor = target_session_operator("subject.knowledge-index-steward")
    return service, repository, embedding, policy, actor, resolved_indexer, permission, audit


async def create_index_stage(
    service: OperationalKnowledgeIndexStagingValidationService,
    embedding: OperationalKnowledgeEmbeddingRecord,
    policy: OperationalKnowledgeIndexPolicySnapshot,
    actor: AuthenticatedSubject,
    *,
    idempotency_key: str = "knowledge-index-staging-001",
) -> OperationalKnowledgeIndexRecord:
    return await service.create(
        actor=actor,
        embedding_set_id=embedding.embedding_set_id,
        embedding_set_digest=embedding.canonical_digest,
        index_policy_id=policy.policy_id,
        index_policy_digest=policy.canonical_digest,
        purpose="Stage and validate the governed inactive knowledge retrieval projection.",
        protected_vector_boundary_acknowledged=True,
        inactive_projection_acknowledged=True,
        no_publication_or_operational_authority_acknowledged=True,
        browser_session_id="session_knowledge_index_staging_001",
        idempotency_key=idempotency_key,
        correlation_id="cor_knowledge_index_staging",
    )


@pytest.mark.asyncio
async def test_index_staging_rejects_non_human_actor() -> None:
    service, _, embedding, policy, actor, *_ = await index_fixture()
    with pytest.raises(OperationalKnowledgeIndexError, match="human_required"):
        await create_index_stage(
            service,
            embedding,
            policy,
            replace(actor, kind=SubjectKind.SERVICE),
        )


@pytest.mark.asyncio
async def test_index_staging_is_metadata_only_complete_and_idempotent() -> None:
    (
        service,
        repository,
        embedding,
        policy,
        actor,
        indexer,
        permission,
        audit,
    ) = await index_fixture()
    record = await create_index_stage(service, embedding, policy, actor)
    repeated = await create_index_stage(service, embedding, policy, actor)
    replay = await service.get(
        actor=actor,
        index_staging_id=record.index_staging_id,
        browser_session_id="session_knowledge_index_staging_001",
        correlation_id="cor_knowledge_index_staging_read",
    )

    assert record.index_staged and record.index_validated and record.embeddings_created
    assert record.staged_point_count == embedding.embedding_count
    assert not record.knowledge_published and not record.retrieval_published
    assert not record.model_context_available and not record.workflow_continued
    assert not record.execution_authorized and not record.infrastructure_mutation_performed
    assert repeated.reused and replay.reused
    assert isinstance(indexer, SyntheticOperationalKnowledgeIndexer)
    assert len(indexer.calls) == 1
    assert await repository.get(index_staging_id=record.index_staging_id) == record
    persisted = OperationalKnowledgeIndexStagingValidationService._normalize(asdict(record))
    assert isinstance(persisted, dict)
    restored = PostgreSQLOperationalKnowledgeIndexRepository._record_to_domain(persisted)
    assert restored == record
    assert len(permission.calls) == 3
    raw = asdict(record)
    response_data = OperationalKnowledgeIndexData.from_domain(record).model_dump()
    for forbidden in (
        "content",
        "excerpt",
        "chunk_coordinates",
        "point_ids",
        "collection_name",
        "vector_values",
        "payload",
        "query_results",
        "encryption_key",
    ):
        assert forbidden not in raw
        assert forbidden not in response_data
    for private_field in (
        "index_steward_subject_digest",
        "browser_session_binding_digest",
        "upstream_accountable_subject_digests",
        "claim_id",
    ):
        assert private_field not in response_data
    assert [item.result_code for item in audit.records] == [
        "operational_knowledge_index_staging_requested",
        "operational_knowledge_index_staging_claimed",
        "operational_knowledge_index_validated",
        "operational_knowledge_index_read",
        "operational_knowledge_index_read",
    ]


@pytest.mark.asyncio
async def test_index_staging_requires_separate_steward() -> None:
    service, repository, embedding, policy, *_ = await index_fixture()
    actor = target_session_operator("subject.knowledge-embedding-steward")
    with pytest.raises(OperationalKnowledgeIndexError, match="separation_required"):
        await create_index_stage(service, embedding, policy, actor)
    assert (
        await repository.get_claim_by_embedding_set(embedding_set_id=embedding.embedding_set_id)
        is None
    )


@pytest.mark.asyncio
async def test_index_staging_permission_denial_precedes_claim() -> None:
    permission = RecordingIndexPermissionAuthorizer(deny=True)
    service, repository, embedding, policy, actor, indexer, *_ = await index_fixture(
        authorizer=permission
    )
    with pytest.raises(OperationalKnowledgeIndexError, match="permission_denied"):
        await create_index_stage(service, embedding, policy, actor)
    assert isinstance(indexer, SyntheticOperationalKnowledgeIndexer)
    assert not indexer.calls
    assert (
        await repository.get_claim_by_embedding_set(embedding_set_id=embedding.embedding_set_id)
        is None
    )


@pytest.mark.asyncio
async def test_index_staging_atomic_claim_blocks_concurrent_duplicate() -> None:
    blocker = BlockingIndexer()
    service, repository, embedding, policy, actor, *_ = await index_fixture(indexer=blocker)
    first = asyncio.create_task(create_index_stage(service, embedding, policy, actor))
    await blocker.started.wait()
    with pytest.raises(OperationalKnowledgeIndexError, match="already_claimed"):
        await create_index_stage(service, embedding, policy, actor)
    blocker.release.set()
    record = await first
    assert await repository.get(index_staging_id=record.index_staging_id) == record


@pytest.mark.asyncio
async def test_index_staging_rejects_drifted_receipt_and_keeps_claim() -> None:
    service, repository, embedding, policy, actor, *_ = await index_fixture(
        indexer=DriftingIndexer()
    )
    with pytest.raises(OperationalKnowledgeIndexError, match="receipt_invalid"):
        await create_index_stage(service, embedding, policy, actor)
    assert await repository.get_claim_by_embedding_set(embedding_set_id=embedding.embedding_set_id)
    with pytest.raises(OperationalKnowledgeIndexError, match="already_claimed"):
        await create_index_stage(service, embedding, policy, actor)


@pytest.mark.asyncio
async def test_production_indexer_fails_closed_after_claim() -> None:
    service, repository, embedding, policy, actor, *_ = await index_fixture(
        indexer=UnavailableOperationalKnowledgeIndexer()
    )
    with pytest.raises(OperationalKnowledgeIndexError, match="indexer_unavailable"):
        await create_index_stage(service, embedding, policy, actor)
    assert await repository.get_claim_by_embedding_set(embedding_set_id=embedding.embedding_set_id)


def test_index_staging_persistence_contract_is_metadata_only() -> None:
    fields = OperationalKnowledgeIndexRecord.__dataclass_fields__
    for forbidden in (
        "content",
        "excerpt",
        "chunk_coordinates",
        "point_ids",
        "collection_name",
        "vector_values",
        "payload",
        "query_results",
        "encryption_key",
    ):
        assert forbidden not in fields
    assert hasattr(PostgreSQLOperationalKnowledgeIndexRepository, "claim")
    assert hasattr(PostgreSQLOperationalKnowledgeIndexRepository, "add")


def test_index_staging_api_input_forbids_projection_and_vector_parameters() -> None:
    payload = {
        "embedding_set_digest": "a" * 64,
        "index_policy_id": "operational-knowledge-index-policy.development",
        "index_policy_digest": "b" * 64,
        "purpose": "Stage and validate the governed inactive knowledge retrieval projection.",
        "acknowledged_protected_vector_boundary": True,
        "acknowledged_inactive_projection": True,
        "acknowledged_no_publication_or_operational_authority": True,
    }
    assert OperationalKnowledgeIndexInput.model_validate(payload)
    for forbidden in (
        "steward_id",
        "content",
        "chunk_ids",
        "vector_values",
        "collection_name",
        "point_ids",
        "payload",
        "index_parameters",
        "retrieval_enabled",
    ):
        with pytest.raises(ValidationError):
            OperationalKnowledgeIndexInput.model_validate({**payload, forbidden: "caller-selected"})
