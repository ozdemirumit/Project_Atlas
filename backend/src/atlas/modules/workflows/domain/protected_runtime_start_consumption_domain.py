from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum
from functools import lru_cache
from typing import Any, cast

from .models import WorkflowScope, canonical_digest
from .protected_runtime_start_authorization_domain import (
    code_owned_workflow_protected_runtime_start_authorization_policy,
)

WORKFLOW_PROTECTED_RUNTIME_START_INSTRUCTION_SIGNING_KEY_ID = (
    "key.workflow-protected-runtime-start-instruction.v1"
)
WORKFLOW_PROTECTED_RUNTIME_START_INSTRUCTION_SIGNATURE_ALGORITHM = "hmac-sha256"


class WorkflowProtectedRuntimeStartConsumptionAttemptState(StrEnum):
    RUNTIME_START_ATTEMPT_STARTED = "runtime_start_attempt_started"


class WorkflowProtectedRuntimeStartConsumptionResultState(StrEnum):
    RUNTIME_STARTED_IN_PROTECTED_BOUNDARY = "runtime_started_in_protected_boundary"
    RUNTIME_START_FAILED_WITHOUT_START = "runtime_start_failed_without_start"
    RUNTIME_START_OUTCOME_UNCERTAIN = "runtime_start_outcome_uncertain"


class WorkflowProtectedRuntimeStartConsumptionFailureClass(StrEnum):
    PROTECTED_STARTER_REJECTED_WITHOUT_START = "protected_starter_rejected_without_start"
    PROTECTED_COMPARE_AND_SWAP_REJECTED = "protected_compare_and_swap_rejected"
    RUNTIME_START_OUTCOME_UNCERTAIN = "runtime_start_outcome_uncertain"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartConsumptionAuthority:
    """Historical evidence with all twenty-seven authority declarations false."""

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
        if any(self.canonical_value().values()):
            raise ValueError("protected runtime start consumption grants no authority")

    def canonical_value(self) -> dict[str, bool]:
        return {field.name: cast(bool, getattr(self, field.name)) for field in fields(self)}


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartConsumptionPolicy:
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
    required_starter_contract_id: str
    required_starter_contract_version: str
    approved_starter_id: str
    approved_starter_version: str
    instruction_signing_key_id: str
    receipt_verification_signing_key_id: str
    receipt_signature_algorithm: str
    runtime_start_profile_id: str
    runtime_start_profile_version: str
    runtime_start_profile_digest: str
    minimum_invocation_margin_milliseconds: int
    irreversible_consumption_acknowledgement_required: bool
    uncertainty_no_retry_acknowledgement_required: bool
    durable_replay_required: bool
    claim_and_attempt_atomic_required: bool
    commit_before_starter_io_required: bool
    at_most_one_starter_call_required: bool
    automatic_retry_allowed: bool
    runtime_resume_forbidden: bool
    generic_process_creation_forbidden: bool
    scheduling_forbidden: bool
    prompt_construction_forbidden: bool
    model_inference_forbidden: bool
    network_activity_forbidden: bool
    connector_activity_forbidden: bool
    dispatch_forbidden: bool
    execution_forbidden: bool
    infrastructure_mutation_forbidden: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        expected = code_owned_workflow_protected_runtime_start_consumption_policy_values()
        if any(getattr(self, name) != value for name, value in expected.items()):
            raise ValueError("protected runtime start consumption policy is not code-owned")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


def code_owned_workflow_protected_runtime_start_consumption_policy_values() -> dict[str, object]:
    source = code_owned_workflow_protected_runtime_start_authorization_policy()
    return {
        "policy_id": "policy.workflow-protected-runtime-start",
        "policy_version": "1.0",
        "source_policy_id": source.policy_id,
        "source_policy_version": source.policy_version,
        "source_policy_digest": source.canonical_digest,
        "consumer_subject_id": source.consumer_subject_id,
        "consumer_audience": source.consumer_audience,
        "consumer_contract_id": source.consumer_contract_id,
        "consumer_contract_version": source.consumer_contract_version,
        "purpose_id": "purpose.workflow-protected-runtime-start",
        "required_source_state": "authorized_unconsumed",
        "required_starter_contract_id": "contract.workflow-protected-runtime-start-executor",
        "required_starter_contract_version": "1.0",
        "approved_starter_id": "executor.workflow-protected-runtime-start",
        "approved_starter_version": "1.0",
        "instruction_signing_key_id": (WORKFLOW_PROTECTED_RUNTIME_START_INSTRUCTION_SIGNING_KEY_ID),
        "receipt_verification_signing_key_id": ("key.workflow-protected-runtime-start-receipt.v1"),
        "receipt_signature_algorithm": "hmac-sha256",
        "runtime_start_profile_id": source.runtime_start_profile_id,
        "runtime_start_profile_version": source.runtime_start_profile_version,
        "runtime_start_profile_digest": source.runtime_start_profile_digest,
        "minimum_invocation_margin_milliseconds": 100,
        "irreversible_consumption_acknowledgement_required": True,
        "uncertainty_no_retry_acknowledgement_required": True,
        "durable_replay_required": True,
        "claim_and_attempt_atomic_required": True,
        "commit_before_starter_io_required": True,
        "at_most_one_starter_call_required": True,
        "automatic_retry_allowed": False,
        "runtime_resume_forbidden": True,
        "generic_process_creation_forbidden": True,
        "scheduling_forbidden": True,
        "prompt_construction_forbidden": True,
        "model_inference_forbidden": True,
        "network_activity_forbidden": True,
        "connector_activity_forbidden": True,
        "dispatch_forbidden": True,
        "execution_forbidden": True,
        "infrastructure_mutation_forbidden": True,
    }


@lru_cache(maxsize=1)
def code_owned_workflow_protected_runtime_start_consumption_policy() -> (
    WorkflowProtectedRuntimeStartConsumptionPolicy
):
    values = code_owned_workflow_protected_runtime_start_consumption_policy_values()
    return WorkflowProtectedRuntimeStartConsumptionPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartConsumptionClaim:
    claim_id: str
    consumption_id: str
    attempt_id: str
    authorization_lease_id: str
    authorization_lease_digest: str
    authorization_claim_id: str
    authorization_claim_digest: str
    use_result_id: str
    use_result_digest: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_slot_commitment: str
    runtime_slot_generation: int
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
    idempotency_digest: str
    request_fingerprint: str
    irreversible_consumption_acknowledged: bool
    uncertainty_no_retry_acknowledged: bool
    claimed_at: datetime
    authority: WorkflowProtectedRuntimeStartConsumptionAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_start_consumption_policy()
        _require_identifiers(self, _CLAIM_IDENTIFIERS)
        _require_digests(self, _CLAIM_DIGESTS)
        if (
            self.destination_generation < 1
            or self.runtime_slot_generation < 1
            or self.runtime_envelope_generation < 1
            or self.runtime_envelope_generation != self.runtime_slot_generation
            or self.claimed_at.tzinfo is None
            or not self.irreversible_consumption_acknowledged
            or not self.uncertainty_no_retry_acknowledged
            or not _matches_policy(self, policy)
        ):
            raise ValueError("protected runtime start consumption claim is invalid")
        _require_zero_authority(self.authority)
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartConsumptionAttempt:
    attempt_id: str
    consumption_id: str
    claim_id: str
    claim_digest: str
    authorization_lease_id: str
    authorization_lease_digest: str
    authorization_claim_id: str
    authorization_claim_digest: str
    use_result_id: str
    use_result_digest: str
    protected_operation_reference: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_slot_commitment: str
    runtime_slot_generation: int
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
    expected_start_count_pre: int
    expected_start_count_post: int
    runtime_start_profile_id: str
    runtime_start_profile_version: str
    runtime_start_profile_digest: str
    starter_contract_id: str
    starter_contract_version: str
    starter_id: str
    starter_version: str
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
    state: WorkflowProtectedRuntimeStartConsumptionAttemptState
    authority: WorkflowProtectedRuntimeStartConsumptionAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_start_consumption_policy()
        _require_identifiers(self, _ATTEMPT_IDENTIFIERS)
        _require_digests(self, _ATTEMPT_DIGESTS)
        if (
            self.destination_generation < 1
            or self.runtime_slot_generation < 1
            or self.runtime_envelope_generation != self.runtime_slot_generation
            or self.expected_start_count_pre != 0
            or self.expected_start_count_post != 1
            or self.started_at.tzinfo is None
            or self.invocation_deadline.tzinfo is None
            or not self.started_at < self.invocation_deadline
            or self.state
            is not (
                WorkflowProtectedRuntimeStartConsumptionAttemptState
            ).RUNTIME_START_ATTEMPT_STARTED
            or not _matches_policy(self, policy)
            or self.starter_contract_id != policy.required_starter_contract_id
            or self.starter_contract_version != policy.required_starter_contract_version
            or self.starter_id != policy.approved_starter_id
            or self.starter_version != policy.approved_starter_version
            or self.receipt_verification_signing_key_id
            != policy.receipt_verification_signing_key_id
        ):
            raise ValueError("protected runtime start attempt is invalid")
        _require_zero_authority(self.authority)
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartInstruction:
    consumption_id: str
    attempt_id: str
    attempt_digest: str
    claim_id: str
    claim_digest: str
    authorization_lease_id: str
    authorization_lease_digest: str
    protected_operation_reference: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_slot_commitment: str
    runtime_slot_generation: int
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
    expected_start_count_pre: int
    expected_start_count_post: int
    runtime_start_profile_id: str
    runtime_start_profile_version: str
    runtime_start_profile_digest: str
    starter_contract_id: str
    starter_contract_version: str
    starter_id: str
    starter_version: str
    request_nonce_digest: str
    scope: WorkflowScope
    policy_id: str
    policy_version: str
    policy_digest: str
    started_at: datetime
    invocation_deadline: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_start_consumption_policy()
        _require_identifiers(self, _INSTRUCTION_IDENTIFIERS)
        _require_digests(self, _INSTRUCTION_DIGESTS)
        if (
            self.destination_generation < 1
            or self.runtime_slot_generation < 1
            or self.runtime_envelope_generation != self.runtime_slot_generation
            or self.expected_start_count_pre != 0
            or self.expected_start_count_post != 1
            or self.started_at.tzinfo is None
            or self.invocation_deadline.tzinfo is None
            or not self.started_at < self.invocation_deadline
            or self.policy_id != policy.policy_id
            or self.policy_version != policy.policy_version
            or self.policy_digest != policy.canonical_digest
            or self.runtime_start_profile_id != policy.runtime_start_profile_id
            or self.runtime_start_profile_version != policy.runtime_start_profile_version
            or self.runtime_start_profile_digest != policy.runtime_start_profile_digest
            or self.starter_contract_id != policy.required_starter_contract_id
            or self.starter_contract_version != policy.required_starter_contract_version
            or self.starter_id != policy.approved_starter_id
            or self.starter_version != policy.approved_starter_version
        ):
            raise ValueError("protected runtime start instruction is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartSignedInstructionEnvelope:
    instruction: WorkflowProtectedRuntimeStartInstruction
    signing_key_id: str
    signature_algorithm: str
    integrity_signature: str
    canonical_digest: str

    def __post_init__(self) -> None:
        _require_identifiers(self, ("signing_key_id", "signature_algorithm"))
        _require_digests(self, ("integrity_signature", "canonical_digest"))
        if (
            self.signing_key_id != WORKFLOW_PROTECTED_RUNTIME_START_INSTRUCTION_SIGNING_KEY_ID
            or self.signature_algorithm
            != WORKFLOW_PROTECTED_RUNTIME_START_INSTRUCTION_SIGNATURE_ALGORITHM
        ):
            raise ValueError("protected runtime start instruction envelope is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartInvocation:
    protected_operation_reference: str
    instruction_digest: str
    invocation_deadline: datetime
    signed_instruction_envelope: WorkflowProtectedRuntimeStartSignedInstructionEnvelope

    def __post_init__(self) -> None:
        _require_identifier(self.protected_operation_reference, "protected_operation_reference")
        _require_digest(self.instruction_digest, "instruction_digest")
        if (
            self.invocation_deadline.tzinfo is None
            or self.instruction_digest
            != self.signed_instruction_envelope.instruction.canonical_digest
            or self.invocation_deadline
            != self.signed_instruction_envelope.instruction.invocation_deadline
        ):
            raise ValueError("protected runtime start invocation is invalid")


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeStartReceipt:
    consumption_id: str
    attempt_id: str
    instruction_digest: str
    protected_operation_reference: str
    authorization_lease_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_slot_commitment: str
    runtime_slot_generation: int
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
    request_nonce_digest: str
    result_state: WorkflowProtectedRuntimeStartConsumptionResultState
    runtime_started: bool
    runtime_start_count_pre: int
    runtime_start_count_post: int
    runtime_envelope_current: bool
    runtime_envelope_inactive: bool
    residual_process_absent: bool
    residual_task_absent: bool
    scheduling_performed: bool
    runtime_resumed: bool
    generic_process_created: bool
    prompt_constructed: bool
    model_inference_performed: bool
    network_activity_performed: bool
    readiness_probe_performed: bool
    publication_performed: bool
    delivery_performed: bool
    connector_activity_performed: bool
    dispatch_performed: bool
    execution_performed: bool
    infrastructure_mutation_performed: bool
    starter_contract_id: str
    starter_contract_version: str
    starter_id: str
    starter_version: str
    signing_key_id: str
    signature_algorithm: str
    completed_at: datetime
    integrity_signature: str
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_start_consumption_policy()
        _require_identifiers(self, _RECEIPT_IDENTIFIERS)
        _require_digests(self, _RECEIPT_DIGESTS)
        forbidden = (
            self.scheduling_performed,
            self.runtime_resumed,
            self.generic_process_created,
            self.prompt_constructed,
            self.model_inference_performed,
            self.network_activity_performed,
            self.readiness_probe_performed,
            self.publication_performed,
            self.delivery_performed,
            self.connector_activity_performed,
            self.dispatch_performed,
            self.execution_performed,
            self.infrastructure_mutation_performed,
        )
        success = (
            self.result_state
            is (
                WorkflowProtectedRuntimeStartConsumptionResultState
            ).RUNTIME_STARTED_IN_PROTECTED_BOUNDARY
            and self.runtime_started
            and self.runtime_start_count_pre == 0
            and self.runtime_start_count_post == 1
            and self.runtime_envelope_current
            and not self.runtime_envelope_inactive
        )
        no_effect = (
            self.result_state
            is (
                WorkflowProtectedRuntimeStartConsumptionResultState
            ).RUNTIME_START_FAILED_WITHOUT_START
            and not self.runtime_started
            and self.runtime_start_count_pre == 0
            and self.runtime_start_count_post == 0
            and self.runtime_envelope_current
            and self.runtime_envelope_inactive
            and self.residual_process_absent
            and self.residual_task_absent
        )
        if (
            self.destination_generation < 1
            or self.runtime_slot_generation < 1
            or self.runtime_envelope_generation != self.runtime_slot_generation
            or self.completed_at.tzinfo is None
            or any(forbidden)
            or not (success or no_effect)
            or self.starter_contract_id != policy.required_starter_contract_id
            or self.starter_contract_version != policy.required_starter_contract_version
            or self.starter_id != policy.approved_starter_id
            or self.starter_version != policy.approved_starter_version
            or self.signing_key_id != policy.receipt_verification_signing_key_id
            or self.signature_algorithm != policy.receipt_signature_algorithm
        ):
            raise ValueError("protected runtime start receipt is invalid")
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
class WorkflowProtectedRuntimeStartConsumptionResult:
    result_id: str
    consumption_id: str
    attempt_id: str
    attempt_digest: str
    claim_id: str
    claim_digest: str
    authorization_lease_id: str
    authorization_lease_digest: str
    runtime_start_profile_id: str
    runtime_start_profile_version: str
    runtime_start_profile_digest: str
    destination_deployment_id: str
    destination_generation: int
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
    state: WorkflowProtectedRuntimeStartConsumptionResultState
    failure_class: WorkflowProtectedRuntimeStartConsumptionFailureClass | None
    outcome_known: bool
    runtime_started: bool | None
    starter_receipt_digest: str | None
    completed_at: datetime | None
    recorded_at: datetime
    scope: WorkflowScope
    policy_id: str
    policy_version: str
    policy_digest: str
    authority: WorkflowProtectedRuntimeStartConsumptionAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_start_consumption_policy()
        _require_identifiers(self, _RESULT_IDENTIFIERS)
        _require_digests(
            self,
            _RESULT_DIGESTS,
            optional=("starter_receipt_digest",),
        )
        success = (
            self.state
            is (
                WorkflowProtectedRuntimeStartConsumptionResultState
            ).RUNTIME_STARTED_IN_PROTECTED_BOUNDARY
            and self.failure_class is None
            and self.outcome_known
            and self.runtime_started is True
            and self.starter_receipt_digest is not None
            and self.completed_at is not None
        )
        no_effect = (
            self.state
            is (
                WorkflowProtectedRuntimeStartConsumptionResultState
            ).RUNTIME_START_FAILED_WITHOUT_START
            and self.failure_class
            in (
                WorkflowProtectedRuntimeStartConsumptionFailureClass.PROTECTED_STARTER_REJECTED_WITHOUT_START,
                WorkflowProtectedRuntimeStartConsumptionFailureClass.PROTECTED_COMPARE_AND_SWAP_REJECTED,
            )
            and self.outcome_known
            and self.runtime_started is False
            and self.starter_receipt_digest is not None
            and self.completed_at is not None
        )
        uncertain = (
            self.state
            is WorkflowProtectedRuntimeStartConsumptionResultState.RUNTIME_START_OUTCOME_UNCERTAIN
            and self.failure_class
            is WorkflowProtectedRuntimeStartConsumptionFailureClass.RUNTIME_START_OUTCOME_UNCERTAIN
            and not self.outcome_known
            and self.runtime_started is None
            and self.starter_receipt_digest is None
            and self.completed_at is None
        )
        if (
            self.destination_generation < 1
            or self.runtime_envelope_generation < 1
            or self.recorded_at.tzinfo is None
            or (self.completed_at is not None and self.completed_at.tzinfo is None)
            or not (success or no_effect or uncertain)
            or self.policy_id != policy.policy_id
            or self.policy_version != policy.policy_version
            or self.policy_digest != policy.canonical_digest
            or self.runtime_start_profile_id != policy.runtime_start_profile_id
            or self.runtime_start_profile_version != policy.runtime_start_profile_version
            or self.runtime_start_profile_digest != policy.runtime_start_profile_digest
        ):
            raise ValueError("protected runtime start result is invalid")
        _require_zero_authority(self.authority)
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


def _matches_policy(
    value: WorkflowProtectedRuntimeStartConsumptionClaim
    | WorkflowProtectedRuntimeStartConsumptionAttempt,
    policy: WorkflowProtectedRuntimeStartConsumptionPolicy,
) -> bool:
    return (
        value.consumer_subject_id == policy.consumer_subject_id
        and value.consumer_audience == policy.consumer_audience
        and value.consumer_contract_id == policy.consumer_contract_id
        and value.consumer_contract_version == policy.consumer_contract_version
        and value.purpose_id == policy.purpose_id
        and value.policy_id == policy.policy_id
        and value.policy_version == policy.policy_version
        and value.policy_digest == policy.canonical_digest
        and value.runtime_start_profile_id == policy.runtime_start_profile_id
        and value.runtime_start_profile_version == policy.runtime_start_profile_version
        and value.runtime_start_profile_digest == policy.runtime_start_profile_digest
    )


def _require_identifier(value: str, name: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 240
        or any(character.isspace() for character in value)
    ):
        raise ValueError(f"invalid protected runtime start identifier: {name}")


def _require_identifiers(instance: object, names: tuple[str, ...]) -> None:
    for name in names:
        _require_identifier(getattr(instance, name), name)


def _require_digest(value: str, name: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"invalid protected runtime start digest: {name}")


def _require_digests(
    instance: object, names: tuple[str, ...], *, optional: tuple[str, ...] = ()
) -> None:
    for name in names:
        value = getattr(instance, name)
        if name in optional and value is None:
            continue
        _require_digest(value, name)


def _require_zero_authority(
    authority: WorkflowProtectedRuntimeStartConsumptionAuthority,
) -> None:
    values = authority.canonical_value()
    if len(values) != 27 or any(values.values()):
        raise ValueError("protected runtime start consumption requires 27 false authorities")


def _require_canonical_digest(instance: Any) -> None:
    if instance.canonical_digest != canonical_digest(instance.digest_payload()):
        raise ValueError("protected runtime start canonical digest mismatch")


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


_CLAIM_IDENTIFIERS = (
    "claim_id",
    "consumption_id",
    "attempt_id",
    "authorization_lease_id",
    "authorization_claim_id",
    "use_result_id",
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
_CLAIM_DIGESTS = (
    "authorization_lease_digest",
    "authorization_claim_digest",
    "use_result_digest",
    "destination_fencing_token_digest",
    "runtime_slot_commitment",
    "runtime_envelope_commitment",
    "runtime_start_profile_digest",
    "policy_digest",
    "idempotency_digest",
    "request_fingerprint",
    "canonical_digest",
)
_ATTEMPT_IDENTIFIERS = (
    *_CLAIM_IDENTIFIERS,
    "claim_id",
    "protected_operation_reference",
    "starter_contract_id",
    "starter_contract_version",
    "starter_id",
    "starter_version",
    "receipt_verification_signing_key_id",
)
_ATTEMPT_DIGESTS = (
    "claim_digest",
    "authorization_lease_digest",
    "authorization_claim_digest",
    "use_result_digest",
    "destination_fencing_token_digest",
    "runtime_slot_commitment",
    "runtime_envelope_commitment",
    "runtime_start_profile_digest",
    "request_nonce_digest",
    "policy_digest",
    "canonical_digest",
)
_INSTRUCTION_IDENTIFIERS = (
    "consumption_id",
    "attempt_id",
    "claim_id",
    "authorization_lease_id",
    "protected_operation_reference",
    "destination_deployment_id",
    "runtime_envelope_id",
    "runtime_start_profile_id",
    "runtime_start_profile_version",
    "starter_contract_id",
    "starter_contract_version",
    "starter_id",
    "starter_version",
    "policy_id",
    "policy_version",
)
_INSTRUCTION_DIGESTS = (
    "attempt_digest",
    "claim_digest",
    "authorization_lease_digest",
    "destination_fencing_token_digest",
    "runtime_slot_commitment",
    "runtime_envelope_commitment",
    "runtime_start_profile_digest",
    "request_nonce_digest",
    "policy_digest",
    "canonical_digest",
)
_RECEIPT_IDENTIFIERS = (
    "consumption_id",
    "attempt_id",
    "protected_operation_reference",
    "authorization_lease_id",
    "destination_deployment_id",
    "runtime_envelope_id",
    "starter_contract_id",
    "starter_contract_version",
    "starter_id",
    "starter_version",
    "signing_key_id",
    "signature_algorithm",
)
_RECEIPT_DIGESTS = (
    "instruction_digest",
    "destination_fencing_token_digest",
    "runtime_slot_commitment",
    "runtime_envelope_commitment",
    "request_nonce_digest",
    "integrity_signature",
    "canonical_digest",
)
_RESULT_IDENTIFIERS = (
    "result_id",
    "consumption_id",
    "attempt_id",
    "claim_id",
    "authorization_lease_id",
    "runtime_start_profile_id",
    "runtime_start_profile_version",
    "destination_deployment_id",
    "policy_id",
    "policy_version",
)
_RESULT_DIGESTS = (
    "attempt_digest",
    "claim_digest",
    "authorization_lease_digest",
    "runtime_start_profile_digest",
    "runtime_envelope_commitment",
    "policy_digest",
    "starter_receipt_digest",
    "canonical_digest",
)


__all__ = [
    "WORKFLOW_PROTECTED_RUNTIME_START_INSTRUCTION_SIGNATURE_ALGORITHM",
    "WORKFLOW_PROTECTED_RUNTIME_START_INSTRUCTION_SIGNING_KEY_ID",
    "WorkflowProtectedRuntimeStartConsumptionAttempt",
    "WorkflowProtectedRuntimeStartConsumptionAttemptState",
    "WorkflowProtectedRuntimeStartConsumptionAuthority",
    "WorkflowProtectedRuntimeStartConsumptionClaim",
    "WorkflowProtectedRuntimeStartConsumptionFailureClass",
    "WorkflowProtectedRuntimeStartConsumptionPolicy",
    "WorkflowProtectedRuntimeStartConsumptionResult",
    "WorkflowProtectedRuntimeStartConsumptionResultState",
    "WorkflowProtectedRuntimeStartInstruction",
    "WorkflowProtectedRuntimeStartInvocation",
    "WorkflowProtectedRuntimeStartReceipt",
    "WorkflowProtectedRuntimeStartSignedInstructionEnvelope",
    "code_owned_workflow_protected_runtime_start_consumption_policy",
    "code_owned_workflow_protected_runtime_start_consumption_policy_values",
]
