from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum
from functools import lru_cache
from typing import Any, cast

from .models import WorkflowScope, canonical_digest
from .protected_runtime_process_scheduling_authorization_domain import (
    code_owned_workflow_protected_runtime_process_scheduling_authorization_policy,
)

WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_INSTRUCTION_SIGNING_KEY_ID = (
    "key.workflow-protected-runtime-process-scheduling-instruction.v1"
)
WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_INSTRUCTION_SIGNATURE_ALGORITHM = "hmac-sha256"


class WorkflowProtectedRuntimeProcessSchedulingConsumptionAttemptState(StrEnum):
    PROCESS_SCHEDULING_ATTEMPT_STARTED = "process_scheduling_attempt_started"


class WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState(StrEnum):
    PROCESS_SCHEDULED_SUSPENDED_IN_PROTECTED_BOUNDARY = (
        "process_scheduled_suspended_in_protected_boundary"
    )
    PROCESS_SCHEDULING_REJECTED_WITHOUT_SCHEDULING = (
        "process_scheduling_rejected_without_scheduling"
    )
    PROCESS_SCHEDULING_FAILED_WITHOUT_SCHEDULING = "process_scheduling_failed_without_scheduling"
    PROCESS_SCHEDULING_OUTCOME_UNCERTAIN = "process_scheduling_outcome_uncertain"


class WorkflowProtectedRuntimeProcessSchedulingConsumptionFailureClass(StrEnum):
    PROTECTED_SCHEDULER_REJECTED_WITHOUT_SCHEDULING = (
        "protected_scheduler_rejected_without_scheduling"
    )
    PROTECTED_SCHEDULER_FAILED_WITHOUT_SCHEDULING = "protected_scheduler_failed_without_scheduling"
    PROCESS_SCHEDULING_OUTCOME_UNCERTAIN = "process_scheduling_outcome_uncertain"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessSchedulingConsumptionAuthority:
    """Immutable historical evidence; consumption and results grant no authority."""

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

    def __post_init__(self) -> None:
        if any(self.canonical_value().values()):
            raise ValueError("process scheduling consumption grants no authority")

    def canonical_value(self) -> dict[str, bool]:
        return {field.name: cast(bool, getattr(self, field.name)) for field in fields(self)}


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessSchedulingConsumptionPolicy:
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
    scheduler_contract_id: str
    scheduler_contract_version: str
    approved_scheduler_id: str
    approved_scheduler_version: str
    instruction_signing_key_id: str
    receipt_verification_signing_key_id: str
    receipt_signature_algorithm: str
    scheduling_profile_id: str
    scheduling_profile_version: str
    scheduling_profile_digest: str
    primitive_id: str
    primitive_version: str
    primitive_digest: str
    minimum_invocation_margin_milliseconds: int
    claim_and_attempt_atomic_required: bool
    commit_before_scheduler_io_required: bool
    at_most_one_scheduler_call_required: bool
    automatic_retry_allowed: bool
    exact_replay_no_io_required: bool
    suspended_process_required: bool
    non_runnable_process_required: bool
    caller_process_material_forbidden: bool
    caller_runtime_material_forbidden: bool
    caller_command_material_forbidden: bool
    caller_scheduler_selection_forbidden: bool
    caller_queue_selection_forbidden: bool
    caller_priority_selection_forbidden: bool
    caller_affinity_selection_forbidden: bool
    caller_resource_selection_forbidden: bool
    resume_forbidden: bool
    dispatch_forbidden: bool
    execution_forbidden: bool
    network_activity_forbidden: bool
    model_activity_forbidden: bool
    mcp_activity_forbidden: bool
    connector_activity_forbidden: bool
    provider_activity_forbidden: bool
    infrastructure_mutation_forbidden: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        expected = (
            code_owned_workflow_protected_runtime_process_scheduling_consumption_policy_values()
        )
        if any(getattr(self, name) != value for name, value in expected.items()):
            raise ValueError("process scheduling consumption policy is not code-owned")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


def code_owned_workflow_protected_runtime_process_scheduling_consumption_policy_values() -> dict[
    str, object
]:
    source = code_owned_workflow_protected_runtime_process_scheduling_authorization_policy()
    primitive = {
        "primitive_id": "primitive.workflow-protected-runtime-schedule-sealed-suspended-process",
        "primitive_version": "1.0",
        "scheduling_profile_digest": source.scheduling_profile_digest,
        "process_resolution": "protected_boundary_internal",
        "process_locator_in_instruction": False,
        "process_identifier_in_instruction": False,
        "caller_scheduler_selection": False,
        "caller_queue_selection": False,
        "caller_priority_selection": False,
        "caller_affinity_selection": False,
        "caller_resource_selection": False,
        "resulting_state": "scheduled_suspended_non_runnable",
    }
    return {
        "policy_id": "policy.workflow-protected-runtime-process-scheduling-consumption",
        "policy_version": "1.0",
        "source_policy_id": source.policy_id,
        "source_policy_version": source.policy_version,
        "source_policy_digest": source.canonical_digest,
        "consumer_subject_id": source.consumer_subject_id,
        "consumer_audience": source.consumer_audience,
        "consumer_contract_id": source.consumer_contract_id,
        "consumer_contract_version": source.consumer_contract_version,
        "purpose_id": "purpose.workflow-protected-runtime-schedule-suspended-process",
        "required_source_state": "authorized_unconsumed",
        "scheduler_contract_id": "contract.workflow-protected-runtime-suspended-process-scheduler",
        "scheduler_contract_version": "1.0",
        "approved_scheduler_id": "scheduler.workflow-protected-runtime-suspended-process",
        "approved_scheduler_version": "1.0",
        "instruction_signing_key_id": (
            WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_INSTRUCTION_SIGNING_KEY_ID
        ),
        "receipt_verification_signing_key_id": (
            "key.workflow-protected-runtime-process-scheduling-receipt.v1"
        ),
        "receipt_signature_algorithm": "hmac-sha256",
        "scheduling_profile_id": source.scheduling_profile_id,
        "scheduling_profile_version": source.scheduling_profile_version,
        "scheduling_profile_digest": source.scheduling_profile_digest,
        "primitive_id": primitive["primitive_id"],
        "primitive_version": primitive["primitive_version"],
        "primitive_digest": canonical_digest(primitive),
        "minimum_invocation_margin_milliseconds": 100,
        "claim_and_attempt_atomic_required": True,
        "commit_before_scheduler_io_required": True,
        "at_most_one_scheduler_call_required": True,
        "automatic_retry_allowed": False,
        "exact_replay_no_io_required": True,
        "suspended_process_required": True,
        "non_runnable_process_required": True,
        "caller_process_material_forbidden": True,
        "caller_runtime_material_forbidden": True,
        "caller_command_material_forbidden": True,
        "caller_scheduler_selection_forbidden": True,
        "caller_queue_selection_forbidden": True,
        "caller_priority_selection_forbidden": True,
        "caller_affinity_selection_forbidden": True,
        "caller_resource_selection_forbidden": True,
        "resume_forbidden": True,
        "dispatch_forbidden": True,
        "execution_forbidden": True,
        "network_activity_forbidden": True,
        "model_activity_forbidden": True,
        "mcp_activity_forbidden": True,
        "connector_activity_forbidden": True,
        "provider_activity_forbidden": True,
        "infrastructure_mutation_forbidden": True,
    }


@lru_cache(maxsize=1)
def code_owned_workflow_protected_runtime_process_scheduling_consumption_policy() -> (
    WorkflowProtectedRuntimeProcessSchedulingConsumptionPolicy
):
    values = code_owned_workflow_protected_runtime_process_scheduling_consumption_policy_values()
    return WorkflowProtectedRuntimeProcessSchedulingConsumptionPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessSchedulingConsumptionClaim:
    claim_id: str
    consumption_id: str
    attempt_id: str
    authorization_lease_id: str
    authorization_lease_digest: str
    authorization_claim_id: str
    authorization_claim_digest: str
    scheduling_profile_id: str
    scheduling_profile_version: str
    scheduling_profile_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    policy_id: str
    policy_version: str
    policy_digest: str
    idempotency_digest: str
    request_fingerprint: str
    claimed_at: datetime
    authority: WorkflowProtectedRuntimeProcessSchedulingConsumptionAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_process_scheduling_consumption_policy()
        _require_identifiers(self, _CLAIM_IDENTIFIERS)
        _require_digests(self, _CLAIM_DIGESTS)
        if self.claimed_at.tzinfo is None or not _matches_policy(self, policy):
            raise ValueError("process scheduling consumption claim is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessSchedulingAttempt:
    attempt_id: str
    consumption_id: str
    claim_id: str
    claim_digest: str
    authorization_lease_id: str
    authorization_lease_digest: str
    protected_operation_reference: str
    scheduling_profile_id: str
    scheduling_profile_version: str
    scheduling_profile_digest: str
    primitive_id: str
    primitive_version: str
    primitive_digest: str
    scheduler_contract_id: str
    scheduler_contract_version: str
    scheduler_id: str
    scheduler_version: str
    receipt_verification_signing_key_id: str
    request_nonce_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    policy_id: str
    policy_version: str
    policy_digest: str
    started_at: datetime
    invocation_deadline: datetime
    state: WorkflowProtectedRuntimeProcessSchedulingConsumptionAttemptState
    authority: WorkflowProtectedRuntimeProcessSchedulingConsumptionAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_process_scheduling_consumption_policy()
        _require_identifiers(self, _ATTEMPT_IDENTIFIERS)
        _require_digests(self, _ATTEMPT_DIGESTS)
        if (
            self.started_at.tzinfo is None
            or self.invocation_deadline.tzinfo is None
            or not self.started_at < self.invocation_deadline
            or self.state
            is not (
                WorkflowProtectedRuntimeProcessSchedulingConsumptionAttemptState
            ).PROCESS_SCHEDULING_ATTEMPT_STARTED
            or not _matches_policy(self, policy)
            or self.primitive_id != policy.primitive_id
            or self.primitive_version != policy.primitive_version
            or self.primitive_digest != policy.primitive_digest
            or self.scheduler_contract_id != policy.scheduler_contract_id
            or self.scheduler_contract_version != policy.scheduler_contract_version
            or self.scheduler_id != policy.approved_scheduler_id
            or self.scheduler_version != policy.approved_scheduler_version
            or self.receipt_verification_signing_key_id
            != policy.receipt_verification_signing_key_id
        ):
            raise ValueError("protected process scheduling attempt is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessSchedulingInstruction:
    consumption_id: str
    attempt_id: str
    attempt_digest: str
    claim_id: str
    claim_digest: str
    authorization_lease_id: str
    authorization_lease_digest: str
    protected_operation_reference: str
    scheduling_profile_id: str
    scheduling_profile_version: str
    scheduling_profile_digest: str
    primitive_id: str
    primitive_version: str
    primitive_digest: str
    scheduler_contract_id: str
    scheduler_contract_version: str
    scheduler_id: str
    scheduler_version: str
    request_nonce_digest: str
    scope: WorkflowScope
    policy_id: str
    policy_version: str
    policy_digest: str
    started_at: datetime
    invocation_deadline: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_process_scheduling_consumption_policy()
        _require_identifiers(self, _INSTRUCTION_IDENTIFIERS)
        _require_digests(self, _INSTRUCTION_DIGESTS)
        if (
            self.started_at.tzinfo is None
            or self.invocation_deadline.tzinfo is None
            or not self.started_at < self.invocation_deadline
            or self.policy_id != policy.policy_id
            or self.policy_version != policy.policy_version
            or self.policy_digest != policy.canonical_digest
            or self.scheduling_profile_digest != policy.scheduling_profile_digest
            or self.primitive_digest != policy.primitive_digest
            or self.scheduler_id != policy.approved_scheduler_id
        ):
            raise ValueError("protected process scheduling instruction is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessSchedulingSignedInstructionEnvelope:
    instruction: WorkflowProtectedRuntimeProcessSchedulingInstruction
    signing_key_id: str
    signature_algorithm: str
    integrity_signature: str
    canonical_digest: str

    def __post_init__(self) -> None:
        _require_identifiers(self, ("signing_key_id", "signature_algorithm"))
        _require_digests(self, ("integrity_signature", "canonical_digest"))
        if (
            self.signing_key_id
            != WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_INSTRUCTION_SIGNING_KEY_ID
            or self.signature_algorithm
            != WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_INSTRUCTION_SIGNATURE_ALGORITHM
        ):
            raise ValueError("process scheduling instruction envelope is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessSchedulingInvocation:
    protected_operation_reference: str
    instruction_digest: str
    invocation_deadline: datetime
    signed_instruction_envelope: WorkflowProtectedRuntimeProcessSchedulingSignedInstructionEnvelope

    def __post_init__(self) -> None:
        _require_identifier(self.protected_operation_reference, "protected_operation_reference")
        _require_digest(self.instruction_digest, "instruction_digest")
        instruction = self.signed_instruction_envelope.instruction
        if (
            self.invocation_deadline.tzinfo is None
            or self.instruction_digest != instruction.canonical_digest
            or self.invocation_deadline != instruction.invocation_deadline
        ):
            raise ValueError("process scheduling invocation is invalid")


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessSchedulingReceipt:
    consumption_id: str
    attempt_id: str
    instruction_digest: str
    protected_operation_reference: str
    authorization_lease_id: str
    scheduling_profile_id: str
    scheduling_profile_version: str
    scheduling_profile_digest: str
    primitive_id: str
    primitive_version: str
    primitive_digest: str
    request_nonce_digest: str
    result_state: WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState
    process_scheduled: bool
    process_suspended: bool
    process_runnable: bool
    process_resumed: bool
    process_dispatched: bool
    process_executed: bool
    caller_material_used: bool
    process_locator_returned: bool
    process_identifier_returned: bool
    queue_or_priority_returned: bool
    network_activity_performed: bool
    model_activity_performed: bool
    mcp_activity_performed: bool
    connector_activity_performed: bool
    provider_activity_performed: bool
    infrastructure_mutation_performed: bool
    scheduler_contract_id: str
    scheduler_contract_version: str
    scheduler_id: str
    scheduler_version: str
    signing_key_id: str
    signature_algorithm: str
    completed_at: datetime
    integrity_signature: str
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_process_scheduling_consumption_policy()
        _require_identifiers(self, _RECEIPT_IDENTIFIERS)
        _require_digests(self, _RECEIPT_DIGESTS)
        success_state = (
            WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState
        ).PROCESS_SCHEDULED_SUSPENDED_IN_PROTECTED_BOUNDARY
        success = self.result_state is success_state
        known_no_schedule = self.result_state in {
            WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState.PROCESS_SCHEDULING_REJECTED_WITHOUT_SCHEDULING,
            WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState.PROCESS_SCHEDULING_FAILED_WITHOUT_SCHEDULING,
        }
        forbidden = (
            self.process_runnable,
            self.process_resumed,
            self.process_dispatched,
            self.process_executed,
            self.caller_material_used,
            self.process_locator_returned,
            self.process_identifier_returned,
            self.queue_or_priority_returned,
            self.network_activity_performed,
            self.model_activity_performed,
            self.mcp_activity_performed,
            self.connector_activity_performed,
            self.provider_activity_performed,
            self.infrastructure_mutation_performed,
        )
        if (
            self.completed_at.tzinfo is None
            or any(forbidden)
            or self.process_scheduled is not success
            or self.process_suspended is not True
            or (not success and not known_no_schedule)
            or self.scheduler_contract_id != policy.scheduler_contract_id
            or self.scheduler_contract_version != policy.scheduler_contract_version
            or self.scheduler_id != policy.approved_scheduler_id
            or self.scheduler_version != policy.approved_scheduler_version
            or self.signing_key_id != policy.receipt_verification_signing_key_id
            or self.signature_algorithm != policy.receipt_signature_algorithm
        ):
            raise ValueError("process scheduling receipt is invalid")
        _require_canonical_digest(self)

    def signature_payload(self) -> dict[str, object]:
        return {
            name: value
            for name, value in self.digest_payload().items()
            if name != "integrity_signature"
        }

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessSchedulingResult:
    result_id: str
    consumption_id: str
    attempt_id: str
    attempt_digest: str
    claim_id: str
    claim_digest: str
    authorization_lease_id: str
    authorization_lease_digest: str
    receipt_digest: str | None
    result_state: WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState
    failure_class: WorkflowProtectedRuntimeProcessSchedulingConsumptionFailureClass | None
    outcome_known: bool
    process_scheduled: bool | None
    process_suspended: bool | None
    process_runnable: bool | None
    process_resumed: bool
    process_dispatched: bool
    process_executed: bool
    scheduling_profile_id: str
    scheduling_profile_version: str
    scheduling_profile_digest: str
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
    completed_at: datetime
    recorded_at: datetime
    authority: WorkflowProtectedRuntimeProcessSchedulingConsumptionAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_process_scheduling_consumption_policy()
        _require_identifiers(self, _RESULT_IDENTIFIERS)
        _require_digests(self, _RESULT_DIGESTS)
        states = WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState
        success = self.result_state is states.PROCESS_SCHEDULED_SUSPENDED_IN_PROTECTED_BOUNDARY
        uncertain = self.result_state is states.PROCESS_SCHEDULING_OUTCOME_UNCERTAIN
        state_values = (self.process_scheduled, self.process_suspended, self.process_runnable)
        if (
            self.completed_at.tzinfo is None
            or self.recorded_at.tzinfo is None
            or self.recorded_at < self.completed_at
            or (uncertain and any(value is not None for value in state_values))
            or (
                not uncertain
                and (
                    self.process_scheduled is not success
                    or self.process_suspended is not True
                    or self.process_runnable is not False
                )
            )
            or self.process_resumed
            or self.process_dispatched
            or self.process_executed
            or self.outcome_known is uncertain
            or (uncertain and self.receipt_digest is not None)
            or (not uncertain and self.receipt_digest is None)
            or (success and self.failure_class is not None)
            or (not success and self.failure_class is None)
            or not _matches_policy(self, policy)
        ):
            raise ValueError("process scheduling result is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


def _matches_policy(
    instance: object, policy: WorkflowProtectedRuntimeProcessSchedulingConsumptionPolicy
) -> bool:
    return all(
        getattr(instance, name) == expected
        for name, expected in (
            ("consumer_subject_id", policy.consumer_subject_id),
            ("consumer_audience", policy.consumer_audience),
            ("consumer_contract_id", policy.consumer_contract_id),
            ("consumer_contract_version", policy.consumer_contract_version),
            ("purpose_id", policy.purpose_id),
            ("policy_id", policy.policy_id),
            ("policy_version", policy.policy_version),
            ("policy_digest", policy.canonical_digest),
            ("scheduling_profile_id", policy.scheduling_profile_id),
            ("scheduling_profile_version", policy.scheduling_profile_version),
            ("scheduling_profile_digest", policy.scheduling_profile_digest),
        )
    )


def _require_identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ValueError(f"{name} is invalid")


def _require_identifiers(instance: object, names: tuple[str, ...]) -> None:
    for name in names:
        _require_identifier(cast(str, getattr(instance, name)), name)


def _require_digest(value: str, name: str) -> None:
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError(f"{name} is invalid")
    try:
        int(value, 16)
    except ValueError as exc:
        raise ValueError(f"{name} is invalid") from exc


def _require_digests(instance: object, names: tuple[str, ...]) -> None:
    for name in names:
        value = getattr(instance, name)
        if value is not None:
            _require_digest(cast(str, value), name)


def _require_canonical_digest(instance: Any) -> None:
    if instance.canonical_digest != canonical_digest(instance.digest_payload()):
        raise ValueError("canonical digest mismatch")


def _payload(instance: object, *, exclude: tuple[str, ...] = ()) -> dict[str, object]:
    return {
        field.name: _canonical_value(getattr(instance, field.name))
        for field in fields(cast(Any, instance))
        if field.name not in exclude
    }


def _canonical_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if hasattr(value, "canonical_value"):
        return value.canonical_value()
    if hasattr(value, "digest_payload") and hasattr(value, "canonical_digest"):
        return value.digest_payload() | {"canonical_digest": value.canonical_digest}
    return value


_COMMON_IDENTIFIERS = (
    "authorization_lease_id",
    "scheduling_profile_id",
    "scheduling_profile_version",
    "consumer_subject_id",
    "consumer_audience",
    "consumer_contract_id",
    "consumer_contract_version",
    "purpose_id",
    "policy_id",
    "policy_version",
)
_COMMON_DIGESTS = (
    "authorization_lease_digest",
    "scheduling_profile_digest",
    "policy_digest",
)
_CLAIM_IDENTIFIERS = (
    "claim_id",
    "consumption_id",
    "attempt_id",
    "authorization_claim_id",
    *_COMMON_IDENTIFIERS,
)
_CLAIM_DIGESTS = (
    "authorization_claim_digest",
    "idempotency_digest",
    "request_fingerprint",
    "canonical_digest",
    *_COMMON_DIGESTS,
)
_ATTEMPT_IDENTIFIERS = (
    "attempt_id",
    "consumption_id",
    "claim_id",
    "protected_operation_reference",
    "primitive_id",
    "primitive_version",
    "scheduler_contract_id",
    "scheduler_contract_version",
    "scheduler_id",
    "scheduler_version",
    "receipt_verification_signing_key_id",
    *_COMMON_IDENTIFIERS,
)
_ATTEMPT_DIGESTS = (
    "claim_digest",
    "primitive_digest",
    "request_nonce_digest",
    "canonical_digest",
    *_COMMON_DIGESTS,
)
_INSTRUCTION_IDENTIFIERS = (
    "consumption_id",
    "attempt_id",
    "claim_id",
    "authorization_lease_id",
    "protected_operation_reference",
    "scheduling_profile_id",
    "scheduling_profile_version",
    "primitive_id",
    "primitive_version",
    "scheduler_contract_id",
    "scheduler_contract_version",
    "scheduler_id",
    "scheduler_version",
    "policy_id",
    "policy_version",
)
_INSTRUCTION_DIGESTS = (
    "attempt_digest",
    "claim_digest",
    "authorization_lease_digest",
    "scheduling_profile_digest",
    "primitive_digest",
    "request_nonce_digest",
    "policy_digest",
    "canonical_digest",
)
_RECEIPT_IDENTIFIERS = (
    "consumption_id",
    "attempt_id",
    "protected_operation_reference",
    "authorization_lease_id",
    "scheduling_profile_id",
    "scheduling_profile_version",
    "primitive_id",
    "primitive_version",
    "scheduler_contract_id",
    "scheduler_contract_version",
    "scheduler_id",
    "scheduler_version",
    "signing_key_id",
    "signature_algorithm",
)
_RECEIPT_DIGESTS = (
    "instruction_digest",
    "scheduling_profile_digest",
    "primitive_digest",
    "request_nonce_digest",
    "integrity_signature",
    "canonical_digest",
)
_RESULT_IDENTIFIERS = (
    "result_id",
    "consumption_id",
    "attempt_id",
    "claim_id",
    "primitive_id",
    "primitive_version",
    *_COMMON_IDENTIFIERS,
)
_RESULT_DIGESTS = (
    "attempt_digest",
    "claim_digest",
    "receipt_digest",
    "primitive_digest",
    "canonical_digest",
    *_COMMON_DIGESTS,
)


__all__ = [
    "WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_INSTRUCTION_SIGNATURE_ALGORITHM",
    "WORKFLOW_PROTECTED_RUNTIME_PROCESS_SCHEDULING_INSTRUCTION_SIGNING_KEY_ID",
    "WorkflowProtectedRuntimeProcessSchedulingAttempt",
    "WorkflowProtectedRuntimeProcessSchedulingConsumptionAttemptState",
    "WorkflowProtectedRuntimeProcessSchedulingConsumptionAuthority",
    "WorkflowProtectedRuntimeProcessSchedulingConsumptionClaim",
    "WorkflowProtectedRuntimeProcessSchedulingConsumptionFailureClass",
    "WorkflowProtectedRuntimeProcessSchedulingConsumptionPolicy",
    "WorkflowProtectedRuntimeProcessSchedulingConsumptionResultState",
    "WorkflowProtectedRuntimeProcessSchedulingInstruction",
    "WorkflowProtectedRuntimeProcessSchedulingInvocation",
    "WorkflowProtectedRuntimeProcessSchedulingReceipt",
    "WorkflowProtectedRuntimeProcessSchedulingResult",
    "WorkflowProtectedRuntimeProcessSchedulingSignedInstructionEnvelope",
    "code_owned_workflow_protected_runtime_process_scheduling_consumption_policy",
    "code_owned_workflow_protected_runtime_process_scheduling_consumption_policy_values",
]
