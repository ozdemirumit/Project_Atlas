from __future__ import annotations

import hmac
import inspect
from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from hashlib import sha256
from typing import Any, cast

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.workflows.application import (
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTargetContextCapsuleLifecycleAttestationRequest,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseRepository,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseRequest,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseResult,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseService,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseStatus,
    validate_workflow_protected_transport_target_context_capsule_handoff_authorization_request,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedTargetContextCapsuleLifecycleAttestation,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBindingAuthority,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBindingState,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseEffectiveState,
    WorkflowProtectedTransportTargetContextCapsuleHandoffLeaseAuthority,
    WorkflowScope,
    canonical_digest,
    canonical_json_bytes,
    code_owned_workflow_protected_transport_target_context_capsule_consumer_binding_policy,
    code_owned_workflow_protected_transport_target_context_capsule_handoff_authorization_policy,
)

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)
DB_NOW = NOW + timedelta(seconds=1)
SCOPE = WorkflowScope("org-atlas", "environment-lab", "site-istanbul")
SIGNING_KEY = b"imp-212-focused-test-capsule-lifecycle-key"


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


def make_binding(
    *, effective_until: datetime = DB_NOW + timedelta(seconds=10)
) -> WorkflowProtectedTransportTargetContextCapsuleConsumerBinding:
    policy = (
        code_owned_workflow_protected_transport_target_context_capsule_consumer_binding_policy()
    )
    values: dict[str, object] = {
        "binding_id": "target-context-capsule-consumer-binding.imp-212",
        "opening_result_id": "target-context-artifact-opening.imp-210",
        "opening_result_digest": "a" * 64,
        "opening_attempt_id": "target-context-artifact-opening-attempt.imp-210",
        "opening_attempt_digest": "1" * 64,
        "lease_consumption_claim_id": "target-context-lease-consumption.imp-210",
        "lease_consumption_claim_digest": "2" * 64,
        "authorization_lease_id": "target-context-access-lease.imp-209",
        "authorization_lease_digest": "3" * 64,
        "sealed_capsule_id": "sealed-target-context-capsule.imp-210",
        "sealed_capsule_digest": "4" * 64,
        "capsule_schema_id": "schema.workflow-sealed-target-context-capsule-lineage",
        "capsule_schema_version": "1.0",
        "capsule_is_bearer_capability": False,
        "target_context_binding_id": "target-context-binding.imp-208",
        "target_context_binding_digest": "5" * 64,
        "target_context_commitment": "6" * 64,
        "outbox_entry_id": "dispatch-outbox.imp-212",
        "outbox_entry_digest": "7" * 64,
        "event_id": "workflow-event.imp-212",
        "event_digest": "8" * 64,
        "event_artifact_id": "workflow-event-artifact.imp-212",
        "event_artifact_digest": "9" * 64,
        "logical_channel_binding_id": "logical-channel-binding.imp-212",
        "logical_channel_binding_digest": "a" * 64,
        "physical_transport_route_binding_id": "physical-route-binding.imp-212",
        "physical_transport_route_binding_digest": "b" * 64,
        "transport_route_snapshot_id": "transport-route-snapshot.imp-212",
        "transport_route_snapshot_digest": "c" * 64,
        "physical_transport_credential_assignment_binding_id": (
            "physical-credential-assignment-binding.imp-212"
        ),
        "physical_transport_credential_assignment_binding_digest": "d" * 64,
        "credential_assignment_snapshot_id": "credential-assignment-snapshot.imp-212",
        "credential_assignment_snapshot_digest": "e" * 64,
        "plan_id": "workflow-plan.imp-212",
        "plan_digest": "f" * 64,
        "run_id": "workflow-run.imp-212",
        "run_digest": "0" * 64,
        "step_run_id": "workflow-step-run.imp-212",
        "step_run_digest": "1" * 64,
        "workflow_execution_attempt_id": "workflow-execution-attempt.imp-212",
        "workflow_execution_attempt_digest": "2" * 64,
        "target_id": "storage-target.imp-212",
        "target_type": "storage",
        "consumer_subject_id": policy.consumer_subject_id,
        "consumer_audience": policy.consumer_audience,
        "consumer_contract_id": policy.consumer_contract_id,
        "consumer_contract_version": policy.consumer_contract_version,
        "purpose_id": policy.purpose_id,
        "scope": SCOPE,
        "binder_subject_id": "service.workflow-protected-transport-target-context-capsule-binder",
        "binder_audience": "audience.workflow-protected-transport-target-context-capsule-binder",
        "bound_at": NOW,
        "effective_until": effective_until,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "request_fingerprint": "3" * 64,
        "idempotency_digest": "4" * 64,
        "authorization_audit_digest": "5" * 64,
        "state": WorkflowProtectedTransportTargetContextCapsuleConsumerBindingState.BOUND,
        "authority": WorkflowProtectedTransportTargetContextCapsuleConsumerBindingAuthority(),
    }
    return WorkflowProtectedTransportTargetContextCapsuleConsumerBinding(
        **cast(Any, values),
        canonical_digest=canonical_digest(_payload(values)),
    )


def make_attestation(
    request: WorkflowProtectedTargetContextCapsuleLifecycleAttestationRequest,
    *,
    valid_until: datetime = DB_NOW + timedelta(seconds=5),
    tamper_binding: bool = False,
    invalid_signature: bool = False,
) -> WorkflowProtectedTargetContextCapsuleLifecycleAttestation:
    values: dict[str, object] = {
        "attestation_id": "target-context-capsule-lifecycle-attestation.imp-212",
        "protected_store_attestor_id": (
            "attestor.workflow-protected-target-context-capsule-lifecycle"
        ),
        "protected_store_attestor_version": "1.0",
        "opening_result_id": request.opening_result_id,
        "opening_result_digest": request.opening_result_digest,
        "consumer_binding_id": (
            "target-context-capsule-consumer-binding.tampered"
            if tamper_binding
            else request.consumer_binding_id
        ),
        "consumer_binding_digest": request.consumer_binding_digest,
        "sealed_capsule_id": request.sealed_capsule_id,
        "sealed_capsule_digest": request.sealed_capsule_digest,
        "capsule_schema_id": request.capsule_schema_id,
        "capsule_schema_version": request.capsule_schema_version,
        "request_nonce_digest": request.request_nonce_digest,
        "observed_at": NOW,
        "valid_until": valid_until,
        "usable": True,
        "revoked": False,
        "destroyed": False,
        "sealed": True,
        "capsule_is_bearer_capability": False,
        "signing_key_id": "signing-key.target-context-capsule-lifecycle.imp-212",
        "signature_algorithm": "hmac-sha256",
    }
    signature = hmac.new(SIGNING_KEY, canonical_json_bytes(_payload(values)), sha256).hexdigest()
    values["integrity_signature"] = "0" * 64 if invalid_signature else signature
    return WorkflowProtectedTargetContextCapsuleLifecycleAttestation(
        **cast(Any, values),
        canonical_digest=canonical_digest(_payload(values)),
    )


def consumer_context(
    **changes: Any,
) -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext:
    values: dict[str, Any] = {
        "subject_id": WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        "actor_type": "service",
        "authentication_method": "workload_token",
        "credential_audience": WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
        "scope": SCOPE,
        "correlation_id": "correlation-imp-212",
        "decision_id": "decision-imp-212",
        "requested_at": NOW,
    }
    values.update(changes)
    return WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(**values)


class CollectingAuditSink:
    def __init__(self, *, fail_kind: str | None = None) -> None:
        self.records: list[AuditRecord] = []
        self.fail_kind = fail_kind

    async def record(self, event: AuditRecord) -> None:
        if self.fail_kind is not None and event.event_type.endswith(f".{self.fail_kind}"):
            raise RuntimeError("audit unavailable")
        self.records.append(event)


class FakeLifecycleAttestor:
    def __init__(
        self,
        calls: list[str],
        *,
        valid_until: datetime = DB_NOW + timedelta(seconds=5),
        tamper_binding: bool = False,
        invalid_signature: bool = False,
    ) -> None:
        self.calls = calls
        self.valid_until = valid_until
        self.tamper_binding = tamper_binding
        self.invalid_signature = invalid_signature
        self.requests: list[WorkflowProtectedTargetContextCapsuleLifecycleAttestationRequest] = []

    async def attest_capsule_lifecycle(
        self, request: WorkflowProtectedTargetContextCapsuleLifecycleAttestationRequest
    ) -> WorkflowProtectedTargetContextCapsuleLifecycleAttestation:
        self.calls.append("attest-capsule-lifecycle")
        self.requests.append(request)
        return make_attestation(
            request,
            valid_until=self.valid_until,
            tamper_binding=self.tamper_binding,
            invalid_signature=self.invalid_signature,
        )


class HmacLifecycleSignatureVerifier:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def verify_capsule_lifecycle_attestation(
        self, attestation: WorkflowProtectedTargetContextCapsuleLifecycleAttestation
    ) -> bool:
        self.calls.append("verify-capsule-lifecycle")
        expected = hmac.new(
            SIGNING_KEY,
            canonical_json_bytes(attestation.signature_payload()),
            sha256,
        ).hexdigest()
        return (
            attestation.signing_key_id == "signing-key.target-context-capsule-lifecycle.imp-212"
            and attestation.signature_algorithm == "hmac-sha256"
            and hmac.compare_digest(expected, attestation.integrity_signature)
        )


class FakeAuthorizationRepository:
    def __init__(
        self,
        binding: WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
        calls: list[str],
        *,
        durable: bool = True,
    ) -> None:
        self.binding = binding
        self.calls = calls
        self._durable = durable
        self.lease: (
            WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease | None
        ) = None
        self.fingerprint: str | None = None
        self.next_status: (
            WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseStatus | None
        ) = None

    @property
    def durable(self) -> bool:
        return self._durable

    async def get_authoritative_time(self) -> datetime:
        self.calls.append("authoritative-time")
        return DB_NOW

    async def get_target_context_capsule_consumer_binding_by_id(
        self, *, binding_id: str
    ) -> WorkflowProtectedTransportTargetContextCapsuleConsumerBinding | None:
        self.calls.append("load-consumer-binding")
        return self.binding if binding_id == self.binding.binding_id else None

    async def authorize_target_context_capsule_handoff(
        self,
        request: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseRequest,
    ) -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseResult:
        self.calls.append("authorize-repository")
        await request.required_precommit_audit()
        validate_workflow_protected_transport_target_context_capsule_handoff_authorization_request(
            request
        )
        if self.next_status is not None:
            return WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseResult(
                self.next_status,
                None,
            )
        if self.lease is not None:
            status_type = (
                WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseStatus
            )
            status = (
                status_type.REPLAY
                if self.fingerprint == request.request_fingerprint
                else status_type.IDEMPOTENCY_CONFLICT
            )
            return WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseResult(
                status,
                self.lease if status.name == "REPLAY" else None,
                self.lease.issued_at if status.name == "REPLAY" else None,
            )
        issued_at = request.candidate.issued_at + timedelta(milliseconds=250)
        valid_until = issued_at + timedelta(seconds=1)
        digest_payload = request.candidate.digest_payload()
        digest_payload["issued_at"] = issued_at.isoformat()
        digest_payload["valid_until"] = valid_until.isoformat()
        self.lease = replace(
            request.candidate,
            issued_at=issued_at,
            valid_until=valid_until,
            canonical_digest=canonical_digest(digest_payload),
        )
        self.fingerprint = request.request_fingerprint
        return WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseResult(
            WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseStatus.AUTHORIZED,
            self.lease,
            issued_at,
        )

    async def list_target_context_capsule_handoff_authorization_leases(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease, ...]:
        if self.lease is None or self.lease.scope != scope:
            return ()
        return (self.lease,)[:limit]


def service_fixture(
    *,
    binding: WorkflowProtectedTransportTargetContextCapsuleConsumerBinding | None = None,
    durable: bool = True,
    valid_until: datetime = DB_NOW + timedelta(seconds=5),
    tamper_binding: bool = False,
    invalid_signature: bool = False,
    audit: CollectingAuditSink | None = None,
) -> tuple[
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseService,
    FakeAuthorizationRepository,
    FakeLifecycleAttestor,
    HmacLifecycleSignatureVerifier,
    CollectingAuditSink,
    list[str],
]:
    calls: list[str] = []
    repository = FakeAuthorizationRepository(binding or make_binding(), calls, durable=durable)
    attestor = FakeLifecycleAttestor(
        calls,
        valid_until=valid_until,
        tamper_binding=tamper_binding,
        invalid_signature=invalid_signature,
    )
    verifier = HmacLifecycleSignatureVerifier(calls)
    selected_audit = audit or CollectingAuditSink()
    service = WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseService(
        authorization_repository=repository,
        lifecycle_status_attestor=attestor,
        lifecycle_signature_verifier=verifier,
        audit_sink=selected_audit,
    )
    return service, repository, attestor, verifier, selected_audit, calls


async def authorize(
    service: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseService,
    *,
    binding_digest: str | None = None,
    idempotency_key: str = "capsule-handoff-authorization-0001",
    context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext
    | None = None,
) -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLease:
    binding = cast(FakeAuthorizationRepository, service.repository).binding
    return await service.authorize(
        consumer_binding_id=binding.binding_id,
        consumer_binding_digest=binding_digest or binding.canonical_digest,
        policy_id=service.policy.policy_id,
        policy_version=service.policy.policy_version,
        idempotency_key=idempotency_key,
        context=context or consumer_context(),
    )


def test_domain_policy_attestation_and_authority_are_exact_and_canonical() -> None:
    policy = code_owned_workflow_protected_transport_target_context_capsule_handoff_authorization_policy()  # noqa: E501
    assert policy.validity_window_seconds == 1
    assert policy.consumer_subject_id == WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT
    assert policy.consumer_audience == WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE
    assert policy.full_window_required is policy.single_use_required is True
    assert policy.renewable_allowed is policy.transferable_allowed is False
    with pytest.raises(ValueError, match="not code-owned"):
        replace(policy, validity_window_seconds=2)

    authority = WorkflowProtectedTransportTargetContextCapsuleHandoffLeaseAuthority()
    assert len(authority.canonical_value()) == 18
    assert [name for name, value in authority.canonical_value().items() if value] == [
        "target_context_capsule_handoff_authorized"
    ]
    with pytest.raises(ValueError, match="only handoff authority"):
        replace(authority, delivery_authorized=True)

    binding = make_binding()
    request = WorkflowProtectedTargetContextCapsuleLifecycleAttestationRequest(
        opening_result_id=binding.opening_result_id,
        opening_result_digest=binding.opening_result_digest,
        consumer_binding_id=binding.binding_id,
        consumer_binding_digest=binding.canonical_digest,
        sealed_capsule_id=binding.sealed_capsule_id,
        sealed_capsule_digest=binding.sealed_capsule_digest,
        capsule_schema_id=binding.capsule_schema_id,
        capsule_schema_version=binding.capsule_schema_version,
        scope=SCOPE,
        consumer_subject_id=policy.consumer_subject_id,
        request_nonce_digest="6" * 64,
        requested_at=NOW,
    )
    attestation = make_attestation(request)
    assert attestation.sealed is True and attestation.capsule_is_bearer_capability is False
    assert canonical_digest(attestation.digest_payload()) == attestation.canonical_digest


@pytest.mark.asyncio
async def test_service_attests_before_repository_and_issues_exact_one_second_lease() -> None:
    service, repository, attestor, _, audit, calls = service_fixture()

    lease = await authorize(service)

    assert calls == [
        "load-consumer-binding",
        "attest-capsule-lifecycle",
        "authoritative-time",
        "verify-capsule-lifecycle",
        "authorize-repository",
        "verify-capsule-lifecycle",
    ]
    assert len(attestor.requests) == 1
    assert lease.valid_until - lease.issued_at == timedelta(seconds=1)
    assert lease.single_use is True and lease.renewable is lease.transferable is False
    assert lease.lease_is_bearer_capability is False
    assert lease.authority.target_context_capsule_handoff_authorized is True
    assert lease.effective_state(evaluated_at=lease.issued_at) is (
        WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseEffectiveState.ACTIVE
    )
    assert await service.list_leases(scope=SCOPE) == (lease,)
    assert repository.lease == lease
    assert [record.event_type.rsplit(".", 1)[-1] for record in audit.records] == [
        "intent",
        "persistence-readiness",
        "completion",
    ]


@pytest.mark.asyncio
async def test_exact_replay_requires_fresh_nonce_bound_lifecycle_attestation() -> None:
    service, repository, attestor, _, audit, _ = service_fixture()
    first = await authorize(service)

    replay = await authorize(service)

    assert replay == first
    assert repository.lease == first
    assert len(attestor.requests) == 2
    assert attestor.requests[0].request_nonce_digest != attestor.requests[1].request_nonce_digest
    assert audit.records[-1].event_type.endswith(".replay")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "context",
    [
        consumer_context(subject_id="service.other"),
        consumer_context(actor_type="human"),
        consumer_context(authentication_method="session_cookie"),
        consumer_context(credential_audience="audience.other"),
    ],
)
async def test_only_exact_code_owned_consumer_subject_and_audience_are_accepted(
    context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
) -> None:
    service, repository, attestor, _, _, calls = service_fixture()

    with pytest.raises(
        WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError
    ) as denied:
        await authorize(service, context=context)

    assert denied.value.code.endswith("consumer_identity_required")
    assert repository.lease is None and not attestor.requests and calls == []


@pytest.mark.asyncio
async def test_invalid_signature_lineage_and_incomplete_windows_fail_closed() -> None:
    service, repository, _, _, _, _ = service_fixture(invalid_signature=True)
    with pytest.raises(
        WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError
    ) as unsigned:
        await authorize(service)
    assert unsigned.value.code.endswith("evidence_conflict")
    assert repository.lease is None

    service, repository, _, _, _, _ = service_fixture(tamper_binding=True)
    with pytest.raises(
        WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError
    ) as mismatched:
        await authorize(service)
    assert mismatched.value.detail == unsigned.value.detail
    assert repository.lease is None

    service, repository, _, _, _, _ = service_fixture(
        valid_until=DB_NOW + timedelta(microseconds=999999)
    )
    with pytest.raises(
        WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError
    ):
        await authorize(service)
    assert repository.lease is None

    service, repository, _, _, _, _ = service_fixture(
        binding=make_binding(effective_until=DB_NOW + timedelta(microseconds=999999))
    )
    with pytest.raises(
        WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError
    ):
        await authorize(service)
    assert repository.lease is None


@pytest.mark.asyncio
async def test_non_durable_repository_fails_before_attestation_provider_io() -> None:
    service, repository, attestor, _, _, calls = service_fixture(durable=False)

    with pytest.raises(
        WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseError
    ) as denied:
        await authorize(service)

    assert denied.value.code.endswith("durable_repository_required")
    assert repository.lease is None and not attestor.requests and calls == []


def test_public_contract_excludes_caller_shaped_authority_and_provider_from_repository() -> None:
    assert set(
        inspect.signature(
            WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseService.authorize
        ).parameters
    ) == {
        "self",
        "consumer_binding_id",
        "consumer_binding_digest",
        "policy_id",
        "policy_version",
        "idempotency_key",
        "context",
    }
    forbidden = {
        "audience",
        "capsule",
        "delivery",
        "digest_policy",
        "network",
        "runtime",
        "subject",
        "ttl",
        "unseal",
    }
    public_fields = set(
        inspect.signature(
            WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseService.authorize
        ).parameters
    )
    assert not public_fields.intersection(forbidden)
    repository_request_fields = {
        field.name
        for field in fields(
            WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseRequest
        )
    }
    assert "lifecycle_attestation" in repository_request_fields
    assert "offline_signature_verifier" in repository_request_fields
    assert "lifecycle_status_attestor" not in repository_request_fields
    repository_members = {
        name
        for name, _ in inspect.getmembers(
            WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseRepository,
            predicate=inspect.isfunction,
        )
        if not name.startswith("_")
    }
    assert repository_members == {
        "authorize_target_context_capsule_handoff",
        "get_authoritative_time",
        "get_target_context_capsule_consumer_binding_by_id",
        "list_target_context_capsule_handoff_authorization_leases",
    }
