from __future__ import annotations

import hmac
from collections.abc import Callable
from dataclasses import fields
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any, NoReturn, cast

from atlas.modules.workflows.application import (
    protected_runtime_process_creation_authorization_ports as process_creation_ports,
)
from atlas.modules.workflows.domain import (
    protected_runtime_process_creation_authorization_domain as process_creation_domain,
)
from atlas.modules.workflows.domain.models import canonical_digest, canonical_json_bytes

AuthorizationError = (
    process_creation_ports.WorkflowProtectedRuntimeProcessCreationAuthorizationError
)
LifecycleAttestation = (
    process_creation_ports.WorkflowProtectedRuntimeProcessCreationLifecycleAttestation
)
LifecycleRequest = (
    process_creation_ports.WorkflowProtectedRuntimeProcessCreationLifecycleAttestationRequest
)
code_owned_policy = process_creation_domain.code_owned_workflow_protected_runtime_process_creation_authorization_policy  # noqa: E501

_DEVELOPMENT_ATTESTATION_KEY = (
    b"atlas-development-only-protected-runtime-process-creation-lifecycle-attestation-v1"
)
_ATTESTOR_ID = "attestor.workflow-protected-runtime-process-creation-lifecycle"
_ATTESTOR_VERSION = "1.0"
_SIGNING_KEY_ID = "key.workflow-protected-runtime-process-creation-lifecycle.v1"


class UnavailableWorkflowProtectedRuntimeProcessCreationLifecycleAttestor:
    @property
    def available(self) -> bool:
        return False

    async def attest_runtime_process_creation_lifecycle(
        self,
        request: LifecycleRequest,
    ) -> LifecycleAttestation:
        del request
        _raise("workflow_protected_runtime_process_creation_lifecycle_attestor_unavailable")

    def verify_runtime_process_creation_lifecycle_attestation(
        self,
        attestation: LifecycleAttestation,
    ) -> bool:
        del attestation
        return False


class DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationLifecycleAttestor:
    """Development-only signed process-creation eligibility evidence with zero I/O."""

    def __init__(
        self,
        *,
        development_enabled: bool = False,
        clock: Callable[[], datetime] | None = None,
        runtime_started: bool = True,
        runtime_ready: bool = True,
        runtime_envelope_current: bool = True,
        destination_generation_current: bool = True,
        destination_fence_current: bool = True,
        runtime_slot_generation_current: bool = True,
        process_creation_absent: bool = True,
        scheduling_absent: bool = True,
        competing_process_creation_authorization_absent: bool = True,
        competing_process_creation_attempt_absent: bool = True,
        process_creation_profile_eligible: bool = True,
        runtime_envelope_eligibility_seconds: int = 2,
    ) -> None:
        if runtime_envelope_eligibility_seconds <= 0:
            raise ValueError("runtime envelope eligibility lifetime must be positive")
        self._development_enabled = development_enabled
        self._clock = clock or (lambda: datetime.now(UTC))
        self._runtime_envelope_eligibility_seconds = runtime_envelope_eligibility_seconds
        self._evidence: dict[str, bool] = {
            "exact_readiness_result_confirmed": True,
            "exact_runtime_readiness_result_confirmed": True,
            "runtime_started_confirmed": runtime_started,
            "runtime_envelope_started": runtime_started,
            "runtime_started": runtime_started,
            "runtime_ready_confirmed": runtime_ready,
            "readiness_assessment_confirmed": runtime_ready,
            "runtime_envelope_ready": runtime_ready,
            "runtime_ready": runtime_ready,
            "runtime_envelope_current": runtime_envelope_current,
            "destination_generation_current": destination_generation_current,
            "destination_fence_current": destination_fence_current,
            "protected_slot_generation_current": runtime_slot_generation_current,
            "runtime_slot_generation_current": runtime_slot_generation_current,
            "generic_process_created": not process_creation_absent,
            "process_creation_absent": process_creation_absent,
            "process_absent": process_creation_absent,
            "process_not_created": process_creation_absent,
            "scheduling_absent": scheduling_absent,
            "process_not_scheduled": scheduling_absent,
            "scheduling_performed": not scheduling_absent,
            "competing_process_creation_authorization_absent": (
                competing_process_creation_authorization_absent
            ),
            "prior_process_creation_authorization_absent": (
                competing_process_creation_authorization_absent
            ),
            "competing_process_creation_attempt_absent": (
                competing_process_creation_attempt_absent
            ),
            "prior_process_creation_attempt_absent": competing_process_creation_attempt_absent,
            "prior_process_creation_claim_absent": (
                competing_process_creation_authorization_absent
            ),
            "prior_process_creation_lease_absent": competing_process_creation_attempt_absent,
            "process_creation_profile_eligible": process_creation_profile_eligible,
        }
        self.calls: list[LifecycleRequest] = []

    @property
    def available(self) -> bool:
        return self._development_enabled

    async def attest_runtime_process_creation_lifecycle(
        self,
        request: LifecycleRequest,
    ) -> LifecycleAttestation:
        if not self._development_enabled:
            _raise(
                "workflow_protected_runtime_process_creation_lifecycle_"
                "development_attestor_disabled"
            )
        now = self._clock()
        if now.tzinfo is None:
            _raise("workflow_protected_runtime_process_creation_lifecycle_clock_must_be_aware")
        ceiling = min(
            _eligibility_ceiling(request, now=now),
            now + timedelta(seconds=self._runtime_envelope_eligibility_seconds),
        )
        if ceiling <= now:
            _raise("workflow_protected_runtime_process_creation_lifecycle_ceiling_expired")

        policy = code_owned_policy()
        values: dict[str, object] = {
            field.name: getattr(request, field.name)
            for field in fields(request)
            if field.name != "requested_at"
        }
        values.update(
            {
                "attestation_id": (
                    "protected-runtime-process-creation-lifecycle."
                    f"{request.request_nonce_digest[:24]}"
                ),
                "attestor_id": _ATTESTOR_ID,
                "attestor_version": _ATTESTOR_VERSION,
                "signing_key_id": _SIGNING_KEY_ID,
                "signature_algorithm": "hmac-sha256",
            }
        )
        for field in fields(LifecycleAttestation):
            name = field.name
            if name in values or name in {"integrity_signature", "canonical_digest"}:
                continue
            values[name] = self._attestation_value(
                name,
                policy=policy,
                observed_at=now,
                valid_until=min(
                    now + timedelta(seconds=policy.maximum_attestation_freshness_seconds),
                    ceiling,
                ),
                eligibility_ceiling=ceiling,
            )

        values["integrity_signature"] = _sign(_payload(values))
        attestation = LifecycleAttestation(
            **cast(Any, values),
            canonical_digest=canonical_digest(_payload(values)),
        )
        self.calls.append(request)
        return attestation

    def verify_runtime_process_creation_lifecycle_attestation(
        self,
        attestation: LifecycleAttestation,
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

    def _attestation_value(
        self,
        name: str,
        *,
        policy: object,
        observed_at: datetime,
        valid_until: datetime,
        eligibility_ceiling: datetime,
    ) -> object:
        if name in self._evidence:
            return self._evidence[name]
        if name in {"observed_at", "issued_at"}:
            return observed_at
        if name in {"valid_until", "expires_at"}:
            return valid_until
        if name in {
            "runtime_envelope_eligible_until",
            "runtime_process_creation_eligible_until",
            "process_creation_eligible_until",
        }:
            return eligibility_ceiling
        policy_value = getattr(policy, name, None)
        if policy_value is not None:
            return policy_value
        if name.endswith(("_included", "_authorized", "_authority_granted", "_performed")):
            return False
        if name.endswith(("_returned", "_revealed", "_present")):
            return False
        if name.endswith("_absent"):
            return True
        if name.endswith(("_current", "_confirmed", "_eligible")):
            return True
        if name in {
            "runtime_resumed",
            "runtime_stopped",
            "runtime_restarted",
            "generic_process_created",
            "process_created",
            "process_scheduled",
            "scheduling_performed",
        }:
            return False
        _raise("workflow_protected_runtime_process_creation_lifecycle_contract_unsupported")


def _eligibility_ceiling(
    request: LifecycleRequest,
    *,
    now: datetime,
) -> datetime:
    ceilings = [
        cast(datetime, getattr(request, field.name))
        for field in fields(request)
        if field.name.endswith(("_usable_until", "_eligible_until", "_valid_until"))
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
    raise AuthorizationError(
        code,
        "Protected runtime process-creation lifecycle attestation is unavailable.",
    )


__all__ = [
    "DeterministicDevelopmentWorkflowProtectedRuntimeProcessCreationLifecycleAttestor",
    "UnavailableWorkflowProtectedRuntimeProcessCreationLifecycleAttestor",
]
