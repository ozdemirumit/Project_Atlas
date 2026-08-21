from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime, timedelta
from enum import StrEnum
from functools import lru_cache
from typing import Any, cast

from .models import WorkflowScope, canonical_digest
from .protected_runtime_process_scheduling_consumption_domain import (
    WorkflowProtectedRuntimeProcessSchedulingConsumptionFailureClass,
    WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState,
    code_owned_workflow_protected_runtime_process_scheduling_consumption_policy,
)

WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_MAXIMUM_ATTESTATION_FRESHNESS_SECONDS = 1
WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_MINIMUM_REMAINING_SAFETY_MARGIN_MILLISECONDS = 100


class WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseState(StrEnum):
    AUTHORIZED_UNCONSUMED = "authorized_unconsumed"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessResumeAuthorizationAuthority:
    """A non-bearer future process-resume-request lease with no operational authority."""

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
    protected_runtime_process_scheduling_authority_granted: bool = False
    protected_runtime_process_resume_authority_granted: bool = False

    def __post_init__(self) -> None:
        declarations = self.canonical_value()
        declarations.pop("protected_runtime_process_resume_authority_granted")
        if any(declarations.values()):
            raise ValueError("runtime process resume authorization grants operational authority")

    def canonical_value(self) -> dict[str, bool]:
        return {field.name: cast(bool, getattr(self, field.name)) for field in fields(self)}


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessResumeAuthorizationPolicy:
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
    resume_profile_id: str
    resume_profile_version: str
    resume_profile_digest: str
    maximum_lifetime_seconds: int
    minimum_remaining_safety_margin_milliseconds: int
    single_use_required: bool
    renewable_allowed: bool
    transferable_allowed: bool
    bearer_capability_allowed: bool
    durable_replay_required: bool
    exact_replay_no_io_required: bool
    fresh_attestation_required: bool
    metadata_only_attestation_required: bool
    process_created_required: bool
    process_sealed_required: bool
    process_suspended_required: bool
    process_scheduled_required: bool
    process_runnable_required: bool
    process_resumed_required: bool
    process_dispatched_required: bool
    process_executed_required: bool
    scheduling_forbidden: bool
    resume_forbidden: bool
    dispatch_forbidden: bool
    execution_forbidden: bool
    process_locator_forbidden: bool
    process_identifier_forbidden: bool
    process_material_forbidden: bool
    runtime_material_forbidden: bool
    command_material_forbidden: bool
    argument_material_forbidden: bool
    environment_material_forbidden: bool
    prompt_material_forbidden: bool
    model_material_forbidden: bool
    network_activity_forbidden: bool
    connector_activity_forbidden: bool
    mcp_activity_forbidden: bool
    provider_activity_forbidden: bool
    infrastructure_mutation_forbidden: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        expected = (
            code_owned_workflow_protected_runtime_process_resume_authorization_policy_values()
        )
        if any(getattr(self, name) != value for name, value in expected.items()):
            raise ValueError("runtime process resume authorization policy is not code-owned")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("runtime process resume authorization policy digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))

    @property
    def maximum_attestation_freshness_seconds(self) -> int:
        return WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_MAXIMUM_ATTESTATION_FRESHNESS_SECONDS


def code_owned_workflow_protected_runtime_process_resume_authorization_policy_values() -> dict[
    str, object
]:
    source = code_owned_workflow_protected_runtime_process_scheduling_consumption_policy()
    profile = {
        "profile_id": "profile.workflow-protected-runtime-process-resume-request",
        "profile_version": "1.0",
        "source_policy_digest": source.canonical_digest,
        "process_created_required": True,
        "process_sealed_required": True,
        "process_suspended_required": True,
        "process_scheduled_required": True,
        "process_runnable_required": False,
        "process_resumed_required": False,
        "process_dispatched_required": False,
        "process_executed_required": False,
        "metadata_only_attestation_required": True,
    }
    return {
        "policy_id": "policy.workflow-protected-runtime-process-resume-authorization",
        "policy_version": "1.0",
        "source_policy_id": source.policy_id,
        "source_policy_version": source.policy_version,
        "source_policy_digest": source.canonical_digest,
        "consumer_subject_id": source.consumer_subject_id,
        "consumer_audience": source.consumer_audience,
        "consumer_contract_id": source.consumer_contract_id,
        "consumer_contract_version": source.consumer_contract_version,
        "purpose_id": "purpose.workflow-protected-runtime-process-resume-request",
        "required_source_state": (
            WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState
        ).PROCESS_SCHEDULED_SUSPENDED_IN_PROTECTED_BOUNDARY.value,
        "resume_profile_id": cast(str, profile["profile_id"]),
        "resume_profile_version": cast(str, profile["profile_version"]),
        "resume_profile_digest": canonical_digest(profile),
        "maximum_lifetime_seconds": 1,
        "minimum_remaining_safety_margin_milliseconds": (
            WORKFLOW_PROTECTED_RUNTIME_PROCESS_RESUME_MINIMUM_REMAINING_SAFETY_MARGIN_MILLISECONDS
        ),
        "single_use_required": True,
        "renewable_allowed": False,
        "transferable_allowed": False,
        "bearer_capability_allowed": False,
        "durable_replay_required": True,
        "exact_replay_no_io_required": True,
        "fresh_attestation_required": True,
        "metadata_only_attestation_required": True,
        "process_created_required": True,
        "process_sealed_required": True,
        "process_suspended_required": True,
        "process_scheduled_required": True,
        "process_runnable_required": False,
        "process_resumed_required": False,
        "process_dispatched_required": False,
        "process_executed_required": False,
        "scheduling_forbidden": True,
        "resume_forbidden": True,
        "dispatch_forbidden": True,
        "execution_forbidden": True,
        "process_locator_forbidden": True,
        "process_identifier_forbidden": True,
        "process_material_forbidden": True,
        "runtime_material_forbidden": True,
        "command_material_forbidden": True,
        "argument_material_forbidden": True,
        "environment_material_forbidden": True,
        "prompt_material_forbidden": True,
        "model_material_forbidden": True,
        "network_activity_forbidden": True,
        "connector_activity_forbidden": True,
        "mcp_activity_forbidden": True,
        "provider_activity_forbidden": True,
        "infrastructure_mutation_forbidden": True,
    }


@lru_cache(maxsize=1)
def code_owned_workflow_protected_runtime_process_resume_authorization_policy() -> (
    WorkflowProtectedRuntimeProcessResumeAuthorizationPolicy
):
    values = code_owned_workflow_protected_runtime_process_resume_authorization_policy_values()
    return WorkflowProtectedRuntimeProcessResumeAuthorizationPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessResumeAuthorizationClaim:
    claim_id: str
    process_scheduling_result_id: str
    process_scheduling_result_digest: str
    process_scheduling_consumption_id: str
    process_scheduling_attempt_id: str
    process_scheduling_attempt_digest: str
    process_scheduling_claim_id: str
    process_scheduling_claim_digest: str
    process_scheduling_authorization_lease_id: str
    process_scheduling_authorization_lease_digest: str
    process_scheduling_authorization_claim_id: str
    process_scheduling_authorization_claim_digest: str
    process_scheduling_receipt_digest: str
    process_scheduling_result_state: WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState
    process_scheduling_failure_class: (
        WorkflowProtectedRuntimeProcessSchedulingConsumptionFailureClass | None
    )
    process_scheduling_outcome_known: bool
    process_created: bool
    process_sealed: bool
    process_suspended: bool
    process_scheduled: bool
    process_runnable: bool
    process_resumed: bool
    process_dispatched: bool
    process_executed: bool
    process_scheduling_completed_at: datetime
    process_scheduling_result_recorded_at: datetime
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    protected_slot_commitment: str
    protected_slot_generation: int
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
    process_scheduling_profile_id: str
    process_scheduling_profile_version: str
    process_scheduling_profile_digest: str
    primitive_id: str
    primitive_version: str
    primitive_digest: str
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
    authority: WorkflowProtectedRuntimeProcessResumeAuthorizationAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        _validate_source_snapshot(self)
        _require_identifiers(self, _CLAIM_IDENTIFIERS)
        _require_digests(self, _CLAIM_DIGESTS)
        if (
            self.claimed_at.tzinfo is None
            or self.claimed_at < self.process_scheduling_result_recorded_at
            or self.authority.protected_runtime_process_resume_authority_granted is not False
        ):
            raise ValueError("runtime process resume authorization claim is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessResumeAuthorizationLease:
    authorization_lease_id: str
    claim_id: str
    claim_digest: str
    process_scheduling_result_id: str
    process_scheduling_result_digest: str
    process_scheduling_consumption_id: str
    process_scheduling_attempt_id: str
    process_scheduling_attempt_digest: str
    process_scheduling_claim_id: str
    process_scheduling_claim_digest: str
    process_scheduling_authorization_lease_id: str
    process_scheduling_authorization_lease_digest: str
    process_scheduling_authorization_claim_id: str
    process_scheduling_authorization_claim_digest: str
    process_scheduling_receipt_digest: str
    process_scheduling_result_state: WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState
    process_scheduling_failure_class: (
        WorkflowProtectedRuntimeProcessSchedulingConsumptionFailureClass | None
    )
    process_scheduling_outcome_known: bool
    process_created: bool
    process_sealed: bool
    process_suspended: bool
    process_scheduled: bool
    process_runnable: bool
    process_resumed: bool
    process_dispatched: bool
    process_executed: bool
    process_scheduling_completed_at: datetime
    process_scheduling_result_recorded_at: datetime
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    protected_slot_commitment: str
    protected_slot_generation: int
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
    process_scheduling_profile_id: str
    process_scheduling_profile_version: str
    process_scheduling_profile_digest: str
    primitive_id: str
    primitive_version: str
    primitive_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    policy_id: str
    policy_version: str
    policy_digest: str
    process_state_attestation_id: str
    process_state_attestation_digest: str
    process_state_attestation_valid_until: datetime
    process_state_eligible_until: datetime
    attestation_metadata_only: bool
    resume_profile_id: str
    resume_profile_version: str
    resume_profile_digest: str
    issued_at: datetime
    valid_until: datetime
    effective_until: datetime
    single_use: bool
    renewable: bool
    transferable: bool
    lease_is_bearer_capability: bool
    state: WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseState
    authority: WorkflowProtectedRuntimeProcessResumeAuthorizationAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_process_resume_authorization_policy()
        _validate_source_snapshot(self)
        _require_identifiers(self, _LEASE_IDENTIFIERS)
        _require_digests(self, _LEASE_DIGESTS)
        if (
            any(
                value.tzinfo is None
                for value in (
                    self.process_state_attestation_valid_until,
                    self.process_state_eligible_until,
                    self.issued_at,
                    self.valid_until,
                    self.effective_until,
                )
            )
            or not self.process_scheduling_result_recorded_at <= self.issued_at < self.valid_until
            or self.valid_until - self.issued_at
            > timedelta(seconds=policy.maximum_lifetime_seconds)
            or self.valid_until != self.effective_until
            or self.effective_until > self.process_state_attestation_valid_until
            or self.effective_until > self.process_state_eligible_until
            or self.attestation_metadata_only is not policy.metadata_only_attestation_required
            or self.resume_profile_id != policy.resume_profile_id
            or self.resume_profile_version != policy.resume_profile_version
            or self.resume_profile_digest != policy.resume_profile_digest
            or self.single_use is not True
            or self.renewable is not False
            or self.transferable is not False
            or self.lease_is_bearer_capability is not False
            or self.state
            is not (
                WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseState
            ).AUTHORIZED_UNCONSUMED
            or self.authority.protected_runtime_process_resume_authority_granted is not True
        ):
            raise ValueError("runtime process resume authorization lease is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))

    def is_active(self, *, evaluated_at: datetime, consumed: bool = False) -> bool:
        if evaluated_at.tzinfo is None:
            raise ValueError("runtime process resume lease evaluation time must be aware")
        return not consumed and self.issued_at <= evaluated_at < self.valid_until

    def presented_authority(
        self, *, evaluated_at: datetime, consumed: bool = False
    ) -> WorkflowProtectedRuntimeProcessResumeAuthorizationAuthority:
        if self.is_active(evaluated_at=evaluated_at, consumed=consumed):
            return self.authority
        return WorkflowProtectedRuntimeProcessResumeAuthorizationAuthority()


def _validate_source_snapshot(
    instance: WorkflowProtectedRuntimeProcessResumeAuthorizationClaim
    | WorkflowProtectedRuntimeProcessResumeAuthorizationLease,
) -> None:
    policy = code_owned_workflow_protected_runtime_process_resume_authorization_policy()
    source_policy = code_owned_workflow_protected_runtime_process_scheduling_consumption_policy()
    authority = instance.authority.canonical_value()
    authority.pop("protected_runtime_process_resume_authority_granted")
    required_state = (
        WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState
    ).PROCESS_SCHEDULED_SUSPENDED_IN_PROTECTED_BOUNDARY
    if (
        instance.process_scheduling_result_state is not required_state
        or instance.process_scheduling_result_state.value != policy.required_source_state
        or instance.process_scheduling_failure_class is not None
        or instance.process_scheduling_outcome_known is not True
        or instance.process_created is not policy.process_created_required
        or instance.process_sealed is not policy.process_sealed_required
        or instance.process_suspended is not policy.process_suspended_required
        or instance.process_scheduled is not policy.process_scheduled_required
        or instance.process_runnable is not policy.process_runnable_required
        or instance.process_resumed is not policy.process_resumed_required
        or instance.process_dispatched is not policy.process_dispatched_required
        or instance.process_executed is not policy.process_executed_required
        or instance.destination_deployment_id != instance.scope.site_id
        or instance.destination_generation < 1
        or instance.destination_generation != instance.runtime_envelope_generation
        or instance.protected_slot_generation < 1
        or instance.runtime_envelope_generation != instance.protected_slot_generation
        or instance.destination_fencing_token_digest != instance.runtime_envelope_commitment
        or instance.protected_slot_commitment != instance.runtime_envelope_commitment
        or instance.process_scheduling_profile_id != source_policy.scheduling_profile_id
        or instance.process_scheduling_profile_version != source_policy.scheduling_profile_version
        or instance.process_scheduling_profile_digest != source_policy.scheduling_profile_digest
        or instance.primitive_id != source_policy.primitive_id
        or instance.primitive_version != source_policy.primitive_version
        or instance.primitive_digest != source_policy.primitive_digest
        or instance.consumer_subject_id != policy.consumer_subject_id
        or instance.consumer_audience != policy.consumer_audience
        or instance.consumer_contract_id != policy.consumer_contract_id
        or instance.consumer_contract_version != policy.consumer_contract_version
        or instance.purpose_id != policy.purpose_id
        or instance.policy_id != policy.policy_id
        or instance.policy_version != policy.policy_version
        or instance.policy_digest != policy.canonical_digest
        or instance.process_scheduling_completed_at.tzinfo is None
        or instance.process_scheduling_result_recorded_at.tzinfo is None
        or instance.process_scheduling_result_recorded_at < instance.process_scheduling_completed_at
        or any(authority.values())
    ):
        raise ValueError("runtime process resume authorization source is ineligible")


_SOURCE_IDENTIFIERS = (
    "process_scheduling_result_id",
    "process_scheduling_consumption_id",
    "process_scheduling_attempt_id",
    "process_scheduling_claim_id",
    "process_scheduling_authorization_lease_id",
    "process_scheduling_authorization_claim_id",
    "destination_deployment_id",
    "runtime_envelope_id",
    "process_scheduling_profile_id",
    "process_scheduling_profile_version",
    "primitive_id",
    "primitive_version",
    "consumer_subject_id",
    "consumer_audience",
    "consumer_contract_id",
    "consumer_contract_version",
    "purpose_id",
    "policy_id",
    "policy_version",
)
_SOURCE_DIGESTS = (
    "process_scheduling_result_digest",
    "process_scheduling_attempt_digest",
    "process_scheduling_claim_digest",
    "process_scheduling_authorization_lease_digest",
    "process_scheduling_authorization_claim_digest",
    "process_scheduling_receipt_digest",
    "destination_fencing_token_digest",
    "protected_slot_commitment",
    "runtime_envelope_commitment",
    "process_scheduling_profile_digest",
    "primitive_digest",
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
    "process_state_attestation_id",
    "resume_profile_id",
    "resume_profile_version",
)
_LEASE_DIGESTS = (
    "claim_digest",
    *_SOURCE_DIGESTS,
    "process_state_attestation_digest",
    "resume_profile_digest",
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
            raise ValueError(f"runtime process resume authorization {name} is invalid")


def _require_digests(instance: object, names: tuple[str, ...]) -> None:
    for name in names:
        value = getattr(instance, name)
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ValueError(f"runtime process resume authorization {name} is invalid")


def _require_canonical_digest(
    instance: WorkflowProtectedRuntimeProcessResumeAuthorizationClaim
    | WorkflowProtectedRuntimeProcessResumeAuthorizationLease,
) -> None:
    if instance.canonical_digest != canonical_digest(instance.digest_payload()):
        raise ValueError("runtime process resume authorization digest mismatch")


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
    "WorkflowProtectedRuntimeProcessResumeAuthorizationAuthority",
    "WorkflowProtectedRuntimeProcessResumeAuthorizationClaim",
    "WorkflowProtectedRuntimeProcessResumeAuthorizationLease",
    "WorkflowProtectedRuntimeProcessResumeAuthorizationLeaseState",
    "WorkflowProtectedRuntimeProcessResumeAuthorizationPolicy",
    "code_owned_workflow_protected_runtime_process_resume_authorization_policy",
    "code_owned_workflow_protected_runtime_process_resume_authorization_policy_values",
]
