from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest

from atlas.modules.workflows.domain.protected_runtime_context_use_authorization_domain import (
    WorkflowProtectedRuntimeContextUseAuthorizationAuthority,
    code_owned_workflow_protected_runtime_context_use_authorization_policy,
)


def test_policy_is_code_owned_bounded_single_use_and_non_bearer() -> None:
    policy = code_owned_workflow_protected_runtime_context_use_authorization_policy()

    assert policy.maximum_lifetime_seconds == 1
    assert policy.single_use_required is True
    assert policy.renewable_allowed is False
    assert policy.transferable_allowed is False
    assert policy.bearer_capability_allowed is False
    assert policy.runtime_use_forbidden is True
    assert policy.runtime_start_forbidden is True
    assert policy.runtime_resume_forbidden is True
    assert policy.network_activity_forbidden is True
    assert policy.connector_activity_forbidden is True
    assert policy.execution_forbidden is True
    assert policy.infrastructure_mutation_forbidden is True


def test_authority_allows_only_the_dedicated_lease_declaration() -> None:
    authority = WorkflowProtectedRuntimeContextUseAuthorizationAuthority(
        protected_runtime_context_use_authority_granted=True
    )
    values = authority.canonical_value()

    assert values.pop("protected_runtime_context_use_authority_granted") is True
    assert not any(values.values())
    assert authority.runtime_use_authorized is False
    assert authority.runtime_start_authorized is False
    assert authority.runtime_resume_authorized is False
    assert authority.connector_activity_authorized is False
    assert authority.network_access_authorized is False
    assert authority.execution_authorized is False
    assert authority.infrastructure_mutation_authorized is False


@pytest.mark.parametrize(
    "field_name",
    [
        "runtime_use_authorized",
        "runtime_start_authorized",
        "runtime_resume_authorized",
        "connector_activity_authorized",
        "network_access_authorized",
        "readiness_probe_authorized",
        "publication_authorized",
        "delivery_authorized",
        "dispatch_authorized",
        "execution_authorized",
        "infrastructure_mutation_authorized",
    ],
)
def test_authority_rejects_every_operational_capability(field_name: str) -> None:
    values = {
        field.name: False
        for field in fields(WorkflowProtectedRuntimeContextUseAuthorizationAuthority)
    }
    values[field_name] = True

    with pytest.raises(ValueError):
        WorkflowProtectedRuntimeContextUseAuthorizationAuthority(**values)


def test_authority_is_immutable() -> None:
    authority = WorkflowProtectedRuntimeContextUseAuthorizationAuthority()

    with pytest.raises(FrozenInstanceError):
        authority.runtime_use_authorized = True  # type: ignore[misc]
