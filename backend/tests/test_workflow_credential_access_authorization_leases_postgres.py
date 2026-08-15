from __future__ import annotations

import asyncio
import inspect
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest
from sqlalchemy import CheckConstraint, Table, UniqueConstraint, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from test_workflow_route_freshness_admissions import CollectingAuditSink
from test_workflow_transport_credential_assignment_bindings_postgres import (
    _request as credential_binding_request,
)
from test_workflow_transport_credential_assignment_bindings_postgres import (
    _seed_live_sources as seed_binding_sources,
)
from test_workflow_transport_credential_assignment_freshness_admissions_postgres import (
    _admission_request,
    _head,
    _reset_live,
)

from atlas.core.persistence.models import (
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationClaimModel,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel,
)
from atlas.modules.workflows.adapters.memory import InMemoryWorkflowPlanRepository
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.adapters.unavailable import UnavailableWorkflowPlanRepository
from atlas.modules.workflows.application import (
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_SUBJECT,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseService,
    WorkflowPhysicalTransportCredentialAccessorContext,
    WorkflowTransportCredentialAccessAuthorizationLeaseError,
)
from atlas.modules.workflows.domain import (
    WorkflowScope,
    code_owned_workflow_event_physical_transport_credential_access_authorization_policy,
)

MIGRATION = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "20260815_0129_workflow_credential_access_authorization_leases.py"
)


def _unique_columns(table: Table) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _context(
    scope: WorkflowScope, requested_at: datetime
) -> WorkflowPhysicalTransportCredentialAccessorContext:
    return WorkflowPhysicalTransportCredentialAccessorContext(
        subject_id=WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_SUBJECT,
        actor_type="service",
        authentication_method="workload_token",
        credential_audience=WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_AUDIENCE,
        scope=scope,
        correlation_id="correlation.credential-access-authorization-postgres.0001",
        decision_id="decision.credential-access-authorization-postgres.0001",
        requested_at=requested_at,
    )


def test_models_enforce_one_lease_atomic_claim_exact_window_and_single_authority() -> None:
    lease = cast(
        Table,
        WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel.__table__,
    )
    claim = cast(
        Table,
        WorkflowEventPhysicalTransportCredentialAccessAuthorizationClaimModel.__table__,
    )
    assert lease.name == "workflow_event_transport_credential_access_authorization_leases"
    assert claim.name == "workflow_event_transport_credential_access_authorization_claims"
    assert {("freshness_admission_id",), ("canonical_digest",)} <= _unique_columns(lease)
    assert {
        ("idempotency_scope_id", "idempotency_key"),
        ("authorization_lease_id",),
        ("canonical_digest",),
    } <= _unique_columns(claim)
    checks = "\n".join(
        str(constraint.sqltext)
        for constraint in lease.constraints
        if isinstance(constraint, CheckConstraint)
    )
    assert "valid_until = issued_at + INTERVAL '15 seconds'" in checks
    assert "credential_access_authority_granted" in checks
    authority_columns = {
        column.name for column in lease.columns if column.name.endswith("_authority_granted")
    }
    assert len(authority_columns) == 17
    assert all(
        name == "credential_access_authority_granted" or f"NOT {name}" in checks
        for name in authority_columns
    )
    forbidden = {
        "username",
        "password",
        "token",
        "private_key",
        "certificate",
        "secret",
        "vault_path",
        "secret_reference",
        "credential_profile",
        "target_commitment",
        "broker",
        "provider_handle",
        "url",
        "hostname",
        "ip_address",
        "port",
        "endpoint",
        "protected_artifact",
        "header",
        "command",
        "environment_variable",
        "provider_response",
    }
    assert not forbidden & (set(lease.columns.keys()) | set(claim.columns.keys()))


def test_repository_uses_adr_156_lock_order_two_db_clocks_and_atomic_insert() -> None:
    source = inspect.getsource(PostgreSQLWorkflowPlanRepository.authorize_credential_access)
    lock = source.index("_lock_credential_access_authorization_sources")
    replay = source.index("_credential_access_authorization_replay", lock)
    evidence = source.index("_credential_access_authorization_evidence_matches", replay)
    audit = source.index("required_precommit_audit", evidence)
    second_clock = source.index("clock_timestamp", audit)
    second_evidence = source.index(
        "_credential_access_authorization_evidence_matches", second_clock
    )
    lease_add = source.index("_credential_access_lease_model", second_evidence)
    flush = source.index("await session.flush()", lease_add)
    claim_add = source.index("_credential_access_claim_model", flush)
    commit = source.index("await session.commit()", claim_add)
    assert lock < replay < evidence < audit < second_clock < second_evidence
    assert second_evidence < lease_add < flush < claim_add < commit

    lock_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._lock_credential_access_authorization_sources
    )
    positions = [
        lock_source.index("binding_row ="),
        lock_source.index("snapshot_row ="),
        lock_source.index("pg_advisory_xact_lock"),
        lock_source.index("assignment_rows ="),
        lock_source.index("admission_row ="),
        lock_source.index("clock_timestamp"),
    ]
    assert positions == sorted(positions)
    assert lock_source.count(".with_for_update()") == 4
    assert "_credential_assignment_registry_lock_id" in lock_source
    assert "rotation_epoch" in lock_source and "credential_generation" in lock_source


def test_migration_is_linear_append_only_and_contains_no_secret_locator_fields() -> None:
    migration = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20260815_0129"' in migration
    assert 'down_revision: str | None = "20260815_0128"' in migration
    assert "valid_until = issued_at + INTERVAL '15 seconds'" in migration
    assert "uq_wf_cred_access_lease_freshness" in migration
    assert "uq_wf_cred_access_claim_idem" in migration
    assert "trg_wf_cred_access_leases_append_only" in migration
    assert "trg_wf_cred_access_claims_append_only" in migration
    assert "reject_wf_credential_access_authorization_mutation" in migration
    assert migration.count("_authority_granted") >= 17
    for forbidden in (
        "vault_path",
        "secret_reference",
        "credential_profile_id",
        "target_scope_commitment",
        "provider_handle",
        "endpoint_url",
    ):
        assert forbidden not in migration


@pytest.mark.asyncio
async def test_unavailable_production_adapter_fails_closed() -> None:
    repository = UnavailableWorkflowPlanRepository()
    with pytest.raises(WorkflowTransportCredentialAccessAuthorizationLeaseError):
        await repository.list_credential_access_authorization_leases(
            scope=WorkflowScope("org-atlas", "environment-lab", "site-istanbul")
        )


@pytest.mark.asyncio
async def test_memory_adapter_preserves_atomic_single_lease_and_exact_replay_parity() -> None:
    requested_at = datetime.now(UTC)
    binding_request, route, snapshot = credential_binding_request(
        bound_at=requested_at - timedelta(seconds=2),
        idempotency_key="credential-binding-for-access-authorization-memory-0001",
        fingerprint="f" * 64,
    )
    binding = binding_request.candidate
    head = _head(route, snapshot)
    freshness_request = _admission_request(
        binding,
        snapshot,
        head,
        requested_at=requested_at,
        idempotency_key="credential-freshness-for-access-authorization-memory-0001",
    )
    repository = InMemoryWorkflowPlanRepository()
    repository._credential_assignment_bindings[
        (binding.physical_transport_route_binding_id, snapshot.snapshot_id)
    ] = binding
    repository._credential_assignment_snapshots[
        (snapshot.assignment_id, snapshot.assignment_revision)
    ] = snapshot
    repository._credential_assignments[(head.assignment_id, head.assignment_revision)] = head
    admitted = await repository.admit_credential_assignment_freshness(freshness_request)
    admission = admitted.admission
    assert admission is not None

    service = WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseService(
        authorization_repository=repository,
        audit_sink=CollectingAuditSink(),
    )
    policy = code_owned_workflow_event_physical_transport_credential_access_authorization_policy()

    async def authorize() -> object:
        return await service.authorize(
            freshness_admission_id=admission.freshness_admission_id,
            freshness_admission_digest=admission.canonical_digest,
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            idempotency_key="credential-access-authorization-memory-0001",
            context=_context(binding.scope, datetime.now(UTC)),
        )

    first = await authorize()
    replay = await authorize()
    assert first == replay
    leases = await repository.list_credential_access_authorization_leases(scope=binding.scope)
    assert leases == (first,)
    assert first.authority.credential_access_authorized is True
    assert all(
        value is False
        for name, value in first.authority.canonical_value().items()
        if name != "credential_access_authorized"
    )


async def _reset_authorization_rows(engine: AsyncEngine, *, freshness_admission_id: str) -> None:
    async with engine.begin() as connection:
        await connection.execute(text("SET LOCAL session_replication_role = replica"))
        await connection.execute(
            text(
                "DELETE FROM workflow_event_transport_credential_access_authorization_claims "
                "WHERE freshness_admission_id = :freshness_admission_id"
            ),
            {"freshness_admission_id": freshness_admission_id},
        )
        await connection.execute(
            text(
                "DELETE FROM workflow_event_transport_credential_access_authorization_leases "
                "WHERE freshness_admission_id = :freshness_admission_id"
            ),
            {"freshness_admission_id": freshness_admission_id},
        )


@pytest.mark.asyncio
async def test_live_postgres_serializes_replay_and_rejects_append_only_mutation() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")

    requested_at = datetime.now(UTC)
    binding_request, route, snapshot = credential_binding_request(
        bound_at=requested_at - timedelta(seconds=2),
        idempotency_key="credential-binding-for-access-authorization-pg-0001",
        fingerprint="e" * 64,
    )
    binding = binding_request.candidate
    head = _head(route, snapshot)
    freshness_request = _admission_request(
        binding,
        snapshot,
        head,
        requested_at=requested_at,
        idempotency_key="credential-freshness-for-access-authorization-pg-0001",
    )
    freshness_id = freshness_request.candidate.freshness_admission_id
    engine = create_async_engine(database_url, pool_pre_ping=True)
    try:
        await _reset_authorization_rows(engine, freshness_admission_id=freshness_id)
        await _reset_live(engine, binding_request, assignment_id=head.assignment_id)
        await seed_binding_sources(engine, route=route, assignments=(snapshot,))
        repository = PostgreSQLWorkflowPlanRepository(engine=engine)
        await repository.synchronize_credential_assignments((head,))
        bound = await repository.bind_credential_assignment(binding_request)
        assert bound.binding == binding
        admitted = await repository.admit_credential_assignment_freshness(freshness_request)
        admission = admitted.admission
        assert admission is not None

        service = WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseService(
            authorization_repository=repository,
            audit_sink=CollectingAuditSink(),
        )
        policy = (
            code_owned_workflow_event_physical_transport_credential_access_authorization_policy()
        )

        async def authorize() -> object:
            return await service.authorize(
                freshness_admission_id=admission.freshness_admission_id,
                freshness_admission_digest=admission.canonical_digest,
                policy_id=policy.policy_id,
                policy_version=policy.policy_version,
                idempotency_key="credential-access-authorization-postgres-0001",
                context=_context(binding.scope, datetime.now(UTC)),
            )

        first, replay = await asyncio.gather(authorize(), authorize())
        assert first == replay
        async with engine.connect() as connection:
            lease_count = await connection.scalar(
                text(
                    "SELECT count(*) "
                    "FROM workflow_event_transport_credential_access_authorization_leases "
                    "WHERE freshness_admission_id = :freshness_admission_id"
                ),
                {"freshness_admission_id": freshness_id},
            )
            claim_count = await connection.scalar(
                text(
                    "SELECT count(*) "
                    "FROM workflow_event_transport_credential_access_authorization_claims "
                    "WHERE freshness_admission_id = :freshness_admission_id"
                ),
                {"freshness_admission_id": freshness_id},
            )
        assert lease_count == claim_count == 1

        for statement in (
            "UPDATE workflow_event_transport_credential_access_authorization_leases "
            "SET state = state WHERE freshness_admission_id = :freshness_admission_id",
            "DELETE FROM workflow_event_transport_credential_access_authorization_claims "
            "WHERE freshness_admission_id = :freshness_admission_id",
        ):
            with pytest.raises(DBAPIError):
                async with engine.begin() as connection:
                    await connection.execute(
                        text(statement), {"freshness_admission_id": freshness_id}
                    )
    finally:
        await _reset_authorization_rows(engine, freshness_admission_id=freshness_id)
        await _reset_live(engine, binding_request, assignment_id=head.assignment_id)
        await engine.dispose()
