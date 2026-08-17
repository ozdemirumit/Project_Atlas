from __future__ import annotations

from typing import NoReturn

from atlas.modules.workflows.application.protected_runtime_context_use_ports import (
    WorkflowProtectedRuntimeContextUseEligibilityAttestation,
    WorkflowProtectedRuntimeContextUseEligibilityAttestationRequest,
    WorkflowProtectedRuntimeContextUseError,
)
from atlas.modules.workflows.domain.protected_runtime_context_use_domain import (
    WorkflowProtectedRuntimeContextUseInvocation,
    WorkflowProtectedRuntimeContextUsePolicy,
    WorkflowProtectedRuntimeContextUseReceipt,
    code_owned_workflow_protected_runtime_context_use_policy,
)


class UnavailableWorkflowProtectedRuntimeContextUseEligibilityAttestor:
    @property
    def available(self) -> bool:
        return False

    async def attest_context_use_eligibility(
        self, request: WorkflowProtectedRuntimeContextUseEligibilityAttestationRequest
    ) -> WorkflowProtectedRuntimeContextUseEligibilityAttestation:
        del request
        _raise("protected_runtime_context_use_eligibility_attestor_unavailable")


class DenyAllWorkflowProtectedRuntimeContextUseEligibilitySignatureVerifier:
    def verify_context_use_eligibility_attestation(
        self, attestation: WorkflowProtectedRuntimeContextUseEligibilityAttestation
    ) -> bool:
        del attestation
        return False


class DenyAllWorkflowProtectedRuntimeContextUseReceiptSignatureVerifier:
    def verify_receipt(self, receipt: WorkflowProtectedRuntimeContextUseReceipt) -> bool:
        del receipt
        return False


class UnavailableWorkflowProtectedRuntimeContextTrustedUser:
    @property
    def available(self) -> bool:
        return False

    @property
    def executor_contract_id(self) -> str:
        return _policy().required_executor_contract_id

    @property
    def executor_contract_version(self) -> str:
        return _policy().required_executor_contract_version

    @property
    def executor_id(self) -> str:
        return _policy().approved_executor_id

    @property
    def executor_version(self) -> str:
        return _policy().approved_executor_version

    @property
    def use_profile_id(self) -> str:
        return _policy().use_profile_id

    @property
    def use_profile_version(self) -> str:
        return _policy().use_profile_version

    @property
    def use_profile_digest(self) -> str:
        return _policy().use_profile_digest

    async def use_context(
        self, invocation: WorkflowProtectedRuntimeContextUseInvocation
    ) -> WorkflowProtectedRuntimeContextUseReceipt:
        del invocation
        _raise("protected_runtime_context_trusted_user_unavailable")


def _policy() -> WorkflowProtectedRuntimeContextUsePolicy:
    return code_owned_workflow_protected_runtime_context_use_policy()


def _raise(code: str) -> NoReturn:
    raise WorkflowProtectedRuntimeContextUseError(code)


__all__ = [
    "DenyAllWorkflowProtectedRuntimeContextUseEligibilitySignatureVerifier",
    "DenyAllWorkflowProtectedRuntimeContextUseReceiptSignatureVerifier",
    "UnavailableWorkflowProtectedRuntimeContextTrustedUser",
    "UnavailableWorkflowProtectedRuntimeContextUseEligibilityAttestor",
]
