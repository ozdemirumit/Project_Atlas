from __future__ import annotations

import hmac
from collections.abc import Callable
from dataclasses import fields
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, NoReturn, cast

from atlas.modules.workflows.application.protected_runtime_context_use_authorization_ports import (
    WorkflowProtectedRuntimeContextUseAuthorizationError,
    WorkflowProtectedRuntimeSlotLifecycleAttestation,
    WorkflowProtectedRuntimeSlotLifecycleAttestationRequest,
)
from atlas.modules.workflows.domain.models import (
    canonical_digest,
    canonical_json_bytes,
)
from atlas.modules.workflows.domain.protected_runtime_context_use_authorization_domain import (
    code_owned_workflow_protected_runtime_context_use_authorization_policy,
)

_DEVELOPMENT_ATTESTATION_KEY = (
    b"atlas-development-only-protected-runtime-slot-lifecycle-attestation-v1"
)


class UnavailableWorkflowProtectedRuntimeSlotLifecycleAttestor:
    @property
    def available(self) -> bool:
        return False

    async def attest_runtime_slot_lifecycle(
        self, request: WorkflowProtectedRuntimeSlotLifecycleAttestationRequest
    ) -> WorkflowProtectedRuntimeSlotLifecycleAttestation:
        del request
        _raise("workflow_protected_runtime_slot_lifecycle_attestor_unavailable")

    def verify_runtime_slot_lifecycle_attestation(
        self, attestation: WorkflowProtectedRuntimeSlotLifecycleAttestation
    ) -> bool:
        del attestation
        return False


class DeterministicDevelopmentWorkflowProtectedRuntimeSlotLifecycleAttestor:
    """Development-only signed passive evidence; it performs no protected-slot I/O."""

    def __init__(
        self,
        *,
        development_enabled: bool = False,
        clock: Callable[[], datetime] | None = None,
        exact_runtime_slot_confirmed: bool = True,
        inert_context_present: bool = True,
        runtime_slot_inert: bool = True,
        runtime_slot_used: bool = False,
        runtime_slot_revoked: bool = False,
        destination_generation_current: bool = True,
        destination_fence_current: bool = True,
        use_profile_eligible: bool = True,
    ) -> None:
        self._development_enabled = development_enabled
        self._clock = clock or (lambda: datetime.now(UTC))
        self._exact_runtime_slot_confirmed = exact_runtime_slot_confirmed
        self._inert_context_present = inert_context_present
        self._runtime_slot_inert = runtime_slot_inert
        self._runtime_slot_used = runtime_slot_used
        self._runtime_slot_revoked = runtime_slot_revoked
        self._destination_generation_current = destination_generation_current
        self._destination_fence_current = destination_fence_current
        self._use_profile_eligible = use_profile_eligible
        self.calls: list[WorkflowProtectedRuntimeSlotLifecycleAttestationRequest] = []

    @property
    def available(self) -> bool:
        return self._development_enabled

    async def attest_runtime_slot_lifecycle(
        self, request: WorkflowProtectedRuntimeSlotLifecycleAttestationRequest
    ) -> WorkflowProtectedRuntimeSlotLifecycleAttestation:
        if not self._development_enabled:
            _raise("workflow_protected_runtime_slot_lifecycle_development_attestor_disabled")
        now = self._clock()
        if now.tzinfo is None:
            _raise("workflow_protected_runtime_slot_lifecycle_clock_must_be_aware")
        if (
            request.injected_context_usable_until.tzinfo is None
            or request.injected_context_usable_until <= now
        ):
            _raise("workflow_protected_runtime_slot_lifecycle_ceiling_expired")
        self.calls.append(request)
        policy = code_owned_workflow_protected_runtime_context_use_authorization_policy()
        values: dict[str, object] = {
            **{
                field.name: getattr(request, field.name)
                for field in fields(request)
                if field.name != "requested_at"
            },
            "attestation_id": (
                f"protected-runtime-slot-lifecycle.{request.request_nonce_digest[:24]}"
            ),
            "attestor_id": policy.required_attestor_id,
            "attestor_version": policy.required_attestor_version,
            "signing_key_id": policy.verification_signing_key_id,
            "signature_algorithm": "hmac-sha256",
            "observed_at": now,
            "valid_until": min(
                now + timedelta(seconds=2),
                request.injected_context_usable_until,
            ),
            "exact_runtime_slot_confirmed": self._exact_runtime_slot_confirmed,
            "inert_context_present": self._inert_context_present,
            "runtime_slot_inert": self._runtime_slot_inert,
            "runtime_slot_unused": not self._runtime_slot_used,
            "runtime_slot_unrevoked": not self._runtime_slot_revoked,
            "destination_generation_current": self._destination_generation_current,
            "destination_fence_current": self._destination_fence_current,
            "use_profile_eligible": self._use_profile_eligible,
            "raw_context_included": False,
            "runtime_payload_included": False,
            "runtime_slot_locator_included": False,
            "endpoint_included": False,
            "credential_included": False,
            "secret_included": False,
            "bearer_token_included": False,
            "runtime_use_authorized": False,
            "runtime_start_authorized": False,
            "runtime_resume_authorized": False,
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
        return WorkflowProtectedRuntimeSlotLifecycleAttestation(
            **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
        )

    def verify_runtime_slot_lifecycle_attestation(
        self, attestation: WorkflowProtectedRuntimeSlotLifecycleAttestation
    ) -> bool:
        if (
            not self._development_enabled
            or attestation.signature_algorithm != "hmac-sha256"
            or attestation.canonical_digest != canonical_digest(attestation.digest_payload())
        ):
            return False
        return hmac.compare_digest(
            _sign(attestation.signature_payload()), attestation.integrity_signature
        )


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
    raise WorkflowProtectedRuntimeContextUseAuthorizationError(
        code,
        "Protected runtime-slot lifecycle attestation is unavailable.",
    )


__all__ = [
    "DeterministicDevelopmentWorkflowProtectedRuntimeSlotLifecycleAttestor",
    "UnavailableWorkflowProtectedRuntimeSlotLifecycleAttestor",
]
