from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, cast

import pytest

from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_start_consumption_domain import (
    WorkflowProtectedRuntimeStartConsumptionAttempt,
    WorkflowProtectedRuntimeStartConsumptionAttemptState,
    WorkflowProtectedRuntimeStartConsumptionAuthority,
    WorkflowProtectedRuntimeStartConsumptionClaim,
    WorkflowProtectedRuntimeStartConsumptionFailureClass,
    WorkflowProtectedRuntimeStartConsumptionResult,
    WorkflowProtectedRuntimeStartConsumptionResultState,
    WorkflowProtectedRuntimeStartReceipt,
    code_owned_workflow_protected_runtime_start_consumption_policy,
)

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.test", "environment.test", "site.test")


def _canonical_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if hasattr(value, "canonical_value"):
        return value.canonical_value()
    return value


def _digest(values: dict[str, object]) -> str:
    return canonical_digest({name: _canonical_value(value) for name, value in values.items()})


def _claim() -> WorkflowProtectedRuntimeStartConsumptionClaim:
    policy = code_owned_workflow_protected_runtime_start_consumption_policy()
    values: dict[str, object] = {
        "claim_id": "runtime-start-consumption-claim.imp-224",
        "consumption_id": "runtime-start-consumption.imp-224",
        "attempt_id": "runtime-start-attempt.imp-224",
        "authorization_lease_id": "runtime-start-lease.imp-223",
        "authorization_lease_digest": "1" * 64,
        "authorization_claim_id": "runtime-start-authorization-claim.imp-223",
        "authorization_claim_digest": "2" * 64,
        "use_result_id": "runtime-use-result.imp-222",
        "use_result_digest": "3" * 64,
        "destination_deployment_id": "deployment.imp-224",
        "destination_generation": 4,
        "destination_fencing_token_digest": "4" * 64,
        "runtime_slot_commitment": "5" * 64,
        "runtime_slot_generation": 8,
        "runtime_envelope_id": "runtime-envelope.imp-224",
        "runtime_envelope_commitment": "6" * 64,
        "runtime_envelope_generation": 8,
        "runtime_start_profile_id": policy.runtime_start_profile_id,
        "runtime_start_profile_version": policy.runtime_start_profile_version,
        "runtime_start_profile_digest": policy.runtime_start_profile_digest,
        "scope": SCOPE,
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "idempotency_digest": "7" * 64,
        "request_fingerprint": "8" * 64,
        "irreversible_consumption_acknowledged": True,
        "uncertainty_no_retry_acknowledged": True,
        "claimed_at": NOW,
        "authority": WorkflowProtectedRuntimeStartConsumptionAuthority(),
    }
    return WorkflowProtectedRuntimeStartConsumptionClaim(
        **cast(Any, values),
        canonical_digest=_digest(values),
    )


def _attempt() -> WorkflowProtectedRuntimeStartConsumptionAttempt:
    claim = _claim()
    policy = code_owned_workflow_protected_runtime_start_consumption_policy()
    values: dict[str, object] = {
        name: getattr(claim, name)
        for name in (
            "attempt_id",
            "consumption_id",
            "authorization_lease_id",
            "authorization_lease_digest",
            "authorization_claim_id",
            "authorization_claim_digest",
            "use_result_id",
            "use_result_digest",
            "destination_deployment_id",
            "destination_generation",
            "destination_fencing_token_digest",
            "runtime_slot_commitment",
            "runtime_slot_generation",
            "runtime_envelope_id",
            "runtime_envelope_commitment",
            "runtime_envelope_generation",
            "runtime_start_profile_id",
            "runtime_start_profile_version",
            "runtime_start_profile_digest",
            "scope",
            "consumer_subject_id",
            "consumer_audience",
            "consumer_contract_id",
            "consumer_contract_version",
            "purpose_id",
            "policy_id",
            "policy_version",
            "policy_digest",
        )
    }
    values.update(
        {
            "claim_id": claim.claim_id,
            "claim_digest": claim.canonical_digest,
            "protected_operation_reference": "protected-runtime-start.imp-224",
            "expected_start_count_pre": 0,
            "expected_start_count_post": 1,
            "starter_contract_id": policy.required_starter_contract_id,
            "starter_contract_version": policy.required_starter_contract_version,
            "starter_id": policy.approved_starter_id,
            "starter_version": policy.approved_starter_version,
            "receipt_verification_signing_key_id": (policy.receipt_verification_signing_key_id),
            "request_nonce_digest": "9" * 64,
            "started_at": NOW,
            "invocation_deadline": NOW + timedelta(milliseconds=700),
            "state": (
                WorkflowProtectedRuntimeStartConsumptionAttemptState
            ).RUNTIME_START_ATTEMPT_STARTED,
            "authority": WorkflowProtectedRuntimeStartConsumptionAuthority(),
        }
    )
    return WorkflowProtectedRuntimeStartConsumptionAttempt(
        **cast(Any, values),
        canonical_digest=_digest(values),
    )


def _receipt(
    state: WorkflowProtectedRuntimeStartConsumptionResultState,
) -> WorkflowProtectedRuntimeStartReceipt:
    attempt = _attempt()
    policy = code_owned_workflow_protected_runtime_start_consumption_policy()
    success = (
        state
        is WorkflowProtectedRuntimeStartConsumptionResultState.RUNTIME_STARTED_IN_PROTECTED_BOUNDARY
    )
    values: dict[str, object] = {
        "consumption_id": attempt.consumption_id,
        "attempt_id": attempt.attempt_id,
        "instruction_digest": "a" * 64,
        "protected_operation_reference": attempt.protected_operation_reference,
        "authorization_lease_id": attempt.authorization_lease_id,
        "destination_deployment_id": attempt.destination_deployment_id,
        "destination_generation": attempt.destination_generation,
        "destination_fencing_token_digest": attempt.destination_fencing_token_digest,
        "runtime_slot_commitment": attempt.runtime_slot_commitment,
        "runtime_slot_generation": attempt.runtime_slot_generation,
        "runtime_envelope_id": attempt.runtime_envelope_id,
        "runtime_envelope_commitment": attempt.runtime_envelope_commitment,
        "runtime_envelope_generation": attempt.runtime_envelope_generation,
        "request_nonce_digest": attempt.request_nonce_digest,
        "result_state": state,
        "runtime_started": success,
        "runtime_start_count_pre": 0,
        "runtime_start_count_post": 1 if success else 0,
        "runtime_envelope_current": True,
        "runtime_envelope_inactive": not success,
        "residual_process_absent": True,
        "residual_task_absent": True,
        "scheduling_performed": False,
        "runtime_resumed": False,
        "generic_process_created": False,
        "prompt_constructed": False,
        "model_inference_performed": False,
        "network_activity_performed": False,
        "readiness_probe_performed": False,
        "publication_performed": False,
        "delivery_performed": False,
        "connector_activity_performed": False,
        "dispatch_performed": False,
        "execution_performed": False,
        "infrastructure_mutation_performed": False,
        "starter_contract_id": policy.required_starter_contract_id,
        "starter_contract_version": policy.required_starter_contract_version,
        "starter_id": policy.approved_starter_id,
        "starter_version": policy.approved_starter_version,
        "signing_key_id": policy.receipt_verification_signing_key_id,
        "signature_algorithm": "hmac-sha256",
        "completed_at": NOW + timedelta(milliseconds=500),
        "integrity_signature": "b" * 64,
    }
    return WorkflowProtectedRuntimeStartReceipt(
        **cast(Any, values),
        canonical_digest=_digest(values),
    )


def test_policy_is_code_owned_irreversible_and_non_retrying() -> None:
    policy = code_owned_workflow_protected_runtime_start_consumption_policy()

    assert policy.policy_id == "policy.workflow-protected-runtime-start"
    assert policy.policy_version == "1.0"
    assert policy.purpose_id == "purpose.workflow-protected-runtime-start"
    assert policy.claim_and_attempt_atomic_required is True
    assert policy.commit_before_starter_io_required is True
    assert policy.at_most_one_starter_call_required is True
    assert policy.automatic_retry_allowed is False
    assert policy.runtime_resume_forbidden is True
    assert policy.network_activity_forbidden is True
    assert policy.infrastructure_mutation_forbidden is True
    assert policy.instruction_signing_key_id != policy.receipt_verification_signing_key_id


def test_authority_has_exactly_twenty_seven_false_declarations_and_is_immutable() -> None:
    authority = WorkflowProtectedRuntimeStartConsumptionAuthority()

    assert len(authority.canonical_value()) == 27
    assert not any(authority.canonical_value().values())
    with pytest.raises(FrozenInstanceError):
        authority.runtime_start_authorized = True  # type: ignore[misc]


@pytest.mark.parametrize(
    "field_name",
    [field.name for field in fields(WorkflowProtectedRuntimeStartConsumptionAuthority)],
)
def test_authority_rejects_every_true_declaration(field_name: str) -> None:
    values = {
        field.name: False for field in fields(WorkflowProtectedRuntimeStartConsumptionAuthority)
    }
    values[field_name] = True

    with pytest.raises(ValueError):
        WorkflowProtectedRuntimeStartConsumptionAuthority(**values)


def test_receipt_verification_key_is_identifier_not_digest() -> None:
    attempt = _attempt()
    policy = code_owned_workflow_protected_runtime_start_consumption_policy()

    assert attempt.receipt_verification_signing_key_id == (
        policy.receipt_verification_signing_key_id
    )
    assert len(attempt.receipt_verification_signing_key_id) != 64

    values = {
        field.name: getattr(attempt, field.name)
        for field in fields(WorkflowProtectedRuntimeStartConsumptionAttempt)
        if field.name != "canonical_digest"
    }
    values["receipt_verification_signing_key_id"] = "c" * 64
    with pytest.raises(ValueError, match="attempt is invalid"):
        WorkflowProtectedRuntimeStartConsumptionAttempt(
            **cast(Any, values),
            canonical_digest=_digest(values),
        )


@pytest.mark.parametrize(
    "state",
    [
        WorkflowProtectedRuntimeStartConsumptionResultState.RUNTIME_STARTED_IN_PROTECTED_BOUNDARY,
        WorkflowProtectedRuntimeStartConsumptionResultState.RUNTIME_START_FAILED_WITHOUT_START,
    ],
)
def test_receipt_accepts_only_exact_success_or_proven_no_effect(
    state: WorkflowProtectedRuntimeStartConsumptionResultState,
) -> None:
    receipt = _receipt(state)

    assert receipt.result_state is state
    assert receipt.runtime_start_count_post == (
        1
        if state
        is WorkflowProtectedRuntimeStartConsumptionResultState.RUNTIME_STARTED_IN_PROTECTED_BOUNDARY
        else 0
    )


def test_receipt_rejects_residual_effect_for_known_failure() -> None:
    receipt = _receipt(
        WorkflowProtectedRuntimeStartConsumptionResultState.RUNTIME_START_FAILED_WITHOUT_START
    )

    with pytest.raises(ValueError, match="receipt is invalid"):
        replace(receipt, residual_process_absent=False)


@pytest.mark.parametrize(
    "field_name",
    [
        "readiness_probe_performed",
        "publication_performed",
        "delivery_performed",
    ],
)
def test_receipt_rejects_new_forbidden_side_effects(field_name: str) -> None:
    receipt = _receipt(
        WorkflowProtectedRuntimeStartConsumptionResultState.RUNTIME_STARTED_IN_PROTECTED_BOUNDARY
    )

    with pytest.raises(ValueError, match="receipt is invalid"):
        replace(receipt, **cast(Any, {field_name: True}))


def test_uncertainty_result_is_permanent_unknown_outcome_with_zero_authority() -> None:
    attempt = _attempt()
    policy = code_owned_workflow_protected_runtime_start_consumption_policy()
    values: dict[str, Any] = {
        "result_id": "runtime-start-result.imp-224",
        "consumption_id": attempt.consumption_id,
        "attempt_id": attempt.attempt_id,
        "attempt_digest": attempt.canonical_digest,
        "claim_id": attempt.claim_id,
        "claim_digest": attempt.claim_digest,
        "authorization_lease_id": attempt.authorization_lease_id,
        "authorization_lease_digest": attempt.authorization_lease_digest,
        "runtime_start_profile_id": attempt.runtime_start_profile_id,
        "runtime_start_profile_version": attempt.runtime_start_profile_version,
        "runtime_start_profile_digest": attempt.runtime_start_profile_digest,
        "destination_deployment_id": attempt.destination_deployment_id,
        "destination_generation": attempt.destination_generation,
        "runtime_envelope_commitment": attempt.runtime_envelope_commitment,
        "runtime_envelope_generation": attempt.runtime_envelope_generation,
        "state": (
            WorkflowProtectedRuntimeStartConsumptionResultState
        ).RUNTIME_START_OUTCOME_UNCERTAIN,
        "failure_class": (
            WorkflowProtectedRuntimeStartConsumptionFailureClass
        ).RUNTIME_START_OUTCOME_UNCERTAIN,
        "outcome_known": False,
        "runtime_started": None,
        "starter_receipt_digest": None,
        "completed_at": None,
        "recorded_at": NOW + timedelta(seconds=1),
        "scope": SCOPE,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "authority": WorkflowProtectedRuntimeStartConsumptionAuthority(),
    }
    result = WorkflowProtectedRuntimeStartConsumptionResult(
        **values, canonical_digest=_digest(values)
    )

    assert result.runtime_started is None
    assert result.outcome_known is False
    assert not any(result.authority.canonical_value().values())
