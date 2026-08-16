from __future__ import annotations

import hmac
from collections.abc import Callable
from dataclasses import fields
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, NoReturn, cast

from atlas.modules.workflows.application.protected_resident_context_access_authorization_ports import (  # noqa: E501
    WorkflowProtectedResidentContextAccessAuthorizationError,
    WorkflowProtectedResidentContextLifecycleAttestation,
    WorkflowProtectedResidentContextLifecycleAttestationRequest,
)
from atlas.modules.workflows.domain import (
    canonical_digest,
    canonical_json_bytes,
    code_owned_workflow_protected_resident_context_access_authorization_policy,
)

_DEVELOPMENT_ATTESTATION_KEY = (
    b"atlas-development-only-protected-resident-context-lifecycle-attestation-v1"
)


class UnavailableWorkflowProtectedResidentContextLifecycleAttestor:
    @property
    def available(self) -> bool:
        return False

    async def attest_resident_context_lifecycle(
        self, request: WorkflowProtectedResidentContextLifecycleAttestationRequest
    ) -> WorkflowProtectedResidentContextLifecycleAttestation:
        del request
        _raise("workflow_protected_resident_context_lifecycle_attestor_unavailable")


class DenyAllWorkflowProtectedResidentContextLifecycleSignatureVerifier:
    def verify_lifecycle_attestation(
        self, attestation: WorkflowProtectedResidentContextLifecycleAttestation
    ) -> bool:
        del attestation
        return False


class DeterministicDevelopmentWorkflowProtectedResidentContextLifecycleAttestor:
    """Explicitly enabled development attestor that emits signed metadata and performs no I/O."""

    def __init__(
        self,
        *,
        development_enabled: bool = False,
        clock: Callable[[], datetime] | None = None,
        resident_context_present: bool = True,
        resident_context_revoked: bool = False,
        resident_context_destroyed: bool = False,
        resident_context_consumed: bool = False,
        access_handle_outstanding: bool = False,
    ) -> None:
        self._development_enabled = development_enabled
        self._clock = clock or (lambda: datetime.now(UTC))
        self._resident_context_present = resident_context_present
        self._resident_context_revoked = resident_context_revoked
        self._resident_context_destroyed = resident_context_destroyed
        self._resident_context_consumed = resident_context_consumed
        self._access_handle_outstanding = access_handle_outstanding
        self.calls: list[WorkflowProtectedResidentContextLifecycleAttestationRequest] = []

    @property
    def available(self) -> bool:
        return self._development_enabled

    async def attest_resident_context_lifecycle(
        self, request: WorkflowProtectedResidentContextLifecycleAttestationRequest
    ) -> WorkflowProtectedResidentContextLifecycleAttestation:
        if not self._development_enabled:
            _raise("workflow_protected_resident_context_lifecycle_development_attestor_disabled")
        now = self._clock()
        if now.tzinfo is None:
            _raise("workflow_protected_resident_context_lifecycle_clock_must_be_aware")
        self.calls.append(request)
        policy = code_owned_workflow_protected_resident_context_access_authorization_policy()
        values: dict[str, object] = {
            **{
                field.name: getattr(request, field.name)
                for field in fields(request)
                if field.name != "requested_at"
            },
            "attestation_id": (
                f"protected-resident-context-lifecycle.{request.request_nonce_digest[:24]}"
            ),
            "attestor_id": policy.required_attestor_id,
            "attestor_version": policy.required_attestor_version,
            "signing_key_id": policy.verification_signing_key_id,
            "signature_algorithm": "hmac-sha256",
            "observed_at": now,
            "valid_until": min(
                request.protected_resident_context_usable_until,
                now + timedelta(seconds=2),
            ),
            "resident_context_present": self._resident_context_present,
            "resident_context_is_bearer_capability": False,
            "resident_context_unexpired": (now < request.protected_resident_context_usable_until),
            "resident_context_unrevoked": not self._resident_context_revoked,
            "resident_context_undestroyed": not self._resident_context_destroyed,
            "resident_context_unconsumed": not self._resident_context_consumed,
            "resident_context_handle_outstanding": self._access_handle_outstanding,
            "raw_context_included": False,
            "endpoint_included": False,
            "credential_included": False,
            "secret_included": False,
            "bearer_token_included": False,
            "locator_included": False,
            "provider_payload_included": False,
            "runtime_handle_creation_authorized": False,
            "network_activity_authorized": False,
            "execution_authorized": False,
            "infrastructure_mutation_authorized": False,
        }
        values["integrity_signature"] = _sign(_payload(values))
        return WorkflowProtectedResidentContextLifecycleAttestation(
            **cast(Any, values),
            canonical_digest=canonical_digest(_payload(values)),
        )

    def verify_lifecycle_attestation(
        self, attestation: WorkflowProtectedResidentContextLifecycleAttestation
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
    raise WorkflowProtectedResidentContextAccessAuthorizationError(
        code, "Protected resident-context lifecycle attestation is unavailable."
    )


__all__ = [
    "DenyAllWorkflowProtectedResidentContextLifecycleSignatureVerifier",
    "DeterministicDevelopmentWorkflowProtectedResidentContextLifecycleAttestor",
    "UnavailableWorkflowProtectedResidentContextLifecycleAttestor",
]
