from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest

from atlas.modules.workflows.domain.protected_runtime_readiness_authorization_domain import (
    WorkflowProtectedRuntimeReadinessAuthorizationAuthority,
    code_owned_workflow_protected_runtime_readiness_authorization_policy,
)


def test_policy_is_code_owned_bounded_single_use_and_non_bearer() -> None:
    policy = code_owned_workflow_protected_runtime_readiness_authorization_policy()

    assert policy.required_source_state == "runtime_started_in_protected_boundary"
    assert policy.maximum_lifetime_seconds == 1
    assert policy.maximum_attestation_freshness_seconds == 1
    assert policy.single_use_required is True
    assert policy.renewable_allowed is False
    assert policy.transferable_allowed is False
    assert policy.bearer_capability_allowed is False
    assert policy.durable_replay_required is True
    assert policy.fresh_attestation_required is True
    assert policy.runtime_start_forbidden is True
    assert policy.runtime_resume_forbidden is True
    assert policy.process_control_forbidden is True
    assert policy.scheduling_forbidden is True
    assert policy.readiness_probe_forbidden is True
    assert policy.network_activity_forbidden is True
    assert policy.connector_activity_forbidden is True
    assert policy.execution_forbidden is True
    assert policy.infrastructure_mutation_forbidden is True


def test_authority_grants_only_future_readiness_request_submission() -> None:
    authority = WorkflowProtectedRuntimeReadinessAuthorizationAuthority(
        protected_runtime_readiness_authority_granted=True
    )
    values = authority.canonical_value()

    assert len(values) == 28
    assert values.pop("protected_runtime_readiness_authority_granted") is True
    assert not any(values.values())
    assert authority.readiness_probe_authorized is False
    assert authority.network_access_authorized is False
    assert authority.connector_activity_authorized is False
    assert authority.runtime_start_authorized is False
    assert authority.runtime_resume_authorized is False
    assert authority.execution_authorized is False
    assert authority.infrastructure_mutation_authorized is False


@pytest.mark.parametrize(
    "field_name",
    [
        field.name
        for field in fields(WorkflowProtectedRuntimeReadinessAuthorizationAuthority)
        if field.name != "protected_runtime_readiness_authority_granted"
    ],
)
def test_authority_rejects_every_preexisting_authority(field_name: str) -> None:
    values = {
        field.name: False
        for field in fields(WorkflowProtectedRuntimeReadinessAuthorizationAuthority)
    }
    values[field_name] = True

    with pytest.raises(ValueError):
        WorkflowProtectedRuntimeReadinessAuthorizationAuthority(**values)


def test_authority_is_immutable() -> None:
    authority = WorkflowProtectedRuntimeReadinessAuthorizationAuthority()

    with pytest.raises(FrozenInstanceError):
        authority.readiness_probe_authorized = True  # type: ignore[misc]
