from __future__ import annotations

import asyncio
import importlib.util
import inspect
import os
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy import CheckConstraint, Constraint, Index, Table, UniqueConstraint, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from atlas.core.persistence.models import (
    WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultModel,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBindingClaimModel,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBindingModel,
)
from atlas.modules.workflows.adapters.memory import InMemoryWorkflowPlanRepository
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.adapters.unavailable import UnavailableWorkflowPlanRepository
from atlas.modules.workflows.application.target_context_capsule_consumer_binding_ports import (
    WorkflowProtectedTransportTargetContextCapsuleConsumerBindingError,
    WorkflowTargetContextCapsuleConsumerBindingRequest,
    WorkflowTargetContextCapsuleConsumerBindingStatus,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBindingAuthority,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBindingState,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_transport_target_context_capsule_consumer_binding_policy,
)

MIGRATION = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "20260816_0134_workflow_target_context_capsule_consumer_binding.py"
)
SCOPE = WorkflowScope("org-atlas", "environment-lab", "site-istanbul")
AUTHORITY_COLUMNS = (
    "route_selection_authority_granted",
    "route_binding_authority_granted",
    "endpoint_resolution_authority_granted",
    "protected_artifact_access_authority_granted",
    "credential_selection_authority_granted",
    "credential_assignment_binding_authority_granted",
    "credential_access_authority_granted",
    "credential_brokerage_authority_granted",
    "credential_resolution_authority_granted",
    "credential_delivery_authority_granted",
    "network_access_authority_granted",
    "readiness_probe_authority_granted",
    "publication_authority_granted",
    "delivery_authority_granted",
    "dispatch_authority_granted",
    "execution_authority_granted",
    "infrastructure_mutation_authority_granted",
)
CODE_OWNED_CONTRACT = {
    "consumer_subject_id": ("service.workflow-protected-transport-target-context-capsule-consumer"),
    "consumer_audience": ("audience.workflow-protected-transport-target-context-capsule-consumer"),
    "consumer_contract_id": (
        "contract.workflow-protected-transport-target-context-capsule-consumer"
    ),
    "consumer_contract_version": "1.0",
    "purpose_id": (
        "purpose.workflow-protected-transport-target-context-capsule-handoff-evaluation"
    ),
    "policy_id": "policy.workflow-protected-transport-target-context-capsule-consumer-binding",
    "policy_version": "1.0",
    "policy_digest": "1f7d71594e9ffdc863626ef68e53e9cc0ff829a81511aaf52b7c2c7f82a85e8f",
    "binder_subject_id": "service.workflow-protected-transport-target-context-capsule-binder",
    "binder_audience": "audience.workflow-protected-transport-target-context-capsule-binder",
}


def _unique_columns(table: Table) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _named_check_sql(table: Table, name: str) -> str:
    return str(
        next(
            constraint.sqltext
            for constraint in table.constraints
            if isinstance(constraint, CheckConstraint) and constraint.name == name
        )
    )


def test_schema_is_append_only_scoped_single_binding_and_zero_authority() -> None:
    binding = cast(
        Table,
        WorkflowProtectedTransportTargetContextCapsuleConsumerBindingModel.__table__,
    )
    claim = cast(
        Table,
        WorkflowProtectedTransportTargetContextCapsuleConsumerBindingClaimModel.__table__,
    )
    assert binding.name == "workflow_event_tctx_capsule_consumer_bindings"
    assert claim.name == "workflow_event_tctx_capsule_consumer_binding_claims"
    assert {
        ("opening_result_id",),
        ("sealed_capsule_id",),
        ("canonical_digest",),
        (
            "outbox_entry_id",
            "event_id",
            "event_artifact_id",
            "consumer_subject_id",
            "consumer_contract_id",
            "consumer_contract_version",
            "purpose_id",
        ),
    } <= _unique_columns(binding)
    assert {
        ("idempotency_scope_id", "idempotency_key"),
        ("binding_id",),
        ("canonical_digest",),
    } <= _unique_columns(claim)
    assert {
        "authorization_audit_digest",
        "authorization_audit_payload",
        "binder_audience",
        "idempotency_digest",
        "request_fingerprint",
    } <= set(claim.columns.keys())
    assert {
        "capsule_schema_id",
        "capsule_schema_version",
        "capsule_is_bearer_capability",
        "logical_channel_binding_id",
        "workflow_execution_attempt_id",
        "effective_until",
    } <= set(binding.columns.keys())
    checks = "\n".join(
        str(constraint.sqltext)
        for constraint in binding.constraints
        if isinstance(constraint, CheckConstraint)
    )
    assert all(f"NOT {column}" in checks for column in AUTHORITY_COLUMNS)
    assert "state = 'bound'" in checks
    assert "bound_at < effective_until" in checks
    assert "NOT capsule_is_bearer_capability" in checks
    claim_checks = "\n".join(
        str(constraint.sqltext)
        for constraint in claim.constraints
        if isinstance(constraint, CheckConstraint)
    )
    assert "authorization_audit_digest ~ '^[0-9a-f]{64}$'" in claim_checks
    assert "authorization_audit_payload <> '{}'::jsonb" in claim_checks
    for table in (binding, claim):
        schema_items: tuple[Constraint | Index, ...] = (*table.constraints, *table.indexes)
        assert all(len(item.name) <= 63 for item in schema_items if isinstance(item.name, str))


def test_code_owned_contract_is_identical_in_orm_and_migration() -> None:
    binding = cast(
        Table,
        WorkflowProtectedTransportTargetContextCapsuleConsumerBindingModel.__table__,
    )
    claim = cast(
        Table,
        WorkflowProtectedTransportTargetContextCapsuleConsumerBindingClaimModel.__table__,
    )
    migration = _migration_module()
    contract_checks = (
        _named_check_sql(binding, "ck_wf_tctx_capsule_binding_contract"),
        _named_check_sql(claim, "ck_wf_tctx_capsule_claim_contract"),
        migration._code_owned_contract_check(),
    )
    for check in contract_checks:
        for column, value in CODE_OWNED_CONTRACT.items():
            assert f"{column} = '{value}'" in check

    policy = (
        code_owned_workflow_protected_transport_target_context_capsule_consumer_binding_policy()
    )
    assert {
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "binder_subject_id": CODE_OWNED_CONTRACT["binder_subject_id"],
        "binder_audience": CODE_OWNED_CONTRACT["binder_audience"],
    } == CODE_OWNED_CONTRACT

    migration_source = MIGRATION.read_text(encoding="utf-8")
    assert 'name="ck_wf_tctx_capsule_binding_contract"' in migration_source
    assert 'name="ck_wf_tctx_capsule_claim_contract"' in migration_source


def test_migration_is_linear_guarded_and_installs_two_append_only_tables() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20260816_0134"' in migration
    assert 'down_revision: str | None = "20260815_0133"' in migration
    assert "workflow_event_tctx_capsule_consumer_bindings" in migration
    assert "workflow_event_tctx_capsule_consumer_binding_claims" in migration
    assert "trg_wf_tctx_capsule_bindings_append_only" in migration
    assert "trg_wf_tctx_capsule_claims_append_only" in migration
    assert "BEFORE UPDATE OR DELETE" in migration
    assert "refusing to downgrade target-context capsule consumer binding schema" in migration
    assert "append-only tables contain evidence" in migration
    assert "op.drop_table(CLAIM_TABLE)" in migration
    assert "op.drop_table(BINDING_TABLE)" in migration


def _migration_module() -> Any:
    spec = importlib.util.spec_from_file_location("imp211_schema_migration", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_downgrade_guard_runs_before_destructive_steps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = _migration_module()
    executed: list[str] = []
    dropped: list[str] = []
    monkeypatch.setattr(migration.op, "execute", lambda statement: executed.append(str(statement)))
    monkeypatch.setattr(migration.op, "drop_table", dropped.append)

    migration.downgrade()

    assert executed[0] == migration.DOWNGRADE_EMPTY_GUARD_SQL
    assert f"SELECT 1 FROM {migration.CLAIM_TABLE} LIMIT 1" in executed[0]
    assert f"SELECT 1 FROM {migration.BINDING_TABLE} LIMIT 1" in executed[0]
    assert "ERRCODE = '55000'" in executed[0]
    assert dropped == [migration.CLAIM_TABLE, migration.BINDING_TABLE]


def test_repository_is_replay_first_and_commits_binding_with_audit_atomically() -> None:
    source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.bind_target_context_capsule_consumer
    )
    preflight = source.index("_target_context_capsule_consumer_binding_replay")
    lock = source.index("_lock_target_context_capsule_consumer_binding_sources", preflight)
    locked_replay = source.index(
        "_target_context_capsule_consumer_binding_replay_from_locked", lock
    )
    first_evidence = source.index(
        "_target_context_capsule_consumer_binding_evidence", locked_replay
    )
    second_clock = source.index("clock_timestamp", first_evidence)
    second_evidence = source.index(
        "_target_context_capsule_consumer_binding_evidence", second_clock
    )
    binding_add = source.index("_target_context_capsule_consumer_binding_model", second_evidence)
    flush = source.index("await session.flush()", binding_add)
    claim_add = source.index("_target_context_capsule_consumer_binding_claim_model", flush)
    commit = source.index("await session.commit()", claim_add)
    assert (
        preflight
        < lock
        < locked_replay
        < first_evidence
        < second_clock
        < second_evidence
        < binding_add
        < flush
        < claim_add
        < commit
    )
    assert all(
        forbidden not in source
        for forbidden in (
            "open_paired_artifacts",
            "destroy_capsule",
            "socket",
            "publish",
            "dispatch",
        )
    )


def test_repository_locks_full_lineage_and_revalidates_current_heads() -> None:
    locker = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._lock_target_context_capsule_consumer_binding_sources
    )
    for model_name in (
        "WorkflowDispatchEventEnvelopeModel",
        "WorkflowEventByteArtifactModel",
        "_lock_target_context_access_sources",
        "WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseModel",
        "WorkflowEventPhysicalTransportTargetContextAccessConsumptionClaimModel",
        "WorkflowEventPhysicalTransportTargetContextArtifactOpeningAttemptModel",
        "WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultModel",
        "WorkflowProtectedTransportTargetContextCapsuleConsumerBindingModel",
        "WorkflowProtectedTransportTargetContextCapsuleConsumerBindingClaimModel",
        "clock_timestamp",
    ):
        assert model_name in locker
    assert locker.count(".with_for_update()") >= 8

    shared_access_lock = locker.index("self._lock_target_context_access_sources")
    event_lock = locker.index("WorkflowDispatchEventEnvelopeModel", shared_access_lock)
    artifact_lock = locker.index("WorkflowEventByteArtifactModel", event_lock)
    assert shared_access_lock < event_lock < artifact_lock

    shared_locker = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._lock_target_context_access_sources
    )
    target_context_lock = shared_locker.index(
        "WorkflowEventPhysicalTransportTargetContextBindingModel"
    )
    shared_outbox_lock = shared_locker.index(
        "WorkflowDispatchOutboxEntryModel", target_context_lock
    )
    assert target_context_lock < shared_outbox_lock

    matcher = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._target_context_capsule_consumer_binding_evidence
    )
    for evidence in (
        "_target_context_artifact_opening_lineage_matches",
        "_target_context_binding_evidence",
        "require_live_overlap=True",
        "selection_superseded",
        "credential_generation",
        "rotation_epoch",
        "route_head_fencing_token_digest",
        "PENDING_PUBLICATION",
        "capsule_is_bearer_capability",
        "minimum_remaining_lifetime_seconds",
    ):
        assert evidence in matcher


def test_replay_reconstructs_full_code_owned_audit_and_checks_scope() -> None:
    replay = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._target_context_capsule_consumer_binding_replay
    )
    assert "idempotency_scope_id" in replay
    assert "opening_result_id" in replay
    assert "with_for_update" in replay
    reader = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._target_context_capsule_consumer_binding_from_claim
    )
    assert "_target_context_capsule_consumer_binding_expected_audit_payload" in reader
    assert "authorization_audit_digest != canonical_digest(audit_payload)" in reader
    assert "dict(claim.authorization_audit_payload) != audit_payload" in reader


@pytest.mark.asyncio
async def test_non_postgres_adapters_fail_closed() -> None:
    for repository in (
        InMemoryWorkflowPlanRepository(),
        UnavailableWorkflowPlanRepository(),
    ):
        with pytest.raises(WorkflowProtectedTransportTargetContextCapsuleConsumerBindingError):
            await repository.list_target_context_capsule_consumer_bindings(scope=SCOPE, limit=1)


async def _live_engine() -> AsyncEngine:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    return create_async_engine(database_url, pool_pre_ping=True)


@pytest.mark.asyncio
async def test_live_postgres_capsule_binding_schema_and_triggers_are_installed() -> None:
    engine = await _live_engine()
    try:
        async with engine.connect() as connection:
            tables = set(
                (
                    await connection.execute(
                        text(
                            "SELECT table_name FROM information_schema.tables "
                            "WHERE table_name IN "
                            "('workflow_event_tctx_capsule_consumer_bindings', "
                            "'workflow_event_tctx_capsule_consumer_binding_claims')"
                        )
                    )
                ).scalars()
            )
            triggers = set(
                (
                    await connection.execute(
                        text(
                            "SELECT tgname FROM pg_trigger WHERE tgname IN "
                            "('trg_wf_tctx_capsule_bindings_append_only', "
                            "'trg_wf_tctx_capsule_claims_append_only')"
                        )
                    )
                ).scalars()
            )
        assert tables == {
            "workflow_event_tctx_capsule_consumer_bindings",
            "workflow_event_tctx_capsule_consumer_binding_claims",
        }
        assert triggers == {
            "trg_wf_tctx_capsule_bindings_append_only",
            "trg_wf_tctx_capsule_claims_append_only",
        }
    finally:
        await engine.dispose()


def _binding_values(*, seed: str, number: int) -> dict[str, object]:
    table = cast(
        Table,
        WorkflowProtectedTransportTargetContextCapsuleConsumerBindingModel.__table__,
    )
    now = datetime(2026, 8, 16, tzinfo=UTC)
    values: dict[str, object] = {}
    for column in table.columns:
        name = column.name
        if name in CODE_OWNED_CONTRACT:
            values[name] = CODE_OWNED_CONTRACT[name]
        elif name == "binding_id":
            values[name] = f"binding.live.{seed}.{number}"
        elif name == "opening_result_id":
            values[name] = f"opening.live.{seed}"
        elif name == "sealed_capsule_id":
            values[name] = f"capsule.live.{seed}"
        elif name in AUTHORITY_COLUMNS or name == "capsule_is_bearer_capability":
            values[name] = False
        elif name == "state":
            values[name] = "bound"
        elif name == "bound_at":
            values[name] = now
        elif name == "effective_until":
            values[name] = now + timedelta(minutes=5)
        elif name == "payload":
            values[name] = {"binding_id": f"binding.live.{seed}.{number}"}
        elif name in {"organization_id", "environment_id", "site_id"}:
            values[name] = getattr(SCOPE, name)
        elif name.endswith("_digest") or name in {
            "target_context_commitment",
            "canonical_digest",
        }:
            values[name] = f"{number:x}" * 64
        else:
            values[name] = f"{name}.live.{seed}.{number}"
    return values


def _claim_values(*, seed: str, number: int) -> dict[str, object]:
    table = cast(
        Table,
        WorkflowProtectedTransportTargetContextCapsuleConsumerBindingClaimModel.__table__,
    )
    values: dict[str, object] = {}
    for column in table.columns:
        name = column.name
        if name in CODE_OWNED_CONTRACT:
            values[name] = CODE_OWNED_CONTRACT[name]
        elif name in {"organization_id", "environment_id", "site_id"}:
            values[name] = getattr(SCOPE, name)
        elif name == "created_at":
            values[name] = datetime(2026, 8, 16, tzinfo=UTC)
        elif name == "payload":
            values[name] = {"claim_id": f"claim.live.{seed}.{number}"}
        elif name == "authorization_audit_payload":
            values[name] = {"event_type": "target_context_capsule_consumer_binding_authorized"}
        elif name.endswith("_digest") or name in {
            "idempotency_scope_id",
            "request_fingerprint",
            "canonical_digest",
        }:
            values[name] = f"{number:x}" * 64
        else:
            values[name] = f"{name}.live.{seed}.{number}"
    return values


def _opening_result_values(*, seed: str) -> dict[str, object]:
    table = cast(
        Table,
        WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultModel.__table__,
    )
    now = datetime.now(UTC)
    values: dict[str, object] = {}
    for column in table.columns:
        name = column.name
        if name == "opening_id":
            values[name] = f"opening.repository-live.{seed}"
        elif name in AUTHORITY_COLUMNS or name == "capsule_is_bearer_capability":
            values[name] = False
        elif name in {"protected_sources_closed", "cleanup_confirmed"}:
            values[name] = True
        elif name == "state":
            values[name] = "opened_protected"
        elif name == "failure_class":
            values[name] = None
        elif name == "completed_at":
            values[name] = now
        elif name == "usable_until":
            values[name] = now + timedelta(minutes=5)
        elif name == "payload":
            values[name] = {"opening_id": f"opening.repository-live.{seed}"}
        elif name in {"organization_id", "environment_id", "site_id"}:
            values[name] = getattr(SCOPE, name)
        elif name.endswith("_digest") or name == "target_context_commitment":
            values[name] = "a" * 64
        elif name.endswith("_version"):
            values[name] = "1.0"
        else:
            values[name] = f"{name}.repository-live.{seed}"
    return values


def test_opening_result_fixture_respects_database_string_limits() -> None:
    table = cast(
        Table,
        WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultModel.__table__,
    )
    values = _opening_result_values(seed="a" * 32)

    for column in table.columns:
        value = values[column.name]
        length = getattr(column.type, "length", None)
        if isinstance(value, str) and isinstance(length, int):
            assert len(value) <= length, column.name


def _binding_request(
    *, seed: str, idempotency_key: str
) -> WorkflowTargetContextCapsuleConsumerBindingRequest:
    policy = (
        code_owned_workflow_protected_transport_target_context_capsule_consumer_binding_policy()
    )
    return WorkflowTargetContextCapsuleConsumerBindingRequest(
        opening_result_id=f"opening.repository-live.{seed}",
        opening_result_digest="a" * 64,
        expected_policy_id=policy.policy_id,
        expected_policy_version=policy.policy_version,
        expected_policy_digest=policy.canonical_digest,
        expected_consumer_subject_id=policy.consumer_subject_id,
        expected_consumer_audience=policy.consumer_audience,
        expected_consumer_contract_id=policy.consumer_contract_id,
        expected_consumer_contract_version=policy.consumer_contract_version,
        expected_purpose_id=policy.purpose_id,
        minimum_remaining_lifetime_seconds=policy.minimum_remaining_lifetime_seconds,
        scope=SCOPE,
        binder_subject_id=CODE_OWNED_CONTRACT["binder_subject_id"],
        binder_audience=CODE_OWNED_CONTRACT["binder_audience"],
        requested_at=datetime.now(UTC),
        idempotency_key=idempotency_key,
        idempotency_digest="b" * 64,
        request_fingerprint="c" * 64,
    )


@dataclass(frozen=True, slots=True)
class _TransactionPathLockedSources:
    """Minimal lock result for the isolated repository transaction-path test."""

    existing_bindings: tuple[object, ...]
    idempotency_claim: object | None
    observed_at: datetime


def _transaction_path_binding(
    request: WorkflowTargetContextCapsuleConsumerBindingRequest,
    *,
    bound_at: datetime,
) -> tuple[
    WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
    dict[str, object],
]:
    policy = (
        code_owned_workflow_protected_transport_target_context_capsule_consumer_binding_policy()
    )
    binding_seed = canonical_digest(
        {
            "opening_result_id": request.opening_result_id,
            "scope": request.scope.canonical_value(),
        }
    )
    authority = WorkflowProtectedTransportTargetContextCapsuleConsumerBindingAuthority()
    values: dict[str, object] = {
        "binding_id": f"workflow-target-context-capsule-consumer-binding.{binding_seed[:48]}",
        "opening_result_id": request.opening_result_id,
        "opening_result_digest": request.opening_result_digest,
        "opening_attempt_id": f"opening-attempt.{binding_seed[:32]}",
        "opening_attempt_digest": "1" * 64,
        "lease_consumption_claim_id": f"lease-claim.{binding_seed[:32]}",
        "lease_consumption_claim_digest": "2" * 64,
        "authorization_lease_id": f"authorization-lease.{binding_seed[:32]}",
        "authorization_lease_digest": "3" * 64,
        "sealed_capsule_id": f"sealed-capsule.{binding_seed[:32]}",
        "sealed_capsule_digest": "4" * 64,
        "capsule_schema_id": "schema.workflow-sealed-target-context-capsule-lineage",
        "capsule_schema_version": "1.0",
        "capsule_is_bearer_capability": False,
        "target_context_binding_id": f"target-context-binding.{binding_seed[:32]}",
        "target_context_binding_digest": "5" * 64,
        "target_context_commitment": "6" * 64,
        "outbox_entry_id": f"dispatch-outbox.{binding_seed[:32]}",
        "outbox_entry_digest": "7" * 64,
        "event_id": f"workflow-event.{binding_seed[:32]}",
        "event_digest": "8" * 64,
        "event_artifact_id": f"workflow-event-artifact.{binding_seed[:32]}",
        "event_artifact_digest": "9" * 64,
        "logical_channel_binding_id": f"logical-channel-binding.{binding_seed[:32]}",
        "logical_channel_binding_digest": "a" * 64,
        "physical_transport_route_binding_id": f"route-binding.{binding_seed[:32]}",
        "physical_transport_route_binding_digest": "b" * 64,
        "transport_route_snapshot_id": f"route-snapshot.{binding_seed[:32]}",
        "transport_route_snapshot_digest": "c" * 64,
        "physical_transport_credential_assignment_binding_id": (
            f"credential-binding.{binding_seed[:32]}"
        ),
        "physical_transport_credential_assignment_binding_digest": "d" * 64,
        "credential_assignment_snapshot_id": f"credential-snapshot.{binding_seed[:32]}",
        "credential_assignment_snapshot_digest": "e" * 64,
        "plan_id": f"workflow-plan.{binding_seed[:32]}",
        "plan_digest": "f" * 64,
        "run_id": f"workflow-run.{binding_seed[:32]}",
        "run_digest": "0" * 64,
        "step_run_id": f"workflow-step-run.{binding_seed[:32]}",
        "step_run_digest": "1" * 64,
        "workflow_execution_attempt_id": f"workflow-attempt.{binding_seed[:32]}",
        "workflow_execution_attempt_digest": "2" * 64,
        "target_id": f"storage-target.{binding_seed[:32]}",
        "target_type": "storage",
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "scope": request.scope,
        "binder_subject_id": request.binder_subject_id,
        "binder_audience": request.binder_audience,
        "bound_at": bound_at,
        "effective_until": bound_at + timedelta(minutes=5),
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "request_fingerprint": request.request_fingerprint,
        "idempotency_digest": request.idempotency_digest,
        "state": WorkflowProtectedTransportTargetContextCapsuleConsumerBindingState.BOUND,
        "authority": authority,
    }
    audit_payload: dict[str, object] = {
        "authority": authority.canonical_value(),
        "binder_audience": request.binder_audience,
        "binder_subject_id": request.binder_subject_id,
        "binding_id": values["binding_id"],
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "consumer_subject_id": policy.consumer_subject_id,
        "event_artifact_id": values["event_artifact_id"],
        "event_id": values["event_id"],
        "idempotency_digest": request.idempotency_digest,
        "opening_result_digest": request.opening_result_digest,
        "opening_result_id": request.opening_result_id,
        "outbox_entry_id": values["outbox_entry_id"],
        "policy_digest": policy.canonical_digest,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "purpose_id": policy.purpose_id,
        "request_fingerprint": request.request_fingerprint,
        "schema_id": "audit.workflow-target-context-capsule-consumer-binding",
        "schema_version": "1.0",
        "scope": request.scope.canonical_value(),
    }
    values["authorization_audit_digest"] = canonical_digest(audit_payload)
    canonical_values = (
        PostgreSQLWorkflowPlanRepository._target_context_capsule_consumer_binding_payload_values(
            values
        )
    )
    binding = WorkflowProtectedTransportTargetContextCapsuleConsumerBinding(
        **cast(Any, values), canonical_digest=canonical_digest(canonical_values)
    )
    return binding, audit_payload


@pytest.mark.asyncio
async def test_live_postgres_rejects_every_non_code_owned_contract_value() -> None:
    engine = await _live_engine()
    seed = uuid4().hex
    tables_and_values = (
        (
            cast(
                Table,
                WorkflowProtectedTransportTargetContextCapsuleConsumerBindingModel.__table__,
            ),
            _binding_values(seed=seed, number=7),
        ),
        (
            cast(
                Table,
                WorkflowProtectedTransportTargetContextCapsuleConsumerBindingClaimModel.__table__,
            ),
            _claim_values(seed=seed, number=8),
        ),
    )
    try:
        for table, valid_values in tables_and_values:
            for column in CODE_OWNED_CONTRACT:
                invalid_values = {**valid_values, column: f"caller-selected.{column}"}
                with pytest.raises(IntegrityError):
                    async with engine.begin() as connection:
                        await connection.execute(
                            text("SET LOCAL session_replication_role = replica")
                        )
                        await connection.execute(table.insert(), invalid_values)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_live_postgres_repository_bind_is_concurrent_and_fails_closed() -> None:
    engine = await _live_engine()
    seed = uuid4().hex
    opening_table = cast(
        Table,
        WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultModel.__table__,
    )
    repository = PostgreSQLWorkflowPlanRepository(engine=engine)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SET LOCAL session_replication_role = replica"))
            await connection.execute(opening_table.insert(), _opening_result_values(seed=seed))

        requests = tuple(
            _binding_request(seed=seed, idempotency_key=f"repository-live-{seed}-{number}")
            for number in range(4)
        )
        results = await asyncio.wait_for(
            asyncio.gather(
                *(repository.bind_target_context_capsule_consumer(request) for request in requests)
            ),
            timeout=15,
        )
        assert {result.status for result in results} == {
            WorkflowTargetContextCapsuleConsumerBindingStatus.EVIDENCE_CONFLICT
        }

        binding_table = cast(
            Table,
            WorkflowProtectedTransportTargetContextCapsuleConsumerBindingModel.__table__,
        )
        async with engine.connect() as connection:
            stored = await connection.scalar(
                text(
                    f"SELECT count(*) FROM {binding_table.name} "
                    "WHERE opening_result_id = :opening_result_id"
                ),
                {"opening_result_id": f"opening.repository-live.{seed}"},
            )
        assert stored == 0
    finally:
        async with engine.begin() as connection:
            await connection.execute(text("SET LOCAL session_replication_role = replica"))
            await connection.execute(
                opening_table.delete().where(
                    opening_table.c.opening_id == f"opening.repository-live.{seed}"
                )
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_live_postgres_repository_transaction_path_is_atomic_and_replay_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise repository persistence without duplicating the IMP-208/210 lineage.

    The isolated session bypasses foreign keys and append-only triggers only. The
    binding and claim CHECK/unique constraints plus the repository's real
    insert/flush/commit, replay, conflict, and rollback paths remain active.
    """
    engine = await _live_engine()
    seed = uuid4().hex
    request = _binding_request(
        seed=seed,
        idempotency_key=f"repository-transaction-live-{seed}",
    )
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

    async def lock_transaction_sources(
        _session: AsyncSession,
        *,
        request: WorkflowTargetContextCapsuleConsumerBindingRequest,
    ) -> _TransactionPathLockedSources:
        del request
        return _TransactionPathLockedSources(
            existing_bindings=(),
            idempotency_claim=None,
            observed_at=datetime.now(UTC),
        )

    def deterministic_evidence(
        _locked: _TransactionPathLockedSources,
        *,
        request: WorkflowTargetContextCapsuleConsumerBindingRequest,
    ) -> dict[str, object]:
        del request
        return {"transaction_path_isolated": True}

    def deterministic_binding(
        *,
        request: WorkflowTargetContextCapsuleConsumerBindingRequest,
        evidence: dict[str, object],
        bound_at: datetime,
    ) -> tuple[
        WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
        dict[str, object],
    ]:
        assert evidence == {"transaction_path_isolated": True}
        binding, audit_payload = _transaction_path_binding(request, bound_at=bound_at)
        assert (
            audit_payload
            == repository._target_context_capsule_consumer_binding_expected_audit_payload(binding)
        )
        return binding, audit_payload

    monkeypatch.setattr(
        repository,
        "_lock_target_context_capsule_consumer_binding_sources",
        lock_transaction_sources,
    )
    monkeypatch.setattr(
        repository,
        "_target_context_capsule_consumer_binding_evidence",
        deterministic_evidence,
    )
    monkeypatch.setattr(
        repository,
        "_target_context_capsule_consumer_binding",
        deterministic_binding,
    )

    binding_table = cast(
        Table,
        WorkflowProtectedTransportTargetContextCapsuleConsumerBindingModel.__table__,
    )
    claim_table = cast(
        Table,
        WorkflowProtectedTransportTargetContextCapsuleConsumerBindingClaimModel.__table__,
    )
    try:
        concurrent = await asyncio.wait_for(
            asyncio.gather(
                repository.bind_target_context_capsule_consumer(request),
                repository.bind_target_context_capsule_consumer(request),
            ),
            timeout=15,
        )
        assert (
            sum(
                result.status is WorkflowTargetContextCapsuleConsumerBindingStatus.BOUND
                for result in concurrent
            )
            == 1
        )
        assert (
            sum(
                result.status
                in {
                    WorkflowTargetContextCapsuleConsumerBindingStatus.REPLAY,
                    WorkflowTargetContextCapsuleConsumerBindingStatus.ALREADY_BOUND,
                }
                for result in concurrent
            )
            == 1
        )

        exact_replay = await repository.bind_target_context_capsule_consumer(request)
        assert exact_replay.status is WorkflowTargetContextCapsuleConsumerBindingStatus.REPLAY
        assert exact_replay.binding is not None

        changed_replay = await repository.bind_target_context_capsule_consumer(
            replace(request, request_fingerprint="d" * 64)
        )
        assert (
            changed_replay.status
            is WorkflowTargetContextCapsuleConsumerBindingStatus.IDEMPOTENCY_CONFLICT
        )
        assert changed_replay.binding is None

        changed_idempotency = await repository.bind_target_context_capsule_consumer(
            replace(
                request,
                idempotency_key=f"repository-transaction-live-changed-{seed}",
                idempotency_digest="e" * 64,
                request_fingerprint="f" * 64,
            )
        )
        assert (
            changed_idempotency.status
            is WorkflowTargetContextCapsuleConsumerBindingStatus.ALREADY_BOUND
        )
        assert changed_idempotency.binding is None

        async with engine.connect() as connection:
            binding_rows = (
                (
                    await connection.execute(
                        text(
                            f"SELECT binding_id FROM {binding_table.name} "
                            "WHERE opening_result_id = :opening_result_id"
                        ),
                        {"opening_result_id": request.opening_result_id},
                    )
                )
                .mappings()
                .all()
            )
            claim_rows = (
                (
                    await connection.execute(
                        text(
                            f"SELECT binding_id, authorization_audit_payload "
                            f"FROM {claim_table.name} "
                            "WHERE opening_result_id = :opening_result_id"
                        ),
                        {"opening_result_id": request.opening_result_id},
                    )
                )
                .mappings()
                .all()
            )
        assert len(binding_rows) == len(claim_rows) == 1
        assert binding_rows[0]["binding_id"] == claim_rows[0]["binding_id"]
        assert dict(claim_rows[0]["authorization_audit_payload"]) == (
            repository._target_context_capsule_consumer_binding_expected_audit_payload(
                exact_replay.binding
            )
        )
    finally:
        async with engine.begin() as connection:
            await connection.execute(text("SET LOCAL session_replication_role = replica"))
            await connection.execute(
                claim_table.delete().where(
                    claim_table.c.opening_result_id == request.opening_result_id
                )
            )
            await connection.execute(
                binding_table.delete().where(
                    binding_table.c.opening_result_id == request.opening_result_id
                )
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_live_postgres_one_binding_per_opening_and_capsule_is_concurrent() -> None:
    engine = await _live_engine()
    seed = uuid4().hex
    table = cast(
        Table,
        WorkflowProtectedTransportTargetContextCapsuleConsumerBindingModel.__table__,
    )

    async def insert(number: int) -> bool:
        try:
            async with engine.begin() as connection:
                await connection.execute(text("SET LOCAL session_replication_role = replica"))
                await connection.execute(table.insert(), _binding_values(seed=seed, number=number))
            return True
        except IntegrityError:
            return False

    try:
        outcomes = await asyncio.gather(insert(1), insert(2))
        assert sorted(outcomes) == [False, True]
        with pytest.raises(DBAPIError):
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        "UPDATE workflow_event_tctx_capsule_consumer_bindings "
                        "SET request_fingerprint = :digest "
                        "WHERE opening_result_id = :opening_result_id"
                    ),
                    {
                        "digest": "9" * 64,
                        "opening_result_id": f"opening.live.{seed}",
                    },
                )
        migration = _migration_module()
        with pytest.raises(DBAPIError, match="append-only tables contain evidence"):
            async with engine.begin() as connection:
                await connection.execute(text(migration.DOWNGRADE_EMPTY_GUARD_SQL))
    finally:
        await engine.dispose()
