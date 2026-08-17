from __future__ import annotations

import inspect
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from atlas.modules.workflows.adapters import protected_runtime_context_users as adapters
from atlas.modules.workflows.adapters.protected_runtime_context_users import (
    DenyAllWorkflowProtectedRuntimeContextUseEligibilitySignatureVerifier,
    DenyAllWorkflowProtectedRuntimeContextUseReceiptSignatureVerifier,
    UnavailableWorkflowProtectedRuntimeContextTrustedUser,
    UnavailableWorkflowProtectedRuntimeContextUseEligibilityAttestor,
)
from atlas.modules.workflows.application.protected_runtime_context_use_ports import (
    WorkflowProtectedRuntimeContextUseError,
)
from atlas.modules.workflows.domain.protected_runtime_context_use_domain import (
    WorkflowProtectedRuntimeContextUseInvocation,
    code_owned_workflow_protected_runtime_context_use_policy,
)


def test_production_defaults_are_unavailable_and_verifiers_deny_all() -> None:
    policy = code_owned_workflow_protected_runtime_context_use_policy()
    attestor = UnavailableWorkflowProtectedRuntimeContextUseEligibilityAttestor()
    trusted_user = UnavailableWorkflowProtectedRuntimeContextTrustedUser()

    assert attestor.available is False
    assert trusted_user.available is False
    assert trusted_user.executor_contract_id == policy.required_executor_contract_id
    assert trusted_user.executor_contract_version == policy.required_executor_contract_version
    assert trusted_user.executor_id == policy.approved_executor_id
    assert trusted_user.executor_version == policy.approved_executor_version
    assert trusted_user.use_profile_id == policy.use_profile_id
    assert trusted_user.use_profile_version == policy.use_profile_version
    assert trusted_user.use_profile_digest == policy.use_profile_digest
    assert (
        DenyAllWorkflowProtectedRuntimeContextUseEligibilitySignatureVerifier().verify_context_use_eligibility_attestation(
            cast(Any, object())
        )
        is False
    )
    assert (
        DenyAllWorkflowProtectedRuntimeContextUseReceiptSignatureVerifier().verify_receipt(
            cast(Any, object())
        )
        is False
    )


@pytest.mark.asyncio
async def test_unavailable_components_fail_closed_without_side_effects() -> None:
    with pytest.raises(
        WorkflowProtectedRuntimeContextUseError,
        match="protected_runtime_context_use_eligibility_attestor_unavailable",
    ):
        await UnavailableWorkflowProtectedRuntimeContextUseEligibilityAttestor().attest_context_use_eligibility(  # noqa: E501
            cast(Any, object())
        )

    invocation = WorkflowProtectedRuntimeContextUseInvocation(
        protected_operation_reference="protected-operation.imp-222",
        instruction_digest="a" * 64,
        use_deadline=datetime(2026, 8, 17, 12, 0, tzinfo=UTC),
    )
    with pytest.raises(
        WorkflowProtectedRuntimeContextUseError,
        match="protected_runtime_context_trusted_user_unavailable",
    ):
        await UnavailableWorkflowProtectedRuntimeContextTrustedUser().use_context(invocation)


def test_module_has_no_canonical_or_deterministic_development_success_adapter() -> None:
    public_names = set(adapters.__all__)
    source = inspect.getsource(adapters)

    assert not any("Development" in name or "Synthetic" in name for name in public_names)
    assert "DeterministicDevelopment" not in source
    assert "Synthetic" not in source
    assert "success" not in source.lower()
