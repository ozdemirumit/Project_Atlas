"""ATLAS-024 SS19/SS20: reproducibility and versioning/supersession.

Reuses `record.DecisionSupersessionState` (slice 8) rather than a second lifecycle state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.decision_engine.domain.record import DecisionSupersessionState


@dataclass(frozen=True, slots=True)
class ReproducibilityManifest:
    """SS19's seven declared elements."""

    evidence_package_reference: str
    decision_request_reference: str
    request_schema_version: str
    rule_and_configuration_versions: tuple[str, ...]
    graph_snapshot_reference: str | None
    agent_identity: str | None
    prompt_identity: str | None
    model_identity: str | None
    endpoint_identity: str | None
    retrieval_trace_reference: str | None
    policy_input_reference: str | None
    policy_result_reference: str | None

    def __post_init__(self) -> None:
        if not self.evidence_package_reference.strip():
            raise ValueError("a reproducibility manifest requires an evidence package reference")
        if not self.decision_request_reference.strip():
            raise ValueError("a reproducibility manifest requires a decision request reference")
        if not self.request_schema_version.strip():
            raise ValueError("a reproducibility manifest requires a request schema version")


def exact_model_output_reproduction_is_promised() -> bool:
    """SS19: "model output may not be bit-for-bit reproducible." Always `False`. Mirrors
    Reasoning's identically-named function (ATLAS-041 SS26) for the same rule, applied here to
    Decision Engine's own reproducibility manifest."""
    return False


class VersionTrigger(StrEnum):
    """SS20: "a new evidence package, target state, rule, model, or material correction creates
    a new decision version.\""""

    NEW_EVIDENCE_PACKAGE = "new_evidence_package"
    TARGET_STATE_CHANGE = "target_state_change"
    RULE_CHANGE = "rule_change"
    MODEL_CHANGE = "model_change"
    MATERIAL_CORRECTION = "material_correction"


def requires_new_decision_version(triggers: frozenset[VersionTrigger]) -> bool:
    """SS20: any of the five named triggers requires a new decision version."""
    return bool(triggers)


def user_annotation_can_rewrite_original_evidence() -> bool:
    """SS20: "user annotations or review do not rewrite original evidence." Always `False`."""
    return False


def can_use_as_current_approval_packet(*, supersession_state: DecisionSupersessionState) -> bool:
    """SS20: "expired decisions cannot be reused as current approval packets." A superseded
    decision is not current either, so only `CURRENT` qualifies -- SS20 names expiry explicitly,
    but a decision that has already been superseded is no less unusable as a *current* packet."""
    return supersession_state is DecisionSupersessionState.CURRENT
