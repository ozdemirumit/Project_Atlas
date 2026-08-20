from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime, timedelta
from enum import StrEnum
from functools import lru_cache
from typing import Any, cast

from .models import WorkflowScope, canonical_digest
from .protected_runtime_readiness_consumption_domain import (
    WorkflowProtectedRuntimeReadinessConsumptionFailureClass,
    WorkflowProtectedRuntimeReadinessConsumptionResultState,
    code_owned_workflow_protected_runtime_readiness_consumption_policy,
)

WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_MAXIMUM_ATTESTATION_FRESHNESS_SECONDS = 1


class WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseState(StrEnum):
    AUTHORIZED_UNCONSUMED = "authorized_unconsumed"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationAuthorizationAuthority:
    """A non-bearer future request lease with no process or operational authority."""

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
    protected_runtime_process_creation_authority_granted: bool = False

    def __post_init__(self) -> None:
        declarations = self.canonical_value()
        declarations.pop("protected_runtime_process_creation_authority_granted")
        if any(declarations.values()):
            raise ValueError("runtime process creation authorization grants operational authority")

    def canonical_value(self) -> dict[str, bool]:
        return {field.name: cast(bool, getattr(self, field.name)) for field in fields(self)}


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationAuthorizationPolicy:
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
    process_creation_profile_id: str
    process_creation_profile_version: str
    process_creation_profile_digest: str
    maximum_lifetime_seconds: int
    single_use_required: bool
    renewable_allowed: bool
    transferable_allowed: bool
    bearer_capability_allowed: bool
    durable_replay_required: bool
    fresh_attestation_required: bool
    metadata_only_attestation_required: bool
    runtime_started_required: bool
    runtime_ready_required: bool
    process_created_required: bool
    process_scheduled_required: bool
    process_creation_forbidden: bool
    process_control_forbidden: bool
    scheduling_forbidden: bool
    command_material_forbidden: bool
    executable_material_forbidden: bool
    argument_material_forbidden: bool
    environment_material_forbidden: bool
    prompt_material_forbidden: bool
    model_material_forbidden: bool
    runtime_material_forbidden: bool
    runtime_locator_forbidden: bool
    network_activity_forbidden: bool
    connector_activity_forbidden: bool
    mcp_activity_forbidden: bool
    provider_activity_forbidden: bool
    publication_forbidden: bool
    delivery_forbidden: bool
    dispatch_forbidden: bool
    execution_forbidden: bool
    infrastructure_mutation_forbidden: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        expected = (
            code_owned_workflow_protected_runtime_process_creation_authorization_policy_values()
        )
        if any(getattr(self, name) != value for name, value in expected.items()):
            raise ValueError("runtime process creation authorization policy is not code-owned")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("runtime process creation authorization policy digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))

    @property
    def maximum_attestation_freshness_seconds(self) -> int:
        return WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_MAXIMUM_ATTESTATION_FRESHNESS_SECONDS


def code_owned_workflow_protected_runtime_process_creation_authorization_policy_values() -> dict[
    str, object
]:
    source = code_owned_workflow_protected_runtime_readiness_consumption_policy()
    profile = {
        "profile_id": "profile.workflow-protected-runtime-process-creation-request",
        "profile_version": "1.0",
        "source_policy_digest": source.canonical_digest,
        "runtime_started_required": True,
        "runtime_ready_required": True,
        "process_created_required": False,
        "process_scheduled_required": False,
        "metadata_only_attestation_required": True,
    }
    return {
        "policy_id": "policy.workflow-protected-runtime-process-creation-authorization",
        "policy_version": "1.0",
        "source_policy_id": source.policy_id,
        "source_policy_version": source.policy_version,
        "source_policy_digest": source.canonical_digest,
        "consumer_subject_id": source.consumer_subject_id,
        "consumer_audience": source.consumer_audience,
        "consumer_contract_id": source.consumer_contract_id,
        "consumer_contract_version": source.consumer_contract_version,
        "purpose_id": "purpose.workflow-protected-runtime-process-creation-request",
        "required_source_state": (
            WorkflowProtectedRuntimeReadinessConsumptionResultState
        ).RUNTIME_READY_IN_PROTECTED_BOUNDARY.value,
        "process_creation_profile_id": cast(str, profile["profile_id"]),
        "process_creation_profile_version": cast(str, profile["profile_version"]),
        "process_creation_profile_digest": canonical_digest(profile),
        "maximum_lifetime_seconds": 1,
        "single_use_required": True,
        "renewable_allowed": False,
        "transferable_allowed": False,
        "bearer_capability_allowed": False,
        "durable_replay_required": True,
        "fresh_attestation_required": True,
        "metadata_only_attestation_required": True,
        "runtime_started_required": True,
        "runtime_ready_required": True,
        "process_created_required": False,
        "process_scheduled_required": False,
        "process_creation_forbidden": True,
        "process_control_forbidden": True,
        "scheduling_forbidden": True,
        "command_material_forbidden": True,
        "executable_material_forbidden": True,
        "argument_material_forbidden": True,
        "environment_material_forbidden": True,
        "prompt_material_forbidden": True,
        "model_material_forbidden": True,
        "runtime_material_forbidden": True,
        "runtime_locator_forbidden": True,
        "network_activity_forbidden": True,
        "connector_activity_forbidden": True,
        "mcp_activity_forbidden": True,
        "provider_activity_forbidden": True,
        "publication_forbidden": True,
        "delivery_forbidden": True,
        "dispatch_forbidden": True,
        "execution_forbidden": True,
        "infrastructure_mutation_forbidden": True,
    }


@lru_cache(maxsize=1)
def code_owned_workflow_protected_runtime_process_creation_authorization_policy() -> (
    WorkflowProtectedRuntimeProcessCreationAuthorizationPolicy
):
    values = code_owned_workflow_protected_runtime_process_creation_authorization_policy_values()
    return WorkflowProtectedRuntimeProcessCreationAuthorizationPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationAuthorizationClaim:
    claim_id: str
    readiness_result_id: str
    readiness_result_digest: str
    readiness_consumption_id: str
    readiness_attempt_id: str
    readiness_attempt_digest: str
    readiness_claim_id: str
    readiness_claim_digest: str
    readiness_authorization_lease_id: str
    readiness_authorization_lease_digest: str
    start_result_id: str
    start_result_digest: str
    assessor_receipt_digest: str
    readiness_result_state: WorkflowProtectedRuntimeReadinessConsumptionResultState
    readiness_failure_class: WorkflowProtectedRuntimeReadinessConsumptionFailureClass | None
    readiness_outcome_known: bool
    readiness_assessment_performed: bool
    runtime_ready: bool
    readiness_completed_at: datetime
    readiness_result_recorded_at: datetime
    readiness_profile_id: str
    readiness_profile_version: str
    readiness_profile_digest: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    protected_slot_commitment: str
    protected_slot_generation: int
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
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
    authority: WorkflowProtectedRuntimeProcessCreationAuthorizationAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        _validate_source_snapshot(self)
        _require_identifiers(self, _CLAIM_IDENTIFIERS)
        _require_digests(self, _CLAIM_DIGESTS)
        if (
            self.claimed_at.tzinfo is None
            or self.claimed_at < self.readiness_result_recorded_at
            or self.authority.protected_runtime_process_creation_authority_granted is not False
        ):
            raise ValueError("runtime process creation authorization claim is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationAuthorizationLease:
    authorization_lease_id: str
    claim_id: str
    claim_digest: str
    readiness_result_id: str
    readiness_result_digest: str
    readiness_consumption_id: str
    readiness_attempt_id: str
    readiness_attempt_digest: str
    readiness_claim_id: str
    readiness_claim_digest: str
    readiness_authorization_lease_id: str
    readiness_authorization_lease_digest: str
    start_result_id: str
    start_result_digest: str
    assessor_receipt_digest: str
    readiness_result_state: WorkflowProtectedRuntimeReadinessConsumptionResultState
    readiness_failure_class: WorkflowProtectedRuntimeReadinessConsumptionFailureClass | None
    readiness_outcome_known: bool
    readiness_assessment_performed: bool
    runtime_ready: bool
    readiness_completed_at: datetime
    readiness_result_recorded_at: datetime
    readiness_profile_id: str
    readiness_profile_version: str
    readiness_profile_digest: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    protected_slot_commitment: str
    protected_slot_generation: int
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
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
    attestation_metadata_only: bool
    runtime_started: bool
    process_created: bool
    process_scheduled: bool
    process_creation_profile_id: str
    process_creation_profile_version: str
    process_creation_profile_digest: str
    issued_at: datetime
    valid_until: datetime
    effective_until: datetime
    single_use: bool
    renewable: bool
    transferable: bool
    lease_is_bearer_capability: bool
    state: WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseState
    authority: WorkflowProtectedRuntimeProcessCreationAuthorizationAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_process_creation_authorization_policy()
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
            or not self.readiness_result_recorded_at <= self.issued_at < self.valid_until
            or self.valid_until - self.issued_at
            > timedelta(seconds=policy.maximum_lifetime_seconds)
            or self.valid_until != self.effective_until
            or self.effective_until > self.lifecycle_attestation_valid_until
            or self.effective_until > self.runtime_envelope_eligible_until
            or self.attestation_metadata_only is not policy.metadata_only_attestation_required
            or self.runtime_started is not policy.runtime_started_required
            or self.process_created is not policy.process_created_required
            or self.process_scheduled is not policy.process_scheduled_required
            or self.process_creation_profile_id != policy.process_creation_profile_id
            or self.process_creation_profile_version != policy.process_creation_profile_version
            or self.process_creation_profile_digest != policy.process_creation_profile_digest
            or self.single_use is not True
            or self.renewable is not False
            or self.transferable is not False
            or self.lease_is_bearer_capability is not False
            or self.state
            is not (
                WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseState
            ).AUTHORIZED_UNCONSUMED
            or self.authority.protected_runtime_process_creation_authority_granted is not True
        ):
            raise ValueError("runtime process creation authorization lease is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))

    def is_active(self, *, evaluated_at: datetime, consumed: bool = False) -> bool:
        if evaluated_at.tzinfo is None:
            raise ValueError("runtime process creation lease evaluation time must be aware")
        return not consumed and self.issued_at <= evaluated_at < self.valid_until

    def presented_authority(
        self, *, evaluated_at: datetime, consumed: bool = False
    ) -> WorkflowProtectedRuntimeProcessCreationAuthorizationAuthority:
        if self.is_active(evaluated_at=evaluated_at, consumed=consumed):
            return self.authority
        return WorkflowProtectedRuntimeProcessCreationAuthorizationAuthority()


def _validate_source_snapshot(
    instance: WorkflowProtectedRuntimeProcessCreationAuthorizationClaim
    | WorkflowProtectedRuntimeProcessCreationAuthorizationLease,
) -> None:
    policy = code_owned_workflow_protected_runtime_process_creation_authorization_policy()
    source_policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()
    authority = instance.authority.canonical_value()
    authority.pop("protected_runtime_process_creation_authority_granted")
    if (
        instance.readiness_result_state.value != policy.required_source_state
        or instance.readiness_failure_class is not None
        or instance.readiness_outcome_known is not True
        or instance.readiness_assessment_performed is not True
        or instance.runtime_ready is not policy.runtime_ready_required
        or instance.destination_generation < 1
        or instance.protected_slot_generation < 1
        or instance.runtime_envelope_generation != instance.protected_slot_generation
        or instance.readiness_profile_id != source_policy.readiness_profile_id
        or instance.readiness_profile_version != source_policy.readiness_profile_version
        or instance.readiness_profile_digest != source_policy.readiness_profile_digest
        or instance.consumer_subject_id != policy.consumer_subject_id
        or instance.consumer_audience != policy.consumer_audience
        or instance.consumer_contract_id != policy.consumer_contract_id
        or instance.consumer_contract_version != policy.consumer_contract_version
        or instance.purpose_id != policy.purpose_id
        or instance.policy_id != policy.policy_id
        or instance.policy_version != policy.policy_version
        or instance.policy_digest != policy.canonical_digest
        or instance.readiness_completed_at.tzinfo is None
        or instance.readiness_result_recorded_at.tzinfo is None
        or instance.readiness_result_recorded_at < instance.readiness_completed_at
        or any(authority.values())
    ):
        raise ValueError("runtime process creation authorization source is ineligible")


_SOURCE_IDENTIFIERS = (
    "readiness_result_id",
    "readiness_consumption_id",
    "readiness_attempt_id",
    "readiness_claim_id",
    "readiness_authorization_lease_id",
    "start_result_id",
    "readiness_profile_id",
    "readiness_profile_version",
    "destination_deployment_id",
    "runtime_envelope_id",
    "consumer_subject_id",
    "consumer_audience",
    "consumer_contract_id",
    "consumer_contract_version",
    "purpose_id",
    "policy_id",
    "policy_version",
)
_SOURCE_DIGESTS = (
    "readiness_result_digest",
    "readiness_attempt_digest",
    "readiness_claim_digest",
    "readiness_authorization_lease_digest",
    "start_result_digest",
    "assessor_receipt_digest",
    "readiness_profile_digest",
    "destination_fencing_token_digest",
    "protected_slot_commitment",
    "runtime_envelope_commitment",
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
    "process_creation_profile_id",
    "process_creation_profile_version",
)
_LEASE_DIGESTS = (
    "claim_digest",
    *_SOURCE_DIGESTS,
    "lifecycle_attestation_digest",
    "process_creation_profile_digest",
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
            raise ValueError(f"runtime process creation authorization {name} is invalid")


def _require_digests(instance: object, names: tuple[str, ...]) -> None:
    for name in names:
        value = getattr(instance, name)
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ValueError(f"runtime process creation authorization {name} is invalid")


def _require_canonical_digest(
    instance: WorkflowProtectedRuntimeProcessCreationAuthorizationClaim
    | WorkflowProtectedRuntimeProcessCreationAuthorizationLease,
) -> None:
    if instance.canonical_digest != canonical_digest(instance.digest_payload()):
        raise ValueError("runtime process creation authorization digest mismatch")


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
    "WorkflowProtectedRuntimeProcessCreationAuthorizationAuthority",
    "WorkflowProtectedRuntimeProcessCreationAuthorizationClaim",
    "WorkflowProtectedRuntimeProcessCreationAuthorizationLease",
    "WorkflowProtectedRuntimeProcessCreationAuthorizationLeaseState",
    "WorkflowProtectedRuntimeProcessCreationAuthorizationPolicy",
    "code_owned_workflow_protected_runtime_process_creation_authorization_policy",
    "code_owned_workflow_protected_runtime_process_creation_authorization_policy_values",
]
