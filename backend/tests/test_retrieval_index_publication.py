from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta

import pytest
from pydantic import ValidationError
from test_index_staging_validation import create_index_stage, index_fixture
from test_package_acquisition import CollectingAuditSink
from test_target_session import target_session_operator

from atlas.api.retrieval_index_publication_schemas import (
    OperationalKnowledgeRetrievalPublicationData,
    OperationalKnowledgeRetrievalPublicationInput,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject, SubjectKind
from atlas.modules.knowledge.adapters.retrieval_index_publication_memory import (
    InMemoryOperationalKnowledgeRetrievalPublicationPolicySource,
    InMemoryOperationalKnowledgeRetrievalPublicationRepository,
)
from atlas.modules.knowledge.adapters.retrieval_index_publication_postgres import (
    PostgreSQLOperationalKnowledgeRetrievalPublicationRepository,
)
from atlas.modules.knowledge.adapters.retrieval_index_publication_synthetic import (
    SyntheticOperationalKnowledgeRetrievalPublisher,
    UnavailableOperationalKnowledgeRetrievalPublisher,
)
from atlas.modules.knowledge.application.retrieval_index_publication import (
    OperationalKnowledgeRetrievalIndexPublicationService,
    build_development_operational_knowledge_retrieval_publication_policy,
)
from atlas.modules.knowledge.application.retrieval_index_publication_ports import (
    OperationalKnowledgeRetrievalPublicationError,
    OperationalKnowledgeRetrievalPublisher,
)
from atlas.modules.knowledge.domain.index_staging_validation import OperationalKnowledgeIndexRecord
from atlas.modules.knowledge.domain.retrieval_index_publication import (
    OperationalKnowledgeRetrievalPublicationInstruction,
    OperationalKnowledgeRetrievalPublicationPolicySnapshot,
    OperationalKnowledgeRetrievalPublicationReceipt,
    OperationalKnowledgeRetrievalPublicationRecord,
)


class RecordingRetrievalPublicationPermissionAuthorizer:
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
            raise OperationalKnowledgeRetrievalPublicationError(
                "operational_knowledge_retrieval_publication_permission_denied"
            )


class BlockingRetrievalPublisher(SyntheticOperationalKnowledgeRetrievalPublisher):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def publish(
        self, instruction: OperationalKnowledgeRetrievalPublicationInstruction
    ) -> OperationalKnowledgeRetrievalPublicationReceipt:
        self.started.set()
        await self.release.wait()
        return await super().publish(instruction)


class DriftingRetrievalPublisher(SyntheticOperationalKnowledgeRetrievalPublisher):
    async def publish(
        self, instruction: OperationalKnowledgeRetrievalPublicationInstruction
    ) -> OperationalKnowledgeRetrievalPublicationReceipt:
        receipt = await super().publish(instruction)
        return replace(receipt, index_staging_digest="f" * 64)


class StaticIndexSource:
    def __init__(self, record: OperationalKnowledgeIndexRecord) -> None:
        self.record = record

    async def source_for_retrieval_publication(
        self, *, index_staging_id: str
    ) -> OperationalKnowledgeIndexRecord | None:
        return self.record if self.record.index_staging_id == index_staging_id else None


async def publication_fixture(
    *,
    publisher: OperationalKnowledgeRetrievalPublisher | None = None,
    authorizer: RecordingRetrievalPublicationPermissionAuthorizer | None = None,
    index_override: OperationalKnowledgeIndexRecord | None = None,
) -> tuple[
    OperationalKnowledgeRetrievalIndexPublicationService,
    InMemoryOperationalKnowledgeRetrievalPublicationRepository,
    OperationalKnowledgeIndexRecord,
    OperationalKnowledgeRetrievalPublicationPolicySnapshot,
    AuthenticatedSubject,
    OperationalKnowledgeRetrievalPublisher,
    RecordingRetrievalPublicationPermissionAuthorizer,
    CollectingAuditSink,
]:
    index_service, _, embedding, index_policy, index_actor, *_ = await index_fixture()
    index = await create_index_stage(index_service, embedding, index_policy, index_actor)
    index = index_override or index
    policy = build_development_operational_knowledge_retrieval_publication_policy(
        organization_id=index.organization_id,
        environment_id=index.environment_id,
        issued_at=index.validated_at - timedelta(hours=1),
        expires_at=index.validated_at + timedelta(days=1),
        index_policy=index_policy,
    )
    resolved_publisher = publisher or SyntheticOperationalKnowledgeRetrievalPublisher()
    if isinstance(resolved_publisher, SyntheticOperationalKnowledgeRetrievalPublisher):
        resolved_publisher._clock = lambda: index.validated_at
    permission = authorizer or RecordingRetrievalPublicationPermissionAuthorizer()
    repository = InMemoryOperationalKnowledgeRetrievalPublicationRepository()
    audit = CollectingAuditSink()
    service = OperationalKnowledgeRetrievalIndexPublicationService(
        repository=repository,
        index_source=StaticIndexSource(index),
        policy_source=InMemoryOperationalKnowledgeRetrievalPublicationPolicySource((policy,)),
        permission_authorizer=permission,
        publisher=resolved_publisher,
        audit_sink=audit,
        environment_id=index.environment_id,
        clock=lambda: index.validated_at,
    )
    actor = target_session_operator("subject.knowledge-retrieval-publication-steward")
    return service, repository, index, policy, actor, resolved_publisher, permission, audit


async def create_publication(
    service: OperationalKnowledgeRetrievalIndexPublicationService,
    index: OperationalKnowledgeIndexRecord,
    policy: OperationalKnowledgeRetrievalPublicationPolicySnapshot,
    actor: AuthenticatedSubject,
    *,
    idempotency_key: str = "knowledge-retrieval-publication-001",
) -> OperationalKnowledgeRetrievalPublicationRecord:
    return await service.create(
        actor=actor,
        index_staging_id=index.index_staging_id,
        index_staging_digest=index.canonical_digest,
        publication_policy_id=policy.policy_id,
        publication_policy_digest=policy.canonical_digest,
        purpose="Atomically publish the governed protected retrieval index for authorized use.",
        policy_filtered_visibility_acknowledged=True,
        no_vector_store_disclosure_acknowledged=True,
        no_context_or_operational_authority_acknowledged=True,
        browser_session_id="session_knowledge_retrieval_publication_001",
        idempotency_key=idempotency_key,
        correlation_id="cor_knowledge_retrieval_publication",
    )


@pytest.mark.asyncio
async def test_retrieval_publication_rejects_non_human_actor() -> None:
    service, _, index, policy, actor, *_ = await publication_fixture()
    with pytest.raises(OperationalKnowledgeRetrievalPublicationError, match="human_required"):
        await create_publication(
            service,
            index,
            policy,
            replace(actor, kind=SubjectKind.SERVICE),
        )


@pytest.mark.asyncio
async def test_retrieval_publication_is_metadata_only_complete_and_idempotent() -> None:
    (
        service,
        repository,
        index,
        policy,
        actor,
        publisher,
        permission,
        audit,
    ) = await publication_fixture()
    record = await create_publication(service, index, policy, actor)
    repeated = await create_publication(service, index, policy, actor)
    replay = await service.get(
        actor=actor,
        publication_id=record.publication_id,
        browser_session_id="session_knowledge_retrieval_publication_001",
        correlation_id="cor_knowledge_retrieval_publication_read",
    )

    assert record.knowledge_published and record.retrieval_published
    assert record.index_staged and record.index_validated
    assert not record.model_context_available and not record.workflow_continued
    assert not record.execution_authorized and not record.infrastructure_mutation_performed
    assert repeated.reused and replay.reused
    assert isinstance(publisher, SyntheticOperationalKnowledgeRetrievalPublisher)
    assert len(publisher.calls) == 1
    assert await repository.get(publication_id=record.publication_id) == record
    persisted = OperationalKnowledgeRetrievalIndexPublicationService._normalize(asdict(record))
    assert isinstance(persisted, dict)
    restored = PostgreSQLOperationalKnowledgeRetrievalPublicationRepository._record_to_domain(
        persisted
    )
    assert restored == record
    assert len(permission.calls) == 3
    raw = asdict(record)
    response_data = OperationalKnowledgeRetrievalPublicationData.from_domain(record).model_dump()
    for forbidden in (
        "content",
        "excerpt",
        "chunk_coordinates",
        "point_ids",
        "collection_name",
        "alias_name",
        "vector_values",
        "payload",
        "filters",
        "query_results",
        "encryption_key",
    ):
        assert forbidden not in raw
        assert forbidden not in response_data
    for private_field in (
        "publication_steward_subject_digest",
        "browser_session_binding_digest",
        "upstream_accountable_subject_digests",
        "claim_id",
    ):
        assert private_field not in response_data
    assert [item.result_code for item in audit.records] == [
        "operational_knowledge_retrieval_publication_requested",
        "operational_knowledge_retrieval_publication_claimed",
        "operational_knowledge_retrieval_published",
        "operational_knowledge_retrieval_publication_read",
        "operational_knowledge_retrieval_publication_read",
    ]


@pytest.mark.asyncio
async def test_retrieval_publication_requires_separate_steward() -> None:
    service, repository, index, policy, *_ = await publication_fixture()
    actor = target_session_operator("subject.knowledge-index-steward")
    with pytest.raises(OperationalKnowledgeRetrievalPublicationError, match="separation_required"):
        await create_publication(service, index, policy, actor)
    assert (
        await repository.get_claim_by_index_staging(index_staging_id=index.index_staging_id) is None
    )


@pytest.mark.asyncio
async def test_retrieval_publication_permission_denial_precedes_claim() -> None:
    permission = RecordingRetrievalPublicationPermissionAuthorizer(deny=True)
    service, repository, index, policy, actor, publisher, *_ = await publication_fixture(
        authorizer=permission
    )
    with pytest.raises(OperationalKnowledgeRetrievalPublicationError, match="permission_denied"):
        await create_publication(service, index, policy, actor)
    assert isinstance(publisher, SyntheticOperationalKnowledgeRetrievalPublisher)
    assert not publisher.calls
    assert (
        await repository.get_claim_by_index_staging(index_staging_id=index.index_staging_id) is None
    )


@pytest.mark.asyncio
async def test_retrieval_publication_atomic_claim_blocks_concurrent_duplicate() -> None:
    blocker = BlockingRetrievalPublisher()
    service, repository, index, policy, actor, *_ = await publication_fixture(publisher=blocker)
    first = asyncio.create_task(create_publication(service, index, policy, actor))
    await blocker.started.wait()
    with pytest.raises(OperationalKnowledgeRetrievalPublicationError, match="already_claimed"):
        await create_publication(service, index, policy, actor)
    blocker.release.set()
    record = await first
    assert await repository.get(publication_id=record.publication_id) == record


@pytest.mark.asyncio
async def test_retrieval_publication_rejects_drifted_receipt_and_keeps_claim() -> None:
    service, repository, index, policy, actor, *_ = await publication_fixture(
        publisher=DriftingRetrievalPublisher()
    )
    with pytest.raises(OperationalKnowledgeRetrievalPublicationError, match="receipt_invalid"):
        await create_publication(service, index, policy, actor)
    assert await repository.get_claim_by_index_staging(index_staging_id=index.index_staging_id)
    with pytest.raises(OperationalKnowledgeRetrievalPublicationError, match="already_claimed"):
        await create_publication(service, index, policy, actor)


@pytest.mark.asyncio
async def test_production_retrieval_publisher_fails_closed_after_claim() -> None:
    service, repository, index, policy, actor, *_ = await publication_fixture(
        publisher=UnavailableOperationalKnowledgeRetrievalPublisher()
    )
    with pytest.raises(
        OperationalKnowledgeRetrievalPublicationError, match="publisher_unavailable"
    ):
        await create_publication(service, index, policy, actor)
    assert await repository.get_claim_by_index_staging(index_staging_id=index.index_staging_id)


@pytest.mark.asyncio
async def test_retrieval_publication_rejects_drifted_staging_lineage() -> None:
    base_service, _, base_index, base_policy, base_actor, *_ = await publication_fixture()
    del base_service, base_policy, base_actor
    drifted = replace(base_index, index_profile_digest="f" * 64)
    service, repository, index, policy, actor, *_ = await publication_fixture(
        index_override=drifted
    )
    with pytest.raises(OperationalKnowledgeRetrievalPublicationError, match="source_invalid"):
        await create_publication(service, index, policy, actor)
    assert (
        await repository.get_claim_by_index_staging(index_staging_id=index.index_staging_id) is None
    )


def test_retrieval_publication_persistence_contract_is_metadata_only() -> None:
    fields = OperationalKnowledgeRetrievalPublicationRecord.__dataclass_fields__
    for forbidden in (
        "content",
        "excerpt",
        "chunk_coordinates",
        "point_ids",
        "collection_name",
        "alias_name",
        "vector_values",
        "payload",
        "filters",
        "query_results",
        "encryption_key",
    ):
        assert forbidden not in fields
    assert hasattr(PostgreSQLOperationalKnowledgeRetrievalPublicationRepository, "claim")
    assert hasattr(PostgreSQLOperationalKnowledgeRetrievalPublicationRepository, "add")


def test_retrieval_publication_api_input_forbids_routing_and_query_parameters() -> None:
    payload = {
        "index_staging_digest": "a" * 64,
        "publication_policy_id": ("operational-knowledge-retrieval-publication-policy.development"),
        "publication_policy_digest": "b" * 64,
        "purpose": "Atomically publish the governed protected retrieval index for authorized use.",
        "acknowledged_policy_filtered_visibility": True,
        "acknowledged_no_vector_store_disclosure": True,
        "acknowledged_no_context_or_operational_authority": True,
    }
    assert OperationalKnowledgeRetrievalPublicationInput.model_validate(payload)
    for forbidden in (
        "steward_id",
        "content",
        "vector_values",
        "collection_name",
        "alias_name",
        "point_ids",
        "payload",
        "filters",
        "query",
        "model_context_enabled",
        "workflow_id",
    ):
        with pytest.raises(ValidationError):
            OperationalKnowledgeRetrievalPublicationInput.model_validate(
                {**payload, forbidden: "caller-selected"}
            )
