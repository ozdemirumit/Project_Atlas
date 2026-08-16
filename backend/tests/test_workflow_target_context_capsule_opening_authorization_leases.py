from __future__ import annotations

from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, cast

import pytest
from test_workflow_target_context_capsule_handoff_authorization_leases import make_binding
from test_workflow_target_context_capsule_handoffs import make_attempt

from atlas.core.audit import AuditRecord
from atlas.modules.workflows.application import (
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestationRequest,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseError,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseRequest,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseResult,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseService,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseStatus,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationSource,
    validate_workflow_protected_transport_target_context_capsule_opening_authorization_request,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestation,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBindingAuthority,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthority,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseState,
    WorkflowProtectedTransportTargetContextCapsuleHandoffConsumptionClaim,
    WorkflowProtectedTransportTargetContextCapsuleHandoffLeaseAuthority,
    WorkflowProtectedTransportTargetContextCapsuleHandoffResult,
    WorkflowProtectedTransportTargetContextCapsuleHandoffResultState,
    WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease,
    WorkflowProtectedTransportTargetContextCapsuleOpeningLeaseAuthority,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_transport_target_context_capsule_handoff_authorization_policy,
    code_owned_workflow_protected_transport_target_context_capsule_handoff_consumption_policy,
    code_owned_workflow_protected_transport_target_context_capsule_opening_authorization_policy,
)

NOW = datetime(2026, 8, 16, 14, 0, tzinfo=UTC)
DB_NOW = NOW + timedelta(milliseconds=100)
SCOPE = WorkflowScope("org-atlas", "environment-lab", "site-istanbul")


def _payload(instance: object) -> dict[str, object]:
    items = (
        instance.items()
        if isinstance(instance, dict)
        else (
            (field.name, getattr(instance, field.name))
            for field in fields(cast(Any, instance))
            if field.name != "canonical_digest"
        )
    )
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
        for name, value in items
    }


def _replace_and_redigest(instance: Any, **changes: object) -> Any:
    values = {
        field.name: getattr(instance, field.name)
        for field in fields(instance)
        if field.name != "canonical_digest"
    }
    values.update(changes)
    return type(instance)(**values, canonical_digest=canonical_digest(_payload(values)))


def make_source() -> WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationSource:
    binding = make_binding(effective_until=DB_NOW + timedelta(seconds=20))
    binding = _replace_and_redigest(
        binding,
        binding_id="target-context-capsule-consumer-binding.imp-214",
        sealed_capsule_id="sealed-target-context-capsule.imp-214",
        sealed_capsule_digest="4" * 64,
        capsule_schema_id="schema.workflow-protected-target-context-capsule",
        capsule_schema_version="1.0",
        authority=WorkflowProtectedTransportTargetContextCapsuleConsumerBindingAuthority(),
    )
    handoff_authorization_policy = code_owned_workflow_protected_transport_target_context_capsule_handoff_authorization_policy()  # noqa: E501
    upstream_values: dict[str, object] = {
        "authorization_lease_id": "workflow-target-context-capsule-handoff-lease.imp-214",
        "consumer_binding_id": binding.binding_id,
        "consumer_binding_digest": binding.canonical_digest,
        "opening_result_id": binding.opening_result_id,
        "opening_result_digest": binding.opening_result_digest,
        "sealed_capsule_id": binding.sealed_capsule_id,
        "sealed_capsule_digest": binding.sealed_capsule_digest,
        "capsule_schema_id": binding.capsule_schema_id,
        "capsule_schema_version": binding.capsule_schema_version,
        "lifecycle_attestation_id": "capsule-lifecycle-attestation.imp-214",
        "lifecycle_attestation_digest": "5" * 64,
        "lifecycle_attestation_valid_until": DB_NOW + timedelta(seconds=10),
        "scope": SCOPE,
        "consumer_subject_id": handoff_authorization_policy.consumer_subject_id,
        "consumer_audience": handoff_authorization_policy.consumer_audience,
        "consumer_contract_id": handoff_authorization_policy.consumer_contract_id,
        "consumer_contract_version": handoff_authorization_policy.consumer_contract_version,
        "purpose_id": handoff_authorization_policy.purpose_id,
        "policy_id": handoff_authorization_policy.policy_id,
        "policy_version": handoff_authorization_policy.policy_version,
        "policy_digest": handoff_authorization_policy.canonical_digest,
        "issued_at": NOW - timedelta(seconds=1),
        "valid_until": NOW,
        "effective_until": binding.effective_until,
        "single_use": True,
        "renewable": False,
        "transferable": False,
        "lease_is_bearer_capability": False,
        "state": (
            WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseState.AUTHORIZED_UNCONSUMED
        ),
        "authority": WorkflowProtectedTransportTargetContextCapsuleHandoffLeaseAuthority(),
    }
    upstream = WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease(
        **cast(Any, upstream_values), canonical_digest=canonical_digest(_payload(upstream_values))
    )
    handoff_policy = (
        code_owned_workflow_protected_transport_target_context_capsule_handoff_consumption_policy()
    )
    claim_values: dict[str, object] = {
        "claim_id": "workflow-target-context-capsule-handoff-claim.imp-214",
        "handoff_id": "workflow-target-context-capsule-handoff.imp-214",
        "attempt_id": "workflow-target-context-capsule-handoff-attempt.imp-214",
        "authorization_lease_id": upstream.authorization_lease_id,
        "authorization_lease_digest": upstream.canonical_digest,
        "consumer_binding_id": binding.binding_id,
        "consumer_binding_digest": binding.canonical_digest,
        "sealed_capsule_id": binding.sealed_capsule_id,
        "sealed_capsule_digest": binding.sealed_capsule_digest,
        "scope": SCOPE,
        "consumer_subject_id": handoff_policy.consumer_subject_id,
        "consumer_audience": handoff_policy.consumer_audience,
        "consumer_contract_id": handoff_policy.consumer_contract_id,
        "consumer_contract_version": handoff_policy.consumer_contract_version,
        "purpose_id": handoff_policy.purpose_id,
        "policy_id": handoff_policy.policy_id,
        "policy_version": handoff_policy.policy_version,
        "policy_digest": handoff_policy.canonical_digest,
        "request_fingerprint": "6" * 64,
        "idempotency_digest": "7" * 64,
        "consumption_authorization_audit_digest": "8" * 64,
        "claimed_at": NOW - timedelta(milliseconds=900),
        "authority": WorkflowProtectedTransportTargetContextCapsuleHandoffAuthority(),
    }
    claim = WorkflowProtectedTransportTargetContextCapsuleHandoffConsumptionClaim(
        **cast(Any, claim_values), canonical_digest=canonical_digest(_payload(claim_values))
    )
    attempt = make_attempt(
        started_at=NOW - timedelta(milliseconds=800),
        handoff_deadline=NOW + timedelta(milliseconds=50),
        handoff_id=claim.handoff_id,
        scope=SCOPE,
    )
    attempt = _replace_and_redigest(
        attempt,
        attempt_id=claim.attempt_id,
        consumption_claim_id=claim.claim_id,
        consumption_claim_digest=claim.canonical_digest,
        authorization_lease_id=upstream.authorization_lease_id,
        authorization_lease_digest=upstream.canonical_digest,
        consumer_binding_id=binding.binding_id,
        consumer_binding_digest=binding.canonical_digest,
        sealed_capsule_id=binding.sealed_capsule_id,
        sealed_capsule_digest=binding.sealed_capsule_digest,
        capsule_schema_id=binding.capsule_schema_id,
        capsule_schema_version=binding.capsule_schema_version,
    )
    result_values: dict[str, object] = {
        "handoff_id": claim.handoff_id,
        "attempt_id": attempt.attempt_id,
        "attempt_digest": attempt.canonical_digest,
        "consumption_claim_id": claim.claim_id,
        "consumption_claim_digest": claim.canonical_digest,
        "authorization_lease_id": upstream.authorization_lease_id,
        "authorization_lease_digest": upstream.canonical_digest,
        "consumer_binding_id": binding.binding_id,
        "consumer_binding_digest": binding.canonical_digest,
        "scope": SCOPE,
        "consumer_contract_id": handoff_policy.consumer_contract_id,
        "consumer_contract_version": handoff_policy.consumer_contract_version,
        "purpose_id": handoff_policy.purpose_id,
        "policy_id": handoff_policy.policy_id,
        "policy_version": handoff_policy.policy_version,
        "policy_digest": handoff_policy.canonical_digest,
        "adapter_contract_id": handoff_policy.required_adapter_contract_id,
        "adapter_contract_version": handoff_policy.required_adapter_contract_version,
        "receipt_digest": "9" * 64,
        "state": WorkflowProtectedTransportTargetContextCapsuleHandoffResultState.HANDED_OFF_SEALED,
        "failure_class": None,
        "consumer_receipt_id": "consumer-receipt.imp-214",
        "consumer_receipt_is_bearer_capability": False,
        "sealed_capsule_handed_off": True,
        "completed_at": NOW,
        "usable_until": DB_NOW + timedelta(seconds=10),
        "source_cleanup_confirmed": False,
        "authority": WorkflowProtectedTransportTargetContextCapsuleHandoffAuthority(),
    }
    result = WorkflowProtectedTransportTargetContextCapsuleHandoffResult(
        **cast(Any, result_values), canonical_digest=canonical_digest(_payload(result_values))
    )
    return WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationSource(
        result=result,
        attempt=attempt,
        consumption_claim=claim,
        upstream_authorization_lease=upstream,
        consumer_binding=binding,
    )


class _AuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, record: AuditRecord) -> None:
        self.records.append(record)


class _Verifier:
    def verify_destination_custody_attestation(
        self, attestation: WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestation
    ) -> bool:
        return attestation.integrity_signature == "signature.imp-214"


class _Attestor:
    def __init__(self, *, available: bool = True) -> None:
        self._available = available
        self.calls = 0

    @property
    def available(self) -> bool:
        return self._available

    async def attest_destination_custody(
        self,
        request: WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestationRequest,
    ) -> WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestation:
        self.calls += 1
        values: dict[str, object] = {
            **{
                name: getattr(request, name)
                for name in (
                    "handoff_id",
                    "handoff_result_digest",
                    "attempt_id",
                    "attempt_digest",
                    "consumption_claim_id",
                    "consumption_claim_digest",
                    "consumer_binding_id",
                    "consumer_binding_digest",
                    "sealed_capsule_id",
                    "sealed_capsule_digest",
                    "consumer_receipt_id",
                    "receipt_digest",
                    "destination_boundary_id",
                    "destination_deployment_id",
                    "destination_generation",
                    "destination_fencing_token_digest",
                    "custody_contract_id",
                    "custody_contract_version",
                    "approved_adapter_id",
                    "approved_adapter_version",
                    "verification_signing_key_id",
                    "trusted_profile_digest",
                    "request_nonce_digest",
                )
            },
            "attestation_id": "destination-custody-attestation.imp-214",
            "attestor_id": "attestor.workflow-protected-target-context-capsule-destination-custody",
            "attestor_version": "1.0",
            "observed_at": request.requested_at,
            "valid_until": DB_NOW + timedelta(seconds=5),
            "handed_off_sealed": True,
            "destination_custody_confirmed": True,
            "custody_finality_confirmed": True,
            "capsule_remains_sealed": True,
            "revoked": False,
            "destroyed": False,
            "signing_key_id": "key.destination-custody.imp-214",
            "signature_algorithm": "test-sha256-v1",
            "integrity_signature": "signature.imp-214",
        }
        return WorkflowProtectedTargetContextCapsuleDestinationCustodyAttestation(
            **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
        )


class _Repository:
    def __init__(
        self, source: WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationSource
    ) -> None:
        self.source = source
        self.requests: list[
            WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseRequest
        ] = []
        self._lease: (
            WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease | None
        ) = None

    @property
    def durable(self) -> bool:
        return True

    async def get_authoritative_time(self) -> datetime:
        return DB_NOW

    async def get_target_context_capsule_opening_authorization_source(
        self, *, handoff_id: str
    ) -> WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationSource | None:
        return self.source if handoff_id == self.source.result.handoff_id else None

    async def authorize_target_context_capsule_opening(
        self,
        request: WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseRequest,
    ) -> WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseResult:
        validate_workflow_protected_transport_target_context_capsule_opening_authorization_request(
            request
        )
        self.requests.append(request)
        await request.required_precommit_audit()
        if self._lease is None:
            self._lease = request.candidate
            status = WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseStatus.AUTHORIZED  # noqa: E501
        else:
            status = (
                WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseStatus.REPLAY
            )
        return WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseResult(
            status, self._lease, DB_NOW
        )

    async def list_target_context_capsule_opening_authorization_leases(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLease, ...]:
        del limit
        return () if self._lease is None or self._lease.scope != scope else (self._lease,)


def _context() -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext:
    return WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
        subject_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        actor_type="service",
        authentication_method="workload_token",
        credential_audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
        scope=SCOPE,
        correlation_id="correlation.imp-214",
        decision_id="decision.imp-214",
        requested_at=NOW,
    )


@pytest.mark.asyncio
async def test_authorizes_exact_one_second_non_bearer_opening_lease() -> None:
    source = make_source()
    repository = _Repository(source)
    attestor = _Attestor()
    service = WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseService(
        authorization_repository=repository,
        custody_attestor=attestor,
        custody_signature_verifier=_Verifier(),
        audit_sink=_AuditSink(),
    )
    policy = code_owned_workflow_protected_transport_target_context_capsule_opening_authorization_policy()  # noqa: E501
    lease = await service.authorize(
        handoff_result_id=source.result.handoff_id,
        handoff_result_digest=source.result.canonical_digest,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        idempotency_key="imp-214-idempotency",
        context=_context(),
    )
    assert lease.valid_until - lease.issued_at == timedelta(seconds=1)
    assert lease.single_use and not lease.renewable and not lease.transferable
    assert not lease.lease_is_bearer_capability
    authority = lease.authority.canonical_value()
    assert authority["target_context_capsule_opening_authorized"] is True
    assert all(
        value is False
        for name, value in authority.items()
        if name != "target_context_capsule_opening_authorized"
    )
    assert attestor.calls == 1
    assert len(repository.requests) == 1


@pytest.mark.asyncio
async def test_rejects_human_before_attestor_or_repository_write() -> None:
    source = make_source()
    repository = _Repository(source)
    attestor = _Attestor()
    service = WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseService(
        authorization_repository=repository,
        custody_attestor=attestor,
        custody_signature_verifier=_Verifier(),
        audit_sink=_AuditSink(),
    )
    policy = service.policy
    with pytest.raises(
        WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseError,
        match="denied",
    ):
        await service.authorize(
            handoff_result_id=source.result.handoff_id,
            handoff_result_digest=source.result.canonical_digest,
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            idempotency_key="imp-214-human",
            context=replace(
                _context(),
                subject_id="user.admin",
                actor_type="human",
                authentication_method="password",
            ),
        )
    assert attestor.calls == 0
    assert repository.requests == []


@pytest.mark.asyncio
async def test_unavailable_trusted_attestor_fails_closed() -> None:
    source = make_source()
    repository = _Repository(source)
    service = WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseService(
        authorization_repository=repository,
        custody_attestor=_Attestor(available=False),
        custody_signature_verifier=_Verifier(),
        audit_sink=_AuditSink(),
    )
    with pytest.raises(
        WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseError
    ) as raised:
        await service.authorize(
            handoff_result_id=source.result.handoff_id,
            handoff_result_digest=source.result.canonical_digest,
            policy_id=service.policy.policy_id,
            policy_version=service.policy.policy_version,
            idempotency_key="imp-214-unavailable",
            context=_context(),
        )
    assert raised.value.code.endswith("trusted_attestor_unavailable")
    assert repository.requests == []


def test_authority_constructor_rejects_handoff_or_operational_authority() -> None:
    with pytest.raises(ValueError):
        WorkflowProtectedTransportTargetContextCapsuleOpeningLeaseAuthority(
            target_context_capsule_handoff_authorized=True
        )
    with pytest.raises(ValueError):
        WorkflowProtectedTransportTargetContextCapsuleOpeningLeaseAuthority(
            protected_artifact_access_authorized=True
        )
