from __future__ import annotations

import inspect

from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository


def _source(name: str) -> str:
    return inspect.getsource(getattr(PostgreSQLWorkflowPlanRepository, name))


def test_repository_exposes_the_complete_imp219_contract() -> None:
    required = {
        "lookup_protected_runtime_context_injection_consumption_replay",
        "get_protected_runtime_context_injection_consumption_source",
        "claim_protected_runtime_context_injection_consumption",
        "record_protected_runtime_context_injection_consumption_result",
        "list_protected_runtime_context_injection_consumption_attempts",
        "get_protected_runtime_context_injection_consumption_results",
    }

    assert required <= set(dir(PostgreSQLWorkflowPlanRepository))
    assert all(
        inspect.iscoroutinefunction(getattr(PostgreSQLWorkflowPlanRepository, name))
        for name in required
    )


def test_claim_locks_revalidates_and_commits_claim_attempt_and_slot_cas_atomically() -> None:
    claim = _source("claim_protected_runtime_context_injection_consumption")
    lock = _source("_lock_protected_runtime_context_injection_consumption_sources")

    assert claim.index("_lock_protected_runtime_context_injection_consumption_sources") < (
        claim.index("_protected_runtime_context_injection_consumption_locked_replay")
    )
    assert claim.count("_protected_runtime_context_injection_consumption_request_is_valid") == 2
    assert claim.index("_cas_protected_runtime_context_injection_slot_head") < claim.index(
        "_protected_runtime_context_injection_consumption_claim_model"
    )
    assert claim.index("_protected_runtime_context_injection_consumption_claim_model") < (
        claim.index("_protected_runtime_context_injection_attempt_model")
    )
    assert claim.index("_protected_runtime_context_injection_attempt_model") < claim.index(
        "session.commit"
    )
    assert "IntegrityError" in claim
    assert "inject_context" not in claim
    assert "network" not in claim
    assert lock.count("clock_timestamp") == 2
    assert lock.count("with_for_update") >= 10
    assert "WorkflowProtectedRuntimeContextInjectionDestinationHeadModel" in lock
    assert "WorkflowProtectedRuntimeContextInjectionSlotHeadModel" in lock
    assert "protected_runtime_handle_digest" in lock
    assert "runtime_slot_pre_generation" in lock


def test_slot_head_uses_exact_compare_and_swap_and_preserves_uncertainty() -> None:
    cas = _source("_cas_protected_runtime_context_injection_slot_head")
    finalize = _source("_finalize_protected_runtime_context_injection_slot_head")

    for field in (
        "destination_deployment_id",
        "runtime_slot_commitment",
        "destination_generation",
        "destination_fencing_token_digest",
        "runtime_slot_profile_digest",
        "slot_generation",
        "slot_state",
        "canonical_digest",
    ):
        assert field in cas
    assert "rowcount == 1" in cas
    assert 'expected_state="outcome_uncertain"' in finalize
    assert '"inert_context_present"' in finalize
    assert 'else "empty_inert"' in finalize
    assert "INJECTION_OUTCOME_UNCERTAIN" in finalize
    uncertain_branch = finalize.index("INJECTION_OUTCOME_UNCERTAIN")
    assert finalize.index("return True", uncertain_branch) < finalize.index(
        "_cas_protected_runtime_context_injection_slot_head", uncertain_branch
    )


def test_replay_is_exact_scoped_and_never_retries_the_injector() -> None:
    replay = _source("_protected_runtime_context_injection_consumption_replay_from_rows")

    assert "idempotency_scope" in replay
    assert "request_fingerprint" in replay
    assert "authorization_lease_id" in replay
    assert "injection_id" in replay
    assert "IDEMPOTENCY_CONFLICT" in replay
    assert "ALREADY_CONSUMED" in replay
    assert "CLAIM_ONLY_PENDING" in replay
    assert "CLAIM_ONLY_UNCERTAIN" in replay
    assert "injection_deadline" in replay
    assert "inject_context" not in replay


def test_known_results_require_verified_receipts_and_uncertainty_is_receipt_free() -> None:
    matches = _source("_protected_runtime_context_injection_result_matches")
    record = _source("record_protected_runtime_context_injection_consumption_result")

    assert "verify_receipt" in matches
    assert "canonical_digest(receipt.digest_payload())" in matches
    assert "receipt is None" in matches
    assert "result.recorded_at >= result.injection_deadline" in matches
    assert "result.injector_receipt_digest is None" in matches
    assert "expected_claim_digest" in matches
    assert "expected_attempt_digest" in matches
    assert "protected_operation_reference" in matches
    assert "receipt.signing_key_id" in matches
    assert "result.recorded_at <= observed_at" in matches
    assert "all(value is False" in matches
    assert "_finalize_protected_runtime_context_injection_slot_head" in record
    assert "session.commit" in record
    assert "inject_context" not in record


def test_consumption_helpers_do_not_shadow_adr168_authorization_helpers() -> None:
    authorization = (
        PostgreSQLWorkflowPlanRepository._protected_runtime_context_injection_claim_from_row
    )
    consumption = PostgreSQLWorkflowPlanRepository._protected_runtime_context_injection_consumption_claim_from_row  # noqa: E501

    assert "InjectionAuthorizationClaimModel" in inspect.getsource(authorization)
    assert "InjectionConsumptionClaimModel" in inspect.getsource(consumption)


def test_adr168_projection_derives_consumed_from_claim_in_the_same_snapshot() -> None:
    projection = _source("list_protected_runtime_context_injection_authorization_presentations")

    assert "exists(" in projection
    assert "WorkflowProtectedRuntimeContextInjectionConsumptionClaimModel" in projection
    assert "authorization_lease_id" in projection
    assert "select(lease_model, consumed, func.statement_timestamp())" in projection
    assert projection.count("session.execute") == 1
    assert "lease_consumed = bool(row[1])" in projection
    assert "evaluated_at = cast(datetime, row[2])" in projection
    assert "consumed=lease_consumed" in projection
    assert "lease.is_active(evaluated_at=evaluated_at, consumed=lease_consumed)" in projection
    assert "protected_runtime_context_injection_authority_granted=active" in projection


def test_result_model_uses_claim_and_attempt_for_non_domain_projection_columns() -> None:
    model = _source("_protected_runtime_context_injection_result_model")

    assert "organization_id=claim_row.organization_id" in model
    assert "environment_id=claim_row.environment_id" in model
    assert "site_id=claim_row.site_id" in model
    assert "consumer_subject_id=attempt_row.consumer_subject_id" in model
    assert "consumer_audience=attempt_row.consumer_audience" in model
    assert "policy_id=attempt_row.policy_id" in model
    assert "policy_version=attempt_row.policy_version" in model
    assert "policy_digest=attempt_row.policy_digest" in model
    assert "authorization_lease_consumed=True" in model
