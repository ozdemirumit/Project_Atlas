from __future__ import annotations

import ast
from pathlib import Path

POSTGRES_PATH = (
    Path(__file__).parents[1]
    / "src"
    / "atlas"
    / "modules"
    / "workflows"
    / "adapters"
    / "postgres.py"
)
SOURCE = POSTGRES_PATH.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
REPOSITORY = next(
    node
    for node in TREE.body
    if isinstance(node, ast.ClassDef) and node.name == "PostgreSQLWorkflowPlanRepository"
)


def _method_source(name: str) -> str:
    node = next(
        item
        for item in REPOSITORY.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name
    )
    return ast.get_source_segment(SOURCE, node) or ""


def test_repository_declares_readiness_models_ports_and_locked_sources() -> None:
    for symbol in (
        "WorkflowProtectedRuntimeReadinessAuthorizationClaimModel",
        "WorkflowProtectedRuntimeReadinessAuthorizationLeaseModel",
        "WorkflowProtectedRuntimeReadinessAuthorizationLeaseRequest",
        "WorkflowProtectedRuntimeReadinessAuthorizationPreflightRequest",
        "WorkflowProtectedRuntimeReadinessAuthorizationPresentation",
        "WorkflowProtectedRuntimeReadinessLifecycleAttestation",
        "WorkflowProtectedRuntimeReadinessLifecycleSignatureVerifier",
        "_ProtectedRuntimeReadinessAuthorizationLockedSources",
    ):
        assert symbol in SOURCE


def test_preflight_is_durable_replay_first_and_never_attests() -> None:
    preflight = _method_source("preflight_protected_runtime_readiness_authorization")

    assert "_lock_protected_runtime_readiness_authorization_rows" in preflight
    assert "_protected_runtime_readiness_idempotency_claim" in preflight
    assert "_protected_runtime_readiness_verified_replay_lease" in preflight
    assert "offline_signature_verifier" in preflight
    assert "offline_start_receipt_signature_verifier" in preflight
    assert "attest_runtime_readiness_lifecycle" not in preflight
    assert "session.add" not in preflight


def test_lock_loads_complete_source_in_order_with_two_database_times() -> None:
    lock = _method_source("_lock_protected_runtime_readiness_authorization_rows")

    assert lock.count("clock_timestamp") == 2
    assert "_lock_protected_runtime_start_authorization_rows" in lock
    assert lock.index("start_authorization =") < lock.index("start_claim =")
    assert lock.index("start_claim =") < lock.index("start_attempt =")
    assert lock.index("start_attempt =") < lock.index("start_result =")
    assert lock.index("start_result =") < lock.index("existing_claims =")
    assert lock.index("existing_claims =") < lock.index("existing_leases =")
    assert "with_for_update" in lock


def test_source_accepts_only_signed_successful_terminal_start() -> None:
    source = _method_source("_protected_runtime_readiness_source_from_locked")

    assert "RUNTIME_STARTED_IN_PROTECTED_BOUNDARY" in source
    assert "runtime_started is True" in source
    assert "starter_receipt" in source
    assert "receipt_verifier=receipt_verifier" in source
    assert 'head.state == "start_attempt_terminal"' in source
    assert "head.runtime_start_attempt_terminal" in source
    assert "head.runtime_start_result_digest == start_result.canonical_digest" in source
    assert "destination.destination_fencing_token_digest" in source
    assert "slot.runtime_slot_commitment" in source
    assert 'slot.slot_state == "context_used_terminal"' in source


def test_authorize_replays_before_retiming_and_has_one_winner_recovery() -> None:
    authorize = _method_source("authorize_protected_runtime_readiness")

    assert authorize.index("_protected_runtime_readiness_replay") < authorize.index(
        "_protected_runtime_readiness_retimed_request"
    )
    assert "validate_workflow_protected_runtime_readiness_authorization_request" in (
        _method_source("_protected_runtime_readiness_evidence_matches")
    )
    assert "except IntegrityError" in authorize
    assert authorize.count("_lock_protected_runtime_readiness_authorization_rows") == 2
    assert authorize.count("_protected_runtime_readiness_replay") == 2
    assert "session.flush" in authorize
    assert "session.commit" in authorize


def test_evidence_uses_offline_signatures_and_both_database_observations() -> None:
    evidence = _method_source("_protected_runtime_readiness_evidence_matches")
    signature = _method_source("_protected_runtime_readiness_attestation_signature_valid")

    assert "offline_start_receipt_signature_verifier" in evidence
    assert "offline_signature_verifier" in evidence
    assert "locked.first_observed_at" in evidence
    assert "locked.observed_at" in evidence
    assert "attestation.valid_until" in evidence
    assert "attestation.runtime_envelope_eligible_until" in evidence
    assert "verify_runtime_readiness_lifecycle_attestation" in signature


def test_repository_path_has_no_probe_or_operational_io() -> None:
    methods = "\n".join(
        _method_source(name)
        for name in (
            "preflight_protected_runtime_readiness_authorization",
            "authorize_protected_runtime_readiness",
            "_lock_protected_runtime_readiness_authorization_rows",
            "_protected_runtime_readiness_evidence_matches",
        )
    ).lower()

    for forbidden in (
        "readiness_prober",
        "probe_runtime",
        "httpx",
        "requests.",
        "socket.",
        "connector_client",
        "mcp_client",
        "process_manager",
        "subprocess",
    ):
        assert forbidden not in methods


def test_presentations_are_read_only_append_only_projections() -> None:
    presentation = _method_source("list_protected_runtime_readiness_authorization_presentations")

    assert "WorkflowProtectedRuntimeReadinessAuthorizationLeaseModel" in presentation
    assert "statement_timestamp" in presentation
    assert "session.execute" in presentation
    assert "session.add" not in presentation
    assert "session.delete" not in presentation
    assert "session.commit" not in presentation
    assert "update(" not in presentation
