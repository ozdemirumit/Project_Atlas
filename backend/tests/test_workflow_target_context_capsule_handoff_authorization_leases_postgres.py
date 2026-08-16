from __future__ import annotations

import asyncio
import importlib.util
import inspect
import os
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy import Boolean, CheckConstraint, Table, UniqueConstraint, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from atlas.core.persistence.models import (
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationClaimModel,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseModel,
)
from atlas.modules.workflows.adapters.memory import InMemoryWorkflowPlanRepository
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.adapters.unavailable import UnavailableWorkflowPlanRepository
from atlas.modules.workflows.application import (
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseRequest,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedTargetContextCapsuleLifecycleAttestation,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseState,
    WorkflowProtectedTransportTargetContextCapsuleHandoffLeaseAuthority,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_transport_target_context_capsule_handoff_authorization_policy,
)

MIGRATION = (
    Path(__file__).parents[1]
    / "migrations"
    / "versions"
    / "20260816_0135_workflow_target_context_capsule_handoff_authorization_lease.py"
)
SCOPE = WorkflowScope("org-atlas", "environment-lab", "site-istanbul")
POLICY_DIGEST = "388fc176751bc5af37489bfea61c603106b3658aa60a6ca3459ee0bab9b51270"
CODE_OWNED_CONTRACT = {
    "consumer_subject_id": "service.workflow-protected-transport-target-context-capsule-consumer",
    "consumer_audience": "audience.workflow-protected-transport-target-context-capsule-consumer",
    "consumer_contract_id": "contract.workflow-protected-transport-target-context-capsule-consumer",
    "consumer_contract_version": "1.0",
    "purpose_id": "purpose.workflow-protected-transport-target-context-capsule-handoff-evaluation",
    "policy_id": "policy.workflow-protected-transport-target-context-capsule-handoff-authorization",
    "policy_version": "1.0",
    "policy_digest": POLICY_DIGEST,
}
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


def _unique_columns(table: Table) -> set[tuple[str, ...]]:
    return {
        tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }


def _checks(table: Table) -> str:
    return "\n".join(
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    )


def _migration_module() -> Any:
    spec = importlib.util.spec_from_file_location("imp212_schema_migration", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_schema_is_single_use_non_bearer_and_single_authority() -> None:
    lease = cast(
        Table,
        WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseModel.__table__,
    )
    claim = cast(
        Table,
        WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationClaimModel.__table__,
    )
    assert lease.name == "workflow_event_tctx_capsule_handoff_authorization_leases"
    assert claim.name == "workflow_event_tctx_capsule_handoff_authorization_claims"
    assert {
        ("consumer_binding_id",),
        ("sealed_capsule_id",),
        ("canonical_digest",),
    } <= _unique_columns(lease)
    assert {
        ("idempotency_scope_id", "idempotency_key"),
        ("authorization_lease_id",),
        ("consumer_binding_id",),
        ("sealed_capsule_id",),
        ("canonical_digest",),
    } <= _unique_columns(claim)
    checks = _checks(lease)
    assert "valid_until = issued_at + INTERVAL '1 second'" in checks
    assert "state = 'authorized_unconsumed'" in checks
    assert "single_use AND NOT renewable AND NOT transferable" in checks
    assert "NOT lease_is_bearer_capability" in checks
    assert "NOT capsule_is_bearer_capability" in checks
    assert "target_context_capsule_handoff_authority_granted" in checks
    assert all(f"NOT {name}" in checks for name in AUTHORITY_COLUMNS)
    assert "lifecycle_attestor_id = " in checks
    assert POLICY_DIGEST in checks
    assert "authorization_audit_payload <> '{}'::jsonb" in checks
    assert POLICY_DIGEST in _checks(claim)
    for table in (lease, claim):
        for item in (*table.constraints, *table.indexes):
            item_name = getattr(item, "name", None)
            if isinstance(item_name, str):
                assert len(item_name) <= 63


def test_code_owned_contract_matches_domain_and_migration() -> None:
    policy = code_owned_workflow_protected_transport_target_context_capsule_handoff_authorization_policy()  # noqa: E501
    assert policy.canonical_digest == POLICY_DIGEST
    assert policy.validity_window_seconds == 1
    assert policy.required_capsule_lifecycle_attestor_id == (
        "attestor.workflow-protected-target-context-capsule-lifecycle"
    )
    contract = {
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
    }
    assert contract == CODE_OWNED_CONTRACT
    migration_contract = _migration_module()._contract_check()
    for name, value in CODE_OWNED_CONTRACT.items():
        assert f"{name} = '{value}'" in migration_contract


def test_migration_is_linear_guarded_and_append_only() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20260816_0135"' in source
    assert 'down_revision: str | None = "20260816_0134"' in source
    assert "trg_wf_tctx_handoff_leases_append_only" in source
    assert "trg_wf_tctx_handoff_claims_append_only" in source
    assert "reject_wf_tctx_capsule_handoff_auth_mutation" in source
    assert "BEFORE UPDATE OR DELETE" in source
    assert "refusing to downgrade target-context capsule handoff authorization schema" in source
    assert "append-only tables contain evidence" in source
    migration = _migration_module()
    executed: list[str] = []
    dropped: list[str] = []
    original_execute = migration.op.execute
    original_drop = migration.op.drop_table
    try:
        migration.op.execute = lambda statement: executed.append(str(statement))
        migration.op.drop_table = dropped.append
        migration.downgrade()
    finally:
        migration.op.execute = original_execute
        migration.op.drop_table = original_drop
    assert executed == [migration.DOWNGRADE_EMPTY_GUARD_SQL]
    assert dropped == [migration.CLAIM_TABLE, migration.LEASE_TABLE]


def test_repository_uses_canonical_lock_order_and_atomic_second_validation() -> None:
    authorize = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.authorize_target_context_capsule_handoff
    )
    precommit = authorize.index("required_precommit_audit")
    transaction = authorize.index("async with self._sessions()", precommit)
    lock = authorize.index("_lock_target_context_capsule_handoff_authorization_sources")
    first_evidence = authorize.index("_target_context_capsule_handoff_evidence_matches", lock)
    second_clock = authorize.index("clock_timestamp", first_evidence)
    retime = authorize.index("_target_context_capsule_handoff_retimed_request", second_clock)
    second_evidence = authorize.index("_target_context_capsule_handoff_evidence_matches", retime)
    lease_add = authorize.index("_target_context_capsule_handoff_lease_model", second_evidence)
    flush = authorize.index("await session.flush()", lease_add)
    claim_add = authorize.index("_target_context_capsule_handoff_claim_model", flush)
    commit = authorize.index("await session.commit()", claim_add)
    assert (
        precommit
        < transaction
        < lock
        < first_evidence
        < second_clock
        < retime
        < second_evidence
        < lease_add
        < flush
        < claim_add
        < commit
    )
    assert "except IntegrityError" in authorize
    assert authorize.count("_lock_target_context_capsule_handoff_authorization_sources") == 2
    assert authorize.count("required_precommit_audit") == 1

    locker = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._lock_target_context_capsule_handoff_authorization_sources
    )
    shared = locker.index("_lock_target_context_capsule_consumer_binding_sources")
    lease_lock = locker.index(
        "WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseModel",
        shared,
    )
    claim_lock = locker.index(
        "WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationClaimModel",
        lease_lock,
    )
    clock = locker.index("clock_timestamp", claim_lock)
    assert shared < lease_lock < claim_lock < clock
    assert locker.count(".with_for_update()") >= 2


def test_repository_verifies_captured_attestation_offline_without_provider_io() -> None:
    verifier = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._verify_capsule_lifecycle_attestation
    )
    assert "verify_capsule_lifecycle_attestation" in verifier
    assert "await" not in verifier
    repository_source = inspect.getsource(PostgreSQLWorkflowPlanRepository)
    assert "attest_capsule_lifecycle" not in repository_source
    assert "WorkflowProtectedTargetContextCapsuleLifecycleStatusAttestor" not in repository_source
    for forbidden in (
        "retrieve_capsule",
        "unseal_capsule",
        "decrypt_capsule",
        "transfer_capsule",
        "socket",
    ):
        assert forbidden not in verifier


class _OfflineVerifier:
    def verify_capsule_lifecycle_attestation(
        self, attestation: WorkflowProtectedTargetContextCapsuleLifecycleAttestation
    ) -> bool:
        return canonical_digest(attestation.digest_payload()) == attestation.canonical_digest


def _domain_request() -> (
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseRequest
):
    policy = code_owned_workflow_protected_transport_target_context_capsule_handoff_authorization_policy()  # noqa: E501
    issued_at = datetime(2026, 8, 16, 10, 30, tzinfo=UTC)
    attestation_values: dict[str, object] = {
        "attestation_id": "capsule-lifecycle-attestation.mapping",
        "protected_store_attestor_id": policy.required_capsule_lifecycle_attestor_id,
        "protected_store_attestor_version": policy.required_capsule_lifecycle_attestor_version,
        "opening_result_id": "opening.mapping",
        "opening_result_digest": "1" * 64,
        "consumer_binding_id": "consumer-binding.mapping",
        "consumer_binding_digest": "2" * 64,
        "sealed_capsule_id": "sealed-capsule.mapping",
        "sealed_capsule_digest": "3" * 64,
        "capsule_schema_id": "schema.workflow-sealed-target-context-capsule-lineage",
        "capsule_schema_version": "1.0",
        "request_nonce_digest": "4" * 64,
        "observed_at": issued_at,
        "valid_until": issued_at + timedelta(seconds=3),
        "usable": True,
        "revoked": False,
        "destroyed": False,
        "sealed": True,
        "capsule_is_bearer_capability": False,
        "signing_key_id": "signing-key.mapping",
        "signature_algorithm": "ed25519",
        "integrity_signature": "signed-mapping-evidence",
    }
    attestation = WorkflowProtectedTargetContextCapsuleLifecycleAttestation(
        **cast(Any, attestation_values),
        canonical_digest=canonical_digest(
            {
                name: value.isoformat() if isinstance(value, datetime) else value
                for name, value in attestation_values.items()
            }
        ),
    )
    lease_values: dict[str, object] = {
        "authorization_lease_id": "capsule-handoff-authorization-lease.mapping",
        "consumer_binding_id": attestation.consumer_binding_id,
        "consumer_binding_digest": attestation.consumer_binding_digest,
        "opening_result_id": attestation.opening_result_id,
        "opening_result_digest": attestation.opening_result_digest,
        "sealed_capsule_id": attestation.sealed_capsule_id,
        "sealed_capsule_digest": attestation.sealed_capsule_digest,
        "capsule_schema_id": attestation.capsule_schema_id,
        "capsule_schema_version": attestation.capsule_schema_version,
        "lifecycle_attestation_id": attestation.attestation_id,
        "lifecycle_attestation_digest": attestation.canonical_digest,
        "lifecycle_attestation_valid_until": attestation.valid_until,
        "scope": SCOPE,
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "issued_at": issued_at,
        "valid_until": issued_at + timedelta(seconds=1),
        "effective_until": issued_at + timedelta(seconds=3),
        "single_use": True,
        "renewable": False,
        "transferable": False,
        "lease_is_bearer_capability": False,
        "state": (
            WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
        ),
        "authority": WorkflowProtectedTransportTargetContextCapsuleHandoffLeaseAuthority(),
    }
    lease = WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease(
        **cast(Any, lease_values),
        canonical_digest=canonical_digest(
            {
                name: value.canonical_value()
                if isinstance(
                    value,
                    (
                        WorkflowScope,
                        WorkflowProtectedTransportTargetContextCapsuleHandoffLeaseAuthority,
                    ),
                )
                else value.isoformat()
                if isinstance(value, datetime)
                else value.value
                if isinstance(
                    value,
                    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseState,
                )
                else value
                for name, value in lease_values.items()
            }
        ),
    )

    async def audit() -> None:
        return None

    return WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseRequest(
        expected_consumer_binding_id=lease.consumer_binding_id,
        expected_consumer_binding_digest=lease.consumer_binding_digest,
        expected_opening_result_id=lease.opening_result_id,
        expected_opening_result_digest=lease.opening_result_digest,
        expected_sealed_capsule_id=lease.sealed_capsule_id,
        expected_sealed_capsule_digest=lease.sealed_capsule_digest,
        expected_capsule_schema_id=lease.capsule_schema_id,
        expected_capsule_schema_version=lease.capsule_schema_version,
        lifecycle_attestation=attestation,
        expected_request_nonce_digest=attestation.request_nonce_digest,
        expected_lifecycle_attestor_id=policy.required_capsule_lifecycle_attestor_id,
        expected_lifecycle_attestor_version=policy.required_capsule_lifecycle_attestor_version,
        offline_signature_verifier=_OfflineVerifier(),
        expected_policy_digest=policy.canonical_digest,
        expected_validity_window_seconds=1,
        scope=SCOPE,
        consumer_subject_id=policy.consumer_subject_id,
        consumer_audience=policy.consumer_audience,
        consumer_contract_id=policy.consumer_contract_id,
        consumer_contract_version=policy.consumer_contract_version,
        purpose_id=policy.purpose_id,
        requested_at=issued_at,
        candidate=lease,
        idempotency_key="mapping-idempotency-key",
        request_fingerprint="5" * 64,
        required_precommit_audit=audit,
    )


def test_repository_retimes_a_new_lease_from_the_second_database_timestamp() -> None:
    request = _domain_request()
    second_database_time = request.requested_at + timedelta(milliseconds=750)

    retimed = PostgreSQLWorkflowPlanRepository._target_context_capsule_handoff_retimed_request(
        request,
        issued_at=second_database_time,
    )

    assert retimed.requested_at == second_database_time
    assert retimed.candidate.issued_at == second_database_time
    assert retimed.candidate.valid_until == second_database_time + timedelta(seconds=1)
    assert retimed.candidate.valid_until - retimed.candidate.issued_at == timedelta(seconds=1)
    assert retimed.candidate.canonical_digest == canonical_digest(
        retimed.candidate.digest_payload()
    )
    assert request.candidate.issued_at != retimed.candidate.issued_at


def test_orm_mapping_round_trips_domain_lease_attestation_claim_and_audit() -> None:
    request = _domain_request()
    evidence: dict[str, object] = {
        "consumer_binding": {
            "binding_id": request.expected_consumer_binding_id,
            "canonical_digest": request.expected_consumer_binding_digest,
        }
    }
    lease_row = PostgreSQLWorkflowPlanRepository._target_context_capsule_handoff_lease_model(
        request,
        evidence_payload=evidence,
    )
    claim = PostgreSQLWorkflowPlanRepository._target_context_capsule_handoff_claim_model(
        request,
        evidence_payload=evidence,
    )
    assert lease_row.authorization_lease_id == request.candidate.authorization_lease_id
    assert lease_row.lifecycle_attestation_id == request.lifecycle_attestation.attestation_id
    assert lease_row.lifecycle_attestor_id == request.expected_lifecycle_attestor_id
    assert lease_row.capsule_is_bearer_capability is False
    assert lease_row.target_context_capsule_handoff_authority_granted is True
    assert all(getattr(lease_row, name) is False for name in AUTHORITY_COLUMNS)
    assert lease_row.authorization_audit_digest == canonical_digest(
        lease_row.authorization_audit_payload
    )
    assert (
        PostgreSQLWorkflowPlanRepository._target_context_capsule_handoff_lease_from_row(lease_row)
        == request.candidate
    )
    assert (
        PostgreSQLWorkflowPlanRepository._target_context_capsule_handoff_lease_from_claim(
            claim,
            lease_row,
        )
        == request.candidate
    )


@pytest.mark.asyncio
async def test_non_postgres_adapters_fail_closed() -> None:
    for repository in (InMemoryWorkflowPlanRepository(), UnavailableWorkflowPlanRepository()):
        with pytest.raises(
            WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError
        ):
            await repository.list_target_context_capsule_handoff_authorization_leases(
                scope=SCOPE,
                limit=1,
            )


async def _live_engine() -> AsyncEngine:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    return create_async_engine(database_url, pool_pre_ping=True)


def _digest(seed: str, name: str) -> str:
    return sha256(f"{seed}:{name}".encode()).hexdigest()


def _lease_values(*, seed: str) -> dict[str, object]:
    table = cast(
        Table,
        WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseModel.__table__,
    )
    now = datetime.now(UTC)
    values: dict[str, object] = {}
    for column in table.columns:
        name = column.name
        if name in CODE_OWNED_CONTRACT:
            values[name] = CODE_OWNED_CONTRACT[name]
        elif name == "lifecycle_attestor_id":
            values[name] = "attestor.workflow-protected-target-context-capsule-lifecycle"
        elif name == "lifecycle_attestor_version":
            values[name] = "1.0"
        elif name == "state":
            values[name] = "authorized_unconsumed"
        elif name == "issued_at":
            values[name] = now
        elif name == "valid_until":
            values[name] = now + timedelta(seconds=1)
        elif name in {"effective_until", "lifecycle_attestation_valid_until"}:
            values[name] = now + timedelta(seconds=2)
        elif name == "single_use" or name == "target_context_capsule_handoff_authority_granted":
            values[name] = True
        elif isinstance(column.type, Boolean):
            values[name] = False
        elif name.endswith("_payload") or name == "payload":
            values[name] = {"schema_id": f"test.{seed}"}
        elif name.endswith("_digest") or name in {
            "canonical_digest",
            "authorization_evidence_digest",
            "authorization_audit_digest",
        }:
            values[name] = _digest(seed, name)
        elif name in {"organization_id", "environment_id", "site_id"}:
            values[name] = getattr(SCOPE, name)
        else:
            raw = f"{name}.{seed}"
            length = getattr(column.type, "length", None)
            values[name] = raw if not isinstance(length, int) else raw[:length]
    return values


def _claim_values(*, seed: str, lease_values: dict[str, object]) -> dict[str, object]:
    table = cast(
        Table,
        WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationClaimModel.__table__,
    )
    values: dict[str, object] = {}
    for column in table.columns:
        name = column.name
        if name in CODE_OWNED_CONTRACT:
            values[name] = CODE_OWNED_CONTRACT[name]
        elif name in {"authorization_lease_id", "consumer_binding_id", "sealed_capsule_id"}:
            values[name] = lease_values[name]
        elif name in {"organization_id", "environment_id", "site_id"}:
            values[name] = getattr(SCOPE, name)
        elif name == "created_at":
            values[name] = lease_values["issued_at"]
        elif name.endswith("_payload") or name == "payload":
            values[name] = {"schema_id": f"test.{seed}"}
        elif name.endswith("_digest") or name in {
            "idempotency_scope_id",
            "request_fingerprint",
            "result_digest",
            "canonical_digest",
            "authorization_audit_digest",
        }:
            values[name] = _digest(seed, name)
        else:
            raw = f"{name}.{seed}"
            length = getattr(column.type, "length", None)
            values[name] = raw if not isinstance(length, int) else raw[:length]
    return values


@pytest.mark.asyncio
async def test_live_postgres_handoff_schema_constraints_and_triggers_are_installed() -> None:
    engine = await _live_engine()
    try:
        async with engine.connect() as connection:
            tables = set(
                (
                    await connection.execute(
                        text(
                            "SELECT table_name FROM information_schema.tables "
                            "WHERE table_name IN "
                            "('workflow_event_tctx_capsule_handoff_authorization_leases', "
                            "'workflow_event_tctx_capsule_handoff_authorization_claims')"
                        )
                    )
                ).scalars()
            )
            triggers = set(
                (
                    await connection.execute(
                        text(
                            "SELECT tgname FROM pg_trigger WHERE tgname IN "
                            "('trg_wf_tctx_handoff_leases_append_only', "
                            "'trg_wf_tctx_handoff_claims_append_only')"
                        )
                    )
                ).scalars()
            )
        assert tables == {
            "workflow_event_tctx_capsule_handoff_authorization_leases",
            "workflow_event_tctx_capsule_handoff_authorization_claims",
        }
        assert triggers == {
            "trg_wf_tctx_handoff_leases_append_only",
            "trg_wf_tctx_handoff_claims_append_only",
        }
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_live_postgres_handoff_contract_uniqueness_and_append_only_enforcement() -> None:
    engine = await _live_engine()
    lease_table = cast(
        Table,
        WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseModel.__table__,
    )
    claim_table = cast(
        Table,
        WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationClaimModel.__table__,
    )
    seed = uuid4().hex
    lease_values = _lease_values(seed=seed)
    claim_values = _claim_values(seed=seed, lease_values=lease_values)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SET LOCAL session_replication_role = replica"))
            await connection.execute(lease_table.insert(), lease_values)
            await connection.execute(claim_table.insert(), claim_values)

        competing = {
            **lease_values,
            "authorization_lease_id": f"authorization-lease.competing.{seed}",
            "canonical_digest": _digest(seed, "competing-canonical"),
        }
        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                await connection.execute(text("SET LOCAL session_replication_role = replica"))
                await connection.execute(lease_table.insert(), competing)

        for table, key, value in (
            (lease_table, "authorization_lease_id", lease_values["authorization_lease_id"]),
            (claim_table, "claim_id", claim_values["claim_id"]),
        ):
            with pytest.raises(DBAPIError):
                async with engine.begin() as connection:
                    await connection.execute(
                        table.update()
                        .where(table.c[key] == value)
                        .values(payload={"changed": True})
                    )
            with pytest.raises(DBAPIError):
                async with engine.begin() as connection:
                    await connection.execute(table.delete().where(table.c[key] == value))
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_live_postgres_concurrent_handoff_inserts_allow_one_binding_and_capsule() -> None:
    engine = await _live_engine()
    table = cast(
        Table,
        WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseModel.__table__,
    )
    seed = uuid4().hex
    first = _lease_values(seed=f"{seed}a")
    second = {
        **_lease_values(seed=f"{seed}b"),
        "consumer_binding_id": first["consumer_binding_id"],
        "sealed_capsule_id": first["sealed_capsule_id"],
    }

    async def insert(values: dict[str, object]) -> BaseException | None:
        try:
            async with engine.begin() as connection:
                await connection.execute(text("SET LOCAL session_replication_role = replica"))
                await connection.execute(table.insert(), values)
        except BaseException as exc:  # pragma: no cover - result is asserted below
            return exc
        return None

    try:
        outcomes = await asyncio.wait_for(
            asyncio.gather(insert(first), insert(second)),
            timeout=15,
        )
        assert sum(outcome is None for outcome in outcomes) == 1
        assert sum(isinstance(outcome, IntegrityError) for outcome in outcomes) == 1
    finally:
        await engine.dispose()
