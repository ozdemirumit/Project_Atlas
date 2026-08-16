from __future__ import annotations

import hmac
from collections.abc import Callable
from dataclasses import fields
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, NoReturn, cast

from atlas.modules.workflows.application.protected_resident_context_access_consumption_ports import (  # noqa: E501
    WorkflowProtectedResidentContextAccessConsumptionError,
    WorkflowProtectedResidentContextAccessorReadinessAttestation,
    WorkflowProtectedResidentContextAccessorReadinessAttestationRequest,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedResidentContextAccessConsumptionFailureClass,
    WorkflowProtectedResidentContextAccessConsumptionPolicy,
    WorkflowProtectedResidentContextAccessConsumptionResultState,
    WorkflowProtectedResidentContextTrustedAccessorInstruction,
    WorkflowProtectedResidentContextTrustedAccessorReceipt,
    canonical_digest,
    canonical_json_bytes,
    code_owned_workflow_protected_resident_context_access_consumption_policy,
)

_DEVELOPMENT_ATTESTATION_KEY = b"atlas-development-resident-context-access-attestation-v1"
_DEVELOPMENT_RECEIPT_KEY = b"atlas-development-resident-context-access-receipt-v1"


class UnavailableWorkflowProtectedResidentContextAccessorReadinessAttestor:
    @property
    def available(self) -> bool:
        return False

    async def attest_accessor_readiness(
        self, request: WorkflowProtectedResidentContextAccessorReadinessAttestationRequest
    ) -> WorkflowProtectedResidentContextAccessorReadinessAttestation:
        del request
        _raise("protected_resident_context_accessor_readiness_attestor_unavailable")


class DenyAllWorkflowProtectedResidentContextAccessorReadinessSignatureVerifier:
    def verify_accessor_readiness_attestation(
        self, attestation: WorkflowProtectedResidentContextAccessorReadinessAttestation
    ) -> bool:
        del attestation
        return False


class UnavailableWorkflowProtectedResidentContextTrustedAccessor:
    @property
    def available(self) -> bool:
        return False

    @property
    def accessor_contract_id(self) -> str:
        return _policy().required_accessor_contract_id

    @property
    def accessor_contract_version(self) -> str:
        return _policy().required_accessor_contract_version

    @property
    def accessor_id(self) -> str:
        return _policy().approved_accessor_id

    @property
    def accessor_version(self) -> str:
        return _policy().approved_accessor_version

    @property
    def runtime_handle_profile_id(self) -> str:
        return _policy().runtime_handle_profile_id

    @property
    def runtime_handle_profile_version(self) -> str:
        return _policy().runtime_handle_profile_version

    @property
    def runtime_handle_profile_digest(self) -> str:
        return _policy().runtime_handle_profile_digest

    async def establish_access(
        self, instruction: WorkflowProtectedResidentContextTrustedAccessorInstruction
    ) -> WorkflowProtectedResidentContextTrustedAccessorReceipt:
        del instruction
        _raise("protected_resident_context_trusted_accessor_unavailable")

    def verify_receipt(
        self, receipt: WorkflowProtectedResidentContextTrustedAccessorReceipt
    ) -> bool:
        del receipt
        return False


class DeterministicDevelopmentWorkflowProtectedResidentContextAccessorReadinessAttestor:
    """Development-only signed metadata attestor with no external or local I/O."""

    def __init__(
        self,
        *,
        development_enabled: bool = False,
        clock: Callable[[], datetime] | None = None,
        ready: bool = True,
    ) -> None:
        self._development_enabled = development_enabled
        self._clock = clock or (lambda: datetime.now(UTC))
        self._ready = ready
        self.calls: list[WorkflowProtectedResidentContextAccessorReadinessAttestationRequest] = []

    @property
    def available(self) -> bool:
        return self._development_enabled

    async def attest_accessor_readiness(
        self, request: WorkflowProtectedResidentContextAccessorReadinessAttestationRequest
    ) -> WorkflowProtectedResidentContextAccessorReadinessAttestation:
        self._require_enabled()
        now = self._aware_now()
        self.calls.append(request)
        policy = _policy()
        valid_until = min(
            request.protected_resident_context_usable_until, now + timedelta(seconds=1)
        )
        values: dict[str, object] = {
            **_request_values(request),
            "attestation_id": (
                f"protected-resident-context-access-readiness.{request.request_nonce_digest[:24]}"
            ),
            "attestor_id": policy.required_readiness_attestor_id,
            "attestor_version": policy.required_readiness_attestor_version,
            "signing_key_id": policy.readiness_verification_signing_key_id,
            "signature_algorithm": "hmac-sha256",
            "observed_at": now,
            "valid_until": valid_until,
            "access_eligible": self._ready,
            "exact_resident_context_confirmed": self._ready,
            "protected_destination_confirmed": self._ready,
            "atomic_compare_and_set_supported": self._ready,
            "resident_context_unconsumed": self._ready,
            "runtime_handle_outstanding": False,
            "runtime_handle_profile_confirmed": self._ready,
            "runtime_handle_is_bearer_capability": False,
            "raw_context_included": False,
            "runtime_handle_locator_included": False,
            "endpoint_included": False,
            "credential_included": False,
            "secret_included": False,
            "bearer_token_included": False,
            "provider_payload_included": False,
            "network_activity_authorized": False,
            "execution_authorized": False,
            "infrastructure_mutation_authorized": False,
        }
        values["integrity_signature"] = _sign(_DEVELOPMENT_ATTESTATION_KEY, _payload(values))
        return WorkflowProtectedResidentContextAccessorReadinessAttestation(
            **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
        )

    def verify_accessor_readiness_attestation(
        self, attestation: WorkflowProtectedResidentContextAccessorReadinessAttestation
    ) -> bool:
        if (
            not self._development_enabled
            or attestation.signing_key_id != _policy().readiness_verification_signing_key_id
            or attestation.signature_algorithm != "hmac-sha256"
            or attestation.canonical_digest != canonical_digest(attestation.digest_payload())
        ):
            return False
        expected = _sign(_DEVELOPMENT_ATTESTATION_KEY, attestation.signature_payload())
        return hmac.compare_digest(expected, attestation.integrity_signature)

    def _require_enabled(self) -> None:
        if not self._development_enabled:
            _raise("protected_resident_context_accessor_readiness_development_adapter_disabled")

    def _aware_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            _raise("protected_resident_context_accessor_development_clock_must_be_aware")
        return value


class DeterministicDevelopmentWorkflowProtectedResidentContextTrustedAccessor:
    """Development-only protected-side CAS simulator; it emits metadata and performs no I/O."""

    def __init__(
        self,
        *,
        development_enabled: bool = False,
        clock: Callable[[], datetime] | None = None,
        fail_with: WorkflowProtectedResidentContextAccessConsumptionFailureClass | None = None,
    ) -> None:
        self._development_enabled = development_enabled
        self._clock = clock or (lambda: datetime.now(UTC))
        self._fail_with = fail_with
        self._consumed_context_digests: set[str] = set()
        self.calls: list[WorkflowProtectedResidentContextTrustedAccessorInstruction] = []

    @property
    def available(self) -> bool:
        return self._development_enabled

    @property
    def accessor_contract_id(self) -> str:
        return _policy().required_accessor_contract_id

    @property
    def accessor_contract_version(self) -> str:
        return _policy().required_accessor_contract_version

    @property
    def accessor_id(self) -> str:
        return _policy().approved_accessor_id

    @property
    def accessor_version(self) -> str:
        return _policy().approved_accessor_version

    @property
    def runtime_handle_profile_id(self) -> str:
        return _policy().runtime_handle_profile_id

    @property
    def runtime_handle_profile_version(self) -> str:
        return _policy().runtime_handle_profile_version

    @property
    def runtime_handle_profile_digest(self) -> str:
        return _policy().runtime_handle_profile_digest

    async def establish_access(
        self, instruction: WorkflowProtectedResidentContextTrustedAccessorInstruction
    ) -> WorkflowProtectedResidentContextTrustedAccessorReceipt:
        if not self._development_enabled:
            _raise("protected_resident_context_trusted_accessor_development_adapter_disabled")
        if instruction.canonical_digest != canonical_digest(instruction.digest_payload()):
            _raise("protected_resident_context_trusted_accessor_instruction_invalid")
        completed_at = self._clock()
        if completed_at.tzinfo is None:
            _raise("protected_resident_context_accessor_development_clock_must_be_aware")
        if completed_at >= instruction.access_deadline:
            _raise("protected_resident_context_trusted_accessor_deadline_expired")
        context_digest = instruction.protected_resident_context_digest
        if context_digest in self._consumed_context_digests:
            _raise("protected_resident_context_trusted_accessor_compare_and_set_rejected")

        # The in-memory transition models the protected boundary's single atomic CAS. It is
        # intentionally irreversible even if receipt persistence later fails.
        self._consumed_context_digests.add(context_digest)
        self.calls.append(instruction)
        failure = self._fail_with
        succeeded = failure is None
        handle_digest = (
            canonical_digest(
                {
                    "attempt_id": instruction.attempt_id,
                    "instruction_digest": instruction.canonical_digest,
                    "runtime_handle_profile_digest": instruction.runtime_handle_profile_digest,
                }
            )
            if succeeded
            else None
        )
        handle_usable_until = (
            min(instruction.protected_resident_context_usable_until, instruction.access_deadline)
            if succeeded
            else None
        )
        values: dict[str, object] = {
            **_instruction_values(instruction),
            "instruction_digest": instruction.canonical_digest,
            "state": (
                WorkflowProtectedResidentContextAccessConsumptionResultState.HANDLE_ESTABLISHED_IN_PROTECTED_BOUNDARY
                if succeeded
                else WorkflowProtectedResidentContextAccessConsumptionResultState.RESIDENT_CONTEXT_ACCESS_FAILED  # noqa: E501
            ),
            "failure_class": failure,
            "protected_runtime_handle_id": (
                None
                if handle_digest is None
                else f"protected-runtime-context-handle.{handle_digest[:24]}"
            ),
            "protected_runtime_handle_digest": handle_digest,
            "protected_runtime_handle_created_at": completed_at if succeeded else None,
            "protected_runtime_handle_usable_until": handle_usable_until,
            "protected_resident_context_consumed": True,
            "runtime_handle_established_in_protected_boundary": succeeded,
            "protected_runtime_handle_is_bearer_capability": False,
            "runtime_handle_absence_confirmed": not succeeded,
            "raw_context_returned": False,
            "runtime_handle_locator_returned": False,
            "endpoint_returned": False,
            "credential_returned": False,
            "secret_returned": False,
            "bearer_token_returned": False,
            "provider_payload_returned": False,
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
            "completed_at": completed_at,
            "attested_by": "attestor.development-protected-resident-context-access-receipt",
            "signing_key_id": _policy().verification_signing_key_id,
            "signature_algorithm": "hmac-sha256",
        }
        receipt_fields = {
            field.name for field in fields(WorkflowProtectedResidentContextTrustedAccessorReceipt)
        }
        receipt_values = {
            name: value
            for name, value in values.items()
            if name in receipt_fields and name != "canonical_digest"
        }
        values_missing = (
            receipt_fields
            - receipt_values.keys()
            - {
                "canonical_digest",
                "integrity_signature",
            }
        )
        if values_missing:
            _raise("protected_resident_context_trusted_accessor_domain_contract_invalid")
        receipt_values["integrity_signature"] = _sign(
            _DEVELOPMENT_RECEIPT_KEY,
            _payload({k: v for k, v in receipt_values.items() if k != "integrity_signature"}),
        )
        return WorkflowProtectedResidentContextTrustedAccessorReceipt(
            **cast(Any, receipt_values),
            canonical_digest=canonical_digest(_payload(receipt_values)),
        )

    def verify_receipt(
        self, receipt: WorkflowProtectedResidentContextTrustedAccessorReceipt
    ) -> bool:
        if (
            not self._development_enabled
            or receipt.accessor_contract_id != self.accessor_contract_id
            or receipt.accessor_contract_version != self.accessor_contract_version
            or receipt.accessor_id != self.accessor_id
            or receipt.accessor_version != self.accessor_version
            or receipt.runtime_handle_profile_id != self.runtime_handle_profile_id
            or receipt.runtime_handle_profile_version != self.runtime_handle_profile_version
            or receipt.runtime_handle_profile_digest != self.runtime_handle_profile_digest
            or receipt.signature_algorithm != "hmac-sha256"
            or receipt.canonical_digest != canonical_digest(receipt.digest_payload())
        ):
            return False
        expected = _sign(_DEVELOPMENT_RECEIPT_KEY, receipt.signature_payload())
        return hmac.compare_digest(expected, receipt.integrity_signature)


def _policy() -> WorkflowProtectedResidentContextAccessConsumptionPolicy:
    return code_owned_workflow_protected_resident_context_access_consumption_policy()


def _request_values(value: Any) -> dict[str, object]:
    return {
        field.name: getattr(value, field.name)
        for field in fields(value)
        if field.name != "requested_at"
    }


def _instruction_values(value: Any) -> dict[str, object]:
    return {
        field.name: getattr(value, field.name)
        for field in fields(value)
        if field.name != "canonical_digest"
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


def _raise(code: str) -> NoReturn:
    raise WorkflowProtectedResidentContextAccessConsumptionError(code)


__all__ = [
    "DenyAllWorkflowProtectedResidentContextAccessorReadinessSignatureVerifier",
    "DeterministicDevelopmentWorkflowProtectedResidentContextAccessorReadinessAttestor",
    "DeterministicDevelopmentWorkflowProtectedResidentContextTrustedAccessor",
    "UnavailableWorkflowProtectedResidentContextAccessorReadinessAttestor",
    "UnavailableWorkflowProtectedResidentContextTrustedAccessor",
]
