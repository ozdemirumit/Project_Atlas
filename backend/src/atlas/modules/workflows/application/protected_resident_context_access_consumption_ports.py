from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol, cast

from atlas.modules.workflows.application.protected_resident_context_access_authorization_ports import (  # noqa: E501
    WorkflowProtectedResidentContextAccessAuthorizationSource,
    WorkflowProtectedResidentContextLifecycleAttestation,
    WorkflowProtectedResidentContextLifecycleSignatureVerifier,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedResidentContextAccessAuthorizationLease,
    WorkflowProtectedResidentContextAccessConsumptionAttempt,
    WorkflowProtectedResidentContextAccessConsumptionClaim,
    WorkflowProtectedResidentContextAccessConsumptionResult,
    WorkflowProtectedResidentContextTrustedAccessorInstruction,
    WorkflowProtectedResidentContextTrustedAccessorReceipt,
    WorkflowScope,
    canonical_digest,
)


class WorkflowProtectedResidentContextAccessConsumptionError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


class WorkflowProtectedResidentContextAccessConsumptionReplayStatus(StrEnum):
    NONE = "none"
    TERMINAL = "terminal"
    CLAIM_ONLY_PENDING = "claim_only_pending"
    CLAIM_ONLY_UNCERTAIN = "claim_only_uncertain"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    ALREADY_CONSUMED = "already_consumed"


class WorkflowProtectedResidentContextAccessConsumptionClaimStatus(StrEnum):
    CLAIMED = "claimed"
    REPLAY_COMPLETED = "replay_completed"
    CLAIM_ONLY_PENDING = "claim_only_pending"
    CLAIM_ONLY_UNCERTAIN = "claim_only_uncertain"
    IDEMPOTENCY_CONFLICT = "idempotency_conflict"
    ALREADY_CONSUMED = "already_consumed"
    EVIDENCE_CONFLICT = "evidence_conflict"
    PRECOMMIT_AUDIT_FAILED = "precommit_audit_failed"


class WorkflowProtectedResidentContextAccessConsumptionResultWriteStatus(StrEnum):
    RECORDED = "recorded"
    REPLAY = "replay"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class WorkflowProtectedResidentContextAccessConsumptionSource:
    """Canonical ADR-166 lease plus its complete ADR-165 source lineage."""

    authorization_lease: WorkflowProtectedResidentContextAccessAuthorizationLease
    authorization_source: WorkflowProtectedResidentContextAccessAuthorizationSource


@dataclass(frozen=True, slots=True)
class WorkflowProtectedResidentContextAccessorReadinessAttestationRequest:
    authorization_lease_id: str
    authorization_lease_digest: str
    protected_resident_context_id: str
    protected_resident_context_digest: str
    protected_resident_context_usable_until: datetime
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    accessor_contract_id: str
    accessor_contract_version: str
    accessor_id: str
    accessor_version: str
    runtime_handle_profile_id: str
    runtime_handle_profile_version: str
    runtime_handle_profile_digest: str
    request_nonce_digest: str
    requested_at: datetime


@dataclass(frozen=True, slots=True)
class WorkflowProtectedResidentContextAccessorReadinessAttestation:
    attestation_id: str
    attestor_id: str
    attestor_version: str
    signing_key_id: str
    signature_algorithm: str
    authorization_lease_id: str
    authorization_lease_digest: str
    protected_resident_context_id: str
    protected_resident_context_digest: str
    protected_resident_context_usable_until: datetime
    destination_boundary_id: str
    destination_deployment_id: str
    destination_generation: int
    destination_fencing_token_digest: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    consumer_contract_id: str
    consumer_contract_version: str
    accessor_contract_id: str
    accessor_contract_version: str
    accessor_id: str
    accessor_version: str
    runtime_handle_profile_id: str
    runtime_handle_profile_version: str
    runtime_handle_profile_digest: str
    request_nonce_digest: str
    observed_at: datetime
    valid_until: datetime
    access_eligible: bool
    exact_resident_context_confirmed: bool
    protected_destination_confirmed: bool
    atomic_compare_and_set_supported: bool
    resident_context_unconsumed: bool
    runtime_handle_outstanding: bool
    runtime_handle_profile_confirmed: bool
    runtime_handle_is_bearer_capability: bool
    raw_context_included: bool
    runtime_handle_locator_included: bool
    endpoint_included: bool
    credential_included: bool
    secret_included: bool
    bearer_token_included: bool
    provider_payload_included: bool
    network_activity_authorized: bool
    execution_authorized: bool
    infrastructure_mutation_authorized: bool
    integrity_signature: str
    canonical_digest: str

    def signature_payload(self) -> dict[str, object]:
        return {
            name: value
            for name, value in self.digest_payload().items()
            if name != "integrity_signature"
        }

    def digest_payload(self) -> dict[str, object]:
        return _canonical_payload(self, exclude=("canonical_digest",))


class WorkflowProtectedResidentContextAccessorReadinessAttestor(Protocol):
    @property
    def available(self) -> bool: ...

    async def attest_accessor_readiness(
        self, request: WorkflowProtectedResidentContextAccessorReadinessAttestationRequest
    ) -> WorkflowProtectedResidentContextAccessorReadinessAttestation: ...


class WorkflowProtectedResidentContextAccessorReadinessSignatureVerifier(Protocol):
    def verify_accessor_readiness_attestation(
        self, attestation: WorkflowProtectedResidentContextAccessorReadinessAttestation
    ) -> bool: ...


class WorkflowProtectedResidentContextTrustedAccessor(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def accessor_contract_id(self) -> str: ...

    @property
    def accessor_contract_version(self) -> str: ...

    @property
    def accessor_id(self) -> str: ...

    @property
    def accessor_version(self) -> str: ...

    @property
    def runtime_handle_profile_id(self) -> str: ...

    @property
    def runtime_handle_profile_version(self) -> str: ...

    @property
    def runtime_handle_profile_digest(self) -> str: ...

    async def establish_access(
        self, instruction: WorkflowProtectedResidentContextTrustedAccessorInstruction
    ) -> WorkflowProtectedResidentContextTrustedAccessorReceipt: ...

    def verify_receipt(
        self, receipt: WorkflowProtectedResidentContextTrustedAccessorReceipt
    ) -> bool: ...


class WorkflowProtectedResidentContextTrustedAccessorReceiptSignatureVerifier(Protocol):
    def verify_receipt(
        self, receipt: WorkflowProtectedResidentContextTrustedAccessorReceipt
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class WorkflowProtectedResidentContextAccessConsumptionReplayLookupRequest:
    authorization_lease_id: str
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    policy_id: str
    policy_version: str
    policy_digest: str
    idempotency_digest: str
    request_fingerprint: str
    consumption_id: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedResidentContextAccessConsumptionReplayLookup:
    status: WorkflowProtectedResidentContextAccessConsumptionReplayStatus
    attempt: WorkflowProtectedResidentContextAccessConsumptionAttempt | None
    result: WorkflowProtectedResidentContextAccessConsumptionResult | None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedResidentContextAccessConsumptionClaimRequest:
    claim_id: str
    attempt_id: str
    consumption_id: str
    source: WorkflowProtectedResidentContextAccessConsumptionSource
    lifecycle_attestation: WorkflowProtectedResidentContextLifecycleAttestation
    accessor_readiness_attestation: WorkflowProtectedResidentContextAccessorReadinessAttestation
    expected_request_nonce_digest: str
    offline_lifecycle_signature_verifier: WorkflowProtectedResidentContextLifecycleSignatureVerifier
    offline_readiness_signature_verifier: (
        WorkflowProtectedResidentContextAccessorReadinessSignatureVerifier
    )
    expected_policy_id: str
    expected_policy_version: str
    expected_policy_digest: str
    expected_lifecycle_attestor_id: str
    expected_lifecycle_attestor_version: str
    expected_readiness_attestor_id: str
    expected_readiness_attestor_version: str
    expected_accessor_contract_id: str
    expected_accessor_contract_version: str
    expected_accessor_id: str
    expected_accessor_version: str
    expected_runtime_handle_profile_id: str
    expected_runtime_handle_profile_version: str
    expected_runtime_handle_profile_digest: str
    expected_readiness_verification_signing_key_id: str
    minimum_remaining_budget_milliseconds: int
    scope: WorkflowScope
    consumer_subject_id: str
    consumer_audience: str
    idempotency_key: str
    idempotency_digest: str
    request_fingerprint: str
    irreversible_consumption_acknowledged: bool
    uncertain_outcome_requires_new_authorization_acknowledged: bool
    consumption_authorization_audit_payload: dict[str, object]
    consumption_authorization_audit_digest: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedResidentContextAccessConsumptionClaimWrite:
    status: WorkflowProtectedResidentContextAccessConsumptionClaimStatus
    claim: WorkflowProtectedResidentContextAccessConsumptionClaim | None
    attempt: WorkflowProtectedResidentContextAccessConsumptionAttempt | None
    result: WorkflowProtectedResidentContextAccessConsumptionResult | None


@dataclass(frozen=True, slots=True)
class WorkflowProtectedResidentContextAccessConsumptionResultRequest:
    result: WorkflowProtectedResidentContextAccessConsumptionResult
    receipt: WorkflowProtectedResidentContextTrustedAccessorReceipt | None
    expected_claim_digest: str
    expected_attempt_digest: str


@dataclass(frozen=True, slots=True)
class WorkflowProtectedResidentContextAccessConsumptionResultWrite:
    status: WorkflowProtectedResidentContextAccessConsumptionResultWriteStatus
    result: WorkflowProtectedResidentContextAccessConsumptionResult | None


class WorkflowProtectedResidentContextAccessConsumptionRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_authoritative_time(self) -> datetime: ...

    async def lookup_protected_resident_context_access_consumption_replay(
        self, request: WorkflowProtectedResidentContextAccessConsumptionReplayLookupRequest
    ) -> WorkflowProtectedResidentContextAccessConsumptionReplayLookup: ...

    async def get_protected_resident_context_access_consumption_source(
        self, *, authorization_lease_id: str
    ) -> WorkflowProtectedResidentContextAccessConsumptionSource | None: ...

    async def claim_protected_resident_context_access_consumption(
        self, request: WorkflowProtectedResidentContextAccessConsumptionClaimRequest
    ) -> WorkflowProtectedResidentContextAccessConsumptionClaimWrite: ...

    async def record_protected_resident_context_access_consumption_result(
        self, request: WorkflowProtectedResidentContextAccessConsumptionResultRequest
    ) -> WorkflowProtectedResidentContextAccessConsumptionResultWrite: ...

    async def list_protected_resident_context_access_consumption_attempts(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedResidentContextAccessConsumptionAttempt, ...]: ...

    async def get_protected_resident_context_access_consumption_results(
        self, *, scope: WorkflowScope, consumption_ids: tuple[str, ...]
    ) -> tuple[WorkflowProtectedResidentContextAccessConsumptionResult, ...]: ...


def build_workflow_protected_resident_context_trusted_accessor_instruction(
    attempt: WorkflowProtectedResidentContextAccessConsumptionAttempt,
) -> WorkflowProtectedResidentContextTrustedAccessorInstruction:
    aliases = {
        "accessor_contract_id": attempt.required_accessor_contract_id,
        "accessor_contract_version": attempt.required_accessor_contract_version,
        "accessor_id": attempt.approved_accessor_id,
        "accessor_version": attempt.approved_accessor_version,
    }
    values: dict[str, object] = {}
    for field in fields(WorkflowProtectedResidentContextTrustedAccessorInstruction):
        if field.name == "canonical_digest":
            continue
        if field.name in aliases:
            values[field.name] = aliases[field.name]
        else:
            values[field.name] = getattr(attempt, field.name)
    return WorkflowProtectedResidentContextTrustedAccessorInstruction(
        **cast(Any, values),
        canonical_digest=canonical_digest(
            {name: _canonical_value(value) for name, value in values.items()}
        ),
    )


def validate_workflow_protected_resident_context_access_consumption_claim_request(
    request: WorkflowProtectedResidentContextAccessConsumptionClaimRequest,
) -> None:
    source = request.source
    lease = source.authorization_lease
    lineage = source.authorization_source
    lifecycle = request.lifecycle_attestation
    readiness = request.accessor_readiness_attestation
    audit_payload: dict[str, object] = {
        "schema_id": "audit.workflow-protected-resident-context-access-consumption-authorization",
        "schema_version": "1.0",
        "event_type": "protected_resident_context_access_lease_consumption_authorized",
        "claim_id": request.claim_id,
        "attempt_id": request.attempt_id,
        "consumption_id": request.consumption_id,
        "authorization_lease_id": lease.authorization_lease_id,
        "authorization_lease_digest": lease.canonical_digest,
        "scope": request.scope.canonical_value(),
        "consumer_subject_id": request.consumer_subject_id,
        "consumer_audience": request.consumer_audience,
        "policy_id": request.expected_policy_id,
        "policy_version": request.expected_policy_version,
        "policy_digest": request.expected_policy_digest,
        "idempotency_digest": request.idempotency_digest,
        "request_fingerprint": request.request_fingerprint,
        "irreversible_consumption_acknowledged": True,
        "uncertain_outcome_requires_new_authorization_acknowledged": True,
    }
    exact = (
        lease.authorization_lease_id == readiness.authorization_lease_id
        and lease.canonical_digest == readiness.authorization_lease_digest
        and lease.opening_id == lifecycle.opening_id == lineage.result.opening_id
        and lease.opening_result_digest
        == lifecycle.opening_result_digest
        == lineage.result.canonical_digest
        and lease.protected_resident_context_id
        == lifecycle.protected_resident_context_id
        == readiness.protected_resident_context_id
        and lease.protected_resident_context_digest
        == lifecycle.protected_resident_context_digest
        == readiness.protected_resident_context_digest
        and lease.protected_resident_context_usable_until
        == lifecycle.protected_resident_context_usable_until
        == readiness.protected_resident_context_usable_until
        and lineage.destination_boundary_id
        == lifecycle.destination_boundary_id
        == readiness.destination_boundary_id
        and lineage.destination_deployment_id
        == lifecycle.destination_deployment_id
        == readiness.destination_deployment_id
        and lineage.destination_generation
        == lifecycle.destination_generation
        == readiness.destination_generation
        and lineage.destination_fencing_token_digest
        == lifecycle.destination_fencing_token_digest
        == readiness.destination_fencing_token_digest
        and lease.scope == lifecycle.scope == readiness.scope == request.scope
        and lease.consumer_subject_id
        == lifecycle.consumer_subject_id
        == readiness.consumer_subject_id
        == request.consumer_subject_id
        and lease.consumer_audience
        == lifecycle.consumer_audience
        == readiness.consumer_audience
        == request.consumer_audience
        and lifecycle.request_nonce_digest
        == readiness.request_nonce_digest
        == request.expected_request_nonce_digest
        and readiness.accessor_contract_id == request.expected_accessor_contract_id
        and readiness.accessor_contract_version == request.expected_accessor_contract_version
        and readiness.accessor_id == request.expected_accessor_id
        and readiness.accessor_version == request.expected_accessor_version
        and readiness.runtime_handle_profile_id == request.expected_runtime_handle_profile_id
        and readiness.runtime_handle_profile_version
        == request.expected_runtime_handle_profile_version
        and readiness.runtime_handle_profile_digest
        == request.expected_runtime_handle_profile_digest
        and lifecycle.attestor_id == request.expected_lifecycle_attestor_id
        and lifecycle.attestor_version == request.expected_lifecycle_attestor_version
        and readiness.attestor_id == request.expected_readiness_attestor_id
        and readiness.attestor_version == request.expected_readiness_attestor_version
        and readiness.signing_key_id == request.expected_readiness_verification_signing_key_id
        and lifecycle.observed_at < lifecycle.valid_until
        and readiness.observed_at < readiness.valid_until
    )
    safe = (
        request.irreversible_consumption_acknowledged is True
        and request.uncertain_outcome_requires_new_authorization_acknowledged is True
        and lifecycle.resident_context_present is True
        and lifecycle.resident_context_unexpired is True
        and lifecycle.resident_context_unrevoked is True
        and lifecycle.resident_context_undestroyed is True
        and lifecycle.resident_context_unconsumed is True
        and lifecycle.resident_context_handle_outstanding is False
        and lifecycle.raw_context_included is False
        and lifecycle.endpoint_included is False
        and lifecycle.credential_included is False
        and lifecycle.secret_included is False
        and lifecycle.bearer_token_included is False
        and lifecycle.locator_included is False
        and lifecycle.provider_payload_included is False
        and readiness.access_eligible is True
        and readiness.exact_resident_context_confirmed is True
        and readiness.protected_destination_confirmed is True
        and readiness.atomic_compare_and_set_supported is True
        and readiness.resident_context_unconsumed is True
        and readiness.runtime_handle_outstanding is False
        and readiness.runtime_handle_profile_confirmed is True
        and readiness.runtime_handle_is_bearer_capability is False
        and readiness.raw_context_included is False
        and readiness.runtime_handle_locator_included is False
        and readiness.endpoint_included is False
        and readiness.credential_included is False
        and readiness.secret_included is False
        and readiness.bearer_token_included is False
        and readiness.provider_payload_included is False
        and readiness.network_activity_authorized is False
        and readiness.execution_authorized is False
        and readiness.infrastructure_mutation_authorized is False
    )
    try:
        lifecycle_valid = request.offline_lifecycle_signature_verifier.verify_lifecycle_attestation(
            lifecycle
        )
        readiness_valid = (
            request.offline_readiness_signature_verifier.verify_accessor_readiness_attestation(
                readiness
            )
        )
    except Exception as exc:
        raise ValueError("resident context access consumption signature is invalid") from exc
    if (
        not exact
        or not safe
        or lifecycle_valid is not True
        or readiness_valid is not True
        or request.minimum_remaining_budget_milliseconds <= 0
        or request.consumption_authorization_audit_payload != audit_payload
        or request.consumption_authorization_audit_digest != canonical_digest(audit_payload)
        or lifecycle.canonical_digest != canonical_digest(lifecycle.digest_payload())
        or readiness.canonical_digest != canonical_digest(readiness.digest_payload())
        or not 8 <= len(request.idempotency_key) <= 128
    ):
        raise ValueError("resident context access consumption evidence is unsafe")
    for value in (
        lease.canonical_digest,
        request.expected_request_nonce_digest,
        request.expected_policy_digest,
        request.expected_runtime_handle_profile_digest,
        request.idempotency_digest,
        request.request_fingerprint,
        request.consumption_authorization_audit_digest,
    ):
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("resident context access consumption digest is invalid")


def _canonical_payload(value: Any, *, exclude: tuple[str, ...] = ()) -> dict[str, object]:
    return {
        field.name: _canonical_value(getattr(value, field.name))
        for field in fields(value)
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
    name
    for name in globals()
    if name.startswith("Workflow") or name.startswith("build_") or name.startswith("validate_")
]
