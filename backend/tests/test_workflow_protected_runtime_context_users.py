from __future__ import annotations

import inspect
from typing import Any, cast

import pytest

from atlas.modules.workflows.adapters import protected_runtime_context_users as adapters
from atlas.modules.workflows.adapters.protected_runtime_context_users import (
    DenyAllWorkflowProtectedRuntimeContextUseEligibilitySignatureVerifier,
    DenyAllWorkflowProtectedRuntimeContextUseInstructionSignatureVerifier,
    DenyAllWorkflowProtectedRuntimeContextUseReceiptSignatureVerifier,
    UnavailableWorkflowProtectedRuntimeContextTrustedUser,
    UnavailableWorkflowProtectedRuntimeContextUseEligibilityAttestor,
    UnavailableWorkflowProtectedRuntimeContextUseInstructionSigner,
)
from atlas.modules.workflows.application.protected_runtime_context_use_ports import (
    WorkflowProtectedRuntimeContextUseError,
)
from atlas.modules.workflows.domain.protected_runtime_context_use_domain import (
    WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNATURE_ALGORITHM,
    WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNING_KEY_ID,
    code_owned_workflow_protected_runtime_context_use_policy,
)


def test_production_defaults_are_unavailable_and_verifiers_deny_all() -> None:
    policy = code_owned_workflow_protected_runtime_context_use_policy()
    attestor = UnavailableWorkflowProtectedRuntimeContextUseEligibilityAttestor()
    instruction_signer = UnavailableWorkflowProtectedRuntimeContextUseInstructionSigner()
    trusted_user = UnavailableWorkflowProtectedRuntimeContextTrustedUser()

    assert attestor.available is False
    assert instruction_signer.available is False
    assert instruction_signer.signing_key_id == (
        WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNING_KEY_ID
    )
    assert instruction_signer.signature_algorithm == (
        WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNATURE_ALGORITHM
    )
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
        DenyAllWorkflowProtectedRuntimeContextUseInstructionSignatureVerifier().verify_instruction_envelope(
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

    with pytest.raises(
        WorkflowProtectedRuntimeContextUseError,
        match="protected_runtime_context_use_instruction_signer_unavailable",
    ):
        UnavailableWorkflowProtectedRuntimeContextUseInstructionSigner().sign_instruction_envelope_digest(
            "a" * 64
        )

    with pytest.raises(
        WorkflowProtectedRuntimeContextUseError,
        match="protected_runtime_context_trusted_user_unavailable",
    ):
        await UnavailableWorkflowProtectedRuntimeContextTrustedUser().use_context(
            cast(Any, object())
        )


def test_module_has_no_canonical_or_deterministic_development_success_adapter() -> None:
    public_names = set(adapters.__all__)
    source = inspect.getsource(adapters)

    assert not any("Development" in name or "Synthetic" in name for name in public_names)
    assert "DeterministicDevelopment" not in source
    assert "Synthetic" not in source
    assert "success" not in source.lower()
