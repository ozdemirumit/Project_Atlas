from dataclasses import FrozenInstanceError, fields

import pytest

from atlas.modules.workflows.domain.models import canonical_digest
from atlas.modules.workflows.domain.protected_runtime_process_scheduling_consumption_domain import (
    WorkflowProtectedRuntimeProcessSchedulingConsumptionAuthority,
    WorkflowProtectedRuntimeProcessSchedulingInstruction,
    code_owned_workflow_protected_runtime_process_scheduling_consumption_policy,
    code_owned_workflow_protected_runtime_process_scheduling_consumption_policy_values,
)


def test_policy_is_atomic_single_call_non_retrying_and_side_effect_bounded() -> None:
    policy = code_owned_workflow_protected_runtime_process_scheduling_consumption_policy()

    assert policy.claim_and_attempt_atomic_required is True
    assert policy.commit_before_scheduler_io_required is True
    assert policy.at_most_one_scheduler_call_required is True
    assert policy.automatic_retry_allowed is False
    assert policy.exact_replay_no_io_required is True
    assert policy.suspended_process_required is True
    assert policy.non_runnable_process_required is True
    assert policy.caller_process_material_forbidden is True
    assert policy.caller_runtime_material_forbidden is True
    assert policy.caller_command_material_forbidden is True
    assert policy.caller_scheduler_selection_forbidden is True
    assert policy.caller_queue_selection_forbidden is True
    assert policy.caller_priority_selection_forbidden is True
    assert policy.caller_affinity_selection_forbidden is True
    assert policy.caller_resource_selection_forbidden is True
    assert policy.resume_forbidden is True
    assert policy.dispatch_forbidden is True
    assert policy.execution_forbidden is True
    assert policy.network_activity_forbidden is True
    assert policy.model_activity_forbidden is True
    assert policy.mcp_activity_forbidden is True
    assert policy.connector_activity_forbidden is True
    assert policy.provider_activity_forbidden is True
    assert policy.infrastructure_mutation_forbidden is True


def test_primitive_digest_binds_internal_resolution_and_no_caller_choices() -> None:
    values = code_owned_workflow_protected_runtime_process_scheduling_consumption_policy_values()

    assert values["primitive_digest"] == canonical_digest(
        {
            "primitive_id": (
                "primitive.workflow-protected-runtime-schedule-sealed-suspended-process"
            ),
            "primitive_version": "1.0",
            "scheduling_profile_digest": values["scheduling_profile_digest"],
            "process_resolution": "protected_boundary_internal",
            "process_locator_in_instruction": False,
            "process_identifier_in_instruction": False,
            "caller_scheduler_selection": False,
            "caller_queue_selection": False,
            "caller_priority_selection": False,
            "caller_affinity_selection": False,
            "caller_resource_selection": False,
            "resulting_state": "scheduled_suspended_non_runnable",
        }
    )


def test_consumed_authority_is_immutable_and_every_declaration_is_false() -> None:
    authority = WorkflowProtectedRuntimeProcessSchedulingConsumptionAuthority()

    assert len(fields(authority)) == 30
    assert not any(authority.canonical_value().values())
    with pytest.raises(FrozenInstanceError):
        authority.execution_authorized = True  # type: ignore[misc]


@pytest.mark.parametrize(
    "field_name",
    [field.name for field in fields(WorkflowProtectedRuntimeProcessSchedulingConsumptionAuthority)],
)
def test_consumed_authority_rejects_every_true_declaration(field_name: str) -> None:
    with pytest.raises(ValueError, match="grants no authority"):
        WorkflowProtectedRuntimeProcessSchedulingConsumptionAuthority(**{field_name: True})


def test_signed_instruction_has_no_process_locator_or_scheduler_choices() -> None:
    names = {field.name for field in fields(WorkflowProtectedRuntimeProcessSchedulingInstruction)}

    assert names.isdisjoint(
        {
            "process_locator",
            "process_identifier",
            "process_handle",
            "runtime_locator",
            "runtime_handle",
            "command",
            "executable",
            "arguments",
            "args",
            "environment",
            "env",
            "working_directory",
            "scheduler",
            "queue",
            "priority",
            "affinity",
            "resources",
        }
    )
