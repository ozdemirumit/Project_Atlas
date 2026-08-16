from __future__ import annotations

import inspect
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.workflows.application import (
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedResidentContextAccessAuthorizationError,
    WorkflowProtectedResidentContextAccessAuthorizationPreflightRequest,
    WorkflowProtectedResidentContextAccessAuthorizationPreflightResult,
    WorkflowProtectedResidentContextAccessAuthorizationPreflightStatus,
    WorkflowProtectedResidentContextAccessAuthorizationService,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
)
from atlas.modules.workflows.domain import WorkflowScope, canonical_digest

NOW = datetime(2026, 8, 16, 22, 0, tzinfo=UTC)
SCOPE = WorkflowScope("org-atlas", "environment-lab", "site-istanbul")


class _Authority:
    def canonical_value(self) -> dict[str, bool]:
        return {
            "protected_resident_context_access_authority_granted": True,
            "target_context_capsule_handoff_authority_granted": False,
            "target_context_capsule_opening_authority_granted": False,
            "protected_artifact_access_authority_granted": False,
            "runtime_handle_creation_authority_granted": False,
            "network_access_authority_granted": False,
            "execution_authority_granted": False,
            "infrastructure_mutation_authority_granted": False,
        }


@dataclass(frozen=True)
class _Lease:
    authorization_lease_id: str
    scope: WorkflowScope
    policy_digest: str
    issued_at: datetime
    valid_until: datetime
    effective_until: datetime
    single_use: bool = True
    renewable: bool = False
    transferable: bool = False
    lease_is_bearer_capability: bool = False
    protected_resident_context_access_authority_granted: bool = True
    protected_resident_context_usable_until: datetime = NOW + timedelta(seconds=10)
    lifecycle_attestation_valid_until: datetime = NOW + timedelta(seconds=2)
    authority: _Authority = field(default_factory=_Authority)
    canonical_digest: str = ""

    def digest_payload(self) -> dict[str, object]:
        return {
            "authorization_lease_id": self.authorization_lease_id,
            "scope": self.scope.canonical_value(),
            "policy_digest": self.policy_digest,
            "issued_at": self.issued_at.isoformat(),
            "valid_until": self.valid_until.isoformat(),
            "effective_until": self.effective_until.isoformat(),
            "single_use": self.single_use,
            "renewable": self.renewable,
            "transferable": self.transferable,
            "lease_is_bearer_capability": self.lease_is_bearer_capability,
            "protected_resident_context_access_authority_granted": (
                self.protected_resident_context_access_authority_granted
            ),
            "protected_resident_context_usable_until": (
                self.protected_resident_context_usable_until.isoformat()
            ),
            "lifecycle_attestation_valid_until": (
                self.lifecycle_attestation_valid_until.isoformat()
            ),
            "authority": self.authority.canonical_value(),
        }

    def effective_state(self, *, evaluated_at: datetime) -> Any:
        return type(
            "EffectiveState",
            (),
            {"value": "active" if self.issued_at <= evaluated_at < self.valid_until else "expired"},
        )()

    def __getattr__(self, name: str) -> bool:
        if name.endswith("_authorized"):
            return False
        raise AttributeError(name)


class _Policy:
    policy_id = "policy.workflow-protected-resident-context-access-authorization"
    policy_version = "1.0"
    canonical_digest = "a" * 64
    purpose_id = "purpose.workflow-protected-resident-context-access-evaluation"
    required_attestor_id = "attestor.workflow-protected-resident-context-lifecycle"
    required_attestor_version = "1.0"
    verification_signing_key_id = "key.workflow-protected-resident-context-lifecycle.v1"


class _Repository:
    durable = True

    def __init__(
        self,
        *,
        status: WorkflowProtectedResidentContextAccessAuthorizationPreflightStatus,
        lease: _Lease | None = None,
    ) -> None:
        self.status = status
        self.lease = lease
        self.preflights: list[
            WorkflowProtectedResidentContextAccessAuthorizationPreflightRequest
        ] = []
        self.source_calls = 0
        self.authorization_calls = 0

    async def preflight_protected_resident_context_access_authorization(
        self, request: WorkflowProtectedResidentContextAccessAuthorizationPreflightRequest
    ) -> WorkflowProtectedResidentContextAccessAuthorizationPreflightResult:
        self.preflights.append(request)
        return WorkflowProtectedResidentContextAccessAuthorizationPreflightResult(
            status=self.status,
            lease=cast(Any, self.lease),
            evaluated_at=NOW + timedelta(milliseconds=100),
        )

    async def get_authoritative_time(self) -> datetime:
        raise AssertionError("replay must not request another database time")

    async def get_protected_resident_context_access_authorization_source(
        self, *, opening_id: str
    ) -> None:
        del opening_id
        self.source_calls += 1
        raise AssertionError("replay must not load source lineage")

    async def authorize_protected_resident_context_access(self, request: object) -> None:
        del request
        self.authorization_calls += 1
        raise AssertionError("replay must not attempt another claim")


class _Attestor:
    available = False

    def __init__(self) -> None:
        self.calls = 0

    async def attest_resident_context_lifecycle(self, request: object) -> None:
        del request
        self.calls += 1
        raise AssertionError("durable replay must bypass attestor I/O")


class _Verifier:
    def verify_lifecycle_attestation(self, attestation: object) -> bool:
        del attestation
        raise AssertionError("durable replay must bypass lifecycle verification")

    def verify_opening_receipt(self, receipt: object) -> bool:
        del receipt
        raise AssertionError("durable replay must bypass receipt verification")


class _FailingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, record: AuditRecord) -> None:
        self.records.append(record)
        raise RuntimeError("syslog unavailable")


def _context() -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext:
    return WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
        subject_id=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
        actor_type="service",
        authentication_method="workload_token",
        credential_audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
        scope=SCOPE,
        correlation_id="correlation.imp-216",
        decision_id="decision.imp-216",
        requested_at=NOW,
    )


def _lease() -> _Lease:
    provisional = _Lease(
        authorization_lease_id="resident-context-access-authorization-lease.imp-216",
        scope=SCOPE,
        policy_digest=_Policy.canonical_digest,
        issued_at=NOW,
        valid_until=NOW + timedelta(seconds=1),
        effective_until=NOW + timedelta(seconds=1),
    )
    return replace(provisional, canonical_digest=canonical_digest(provisional.digest_payload()))


def _service(
    repository: _Repository, attestor: _Attestor, audit_sink: _FailingAuditSink
) -> WorkflowProtectedResidentContextAccessAuthorizationService:
    verifier = _Verifier()
    return WorkflowProtectedResidentContextAccessAuthorizationService(
        authorization_repository=cast(Any, repository),
        lifecycle_attestor=cast(Any, attestor),
        lifecycle_signature_verifier=cast(Any, verifier),
        opening_receipt_signature_verifier=cast(Any, verifier),
        audit_sink=audit_sink,
        policy=cast(Any, _Policy()),
    )


@pytest.mark.asyncio
async def test_durable_exact_replay_precedes_attestor_io_and_audit_is_best_effort() -> None:
    repository = _Repository(
        status=WorkflowProtectedResidentContextAccessAuthorizationPreflightStatus.REPLAY,
        lease=_lease(),
    )
    attestor = _Attestor()
    audit_sink = _FailingAuditSink()

    lease = await _service(repository, attestor, audit_sink).authorize(
        opening_result_id="workflow-target-context-capsule-opening.imp-216",
        opening_result_digest="b" * 64,
        policy_id=_Policy.policy_id,
        policy_version=_Policy.policy_version,
        idempotency_key="imp-216-exact-replay",
        context=_context(),
    )

    assert lease is cast(Any, repository.lease)
    assert len(repository.preflights) == 1
    assert repository.source_calls == 0
    assert repository.authorization_calls == 0
    assert attestor.calls == 0
    assert len(audit_sink.records) == 1
    assert audit_sink.records[0].idempotency_key is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    (
        WorkflowProtectedResidentContextAccessAuthorizationPreflightStatus.IDEMPOTENCY_CONFLICT,
        WorkflowProtectedResidentContextAccessAuthorizationPreflightStatus.EVIDENCE_CONFLICT,
        WorkflowProtectedResidentContextAccessAuthorizationPreflightStatus.ALREADY_AUTHORIZED,
    ),
)
async def test_preflight_conflict_fails_before_attestor_and_source_io(
    status: WorkflowProtectedResidentContextAccessAuthorizationPreflightStatus,
) -> None:
    repository = _Repository(status=status)
    attestor = _Attestor()

    with pytest.raises(WorkflowProtectedResidentContextAccessAuthorizationError):
        await _service(repository, attestor, _FailingAuditSink()).authorize(
            opening_result_id="workflow-target-context-capsule-opening.imp-216",
            opening_result_digest="b" * 64,
            policy_id=_Policy.policy_id,
            policy_version=_Policy.policy_version,
            idempotency_key="imp-216-conflict",
            context=_context(),
        )

    assert repository.source_calls == 0
    assert repository.authorization_calls == 0
    assert attestor.calls == 0


@pytest.mark.asyncio
async def test_non_consumer_identity_fails_before_durable_preflight() -> None:
    repository = _Repository(
        status=WorkflowProtectedResidentContextAccessAuthorizationPreflightStatus.REPLAY,
        lease=_lease(),
    )
    context = replace(_context(), subject_id="user.admin", actor_type="human")

    with pytest.raises(WorkflowProtectedResidentContextAccessAuthorizationError) as caught:
        await _service(repository, _Attestor(), _FailingAuditSink()).authorize(
            opening_result_id="workflow-target-context-capsule-opening.imp-216",
            opening_result_digest="b" * 64,
            policy_id=_Policy.policy_id,
            policy_version=_Policy.policy_version,
            idempotency_key="imp-216-human",
            context=context,
        )

    assert caught.value.code.endswith("consumer_identity_required")
    assert repository.preflights == []


def test_authorize_caller_surface_contains_only_adr_166_fields_and_context() -> None:
    parameters = set(
        inspect.signature(
            WorkflowProtectedResidentContextAccessAuthorizationService.authorize
        ).parameters
    )
    assert parameters == {
        "self",
        "opening_result_id",
        "opening_result_digest",
        "policy_id",
        "policy_version",
        "idempotency_key",
        "context",
    }
    assert not parameters.intersection(
        {
            "protected_resident_context_id",
            "runtime_handle",
            "endpoint",
            "credential",
            "network",
            "execution",
            "infrastructure_mutation",
        }
    )
