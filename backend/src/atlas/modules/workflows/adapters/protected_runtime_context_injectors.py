from __future__ import annotations

import hmac
from collections.abc import Callable
from dataclasses import fields
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, NoReturn, cast

from atlas.modules.workflows.application.protected_runtime_context_injection_consumption_ports import (  # noqa: E501
    WorkflowProtectedRuntimeContextInjectionConsumptionError,
    WorkflowProtectedRuntimeSlotReadinessAttestation,
    WorkflowProtectedRuntimeSlotReadinessAttestationRequest,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedRuntimeContextInjectionConsumptionFailureClass,
    WorkflowProtectedRuntimeContextInjectionConsumptionPolicy,
    WorkflowProtectedRuntimeContextInjectionConsumptionResultState,
    WorkflowProtectedRuntimeContextTrustedInjectorInvocation,
    WorkflowProtectedRuntimeContextTrustedInjectorReceipt,
    canonical_digest,
    canonical_json_bytes,
    code_owned_workflow_protected_runtime_context_injection_consumption_policy,
)

_DEVELOPMENT_READINESS_KEY = b"atlas-development-runtime-slot-readiness-v1"
_DEVELOPMENT_RECEIPT_KEY = b"atlas-development-runtime-context-injection-receipt-v1"


class UnavailableWorkflowProtectedRuntimeSlotReadinessAttestor:
    @property
    def available(self) -> bool:
        return False

    async def attest_runtime_slot_readiness(
        self, request: WorkflowProtectedRuntimeSlotReadinessAttestationRequest
    ) -> WorkflowProtectedRuntimeSlotReadinessAttestation:
        del request
        _raise("protected_runtime_slot_readiness_attestor_unavailable")


class DenyAllWorkflowProtectedRuntimeSlotReadinessSignatureVerifier:
    def verify_runtime_slot_readiness_attestation(
        self, attestation: WorkflowProtectedRuntimeSlotReadinessAttestation
    ) -> bool:
        del attestation
        return False


class DenyAllWorkflowProtectedRuntimeContextTrustedInjectorReceiptSignatureVerifier:
    def verify_receipt(
        self, receipt: WorkflowProtectedRuntimeContextTrustedInjectorReceipt
    ) -> bool:
        del receipt
        return False


class UnavailableWorkflowProtectedRuntimeContextTrustedInjector:
    @property
    def available(self) -> bool:
        return False

    @property
    def injector_contract_id(self) -> str:
        return _policy().required_injector_contract_id

    @property
    def injector_contract_version(self) -> str:
        return _policy().required_injector_contract_version

    @property
    def injector_id(self) -> str:
        return _policy().approved_injector_id

    @property
    def injector_version(self) -> str:
        return _policy().approved_injector_version

    @property
    def runtime_slot_profile_id(self) -> str:
        return _policy().runtime_slot_profile_id

    @property
    def runtime_slot_profile_version(self) -> str:
        return _policy().runtime_slot_profile_version

    @property
    def runtime_slot_profile_digest(self) -> str:
        return _policy().runtime_slot_profile_digest

    async def inject_context(
        self, invocation: WorkflowProtectedRuntimeContextTrustedInjectorInvocation
    ) -> WorkflowProtectedRuntimeContextTrustedInjectorReceipt:
        del invocation
        _raise("protected_runtime_context_trusted_injector_unavailable")


class DeterministicDevelopmentWorkflowProtectedRuntimeSlotReadinessAttestor:
    """Development-only signed metadata attestor with no external or local I/O."""

    def __init__(
        self,
        *,
        development_enabled: bool = False,
        clock: Callable[[], datetime] | None = None,
        ready: bool = True,
        runtime_slot_pre_generation: int = 0,
    ) -> None:
        self._development_enabled = development_enabled
        self._clock = clock or (lambda: datetime.now(UTC))
        self._ready = ready
        self._runtime_slot_pre_generation = runtime_slot_pre_generation
        self.calls: list[WorkflowProtectedRuntimeSlotReadinessAttestationRequest] = []

    @property
    def available(self) -> bool:
        return self._development_enabled

    async def attest_runtime_slot_readiness(
        self, request: WorkflowProtectedRuntimeSlotReadinessAttestationRequest
    ) -> WorkflowProtectedRuntimeSlotReadinessAttestation:
        self._require_enabled()
        now = self._aware_now()
        self.calls.append(request)
        policy = _policy()
        ready = self._ready
        values: dict[str, object] = {
            **_request_values(request),
            "attestation_id": (
                f"protected-runtime-slot-readiness.{request.request_nonce_digest[:24]}"
            ),
            "attestor_id": policy.required_slot_readiness_attestor_id,
            "attestor_version": policy.required_slot_readiness_attestor_version,
            "signing_key_id": policy.slot_readiness_verification_signing_key_id,
            "signature_algorithm": "hmac-sha256",
            "runtime_slot_commitment": canonical_digest(
                {
                    "destination_boundary_id": request.destination_boundary_id,
                    "destination_deployment_id": request.destination_deployment_id,
                    "runtime_slot_profile_digest": request.runtime_slot_profile_digest,
                }
            ),
            "runtime_slot_pre_generation": self._runtime_slot_pre_generation,
            "observed_at": now,
            "valid_until": min(
                request.protected_runtime_handle_usable_until, now + timedelta(seconds=1)
            ),
            "exact_runtime_slot_confirmed": ready,
            "runtime_slot_empty": ready,
            "runtime_slot_inert": ready,
            "runtime_slot_eligible": ready,
            "atomic_compare_and_swap_supported": ready,
            "destination_generation_current": ready,
            "destination_fence_current": ready,
            "injector_profile_eligible": ready,
            "runtime_autostart_disabled": True,
            "raw_context_included": False,
            "runtime_handle_material_included": False,
            "runtime_payload_included": False,
            "runtime_slot_locator_included": False,
            "endpoint_included": False,
            "credential_included": False,
            "bearer_token_included": False,
            "connector_activity_authorized": False,
            "network_activity_authorized": False,
            "readiness_probe_authorized": False,
            "execution_authorized": False,
            "infrastructure_mutation_authorized": False,
        }
        values["integrity_signature"] = _sign(_DEVELOPMENT_READINESS_KEY, _payload(values))
        return WorkflowProtectedRuntimeSlotReadinessAttestation(
            **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
        )

    def verify_runtime_slot_readiness_attestation(
        self, attestation: WorkflowProtectedRuntimeSlotReadinessAttestation
    ) -> bool:
        if (
            not self._development_enabled
            or attestation.signing_key_id != _policy().slot_readiness_verification_signing_key_id
            or attestation.signature_algorithm != "hmac-sha256"
            or attestation.canonical_digest != canonical_digest(attestation.digest_payload())
        ):
            return False
        expected = _sign(_DEVELOPMENT_READINESS_KEY, attestation.signature_payload())
        return hmac.compare_digest(expected, attestation.integrity_signature)

    def _require_enabled(self) -> None:
        if not self._development_enabled:
            _raise("protected_runtime_slot_readiness_development_adapter_disabled")

    def _aware_now(self) -> datetime:
        value = self._clock()
        if value.tzinfo is None:
            _raise("protected_runtime_context_injector_development_clock_must_be_aware")
        return value


class DeterministicDevelopmentWorkflowProtectedRuntimeContextTrustedInjector:
    """Development-only CAS simulator receiving only an opaque reference and digest."""

    def __init__(
        self,
        *,
        development_enabled: bool = False,
        clock: Callable[[], datetime] | None = None,
        runtime_slot_pre_generation: int = 0,
        fail_with: WorkflowProtectedRuntimeContextInjectionConsumptionFailureClass | None = None,
    ) -> None:
        self._development_enabled = development_enabled
        self._clock = clock or (lambda: datetime.now(UTC))
        self._runtime_slot_pre_generation = runtime_slot_pre_generation
        self._fail_with = fail_with
        self._consumed_instruction_digests: set[str] = set()
        self.calls: list[WorkflowProtectedRuntimeContextTrustedInjectorInvocation] = []

    @property
    def available(self) -> bool:
        return self._development_enabled

    @property
    def injector_contract_id(self) -> str:
        return _policy().required_injector_contract_id

    @property
    def injector_contract_version(self) -> str:
        return _policy().required_injector_contract_version

    @property
    def injector_id(self) -> str:
        return _policy().approved_injector_id

    @property
    def injector_version(self) -> str:
        return _policy().approved_injector_version

    @property
    def runtime_slot_profile_id(self) -> str:
        return _policy().runtime_slot_profile_id

    @property
    def runtime_slot_profile_version(self) -> str:
        return _policy().runtime_slot_profile_version

    @property
    def runtime_slot_profile_digest(self) -> str:
        return _policy().runtime_slot_profile_digest

    async def inject_context(
        self, invocation: WorkflowProtectedRuntimeContextTrustedInjectorInvocation
    ) -> WorkflowProtectedRuntimeContextTrustedInjectorReceipt:
        if not self._development_enabled:
            _raise("protected_runtime_context_trusted_injector_development_adapter_disabled")
        completed_at = self._clock()
        if completed_at.tzinfo is None:
            _raise("protected_runtime_context_injector_development_clock_must_be_aware")
        if completed_at >= invocation.injection_deadline:
            _raise("protected_runtime_context_trusted_injector_deadline_expired")
        if invocation.instruction_digest in self._consumed_instruction_digests:
            _raise("protected_runtime_context_trusted_injector_compare_and_swap_rejected")

        self._consumed_instruction_digests.add(invocation.instruction_digest)
        self.calls.append(invocation)
        failure = self._fail_with
        succeeded = failure is None
        values: dict[str, object] = {
            "instruction_digest": invocation.instruction_digest,
            "protected_operation_reference": invocation.protected_operation_reference,
            "runtime_slot_pre_generation": self._runtime_slot_pre_generation,
            "runtime_slot_post_generation": (
                self._runtime_slot_pre_generation + 1
                if succeeded
                else self._runtime_slot_pre_generation
            ),
            "injector_contract_id": self.injector_contract_id,
            "injector_contract_version": self.injector_contract_version,
            "injector_id": self.injector_id,
            "injector_version": self.injector_version,
            "state": (
                WorkflowProtectedRuntimeContextInjectionConsumptionResultState.INJECTED_INTO_PROTECTED_RUNTIME_SLOT
                if succeeded
                else WorkflowProtectedRuntimeContextInjectionConsumptionResultState.INJECTION_FAILED
            ),
            "failure_class": failure,
            "protected_runtime_handle_consumed": succeeded,
            "inert_context_injected": succeeded,
            "runtime_slot_mutation_performed": succeeded,
            "runtime_slot_empty_confirmed": not succeeded,
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
            "completed_at": completed_at,
            "injection_deadline": invocation.injection_deadline,
            "attested_by": "attestor.development-protected-runtime-context-injection-receipt",
            "signing_key_id": _policy().receipt_verification_signing_key_id,
            "signature_algorithm": "hmac-sha256",
        }
        values["integrity_signature"] = _sign(_DEVELOPMENT_RECEIPT_KEY, _payload(values))
        return WorkflowProtectedRuntimeContextTrustedInjectorReceipt(
            **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
        )

    def verify_receipt(
        self, receipt: WorkflowProtectedRuntimeContextTrustedInjectorReceipt
    ) -> bool:
        if (
            not self._development_enabled
            or receipt.injector_contract_id != self.injector_contract_id
            or receipt.injector_contract_version != self.injector_contract_version
            or receipt.injector_id != self.injector_id
            or receipt.injector_version != self.injector_version
            or receipt.signing_key_id != _policy().receipt_verification_signing_key_id
            or receipt.signature_algorithm != "hmac-sha256"
            or receipt.canonical_digest != canonical_digest(receipt.digest_payload())
        ):
            return False
        expected = _sign(_DEVELOPMENT_RECEIPT_KEY, receipt.signature_payload())
        return hmac.compare_digest(expected, receipt.integrity_signature)


def _policy() -> WorkflowProtectedRuntimeContextInjectionConsumptionPolicy:
    return code_owned_workflow_protected_runtime_context_injection_consumption_policy()


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


def _raise(code: str) -> NoReturn:
    raise WorkflowProtectedRuntimeContextInjectionConsumptionError(code)


__all__ = [
    "DenyAllWorkflowProtectedRuntimeContextTrustedInjectorReceiptSignatureVerifier",
    "DenyAllWorkflowProtectedRuntimeSlotReadinessSignatureVerifier",
    "DeterministicDevelopmentWorkflowProtectedRuntimeContextTrustedInjector",
    "DeterministicDevelopmentWorkflowProtectedRuntimeSlotReadinessAttestor",
    "UnavailableWorkflowProtectedRuntimeContextTrustedInjector",
    "UnavailableWorkflowProtectedRuntimeSlotReadinessAttestor",
]
