from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import pytest

from atlas.modules.workflows.domain import (
    WorkflowEventPhysicalTransportTargetContextBinding,
    WorkflowEventPhysicalTransportTargetContextBindingAuthority,
    WorkflowEventPhysicalTransportTargetContextBindingEffectiveState,
    WorkflowEventPhysicalTransportTargetContextBindingPolicy,
    WorkflowEventPhysicalTransportTargetContextBindingState,
    WorkflowScope,
    canonical_digest,
    code_owned_workflow_event_physical_transport_target_context_binding_policy,
)

NOW = datetime(2026, 8, 15, 20, 0, tzinfo=UTC)
SCOPE = WorkflowScope("org-atlas", "environment-lab", "site-istanbul")


def canonical_payload(values: dict[str, object]) -> dict[str, object]:
    payload: dict[str, object] = {}
    for name, value in values.items():
        if isinstance(value, datetime):
            payload[name] = value.isoformat()
        elif isinstance(value, StrEnum):
            payload[name] = value.value
        elif isinstance(
            value,
            (
                WorkflowScope,
                WorkflowEventPhysicalTransportTargetContextBindingAuthority,
            ),
        ):
            payload[name] = value.canonical_value()
        else:
            payload[name] = value
    return payload


def binding_values() -> dict[str, object]:
    policy = code_owned_workflow_event_physical_transport_target_context_binding_policy()
    return {
        "binding_id": "workflow-physical-transport-target-context-binding.primary",
        "physical_transport_route_binding_id": (
            "workflow-event-physical-transport-route-binding.primary"
        ),
        "physical_transport_route_binding_digest": "1" * 64,
        "transport_route_snapshot_id": "event-physical-transport-route-snapshot.primary",
        "transport_route_snapshot_digest": "2" * 64,
        "endpoint_materialization_id": "workflow-endpoint-materialization.primary",
        "endpoint_materialization_digest": "3" * 64,
        "physical_transport_credential_assignment_binding_id": (
            "workflow-physical-transport-credential-assignment-binding.primary"
        ),
        "physical_transport_credential_assignment_binding_digest": "4" * 64,
        "credential_assignment_snapshot_id": (
            "event-physical-transport-credential-assignment-snapshot.primary"
        ),
        "credential_assignment_snapshot_digest": "5" * 64,
        "credential_materialization_id": "workflow-credential-materialization.primary",
        "credential_materialization_digest": "6" * 64,
        "resolver_subject_id": "workload.workflow-physical-transport-endpoint-resolver",
        "accessor_subject_id": "workload.workflow-physical-transport-credential-accessor",
        "target_context_schema_id": policy.target_context_schema_id,
        "target_context_schema_version": policy.target_context_schema_version,
        "target_context_commitment": "7" * 64,
        "scope": SCOPE,
        "binder_subject_id": "workload.workflow-physical-transport-target-context-binder",
        "bound_at": NOW,
        "joint_usable_until": NOW + timedelta(seconds=8),
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "policy_digest": policy.canonical_digest,
        "state": WorkflowEventPhysicalTransportTargetContextBindingState.BOUND,
        "authority": WorkflowEventPhysicalTransportTargetContextBindingAuthority(),
    }


def make_binding(**changes: object) -> WorkflowEventPhysicalTransportTargetContextBinding:
    values = {**binding_values(), **changes}
    return WorkflowEventPhysicalTransportTargetContextBinding(
        **values,
        canonical_digest=canonical_digest(canonical_payload(values)),
    )


def test_code_owned_policy_v1_requires_versioned_safe_binding_contract() -> None:
    policy = code_owned_workflow_event_physical_transport_target_context_binding_policy()

    assert policy.policy_version == "1.0"
    assert policy.target_context_schema_id == ("schema.workflow-physical-transport-target-context")
    assert policy.target_context_schema_version == "1.0"
    assert policy.successful_endpoint_materialization_required is True
    assert policy.successful_credential_materialization_required is True
    assert policy.exact_route_lineage_required is True
    assert policy.unexpired_overlap_required is True
    assert policy.one_binding_per_source_required is True
    assert policy.canonical_digest == canonical_digest(policy.digest_payload())
    assert policy.canonical_value()["canonical_digest"] == policy.canonical_digest

    unsafe = {**policy.digest_payload(), "exact_route_lineage_required": False}
    with pytest.raises(ValueError, match="requirements must remain enabled"):
        WorkflowEventPhysicalTransportTargetContextBindingPolicy(
            **unsafe,
            canonical_digest=canonical_digest(unsafe),
        )


def test_authority_requires_exactly_seventeen_false_declarations() -> None:
    authority = WorkflowEventPhysicalTransportTargetContextBindingAuthority()

    assert len(authority.canonical_value()) == 17
    assert set(authority.canonical_value().values()) == {False}
    with pytest.raises(ValueError, match="cannot grant authority"):
        WorkflowEventPhysicalTransportTargetContextBindingAuthority(
            protected_artifact_access_authorized=True
        )
    with pytest.raises(ValueError, match="cannot grant authority"):
        WorkflowEventPhysicalTransportTargetContextBindingAuthority(network_access_authorized=True)
    with pytest.raises(ValueError, match="cannot grant authority"):
        WorkflowEventPhysicalTransportTargetContextBindingAuthority(
            execution_authorized=0  # type: ignore[arg-type]
        )


def test_binding_is_immutable_canonical_and_contains_only_opaque_lineage() -> None:
    binding = make_binding()

    assert binding.canonical_digest == canonical_digest(binding.digest_payload())
    assert binding.canonical_value()["canonical_digest"] == binding.canonical_digest
    assert binding.resolver_subject_id != binding.accessor_subject_id
    assert binding.state is WorkflowEventPhysicalTransportTargetContextBindingState.BOUND
    with pytest.raises(FrozenInstanceError):
        binding.binding_id = "changed"  # type: ignore[misc]

    model_fields = {field.name for field in fields(type(binding))}
    forbidden = {
        "endpoint",
        "hostname",
        "url",
        "ip_address",
        "port",
        "username",
        "password",
        "token",
        "private_key",
        "certificate",
        "secret",
        "secret_locator",
        "vault_path",
        "protected_artifact_id",
        "protected_artifact_digest",
        "provider_payload",
    }
    assert forbidden.isdisjoint(model_fields)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"binding_id": ""}, "target context binding id"),
        (
            {"bound_at": datetime(2026, 8, 15, 20, 0)},
            "times must be timezone-aware",
        ),
        (
            {"joint_usable_until": NOW},
            "requires an unexpired usable overlap",
        ),
        (
            {"state": "bound"},
            "must remain bound",
        ),
        (
            {
                "authority": WorkflowEventPhysicalTransportTargetContextBindingAuthority(),
                "target_context_commitment": "invalid",
            },
            "target context commitment",
        ),
    ],
)
def test_binding_validation_fails_closed(changes: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        make_binding(**changes)

    binding = make_binding()
    with pytest.raises(ValueError, match="canonical digest mismatch"):
        replace(binding, endpoint_materialization_digest="8" * 64)


def test_effective_state_is_active_only_inside_joint_usable_window() -> None:
    binding = make_binding()

    assert (
        binding.effective_state(evaluated_at=binding.bound_at - timedelta(microseconds=1))
        is WorkflowEventPhysicalTransportTargetContextBindingEffectiveState.EXPIRED
    )
    assert (
        binding.effective_state(evaluated_at=binding.bound_at)
        is WorkflowEventPhysicalTransportTargetContextBindingEffectiveState.ACTIVE
    )
    assert (
        binding.effective_state(evaluated_at=binding.joint_usable_until - timedelta(microseconds=1))
        is WorkflowEventPhysicalTransportTargetContextBindingEffectiveState.ACTIVE
    )
    assert (
        binding.effective_state(evaluated_at=binding.joint_usable_until)
        is WorkflowEventPhysicalTransportTargetContextBindingEffectiveState.EXPIRED
    )
    with pytest.raises(ValueError, match="evaluation time must be aware"):
        binding.effective_state(evaluated_at=datetime(2026, 8, 15, 20, 0))
