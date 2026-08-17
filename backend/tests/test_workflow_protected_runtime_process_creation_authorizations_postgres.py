from __future__ import annotations

import ast
import inspect

from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository


def _method_source(name: str) -> str:
    return inspect.getsource(getattr(PostgreSQLWorkflowPlanRepository, name))


def test_repository_exposes_process_creation_authorization_persistence_contract() -> None:
    for name in (
        "preflight_protected_runtime_process_creation_authorization",
        "get_protected_runtime_process_creation_authorization_source",
        "authorize_protected_runtime_process_creation",
        "list_protected_runtime_process_creation_authorization_presentations",
        "_lock_protected_runtime_process_creation_authorization_rows",
        "_protected_runtime_process_creation_authorization_replay",
        "_protected_runtime_process_creation_authorization_source_is_eligible",
        "_protected_runtime_process_creation_authorization_lease_model",
        "_protected_runtime_process_creation_authorization_claim_model",
    ):
        assert callable(getattr(PostgreSQLWorkflowPlanRepository, name))


def test_lock_is_replay_first_and_uses_two_authoritative_database_times() -> None:
    source = _method_source("_lock_protected_runtime_process_creation_authorization_rows")

    assert source.index("existing_claims = tuple(") < source.index("source_statement = (")
    assert "select(func.clock_timestamp())" in source
    assert source.count("func.clock_timestamp()") >= 2
    assert ".with_for_update()" in source
    assert "WorkflowProtectedRuntimeProcessCreationAuthorizationClaimModel" in source
    assert "WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseModel" in source


def test_lock_binds_exact_ready_result_and_all_immediate_source_rows() -> None:
    source = _method_source("_lock_protected_runtime_process_creation_authorization_rows")

    for model in (
        "WorkflowProtectedRuntimeReadinessConsumptionResultModel",
        "WorkflowProtectedRuntimeReadinessConsumptionAttemptModel",
        "WorkflowProtectedRuntimeReadinessConsumptionClaimModel",
        "WorkflowProtectedRuntimeReadinessAuthorizationLeaseModel",
        "WorkflowProtectedRuntimeReadinessAuthorizationClaimModel",
        "WorkflowProtectedRuntimeContextInjectionDestinationHeadModel",
        "WorkflowProtectedRuntimeContextInjectionSlotHeadModel",
        "WorkflowProtectedRuntimeStartCoordinationHeadModel",
    ):
        assert model in source
    assert 'result.state == "runtime_ready_in_protected_boundary"' in source
    assert "result.outcome_known.is_(True)" in source
    assert "result.assessment_performed.is_(True)" in source
    assert "result.runtime_ready.is_(True)" in source
    assert "destination.current.is_(True)" in source
    assert "slot.current.is_(True)" in source
    assert 'head.state == "start_attempt_terminal"' in source
    assert "head.process_created.is_(False)" in source
    assert "head.process_scheduled.is_(False)" in source


def test_authorize_rechecks_final_window_and_fails_closed() -> None:
    source = _method_source("authorize_protected_runtime_process_creation")

    assert source.count("_lock_protected_runtime_process_creation_authorization_rows") == 2
    assert "authorized_at > locked.first_observed_at + timedelta(seconds=1)" in source
    assert "statuses.EVIDENCE_CONFLICT" in source
    assert "statuses.ALREADY_AUTHORIZED" in source
    assert "except (IntegrityError, TypeError, ValueError)" in source
    assert "session.add(" in source
    assert "await session.flush()" in source
    assert "await session.commit()" in source


def test_replay_requires_exact_idempotency_and_source_digest() -> None:
    source = _method_source("_protected_runtime_process_creation_authorization_replay")

    assert "claim_row.idempotency_digest != request.idempotency_digest" in source
    assert "claim_row.request_fingerprint != request.request_fingerprint" in source
    assert "claim_row.readiness_result_digest" in source
    assert "lease_row.canonical_digest != working.candidate.canonical_digest" in source
    assert "statuses.IDEMPOTENCY_CONFLICT" in source
    assert "statuses.REPLAY" in source


def test_adapter_has_no_memory_or_permissive_process_creation_fallback() -> None:
    tree = ast.parse(inspect.getsource(PostgreSQLWorkflowPlanRepository))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    source = _method_source("authorize_protected_runtime_process_creation")

    assert "InMemory" not in names
    assert "fallback" not in source.lower()
    assert "network" not in source.lower()
    assert "connector" not in source.lower()
    assert "subprocess" not in source.lower()
