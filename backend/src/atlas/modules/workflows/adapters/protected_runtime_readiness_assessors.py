from __future__ import annotations

import hmac
from collections.abc import Callable
from dataclasses import fields
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Any, NoReturn, cast

from atlas.modules.workflows.application.protected_runtime_readiness_consumption_ports import (
    WorkflowProtectedRuntimeReadinessConsumptionError,
)
from atlas.modules.workflows.domain.models import canonical_digest, canonical_json_bytes
from atlas.modules.workflows.domain.protected_runtime_readiness_consumption_domain import (
    WORKFLOW_PROTECTED_RUNTIME_READINESS_INSTRUCTION_SIGNATURE_ALGORITHM,
    WorkflowProtectedRuntimeReadinessConsumptionPolicy,
    WorkflowProtectedRuntimeReadinessConsumptionResultState,
    WorkflowProtectedRuntimeReadinessInvocation,
    WorkflowProtectedRuntimeReadinessReceipt,
    WorkflowProtectedRuntimeReadinessSignedInstructionEnvelope,
    code_owned_workflow_protected_runtime_readiness_consumption_policy,
)

_DEVELOPMENT_INSTRUCTION_KEY = b"atlas-development-protected-runtime-readiness-instruction-v1"
_DEVELOPMENT_RECEIPT_KEY = b"atlas-development-protected-runtime-readiness-receipt-v1"


class DevelopmentWorkflowProtectedRuntimeReadinessOutcome(StrEnum):
    READY = "ready"
    NOT_READY = "not_ready"
    FAILED_WITHOUT_ASSESSMENT = "failed_without_assessment"
    TIMEOUT = "timeout"
    ERROR = "error"


class UnavailableWorkflowProtectedRuntimeReadinessInstructionSigner:
    @property
    def available(self) -> bool:
        return False

    @property
    def signing_key_id(self) -> str:
        return _policy().instruction_signing_key_id

    @property
    def signature_algorithm(self) -> str:
        return WORKFLOW_PROTECTED_RUNTIME_READINESS_INSTRUCTION_SIGNATURE_ALGORITHM

    def sign_instruction_envelope_digest(self, payload_digest: str) -> str:
        del payload_digest
        _raise("protected_runtime_readiness_instruction_signer_unavailable")


class DenyAllWorkflowProtectedRuntimeReadinessInstructionSignatureVerifier:
    @property
    def available(self) -> bool:
        return False

    def verify_instruction_envelope(
        self, envelope: WorkflowProtectedRuntimeReadinessSignedInstructionEnvelope
    ) -> bool:
        del envelope
        return False


class DenyAllWorkflowProtectedRuntimeReadinessReceiptSignatureVerifier:
    @property
    def available(self) -> bool:
        return False

    def verify_receipt(self, receipt: WorkflowProtectedRuntimeReadinessReceipt) -> bool:
        del receipt
        return False


class UnavailableWorkflowProtectedRuntimeReadinessAssessor:
    @property
    def available(self) -> bool:
        return False

    @property
    def assessor_contract_id(self) -> str:
        return _policy().required_assessor_contract_id

    @property
    def assessor_contract_version(self) -> str:
        return _policy().required_assessor_contract_version

    @property
    def assessor_id(self) -> str:
        return _policy().approved_assessor_id

    @property
    def assessor_version(self) -> str:
        return _policy().approved_assessor_version

    @property
    def readiness_profile_id(self) -> str:
        return _policy().readiness_profile_id

    @property
    def readiness_profile_version(self) -> str:
        return _policy().readiness_profile_version

    @property
    def readiness_profile_digest(self) -> str:
        return _policy().readiness_profile_digest

    async def assess_runtime_readiness(
        self, invocation: WorkflowProtectedRuntimeReadinessInvocation
    ) -> WorkflowProtectedRuntimeReadinessReceipt:
        del invocation
        _raise("protected_runtime_readiness_assessor_unavailable")


class DeterministicDevelopmentWorkflowProtectedRuntimeReadinessInstructionSigner:
    """Development-only instruction signer with no external key or network I/O."""

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
        return WORKFLOW_PROTECTED_RUNTIME_READINESS_INSTRUCTION_SIGNATURE_ALGORITHM

    def sign_instruction_envelope_digest(self, payload_digest: str) -> str:
        self._require_enabled()
        return _sign_digest(_DEVELOPMENT_INSTRUCTION_KEY, payload_digest)

    def _require_enabled(self) -> None:
        if not self._development_enabled:
            _raise("protected_runtime_readiness_instruction_development_signer_disabled")


class DeterministicDevelopmentWorkflowProtectedRuntimeReadinessInstructionSignatureVerifier:
    """Development-only verifier kept separate from the instruction signer."""

    def __init__(self, *, development_enabled: bool = False) -> None:
        self._development_enabled = development_enabled

    @property
    def available(self) -> bool:
        return self._development_enabled

    def verify_instruction_envelope(
        self, envelope: WorkflowProtectedRuntimeReadinessSignedInstructionEnvelope
    ) -> bool:
        if (
            not self._development_enabled
            or envelope.signing_key_id != _policy().instruction_signing_key_id
            or envelope.signature_algorithm
            != WORKFLOW_PROTECTED_RUNTIME_READINESS_INSTRUCTION_SIGNATURE_ALGORITHM
            or envelope.canonical_digest != canonical_digest(envelope.digest_payload())
        ):
            return False
        payload_digest = canonical_digest(_instruction_signature_payload(envelope))
        expected = _sign_digest(_DEVELOPMENT_INSTRUCTION_KEY, payload_digest)
        return hmac.compare_digest(expected, envelope.integrity_signature)


class DeterministicDevelopmentWorkflowProtectedRuntimeReadinessReceiptSignatureVerifier:
    """Development-only receipt verifier using a distinct receipt key."""

    def __init__(self, *, development_enabled: bool = False) -> None:
        self._development_enabled = development_enabled

    @property
    def available(self) -> bool:
        return self._development_enabled

    def verify_receipt(self, receipt: WorkflowProtectedRuntimeReadinessReceipt) -> bool:
        if (
            not self._development_enabled
            or receipt.signing_key_id != _policy().receipt_verification_signing_key_id
            or receipt.signature_algorithm != _policy().receipt_signature_algorithm
            or receipt.canonical_digest != canonical_digest(receipt.digest_payload())
        ):
            return False
        expected = _sign_payload(_DEVELOPMENT_RECEIPT_KEY, receipt.signature_payload())
        return hmac.compare_digest(expected, receipt.integrity_signature)


class DeterministicDevelopmentWorkflowProtectedRuntimeReadinessAssessor:
    """Development-only metadata assessment simulator for the protected boundary."""

    def __init__(
        self,
        *,
        development_enabled: bool = False,
        instruction_signature_verifier: (
            DeterministicDevelopmentWorkflowProtectedRuntimeReadinessInstructionSignatureVerifier
            | None
        ) = None,
        clock: Callable[[], datetime] | None = None,
        outcome: DevelopmentWorkflowProtectedRuntimeReadinessOutcome = (
            DevelopmentWorkflowProtectedRuntimeReadinessOutcome.READY
        ),
    ) -> None:
        self._development_enabled = development_enabled
        self._instruction_signature_verifier = instruction_signature_verifier or (
            DeterministicDevelopmentWorkflowProtectedRuntimeReadinessInstructionSignatureVerifier(
                development_enabled=development_enabled
            )
        )
        self._clock = clock or (lambda: datetime.now(UTC))
        self._outcome = outcome
        self._attempt_instruction_digests: dict[str, str] = {}
        self._receipts: dict[tuple[str, str], WorkflowProtectedRuntimeReadinessReceipt] = {}
        self._uncertain_invocations: set[tuple[str, str]] = set()
        self.calls: list[WorkflowProtectedRuntimeReadinessInvocation] = []

    @property
    def available(self) -> bool:
        return self._development_enabled and self._instruction_signature_verifier.available

    @property
    def assessor_contract_id(self) -> str:
        return _policy().required_assessor_contract_id

    @property
    def assessor_contract_version(self) -> str:
        return _policy().required_assessor_contract_version

    @property
    def assessor_id(self) -> str:
        return _policy().approved_assessor_id

    @property
    def assessor_version(self) -> str:
        return _policy().approved_assessor_version

    @property
    def readiness_profile_id(self) -> str:
        return _policy().readiness_profile_id

    @property
    def readiness_profile_version(self) -> str:
        return _policy().readiness_profile_version

    @property
    def readiness_profile_digest(self) -> str:
        return _policy().readiness_profile_digest

    async def assess_runtime_readiness(
        self, invocation: WorkflowProtectedRuntimeReadinessInvocation
    ) -> WorkflowProtectedRuntimeReadinessReceipt:
        self._require_enabled()
        instruction = invocation.signed_instruction_envelope.instruction
        if (
            invocation.instruction_digest != instruction.canonical_digest
            or not self._instruction_signature_verifier.verify_instruction_envelope(
                invocation.signed_instruction_envelope
            )
        ):
            _raise("protected_runtime_readiness_instruction_envelope_invalid")

        attempt_id = instruction.attempt_id
        instruction_digest = invocation.instruction_digest
        replay_key = (attempt_id, instruction_digest)
        existing_digest = self._attempt_instruction_digests.get(attempt_id)
        if existing_digest is not None and existing_digest != instruction_digest:
            _raise("protected_runtime_readiness_instruction_changed_for_attempt")
        if replay_key in self._receipts:
            return self._receipts[replay_key]
        if replay_key in self._uncertain_invocations:
            _raise("protected_runtime_readiness_outcome_permanently_uncertain")

        now = self._aware_now()
        if now >= invocation.invocation_deadline:
            _raise("protected_runtime_readiness_deadline_expired")

        self._attempt_instruction_digests[attempt_id] = instruction_digest
        self.calls.append(invocation)
        if self._outcome is DevelopmentWorkflowProtectedRuntimeReadinessOutcome.TIMEOUT:
            self._uncertain_invocations.add(replay_key)
            raise TimeoutError("protected runtime readiness assessment timed out")
        if self._outcome is DevelopmentWorkflowProtectedRuntimeReadinessOutcome.ERROR:
            self._uncertain_invocations.add(replay_key)
            _raise("protected_runtime_readiness_assessment_failed")

        receipt = _build_receipt(
            invocation=invocation,
            completed_at=now,
            outcome=self._outcome,
            assessor=self,
        )
        self._receipts[replay_key] = receipt
        return receipt

    def _require_enabled(self) -> None:
        if not self.available:
            _raise("protected_runtime_readiness_development_assessor_disabled")

    def _aware_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            _raise("protected_runtime_readiness_development_clock_must_be_aware")
        return value


def _build_receipt(
    *,
    invocation: WorkflowProtectedRuntimeReadinessInvocation,
    completed_at: datetime,
    outcome: DevelopmentWorkflowProtectedRuntimeReadinessOutcome,
    assessor: DeterministicDevelopmentWorkflowProtectedRuntimeReadinessAssessor,
) -> WorkflowProtectedRuntimeReadinessReceipt:
    instruction = invocation.signed_instruction_envelope.instruction
    failed = (
        outcome is DevelopmentWorkflowProtectedRuntimeReadinessOutcome.FAILED_WITHOUT_ASSESSMENT
    )
    ready = outcome is DevelopmentWorkflowProtectedRuntimeReadinessOutcome.READY
    state = (
        WorkflowProtectedRuntimeReadinessConsumptionResultState.RUNTIME_READINESS_FAILED_WITHOUT_ASSESSMENT
        if failed
        else (
            WorkflowProtectedRuntimeReadinessConsumptionResultState
        ).RUNTIME_READY_IN_PROTECTED_BOUNDARY
        if ready
        else (
            WorkflowProtectedRuntimeReadinessConsumptionResultState
        ).RUNTIME_NOT_READY_IN_PROTECTED_BOUNDARY
    )
    aliases: dict[str, object] = {
        "instruction_digest": invocation.instruction_digest,
        "assessor_contract_id": assessor.assessor_contract_id,
        "assessor_contract_version": assessor.assessor_contract_version,
        "assessor_id": assessor.assessor_id,
        "assessor_version": assessor.assessor_version,
        "readiness_profile_id": assessor.readiness_profile_id,
        "readiness_profile_version": assessor.readiness_profile_version,
        "readiness_profile_digest": assessor.readiness_profile_digest,
        "assessment_count_pre": 0,
        "assessment_count_post": 0 if failed else 1,
        "result_state": state,
        "runtime_ready": None if failed else ready,
        "readiness_assessment_performed": not failed,
        "runtime_locator_returned": False,
        "process_identifier_returned": False,
        "runtime_context_returned": False,
        "endpoint_material_returned": False,
        "credential_material_returned": False,
        "secret_material_returned": False,
        "command_constructed": False,
        "prompt_constructed": False,
        "model_inference_performed": False,
        "network_activity_performed": False,
        "connector_activity_performed": False,
        "mcp_activity_performed": False,
        "publication_performed": False,
        "delivery_performed": False,
        "dispatch_performed": False,
        "execution_performed": False,
        "infrastructure_mutation_performed": False,
        "completed_at": completed_at,
        "signing_key_id": _policy().receipt_verification_signing_key_id,
        "signature_algorithm": _policy().receipt_signature_algorithm,
    }
    values: dict[str, object] = {}
    for field in fields(WorkflowProtectedRuntimeReadinessReceipt):
        if field.name in {"canonical_digest", "integrity_signature"}:
            continue
        if field.name in aliases:
            values[field.name] = aliases[field.name]
        elif hasattr(instruction, field.name):
            values[field.name] = getattr(instruction, field.name)
        else:
            _raise(f"protected_runtime_readiness_receipt_field_unsupported:{field.name}")
    values["integrity_signature"] = _sign_payload(_DEVELOPMENT_RECEIPT_KEY, _payload(values))
    return WorkflowProtectedRuntimeReadinessReceipt(
        **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
    )


def _policy() -> WorkflowProtectedRuntimeReadinessConsumptionPolicy:
    return code_owned_workflow_protected_runtime_readiness_consumption_policy()


def _payload(values: dict[str, object]) -> dict[str, object]:
    return {name: _canonical_value(value) for name, value in values.items()}


def _canonical_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "canonical_value"):
        return value.canonical_value()
    return value


def _instruction_signature_payload(
    envelope: WorkflowProtectedRuntimeReadinessSignedInstructionEnvelope,
) -> dict[str, object]:
    instruction = envelope.instruction
    return {
        "instruction": instruction.digest_payload()
        | {"canonical_digest": instruction.canonical_digest},
        "signing_key_id": envelope.signing_key_id,
        "signature_algorithm": envelope.signature_algorithm,
    }


def _sign_digest(key: bytes, payload_digest: str) -> str:
    return hmac.new(key, payload_digest.encode("ascii"), sha256).hexdigest()


def _sign_payload(key: bytes, payload: dict[str, object]) -> str:
    return hmac.new(key, canonical_json_bytes(payload), sha256).hexdigest()


def _raise(code: str) -> NoReturn:
    raise WorkflowProtectedRuntimeReadinessConsumptionError(code)


__all__ = [
    "DenyAllWorkflowProtectedRuntimeReadinessInstructionSignatureVerifier",
    "DenyAllWorkflowProtectedRuntimeReadinessReceiptSignatureVerifier",
    "DeterministicDevelopmentWorkflowProtectedRuntimeReadinessAssessor",
    "DeterministicDevelopmentWorkflowProtectedRuntimeReadinessInstructionSignatureVerifier",
    "DeterministicDevelopmentWorkflowProtectedRuntimeReadinessInstructionSigner",
    "DeterministicDevelopmentWorkflowProtectedRuntimeReadinessReceiptSignatureVerifier",
    "DevelopmentWorkflowProtectedRuntimeReadinessOutcome",
    "UnavailableWorkflowProtectedRuntimeReadinessAssessor",
    "UnavailableWorkflowProtectedRuntimeReadinessInstructionSigner",
]
