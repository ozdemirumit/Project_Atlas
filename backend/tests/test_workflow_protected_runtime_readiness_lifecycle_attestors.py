from __future__ import annotations

from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from atlas.modules.workflows.adapters.protected_runtime_readiness_lifecycle_attestors import (
    DeterministicDevelopmentWorkflowProtectedRuntimeReadinessLifecycleAttestor,
    UnavailableWorkflowProtectedRuntimeReadinessLifecycleAttestor,
)
from atlas.modules.workflows.application.protected_runtime_readiness_authorization_ports import (
    WorkflowProtectedRuntimeReadinessAuthorizationError,
    WorkflowProtectedRuntimeReadinessLifecycleAttestationRequest,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_readiness_authorization_domain import (
    code_owned_workflow_protected_runtime_readiness_authorization_policy,
)

NOW = datetime(2026, 8, 17, 14, 0, tzinfo=UTC)


def _request(
    *,
    nonce: str = "a" * 64,
) -> WorkflowProtectedRuntimeReadinessLifecycleAttestationRequest:
    policy = code_owned_workflow_protected_runtime_readiness_authorization_policy()
    values: dict[str, object] = {}
    for field in fields(WorkflowProtectedRuntimeReadinessLifecycleAttestationRequest):
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
        elif name.endswith(("_usable_until", "_eligible_until", "_valid_until")):
            values[name] = NOW + timedelta(seconds=1)
        elif name.endswith("_at"):
            values[name] = NOW - timedelta(seconds=1)
        elif name.endswith(("_generation", "_count")):
            values[name] = 7 if name.endswith("_generation") else 1
        elif name.endswith(("_digest", "_commitment")):
            values[name] = canonical_digest({"field": name})
        elif name.endswith("_version"):
            values[name] = "1.0"
        elif name == "runtime_start_result_state":
            values[name] = "runtime_started_in_protected_boundary"
        elif name in {"runtime_lifecycle_state", "runtime_envelope_lifecycle_state"}:
            values[name] = "started"
        elif name.startswith(("is_", "has_")) or name.endswith(("_current", "_terminal", "_known")):
            values[name] = True
        else:
            values[name] = f"{name}.test"
    return WorkflowProtectedRuntimeReadinessLifecycleAttestationRequest(**cast(Any, values))


@pytest.mark.asyncio
async def test_development_attestor_binds_started_lineage_and_zero_effects() -> None:
    attestor = DeterministicDevelopmentWorkflowProtectedRuntimeReadinessLifecycleAttestor(
        development_enabled=True,
        clock=lambda: NOW,
    )
    request = _request()

    first = await attestor.attest_runtime_readiness_lifecycle(request)
    second = await attestor.attest_runtime_readiness_lifecycle(request)

    assert first == second
    assert first.request_nonce_digest == request.request_nonce_digest
    assert first.valid_until <= NOW + timedelta(seconds=2)
    assert first.runtime_envelope_eligible_until == NOW + timedelta(seconds=2)
    assert first.exact_start_result_confirmed is True
    assert first.runtime_started_confirmed is True
    assert first.runtime_envelope_started is True
    assert first.runtime_envelope_current is True
    assert first.destination_generation_current is True
    assert first.destination_fence_current is True
    assert first.protected_slot_generation_current is True
    assert first.readiness_profile_eligible is True
    assert first.prior_readiness_claim_absent is True
    assert first.prior_readiness_lease_absent is True
    assert first.prior_readiness_attempt_absent is True
    assert first.prior_readiness_result_absent is True

    request_names = {field.name for field in fields(request)} - {"requested_at"}
    attestation_names = {field.name for field in fields(first)}
    for name in request_names & attestation_names:
        assert getattr(first, name) == getattr(request, name)

    forbidden_effects = [
        getattr(first, field.name)
        for field in fields(first)
        if field.name.endswith(("_included", "_authorized", "_authority_granted", "_performed"))
    ]
    assert forbidden_effects
    assert all(value is False for value in forbidden_effects)
    assert attestor.verify_runtime_readiness_lifecycle_attestation(first) is True
    assert (
        attestor.verify_runtime_readiness_lifecycle_attestation(
            replace(first, request_nonce_digest="b" * 64)
        )
        is False
    )


@pytest.mark.asyncio
async def test_development_attestor_preserves_negative_currentness_and_history() -> None:
    attestor = DeterministicDevelopmentWorkflowProtectedRuntimeReadinessLifecycleAttestor(
        development_enabled=True,
        clock=lambda: NOW,
        runtime_started=False,
        destination_fence_current=False,
        readiness_profile_eligible=False,
        prior_readiness_attempt_absent=False,
    )

    evidence = await attestor.attest_runtime_readiness_lifecycle(_request())

    assert evidence.runtime_started_confirmed is False
    assert evidence.runtime_envelope_started is False
    assert evidence.destination_fence_current is False
    assert evidence.readiness_profile_eligible is False
    assert evidence.prior_readiness_attempt_absent is False
    assert attestor.verify_runtime_readiness_lifecycle_attestation(evidence) is True


@pytest.mark.asyncio
async def test_development_attestor_rejects_naive_clock() -> None:
    naive = DeterministicDevelopmentWorkflowProtectedRuntimeReadinessLifecycleAttestor(
        development_enabled=True,
        clock=lambda: NOW.replace(tzinfo=None),
    )
    with pytest.raises(WorkflowProtectedRuntimeReadinessAuthorizationError) as caught:
        await naive.attest_runtime_readiness_lifecycle(_request())
    assert caught.value.code == "workflow_protected_runtime_readiness_lifecycle_clock_must_be_aware"


@pytest.mark.asyncio
async def test_unavailable_and_disabled_attestors_fail_closed_without_request_leakage() -> None:
    request = _request()
    disabled = DeterministicDevelopmentWorkflowProtectedRuntimeReadinessLifecycleAttestor()
    unavailable = UnavailableWorkflowProtectedRuntimeReadinessLifecycleAttestor()

    for attestor in (disabled, unavailable):
        with pytest.raises(WorkflowProtectedRuntimeReadinessAuthorizationError) as caught:
            await attestor.attest_runtime_readiness_lifecycle(request)
        rendered = f"{caught.value} {caught.value.detail}"
        assert request.request_nonce_digest not in rendered
        if hasattr(attestor, "calls"):
            assert attestor.calls == []
        assert attestor.verify_runtime_readiness_lifecycle_attestation(cast(Any, None)) is False
