from __future__ import annotations

import inspect
from dataclasses import fields
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, cast

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.workflows.application import (
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_AUDIENCE,
    WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_SUBJECT,
    WorkflowEventPhysicalTransportTargetContextBindingError,
    WorkflowEventPhysicalTransportTargetContextBindingRepository,
    WorkflowEventPhysicalTransportTargetContextBindingRequest,
    WorkflowEventPhysicalTransportTargetContextBindingResult,
    WorkflowEventPhysicalTransportTargetContextBindingService,
    WorkflowEventPhysicalTransportTargetContextBindingStatus,
    WorkflowPhysicalTransportTargetContextBinderContext,
)
from atlas.modules.workflows.domain import (
    WorkflowEventPhysicalTransportTargetContextBinding,
    WorkflowEventPhysicalTransportTargetContextBindingAuthority,
    WorkflowEventPhysicalTransportTargetContextBindingState,
    WorkflowScope,
    canonical_digest,
)

NOW = datetime(2026, 8, 15, 21, 0, tzinfo=UTC)
SCOPE = WorkflowScope("org-atlas", "environment-lab", "site-istanbul")
ENDPOINT_ID = "workflow-endpoint-materialization.imp-208"
ENDPOINT_DIGEST = "1" * 64
CREDENTIAL_ID = "workflow-credential-materialization.imp-208"
CREDENTIAL_DIGEST = "2" * 64


def _canonical_payload(values: dict[str, object]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for name, value in values.items():
        if isinstance(value, datetime):
            payload[name] = value.isoformat()
        elif isinstance(value, StrEnum):
            payload[name] = value.value
        elif isinstance(
            value,
            (WorkflowScope, WorkflowEventPhysicalTransportTargetContextBindingAuthority),
        ):
            payload[name] = value.canonical_value()
        else:
            payload[name] = value
    return payload


class CollectingAuditSink:
    def __init__(self, *, fail_kind: str | None = None, fail_all: bool = False) -> None:
        self.records: list[AuditRecord] = []
        self.fail_kind = fail_kind
        self.fail_all = fail_all

    async def record(self, event: AuditRecord) -> None:
        if self.fail_all or (
            self.fail_kind is not None and event.event_type.endswith(f".{self.fail_kind}")
        ):
            raise RuntimeError("audit unavailable")
        self.records.append(event)


class NonZeroAuthority:
    def canonical_value(self) -> dict[str, bool]:
        return {"network_access_authorized": True}


class FakeTargetContextBindingRepository:
    def __init__(self, *, durable: bool = True) -> None:
        self._durable = durable
        self.bindings: list[WorkflowEventPhysicalTransportTargetContextBinding] = []
        self.requests: dict[
            tuple[WorkflowScope, str, str],
            tuple[str, WorkflowEventPhysicalTransportTargetContextBinding],
        ] = {}
        self.calls: list[WorkflowEventPhysicalTransportTargetContextBindingRequest] = []
        self.tamper_authority = False

    @property
    def durable(self) -> bool:
        return self._durable

    async def bind_target_context(
        self,
        request: WorkflowEventPhysicalTransportTargetContextBindingRequest,
    ) -> WorkflowEventPhysicalTransportTargetContextBindingResult:
        self.calls.append(request)
        key = (request.scope, request.binder_subject_id, request.idempotency_key)
        prior = self.requests.get(key)
        if prior is not None:
            fingerprint, binding = prior
            status = (
                WorkflowEventPhysicalTransportTargetContextBindingStatus.REPLAY
                if fingerprint == request.request_fingerprint
                else WorkflowEventPhysicalTransportTargetContextBindingStatus.IDEMPOTENCY_CONFLICT
            )
            return WorkflowEventPhysicalTransportTargetContextBindingResult(
                status,
                binding if status.value == "replay" else None,
            )
        if any(
            binding.endpoint_materialization_id == request.expected_endpoint_materialization_id
            or binding.credential_materialization_id
            == request.expected_credential_materialization_id
            for binding in self.bindings
        ):
            return WorkflowEventPhysicalTransportTargetContextBindingResult(
                WorkflowEventPhysicalTransportTargetContextBindingStatus.ALREADY_BOUND,
                None,
            )
        try:
            await request.required_precommit_audit()
        except Exception:
            return WorkflowEventPhysicalTransportTargetContextBindingResult(
                WorkflowEventPhysicalTransportTargetContextBindingStatus.PRECOMMIT_AUDIT_FAILED,
                None,
            )
        binding = self._build_binding(request)
        if self.tamper_authority:
            object.__setattr__(binding, "authority", NonZeroAuthority())
            object.__setattr__(
                binding, "canonical_digest", canonical_digest(binding.digest_payload())
            )
        self.bindings.append(binding)
        self.requests[key] = (request.request_fingerprint, binding)
        return WorkflowEventPhysicalTransportTargetContextBindingResult(
            WorkflowEventPhysicalTransportTargetContextBindingStatus.BOUND,
            binding,
        )

    async def list_target_context_bindings(
        self,
        *,
        scope: WorkflowScope,
        limit: int = 256,
    ) -> tuple[WorkflowEventPhysicalTransportTargetContextBinding, ...]:
        return tuple(binding for binding in self.bindings if binding.scope == scope)[:limit]

    @staticmethod
    def _build_binding(
        request: WorkflowEventPhysicalTransportTargetContextBindingRequest,
    ) -> WorkflowEventPhysicalTransportTargetContextBinding:
        bound_at = request.requested_at + timedelta(seconds=1)
        values: dict[str, object] = {
            "binding_id": "workflow-physical-transport-target-context-binding.imp-208",
            "physical_transport_route_binding_id": "workflow-route-binding.imp-208",
            "physical_transport_route_binding_digest": "3" * 64,
            "transport_route_snapshot_id": "transport-route-snapshot.imp-208",
            "transport_route_snapshot_digest": "4" * 64,
            "endpoint_materialization_id": request.expected_endpoint_materialization_id,
            "endpoint_materialization_digest": request.expected_endpoint_materialization_digest,
            "physical_transport_credential_assignment_binding_id": (
                "workflow-credential-assignment-binding.imp-208"
            ),
            "physical_transport_credential_assignment_binding_digest": "5" * 64,
            "credential_assignment_snapshot_id": "credential-assignment-snapshot.imp-208",
            "credential_assignment_snapshot_digest": "6" * 64,
            "credential_materialization_id": request.expected_credential_materialization_id,
            "credential_materialization_digest": request.expected_credential_materialization_digest,
            "resolver_subject_id": "service.workflow-physical-transport-endpoint-resolver",
            "accessor_subject_id": "service.workflow-physical-transport-credential-accessor",
            "target_context_schema_id": ("schema.workflow-physical-transport-target-context"),
            "target_context_schema_version": "1.0",
            "target_context_commitment": "7" * 64,
            "scope": request.scope,
            "binder_subject_id": request.binder_subject_id,
            "bound_at": bound_at,
            "joint_usable_until": bound_at + timedelta(seconds=8),
            "policy_id": request.expected_policy_id,
            "policy_version": request.expected_policy_version,
            "policy_digest": request.expected_policy_digest,
            "state": WorkflowEventPhysicalTransportTargetContextBindingState.BOUND,
            "authority": WorkflowEventPhysicalTransportTargetContextBindingAuthority(),
        }
        return WorkflowEventPhysicalTransportTargetContextBinding(
            **cast(Any, values),
            canonical_digest=canonical_digest(_canonical_payload(values)),
        )


def binder_context(
    *,
    subject_id: str = WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_SUBJECT,
    actor_type: str = "service",
    authentication_method: str = "workload_token",
    audience: str = WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_AUDIENCE,
) -> WorkflowPhysicalTransportTargetContextBinderContext:
    return WorkflowPhysicalTransportTargetContextBinderContext(
        subject_id=subject_id,
        actor_type=actor_type,
        authentication_method=authentication_method,
        credential_audience=audience,
        scope=SCOPE,
        correlation_id="correlation.imp-208",
        decision_id="decision.imp-208",
        requested_at=NOW,
    )


def service_fixture(
    *,
    repository: FakeTargetContextBindingRepository | None = None,
    audit: CollectingAuditSink | None = None,
) -> tuple[
    WorkflowEventPhysicalTransportTargetContextBindingService,
    FakeTargetContextBindingRepository,
    CollectingAuditSink,
]:
    selected_repository = repository or FakeTargetContextBindingRepository()
    selected_audit = audit or CollectingAuditSink()
    return (
        WorkflowEventPhysicalTransportTargetContextBindingService(
            binding_repository=selected_repository,
            audit_sink=selected_audit,
        ),
        selected_repository,
        selected_audit,
    )


async def bind(
    service: WorkflowEventPhysicalTransportTargetContextBindingService,
    *,
    endpoint_id: str = ENDPOINT_ID,
    endpoint_digest: str = ENDPOINT_DIGEST,
    credential_id: str = CREDENTIAL_ID,
    credential_digest: str = CREDENTIAL_DIGEST,
    idempotency_key: str = "target-context-binding-0001",
    context: WorkflowPhysicalTransportTargetContextBinderContext | None = None,
) -> WorkflowEventPhysicalTransportTargetContextBinding:
    policy = service.policy
    return await service.bind(
        endpoint_materialization_id=endpoint_id,
        endpoint_materialization_digest=endpoint_digest,
        credential_materialization_id=credential_id,
        credential_materialization_digest=credential_digest,
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        policy_digest=policy.canonical_digest,
        idempotency_key=idempotency_key,
        context=context or binder_context(),
    )


@pytest.mark.asyncio
async def test_binding_contract_is_atomic_minimized_and_audited() -> None:
    service, repository, audit = service_fixture()

    binding = await bind(service)

    assert binding.endpoint_materialization_id == ENDPOINT_ID
    assert binding.credential_materialization_id == CREDENTIAL_ID
    assert binding.binder_subject_id == WORKFLOW_PHYSICAL_TRANSPORT_TARGET_CONTEXT_BINDER_SUBJECT
    assert not any(binding.authority.canonical_value().values())
    assert canonical_digest(binding.digest_payload()) == binding.canonical_digest
    assert [record.event_type.rsplit(".", 1)[-1] for record in audit.records] == [
        "intent",
        "commit-authorization",
        "completion",
    ]
    assert await repository.list_target_context_bindings(scope=SCOPE) == (binding,)
    request_fields = {field.name for field in fields(type(repository.calls[0]))}
    assert request_fields == {
        "expected_endpoint_materialization_id",
        "expected_endpoint_materialization_digest",
        "expected_credential_materialization_id",
        "expected_credential_materialization_digest",
        "expected_policy_id",
        "expected_policy_version",
        "expected_policy_digest",
        "scope",
        "binder_subject_id",
        "requested_at",
        "idempotency_key",
        "request_fingerprint",
        "required_precommit_audit",
    }


@pytest.mark.asyncio
async def test_exact_replay_returns_same_binding_without_second_commit() -> None:
    service, repository, audit = service_fixture()
    first = await bind(service)

    replay = await bind(service)

    assert replay == first
    assert len(repository.bindings) == 1
    assert audit.records[-1].event_type.endswith(".replay")


@pytest.mark.asyncio
async def test_changed_idempotency_and_alternate_pair_fail_closed() -> None:
    service, repository, _ = service_fixture()
    await bind(service)

    with pytest.raises(WorkflowEventPhysicalTransportTargetContextBindingError) as changed:
        await bind(service, credential_digest="8" * 64)
    with pytest.raises(WorkflowEventPhysicalTransportTargetContextBindingError) as alternate:
        await bind(
            service,
            credential_id="workflow-credential-materialization.alternate",
            credential_digest="9" * 64,
            idempotency_key="target-context-binding-0002",
        )

    assert changed.value.code.endswith("idempotency_conflict")
    assert alternate.value.code.endswith("already_bound")
    assert changed.value.detail == alternate.value.detail
    assert len(repository.bindings) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "context",
    [
        binder_context(subject_id="service.other"),
        binder_context(actor_type="human"),
        binder_context(authentication_method="session_cookie"),
        binder_context(audience="audience.other"),
    ],
)
async def test_only_exact_binder_workload_and_audience_are_accepted(
    context: WorkflowPhysicalTransportTargetContextBinderContext,
) -> None:
    service, repository, _ = service_fixture()

    with pytest.raises(WorkflowEventPhysicalTransportTargetContextBindingError) as denied:
        await bind(service, context=context)

    assert denied.value.code.endswith("binder_identity_required")
    assert not repository.calls


@pytest.mark.asyncio
async def test_request_validation_and_policy_fail_before_repository() -> None:
    service, repository, _ = service_fixture()
    policy = service.policy

    with pytest.raises(WorkflowEventPhysicalTransportTargetContextBindingError) as digest_error:
        await bind(service, endpoint_digest="invalid")
    with pytest.raises(WorkflowEventPhysicalTransportTargetContextBindingError) as policy_error:
        await service.bind(
            endpoint_materialization_id=ENDPOINT_ID,
            endpoint_materialization_digest=ENDPOINT_DIGEST,
            credential_materialization_id=CREDENTIAL_ID,
            credential_materialization_digest=CREDENTIAL_DIGEST,
            policy_id=policy.policy_id,
            policy_version="2.0",
            policy_digest=policy.canonical_digest,
            idempotency_key="target-context-binding-0001",
            context=binder_context(),
        )

    assert digest_error.value.code.endswith("endpoint_materialization_digest_invalid")
    assert policy_error.value.code.endswith("policy_mismatch")
    assert not repository.calls
    signature = inspect.signature(service.bind)
    assert not {
        "artifact_id",
        "endpoint",
        "credential",
        "target",
        "route",
        "assignment",
        "provider",
    }.intersection(signature.parameters)


@pytest.mark.asyncio
async def test_precommit_and_completion_audit_failures_preserve_atomic_semantics() -> None:
    precommit_audit = CollectingAuditSink(fail_kind="commit-authorization")
    service, repository, _ = service_fixture(audit=precommit_audit)

    with pytest.raises(WorkflowEventPhysicalTransportTargetContextBindingError) as precommit:
        await bind(service)
    assert precommit.value.code.endswith("precommit_audit_failed")
    assert not repository.bindings

    completion_audit = CollectingAuditSink(fail_kind="completion")
    service, repository, _ = service_fixture(audit=completion_audit)
    with pytest.raises(WorkflowEventPhysicalTransportTargetContextBindingError) as completion:
        await bind(service)
    assert completion.value.code.endswith("completion_audit_outcome_uncertain")
    assert len(repository.bindings) == 1

    completion_audit.fail_kind = None
    recovered = await bind(service)
    assert recovered == repository.bindings[0]


@pytest.mark.asyncio
async def test_non_durable_and_noncanonical_repository_results_fail_closed() -> None:
    service, repository, _ = service_fixture(
        repository=FakeTargetContextBindingRepository(durable=False)
    )
    with pytest.raises(WorkflowEventPhysicalTransportTargetContextBindingError) as non_durable:
        await bind(service)
    assert non_durable.value.code.endswith("durable_repository_required")
    assert not repository.calls

    tampered_repository = FakeTargetContextBindingRepository()
    tampered_repository.tamper_authority = True
    service, _, _ = service_fixture(repository=tampered_repository)
    with pytest.raises(WorkflowEventPhysicalTransportTargetContextBindingError) as tampered:
        await bind(service)
    assert tampered.value.code.endswith("repository_contract_violation")


def test_repository_protocol_exposes_only_durable_bind_and_scope_list_contract() -> None:
    public_members = {
        name
        for name, _ in inspect.getmembers(
            WorkflowEventPhysicalTransportTargetContextBindingRepository,
            predicate=inspect.isfunction,
        )
        if not name.startswith("_")
    }
    assert public_members == {"bind_target_context", "list_target_context_bindings"}
