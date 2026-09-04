"""ATLAS-040 SS17: human interaction."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class HumanInteractionKind(StrEnum):
    """SS17's five request kinds."""

    MISSING_TARGET_TIME_RANGE_SYMPTOM_OR_DESIRED_OUTCOME = (
        "missing_target_time_range_symptom_or_desired_outcome"
    )
    PERMISSION_FOR_ELIGIBLE_BOUNDED_READ_OR_DIAGNOSTIC = (
        "permission_for_eligible_bounded_read_or_diagnostic"
    )
    CONFIRMATION_OF_AMBIGUOUS_ENVIRONMENT_CONTEXT = "confirmation_of_ambiguous_environment_context"
    HUMAN_VALIDATION_OF_HYPOTHESIS_OR_RECOMMENDATION = (
        "human_validation_of_hypothesis_or_recommendation"
    )
    REVIEW_OF_GENERATED_CONTENT = "review_of_generated_content"


@dataclass(frozen=True, slots=True)
class HumanInteractionRequest:
    """No field here can represent granting formal approval -- see
    `human_interaction_request_can_grant_formal_approval` below."""

    request_id: str
    task_id: str
    kind: HumanInteractionKind
    prompt: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.request_id, "request_id")
        validate_stable_identifier(self.task_id, "task_id")
        if not self.prompt.strip():
            raise ValueError("a human interaction request requires a prompt")


def can_use_persuasion_tactics_to_obtain_approval() -> bool:
    """SS17: "agents must not use urgency, authority claims, or fabricated certainty to obtain
    approval.\""""
    return False


def human_interaction_request_can_grant_formal_approval() -> bool:
    """SS17: "the UI separates conversation from formal ATLAS-037 approval.\""""
    return False
