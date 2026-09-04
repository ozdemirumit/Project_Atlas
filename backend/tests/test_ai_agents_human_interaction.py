from __future__ import annotations

import pytest

from atlas.modules.ai_agents.domain.human_interaction import (
    HumanInteractionKind,
    HumanInteractionRequest,
    can_use_persuasion_tactics_to_obtain_approval,
    human_interaction_request_can_grant_formal_approval,
)


def test_request_requires_prompt() -> None:
    with pytest.raises(ValueError, match="requires a prompt"):
        HumanInteractionRequest(
            request_id="human-interaction.example",
            task_id="task.example",
            kind=HumanInteractionKind.MISSING_TARGET_TIME_RANGE_SYMPTOM_OR_DESIRED_OUTCOME,
            prompt="",
        )


def test_request_accepts_valid_state() -> None:
    request = HumanInteractionRequest(
        request_id="human-interaction.example",
        task_id="task.example",
        kind=HumanInteractionKind.HUMAN_VALIDATION_OF_HYPOTHESIS_OR_RECOMMENDATION,
        prompt="Can you confirm fabric instability is a plausible cause here?",
    )
    assert request.kind is HumanInteractionKind.HUMAN_VALIDATION_OF_HYPOTHESIS_OR_RECOMMENDATION


def test_can_never_use_persuasion_tactics() -> None:
    assert can_use_persuasion_tactics_to_obtain_approval() is False


def test_human_interaction_request_never_grants_formal_approval() -> None:
    assert human_interaction_request_can_grant_formal_approval() is False
