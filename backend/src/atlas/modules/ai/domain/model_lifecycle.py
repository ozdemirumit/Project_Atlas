"""ATLAS-014 SS19: Model Lifecycle.

`ModelEndpointProfile.lifecycle`/`evaluation_status` (`domain/models.py`) are narrow runtime
gating flags `ModelGateway` checks before every invocation -- "is this endpoint switched on" and
"has it passed evaluation at all." SS19.1's seven-state lifecycle is a broader governance concept
over introducing, approving-for-a-tier, and eventually retiring a model *version* -- a distinct
concern this module represents on its own rather than forcing onto the gateway's narrower fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier

_NON_IMMUTABLE_ALIASES = frozenset({"latest", "current", "stable", "default"})


class ModelLifecycleStage(StrEnum):
    """SS19.1's seven named states."""

    REGISTERED = "registered"
    UNDER_EVALUATION = "under_evaluation"
    APPROVED_FOR_RESTRICTED_TASKS = "approved_for_restricted_tasks"
    APPROVED_FOR_PRODUCTION_TASKS = "approved_for_production_tasks"
    SUSPENDED = "suspended"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


_MODEL_LIFECYCLE_TRANSITIONS: dict[ModelLifecycleStage, frozenset[ModelLifecycleStage]] = {
    ModelLifecycleStage.REGISTERED: frozenset({ModelLifecycleStage.UNDER_EVALUATION}),
    ModelLifecycleStage.UNDER_EVALUATION: frozenset(
        {
            ModelLifecycleStage.APPROVED_FOR_RESTRICTED_TASKS,
            ModelLifecycleStage.APPROVED_FOR_PRODUCTION_TASKS,
            ModelLifecycleStage.RETIRED,
        }
    ),
    ModelLifecycleStage.APPROVED_FOR_RESTRICTED_TASKS: frozenset(
        {
            ModelLifecycleStage.APPROVED_FOR_PRODUCTION_TASKS,
            ModelLifecycleStage.SUSPENDED,
            ModelLifecycleStage.DEPRECATED,
        }
    ),
    ModelLifecycleStage.APPROVED_FOR_PRODUCTION_TASKS: frozenset(
        {
            ModelLifecycleStage.SUSPENDED,
            ModelLifecycleStage.DEPRECATED,
        }
    ),
    ModelLifecycleStage.SUSPENDED: frozenset(
        {
            ModelLifecycleStage.APPROVED_FOR_RESTRICTED_TASKS,
            ModelLifecycleStage.APPROVED_FOR_PRODUCTION_TASKS,
            ModelLifecycleStage.DEPRECATED,
            ModelLifecycleStage.RETIRED,
        }
    ),
    ModelLifecycleStage.DEPRECATED: frozenset({ModelLifecycleStage.RETIRED}),
    ModelLifecycleStage.RETIRED: frozenset(),
}


def is_valid_model_lifecycle_transition(
    current: ModelLifecycleStage, target: ModelLifecycleStage
) -> bool:
    """SS19.1's seven-state lifecycle, reproduced as an explicit adjacency table (mirrors
    `RunbookLifecycleState`'s and `GuardrailLifecycleStage`'s established pattern)."""
    return target in _MODEL_LIFECYCLE_TRANSITIONS[current]


@dataclass(frozen=True, slots=True)
class ModelVersionChangeRecord:
    """SS19.2: "a model or endpoint version change requires" seven named elements."""

    change_id: str
    model_id: str
    prior_version: str
    new_version: str
    identity_and_capability_comparison: str
    evaluation_suite_reference: str
    hosting_or_behavior_changed: bool
    security_privacy_review_reference: str | None
    compatibility_validation_reference: str
    performance_capacity_validation_reference: str
    rollback_readiness_reference: str
    release_note: str
    affected_agent_ids: tuple[str, ...]
    recorded_by: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        for value, name in (
            (self.change_id, "change_id"),
            (self.model_id, "model_id"),
            (self.recorded_by, "recorded_by"),
        ):
            validate_stable_identifier(value, name)
        required = (
            self.prior_version,
            self.new_version,
            self.identity_and_capability_comparison,
            self.evaluation_suite_reference,
            self.compatibility_validation_reference,
            self.performance_capacity_validation_reference,
            self.rollback_readiness_reference,
            self.release_note,
        )
        if not all(value.strip() for value in required):
            raise ValueError(
                "a model version change record requires every SS19.2 change-control element"
            )
        if self.new_version.strip().lower() in _NON_IMMUTABLE_ALIASES:
            raise ValueError(
                "aliases such as 'latest' are not sufficient production model identities unless"
                " resolved and recorded to an immutable version"
            )
        if self.hosting_or_behavior_changed:
            if not (
                self.security_privacy_review_reference is not None
                and self.security_privacy_review_reference.strip()
            ):
                raise ValueError(
                    "a security and privacy review is required when hosting or behavior changes"
                )
        elif self.security_privacy_review_reference is not None:
            raise ValueError(
                "a security and privacy review reference is only recorded when hosting or"
                " behavior actually changed"
            )
        if self.recorded_at.tzinfo is None:
            raise ValueError("model version change time must be timezone-aware")


def a_non_immutable_model_alias_is_recorded_as_a_production_model_identity() -> bool:
    """SS19.2: "Aliases such as `latest` are not sufficient production model identities unless
    resolved and recorded to an immutable version." `ModelVersionChangeRecord` makes recording a
    known mutable alias as `new_version` unconstructable."""
    return False
