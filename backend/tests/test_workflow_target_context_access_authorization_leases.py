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
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_SUBJECT,
    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseService,
    WorkflowPhysicalTransportTargetContextAccessorContext,
    WorkflowProtectedArtifactStatusAttestationRequest,
    WorkflowTargetContextAccessAuthorizationLeaseError,
    WorkflowTargetContextAccessAuthorizationLeaseRepository,
    WorkflowTargetContextAccessAuthorizationLeaseRequest,
    WorkflowTargetContextAccessAuthorizationLeaseResult,
    WorkflowTargetContextAccessAuthorizationLeaseStatus,
    validate_workflow_target_context_access_authorization_request,
)
from atlas.modules.workflows.domain import (
    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease,
    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseAuthority,
    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseEffectiveState,
    WorkflowEventPhysicalTransportTargetContextBinding,
    WorkflowEventPhysicalTransportTargetContextBindingAuthority,
    WorkflowEventPhysicalTransportTargetContextBindingState,
    WorkflowProtectedArtifactKind,
    WorkflowProtectedArtifactStatusAttestation,
    WorkflowScope,
    canonical_digest,
    canonical_json_bytes,
    code_owned_workflow_event_physical_transport_target_context_access_authorization_policy,
)

NOW = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
DB_NOW = NOW + timedelta(seconds=1)
SCOPE = WorkflowScope("org-atlas", "environment-lab", "site-istanbul")
BINDING_ID = "workflow-target-context-binding.imp-209"
TARGET_CONTEXT_COMMITMENT = "7" * 64
STATUS_SIGNING_KEY = b"imp-209-focused-test-status-signing-key"


def _canonical_payload(values: dict[str, object]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for name, value in values.items():
        if isinstance(value, datetime):
            payload[name] = value.isoformat()
        elif isinstance(value, StrEnum):
            payload[name] = value.value
        elif isinstance(
            value,
            (
                WorkflowScope,
                WorkflowEventPhysicalTransportTargetContextBindingAuthority,
                WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseAuthority,
            ),
        ):
            payload[name] = value.canonical_value()
        else:
            payload[name] = value
    return payload


def make_binding(
    *, joint_usable_until: datetime = NOW + timedelta(minutes=30)
) -> WorkflowEventPhysicalTransportTargetContextBinding:
    values: dict[str, object] = {
        "binding_id": BINDING_ID,
        "physical_transport_route_binding_id": "workflow-route-binding.imp-209",
        "physical_transport_route_binding_digest": "1" * 64,
        "transport_route_snapshot_id": "transport-route-snapshot.imp-209",
        "transport_route_snapshot_digest": "2" * 64,
        "endpoint_materialization_id": "endpoint-materialization.imp-209",
        "endpoint_materialization_digest": "3" * 64,
        "physical_transport_credential_assignment_binding_id": (
            "workflow-credential-assignment-binding.imp-209"
        ),
        "physical_transport_credential_assignment_binding_digest": "4" * 64,
        "credential_assignment_snapshot_id": "credential-assignment-snapshot.imp-209",
        "credential_assignment_snapshot_digest": "5" * 64,
        "credential_materialization_id": "credential-materialization.imp-209",
        "credential_materialization_digest": "6" * 64,
        "resolver_subject_id": "service.workflow-physical-transport-endpoint-resolver",
        "accessor_subject_id": "service.workflow-physical-transport-credential-accessor",
        "target_context_schema_id": "schema.workflow-physical-transport-target-context",
        "target_context_schema_version": "1.0",
        "target_context_commitment": TARGET_CONTEXT_COMMITMENT,
        "scope": SCOPE,
        "binder_subject_id": "service.workflow-physical-transport-target-context-binder",
        "bound_at": NOW - timedelta(seconds=1),
        "joint_usable_until": joint_usable_until,
        "policy_id": "policy.workflow-event-physical-transport-target-context-binding",
        "policy_version": "1.0",
        "policy_digest": "8" * 64,
        "state": WorkflowEventPhysicalTransportTargetContextBindingState.BOUND,
        "authority": WorkflowEventPhysicalTransportTargetContextBindingAuthority(),
    }
    return WorkflowEventPhysicalTransportTargetContextBinding(
        **cast(Any, values),
        canonical_digest=canonical_digest(_canonical_payload(values)),
    )


def make_attestation(
    request: WorkflowProtectedArtifactStatusAttestationRequest,
    *,
    valid_until: datetime = NOW + timedelta(seconds=20),
    tamper_binding: bool = False,
    invalid_signature: bool = False,
) -> WorkflowProtectedArtifactStatusAttestation:
    kind = request.artifact_kind.value
    values: dict[str, object] = {
        "artifact_kind": request.artifact_kind,
        "materialization_id": request.materialization_id,
        "materialization_digest": request.materialization_digest,
        "target_context_binding_id": (
            "workflow-target-context-binding.tampered"
            if tamper_binding
            else request.target_context_binding_id
        ),
        "target_context_binding_digest": request.target_context_binding_digest,
        "target_context_commitment": request.target_context_commitment,
        "protected_store_attestor_id": (f"attestor.workflow-protected-{kind}-store-status"),
        "protected_store_attestor_version": "1.0",
        "attestation_id": f"protected-{kind}-status-attestation.imp-209",
        "request_nonce_digest": request.request_nonce_digest,
        "observed_at": NOW,
        "valid_until": valid_until,
        "usable": True,
        "revoked": False,
        "destroyed": False,
        "signing_key_id": "signing-key.workflow-protected-store-status.imp-209",
        "signature_algorithm": "hmac-sha256",
    }
    signature = hmac.new(
        STATUS_SIGNING_KEY,
        canonical_json_bytes(_canonical_payload(values)),
        sha256,
    ).hexdigest()
    values["integrity_signature"] = "0" * 64 if invalid_signature else signature
    return WorkflowProtectedArtifactStatusAttestation(
        **cast(Any, values),
        canonical_digest=canonical_digest(_canonical_payload(values)),
    )


class CollectingAuditSink:
    def __init__(self, *, fail_kind: str | None = None) -> None:
        self.records: list[AuditRecord] = []
        self.fail_kind = fail_kind

    async def record(self, event: AuditRecord) -> None:
        if self.fail_kind is not None and event.event_type.endswith(f".{self.fail_kind}"):
            raise RuntimeError("audit unavailable")
        self.records.append(event)


class FakeStatusAttestor:
    def __init__(
        self,
        *,
        kind: WorkflowProtectedArtifactKind,
        calls: list[str],
        valid_until: datetime = NOW + timedelta(seconds=20),
        tamper_binding: bool = False,
        invalid_signature: bool = False,
    ) -> None:
        self.kind = kind
        self.calls = calls
        self.valid_until = valid_until
        self.tamper_binding = tamper_binding
        self.invalid_signature = invalid_signature
        self.requests: list[WorkflowProtectedArtifactStatusAttestationRequest] = []

    async def attest_endpoint_artifact_status(
        self, request: WorkflowProtectedArtifactStatusAttestationRequest
    ) -> WorkflowProtectedArtifactStatusAttestation:
        assert self.kind is WorkflowProtectedArtifactKind.ENDPOINT
        return self._attest(request)

    async def attest_credential_artifact_status(
        self, request: WorkflowProtectedArtifactStatusAttestationRequest
    ) -> WorkflowProtectedArtifactStatusAttestation:
        assert self.kind is WorkflowProtectedArtifactKind.CREDENTIAL
        return self._attest(request)

    def _attest(
        self, request: WorkflowProtectedArtifactStatusAttestationRequest
    ) -> WorkflowProtectedArtifactStatusAttestation:
        self.calls.append(f"attest-{self.kind.value}")
        self.requests.append(request)
        return make_attestation(
            request,
            valid_until=self.valid_until,
            tamper_binding=self.tamper_binding,
            invalid_signature=self.invalid_signature,
        )


class HmacStatusSignatureVerifier:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    def verify_status_attestation(
        self, attestation: WorkflowProtectedArtifactStatusAttestation
    ) -> bool:
        self.calls.append(f"verify-{attestation.artifact_kind.value}")
        if (
            attestation.signing_key_id != "signing-key.workflow-protected-store-status.imp-209"
            or attestation.signature_algorithm != "hmac-sha256"
        ):
            return False
        expected = hmac.new(
            STATUS_SIGNING_KEY,
            canonical_json_bytes(attestation.signature_payload()),
            sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, attestation.integrity_signature)


class FakeAuthorizationRepository:
    def __init__(
        self,
        binding: WorkflowEventPhysicalTransportTargetContextBinding,
        calls: list[str],
        *,
        durable: bool = True,
    ) -> None:
        self.binding = binding
        self.calls = calls
        self._durable = durable
        self.leases: list[WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease] = []
        self.requests: dict[
            tuple[WorkflowScope, str, str],
            tuple[str, WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease],
        ] = {}
        self.next_status: WorkflowTargetContextAccessAuthorizationLeaseStatus | None = None

    @property
    def durable(self) -> bool:
        return self._durable

    async def get_authoritative_time(self) -> datetime:
        self.calls.append("authoritative-time")
        return DB_NOW

    async def get_target_context_binding_by_id(
        self, *, binding_id: str
    ) -> WorkflowEventPhysicalTransportTargetContextBinding | None:
        self.calls.append("load-binding")
        return self.binding if binding_id == self.binding.binding_id else None

    async def authorize_target_context_access(
        self, request: WorkflowTargetContextAccessAuthorizationLeaseRequest
    ) -> WorkflowTargetContextAccessAuthorizationLeaseResult:
        self.calls.append("authorize-repository")
        validate_workflow_target_context_access_authorization_request(request)
        if self.next_status is not None:
            return WorkflowTargetContextAccessAuthorizationLeaseResult(self.next_status, None)
        key = (request.scope, request.accessor_subject_id, request.idempotency_key)
        prior = self.requests.get(key)
        if prior is not None:
            fingerprint, lease = prior
            return WorkflowTargetContextAccessAuthorizationLeaseResult(
                (
                    WorkflowTargetContextAccessAuthorizationLeaseStatus.REPLAY
                    if fingerprint == request.request_fingerprint
                    else WorkflowTargetContextAccessAuthorizationLeaseStatus.IDEMPOTENCY_CONFLICT
                ),
                lease if fingerprint == request.request_fingerprint else None,
            )
        if self.leases:
            return WorkflowTargetContextAccessAuthorizationLeaseResult(
                WorkflowTargetContextAccessAuthorizationLeaseStatus.ALREADY_AUTHORIZED,
                None,
            )
        try:
            await request.required_precommit_audit()
        except Exception:
            return WorkflowTargetContextAccessAuthorizationLeaseResult(
                WorkflowTargetContextAccessAuthorizationLeaseStatus.PRECOMMIT_AUDIT_FAILED,
                None,
            )
        self.leases.append(request.candidate)
        self.requests[key] = (request.request_fingerprint, request.candidate)
        return WorkflowTargetContextAccessAuthorizationLeaseResult(
            WorkflowTargetContextAccessAuthorizationLeaseStatus.AUTHORIZED,
            request.candidate,
        )

    async def list_target_context_access_authorization_leases(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease, ...]:
        return tuple(lease for lease in self.leases if lease.scope == scope)[:limit]


def accessor_context(
    *,
    subject_id: str = WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_SUBJECT,
    actor_type: str = "service",
    authentication_method: str = "workload_token",
    audience: str = WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_AUDIENCE,
) -> WorkflowPhysicalTransportTargetContextAccessorContext:
    return WorkflowPhysicalTransportTargetContextAccessorContext(
        subject_id=subject_id,
        actor_type=actor_type,
        authentication_method=authentication_method,
        credential_audience=audience,
        scope=SCOPE,
        correlation_id="correlation.imp-209",
        decision_id="decision.imp-209",
        requested_at=NOW,
    )


def service_fixture(
    *,
    binding: WorkflowEventPhysicalTransportTargetContextBinding | None = None,
    durable: bool = True,
    endpoint_valid_until: datetime = NOW + timedelta(seconds=20),
    credential_valid_until: datetime = NOW + timedelta(seconds=20),
    tamper_endpoint_binding: bool = False,
    invalid_endpoint_signature: bool = False,
    audit: CollectingAuditSink | None = None,
) -> tuple[
    WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseService,
    FakeAuthorizationRepository,
    FakeStatusAttestor,
    FakeStatusAttestor,
    HmacStatusSignatureVerifier,
    CollectingAuditSink,
    list[str],
]:
    calls: list[str] = []
    repository = FakeAuthorizationRepository(binding or make_binding(), calls, durable=durable)
    endpoint = FakeStatusAttestor(
        kind=WorkflowProtectedArtifactKind.ENDPOINT,
        calls=calls,
        valid_until=endpoint_valid_until,
        tamper_binding=tamper_endpoint_binding,
        invalid_signature=invalid_endpoint_signature,
    )
    credential = FakeStatusAttestor(
        kind=WorkflowProtectedArtifactKind.CREDENTIAL,
        calls=calls,
        valid_until=credential_valid_until,
    )
    selected_audit = audit or CollectingAuditSink()
    verifier = HmacStatusSignatureVerifier(calls)
    service = WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseService(
        authorization_repository=repository,
        endpoint_status_attestor=endpoint,
        credential_status_attestor=credential,
        status_signature_verifier=verifier,
        audit_sink=selected_audit,
    )
    return service, repository, endpoint, credential, verifier, selected_audit, calls


async def authorize(
    service: WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseService,
    *,
    binding_id: str = BINDING_ID,
    binding_digest: str | None = None,
    idempotency_key: str = "target-context-access-0001",
    context: WorkflowPhysicalTransportTargetContextAccessorContext | None = None,
) -> WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLease:
    policy = service.policy
    return await service.authorize(
        target_context_binding_id=binding_id,
        target_context_binding_digest=binding_digest or make_binding().canonical_digest,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        idempotency_key=idempotency_key,
        context=context or accessor_context(),
    )


def test_domain_policy_attestation_and_authority_are_exact_and_canonical() -> None:
    policy = (
        code_owned_workflow_event_physical_transport_target_context_access_authorization_policy()
    )
    assert policy.validity_window_seconds == 5
    assert policy.single_use_required is True
    assert policy.renewable_allowed is False
    assert policy.transferable_allowed is False
    assert policy.required_endpoint_status_attestor_id == (
        "attestor.workflow-protected-endpoint-store-status"
    )
    assert policy.required_credential_status_attestor_id == (
        "attestor.workflow-protected-credential-store-status"
    )
    with pytest.raises(ValueError, match="code-owned status attestors"):
        replace(
            policy,
            required_endpoint_status_attestor_id="attestor.untrusted",
        )

    binding = make_binding()
    request = WorkflowProtectedArtifactStatusAttestationRequest(
        artifact_kind=WorkflowProtectedArtifactKind.ENDPOINT,
        materialization_id=binding.endpoint_materialization_id,
        materialization_digest=binding.endpoint_materialization_digest,
        target_context_binding_id=binding.binding_id,
        target_context_binding_digest=binding.canonical_digest,
        target_context_commitment=binding.target_context_commitment,
        scope=SCOPE,
        accessor_subject_id=WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_ACCESSOR_SUBJECT,
        request_nonce_digest="b" * 64,
        requested_at=NOW,
    )
    attestation = make_attestation(request)
    assert attestation.digest_payload()["target_context_binding_id"] == binding.binding_id
    assert attestation.digest_payload()["target_context_binding_digest"] == binding.canonical_digest
    assert (
        attestation.digest_payload()["target_context_commitment"]
        == binding.target_context_commitment
    )
    with pytest.raises(ValueError, match="canonical digest mismatch"):
        replace(attestation, target_context_commitment="c" * 64)

    authority = WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseAuthority()
    assert len(authority.canonical_value()) == 17
    assert [name for name, value in authority.canonical_value().items() if value] == [
        "protected_artifact_access_authorized"
    ]


@pytest.mark.asyncio
async def test_service_attests_outside_repository_authorization_and_issues_exact_lease() -> None:
    service, repository, endpoint, credential, _, audit, calls = service_fixture()

    lease = await authorize(service)

    assert calls == [
        "load-binding",
        "attest-endpoint",
        "attest-credential",
        "authoritative-time",
        "verify-endpoint",
        "verify-credential",
        "authorize-repository",
        "verify-endpoint",
        "verify-credential",
    ]
    assert endpoint.requests[0].request_nonce_digest == credential.requests[0].request_nonce_digest
    assert lease.valid_until - lease.issued_at == timedelta(seconds=5)
    assert lease.single_use is True and lease.renewable is False and lease.transferable is False
    assert lease.authority.protected_artifact_access_authorized is True
    assert lease.effective_state(evaluated_at=lease.issued_at) is (
        WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseEffectiveState.ACTIVE
    )
    assert await service.list_leases(scope=SCOPE) == (lease,)
    assert len(repository.leases) == 1
    assert [record.event_type.rsplit(".", 1)[-1] for record in audit.records] == [
        "intent",
        "commit-authorization",
        "completion",
    ]


@pytest.mark.asyncio
async def test_exact_replay_returns_same_lease_with_fresh_status_attestations() -> None:
    service, repository, endpoint, credential, _, audit, _ = service_fixture()
    first = await authorize(service)

    replay = await authorize(service)

    assert replay == first
    assert len(repository.leases) == 1
    assert len(endpoint.requests) == len(credential.requests) == 2
    assert endpoint.requests[0].request_nonce_digest != endpoint.requests[1].request_nonce_digest
    assert audit.records[-1].event_type.endswith(".replay")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "context",
    [
        accessor_context(subject_id="service.other"),
        accessor_context(actor_type="human"),
        accessor_context(authentication_method="session_cookie"),
        accessor_context(audience="audience.other"),
    ],
)
async def test_only_exact_accessor_workload_is_accepted(
    context: WorkflowPhysicalTransportTargetContextAccessorContext,
) -> None:
    service, _, endpoint, credential, _, _, calls = service_fixture()

    with pytest.raises(WorkflowTargetContextAccessAuthorizationLeaseError) as denied:
        await authorize(service, context=context)

    assert denied.value.code.endswith("accessor_identity_required")
    assert calls == []
    assert not endpoint.requests and not credential.requests


@pytest.mark.asyncio
async def test_tampered_binding_attestation_and_short_windows_fail_closed() -> None:
    service, repository, _, _, _, _, _ = service_fixture(tamper_endpoint_binding=True)
    with pytest.raises(WorkflowTargetContextAccessAuthorizationLeaseError) as tampered:
        await authorize(service)
    assert tampered.value.detail == "The target context access authorization request was denied."
    assert not repository.leases

    service, repository, _, _, _, _, calls = service_fixture(invalid_endpoint_signature=True)
    with pytest.raises(WorkflowTargetContextAccessAuthorizationLeaseError) as unsigned:
        await authorize(service)
    assert unsigned.value.code.endswith("evidence_conflict")
    assert calls.count("verify-endpoint") == 1
    assert "authorize-repository" not in calls
    assert not repository.leases

    service, repository, _, _, _, _, _ = service_fixture(
        endpoint_valid_until=DB_NOW + timedelta(seconds=4, microseconds=999999)
    )
    with pytest.raises(WorkflowTargetContextAccessAuthorizationLeaseError) as short_attestation:
        await authorize(service)
    assert short_attestation.value.code.endswith("evidence_conflict")
    assert not repository.leases

    service, repository, _, _, _, _, _ = service_fixture(
        binding=make_binding(joint_usable_until=DB_NOW + timedelta(seconds=4))
    )
    with pytest.raises(WorkflowTargetContextAccessAuthorizationLeaseError) as short_binding:
        await authorize(service, binding_digest=repository.binding.canonical_digest)
    assert short_binding.value.detail == short_attestation.value.detail
    assert not repository.leases


@pytest.mark.asyncio
async def test_repository_conflicts_are_non_oracle_and_audited() -> None:
    details: set[str] = set()
    for status in (
        WorkflowTargetContextAccessAuthorizationLeaseStatus.IDEMPOTENCY_CONFLICT,
        WorkflowTargetContextAccessAuthorizationLeaseStatus.EVIDENCE_CONFLICT,
        WorkflowTargetContextAccessAuthorizationLeaseStatus.ALREADY_AUTHORIZED,
    ):
        service, repository, _, _, _, audit, _ = service_fixture()
        repository.next_status = status
        with pytest.raises(WorkflowTargetContextAccessAuthorizationLeaseError) as denied:
            await authorize(service)
        details.add(denied.value.detail)
        assert audit.records[-1].event_type.endswith(".denied")
    assert details == {"The target context access authorization request was denied."}


@pytest.mark.asyncio
async def test_precommit_and_completion_audit_failures_preserve_atomic_boundary() -> None:
    service, repository, _, _, _, _, _ = service_fixture(
        audit=CollectingAuditSink(fail_kind="commit-authorization")
    )
    with pytest.raises(WorkflowTargetContextAccessAuthorizationLeaseError) as precommit:
        await authorize(service)
    assert precommit.value.code.endswith("precommit_audit_failed")
    assert not repository.leases

    service, repository, _, _, _, audit, _ = service_fixture(
        audit=CollectingAuditSink(fail_kind="completion")
    )
    with pytest.raises(WorkflowTargetContextAccessAuthorizationLeaseError) as completion:
        await authorize(service)
    assert completion.value.code.endswith("completion_audit_outcome_uncertain")
    assert len(repository.leases) == 1

    audit.fail_kind = None
    assert await authorize(service) == repository.leases[0]


@pytest.mark.asyncio
async def test_non_durable_repository_fails_before_evidence_calls() -> None:
    service, repository, endpoint, credential, _, _, calls = service_fixture(durable=False)
    with pytest.raises(WorkflowTargetContextAccessAuthorizationLeaseError) as denied:
        await authorize(service)
    assert denied.value.code.endswith("durable_repository_required")
    assert not repository.leases and not endpoint.requests and not credential.requests
    assert calls == []


def test_external_contract_excludes_policy_digest_and_sensitive_or_operational_inputs() -> None:
    assert set(
        inspect.signature(
            WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseService.authorize
        ).parameters
    ) == {
        "self",
        "target_context_binding_id",
        "target_context_binding_digest",
        "policy_id",
        "policy_version",
        "idempotency_key",
        "context",
    }
    forbidden = {
        "artifact",
        "credential",
        "endpoint",
        "locator",
        "network",
        "provider",
        "publication",
        "runtime",
        "secret",
        "token",
    }
    attestation_fields = {
        field.name for field in fields(WorkflowProtectedArtifactStatusAttestation)
    }
    external_fields = set(
        inspect.signature(
            WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseService.authorize
        ).parameters
    )
    assert not any(
        forbidden_name in field_name
        for forbidden_name in forbidden
        for field_name in attestation_fields
        if forbidden_name not in {"artifact", "credential", "endpoint"}
    )
    assert "policy_digest" not in external_fields
    repository_members = {
        name
        for name, _ in inspect.getmembers(
            WorkflowTargetContextAccessAuthorizationLeaseRepository,
            predicate=inspect.isfunction,
        )
        if not name.startswith("_")
    }
    assert repository_members == {
        "authorize_target_context_access",
        "get_authoritative_time",
        "get_target_context_binding_by_id",
        "list_target_context_access_authorization_leases",
    }
