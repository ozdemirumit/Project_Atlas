from __future__ import annotations

import inspect
from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any, cast

import pytest

from atlas.modules.workflows.application import (
    WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_AUDIENCE,
    WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleBinderContext,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBindingError,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBindingService,
    WorkflowTargetContextCapsuleConsumerBindingRequest,
    WorkflowTargetContextCapsuleConsumerBindingResult,
    WorkflowTargetContextCapsuleConsumerBindingStatus,
    validate_workflow_target_context_capsule_consumer_binding_request,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedTransportTargetContextCapsuleConsumerBinding,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBindingAuthority,
    WorkflowProtectedTransportTargetContextCapsuleConsumerBindingState,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_protected_transport_target_context_capsule_consumer_binding_policy,
)

NOW = datetime(2026, 8, 16, 9, 0, tzinfo=UTC)
SCOPE = WorkflowScope(
    organization_id="org-atlas",
    environment_id="production",
    site_id="site-istanbul",
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


def binder_context(**changes: Any) -> WorkflowProtectedTransportTargetContextCapsuleBinderContext:
    values: dict[str, Any] = {
        "subject_id": WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_SUBJECT,
        "actor_type": "service",
        "authentication_method": "workload_token",
        "credential_audience": (
            WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_AUDIENCE
        ),
        "scope": SCOPE,
        "correlation_id": "correlation-imp-211",
        "decision_id": "decision-imp-211",
        "requested_at": NOW,
    }
    values.update(changes)
    return WorkflowProtectedTransportTargetContextCapsuleBinderContext(**values)


class InMemoryCapsuleConsumerBindingRepository:
    def __init__(self, *, durable: bool = True) -> None:
        self._durable = durable
        self.calls: list[WorkflowTargetContextCapsuleConsumerBindingRequest] = []
        self.binding: WorkflowProtectedTransportTargetContextCapsuleConsumerBinding | None = None
        self.force_status: WorkflowTargetContextCapsuleConsumerBindingStatus | None = None
        self.tamper_result = False

    @property
    def durable(self) -> bool:
        return self._durable

    async def bind_target_context_capsule_consumer(
        self, request: WorkflowTargetContextCapsuleConsumerBindingRequest
    ) -> WorkflowTargetContextCapsuleConsumerBindingResult:
        validate_workflow_target_context_capsule_consumer_binding_request(request)
        self.calls.append(request)
        if self.force_status is not None:
            return WorkflowTargetContextCapsuleConsumerBindingResult(self.force_status, None)
        if self.binding is not None:
            if self.binding.idempotency_digest == request.idempotency_digest:
                status = (
                    WorkflowTargetContextCapsuleConsumerBindingStatus.REPLAY
                    if self.binding.request_fingerprint == request.request_fingerprint
                    else WorkflowTargetContextCapsuleConsumerBindingStatus.IDEMPOTENCY_CONFLICT
                )
            else:
                status = WorkflowTargetContextCapsuleConsumerBindingStatus.ALREADY_BOUND
            return WorkflowTargetContextCapsuleConsumerBindingResult(
                status,
                self.binding
                if status is WorkflowTargetContextCapsuleConsumerBindingStatus.REPLAY
                else None,
            )
        policy = (
            code_owned_workflow_protected_transport_target_context_capsule_consumer_binding_policy()
        )
        authority = WorkflowProtectedTransportTargetContextCapsuleConsumerBindingAuthority()
        values: dict[str, object] = {
            "binding_id": "target-context-capsule-consumer-binding.imp-211",
            "opening_result_id": request.opening_result_id,
            "opening_result_digest": request.opening_result_digest,
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
            "outbox_entry_id": "dispatch-outbox.imp-211",
            "outbox_entry_digest": "7" * 64,
            "event_id": "workflow-event.imp-211",
            "event_digest": "8" * 64,
            "event_artifact_id": "workflow-event-artifact.imp-211",
            "event_artifact_digest": "9" * 64,
            "logical_channel_binding_id": "logical-channel-binding.imp-211",
            "logical_channel_binding_digest": "a" * 64,
            "physical_transport_route_binding_id": "physical-route-binding.imp-211",
            "physical_transport_route_binding_digest": "b" * 64,
            "transport_route_snapshot_id": "transport-route-snapshot.imp-211",
            "transport_route_snapshot_digest": "c" * 64,
            "physical_transport_credential_assignment_binding_id": (
                "physical-credential-assignment-binding.imp-211"
            ),
            "physical_transport_credential_assignment_binding_digest": "d" * 64,
            "credential_assignment_snapshot_id": "credential-assignment-snapshot.imp-211",
            "credential_assignment_snapshot_digest": "e" * 64,
            "plan_id": "workflow-plan.imp-211",
            "plan_digest": "f" * 64,
            "run_id": "workflow-run.imp-211",
            "run_digest": "0" * 64,
            "step_run_id": "workflow-step-run.imp-211",
            "step_run_digest": "1" * 64,
            "workflow_execution_attempt_id": "workflow-execution-attempt.imp-211",
            "workflow_execution_attempt_digest": "2" * 64,
            "target_id": "storage-target.imp-211",
            "target_type": "storage",
            "consumer_subject_id": policy.consumer_subject_id,
            "consumer_audience": policy.consumer_audience,
            "consumer_contract_id": policy.consumer_contract_id,
            "consumer_contract_version": policy.consumer_contract_version,
            "purpose_id": policy.purpose_id,
            "scope": request.scope,
            "binder_subject_id": request.binder_subject_id,
            "binder_audience": request.binder_audience,
            "bound_at": NOW,
            "effective_until": NOW + timedelta(seconds=2),
            "policy_id": policy.policy_id,
            "policy_version": policy.policy_version,
            "policy_digest": policy.canonical_digest,
            "request_fingerprint": request.request_fingerprint,
            "idempotency_digest": request.idempotency_digest,
            "authorization_audit_digest": canonical_digest(
                {
                    "event_type": "target_context_capsule_consumer_binding_authorized",
                    "request_fingerprint": request.request_fingerprint,
                }
            ),
            "state": WorkflowProtectedTransportTargetContextCapsuleConsumerBindingState.BOUND,
            "authority": authority,
        }
        binding = WorkflowProtectedTransportTargetContextCapsuleConsumerBinding(
            **cast(Any, values), canonical_digest=canonical_digest(_payload(values))
        )
        if self.tamper_result:
            object.__setattr__(binding, "opening_result_digest", "0" * 64)
        self.binding = binding
        return WorkflowTargetContextCapsuleConsumerBindingResult(
            WorkflowTargetContextCapsuleConsumerBindingStatus.BOUND, binding
        )

    async def list_target_context_capsule_consumer_bindings(
        self, *, scope: WorkflowScope, limit: int
    ) -> tuple[WorkflowProtectedTransportTargetContextCapsuleConsumerBinding, ...]:
        if self.binding is None or self.binding.scope != scope:
            return ()
        return (self.binding,)[:limit]


async def bind(
    service: WorkflowProtectedTransportTargetContextCapsuleConsumerBindingService,
    **changes: Any,
) -> WorkflowProtectedTransportTargetContextCapsuleConsumerBinding:
    values: dict[str, Any] = {
        "opening_result_id": "target-context-artifact-opening.imp-210",
        "opening_result_digest": "a" * 64,
        "policy_id": service.policy.policy_id,
        "policy_version": service.policy.policy_version,
        "idempotency_key": "capsule-consumer-binding-0001",
        "context": binder_context(),
    }
    values.update(changes)
    return await service.bind(**values)


def test_policy_authority_and_public_command_are_strict() -> None:
    policy = (
        code_owned_workflow_protected_transport_target_context_capsule_consumer_binding_policy()
    )
    assert policy.successful_opening_required is True
    assert policy.exact_pending_event_lineage_required is True
    assert policy.handoff_forbidden is True
    assert policy.unsealing_forbidden is True
    assert policy.external_io_forbidden is True
    assert policy.canonical_digest == canonical_digest(policy.digest_payload())

    authority = WorkflowProtectedTransportTargetContextCapsuleConsumerBindingAuthority()
    assert len(authority.canonical_value()) == 17
    assert set(authority.canonical_value().values()) == {False}
    with pytest.raises(ValueError, match="cannot grant authority"):
        replace(authority, delivery_authorized=True)

    parameters = inspect.signature(
        WorkflowProtectedTransportTargetContextCapsuleConsumerBindingService.bind
    ).parameters
    assert set(parameters) == {
        "self",
        "opening_result_id",
        "opening_result_digest",
        "policy_id",
        "policy_version",
        "idempotency_key",
        "context",
    }
    forbidden = {
        "sealed_capsule_id",
        "sealed_capsule_digest",
        "consumer_subject_id",
        "consumer_audience",
        "consumer_contract_id",
        "purpose_id",
        "outbox_entry_id",
        "event_id",
        "endpoint",
        "credential",
        "network_client",
        "runtime_handle",
    }
    assert forbidden.isdisjoint(parameters)


@pytest.mark.asyncio
async def test_bind_derives_consumer_and_returns_immutable_zero_authority_evidence() -> None:
    repository = InMemoryCapsuleConsumerBindingRepository()
    service = WorkflowProtectedTransportTargetContextCapsuleConsumerBindingService(
        repository=repository
    )

    binding = await bind(service)

    assert len(repository.calls) == 1
    request = repository.calls[0]
    assert request.expected_consumer_subject_id == service.policy.consumer_subject_id
    assert request.expected_consumer_audience == service.policy.consumer_audience
    assert request.expected_consumer_contract_id == service.policy.consumer_contract_id
    assert request.expected_purpose_id == service.policy.purpose_id
    assert binding.capsule_is_bearer_capability is False
    assert binding.state is WorkflowProtectedTransportTargetContextCapsuleConsumerBindingState.BOUND
    assert len(fields(binding.authority)) == 17
    assert not any(binding.authority.canonical_value().values())
    assert binding.canonical_digest == canonical_digest(binding.digest_payload())


@pytest.mark.asyncio
async def test_exact_replay_is_stable_and_changed_replay_fails_closed() -> None:
    repository = InMemoryCapsuleConsumerBindingRepository()
    service = WorkflowProtectedTransportTargetContextCapsuleConsumerBindingService(
        repository=repository
    )

    first = await bind(service)
    replay = await bind(service, context=binder_context(requested_at=NOW + timedelta(minutes=5)))

    assert replay is first
    assert len(repository.calls) == 2
    with pytest.raises(
        WorkflowProtectedTransportTargetContextCapsuleConsumerBindingError,
        match="target_context_capsule_consumer_binding_idempotency_conflict",
    ):
        await bind(service, opening_result_digest="b" * 64)
    with pytest.raises(
        WorkflowProtectedTransportTargetContextCapsuleConsumerBindingError,
        match="target_context_capsule_consumer_binding_already_bound",
    ):
        await bind(service, idempotency_key="capsule-consumer-binding-0002")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "context",
    (
        binder_context(subject_id="service.other"),
        binder_context(actor_type="human"),
        binder_context(authentication_method="session"),
        binder_context(credential_audience="audience.other"),
    ),
)
async def test_only_exact_binder_workload_and_audience_are_accepted(
    context: WorkflowProtectedTransportTargetContextCapsuleBinderContext,
) -> None:
    service = WorkflowProtectedTransportTargetContextCapsuleConsumerBindingService(
        repository=InMemoryCapsuleConsumerBindingRepository()
    )

    with pytest.raises(
        WorkflowProtectedTransportTargetContextCapsuleConsumerBindingError,
        match="target_context_capsule_consumer_binding_binder_identity_required",
    ):
        await bind(service, context=context)


@pytest.mark.asyncio
async def test_durable_repository_policy_and_repository_contract_are_required() -> None:
    unavailable = WorkflowProtectedTransportTargetContextCapsuleConsumerBindingService(
        repository=InMemoryCapsuleConsumerBindingRepository(durable=False)
    )
    with pytest.raises(
        WorkflowProtectedTransportTargetContextCapsuleConsumerBindingError,
        match="target_context_capsule_consumer_binding_durable_repository_required",
    ):
        await bind(unavailable)

    service = WorkflowProtectedTransportTargetContextCapsuleConsumerBindingService(
        repository=InMemoryCapsuleConsumerBindingRepository()
    )
    with pytest.raises(
        WorkflowProtectedTransportTargetContextCapsuleConsumerBindingError,
        match="target_context_capsule_consumer_binding_policy_mismatch",
    ):
        await bind(service, policy_version="2.0")

    tampering_repository = InMemoryCapsuleConsumerBindingRepository()
    tampering_repository.tamper_result = True
    tampered = WorkflowProtectedTransportTargetContextCapsuleConsumerBindingService(
        repository=tampering_repository
    )
    with pytest.raises(
        WorkflowProtectedTransportTargetContextCapsuleConsumerBindingError,
        match="target_context_capsule_consumer_binding_repository_contract_violation",
    ):
        await bind(tampered)


def test_repository_request_validator_rejects_non_code_owned_derivation() -> None:
    policy = (
        code_owned_workflow_protected_transport_target_context_capsule_consumer_binding_policy()
    )
    request = WorkflowTargetContextCapsuleConsumerBindingRequest(
        opening_result_id="target-context-artifact-opening.imp-210",
        opening_result_digest="a" * 64,
        expected_policy_id=policy.policy_id,
        expected_policy_version=policy.policy_version,
        expected_policy_digest=policy.canonical_digest,
        expected_consumer_subject_id=policy.consumer_subject_id,
        expected_consumer_audience=policy.consumer_audience,
        expected_consumer_contract_id=policy.consumer_contract_id,
        expected_consumer_contract_version=policy.consumer_contract_version,
        expected_purpose_id=policy.purpose_id,
        minimum_remaining_lifetime_seconds=policy.minimum_remaining_lifetime_seconds,
        scope=SCOPE,
        binder_subject_id=WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_SUBJECT,
        binder_audience=WORKFLOW_PROTECTED_TRANSPORT_TARGET_CONTEXT_CAPSULE_BINDER_AUDIENCE,
        requested_at=NOW,
        idempotency_key="capsule-consumer-binding-0001",
        idempotency_digest="b" * 64,
        request_fingerprint="c" * 64,
    )
    validate_workflow_target_context_capsule_consumer_binding_request(request)
    with pytest.raises(ValueError, match="unsafe"):
        validate_workflow_target_context_capsule_consumer_binding_request(
            replace(request, expected_consumer_subject_id="service.caller-selected")
        )
