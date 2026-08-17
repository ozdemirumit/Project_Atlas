from __future__ import annotations

import hmac
from collections.abc import Callable
from dataclasses import fields
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, NoReturn, cast

from atlas.modules.workflows.application.protected_runtime_start_authorization_ports import (
    WorkflowProtectedRuntimeStartAuthorizationError,
    WorkflowProtectedRuntimeStartLifecycleAttestation,
    WorkflowProtectedRuntimeStartLifecycleAttestationRequest,
)
from atlas.modules.workflows.domain.models import canonical_digest, canonical_json_bytes
from atlas.modules.workflows.domain.protected_runtime_start_authorization_domain import (
    code_owned_workflow_protected_runtime_start_authorization_policy,
)

_DEVELOPMENT_ATTESTATION_KEY = (
    b"atlas-development-only-protected-runtime-start-lifecycle-attestation-v1"
)


class UnavailableWorkflowProtectedRuntimeStartLifecycleAttestor:
    @property
    def available(self) -> bool:
        return False

    async def attest_runtime_start_lifecycle(
        self, request: WorkflowProtectedRuntimeStartLifecycleAttestationRequest
    ) -> WorkflowProtectedRuntimeStartLifecycleAttestation:
        del request
        _raise("workflow_protected_runtime_start_lifecycle_attestor_unavailable")

    def verify_runtime_start_lifecycle_attestation(
        self, attestation: WorkflowProtectedRuntimeStartLifecycleAttestation
    ) -> bool:
        del attestation
        return False


class DeterministicDevelopmentWorkflowProtectedRuntimeStartLifecycleAttestor:
    """Development-only signed metadata evidence with no protected runtime I/O."""

    def __init__(
        self,
        *,
        development_enabled: bool = False,
        clock: Callable[[], datetime] | None = None,
        adopted_context_terminal: bool = True,
        adopted_context_non_reusable: bool = True,
        runtime_envelope_inactive: bool = True,
        runtime_envelope_unstarted: bool = True,
        runtime_envelope_unresumed: bool = True,
        runtime_start_attempt_absent: bool = True,
        process_creation_absent: bool = True,
        scheduling_absent: bool = True,
        competing_authorization_absent: bool = True,
        competing_consumption_absent: bool = True,
        destination_generation_current: bool = True,
        destination_fence_current: bool = True,
        runtime_slot_generation_current: bool = True,
        runtime_start_profile_eligible: bool = True,
    ) -> None:
        self._development_enabled = development_enabled
        self._clock = clock or (lambda: datetime.now(UTC))
        self._evidence = {
            "exact_use_result_confirmed": True,
            "context_adoption_confirmed": True,
            "context_terminal_non_reusable": (
                adopted_context_terminal and adopted_context_non_reusable
            ),
            "adopted_context_terminal": adopted_context_terminal,
            "context_used_terminal": adopted_context_terminal,
            "adopted_context_non_reusable": adopted_context_non_reusable,
            "context_non_reusable": adopted_context_non_reusable,
            "runtime_envelope_inactive": runtime_envelope_inactive,
            "runtime_envelope_current": True,
            "runtime_envelope_unstarted": runtime_envelope_unstarted,
            "runtime_unstarted": runtime_envelope_unstarted,
            "runtime_not_started": runtime_envelope_unstarted,
            "runtime_envelope_unresumed": runtime_envelope_unresumed,
            "runtime_unresumed": runtime_envelope_unresumed,
            "runtime_not_resumed": runtime_envelope_unresumed,
            "runtime_start_attempt_absent": runtime_start_attempt_absent,
            "process_creation_absent": process_creation_absent,
            "process_absent": process_creation_absent,
            "process_not_created": process_creation_absent,
            "scheduling_absent": scheduling_absent,
            "scheduled_process_absent": scheduling_absent,
            "competing_runtime_start_authorization_absent": competing_authorization_absent,
            "competing_authorization_absent": competing_authorization_absent,
            "competing_runtime_start_consumption_absent": competing_consumption_absent,
            "competing_consumption_absent": competing_consumption_absent,
            "destination_generation_current": destination_generation_current,
            "destination_fence_current": destination_fence_current,
            "runtime_slot_generation_current": runtime_slot_generation_current,
            "runtime_start_profile_eligible": runtime_start_profile_eligible,
        }
        self.calls: list[WorkflowProtectedRuntimeStartLifecycleAttestationRequest] = []

    @property
    def available(self) -> bool:
        return self._development_enabled

    async def attest_runtime_start_lifecycle(
        self, request: WorkflowProtectedRuntimeStartLifecycleAttestationRequest
    ) -> WorkflowProtectedRuntimeStartLifecycleAttestation:
        if not self._development_enabled:
            _raise("workflow_protected_runtime_start_lifecycle_development_attestor_disabled")
        now = self._clock()
        if now.tzinfo is None:
            _raise("workflow_protected_runtime_start_lifecycle_clock_must_be_aware")
        ceiling = _eligibility_ceiling(request, now=now)
        if ceiling <= now:
            _raise("workflow_protected_runtime_start_lifecycle_ceiling_expired")

        policy = code_owned_workflow_protected_runtime_start_authorization_policy()
        values: dict[str, object] = {
            field.name: getattr(request, field.name)
            for field in fields(request)
            if field.name != "requested_at"
        }
        values.update(
            {
                "attestation_id": (
                    f"protected-runtime-start-lifecycle.{request.request_nonce_digest[:24]}"
                ),
                "attestor_id": policy.required_attestor_id,
                "attestor_version": policy.required_attestor_version,
                "signing_key_id": policy.verification_signing_key_id,
                "signature_algorithm": "hmac-sha256",
                "observed_at": now,
                "valid_until": min(now + timedelta(seconds=2), ceiling),
            }
        )
        for field in fields(WorkflowProtectedRuntimeStartLifecycleAttestation):
            if field.name in values or field.name in {"integrity_signature", "canonical_digest"}:
                continue
            values[field.name] = self._attestation_flag(field.name)

        values["integrity_signature"] = _sign(_payload(values))
        attestation = WorkflowProtectedRuntimeStartLifecycleAttestation(
            **cast(Any, values),
            canonical_digest=canonical_digest(_payload(values)),
        )
        self.calls.append(request)
        return attestation

    def verify_runtime_start_lifecycle_attestation(
        self, attestation: WorkflowProtectedRuntimeStartLifecycleAttestation
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

    def _attestation_flag(self, name: str) -> bool | int:
        if name in self._evidence:
            return self._evidence[name]
        if name in {"context_use_count", "use_count"}:
            return 1
        if name in {
            "exact_context_use_result_confirmed",
            "exact_runtime_slot_confirmed",
            "exact_runtime_envelope_confirmed",
            "context_use_succeeded",
            "context_adopted_once",
        }:
            return True
        if (
            name.endswith("_included")
            or name.endswith("_authorized")
            or name.endswith("_authority_granted")
            or name
            in {
                "runtime_started",
                "runtime_resumed",
                "process_created",
                "process_scheduled",
                "runtime_start_attempt_pending",
                "runtime_start_attempt_terminal",
            }
        ):
            return False
        _raise("workflow_protected_runtime_start_lifecycle_contract_unsupported")


def _eligibility_ceiling(
    request: WorkflowProtectedRuntimeStartLifecycleAttestationRequest,
    *,
    now: datetime,
) -> datetime:
    ceilings = [
        cast(datetime, getattr(request, field.name))
        for field in fields(request)
        if field.name.endswith(("_usable_until", "_eligible_until"))
        and isinstance(getattr(request, field.name), datetime)
    ]
    return min(ceilings, default=now + timedelta(seconds=2))


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


def _sign(payload: dict[str, object]) -> str:
    return hmac.new(
        _DEVELOPMENT_ATTESTATION_KEY,
        canonical_json_bytes(payload),
        sha256,
    ).hexdigest()


def _raise(code: str) -> NoReturn:
    raise WorkflowProtectedRuntimeStartAuthorizationError(
        code,
        "Protected runtime-start lifecycle attestation is unavailable.",
    )


__all__ = [
    "DeterministicDevelopmentWorkflowProtectedRuntimeStartLifecycleAttestor",
    "UnavailableWorkflowProtectedRuntimeStartLifecycleAttestor",
]
