from __future__ import annotations

import hmac
from collections.abc import Callable
from dataclasses import fields
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, NoReturn, cast

from atlas.modules.workflows.application import (
    protected_runtime_process_scheduling_authorization_ports as scheduling_ports,
)
from atlas.modules.workflows.domain import (
    protected_runtime_process_scheduling_authorization_domain as scheduling_domain,
)
from atlas.modules.workflows.domain.models import canonical_digest, canonical_json_bytes

AuthorizationError = scheduling_ports.WorkflowProtectedRuntimeProcessSchedulingAuthorizationError
StateAttestation = scheduling_ports.WorkflowProtectedRuntimeProcessSchedulingStateAttestation
StateAttestationRequest = (
    scheduling_ports.WorkflowProtectedRuntimeProcessSchedulingStateAttestationRequest
)
code_owned_policy = (
    scheduling_domain.code_owned_workflow_protected_runtime_process_scheduling_authorization_policy
)

_DEVELOPMENT_ATTESTATION_KEY = (
    b"atlas-development-only-protected-runtime-process-scheduling-state-attestation-v1"
)
_ATTESTOR_ID = scheduling_ports.WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_ATTESTOR_ID
_ATTESTOR_VERSION = scheduling_ports.WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_ATTESTOR_VERSION
_SIGNING_KEY_ID = (
    scheduling_ports.WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_ATTESTATION_SIGNING_KEY_ID
)


class UnavailableWorkflowProtectedRuntimeProcessSchedulingStateAttestor:
    @property
    def available(self) -> bool:
        return False

    async def attest_runtime_process_scheduling_state(
        self,
        request: StateAttestationRequest,
    ) -> StateAttestation:
        del request
        _raise("workflow_protected_runtime_process_scheduling_state_attestor_unavailable")

    def verify_runtime_process_scheduling_state_attestation(
        self,
        attestation: StateAttestation,
    ) -> bool:
        del attestation
        return False


class DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingStateAttestor:
    """Development-only signed metadata for one still-suspended protected process."""

    def __init__(
        self,
        *,
        development_enabled: bool = False,
        clock: Callable[[], datetime] | None = None,
        process_created: bool = True,
        process_sealed: bool = True,
        process_suspended: bool = True,
        process_scheduled: bool = False,
        process_resumed: bool = False,
        process_dispatched: bool = False,
        process_executed: bool = False,
        runtime_envelope_current: bool = True,
        destination_generation_current: bool = True,
        destination_fence_current: bool = True,
        protected_slot_generation_current: bool = True,
        prior_scheduling_claim_absent: bool = True,
        prior_scheduling_lease_absent: bool = True,
        process_state_eligibility_seconds: int = 2,
    ) -> None:
        if process_state_eligibility_seconds <= 0:
            raise ValueError("process-state eligibility lifetime must be positive")
        self._development_enabled = development_enabled
        self._clock = clock or (lambda: datetime.now(UTC))
        self._process_state_eligibility_seconds = process_state_eligibility_seconds
        self._evidence: dict[str, bool] = {
            "exact_process_creation_result_confirmed": True,
            "terminal_success_confirmed": True,
            "metadata_only_confirmed": True,
            "process_created_confirmed": process_created,
            "process_sealed_confirmed": process_sealed,
            "process_suspended_confirmed": process_suspended,
            "process_not_scheduled_confirmed": not process_scheduled,
            "process_not_resumed_confirmed": not process_resumed,
            "process_not_dispatched_confirmed": not process_dispatched,
            "process_not_executed_confirmed": not process_executed,
            "runtime_envelope_current": runtime_envelope_current,
            "destination_generation_current": destination_generation_current,
            "destination_fence_current": destination_fence_current,
            "protected_slot_generation_current": protected_slot_generation_current,
            "prior_process_scheduling_claim_absent": prior_scheduling_claim_absent,
            "prior_process_scheduling_lease_absent": prior_scheduling_lease_absent,
            "scheduling_performed": process_scheduled,
            "resume_performed": process_resumed,
            "dispatch_performed": process_dispatched,
            "execution_performed": process_executed,
        }
        self.calls: list[StateAttestationRequest] = []

    @property
    def available(self) -> bool:
        return self._development_enabled

    async def attest_runtime_process_scheduling_state(
        self,
        request: StateAttestationRequest,
    ) -> StateAttestation:
        if not self._development_enabled:
            _raise(
                "workflow_protected_runtime_process_scheduling_state_development_attestor_disabled"
            )
        now = self._clock()
        if now.tzinfo is None:
            _raise("workflow_protected_runtime_process_scheduling_state_clock_must_be_aware")

        policy = code_owned_policy()
        eligibility_ceiling = now + timedelta(seconds=self._process_state_eligibility_seconds)
        valid_until = min(
            eligibility_ceiling,
            now + timedelta(seconds=policy.maximum_attestation_freshness_seconds),
        )
        if valid_until <= now:
            _raise("workflow_protected_runtime_process_scheduling_state_ceiling_expired")

        values: dict[str, object] = {
            field.name: getattr(request, field.name)
            for field in fields(request)
            if field.name != "requested_at"
        }
        values.update(
            {
                "attestation_id": (
                    "protected-runtime-process-scheduling-state."
                    f"{request.request_nonce_digest[:24]}"
                ),
                "attestor_id": _ATTESTOR_ID,
                "attestor_version": _ATTESTOR_VERSION,
                "signing_key_id": _SIGNING_KEY_ID,
                "signature_algorithm": "hmac-sha256",
                "observed_at": now,
                "valid_until": valid_until,
                "process_state_eligible_until": eligibility_ceiling,
            }
        )
        for field in fields(StateAttestation):
            name = field.name
            if name in values or name in {"integrity_signature", "canonical_digest"}:
                continue
            if name in self._evidence:
                values[name] = self._evidence[name]
            elif name.endswith(("_included", "_performed")):
                values[name] = False
            else:
                _raise("workflow_protected_runtime_process_scheduling_state_contract_unsupported")

        values["integrity_signature"] = _sign(_payload(values))
        attestation = StateAttestation(
            **cast(Any, values),
            canonical_digest=canonical_digest(_payload(values)),
        )
        self.calls.append(request)
        return attestation

    def verify_runtime_process_scheduling_state_attestation(
        self,
        attestation: StateAttestation,
    ) -> bool:
        if not isinstance(attestation, StateAttestation):
            return False
        if (
            not self._development_enabled
            or attestation.signature_algorithm != "hmac-sha256"
            or attestation.attestor_id != _ATTESTOR_ID
            or attestation.attestor_version != _ATTESTOR_VERSION
            or attestation.signing_key_id != _SIGNING_KEY_ID
            or attestation.canonical_digest != canonical_digest(attestation.digest_payload())
        ):
            return False
        return hmac.compare_digest(
            _sign(attestation.signature_payload()),
            attestation.integrity_signature,
        )


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
    raise AuthorizationError(
        code,
        "Protected runtime process-scheduling state attestation is unavailable.",
    )


__all__ = [
    "DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingStateAttestor",
    "UnavailableWorkflowProtectedRuntimeProcessSchedulingStateAttestor",
]
