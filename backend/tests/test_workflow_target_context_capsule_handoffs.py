from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any, cast

import pytest
from test_workflow_target_context_capsule_handoff_authorization_leases import (
    CollectingAuditSink,
    authorize,
    consumer_context,
)
from test_workflow_target_context_capsule_handoff_authorization_leases import (
    service_fixture as authorization_service_fixture,
)

from atlas.modules.workflows.adapters.target_context_capsule_handoff_adapters import (
    DeterministicSyntheticWorkflowProtectedTargetContextCapsuleSealedHandoffAdapter,
)
from atlas.modules.workflows.application import (
    WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestationRequest,
    WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestationRequest,
    WorkflowProtectedTransportTargetContextCapsuleHandoffClaimStatus,
    WorkflowProtectedTransportTargetContextCapsuleHandoffError,
    WorkflowProtectedTransportTargetContextCapsuleHandoffReplayStatus,
    WorkflowProtectedTransportTargetContextCapsuleHandoffResultWriteStatus,
    WorkflowProtectedTransportTargetContextCapsuleHandoffService,
    WorkflowTargetContextCapsuleHandoffClaimRequest,
    WorkflowTargetContextCapsuleHandoffClaimResult,
    WorkflowTargetContextCapsuleHandoffReplayLookup,
    WorkflowTargetContextCapsuleHandoffReplayLookupRequest,
    WorkflowTargetContextCapsuleHandoffResultRequest,
    WorkflowTargetContextCapsuleHandoffResultWrite,
    validate_workflow_target_context_capsule_handoff_claim_request,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestation,
    WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestation,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAttempt,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAttemptState,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthority,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease,
    WorkflowProtectedTransportTargetContextCapsuleHandoffConsumptionClaim,
    WorkflowProtectedTransportTargetContextCapsuleHandoffResult,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_transport_target_context_capsule_handoff_consumption_policy,
)


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


def make_attempt(
    *,
    started_at: datetime,
    handoff_deadline: datetime,
    handoff_id: str = "workflow-target-context-capsule-handoff.imp-213",
    scope: WorkflowScope | None = None,
) -> WorkflowProtectedTransportTargetContextCapsuleHandoffAttempt:
    policy = (
        code_owned_workflow_protected_transport_target_context_capsule_handoff_consumption_policy()
    )
    selected_scope = scope or WorkflowScope("org-atlas", "environment-lab", "site-istanbul")
    values: dict[str, object] = {
        "attempt_id": "workflow-target-context-capsule-handoff-attempt.imp-213",
        "handoff_id": handoff_id,
        "consumption_claim_id": "workflow-target-context-capsule-handoff-claim.imp-213",
        "consumption_claim_digest": "1" * 64,
        "authorization_lease_id": "workflow-target-context-capsule-handoff-lease.imp-213",
        "authorization_lease_digest": "2" * 64,
        "consumer_binding_id": "target-context-capsule-consumer-binding.imp-213",
        "consumer_binding_digest": "3" * 64,
        "sealed_capsule_id": "sealed-target-context-capsule.imp-213",
        "sealed_capsule_digest": "4" * 64,
        "capsule_schema_id": "schema.workflow-protected-target-context-capsule",
        "capsule_schema_version": "1.0",
        "scope": selected_scope,
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "adapter_contract_id": policy.required_adapter_contract_id,
        "adapter_contract_version": policy.required_adapter_contract_version,
        "approved_adapter_id": policy.approved_adapter_id,
        "approved_adapter_version": policy.approved_adapter_version,
        "destination_boundary_id": policy.destination_boundary_id,
        "destination_deployment_id": policy.destination_deployment_id,
        "destination_generation": policy.destination_generation,
        "destination_fencing_token_digest": policy.destination_fencing_token_digest,
        "custody_contract_id": policy.custody_contract_id,
        "custody_contract_version": policy.custody_contract_version,
        "verification_signing_key_id": policy.verification_signing_key_id,
        "trusted_profile_digest": policy.trusted_profile_digest,
        "lifecycle_attestation_id": "target-context-capsule-handoff-lifecycle.imp-213",
        "lifecycle_attestation_digest": "5" * 64,
        "acceptance_attestation_id": "target-context-capsule-handoff-acceptance.imp-213",
        "acceptance_attestation_digest": "6" * 64,
        "request_nonce_digest": "7" * 64,
        "started_at": started_at,
        "handoff_deadline": handoff_deadline,
        "lease_valid_until": handoff_deadline,
        "binding_effective_until": handoff_deadline + timedelta(seconds=1),
        "source_effective_until": handoff_deadline + timedelta(seconds=1),
        "lifecycle_attestation_valid_until": handoff_deadline + timedelta(seconds=1),
        "acceptance_attestation_valid_until": handoff_deadline + timedelta(seconds=1),
        "state": WorkflowProtectedTransportTargetContextCapsuleHandoffAttemptState.STARTED,
        "authority": WorkflowProtectedTransportTargetContextCapsuleHandoffAuthority(),
    }
    return WorkflowProtectedTransportTargetContextCapsuleHandoffAttempt(
        **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
    )


class _Verifier:
    def verify_capsule_handoff_lifecycle_attestation(self, _: object) -> bool:
        return True

    def verify_consumer_boundary_acceptance_attestation(self, _: object) -> bool:
        return True


class _LifecycleAttestor:
    def __init__(self, calls: list[str], valid_until: datetime) -> None:
        self.calls = calls
        self.valid_until = valid_until

    async def attest_capsule_handoff_lifecycle(
        self, request: WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestationRequest
    ) -> WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestation:
        self.calls.append("lifecycle-attestor")
        values: dict[str, object] = {
            "attestation_id": "target-context-capsule-handoff-lifecycle.imp-213",
            "attestor_id": ("attestor.workflow-protected-target-context-capsule-handoff-lifecycle"),
            "attestor_version": "1.0",
            "authorization_lease_id": request.authorization_lease_id,
            "authorization_lease_digest": request.authorization_lease_digest,
            "consumer_binding_id": request.consumer_binding_id,
            "consumer_binding_digest": request.consumer_binding_digest,
            "sealed_capsule_id": request.sealed_capsule_id,
            "sealed_capsule_digest": request.sealed_capsule_digest,
            "capsule_schema_id": request.capsule_schema_id,
            "capsule_schema_version": request.capsule_schema_version,
            "request_nonce_digest": request.request_nonce_digest,
            "observed_at": request.requested_at,
            "valid_until": self.valid_until,
            "handoff_eligible": True,
            "revoked": False,
            "destroyed": False,
            "sealed": True,
            "already_handed_off": False,
            "capsule_is_bearer_capability": False,
            "signing_key_id": "key.target-context-capsule-lifecycle.imp-213",
            "signature_algorithm": "test-sha256-v1",
            "integrity_signature": "signature.imp-213",
        }
        return WorkflowProtectedTargetContextCapsuleHandoffLifecycleAttestation(
            **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
        )


class _AcceptanceAttestor:
    def __init__(self, calls: list[str], valid_until: datetime) -> None:
        self.calls = calls
        self.valid_until = valid_until

    async def attest_consumer_boundary_acceptance(
        self, request: WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestationRequest
    ) -> WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestation:
        self.calls.append("acceptance-attestor")
        values: dict[str, object] = {
            "attestation_id": "target-context-capsule-handoff-acceptance.imp-213",
            "attestor_id": (
                "attestor.workflow-protected-target-context-consumer-boundary-acceptance"
            ),
            "attestor_version": "1.0",
            "authorization_lease_id": request.authorization_lease_id,
            "authorization_lease_digest": request.authorization_lease_digest,
            "consumer_binding_id": request.consumer_binding_id,
            "consumer_binding_digest": request.consumer_binding_digest,
            "consumer_subject_id": request.consumer_subject_id,
            "consumer_audience": request.consumer_audience,
            "consumer_contract_id": request.consumer_contract_id,
            "consumer_contract_version": request.consumer_contract_version,
            "purpose_id": request.purpose_id,
            "capsule_schema_id": request.capsule_schema_id,
            "capsule_schema_version": request.capsule_schema_version,
            "destination_boundary_id": request.destination_boundary_id,
            "destination_deployment_id": request.destination_deployment_id,
            "destination_generation": request.destination_generation,
            "destination_fencing_token_digest": request.destination_fencing_token_digest,
            "custody_contract_id": request.custody_contract_id,
            "custody_contract_version": request.custody_contract_version,
            "approved_adapter_id": request.approved_adapter_id,
            "approved_adapter_version": request.approved_adapter_version,
            "verification_signing_key_id": request.verification_signing_key_id,
            "trusted_profile_digest": request.trusted_profile_digest,
            "request_nonce_digest": request.request_nonce_digest,
            "observed_at": request.requested_at,
            "valid_until": self.valid_until,
            "acceptance_eligible": True,
            "destination_is_protected_boundary": True,
            "runtime_use_authorized": False,
            "signing_key_id": "key.target-context-capsule-acceptance.imp-213",
            "signature_algorithm": "test-sha256-v1",
            "integrity_signature": "signature.imp-213",
        }
        return WorkflowProtectedTargetContextConsumerBoundaryAcceptanceAttestation(
            **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
        )


class _CountingAdapter:
    def __init__(self, calls: list[str], clock: Any) -> None:
        self.calls = calls
        self.delegate = (
            DeterministicSyntheticWorkflowProtectedTargetContextCapsuleSealedHandoffAdapter(
                allow_synthetic_handoff=True, clock=clock
            )
        )

    @property
    def available(self) -> bool:
        return self.delegate.available

    @property
    def adapter_id(self) -> str:
        return self.delegate.adapter_id

    @property
    def adapter_version(self) -> str:
        return self.delegate.adapter_version

    @property
    def adapter_contract_id(self) -> str:
        return self.delegate.adapter_contract_id

    @property
    def adapter_contract_version(self) -> str:
        return self.delegate.adapter_contract_version

    async def handoff_sealed_capsule(self, instruction: Any) -> Any:
        self.calls.append("adapter")
        return await self.delegate.handoff_sealed_capsule(instruction)

    def verify_receipt(self, receipt: Any) -> bool:
        return self.delegate.verify_receipt(receipt)


class _Repository:
    def __init__(
        self,
        *,
        lease: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease,
        binding: WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
        now: datetime,
        calls: list[str],
        durable: bool = True,
    ) -> None:
        self.lease = lease
        self.binding = binding
        self.now = now
        self.calls = calls
        self._durable = durable
        self.claim: WorkflowProtectedTransportTargetContextCapsuleHandoffConsumptionClaim | None = (
            None
        )
        self.attempt: WorkflowProtectedTransportTargetContextCapsuleHandoffAttempt | None = None
        self.result: WorkflowProtectedTransportTargetContextCapsuleHandoffResult | None = None

    @property
    def durable(self) -> bool:
        return self._durable

    async def get_authoritative_time(self) -> datetime:
        self.calls.append("authoritative-time")
        return self.now

    async def get_target_context_capsule_handoff_authorization_lease_by_id(
        self, *, authorization_lease_id: str
    ) -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease | None:
        self.calls.append("load-lease")
        return self.lease if authorization_lease_id == self.lease.authorization_lease_id else None

    async def get_target_context_capsule_consumer_binding_by_id(
        self, *, binding_id: str
    ) -> WorkflowProtectedTransportTargetContextCapsuleConsumerBinding | None:
        self.calls.append("load-binding")
        return self.binding if binding_id == self.binding.binding_id else None

    async def lookup_target_context_capsule_handoff_replay(
        self, request: WorkflowTargetContextCapsuleHandoffReplayLookupRequest
    ) -> WorkflowTargetContextCapsuleHandoffReplayLookup:
        self.calls.append("replay-lookup")
        if self.claim is None:
            return WorkflowTargetContextCapsuleHandoffReplayLookup(
                WorkflowProtectedTransportTargetContextCapsuleHandoffReplayStatus.NONE, None, None
            )
        if self.claim.idempotency_digest == request.idempotency_digest:
            if self.claim.request_fingerprint != request.request_fingerprint:
                return WorkflowTargetContextCapsuleHandoffReplayLookup(
                    WorkflowProtectedTransportTargetContextCapsuleHandoffReplayStatus.IDEMPOTENCY_CONFLICT,
                    None,
                    None,
                )
        elif self.claim.request_fingerprint != request.request_fingerprint:
            return WorkflowTargetContextCapsuleHandoffReplayLookup(
                WorkflowProtectedTransportTargetContextCapsuleHandoffReplayStatus.ALREADY_CONSUMED,
                None,
                None,
            )
        return WorkflowTargetContextCapsuleHandoffReplayLookup(
            (
                WorkflowProtectedTransportTargetContextCapsuleHandoffReplayStatus.TERMINAL
                if self.result is not None
                else (
                    WorkflowProtectedTransportTargetContextCapsuleHandoffReplayStatus
                ).CLAIM_ONLY_UNCERTAIN
            ),
            self.attempt,
            self.result,
        )

    async def claim_target_context_capsule_handoff(
        self, request: WorkflowTargetContextCapsuleHandoffClaimRequest
    ) -> WorkflowTargetContextCapsuleHandoffClaimResult:
        self.calls.append("claim")
        validate_workflow_target_context_capsule_handoff_claim_request(request)
        authority = WorkflowProtectedTransportTargetContextCapsuleHandoffAuthority()
        claim_values: dict[str, object] = {
            "claim_id": request.claim_id,
            "handoff_id": request.handoff_id,
            "attempt_id": request.attempt_id,
            "authorization_lease_id": request.authorization_lease_id,
            "authorization_lease_digest": request.authorization_lease_digest,
            "consumer_binding_id": request.expected_consumer_binding_id,
            "consumer_binding_digest": request.expected_consumer_binding_digest,
            "sealed_capsule_id": request.expected_sealed_capsule_id,
            "sealed_capsule_digest": request.expected_sealed_capsule_digest,
            "scope": request.scope,
            "consumer_subject_id": request.consumer_subject_id,
            "consumer_audience": request.consumer_audience,
            "consumer_contract_id": request.consumer_contract_id,
            "consumer_contract_version": request.consumer_contract_version,
            "purpose_id": request.purpose_id,
            "policy_id": request.expected_policy_id,
            "policy_version": request.expected_policy_version,
            "policy_digest": request.expected_policy_digest,
            "request_fingerprint": request.request_fingerprint,
            "idempotency_digest": request.idempotency_digest,
            "consumption_authorization_audit_digest": (
                request.consumption_authorization_audit_digest
            ),
            "claimed_at": self.now,
            "authority": authority,
        }
        claim = WorkflowProtectedTransportTargetContextCapsuleHandoffConsumptionClaim(
            **cast(Any, claim_values),
            canonical_digest=canonical_digest(_payload(claim_values)),
        )
        deadline = min(
            self.lease.valid_until,
            self.binding.effective_until,
            request.lifecycle_attestation.valid_until,
            request.acceptance_attestation.valid_until,
        )
        attempt_values: dict[str, object] = {
            "attempt_id": request.attempt_id,
            "handoff_id": request.handoff_id,
            "consumption_claim_id": claim.claim_id,
            "consumption_claim_digest": claim.canonical_digest,
            "authorization_lease_id": request.authorization_lease_id,
            "authorization_lease_digest": request.authorization_lease_digest,
            "consumer_binding_id": request.expected_consumer_binding_id,
            "consumer_binding_digest": request.expected_consumer_binding_digest,
            "sealed_capsule_id": request.expected_sealed_capsule_id,
            "sealed_capsule_digest": request.expected_sealed_capsule_digest,
            "capsule_schema_id": request.expected_capsule_schema_id,
            "capsule_schema_version": request.expected_capsule_schema_version,
            "scope": request.scope,
            "consumer_subject_id": request.consumer_subject_id,
            "consumer_audience": request.consumer_audience,
            "consumer_contract_id": request.consumer_contract_id,
            "consumer_contract_version": request.consumer_contract_version,
            "purpose_id": request.purpose_id,
            "policy_id": request.expected_policy_id,
            "policy_version": request.expected_policy_version,
            "policy_digest": request.expected_policy_digest,
            "adapter_contract_id": request.expected_adapter_contract_id,
            "adapter_contract_version": request.expected_adapter_contract_version,
            "approved_adapter_id": request.expected_approved_adapter_id,
            "approved_adapter_version": request.expected_approved_adapter_version,
            "destination_boundary_id": request.expected_destination_boundary_id,
            "destination_deployment_id": request.expected_destination_deployment_id,
            "destination_generation": request.expected_destination_generation,
            "destination_fencing_token_digest": (request.expected_destination_fencing_token_digest),
            "custody_contract_id": request.expected_custody_contract_id,
            "custody_contract_version": request.expected_custody_contract_version,
            "verification_signing_key_id": request.expected_verification_signing_key_id,
            "trusted_profile_digest": request.expected_trusted_profile_digest,
            "lifecycle_attestation_id": request.lifecycle_attestation.attestation_id,
            "lifecycle_attestation_digest": request.lifecycle_attestation.canonical_digest,
            "acceptance_attestation_id": request.acceptance_attestation.attestation_id,
            "acceptance_attestation_digest": request.acceptance_attestation.canonical_digest,
            "request_nonce_digest": request.expected_request_nonce_digest,
            "started_at": self.now,
            "handoff_deadline": deadline,
            "lease_valid_until": self.lease.valid_until,
            "binding_effective_until": self.binding.effective_until,
            "source_effective_until": self.binding.effective_until,
            "lifecycle_attestation_valid_until": request.lifecycle_attestation.valid_until,
            "acceptance_attestation_valid_until": request.acceptance_attestation.valid_until,
            "state": WorkflowProtectedTransportTargetContextCapsuleHandoffAttemptState.STARTED,
            "authority": authority,
        }
        attempt = WorkflowProtectedTransportTargetContextCapsuleHandoffAttempt(
            **cast(Any, attempt_values),
            canonical_digest=canonical_digest(_payload(attempt_values)),
        )
        self.claim = claim
        self.attempt = attempt
        return WorkflowTargetContextCapsuleHandoffClaimResult(
            WorkflowProtectedTransportTargetContextCapsuleHandoffClaimStatus.CLAIMED,
            claim,
            attempt,
            None,
        )

    async def record_target_context_capsule_handoff_result(
        self, request: WorkflowTargetContextCapsuleHandoffResultRequest
    ) -> WorkflowTargetContextCapsuleHandoffResultWrite:
        self.calls.append("record-result")
        self.result = request.result
        return WorkflowTargetContextCapsuleHandoffResultWrite(
            WorkflowProtectedTransportTargetContextCapsuleHandoffResultWriteStatus.RECORDED,
            self.result,
        )

    async def list_target_context_capsule_handoff_attempts(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedTransportTargetContextCapsuleHandoffAttempt, ...]:
        if self.attempt is None or self.attempt.scope != scope:
            return ()
        return (self.attempt,)[:limit]

    async def get_target_context_capsule_handoff_results_by_handoff_ids(
        self, *, scope: WorkflowScope, handoff_ids: tuple[str, ...]
    ) -> tuple[WorkflowProtectedTransportTargetContextCapsuleHandoffResult, ...]:
        if (
            self.result is None
            or self.result.scope != scope
            or self.result.handoff_id not in handoff_ids
        ):
            return ()
        return (self.result,)


async def _fixture(*, durable: bool = True) -> tuple[Any, _Repository, _CountingAdapter, Any]:
    authorization_service, authorization_repository, *_ = authorization_service_fixture()
    lease = await authorize(authorization_service)
    now = lease.issued_at + timedelta(milliseconds=200)
    calls: list[str] = []
    repository = _Repository(
        lease=lease,
        binding=authorization_repository.binding,
        now=now,
        calls=calls,
        durable=durable,
    )
    adapter = _CountingAdapter([], lambda: now + timedelta(milliseconds=100))
    service = WorkflowProtectedTransportTargetContextCapsuleHandoffService(
        repository=cast(Any, repository),
        lifecycle_attestor=_LifecycleAttestor(calls, lease.effective_until),
        acceptance_attestor=_AcceptanceAttestor(calls, lease.effective_until),
        attestation_signature_verifier=_Verifier(),
        adapter=adapter,
        audit_sink=CollectingAuditSink(),
    )
    return service, repository, adapter, lease


async def _handoff(service: Any, lease: Any, **changes: Any) -> Any:
    values: dict[str, Any] = {
        "authorization_lease_id": lease.authorization_lease_id,
        "authorization_lease_digest": lease.canonical_digest,
        "policy_id": service.policy.policy_id,
        "policy_version": service.policy.policy_version,
        "irreversible_consumption_acknowledged": True,
        "uncertain_outcome_requires_new_authorization_acknowledged": True,
        "idempotency_key": "target-context-capsule-handoff-0001",
        "context": consumer_context(requested_at=lease.issued_at),
    }
    values.update(changes)
    return await service.handoff(**values)


@pytest.mark.asyncio
async def test_exact_replay_preflight_skips_attestor_and_adapter_io() -> None:
    service, repository, adapter, lease = await _fixture()
    first = await _handoff(service, lease)
    assert first.result is not None
    assert adapter.calls.count("adapter") == 1

    repository.calls.clear()
    second = await _handoff(service, lease)

    assert second == first
    assert repository.calls == ["replay-lookup"]
    assert adapter.calls.count("adapter") == 1


@pytest.mark.asyncio
async def test_invalid_request_and_non_durable_repository_fail_closed_without_io() -> None:
    service, repository, adapter, lease = await _fixture()
    with pytest.raises(
        WorkflowProtectedTransportTargetContextCapsuleHandoffError,
        match="target_context_capsule_handoff_request_invalid",
    ):
        await _handoff(service, lease, irreversible_consumption_acknowledged=False)
    assert repository.calls == []
    assert adapter.calls == []

    service, repository, adapter, lease = await _fixture(durable=False)
    with pytest.raises(
        WorkflowProtectedTransportTargetContextCapsuleHandoffError,
        match="target_context_capsule_handoff_durable_repository_required",
    ):
        await _handoff(service, lease)
    assert repository.calls == []
    assert adapter.calls == []


@pytest.mark.asyncio
async def test_adapter_is_called_at_most_once_and_all_evidence_has_zero_authority() -> None:
    service, repository, adapter, lease = await _fixture()

    presentation = await _handoff(service, lease)

    assert adapter.calls.count("adapter") == 1
    assert presentation.result is not None
    assert repository.claim is not None and repository.attempt is not None
    for evidence in (repository.claim, repository.attempt, presentation.result):
        authority = evidence.authority.canonical_value()
        assert len(authority) == 18
        assert all(value is False for value in authority.values())


@pytest.mark.asyncio
async def test_idempotency_conflict_fails_before_attestor_and_adapter_io() -> None:
    service, repository, adapter, lease = await _fixture()
    await _handoff(service, lease)
    repository.calls.clear()

    with pytest.raises(
        WorkflowProtectedTransportTargetContextCapsuleHandoffError,
        match="target_context_capsule_handoff_idempotency_conflict",
    ):
        await _handoff(service, lease, authorization_lease_digest="f" * 64)

    assert repository.calls == ["replay-lookup"]
    assert adapter.calls.count("adapter") == 1
