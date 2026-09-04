"""ATLAS-024 SS17: decision record.

Aggregates what earlier slices already built (request, evidence package, findings, hypotheses,
impact assessment, recommendation candidates, policy handoff) rather than a second capture of
any of them, matching the aggregator pattern established across this session (Reasoning's
`ReasoningArtifact`, Runbook Engine's `RunbookHandoffView`, Explainability's
`InvestigationPresentation`).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.decision_engine.domain.candidates import DecisionRecommendationCandidate
from atlas.modules.decision_engine.domain.findings import DecisionFinding
from atlas.modules.decision_engine.domain.hypotheses import (
    DecisionConfidenceCategory,
    DecisionHypothesis,
)
from atlas.modules.decision_engine.domain.impact import DecisionImpactAssessment
from atlas.modules.decision_engine.domain.models import DecisionRequest
from atlas.modules.decision_engine.domain.policy_handoff import PolicyHandoffRecord
from atlas.modules.identity.domain.models import validate_stable_identifier


@dataclass(frozen=True, slots=True)
class DecisionComponentVersions:
    """SS17: "models, rules, agents, prompts, and schemas used.\""""

    model_version: str | None
    rule_version: str | None
    agent_version: str | None
    prompt_version: str | None
    schema_version: str | None


class DecisionReviewState(StrEnum):
    UNREVIEWED = "unreviewed"
    REVIEWED = "reviewed"
    DISPUTED = "disputed"


class DecisionSupersessionState(StrEnum):
    CURRENT = "current"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class DecisionRecord:
    """SS17's twelve declared elements. Version-linkage mirrors Reasoning's `ReasoningArtifact`
    (ATLAS-041 SS22): version 1 cannot carry a `prior_version_id`, every later version requires
    one."""

    decision_id: str
    version: int
    prior_version_id: str | None
    request: DecisionRequest
    workflow_id: str | None
    created_at: datetime
    valid_until: datetime | None
    target_ids: tuple[str, ...]
    scope: str
    evidence_package_version: str
    findings: tuple[DecisionFinding, ...]
    hypotheses: tuple[DecisionHypothesis, ...]
    confidence_category: DecisionConfidenceCategory
    confidence_uncertainty_note: str
    impact_assessment: DecisionImpactAssessment | None
    graph_freshness_statement: str
    recommendation_candidates: tuple[DecisionRecommendationCandidate, ...]
    alternatives: tuple[str, ...]
    policy_handoffs: tuple[PolicyHandoffRecord, ...]
    required_approvals: tuple[str, ...]
    component_versions: DecisionComponentVersions
    review_state: DecisionReviewState
    supersession_state: DecisionSupersessionState
    superseded_by_decision_id: str | None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.decision_id, "decision_id")
        if self.version < 1:
            raise ValueError("a decision record requires a positive version")
        if self.version == 1 and self.prior_version_id is not None:
            raise ValueError("version 1 of a decision record cannot have a prior version")
        if self.version > 1 and self.prior_version_id is None:
            raise ValueError("a decision record beyond version 1 requires prior_version_id")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if self.valid_until is not None and self.valid_until.tzinfo is None:
            raise ValueError("valid_until must be timezone-aware")
        if not self.scope.strip():
            raise ValueError("a decision record requires a scope statement")
        if not self.evidence_package_version.strip():
            raise ValueError("a decision record requires the evidence package version")
        if not self.graph_freshness_statement.strip():
            raise ValueError("a decision record requires a graph-freshness statement")
        is_superseded = self.supersession_state is DecisionSupersessionState.SUPERSEDED
        if is_superseded and self.superseded_by_decision_id is None:
            raise ValueError(
                "a superseded decision record requires the decision that superseded it"
            )
        if not is_superseded and self.superseded_by_decision_id is not None:
            raise ValueError("superseded_by_decision_id is only meaningful for a SUPERSEDED record")
