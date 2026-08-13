from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from sqlalchemy import Table
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from atlas.core.persistence.models import (
    OperationalConversationIdempotencyModel,
    OperationalConversationModel,
    OperationalConversationTurnModel,
)
from atlas.modules.conversations.adapters.postgres import PostgreSQLConversationRepository
from atlas.modules.conversations.application.ports import ConversationMutationStatus
from atlas.modules.conversations.domain.models import (
    NO_EXECUTION_SAFETY_NOTICE,
    ConversationArtifactReference,
    ConversationAuthority,
    ConversationEvidenceReference,
    ConversationLifecycle,
    ConversationScope,
    ConversationTurn,
    ConversationTurnRole,
    ConversationTurnStatus,
    OperationalConversation,
    canonical_digest,
)

NOW = datetime(2026, 8, 13, 7, 0, tzinfo=UTC)
SCOPE = ConversationScope("organization.acme", "environment.production", "site.istanbul")


class _ScalarResult:
    def __init__(self, values: Iterable[object]) -> None:
        self._values = list(values)

    def all(self) -> list[object]:
        return self._values


class _RowcountResult:
    rowcount = 1


class _FakeSession:
    def __init__(
        self,
        *,
        scalar_values: Iterable[object | None] = (),
        scalar_batches: Iterable[Iterable[object]] = (),
        records: dict[tuple[type[object], object], object] | None = None,
    ) -> None:
        self.scalar_values = list(scalar_values)
        self.scalar_batches = [list(batch) for batch in scalar_batches]
        self.records = records or {}
        self.added: list[object] = []
        self.statements: list[object] = []
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        return None

    async def scalar(self, statement: object) -> object | None:
        self.statements.append(statement)
        return self.scalar_values.pop(0)

    async def scalars(self, statement: object) -> _ScalarResult:
        self.statements.append(statement)
        return _ScalarResult(self.scalar_batches.pop(0))

    async def get(self, entity: type[object], identifier: object) -> object | None:
        return self.records.get((entity, identifier))

    def add(self, instance: object) -> None:
        self.added.append(instance)

    def add_all(self, instances: Iterable[object]) -> None:
        self.added.extend(instances)

    async def execute(self, statement: object) -> _RowcountResult:
        self.statements.append(statement)
        return _RowcountResult()

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def _repository(session: _FakeSession) -> PostgreSQLConversationRepository:
    def factory() -> AsyncSession:
        return cast(AsyncSession, session)

    return PostgreSQLConversationRepository(
        engine=cast(AsyncEngine, object()), session_factory=factory
    )


def _turn(
    *, ordinal: int, role: ConversationTurnRole, status: ConversationTurnStatus
) -> ConversationTurn:
    evidence = (
        (
            ConversationEvidenceReference(
                evidence_id="evidence.storage.health",
                citation="Controller pair reports healthy redundancy.",
                artifact_id="artifact.health.snapshot",
                artifact_version="3",
                source_type="storage_health_snapshot",
                source_reference="atlas://storage/health/1",
                observed_at=NOW,
            ),
        )
        if role is ConversationTurnRole.ASSISTANT and status is ConversationTurnStatus.COMPLETED
        else ()
    )
    artifacts = (
        (
            ConversationArtifactReference(
                artifact_id="artifact.health.snapshot",
                artifact_version=3,
                artifact_type="health_snapshot",
            ),
        )
        if evidence
        else ()
    )
    assumptions: tuple[str, ...] = ()
    unknowns = (
        ("Current fabric path telemetry is unavailable.",)
        if status is not ConversationTurnStatus.COMPLETED
        else ()
    )
    confidence_basis = (
        ("Current governed health evidence supports this answer.",)
        if role is ConversationTurnRole.ASSISTANT
        else ()
    )
    failure_code = "generation_unavailable" if status is ConversationTurnStatus.FAILED else None
    text = (
        "What is the current controller health?"
        if role is ConversationTurnRole.USER
        else "The controller pair is healthy based on the current governed evidence."
    )
    authority = ConversationAuthority()
    observed_at = NOW + timedelta(minutes=ordinal)
    digest_payload: dict[str, object] = {
        "artifact_references": [item.canonical_value() for item in artifacts],
        "assumptions": assumptions,
        "authority": authority.canonical_value(),
        "confidence_basis": confidence_basis,
        "evidence_references": [item.canonical_value() for item in evidence],
        "failure_code": failure_code,
        "observed_at": observed_at.isoformat(),
        "ordinal": ordinal,
        "role": role.value,
        "safety_notice": NO_EXECUTION_SAFETY_NOTICE,
        "status": status.value,
        "text": text,
        "turn_id": f"turn.{ordinal}",
        "unknowns": unknowns,
    }
    return ConversationTurn(
        turn_id=f"turn.{ordinal}",
        ordinal=ordinal,
        role=role,
        status=status,
        text=text,
        observed_at=observed_at,
        evidence_references=evidence,
        artifact_references=artifacts,
        assumptions=assumptions,
        unknowns=unknowns,
        confidence_basis=confidence_basis,
        failure_code=failure_code,
        safety_notice=NO_EXECUTION_SAFETY_NOTICE,
        authority=authority,
        canonical_digest=canonical_digest(digest_payload),
    )


def _conversation(*, turns: tuple[ConversationTurn, ...] = ()) -> OperationalConversation:
    version = 1 + len(turns) // 2
    updated_at = NOW + timedelta(minutes=len(turns))
    digest_payload: dict[str, object] = {
        "conversation_id": "conversation.storage.001",
        "created_at": NOW.isoformat(),
        "created_by": "subject.operator",
        "durable": True,
        "lifecycle": ConversationLifecycle.OPEN.value,
        "owner_subject_id": "subject.operator",
        "scope": SCOPE.canonical_value(),
        "target_id": "storage.array.001",
        "target_type": "storage",
        "title": "Controller health investigation",
        "turn_digests": [turn.canonical_digest for turn in turns],
        "updated_at": updated_at.isoformat(),
        "updated_by": "subject.operator",
        "version": version,
    }
    return OperationalConversation(
        conversation_id="conversation.storage.001",
        version=version,
        lifecycle=ConversationLifecycle.OPEN,
        title="Controller health investigation",
        scope=SCOPE,
        owner_subject_id="subject.operator",
        target_id="storage.array.001",
        target_type="storage",
        created_by="subject.operator",
        updated_by="subject.operator",
        created_at=NOW,
        updated_at=updated_at,
        durable=True,
        turns=turns,
        canonical_digest=canonical_digest(digest_payload),
    )


def _appended_conversation() -> OperationalConversation:
    return _conversation(
        turns=(
            _turn(
                ordinal=1,
                role=ConversationTurnRole.USER,
                status=ConversationTurnStatus.COMPLETED,
            ),
            _turn(
                ordinal=2,
                role=ConversationTurnRole.ASSISTANT,
                status=ConversationTurnStatus.COMPLETED,
            ),
        )
    )


def _twice_appended_conversation() -> OperationalConversation:
    return _conversation(
        turns=(
            _turn(
                ordinal=1,
                role=ConversationTurnRole.USER,
                status=ConversationTurnStatus.COMPLETED,
            ),
            _turn(
                ordinal=2,
                role=ConversationTurnRole.ASSISTANT,
                status=ConversationTurnStatus.COMPLETED,
            ),
            _turn(
                ordinal=3,
                role=ConversationTurnRole.USER,
                status=ConversationTurnStatus.COMPLETED,
            ),
            _turn(
                ordinal=4,
                role=ConversationTurnRole.ASSISTANT,
                status=ConversationTurnStatus.COMPLETED,
            ),
        )
    )


def test_models_preserve_scope_order_and_append_only_foreign_keys() -> None:
    conversation_columns = OperationalConversationModel.__table__.columns
    assert {
        "organization_id",
        "environment_id",
        "site_id",
        "owner_subject_id",
        "version",
        "payload",
    } <= set(conversation_columns.keys())

    turn_table = cast(Table, OperationalConversationTurnModel.__table__)
    turn_constraints = {constraint.name for constraint in turn_table.constraints}
    assert "uq_operational_conversation_turn_ordinal" in turn_constraints
    turn_foreign_key = next(iter(OperationalConversationTurnModel.__table__.foreign_keys))
    assert turn_foreign_key.target_fullname == "operational_conversations.conversation_id"
    assert turn_foreign_key.ondelete is None

    idempotency_table = cast(Table, OperationalConversationIdempotencyModel.__table__)
    idempotency_constraints = {constraint.name for constraint in idempotency_table.constraints}
    assert "uq_operational_conversation_operation_scope_idem" in idempotency_constraints
    assert not hasattr(PostgreSQLConversationRepository, "delete")


def test_canonical_payload_round_trip_restores_ordered_turns() -> None:
    record = _appended_conversation()
    model = PostgreSQLConversationRepository._conversation_model(record)
    turn_models = tuple(
        PostgreSQLConversationRepository._turn_model(record.conversation_id, turn)
        for turn in record.turns
    )

    assert "turns" not in model.payload
    restored = PostgreSQLConversationRepository._to_domain(
        model.payload,
        tuple(
            PostgreSQLConversationRepository._turn_to_domain(turn_model.payload)
            for turn_model in turn_models
        ),
    )
    assert restored == record
    assert tuple(turn.ordinal for turn in restored.turns) == (1, 2)


@pytest.mark.asyncio
async def test_create_persists_aggregate_and_replays_only_exact_request() -> None:
    record = _conversation()
    created_session = _FakeSession(scalar_values=(None,))
    created = await _repository(created_session).create(
        record,
        idempotency_key="conversation-create-001",
        request_fingerprint="request-fingerprint-create",
    )

    assert created.status is ConversationMutationStatus.CREATED
    assert created.conversation == record
    assert created_session.commits == 1
    assert [type(item) for item in created_session.added] == [
        OperationalConversationModel,
        OperationalConversationIdempotencyModel,
    ]

    claim = cast(OperationalConversationIdempotencyModel, created_session.added[1])
    replay_session = _FakeSession(scalar_values=(claim,))
    replay = await _repository(replay_session).create(
        record,
        idempotency_key="conversation-create-001",
        request_fingerprint="request-fingerprint-create",
    )
    assert replay.status is ConversationMutationStatus.REPLAY
    assert replay.conversation == record

    conflict_session = _FakeSession(scalar_values=(claim,))
    conflict = await _repository(conflict_session).create(
        record,
        idempotency_key="conversation-create-001",
        request_fingerprint="different-request-fingerprint",
    )
    assert conflict.status is ConversationMutationStatus.IDEMPOTENCY_CONFLICT
    assert conflict.conversation == record

    lookup = await _repository(_FakeSession(scalar_values=(claim,))).get_create_request(
        owner_subject_id=record.owner_subject_id,
        idempotency_key="conversation-create-001",
    )
    assert lookup is not None
    assert lookup.request_fingerprint == "request-fingerprint-create"
    assert lookup.conversation == record


@pytest.mark.asyncio
async def test_append_is_atomic_versioned_and_replayable() -> None:
    current = _conversation()
    candidate = _appended_conversation()
    current_model = PostgreSQLConversationRepository._conversation_model(current)
    append_session = _FakeSession(
        scalar_values=(None, current_model, None),
        scalar_batches=((),),
    )
    result = await _repository(append_session).append(
        candidate,
        expected_version=1,
        idempotency_key="conversation-append-001",
        request_fingerprint="request-fingerprint-append",
    )

    assert result.status is ConversationMutationStatus.CREATED
    assert result.conversation == candidate
    assert append_session.commits == 1
    assert [type(item) for item in append_session.added] == [
        OperationalConversationTurnModel,
        OperationalConversationTurnModel,
        OperationalConversationIdempotencyModel,
    ]

    claim = cast(OperationalConversationIdempotencyModel, append_session.added[-1])
    replay_session = _FakeSession(scalar_values=(claim,))
    replay = await _repository(replay_session).append(
        candidate,
        expected_version=1,
        idempotency_key="conversation-append-001",
        request_fingerprint="request-fingerprint-append",
    )
    assert replay.status is ConversationMutationStatus.REPLAY
    assert replay.conversation == candidate

    lookup = await _repository(_FakeSession(scalar_values=(claim,))).get_append_request(
        conversation_id=candidate.conversation_id,
        idempotency_key="conversation-append-001",
    )
    assert lookup is not None
    assert lookup.request_fingerprint == "request-fingerprint-append"
    assert lookup.conversation == candidate


@pytest.mark.asyncio
async def test_append_replay_returns_exact_historical_aggregate_after_later_appends() -> None:
    first_result = _appended_conversation()
    later_result = _twice_appended_conversation()
    claim = PostgreSQLConversationRepository._idempotency_model(
        operation="append",
        scope_id=first_result.conversation_id,
        idempotency_key="conversation-append-historical",
        request_fingerprint="request-fingerprint-historical",
        record=first_result,
        appended_turns=first_result.turns[-2:],
    )
    latest_model = PostgreSQLConversationRepository._conversation_model(later_result)
    latest_turn_models = tuple(
        PostgreSQLConversationRepository._turn_model(later_result.conversation_id, turn)
        for turn in later_result.turns
    )
    session = _FakeSession(
        scalar_values=(claim,),
        scalar_batches=(latest_turn_models,),
        records={(OperationalConversationModel, later_result.conversation_id): latest_model},
    )

    replay = await _repository(session).append(
        first_result,
        expected_version=1,
        idempotency_key="conversation-append-historical",
        request_fingerprint="request-fingerprint-historical",
    )

    assert replay.status is ConversationMutationStatus.REPLAY
    assert replay.conversation == first_result
    assert replay.conversation != later_result
    assert replay.conversation.version == 2
    assert tuple(turn.ordinal for turn in replay.conversation.turns) == (1, 2)


@pytest.mark.asyncio
async def test_append_rejects_stale_version_and_modified_history() -> None:
    current = _conversation()
    candidate = _appended_conversation()
    current_model = PostgreSQLConversationRepository._conversation_model(current)
    stale_session = _FakeSession(scalar_values=(None, current_model, None), scalar_batches=((),))
    stale = await _repository(stale_session).append(
        candidate,
        expected_version=0,
        idempotency_key="conversation-append-stale",
        request_fingerprint="request-fingerprint-stale",
    )
    assert stale.status is ConversationMutationStatus.VERSION_CONFLICT
    assert stale.conversation == current
    assert stale_session.commits == 0

    assert (
        PostgreSQLConversationRepository._validate_append_transition(
            current=candidate,
            candidate=candidate,
            expected_version=candidate.version,
        )
        is None
    )


@pytest.mark.asyncio
async def test_list_owned_query_contains_exact_scope_owner_and_stable_order() -> None:
    session = _FakeSession(scalar_batches=((), ()))
    result = await _repository(session).list_owned(
        scope=SCOPE,
        owner_subject_id="subject.operator",
        authorized_target_ids=frozenset({"asset.storage.primary"}),
        limit=25,
    )
    assert result == ()
    statement = session.statements[0]
    sql = str(statement)
    params = statement.compile().params  # type: ignore[attr-defined]
    assert "operational_conversations.organization_id" in sql
    assert "operational_conversations.environment_id" in sql
    assert "operational_conversations.site_id" in sql
    assert "operational_conversations.owner_subject_id" in sql
    assert "operational_conversations.updated_at DESC" in sql
    scalar_params = {value for value in params.values() if isinstance(value, str)}
    assert {
        "organization.acme",
        "environment.production",
        "site.istanbul",
        "subject.operator",
    } <= scalar_params
    assert ["asset.storage.primary"] in params.values()
