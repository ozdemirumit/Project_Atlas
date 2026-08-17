from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum
from typing import Any, cast

from .models import WorkflowScope, canonical_digest
from .protected_runtime_context_use_authorization_consumption_domain import (
    code_owned_workflow_protected_runtime_context_use_authorization_consumption_policy,
)
from .protected_runtime_context_use_authorization_domain import (
    code_owned_workflow_protected_runtime_context_use_authorization_policy,
)

WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNING_KEY_ID = (
    "key.workflow-protected-runtime-context-use-instruction.v1"
)
WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNATURE_ALGORITHM = "hmac-sha256"


class WorkflowProtectedRuntimeContextUseAttemptState(StrEnum):
    USE_STARTED = "use_started"


class WorkflowProtectedRuntimeContextUseResultState(StrEnum):
    CONTEXT_USED_ONCE_IN_PROTECTED_BOUNDARY = "context_used_once_in_protected_boundary"
    CONTEXT_USE_FAILED_WITHOUT_USE = "context_use_failed_without_use"
    CONTEXT_USE_OUTCOME_UNCERTAIN = "context_use_outcome_uncertain"


class WorkflowProtectedRuntimeContextUseFailureClass(StrEnum):
    TRUSTED_EXECUTOR_REJECTED = "trusted_executor_rejected"
    CONTEXT_COMPARE_AND_SWAP_REJECTED = "context_compare_and_swap_rejected"
    DEADLINE_EXPIRED = "deadline_expired"
    CONTEXT_USE_OUTCOME_UNCERTAIN = "context_use_outcome_uncertain"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseAuthority:
    """Non-bearer context-use evidence with every authority declaration false."""

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
        if any(self.canonical_value().values()):
            raise ValueError("protected runtime context use grants no authority")

    def canonical_value(self) -> dict[str, bool]:
        return {field.name: cast(bool, getattr(self, field.name)) for field in fields(self)}


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUsePolicy:
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
    attestation_verification_signing_key_id: str
    required_executor_contract_id: str
    required_executor_contract_version: str
    approved_executor_id: str
    approved_executor_version: str
    receipt_verification_signing_key_id: str
    use_profile_id: str
    use_profile_version: str
    use_profile_digest: str
    minimum_remaining_budget_milliseconds: int
    irreversible_use_acknowledgement_required: bool
    uncertainty_no_retry_acknowledgement_required: bool
    durable_replay_required: bool
    fresh_attestation_required: bool
    claim_before_executor_io_required: bool
    at_most_one_executor_call_required: bool
    automatic_retry_allowed: bool
    context_disclosure_forbidden: bool
    runtime_start_forbidden: bool
    runtime_resume_forbidden: bool
    process_creation_forbidden: bool
    prompt_construction_forbidden: bool
    model_inference_forbidden: bool
    network_activity_forbidden: bool
    connector_activity_forbidden: bool
    dispatch_forbidden: bool
    execution_forbidden: bool
    infrastructure_mutation_forbidden: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        expected = code_owned_workflow_protected_runtime_context_use_policy_values()
        if any(getattr(self, name) != value for name, value in expected.items()):
            raise ValueError("protected runtime context use policy is not code-owned")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("protected runtime context use policy digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


def code_owned_workflow_protected_runtime_context_use_policy_values() -> dict[str, object]:
    source = code_owned_workflow_protected_runtime_context_use_authorization_consumption_policy()
    authorization = code_owned_workflow_protected_runtime_context_use_authorization_policy()
    return {
        "policy_id": "policy.workflow-protected-runtime-context-use",
        "policy_version": "1.0",
        "source_policy_id": source.policy_id,
        "source_policy_version": source.policy_version,
        "source_policy_digest": source.canonical_digest,
        "consumer_subject_id": source.consumer_subject_id,
        "consumer_audience": source.consumer_audience,
        "consumer_contract_id": source.consumer_contract_id,
        "consumer_contract_version": source.consumer_contract_version,
        "purpose_id": "purpose.workflow-protected-runtime-context-use",
        "required_source_state": "authorization_consumed_without_runtime_use",
        "required_attestor_id": "attestor.workflow-protected-runtime-context-use-eligibility",
        "required_attestor_version": "1.0",
        "attestation_verification_signing_key_id": (
            "key.workflow-protected-runtime-context-use-eligibility.v1"
        ),
        "required_executor_contract_id": (
            "contract.workflow-protected-runtime-context-use-executor"
        ),
        "required_executor_contract_version": "1.0",
        "approved_executor_id": "executor.workflow-protected-runtime-context-use",
        "approved_executor_version": "1.0",
        "receipt_verification_signing_key_id": (
            "key.workflow-protected-runtime-context-use-receipt.v1"
        ),
        "use_profile_id": authorization.use_profile_id,
        "use_profile_version": authorization.use_profile_version,
        "use_profile_digest": authorization.use_profile_digest,
        "minimum_remaining_budget_milliseconds": 100,
        "irreversible_use_acknowledgement_required": True,
        "uncertainty_no_retry_acknowledgement_required": True,
        "durable_replay_required": True,
        "fresh_attestation_required": True,
        "claim_before_executor_io_required": True,
        "at_most_one_executor_call_required": True,
        "automatic_retry_allowed": False,
        "context_disclosure_forbidden": True,
        "runtime_start_forbidden": True,
        "runtime_resume_forbidden": True,
        "process_creation_forbidden": True,
        "prompt_construction_forbidden": True,
        "model_inference_forbidden": True,
        "network_activity_forbidden": True,
        "connector_activity_forbidden": True,
        "dispatch_forbidden": True,
        "execution_forbidden": True,
        "infrastructure_mutation_forbidden": True,
    }


def code_owned_workflow_protected_runtime_context_use_policy() -> (
    WorkflowProtectedRuntimeContextUsePolicy
):
    values = code_owned_workflow_protected_runtime_context_use_policy_values()
    return WorkflowProtectedRuntimeContextUsePolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseClaim:
    claim_id: str
    use_id: str
    attempt_id: str
    authorization_consumption_result_id: str
    authorization_consumption_result_digest: str
    authorization_consumption_claim_id: str
    authorization_consumption_claim_digest: str
    authorization_lease_id: str
    authorization_lease_digest: str
    injection_result_id: str
    injection_result_digest: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_slot_commitment: str
    runtime_slot_pre_generation: int
    injected_context_usable_until: datetime
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
    idempotency_digest: str
    request_fingerprint: str
    use_authorization_audit_digest: str
    irreversible_use_acknowledged: bool
    uncertainty_no_retry_acknowledged: bool
    claimed_at: datetime
    authority: WorkflowProtectedRuntimeContextUseAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_context_use_policy()
        _require_identifiers(self, _CLAIM_IDENTIFIERS)
        _require_digests(self, _CLAIM_DIGESTS)
        if (
            self.destination_generation < 1
            or self.runtime_slot_pre_generation < 1
            or self.claimed_at.tzinfo is None
            or self.injected_context_usable_until.tzinfo is None
            or self.claimed_at >= self.injected_context_usable_until
            or self.consumer_subject_id != policy.consumer_subject_id
            or self.consumer_audience != policy.consumer_audience
            or self.consumer_contract_id != policy.consumer_contract_id
            or self.consumer_contract_version != policy.consumer_contract_version
            or self.purpose_id != policy.purpose_id
            or self.policy_id != policy.policy_id
            or self.policy_version != policy.policy_version
            or self.policy_digest != policy.canonical_digest
            or self.use_profile_id != policy.use_profile_id
            or self.use_profile_version != policy.use_profile_version
            or self.use_profile_digest != policy.use_profile_digest
            or self.irreversible_use_acknowledged is not True
            or self.uncertainty_no_retry_acknowledged is not True
        ):
            raise ValueError("protected runtime context use claim is invalid")
        _require_zero_authority(self.authority)
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseAttempt:
    attempt_id: str
    use_id: str
    claim_id: str
    claim_digest: str
    authorization_consumption_result_id: str
    authorization_consumption_result_digest: str
    authorization_consumption_claim_id: str
    authorization_consumption_claim_digest: str
    authorization_lease_id: str
    authorization_lease_digest: str
    injection_result_id: str
    injection_result_digest: str
    protected_operation_reference: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_slot_commitment: str
    runtime_slot_pre_generation: int
    expected_runtime_slot_post_generation: int
    expected_use_count_pre: int
    expected_use_count_post: int
    injected_context_usable_until: datetime
    use_profile_id: str
    use_profile_version: str
    use_profile_digest: str
    required_executor_contract_id: str
    required_executor_contract_version: str
    approved_executor_id: str
    approved_executor_version: str
    receipt_verification_signing_key_id: str
    eligibility_attestation_id: str
    eligibility_attestation_digest: str
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
    use_deadline: datetime
    attestation_valid_until: datetime
    state: WorkflowProtectedRuntimeContextUseAttemptState
    authority: WorkflowProtectedRuntimeContextUseAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_context_use_policy()
        _require_identifiers(self, _ATTEMPT_IDENTIFIERS)
        _require_digests(self, _ATTEMPT_DIGESTS)
        deadlines = (self.injected_context_usable_until, self.attestation_valid_until)
        if (
            self.destination_generation < 1
            or self.runtime_slot_pre_generation < 1
            or self.expected_runtime_slot_post_generation != self.runtime_slot_pre_generation + 1
            or self.expected_use_count_pre != 0
            or self.expected_use_count_post != 1
            or any(value.tzinfo is None for value in deadlines)
            or self.started_at.tzinfo is None
            or self.use_deadline.tzinfo is None
            or not self.started_at < self.use_deadline <= min(deadlines)
            or self.state is not WorkflowProtectedRuntimeContextUseAttemptState.USE_STARTED
            or self.consumer_subject_id != policy.consumer_subject_id
            or self.consumer_audience != policy.consumer_audience
            or self.consumer_contract_id != policy.consumer_contract_id
            or self.consumer_contract_version != policy.consumer_contract_version
            or self.purpose_id != policy.purpose_id
            or self.policy_id != policy.policy_id
            or self.policy_version != policy.policy_version
            or self.policy_digest != policy.canonical_digest
            or self.use_profile_id != policy.use_profile_id
            or self.use_profile_version != policy.use_profile_version
            or self.use_profile_digest != policy.use_profile_digest
            or self.required_executor_contract_id != policy.required_executor_contract_id
            or self.required_executor_contract_version != policy.required_executor_contract_version
            or self.approved_executor_id != policy.approved_executor_id
            or self.approved_executor_version != policy.approved_executor_version
            or self.receipt_verification_signing_key_id
            != policy.receipt_verification_signing_key_id
        ):
            raise ValueError("protected runtime context use attempt is invalid")
        _require_zero_authority(self.authority)
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseInstruction:
    use_id: str
    attempt_id: str
    attempt_digest: str
    claim_id: str
    claim_digest: str
    authorization_consumption_result_id: str
    authorization_consumption_result_digest: str
    authorization_consumption_claim_id: str
    authorization_consumption_claim_digest: str
    authorization_lease_id: str
    authorization_lease_digest: str
    injection_result_id: str
    injection_result_digest: str
    protected_operation_reference: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_slot_commitment: str
    runtime_slot_pre_generation: int
    expected_runtime_slot_post_generation: int
    expected_use_count_pre: int
    expected_use_count_post: int
    use_profile_id: str
    use_profile_version: str
    use_profile_digest: str
    executor_contract_id: str
    executor_contract_version: str
    executor_id: str
    executor_version: str
    eligibility_attestation_id: str
    eligibility_attestation_digest: str
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
    use_deadline: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_context_use_policy()
        _require_identifiers(self, _INSTRUCTION_IDENTIFIERS)
        _require_digests(self, _INSTRUCTION_DIGESTS)
        if (
            self.destination_generation < 1
            or self.runtime_slot_pre_generation < 1
            or self.expected_runtime_slot_post_generation != self.runtime_slot_pre_generation + 1
            or self.expected_use_count_pre != 0
            or self.expected_use_count_post != 1
            or self.started_at.tzinfo is None
            or self.use_deadline.tzinfo is None
            or not self.started_at < self.use_deadline
            or self.consumer_subject_id != policy.consumer_subject_id
            or self.consumer_audience != policy.consumer_audience
            or self.consumer_contract_id != policy.consumer_contract_id
            or self.consumer_contract_version != policy.consumer_contract_version
            or self.purpose_id != policy.purpose_id
            or self.policy_id != policy.policy_id
            or self.policy_version != policy.policy_version
            or self.policy_digest != policy.canonical_digest
            or self.use_profile_id != policy.use_profile_id
            or self.use_profile_version != policy.use_profile_version
            or self.use_profile_digest != policy.use_profile_digest
            or self.executor_contract_id != policy.required_executor_contract_id
            or self.executor_contract_version != policy.required_executor_contract_version
            or self.executor_id != policy.approved_executor_id
            or self.executor_version != policy.approved_executor_version
        ):
            raise ValueError("protected runtime context use instruction is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseSignedInstructionEnvelope:
    """Signed, non-bearer instruction evidence for the protected call gate."""

    instruction: WorkflowProtectedRuntimeContextUseInstruction
    signing_key_id: str
    signature_algorithm: str
    integrity_signature: str
    canonical_digest: str

    def __post_init__(self) -> None:
        _require_identifiers(self, ("signing_key_id", "signature_algorithm"))
        _require_digests(self, ("integrity_signature", "canonical_digest"))
        if (
            self.signing_key_id != WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNING_KEY_ID
            or self.signature_algorithm
            != WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNATURE_ALGORITHM
        ):
            raise ValueError("protected runtime context use instruction envelope is invalid")
        _require_canonical_digest(self)

    def signature_payload(self) -> dict[str, object]:
        return {
            "instruction": self.instruction.digest_payload()
            | {"canonical_digest": self.instruction.canonical_digest},
            "signing_key_id": self.signing_key_id,
            "signature_algorithm": self.signature_algorithm,
        }

    def digest_payload(self) -> dict[str, object]:
        return self.signature_payload() | {"integrity_signature": self.integrity_signature}


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseInvocation:
    """The complete payload allowed across the authenticated protected call gate."""

    protected_operation_reference: str
    instruction_digest: str
    use_deadline: datetime
    signed_instruction_envelope: WorkflowProtectedRuntimeContextUseSignedInstructionEnvelope

    def __post_init__(self) -> None:
        _require_identifiers(self, ("protected_operation_reference",))
        _require_digests(self, ("instruction_digest",))
        instruction = self.signed_instruction_envelope.instruction
        if (
            self.use_deadline.tzinfo is None
            or self.protected_operation_reference != instruction.protected_operation_reference
            or self.instruction_digest != instruction.canonical_digest
            or self.use_deadline != instruction.use_deadline
        ):
            raise ValueError("protected runtime context use invocation is invalid")


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseReceipt:
    instruction_digest: str
    protected_operation_reference: str
    authorization_consumption_result_id: str
    authorization_consumption_result_digest: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_slot_commitment: str
    runtime_slot_pre_generation: int
    runtime_slot_post_generation: int
    use_count_pre: int
    use_count_post: int
    use_profile_id: str
    use_profile_version: str
    use_profile_digest: str
    executor_contract_id: str
    executor_contract_version: str
    executor_id: str
    executor_version: str
    state: WorkflowProtectedRuntimeContextUseResultState
    failure_class: WorkflowProtectedRuntimeContextUseFailureClass | None
    context_adopted: bool
    protected_runtime_context_use_performed: bool
    context_terminal_non_reusable: bool
    transient_material_zeroized: bool
    context_disclosed: bool
    runtime_started: bool
    runtime_resumed: bool
    process_created: bool
    prompt_constructed: bool
    model_inference_performed: bool
    model_output_created: bool
    filesystem_activity_performed: bool
    provider_activity_performed: bool
    connector_activity_performed: bool
    network_activity_performed: bool
    readiness_probe_performed: bool
    publication_performed: bool
    delivery_performed: bool
    dispatch_performed: bool
    execution_performed: bool
    infrastructure_mutation_performed: bool
    completed_at: datetime
    use_deadline: datetime
    attested_by: str
    signing_key_id: str
    signature_algorithm: str
    integrity_signature: str
    canonical_digest: str

    def __post_init__(self) -> None:
        _require_identifiers(self, _RECEIPT_IDENTIFIERS)
        _require_digests(self, _RECEIPT_DIGESTS)
        success = (
            self.state
            is WorkflowProtectedRuntimeContextUseResultState.CONTEXT_USED_ONCE_IN_PROTECTED_BOUNDARY
        )
        failure = (
            self.state
            is WorkflowProtectedRuntimeContextUseResultState.CONTEXT_USE_FAILED_WITHOUT_USE
        )
        forbidden = (
            self.context_disclosed,
            self.runtime_started,
            self.runtime_resumed,
            self.process_created,
            self.prompt_constructed,
            self.model_inference_performed,
            self.model_output_created,
            self.filesystem_activity_performed,
            self.provider_activity_performed,
            self.connector_activity_performed,
            self.network_activity_performed,
            self.readiness_probe_performed,
            self.publication_performed,
            self.delivery_performed,
            self.dispatch_performed,
            self.execution_performed,
            self.infrastructure_mutation_performed,
        )
        if (
            self.completed_at.tzinfo is None
            or self.use_deadline.tzinfo is None
            or self.completed_at >= self.use_deadline
            or self.destination_generation < 1
            or self.runtime_slot_pre_generation < 1
            or self.use_count_pre != 0
            or any(forbidden)
            or not (success or failure)
            or (success and self.failure_class is not None)
            or (
                success
                and self.runtime_slot_post_generation != self.runtime_slot_pre_generation + 1
            )
            or (success and self.use_count_post != 1)
            or (success and self.context_adopted is not True)
            or (success and self.protected_runtime_context_use_performed is not True)
            or (success and self.context_terminal_non_reusable is not True)
            or (success and self.transient_material_zeroized is not True)
            or (failure and self.failure_class is None)
            or (
                failure
                and self.failure_class
                is WorkflowProtectedRuntimeContextUseFailureClass.CONTEXT_USE_OUTCOME_UNCERTAIN
            )
            or (failure and self.runtime_slot_post_generation != self.runtime_slot_pre_generation)
            or (failure and self.use_count_post != 0)
            or (failure and self.context_adopted is not False)
            or (failure and self.protected_runtime_context_use_performed is not False)
            or (failure and self.context_terminal_non_reusable is not False)
            or (failure and self.transient_material_zeroized is not True)
        ):
            raise ValueError("protected runtime context use receipt is invalid")
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
class WorkflowProtectedRuntimeContextUseResult:
    result_id: str
    use_id: str
    attempt_id: str
    attempt_digest: str
    claim_id: str
    claim_digest: str
    authorization_consumption_result_id: str
    authorization_consumption_result_digest: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_slot_commitment: str
    runtime_slot_pre_generation: int
    runtime_slot_post_generation: int | None
    use_count_pre: int
    use_count_post: int | None
    use_profile_id: str
    use_profile_version: str
    use_profile_digest: str
    executor_contract_id: str
    executor_contract_version: str
    executor_id: str
    executor_version: str
    executor_receipt_digest: str | None
    state: WorkflowProtectedRuntimeContextUseResultState
    failure_class: WorkflowProtectedRuntimeContextUseFailureClass | None
    outcome_known: bool
    context_adopted: bool
    protected_runtime_context_use_performed: bool
    context_terminal_non_reusable: bool
    transient_material_zeroized: bool
    completed_at: datetime | None
    recorded_at: datetime
    use_deadline: datetime
    authority: WorkflowProtectedRuntimeContextUseAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        _require_identifiers(self, _RESULT_IDENTIFIERS)
        _require_digests(self, _RESULT_DIGESTS, optional=("executor_receipt_digest",))
        success = (
            self.state
            is WorkflowProtectedRuntimeContextUseResultState.CONTEXT_USED_ONCE_IN_PROTECTED_BOUNDARY
        )
        failure = (
            self.state
            is WorkflowProtectedRuntimeContextUseResultState.CONTEXT_USE_FAILED_WITHOUT_USE
        )
        uncertain = (
            self.state
            is WorkflowProtectedRuntimeContextUseResultState.CONTEXT_USE_OUTCOME_UNCERTAIN
        )
        if (
            self.recorded_at.tzinfo is None
            or self.use_deadline.tzinfo is None
            or (self.completed_at is not None and self.completed_at.tzinfo is None)
            or self.destination_generation < 1
            or self.runtime_slot_pre_generation < 1
            or self.use_count_pre != 0
            or (success and not self._known_success_is_valid())
            or (failure and not self._known_failure_is_valid())
            or (uncertain and not self._uncertainty_is_valid())
            or not (success or failure or uncertain)
        ):
            raise ValueError("protected runtime context use result is invalid")
        _require_zero_authority(self.authority)
        _require_canonical_digest(self)

    def _known_success_is_valid(self) -> bool:
        return (
            self.executor_receipt_digest is not None
            and self.failure_class is None
            and self.outcome_known is True
            and self.runtime_slot_post_generation == self.runtime_slot_pre_generation + 1
            and self.use_count_post == 1
            and self.context_adopted is True
            and self.protected_runtime_context_use_performed is True
            and self.context_terminal_non_reusable is True
            and self.transient_material_zeroized is True
            and self.completed_at is not None
            and self.completed_at < self.use_deadline
            and self.recorded_at >= self.completed_at
        )

    def _known_failure_is_valid(self) -> bool:
        return (
            self.executor_receipt_digest is not None
            and self.failure_class is not None
            and self.failure_class
            is not WorkflowProtectedRuntimeContextUseFailureClass.CONTEXT_USE_OUTCOME_UNCERTAIN
            and self.outcome_known is True
            and self.runtime_slot_post_generation == self.runtime_slot_pre_generation
            and self.use_count_post == 0
            and self.context_adopted is False
            and self.protected_runtime_context_use_performed is False
            and self.context_terminal_non_reusable is False
            and self.transient_material_zeroized is True
            and self.completed_at is not None
            and self.completed_at < self.use_deadline
            and self.recorded_at >= self.completed_at
        )

    def _uncertainty_is_valid(self) -> bool:
        return (
            self.executor_receipt_digest is None
            and self.failure_class
            is WorkflowProtectedRuntimeContextUseFailureClass.CONTEXT_USE_OUTCOME_UNCERTAIN
            and self.outcome_known is False
            and self.runtime_slot_post_generation is None
            and self.use_count_post is None
            and self.context_adopted is False
            and self.protected_runtime_context_use_performed is False
            and self.context_terminal_non_reusable is False
            and self.transient_material_zeroized is False
            and self.completed_at is None
        )

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


_CLAIM_IDENTIFIERS = (
    "claim_id",
    "use_id",
    "attempt_id",
    "authorization_consumption_result_id",
    "authorization_consumption_claim_id",
    "authorization_lease_id",
    "injection_result_id",
    "destination_deployment_id",
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
_CLAIM_DIGESTS = (
    "authorization_consumption_result_digest",
    "authorization_consumption_claim_digest",
    "authorization_lease_digest",
    "injection_result_digest",
    "destination_fencing_token_digest",
    "runtime_slot_commitment",
    "use_profile_digest",
    "policy_digest",
    "idempotency_digest",
    "request_fingerprint",
    "use_authorization_audit_digest",
    "canonical_digest",
)
_ATTEMPT_IDENTIFIERS = (
    "attempt_id",
    "use_id",
    "claim_id",
    "authorization_consumption_result_id",
    "authorization_consumption_claim_id",
    "authorization_lease_id",
    "injection_result_id",
    "protected_operation_reference",
    "destination_deployment_id",
    "use_profile_id",
    "use_profile_version",
    "required_executor_contract_id",
    "required_executor_contract_version",
    "approved_executor_id",
    "approved_executor_version",
    "receipt_verification_signing_key_id",
    "eligibility_attestation_id",
    "consumer_subject_id",
    "consumer_audience",
    "consumer_contract_id",
    "consumer_contract_version",
    "purpose_id",
    "policy_id",
    "policy_version",
)
_ATTEMPT_DIGESTS = (
    "claim_digest",
    "authorization_consumption_result_digest",
    "authorization_consumption_claim_digest",
    "authorization_lease_digest",
    "injection_result_digest",
    "destination_fencing_token_digest",
    "runtime_slot_commitment",
    "use_profile_digest",
    "eligibility_attestation_digest",
    "request_nonce_digest",
    "policy_digest",
    "canonical_digest",
)
_INSTRUCTION_IDENTIFIERS = (
    "use_id",
    "attempt_id",
    "claim_id",
    "authorization_consumption_result_id",
    "authorization_consumption_claim_id",
    "authorization_lease_id",
    "injection_result_id",
    "protected_operation_reference",
    "destination_deployment_id",
    "use_profile_id",
    "use_profile_version",
    "executor_contract_id",
    "executor_contract_version",
    "executor_id",
    "executor_version",
    "eligibility_attestation_id",
    "consumer_subject_id",
    "consumer_audience",
    "consumer_contract_id",
    "consumer_contract_version",
    "purpose_id",
    "policy_id",
    "policy_version",
)
_INSTRUCTION_DIGESTS = (
    "attempt_digest",
    "claim_digest",
    "authorization_consumption_result_digest",
    "authorization_consumption_claim_digest",
    "authorization_lease_digest",
    "injection_result_digest",
    "destination_fencing_token_digest",
    "runtime_slot_commitment",
    "use_profile_digest",
    "eligibility_attestation_digest",
    "request_nonce_digest",
    "policy_digest",
    "canonical_digest",
)
_RECEIPT_IDENTIFIERS = (
    "protected_operation_reference",
    "authorization_consumption_result_id",
    "destination_deployment_id",
    "use_profile_id",
    "use_profile_version",
    "executor_contract_id",
    "executor_contract_version",
    "executor_id",
    "executor_version",
    "attested_by",
    "signing_key_id",
    "signature_algorithm",
)
_RECEIPT_DIGESTS = (
    "instruction_digest",
    "authorization_consumption_result_digest",
    "destination_fencing_token_digest",
    "runtime_slot_commitment",
    "use_profile_digest",
    "integrity_signature",
    "canonical_digest",
)
_RESULT_IDENTIFIERS = (
    "result_id",
    "use_id",
    "attempt_id",
    "claim_id",
    "authorization_consumption_result_id",
    "destination_deployment_id",
    "use_profile_id",
    "use_profile_version",
    "executor_contract_id",
    "executor_contract_version",
    "executor_id",
    "executor_version",
)
_RESULT_DIGESTS = (
    "attempt_digest",
    "claim_digest",
    "authorization_consumption_result_digest",
    "destination_fencing_token_digest",
    "runtime_slot_commitment",
    "use_profile_digest",
    "executor_receipt_digest",
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
            raise ValueError(f"invalid protected runtime context use identifier: {name}")


def _require_digests(
    instance: object, names: tuple[str, ...], *, optional: tuple[str, ...] = ()
) -> None:
    for name in names:
        value = getattr(instance, name)
        if name in optional and value is None:
            continue
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ValueError(f"invalid protected runtime context use digest: {name}")


def _require_zero_authority(authority: WorkflowProtectedRuntimeContextUseAuthority) -> None:
    values = authority.canonical_value()
    if len(values) != 26 or any(values.values()):
        raise ValueError("protected runtime context use must have 26 false authorities")


def _require_canonical_digest(instance: Any) -> None:
    if instance.canonical_digest != canonical_digest(instance.digest_payload()):
        raise ValueError("protected runtime context use canonical digest mismatch")


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
    return value


__all__ = [
    "WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNATURE_ALGORITHM",
    "WORKFLOW_PROTECTED_RUNTIME_CONTEXT_USE_INSTRUCTION_SIGNING_KEY_ID",
    "WorkflowProtectedRuntimeContextUseAttempt",
    "WorkflowProtectedRuntimeContextUseAttemptState",
    "WorkflowProtectedRuntimeContextUseAuthority",
    "WorkflowProtectedRuntimeContextUseClaim",
    "WorkflowProtectedRuntimeContextUseFailureClass",
    "WorkflowProtectedRuntimeContextUseInstruction",
    "WorkflowProtectedRuntimeContextUseInvocation",
    "WorkflowProtectedRuntimeContextUsePolicy",
    "WorkflowProtectedRuntimeContextUseReceipt",
    "WorkflowProtectedRuntimeContextUseResult",
    "WorkflowProtectedRuntimeContextUseResultState",
    "WorkflowProtectedRuntimeContextUseSignedInstructionEnvelope",
    "code_owned_workflow_protected_runtime_context_use_policy",
    "code_owned_workflow_protected_runtime_context_use_policy_values",
]
