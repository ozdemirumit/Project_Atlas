from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.conversations.adapters import (
    InMemoryConversationRepository,
    UnavailableConversationRepository,
)
from atlas.modules.conversations.application import (
    ConversationAccessContext,
    ConversationOperationsError,
    ConversationService,
)
from atlas.modules.conversations.domain import (
    NO_EXECUTION_SAFETY_NOTICE,
    ConversationArtifactReference,
    ConversationAuthority,
    ConversationEvidenceReference,
    ConversationGenerationRequest,
    ConversationGenerationResult,
    ConversationScope,
    ConversationTurnStatus,
    OperationalConversation,
    canonical_digest,
)

NOW = datetime(2026, 8, 13, 10, 0, tzinfo=UTC)
SCOPE = ConversationScope("organization.atlas", "development", "site.local")
TARGET_ID = "asset.storage.lab.primary"


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []
        self.fail = False

    async def record(self, event: AuditRecord) -> None:
        if self.fail:
            raise RuntimeError("conversation audit unavailable")
        self.records.append(event)


class GroundedGenerator:
    def __init__(self) -> None:
        self.requests: list[ConversationGenerationRequest] = []
        self.fail = False
        self.mismatch_target = False

    async def generate(
        self, request: ConversationGenerationRequest
    ) -> ConversationGenerationResult:
        self.requests.append(request)
        if self.fail:
            raise RuntimeError("model unavailable")
        target_id = "asset.storage.lab.foreign" if self.mismatch_target else request.target_id
        evidence = (
            ConversationEvidenceReference(
                evidence_id="evidence.storage.health.1",
                citation="Storage health observation at 2026-08-13T10:00:00Z.",
                artifact_id="artifact.storage.health",
                artifact_version="3",
                source_type="storage_health_snapshot",
                source_reference="atlas://storage/health/1",
                observed_at=NOW,
            ),
        )
        artifacts = (
            ConversationArtifactReference(
                artifact_id="artifact.storage.health",
                artifact_version=3,
                artifact_type="storage-health",
            ),
        )
        authority = ConversationAuthority()
        payload = {
            "artifact_references": [item.canonical_value() for item in artifacts],
            "assumptions": ("The authorized observation represents the selected target.",),
            "authority": authority.canonical_value(),
            "confidence_basis": ("One current authorized health observation is available.",),
            "conversation_id": request.conversation_id,
            "evidence_references": [item.canonical_value() for item in evidence],
            "failure_code": None,
            "observed_at": request.requested_at.isoformat(),
            "owner_subject_id": request.owner_subject_id,
            "request_digest": request.request_digest,
            "safety_notice": NO_EXECUTION_SAFETY_NOTICE,
            "scope": request.scope.canonical_value(),
            "status": ConversationTurnStatus.COMPLETED.value,
            "target_id": target_id,
            "text": "The available evidence reports normal controller health.",
            "unknowns": ("No workload-path telemetry was included.",),
        }
        return ConversationGenerationResult(
            request_digest=request.request_digest,
            conversation_id=request.conversation_id,
            scope=request.scope,
            owner_subject_id=request.owner_subject_id,
            target_id=target_id,
            status=ConversationTurnStatus.COMPLETED,
            text="The available evidence reports normal controller health.",
            observed_at=request.requested_at,
            evidence_references=evidence,
            artifact_references=artifacts,
            assumptions=("The authorized observation represents the selected target.",),
            unknowns=("No workload-path telemetry was included.",),
            confidence_basis=("One current authorized health observation is available.",),
            failure_code=None,
            safety_notice=NO_EXECUTION_SAFETY_NOTICE,
            authority=authority,
            result_digest=canonical_digest(payload),
        )


def context(
    *,
    subject_id: str = "subject.operator",
    scope: ConversationScope = SCOPE,
    targets: frozenset[str] = frozenset({TARGET_ID}),
    requested_at: datetime = NOW,
) -> ConversationAccessContext:
    return ConversationAccessContext(
        subject_id=subject_id,
        role_ids=frozenset({"role.infrastructure-operator"}),
        actor_type="human",
        authentication_method="browser_session",
        assurance_level="aal2",
        scope=scope,
        authorized_target_ids=targets,
        correlation_id=f"correlation.{subject_id}",
        decision_id=f"decision.{subject_id}",
        generation_decision_id=f"decision.ai.{subject_id}",
        requested_at=requested_at,
    )


def fixture() -> tuple[
    ConversationService,
    InMemoryConversationRepository,
    GroundedGenerator,
    CollectingAuditSink,
]:
    repository = InMemoryConversationRepository()
    generator = GroundedGenerator()
    audit = CollectingAuditSink()
    return (
        ConversationService(repository=repository, generator=generator, audit_sink=audit),
        repository,
        generator,
        audit,
    )


async def create_conversation(
    service: ConversationService,
    *,
    access: ConversationAccessContext | None = None,
    key: str = "conversation-create-0001",
) -> OperationalConversation:
    return await service.create(
        title="Primary storage investigation",
        target_id=TARGET_ID,
        idempotency_key=key,
        context=access or context(),
    )


@pytest.mark.asyncio
async def test_create_is_scope_bound_non_durable_and_exactly_replayable() -> None:
    service, _, generator, audit = fixture()

    created = await create_conversation(service)
    replayed = await create_conversation(
        service, access=context(requested_at=NOW + timedelta(minutes=1))
    )

    assert replayed == created
    assert created.version == 1
    assert created.turns == ()
    assert created.scope == SCOPE
    assert created.owner_subject_id == "subject.operator"
    assert created.target_id == TARGET_ID
    assert created.durable is False
    assert created.canonical_digest == canonical_digest(created.digest_payload())
    assert generator.requests == []
    assert [record.result_code for record in audit.records] == [
        "conversation_create_authorized",
        "conversation_create_replayed",
    ]


@pytest.mark.asyncio
async def test_create_rejects_unknown_target_and_changed_idempotent_content() -> None:
    service, repository, _, _ = fixture()
    await create_conversation(service)

    with pytest.raises(ConversationOperationsError) as reused:
        await service.create(
            title="Changed title",
            target_id=TARGET_ID,
            idempotency_key="conversation-create-0001",
            context=context(),
        )
    assert reused.value.code == "conversation_idempotency_conflict"

    with pytest.raises(ConversationOperationsError) as unknown:
        await service.create(
            title="Unknown storage",
            target_id="asset.storage.lab.unknown",
            idempotency_key="conversation-create-0002",
            context=context(),
        )
    assert unknown.value.code == "conversation_target_unavailable"
    assert (
        len(
            await repository.list_owned(
                scope=SCOPE,
                owner_subject_id="subject.operator",
                authorized_target_ids=frozenset({TARGET_ID}),
                limit=10,
            )
        )
        == 1
    )


@pytest.mark.asyncio
async def test_append_creates_ordered_grounded_pair_with_zero_authority() -> None:
    service, _, generator, _ = fixture()
    created = await create_conversation(service)

    updated = await service.append_turn(
        conversation_id=created.conversation_id,
        question="What is the current controller health?",
        expected_version=created.version,
        idempotency_key="conversation-turn-0001",
        context=context(requested_at=NOW + timedelta(minutes=1)),
    )

    assert updated.version == 2
    assert [turn.ordinal for turn in updated.turns] == [1, 2]
    assert [turn.role.value for turn in updated.turns] == ["user", "assistant"]
    assert updated.turns[1].status is ConversationTurnStatus.COMPLETED
    assert updated.turns[1].evidence_references[0].artifact_version == "3"
    assert updated.turns[1].artifact_references[0].artifact_id == "artifact.storage.health"
    assert updated.turns[1].unknowns
    assert updated.turns[1].confidence_basis
    assert not any(updated.turns[1].authority.canonical_value().values())
    assert updated.turns[1].safety_notice == NO_EXECUTION_SAFETY_NOTICE
    assert updated.canonical_digest == canonical_digest(updated.digest_payload())
    assert len(generator.requests) == 1
    assert generator.requests[0].prior_turns == ()
    assert generator.requests[0].decision_id == "decision.ai.subject.operator"


@pytest.mark.asyncio
async def test_append_replay_precedes_version_check_and_does_not_regenerate() -> None:
    service, _, generator, _ = fixture()
    created = await create_conversation(service)
    appended = await service.append_turn(
        conversation_id=created.conversation_id,
        question="What is the current controller health?",
        expected_version=1,
        idempotency_key="conversation-turn-0001",
        context=context(requested_at=NOW + timedelta(minutes=1)),
    )
    await service.append_turn(
        conversation_id=created.conversation_id,
        question="What evidence is still missing?",
        expected_version=2,
        idempotency_key="conversation-turn-0002",
        context=context(requested_at=NOW + timedelta(minutes=2)),
    )

    replayed = await service.append_turn(
        conversation_id=created.conversation_id,
        question="What is the current controller health?",
        expected_version=1,
        idempotency_key="conversation-turn-0001",
        context=context(requested_at=NOW + timedelta(minutes=3)),
    )

    assert replayed == appended
    assert replayed.version == 2
    assert len(generator.requests) == 2
    assert generator.requests[1].prior_turns == appended.turns


@pytest.mark.asyncio
async def test_append_rejects_changed_replay_stale_version_and_closed_lifecycle() -> None:
    service, repository, _, _ = fixture()
    created = await create_conversation(service)
    updated = await service.append_turn(
        conversation_id=created.conversation_id,
        question="What is the current controller health?",
        expected_version=1,
        idempotency_key="conversation-turn-0001",
        context=context(requested_at=NOW + timedelta(minutes=1)),
    )

    with pytest.raises(ConversationOperationsError) as reused:
        await service.append_turn(
            conversation_id=created.conversation_id,
            question="Changed question",
            expected_version=1,
            idempotency_key="conversation-turn-0001",
            context=context(requested_at=NOW + timedelta(minutes=2)),
        )
    assert reused.value.code == "conversation_idempotency_conflict"

    with pytest.raises(ConversationOperationsError) as stale:
        await service.append_turn(
            conversation_id=created.conversation_id,
            question="A stale question",
            expected_version=1,
            idempotency_key="conversation-turn-stale",
            context=context(requested_at=NOW + timedelta(minutes=2)),
        )
    assert stale.value.code == "conversation_version_conflict"
    assert await repository.get_by_id(conversation_id=created.conversation_id) == updated


@pytest.mark.asyncio
async def test_get_and_list_do_not_disclose_foreign_owner_scope_or_target() -> None:
    service, _, _, audit = fixture()
    created = await create_conversation(service)
    foreign_scope = ConversationScope("organization.foreign", "development", "site.local")

    for access in (
        context(subject_id="subject.foreign"),
        context(scope=foreign_scope),
        context(targets=frozenset({"asset.storage.lab.secondary"})),
    ):
        with pytest.raises(ConversationOperationsError) as denied:
            await service.get(conversation_id=created.conversation_id, context=access)
        assert denied.value.code == "conversation_not_found"

    assert await service.list(context=context(subject_id="subject.foreign")) == ()
    assert all(
        created.conversation_id not in dict(record.target_metadata)
        for record in audit.records
        if record.outcome == "denied"
    )


@pytest.mark.asyncio
async def test_generator_unavailability_persists_explicit_failed_turn_without_claims() -> None:
    service, _, generator, audit = fixture()
    created = await create_conversation(service)
    generator.fail = True

    updated = await service.append_turn(
        conversation_id=created.conversation_id,
        question="Can this storage be restarted safely?",
        expected_version=1,
        idempotency_key="conversation-turn-failure",
        context=context(requested_at=NOW + timedelta(minutes=1)),
    )

    failed = updated.turns[-1]
    assert failed.status is ConversationTurnStatus.FAILED
    assert failed.failure_code == "conversation_generation_unavailable"
    assert failed.evidence_references == ()
    assert failed.artifact_references == ()
    assert failed.assumptions == ()
    assert failed.unknowns
    assert not any(failed.authority.canonical_value().values())
    assert audit.records[-1].result_code == "conversation_turn_failed"


@pytest.mark.asyncio
async def test_mismatched_generated_binding_fails_closed_without_mutation() -> None:
    service, repository, generator, audit = fixture()
    created = await create_conversation(service)
    generator.mismatch_target = True

    with pytest.raises(ConversationOperationsError) as malformed:
        await service.append_turn(
            conversation_id=created.conversation_id,
            question="Show target health.",
            expected_version=1,
            idempotency_key="conversation-turn-malformed",
            context=context(requested_at=NOW + timedelta(minutes=1)),
        )

    assert malformed.value.code == "conversation_generation_validation_failed"
    assert await repository.get_by_id(conversation_id=created.conversation_id) == created
    assert audit.records[-1].result_code == "conversation_generation_validation_failed"


@pytest.mark.asyncio
async def test_concurrent_appends_allow_only_one_expected_version_transition() -> None:
    service, repository, _, _ = fixture()
    created = await create_conversation(service)
    access = context(requested_at=NOW + timedelta(minutes=1))

    results = await asyncio.gather(
        service.append_turn(
            conversation_id=created.conversation_id,
            question="First concurrent question",
            expected_version=1,
            idempotency_key="conversation-turn-race-one",
            context=access,
        ),
        service.append_turn(
            conversation_id=created.conversation_id,
            question="Second concurrent question",
            expected_version=1,
            idempotency_key="conversation-turn-race-two",
            context=access,
        ),
        return_exceptions=True,
    )

    assert sum(not isinstance(result, Exception) for result in results) == 1
    error = next(result for result in results if isinstance(result, ConversationOperationsError))
    assert error.code == "conversation_version_conflict"
    stored = await repository.get_by_id(conversation_id=created.conversation_id)
    assert stored is not None and stored.version == 2 and len(stored.turns) == 2


@pytest.mark.asyncio
async def test_required_audit_failure_prevents_create_and_append_mutations() -> None:
    service, repository, _, audit = fixture()
    audit.fail = True
    with pytest.raises(RuntimeError, match="conversation audit unavailable"):
        await create_conversation(service)
    assert (
        await repository.list_owned(
            scope=SCOPE,
            owner_subject_id="subject.operator",
            authorized_target_ids=frozenset({TARGET_ID}),
            limit=10,
        )
        == ()
    )

    audit.fail = False
    created = await create_conversation(service, key="conversation-create-0002")
    audit.fail = True
    with pytest.raises(RuntimeError, match="conversation audit unavailable"):
        await service.append_turn(
            conversation_id=created.conversation_id,
            question="This mutation must not survive audit failure.",
            expected_version=1,
            idempotency_key="conversation-turn-audit-failure",
            context=context(requested_at=NOW + timedelta(minutes=1)),
        )
    assert await repository.get_by_id(conversation_id=created.conversation_id) == created


def test_domain_rejects_authority_and_digest_tampering() -> None:
    with pytest.raises(ValueError, match="cannot grant execution authority"):
        ConversationAuthority(infrastructure_execution_authorized=True)

    service, _, _, _ = fixture()
    created = asyncio.run(create_conversation(service))
    with pytest.raises(ValueError, match="canonical digest mismatch"):
        replace(created, canonical_digest="0" * 64)


@pytest.mark.asyncio
async def test_unavailable_repository_never_falls_back_to_memory() -> None:
    repository = UnavailableConversationRepository()

    assert repository.durable is False
    with pytest.raises(
        ConversationOperationsError,
        match="Durable conversation storage is not configured",
    ):
        await repository.list_owned(
            scope=SCOPE,
            owner_subject_id="subject.operator",
            authorized_target_ids=frozenset({TARGET_ID}),
            limit=10,
        )
