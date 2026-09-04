from __future__ import annotations

import pytest

from atlas.modules.mcp_plugin_sdk.domain.workflow_generated import (
    DEVELOPER_WORKFLOW_ORDER,
    DeveloperWorkflowStep,
    GeneratedProjectProvenance,
    generated_connector_receives_reduced_review_path,
    is_valid_next_step,
)


def test_developer_workflow_order_has_twelve_steps() -> None:
    assert len(DEVELOPER_WORKFLOW_ORDER) == 12
    assert len(set(DEVELOPER_WORKFLOW_ORDER)) == 12


def test_is_valid_next_step_true_for_first_step_with_no_completions() -> None:
    assert (
        is_valid_next_step(
            completed_steps=(), candidate=DeveloperWorkflowStep.SELECT_APPROVED_LANGUAGE_PROFILE
        )
        is True
    )


def test_is_valid_next_step_false_when_skipping_ahead() -> None:
    assert (
        is_valid_next_step(
            completed_steps=(), candidate=DeveloperWorkflowStep.RUN_CONNECTOR_VALIDATOR
        )
        is False
    )


def test_is_valid_next_step_true_for_second_step_after_first_completed() -> None:
    assert (
        is_valid_next_step(
            completed_steps=(DeveloperWorkflowStep.SELECT_APPROVED_LANGUAGE_PROFILE,),
            candidate=DeveloperWorkflowStep.GENERATE_PROJECT_SCAFFOLD,
        )
        is True
    )


def test_is_valid_next_step_false_when_workflow_already_complete() -> None:
    assert (
        is_valid_next_step(
            completed_steps=DEVELOPER_WORKFLOW_ORDER,
            candidate=DeveloperWorkflowStep.SELECT_APPROVED_LANGUAGE_PROFILE,
        )
        is False
    )


def test_generated_connector_never_receives_reduced_review_path() -> None:
    assert generated_connector_receives_reduced_review_path() is False


def test_generated_project_provenance_accepts_valid_state() -> None:
    provenance = GeneratedProjectProvenance(
        package_reference="connector.generated-example:v1.0.0",
        generator_id="mcp-builder.generator",
        generator_version="1.4.0",
        source_specification_reference="openapi-spec.example-vendor.v2",
    )
    assert provenance.generator_id == "mcp-builder.generator"


def test_generated_project_provenance_requires_source_specification() -> None:
    with pytest.raises(ValueError, match="source specification reference"):
        GeneratedProjectProvenance(
            package_reference="connector.generated-example:v1.0.0",
            generator_id="mcp-builder.generator",
            generator_version="1.4.0",
            source_specification_reference="",
        )
