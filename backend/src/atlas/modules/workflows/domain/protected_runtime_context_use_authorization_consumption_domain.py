from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum
from typing import Any, cast

from .models import WorkflowScope, canonical_digest
from .protected_runtime_context_use_authorization_domain import (
    WorkflowProtectedRuntimeContextUseAuthorizationLeaseState,
    code_owned_workflow_protected_runtime_context_use_authorization_policy,
)


class WorkflowProtectedRuntimeContextUseAuthorizationConsumptionState(StrEnum):
    AUTHORIZATION_CONSUMED_WITHOUT_RUNTIME_USE = "authorization_consumed_without_runtime_use"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseAuthorizationConsumptionAuthority:
    """Historical consumption evidence that grants no authority of any kind."""

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
            raise ValueError("runtime context use consumption cannot grant authority")

    def canonical_value(self) -> dict[str, bool]:
        return {field.name: cast(bool, getattr(self, field.name)) for field in fields(self)}


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPolicy:
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
    irreversible_acknowledgement_required: bool
    durable_replay_required: bool
    atomic_claim_and_result_required: bool
    external_io_forbidden: bool
    context_access_forbidden: bool
    context_use_forbidden: bool
    runtime_start_forbidden: bool
    runtime_resume_forbidden: bool
    network_activity_forbidden: bool
    connector_activity_forbidden: bool
    publication_forbidden: bool
    delivery_forbidden: bool
    dispatch_forbidden: bool
    execution_forbidden: bool
    infrastructure_mutation_forbidden: bool
    renewal_forbidden: bool
    transfer_forbidden: bool
    replacement_forbidden: bool
    retry_forbidden: bool
    canonical_digest: str

    def __post_init__(self) -> None:
        expected = code_owned_workflow_protected_runtime_context_use_authorization_consumption_policy_values()  # noqa: E501
        if any(getattr(self, name) != value for name, value in expected.items()):
            raise ValueError("runtime context use consumption policy is not code-owned")
        if self.canonical_digest != canonical_digest(self.digest_payload()):
            raise ValueError("runtime context use consumption policy digest mismatch")

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


def code_owned_workflow_protected_runtime_context_use_authorization_consumption_policy_values() -> (
    dict[str, object]
):
    source = code_owned_workflow_protected_runtime_context_use_authorization_policy()
    return {
        "policy_id": ("policy.workflow-protected-runtime-context-use-authorization-consumption"),
        "policy_version": "1.0",
        "source_policy_id": source.policy_id,
        "source_policy_version": source.policy_version,
        "source_policy_digest": source.canonical_digest,
        "consumer_subject_id": source.consumer_subject_id,
        "consumer_audience": source.consumer_audience,
        "consumer_contract_id": source.consumer_contract_id,
        "consumer_contract_version": source.consumer_contract_version,
        "purpose_id": ("purpose.workflow-protected-runtime-context-use-authorization-consumption"),
        "required_source_state": (
            WorkflowProtectedRuntimeContextUseAuthorizationLeaseState.AUTHORIZED_UNCONSUMED.value
        ),
        "irreversible_acknowledgement_required": True,
        "durable_replay_required": True,
        "atomic_claim_and_result_required": True,
        "external_io_forbidden": True,
        "context_access_forbidden": True,
        "context_use_forbidden": True,
        "runtime_start_forbidden": True,
        "runtime_resume_forbidden": True,
        "network_activity_forbidden": True,
        "connector_activity_forbidden": True,
        "publication_forbidden": True,
        "delivery_forbidden": True,
        "dispatch_forbidden": True,
        "execution_forbidden": True,
        "infrastructure_mutation_forbidden": True,
        "renewal_forbidden": True,
        "transfer_forbidden": True,
        "replacement_forbidden": True,
        "retry_forbidden": True,
    }


def code_owned_workflow_protected_runtime_context_use_authorization_consumption_policy() -> (
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPolicy
):
    values = (
        code_owned_workflow_protected_runtime_context_use_authorization_consumption_policy_values()
    )
    return WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPolicy(
        **cast(Any, values), canonical_digest=canonical_digest(values)
    )


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseAuthorizationConsumptionClaim:
    consumption_claim_id: str
    consumption_id: str
    authorization_lease_id: str
    authorization_lease_digest: str
    authorization_claim_id: str
    authorization_claim_digest: str
    injection_result_id: str
    injection_result_digest: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    runtime_slot_commitment: str
    runtime_slot_post_generation: int
    injected_context_usable_until: datetime
    use_profile_id: str
    use_profile_version: str
    use_profile_digest: str
    source_lease_state: WorkflowProtectedRuntimeContextUseAuthorizationLeaseState
    source_lease_issued_at: datetime
    source_lease_valid_until: datetime
    source_lease_effective_until: datetime
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    policy_id: str
    policy_version: str
    policy_digest: str
    source_policy_id: str
    source_policy_version: str
    source_policy_digest: str
    idempotency_digest: str
    request_fingerprint: str
    irreversible_consumption_acknowledged: bool
    consumption_audit_digest: str
    claimed_at: datetime
    authority: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = (
            code_owned_workflow_protected_runtime_context_use_authorization_consumption_policy()
        )
        _require_identifiers(self, _CLAIM_IDENTIFIERS)
        _require_digests(self, _CLAIM_DIGESTS)
        if (
            self.destination_generation < 1
            or self.runtime_slot_post_generation < 1
            or self.source_lease_state.value != policy.required_source_state
            or self.consumer_subject_id != policy.consumer_subject_id
            or self.consumer_audience != policy.consumer_audience
            or self.consumer_contract_id != policy.consumer_contract_id
            or self.consumer_contract_version != policy.consumer_contract_version
            or self.purpose_id != policy.purpose_id
            or self.policy_id != policy.policy_id
            or self.policy_version != policy.policy_version
            or self.policy_digest != policy.canonical_digest
            or self.source_policy_id != policy.source_policy_id
            or self.source_policy_version != policy.source_policy_version
            or self.source_policy_digest != policy.source_policy_digest
            or self.irreversible_consumption_acknowledged is not True
            or any(
                value.tzinfo is None
                for value in (
                    self.injected_context_usable_until,
                    self.source_lease_issued_at,
                    self.source_lease_valid_until,
                    self.source_lease_effective_until,
                    self.claimed_at,
                )
            )
            or not self.source_lease_issued_at
            < self.source_lease_valid_until
            <= self.source_lease_effective_until
            <= self.injected_context_usable_until
            or not self.source_lease_issued_at <= self.claimed_at < self.source_lease_valid_until
            or self.claimed_at >= self.source_lease_effective_until
            or self.claimed_at >= self.injected_context_usable_until
            or any(self.authority.canonical_value().values())
        ):
            raise ValueError("runtime context use authorization consumption claim is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


@dataclass(frozen=True, slots=True)
class WorkflowProtectedRuntimeContextUseAuthorizationConsumptionResult:
    result_id: str
    consumption_id: str
    consumption_claim_id: str
    consumption_claim_digest: str
    authorization_lease_id: str
    authorization_lease_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    purpose_id: str
    policy_id: str
    policy_version: str
    policy_digest: str
    source_policy_id: str
    source_policy_version: str
    source_policy_digest: str
    state: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionState
    consumed_at: datetime
    recorded_at: datetime
    authorization_lease_consumed: bool
    historical_result_only: bool
    context_accessed: bool
    context_used: bool
    runtime_started: bool
    runtime_resumed: bool
    network_activity_performed: bool
    connector_activity_performed: bool
    readiness_probe_performed: bool
    publication_performed: bool
    delivery_performed: bool
    dispatch_performed: bool
    execution_performed: bool
    infrastructure_mutation_performed: bool
    renewal_created: bool
    transfer_created: bool
    replacement_created: bool
    retry_created: bool
    authority: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        policy = (
            code_owned_workflow_protected_runtime_context_use_authorization_consumption_policy()
        )
        terminal_state = type(self.state).AUTHORIZATION_CONSUMED_WITHOUT_RUNTIME_USE
        _require_identifiers(self, _RESULT_IDENTIFIERS)
        _require_digests(self, _RESULT_DIGESTS)
        forbidden_effects = (
            self.context_accessed,
            self.context_used,
            self.runtime_started,
            self.runtime_resumed,
            self.network_activity_performed,
            self.connector_activity_performed,
            self.readiness_probe_performed,
            self.publication_performed,
            self.delivery_performed,
            self.dispatch_performed,
            self.execution_performed,
            self.infrastructure_mutation_performed,
            self.renewal_created,
            self.transfer_created,
            self.replacement_created,
            self.retry_created,
        )
        if (
            self.consumer_subject_id != policy.consumer_subject_id
            or self.consumer_audience != policy.consumer_audience
            or self.consumer_contract_id != policy.consumer_contract_id
            or self.consumer_contract_version != policy.consumer_contract_version
            or self.purpose_id != policy.purpose_id
            or self.policy_id != policy.policy_id
            or self.policy_version != policy.policy_version
            or self.policy_digest != policy.canonical_digest
            or self.source_policy_id != policy.source_policy_id
            or self.source_policy_version != policy.source_policy_version
            or self.source_policy_digest != policy.source_policy_digest
            or self.state is not terminal_state
            or self.consumed_at.tzinfo is None
            or self.recorded_at.tzinfo is None
            or self.recorded_at < self.consumed_at
            or self.authorization_lease_consumed is not True
            or self.historical_result_only is not True
            or any(forbidden_effects)
            or any(self.authority.canonical_value().values())
        ):
            raise ValueError("runtime context use authorization consumption result is invalid")
        _require_canonical_digest(self)

    def digest_payload(self) -> dict[str, object]:
        return _payload(self, exclude=("canonical_digest",))


_CLAIM_IDENTIFIERS = (
    "consumption_claim_id",
    "consumption_id",
    "authorization_lease_id",
    "authorization_claim_id",
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
    "source_policy_id",
    "source_policy_version",
)
_CLAIM_DIGESTS = (
    "authorization_lease_digest",
    "authorization_claim_digest",
    "injection_result_digest",
    "destination_fencing_token_digest",
    "runtime_slot_commitment",
    "use_profile_digest",
    "policy_digest",
    "source_policy_digest",
    "idempotency_digest",
    "request_fingerprint",
    "consumption_audit_digest",
    "canonical_digest",
)
_RESULT_IDENTIFIERS = (
    "result_id",
    "consumption_id",
    "consumption_claim_id",
    "authorization_lease_id",
    "consumer_subject_id",
    "consumer_audience",
    "consumer_contract_id",
    "consumer_contract_version",
    "purpose_id",
    "policy_id",
    "policy_version",
    "source_policy_id",
    "source_policy_version",
)
_RESULT_DIGESTS = (
    "consumption_claim_digest",
    "authorization_lease_digest",
    "policy_digest",
    "source_policy_digest",
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
            raise ValueError(f"runtime context use consumption {name} is invalid")


def _require_digests(instance: object, names: tuple[str, ...]) -> None:
    for name in names:
        value = getattr(instance, name)
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ValueError(f"runtime context use consumption {name} is invalid")


def _require_canonical_digest(
    instance: (
        WorkflowProtectedRuntimeContextUseAuthorizationConsumptionClaim
        | WorkflowProtectedRuntimeContextUseAuthorizationConsumptionResult
    ),
) -> None:
    if instance.canonical_digest != canonical_digest(instance.digest_payload()):
        raise ValueError("runtime context use authorization consumption digest mismatch")


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
    "WorkflowProtectedRuntimeContextUseAuthorizationConsumptionAuthority",
    "WorkflowProtectedRuntimeContextUseAuthorizationConsumptionClaim",
    "WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPolicy",
    "WorkflowProtectedRuntimeContextUseAuthorizationConsumptionResult",
    "WorkflowProtectedRuntimeContextUseAuthorizationConsumptionState",
    "code_owned_workflow_protected_runtime_context_use_authorization_consumption_policy",
    "code_owned_workflow_protected_runtime_context_use_authorization_consumption_policy_values",
]
