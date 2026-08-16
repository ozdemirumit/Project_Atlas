from __future__ import annotations

from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from atlas.modules.workflows.domain import (
    WorkflowProtectedRuntimeContextInjectionConsumptionAuthority,
    WorkflowProtectedRuntimeContextInjectionConsumptionResultState,
    WorkflowProtectedRuntimeContextTrustedInjectorInvocation,
    WorkflowProtectedRuntimeContextTrustedInjectorReceipt,
    canonical_digest,
    code_owned_workflow_protected_runtime_context_injection_consumption_policy,
)

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


def _receipt() -> WorkflowProtectedRuntimeContextTrustedInjectorReceipt:
    policy = code_owned_workflow_protected_runtime_context_injection_consumption_policy()
    values: dict[str, object] = {
        "instruction_digest": "1" * 64,
        "protected_operation_reference": "protected-operation.test",
        "runtime_slot_pre_generation": 7,
        "runtime_slot_post_generation": 8,
        "injector_contract_id": policy.required_injector_contract_id,
        "injector_contract_version": policy.required_injector_contract_version,
        "injector_id": policy.approved_injector_id,
        "injector_version": policy.approved_injector_version,
        "state": (
            WorkflowProtectedRuntimeContextInjectionConsumptionResultState.INJECTED_INTO_PROTECTED_RUNTIME_SLOT
        ),
        "failure_class": None,
        "protected_runtime_handle_consumed": True,
        "inert_context_injected": True,
        "runtime_slot_mutation_performed": True,
        "runtime_slot_empty_confirmed": False,
        "temporary_material_zeroized": True,
        "runtime_started": False,
        "runtime_resumed": False,
        "filesystem_activity_performed": False,
        "provider_activity_performed": False,
        "connector_activity_performed": False,
        "network_activity_performed": False,
        "readiness_probe_performed": False,
        "publication_performed": False,
        "delivery_performed": False,
        "dispatch_performed": False,
        "execution_performed": False,
        "infrastructure_mutation_performed": False,
        "completed_at": NOW,
        "injection_deadline": NOW + timedelta(seconds=1),
        "attested_by": "attestor.test",
        "signing_key_id": policy.receipt_verification_signing_key_id,
        "signature_algorithm": "hmac-sha256",
        "integrity_signature": "2" * 64,
    }
    return WorkflowProtectedRuntimeContextTrustedInjectorReceipt(
        **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
    )


def _payload(values: dict[str, object]) -> dict[str, object]:
    return {
        name: (
            value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if hasattr(value, "value")
            else value
        )
        for name, value in values.items()
    }


def test_policy_is_code_owned_single_use_and_zero_automation() -> None:
    policy = code_owned_workflow_protected_runtime_context_injection_consumption_policy()

    assert policy.automatic_retry_allowed is False
    assert policy.runtime_autostart_forbidden is True
    assert policy.network_activity_forbidden is True
    assert policy.execution_forbidden is True
    assert policy.infrastructure_mutation_forbidden is True


def test_authority_object_rejects_any_runtime_or_infrastructure_authority() -> None:
    authority = WorkflowProtectedRuntimeContextInjectionConsumptionAuthority()

    assert len(authority.canonical_value()) == 22
    assert not any(authority.canonical_value().values())
    with pytest.raises(ValueError):
        WorkflowProtectedRuntimeContextInjectionConsumptionAuthority(runtime_use_authorized=True)


def test_external_injector_invocation_is_an_explicit_three_field_trust_boundary() -> None:
    invocation = WorkflowProtectedRuntimeContextTrustedInjectorInvocation(
        protected_operation_reference="protected-operation.test",
        instruction_digest="1" * 64,
        injection_deadline=NOW + timedelta(seconds=1),
    )

    assert [field.name for field in fields(invocation)] == [
        "protected_operation_reference",
        "instruction_digest",
        "injection_deadline",
    ]
    for forbidden in (
        "protected_runtime_handle_id",
        "protected_runtime_handle_digest",
        "runtime_handle_locator",
        "runtime_slot_commitment",
        "destination_boundary_id",
    ):
        assert not hasattr(invocation, forbidden)


def test_signed_known_receipt_contains_no_handle_identity_and_proves_inert_success() -> None:
    receipt = _receipt()

    assert not hasattr(receipt, "protected_runtime_handle_id")
    assert not hasattr(receipt, "protected_runtime_handle_digest")
    assert receipt.runtime_slot_post_generation == receipt.runtime_slot_pre_generation + 1
    assert receipt.inert_context_injected is True
    assert receipt.runtime_started is False
    assert receipt.network_activity_performed is False
    assert receipt.execution_performed is False
    assert receipt.infrastructure_mutation_performed is False


def test_receipt_rejects_forbidden_runtime_start_side_effect() -> None:
    receipt = _receipt()

    with pytest.raises(ValueError):
        replace(
            receipt,
            runtime_started=True,
            canonical_digest="3" * 64,
        )
