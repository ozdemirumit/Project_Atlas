from __future__ import annotations

from dataclasses import fields, replace
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from atlas.modules.workflows.adapters import (
    protected_runtime_process_scheduling_state_attestors as state_attestors,
)
from atlas.modules.workflows.application import (
    protected_runtime_process_scheduling_authorization_ports as scheduling_ports,
)
from atlas.modules.workflows.domain import (
    protected_runtime_process_scheduling_authorization_domain as scheduling_domain,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest

DevelopmentAttestor = (
    state_attestors.DeterministicDevelopmentWorkflowProtectedRuntimeProcessSchedulingStateAttestor
)
UnavailableAttestor = (
    state_attestors.UnavailableWorkflowProtectedRuntimeProcessSchedulingStateAttestor
)
AuthorizationError = scheduling_ports.WorkflowProtectedRuntimeProcessSchedulingAuthorizationError
StateRequest = scheduling_ports.WorkflowProtectedRuntimeProcessSchedulingStateAttestationRequest
code_owned_policy = (
    scheduling_domain.code_owned_workflow_protected_runtime_process_scheduling_authorization_policy
)

NOW = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)


def _request(*, nonce: str = "a" * 64) -> StateRequest:
    policy = code_owned_policy()
    values: dict[str, object] = {}
    for field in fields(StateRequest):
        name = field.name
        policy_value = getattr(policy, name, None)
        if policy_value is not None:
            values[name] = policy_value
        elif name == "scope":
            values[name] = WorkflowScope("organization.test", "environment.test", "site.test")
        elif name == "request_nonce_digest":
            values[name] = nonce
        elif name == "requested_at":
            values[name] = NOW
        elif name.endswith("_generation"):
            values[name] = 7
        elif name.endswith(("_digest", "_commitment")):
            values[name] = canonical_digest({"field": name})
        elif name.endswith("_version"):
            values[name] = "1.0"
        else:
            values[name] = f"{name}.test"
    return StateRequest(**cast(Any, values))


@pytest.mark.asyncio
async def test_development_attestor_binds_suspended_process_and_zero_effects() -> None:
    attestor = DevelopmentAttestor(development_enabled=True, clock=lambda: NOW)
    request = _request()

    first = await attestor.attest_runtime_process_scheduling_state(request)
    second = await attestor.attest_runtime_process_scheduling_state(request)

    assert first == second
    assert first.request_nonce_digest == request.request_nonce_digest
    assert first.exact_process_creation_result_confirmed is True
    assert first.terminal_success_confirmed is True
    assert first.metadata_only_confirmed is True
    assert first.process_created_confirmed is True
    assert first.process_sealed_confirmed is True
    assert first.process_suspended_confirmed is True
    assert first.process_not_scheduled_confirmed is True
    assert first.process_not_resumed_confirmed is True
    assert first.process_not_dispatched_confirmed is True
    assert first.process_not_executed_confirmed is True
    assert first.prior_process_scheduling_claim_absent is True
    assert first.prior_process_scheduling_lease_absent is True

    request_names = {field.name for field in fields(request)} - {"requested_at"}
    attestation_names = {field.name for field in fields(first)}
    for name in request_names & attestation_names:
        assert getattr(first, name) == getattr(request, name)

    prohibited = [
        getattr(first, field.name)
        for field in fields(first)
        if field.name.endswith(("_included", "_performed"))
    ]
    assert prohibited
    assert all(value is False for value in prohibited)
    assert attestor.verify_runtime_process_scheduling_state_attestation(first) is True
    assert (
        attestor.verify_runtime_process_scheduling_state_attestation(
            replace(first, request_nonce_digest="b" * 64)
        )
        is False
    )


@pytest.mark.asyncio
async def test_development_attestor_preserves_negative_process_state() -> None:
    attestor = DevelopmentAttestor(
        development_enabled=True,
        clock=lambda: NOW,
        process_created=False,
        process_sealed=False,
        process_suspended=False,
        process_scheduled=True,
        process_resumed=True,
        process_dispatched=True,
        process_executed=True,
        destination_fence_current=False,
        prior_scheduling_claim_absent=False,
        prior_scheduling_lease_absent=False,
    )

    evidence = await attestor.attest_runtime_process_scheduling_state(_request())

    assert evidence.process_created_confirmed is False
    assert evidence.process_sealed_confirmed is False
    assert evidence.process_suspended_confirmed is False
    assert evidence.process_not_scheduled_confirmed is False
    assert evidence.process_not_resumed_confirmed is False
    assert evidence.process_not_dispatched_confirmed is False
    assert evidence.process_not_executed_confirmed is False
    assert evidence.scheduling_performed is True
    assert evidence.resume_performed is True
    assert evidence.dispatch_performed is True
    assert evidence.execution_performed is True
    assert evidence.destination_fence_current is False
    assert evidence.prior_process_scheduling_claim_absent is False
    assert evidence.prior_process_scheduling_lease_absent is False
    assert attestor.verify_runtime_process_scheduling_state_attestation(evidence) is True


@pytest.mark.asyncio
async def test_development_attestor_binds_every_lineage_digest() -> None:
    attestor = DevelopmentAttestor(development_enabled=True, clock=lambda: NOW)
    evidence = await attestor.attest_runtime_process_scheduling_state(_request())
    digest_fields = [
        field.name
        for field in fields(evidence)
        if field.name.endswith("_digest")
        and field.name not in {"canonical_digest", "request_nonce_digest"}
    ]

    assert digest_fields
    for name in digest_fields:
        tampered = replace(evidence, **cast(Any, {name: "0" * 64}))
        assert attestor.verify_runtime_process_scheduling_state_attestation(tampered) is False


@pytest.mark.asyncio
async def test_unavailable_disabled_and_naive_attestors_fail_closed() -> None:
    request = _request()
    naive = DevelopmentAttestor(
        development_enabled=True,
        clock=lambda: NOW.replace(tzinfo=None),
    )
    disabled = DevelopmentAttestor()
    unavailable = UnavailableAttestor()

    for attestor in (naive, disabled, unavailable):
        with pytest.raises(AuthorizationError) as caught:
            await attestor.attest_runtime_process_scheduling_state(request)
        assert request.request_nonce_digest not in f"{caught.value} {caught.value.detail}"
        if hasattr(attestor, "calls"):
            assert attestor.calls == []
        assert (
            attestor.verify_runtime_process_scheduling_state_attestation(cast(Any, None)) is False
        )
