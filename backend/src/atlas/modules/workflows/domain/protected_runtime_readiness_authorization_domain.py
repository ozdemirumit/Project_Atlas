from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime, timedelta
from enum import StrEnum
from functools import lru_cache
from typing import Any, cast

from .models import WorkflowScope, canonical_digest
from .protected_runtime_start_consumption_domain import (
    WorkflowProtectedRuntimeStartConsumptionResultState,
    code_owned_workflow_protected_runtime_start_consumption_policy,
)

WORKFLOW_PROTECTED_RUNTIME_READINESS_MAXIMUM_ATTESTATION_FRESHNESS_SECONDS = 1


class WorkflowProtectedRuntimeReadinessAuthorizationLeaseState(StrEnum):
    AUTHORIZED_UNCONSUMED = "authorized_unconsumed"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessAuthorizationAuthority:
    """A non-bearer future readiness-request lease with no probe authority."""

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
    protected_runtime_start_authority_granted: bool = False
    protected_runtime_readiness_authority_granted: bool = False

    def __post_init__(self) -> None:
        declarations = self.canonical_value()
        declarations.pop("protected_runtime_readiness_authority_granted")
        if any(declarations.values()):
            raise ValueError("runtime readiness authorization grants operational authority")

    def canonical_value(self) -> dict[str, bool]:
        return {field.name: cast(bool, getattr(self, field.name)) for field in fields(self)}


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessAuthorizationPolicy:
    policy_id: str
    policy_version: str
    source_policy_id: str
    source_policy_version: str
    source_policy_digest: str
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
    readiness_profile_id: str
    readiness_profile_version: str
    readiness_profile_digest: str
    maximum_lifetime_seconds: int
    single_use_required: bool
    renewable_allowed: bool
    transferable_allowed: bool
    bearer_capability_allowed: bool
    durable_replay_required: bool
    fresh_attestation_required: bool
    runtime_use_forbidden: bool
    runtime_start_forbidden: bool
    runtime_resume_forbidden: bool
    process_control_forbidden: bool
    scheduling_forbidden: bool
    readiness_probe_forbidden: bool
    network_activity_forbidden: bool
    connector_activity_forbidden: bool
    publication_forbidden: bool
    delivery_forbidden: bool
    dispatch_forbidden: bool
    execution_forbidden: bool
    infrastructure_mutation_forbidden: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        expected = code_owned_workflow_protected_runtime_readiness_authorization_policy_values()
        if any(getattr(self, name) != value for name, value in expected.items()):
            raise ValueError("runtime readiness authorization policy is not code-owned")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("runtime readiness authorization policy digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))

    @property
    def maximum_attestation_freshness_seconds(self) -> int:
        """Code-owned freshness ceiling that does not alter the persisted policy digest."""

        return WORKFLOW_PROTECTED_RUNTIME_READINESS_MAXIMUM_ATTESTATION_FRESHNESS_SECONDS


def code_owned_workflow_protected_runtime_readiness_authorization_policy_values() -> dict[
    str, object
]:
    source = code_owned_workflow_protected_runtime_start_consumption_policy()
    profile = {
        "profile_id": "profile.workflow-protected-runtime-readiness",
        "profile_version": "1.0",
        "source_policy_digest": source.canonical_digest,
        "runtime_started_required": True,
        "readiness_probe_forbidden": True,
    }
    return {
        "policy_id": "policy.workflow-protected-runtime-readiness-authorization",
        "policy_version": "1.0",
        "source_policy_id": source.policy_id,
        "source_policy_version": source.policy_version,
        "source_policy_digest": source.canonical_digest,
        "consumer_subject_id": source.consumer_subject_id,
        "consumer_audience": source.consumer_audience,
        "consumer_contract_id": source.consumer_contract_id,
        "consumer_contract_version": source.consumer_contract_version,
        "purpose_id": "purpose.workflow-protected-runtime-readiness-evaluation",
        "required_source_state": (
            WorkflowProtectedRuntimeStartConsumptionResultState
        ).RUNTIME_STARTED_IN_PROTECTED_BOUNDARY.value,
        "required_attestor_id": "attestor.workflow-protected-runtime-readiness-lifecycle",
        "required_attestor_version": "1.0",
        "verification_signing_key_id": ("key.workflow-protected-runtime-readiness-lifecycle.v1"),
        "receipt_verification_signing_key_id": source.receipt_verification_signing_key_id,
        "readiness_profile_id": cast(str, profile["profile_id"]),
        "readiness_profile_version": cast(str, profile["profile_version"]),
        "readiness_profile_digest": canonical_digest(profile),
        "maximum_lifetime_seconds": 1,
        "single_use_required": True,
        "renewable_allowed": False,
        "transferable_allowed": False,
        "bearer_capability_allowed": False,
        "durable_replay_required": True,
        "fresh_attestation_required": True,
        "runtime_use_forbidden": True,
        "runtime_start_forbidden": True,
        "runtime_resume_forbidden": True,
        "process_control_forbidden": True,
        "scheduling_forbidden": True,
        "readiness_probe_forbidden": True,
        "network_activity_forbidden": True,
        "connector_activity_forbidden": True,
        "publication_forbidden": True,
        "delivery_forbidden": True,
        "dispatch_forbidden": True,
        "execution_forbidden": True,
        "infrastructure_mutation_forbidden": True,
    }


@lru_cache(maxsize=1)
def code_owned_workflow_protected_runtime_readiness_authorization_policy() -> (
    WorkflowProtectedRuntimeReadinessAuthorizationPolicy
):
    values = code_owned_workflow_protected_runtime_readiness_authorization_policy_values()
    return WorkflowProtectedRuntimeReadinessAuthorizationPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessAuthorizationClaim:
    claim_id: str
    start_result_id: str
    start_result_digest: str
    start_consumption_id: str
    start_attempt_id: str
    start_attempt_digest: str
    start_claim_id: str
    start_claim_digest: str
    start_authorization_lease_id: str
    start_authorization_lease_digest: str
    starter_receipt_digest: str
    start_result_state: WorkflowProtectedRuntimeStartConsumptionResultState
    start_completed_at: datetime
    start_result_recorded_at: datetime
    start_outcome_known: bool
    runtime_started: bool
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    protected_slot_commitment: str
    protected_slot_generation: int
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
    runtime_start_profile_id: str
    runtime_start_profile_version: str
    runtime_start_profile_digest: str
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
    authority: WorkflowProtectedRuntimeReadinessAuthorizationAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        _validate_source_snapshot(self)
        _require_identifiers(self, _CLAIM_IDENTIFIERS)
        _require_digests(self, _CLAIM_DIGESTS)
        if (
            self.claimed_at.tzinfo is None
            or self.claimed_at < self.start_result_recorded_at
            or self.authority.protected_runtime_readiness_authority_granted is not False
        ):
            raise ValueError("runtime readiness authorization claim is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessAuthorizationLease:
    authorization_lease_id: str
    claim_id: str
    claim_digest: str
    start_result_id: str
    start_result_digest: str
    start_consumption_id: str
    start_attempt_id: str
    start_attempt_digest: str
    start_claim_id: str
    start_claim_digest: str
    start_authorization_lease_id: str
    start_authorization_lease_digest: str
    starter_receipt_digest: str
    start_result_state: WorkflowProtectedRuntimeStartConsumptionResultState
    start_completed_at: datetime
    start_result_recorded_at: datetime
    start_outcome_known: bool
    runtime_started: bool
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    protected_slot_commitment: str
    protected_slot_generation: int
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
    runtime_start_profile_id: str
    runtime_start_profile_version: str
    runtime_start_profile_digest: str
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
    runtime_envelope_eligible_until: datetime
    readiness_profile_id: str
    readiness_profile_version: str
    readiness_profile_digest: str
    issued_at: datetime
    valid_until: datetime
    effective_until: datetime
    single_use: bool
    renewable: bool
    transferable: bool
    lease_is_bearer_capability: bool
    state: WorkflowProtectedRuntimeReadinessAuthorizationLeaseState
    authority: WorkflowProtectedRuntimeReadinessAuthorizationAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_readiness_authorization_policy()
        _validate_source_snapshot(self)
        _require_identifiers(self, _LEASE_IDENTIFIERS)
        _require_digests(self, _LEASE_DIGESTS)
        if (
            any(
                value.tzinfo is None
                for value in (
                    self.lifecycle_attestation_valid_until,
                    self.runtime_envelope_eligible_until,
                    self.issued_at,
                    self.valid_until,
                    self.effective_until,
                )
            )
            or not self.start_result_recorded_at <= self.issued_at < self.valid_until
            or self.valid_until - self.issued_at
            > timedelta(seconds=policy.maximum_lifetime_seconds)
            or self.valid_until != self.effective_until
            or self.effective_until > self.lifecycle_attestation_valid_until
            or self.effective_until > self.runtime_envelope_eligible_until
            or self.readiness_profile_id != policy.readiness_profile_id
            or self.readiness_profile_version != policy.readiness_profile_version
            or self.readiness_profile_digest != policy.readiness_profile_digest
            or self.single_use is not True
            or self.renewable is not False
            or self.transferable is not False
            or self.lease_is_bearer_capability is not False
            or self.state
            is not WorkflowProtectedRuntimeReadinessAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
            or self.authority.protected_runtime_readiness_authority_granted is not True
        ):
            raise ValueError("runtime readiness authorization lease is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))

    def is_active(self, *, evaluated_at: datetime, consumed: bool = False) -> bool:
        if evaluated_at.tzinfo is None:
            raise ValueError("runtime readiness lease evaluation time must be aware")
        return not consumed and self.issued_at <= evaluated_at < self.valid_until


def _validate_source_snapshot(
    instance: WorkflowProtectedRuntimeReadinessAuthorizationClaim
    | WorkflowProtectedRuntimeReadinessAuthorizationLease,
) -> None:
    policy = code_owned_workflow_protected_runtime_readiness_authorization_policy()
    authority = instance.authority.canonical_value()
    authority.pop("protected_runtime_readiness_authority_granted")
    if (
        instance.start_result_state.value != policy.required_source_state
        or instance.start_outcome_known is not True
        or instance.runtime_started is not True
        or instance.destination_generation < 1
        or instance.protected_slot_generation < 1
        or instance.runtime_envelope_generation != instance.protected_slot_generation
        or instance.consumer_subject_id != policy.consumer_subject_id
        or instance.consumer_audience != policy.consumer_audience
        or instance.consumer_contract_id != policy.consumer_contract_id
        or instance.consumer_contract_version != policy.consumer_contract_version
        or instance.purpose_id != policy.purpose_id
        or instance.policy_id != policy.policy_id
        or instance.policy_version != policy.policy_version
        or instance.policy_digest != policy.canonical_digest
        or instance.start_completed_at.tzinfo is None
        or instance.start_result_recorded_at.tzinfo is None
        or instance.start_result_recorded_at < instance.start_completed_at
        or any(authority.values())
    ):
        raise ValueError("runtime readiness authorization source is ineligible")


_SOURCE_IDENTIFIERS = (
    "start_result_id",
    "start_consumption_id",
    "start_attempt_id",
    "start_claim_id",
    "start_authorization_lease_id",
    "destination_deployment_id",
    "runtime_envelope_id",
    "runtime_start_profile_id",
    "runtime_start_profile_version",
    "consumer_subject_id",
    "consumer_audience",
    "consumer_contract_id",
    "consumer_contract_version",
    "purpose_id",
    "policy_id",
    "policy_version",
)
_SOURCE_DIGESTS = (
    "start_result_digest",
    "start_attempt_digest",
    "start_claim_digest",
    "start_authorization_lease_digest",
    "starter_receipt_digest",
    "destination_fencing_token_digest",
    "protected_slot_commitment",
    "runtime_envelope_commitment",
    "runtime_start_profile_digest",
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
    "readiness_profile_id",
    "readiness_profile_version",
)
_LEASE_DIGESTS = (
    "claim_digest",
    *_SOURCE_DIGESTS,
    "lifecycle_attestation_digest",
    "readiness_profile_digest",
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
            raise ValueError(f"runtime readiness authorization {name} is invalid")


def _require_digests(instance: object, names: tuple[str, ...]) -> None:
    for name in names:
        value = getattr(instance, name)
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ValueError(f"runtime readiness authorization {name} is invalid")


def _require_canonical_digest(
    instance: WorkflowProtectedRuntimeReadinessAuthorizationClaim
    | WorkflowProtectedRuntimeReadinessAuthorizationLease,
) -> None:
    if instance.canonical_digest != canonical_digest(instance.digest_payload()):
        raise ValueError("runtime readiness authorization digest mismatch")


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
    "WorkflowProtectedRuntimeReadinessAuthorizationAuthority",
    "WorkflowProtectedRuntimeReadinessAuthorizationClaim",
    "WorkflowProtectedRuntimeReadinessAuthorizationLease",
    "WorkflowProtectedRuntimeReadinessAuthorizationLeaseState",
    "WorkflowProtectedRuntimeReadinessAuthorizationPolicy",
    "code_owned_workflow_protected_runtime_readiness_authorization_policy",
    "code_owned_workflow_protected_runtime_readiness_authorization_policy_values",
]
