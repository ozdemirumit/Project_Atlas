from __future__ import annotations

import hmac
from collections.abc import Callable
from dataclasses import fields
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, NoReturn, cast

from atlas.modules.workflows.application.protected_runtime_context_injection_authorization_ports import (  # noqa: E501
    WorkflowProtectedRuntimeContextInjectionAuthorizationError,
    WorkflowProtectedRuntimeHandleLifecycleAttestation,
    WorkflowProtectedRuntimeHandleLifecycleAttestationRequest,
)
from atlas.modules.workflows.domain import (
    canonical_digest,
    canonical_json_bytes,
    code_owned_workflow_protected_runtime_context_injection_authorization_policy,
)

_DEVELOPMENT_ATTESTATION_KEY = (
    b"atlas-development-only-protected-runtime-handle-lifecycle-attestation-v1"
)


class UnavailableWorkflowProtectedRuntimeHandleLifecycleAttestor:
    @property
    def available(self) -> bool:
        return False

    async def attest_runtime_handle_lifecycle(
        self, request: WorkflowProtectedRuntimeHandleLifecycleAttestationRequest
    ) -> WorkflowProtectedRuntimeHandleLifecycleAttestation:
        del request
        _raise("workflow_protected_runtime_handle_lifecycle_attestor_unavailable")

    def verify_runtime_handle_lifecycle_attestation(
        self, attestation: WorkflowProtectedRuntimeHandleLifecycleAttestation
    ) -> bool:
        del attestation
        return False


class DeterministicDevelopmentWorkflowProtectedRuntimeHandleLifecycleAttestor:
    """Explicit development-only signed metadata attestor with no protected I/O."""

    def __init__(
        self,
        *,
        development_enabled: bool = False,
        clock: Callable[[], datetime] | None = None,
        runtime_handle_present: bool = True,
        runtime_handle_revoked: bool = False,
        runtime_handle_destroyed: bool = False,
        runtime_handle_injected: bool = False,
        runtime_handle_used: bool = False,
        injection_consumption_outstanding: bool = False,
        destination_generation_current: bool = True,
        destination_fence_current: bool = True,
        injector_profile_eligible: bool = True,
        runtime_slot_profile_eligible: bool = True,
    ) -> None:
        self._development_enabled = development_enabled
        self._clock = clock or (lambda: datetime.now(UTC))
        self._runtime_handle_present = runtime_handle_present
        self._runtime_handle_revoked = runtime_handle_revoked
        self._runtime_handle_destroyed = runtime_handle_destroyed
        self._runtime_handle_injected = runtime_handle_injected
        self._runtime_handle_used = runtime_handle_used
        self._injection_consumption_outstanding = injection_consumption_outstanding
        self._destination_generation_current = destination_generation_current
        self._destination_fence_current = destination_fence_current
        self._injector_profile_eligible = injector_profile_eligible
        self._runtime_slot_profile_eligible = runtime_slot_profile_eligible
        self.calls: list[WorkflowProtectedRuntimeHandleLifecycleAttestationRequest] = []

    @property
    def available(self) -> bool:
        return self._development_enabled

    async def attest_runtime_handle_lifecycle(
        self, request: WorkflowProtectedRuntimeHandleLifecycleAttestationRequest
    ) -> WorkflowProtectedRuntimeHandleLifecycleAttestation:
        if not self._development_enabled:
            _raise("workflow_protected_runtime_handle_lifecycle_development_attestor_disabled")
        now = self._clock()
        if now.tzinfo is None:
            _raise("workflow_protected_runtime_handle_lifecycle_clock_must_be_aware")
        self.calls.append(request)
        policy = code_owned_workflow_protected_runtime_context_injection_authorization_policy()
        values: dict[str, object] = {
            **{
                field.name: getattr(request, field.name)
                for field in fields(request)
                if field.name != "requested_at"
            },
            "attestation_id": (
                f"protected-runtime-handle-lifecycle.{request.request_nonce_digest[:24]}"
            ),
            "attestor_id": policy.required_attestor_id,
            "attestor_version": policy.required_attestor_version,
            "signing_key_id": policy.verification_signing_key_id,
            "signature_algorithm": "hmac-sha256",
            "observed_at": now,
            "valid_until": min(
                request.protected_runtime_handle_usable_until,
                now + timedelta(seconds=2),
            ),
            "runtime_handle_present": self._runtime_handle_present,
            "runtime_handle_is_bearer_capability": False,
            "runtime_handle_unexpired": now < request.protected_runtime_handle_usable_until,
            "runtime_handle_unrevoked": not self._runtime_handle_revoked,
            "runtime_handle_undestroyed": not self._runtime_handle_destroyed,
            "runtime_handle_uninjected": not self._runtime_handle_injected,
            "runtime_handle_unused": not self._runtime_handle_used,
            "destination_generation_current": self._destination_generation_current,
            "destination_fence_current": self._destination_fence_current,
            "injector_profile_eligible": self._injector_profile_eligible,
            "runtime_slot_profile_eligible": self._runtime_slot_profile_eligible,
            "raw_context_included": False,
            "runtime_handle_material_included": False,
            "runtime_payload_included": False,
            "runtime_handle_locator_included": False,
            "endpoint_included": False,
            "credential_included": False,
            "secret_included": False,
            "bearer_token_included": False,
            "provider_payload_included": False,
            "handle_lookup_authorized": False,
            "handle_retrieval_authorized": False,
            "handle_use_authorized": False,
            "runtime_use_authorized": False,
            "runtime_context_injection_authorized": False,
            "injection_consumption_outstanding": self._injection_consumption_outstanding,
            "connector_activity_authorized": False,
            "network_activity_authorized": False,
            "readiness_probe_authorized": False,
            "publication_authorized": False,
            "delivery_authorized": False,
            "dispatch_authorized": False,
            "execution_authorized": False,
            "infrastructure_mutation_authorized": False,
        }
        values["integrity_signature"] = _sign(_payload(values))
        return WorkflowProtectedRuntimeHandleLifecycleAttestation(
            **cast(Any, values),
            canonical_digest=canonical_digest(_payload(values)),
        )

    def verify_runtime_handle_lifecycle_attestation(
        self, attestation: WorkflowProtectedRuntimeHandleLifecycleAttestation
    ) -> bool:
        if (
            not self._development_enabled
            or attestation.signature_algorithm != "hmac-sha256"
            or attestation.canonical_digest != canonical_digest(attestation.digest_payload())
        ):
            return False
        expected = _sign(attestation.signature_payload())
        return hmac.compare_digest(expected, attestation.integrity_signature)


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


def _sign(payload: dict[str, object]) -> str:
    return hmac.new(
        _DEVELOPMENT_ATTESTATION_KEY,
        canonical_json_bytes(payload),
        sha256,
    ).hexdigest()


def _raise(code: str) -> NoReturn:
    raise WorkflowProtectedRuntimeContextInjectionAuthorizationError(
        code,
        "Protected runtime-handle lifecycle attestation is unavailable.",
    )


__all__ = [
    "DeterministicDevelopmentWorkflowProtectedRuntimeHandleLifecycleAttestor",
    "UnavailableWorkflowProtectedRuntimeHandleLifecycleAttestor",
]
