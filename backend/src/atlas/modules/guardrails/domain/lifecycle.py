"""ATLAS-047 SS27: Guardrail Lifecycle.

"Invariant enforcement cannot be placed indefinitely in observe-only mode." SS7 already frames
invariants even more strongly than that ("must always hold; violation stops operation"), and
`GuardrailDecision.__post_init__` already limits an invariant's outcome to pass/block, never warn
-- so this module goes further and makes an invariant-class guardrail unconstructable in anything
but `ENFORCE` deployment mode at all, rather than merely forbidding it being left there forever.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.guardrails.domain.models import GuardrailClass
from atlas.modules.identity.domain.models import validate_stable_identifier


class GuardrailLifecycleStage(StrEnum):
    """SS27's eight-step lifecycle."""

    DRAFT = "draft"
    IMPLEMENTED = "implemented"
    TESTED = "tested"
    REVIEWED = "reviewed"
    APPROVED_PUBLISHED = "approved_published"
    DEPLOYED = "deployed"
    MONITORED = "monitored"
    UPGRADED = "upgraded"
    ROLLED_BACK = "rolled_back"
    SUSPENDED = "suspended"
    RETIRED = "retired"


_LIFECYCLE_TRANSITIONS: dict[GuardrailLifecycleStage, frozenset[GuardrailLifecycleStage]] = {
    GuardrailLifecycleStage.DRAFT: frozenset({GuardrailLifecycleStage.IMPLEMENTED}),
    GuardrailLifecycleStage.IMPLEMENTED: frozenset({GuardrailLifecycleStage.TESTED}),
    GuardrailLifecycleStage.TESTED: frozenset(
        {GuardrailLifecycleStage.REVIEWED, GuardrailLifecycleStage.IMPLEMENTED}
    ),
    GuardrailLifecycleStage.REVIEWED: frozenset(
        {GuardrailLifecycleStage.APPROVED_PUBLISHED, GuardrailLifecycleStage.IMPLEMENTED}
    ),
    GuardrailLifecycleStage.APPROVED_PUBLISHED: frozenset({GuardrailLifecycleStage.DEPLOYED}),
    GuardrailLifecycleStage.DEPLOYED: frozenset({GuardrailLifecycleStage.MONITORED}),
    GuardrailLifecycleStage.MONITORED: frozenset(
        {
            GuardrailLifecycleStage.UPGRADED,
            GuardrailLifecycleStage.ROLLED_BACK,
            GuardrailLifecycleStage.SUSPENDED,
            GuardrailLifecycleStage.RETIRED,
        }
    ),
    GuardrailLifecycleStage.UPGRADED: frozenset({GuardrailLifecycleStage.DRAFT}),
    GuardrailLifecycleStage.ROLLED_BACK: frozenset({GuardrailLifecycleStage.MONITORED}),
    GuardrailLifecycleStage.SUSPENDED: frozenset(
        {GuardrailLifecycleStage.MONITORED, GuardrailLifecycleStage.RETIRED}
    ),
    GuardrailLifecycleStage.RETIRED: frozenset(),
}


def is_valid_guardrail_lifecycle_transition(
    current: GuardrailLifecycleStage, target: GuardrailLifecycleStage
) -> bool:
    """SS27's eight-step lifecycle, reproduced as an explicit adjacency table (mirrors
    `RunbookLifecycleState`'s and `is_valid_transition`'s established pattern elsewhere)."""
    return target in _LIFECYCLE_TRANSITIONS[current]


class GuardrailDeploymentMode(StrEnum):
    """SS27: "Deploy in observe, warn, or enforce mode only where the class permits staged
    rollout.\""""

    OBSERVE = "observe"
    WARN = "warn"
    ENFORCE = "enforce"


@dataclass(frozen=True, slots=True)
class GuardrailLifecycleRecord:
    """SS27 step 1's draft contract (owner, threat, scope, behavior, false-positive risk) plus
    the rule's current stage and deployment mode."""

    rule_id: str
    rule_version: int
    guardrail_class: GuardrailClass
    stage: GuardrailLifecycleStage
    deployment_mode: GuardrailDeploymentMode | None
    owner: str
    threat: str
    scope: str
    behavior: str
    false_positive_risk: str
    updated_at: datetime
    updated_by: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.rule_id, "rule_id")
        if self.rule_version < 1:
            raise ValueError("guardrail rule_version must be positive")
        required = (self.owner, self.threat, self.scope, self.behavior, self.false_positive_risk)
        if not all(value.strip() for value in required):
            raise ValueError(
                "a guardrail lifecycle record requires owner, threat, scope, behavior, and "
                "false-positive risk"
            )
        if self.updated_at.tzinfo is None:
            raise ValueError("guardrail lifecycle timestamps must be timezone-aware")
        deployed_stages = frozenset(
            {
                GuardrailLifecycleStage.DEPLOYED,
                GuardrailLifecycleStage.MONITORED,
                GuardrailLifecycleStage.ROLLED_BACK,
            }
        )
        if self.stage in deployed_stages:
            if self.deployment_mode is None:
                raise ValueError("a deployed guardrail requires a deployment mode")
        elif self.deployment_mode is not None:
            raise ValueError("only a deployed guardrail carries a deployment mode")
        if (
            self.guardrail_class is GuardrailClass.INVARIANT
            and self.deployment_mode is not None
            and self.deployment_mode is not GuardrailDeploymentMode.ENFORCE
        ):
            raise ValueError(
                "an invariant-class guardrail can only ever be deployed in enforce mode"
            )


def an_invariant_class_guardrail_is_deployed_indefinitely_in_observe_only_mode() -> bool:
    """SS27: "Invariant enforcement cannot be placed indefinitely in observe-only mode."
    `GuardrailLifecycleRecord` goes further and makes an invariant-class guardrail
    unconstructable in `observe` or `warn` mode at all -- SS7 already frames invariants as
    "must always hold; violation stops operation", leaving no room for a staged rollout."""
    return False
