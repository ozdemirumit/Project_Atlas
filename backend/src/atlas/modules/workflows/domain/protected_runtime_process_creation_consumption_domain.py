from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum
from functools import lru_cache
from typing import Any, cast

from .models import WorkflowScope, canonical_digest
from .protected_runtime_process_creation_authorization_domain import (
    code_owned_workflow_protected_runtime_process_creation_authorization_policy,
)

WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_INSTRUCTION_SIGNING_KEY_ID = (
    "key.workflow-protected-runtime-process-creation-instruction.v1"
)
WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_INSTRUCTION_SIGNATURE_ALGORITHM = "hmac-sha256"


class WorkflowProtectedRuntimeProcessCreationConsumptionAttemptState(StrEnum):
    PROCESS_CREATION_ATTEMPT_STARTED = "process_creation_attempt_started"


class WorkflowProtectedRuntimeProcessCreationConsumptionResultState(StrEnum):
    PROCESS_CREATED_SUSPENDED_IN_PROTECTED_BOUNDARY = (
        "process_created_suspended_in_protected_boundary"
    )
    PROCESS_CREATION_REJECTED_WITHOUT_CREATION = "process_creation_rejected_without_creation"
    PROCESS_CREATION_FAILED_WITHOUT_CREATION = "process_creation_failed_without_creation"
    PROCESS_CREATION_OUTCOME_UNCERTAIN = "process_creation_outcome_uncertain"


class WorkflowProtectedRuntimeProcessCreationConsumptionFailureClass(StrEnum):
    PROTECTED_CREATOR_REJECTED_WITHOUT_CREATION = "protected_creator_rejected_without_creation"
    PROTECTED_CREATOR_FAILED_WITHOUT_CREATION = "protected_creator_failed_without_creation"
    PROCESS_CREATION_OUTCOME_UNCERTAIN = "process_creation_outcome_uncertain"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationConsumptionAuthority:
    """Immutable evidence. A consumed lease and every result carry zero authority."""

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
        if any(self.canonical_value().values()):
            raise ValueError("process creation consumption grants no authority")

    def canonical_value(self) -> dict[str, bool]:
        return {field.name: cast(bool, getattr(self, field.name)) for field in fields(self)}


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationConsumptionPolicy:
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
    creator_contract_id: str
    creator_contract_version: str
    approved_creator_id: str
    approved_creator_version: str
    instruction_signing_key_id: str
    receipt_verification_signing_key_id: str
    receipt_signature_algorithm: str
    process_creation_profile_id: str
    process_creation_profile_version: str
    process_creation_profile_digest: str
    primitive_id: str
    primitive_version: str
    primitive_digest: str
    minimum_invocation_margin_milliseconds: int
    claim_and_attempt_atomic_required: bool
    commit_before_creator_io_required: bool
    at_most_one_creator_call_required: bool
    automatic_retry_allowed: bool
    exact_replay_no_io_required: bool
    sealed_process_required: bool
    suspended_process_required: bool
    caller_material_forbidden: bool
    scheduling_forbidden: bool
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
            code_owned_workflow_protected_runtime_process_creation_consumption_policy_values()
        )
        if any(getattr(self, name) != value for name, value in expected.items()):
            raise ValueError("process creation consumption policy is not code-owned")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


def code_owned_workflow_protected_runtime_process_creation_consumption_policy_values() -> dict[
    str, object
]:
    source = code_owned_workflow_protected_runtime_process_creation_authorization_policy()
    process_image_digest = canonical_digest(
        {
            "image_id": "image.workflow-protected-runtime-sealed-process",
            "image_version": "1.0",
            "immutable": True,
        }
    )
    process_manifest_digest = canonical_digest(
        {
            "manifest_id": "manifest.workflow-protected-runtime-sealed-process",
            "manifest_version": "1.0",
            "process_image_digest": process_image_digest,
            "caller_material": False,
            "network_enabled": False,
            "initial_state": "suspended_non_runnable",
        }
    )
    primitive = {
        "primitive_id": "primitive.workflow-protected-runtime-create-sealed-suspended-process",
        "primitive_version": "1.0",
        "process_creation_profile_digest": source.process_creation_profile_digest,
        "process_image_digest": process_image_digest,
        "process_manifest_digest": process_manifest_digest,
        "sealed": True,
        "suspended": True,
        "caller_material": False,
    }
    return {
        "policy_id": "policy.workflow-protected-runtime-process-creation-consumption",
        "policy_version": "1.0",
        "source_policy_id": source.policy_id,
        "source_policy_version": source.policy_version,
        "source_policy_digest": source.canonical_digest,
        "consumer_subject_id": source.consumer_subject_id,
        "consumer_audience": source.consumer_audience,
        "consumer_contract_id": source.consumer_contract_id,
        "consumer_contract_version": source.consumer_contract_version,
        "purpose_id": "purpose.workflow-protected-runtime-create-sealed-suspended-process",
        "required_source_state": "authorized_unconsumed",
        "creator_contract_id": "contract.workflow-protected-runtime-sealed-process-creator",
        "creator_contract_version": "1.0",
        "approved_creator_id": "creator.workflow-protected-runtime-sealed-process",
        "approved_creator_version": "1.0",
        "instruction_signing_key_id": (
            WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_INSTRUCTION_SIGNING_KEY_ID
        ),
        "receipt_verification_signing_key_id": (
            "key.workflow-protected-runtime-process-creation-receipt.v1"
        ),
        "receipt_signature_algorithm": "hmac-sha256",
        "process_creation_profile_id": source.process_creation_profile_id,
        "process_creation_profile_version": source.process_creation_profile_version,
        "process_creation_profile_digest": source.process_creation_profile_digest,
        "primitive_id": primitive["primitive_id"],
        "primitive_version": primitive["primitive_version"],
        "primitive_digest": canonical_digest(primitive),
        "minimum_invocation_margin_milliseconds": 100,
        "claim_and_attempt_atomic_required": True,
        "commit_before_creator_io_required": True,
        "at_most_one_creator_call_required": True,
        "automatic_retry_allowed": False,
        "exact_replay_no_io_required": True,
        "sealed_process_required": True,
        "suspended_process_required": True,
        "caller_material_forbidden": True,
        "scheduling_forbidden": True,
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
def code_owned_workflow_protected_runtime_process_creation_consumption_policy() -> (
    WorkflowProtectedRuntimeProcessCreationConsumptionPolicy
):
    values = code_owned_workflow_protected_runtime_process_creation_consumption_policy_values()
    return WorkflowProtectedRuntimeProcessCreationConsumptionPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationConsumptionClaim:
    claim_id: str
    consumption_id: str
    attempt_id: str
    authorization_lease_id: str
    authorization_lease_digest: str
    authorization_claim_id: str
    authorization_claim_digest: str
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
    process_creation_profile_id: str
    process_creation_profile_version: str
    process_creation_profile_digest: str
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
    authority: WorkflowProtectedRuntimeProcessCreationConsumptionAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_process_creation_consumption_policy()
        _require_identifiers(self, _CLAIM_IDENTIFIERS)
        _require_digests(self, _CLAIM_DIGESTS)
        if (
            self.runtime_envelope_generation < 1
            or self.claimed_at.tzinfo is None
            or not _matches_policy(self, policy)
        ):
            raise ValueError("process creation consumption claim is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationAttempt:
    attempt_id: str
    consumption_id: str
    claim_id: str
    claim_digest: str
    authorization_lease_id: str
    authorization_lease_digest: str
    protected_operation_reference: str
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
    process_creation_profile_id: str
    process_creation_profile_version: str
    process_creation_profile_digest: str
    primitive_id: str
    primitive_version: str
    primitive_digest: str
    creator_contract_id: str
    creator_contract_version: str
    creator_id: str
    creator_version: str
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
    state: WorkflowProtectedRuntimeProcessCreationConsumptionAttemptState
    authority: WorkflowProtectedRuntimeProcessCreationConsumptionAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_process_creation_consumption_policy()
        _require_identifiers(self, _ATTEMPT_IDENTIFIERS)
        _require_digests(self, _ATTEMPT_DIGESTS)
        if (
            self.runtime_envelope_generation < 1
            or self.started_at.tzinfo is None
            or self.invocation_deadline.tzinfo is None
            or not self.started_at < self.invocation_deadline
            or self.state
            is not (
                WorkflowProtectedRuntimeProcessCreationConsumptionAttemptState
            ).PROCESS_CREATION_ATTEMPT_STARTED
            or not _matches_policy(self, policy)
            or self.primitive_id != policy.primitive_id
            or self.primitive_version != policy.primitive_version
            or self.primitive_digest != policy.primitive_digest
            or self.creator_contract_id != policy.creator_contract_id
            or self.creator_contract_version != policy.creator_contract_version
            or self.creator_id != policy.approved_creator_id
            or self.creator_version != policy.approved_creator_version
            or self.receipt_verification_signing_key_id
            != policy.receipt_verification_signing_key_id
        ):
            raise ValueError("protected process creation attempt is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationInstruction:
    consumption_id: str
    attempt_id: str
    attempt_digest: str
    claim_id: str
    claim_digest: str
    authorization_lease_id: str
    authorization_lease_digest: str
    protected_operation_reference: str
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
    process_creation_profile_id: str
    process_creation_profile_version: str
    process_creation_profile_digest: str
    primitive_id: str
    primitive_version: str
    primitive_digest: str
    creator_contract_id: str
    creator_contract_version: str
    creator_id: str
    creator_version: str
    request_nonce_digest: str
    scope: WorkflowScope
    policy_id: str
    policy_version: str
    policy_digest: str
    started_at: datetime
    invocation_deadline: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_process_creation_consumption_policy()
        _require_identifiers(self, _INSTRUCTION_IDENTIFIERS)
        _require_digests(self, _INSTRUCTION_DIGESTS)
        if (
            self.runtime_envelope_generation < 1
            or self.started_at.tzinfo is None
            or self.invocation_deadline.tzinfo is None
            or not self.started_at < self.invocation_deadline
            or self.policy_id != policy.policy_id
            or self.policy_version != policy.policy_version
            or self.policy_digest != policy.canonical_digest
            or self.process_creation_profile_digest != policy.process_creation_profile_digest
            or self.primitive_digest != policy.primitive_digest
            or self.creator_id != policy.approved_creator_id
        ):
            raise ValueError("protected process creation instruction is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationSignedInstructionEnvelope:
    instruction: WorkflowProtectedRuntimeProcessCreationInstruction
    signing_key_id: str
    signature_algorithm: str
    integrity_signature: str
    canonical_digest: str

    def __post_init__(self) -> None:
        _require_identifiers(self, ("signing_key_id", "signature_algorithm"))
        _require_digests(self, ("integrity_signature", "canonical_digest"))
        if (
            self.signing_key_id
            != WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_INSTRUCTION_SIGNING_KEY_ID
            or self.signature_algorithm
            != WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_INSTRUCTION_SIGNATURE_ALGORITHM
        ):
            raise ValueError("process creation instruction envelope is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationInvocation:
    protected_operation_reference: str
    instruction_digest: str
    invocation_deadline: datetime
    signed_instruction_envelope: WorkflowProtectedRuntimeProcessCreationSignedInstructionEnvelope

    def __post_init__(self) -> None:
        _require_identifier(self.protected_operation_reference, "protected_operation_reference")
        _require_digest(self.instruction_digest, "instruction_digest")
        instruction = self.signed_instruction_envelope.instruction
        if (
            self.invocation_deadline.tzinfo is None
            or self.instruction_digest != instruction.canonical_digest
            or self.invocation_deadline != instruction.invocation_deadline
        ):
            raise ValueError("process creation invocation is invalid")


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeProcessCreationReceipt:
    consumption_id: str
    attempt_id: str
    instruction_digest: str
    protected_operation_reference: str
    authorization_lease_id: str
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
    process_creation_profile_id: str
    process_creation_profile_version: str
    process_creation_profile_digest: str
    primitive_id: str
    primitive_version: str
    primitive_digest: str
    request_nonce_digest: str
    result_state: WorkflowProtectedRuntimeProcessCreationConsumptionResultState
    process_created: bool
    process_sealed: bool
    process_suspended: bool
    process_scheduled: bool
    process_resumed: bool
    process_dispatched: bool
    process_executed: bool
    caller_material_used: bool
    runtime_locator_returned: bool
    process_identifier_returned: bool
    network_activity_performed: bool
    model_activity_performed: bool
    mcp_activity_performed: bool
    connector_activity_performed: bool
    provider_activity_performed: bool
    infrastructure_mutation_performed: bool
    creator_contract_id: str
    creator_contract_version: str
    creator_id: str
    creator_version: str
    signing_key_id: str
    signature_algorithm: str
    completed_at: datetime
    integrity_signature: str
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_process_creation_consumption_policy()
        _require_identifiers(self, _RECEIPT_IDENTIFIERS)
        _require_digests(self, _RECEIPT_DIGESTS)
        forbidden = (
            self.process_scheduled,
            self.process_resumed,
            self.process_dispatched,
            self.process_executed,
            self.caller_material_used,
            self.runtime_locator_returned,
            self.process_identifier_returned,
            self.network_activity_performed,
            self.model_activity_performed,
            self.mcp_activity_performed,
            self.connector_activity_performed,
            self.provider_activity_performed,
            self.infrastructure_mutation_performed,
        )
        success = (
            self.result_state
            is (
                WorkflowProtectedRuntimeProcessCreationConsumptionResultState
            ).PROCESS_CREATED_SUSPENDED_IN_PROTECTED_BOUNDARY
        )
        known_no_creation = self.result_state in {
            WorkflowProtectedRuntimeProcessCreationConsumptionResultState.PROCESS_CREATION_REJECTED_WITHOUT_CREATION,
            WorkflowProtectedRuntimeProcessCreationConsumptionResultState.PROCESS_CREATION_FAILED_WITHOUT_CREATION,
        }
        if (
            self.runtime_envelope_generation < 1
            or self.completed_at.tzinfo is None
            or any(forbidden)
            or self.process_created is not success
            or self.process_sealed is not success
            or self.process_suspended is not success
            or (not success and not known_no_creation)
            or self.creator_contract_id != policy.creator_contract_id
            or self.creator_contract_version != policy.creator_contract_version
            or self.creator_id != policy.approved_creator_id
            or self.creator_version != policy.approved_creator_version
            or self.signing_key_id != policy.receipt_verification_signing_key_id
            or self.signature_algorithm != policy.receipt_signature_algorithm
        ):
            raise ValueError("process creation receipt is invalid")
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
class WorkflowProtectedRuntimeProcessCreationResult:
    result_id: str
    consumption_id: str
    attempt_id: str
    attempt_digest: str
    claim_id: str
    claim_digest: str
    authorization_lease_id: str
    authorization_lease_digest: str
    receipt_digest: str | None
    result_state: WorkflowProtectedRuntimeProcessCreationConsumptionResultState
    failure_class: WorkflowProtectedRuntimeProcessCreationConsumptionFailureClass | None
    outcome_known: bool
    process_created: bool | None
    process_sealed: bool | None
    process_suspended: bool | None
    process_scheduled: bool
    process_resumed: bool
    process_dispatched: bool
    process_executed: bool
    runtime_envelope_id: str
    runtime_envelope_commitment: str
    runtime_envelope_generation: int
    process_creation_profile_id: str
    process_creation_profile_version: str
    process_creation_profile_digest: str
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
    authority: WorkflowProtectedRuntimeProcessCreationConsumptionAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_process_creation_consumption_policy()
        _require_identifiers(self, _RESULT_IDENTIFIERS)
        _require_digests(self, _RESULT_DIGESTS)
        success = (
            self.result_state
            is (
                WorkflowProtectedRuntimeProcessCreationConsumptionResultState
            ).PROCESS_CREATED_SUSPENDED_IN_PROTECTED_BOUNDARY
        )
        uncertain = (
            self.result_state
            is (
                WorkflowProtectedRuntimeProcessCreationConsumptionResultState
            ).PROCESS_CREATION_OUTCOME_UNCERTAIN
        )
        if (
            self.completed_at.tzinfo is None
            or self.recorded_at.tzinfo is None
            or self.recorded_at < self.completed_at
            or (
                uncertain
                and any(
                    value is not None
                    for value in (
                        self.process_created,
                        self.process_sealed,
                        self.process_suspended,
                    )
                )
            )
            or (
                not uncertain
                and any(
                    value is not success
                    for value in (
                        self.process_created,
                        self.process_sealed,
                        self.process_suspended,
                    )
                )
            )
            or self.process_scheduled
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
            raise ValueError("process creation result is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


def _matches_policy(
    instance: object, policy: WorkflowProtectedRuntimeProcessCreationConsumptionPolicy
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
            ("process_creation_profile_id", policy.process_creation_profile_id),
            ("process_creation_profile_version", policy.process_creation_profile_version),
            ("process_creation_profile_digest", policy.process_creation_profile_digest),
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


_CLAIM_IDENTIFIERS = (
    "claim_id",
    "consumption_id",
    "attempt_id",
    "authorization_lease_id",
    "authorization_claim_id",
    "runtime_envelope_id",
    "process_creation_profile_id",
    "process_creation_profile_version",
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
    "runtime_envelope_commitment",
    "process_creation_profile_digest",
    "policy_digest",
    "idempotency_digest",
    "request_fingerprint",
    "canonical_digest",
)
_ATTEMPT_IDENTIFIERS = (
    "attempt_id",
    "consumption_id",
    "claim_id",
    "authorization_lease_id",
    "protected_operation_reference",
    "runtime_envelope_id",
    "process_creation_profile_id",
    "process_creation_profile_version",
    "primitive_id",
    "primitive_version",
    "creator_contract_id",
    "creator_contract_version",
    "creator_id",
    "creator_version",
    "receipt_verification_signing_key_id",
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
    "authorization_lease_digest",
    "runtime_envelope_commitment",
    "process_creation_profile_digest",
    "primitive_digest",
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
    "runtime_envelope_id",
    "process_creation_profile_id",
    "process_creation_profile_version",
    "primitive_id",
    "primitive_version",
    "creator_contract_id",
    "creator_contract_version",
    "creator_id",
    "creator_version",
    "policy_id",
    "policy_version",
)
_INSTRUCTION_DIGESTS = (
    "attempt_digest",
    "claim_digest",
    "authorization_lease_digest",
    "runtime_envelope_commitment",
    "process_creation_profile_digest",
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
    "runtime_envelope_id",
    "process_creation_profile_id",
    "process_creation_profile_version",
    "primitive_id",
    "primitive_version",
    "creator_contract_id",
    "creator_contract_version",
    "creator_id",
    "creator_version",
    "signing_key_id",
    "signature_algorithm",
)
_RECEIPT_DIGESTS = (
    "instruction_digest",
    "runtime_envelope_commitment",
    "process_creation_profile_digest",
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
    "authorization_lease_id",
    "runtime_envelope_id",
    "process_creation_profile_id",
    "process_creation_profile_version",
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
_RESULT_DIGESTS = (
    "attempt_digest",
    "claim_digest",
    "authorization_lease_digest",
    "receipt_digest",
    "runtime_envelope_commitment",
    "process_creation_profile_digest",
    "primitive_digest",
    "policy_digest",
    "canonical_digest",
)


__all__ = [
    "WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_INSTRUCTION_SIGNATURE_ALGORITHM",
    "WORKFLOW_PROTECTED_RUNTIME_PROCESS_CREATION_INSTRUCTION_SIGNING_KEY_ID",
    "WorkflowProtectedRuntimeProcessCreationAttempt",
    "WorkflowProtectedRuntimeProcessCreationConsumptionAttemptState",
    "WorkflowProtectedRuntimeProcessCreationConsumptionAuthority",
    "WorkflowProtectedRuntimeProcessCreationConsumptionClaim",
    "WorkflowProtectedRuntimeProcessCreationConsumptionFailureClass",
    "WorkflowProtectedRuntimeProcessCreationConsumptionPolicy",
    "WorkflowProtectedRuntimeProcessCreationConsumptionResultState",
    "WorkflowProtectedRuntimeProcessCreationInstruction",
    "WorkflowProtectedRuntimeProcessCreationInvocation",
    "WorkflowProtectedRuntimeProcessCreationReceipt",
    "WorkflowProtectedRuntimeProcessCreationResult",
    "WorkflowProtectedRuntimeProcessCreationSignedInstructionEnvelope",
    "code_owned_workflow_protected_runtime_process_creation_consumption_policy",
    "code_owned_workflow_protected_runtime_process_creation_consumption_policy_values",
]
