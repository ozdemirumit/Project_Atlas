from __future__ import annotations

import asyncio
import importlib
import inspect
import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy import Boolean, Table, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from atlas.core.persistence.models import (
    WorkflowProtectedTransportTargetContextCapsuleOpeningAttemptModel,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseModel,
    WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionClaimModel,
    WorkflowProtectedTransportTargetContextCapsuleOpeningResultModel,
)
from atlas.modules.workflows.adapters.postgres import (
    PostgreSQLWorkflowPlanRepository,
    _TargetContextCapsuleOpeningLockedSources,
)
from atlas.modules.workflows.application import (
    WorkflowProtectedTransportTargetContextCapsuleOpeningClaimStatus,
    WorkflowProtectedTransportTargetContextCapsuleOpeningResultWriteStatus,
    WorkflowTargetContextCapsuleOpeningResultRequest,
)
from atlas.modules.workflows.domain import (
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_transport_target_context_capsule_opening_authorization_policy,
    code_owned_workflow_protected_transport_target_context_capsule_opening_consumption_policy,
)

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "20260816_0138_workflow_target_context_capsule_opening_consumption.py"
)
SCOPE = WorkflowScope("organization.development", "environment.test", "site.local")


def test_migration_is_linear_append_only_guarded_and_has_composite_lineage() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert 'revision: str = "20260816_0138"' in source
    assert 'down_revision: str | None = "20260816_0137"' in source
    assert source.count("op.create_table(") == 3
    assert source.count("BEFORE UPDATE OR DELETE") == 1
    assert "trg_wf_tctx_open_consume_append_only" in source
    assert "trg_wf_tctx_open_attempt_append_only" in source
    assert "trg_wf_tctx_open_result_append_only" in source
    assert "refusing guarded downgrade: capsule opening evidence exists" in source
    assert "fk_wf_tctx_open_consume_lease_lineage" in source
    assert "fk_wf_tctx_caps_open_attempt_claim_lineage" in source
    assert "fk_wf_tctx_caps_open_result_attempt_lineage" in source
    assert "uq_wf_tctx_open_auth_consume_lineage" in source
    assert "uq_wf_tctx_open_consume_lease" in source
    assert "uq_wf_tctx_open_consume_handoff" in source
    assert "uq_wf_tctx_open_consume_receipt" in source
    assert "uq_wf_tctx_open_consume_capsule" in source
    assert source.count("_authority_granted") >= 19


def test_orm_contract_has_exact_identity_acknowledgements_and_zero_authority() -> None:
    claim_table = cast(
        Table,
        WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionClaimModel.__table__,
    )
    attempt_table = cast(
        Table, WorkflowProtectedTransportTargetContextCapsuleOpeningAttemptModel.__table__
    )
    result_table = cast(
        Table, WorkflowProtectedTransportTargetContextCapsuleOpeningResultModel.__table__
    )
    claim_checks = " ".join(
        str(constraint.sqltext)
        for constraint in claim_table.constraints
        if hasattr(constraint, "sqltext")
    )
    assert "service.workflow-protected-transport-target-context-capsule-consumer" in claim_checks
    assert "contract.workflow-protected-transport-target-context-capsule-consumer" in claim_checks
    assert "irreversible_consumption_acknowledged" in claim_checks
    assert "uncertain_outcome_requires_new_authorization_acknowledged" in claim_checks
    assert "NOT target_context_capsule_opening_authority_granted" in claim_checks
    assert "NOT target_context_capsule_handoff_authority_granted" in claim_checks
    assert "NOT infrastructure_mutation_authority_granted" in claim_checks
    assert "fk_wf_tctx_open_consume_lease_lineage" in {
        constraint.name for constraint in claim_table.foreign_key_constraints
    }
    assert "fk_wf_tctx_caps_open_attempt_claim_lineage" in {
        constraint.name for constraint in attempt_table.foreign_key_constraints
    }
    assert "fk_wf_tctx_caps_open_result_attempt_lineage" in {
        constraint.name for constraint in result_table.foreign_key_constraints
    }
    assert "protected_resident_context_created_at" in result_table.c
    assert "protected_resident_context_usable_until" in result_table.c
    assert "resident_context_usable_until_limit" in attempt_table.c
    result_checks = " ".join(
        str(constraint.sqltext)
        for constraint in result_table.constraints
        if hasattr(constraint, "sqltext")
    )
    assert "completed_at < opening_deadline" in result_checks
    assert "INTERVAL '30 seconds'" in result_checks


def test_repository_claim_orders_locks_second_db_time_and_atomic_commit() -> None:
    source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.claim_target_context_capsule_opening
    )
    lock = source.index("_lock_target_context_capsule_opening_sources")
    evidence = source.index("_target_context_capsule_opening_claim_is_valid", lock)
    second_clock = source.index("clock_timestamp", evidence)
    second_evidence = source.index("_target_context_capsule_opening_claim_is_valid", second_clock)
    claim_add = source.index(
        "_target_context_capsule_opening_consumption_claim_model", second_evidence
    )
    first_flush = source.index("session.flush", claim_add)
    attempt_add = source.index("_target_context_capsule_opening_attempt_model", first_flush)
    second_flush = source.index("session.flush", attempt_add)
    commit = source.index("session.commit", second_evidence)

    assert lock < evidence < second_clock < second_evidence < claim_add
    assert claim_add < first_flush < attempt_add < second_flush < commit
    assert "required_precommit_audit" not in source
    assert "Memory" not in source
    lock_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._lock_target_context_capsule_opening_sources
    )
    hint = lock_source.index("lease_hint")
    upstream = lock_source.index("_lock_target_context_capsule_consumer_binding_sources")
    lease_lock = lock_source.index("lease_row = cast", upstream)
    assert hint < upstream < lease_lock
    lock_source += inspect.getsource(
        PostgreSQLWorkflowPlanRepository._load_target_context_capsule_opening_consumption_claims
    )
    for model_name in (
        "WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseModel",
        "WorkflowProtectedTransportTargetContextCapsuleHandoffResultModel",
        "WorkflowProtectedTransportTargetContextCapsuleHandoffAttemptModel",
        "WorkflowProtectedTransportTargetContextCapsuleHandoffConsumptionClaimModel",
        "WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseModel",
        "WorkflowProtectedTransportTargetContextCapsuleConsumerBindingModel",
        "WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionClaimModel",
        "WorkflowProtectedTransportTargetContextCapsuleOpeningAttemptModel",
        "WorkflowProtectedTransportTargetContextCapsuleOpeningResultModel",
    ):
        assert model_name in lock_source
    assert "_lock_target_context_capsule_consumer_binding_sources" in lock_source
    assert "with_for_update" in lock_source


def test_repository_rejects_resident_context_beyond_persisted_source_limit() -> None:
    limit = datetime(2026, 8, 16, 21, 0, 1, tzinfo=UTC)
    attempt = cast(Any, SimpleNamespace(resident_context_usable_until_limit=limit))
    repository_type = PostgreSQLWorkflowPlanRepository
    validator = (
        repository_type._target_context_capsule_opening_resident_context_within_source_lifetime
    )

    assert validator(usable_until=limit, attempt=attempt)
    assert not validator(
        usable_until=limit + timedelta(microseconds=1),
        attempt=attempt,
    )


@pytest.mark.asyncio
async def test_live_postgres_constraints_concurrency_lineage_append_only_and_claim_only_when_configured() -> (  # noqa: E501
    None
):
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    engine = create_async_engine(database_url)
    try:
        await _assert_installed_contract(engine)
        lease_table = cast(
            Table,
            WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseModel.__table__,
        )
        claim_table = cast(
            Table,
            WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionClaimModel.__table__,
        )
        attempt_table = cast(
            Table, WorkflowProtectedTransportTargetContextCapsuleOpeningAttemptModel.__table__
        )
        result_table = cast(
            Table, WorkflowProtectedTransportTargetContextCapsuleOpeningResultModel.__table__
        )
        seed = uuid4().hex
        lease = _live_lease_values(seed=seed, table=lease_table)
        async with engine.begin() as connection:
            await connection.execute(text("SET LOCAL session_replication_role = replica"))
            await connection.execute(lease_table.insert(), lease)

        first = _live_claim_values(seed=f"{seed}a", table=claim_table, lease=lease)
        second = {
            **_live_claim_values(seed=f"{seed}b", table=claim_table, lease=lease),
            "authorization_lease_id": first["authorization_lease_id"],
            "handoff_id": first["handoff_id"],
            "consumer_receipt_id": first["consumer_receipt_id"],
            "sealed_capsule_id": first["sealed_capsule_id"],
        }

        async def insert(values: dict[str, object]) -> BaseException | None:
            try:
                async with engine.begin() as connection:
                    await connection.execute(claim_table.insert(), values)
            except BaseException as error:  # pragma: no cover - asserted below
                return error
            return None

        outcomes = await asyncio.wait_for(asyncio.gather(insert(first), insert(second)), timeout=15)
        assert sum(outcome is None for outcome in outcomes) == 1
        assert sum(isinstance(outcome, IntegrityError) for outcome in outcomes) == 1
        winner = first if outcomes[0] is None else second

        for field, unsafe_value in (
            ("consumer_subject_id", "service.workflow-unrelated"),
            ("consumer_contract_id", "contract.workflow-unrelated"),
        ):
            unsafe = {
                **_live_claim_values(seed=f"{seed}{field}", table=claim_table, lease=lease),
                "authorization_lease_id": f"lease.{seed}.{field}",
                "handoff_id": f"handoff.{seed}.{field}",
                "consumer_receipt_id": f"receipt.{seed}.{field}",
                "sealed_capsule_id": f"capsule.{seed}.{field}",
                field: unsafe_value,
            }
            with pytest.raises(IntegrityError):
                async with engine.begin() as connection:
                    await connection.execute(text("SET LOCAL session_replication_role = replica"))
                    await connection.execute(claim_table.insert(), unsafe)

        attempt = _live_attempt_values(seed=seed, table=attempt_table, claim=winner, lease=lease)
        mismatched = {**attempt, "authorization_lease_digest": _live_digest(seed, "mismatch")}
        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                await connection.execute(attempt_table.insert(), mismatched)

        async with engine.begin() as connection:
            await connection.execute(attempt_table.insert(), attempt)

        async with engine.connect() as connection:
            durable_claim = await connection.scalar(
                text(
                    "SELECT count(*) FROM workflow_event_tctx_capsule_opening_consumption_claims "
                    "WHERE claim_id = :claim_id"
                ),
                {"claim_id": winner["claim_id"]},
            )
            durable_attempt = await connection.scalar(
                text(
                    "SELECT count(*) FROM workflow_event_tctx_capsule_opening_attempts "
                    "WHERE attempt_id = :attempt_id"
                ),
                {"attempt_id": attempt["attempt_id"]},
            )
            no_result = await connection.scalar(
                text(
                    "SELECT count(*) FROM workflow_event_tctx_capsule_opening_results "
                    "WHERE opening_id = :opening_id"
                ),
                {"opening_id": attempt["opening_id"]},
            )
        assert (durable_claim, durable_attempt, no_result) == (1, 1, 0)

        result = _live_uncertain_result_values(
            seed=seed,
            table=result_table,
            claim=winner,
            attempt=attempt,
        )
        async with engine.begin() as connection:
            await connection.execute(result_table.insert(), result)

        for table, key, row_value in (
            (claim_table, "claim_id", winner["claim_id"]),
            (attempt_table, "attempt_id", attempt["attempt_id"]),
            (result_table, "opening_id", result["opening_id"]),
        ):
            with pytest.raises(DBAPIError):
                async with engine.begin() as connection:
                    await connection.execute(
                        table.update()
                        .where(table.c[key] == row_value)
                        .values(payload={"changed": True})
                    )
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_live_postgres_repository_claim_commit_and_replay_are_atomic_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    engine = create_async_engine(database_url)
    request = await _captured_claim_request(monkeypatch, idempotency_key=f"live-{uuid4().hex}")
    repository, observed_times = _isolated_live_repository(
        engine=engine,
        monkeypatch=monkeypatch,
    )
    claim_table = cast(
        Table,
        WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionClaimModel.__table__,
    )
    attempt_table = cast(
        Table, WorkflowProtectedTransportTargetContextCapsuleOpeningAttemptModel.__table__
    )
    try:
        outcomes = await asyncio.wait_for(
            asyncio.gather(
                repository.claim_target_context_capsule_opening(request),
                repository.claim_target_context_capsule_opening(request),
            ),
            timeout=15,
        )
        assert (
            sum(
                result.status
                is WorkflowProtectedTransportTargetContextCapsuleOpeningClaimStatus.CLAIMED
                for result in outcomes
            )
            == 1
        )
        assert (
            sum(
                result.status
                is (
                    WorkflowProtectedTransportTargetContextCapsuleOpeningClaimStatus.CLAIM_ONLY_PENDING
                )
                for result in outcomes
            )
            == 1
        )
        assert len(observed_times) >= 2
        assert not hasattr(request, "required_precommit_audit")

        exact_replay = await repository.claim_target_context_capsule_opening(request)
        assert exact_replay.status is (
            WorkflowProtectedTransportTargetContextCapsuleOpeningClaimStatus.CLAIM_ONLY_PENDING
        )
        async with engine.connect() as connection:
            claim_count = await connection.scalar(
                text(f"SELECT count(*) FROM {claim_table.name} WHERE opening_id = :opening_id"),
                {"opening_id": request.opening_id},
            )
            attempt_count = await connection.scalar(
                text(f"SELECT count(*) FROM {attempt_table.name} WHERE opening_id = :opening_id"),
                {"opening_id": request.opening_id},
            )
        assert (claim_count, attempt_count) == (1, 1)
    finally:
        await _delete_isolated_repository_rows(engine, opening_id=request.opening_id)
        await engine.dispose()


@pytest.mark.asyncio
async def test_live_postgres_repository_second_time_drift_rolls_back_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    engine = create_async_engine(database_url)
    request = await _captured_claim_request(monkeypatch, idempotency_key=f"drift-{uuid4().hex}")
    repository, observed_times = _isolated_live_repository(
        engine=engine,
        monkeypatch=monkeypatch,
        reject_second_validation=True,
    )
    try:
        result = await repository.claim_target_context_capsule_opening(request)
        assert result.status is (
            WorkflowProtectedTransportTargetContextCapsuleOpeningClaimStatus.EVIDENCE_CONFLICT
        )
        assert len(observed_times) == 2
        async with engine.connect() as connection:
            stored = await connection.scalar(
                text(
                    "SELECT count(*) FROM "
                    "workflow_event_tctx_capsule_opening_consumption_claims "
                    "WHERE opening_id = :opening_id"
                ),
                {"opening_id": request.opening_id},
            )
        assert stored == 0
    finally:
        await _delete_isolated_repository_rows(engine, opening_id=request.opening_id)
        await engine.dispose()


@pytest.mark.asyncio
async def test_live_postgres_repository_rejects_result_beyond_source_limit_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    engine = create_async_engine(database_url)
    request = await _captured_claim_request(monkeypatch, idempotency_key=f"limit-{uuid4().hex}")
    repository, _ = _isolated_live_repository(engine=engine, monkeypatch=monkeypatch)
    result_table = cast(
        Table, WorkflowProtectedTransportTargetContextCapsuleOpeningResultModel.__table__
    )
    try:
        claimed = await repository.claim_target_context_capsule_opening(request)
        assert (
            claimed.status
            is WorkflowProtectedTransportTargetContextCapsuleOpeningClaimStatus.CLAIMED
        )
        assert claimed.claim is not None
        assert claimed.attempt is not None

        unit_openings: Any = importlib.import_module(
            "test_workflow_target_context_capsule_openings"
        )
        opener = unit_openings.SyntheticWorkflowProtectedTargetContextCapsuleTrustedOpener(
            test_enabled=True,
            clock=lambda: claimed.attempt.started_at + timedelta(milliseconds=1),
        )
        service, _, _, _ = unit_openings._service(
            unit_openings._Repository(),
            opener=opener,
        )
        instruction = service._build_instruction(
            source=request.source,
            attempt=claimed.attempt,
        )
        receipt = await opener.open_capsule(instruction)
        unsafe_usable_until = claimed.attempt.resident_context_usable_until_limit + timedelta(
            microseconds=1
        )
        receipt_payload = receipt.digest_payload()
        receipt_payload["protected_resident_context_usable_until"] = unsafe_usable_until.isoformat()
        unsafe_receipt = replace(
            receipt,
            protected_resident_context_usable_until=unsafe_usable_until,
            canonical_digest=canonical_digest(receipt_payload),
        )
        unsafe_result = service._build_receipted_result(
            source=request.source,
            claim_digest=claimed.claim.canonical_digest,
            attempt=claimed.attempt,
            receipt=unsafe_receipt,
            recorded_at=unsafe_receipt.completed_at,
        )

        write = await repository.record_target_context_capsule_opening_result(
            WorkflowTargetContextCapsuleOpeningResultRequest(
                result=unsafe_result,
                receipt=unsafe_receipt,
                expected_claim_digest=claimed.claim.canonical_digest,
                expected_attempt_digest=claimed.attempt.canonical_digest,
            )
        )

        assert write.status is (
            WorkflowProtectedTransportTargetContextCapsuleOpeningResultWriteStatus.CONFLICT
        )
        async with engine.connect() as connection:
            stored = await connection.scalar(
                text(f"SELECT count(*) FROM {result_table.name} WHERE opening_id = :opening_id"),
                {"opening_id": request.opening_id},
            )
        assert stored == 0
    finally:
        await _delete_isolated_repository_rows(engine, opening_id=request.opening_id)
        await engine.dispose()


async def _captured_claim_request(monkeypatch: pytest.MonkeyPatch, *, idempotency_key: str) -> Any:
    unit_openings: Any = importlib.import_module("test_workflow_target_context_capsule_openings")
    monkeypatch.setattr(
        unit_openings,
        "NOW",
        datetime.now(UTC) + timedelta(seconds=5),
    )
    fake_repository = unit_openings._Repository()
    service, _, _, _ = unit_openings._service(fake_repository)
    policy = service.policy
    lease = fake_repository.source.lease
    await service.open(
        authorization_lease_id=lease.authorization_lease_id,
        authorization_lease_digest=lease.canonical_digest,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        irreversible_consumption_acknowledged=True,
        uncertain_outcome_requires_new_authorization_acknowledged=True,
        idempotency_key=idempotency_key,
        context=unit_openings._context(),
    )
    assert fake_repository.last_claim_request is not None
    return fake_repository.last_claim_request


def _isolated_live_repository(
    *,
    engine: AsyncEngine,
    monkeypatch: pytest.MonkeyPatch,
    reject_second_validation: bool = False,
) -> tuple[PostgreSQLWorkflowPlanRepository, list[datetime]]:
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    @asynccontextmanager
    async def isolated_transaction_session() -> AsyncIterator[AsyncSession]:
        async with sessions() as session:
            await session.execute(text("SET LOCAL session_replication_role = replica"))
            yield session

    repository = PostgreSQLWorkflowPlanRepository(
        engine=engine,
        session_factory=cast(Callable[[], AsyncSession], isolated_transaction_session),
    )
    observed_times: list[datetime] = []

    async def isolated_lock(
        session: AsyncSession,
        *,
        request: Any,
    ) -> _TargetContextCapsuleOpeningLockedSources:
        del request
        observed_at = cast(datetime, await session.scalar(text("SELECT clock_timestamp()")))
        return _TargetContextCapsuleOpeningLockedSources(
            authorization_lease=None,
            authorization_claim=None,
            handoff_result=None,
            handoff_attempt=None,
            handoff_claim=None,
            upstream_lease=None,
            upstream_claim=None,
            consumer_binding=None,
            consumer_binding_claim=None,
            consumer_binding_sources=None,
            consumption_claims=(),
            attempt=None,
            result=None,
            observed_at=observed_at,
        )

    def isolated_validation(*, request: Any, locked: Any) -> bool:
        del request
        observed_times.append(locked.observed_at)
        return not reject_second_validation or len(observed_times) == 1

    monkeypatch.setattr(repository, "_lock_target_context_capsule_opening_sources", isolated_lock)
    monkeypatch.setattr(
        repository, "_target_context_capsule_opening_claim_is_valid", isolated_validation
    )
    return repository, observed_times


async def _delete_isolated_repository_rows(engine: AsyncEngine, *, opening_id: str) -> None:
    async with engine.begin() as connection:
        await connection.execute(text("SET LOCAL session_replication_role = replica"))
        await connection.execute(
            text(
                "DELETE FROM workflow_event_tctx_capsule_opening_results "
                "WHERE opening_id = :opening_id"
            ),
            {"opening_id": opening_id},
        )
        await connection.execute(
            text(
                "DELETE FROM workflow_event_tctx_capsule_opening_attempts "
                "WHERE opening_id = :opening_id"
            ),
            {"opening_id": opening_id},
        )
        await connection.execute(
            text(
                "DELETE FROM workflow_event_tctx_capsule_opening_consumption_claims "
                "WHERE opening_id = :opening_id"
            ),
            {"opening_id": opening_id},
        )


async def _assert_installed_contract(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        tables = set(
            (
                await connection.execute(
                    text(
                        "SELECT tablename FROM pg_tables WHERE schemaname = current_schema() "
                        "AND tablename IN (:claim, :attempt, :result)"
                    ),
                    {
                        "claim": "workflow_event_tctx_capsule_opening_consumption_claims",
                        "attempt": "workflow_event_tctx_capsule_opening_attempts",
                        "result": "workflow_event_tctx_capsule_opening_results",
                    },
                )
            ).scalars()
        )
        assert tables == {
            "workflow_event_tctx_capsule_opening_consumption_claims",
            "workflow_event_tctx_capsule_opening_attempts",
            "workflow_event_tctx_capsule_opening_results",
        }
        constraints = set(
            (
                await connection.execute(
                    text(
                        "SELECT conname FROM pg_constraint WHERE conname IN "
                        "('ck_wf_tctx_open_consume_contract', "
                        "'ck_wf_tctx_open_consume_ack', "
                        "'ck_wf_tctx_open_consume_authority', "
                        "'uq_wf_tctx_open_consume_lease', "
                        "'fk_wf_tctx_caps_open_attempt_claim_lineage', "
                        "'fk_wf_tctx_caps_open_result_attempt_lineage')"
                    )
                )
            ).scalars()
        )
        assert constraints == {
            "ck_wf_tctx_open_consume_contract",
            "ck_wf_tctx_open_consume_ack",
            "ck_wf_tctx_open_consume_authority",
            "uq_wf_tctx_open_consume_lease",
            "fk_wf_tctx_caps_open_attempt_claim_lineage",
            "fk_wf_tctx_caps_open_result_attempt_lineage",
        }
        triggers = set(
            (
                await connection.execute(
                    text(
                        "SELECT tgname FROM pg_trigger WHERE tgname IN "
                        "('trg_wf_tctx_open_consume_append_only', "
                        "'trg_wf_tctx_open_attempt_append_only', "
                        "'trg_wf_tctx_open_result_append_only')"
                    )
                )
            ).scalars()
        )
        assert triggers == {
            "trg_wf_tctx_open_consume_append_only",
            "trg_wf_tctx_open_attempt_append_only",
            "trg_wf_tctx_open_result_append_only",
        }


def _live_digest(seed: str, name: str) -> str:
    return sha256(f"{seed}:{name}".encode()).hexdigest()


def _live_lease_values(*, seed: str, table: Table) -> dict[str, object]:
    policy = code_owned_workflow_protected_transport_target_context_capsule_opening_authorization_policy()  # noqa: E501
    now = datetime.now(UTC)
    values: dict[str, object] = {}
    for column in table.columns:
        name = column.name
        if hasattr(policy, name):
            values[name] = getattr(policy, name)
        elif name == "state":
            values[name] = "authorized_unconsumed"
        elif name == "issued_at":
            values[name] = now
        elif name == "valid_until":
            values[name] = now + timedelta(seconds=1)
        elif name in {"effective_until", "custody_attestation_valid_until"}:
            values[name] = now + timedelta(seconds=2)
        elif name in {"single_use", "target_context_capsule_opening_authority_granted"}:
            values[name] = True
        elif isinstance(column.type, Boolean):
            values[name] = False
        elif name in {"organization_id", "environment_id", "site_id"}:
            values[name] = getattr(SCOPE, name)
        elif name.endswith("_payload") or name == "payload":
            values[name] = {"schema_id": f"test.{seed}"}
        elif name.endswith("_digest") or name == "canonical_digest":
            values[name] = _live_digest(seed, name)
        else:
            raw = f"{name}.{seed}"
            length = getattr(column.type, "length", None)
            values[name] = raw if not isinstance(length, int) else raw[:length]
    return values


def _live_claim_values(*, seed: str, table: Table, lease: dict[str, object]) -> dict[str, object]:
    policy = (
        code_owned_workflow_protected_transport_target_context_capsule_opening_consumption_policy()
    )
    lineage = {
        "authorization_lease_id": lease["authorization_lease_id"],
        "authorization_lease_digest": lease["canonical_digest"],
        "handoff_id": lease["handoff_id"],
        "handoff_result_digest": lease["handoff_result_digest"],
        "handoff_attempt_id": lease["attempt_id"],
        "handoff_attempt_digest": lease["attempt_digest"],
        "handoff_consumption_claim_id": lease["consumption_claim_id"],
        "handoff_consumption_claim_digest": lease["consumption_claim_digest"],
        "consumer_binding_id": lease["consumer_binding_id"],
        "consumer_binding_digest": lease["consumer_binding_digest"],
        "sealed_capsule_id": lease["sealed_capsule_id"],
        "sealed_capsule_digest": lease["sealed_capsule_digest"],
        "consumer_receipt_id": lease["consumer_receipt_id"],
        "consumer_receipt_digest": lease["receipt_digest"],
    }
    values: dict[str, object] = {}
    for column in table.columns:
        name = column.name
        if name in lineage:
            values[name] = lineage[name]
        elif hasattr(policy, name):
            values[name] = getattr(policy, name)
        elif name in {
            "irreversible_consumption_acknowledged",
            "uncertain_outcome_requires_new_authorization_acknowledged",
        }:
            values[name] = True
        elif isinstance(column.type, Boolean):
            values[name] = False
        elif name in {"organization_id", "environment_id", "site_id"}:
            values[name] = getattr(SCOPE, name)
        elif name == "claimed_at":
            values[name] = datetime.now(UTC)
        elif name.endswith("_payload") or name == "payload":
            values[name] = {"schema_id": f"test.{seed}"}
        elif name.endswith("_digest") or name in {
            "idempotency_scope_id",
            "request_fingerprint",
            "canonical_digest",
        }:
            values[name] = _live_digest(seed, name)
        else:
            raw = f"{name}.{seed}"
            length = getattr(column.type, "length", None)
            values[name] = raw if not isinstance(length, int) else raw[:length]
    return values


def _live_attempt_values(
    *,
    seed: str,
    table: Table,
    claim: dict[str, object],
    lease: dict[str, object],
) -> dict[str, object]:
    policy = (
        code_owned_workflow_protected_transport_target_context_capsule_opening_consumption_policy()
    )
    started_at = cast(datetime, lease["issued_at"])
    deadline = started_at + timedelta(milliseconds=500)
    lineage = {
        "attempt_id": claim["attempt_id"],
        "opening_id": claim["opening_id"],
        "consumption_claim_id": claim["claim_id"],
        "consumption_claim_digest": claim["canonical_digest"],
        "authorization_lease_id": claim["authorization_lease_id"],
        "authorization_lease_digest": claim["authorization_lease_digest"],
        "consumer_binding_id": claim["consumer_binding_id"],
        "consumer_binding_digest": claim["consumer_binding_digest"],
        "sealed_capsule_id": claim["sealed_capsule_id"],
        "sealed_capsule_digest": claim["sealed_capsule_digest"],
        "consumer_receipt_id": claim["consumer_receipt_id"],
        "consumer_receipt_digest": claim["consumer_receipt_digest"],
    }
    values: dict[str, object] = {}
    for column in table.columns:
        name = column.name
        if name in lineage:
            values[name] = lineage[name]
        elif hasattr(policy, name):
            values[name] = getattr(policy, name)
        elif name == "state":
            values[name] = "started"
        elif name == "started_at":
            values[name] = started_at
        elif name == "opening_deadline":
            values[name] = deadline
        elif name == "lease_valid_until":
            values[name] = lease["valid_until"]
        elif name in {"custody_attestation_valid_until", "openability_attestation_valid_until"}:
            values[name] = cast(datetime, lease["valid_until"]) + timedelta(seconds=1)
        elif name == "resident_context_usable_until_limit":
            values[name] = cast(datetime, lease["effective_until"])
        elif isinstance(column.type, Boolean):
            values[name] = False
        elif name in {"organization_id", "environment_id", "site_id"}:
            values[name] = getattr(SCOPE, name)
        elif name.endswith("_payload") or name == "payload":
            values[name] = {"schema_id": f"test.{seed}"}
        elif name.endswith("_digest") or name == "canonical_digest":
            values[name] = _live_digest(seed, name)
        else:
            raw = f"{name}.{seed}"
            length = getattr(column.type, "length", None)
            values[name] = raw if not isinstance(length, int) else raw[:length]
    return values


def _live_uncertain_result_values(
    *,
    seed: str,
    table: Table,
    claim: dict[str, object],
    attempt: dict[str, object],
) -> dict[str, object]:
    policy = (
        code_owned_workflow_protected_transport_target_context_capsule_opening_consumption_policy()
    )
    lineage = {
        "opening_id": attempt["opening_id"],
        "attempt_id": attempt["attempt_id"],
        "attempt_digest": attempt["canonical_digest"],
        "consumption_claim_id": claim["claim_id"],
        "consumption_claim_digest": claim["canonical_digest"],
        "authorization_lease_id": claim["authorization_lease_id"],
        "authorization_lease_digest": claim["authorization_lease_digest"],
        "consumer_binding_id": claim["consumer_binding_id"],
        "consumer_binding_digest": claim["consumer_binding_digest"],
        "sealed_capsule_id": claim["sealed_capsule_id"],
        "sealed_capsule_digest": claim["sealed_capsule_digest"],
        "consumer_receipt_id": claim["consumer_receipt_id"],
        "consumer_receipt_digest": claim["consumer_receipt_digest"],
    }
    values: dict[str, object] = {}
    for column in table.columns:
        name = column.name
        if name in lineage:
            values[name] = lineage[name]
        elif hasattr(policy, name):
            values[name] = getattr(policy, name)
        elif name == "state" or name == "failure_class":
            values[name] = "opening_outcome_uncertain"
        elif name in {"opening_deadline", "recorded_at"}:
            values[name] = attempt["opening_deadline"]
        elif name in {
            "opening_receipt_digest",
            "opening_receipt_payload",
            "protected_resident_context_id",
            "protected_resident_context_digest",
            "protected_resident_context_created_at",
            "protected_resident_context_usable_until",
            "completed_at",
        }:
            values[name] = None
        elif isinstance(column.type, Boolean):
            values[name] = False
        elif name in {"organization_id", "environment_id", "site_id"}:
            values[name] = getattr(SCOPE, name)
        elif name == "payload":
            values[name] = {"schema_id": f"test.{seed}"}
        elif name.endswith("_digest") or name == "canonical_digest":
            values[name] = _live_digest(seed, name)
        else:
            raw = f"{name}.{seed}"
            length = getattr(column.type, "length", None)
            values[name] = raw if not isinstance(length, int) else raw[:length]
    return values
