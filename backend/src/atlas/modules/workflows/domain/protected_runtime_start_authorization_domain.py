from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, cast

from .models import WorkflowScope, canonical_digest
from .protected_runtime_context_use_domain import (
    WorkflowProtectedRuntimeContextUseResultState,
    code_owned_workflow_protected_runtime_context_use_policy,
)


class WorkflowProtectedRuntimeStartAuthorizationLeaseState(StrEnum):
    AUTHORIZED_UNCONSUMED = "authorized_unconsumed"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartEnvelopeBinding:
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int


def workflow_protected_runtime_start_envelope_binding(
    *,
    use_result_id: str,
    use_result_digest: str,
    destination_deployment_id: str,
    destination_generation: int,
    destination_fencing_token_digest: str,
    runtime_slot_commitment: str,
    runtime_slot_post_generation: int,
) -> WorkflowProtectedRuntimeStartEnvelopeBinding:
    payload = {
        "use_result_id": use_result_id,
        "use_result_digest": use_result_digest,
        "destination_deployment_id": destination_deployment_id,
        "destination_generation": destination_generation,
        "destination_fencing_token_digest": destination_fencing_token_digest,
        "runtime_slot_commitment": runtime_slot_commitment,
        "runtime_slot_post_generation": runtime_slot_post_generation,
    }
    commitment = canonical_digest(payload)
    return WorkflowProtectedRuntimeStartEnvelopeBinding(
        runtime_envelope_id=f"runtime-envelope.{commitment[:48]}",
        runtime_envelope_commitment=commitment,
        runtime_envelope_generation=runtime_slot_post_generation,
    )


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartAuthorizationAuthority:
    """A non-bearer future-request lease with no runtime-start permission."""

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

    def __post_init__(self) -> None:
        declarations = self.canonical_value()
        declarations.pop("protected_runtime_start_authority_granted")
        if any(declarations.values()):
            raise ValueError("runtime start authorization grants operational authority")

    def canonical_value(self) -> dict[str, bool]:
        return {field.name: cast(bool, getattr(self, field.name)) for field in fields(self)}


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartAuthorizationPolicy:
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
    runtime_start_profile_id: str
    runtime_start_profile_version: str
    runtime_start_profile_digest: str
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
    process_creation_forbidden: bool
    scheduling_forbidden: bool
    prompt_construction_forbidden: bool
    model_inference_forbidden: bool
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
        expected = code_owned_workflow_protected_runtime_start_authorization_policy_values()
        if any(getattr(self, name) != value for name, value in expected.items()):
            raise ValueError("runtime start authorization policy is not code-owned")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("runtime start authorization policy digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


def code_owned_workflow_protected_runtime_start_authorization_policy_values() -> dict[str, object]:
    source = code_owned_workflow_protected_runtime_context_use_policy()
    profile = {
        "profile_id": "profile.workflow-protected-runtime-start",
        "profile_version": "1.0",
        "source_policy_digest": source.canonical_digest,
        "runtime_start_forbidden": True,
    }
    return {
        "policy_id": "policy.workflow-protected-runtime-start-authorization",
        "policy_version": "1.0",
        "source_policy_id": source.policy_id,
        "source_policy_version": source.policy_version,
        "source_policy_digest": source.canonical_digest,
        "consumer_subject_id": source.consumer_subject_id,
        "consumer_audience": source.consumer_audience,
        "consumer_contract_id": source.consumer_contract_id,
        "consumer_contract_version": source.consumer_contract_version,
        "purpose_id": "purpose.workflow-protected-runtime-start-evaluation",
        "required_source_state": (
            WorkflowProtectedRuntimeContextUseResultState.CONTEXT_USED_ONCE_IN_PROTECTED_BOUNDARY.value
        ),
        "required_attestor_id": "attestor.workflow-protected-runtime-start-lifecycle",
        "required_attestor_version": "1.0",
        "verification_signing_key_id": "key.workflow-protected-runtime-start-lifecycle.v1",
        "receipt_verification_signing_key_id": source.receipt_verification_signing_key_id,
        "runtime_start_profile_id": cast(str, profile["profile_id"]),
        "runtime_start_profile_version": cast(str, profile["profile_version"]),
        "runtime_start_profile_digest": canonical_digest(profile),
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
        "process_creation_forbidden": True,
        "scheduling_forbidden": True,
        "prompt_construction_forbidden": True,
        "model_inference_forbidden": True,
        "network_activity_forbidden": True,
        "connector_activity_forbidden": True,
        "readiness_probe_forbidden": True,
        "publication_forbidden": True,
        "delivery_forbidden": True,
        "dispatch_forbidden": True,
        "execution_forbidden": True,
        "infrastructure_mutation_forbidden": True,
    }


def code_owned_workflow_protected_runtime_start_authorization_policy() -> (
    WorkflowProtectedRuntimeStartAuthorizationPolicy
):
    values = code_owned_workflow_protected_runtime_start_authorization_policy_values()
    return WorkflowProtectedRuntimeStartAuthorizationPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartAuthorizationClaim:
    claim_id: str
    use_result_id: str
    use_result_digest: str
    use_id: str
    use_attempt_id: str
    use_attempt_digest: str
    use_claim_id: str
    use_claim_digest: str
    use_receipt_digest: str
    authorization_consumption_result_id: str
    authorization_consumption_result_digest: str
    use_result_state: WorkflowProtectedRuntimeContextUseResultState
    use_completed_at: datetime
    use_result_recorded_at: datetime
    use_outcome_known: bool
    context_adopted: bool
    protected_runtime_context_use_performed: bool
    context_terminal_non_reusable: bool
    transient_material_zeroized: bool
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_slot_commitment: str
    runtime_slot_post_generation: int
    use_count_post: int
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
    use_profile_id: str
    use_profile_version: str
    use_profile_digest: str
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
    authority: WorkflowProtectedRuntimeStartAuthorizationAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        _validate_source_snapshot(self)
        _require_identifiers(self, _CLAIM_IDENTIFIERS)
        _require_digests(self, _CLAIM_DIGESTS)
        if (
            self.claimed_at.tzinfo is None
            or self.claimed_at < self.use_result_recorded_at
            or self.authority.protected_runtime_start_authority_granted is not False
        ):
            raise ValueError("runtime start authorization claim is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartAuthorizationLease:
    authorization_lease_id: str
    claim_id: str
    claim_digest: str
    use_result_id: str
    use_result_digest: str
    use_id: str
    use_attempt_id: str
    use_attempt_digest: str
    use_claim_id: str
    use_claim_digest: str
    use_receipt_digest: str
    authorization_consumption_result_id: str
    authorization_consumption_result_digest: str
    use_result_state: WorkflowProtectedRuntimeContextUseResultState
    use_completed_at: datetime
    use_result_recorded_at: datetime
    use_outcome_known: bool
    context_adopted: bool
    protected_runtime_context_use_performed: bool
    context_terminal_non_reusable: bool
    transient_material_zeroized: bool
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_slot_commitment: str
    runtime_slot_post_generation: int
    use_count_post: int
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
    use_profile_id: str
    use_profile_version: str
    use_profile_digest: str
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
    runtime_start_profile_id: str
    runtime_start_profile_version: str
    runtime_start_profile_digest: str
    issued_at: datetime
    valid_until: datetime
    effective_until: datetime
    single_use: bool
    renewable: bool
    transferable: bool
    lease_is_bearer_capability: bool
    state: WorkflowProtectedRuntimeStartAuthorizationLeaseState
    authority: WorkflowProtectedRuntimeStartAuthorizationAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_start_authorization_policy()
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
            or not self.use_result_recorded_at <= self.issued_at < self.valid_until
            or self.valid_until - self.issued_at
            > timedelta(seconds=policy.maximum_lifetime_seconds)
            or self.valid_until > self.effective_until
            or self.effective_until > self.lifecycle_attestation_valid_until
            or self.effective_until > self.runtime_envelope_eligible_until
            or self.runtime_start_profile_id != policy.runtime_start_profile_id
            or self.runtime_start_profile_version != policy.runtime_start_profile_version
            or self.runtime_start_profile_digest != policy.runtime_start_profile_digest
            or self.single_use is not policy.single_use_required
            or self.renewable is not policy.renewable_allowed
            or self.transferable is not policy.transferable_allowed
            or self.lease_is_bearer_capability is not policy.bearer_capability_allowed
            or self.state
            is not WorkflowProtectedRuntimeStartAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
            or self.authority.protected_runtime_start_authority_granted is not True
        ):
            raise ValueError("runtime start authorization lease is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))

    def is_active(self, *, evaluated_at: datetime, consumed: bool = False) -> bool:
        if evaluated_at.tzinfo is None:
            raise ValueError("runtime start lease evaluation time must be aware")
        return not consumed and self.issued_at <= evaluated_at < self.valid_until


def _validate_source_snapshot(
    instance: WorkflowProtectedRuntimeStartAuthorizationClaim
    | WorkflowProtectedRuntimeStartAuthorizationLease,
) -> None:
    policy = code_owned_workflow_protected_runtime_start_authorization_policy()
    authority = instance.authority.canonical_value()
    authority.pop("protected_runtime_start_authority_granted")
    if (
        instance.use_result_state.value != policy.required_source_state
        or instance.use_outcome_known is not True
        or instance.context_adopted is not True
        or instance.protected_runtime_context_use_performed is not True
        or instance.context_terminal_non_reusable is not True
        or instance.transient_material_zeroized is not True
        or instance.runtime_slot_post_generation < 2
        or instance.use_count_post != 1
        or instance.runtime_envelope_generation != instance.runtime_slot_post_generation
        or instance.destination_generation < 1
        or instance.consumer_subject_id != policy.consumer_subject_id
        or instance.consumer_audience != policy.consumer_audience
        or instance.consumer_contract_id != policy.consumer_contract_id
        or instance.consumer_contract_version != policy.consumer_contract_version
        or instance.purpose_id != policy.purpose_id
        or instance.policy_id != policy.policy_id
        or instance.policy_version != policy.policy_version
        or instance.policy_digest != policy.canonical_digest
        or instance.use_completed_at.tzinfo is None
        or instance.use_result_recorded_at.tzinfo is None
        or instance.use_result_recorded_at < instance.use_completed_at
        or any(authority.values())
    ):
        raise ValueError("runtime start authorization source is ineligible")


_SOURCE_IDENTIFIERS = (
    "use_result_id",
    "use_id",
    "use_attempt_id",
    "use_claim_id",
    "authorization_consumption_result_id",
    "destination_deployment_id",
    "runtime_envelope_id",
    "use_profile_id",
    "use_profile_version",
    "consumer_subject_id",
    "consumer_audience",
    "consumer_contract_id",
    "consumer_contract_version",
    "purpose_id",
    "policy_id",
    "policy_version",
)
_SOURCE_DIGESTS = (
    "use_result_digest",
    "use_attempt_digest",
    "use_claim_digest",
    "use_receipt_digest",
    "authorization_consumption_result_digest",
    "destination_fencing_token_digest",
    "runtime_slot_commitment",
    "runtime_envelope_commitment",
    "use_profile_digest",
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
    "runtime_start_profile_id",
    "runtime_start_profile_version",
)
_LEASE_DIGESTS = (
    "claim_digest",
    *_SOURCE_DIGESTS,
    "lifecycle_attestation_digest",
    "runtime_start_profile_digest",
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
            raise ValueError(f"runtime start authorization {name} is invalid")


def _require_digests(instance: object, names: tuple[str, ...]) -> None:
    for name in names:
        value = getattr(instance, name)
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ValueError(f"runtime start authorization {name} is invalid")


def _require_canonical_digest(
    instance: WorkflowProtectedRuntimeStartAuthorizationClaim
    | WorkflowProtectedRuntimeStartAuthorizationLease,
) -> None:
    if instance.canonical_digest != canonical_digest(instance.digest_payload()):
        raise ValueError("runtime start authorization digest mismatch")


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
    "WorkflowProtectedRuntimeStartAuthorizationAuthority",
    "WorkflowProtectedRuntimeStartAuthorizationClaim",
    "WorkflowProtectedRuntimeStartAuthorizationLease",
    "WorkflowProtectedRuntimeStartAuthorizationLeaseState",
    "WorkflowProtectedRuntimeStartAuthorizationPolicy",
    "WorkflowProtectedRuntimeStartEnvelopeBinding",
    "code_owned_workflow_protected_runtime_start_authorization_policy",
    "code_owned_workflow_protected_runtime_start_authorization_policy_values",
    "workflow_protected_runtime_start_envelope_binding",
]
