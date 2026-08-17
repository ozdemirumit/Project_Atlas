from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum
from functools import lru_cache
from typing import Any, cast

from .models import WorkflowScope, canonical_digest
from .protected_runtime_readiness_authorization_domain import (
    code_owned_workflow_protected_runtime_readiness_authorization_policy,
)

WORKFLOW_PROTECTED_RUNTIME_READINESS_INSTRUCTION_SIGNING_KEY_ID = (
    "key.workflow-protected-runtime-readiness-instruction.v1"
)
WORKFLOW_PROTECTED_RUNTIME_READINESS_INSTRUCTION_SIGNATURE_ALGORITHM = "hmac-sha256"


class WorkflowProtectedRuntimeReadinessConsumptionAttemptState(StrEnum):
    RUNTIME_READINESS_ATTEMPT_STARTED = "runtime_readiness_attempt_started"


class WorkflowProtectedRuntimeReadinessConsumptionResultState(StrEnum):
    RUNTIME_READY_IN_PROTECTED_BOUNDARY = "runtime_ready_in_protected_boundary"
    RUNTIME_NOT_READY_IN_PROTECTED_BOUNDARY = "runtime_not_ready_in_protected_boundary"
    RUNTIME_READINESS_FAILED_WITHOUT_ASSESSMENT = "runtime_readiness_failed_without_assessment"
    RUNTIME_READINESS_OUTCOME_UNCERTAIN = "runtime_readiness_outcome_uncertain"


class WorkflowProtectedRuntimeReadinessConsumptionFailureClass(StrEnum):
    PROTECTED_ASSESSOR_REJECTED_WITHOUT_ASSESSMENT = (
        "protected_assessor_rejected_without_assessment"
    )
    PROTECTED_ASSESSMENT_FAILED_WITHOUT_ASSESSMENT = (
        "protected_assessment_failed_without_assessment"
    )
    RUNTIME_READINESS_OUTCOME_UNCERTAIN = "runtime_readiness_outcome_uncertain"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessConsumptionAuthority:
    """Historical readiness evidence with every reusable authority set to false."""

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
        if any(self.canonical_value().values()):
            raise ValueError("protected runtime readiness consumption grants no authority")

    def canonical_value(self) -> dict[str, bool]:
        return {field.name: cast(bool, getattr(self, field.name)) for field in fields(self)}


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessConsumptionPolicy:
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
    required_assessor_contract_id: str
    required_assessor_contract_version: str
    approved_assessor_id: str
    approved_assessor_version: str
    instruction_signing_key_id: str
    instruction_signature_algorithm: str
    receipt_verification_signing_key_id: str
    receipt_signature_algorithm: str
    readiness_profile_id: str
    readiness_profile_version: str
    readiness_profile_digest: str
    minimum_invocation_margin_milliseconds: int
    irreversible_consumption_acknowledgement_required: bool
    uncertainty_no_retry_acknowledgement_required: bool
    durable_replay_required: bool
    claim_and_attempt_atomic_required: bool
    commit_before_assessor_io_required: bool
    at_most_one_assessor_call_required: bool
    automatic_retry_allowed: bool
    protected_boundary_only_required: bool
    metadata_only_instruction_required: bool
    runtime_locator_forbidden: bool
    process_identifier_forbidden: bool
    runtime_context_forbidden: bool
    endpoint_material_forbidden: bool
    credential_material_forbidden: bool
    secret_material_forbidden: bool
    command_construction_forbidden: bool
    prompt_construction_forbidden: bool
    model_inference_forbidden: bool
    network_activity_forbidden: bool
    connector_activity_forbidden: bool
    mcp_activity_forbidden: bool
    publication_forbidden: bool
    delivery_forbidden: bool
    dispatch_forbidden: bool
    execution_forbidden: bool
    infrastructure_mutation_forbidden: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        expected = code_owned_workflow_protected_runtime_readiness_consumption_policy_values()
        if any(getattr(self, name) != value for name, value in expected.items()):
            raise ValueError("protected runtime readiness consumption policy is not code-owned")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


def code_owned_workflow_protected_runtime_readiness_consumption_policy_values() -> dict[
    str, object
]:
    source = code_owned_workflow_protected_runtime_readiness_authorization_policy()
    return {
        "policy_id": "policy.workflow-protected-runtime-readiness-consumption",
        "policy_version": "1.0",
        "source_policy_id": source.policy_id,
        "source_policy_version": source.policy_version,
        "source_policy_digest": source.canonical_digest,
        "consumer_subject_id": source.consumer_subject_id,
        "consumer_audience": source.consumer_audience,
        "consumer_contract_id": source.consumer_contract_id,
        "consumer_contract_version": source.consumer_contract_version,
        "purpose_id": source.purpose_id,
        "required_source_state": "authorized_unconsumed",
        "required_assessor_contract_id": ("contract.workflow-protected-runtime-readiness-assessor"),
        "required_assessor_contract_version": "1.0",
        "approved_assessor_id": "assessor.workflow-protected-runtime-readiness",
        "approved_assessor_version": "1.0",
        "instruction_signing_key_id": (
            WORKFLOW_PROTECTED_RUNTIME_READINESS_INSTRUCTION_SIGNING_KEY_ID
        ),
        "instruction_signature_algorithm": (
            WORKFLOW_PROTECTED_RUNTIME_READINESS_INSTRUCTION_SIGNATURE_ALGORITHM
        ),
        "receipt_verification_signing_key_id": (
            "key.workflow-protected-runtime-readiness-receipt.v1"
        ),
        "receipt_signature_algorithm": "hmac-sha256",
        "readiness_profile_id": source.readiness_profile_id,
        "readiness_profile_version": source.readiness_profile_version,
        "readiness_profile_digest": source.readiness_profile_digest,
        "minimum_invocation_margin_milliseconds": 100,
        "irreversible_consumption_acknowledgement_required": True,
        "uncertainty_no_retry_acknowledgement_required": True,
        "durable_replay_required": True,
        "claim_and_attempt_atomic_required": True,
        "commit_before_assessor_io_required": True,
        "at_most_one_assessor_call_required": True,
        "automatic_retry_allowed": False,
        "protected_boundary_only_required": True,
        "metadata_only_instruction_required": True,
        "runtime_locator_forbidden": True,
        "process_identifier_forbidden": True,
        "runtime_context_forbidden": True,
        "endpoint_material_forbidden": True,
        "credential_material_forbidden": True,
        "secret_material_forbidden": True,
        "command_construction_forbidden": True,
        "prompt_construction_forbidden": True,
        "model_inference_forbidden": True,
        "network_activity_forbidden": True,
        "connector_activity_forbidden": True,
        "mcp_activity_forbidden": True,
        "publication_forbidden": True,
        "delivery_forbidden": True,
        "dispatch_forbidden": True,
        "execution_forbidden": True,
        "infrastructure_mutation_forbidden": True,
    }


@lru_cache(maxsize=1)
def code_owned_workflow_protected_runtime_readiness_consumption_policy() -> (
    WorkflowProtectedRuntimeReadinessConsumptionPolicy
):
    values = code_owned_workflow_protected_runtime_readiness_consumption_policy_values()
    return WorkflowProtectedRuntimeReadinessConsumptionPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessConsumptionClaim:
    claim_id: str
    consumption_id: str
    attempt_id: str
    authorization_lease_id: str
    authorization_lease_digest: str
    authorization_claim_id: str
    authorization_claim_digest: str
    start_result_id: str
    start_result_digest: str
    start_consumption_id: str
    start_attempt_id: str
    start_attempt_digest: str
    start_claim_id: str
    start_claim_digest: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    protected_slot_commitment: str
    protected_slot_generation: int
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
    readiness_profile_id: str
    readiness_profile_version: str
    readiness_profile_digest: str
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
    authority: WorkflowProtectedRuntimeReadinessConsumptionAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()
        _require_identifiers(self, _CLAIM_IDENTIFIERS)
        _require_digests(self, _CLAIM_DIGESTS)
        if (
            self.destination_generation < 1
            or self.protected_slot_generation < 1
            or self.runtime_envelope_generation != self.protected_slot_generation
            or self.claimed_at.tzinfo is None
            or not self.irreversible_consumption_acknowledged
            or not self.uncertainty_no_retry_acknowledged
            or not _matches_policy(self, policy)
        ):
            raise ValueError("protected runtime readiness consumption claim is invalid")
        _require_zero_authority(self.authority)
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessAttempt:
    attempt_id: str
    consumption_id: str
    claim_id: str
    claim_digest: str
    authorization_lease_id: str
    authorization_lease_digest: str
    authorization_claim_id: str
    authorization_claim_digest: str
    start_result_id: str
    start_result_digest: str
    start_consumption_id: str
    start_attempt_id: str
    start_attempt_digest: str
    start_claim_id: str
    start_claim_digest: str
    protected_operation_reference: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    protected_slot_commitment: str
    protected_slot_generation: int
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
    readiness_profile_id: str
    readiness_profile_version: str
    readiness_profile_digest: str
    expected_assessment_count_pre: int
    expected_assessment_count_post: int
    assessor_contract_id: str
    assessor_contract_version: str
    assessor_id: str
    assessor_version: str
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
    state: WorkflowProtectedRuntimeReadinessConsumptionAttemptState
    authority: WorkflowProtectedRuntimeReadinessConsumptionAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()
        _require_identifiers(self, _ATTEMPT_IDENTIFIERS)
        _require_digests(self, _ATTEMPT_DIGESTS)
        if (
            self.destination_generation < 1
            or self.protected_slot_generation < 1
            or self.runtime_envelope_generation != self.protected_slot_generation
            or self.expected_assessment_count_pre != 0
            or self.expected_assessment_count_post != 1
            or self.started_at.tzinfo is None
            or self.invocation_deadline.tzinfo is None
            or not self.started_at < self.invocation_deadline
            or self.state
            is not (
                WorkflowProtectedRuntimeReadinessConsumptionAttemptState
            ).RUNTIME_READINESS_ATTEMPT_STARTED
            or not _matches_policy(self, policy)
            or self.assessor_contract_id != policy.required_assessor_contract_id
            or self.assessor_contract_version != policy.required_assessor_contract_version
            or self.assessor_id != policy.approved_assessor_id
            or self.assessor_version != policy.approved_assessor_version
            or self.receipt_verification_signing_key_id
            != policy.receipt_verification_signing_key_id
        ):
            raise ValueError("protected runtime readiness attempt is invalid")
        _require_zero_authority(self.authority)
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessInstruction:
    consumption_id: str
    attempt_id: str
    attempt_digest: str
    claim_id: str
    claim_digest: str
    authorization_lease_id: str
    authorization_lease_digest: str
    start_result_id: str
    start_result_digest: str
    protected_operation_reference: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    protected_slot_commitment: str
    protected_slot_generation: int
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
    readiness_profile_id: str
    readiness_profile_version: str
    readiness_profile_digest: str
    expected_assessment_count_pre: int
    expected_assessment_count_post: int
    assessor_contract_id: str
    assessor_contract_version: str
    assessor_id: str
    assessor_version: str
    request_nonce_digest: str
    scope: WorkflowScope
    policy_id: str
    policy_version: str
    policy_digest: str
    started_at: datetime
    invocation_deadline: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()
        _require_identifiers(self, _INSTRUCTION_IDENTIFIERS)
        _require_digests(self, _INSTRUCTION_DIGESTS)
        if (
            self.destination_generation < 1
            or self.protected_slot_generation < 1
            or self.runtime_envelope_generation != self.protected_slot_generation
            or self.expected_assessment_count_pre != 0
            or self.expected_assessment_count_post != 1
            or self.started_at.tzinfo is None
            or self.invocation_deadline.tzinfo is None
            or not self.started_at < self.invocation_deadline
            or not _instruction_matches_policy(self, policy)
        ):
            raise ValueError("protected runtime readiness instruction is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessSignedInstructionEnvelope:
    instruction: WorkflowProtectedRuntimeReadinessInstruction
    signing_key_id: str
    signature_algorithm: str
    integrity_signature: str
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()
        _require_identifiers(self, ("signing_key_id", "signature_algorithm"))
        _require_digests(self, ("integrity_signature", "canonical_digest"))
        if (
            self.signing_key_id != policy.instruction_signing_key_id
            or self.signature_algorithm != policy.instruction_signature_algorithm
        ):
            raise ValueError("protected runtime readiness instruction envelope is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessInvocation:
    protected_operation_reference: str
    instruction_digest: str
    invocation_deadline: datetime
    signed_instruction_envelope: WorkflowProtectedRuntimeReadinessSignedInstructionEnvelope

    def __post_init__(self) -> None:
        _require_identifier(self.protected_operation_reference, "protected_operation_reference")
        _require_digest(self.instruction_digest, "instruction_digest")
        instruction = self.signed_instruction_envelope.instruction
        if (
            self.invocation_deadline.tzinfo is None
            or self.protected_operation_reference != instruction.protected_operation_reference
            or self.instruction_digest != instruction.canonical_digest
            or self.invocation_deadline != instruction.invocation_deadline
        ):
            raise ValueError("protected runtime readiness invocation is invalid")


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeReadinessReceipt:
    consumption_id: str
    attempt_id: str
    attempt_digest: str
    claim_id: str
    claim_digest: str
    instruction_digest: str
    authorization_lease_id: str
    authorization_lease_digest: str
    start_result_id: str
    start_result_digest: str
    protected_operation_reference: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    protected_slot_commitment: str
    protected_slot_generation: int
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
    readiness_profile_id: str
    readiness_profile_version: str
    readiness_profile_digest: str
    assessor_contract_id: str
    assessor_contract_version: str
    assessor_id: str
    assessor_version: str
    request_nonce_digest: str
    assessment_count_pre: int
    assessment_count_post: int
    result_state: WorkflowProtectedRuntimeReadinessConsumptionResultState
    runtime_ready: bool | None
    readiness_assessment_performed: bool
    runtime_locator_returned: bool
    process_identifier_returned: bool
    runtime_context_returned: bool
    endpoint_material_returned: bool
    credential_material_returned: bool
    secret_material_returned: bool
    command_constructed: bool
    prompt_constructed: bool
    model_inference_performed: bool
    network_activity_performed: bool
    connector_activity_performed: bool
    mcp_activity_performed: bool
    publication_performed: bool
    delivery_performed: bool
    dispatch_performed: bool
    execution_performed: bool
    infrastructure_mutation_performed: bool
    started_at: datetime
    invocation_deadline: datetime
    completed_at: datetime
    signing_key_id: str
    signature_algorithm: str
    integrity_signature: str
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()
        _require_identifiers(self, _RECEIPT_IDENTIFIERS)
        _require_digests(self, _RECEIPT_DIGESTS)
        forbidden = (
            self.runtime_locator_returned,
            self.process_identifier_returned,
            self.runtime_context_returned,
            self.endpoint_material_returned,
            self.credential_material_returned,
            self.secret_material_returned,
            self.command_constructed,
            self.prompt_constructed,
            self.model_inference_performed,
            self.network_activity_performed,
            self.connector_activity_performed,
            self.mcp_activity_performed,
            self.publication_performed,
            self.delivery_performed,
            self.dispatch_performed,
            self.execution_performed,
            self.infrastructure_mutation_performed,
        )
        ready = (
            self.result_state
            is (
                WorkflowProtectedRuntimeReadinessConsumptionResultState
            ).RUNTIME_READY_IN_PROTECTED_BOUNDARY
            and self.runtime_ready is True
            and self.readiness_assessment_performed
            and self.assessment_count_pre == 0
            and self.assessment_count_post == 1
        )
        not_ready = (
            self.result_state
            is (
                WorkflowProtectedRuntimeReadinessConsumptionResultState
            ).RUNTIME_NOT_READY_IN_PROTECTED_BOUNDARY
            and self.runtime_ready is False
            and self.readiness_assessment_performed
            and self.assessment_count_pre == 0
            and self.assessment_count_post == 1
        )
        failed_without_assessment = (
            self.result_state
            is (
                WorkflowProtectedRuntimeReadinessConsumptionResultState
            ).RUNTIME_READINESS_FAILED_WITHOUT_ASSESSMENT
            and self.runtime_ready is None
            and not self.readiness_assessment_performed
            and self.assessment_count_pre == 0
            and self.assessment_count_post == 0
        )
        if (
            self.destination_generation < 1
            or self.protected_slot_generation < 1
            or self.runtime_envelope_generation != self.protected_slot_generation
            or not (ready or not_ready or failed_without_assessment)
            or any(forbidden)
            or any(
                value.tzinfo is None
                for value in (self.started_at, self.invocation_deadline, self.completed_at)
            )
            or not self.started_at <= self.completed_at < self.invocation_deadline
            or self.assessor_contract_id != policy.required_assessor_contract_id
            or self.assessor_contract_version != policy.required_assessor_contract_version
            or self.assessor_id != policy.approved_assessor_id
            or self.assessor_version != policy.approved_assessor_version
            or self.readiness_profile_id != policy.readiness_profile_id
            or self.readiness_profile_version != policy.readiness_profile_version
            or self.readiness_profile_digest != policy.readiness_profile_digest
            or self.signing_key_id != policy.receipt_verification_signing_key_id
            or self.signature_algorithm != policy.receipt_signature_algorithm
        ):
            raise ValueError("protected runtime readiness receipt is invalid")
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
class WorkflowProtectedRuntimeReadinessResult:
    result_id: str
    consumption_id: str
    attempt_id: str
    attempt_digest: str
    claim_id: str
    claim_digest: str
    authorization_lease_id: str
    authorization_lease_digest: str
    start_result_id: str
    start_result_digest: str
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
    state: WorkflowProtectedRuntimeReadinessConsumptionResultState
    failure_class: WorkflowProtectedRuntimeReadinessConsumptionFailureClass | None
    outcome_known: bool
    assessment_performed: bool | None
    runtime_ready: bool | None
    assessor_receipt_digest: str | None
    completed_at: datetime | None
    recorded_at: datetime
    scope: WorkflowScope
    policy_id: str
    policy_version: str
    policy_digest: str
    authority: WorkflowProtectedRuntimeReadinessConsumptionAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_readiness_consumption_policy()
        _require_identifiers(self, _RESULT_IDENTIFIERS)
        _require_digests(self, _RESULT_DIGESTS, optional=("assessor_receipt_digest",))
        ready = self._is_known_readiness(ready=True)
        not_ready = self._is_known_readiness(ready=False)
        failed = (
            self.state
            is (
                WorkflowProtectedRuntimeReadinessConsumptionResultState
            ).RUNTIME_READINESS_FAILED_WITHOUT_ASSESSMENT
            and self.failure_class
            in (
                WorkflowProtectedRuntimeReadinessConsumptionFailureClass.PROTECTED_ASSESSOR_REJECTED_WITHOUT_ASSESSMENT,
                WorkflowProtectedRuntimeReadinessConsumptionFailureClass.PROTECTED_ASSESSMENT_FAILED_WITHOUT_ASSESSMENT,
            )
            and self.outcome_known
            and self.assessment_performed is False
            and self.runtime_ready is None
            and self.assessor_receipt_digest is not None
            and self.completed_at is not None
        )
        uncertain = (
            self.state
            is (
                WorkflowProtectedRuntimeReadinessConsumptionResultState
            ).RUNTIME_READINESS_OUTCOME_UNCERTAIN
            and self.failure_class
            is (
                WorkflowProtectedRuntimeReadinessConsumptionFailureClass
            ).RUNTIME_READINESS_OUTCOME_UNCERTAIN
            and not self.outcome_known
            and self.assessment_performed is None
            and self.runtime_ready is None
            and self.assessor_receipt_digest is None
            and self.completed_at is None
        )
        if (
            self.destination_generation < 1
            or self.protected_slot_generation < 1
            or self.runtime_envelope_generation != self.protected_slot_generation
            or self.recorded_at.tzinfo is None
            or (self.completed_at is not None and self.completed_at.tzinfo is None)
            or (self.completed_at is not None and self.recorded_at < self.completed_at)
            or not (ready or not_ready or failed or uncertain)
            or self.policy_id != policy.policy_id
            or self.policy_version != policy.policy_version
            or self.policy_digest != policy.canonical_digest
            or self.readiness_profile_id != policy.readiness_profile_id
            or self.readiness_profile_version != policy.readiness_profile_version
            or self.readiness_profile_digest != policy.readiness_profile_digest
        ):
            raise ValueError("protected runtime readiness result is invalid")
        _require_zero_authority(self.authority)
        _require_canonical_digest(self)

    def _is_known_readiness(self, *, ready: bool) -> bool:
        expected_state = (
            (
                WorkflowProtectedRuntimeReadinessConsumptionResultState
            ).RUNTIME_READY_IN_PROTECTED_BOUNDARY
            if ready
            else (
                WorkflowProtectedRuntimeReadinessConsumptionResultState
            ).RUNTIME_NOT_READY_IN_PROTECTED_BOUNDARY
        )
        return (
            self.state is expected_state
            and self.failure_class is None
            and self.outcome_known
            and self.assessment_performed is True
            and self.runtime_ready is ready
            and self.assessor_receipt_digest is not None
            and self.completed_at is not None
        )

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


def _matches_policy(
    value: WorkflowProtectedRuntimeReadinessConsumptionClaim
    | WorkflowProtectedRuntimeReadinessAttempt,
    policy: WorkflowProtectedRuntimeReadinessConsumptionPolicy,
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
        and value.readiness_profile_id == policy.readiness_profile_id
        and value.readiness_profile_version == policy.readiness_profile_version
        and value.readiness_profile_digest == policy.readiness_profile_digest
    )


def _instruction_matches_policy(
    value: WorkflowProtectedRuntimeReadinessInstruction,
    policy: WorkflowProtectedRuntimeReadinessConsumptionPolicy,
) -> bool:
    return (
        value.policy_id == policy.policy_id
        and value.policy_version == policy.policy_version
        and value.policy_digest == policy.canonical_digest
        and value.readiness_profile_id == policy.readiness_profile_id
        and value.readiness_profile_version == policy.readiness_profile_version
        and value.readiness_profile_digest == policy.readiness_profile_digest
        and value.assessor_contract_id == policy.required_assessor_contract_id
        and value.assessor_contract_version == policy.required_assessor_contract_version
        and value.assessor_id == policy.approved_assessor_id
        and value.assessor_version == policy.approved_assessor_version
    )


def _require_identifier(value: str, name: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > 240
        or any(character.isspace() for character in value)
    ):
        raise ValueError(f"invalid protected runtime readiness identifier: {name}")


def _require_identifiers(instance: object, names: tuple[str, ...]) -> None:
    for name in names:
        _require_identifier(getattr(instance, name), name)


def _require_digest(value: str, name: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"invalid protected runtime readiness digest: {name}")


def _require_digests(
    instance: object, names: tuple[str, ...], *, optional: tuple[str, ...] = ()
) -> None:
    for name in names:
        value = getattr(instance, name)
        if name in optional and value is None:
            continue
        _require_digest(value, name)


def _require_zero_authority(
    authority: WorkflowProtectedRuntimeReadinessConsumptionAuthority,
) -> None:
    values = authority.canonical_value()
    if len(values) != 28 or any(values.values()):
        raise ValueError("protected runtime readiness consumption requires 28 false authorities")


def _require_canonical_digest(instance: Any) -> None:
    if instance.canonical_digest != canonical_digest(instance.digest_payload()):
        raise ValueError("protected runtime readiness canonical digest mismatch")


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


_SOURCE_IDENTIFIERS = (
    "authorization_lease_id",
    "authorization_claim_id",
    "start_result_id",
    "start_consumption_id",
    "start_attempt_id",
    "start_claim_id",
    "destination_deployment_id",
    "runtime_envelope_id",
    "readiness_profile_id",
    "readiness_profile_version",
)
_SOURCE_DIGESTS = (
    "authorization_lease_digest",
    "authorization_claim_digest",
    "start_result_digest",
    "start_attempt_digest",
    "start_claim_digest",
    "destination_fencing_token_digest",
    "protected_slot_commitment",
    "runtime_envelope_commitment",
    "readiness_profile_digest",
)
_CLAIM_IDENTIFIERS = (
    "claim_id",
    "consumption_id",
    "attempt_id",
    *_SOURCE_IDENTIFIERS,
    "consumer_subject_id",
    "consumer_audience",
    "consumer_contract_id",
    "consumer_contract_version",
    "purpose_id",
    "policy_id",
    "policy_version",
)
_CLAIM_DIGESTS = (
    *_SOURCE_DIGESTS,
    "policy_digest",
    "idempotency_digest",
    "request_fingerprint",
    "canonical_digest",
)
_ATTEMPT_IDENTIFIERS = (
    *_CLAIM_IDENTIFIERS,
    "claim_id",
    "protected_operation_reference",
    "assessor_contract_id",
    "assessor_contract_version",
    "assessor_id",
    "assessor_version",
    "receipt_verification_signing_key_id",
)
_ATTEMPT_DIGESTS = (
    "claim_digest",
    *_SOURCE_DIGESTS,
    "request_nonce_digest",
    "policy_digest",
    "canonical_digest",
)
_INSTRUCTION_IDENTIFIERS = (
    "consumption_id",
    "attempt_id",
    "claim_id",
    "authorization_lease_id",
    "start_result_id",
    "protected_operation_reference",
    "destination_deployment_id",
    "runtime_envelope_id",
    "readiness_profile_id",
    "readiness_profile_version",
    "assessor_contract_id",
    "assessor_contract_version",
    "assessor_id",
    "assessor_version",
    "policy_id",
    "policy_version",
)
_INSTRUCTION_DIGESTS = (
    "attempt_digest",
    "claim_digest",
    "authorization_lease_digest",
    "start_result_digest",
    "destination_fencing_token_digest",
    "protected_slot_commitment",
    "runtime_envelope_commitment",
    "readiness_profile_digest",
    "request_nonce_digest",
    "policy_digest",
    "canonical_digest",
)
_RECEIPT_IDENTIFIERS = (
    "consumption_id",
    "attempt_id",
    "claim_id",
    "authorization_lease_id",
    "start_result_id",
    "protected_operation_reference",
    "destination_deployment_id",
    "runtime_envelope_id",
    "readiness_profile_id",
    "readiness_profile_version",
    "assessor_contract_id",
    "assessor_contract_version",
    "assessor_id",
    "assessor_version",
    "signing_key_id",
    "signature_algorithm",
)
_RECEIPT_DIGESTS = (
    "attempt_digest",
    "claim_digest",
    "instruction_digest",
    "authorization_lease_digest",
    "start_result_digest",
    "destination_fencing_token_digest",
    "protected_slot_commitment",
    "runtime_envelope_commitment",
    "readiness_profile_digest",
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
    "start_result_id",
    "readiness_profile_id",
    "readiness_profile_version",
    "destination_deployment_id",
    "runtime_envelope_id",
    "policy_id",
    "policy_version",
)
_RESULT_DIGESTS = (
    "attempt_digest",
    "claim_digest",
    "authorization_lease_digest",
    "start_result_digest",
    "readiness_profile_digest",
    "destination_fencing_token_digest",
    "protected_slot_commitment",
    "runtime_envelope_commitment",
    "policy_digest",
    "assessor_receipt_digest",
    "canonical_digest",
)


__all__ = [
    "WORKFLOW_PROTECTED_RUNTIME_READINESS_INSTRUCTION_SIGNATURE_ALGORITHM",
    "WORKFLOW_PROTECTED_RUNTIME_READINESS_INSTRUCTION_SIGNING_KEY_ID",
    "WorkflowProtectedRuntimeReadinessAttempt",
    "WorkflowProtectedRuntimeReadinessConsumptionAttemptState",
    "WorkflowProtectedRuntimeReadinessConsumptionAuthority",
    "WorkflowProtectedRuntimeReadinessConsumptionClaim",
    "WorkflowProtectedRuntimeReadinessConsumptionFailureClass",
    "WorkflowProtectedRuntimeReadinessConsumptionPolicy",
    "WorkflowProtectedRuntimeReadinessConsumptionResultState",
    "WorkflowProtectedRuntimeReadinessInstruction",
    "WorkflowProtectedRuntimeReadinessInvocation",
    "WorkflowProtectedRuntimeReadinessReceipt",
    "WorkflowProtectedRuntimeReadinessResult",
    "WorkflowProtectedRuntimeReadinessSignedInstructionEnvelope",
    "code_owned_workflow_protected_runtime_readiness_consumption_policy",
    "code_owned_workflow_protected_runtime_readiness_consumption_policy_values",
]
