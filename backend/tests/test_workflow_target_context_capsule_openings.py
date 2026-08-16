from __future__ import annotations

from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, cast

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.workflows.adapters import (
    DenyAllWorkflowProtectedTargetContextCapsuleOpeningAttestationSignatureVerifier,
    SyntheticWorkflowProtectedTargetContextCapsuleOpeningAttestors,
    SyntheticWorkflowProtectedTargetContextCapsuleTrustedOpener,
    UnavailableWorkflowProtectedTargetContextCapsuleOpenabilityAttestor,
    UnavailableWorkflowProtectedTargetContextCapsuleOpeningCustodyAttestor,
    UnavailableWorkflowProtectedTargetContextCapsuleTrustedOpener,
)
from atlas.modules.workflows.application import (
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    WorkflowProtectedTransportTargetContextCapsuleOpeningClaimStatus,
    WorkflowProtectedTransportTargetContextCapsuleOpeningError,
    WorkflowProtectedTransportTargetContextCapsuleOpeningReplayStatus,
    WorkflowProtectedTransportTargetContextCapsuleOpeningResultWriteStatus,
    WorkflowProtectedTransportTargetContextCapsuleOpeningService,
    WorkflowProtectedTransportTargetContextCapsuleOpeningSource,
    WorkflowTargetContextCapsuleOpeningClaimRequest,
    WorkflowTargetContextCapsuleOpeningClaimResult,
    WorkflowTargetContextCapsuleOpeningReplayLookup,
    WorkflowTargetContextCapsuleOpeningReplayLookupRequest,
    WorkflowTargetContextCapsuleOpeningResultRequest,
    WorkflowTargetContextCapsuleOpeningResultWrite,
    validate_workflow_target_context_capsule_opening_claim_request,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedTransportTargetContextCapsuleOpeningAttempt,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAttemptState,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthority,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseState,
    WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionClaim,
    WorkflowProtectedTransportTargetContextCapsuleOpeningFailureClass,
    WorkflowProtectedTransportTargetContextCapsuleOpeningLeaseAuthority,
    WorkflowProtectedTransportTargetContextCapsuleOpeningResult,
    WorkflowProtectedTransportTargetContextCapsuleOpeningResultState,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_transport_target_context_capsule_opening_authorization_policy,
    code_owned_workflow_protected_transport_target_context_capsule_opening_consumption_policy,
)

NOW = datetime(2026, 8, 16, 21, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.development", "environment.development", "site.local")


def _payload(values: dict[str, object]) -> dict[str, object]:
    return {
        name: (
            value.isoformat()
            if isinstance(value, datetime)
            else value.value
            if isinstance(value, StrEnum)
            else value.canonical_value()
            if hasattr(value, "canonical_value")
            else value
        )
        for name, value in values.items()
    }


def _lease() -> WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease:
    policy = code_owned_workflow_protected_transport_target_context_capsule_opening_authorization_policy()  # noqa: E501
    values: dict[str, object] = {
        "authorization_lease_id": "target-context-capsule-opening-lease.imp-215",
        "handoff_id": "target-context-capsule-handoff.imp-213",
        "handoff_result_digest": "1" * 64,
        "attempt_id": "target-context-capsule-handoff-attempt.imp-213",
        "attempt_digest": "2" * 64,
        "consumption_claim_id": "target-context-capsule-handoff-claim.imp-213",
        "consumption_claim_digest": "3" * 64,
        "upstream_authorization_lease_id": "target-context-capsule-handoff-lease.imp-213",
        "upstream_authorization_lease_digest": "4" * 64,
        "consumer_binding_id": "target-context-capsule-consumer-binding.imp-212",
        "consumer_binding_digest": "5" * 64,
        "sealed_capsule_id": "sealed-target-context-capsule.imp-211",
        "sealed_capsule_digest": "6" * 64,
        "consumer_receipt_id": "target-context-capsule-consumer-receipt.imp-213",
        "receipt_digest": "7" * 64,
        "destination_boundary_id": policy.destination_boundary_id,
        "destination_deployment_id": policy.destination_deployment_id,
        "destination_generation": policy.destination_generation,
        "destination_fencing_token_digest": policy.destination_fencing_token_digest,
        "custody_contract_id": policy.custody_contract_id,
        "custody_contract_version": policy.custody_contract_version,
        "approved_adapter_id": policy.approved_adapter_id,
        "approved_adapter_version": policy.approved_adapter_version,
        "verification_signing_key_id": policy.verification_signing_key_id,
        "trusted_profile_digest": policy.trusted_profile_digest,
        "custody_attestation_id": "destination-custody-attestation.imp-214",
        "custody_attestation_digest": "8" * 64,
        "custody_attestation_valid_until": NOW + timedelta(seconds=5),
        "scope": SCOPE,
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "issued_at": NOW,
        "valid_until": NOW + timedelta(seconds=1),
        "effective_until": NOW + timedelta(seconds=5),
        "single_use": True,
        "renewable": False,
        "transferable": False,
        "lease_is_bearer_capability": False,
        "state": (
            WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
        ),
        "authority": WorkflowProtectedTransportTargetContextCapsuleOpeningLeaseAuthority(),
    }
    return WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease(
        **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
    )


def _context(
    **changes: object,
) -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext:
    values: dict[str, object] = {
        "subject_id": WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        "actor_type": "service",
        "authentication_method": "workload_token",
        "credential_audience": WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
        "scope": SCOPE,
        "correlation_id": "correlation.imp-215",
        "decision_id": "decision.imp-215",
        "requested_at": NOW,
    }
    values.update(changes)
    return WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
        **cast(Any, values)
    )


class _AuditSink:
    def __init__(self, repository: _Repository | None = None, *, fail: bool = False) -> None:
        self.records: list[AuditRecord] = []
        self.commit_states: list[bool] = []
        self._repository = repository
        self._fail = fail

    async def record(self, record: AuditRecord) -> None:
        if self._repository is not None:
            self.commit_states.append(self._repository.claim_committed)
        if self._fail:
            raise RuntimeError("synthetic audit export failure")
        self.records.append(record)


class _Repository:
    def __init__(
        self,
        *,
        replay_status: WorkflowProtectedTransportTargetContextCapsuleOpeningReplayStatus = (
            WorkflowProtectedTransportTargetContextCapsuleOpeningReplayStatus.NONE
        ),
        second_time: datetime = NOW + timedelta(milliseconds=300),
    ) -> None:
        self.source = WorkflowProtectedTransportTargetContextCapsuleOpeningSource(
            lease=_lease(),
            capsule_schema_id="schema.workflow-protected-target-context-capsule",
            capsule_schema_version="1.0",
        )
        self.replay_status = replay_status
        self.second_time = second_time
        self.time_calls = 0
        self.lookup_calls = 0
        self.source_calls = 0
        self.claim_calls = 0
        self.result_calls = 0
        self.claim_committed = False
        self.claim: WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionClaim | None = (
            None
        )
        self.attempt: WorkflowProtectedTransportTargetContextCapsuleOpeningAttempt | None = None
        self.result: WorkflowProtectedTransportTargetContextCapsuleOpeningResult | None = None
        self.last_claim_request: WorkflowTargetContextCapsuleOpeningClaimRequest | None = None

    @property
    def durable(self) -> bool:
        return True

    async def get_authoritative_time(self) -> datetime:
        self.time_calls += 1
        return NOW + timedelta(milliseconds=100) if self.time_calls == 1 else self.second_time

    async def get_target_context_capsule_opening_source(
        self, *, authorization_lease_id: str
    ) -> WorkflowProtectedTransportTargetContextCapsuleOpeningSource | None:
        self.source_calls += 1
        return (
            self.source
            if authorization_lease_id == self.source.lease.authorization_lease_id
            else None
        )

    async def lookup_target_context_capsule_opening_replay(
        self, request: WorkflowTargetContextCapsuleOpeningReplayLookupRequest
    ) -> WorkflowTargetContextCapsuleOpeningReplayLookup:
        self.lookup_calls += 1
        return WorkflowTargetContextCapsuleOpeningReplayLookup(
            self.replay_status,
            self.attempt if self.replay_status is not request_statuses.NONE else None,
            self.result if self.replay_status is request_statuses.TERMINAL else None,
        )

    async def claim_target_context_capsule_opening(
        self, request: WorkflowTargetContextCapsuleOpeningClaimRequest
    ) -> WorkflowTargetContextCapsuleOpeningClaimResult:
        self.claim_calls += 1
        self.last_claim_request = request
        validate_workflow_target_context_capsule_opening_claim_request(request)
        policy = code_owned_workflow_protected_transport_target_context_capsule_opening_consumption_policy()  # noqa: E501
        lease = request.source.lease
        claim_values: dict[str, object] = {
            "claim_id": request.claim_id,
            "opening_id": request.opening_id,
            "attempt_id": request.attempt_id,
            "authorization_lease_id": lease.authorization_lease_id,
            "authorization_lease_digest": lease.canonical_digest,
            "handoff_id": lease.handoff_id,
            "handoff_result_digest": lease.handoff_result_digest,
            "handoff_attempt_id": lease.attempt_id,
            "handoff_attempt_digest": lease.attempt_digest,
            "handoff_consumption_claim_id": lease.consumption_claim_id,
            "handoff_consumption_claim_digest": lease.consumption_claim_digest,
            "consumer_binding_id": lease.consumer_binding_id,
            "consumer_binding_digest": lease.consumer_binding_digest,
            "sealed_capsule_id": lease.sealed_capsule_id,
            "sealed_capsule_digest": lease.sealed_capsule_digest,
            "consumer_receipt_id": lease.consumer_receipt_id,
            "consumer_receipt_digest": lease.receipt_digest,
            "sealed_capsule_is_bearer_capability": False,
            "consumer_receipt_is_bearer_capability": False,
            "scope": request.scope,
            "consumer_subject_id": request.consumer_subject_id,
            "consumer_audience": request.consumer_audience,
            "consumer_contract_id": lease.consumer_contract_id,
            "consumer_contract_version": lease.consumer_contract_version,
            "purpose_id": lease.purpose_id,
            "policy_id": policy.policy_id,
            "policy_version": policy.policy_version,
            "policy_digest": policy.canonical_digest,
            "irreversible_consumption_acknowledged": True,
            "uncertain_outcome_requires_new_authorization_acknowledged": True,
            "request_fingerprint": request.request_fingerprint,
            "idempotency_digest": request.idempotency_digest,
            "consumption_authorization_audit_digest": (
                request.consumption_authorization_audit_digest
            ),
            "claimed_at": NOW + timedelta(milliseconds=100),
            "authority": WorkflowProtectedTransportTargetContextCapsuleOpeningAuthority(),
        }
        self.claim = WorkflowProtectedTransportTargetContextCapsuleOpeningConsumptionClaim(
            **cast(Any, claim_values),
            canonical_digest=canonical_digest(_payload(claim_values)),
        )
        attempt_values: dict[str, object] = {
            "attempt_id": request.attempt_id,
            "opening_id": request.opening_id,
            "consumption_claim_id": request.claim_id,
            "consumption_claim_digest": self.claim.canonical_digest,
            "authorization_lease_id": lease.authorization_lease_id,
            "authorization_lease_digest": lease.canonical_digest,
            "consumer_binding_id": lease.consumer_binding_id,
            "consumer_binding_digest": lease.consumer_binding_digest,
            "sealed_capsule_id": lease.sealed_capsule_id,
            "sealed_capsule_digest": lease.sealed_capsule_digest,
            "consumer_receipt_id": lease.consumer_receipt_id,
            "consumer_receipt_digest": lease.receipt_digest,
            "sealed_capsule_is_bearer_capability": False,
            "consumer_receipt_is_bearer_capability": False,
            "scope": request.scope,
            "consumer_subject_id": request.consumer_subject_id,
            "consumer_audience": request.consumer_audience,
            "consumer_contract_id": lease.consumer_contract_id,
            "consumer_contract_version": lease.consumer_contract_version,
            "purpose_id": lease.purpose_id,
            "policy_id": policy.policy_id,
            "policy_version": policy.policy_version,
            "policy_digest": policy.canonical_digest,
            "required_opener_contract_id": policy.required_opener_contract_id,
            "required_opener_contract_version": policy.required_opener_contract_version,
            "approved_opener_id": policy.approved_opener_id,
            "approved_opener_version": policy.approved_opener_version,
            "destination_boundary_id": policy.destination_boundary_id,
            "destination_deployment_id": policy.destination_deployment_id,
            "destination_generation": policy.destination_generation,
            "destination_fencing_token_digest": policy.destination_fencing_token_digest,
            "custody_contract_id": policy.custody_contract_id,
            "custody_contract_version": policy.custody_contract_version,
            "verification_signing_key_id": policy.verification_signing_key_id,
            "trusted_opener_profile_digest": policy.trusted_opener_profile_digest,
            "custody_attestation_id": request.custody_attestation.attestation_id,
            "custody_attestation_digest": request.custody_attestation.canonical_digest,
            "openability_attestation_id": request.openability_attestation.attestation_id,
            "openability_attestation_digest": request.openability_attestation.canonical_digest,
            "request_nonce_digest": request.expected_request_nonce_digest,
            "started_at": NOW + timedelta(milliseconds=100),
            "opening_deadline": NOW + timedelta(milliseconds=500),
            "lease_valid_until": lease.valid_until,
            "custody_attestation_valid_until": request.custody_attestation.valid_until,
            "openability_attestation_valid_until": request.openability_attestation.valid_until,
            "resident_context_usable_until_limit": min(
                lease.effective_until,
                request.custody_attestation.valid_until,
                request.openability_attestation.valid_until,
            ),
            "state": WorkflowProtectedTransportTargetContextCapsuleOpeningAttemptState.STARTED,
            "authority": WorkflowProtectedTransportTargetContextCapsuleOpeningAuthority(),
        }
        self.attempt = WorkflowProtectedTransportTargetContextCapsuleOpeningAttempt(
            **cast(Any, attempt_values),
            canonical_digest=canonical_digest(_payload(attempt_values)),
        )
        self.claim_committed = True
        return WorkflowTargetContextCapsuleOpeningClaimResult(
            WorkflowProtectedTransportTargetContextCapsuleOpeningClaimStatus.CLAIMED,
            self.claim,
            self.attempt,
            None,
        )

    async def record_target_context_capsule_opening_result(
        self, request: WorkflowTargetContextCapsuleOpeningResultRequest
    ) -> WorkflowTargetContextCapsuleOpeningResultWrite:
        self.result_calls += 1
        self.result = request.result
        return WorkflowTargetContextCapsuleOpeningResultWrite(
            WorkflowProtectedTransportTargetContextCapsuleOpeningResultWriteStatus.RECORDED,
            self.result,
        )

    async def list_target_context_capsule_opening_attempts(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedTransportTargetContextCapsuleOpeningAttempt, ...]:
        del scope, limit
        return () if self.attempt is None else (self.attempt,)

    async def get_target_context_capsule_opening_results_by_opening_ids(
        self, *, scope: WorkflowScope, opening_ids: tuple[str, ...]
    ) -> tuple[WorkflowProtectedTransportTargetContextCapsuleOpeningResult, ...]:
        del scope, opening_ids
        return () if self.result is None else (self.result,)


request_statuses = WorkflowProtectedTransportTargetContextCapsuleOpeningReplayStatus


class _CommitCheckingOpener(SyntheticWorkflowProtectedTargetContextCapsuleTrustedOpener):
    def __init__(self, repository: _Repository, **kwargs: Any) -> None:
        super().__init__(
            test_enabled=True, clock=lambda: NOW + timedelta(milliseconds=200), **kwargs
        )
        self._repository = repository

    async def open_capsule(self, instruction: Any) -> Any:
        assert self._repository.claim_committed is True
        return await super().open_capsule(instruction)


class _RaisingOpener(_CommitCheckingOpener):
    async def open_capsule(self, instruction: Any) -> Any:
        assert self._repository.claim_committed is True
        self.calls.append(instruction)
        raise RuntimeError("synthetic opener uncertainty")


def _service(
    repository: _Repository,
    *,
    attestors: SyntheticWorkflowProtectedTargetContextCapsuleOpeningAttestors | None = None,
    opener: SyntheticWorkflowProtectedTargetContextCapsuleTrustedOpener | None = None,
    audit: _AuditSink | None = None,
) -> tuple[
    WorkflowProtectedTransportTargetContextCapsuleOpeningService,
    SyntheticWorkflowProtectedTargetContextCapsuleOpeningAttestors,
    SyntheticWorkflowProtectedTargetContextCapsuleTrustedOpener,
    _AuditSink,
]:
    evidence = attestors or SyntheticWorkflowProtectedTargetContextCapsuleOpeningAttestors(
        test_enabled=True, clock=lambda: NOW + timedelta(milliseconds=50)
    )
    trusted_opener = opener or _CommitCheckingOpener(repository)
    audit_sink = audit or _AuditSink(repository)
    return (
        WorkflowProtectedTransportTargetContextCapsuleOpeningService(
            repository=repository,
            custody_attestor=evidence,
            openability_attestor=evidence,
            attestation_signature_verifier=evidence,
            opener=trusted_opener,
            audit_sink=audit_sink,
        ),
        evidence,
        trusted_opener,
        audit_sink,
    )


async def _open(
    service: WorkflowProtectedTransportTargetContextCapsuleOpeningService,
    *,
    context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext
    | None = None,
) -> Any:
    policy = service.policy
    lease = _lease()
    return await service.open(
        authorization_lease_id=lease.authorization_lease_id,
        authorization_lease_digest=lease.canonical_digest,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        irreversible_consumption_acknowledged=True,
        uncertain_outcome_requires_new_authorization_acknowledged=True,
        idempotency_key="idempotency.imp-215",
        context=context or _context(),
    )


@pytest.mark.asyncio
async def test_success_commits_before_one_opener_call_and_returns_zero_authority() -> None:
    repository = _Repository()
    service, attestors, opener, audit = _service(repository)

    presentation = await _open(service)

    assert repository.lookup_calls == 1
    assert repository.claim_calls == 1
    assert repository.result_calls == 1
    assert len(attestors.custody_calls) == len(attestors.openability_calls) == 1
    assert len(opener.calls) == 1
    assert len(audit.records) == 1
    assert audit.commit_states == [True]
    assert presentation.result is not None
    assert presentation.result.state is (
        WorkflowProtectedTransportTargetContextCapsuleOpeningResultState.OPENED_IN_PROTECTED_CONSUMER_BOUNDARY
    )
    assert len(presentation.result.authority.canonical_value()) == 19
    assert set(presentation.result.authority.canonical_value().values()) == {False}
    assert repository.claim is not None
    assert set(repository.claim.authority.canonical_value().values()) == {False}
    assert set(presentation.attempt.authority.canonical_value().values()) == {False}
    assert presentation.result.protected_resident_context_is_bearer_capability is False
    custody_request = attestors.custody_calls[0]
    openability_request = attestors.openability_calls[0]
    assert custody_request.request_nonce_digest == openability_request.request_nonce_digest
    assert (
        custody_request.request_nonce_digest != repository.source.lease.custody_attestation_digest
    )


@pytest.mark.asyncio
async def test_postcommit_audit_export_failure_does_not_retry_or_block_opening() -> None:
    repository = _Repository()
    audit = _AuditSink(repository, fail=True)
    service, _, opener, _ = _service(repository, audit=audit)

    presentation = await _open(service)

    assert audit.commit_states == [True]
    assert repository.claim_calls == 1
    assert len(opener.calls) == 1
    assert repository.result_calls == 1
    assert presentation.result is not None


@pytest.mark.asyncio
async def test_exact_terminal_replay_performs_no_attestor_or_opener_io() -> None:
    original_repository = _Repository()
    original_service, _, _, _ = _service(original_repository)
    original = await _open(original_service)
    repository = _Repository(replay_status=request_statuses.TERMINAL)
    repository.attempt = original.attempt
    repository.result = original.result
    service, attestors, opener, _ = _service(repository)

    replay = await _open(service)

    assert replay == original
    assert repository.source_calls == repository.claim_calls == 0
    assert not attestors.custody_calls
    assert not attestors.openability_calls
    assert opener.calls == []


@pytest.mark.asyncio
async def test_claim_only_replay_performs_no_external_io() -> None:
    base_repository = _Repository()
    base_service, _, _, _ = _service(base_repository)
    original = await _open(base_service)
    repository = _Repository(replay_status=request_statuses.CLAIM_ONLY_UNCERTAIN)
    repository.attempt = original.attempt
    service, attestors, opener, _ = _service(repository)

    replay = await _open(service)

    assert replay.attempt == original.attempt
    assert replay.result is None
    assert not attestors.custody_calls
    assert not attestors.openability_calls
    assert opener.calls == []


@pytest.mark.asyncio
async def test_idempotency_conflict_fails_before_external_io() -> None:
    repository = _Repository(replay_status=request_statuses.IDEMPOTENCY_CONFLICT)
    service, attestors, opener, _ = _service(repository)

    with pytest.raises(
        WorkflowProtectedTransportTargetContextCapsuleOpeningError,
        match="idempotency_conflict",
    ):
        await _open(service)

    assert repository.source_calls == repository.claim_calls == 0
    assert not attestors.custody_calls
    assert not attestors.openability_calls
    assert opener.calls == []


@pytest.mark.asyncio
async def test_negative_openability_fails_before_claim() -> None:
    repository = _Repository()
    attestors = SyntheticWorkflowProtectedTargetContextCapsuleOpeningAttestors(
        test_enabled=True,
        clock=lambda: NOW + timedelta(milliseconds=50),
        openable=False,
    )
    service, _, opener, _ = _service(repository, attestors=attestors)

    with pytest.raises(
        WorkflowProtectedTransportTargetContextCapsuleOpeningError,
        match="evidence_conflict",
    ):
        await _open(service)

    assert repository.claim_calls == 0
    assert opener.calls == []


@pytest.mark.asyncio
async def test_known_failure_requires_signed_receipt_and_is_terminal() -> None:
    repository = _Repository()
    opener = _CommitCheckingOpener(
        repository,
        failure_class=(
            WorkflowProtectedTransportTargetContextCapsuleOpeningFailureClass.TRUSTED_OPENER_REJECTED
        ),
    )
    service, _, _, _ = _service(repository, opener=opener)

    presentation = await _open(service)

    assert presentation.result is not None
    assert presentation.result.state is (
        WorkflowProtectedTransportTargetContextCapsuleOpeningResultState.OPENING_FAILED
    )
    assert presentation.result.opening_receipt_digest is not None
    assert presentation.result.protected_source_closed is True
    assert presentation.result.source_capsule_zeroized is True


@pytest.mark.asyncio
async def test_opener_exception_is_not_retried_and_remains_pending_before_deadline() -> None:
    repository = _Repository()
    opener = _RaisingOpener(repository)
    service, _, _, _ = _service(repository, opener=opener)

    presentation = await _open(service)

    assert len(opener.calls) == 1
    assert presentation.result is None
    assert repository.claim_committed is True
    assert repository.result_calls == 0


@pytest.mark.asyncio
async def test_opener_exception_records_code_owned_uncertainty_after_deadline() -> None:
    repository = _Repository(second_time=NOW + timedelta(milliseconds=700))
    opener = _RaisingOpener(repository)
    service, _, _, _ = _service(repository, opener=opener)

    presentation = await _open(service)

    assert len(opener.calls) == 1
    assert presentation.result is not None
    assert presentation.result.state is (
        WorkflowProtectedTransportTargetContextCapsuleOpeningResultState.OPENING_OUTCOME_UNCERTAIN
    )
    assert presentation.result.opening_receipt_digest is None
    assert presentation.result.outcome_known is False
    assert set(presentation.result.authority.canonical_value().values()) == {False}


@pytest.mark.asyncio
async def test_wrong_identity_and_missing_acknowledgement_fail_before_replay() -> None:
    repository = _Repository()
    service, _, _, _ = _service(repository)

    with pytest.raises(WorkflowProtectedTransportTargetContextCapsuleOpeningError):
        await _open(service, context=_context(actor_type="human"))

    assert repository.lookup_calls == 0


def test_production_adapters_fail_closed_and_synthetic_requires_enablement() -> None:
    assert (
        UnavailableWorkflowProtectedTargetContextCapsuleOpeningCustodyAttestor().available is False
    )
    assert UnavailableWorkflowProtectedTargetContextCapsuleOpenabilityAttestor().available is False
    assert UnavailableWorkflowProtectedTargetContextCapsuleTrustedOpener().available is False
    verifier = DenyAllWorkflowProtectedTargetContextCapsuleOpeningAttestationSignatureVerifier()
    assert verifier.verify_opening_custody_attestation(cast(Any, object())) is False
    assert verifier.verify_capsule_openability_attestation(cast(Any, object())) is False
    assert SyntheticWorkflowProtectedTargetContextCapsuleOpeningAttestors().available is False
    assert SyntheticWorkflowProtectedTargetContextCapsuleTrustedOpener().available is False


def test_application_and_opener_contracts_are_metadata_only() -> None:
    forbidden_fragments = {
        "credential",
        "endpoint",
        "locator",
        "password",
        "raw_material",
        "secret",
        "token",
    }
    contract_types = (
        WorkflowProtectedTransportTargetContextCapsuleOpeningSource,
        WorkflowTargetContextCapsuleOpeningClaimRequest,
    )

    for contract_type in contract_types:
        names = {field.name for field in fields(contract_type)}
        assert all(fragment not in name for name in names for fragment in forbidden_fragments)


@pytest.mark.asyncio
async def test_under_lock_validator_rejects_changed_signed_evidence() -> None:
    repository = _Repository()
    service, _, _, _ = _service(repository)
    await _open(service)
    request = repository.last_claim_request
    assert request is not None
    changed = replace(
        request.openability_attestation,
        consumer_receipt_digest="f" * 64,
    )

    with pytest.raises(ValueError, match="unsafe"):
        validate_workflow_target_context_capsule_opening_claim_request(
            replace(request, openability_attestation=changed)
        )
