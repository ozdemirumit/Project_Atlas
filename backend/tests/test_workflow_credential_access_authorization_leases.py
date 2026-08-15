from __future__ import annotations

import inspect
from dataclasses import fields, replace
from datetime import datetime, timedelta
from typing import Any, cast

import pytest
from test_workflow_transport_credential_assignment_freshness_admissions import (
    NOW,
    CollectingAuditSink,
    _admit,
    _fixture,
)

from atlas.modules.workflows.application import (
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_SUBJECT,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseService,
    WorkflowPhysicalTransportCredentialAccessorContext,
    WorkflowTransportCredentialAccessAuthorizationLeaseError,
    WorkflowTransportCredentialAccessAuthorizationLeaseIdempotencyRecord,
    WorkflowTransportCredentialAccessAuthorizationLeaseRequest,
    WorkflowTransportCredentialAccessAuthorizationLeaseResult,
    WorkflowTransportCredentialAccessAuthorizationLeaseStatus,
    validate_workflow_transport_credential_access_authorization_request,
)
from atlas.modules.workflows.domain import (
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseAuthority,
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseEffectiveState,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_credential_access_authorization_policy,
)

LEASE_NOW = NOW + timedelta(seconds=1)


class InMemoryCredentialAccessAuthorizationRepository:
    def __init__(
        self,
        *,
        source: Any,
        admission: Any,
        binding: Any,
        snapshot: Any,
        head: Any,
    ) -> None:
        self.source = source
        self.admission = admission
        self.binding = binding
        self.snapshot = snapshot
        self.head = head
        self.now = LEASE_NOW
        self.calls = 0
        self.leases: dict[
            str, WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease
        ] = {}
        self.claims: dict[
            tuple[WorkflowScope, str, str],
            WorkflowTransportCredentialAccessAuthorizationLeaseIdempotencyRecord,
        ] = {}

    @property
    def durable(self) -> bool:
        return True

    async def get_authoritative_time(self) -> datetime:
        return self.now

    async def get_credential_assignment_freshness_admission_by_id(
        self, *, freshness_admission_id: str
    ) -> Any:
        return (
            self.admission
            if self.admission.freshness_admission_id == freshness_admission_id
            else None
        )

    async def get_credential_assignment_binding_by_id(self, *, binding_id: str) -> Any:
        return self.binding if self.binding.binding_id == binding_id else None

    async def get_credential_assignment_snapshot_by_id(self, *, snapshot_id: str) -> Any:
        return self.snapshot if self.snapshot.snapshot_id == snapshot_id else None

    async def get_current_credential_assignment_head(self, *, assignment_id: str) -> Any:
        return self.head if self.head.assignment_id == assignment_id else None

    async def list_credential_access_authorization_leases(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease, ...]:
        return tuple(value for value in self.leases.values() if value.scope == scope)[:limit]

    async def authorize_credential_access(
        self, request: WorkflowTransportCredentialAccessAuthorizationLeaseRequest
    ) -> WorkflowTransportCredentialAccessAuthorizationLeaseResult:
        self.calls += 1
        validate_workflow_transport_credential_access_authorization_request(request)
        key = (request.scope, request.accessor_subject_id, request.idempotency_key)
        prior = self.claims.get(key)
        if prior is not None:
            if prior.request_fingerprint != request.request_fingerprint:
                return WorkflowTransportCredentialAccessAuthorizationLeaseResult(
                    WorkflowTransportCredentialAccessAuthorizationLeaseStatus.IDEMPOTENCY_CONFLICT,
                    prior.lease,
                )
            if not self._source_is_current(prior.lease):
                return WorkflowTransportCredentialAccessAuthorizationLeaseResult(
                    WorkflowTransportCredentialAccessAuthorizationLeaseStatus.EVIDENCE_CONFLICT,
                    None,
                )
            return WorkflowTransportCredentialAccessAuthorizationLeaseResult(
                WorkflowTransportCredentialAccessAuthorizationLeaseStatus.REPLAY,
                prior.lease,
            )
        current = self.leases.get(request.expected_freshness_admission_id)
        if current is not None:
            return WorkflowTransportCredentialAccessAuthorizationLeaseResult(
                WorkflowTransportCredentialAccessAuthorizationLeaseStatus.ALREADY_AUTHORIZED,
                current,
            )
        expected = (
            request.expected_freshness_admission_id,
            request.expected_freshness_admission_digest,
            request.expected_freshness_admission_valid_until,
            request.expected_credential_assignment_binding_id,
            request.expected_credential_assignment_binding_digest,
            request.expected_credential_assignment_snapshot_id,
            request.expected_credential_assignment_snapshot_digest,
            request.expected_assignment_id,
            request.expected_assignment_revision,
            request.expected_source_assignment_digest,
            request.expected_credential_generation,
            request.expected_rotation_epoch,
            request.expected_assignment_activated_at,
            request.expected_assignment_expires_at,
            request.expected_assignment_active,
            request.expected_assignment_revoked,
        )
        actual = (
            self.admission.freshness_admission_id,
            self.admission.canonical_digest,
            self.admission.valid_until,
            self.binding.binding_id,
            self.binding.canonical_digest,
            self.snapshot.snapshot_id,
            self.snapshot.canonical_digest,
            self.head.assignment_id,
            self.head.assignment_revision,
            self.head.canonical_digest,
            self.head.credential_generation,
            self.head.rotation_epoch,
            self.head.activated_at,
            self.head.expires_at,
            self.head.active,
            self.head.revoked,
        )
        if expected != actual or not self._source_is_current(request.candidate):
            return WorkflowTransportCredentialAccessAuthorizationLeaseResult(
                WorkflowTransportCredentialAccessAuthorizationLeaseStatus.EVIDENCE_CONFLICT,
                None,
            )
        try:
            await request.required_precommit_audit()
        except Exception:
            return WorkflowTransportCredentialAccessAuthorizationLeaseResult(
                WorkflowTransportCredentialAccessAuthorizationLeaseStatus.PRECOMMIT_AUDIT_FAILED,
                None,
            )
        if not self._source_is_current(request.candidate):
            return WorkflowTransportCredentialAccessAuthorizationLeaseResult(
                WorkflowTransportCredentialAccessAuthorizationLeaseStatus.EVIDENCE_CONFLICT,
                None,
            )
        self.leases[request.expected_freshness_admission_id] = request.candidate
        self.claims[key] = WorkflowTransportCredentialAccessAuthorizationLeaseIdempotencyRecord(
            request.request_fingerprint, request.candidate
        )
        return WorkflowTransportCredentialAccessAuthorizationLeaseResult(
            WorkflowTransportCredentialAccessAuthorizationLeaseStatus.AUTHORIZED,
            request.candidate,
        )

    def _source_is_current(
        self, lease: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease
    ) -> bool:
        return (
            self.now < lease.valid_until
            and self.now < self.admission.valid_until
            and self.now < self.head.expires_at
            and self.head.active is True
            and self.head.revoked is False
            and self.head.assignment_revision == lease.assignment_revision
            and self.head.canonical_digest == lease.source_assignment_digest
            and self.head.credential_generation == lease.credential_generation
            and self.head.rotation_epoch == lease.rotation_epoch
        )


def accessor_context(
    *,
    scope: WorkflowScope,
    subject_id: str = WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_SUBJECT,
    actor_type: str = "service",
    authentication_method: str = "workload_token",
    audience: str = WORKFLOW_PHYSICAL_TRANSPORT_CREDENTIAL_ACCESSOR_AUDIENCE,
) -> WorkflowPhysicalTransportCredentialAccessorContext:
    return WorkflowPhysicalTransportCredentialAccessorContext(
        subject_id=subject_id,
        actor_type=actor_type,
        authentication_method=authentication_method,
        credential_audience=audience,
        scope=scope,
        correlation_id="correlation.credential-access-authorization.0001",
        decision_id="decision.credential-access-authorization.0001",
        requested_at=LEASE_NOW,
    )


async def service_fixture(
    *, audit: CollectingAuditSink | None = None
) -> tuple[
    WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseService,
    InMemoryCredentialAccessAuthorizationRepository,
    CollectingAuditSink,
]:
    freshness_service, source, _, binding, snapshot, head = _fixture()
    admission = await _admit(freshness_service, binding=binding)
    sink = audit or CollectingAuditSink()
    repository = InMemoryCredentialAccessAuthorizationRepository(
        source=source,
        admission=admission,
        binding=binding,
        snapshot=snapshot,
        head=head,
    )
    return (
        WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseService(
            authorization_repository=cast(Any, repository), audit_sink=sink
        ),
        repository,
        sink,
    )


async def authorize(
    service: WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseService,
    repository: InMemoryCredentialAccessAuthorizationRepository,
    *,
    idempotency_key: str = "credential-access-authorization-0001",
    context: WorkflowPhysicalTransportCredentialAccessorContext | None = None,
    **changes: object,
) -> WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease:
    values: dict[str, object] = {
        "freshness_admission_id": repository.admission.freshness_admission_id,
        "freshness_admission_digest": repository.admission.canonical_digest,
        "policy_id": service.policy.policy_id,
        "policy_version": service.policy.policy_version,
        "idempotency_key": idempotency_key,
        "context": context or accessor_context(scope=repository.admission.scope),
    }
    values.update(changes)
    return await service.authorize(**cast(Any, values))


@pytest.mark.asyncio
async def test_authorizes_exact_chain_for_15_seconds_with_exactly_one_authority() -> None:
    service, repository, audit = await service_fixture()

    lease = await authorize(service, repository)

    assert service.durable is True
    assert lease.valid_until - lease.issued_at == timedelta(seconds=15)
    assert lease.valid_until <= repository.admission.valid_until
    assert lease.valid_until <= repository.head.expires_at
    authority = lease.authority.canonical_value()
    assert len(authority) == 17
    assert authority["credential_access_authorized"] is True
    assert all(
        value is False
        for name, value in authority.items()
        if name != "credential_access_authorized"
    )
    assert [record.event_type.rsplit(".", 1)[-1] for record in audit.records] == [
        "intent",
        "authorization",
        "created",
    ]


@pytest.mark.asyncio
async def test_exact_replay_always_reenters_repository_and_fails_after_expiry_or_head_drift() -> (
    None
):
    service, repository, _ = await service_fixture()
    first = await authorize(service, repository)
    replay = await authorize(service, repository)
    assert replay == first
    assert repository.calls == 2

    repository.now = first.valid_until
    with pytest.raises(WorkflowTransportCredentialAccessAuthorizationLeaseError) as expired:
        await authorize(service, repository)
    assert expired.value.code.endswith("_evidence_conflict")
    assert repository.calls == 3

    repository.now = first.issued_at + timedelta(seconds=1)
    repository.head = replace(
        repository.head,
        active=False,
        canonical_digest=canonical_digest(repository.head.digest_payload() | {"active": False}),
    )
    with pytest.raises(WorkflowTransportCredentialAccessAuthorizationLeaseError) as drift:
        await authorize(service, repository)
    assert drift.value.code.endswith("_evidence_conflict")


@pytest.mark.asyncio
async def test_full_window_single_lease_and_fixed_workload_identity_are_mandatory() -> None:
    service, repository, _ = await service_fixture()
    repository.now = repository.admission.valid_until - timedelta(seconds=14)
    with pytest.raises(WorkflowTransportCredentialAccessAuthorizationLeaseError) as short:
        await authorize(service, repository)
    assert short.value.code.endswith("_evidence_conflict")

    service, repository, _ = await service_fixture()
    for context in (
        accessor_context(scope=repository.admission.scope, subject_id="service.other"),
        accessor_context(scope=repository.admission.scope, actor_type="human"),
        accessor_context(scope=repository.admission.scope, authentication_method="password"),
        accessor_context(scope=repository.admission.scope, audience="audience.browser"),
    ):
        with pytest.raises(WorkflowTransportCredentialAccessAuthorizationLeaseError) as identity:
            await authorize(service, repository, context=context)
        assert identity.value.code.endswith("_accessor_identity_required")

    first = await authorize(service, repository)
    with pytest.raises(WorkflowTransportCredentialAccessAuthorizationLeaseError) as duplicate:
        await authorize(
            service,
            repository,
            idempotency_key="credential-access-authorization-0002",
        )
    assert duplicate.value.code.endswith("_already_authorized")
    assert tuple(repository.leases.values()) == (first,)


@pytest.mark.asyncio
async def test_historical_policy_replay_and_completion_audit_recovery() -> None:
    failing = CollectingAuditSink(fail_kind="created")
    service, repository, _ = await service_fixture(audit=failing)
    with pytest.raises(WorkflowTransportCredentialAccessAuthorizationLeaseError) as uncertain:
        await authorize(service, repository)
    assert uncertain.value.code.endswith("_completion_audit_outcome_uncertain")
    committed = next(iter(repository.leases.values()))

    current = service.policy

    class RotatedPolicy:
        policy_id = current.policy_id
        policy_version = current.policy_version
        validity_window_seconds = 15
        full_freshness_window_required = True
        accessor_subject_bound = True
        single_use_required = True

        def digest_payload(self) -> dict[str, object]:
            return {**current.digest_payload(), "code_owned_rotation": 2}

        canonical_digest = canonical_digest({**current.digest_payload(), "code_owned_rotation": 2})

    failing.fail_kind = None
    rotated = WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseService(
        authorization_repository=cast(Any, repository),
        audit_sink=failing,
        policy=cast(Any, RotatedPolicy()),
    )
    replay = await authorize(rotated, repository)
    assert replay == committed
    assert replay.policy_digest == current.canonical_digest
    assert replay.policy_digest != rotated.policy.canonical_digest
    assert repository.calls == 2


def test_domain_and_public_surface_reject_authority_and_secret_material_drift() -> None:
    policy = code_owned_workflow_event_physical_transport_credential_access_authorization_policy()
    assert policy.validity_window_seconds == 15
    assert policy.canonical_digest == canonical_digest(policy.digest_payload())
    with pytest.raises(ValueError, match="grant only credential access"):
        WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseAuthority(
            credential_access_authorized=False
        )
    with pytest.raises(ValueError, match="grant only credential access"):
        WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseAuthority(
            network_access_authorized=True
        )
    with pytest.raises(ValueError, match="grant only credential access"):
        WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseAuthority(
            route_selection_authorized=0  # type: ignore[arg-type]
        )

    forbidden = {
        "username",
        "password",
        "token",
        "private_key",
        "certificate",
        "secret",
        "vault_path",
        "credential_profile",
        "target_commitment",
        "broker",
        "endpoint",
        "hostname",
        "url",
        "ip_address",
        "port",
        "protected_artifact",
        "header",
        "command",
        "environment_variable",
        "provider_response",
    }
    model_fields = {
        field.name
        for field in fields(WorkflowEventPhysicalTransportCredentialAccessAuthorizationLease)
    }
    request_fields = {
        field.name for field in fields(WorkflowTransportCredentialAccessAuthorizationLeaseRequest)
    }
    assert forbidden.isdisjoint(model_fields)
    assert forbidden.isdisjoint(request_fields)
    assert set(
        inspect.signature(
            WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseService.authorize
        ).parameters
    ) == {
        "self",
        "freshness_admission_id",
        "freshness_admission_digest",
        "policy_id",
        "policy_version",
        "idempotency_key",
        "context",
    }


@pytest.mark.asyncio
async def test_effective_state_and_precommit_audit_failure_are_fail_closed() -> None:
    service, repository, _ = await service_fixture()
    lease = await authorize(service, repository)
    assert (
        lease.effective_state(evaluated_at=lease.valid_until - timedelta(microseconds=1))
        is WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseEffectiveState.ACTIVE
    )
    assert (
        lease.effective_state(evaluated_at=lease.valid_until)
        is WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseEffectiveState.EXPIRED
    )
    with pytest.raises(ValueError, match="exact 15-second window"):
        replace(lease, valid_until=lease.valid_until + timedelta(seconds=1))

    failing = CollectingAuditSink(fail_kind="authorization")
    service, repository, _ = await service_fixture(audit=failing)
    with pytest.raises(WorkflowTransportCredentialAccessAuthorizationLeaseError) as audit_error:
        await authorize(service, repository)
    assert audit_error.value.code.endswith("_audit_unavailable")
    assert repository.leases == {}
    assert repository.claims == {}
