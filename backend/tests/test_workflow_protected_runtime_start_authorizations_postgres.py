from __future__ import annotations

import asyncio
import inspect
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy import (
    CheckConstraint,
    MetaData,
    Table,
    UniqueConstraint,
    func,
    insert,
    select,
    text,
)
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from test_workflow_protected_runtime_start_authorizations import (
    _Attestor,
    _authorize,
    _ReceiptVerifier,
    _Repository,
    _service,
    _source,
)

from atlas.core.persistence.models import (
    WorkflowProtectedRuntimeContextUseAttemptModel,
    WorkflowProtectedRuntimeContextUseClaimModel,
    WorkflowProtectedRuntimeContextUseResultModel,
    WorkflowProtectedRuntimeStartAuthorizationClaimModel,
    WorkflowProtectedRuntimeStartAuthorizationLeaseModel,
    WorkflowProtectedRuntimeStartCoordinationHeadModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.domain.protected_runtime_start_authorization_domain import (
    code_owned_workflow_protected_runtime_start_authorization_policy,
)

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "20260817_0146_workflow_protected_runtime_start_authorization.py"
)


def _checks(table: Table) -> str:
    return " ".join(
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    )


def _model_values(model: object) -> dict[str, object]:
    table = cast(Any, type(model)).__table__
    return {column.name: getattr(model, column.name) for column in table.columns}


def _coordination_row(*, suffix: str, use_result_id: str) -> dict[str, object]:
    return {
        "runtime_envelope_id": f"runtime-envelope.{suffix}",
        "runtime_envelope_commitment": suffix.ljust(64, "a")[:64],
        "runtime_envelope_generation": 2,
        "use_result_id": use_result_id,
        "use_result_digest": "b" * 64,
        "destination_deployment_id": "deployment.imp-223-concurrency",
        "destination_generation": 1,
        "destination_fencing_token_digest": "c" * 64,
        "runtime_slot_commitment": "d" * 64,
        "runtime_slot_post_generation": 2,
        "state": "inactive_unstarted",
        "active_authorization_lease_id": None,
        "consumption_claim_id": None,
        "runtime_start_attempt_id": None,
        "runtime_start_attempt_pending": False,
        "runtime_start_attempt_terminal": False,
        "runtime_started": False,
        "runtime_resumed": False,
        "process_created": False,
        "process_scheduled": False,
        "version": 1,
        "updated_at": datetime.now(UTC),
    }


def test_migration_is_linear_append_only_guarded_and_non_colliding() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    policy = code_owned_workflow_protected_runtime_start_authorization_policy()

    assert 'revision: str = "20260817_0146"' in source
    assert 'down_revision: str | None = "20260817_0145"' in source
    assert source.count("op.create_table(") == 3
    assert "workflow_event_runtime_start_auth_claims" in source
    assert "workflow_event_runtime_start_auth_leases" in source
    assert "workflow_event_runtime_start_coordination_heads" in source
    assert "workflow_protected_runtime_context_use_results" in source
    assert "workflow_protected_runtime_context_use_attempts" in source
    assert "workflow_protected_runtime_context_use_claims" in source
    assert "fk_wf_rtstart_{prefix}_use_result" in source
    assert "fk_wf_rtstart_{prefix}_use_attempt" in source
    assert "fk_wf_rtstart_{prefix}_use_claim" in source
    assert "uq_wf_rtctx_use_result_start_identity" in source
    assert "uq_wf_rtctx_use_result_start_source" in source
    assert "uq_wf_rtctx_use_attempt_start_source" in source
    assert "uq_wf_rtctx_use_claim_start_source" in source
    assert "INTERVAL '1 second'" in source
    assert "use_count_pre = 0 AND use_count_post = 1" in source
    assert "context_used_once_in_protected_boundary" in source
    assert "context_terminal_non_reusable" in source
    assert "protected_runtime_start_authority_granted" in source
    assert "BEFORE UPDATE OR DELETE" in source
    assert "trg_wf_rtstart_auth_lease_append_only" in source
    assert "trg_wf_rtstart_auth_claim_append_only" in source
    assert "trg_wf_rtstart_coord_guard" in source
    assert "uq_wf_rtctx_use_result_start_runtime" in source
    assert "uq_wf_rtctx_use_result_start_outcome" in source
    assert (
        "refusing guarded downgrade: protected runtime-start authorization evidence exists"
        in source
    )
    assert policy.canonical_digest in source
    assert policy.source_policy_digest in source
    assert policy.runtime_start_profile_digest in source
    names = re.findall(r'name="([^"]+)"', source)
    assert len(names) == len(set(names))
    assert max(map(len, names)) <= 63


def test_orm_binds_exact_adr172_lineage_and_one_winner_constraints() -> None:
    lease = cast(Table, WorkflowProtectedRuntimeStartAuthorizationLeaseModel.__table__)
    claim = cast(Table, WorkflowProtectedRuntimeStartAuthorizationClaimModel.__table__)
    coordination = cast(Table, WorkflowProtectedRuntimeStartCoordinationHeadModel.__table__)

    assert lease.name == "workflow_event_runtime_start_auth_leases"
    assert claim.name == "workflow_event_runtime_start_auth_claims"
    assert coordination.name == "workflow_event_runtime_start_coordination_heads"
    required = {
        "use_result_id",
        "use_result_digest",
        "use_id",
        "use_attempt_id",
        "use_attempt_digest",
        "use_claim_id",
        "use_claim_digest",
        "use_receipt_digest",
        "authorization_consumption_result_id",
        "authorization_consumption_result_digest",
        "runtime_slot_pre_generation",
        "runtime_slot_post_generation",
        "use_count_pre",
        "use_count_post",
        "runtime_envelope_id",
        "runtime_envelope_commitment",
        "runtime_envelope_generation",
    }
    assert required <= set(lease.c.keys())
    assert required <= set(claim.c.keys())
    assert {
        "uq_wf_rtstart_auth_lease_use_result",
        "uq_wf_rtstart_auth_lease_slot",
        "uq_wf_rtstart_auth_lease_claim",
    } <= {constraint.name for constraint in lease.constraints}
    assert {
        "uq_wf_rtstart_auth_claim_use_result",
        "uq_wf_rtstart_auth_claim_slot",
        "uq_wf_rtstart_auth_scope_idem",
    } <= {constraint.name for constraint in claim.constraints}
    lease_claim = next(
        constraint
        for constraint in lease.foreign_key_constraints
        if constraint.name == "fk_wf_rtstart_auth_lease_claim"
    )
    claim_lease = next(
        constraint
        for constraint in claim.foreign_key_constraints
        if constraint.name == "fk_wf_rtstart_auth_claim_lease"
    )
    assert lease_claim.deferrable is True and lease_claim.initially == "DEFERRED"
    assert claim_lease.deferrable is True and claim_lease.initially == "DEFERRED"


def test_orm_composite_foreign_keys_bind_result_attempt_and_claim_digests() -> None:
    lease = cast(Table, WorkflowProtectedRuntimeStartAuthorizationLeaseModel.__table__)
    claim = cast(Table, WorkflowProtectedRuntimeStartAuthorizationClaimModel.__table__)
    parents = (
        (
            cast(Table, WorkflowProtectedRuntimeContextUseResultModel.__table__),
            "fk_wf_rtstart_lease_use_result",
            "fk_wf_rtstart_claim_use_result",
            ("use_result_id", "use_result_digest"),
        ),
        (
            cast(Table, WorkflowProtectedRuntimeContextUseAttemptModel.__table__),
            "fk_wf_rtstart_lease_use_attempt",
            "fk_wf_rtstart_claim_use_attempt",
            ("use_attempt_id", "use_attempt_digest"),
        ),
        (
            cast(Table, WorkflowProtectedRuntimeContextUseClaimModel.__table__),
            "fk_wf_rtstart_lease_use_claim",
            "fk_wf_rtstart_claim_use_claim",
            ("use_claim_id", "use_claim_digest"),
        ),
    )
    for parent, lease_name, claim_name, leading in parents:
        for child, expected_name in ((lease, lease_name), (claim, claim_name)):
            constraint = next(
                item for item in child.foreign_key_constraints if item.name == expected_name
            )
            local = tuple(element.parent.name for element in constraint.elements)
            assert local[:2] == leading
            assert all(element.column.table is parent for element in constraint.elements)
        assert any(isinstance(item, UniqueConstraint) for item in parent.constraints)


def test_orm_enforces_one_second_lease_only_authority_and_zero_existing_authority() -> None:
    lease = cast(Table, WorkflowProtectedRuntimeStartAuthorizationLeaseModel.__table__)
    claim = cast(Table, WorkflowProtectedRuntimeStartAuthorizationClaimModel.__table__)
    lease_checks = _checks(lease)
    claim_checks = _checks(claim)

    assert "INTERVAL '1 second'" in lease_checks
    assert "single_use" in lease_checks
    assert "NOT renewable" in lease_checks
    assert "NOT transferable" in lease_checks
    assert "NOT lease_is_bearer_capability" in lease_checks
    assert "protected_runtime_start_authority_granted" in lease_checks
    assert "NOT protected_runtime_start_authority_granted" in claim_checks
    for forbidden in (
        "runtime_use_authorized",
        "runtime_start_authorized",
        "runtime_resume_authorized",
        "connector_activity_authorized",
        "network_access_authorized",
        "readiness_probe_authorized",
        "publication_authorized",
        "delivery_authorized",
        "dispatch_authorized",
        "execution_authorized",
        "infrastructure_mutation_authorized",
        "protected_runtime_context_use_authority_granted",
    ):
        assert f"NOT {forbidden}" in lease_checks
        assert f"NOT {forbidden}" in claim_checks


def test_repository_uses_two_database_times_terminal_slot_and_coordination_gate() -> None:
    lock_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._lock_protected_runtime_start_authorization_rows
    )
    authorize_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.authorize_protected_runtime_start
    )
    evidence_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._protected_runtime_start_evidence_matches
    )
    presentation_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.list_protected_runtime_start_authorization_presentations
    )

    assert lock_source.count("clock_timestamp") == 2
    assert "with_for_update" in lock_source
    assert lock_source.index("use_claim =") < lock_source.index("use_attempt =")
    assert lock_source.index("use_attempt =") < lock_source.index("use_result =")
    assert "context_used_terminal" in evidence_source
    assert "runtime_slot_post_generation" in evidence_source
    assert "destination_fencing_token_digest" in evidence_source
    assert "coordination_head" in lock_source
    assert "_protected_runtime_start_coordination_allows_issuance" in evidence_source
    assert "validate_workflow_protected_runtime_start_authorization_request" in evidence_source
    assert "except IntegrityError" in authorize_source
    assert "_protected_runtime_start_replay" in authorize_source
    assert "to_regclass" not in presentation_source
    assert "WorkflowProtectedRuntimeStartCoordinationHeadModel" in presentation_source
    assert presentation_source.count("session.execute") == 1
    for forbidden in ("executor", "connector", "mcp", "network", "process_manager"):
        assert forbidden not in authorize_source.lower()


@pytest.mark.asyncio
async def test_live_postgres_tables_constraints_and_append_only_triggers_when_configured() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            transaction = await connection.begin()
            try:
                tables = set(
                    (
                        await connection.execute(
                            text(
                                "SELECT tablename FROM pg_tables "
                                "WHERE schemaname = current_schema() "
                                "AND tablename IN (:lease, :claim, :coordination)"
                            ),
                            {
                                "lease": "workflow_event_runtime_start_auth_leases",
                                "claim": "workflow_event_runtime_start_auth_claims",
                                "coordination": ("workflow_event_runtime_start_coordination_heads"),
                            },
                        )
                    ).scalars()
                )
                assert tables == {
                    "workflow_event_runtime_start_auth_leases",
                    "workflow_event_runtime_start_auth_claims",
                    "workflow_event_runtime_start_coordination_heads",
                }
                triggers = set(
                    (
                        await connection.execute(
                            text(
                                "SELECT tgname FROM pg_trigger WHERE tgname IN "
                                "('trg_wf_rtstart_auth_lease_append_only', "
                                "'trg_wf_rtstart_auth_claim_append_only', "
                                "'trg_wf_rtstart_coord_guard')"
                            )
                        )
                    ).scalars()
                )
                assert triggers == {
                    "trg_wf_rtstart_auth_lease_append_only",
                    "trg_wf_rtstart_auth_claim_append_only",
                    "trg_wf_rtstart_coord_guard",
                }
                constraints = " ".join(
                    (
                        await connection.execute(
                            text(
                                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                                "WHERE conrelid IN "
                                "('workflow_event_runtime_start_auth_leases'::regclass, "
                                "'workflow_event_runtime_start_auth_claims'::regclass)"
                            )
                        )
                    ).scalars()
                )
                assert "context_used_once_in_protected_boundary" in constraints
                assert "context_terminal_non_reusable" in constraints
                assert "use_count_pre = 0" in constraints
                assert "use_count_post = 1" in constraints
                assert "1 second" in constraints
                assert "executor_receipt_digest" in constraints
                assert "runtime_envelope_commitment" in constraints
                assert "runtime_start_attempt_pending" in constraints

                await connection.execute(
                    text(
                        "CREATE TEMP TABLE imp223_lineage_parent ("
                        "result_id text, receipt_digest text, destination_generation int, "
                        "fence_digest text, slot_commitment text, slot_generation int, "
                        "use_count int, profile_digest text, "
                        "UNIQUE (result_id, receipt_digest, destination_generation, "
                        "fence_digest, slot_commitment, slot_generation, use_count, "
                        "profile_digest))"
                    )
                )
                await connection.execute(
                    text(
                        "CREATE TEMP TABLE imp223_lineage_child ("
                        "result_id text, receipt_digest text, destination_generation int, "
                        "fence_digest text, slot_commitment text, slot_generation int, "
                        "use_count int, profile_digest text, FOREIGN KEY (result_id, "
                        "receipt_digest, destination_generation, fence_digest, "
                        "slot_commitment, slot_generation, use_count, profile_digest) "
                        "REFERENCES imp223_lineage_parent (result_id, receipt_digest, "
                        "destination_generation, fence_digest, slot_commitment, "
                        "slot_generation, use_count, profile_digest))"
                    )
                )
                lineage = {
                    "result": "result.imp-223-lineage",
                    "receipt": "1" * 64,
                    "generation": 1,
                    "fence": "2" * 64,
                    "slot": "3" * 64,
                    "slot_generation": 2,
                    "count": 1,
                    "profile": "4" * 64,
                }
                await connection.execute(
                    text(
                        "INSERT INTO imp223_lineage_parent VALUES (:result, :receipt, "
                        ":generation, :fence, :slot, :slot_generation, :count, :profile)"
                    ),
                    lineage,
                )
                forged_savepoint = await connection.begin_nested()
                with pytest.raises(IntegrityError):
                    await connection.execute(
                        text(
                            "INSERT INTO imp223_lineage_child VALUES (:result, :receipt, "
                            ":generation, :forged_fence, :slot, :slot_generation, "
                            ":count, :profile)"
                        ),
                        {**lineage, "forged_fence": "f" * 64},
                    )
                await forged_savepoint.rollback()

                source = _source()
                events: list[str] = []
                memory_repository = _Repository(source, events)
                lease = await _authorize(
                    _service(memory_repository, _Attestor(events), _ReceiptVerifier()), source
                )
                request = memory_repository.requests[0]
                repository = PostgreSQLWorkflowPlanRepository(engine=engine)
                assert source.result.runtime_slot_post_generation is not None
                source_result = SimpleNamespace(
                    runtime_slot_pre_generation=(source.result.runtime_slot_post_generation - 1),
                    use_count_pre=0,
                )
                lease_model = repository._protected_runtime_start_lease_model(
                    lease,
                    request.lifecycle_attestation,
                    source_result=cast(Any, source_result),
                )
                head_model = repository._protected_runtime_start_coordination_head_model(
                    source, observed_at=lease.issued_at
                )
                head_model.state = "authorized_unconsumed"
                head_model.active_authorization_lease_id = lease.authorization_lease_id
                head_model.version = 2

                await connection.execute(text("SET LOCAL session_replication_role = replica"))
                await connection.execute(
                    insert(cast(Any, WorkflowProtectedRuntimeStartCoordinationHeadModel.__table__)),
                    _model_values(head_model),
                )
                await connection.execute(
                    insert(
                        cast(
                            Any,
                            WorkflowProtectedRuntimeStartAuthorizationLeaseModel.__table__,
                        )
                    ),
                    _model_values(lease_model),
                )
                await connection.execute(text("SET LOCAL session_replication_role = origin"))

                def session_factory() -> AsyncSession:
                    return AsyncSession(
                        bind=connection,
                        expire_on_commit=False,
                        join_transaction_mode="create_savepoint",
                    )

                projected_repository = PostgreSQLWorkflowPlanRepository(
                    engine=engine, session_factory=session_factory
                )
                before = await (
                    projected_repository.list_protected_runtime_start_authorization_presentations(
                        scope=lease.scope,
                        authorization_lease_ids=(lease.authorization_lease_id,),
                    )
                )
                assert len(before) == 1
                assert before[0].consumed is False
                assert before[0].protected_runtime_start_authority_granted is False

                await connection.execute(
                    text(
                        "UPDATE workflow_event_runtime_start_coordination_heads SET "
                        "state = 'start_attempt_pending', "
                        "consumption_claim_id = 'consumption.imp-224-test', "
                        "runtime_start_attempt_id = 'start-attempt.imp-224-test', "
                        "runtime_start_attempt_pending = TRUE, version = 3, "
                        "updated_at = clock_timestamp() "
                        "WHERE runtime_envelope_id = :envelope_id"
                    ),
                    {"envelope_id": head_model.runtime_envelope_id},
                )
                after = await (
                    projected_repository.list_protected_runtime_start_authorization_presentations(
                        scope=lease.scope,
                        authorization_lease_ids=(lease.authorization_lease_id,),
                    )
                )
                assert len(after) == 1
                assert after[0].consumed is True
                assert after[0].protected_runtime_start_authority_granted is False

                append_savepoint = await connection.begin_nested()
                with pytest.raises(DBAPIError, match="append-only"):
                    await connection.execute(
                        text(
                            "UPDATE workflow_event_runtime_start_auth_leases "
                            "SET canonical_digest = :digest "
                            "WHERE authorization_lease_id = :lease_id"
                        ),
                        {"digest": "0" * 64, "lease_id": lease.authorization_lease_id},
                    )
                await append_savepoint.rollback()

                downgrade_savepoint = await connection.begin_nested()
                with pytest.raises(DBAPIError, match="refusing guarded downgrade"):
                    await connection.execute(
                        text(
                            "DO $$ BEGIN "
                            "IF EXISTS (SELECT 1 FROM "
                            "workflow_event_runtime_start_auth_leases LIMIT 1) "
                            "OR EXISTS (SELECT 1 FROM "
                            "workflow_event_runtime_start_auth_claims LIMIT 1) THEN "
                            "RAISE EXCEPTION 'refusing guarded downgrade: "
                            "protected runtime-start authorization evidence exists' "
                            "USING ERRCODE = '55000'; END IF; END $$;"
                        )
                    )
                await downgrade_savepoint.rollback()

                await connection.execute(text("CREATE TEMP TABLE rtstart_append_probe (id int)"))
                await connection.execute(
                    text(
                        "CREATE TRIGGER rtstart_append_probe_trigger "
                        "BEFORE UPDATE OR DELETE ON rtstart_append_probe "
                        "FOR EACH ROW EXECUTE FUNCTION reject_wf_rtstart_auth_mutation()"
                    )
                )
                await connection.execute(text("INSERT INTO rtstart_append_probe VALUES (1)"))
                with pytest.raises(Exception, match="append-only"):
                    await connection.execute(text("UPDATE rtstart_append_probe SET id = 2"))
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_live_postgres_coordination_head_has_one_concurrent_winner_when_configured() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    engine = create_async_engine(database_url)
    table_name = f"imp223_coord_race_{uuid4().hex}"
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    f"CREATE UNLOGGED TABLE {table_name} "
                    "(LIKE workflow_event_runtime_start_coordination_heads INCLUDING ALL)"
                )
            )
        async with engine.connect() as reflection_connection:
            table = await reflection_connection.run_sync(
                lambda sync_connection: Table(table_name, MetaData(), autoload_with=sync_connection)
            )

        use_result_id = f"runtime-use-result.concurrent.{uuid4().hex}"
        first_row = _coordination_row(suffix=uuid4().hex, use_result_id=use_result_id)
        second_row = _coordination_row(suffix=uuid4().hex, use_result_id=use_result_id)
        async with engine.connect() as first, engine.connect() as second:
            first_tx = await first.begin()
            second_tx = await second.begin()
            await first.execute(insert(table), first_row)
            competing = asyncio.create_task(second.execute(insert(table), second_row))
            await asyncio.sleep(0.1)
            assert competing.done() is False
            await first_tx.commit()
            with pytest.raises(IntegrityError):
                await competing
            await second_tx.rollback()

        async with engine.connect() as connection:
            assert await connection.scalar(select(func.count()).select_from(table)) == 1
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
        await engine.dispose()
