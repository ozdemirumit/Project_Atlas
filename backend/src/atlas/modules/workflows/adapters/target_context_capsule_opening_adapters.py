from __future__ import annotations

import hmac
from collections.abc import Callable
from dataclasses import fields
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, NoReturn, cast

from atlas.modules.workflows.application.target_context_capsule_opening_ports import (
    WorkflowProtectedTargetContextCapsuleOpenabilityAttestation,
    WorkflowProtectedTargetContextCapsuleOpenabilityAttestationRequest,
    WorkflowProtectedTargetContextCapsuleOpeningCustodyAttestation,
    WorkflowProtectedTargetContextCapsuleOpeningCustodyAttestationRequest,
    WorkflowProtectedTransportTargetContextCapsuleOpeningError,
)
from atlas.modules.workflows.domain import (
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_RESIDENT_CONTEXT_MAXIMUM_LIFETIME_SECONDS,
    WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionPolicy,
    WorkflowProtectedTransportTargetContextCapsuleOpeningFailureClass,
    WorkflowProtectedTransportTargetContextCapsuleOpeningResultState,
    WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerInstruction,
    WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerReceipt,
    canonical_digest,
    canonical_json_bytes,
    code_owned_workflow_protected_transport_target_context_capsule_opening_consumption_policy,
)

_SYNTHETIC_ATTESTATION_KEY = b"atlas-test-only-capsule-opening-attestation-v1"
_SYNTHETIC_RECEIPT_KEY = b"atlas-test-only-capsule-opening-receipt-v1"


class UnavailableWorkflowProtectedTargetContextCapsuleOpeningCustodyAttestor:
    @property
    def available(self) -> bool:
        return False

    async def attest_opening_custody(
        self, request: WorkflowProtectedTargetContextCapsuleOpeningCustodyAttestationRequest
    ) -> WorkflowProtectedTargetContextCapsuleOpeningCustodyAttestation:
        del request
        _raise("target_context_capsule_opening_custody_attestor_unavailable")


class UnavailableWorkflowProtectedTargetContextCapsuleOpenabilityAttestor:
    @property
    def available(self) -> bool:
        return False

    async def attest_capsule_openability(
        self, request: WorkflowProtectedTargetContextCapsuleOpenabilityAttestationRequest
    ) -> WorkflowProtectedTargetContextCapsuleOpenabilityAttestation:
        del request
        _raise("target_context_capsule_opening_openability_attestor_unavailable")


class DenyAllWorkflowProtectedTargetContextCapsuleOpeningAttestationSignatureVerifier:
    def verify_opening_custody_attestation(
        self, attestation: WorkflowProtectedTargetContextCapsuleOpeningCustodyAttestation
    ) -> bool:
        del attestation
        return False

    def verify_capsule_openability_attestation(
        self, attestation: WorkflowProtectedTargetContextCapsuleOpenabilityAttestation
    ) -> bool:
        del attestation
        return False


class UnavailableWorkflowProtectedTargetContextCapsuleTrustedOpener:
    @property
    def available(self) -> bool:
        return False

    @property
    def opener_contract_id(self) -> str:
        return _policy().required_opener_contract_id

    @property
    def opener_contract_version(self) -> str:
        return _policy().required_opener_contract_version

    @property
    def opener_id(self) -> str:
        return _policy().approved_opener_id

    @property
    def opener_version(self) -> str:
        return _policy().approved_opener_version

    async def open_capsule(
        self, instruction: WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerInstruction
    ) -> WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerReceipt:
        del instruction
        _raise("target_context_capsule_opening_trusted_opener_unavailable")

    def verify_receipt(
        self, receipt: WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerReceipt
    ) -> bool:
        del receipt
        return False


class SyntheticWorkflowProtectedTargetContextCapsuleOpeningAttestors:
    """Test-only metadata attestors; they perform no external or local I/O."""

    def __init__(
        self,
        *,
        test_enabled: bool = False,
        clock: Callable[[], datetime] | None = None,
        custody_safe: bool = True,
        openable: bool = True,
    ) -> None:
        self._test_enabled = test_enabled
        self._clock = clock or (lambda: datetime.now(UTC))
        self._custody_safe = custody_safe
        self._openable = openable
        self.custody_calls: list[
            WorkflowProtectedTargetContextCapsuleOpeningCustodyAttestationRequest
        ] = []
        self.openability_calls: list[
            WorkflowProtectedTargetContextCapsuleOpenabilityAttestationRequest
        ] = []

    @property
    def available(self) -> bool:
        return self._test_enabled

    async def attest_opening_custody(
        self, request: WorkflowProtectedTargetContextCapsuleOpeningCustodyAttestationRequest
    ) -> WorkflowProtectedTargetContextCapsuleOpeningCustodyAttestation:
        self._require_enabled()
        self.custody_calls.append(request)
        now = self._aware_now()
        policy = _policy()
        values: dict[str, object] = {
            **_request_values(request),
            "attestation_id": (
                f"target-context-capsule-opening-custody.{request.request_nonce_digest[:24]}"
            ),
            "attestor_id": policy.required_custody_attestor_id,
            "attestor_version": policy.required_custody_attestor_version,
            "observed_at": now,
            "valid_until": now + timedelta(seconds=1),
            "capsule_remains_sealed": self._custody_safe,
            "destination_custody_final": self._custody_safe,
            "source_reuse_authority_terminated": self._custody_safe,
            "sealed_capsule_is_bearer_capability": False,
            "consumer_receipt_is_bearer_capability": False,
            "runtime_authority_granted": False,
            "runtime_authority_count": 0,
            "revoked": False,
            "destroyed": False,
            "signing_key_id": "key.synthetic-capsule-opening-attestation.v1",
            "signature_algorithm": "hmac-sha256",
        }
        signature_payload = _payload(values)
        values["integrity_signature"] = _sign(_SYNTHETIC_ATTESTATION_KEY, signature_payload)
        digest_payload = _payload(values)
        return WorkflowProtectedTargetContextCapsuleOpeningCustodyAttestation(
            **cast(Any, values), canonical_digest=canonical_digest(digest_payload)
        )

    async def attest_capsule_openability(
        self, request: WorkflowProtectedTargetContextCapsuleOpenabilityAttestationRequest
    ) -> WorkflowProtectedTargetContextCapsuleOpenabilityAttestation:
        self._require_enabled()
        self.openability_calls.append(request)
        now = self._aware_now()
        policy = _policy()
        values: dict[str, object] = {
            **_request_values(request),
            "attestation_id": (
                f"target-context-capsule-openability.{request.request_nonce_digest[:24]}"
            ),
            "attestor_id": policy.required_openability_attestor_id,
            "attestor_version": policy.required_openability_attestor_version,
            "observed_at": now,
            "valid_until": now + timedelta(seconds=1),
            "acceptance_eligible": self._openable,
            "capsule_openable": self._openable,
            "exact_capsule_binding_confirmed": self._openable,
            "protected_destination_confirmed": self._openable,
            "protected_resident_context_profile_confirmed": self._openable,
            "sealed_capsule_is_bearer_capability": False,
            "consumer_receipt_is_bearer_capability": False,
            "raw_material_return_authorized": False,
            "runtime_handle_creation_authorized": False,
            "network_activity_authorized": False,
            "delivery_authorized": False,
            "execution_authorized": False,
            "signing_key_id": "key.synthetic-capsule-opening-attestation.v1",
            "signature_algorithm": "hmac-sha256",
        }
        signature_payload = _payload(values)
        values["integrity_signature"] = _sign(_SYNTHETIC_ATTESTATION_KEY, signature_payload)
        digest_payload = _payload(values)
        return WorkflowProtectedTargetContextCapsuleOpenabilityAttestation(
            **cast(Any, values), canonical_digest=canonical_digest(digest_payload)
        )

    def verify_opening_custody_attestation(
        self, attestation: WorkflowProtectedTargetContextCapsuleOpeningCustodyAttestation
    ) -> bool:
        return self._test_enabled and _verify_attestation(attestation)

    def verify_capsule_openability_attestation(
        self, attestation: WorkflowProtectedTargetContextCapsuleOpenabilityAttestation
    ) -> bool:
        return self._test_enabled and _verify_attestation(attestation)

    def _require_enabled(self) -> None:
        if not self._test_enabled:
            _raise("target_context_capsule_opening_synthetic_attestor_disabled")

    def _aware_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            _raise("target_context_capsule_opening_synthetic_clock_must_be_aware")
        return value


class SyntheticWorkflowProtectedTargetContextCapsuleTrustedOpener:
    """Explicitly enabled test opener that emits fixed metadata and performs no I/O."""

    def __init__(
        self,
        *,
        test_enabled: bool = False,
        clock: Callable[[], datetime] | None = None,
        failure_class: WorkflowProtectedTransportTargetContextCapsuleOpeningFailureClass
        | None = None,
    ) -> None:
        self._test_enabled = test_enabled
        self._clock = clock or (lambda: datetime.now(UTC))
        self._failure_class = failure_class
        self.calls: list[
            WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerInstruction
        ] = []

    @property
    def available(self) -> bool:
        return self._test_enabled

    @property
    def opener_contract_id(self) -> str:
        return _policy().required_opener_contract_id

    @property
    def opener_contract_version(self) -> str:
        return _policy().required_opener_contract_version

    @property
    def opener_id(self) -> str:
        return _policy().approved_opener_id

    @property
    def opener_version(self) -> str:
        return _policy().approved_opener_version

    async def open_capsule(
        self, instruction: WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerInstruction
    ) -> WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerReceipt:
        if not self._test_enabled:
            _raise("target_context_capsule_opening_synthetic_opener_disabled")
        if instruction.canonical_digest != canonical_digest(instruction.digest_payload()):
            _raise("target_context_capsule_opening_instruction_invalid")
        self.calls.append(instruction)
        completed_at = self._clock()
        if completed_at.tzinfo is None:
            _raise("target_context_capsule_opening_synthetic_clock_must_be_aware")
        failure = self._failure_class
        if completed_at >= instruction.opening_deadline:
            failure = (
                WorkflowProtectedTransportTargetContextCapsuleOpeningFailureClass.DEADLINE_EXPIRED
            )
        failed = failure is not None
        resident_context_created_at = None if failed else completed_at
        resident_context_usable_until = (
            None
            if failed
            else min(
                instruction.resident_context_usable_until_limit,
                completed_at
                + timedelta(
                    seconds=(
                        WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_RESIDENT_CONTEXT_MAXIMUM_LIFETIME_SECONDS
                    )
                ),
            )
        )
        resident_digest = canonical_digest(
            {
                "attempt_id": instruction.attempt_id,
                "instruction_digest": instruction.canonical_digest,
                "profile_digest": instruction.trusted_opener_profile_digest,
            }
        )
        values: dict[str, object] = {
            "opening_id": instruction.opening_id,
            "attempt_id": instruction.attempt_id,
            "consumption_claim_id": instruction.consumption_claim_id,
            "instruction_digest": instruction.canonical_digest,
            "authorization_lease_id": instruction.authorization_lease_id,
            "authorization_lease_digest": instruction.authorization_lease_digest,
            "sealed_capsule_id": instruction.sealed_capsule_id,
            "sealed_capsule_digest": instruction.sealed_capsule_digest,
            "consumer_receipt_id": instruction.consumer_receipt_id,
            "consumer_receipt_digest": instruction.consumer_receipt_digest,
            "opener_contract_id": self.opener_contract_id,
            "opener_contract_version": self.opener_contract_version,
            "opener_id": self.opener_id,
            "opener_version": self.opener_version,
            "destination_boundary_id": instruction.destination_boundary_id,
            "destination_deployment_id": instruction.destination_deployment_id,
            "destination_generation": instruction.destination_generation,
            "destination_fencing_token_digest": (instruction.destination_fencing_token_digest),
            "custody_contract_id": instruction.custody_contract_id,
            "custody_contract_version": instruction.custody_contract_version,
            "trusted_opener_profile_digest": instruction.trusted_opener_profile_digest,
            "state": (
                WorkflowProtectedTransportTargetContextCapsuleOpeningResultState.OPENING_FAILED
                if failed
                else (
                    WorkflowProtectedTransportTargetContextCapsuleOpeningResultState
                ).OPENED_IN_PROTECTED_CONSUMER_BOUNDARY
            ),
            "failure_class": failure,
            "protected_resident_context_id": (
                None if failed else f"protected-resident-target-context.{resident_digest[:24]}"
            ),
            "protected_resident_context_digest": None if failed else resident_digest,
            "protected_resident_context_created_at": resident_context_created_at,
            "protected_resident_context_usable_until": resident_context_usable_until,
            "protected_resident_context_is_bearer_capability": False,
            "capsule_opened_in_protected_boundary": not failed,
            "target_context_pair_verified": not failed,
            "raw_target_context_returned": False,
            "runtime_handle_created": False,
            "network_activity_performed": False,
            "delivery_performed": False,
            "execution_performed": False,
            "protected_source_closed": True,
            "source_capsule_zeroized": True,
            "completed_at": completed_at,
            "opening_deadline": instruction.opening_deadline,
            "attested_by": "attestor.synthetic-capsule-opening-receipt",
            "signing_key_id": _policy().verification_signing_key_id,
            "signature_algorithm": "hmac-sha256",
        }
        values["integrity_signature"] = _sign(_SYNTHETIC_RECEIPT_KEY, _payload(values))
        return WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerReceipt(
            **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
        )

    def verify_receipt(
        self, receipt: WorkflowProtectedTransportTargetContextCapsuleTrustedOpenerReceipt
    ) -> bool:
        if (
            not self._test_enabled
            or receipt.opener_contract_id != self.opener_contract_id
            or receipt.opener_contract_version != self.opener_contract_version
            or receipt.opener_id != self.opener_id
            or receipt.opener_version != self.opener_version
            or receipt.signature_algorithm != "hmac-sha256"
            or receipt.canonical_digest != canonical_digest(receipt.digest_payload())
        ):
            return False
        expected = _sign(_SYNTHETIC_RECEIPT_KEY, receipt.signature_payload())
        return hmac.compare_digest(expected, receipt.integrity_signature)


def _policy() -> WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionPolicy:
    return (
        code_owned_workflow_protected_transport_target_context_capsule_opening_consumption_policy()
    )


def _request_values(value: Any) -> dict[str, object]:
    return {
        field.name: getattr(value, field.name)
        for field in fields(value)
        if field.name != "requested_at"
    }


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


def _sign(key: bytes, payload: dict[str, object]) -> str:
    return hmac.new(key, canonical_json_bytes(payload), sha256).hexdigest()


def _verify_attestation(
    attestation: WorkflowProtectedTargetContextCapsuleOpeningCustodyAttestation
    | WorkflowProtectedTargetContextCapsuleOpenabilityAttestation,
) -> bool:
    if (
        attestation.signing_key_id != "key.synthetic-capsule-opening-attestation.v1"
        or attestation.signature_algorithm != "hmac-sha256"
        or attestation.canonical_digest != canonical_digest(attestation.digest_payload())
    ):
        return False
    expected = _sign(_SYNTHETIC_ATTESTATION_KEY, attestation.signature_payload())
    return hmac.compare_digest(expected, attestation.integrity_signature)


def _raise(code: str) -> NoReturn:
    raise WorkflowProtectedTransportTargetContextCapsuleOpeningError(code)


__all__ = [
    "DenyAllWorkflowProtectedTargetContextCapsuleOpeningAttestationSignatureVerifier",
    "SyntheticWorkflowProtectedTargetContextCapsuleOpeningAttestors",
    "SyntheticWorkflowProtectedTargetContextCapsuleTrustedOpener",
    "UnavailableWorkflowProtectedTargetContextCapsuleOpenabilityAttestor",
    "UnavailableWorkflowProtectedTargetContextCapsuleOpeningCustodyAttestor",
    "UnavailableWorkflowProtectedTargetContextCapsuleTrustedOpener",
]
