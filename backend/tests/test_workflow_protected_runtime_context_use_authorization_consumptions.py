from __future__ import annotations

import inspect
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

import pytest

from atlas.modules.workflows.application.protected_runtime_context_use_authorization_consumption_ports import (  # noqa: E501
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionError,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPresentation,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayLookup,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayLookupRequest,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayStatus,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionRequest,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionWrite,
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionWriteStatus,
    validate_workflow_protected_runtime_context_use_authorization_consumption_request,
)
from atlas.modules.workflows.application.protected_runtime_context_use_authorization_consumptions import (  # noqa: E501
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionService,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
)
from atlas.modules.workflows.domain.models import WorkflowScope
from atlas.modules.workflows.domain.protected_runtime_context_use_authorization_consumption_domain import (  # noqa: E501
    WorkflowProtectedRuntimeContextUseAuthorizationConsumptionState,
)

NOW = datetime(2026, 8, 17, 10, 0, tzinfo=UTC)
SCOPE = WorkflowScope("organization.test", "environment.test", "site.test")


def _context(
    *,
    subject_id: str = WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    audience: str = WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    actor_type: str = "service",
    authentication_method: str = "workload_token",
    scope: WorkflowScope = SCOPE,
) -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext:
    return WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
        subject_id=subject_id,
        actor_type=actor_type,
        authentication_method=authentication_method,
        credential_audience=audience,
        scope=scope,
        correlation_id="correlation.imp-221",
        decision_id="decision.imp-221",
        requested_at=NOW,
    )


def _presentation(
    request: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionRequest,
) -> WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPresentation:
    claim = SimpleNamespace(
        consumption_id=request.consumption_id,
        consumption_claim_id=request.consumption_claim_id,
        canonical_digest="a" * 64,
        authorization_lease_id=request.authorization_lease_id,
        authorization_lease_digest="b" * 64,
        scope=request.scope,
        consumer_subject_id=request.consumer_subject_id,
        consumer_audience=request.consumer_audience,
        policy_digest=request.policy_digest,
        source_policy_digest=request.source_policy_digest,
        claimed_at=NOW,
    )
    result = SimpleNamespace(
        state=(
            WorkflowProtectedRuntimeContextUseAuthorizationConsumptionState.AUTHORIZATION_CONSUMED_WITHOUT_RUNTIME_USE
        ),
        consumption_id=request.consumption_id,
        consumption_claim_id=request.consumption_claim_id,
        consumption_claim_digest=claim.canonical_digest,
        authorization_lease_id=request.authorization_lease_id,
        authorization_lease_digest=claim.authorization_lease_digest,
        scope=request.scope,
        consumer_subject_id=request.consumer_subject_id,
        consumer_audience=request.consumer_audience,
        policy_digest=request.policy_digest,
        source_policy_digest=request.source_policy_digest,
        consumed_at=NOW,
    )
    return WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPresentation(
        cast(Any, claim), cast(Any, result)
    )


class _Repository:
    def __init__(self, *, durable: bool = True) -> None:
        self.durable = durable
        self.events: list[str] = []
        self.replay_status = (
            WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayStatus.NONE
        )
        self.write_status = (
            WorkflowProtectedRuntimeContextUseAuthorizationConsumptionWriteStatus.CONSUMED
        )
        self.replay_presentation: (
            WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPresentation | None
        ) = None
        self.requests: list[WorkflowProtectedRuntimeContextUseAuthorizationConsumptionRequest] = []
        self.replay_requests: list[
            WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayLookupRequest
        ] = []

    async def lookup_protected_runtime_context_use_authorization_consumption_replay(
        self,
        request: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayLookupRequest,
    ) -> WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayLookup:
        self.events.append("replay")
        self.replay_requests.append(request)
        presentation = self.replay_presentation
        return WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayLookup(
            status=self.replay_status,
            claim=presentation.claim if presentation is not None else None,
            result=presentation.result if presentation is not None else None,
        )

    async def consume_protected_runtime_context_use_authorization(
        self, request: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionRequest
    ) -> WorkflowProtectedRuntimeContextUseAuthorizationConsumptionWrite:
        self.events.append("consume")
        validate_workflow_protected_runtime_context_use_authorization_consumption_request(request)
        self.requests.append(request)
        presentation = _presentation(request)
        return WorkflowProtectedRuntimeContextUseAuthorizationConsumptionWrite(
            status=self.write_status,
            claim=presentation.claim,
            result=presentation.result,
        )

    async def list_protected_runtime_context_use_authorization_consumption_presentations(
        self, *, scope: WorkflowScope, limit: int = 256
    ) -> tuple[WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPresentation, ...]:
        self.events.append(f"list:{scope.site_id}:{limit}")
        return (self.replay_presentation,) if self.replay_presentation is not None else ()


async def _consume(
    service: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionService,
    *,
    idempotency_key: str = "imp-221-use-authorization-consumption",
    context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext
    | None = None,
) -> WorkflowProtectedRuntimeContextUseAuthorizationConsumptionPresentation:
    return await service.consume(
        authorization_lease_id="use-authorization-lease.imp-220",
        policy_id=service.policy.policy_id,
        policy_version=service.policy.policy_version,
        idempotency_key=idempotency_key,
        irreversible_consumption_acknowledged=True,
        context=context or _context(),
    )


def test_service_surface_has_no_attestor_adapter_runtime_or_operational_fields() -> None:
    constructor = set(
        inspect.signature(
            WorkflowProtectedRuntimeContextUseAuthorizationConsumptionService
        ).parameters
    )
    consume = set(
        inspect.signature(
            WorkflowProtectedRuntimeContextUseAuthorizationConsumptionService.consume
        ).parameters
    )

    assert constructor == {"repository", "policy"}
    assert consume == {
        "self",
        "authorization_lease_id",
        "policy_id",
        "policy_version",
        "idempotency_key",
        "irreversible_consumption_acknowledged",
        "context",
    }
    assert not consume.intersection(
        {
            "attestor",
            "adapter",
            "context_handle",
            "runtime_slot_commitment",
            "runtime_use",
            "runtime_start",
            "connector",
            "network",
            "dispatch",
            "execution",
            "mutation",
        }
    )


@pytest.mark.asyncio
async def test_exact_replay_is_first_and_skips_atomic_consumption() -> None:
    original = _Repository()
    service = WorkflowProtectedRuntimeContextUseAuthorizationConsumptionService(
        repository=cast(Any, original)
    )
    first = await _consume(service)
    request = original.requests[0]

    replay = _Repository()
    replay.replay_status = (
        WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayStatus.TERMINAL
    )
    replay.replay_presentation = first
    replayed = await _consume(
        WorkflowProtectedRuntimeContextUseAuthorizationConsumptionService(
            repository=cast(Any, replay)
        )
    )

    assert original.events == ["replay", "consume"]
    assert replay.events == ["replay"]
    assert replayed is first or replayed == first
    assert replay.replay_requests[0].request_fingerprint == request.request_fingerprint
    assert replay.replay_requests[0].idempotency_digest == request.idempotency_digest


@pytest.mark.asyncio
async def test_idempotency_digest_is_scoped_to_the_exact_tenant() -> None:
    first_repository = _Repository()
    second_repository = _Repository()
    first_service = WorkflowProtectedRuntimeContextUseAuthorizationConsumptionService(
        repository=cast(Any, first_repository)
    )
    second_service = WorkflowProtectedRuntimeContextUseAuthorizationConsumptionService(
        repository=cast(Any, second_repository)
    )

    await _consume(first_service, idempotency_key="same-key-across-scopes")
    await _consume(
        second_service,
        idempotency_key="same-key-across-scopes",
        context=_context(
            scope=WorkflowScope("organization.other", "environment.other", "site.other")
        ),
    )

    assert first_repository.requests[0].idempotency_digest != (
        second_repository.requests[0].idempotency_digest
    )


@pytest.mark.asyncio
async def test_atomic_request_is_minimized_code_owned_and_zero_effect() -> None:
    repository = _Repository()
    service = WorkflowProtectedRuntimeContextUseAuthorizationConsumptionService(
        repository=cast(Any, repository)
    )

    presentation = await _consume(service)
    request = repository.requests[0]

    assert repository.events == ["replay", "consume"]
    assert request.irreversible_consumption_acknowledged is True
    assert request.consumer_subject_id == service.policy.consumer_subject_id
    assert request.consumer_audience == service.policy.consumer_audience
    assert request.policy_digest == service.policy.canonical_digest
    assert request.source_policy_digest == service.policy.source_policy_digest
    assert request.consumption_audit_payload["context_accessed"] is False
    assert request.consumption_audit_payload["context_used"] is False
    assert request.consumption_audit_payload["runtime_started"] is False
    assert request.consumption_audit_payload["network_activity_performed"] is False
    assert request.consumption_audit_payload["connector_activity_performed"] is False
    assert request.consumption_audit_payload["dispatch_performed"] is False
    assert request.consumption_audit_payload["execution_performed"] is False
    assert request.consumption_audit_payload["infrastructure_mutation_performed"] is False
    assert presentation.result.state.value == ("authorization_consumed_without_runtime_use")
    request_fields = set(request.__dataclass_fields__)
    assert not request_fields.intersection(
        {
            "context_material",
            "context_handle",
            "runtime_slot_locator",
            "endpoint",
            "credential",
            "secret",
            "authority",
        }
    )


@pytest.mark.asyncio
async def test_durable_repository_is_required_before_any_repository_operation() -> None:
    repository = _Repository(durable=False)
    service = WorkflowProtectedRuntimeContextUseAuthorizationConsumptionService(
        repository=cast(Any, repository)
    )

    with pytest.raises(
        WorkflowProtectedRuntimeContextUseAuthorizationConsumptionError,
        match="durable_repository_required",
    ):
        await _consume(service)

    assert repository.events == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "context",
    [
        _context(subject_id="service.workflow-generic"),
        _context(audience="audience.workflow-generic"),
        _context(actor_type="human"),
        _context(authentication_method="password"),
    ],
)
async def test_only_exact_protected_consumer_workload_may_consume(
    context: WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
) -> None:
    repository = _Repository()
    service = WorkflowProtectedRuntimeContextUseAuthorizationConsumptionService(
        repository=cast(Any, repository)
    )

    with pytest.raises(
        WorkflowProtectedRuntimeContextUseAuthorizationConsumptionError,
        match="request_invalid",
    ):
        await _consume(service, context=context)

    assert repository.events == []


@pytest.mark.asyncio
async def test_acknowledgement_policy_and_idempotency_fail_before_replay() -> None:
    repository = _Repository()
    service = WorkflowProtectedRuntimeContextUseAuthorizationConsumptionService(
        repository=cast(Any, repository)
    )

    invalid_calls = (
        {"policy_id": "policy.changed", "irreversible": True, "key": "valid-key"},
        {
            "policy_id": service.policy.policy_id,
            "irreversible": False,
            "key": "valid-key",
        },
        {
            "policy_id": service.policy.policy_id,
            "irreversible": True,
            "key": "short",
        },
    )
    for values in invalid_calls:
        with pytest.raises(
            WorkflowProtectedRuntimeContextUseAuthorizationConsumptionError,
            match="request_invalid",
        ):
            await service.consume(
                authorization_lease_id="use-authorization-lease.imp-220",
                policy_id=cast(str, values["policy_id"]),
                policy_version=service.policy.policy_version,
                idempotency_key=cast(str, values["key"]),
                irreversible_consumption_acknowledged=cast(bool, values["irreversible"]),
                context=_context(),
            )

    assert repository.events == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [
        WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayStatus.IDEMPOTENCY_CONFLICT,
        WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayStatus.EVIDENCE_CONFLICT,
        WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayStatus.ALREADY_CONSUMED,
    ],
)
async def test_non_exact_replay_states_fail_closed_before_consuming(
    status: WorkflowProtectedRuntimeContextUseAuthorizationConsumptionReplayStatus,
) -> None:
    repository = _Repository()
    repository.replay_status = status
    service = WorkflowProtectedRuntimeContextUseAuthorizationConsumptionService(
        repository=cast(Any, repository)
    )

    with pytest.raises(
        WorkflowProtectedRuntimeContextUseAuthorizationConsumptionError,
        match=status.value,
    ):
        await _consume(service)

    assert repository.events == ["replay"]


@pytest.mark.asyncio
async def test_list_presentations_is_durable_read_only_repository_projection() -> None:
    populated = _Repository()
    service = WorkflowProtectedRuntimeContextUseAuthorizationConsumptionService(
        repository=cast(Any, populated)
    )
    populated.replay_presentation = await _consume(service)
    populated.events.clear()

    presentations = await service.list_presentations(scope=SCOPE, limit=17)

    assert presentations == (populated.replay_presentation,)
    assert populated.events == ["list:site.test:17"]
