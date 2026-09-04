from __future__ import annotations

import pytest

from atlas.modules.guardrails.domain.instruction_hierarchy import (
    InstructionHierarchyViolation,
    InstructionSource,
    can_override,
    effective_source,
    require_no_precedence_violation,
)


def test_precedence_values_match_the_documents_own_numbering() -> None:
    assert InstructionSource.PLATFORM_INVARIANT.value == 1
    assert InstructionSource.APPROVED_SYSTEM_OR_AGENT_DEFINITION.value == 2
    assert InstructionSource.AUTHORIZED_ORGANIZATION_POLICY_OR_TASK_CONTRACT.value == 3
    assert InstructionSource.GOVERNED_WORKFLOW_INSTRUCTION.value == 4
    assert InstructionSource.AUTHENTICATED_USER_REQUEST.value == 5
    assert InstructionSource.RETRIEVED_OR_TOOL_PROVIDED_CONTENT.value == 6


def test_only_retrieved_or_tool_provided_content_is_data_only() -> None:
    for source in InstructionSource:
        expected = source is InstructionSource.RETRIEVED_OR_TOOL_PROVIDED_CONTENT
        assert source.is_data_only is expected


def test_effective_source_ignores_any_claim() -> None:
    # Content claiming to be a platform invariant but actually arriving as retrieved content
    # is still treated as retrieved content -- the claim has zero effect on the outcome.
    result = effective_source(
        claimed_source=InstructionSource.PLATFORM_INVARIANT,
        actual_channel=InstructionSource.RETRIEVED_OR_TOOL_PROVIDED_CONTENT,
    )
    assert result is InstructionSource.RETRIEVED_OR_TOOL_PROVIDED_CONTENT


def test_effective_source_with_no_claim_at_all() -> None:
    result = effective_source(
        claimed_source=None, actual_channel=InstructionSource.AUTHENTICATED_USER_REQUEST
    )
    assert result is InstructionSource.AUTHENTICATED_USER_REQUEST


def test_a_source_can_override_itself() -> None:
    assert can_override(
        acting_source=InstructionSource.AUTHENTICATED_USER_REQUEST,
        target_source=InstructionSource.AUTHENTICATED_USER_REQUEST,
    )


def test_a_source_can_override_a_lower_precedence_target() -> None:
    assert can_override(
        acting_source=InstructionSource.GOVERNED_WORKFLOW_INSTRUCTION,
        target_source=InstructionSource.RETRIEVED_OR_TOOL_PROVIDED_CONTENT,
    )


def test_a_source_cannot_override_a_higher_precedence_target() -> None:
    assert not can_override(
        acting_source=InstructionSource.RETRIEVED_OR_TOOL_PROVIDED_CONTENT,
        target_source=InstructionSource.PLATFORM_INVARIANT,
    )


def test_retrieved_content_cannot_override_the_current_user_request() -> None:
    assert not can_override(
        acting_source=InstructionSource.RETRIEVED_OR_TOOL_PROVIDED_CONTENT,
        target_source=InstructionSource.AUTHENTICATED_USER_REQUEST,
    )


def test_require_no_precedence_violation_passes_silently_when_allowed() -> None:
    require_no_precedence_violation(
        acting_source=InstructionSource.AUTHENTICATED_USER_REQUEST,
        target_source=InstructionSource.RETRIEVED_OR_TOOL_PROVIDED_CONTENT,
    )


def test_require_no_precedence_violation_raises_when_disallowed() -> None:
    with pytest.raises(InstructionHierarchyViolation) as excinfo:
        require_no_precedence_violation(
            acting_source=InstructionSource.RETRIEVED_OR_TOOL_PROVIDED_CONTENT,
            target_source=InstructionSource.PLATFORM_INVARIANT,
        )
    assert excinfo.value.acting_source is InstructionSource.RETRIEVED_OR_TOOL_PROVIDED_CONTENT
    assert excinfo.value.target_source is InstructionSource.PLATFORM_INVARIANT


def test_no_source_can_ever_override_a_platform_invariant_except_itself() -> None:
    for source in InstructionSource:
        if source is InstructionSource.PLATFORM_INVARIANT:
            assert can_override(
                acting_source=source, target_source=InstructionSource.PLATFORM_INVARIANT
            )
        else:
            assert not can_override(
                acting_source=source, target_source=InstructionSource.PLATFORM_INVARIANT
            )
