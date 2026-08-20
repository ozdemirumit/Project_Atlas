from dataclasses import FrozenInstanceError, fields

import pytest

from atlas.modules.workflows.domain.models import canonical_digest
from atlas.modules.workflows.domain.protected_runtime_process_creation_consumption_domain import (
    WorkflowProtectedRuntimeProcessCreationConsumptionAuthority,
    WorkflowProtectedRuntimeProcessCreationInstruction,
    code_owned_workflow_protected_runtime_process_creation_consumption_policy,
    code_owned_workflow_protected_runtime_process_creation_consumption_policy_values,
)


def test_policy_is_fixed_single_call_non_retrying_and_side_effect_bounded() -> None:
    policy = code_owned_workflow_protected_runtime_process_creation_consumption_policy()

    assert policy.claim_and_attempt_atomic_required is True
    assert policy.commit_before_creator_io_required is True
    assert policy.at_most_one_creator_call_required is True
    assert policy.automatic_retry_allowed is False
    assert policy.exact_replay_no_io_required is True
    assert policy.sealed_process_required is True
    assert policy.suspended_process_required is True
    assert policy.caller_material_forbidden is True
    assert policy.scheduling_forbidden is True
    assert policy.resume_forbidden is True
    assert policy.dispatch_forbidden is True
    assert policy.execution_forbidden is True
    assert policy.network_activity_forbidden is True
    assert policy.model_activity_forbidden is True
    assert policy.mcp_activity_forbidden is True
    assert policy.connector_activity_forbidden is True
    assert policy.provider_activity_forbidden is True
    assert policy.infrastructure_mutation_forbidden is True


def test_primitive_digest_binds_code_owned_process_image_and_manifest() -> None:
    values = code_owned_workflow_protected_runtime_process_creation_consumption_policy_values()
    image_digest = canonical_digest(
        {
            "image_id": "image.workflow-protected-runtime-sealed-process",
            "image_version": "1.0",
            "immutable": True,
        }
    )
    manifest_digest = canonical_digest(
        {
            "manifest_id": "manifest.workflow-protected-runtime-sealed-process",
            "manifest_version": "1.0",
            "process_image_digest": image_digest,
            "caller_material": False,
            "network_enabled": False,
            "initial_state": "suspended_non_runnable",
        }
    )

    assert values["primitive_digest"] == canonical_digest(
        {
            "primitive_id": "primitive.workflow-protected-runtime-create-sealed-suspended-process",
            "primitive_version": "1.0",
            "process_creation_profile_digest": values["process_creation_profile_digest"],
            "process_image_digest": image_digest,
            "process_manifest_digest": manifest_digest,
            "sealed": True,
            "suspended": True,
            "caller_material": False,
        }
    )


def test_consumed_authority_is_immutable_and_every_declaration_is_false() -> None:
    authority = WorkflowProtectedRuntimeProcessCreationConsumptionAuthority()

    assert len(fields(authority)) == 29
    assert not any(authority.canonical_value().values())
    with pytest.raises(FrozenInstanceError):
        authority.execution_authorized = True  # type: ignore[misc]


@pytest.mark.parametrize(
    "field_name",
    [field.name for field in fields(WorkflowProtectedRuntimeProcessCreationConsumptionAuthority)],
)
def test_consumed_authority_rejects_every_true_declaration(field_name: str) -> None:
    with pytest.raises(ValueError, match="grants no authority"):
        WorkflowProtectedRuntimeProcessCreationConsumptionAuthority(**{field_name: True})


def test_instruction_has_no_caller_supplied_process_or_runtime_material() -> None:
    names = {field.name for field in fields(WorkflowProtectedRuntimeProcessCreationInstruction)}

    assert names.isdisjoint(
        {
            "command",
            "executable",
            "arguments",
            "args",
            "environment",
            "env",
            "working_directory",
            "runtime_locator",
            "runtime_material",
        }
    )
