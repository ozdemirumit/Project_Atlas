from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, cast

from .models import WorkflowScope, canonical_digest
from .protected_runtime_context_injection_consumption_domain import (
    WorkflowProtectedRuntimeContextInjectionConsumptionResultState,
    code_owned_workflow_protected_runtime_context_injection_consumption_policy,
)


class WorkflowProtectedRuntimeContextUseAuthorizationLeaseState(StrEnum):
    AUTHORIZED_UNCONSUMED = "authorized_unconsumed"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseAuthorizationAuthority:
    """A narrow lease declaration, never permission to use or execute runtime context."""

    endpoint_resolution_authorized: bool = False
    route_selection_authorized: bool = False
    route_binding_authorized: bool = False
    credential_selection_authorized: bool = False
    credential_assignment_binding_authorized: bool = False
    credential_access_authorized: bool = False
    credential_brokerage_authorized: bool = False
    credential_resolution_authorized: bool = False
    protected_artifact_access_authorized: bool = False
    credential_delivery_authorized: bool = False
    network_access_authorized: bool = False
    readiness_probe_authorized: bool = False
    publication_authorized: bool = False
    delivery_authorized: bool = False
    dispatch_authorized: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_authorized: bool = False
    target_context_capsule_handoff_authorized: bool = False
    target_context_capsule_opening_authorized: bool = False
    protected_resident_context_access_authority_granted: bool = False
    protected_runtime_context_injection_authority_granted: bool = False
    runtime_use_authorized: bool = False
    runtime_start_authorized: bool = False
    runtime_resume_authorized: bool = False
    connector_activity_authorized: bool = False
    protected_runtime_context_use_authority_granted: bool = False

    def __post_init__(self) -> None:
        operational = self.canonical_value()
        operational.pop("protected_runtime_context_use_authority_granted")
        if any(operational.values()):
            raise ValueError("runtime context use authorization grants operational authority")

    def canonical_value(self) -> dict[str, bool]:
        return {field.name: cast(bool, getattr(self, field.name)) for field in fields(self)}


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseAuthorizationPolicy:
    policy_id: str
    policy_version: str
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    required_source_state: str
    required_attestor_id: str
    required_attestor_version: str
    verification_signing_key_id: str
    receipt_verification_signing_key_id: str
    runtime_slot_profile_id: str
    runtime_slot_profile_version: str
    runtime_slot_profile_digest: str
    use_profile_id: str
    use_profile_version: str
    use_profile_digest: str
    maximum_lifetime_seconds: int
    single_use_required: bool
    renewable_allowed: bool
    transferable_allowed: bool
    bearer_capability_allowed: bool
    runtime_use_forbidden: bool
    runtime_start_forbidden: bool
    runtime_resume_forbidden: bool
    network_activity_forbidden: bool
    connector_activity_forbidden: bool
    readiness_probe_forbidden: bool
    publication_forbidden: bool
    delivery_forbidden: bool
    dispatch_forbidden: bool
    execution_forbidden: bool
    infrastructure_mutation_forbidden: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        expected = code_owned_workflow_protected_runtime_context_use_authorization_policy_values()
        if any(getattr(self, name) != value for name, value in expected.items()):
            raise ValueError("runtime context use authorization policy is not code-owned")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("runtime context use authorization policy digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


def code_owned_workflow_protected_runtime_context_use_authorization_policy_values() -> dict[
    str, object
]:
    injection = code_owned_workflow_protected_runtime_context_injection_consumption_policy()
    use_profile = {
        "profile_id": "profile.workflow-protected-runtime-context-use",
        "profile_version": "1.0",
        "runtime_slot_profile_digest": injection.runtime_slot_profile_digest,
        "runtime_use_forbidden": True,
    }
    return {
        "policy_id": "policy.workflow-protected-runtime-context-use-authorization",
        "policy_version": "1.0",
        "consumer_subject_id": injection.consumer_subject_id,
        "consumer_audience": injection.consumer_audience,
        "consumer_contract_id": injection.consumer_contract_id,
        "consumer_contract_version": injection.consumer_contract_version,
        "purpose_id": "purpose.workflow-protected-runtime-context-use-evaluation",
        "required_source_state": (
            WorkflowProtectedRuntimeContextInjectionConsumptionResultState.INJECTED_INTO_PROTECTED_RUNTIME_SLOT.value
        ),
        "required_attestor_id": "attestor.workflow-protected-runtime-slot-lifecycle",
        "required_attestor_version": "1.0",
        "verification_signing_key_id": ("key.workflow-protected-runtime-slot-lifecycle.v1"),
        "receipt_verification_signing_key_id": (injection.receipt_verification_signing_key_id),
        "runtime_slot_profile_id": injection.runtime_slot_profile_id,
        "runtime_slot_profile_version": injection.runtime_slot_profile_version,
        "runtime_slot_profile_digest": injection.runtime_slot_profile_digest,
        "use_profile_id": cast(str, use_profile["profile_id"]),
        "use_profile_version": cast(str, use_profile["profile_version"]),
        "use_profile_digest": canonical_digest(use_profile),
        "maximum_lifetime_seconds": 1,
        "single_use_required": True,
        "renewable_allowed": False,
        "transferable_allowed": False,
        "bearer_capability_allowed": False,
        "runtime_use_forbidden": True,
        "runtime_start_forbidden": True,
        "runtime_resume_forbidden": True,
        "network_activity_forbidden": True,
        "connector_activity_forbidden": True,
        "readiness_probe_forbidden": True,
        "publication_forbidden": True,
        "delivery_forbidden": True,
        "dispatch_forbidden": True,
        "execution_forbidden": True,
        "infrastructure_mutation_forbidden": True,
    }


def code_owned_workflow_protected_runtime_context_use_authorization_policy() -> (
    WorkflowProtectedRuntimeContextUseAuthorizationPolicy
):
    values = code_owned_workflow_protected_runtime_context_use_authorization_policy_values()
    return WorkflowProtectedRuntimeContextUseAuthorizationPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseAuthorizationClaim:
    claim_id: str
    injection_result_id: str
    injection_result_digest: str
    injection_id: str
    injection_attempt_id: str
    injection_attempt_digest: str
    injection_consumption_claim_id: str
    injection_consumption_claim_digest: str
    injection_authorization_lease_id: str
    injection_authorization_lease_digest: str
    injector_receipt_digest: str
    injection_result_state: WorkflowProtectedRuntimeContextInjectionConsumptionResultState
    injection_completed_at: datetime
    injection_result_recorded_at: datetime
    injection_deadline: datetime
    inert_context_injected: bool
    runtime_slot_mutation_performed: bool
    protected_runtime_handle_consumed: bool
    injection_outcome_known: bool
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_slot_profile_id: str
    runtime_slot_profile_version: str
    runtime_slot_profile_digest: str
    runtime_slot_commitment: str
    runtime_slot_post_generation: int
    injected_context_usable_until: datetime
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    policy_id: str
    policy_version: str
    policy_digest: str
    request_fingerprint: str
    idempotency_digest: str
    authorization_audit_digest: str
    claimed_at: datetime
    authority: WorkflowProtectedRuntimeContextUseAuthorizationAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        _validate_source_snapshot(self)
        _require_identifiers(self, _CLAIM_IDENTIFIERS)
        _require_digests(self, _CLAIM_DIGESTS)
        if (
            self.claimed_at.tzinfo is None
            or self.claimed_at < self.injection_result_recorded_at
            or self.claimed_at >= self.injected_context_usable_until
            or self.authority.protected_runtime_context_use_authority_granted is not False
        ):
            raise ValueError("runtime context use authorization claim is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseAuthorizationLease:
    authorization_lease_id: str
    claim_id: str
    claim_digest: str
    injection_result_id: str
    injection_result_digest: str
    injection_id: str
    injection_attempt_id: str
    injection_attempt_digest: str
    injection_consumption_claim_id: str
    injection_consumption_claim_digest: str
    injection_authorization_lease_id: str
    injection_authorization_lease_digest: str
    injector_receipt_digest: str
    injection_result_state: WorkflowProtectedRuntimeContextInjectionConsumptionResultState
    injection_completed_at: datetime
    injection_result_recorded_at: datetime
    injection_deadline: datetime
    inert_context_injected: bool
    runtime_slot_mutation_performed: bool
    protected_runtime_handle_consumed: bool
    injection_outcome_known: bool
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_slot_profile_id: str
    runtime_slot_profile_version: str
    runtime_slot_profile_digest: str
    runtime_slot_commitment: str
    runtime_slot_post_generation: int
    injected_context_usable_until: datetime
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    policy_id: str
    policy_version: str
    policy_digest: str
    lifecycle_attestation_id: str
    lifecycle_attestation_digest: str
    lifecycle_attestation_valid_until: datetime
    use_profile_id: str
    use_profile_version: str
    use_profile_digest: str
    issued_at: datetime
    valid_until: datetime
    effective_until: datetime
    single_use: bool
    renewable: bool
    transferable: bool
    lease_is_bearer_capability: bool
    state: WorkflowProtectedRuntimeContextUseAuthorizationLeaseState
    authority: WorkflowProtectedRuntimeContextUseAuthorizationAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_context_use_authorization_policy()
        _validate_source_snapshot(self)
        _require_identifiers(self, _LEASE_IDENTIFIERS)
        _require_digests(self, _LEASE_DIGESTS)
        if (
            any(
                value.tzinfo is None
                for value in (
                    self.lifecycle_attestation_valid_until,
                    self.injected_context_usable_until,
                    self.issued_at,
                    self.valid_until,
                    self.effective_until,
                )
            )
            or not self.injection_result_recorded_at <= self.issued_at < self.valid_until
            or self.valid_until - self.issued_at
            > timedelta(seconds=policy.maximum_lifetime_seconds)
            or self.valid_until > self.effective_until
            or self.effective_until > self.lifecycle_attestation_valid_until
            or self.effective_until > self.injected_context_usable_until
            or self.use_profile_id != policy.use_profile_id
            or self.use_profile_version != policy.use_profile_version
            or self.use_profile_digest != policy.use_profile_digest
            or self.single_use is not policy.single_use_required
            or self.renewable is not policy.renewable_allowed
            or self.transferable is not policy.transferable_allowed
            or self.lease_is_bearer_capability is not policy.bearer_capability_allowed
            or self.state
            is not WorkflowProtectedRuntimeContextUseAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
            or self.authority.protected_runtime_context_use_authority_granted is not True
        ):
            raise ValueError("runtime context use authorization lease is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))

    def is_active(self, *, evaluated_at: datetime, consumed: bool = False) -> bool:
        if evaluated_at.tzinfo is None:
            raise ValueError("runtime context use lease evaluation time must be aware")
        return not consumed and self.issued_at <= evaluated_at < self.valid_until


def _validate_source_snapshot(
    instance: (
        WorkflowProtectedRuntimeContextUseAuthorizationClaim
        | WorkflowProtectedRuntimeContextUseAuthorizationLease
    ),
) -> None:
    policy = code_owned_workflow_protected_runtime_context_use_authorization_policy()
    state = instance.injection_result_state
    authority = instance.authority
    if (
        state.value != policy.required_source_state
        or instance.inert_context_injected is not True
        or instance.runtime_slot_mutation_performed is not True
        or instance.protected_runtime_handle_consumed is not True
        or instance.injection_outcome_known is not True
        or instance.runtime_slot_post_generation < 1
        or instance.destination_generation < 1
        or instance.runtime_slot_profile_id != policy.runtime_slot_profile_id
        or instance.runtime_slot_profile_version != policy.runtime_slot_profile_version
        or instance.runtime_slot_profile_digest != policy.runtime_slot_profile_digest
        or instance.consumer_subject_id != policy.consumer_subject_id
        or instance.consumer_audience != policy.consumer_audience
        or instance.consumer_contract_id != policy.consumer_contract_id
        or instance.consumer_contract_version != policy.consumer_contract_version
        or instance.purpose_id != policy.purpose_id
        or instance.policy_id != policy.policy_id
        or instance.policy_version != policy.policy_version
        or instance.policy_digest != policy.canonical_digest
        or any(
            value.tzinfo is None
            for value in (
                instance.injection_completed_at,
                instance.injection_result_recorded_at,
                instance.injection_deadline,
                instance.injected_context_usable_until,
            )
        )
        or not instance.injection_completed_at < instance.injection_deadline
        or not instance.injection_completed_at < instance.injected_context_usable_until
        or instance.injection_result_recorded_at < instance.injection_completed_at
        or any(
            value
            for name, value in authority.canonical_value().items()
            if name != "protected_runtime_context_use_authority_granted"
        )
    ):
        raise ValueError("runtime context use authorization source is ineligible")


_SOURCE_IDENTIFIERS = (
    "injection_result_id",
    "injection_id",
    "injection_attempt_id",
    "injection_consumption_claim_id",
    "injection_authorization_lease_id",
    "destination_boundary_id",
    "destination_deployment_id",
    "runtime_slot_profile_id",
    "runtime_slot_profile_version",
    "consumer_subject_id",
    "consumer_audience",
    "consumer_contract_id",
    "consumer_contract_version",
    "purpose_id",
    "policy_id",
    "policy_version",
)
_SOURCE_DIGESTS = (
    "injection_result_digest",
    "injection_attempt_digest",
    "injection_consumption_claim_digest",
    "injection_authorization_lease_digest",
    "injector_receipt_digest",
    "destination_fencing_token_digest",
    "runtime_slot_profile_digest",
    "runtime_slot_commitment",
    "policy_digest",
)
_CLAIM_IDENTIFIERS = ("claim_id", *_SOURCE_IDENTIFIERS)
_CLAIM_DIGESTS = (
    *_SOURCE_DIGESTS,
    "request_fingerprint",
    "idempotency_digest",
    "authorization_audit_digest",
    "canonical_digest",
)
_LEASE_IDENTIFIERS = (
    "authorization_lease_id",
    "claim_id",
    *_SOURCE_IDENTIFIERS,
    "lifecycle_attestation_id",
    "use_profile_id",
    "use_profile_version",
)
_LEASE_DIGESTS = (
    "claim_digest",
    *_SOURCE_DIGESTS,
    "lifecycle_attestation_digest",
    "use_profile_digest",
    "canonical_digest",
)


def _require_identifiers(instance: object, names: tuple[str, ...]) -> None:
    for name in names:
        value = getattr(instance, name)
        if (
            not isinstance(value, str)
            or not value
            or value != value.strip()
            or len(value) > 240
            or any(character.isspace() for character in value)
        ):
            raise ValueError(f"runtime context use authorization {name} is invalid")


def _require_digests(instance: object, names: tuple[str, ...]) -> None:
    for name in names:
        value = getattr(instance, name)
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ValueError(f"runtime context use authorization {name} is invalid")


def _require_canonical_digest(
    instance: (
        WorkflowProtectedRuntimeContextUseAuthorizationClaim
        | WorkflowProtectedRuntimeContextUseAuthorizationLease
    ),
) -> None:
    if instance.canonical_digest != canonical_digest(instance.digest_payload()):
        raise ValueError("runtime context use authorization digest mismatch")


def _payload(instance: object, *, exclude: tuple[str, ...] = ()) -> dict[str, object]:
    return {
        field.name: _canonical_value(getattr(instance, field.name))
        for field in fields(cast(Any, instance))
        if field.name not in exclude
    }


def _canonical_value(value: Any) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if hasattr(value, "canonical_value"):
        return value.canonical_value()
    return value


__all__ = [
    "WorkflowProtectedRuntimeContextUseAuthorizationAuthority",
    "WorkflowProtectedRuntimeContextUseAuthorizationClaim",
    "WorkflowProtectedRuntimeContextUseAuthorizationLease",
    "WorkflowProtectedRuntimeContextUseAuthorizationLeaseState",
    "WorkflowProtectedRuntimeContextUseAuthorizationPolicy",
    "code_owned_workflow_protected_runtime_context_use_authorization_policy",
    "code_owned_workflow_protected_runtime_context_use_authorization_policy_values",
]
