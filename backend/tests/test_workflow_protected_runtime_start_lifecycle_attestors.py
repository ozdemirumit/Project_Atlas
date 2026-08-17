from __future__ import annotations

from dataclasses import fields, replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pytest

from atlas.modules.workflows.adapters.protected_runtime_start_lifecycle_attestors import (
    DeterministicDevelopmentWorkflowProtectedRuntimeStartLifecycleAttestor,
    UnavailableWorkflowProtectedRuntimeStartLifecycleAttestor,
)
from atlas.modules.workflows.application.protected_runtime_start_authorization_ports import (
    WorkflowProtectedRuntimeStartAuthorizationError,
    WorkflowProtectedRuntimeStartLifecycleAttestationRequest,
)
from atlas.modules.workflows.domain.models import WorkflowScope, canonical_digest
from atlas.modules.workflows.domain.protected_runtime_start_authorization_domain import (
    code_owned_workflow_protected_runtime_start_authorization_policy,
)

NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


def _request(
    *,
    nonce: str = "8" * 64,
    eligible_until: datetime | None = None,
) -> WorkflowProtectedRuntimeStartLifecycleAttestationRequest:
    policy = code_owned_workflow_protected_runtime_start_authorization_policy()
    values: dict[str, object] = {}
    for field in fields(WorkflowProtectedRuntimeStartLifecycleAttestationRequest):
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
        elif name.endswith(("_usable_until", "_eligible_until")):
            values[name] = eligible_until or NOW + timedelta(seconds=1)
        elif name.endswith("_at"):
            values[name] = NOW - timedelta(seconds=1)
        elif name.endswith(("_generation", "_count")):
            values[name] = 7 if name.endswith("_generation") else 1
        elif name.endswith(("_digest", "_commitment")):
            values[name] = canonical_digest({"field": name})
        elif name.endswith("_version"):
            values[name] = "1.0"
        elif name.startswith(("is_", "has_")) or name.endswith(
            ("_current", "_terminal", "_performed", "_known")
        ):
            values[name] = True
        else:
            values[name] = f"{name}.test"
    return WorkflowProtectedRuntimeStartLifecycleAttestationRequest(**cast(Any, values))


@pytest.mark.asyncio
async def test_development_attestor_returns_deterministic_nonce_bound_metadata_only_evidence() -> (
    None
):
    attestor = DeterministicDevelopmentWorkflowProtectedRuntimeStartLifecycleAttestor(
        development_enabled=True,
        clock=lambda: NOW,
    )
    request = _request()

    first = await attestor.attest_runtime_start_lifecycle(request)
    second = await attestor.attest_runtime_start_lifecycle(request)

    assert first == second
    assert first.request_nonce_digest == request.request_nonce_digest
    assert first.valid_until <= NOW + timedelta(seconds=2)
    assert first.exact_use_result_confirmed is True
    assert first.context_adoption_confirmed is True
    assert first.context_terminal_non_reusable is True
    assert first.runtime_envelope_current is True
    assert first.runtime_envelope_inactive is True
    assert first.runtime_not_started is True
    assert first.runtime_not_resumed is True
    assert first.process_not_created is True
    assert attestor.verify_runtime_start_lifecycle_attestation(first) is True
    assert (
        attestor.verify_runtime_start_lifecycle_attestation(
            replace(first, request_nonce_digest="9" * 64)
        )
        is False
    )

    request_names = {field.name for field in fields(request)} - {"requested_at"}
    attestation_names = {field.name for field in fields(first)}
    for name in request_names & attestation_names:
        assert getattr(first, name) == getattr(request, name)

    assert all(
        getattr(first, field.name) is False
        for field in fields(first)
        if field.name.endswith(("_included", "_authorized", "_authority_granted"))
    )


@pytest.mark.asyncio
async def test_development_attestor_binds_exact_lineage_and_negative_lifecycle_evidence() -> None:
    request = _request()
    safe = DeterministicDevelopmentWorkflowProtectedRuntimeStartLifecycleAttestor(
        development_enabled=True,
        clock=lambda: NOW,
    )
    negative = DeterministicDevelopmentWorkflowProtectedRuntimeStartLifecycleAttestor(
        development_enabled=True,
        clock=lambda: NOW,
        runtime_envelope_unstarted=False,
        destination_fence_current=False,
    )

    safe_evidence = await safe.attest_runtime_start_lifecycle(request)
    negative_evidence = await negative.attest_runtime_start_lifecycle(request)

    assert safe_evidence.integrity_signature != negative_evidence.integrity_signature
    assert negative.verify_runtime_start_lifecycle_attestation(negative_evidence) is True
    for name in ("runtime_envelope_unstarted", "runtime_unstarted"):
        if hasattr(negative_evidence, name):
            assert getattr(negative_evidence, name) is False
    assert negative_evidence.destination_fence_current is False

    lineage_digest_fields = [
        field.name
        for field in fields(safe_evidence)
        if field.name.endswith("_digest")
        and field.name not in {"canonical_digest", "request_nonce_digest"}
    ]
    assert lineage_digest_fields
    tampered = replace(
        safe_evidence,
        **cast(Any, {lineage_digest_fields[0]: "0" * 64}),
    )
    assert safe.verify_runtime_start_lifecycle_attestation(tampered) is False


@pytest.mark.asyncio
async def test_development_attestor_rejects_naive_clock() -> None:
    naive = DeterministicDevelopmentWorkflowProtectedRuntimeStartLifecycleAttestor(
        development_enabled=True,
        clock=lambda: NOW.replace(tzinfo=None),
    )
    with pytest.raises(WorkflowProtectedRuntimeStartAuthorizationError) as caught:
        await naive.attest_runtime_start_lifecycle(_request())
    assert caught.value.code == "workflow_protected_runtime_start_lifecycle_clock_must_be_aware"


@pytest.mark.asyncio
async def test_unavailable_and_disabled_attestors_fail_closed_without_request_leakage() -> None:
    request = _request()
    disabled = DeterministicDevelopmentWorkflowProtectedRuntimeStartLifecycleAttestor()
    unavailable = UnavailableWorkflowProtectedRuntimeStartLifecycleAttestor()

    for attestor in (disabled, unavailable):
        with pytest.raises(WorkflowProtectedRuntimeStartAuthorizationError) as caught:
            await attestor.attest_runtime_start_lifecycle(request)
        rendered = f"{caught.value} {caught.value.detail}"
        assert request.request_nonce_digest not in rendered
        if hasattr(attestor, "calls"):
            assert attestor.calls == []
        assert attestor.verify_runtime_start_lifecycle_attestation(cast(Any, None)) is False
