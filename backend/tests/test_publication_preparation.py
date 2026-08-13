from __future__ import annotations

import asyncio
from dataclasses import asdict, replace
from datetime import timedelta

import pytest
from pydantic import ValidationError
from test_final_resolution import final_resolution_fixture, resolve
from test_package_acquisition import CollectingAuditSink
from test_protected_inspection import domain_reviewer
from test_target_session import development_target_session_operator, target_session_operator

from atlas.api.publication_preparation_schemas import (
    OperationalKnowledgePublicationPreparationInput,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.knowledge.adapters.publication_preparation_memory import (
    InMemoryOperationalKnowledgePublicationPreparationPolicySource,
    InMemoryOperationalKnowledgePublicationPreparationRepository,
)
from atlas.modules.knowledge.adapters.publication_preparation_postgres import (
    PostgreSQLOperationalKnowledgePublicationPreparationRepository,
)
from atlas.modules.knowledge.adapters.publication_preparation_synthetic import (
    SyntheticOperationalKnowledgePublicationPreparer,
)
from atlas.modules.knowledge.application.final_resolution import (
    OperationalKnowledgeFinalResolutionService,
)
from atlas.modules.knowledge.application.publication_preparation import (
    OperationalKnowledgePublicationPreparationService,
    build_development_operational_knowledge_publication_preparation_policy,
)
from atlas.modules.knowledge.application.publication_preparation_ports import (
    OperationalKnowledgePublicationPreparationError,
)
from atlas.modules.knowledge.domain.final_resolution import (
    OperationalKnowledgeFinalResolutionRecord,
)
from atlas.modules.knowledge.domain.publication_preparation import (
    OperationalKnowledgePublicationPreparationInstruction,
    OperationalKnowledgePublicationPreparationPolicySnapshot,
    OperationalKnowledgePublicationPreparationReceipt,
    OperationalKnowledgePublicationPreparationRecord,
)


class RecordingPublicationPreparationPermissionAuthorizer:
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
            raise OperationalKnowledgePublicationPreparationError(
                "operational_knowledge_publication_preparation_permission_denied"
            )


class BlockingPublicationPreparer(SyntheticOperationalKnowledgePublicationPreparer):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def prepare(
        self, instruction: OperationalKnowledgePublicationPreparationInstruction
    ) -> OperationalKnowledgePublicationPreparationReceipt:
        self.started.set()
        await self.release.wait()
        return await super().prepare(instruction)


class DriftingPublicationPreparer(SyntheticOperationalKnowledgePublicationPreparer):
    async def prepare(
        self, instruction: OperationalKnowledgePublicationPreparationInstruction
    ) -> OperationalKnowledgePublicationPreparationReceipt:
        receipt = await super().prepare(instruction)
        return replace(receipt, source_artifact_digest="f" * 64)


async def publication_preparation_fixture(
    *,
    final_disposition: str = "final-resolution.approved",
    preparer: SyntheticOperationalKnowledgePublicationPreparer | None = None,
    authorizer: RecordingPublicationPreparationPermissionAuthorizer | None = None,
) -> tuple[
    OperationalKnowledgePublicationPreparationService,
    InMemoryOperationalKnowledgePublicationPreparationRepository,
    OperationalKnowledgeFinalResolutionService,
    OperationalKnowledgeFinalResolutionRecord,
    OperationalKnowledgePublicationPreparationPolicySnapshot,
    AuthenticatedSubject,
    SyntheticOperationalKnowledgePublicationPreparer,
    RecordingPublicationPreparationPermissionAuthorizer,
    CollectingAuditSink,
]:
    final_service, _, source, final_policy, final_actor, *_ = await final_resolution_fixture()
    resolution = await resolve(
        final_service,
        source,
        final_policy,
        final_actor,
        disposition_code=final_disposition,
    )
    policy = build_development_operational_knowledge_publication_preparation_policy(
        organization_id=resolution.organization_id,
        environment_id=resolution.environment_id,
        issued_at=resolution.resolved_at - timedelta(hours=1),
        expires_at=resolution.resolved_at + timedelta(days=1),
    )
    resolved_preparer = preparer or SyntheticOperationalKnowledgePublicationPreparer()
    resolved_preparer._clock = lambda: resolution.resolved_at
    permission = authorizer or RecordingPublicationPreparationPermissionAuthorizer()
    repository = InMemoryOperationalKnowledgePublicationPreparationRepository()
    audit = CollectingAuditSink()
    service = OperationalKnowledgePublicationPreparationService(
        repository=repository,
        source=final_service,
        policy_source=InMemoryOperationalKnowledgePublicationPreparationPolicySource((policy,)),
        permission_authorizer=permission,
        preparer=resolved_preparer,
        audit_sink=audit,
        environment_id=resolution.environment_id,
        clock=lambda: resolution.resolved_at,
    )
    actor = development_target_session_operator("subject.knowledge-publication-steward")
    return (
        service,
        repository,
        final_service,
        resolution,
        policy,
        actor,
        resolved_preparer,
        permission,
        audit,
    )


async def prepare(
    service: OperationalKnowledgePublicationPreparationService,
    resolution: OperationalKnowledgeFinalResolutionRecord,
    policy: OperationalKnowledgePublicationPreparationPolicySnapshot,
    actor: AuthenticatedSubject,
    *,
    idempotency_key: str = "knowledge-publication-preparation-001",
) -> OperationalKnowledgePublicationPreparationRecord:
    return await service.create(
        actor=actor,
        resolution_id=resolution.resolution_id,
        resolution_digest=resolution.canonical_digest,
        preparation_policy_id=policy.policy_id,
        preparation_policy_digest=policy.canonical_digest,
        purpose="Prepare immutable metadata for the exact approved knowledge generation.",
        immutable_generation_acknowledged=True,
        metadata_only_acknowledged=True,
        no_processing_or_operational_authority_acknowledged=True,
        browser_session_id="session_knowledge_publication_preparation_001",
        idempotency_key=idempotency_key,
        correlation_id="cor_knowledge_publication_preparation",
    )


@pytest.mark.asyncio
async def test_publication_preparation_accepts_development_password_and_is_immutable() -> None:
    (
        service,
        repository,
        _,
        resolution,
        policy,
        actor,
        preparer,
        permission,
        audit,
    ) = await publication_preparation_fixture()
    assert actor.authentication_method is AuthenticationMethod.DEVELOPMENT
    assert actor.assurance_level is AssuranceLevel.DEVELOPMENT
    record = await prepare(service, resolution, policy, actor)
    repeated = await prepare(service, resolution, policy, actor)
    replay = await service.get(
        actor=actor,
        preparation_id=record.preparation_id,
        browser_session_id="session_knowledge_publication_preparation_001",
        correlation_id="cor_knowledge_publication_preparation_read",
    )

    assert record.knowledge_approved and record.publication_ready and record.publication_prepared
    assert not record.chunks_created and not record.embeddings_created
    assert not record.index_staged and not record.index_validated
    assert not record.knowledge_published and not record.retrieval_published
    assert not record.workflow_continued and not record.execution_authorized
    assert repeated.reused and replay.reused and len(preparer.calls) == 1
    assert await repository.get(preparation_id=record.preparation_id) == record
    assert len(permission.calls) == 3
    raw = asdict(record)
    for forbidden in ("content", "title", "artifact_location", "raw_identity", "embedding"):
        assert forbidden not in raw
    assert [item.result_code for item in audit.records] == [
        "operational_knowledge_publication_preparation_requested",
        "operational_knowledge_publication_preparation_claimed",
        "operational_knowledge_publication_preparation_recorded",
        "operational_knowledge_publication_preparation_read",
        "operational_knowledge_publication_preparation_read",
    ]


@pytest.mark.asyncio
async def test_publication_preparation_rejects_non_human_actor() -> None:
    service, repository, _, resolution, policy, actor, *_ = await publication_preparation_fixture()
    service_actor = replace(
        actor,
        kind=SubjectKind.SERVICE,
        authentication_method=AuthenticationMethod.WORKLOAD_TOKEN,
    )

    with pytest.raises(OperationalKnowledgePublicationPreparationError, match="human_required"):
        await prepare(service, resolution, policy, service_actor)

    assert await repository.get_claim_by_resolution(resolution_id=resolution.resolution_id) is None


@pytest.mark.asyncio
async def test_publication_preparation_requires_approved_final_resolution() -> None:
    (
        service,
        repository,
        _,
        resolution,
        policy,
        actor,
        preparer,
        *_,
    ) = await publication_preparation_fixture(final_disposition="final-resolution.rejected")
    with pytest.raises(OperationalKnowledgePublicationPreparationError, match="source_invalid"):
        await prepare(service, resolution, policy, actor)
    assert not preparer.calls
    assert await repository.get_claim_by_resolution(resolution_id=resolution.resolution_id) is None


@pytest.mark.asyncio
@pytest.mark.parametrize("identity", ["approver", "curator", "reviewer"])
async def test_publication_preparation_requires_separate_steward(identity: str) -> None:
    (
        service,
        repository,
        final_service,
        resolution,
        policy,
        _publication_actor,
        preparer,
        *_,
    ) = await publication_preparation_fixture()
    _, _, _, draft = await final_service.publication_preparation_source(
        resolution_id=resolution.resolution_id
    )
    actor = {
        "approver": target_session_operator("subject.knowledge-final-approver"),
        "curator": target_session_operator(draft.curated_by),
        "reviewer": domain_reviewer(),
    }[identity]
    with pytest.raises(
        OperationalKnowledgePublicationPreparationError, match="separation_required"
    ):
        await prepare(service, resolution, policy, actor)
    assert not preparer.calls
    assert await repository.get_claim_by_resolution(resolution_id=resolution.resolution_id) is None


@pytest.mark.asyncio
async def test_publication_preparation_permission_denial_precedes_claim() -> None:
    permission = RecordingPublicationPreparationPermissionAuthorizer(deny=True)
    (
        service,
        repository,
        _,
        resolution,
        policy,
        actor,
        preparer,
        *_,
    ) = await publication_preparation_fixture(authorizer=permission)
    with pytest.raises(OperationalKnowledgePublicationPreparationError, match="permission_denied"):
        await prepare(service, resolution, policy, actor)
    assert not preparer.calls
    assert await repository.get_claim_by_resolution(resolution_id=resolution.resolution_id) is None


@pytest.mark.asyncio
async def test_publication_preparation_atomic_claim_blocks_concurrent_duplicate() -> None:
    blocker = BlockingPublicationPreparer()
    service, repository, _, resolution, policy, actor, *_ = await publication_preparation_fixture(
        preparer=blocker
    )
    first = asyncio.create_task(prepare(service, resolution, policy, actor))
    await blocker.started.wait()
    with pytest.raises(OperationalKnowledgePublicationPreparationError, match="already_claimed"):
        await prepare(service, resolution, policy, actor)
    blocker.release.set()
    record = await first
    assert await repository.get(preparation_id=record.preparation_id) == record


@pytest.mark.asyncio
async def test_publication_preparation_rejects_drifted_receipt_and_keeps_claim() -> None:
    service, repository, _, resolution, policy, actor, *_ = await publication_preparation_fixture(
        preparer=DriftingPublicationPreparer()
    )
    with pytest.raises(OperationalKnowledgePublicationPreparationError, match="receipt_invalid"):
        await prepare(service, resolution, policy, actor)
    assert await repository.get_claim_by_resolution(resolution_id=resolution.resolution_id)
    with pytest.raises(OperationalKnowledgePublicationPreparationError, match="already_claimed"):
        await prepare(service, resolution, policy, actor)


def test_publication_preparation_postgres_mapping_is_metadata_only() -> None:
    fields = OperationalKnowledgePublicationPreparationRecord.__dataclass_fields__
    for forbidden in ("content", "title", "artifact_location", "raw_identity", "embedding"):
        assert forbidden not in fields
    assert hasattr(PostgreSQLOperationalKnowledgePublicationPreparationRepository, "claim")
    assert hasattr(PostgreSQLOperationalKnowledgePublicationPreparationRepository, "add")


def test_publication_preparation_api_input_forbids_identity_content_and_authority() -> None:
    payload = {
        "final_resolution_digest": "a" * 64,
        "preparation_policy_id": (
            "operational-knowledge-publication-preparation-policy.development"
        ),
        "preparation_policy_digest": "b" * 64,
        "purpose": "Prepare immutable metadata for the exact approved knowledge generation.",
        "acknowledged_immutable_approved_generation": True,
        "acknowledged_metadata_only_preparation": True,
        "acknowledged_no_processing_or_operational_authority": True,
    }
    assert OperationalKnowledgePublicationPreparationInput.model_validate(payload)
    for forbidden in (
        "steward_id",
        "content",
        "chunking_profile_id",
        "index_id",
        "publication_prepared",
    ):
        with pytest.raises(ValidationError):
            OperationalKnowledgePublicationPreparationInput.model_validate(
                {**payload, forbidden: "caller-selected"}
            )
