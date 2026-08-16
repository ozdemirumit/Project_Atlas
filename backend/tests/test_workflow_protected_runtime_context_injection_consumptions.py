from __future__ import annotations

import inspect
from dataclasses import fields
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, cast

import pytest

from atlas.modules.workflows.application import (
    protected_runtime_context_injection_consumptions as service_module,
)
from atlas.modules.workflows.application.protected_runtime_context_injection_consumption_ports import (  # noqa: E501
    WorkflowProtectedRuntimeContextInjectionConsumptionClaimStatus,
    WorkflowProtectedRuntimeContextInjectionConsumptionClaimWrite,
    WorkflowProtectedRuntimeContextInjectionConsumptionError,
    WorkflowProtectedRuntimeContextInjectionConsumptionReplayLookup,
    WorkflowProtectedRuntimeContextInjectionConsumptionReplayStatus,
    WorkflowProtectedRuntimeContextInjectionConsumptionResultWrite,
    WorkflowProtectedRuntimeContextInjectionConsumptionResultWriteStatus,
)
from atlas.modules.workflows.application.protected_runtime_context_injection_consumptions import (
    WorkflowProtectedRuntimeContextInjectionConsumptionPresentation,
    WorkflowProtectedRuntimeContextInjectionConsumptionService,
)
from atlas.modules.workflows.application.target_context_capsule_handoff_authorization_leases import (  # noqa: E501
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
    WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT,
    WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedRuntimeContextTrustedInjectorInvocation,
    WorkflowScope,
)

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


class _AuditSink:
    async def record(self, record: object) -> None:
        del record


class _External:
    available = True

    def __init__(self, order: list[str]) -> None:
        self.order = order
        self.calls: list[object] = []


class _Injector:
    available = True
    injector_contract_id = "contract.injector"
    injector_contract_version = "1.0"
    injector_id = "injector.test"
    injector_version = "1.0"
    runtime_slot_profile_id = "profile.slot"
    runtime_slot_profile_version = "1.0"
    runtime_slot_profile_digest = "a" * 64

    def __init__(self, order: list[str], *, raises: bool = False) -> None:
        self.order = order
        self.raises = raises
        self.calls: list[WorkflowProtectedRuntimeContextTrustedInjectorInvocation] = []

    async def inject_context(
        self, invocation: WorkflowProtectedRuntimeContextTrustedInjectorInvocation
    ) -> object:
        self.order.append("injector")
        self.calls.append(invocation)
        if self.raises:
            raise RuntimeError("outcome uncertain")
        return SimpleNamespace(canonical_digest="9" * 64)

    def verify_receipt(self, receipt: object) -> bool:
        del receipt
        return True


class _Repository:
    durable = True

    def __init__(self, order: list[str]) -> None:
        self.order = order
        self.replay = WorkflowProtectedRuntimeContextInjectionConsumptionReplayLookup(
            status=WorkflowProtectedRuntimeContextInjectionConsumptionReplayStatus.NONE,
            attempt=None,
            result=None,
        )
        self.claim: WorkflowProtectedRuntimeContextInjectionConsumptionClaimWrite | None = None
        self.result_write: WorkflowProtectedRuntimeContextInjectionConsumptionResultWrite | None = (
            None
        )

    async def lookup_protected_runtime_context_injection_consumption_replay(
        self, request: object
    ) -> WorkflowProtectedRuntimeContextInjectionConsumptionReplayLookup:
        del request
        self.order.append("replay")
        return self.replay

    async def get_protected_runtime_context_injection_consumption_source(
        self, *, authorization_lease_id: str
    ) -> object | None:
        del authorization_lease_id
        self.order.append("source")
        return None

    async def claim_protected_runtime_context_injection_consumption(
        self, request: object
    ) -> WorkflowProtectedRuntimeContextInjectionConsumptionClaimWrite:
        del request
        self.order.append("claim")
        assert self.claim is not None
        return self.claim

    async def record_protected_runtime_context_injection_consumption_result(
        self, request: object
    ) -> WorkflowProtectedRuntimeContextInjectionConsumptionResultWrite:
        del request
        self.order.append("result")
        assert self.result_write is not None
        return self.result_write

    async def get_authoritative_time(self) -> datetime:
        self.order.append("time")
        return NOW + timedelta(milliseconds=200)


def _policy() -> Any:
    return SimpleNamespace(
        policy_id="policy.injection-consumption",
        policy_version="1.0",
        canonical_digest="b" * 64,
        required_lifecycle_attestor_id="attestor.lifecycle",
        required_lifecycle_attestor_version="1.0",
        required_slot_readiness_attestor_id="attestor.slot",
        required_slot_readiness_attestor_version="1.0",
        required_injector_contract_id="contract.injector",
        required_injector_contract_version="1.0",
        approved_injector_id="injector.test",
        approved_injector_version="1.0",
        runtime_slot_profile_id="profile.slot",
        runtime_slot_profile_version="1.0",
        runtime_slot_profile_digest="a" * 64,
        slot_readiness_verification_signing_key_id="key.slot",
        receipt_verification_signing_key_id="key.receipt",
        minimum_remaining_budget_milliseconds=100,
    )


def _context(
    *, subject_id: str = WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_SUBJECT
) -> WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext:
    return WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationContext(
        subject_id=subject_id,
        actor_type="service",
        authentication_method="workload_token",
        credential_audience=WORKFLOW_PROTECTED_TARGET_CONTEXT_CAPSULE_CONSUMER_AUDIENCE,
        scope=WorkflowScope("organization.test", "environment.test", "site.test"),
        correlation_id="correlation.test",
        decision_id="decision.test",
        requested_at=NOW,
    )


def _service(
    repository: _Repository, injector: _Injector, order: list[str]
) -> WorkflowProtectedRuntimeContextInjectionConsumptionService:
    external = _External(order)
    return WorkflowProtectedRuntimeContextInjectionConsumptionService(
        repository=cast(Any, repository),
        lifecycle_attestor=cast(Any, external),
        slot_readiness_attestor=cast(Any, external),
        lifecycle_signature_verifier=cast(Any, external),
        slot_readiness_signature_verifier=cast(Any, external),
        injector=cast(Any, injector),
        receipt_signature_verifier=cast(Any, injector),
        audit_sink=cast(Any, _AuditSink()),
        policy=_policy(),
    )


def _request() -> dict[str, object]:
    return {
        "authorization_lease_id": "workflow-protected-runtime-context-injection-lease.test",
        "policy_id": "policy.injection-consumption",
        "policy_version": "1.0",
        "irreversible_consumption_acknowledged": True,
        "uncertain_outcome_requires_new_authorization_acknowledged": True,
        "idempotency_key": "idempotency-test-001",
        "context": _context(),
    }


def test_public_command_accepts_only_lease_and_governance_metadata() -> None:
    parameters = inspect.signature(
        WorkflowProtectedRuntimeContextInjectionConsumptionService.consume
    ).parameters

    assert "authorization_lease_id" in parameters
    assert "protected_runtime_handle_id" not in parameters
    assert "protected_runtime_handle_digest" not in parameters
    assert "runtime_slot_commitment" not in parameters
    assert "runtime_slot_pre_generation" not in parameters


@pytest.mark.asyncio
async def test_terminal_replay_precedes_all_attestor_and_injector_io() -> None:
    order: list[str] = []
    repository = _Repository(order)
    attempt = SimpleNamespace(
        injection_id="workflow-protected-runtime-context-injection-consumption.test"
    )
    result = SimpleNamespace(injection_id=attempt.injection_id)
    repository.replay = WorkflowProtectedRuntimeContextInjectionConsumptionReplayLookup(
        status=WorkflowProtectedRuntimeContextInjectionConsumptionReplayStatus.TERMINAL,
        attempt=cast(Any, attempt),
        result=cast(Any, result),
    )
    injector = _Injector(order)

    presentation = await cast(Any, _service(repository, injector, order).consume)(**_request())

    assert cast(Any, presentation.attempt) is attempt
    assert cast(Any, presentation.result) is result
    assert order == ["replay"]
    assert injector.calls == []


@pytest.mark.asyncio
async def test_wrong_workload_identity_fails_before_repository_io() -> None:
    order: list[str] = []
    repository = _Repository(order)
    request = _request()
    request["context"] = _context(subject_id="service.some-other-workload")

    with pytest.raises(WorkflowProtectedRuntimeContextInjectionConsumptionError):
        await cast(Any, _service(repository, _Injector(order), order).consume)(**request)

    assert order == []


@pytest.mark.asyncio
async def test_claim_commit_precedes_one_minimized_injector_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order: list[str] = []
    repository = _Repository(order)
    attempt = SimpleNamespace(
        attempt_id="workflow-protected-runtime-context-injection-attempt.test",
        injection_id="workflow-protected-runtime-context-injection-consumption.test",
        canonical_digest="c" * 64,
        injection_deadline=NOW + timedelta(seconds=1),
    )
    claim = SimpleNamespace(canonical_digest="d" * 64)
    result = SimpleNamespace(injection_id=attempt.injection_id)
    repository.claim = WorkflowProtectedRuntimeContextInjectionConsumptionClaimWrite(
        status=WorkflowProtectedRuntimeContextInjectionConsumptionClaimStatus.CLAIMED,
        claim=cast(Any, claim),
        attempt=cast(Any, attempt),
        result=None,
    )
    repository.result_write = WorkflowProtectedRuntimeContextInjectionConsumptionResultWrite(
        status=WorkflowProtectedRuntimeContextInjectionConsumptionResultWriteStatus.RECORDED,
        result=cast(Any, result),
    )
    injector = _Injector(order)
    service = _service(repository, injector, order)
    evidence = SimpleNamespace(
        source=SimpleNamespace(
            authorization_lease=SimpleNamespace(
                authorization_lease_id="lease.test", canonical_digest="e" * 64
            )
        ),
        lifecycle=SimpleNamespace(request_nonce_digest="f" * 64),
        readiness=SimpleNamespace(runtime_slot_commitment="1" * 64, runtime_slot_pre_generation=4),
    )

    async def load_and_attest(**values: object) -> object:
        del values
        order.append("attest")
        return evidence

    instruction = SimpleNamespace(
        protected_operation_reference="protected-operation.test",
        canonical_digest="2" * 64,
        injection_deadline=NOW + timedelta(seconds=1),
    )
    invocation = WorkflowProtectedRuntimeContextTrustedInjectorInvocation(
        protected_operation_reference=instruction.protected_operation_reference,
        instruction_digest=instruction.canonical_digest,
        injection_deadline=instruction.injection_deadline,
    )
    monkeypatch.setattr(service, "_load_and_attest", load_and_attest)
    monkeypatch.setattr(
        service_module,
        "build_workflow_protected_runtime_context_trusted_injector_instruction",
        lambda value: instruction,
    )
    monkeypatch.setattr(
        service_module,
        "build_workflow_protected_runtime_context_trusted_injector_invocation",
        lambda value: invocation,
    )
    monkeypatch.setattr(service, "_verify_receipt", lambda receipt, value: None)
    monkeypatch.setattr(service, "_build_receipted_result", lambda **values: result)

    presentation = await cast(Any, service.consume)(**_request())

    assert presentation.result is result
    assert order.index("replay") < order.index("attest") < order.index("claim")
    assert order.index("claim") < order.index("injector") < order.index("result")
    assert injector.calls == [invocation]
    assert {field.name for field in fields(invocation)} == {
        "protected_operation_reference",
        "instruction_digest",
        "injection_deadline",
    }
    assert not hasattr(invocation, "protected_runtime_handle_digest")


@pytest.mark.asyncio
async def test_postcommit_injector_failure_is_never_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order: list[str] = []
    repository = _Repository(order)
    attempt = SimpleNamespace(
        attempt_id="workflow-protected-runtime-context-injection-attempt.test",
        injection_id="workflow-protected-runtime-context-injection-consumption.test",
        canonical_digest="c" * 64,
        injection_deadline=NOW + timedelta(seconds=1),
    )
    repository.claim = WorkflowProtectedRuntimeContextInjectionConsumptionClaimWrite(
        status=WorkflowProtectedRuntimeContextInjectionConsumptionClaimStatus.CLAIMED,
        claim=cast(Any, SimpleNamespace(canonical_digest="d" * 64)),
        attempt=cast(Any, attempt),
        result=None,
    )
    injector = _Injector(order, raises=True)
    service = _service(repository, injector, order)
    evidence = SimpleNamespace(
        source=SimpleNamespace(
            authorization_lease=SimpleNamespace(
                authorization_lease_id="lease.test", canonical_digest="e" * 64
            )
        ),
        lifecycle=SimpleNamespace(request_nonce_digest="f" * 64),
        readiness=SimpleNamespace(runtime_slot_commitment="1" * 64, runtime_slot_pre_generation=4),
    )

    async def load_and_attest(**values: object) -> object:
        del values
        return evidence

    async def record_uncertainty(**values: object) -> object:
        del values
        return WorkflowProtectedRuntimeContextInjectionConsumptionPresentation(
            cast(Any, attempt), None
        )

    invocation = WorkflowProtectedRuntimeContextTrustedInjectorInvocation(
        protected_operation_reference="protected-operation.test",
        instruction_digest="2" * 64,
        injection_deadline=NOW + timedelta(seconds=1),
    )
    monkeypatch.setattr(service, "_load_and_attest", load_and_attest)
    monkeypatch.setattr(
        service_module,
        "build_workflow_protected_runtime_context_trusted_injector_instruction",
        lambda value: SimpleNamespace(),
    )
    monkeypatch.setattr(
        service_module,
        "build_workflow_protected_runtime_context_trusted_injector_invocation",
        lambda value: invocation,
    )
    monkeypatch.setattr(service, "_record_uncertainty", record_uncertainty)

    presentation = await cast(Any, service.consume)(**_request())

    assert presentation.result is None
    assert order.count("injector") == 1
