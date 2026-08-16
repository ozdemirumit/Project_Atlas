from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum
from typing import Any, cast

from .models import (
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_runtime_context_injection_authorization_policy,
)


class WorkflowProtectedRuntimeContextInjectionConsumptionAttemptState(StrEnum):
    STARTED = "started"


class WorkflowProtectedRuntimeContextInjectionConsumptionResultState(StrEnum):
    INJECTED_INTO_PROTECTED_RUNTIME_SLOT = "injected_into_protected_runtime_slot"
    INJECTION_FAILED = "injection_failed"
    INJECTION_OUTCOME_UNCERTAIN = "injection_outcome_uncertain"


class WorkflowProtectedRuntimeContextInjectionConsumptionFailureClass(StrEnum):
    TRUSTED_INJECTOR_REJECTED = "trusted_injector_rejected"
    SLOT_COMPARE_AND_SWAP_REJECTED = "slot_compare_and_swap_rejected"
    DEADLINE_EXPIRED = "deadline_expired"
    INJECTION_OUTCOME_UNCERTAIN = "injection_outcome_uncertain"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextInjectionConsumptionAuthority:
    """Explicit zero-authority evidence after the protected-slot mutation boundary."""

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

    def __post_init__(self) -> None:
        if any(self.canonical_value().values()):
            raise ValueError("runtime context injection consumption grants no authority")

    def canonical_value(self) -> dict[str, bool]:
        return {field.name: cast(bool, getattr(self, field.name)) for field in fields(self)}


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextInjectionConsumptionPolicy:
    policy_id: str
    policy_version: str
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    required_lifecycle_attestor_id: str
    required_lifecycle_attestor_version: str
    required_slot_readiness_attestor_id: str
    required_slot_readiness_attestor_version: str
    required_injector_contract_id: str
    required_injector_contract_version: str
    approved_injector_id: str
    approved_injector_version: str
    runtime_slot_profile_id: str
    runtime_slot_profile_version: str
    runtime_slot_profile_digest: str
    slot_readiness_verification_signing_key_id: str
    receipt_verification_signing_key_id: str
    minimum_remaining_budget_milliseconds: int
    irreversible_consumption_acknowledgement_required: bool
    uncertain_outcome_requires_new_authorization_acknowledgement_required: bool
    automatic_retry_allowed: bool
    runtime_autostart_forbidden: bool
    network_activity_forbidden: bool
    connector_activity_forbidden: bool
    readiness_probe_forbidden: bool
    execution_forbidden: bool
    infrastructure_mutation_forbidden: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        expected = (
            code_owned_workflow_protected_runtime_context_injection_consumption_policy_values()
        )
        if any(getattr(self, name) != value for name, value in expected.items()):
            raise ValueError("runtime context injection consumption policy is not code-owned")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("runtime context injection consumption policy digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


def code_owned_workflow_protected_runtime_context_injection_consumption_policy_values() -> dict[
    str, object
]:
    authorization = code_owned_workflow_protected_runtime_context_injection_authorization_policy()
    return {
        "policy_id": "policy.workflow-protected-runtime-context-injection-consumption",
        "policy_version": "1.0",
        "consumer_subject_id": authorization.consumer_subject_id,
        "consumer_audience": authorization.consumer_audience,
        "consumer_contract_id": authorization.consumer_contract_id,
        "consumer_contract_version": authorization.consumer_contract_version,
        "purpose_id": "purpose.workflow-protected-runtime-context-injection-consumption",
        "required_lifecycle_attestor_id": authorization.required_attestor_id,
        "required_lifecycle_attestor_version": authorization.required_attestor_version,
        "required_slot_readiness_attestor_id": (
            "attestor.workflow-protected-runtime-context-slot-readiness"
        ),
        "required_slot_readiness_attestor_version": "1.0",
        "required_injector_contract_id": authorization.required_injector_contract_id,
        "required_injector_contract_version": authorization.required_injector_contract_version,
        "approved_injector_id": authorization.approved_injector_id,
        "approved_injector_version": authorization.approved_injector_version,
        "runtime_slot_profile_id": authorization.runtime_slot_profile_id,
        "runtime_slot_profile_version": authorization.runtime_slot_profile_version,
        "runtime_slot_profile_digest": authorization.runtime_slot_profile_digest,
        "slot_readiness_verification_signing_key_id": (
            "key.workflow-protected-runtime-context-slot-readiness.v1"
        ),
        "receipt_verification_signing_key_id": (
            "key.workflow-protected-runtime-context-injection-receipt.v1"
        ),
        "minimum_remaining_budget_milliseconds": 100,
        "irreversible_consumption_acknowledgement_required": True,
        "uncertain_outcome_requires_new_authorization_acknowledgement_required": True,
        "automatic_retry_allowed": False,
        "runtime_autostart_forbidden": True,
        "network_activity_forbidden": True,
        "connector_activity_forbidden": True,
        "readiness_probe_forbidden": True,
        "execution_forbidden": True,
        "infrastructure_mutation_forbidden": True,
    }


def code_owned_workflow_protected_runtime_context_injection_consumption_policy() -> (
    WorkflowProtectedRuntimeContextInjectionConsumptionPolicy
):
    values = code_owned_workflow_protected_runtime_context_injection_consumption_policy_values()
    return WorkflowProtectedRuntimeContextInjectionConsumptionPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextInjectionConsumptionClaim:
    claim_id: str
    injection_id: str
    attempt_id: str
    authorization_lease_id: str
    authorization_lease_digest: str
    protected_runtime_handle_digest: str
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_slot_commitment: str
    runtime_slot_pre_generation: int
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    policy_id: str
    policy_version: str
    policy_digest: str
    irreversible_consumption_acknowledged: bool
    uncertain_outcome_requires_new_authorization_acknowledged: bool
    request_fingerprint: str
    idempotency_digest: str
    consumption_authorization_audit_digest: str
    claimed_at: datetime
    authority: WorkflowProtectedRuntimeContextInjectionConsumptionAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_context_injection_consumption_policy()
        _require_identifiers(self, _CLAIM_IDENTIFIERS)
        _require_digests(self, _CLAIM_DIGESTS)
        if (
            self.claimed_at.tzinfo is None
            or self.destination_generation < 1
            or self.runtime_slot_pre_generation < 0
            or self.consumer_subject_id != policy.consumer_subject_id
            or self.consumer_audience != policy.consumer_audience
            or self.consumer_contract_id != policy.consumer_contract_id
            or self.consumer_contract_version != policy.consumer_contract_version
            or self.purpose_id != policy.purpose_id
            or self.policy_id != policy.policy_id
            or self.policy_version != policy.policy_version
            or self.policy_digest != policy.canonical_digest
            or self.irreversible_consumption_acknowledged is not True
            or self.uncertain_outcome_requires_new_authorization_acknowledged is not True
        ):
            raise ValueError("runtime context injection consumption claim is invalid")
        _require_zero_authority(self.authority)
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextInjectionConsumptionAttempt:
    attempt_id: str
    injection_id: str
    consumption_claim_id: str
    consumption_claim_digest: str
    authorization_lease_id: str
    authorization_lease_digest: str
    protected_runtime_handle_digest: str
    protected_operation_reference: str
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_slot_profile_id: str
    runtime_slot_profile_version: str
    runtime_slot_profile_digest: str
    runtime_slot_commitment: str
    runtime_slot_pre_generation: int
    expected_runtime_slot_post_generation: int
    required_injector_contract_id: str
    required_injector_contract_version: str
    approved_injector_id: str
    approved_injector_version: str
    receipt_verification_signing_key_id: str
    lifecycle_attestation_id: str
    lifecycle_attestation_digest: str
    slot_readiness_attestation_id: str
    slot_readiness_attestation_digest: str
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
    injection_deadline: datetime
    authorization_lease_valid_until: datetime
    protected_runtime_handle_usable_until: datetime
    lifecycle_attestation_valid_until: datetime
    slot_readiness_attestation_valid_until: datetime
    state: WorkflowProtectedRuntimeContextInjectionConsumptionAttemptState
    authority: WorkflowProtectedRuntimeContextInjectionConsumptionAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = code_owned_workflow_protected_runtime_context_injection_consumption_policy()
        _require_identifiers(self, _ATTEMPT_IDENTIFIERS)
        _require_digests(self, _ATTEMPT_DIGESTS)
        deadlines = (
            self.authorization_lease_valid_until,
            self.protected_runtime_handle_usable_until,
            self.lifecycle_attestation_valid_until,
            self.slot_readiness_attestation_valid_until,
        )
        if (
            self.started_at.tzinfo is None
            or self.injection_deadline.tzinfo is None
            or any(value.tzinfo is None for value in deadlines)
            or not self.started_at < self.injection_deadline <= min(deadlines)
            or self.runtime_slot_pre_generation < 0
            or self.expected_runtime_slot_post_generation != self.runtime_slot_pre_generation + 1
            or self.state
            is not WorkflowProtectedRuntimeContextInjectionConsumptionAttemptState.STARTED
            or self.consumer_subject_id != policy.consumer_subject_id
            or self.consumer_audience != policy.consumer_audience
            or self.consumer_contract_id != policy.consumer_contract_id
            or self.consumer_contract_version != policy.consumer_contract_version
            or self.purpose_id != policy.purpose_id
            or self.policy_id != policy.policy_id
            or self.policy_version != policy.policy_version
            or self.policy_digest != policy.canonical_digest
            or self.required_injector_contract_id != policy.required_injector_contract_id
            or self.required_injector_contract_version != policy.required_injector_contract_version
            or self.approved_injector_id != policy.approved_injector_id
            or self.approved_injector_version != policy.approved_injector_version
            or self.runtime_slot_profile_id != policy.runtime_slot_profile_id
            or self.runtime_slot_profile_version != policy.runtime_slot_profile_version
            or self.runtime_slot_profile_digest != policy.runtime_slot_profile_digest
            or self.receipt_verification_signing_key_id
            != policy.receipt_verification_signing_key_id
        ):
            raise ValueError("runtime context injection consumption attempt is invalid")
        _require_zero_authority(self.authority)
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextTrustedInjectorInstruction:
    injection_id: str
    attempt_id: str
    consumption_claim_id: str
    authorization_lease_id: str
    authorization_lease_digest: str
    protected_runtime_handle_digest: str
    protected_operation_reference: str
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_slot_profile_id: str
    runtime_slot_profile_version: str
    runtime_slot_profile_digest: str
    runtime_slot_commitment: str
    runtime_slot_pre_generation: int
    expected_runtime_slot_post_generation: int
    injector_contract_id: str
    injector_contract_version: str
    injector_id: str
    injector_version: str
    started_at: datetime
    injection_deadline: datetime
    canonical_digest: str

    def __post_init__(self) -> None:
        _require_identifiers(self, _INSTRUCTION_IDENTIFIERS)
        _require_digests(self, _INSTRUCTION_DIGESTS)
        if (
            self.started_at.tzinfo is None
            or self.injection_deadline.tzinfo is None
            or not self.started_at < self.injection_deadline
            or self.expected_runtime_slot_post_generation != self.runtime_slot_pre_generation + 1
        ):
            raise ValueError("runtime context injector instruction is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextTrustedInjectorInvocation:
    """The complete and exclusive payload allowed to cross into the trusted injector."""

    protected_operation_reference: str
    instruction_digest: str
    injection_deadline: datetime

    def __post_init__(self) -> None:
        _require_identifiers(self, ("protected_operation_reference",))
        _require_digests(self, ("instruction_digest",))
        if self.injection_deadline.tzinfo is None:
            raise ValueError("runtime context injector invocation deadline must be aware")


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextTrustedInjectorReceipt:
    instruction_digest: str
    protected_operation_reference: str
    runtime_slot_pre_generation: int
    runtime_slot_post_generation: int
    injector_contract_id: str
    injector_contract_version: str
    injector_id: str
    injector_version: str
    state: WorkflowProtectedRuntimeContextInjectionConsumptionResultState
    failure_class: WorkflowProtectedRuntimeContextInjectionConsumptionFailureClass | None
    protected_runtime_handle_consumed: bool
    inert_context_injected: bool
    runtime_slot_mutation_performed: bool
    runtime_slot_empty_confirmed: bool
    temporary_material_zeroized: bool
    runtime_started: bool
    runtime_resumed: bool
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
    injection_deadline: datetime
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
            is WorkflowProtectedRuntimeContextInjectionConsumptionResultState.INJECTED_INTO_PROTECTED_RUNTIME_SLOT  # noqa: E501
        )
        failure = (
            self.state
            is WorkflowProtectedRuntimeContextInjectionConsumptionResultState.INJECTION_FAILED
        )
        forbidden_effects = (
            self.runtime_started,
            self.runtime_resumed,
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
            or self.injection_deadline.tzinfo is None
            or self.completed_at >= self.injection_deadline
            or not (success or failure)
            or any(forbidden_effects)
            or self.temporary_material_zeroized is not True
            or (success and self.failure_class is not None)
            or (
                success
                and self.runtime_slot_post_generation != self.runtime_slot_pre_generation + 1
            )
            or (success and self.protected_runtime_handle_consumed is not True)
            or (success and self.inert_context_injected is not True)
            or (success and self.runtime_slot_mutation_performed is not True)
            or (failure and self.failure_class is None)
            or (failure and self.runtime_slot_post_generation != self.runtime_slot_pre_generation)
            or (failure and self.protected_runtime_handle_consumed is not False)
            or (failure and self.inert_context_injected is not False)
            or (failure and self.runtime_slot_mutation_performed is not False)
            or (failure and self.runtime_slot_empty_confirmed is not True)
        ):
            raise ValueError("runtime context injector receipt is invalid")
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
class WorkflowProtectedRuntimeContextInjectionConsumptionResult:
    result_id: str
    injection_id: str
    attempt_id: str
    attempt_digest: str
    consumption_claim_id: str
    consumption_claim_digest: str
    authorization_lease_id: str
    authorization_lease_digest: str
    protected_runtime_handle_digest: str
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_slot_profile_id: str
    runtime_slot_profile_version: str
    runtime_slot_profile_digest: str
    runtime_slot_commitment: str
    runtime_slot_pre_generation: int
    runtime_slot_post_generation: int | None
    injector_contract_id: str
    injector_contract_version: str
    injector_id: str
    injector_version: str
    injector_receipt_digest: str | None
    state: WorkflowProtectedRuntimeContextInjectionConsumptionResultState
    failure_class: WorkflowProtectedRuntimeContextInjectionConsumptionFailureClass | None
    outcome_known: bool
    protected_runtime_handle_consumed: bool | None
    inert_context_injected: bool
    runtime_slot_mutation_performed: bool
    completed_at: datetime | None
    recorded_at: datetime
    injection_deadline: datetime
    authority: WorkflowProtectedRuntimeContextInjectionConsumptionAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        _require_identifiers(self, _RESULT_IDENTIFIERS)
        _require_digests(self, _RESULT_DIGESTS, optional=("injector_receipt_digest",))
        success = (
            self.state
            is WorkflowProtectedRuntimeContextInjectionConsumptionResultState.INJECTED_INTO_PROTECTED_RUNTIME_SLOT  # noqa: E501
        )
        failure = (
            self.state
            is WorkflowProtectedRuntimeContextInjectionConsumptionResultState.INJECTION_FAILED
        )
        uncertain = (
            self.state
            is WorkflowProtectedRuntimeContextInjectionConsumptionResultState.INJECTION_OUTCOME_UNCERTAIN  # noqa: E501
        )
        if (
            self.recorded_at.tzinfo is None
            or self.injection_deadline.tzinfo is None
            or (self.completed_at is not None and self.completed_at.tzinfo is None)
            or (success and not self._known_success_is_valid())
            or (failure and not self._known_failure_is_valid())
            or (uncertain and not self._uncertainty_is_valid())
            or not (success or failure or uncertain)
        ):
            raise ValueError("runtime context injection consumption result is invalid")
        _require_zero_authority(self.authority)
        _require_canonical_digest(self)

    def _known_success_is_valid(self) -> bool:
        return (
            self.injector_receipt_digest is not None
            and self.failure_class is None
            and self.outcome_known is True
            and self.protected_runtime_handle_consumed is True
            and self.inert_context_injected is True
            and self.runtime_slot_mutation_performed is True
            and self.runtime_slot_post_generation == self.runtime_slot_pre_generation + 1
            and self.completed_at is not None
            and self.completed_at < self.injection_deadline
            and self.recorded_at >= self.completed_at
        )

    def _known_failure_is_valid(self) -> bool:
        return (
            self.injector_receipt_digest is not None
            and self.failure_class is not None
            and self.outcome_known is True
            and self.protected_runtime_handle_consumed is False
            and self.inert_context_injected is False
            and self.runtime_slot_mutation_performed is False
            and self.runtime_slot_post_generation == self.runtime_slot_pre_generation
            and self.completed_at is not None
            and self.completed_at < self.injection_deadline
            and self.recorded_at >= self.completed_at
        )

    def _uncertainty_is_valid(self) -> bool:
        return (
            self.injector_receipt_digest is None
            and self.failure_class
            is WorkflowProtectedRuntimeContextInjectionConsumptionFailureClass.INJECTION_OUTCOME_UNCERTAIN  # noqa: E501
            and self.outcome_known is False
            and self.protected_runtime_handle_consumed is None
            and self.inert_context_injected is False
            and self.runtime_slot_mutation_performed is False
            and self.runtime_slot_post_generation is None
            and self.completed_at is None
        )

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


_CLAIM_IDENTIFIERS = (
    "claim_id",
    "injection_id",
    "attempt_id",
    "authorization_lease_id",
    "destination_boundary_id",
    "destination_deployment_id",
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
    "protected_runtime_handle_digest",
    "destination_fencing_token_digest",
    "runtime_slot_commitment",
    "policy_digest",
    "request_fingerprint",
    "idempotency_digest",
    "consumption_authorization_audit_digest",
    "canonical_digest",
)
_ATTEMPT_IDENTIFIERS = (
    "attempt_id",
    "injection_id",
    "consumption_claim_id",
    "authorization_lease_id",
    "protected_operation_reference",
    "destination_boundary_id",
    "destination_deployment_id",
    "runtime_slot_profile_id",
    "runtime_slot_profile_version",
    "required_injector_contract_id",
    "required_injector_contract_version",
    "approved_injector_id",
    "approved_injector_version",
    "receipt_verification_signing_key_id",
    "lifecycle_attestation_id",
    "slot_readiness_attestation_id",
    "consumer_subject_id",
    "consumer_audience",
    "consumer_contract_id",
    "consumer_contract_version",
    "purpose_id",
    "policy_id",
    "policy_version",
)
_ATTEMPT_DIGESTS = (
    "consumption_claim_digest",
    "authorization_lease_digest",
    "protected_runtime_handle_digest",
    "destination_fencing_token_digest",
    "runtime_slot_profile_digest",
    "runtime_slot_commitment",
    "lifecycle_attestation_digest",
    "slot_readiness_attestation_digest",
    "request_nonce_digest",
    "policy_digest",
    "canonical_digest",
)
_INSTRUCTION_IDENTIFIERS = (
    "injection_id",
    "attempt_id",
    "consumption_claim_id",
    "authorization_lease_id",
    "protected_operation_reference",
    "destination_boundary_id",
    "destination_deployment_id",
    "runtime_slot_profile_id",
    "runtime_slot_profile_version",
    "injector_contract_id",
    "injector_contract_version",
    "injector_id",
    "injector_version",
)
_INSTRUCTION_DIGESTS = (
    "authorization_lease_digest",
    "protected_runtime_handle_digest",
    "destination_fencing_token_digest",
    "runtime_slot_profile_digest",
    "runtime_slot_commitment",
    "canonical_digest",
)
_RECEIPT_IDENTIFIERS = (
    "protected_operation_reference",
    "injector_contract_id",
    "injector_contract_version",
    "injector_id",
    "injector_version",
    "attested_by",
    "signing_key_id",
    "signature_algorithm",
)
_RECEIPT_DIGESTS = ("instruction_digest", "integrity_signature", "canonical_digest")
_RESULT_IDENTIFIERS = (
    "result_id",
    "injection_id",
    "attempt_id",
    "consumption_claim_id",
    "authorization_lease_id",
    "destination_boundary_id",
    "destination_deployment_id",
    "runtime_slot_profile_id",
    "runtime_slot_profile_version",
    "injector_contract_id",
    "injector_contract_version",
    "injector_id",
    "injector_version",
)
_RESULT_DIGESTS = (
    "attempt_digest",
    "consumption_claim_digest",
    "authorization_lease_digest",
    "protected_runtime_handle_digest",
    "destination_fencing_token_digest",
    "runtime_slot_profile_digest",
    "runtime_slot_commitment",
    "injector_receipt_digest",
    "canonical_digest",
)


def _require_identifiers(instance: object, names: tuple[str, ...]) -> None:
    for name in names:
        value = getattr(instance, name)
        if not isinstance(value, str) or not value or value != value.strip() or len(value) > 240:
            raise ValueError(f"invalid runtime context injection identifier: {name}")


def _require_digests(
    instance: object, names: tuple[str, ...], *, optional: tuple[str, ...] = ()
) -> None:
    for name in names:
        value = getattr(instance, name)
        if name in optional and value is None:
            continue
        if not isinstance(value, str) or len(value) != 64:
            raise ValueError(f"invalid runtime context injection digest: {name}")
        try:
            int(value, 16)
        except ValueError as error:
            raise ValueError(f"invalid runtime context injection digest: {name}") from error


def _require_zero_authority(
    authority: WorkflowProtectedRuntimeContextInjectionConsumptionAuthority,
) -> None:
    values = authority.canonical_value()
    if len(values) != 22 or any(values.values()):
        raise ValueError("runtime context injection consumption must have 22 false authorities")


def _require_canonical_digest(instance: Any) -> None:
    if instance.canonical_digest != canonical_digest(instance.digest_payload()):
        raise ValueError("runtime context injection canonical digest mismatch")


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
    "WorkflowProtectedRuntimeContextInjectionConsumptionAttempt",
    "WorkflowProtectedRuntimeContextInjectionConsumptionAttemptState",
    "WorkflowProtectedRuntimeContextInjectionConsumptionAuthority",
    "WorkflowProtectedRuntimeContextInjectionConsumptionClaim",
    "WorkflowProtectedRuntimeContextInjectionConsumptionFailureClass",
    "WorkflowProtectedRuntimeContextInjectionConsumptionPolicy",
    "WorkflowProtectedRuntimeContextInjectionConsumptionResult",
    "WorkflowProtectedRuntimeContextInjectionConsumptionResultState",
    "WorkflowProtectedRuntimeContextTrustedInjectorInstruction",
    "WorkflowProtectedRuntimeContextTrustedInjectorInvocation",
    "WorkflowProtectedRuntimeContextTrustedInjectorReceipt",
    "code_owned_workflow_protected_runtime_context_injection_consumption_policy",
    "code_owned_workflow_protected_runtime_context_injection_consumption_policy_values",
]
