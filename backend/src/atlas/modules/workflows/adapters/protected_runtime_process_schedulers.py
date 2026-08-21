from __future__ import annotations

import hmac
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Any, NoReturn, cast

from atlas.modules.workflows.application.protected_runtime_process_scheduling_consumption_ports import (  # noqa: E501
    WorkflowProtectedRuntimeProcessSchedulingConsumptionError,
)
from atlas.modules.workflows.domain.models import canonical_digest, canonical_json_bytes
from atlas.modules.workflows.domain.protected_runtime_process_scheduling_consumption_domain import (
    WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_INSTRUCTION_SIGNATURE_ALGORITHM,
    WorkflowProtectedRuntimeProcessSchedulingConsumptionPolicy,
    WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState,
    WorkflowProtectedRuntimeProcessSchedulingInvocation,
    WorkflowProtectedRuntimeProcessSchedulingReceipt,
    WorkflowProtectedRuntimeProcessSchedulingSignedInstructionEnvelope,
    code_owned_workflow_protected_runtime_process_scheduling_consumption_policy,
)

_DEVELOPMENT_INSTRUCTION_KEY = (
    b"atlas-development-protected-runtime-process-scheduling-instruction-v1"
)
_DEVELOPMENT_RECEIPT_KEY = b"atlas-development-protected-runtime-process-scheduling-receipt-v1"


class DevelopmentWorkflowProtectedRuntimeProcessSchedulingOutcome(StrEnum):
    SUCCESS = "success"
    REJECTED_WITHOUT_SCHEDULING = "rejected_without_scheduling"
    FAILED_WITHOUT_SCHEDULING = "failed_without_scheduling"
    OUTCOME_UNCERTAIN = "outcome_uncertain"


class UnavailableWorkflowProtectedRuntimeProcessSchedulingInstructionSigner:
    @property
    def available(self) -> bool:
        return False

    @property
    def signing_key_id(self) -> str:
        return _policy().instruction_signing_key_id

    @property
    def signature_algorithm(self) -> str:
        return WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_INSTRUCTION_SIGNATURE_ALGORITHM

    def sign_instruction_envelope_digest(self, payload_digest: str) -> str:
        del payload_digest
        _raise("protected_runtime_process_scheduling_instruction_signer_unavailable")


class DenyAllWorkflowProtectedRuntimeProcessSchedulingInstructionSignatureVerifier:
    @property
    def available(self) -> bool:
        return False

    def verify_instruction_envelope(
        self, envelope: WorkflowProtectedRuntimeProcessSchedulingSignedInstructionEnvelope
    ) -> bool:
        del envelope
        return False


class DenyAllWorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier:
    @property
    def available(self) -> bool:
        return False

    def verify_receipt(self, receipt: WorkflowProtectedRuntimeProcessSchedulingReceipt) -> bool:
        del receipt
        return False


class UnavailableWorkflowProtectedRuntimeProcessScheduler:
    @property
    def available(self) -> bool:
        return False

    @property
    def scheduler_contract_id(self) -> str:
        return _policy().scheduler_contract_id

    @property
    def scheduler_contract_version(self) -> str:
        return _policy().scheduler_contract_version

    @property
    def scheduler_id(self) -> str:
        return _policy().approved_scheduler_id

    @property
    def scheduler_version(self) -> str:
        return _policy().approved_scheduler_version

    @property
    def scheduling_profile_id(self) -> str:
        return _policy().scheduling_profile_id

    @property
    def scheduling_profile_version(self) -> str:
        return _policy().scheduling_profile_version

    @property
    def scheduling_profile_digest(self) -> str:
        return _policy().scheduling_profile_digest

    @property
    def primitive_id(self) -> str:
        return _policy().primitive_id

    @property
    def primitive_version(self) -> str:
        return _policy().primitive_version

    @property
    def primitive_digest(self) -> str:
        return _policy().primitive_digest

    async def schedule_suspended_process(
        self, invocation: WorkflowProtectedRuntimeProcessSchedulingInvocation
    ) -> WorkflowProtectedRuntimeProcessSchedulingReceipt:
        del invocation
        _raise("protected_runtime_process_scheduler_unavailable")


class DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingInstructionSigner:
    """Development-only signer with no external key or network I/O."""

    def __init__(self, *, development_enabled: bool = False) -> None:
        self._development_enabled = development_enabled

    @property
    def available(self) -> bool:
        return self._development_enabled

    @property
    def signing_key_id(self) -> str:
        return _policy().instruction_signing_key_id

    @property
    def signature_algorithm(self) -> str:
        return WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_INSTRUCTION_SIGNATURE_ALGORITHM

    def sign_instruction_envelope_digest(self, payload_digest: str) -> str:
        if not self._development_enabled:
            _raise("protected_runtime_process_scheduling_development_signer_disabled")
        return _sign_digest(_DEVELOPMENT_INSTRUCTION_KEY, payload_digest)


class DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingInstructionSignatureVerifier:
    def __init__(self, *, development_enabled: bool = False) -> None:
        self._development_enabled = development_enabled

    @property
    def available(self) -> bool:
        return self._development_enabled

    def verify_instruction_envelope(
        self, envelope: WorkflowProtectedRuntimeProcessSchedulingSignedInstructionEnvelope
    ) -> bool:
        if (
            not self._development_enabled
            or envelope.signing_key_id != _policy().instruction_signing_key_id
            or envelope.signature_algorithm
            != WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_INSTRUCTION_SIGNATURE_ALGORITHM
            or envelope.canonical_digest != canonical_digest(envelope.digest_payload())
        ):
            return False
        payload = {
            "instruction": envelope.instruction.digest_payload()
            | {"canonical_digest": envelope.instruction.canonical_digest},
            "signing_key_id": envelope.signing_key_id,
            "signature_algorithm": envelope.signature_algorithm,
        }
        return hmac.compare_digest(
            _sign_digest(_DEVELOPMENT_INSTRUCTION_KEY, canonical_digest(payload)),
            envelope.integrity_signature,
        )


class DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier:
    def __init__(self, *, development_enabled: bool = False) -> None:
        self._development_enabled = development_enabled

    @property
    def available(self) -> bool:
        return self._development_enabled

    def verify_receipt(self, receipt: WorkflowProtectedRuntimeProcessSchedulingReceipt) -> bool:
        if (
            not self._development_enabled
            or receipt.signing_key_id != _policy().receipt_verification_signing_key_id
            or receipt.signature_algorithm != _policy().receipt_signature_algorithm
            or receipt.canonical_digest != canonical_digest(receipt.digest_payload())
        ):
            return False
        return hmac.compare_digest(
            _sign_payload(_DEVELOPMENT_RECEIPT_KEY, receipt.signature_payload()),
            receipt.integrity_signature,
        )


class DeterministicDevelopmentWorkflowProtectedRuntimeProcessScheduler:
    """Fixed protected scheduler; accepts no process locator or scheduling choices."""

    def __init__(
        self,
        *,
        development_enabled: bool = False,
        instruction_signature_verifier: (
            DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingInstructionSignatureVerifier
            | None
        ) = None,
        clock: Callable[[], datetime] | None = None,
        outcome: DevelopmentWorkflowProtectedRuntimeProcessSchedulingOutcome = (
            DevelopmentWorkflowProtectedRuntimeProcessSchedulingOutcome.SUCCESS
        ),
    ) -> None:
        self._development_enabled = development_enabled
        self._verifier = instruction_signature_verifier or (
            DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingInstructionSignatureVerifier(
                development_enabled=development_enabled
            )
        )
        self._clock = clock or (lambda: datetime.now(UTC))
        self._outcome = outcome
        self._attempt_instruction_digests: dict[str, str] = {}
        self._lease_attempts: dict[str, str] = {}
        self._receipts: dict[tuple[str, str], WorkflowProtectedRuntimeProcessSchedulingReceipt] = {}
        self._uncertain: set[tuple[str, str]] = set()
        self.calls: list[WorkflowProtectedRuntimeProcessSchedulingInvocation] = []

    @property
    def available(self) -> bool:
        return self._development_enabled and self._verifier.available

    @property
    def scheduler_contract_id(self) -> str:
        return _policy().scheduler_contract_id

    @property
    def scheduler_contract_version(self) -> str:
        return _policy().scheduler_contract_version

    @property
    def scheduler_id(self) -> str:
        return _policy().approved_scheduler_id

    @property
    def scheduler_version(self) -> str:
        return _policy().approved_scheduler_version

    @property
    def scheduling_profile_id(self) -> str:
        return _policy().scheduling_profile_id

    @property
    def scheduling_profile_version(self) -> str:
        return _policy().scheduling_profile_version

    @property
    def scheduling_profile_digest(self) -> str:
        return _policy().scheduling_profile_digest

    @property
    def primitive_id(self) -> str:
        return _policy().primitive_id

    @property
    def primitive_version(self) -> str:
        return _policy().primitive_version

    @property
    def primitive_digest(self) -> str:
        return _policy().primitive_digest

    async def schedule_suspended_process(
        self, invocation: WorkflowProtectedRuntimeProcessSchedulingInvocation
    ) -> WorkflowProtectedRuntimeProcessSchedulingReceipt:
        if not self.available:
            _raise("protected_runtime_process_scheduler_disabled")
        envelope = invocation.signed_instruction_envelope
        instruction = envelope.instruction
        if (
            invocation.instruction_digest != instruction.canonical_digest
            or not self._verifier.verify_instruction_envelope(envelope)
        ):
            _raise("protected_runtime_process_scheduling_instruction_invalid")
        replay_key = (instruction.attempt_id, invocation.instruction_digest)
        existing = self._attempt_instruction_digests.get(instruction.attempt_id)
        if existing is not None and existing != invocation.instruction_digest:
            _raise("protected_runtime_process_scheduling_instruction_changed_for_attempt")
        if replay_key in self._receipts:
            return self._receipts[replay_key]
        if replay_key in self._uncertain:
            _raise("protected_runtime_process_scheduling_outcome_permanently_uncertain")
        now = self._clock()
        if now.tzinfo is None or now >= invocation.invocation_deadline:
            _raise("protected_runtime_process_scheduling_deadline_expired")
        prior_attempt = self._lease_attempts.get(instruction.authorization_lease_id)
        if prior_attempt is not None and prior_attempt != instruction.attempt_id:
            _raise("protected_runtime_process_scheduling_lease_compare_and_swap_rejected")
        self._attempt_instruction_digests[instruction.attempt_id] = invocation.instruction_digest
        self._lease_attempts[instruction.authorization_lease_id] = instruction.attempt_id
        self.calls.append(invocation)
        if (
            self._outcome
            is DevelopmentWorkflowProtectedRuntimeProcessSchedulingOutcome.OUTCOME_UNCERTAIN
        ):
            self._uncertain.add(replay_key)
            _raise("protected_runtime_process_scheduling_post_commit_outcome_uncertain")
        receipt = _build_receipt(invocation=invocation, completed_at=now, outcome=self._outcome)
        self._receipts[replay_key] = receipt
        return receipt


def _build_receipt(
    *,
    invocation: WorkflowProtectedRuntimeProcessSchedulingInvocation,
    completed_at: datetime,
    outcome: DevelopmentWorkflowProtectedRuntimeProcessSchedulingOutcome,
) -> WorkflowProtectedRuntimeProcessSchedulingReceipt:
    instruction = invocation.signed_instruction_envelope.instruction
    result_states = WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState
    states = {
        DevelopmentWorkflowProtectedRuntimeProcessSchedulingOutcome.SUCCESS: (
            result_states.PROCESS_SCHEDULED_SUSPENDED_IN_PROTECTED_BOUNDARY
        ),
        DevelopmentWorkflowProtectedRuntimeProcessSchedulingOutcome.REJECTED_WITHOUT_SCHEDULING: (
            result_states.PROCESS_SCHEDULING_REJECTED_WITHOUT_SCHEDULING
        ),
        DevelopmentWorkflowProtectedRuntimeProcessSchedulingOutcome.FAILED_WITHOUT_SCHEDULING: (
            result_states.PROCESS_SCHEDULING_FAILED_WITHOUT_SCHEDULING
        ),
    }
    state = states[outcome]
    scheduled = outcome is DevelopmentWorkflowProtectedRuntimeProcessSchedulingOutcome.SUCCESS
    values: dict[str, object] = {
        "consumption_id": instruction.consumption_id,
        "attempt_id": instruction.attempt_id,
        "instruction_digest": invocation.instruction_digest,
        "protected_operation_reference": instruction.protected_operation_reference,
        "authorization_lease_id": instruction.authorization_lease_id,
        "scheduling_profile_id": instruction.scheduling_profile_id,
        "scheduling_profile_version": instruction.scheduling_profile_version,
        "scheduling_profile_digest": instruction.scheduling_profile_digest,
        "primitive_id": instruction.primitive_id,
        "primitive_version": instruction.primitive_version,
        "primitive_digest": instruction.primitive_digest,
        "request_nonce_digest": instruction.request_nonce_digest,
        "result_state": state,
        "process_scheduled": scheduled,
        "process_suspended": True,
        "process_runnable": False,
        "process_resumed": False,
        "process_dispatched": False,
        "process_executed": False,
        "caller_material_used": False,
        "process_locator_returned": False,
        "process_identifier_returned": False,
        "queue_or_priority_returned": False,
        "network_activity_performed": False,
        "model_activity_performed": False,
        "mcp_activity_performed": False,
        "connector_activity_performed": False,
        "provider_activity_performed": False,
        "infrastructure_mutation_performed": False,
        "scheduler_contract_id": _policy().scheduler_contract_id,
        "scheduler_contract_version": _policy().scheduler_contract_version,
        "scheduler_id": _policy().approved_scheduler_id,
        "scheduler_version": _policy().approved_scheduler_version,
        "signing_key_id": _policy().receipt_verification_signing_key_id,
        "signature_algorithm": _policy().receipt_signature_algorithm,
        "completed_at": completed_at,
    }
    values["integrity_signature"] = _sign_payload(_DEVELOPMENT_RECEIPT_KEY, _payload(values))
    return WorkflowProtectedRuntimeProcessSchedulingReceipt(
        **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
    )


def _policy() -> WorkflowProtectedRuntimeProcessSchedulingConsumptionPolicy:
    return code_owned_workflow_protected_runtime_process_scheduling_consumption_policy()


def _sign_digest(key: bytes, payload_digest: str) -> str:
    return hmac.new(key, payload_digest.encode("ascii"), sha256).hexdigest()


def _sign_payload(key: bytes, payload: dict[str, object]) -> str:
    return hmac.new(key, canonical_json_bytes(payload), sha256).hexdigest()


def _payload(values: dict[str, object]) -> dict[str, object]:
    return {
        name: (
            value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(value, StrEnum)
            else value.canonical_value()
            if hasattr(value, "canonical_value")
            else value
        )
        for name, value in values.items()
    }


def _raise(code: str) -> NoReturn:
    raise WorkflowProtectedRuntimeProcessSchedulingConsumptionError(code)


__all__ = [
    "DenyAllWorkflowProtectedRuntimeProcessSchedulingInstructionSignatureVerifier",
    "DenyAllWorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier",
    "DeterministicDevelopmentWorkflowProtectedRuntimeProcessScheduler",
    "DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingInstructionSignatureVerifier",
    "DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingInstructionSigner",
    "DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingReceiptSignatureVerifier",
    "DevelopmentWorkflowProtectedRuntimeProcessSchedulingOutcome",
    "UnavailableWorkflowProtectedRuntimeProcessScheduler",
    "UnavailableWorkflowProtectedRuntimeProcessSchedulingInstructionSigner",
]
