from __future__ import annotations

import hmac
from collections.abc import Callable
from dataclasses import fields
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Any, NoReturn, cast

from atlas.modules.workflows.application.protected_runtime_start_consumption_ports import (
    WorkflowProtectedRuntimeStartConsumptionError,
)
from atlas.modules.workflows.domain.models import canonical_digest, canonical_json_bytes
from atlas.modules.workflows.domain.protected_runtime_start_consumption_domain import (
    WORKFLOW_PROTECTED_RUNTIME_START_INSTRUCTION_SIGNATURE_ALGORITHM,
    WorkflowProtectedRuntimeStartConsumptionPolicy,
    WorkflowProtectedRuntimeStartConsumptionResultState,
    WorkflowProtectedRuntimeStartInvocation,
    WorkflowProtectedRuntimeStartReceipt,
    WorkflowProtectedRuntimeStartSignedInstructionEnvelope,
    code_owned_workflow_protected_runtime_start_consumption_policy,
)

_DEVELOPMENT_INSTRUCTION_KEY = b"atlas-development-protected-runtime-start-instruction-v1"
_DEVELOPMENT_RECEIPT_KEY = b"atlas-development-protected-runtime-start-receipt-v1"


class DevelopmentWorkflowProtectedRuntimeStartOutcome(StrEnum):
    SUCCESS = "success"
    KNOWN_NO_EFFECT_FAILURE = "known_no_effect_failure"
    PARTIAL_UNCERTAIN = "partial_uncertain"


class UnavailableWorkflowProtectedRuntimeStartInstructionSigner:
    @property
    def available(self) -> bool:
        return False

    @property
    def signing_key_id(self) -> str:
        return _policy().instruction_signing_key_id

    @property
    def signature_algorithm(self) -> str:
        return WORKFLOW_PROTECTED_RUNTIME_START_INSTRUCTION_SIGNATURE_ALGORITHM

    def sign_instruction_envelope_digest(self, payload_digest: str) -> str:
        del payload_digest
        _raise("protected_runtime_start_instruction_signer_unavailable")


class DenyAllWorkflowProtectedRuntimeStartInstructionSignatureVerifier:
    @property
    def available(self) -> bool:
        return False

    def verify_instruction_envelope(
        self, envelope: WorkflowProtectedRuntimeStartSignedInstructionEnvelope
    ) -> bool:
        del envelope
        return False


class DenyAllWorkflowProtectedRuntimeStartReceiptSignatureVerifier:
    @property
    def available(self) -> bool:
        return False

    def verify_receipt(self, receipt: WorkflowProtectedRuntimeStartReceipt) -> bool:
        del receipt
        return False


class UnavailableWorkflowProtectedRuntimeStarter:
    @property
    def available(self) -> bool:
        return False

    @property
    def starter_contract_id(self) -> str:
        return _policy().required_starter_contract_id

    @property
    def starter_contract_version(self) -> str:
        return _policy().required_starter_contract_version

    @property
    def starter_id(self) -> str:
        return _policy().approved_starter_id

    @property
    def starter_version(self) -> str:
        return _policy().approved_starter_version

    @property
    def runtime_start_profile_id(self) -> str:
        return _policy().runtime_start_profile_id

    @property
    def runtime_start_profile_version(self) -> str:
        return _policy().runtime_start_profile_version

    @property
    def runtime_start_profile_digest(self) -> str:
        return _policy().runtime_start_profile_digest

    async def start_runtime(
        self, invocation: WorkflowProtectedRuntimeStartInvocation
    ) -> WorkflowProtectedRuntimeStartReceipt:
        del invocation
        _raise("protected_runtime_starter_unavailable")


class DeterministicDevelopmentWorkflowProtectedRuntimeStartInstructionSigner:
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
        return WORKFLOW_PROTECTED_RUNTIME_START_INSTRUCTION_SIGNATURE_ALGORITHM

    def sign_instruction_envelope_digest(self, payload_digest: str) -> str:
        self._require_enabled()
        return _sign_digest(_DEVELOPMENT_INSTRUCTION_KEY, payload_digest)

    def _require_enabled(self) -> None:
        if not self._development_enabled:
            _raise("protected_runtime_start_instruction_development_signer_disabled")


class DeterministicDevelopmentWorkflowProtectedRuntimeStartInstructionSignatureVerifier:
    """Development-only verifier kept distinct from the instruction signer."""

    def __init__(self, *, development_enabled: bool = False) -> None:
        self._development_enabled = development_enabled

    @property
    def available(self) -> bool:
        return self._development_enabled

    def verify_instruction_envelope(
        self, envelope: WorkflowProtectedRuntimeStartSignedInstructionEnvelope
    ) -> bool:
        if (
            not self._development_enabled
            or envelope.signing_key_id != _policy().instruction_signing_key_id
            or envelope.signature_algorithm
            != WORKFLOW_PROTECTED_RUNTIME_START_INSTRUCTION_SIGNATURE_ALGORITHM
            or envelope.canonical_digest != canonical_digest(envelope.digest_payload())
        ):
            return False
        payload_digest = canonical_digest(_instruction_signature_payload(envelope))
        expected = _sign_digest(_DEVELOPMENT_INSTRUCTION_KEY, payload_digest)
        return hmac.compare_digest(expected, envelope.integrity_signature)


class DeterministicDevelopmentWorkflowProtectedRuntimeStartReceiptSignatureVerifier:
    """Development-only receipt verifier with a key distinct from instruction signing."""

    def __init__(self, *, development_enabled: bool = False) -> None:
        self._development_enabled = development_enabled

    @property
    def available(self) -> bool:
        return self._development_enabled

    def verify_receipt(self, receipt: WorkflowProtectedRuntimeStartReceipt) -> bool:
        if (
            not self._development_enabled
            or receipt.signing_key_id != _policy().receipt_verification_signing_key_id
            or receipt.signature_algorithm != "hmac-sha256"
            or receipt.canonical_digest != canonical_digest(receipt.digest_payload())
        ):
            return False
        expected = _sign_payload(_DEVELOPMENT_RECEIPT_KEY, receipt.signature_payload())
        return hmac.compare_digest(expected, receipt.integrity_signature)


class DeterministicDevelopmentWorkflowProtectedRuntimeStarter:
    """Development-only exact-instruction CAS simulator with no raw locator output."""

    def __init__(
        self,
        *,
        development_enabled: bool = False,
        instruction_signature_verifier: (
            DeterministicDevelopmentWorkflowProtectedRuntimeStartInstructionSignatureVerifier | None
        ) = None,
        clock: Callable[[], datetime] | None = None,
        outcome: DevelopmentWorkflowProtectedRuntimeStartOutcome = (
            DevelopmentWorkflowProtectedRuntimeStartOutcome.SUCCESS
        ),
    ) -> None:
        self._development_enabled = development_enabled
        self._instruction_signature_verifier = instruction_signature_verifier or (
            DeterministicDevelopmentWorkflowProtectedRuntimeStartInstructionSignatureVerifier(
                development_enabled=development_enabled
            )
        )
        self._clock = clock or (lambda: datetime.now(UTC))
        self._outcome = outcome
        self._attempt_instruction_digests: dict[str, str] = {}
        self._envelope_attempts: dict[tuple[str, str, int], str] = {}
        self._receipts: dict[tuple[str, str], WorkflowProtectedRuntimeStartReceipt] = {}
        self._uncertain_invocations: set[tuple[str, str]] = set()
        self.calls: list[WorkflowProtectedRuntimeStartInvocation] = []

    @property
    def available(self) -> bool:
        return self._development_enabled and self._instruction_signature_verifier.available

    @property
    def starter_contract_id(self) -> str:
        return _policy().required_starter_contract_id

    @property
    def starter_contract_version(self) -> str:
        return _policy().required_starter_contract_version

    @property
    def starter_id(self) -> str:
        return _policy().approved_starter_id

    @property
    def starter_version(self) -> str:
        return _policy().approved_starter_version

    @property
    def runtime_start_profile_id(self) -> str:
        return _policy().runtime_start_profile_id

    @property
    def runtime_start_profile_version(self) -> str:
        return _policy().runtime_start_profile_version

    @property
    def runtime_start_profile_digest(self) -> str:
        return _policy().runtime_start_profile_digest

    async def start_runtime(
        self, invocation: WorkflowProtectedRuntimeStartInvocation
    ) -> WorkflowProtectedRuntimeStartReceipt:
        self._require_enabled()
        instruction = invocation.signed_instruction_envelope.instruction
        if (
            invocation.instruction_digest != instruction.canonical_digest
            or not self._instruction_signature_verifier.verify_instruction_envelope(
                invocation.signed_instruction_envelope
            )
        ):
            _raise("protected_runtime_start_instruction_envelope_invalid")

        attempt_id = _identifier(instruction, "start_attempt_id", "attempt_id")
        instruction_digest = invocation.instruction_digest
        replay_key = (attempt_id, instruction_digest)

        existing_digest = self._attempt_instruction_digests.get(attempt_id)
        if existing_digest is not None and existing_digest != instruction_digest:
            _raise("protected_runtime_start_instruction_changed_for_attempt")
        if replay_key in self._receipts:
            return self._receipts[replay_key]
        if replay_key in self._uncertain_invocations:
            _raise("protected_runtime_start_outcome_permanently_uncertain")

        now = self._aware_now()
        deadline = _deadline(invocation)
        if now >= deadline:
            _raise("protected_runtime_start_deadline_expired")

        envelope_key = (
            _identifier(instruction, "runtime_envelope_id"),
            _digest(instruction, "runtime_envelope_commitment"),
            _integer(instruction, "runtime_envelope_generation"),
        )
        existing_attempt = self._envelope_attempts.get(envelope_key)
        if existing_attempt is not None and existing_attempt != attempt_id:
            _raise("protected_runtime_start_compare_and_swap_rejected")

        self._attempt_instruction_digests[attempt_id] = instruction_digest
        self._envelope_attempts[envelope_key] = attempt_id
        self.calls.append(invocation)

        if self._outcome is DevelopmentWorkflowProtectedRuntimeStartOutcome.PARTIAL_UNCERTAIN:
            self._uncertain_invocations.add(replay_key)
            _raise("protected_runtime_start_partial_transition_outcome_uncertain")

        succeeded = self._outcome is DevelopmentWorkflowProtectedRuntimeStartOutcome.SUCCESS
        receipt = _build_receipt(
            invocation=invocation,
            completed_at=now,
            succeeded=succeeded,
            starter=self,
        )
        self._receipts[replay_key] = receipt
        return receipt

    def _require_enabled(self) -> None:
        if not self.available:
            _raise("protected_runtime_start_development_starter_disabled")

    def _aware_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            _raise("protected_runtime_start_development_clock_must_be_aware")
        return value


def _build_receipt(
    *,
    invocation: WorkflowProtectedRuntimeStartInvocation,
    completed_at: datetime,
    succeeded: bool,
    starter: DeterministicDevelopmentWorkflowProtectedRuntimeStarter,
) -> WorkflowProtectedRuntimeStartReceipt:
    instruction = invocation.signed_instruction_envelope.instruction
    state = (
        WorkflowProtectedRuntimeStartConsumptionResultState.RUNTIME_STARTED_IN_PROTECTED_BOUNDARY
        if succeeded
        else WorkflowProtectedRuntimeStartConsumptionResultState.RUNTIME_START_FAILED_WITHOUT_START
    )
    aliases: dict[str, object] = {
        "instruction_digest": invocation.instruction_digest,
        "starter_contract_id": starter.starter_contract_id,
        "starter_contract_version": starter.starter_contract_version,
        "starter_id": starter.starter_id,
        "starter_version": starter.starter_version,
        "runtime_start_profile_id": starter.runtime_start_profile_id,
        "runtime_start_profile_version": starter.runtime_start_profile_version,
        "runtime_start_profile_digest": starter.runtime_start_profile_digest,
        "result_state": state,
        "runtime_start_count_pre": 0,
        "runtime_start_count_post": 1 if succeeded else 0,
        "runtime_started": succeeded,
        "runtime_envelope_current": True,
        "runtime_envelope_inactive": not succeeded,
        "residual_process_absent": not succeeded,
        "residual_task_absent": not succeeded,
        "scheduling_performed": False,
        "runtime_resumed": False,
        "generic_process_created": False,
        "prompt_constructed": False,
        "model_inference_performed": False,
        "connector_activity_performed": False,
        "network_activity_performed": False,
        "readiness_probe_performed": False,
        "publication_performed": False,
        "delivery_performed": False,
        "dispatch_performed": False,
        "execution_performed": False,
        "infrastructure_mutation_performed": False,
        "completed_at": completed_at,
        "signing_key_id": _policy().receipt_verification_signing_key_id,
        "signature_algorithm": "hmac-sha256",
    }
    values: dict[str, object] = {}
    for field in fields(WorkflowProtectedRuntimeStartReceipt):
        if field.name == "canonical_digest":
            continue
        if field.name == "integrity_signature":
            continue
        if field.name in aliases:
            values[field.name] = aliases[field.name]
        elif hasattr(instruction, field.name):
            values[field.name] = getattr(instruction, field.name)
        else:
            _raise(f"protected_runtime_start_receipt_field_unsupported:{field.name}")
    values["integrity_signature"] = _sign_payload(_DEVELOPMENT_RECEIPT_KEY, _payload(values))
    return WorkflowProtectedRuntimeStartReceipt(
        **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
    )


def _policy() -> WorkflowProtectedRuntimeStartConsumptionPolicy:
    return code_owned_workflow_protected_runtime_start_consumption_policy()


def _deadline(invocation: WorkflowProtectedRuntimeStartInvocation) -> datetime:
    for name in ("invocation_deadline", "start_deadline"):
        value = getattr(invocation, name, None)
        if isinstance(value, datetime):
            return value
    _raise("protected_runtime_start_invocation_deadline_missing")


def _identifier(value: object, *names: str) -> str:
    for name in names:
        candidate = getattr(value, name, None)
        if isinstance(candidate, str) and candidate:
            return candidate
    _raise(f"protected_runtime_start_identifier_missing:{','.join(names)}")


def _digest(value: object, name: str) -> str:
    candidate = getattr(value, name, None)
    if not isinstance(candidate, str) or not candidate:
        _raise(f"protected_runtime_start_digest_missing:{name}")
    return candidate


def _integer(value: object, name: str) -> int:
    candidate = getattr(value, name, None)
    if not isinstance(candidate, int) or isinstance(candidate, bool):
        _raise(f"protected_runtime_start_integer_missing:{name}")
    return candidate


def _payload(values: dict[str, object]) -> dict[str, object]:
    return {
        name: (
            value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if hasattr(value, "value")
            else value.canonical_value()
            if hasattr(value, "canonical_value")
            else value
        )
        for name, value in values.items()
    }


def _instruction_signature_payload(
    envelope: WorkflowProtectedRuntimeStartSignedInstructionEnvelope,
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
    raise WorkflowProtectedRuntimeStartConsumptionError(code)


__all__ = [
    "DenyAllWorkflowProtectedRuntimeStartInstructionSignatureVerifier",
    "DenyAllWorkflowProtectedRuntimeStartReceiptSignatureVerifier",
    "DeterministicDevelopmentWorkflowProtectedRuntimeStartInstructionSignatureVerifier",
    "DeterministicDevelopmentWorkflowProtectedRuntimeStartInstructionSigner",
    "DeterministicDevelopmentWorkflowProtectedRuntimeStartReceiptSignatureVerifier",
    "DeterministicDevelopmentWorkflowProtectedRuntimeStarter",
    "DevelopmentWorkflowProtectedRuntimeStartOutcome",
    "UnavailableWorkflowProtectedRuntimeStartInstructionSigner",
    "UnavailableWorkflowProtectedRuntimeStarter",
]
