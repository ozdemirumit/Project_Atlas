from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta

import pytest
from pydantic import ValidationError
from test_package_acquisition import CollectingAuditSink
from test_publication_preparation import prepare, publication_preparation_fixture
from test_target_session import target_session_operator

from atlas.api.source_materialization_schemas import (
    OperationalKnowledgeSourceMaterializationInput,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.knowledge.adapters.source_materialization_memory import (
    InMemoryOperationalKnowledgeSourceMaterializationPolicySource,
    InMemoryOperationalKnowledgeSourceMaterializationRepository,
)
from atlas.modules.knowledge.adapters.source_materialization_postgres import (
    PostgreSQLOperationalKnowledgeSourceMaterializationRepository,
)
from atlas.modules.knowledge.adapters.source_materialization_synthetic import (
    SyntheticOperationalKnowledgeSourceMaterializer,
)
from atlas.modules.knowledge.application.source_materialization import (
    OperationalKnowledgeSourceMaterializationService,
    build_development_operational_knowledge_source_materialization_policy,
)
from atlas.modules.knowledge.application.source_materialization_ports import (
    OperationalKnowledgeSourceMaterializationError,
)
from atlas.modules.knowledge.domain.publication_preparation import (
    OperationalKnowledgePublicationPreparationRecord,
)
from atlas.modules.knowledge.domain.source_materialization import (
    OperationalKnowledgeSourceMaterializationInstruction,
    OperationalKnowledgeSourceMaterializationPolicySnapshot,
    OperationalKnowledgeSourceMaterializationReceipt,
    OperationalKnowledgeSourceMaterializationRecord,
)


class RecordingSourceMaterializationPermissionAuthorizer:
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
            raise OperationalKnowledgeSourceMaterializationError(
                "operational_knowledge_source_materialization_permission_denied"
            )


class BlockingSourceMaterializer(SyntheticOperationalKnowledgeSourceMaterializer):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def materialize(
        self, instruction: OperationalKnowledgeSourceMaterializationInstruction
    ) -> OperationalKnowledgeSourceMaterializationReceipt:
        self.started.set()
        await self.release.wait()
        return await super().materialize(instruction)


class DriftingSourceMaterializer(SyntheticOperationalKnowledgeSourceMaterializer):
    async def materialize(
        self, instruction: OperationalKnowledgeSourceMaterializationInstruction
    ) -> OperationalKnowledgeSourceMaterializationReceipt:
        receipt = await super().materialize(instruction)
        return replace(receipt, source_artifact_digest="f" * 64)


async def source_materialization_fixture(
    *,
    materializer: SyntheticOperationalKnowledgeSourceMaterializer | None = None,
    authorizer: RecordingSourceMaterializationPermissionAuthorizer | None = None,
) -> tuple[
    OperationalKnowledgeSourceMaterializationService,
    InMemoryOperationalKnowledgeSourceMaterializationRepository,
    OperationalKnowledgePublicationPreparationRecord,
    OperationalKnowledgeSourceMaterializationPolicySnapshot,
    AuthenticatedSubject,
    SyntheticOperationalKnowledgeSourceMaterializer,
    RecordingSourceMaterializationPermissionAuthorizer,
    CollectingAuditSink,
]:
    (
        preparation_service,
        _,
        final_service,
        resolution,
        preparation_policy,
        preparation_actor,
        *_,
    ) = await publication_preparation_fixture()
    preparation = await prepare(
        preparation_service, resolution, preparation_policy, preparation_actor
    )
    policy = build_development_operational_knowledge_source_materialization_policy(
        organization_id=preparation.organization_id,
        environment_id=preparation.environment_id,
        issued_at=preparation.prepared_at - timedelta(hours=1),
        expires_at=preparation.prepared_at + timedelta(days=1),
    )
    resolved_materializer = materializer or SyntheticOperationalKnowledgeSourceMaterializer()
    resolved_materializer._clock = lambda: preparation.prepared_at
    permission = authorizer or RecordingSourceMaterializationPermissionAuthorizer()
    repository = InMemoryOperationalKnowledgeSourceMaterializationRepository()
    audit = CollectingAuditSink()
    service = OperationalKnowledgeSourceMaterializationService(
        repository=repository,
        preparation_source=preparation_service,
        lineage_source=final_service,
        policy_source=InMemoryOperationalKnowledgeSourceMaterializationPolicySource((policy,)),
        permission_authorizer=permission,
        materializer=resolved_materializer,
        audit_sink=audit,
        environment_id=preparation.environment_id,
        clock=lambda: preparation.prepared_at,
    )
    actor = target_session_operator("subject.knowledge-materialization-steward")
    return (
        service,
        repository,
        preparation,
        policy,
        actor,
        resolved_materializer,
        permission,
        audit,
    )


async def materialize(
    service: OperationalKnowledgeSourceMaterializationService,
    preparation: OperationalKnowledgePublicationPreparationRecord,
    policy: OperationalKnowledgeSourceMaterializationPolicySnapshot,
    actor: AuthenticatedSubject,
    *,
    idempotency_key: str = "knowledge-source-materialization-001",
) -> OperationalKnowledgeSourceMaterializationRecord:
    return await service.create(
        actor=actor,
        preparation_id=preparation.preparation_id,
        preparation_digest=preparation.canonical_digest,
        materialization_policy_id=policy.policy_id,
        materialization_policy_digest=policy.canonical_digest,
        purpose="Materialize the exact approved source inside the protected knowledge boundary.",
        immutable_source_acknowledged=True,
        protected_boundary_acknowledged=True,
        no_chunking_or_operational_authority_acknowledged=True,
        browser_session_id="session_knowledge_source_materialization_001",
        idempotency_key=idempotency_key,
        correlation_id="cor_knowledge_source_materialization",
    )


@pytest.mark.asyncio
async def test_source_materialization_is_metadata_only_immutable_and_idempotent() -> None:
    (
        service,
        repository,
        preparation,
        policy,
        actor,
        materializer,
        permission,
        audit,
    ) = await source_materialization_fixture()
    record = await materialize(service, preparation, policy, actor)
    repeated = await materialize(service, preparation, policy, actor)
    replay = await service.get(
        actor=actor,
        materialization_id=record.materialization_id,
        browser_session_id="session_knowledge_source_materialization_001",
        correlation_id="cor_knowledge_source_materialization_read",
    )

    assert record.source_materialized and record.publication_prepared
    assert not record.chunks_created and not record.embeddings_created
    assert not record.index_staged and not record.index_validated
    assert not record.knowledge_published and not record.retrieval_published
    assert not record.workflow_continued and not record.execution_authorized
    assert repeated.reused and replay.reused and len(materializer.calls) == 1
    assert await repository.get(materialization_id=record.materialization_id) == record
    assert len(permission.calls) == 3
    raw = asdict(record)
    for forbidden in ("content", "excerpt", "source_coordinate", "encryption_key", "embedding"):
        assert forbidden not in raw
    assert [item.result_code for item in audit.records] == [
        "operational_knowledge_source_materialization_requested",
        "operational_knowledge_source_materialization_claimed",
        "operational_knowledge_source_materialization_recorded",
        "operational_knowledge_source_materialization_read",
        "operational_knowledge_source_materialization_read",
    ]


@pytest.mark.asyncio
async def test_source_materialization_requires_separate_steward() -> None:
    service, repository, preparation, policy, *_ = await source_materialization_fixture()
    actor = target_session_operator("subject.knowledge-publication-steward")
    with pytest.raises(OperationalKnowledgeSourceMaterializationError, match="separation_required"):
        await materialize(service, preparation, policy, actor)
    assert (
        await repository.get_claim_by_preparation(preparation_id=preparation.preparation_id) is None
    )


@pytest.mark.asyncio
async def test_source_materialization_permission_denial_precedes_claim() -> None:
    permission = RecordingSourceMaterializationPermissionAuthorizer(deny=True)
    (
        service,
        repository,
        preparation,
        policy,
        actor,
        materializer,
        *_,
    ) = await source_materialization_fixture(authorizer=permission)
    with pytest.raises(OperationalKnowledgeSourceMaterializationError, match="permission_denied"):
        await materialize(service, preparation, policy, actor)
    assert not materializer.calls
    assert (
        await repository.get_claim_by_preparation(preparation_id=preparation.preparation_id) is None
    )


@pytest.mark.asyncio
async def test_source_materialization_atomic_claim_blocks_concurrent_duplicate() -> None:
    blocker = BlockingSourceMaterializer()
    service, repository, preparation, policy, actor, *_ = await source_materialization_fixture(
        materializer=blocker
    )
    first = asyncio.create_task(materialize(service, preparation, policy, actor))
    await blocker.started.wait()
    with pytest.raises(OperationalKnowledgeSourceMaterializationError, match="already_claimed"):
        await materialize(service, preparation, policy, actor)
    blocker.release.set()
    record = await first
    assert await repository.get(materialization_id=record.materialization_id) == record


@pytest.mark.asyncio
async def test_source_materialization_rejects_drifted_receipt_and_keeps_claim() -> None:
    service, repository, preparation, policy, actor, *_ = await source_materialization_fixture(
        materializer=DriftingSourceMaterializer()
    )
    with pytest.raises(OperationalKnowledgeSourceMaterializationError, match="receipt_invalid"):
        await materialize(service, preparation, policy, actor)
    assert await repository.get_claim_by_preparation(preparation_id=preparation.preparation_id)
    with pytest.raises(OperationalKnowledgeSourceMaterializationError, match="already_claimed"):
        await materialize(service, preparation, policy, actor)


def test_source_materialization_postgres_mapping_is_metadata_only() -> None:
    fields = OperationalKnowledgeSourceMaterializationRecord.__dataclass_fields__
    for forbidden in ("content", "excerpt", "source_coordinate", "encryption_key", "embedding"):
        assert forbidden not in fields
    assert hasattr(PostgreSQLOperationalKnowledgeSourceMaterializationRepository, "claim")
    assert hasattr(PostgreSQLOperationalKnowledgeSourceMaterializationRepository, "add")


def test_source_materialization_api_input_forbids_content_coordinates_and_profiles() -> None:
    payload = {
        "publication_preparation_digest": "a" * 64,
        "materialization_policy_id": (
            "operational-knowledge-source-materialization-policy.development"
        ),
        "materialization_policy_digest": "b" * 64,
        "purpose": "Materialize the exact approved source inside the protected knowledge boundary.",
        "acknowledged_immutable_approved_source": True,
        "acknowledged_protected_content_boundary": True,
        "acknowledged_no_chunking_or_operational_authority": True,
    }
    assert OperationalKnowledgeSourceMaterializationInput.model_validate(payload)
    for forbidden in (
        "steward_id",
        "content",
        "source_coordinate",
        "canonicalization_profile_id",
        "index_id",
    ):
        with pytest.raises(ValidationError):
            OperationalKnowledgeSourceMaterializationInput.model_validate(
                {**payload, forbidden: "caller-selected"}
            )
