from __future__ import annotations

import inspect
import os
from datetime import timedelta
from typing import Any, cast

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from test_workflow_protected_runtime_context_uses import (
    NOW,
    SCOPE,
    _Attestor,
    _SignatureVerifier,
    _source,
)

from atlas.core.persistence.models import (
    WorkflowProtectedRuntimeContextInjectionSlotHeadModel,
)
from atlas.modules.workflows.adapters.postgres import PostgreSQLWorkflowPlanRepository
from atlas.modules.workflows.application.protected_runtime_context_use_ports import (
    WorkflowProtectedRuntimeContextUseClaimRequest,
    WorkflowProtectedRuntimeContextUseEligibilityAttestationRequest,
    WorkflowProtectedRuntimeContextUseError,
)
from atlas.modules.workflows.domain import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_context_use_domain import (
    code_owned_workflow_protected_runtime_context_use_policy,
)


class _RowCount:
    rowcount = 1


class _CapturingSession:
    def __init__(self) -> None:
        self.statement: object | None = None

    async def execute(self, statement: object) -> _RowCount:
        self.statement = statement
        return _RowCount()


def _repository() -> PostgreSQLWorkflowPlanRepository:
    return PostgreSQLWorkflowPlanRepository(engine=cast(Any, object()))


async def _claim_request() -> WorkflowProtectedRuntimeContextUseClaimRequest:
    repository = _repository()
    source = _source()
    source_claim = source.authorization_consumption_claim
    source_result = source.authorization_consumption_result
    policy = code_owned_workflow_protected_runtime_context_use_policy()
    nonce = "a" * 64
    attestation = await _Attestor([]).attest_context_use_eligibility(
        WorkflowProtectedRuntimeContextUseEligibilityAttestationRequest(
            authorization_consumption_result_id=source_result.result_id,
            authorization_consumption_result_digest=source_result.canonical_digest,
            authorization_consumption_claim_id=source_claim.consumption_claim_id,
            authorization_consumption_claim_digest=source_claim.canonical_digest,
            injection_result_id=source_claim.injection_result_id,
            injection_result_digest=source_claim.injection_result_digest,
            destination_deployment_id=source_claim.destination_deployment_id,
            destination_generation=source_claim.destination_generation,
            destination_fencing_token_digest=source_claim.destination_fencing_token_digest,
            runtime_slot_commitment=source_claim.runtime_slot_commitment,
            runtime_slot_generation=source_claim.runtime_slot_post_generation,
            injected_context_usable_until=source_claim.injected_context_usable_until,
            use_profile_id=policy.use_profile_id,
            use_profile_version=policy.use_profile_version,
            use_profile_digest=policy.use_profile_digest,
            executor_contract_id=policy.required_executor_contract_id,
            executor_contract_version=policy.required_executor_contract_version,
            executor_id=policy.approved_executor_id,
            executor_version=policy.approved_executor_version,
            scope=SCOPE,
            consumer_subject_id=policy.consumer_subject_id,
            consumer_audience=policy.consumer_audience,
            purpose_id=policy.purpose_id,
            request_nonce_digest=nonce,
            requested_at=NOW,
        )
    )
    idempotency_digest = canonical_digest(
        {
            "scope": SCOPE.canonical_value(),
            "consumer_subject_id": policy.consumer_subject_id,
            "consumer_audience": policy.consumer_audience,
            "idempotency_key_sha256": "b" * 64,
        }
    )
    fingerprint = canonical_digest(
        {
            "authorization_consumption_result_id": source_result.result_id,
            "authorization_consumption_result_digest": source_result.canonical_digest,
            "scope": SCOPE.canonical_value(),
            "consumer_subject_id": policy.consumer_subject_id,
            "consumer_audience": policy.consumer_audience,
            "policy_id": policy.policy_id,
            "policy_version": policy.policy_version,
            "policy_digest": policy.canonical_digest,
            "idempotency_digest": idempotency_digest,
            "irreversible_use_acknowledged": True,
            "uncertainty_no_retry_acknowledged": True,
        }
    )
    use_id = "workflow-protected-runtime-context-use.imp-222"
    claim_id = "workflow-protected-runtime-context-use-claim.imp-222"
    attempt_id = "workflow-protected-runtime-context-use-attempt.imp-222"
    audit = {
        "schema_id": "audit.workflow-protected-runtime-context-use",
        "schema_version": "1.0",
        "event_type": "protected_runtime_context_use_claimed",
        "use_id": use_id,
        "claim_id": claim_id,
        "attempt_id": attempt_id,
        "authorization_consumption_result_id": source_result.result_id,
        "authorization_consumption_result_digest": source_result.canonical_digest,
        "scope": SCOPE.canonical_value(),
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "idempotency_digest": idempotency_digest,
        "request_fingerprint": fingerprint,
        "irreversible_use_acknowledged": True,
        "uncertainty_no_retry_acknowledged": True,
        "runtime_started": False,
        "runtime_resumed": False,
        "network_activity_performed": False,
        "connector_activity_performed": False,
        "dispatch_performed": False,
        "execution_performed": False,
        "infrastructure_mutation_performed": False,
    }
    request = WorkflowProtectedRuntimeContextUseClaimRequest(
        claim_id=claim_id,
        attempt_id=attempt_id,
        use_id=use_id,
        source=source,
        eligibility_attestation=attestation,
        expected_request_nonce_digest=nonce,
        offline_attestation_signature_verifier=_SignatureVerifier(),
        expected_policy_id=policy.policy_id,
        expected_policy_version=policy.policy_version,
        expected_policy_digest=policy.canonical_digest,
        expected_attestor_id=policy.required_attestor_id,
        expected_attestor_version=policy.required_attestor_version,
        expected_executor_contract_id=policy.required_executor_contract_id,
        expected_executor_contract_version=policy.required_executor_contract_version,
        expected_executor_id=policy.approved_executor_id,
        expected_executor_version=policy.approved_executor_version,
        expected_use_profile_id=policy.use_profile_id,
        expected_use_profile_version=policy.use_profile_version,
        expected_use_profile_digest=policy.use_profile_digest,
        expected_attestation_verification_signing_key_id=(
            policy.attestation_verification_signing_key_id
        ),
        expected_receipt_verification_signing_key_id=(policy.receipt_verification_signing_key_id),
        minimum_remaining_budget_milliseconds=policy.minimum_remaining_budget_milliseconds,
        scope=SCOPE,
        consumer_subject_id=policy.consumer_subject_id,
        consumer_audience=policy.consumer_audience,
        idempotency_key="imp-222-context-use",
        idempotency_digest=idempotency_digest,
        request_fingerprint=fingerprint,
        irreversible_use_acknowledged=True,
        uncertainty_no_retry_acknowledged=True,
        use_authorization_audit_payload=audit,
        use_authorization_audit_digest=canonical_digest(audit),
    )
    assert repository._protected_runtime_context_use_audit_payload(request) == audit
    return request


def test_repository_contract_is_replay_first_locked_and_two_clocked() -> None:
    replay_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.lookup_protected_runtime_context_use_replay
    )
    lock_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._lock_protected_runtime_context_use_sources
    )
    claim_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository.claim_protected_runtime_context_use
    )

    assert "full=True" in replay_source
    assert replay_source.count("session.execute(statement)") == 1
    assert "attest_context_use_eligibility" not in replay_source
    assert "use_context" not in replay_source
    assert lock_source.count("func.clock_timestamp()") == 2
    assert lock_source.count("with_for_update()") >= 3
    assert lock_source.index(
        "_lock_protected_runtime_context_use_authorization_consumption_rows"
    ) < lock_source.index("WorkflowProtectedRuntimeContextUseClaimModel")
    assert claim_source.index("_cas_protected_runtime_context_use_slot") < claim_source.index(
        "session.add"
    )
    assert "claimed_at=locked.observed_at" in claim_source
    assert claim_source.index("session.flush") < claim_source.index("session.commit")


def test_result_contract_verifies_receipt_and_finalizes_exact_slot_states() -> None:
    result_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._protected_runtime_context_use_result_matches
    )
    finalization_source = inspect.getsource(
        PostgreSQLWorkflowPlanRepository._finalize_protected_runtime_context_use_slot
    )

    assert "verify_receipt" in result_source
    assert "use_outcome_uncertain" in result_source
    assert "result.recorded_at >= attempt.started_at" in result_source
    assert "result.recorded_at >= result.use_deadline" not in result_source
    assert "context_used_terminal" in finalization_source
    assert "inert_context_present" in finalization_source
    assert "CONTEXT_USE_OUTCOME_UNCERTAIN" in finalization_source
    assert "automatic" not in result_source.lower()


def test_tenant_scoped_idempotency_changes_across_each_scope_dimension() -> None:
    repository = _repository()
    baseline = repository._protected_runtime_context_adoption_idempotency_scope(
        SCOPE, "subject", "audience"
    )
    variants = (
        WorkflowScope("other", SCOPE.environment_id, SCOPE.site_id),
        WorkflowScope(SCOPE.organization_id, "other", SCOPE.site_id),
        WorkflowScope(SCOPE.organization_id, SCOPE.environment_id, "other"),
    )

    assert len(baseline) == 64
    assert all(
        repository._protected_runtime_context_adoption_idempotency_scope(
            scope, "subject", "audience"
        )
        != baseline
        for scope in variants
    )


@pytest.mark.asyncio
async def test_claim_and_attempt_rows_round_trip_and_tampering_fails_closed() -> None:
    repository = _repository()
    request = await _claim_request()
    claim = repository._protected_runtime_context_use_claim(request, claimed_at=NOW)
    attempt = repository._protected_runtime_context_use_attempt(
        request,
        claim=claim,
        started_at=NOW + timedelta(milliseconds=10),
        use_deadline=NOW + timedelta(milliseconds=500),
    )
    claim_row = repository._protected_runtime_context_adoption_claim_model(request, claim)
    attempt_row = repository._protected_runtime_context_use_attempt_model(request, claim, attempt)

    assert repository._protected_runtime_context_adoption_claim_from_row(claim_row) == claim
    assert repository._protected_runtime_context_use_attempt_from_row(attempt_row) == attempt

    claim_row.policy_digest = "0" * 64
    with pytest.raises(
        WorkflowProtectedRuntimeContextUseError,
        match="protected_runtime_context_use_repository_contract_violation",
    ):
        repository._protected_runtime_context_adoption_claim_from_row(claim_row)


@pytest.mark.asyncio
async def test_slot_compare_and_swap_binds_state_generation_fence_and_digest() -> None:
    repository = _repository()
    payload = {
        "destination_boundary_id": "boundary.test",
        "destination_deployment_id": "deployment.test",
        "destination_generation": 3,
        "destination_fencing_token_digest": "a" * 64,
        "runtime_slot_commitment": "b" * 64,
        "runtime_slot_profile_digest": "c" * 64,
        "slot_generation": 7,
        "slot_state": "inert_context_present",
    }
    row = WorkflowProtectedRuntimeContextInjectionSlotHeadModel(
        **payload,
        current=True,
        canonical_digest=canonical_digest(payload),
        payload=payload,
    )
    session = _CapturingSession()

    changed = await repository._cas_protected_runtime_context_use_slot(
        cast(Any, session),
        slot_row=row,
        expected_state="inert_context_present",
        expected_generation=7,
        next_state="use_outcome_uncertain",
        next_generation=7,
    )

    assert changed is True
    assert session.statement is not None
    sql = str(session.statement)
    assert "slot_state" in sql
    assert "slot_generation" in sql
    assert "destination_fencing_token_digest" in sql
    assert "canonical_digest" in sql


def test_receipt_verifier_binding_is_single_assignment() -> None:
    repository = _repository()
    first = _SignatureVerifier()
    repository.bind_protected_runtime_context_use_receipt_signature_verifier(first)
    repository.bind_protected_runtime_context_use_receipt_signature_verifier(first)

    with pytest.raises(ValueError, match="already bound"):
        repository.bind_protected_runtime_context_use_receipt_signature_verifier(
            _SignatureVerifier()
        )


@pytest.mark.asyncio
async def test_live_postgres_append_only_tables_and_triggers_when_configured() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            tables = set(
                (
                    await connection.execute(
                        text(
                            "SELECT tablename FROM pg_tables WHERE schemaname = current_schema() "
                            "AND tablename IN ('workflow_protected_runtime_context_use_claims', "
                            "'workflow_protected_runtime_context_use_attempts', "
                            "'workflow_protected_runtime_context_use_results')"
                        )
                    )
                ).scalars()
            )
            assert tables == {
                "workflow_protected_runtime_context_use_claims",
                "workflow_protected_runtime_context_use_attempts",
                "workflow_protected_runtime_context_use_results",
            }
            triggers = set(
                (
                    await connection.execute(
                        text(
                            "SELECT tgname FROM pg_trigger WHERE tgname IN "
                            "('trg_wf_rtctx_use_claim_append_only', "
                            "'trg_wf_rtctx_use_attempt_append_only', "
                            "'trg_wf_rtctx_use_result_append_only')"
                        )
                    )
                ).scalars()
            )
            assert triggers == {
                "trg_wf_rtctx_use_claim_append_only",
                "trg_wf_rtctx_use_attempt_append_only",
                "trg_wf_rtctx_use_result_append_only",
            }
    finally:
        await engine.dispose()
