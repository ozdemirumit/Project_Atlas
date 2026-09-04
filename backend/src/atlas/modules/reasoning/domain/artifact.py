"""ATLAS-041 SS22: reasoning artifact.

Aggregates what earlier slices already built (problem frame, evidence, quality, claims,
timeline, hypotheses, discriminating checks, confidence) rather than a second capture of any of
them, matching the aggregator pattern established by Runbook Engine's `RunbookHandoffView` and
Explainability's `InvestigationPresentation`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.reasoning.domain.claims import ReasoningClaim
from atlas.modules.reasoning.domain.confidence import ConfidenceAssessment
from atlas.modules.reasoning.domain.discriminating_checks import DiscriminatingCheck
from atlas.modules.reasoning.domain.evidence_gaps import EvidenceConflictRecord
from atlas.modules.reasoning.domain.framing import ProblemFrame
from atlas.modules.reasoning.domain.hypotheses import ReasoningHypothesis
from atlas.modules.reasoning.domain.models import EvidenceUnit
from atlas.modules.reasoning.domain.quality import EvidenceQualityAssessment
from atlas.modules.reasoning.domain.temporal import TemporalEvent


@dataclass(frozen=True, slots=True)
class ComponentVersions:
    """SS22: "agent, model, prompt, tool, graph, knowledge, and policy versions.\""""

    agent_version: str | None
    model_version: str | None
    prompt_version: str | None
    tool_version: str | None
    graph_version: str | None
    knowledge_version: str | None
    policy_version: str | None


class StopReason(StrEnum):
    """SS24's eight stopping-rule reasons -- defined here since SS22's artifact needs a stop
    reason before SS24's own dedicated slice builds the fuller `apply_stopping_rules` logic that
    reuses this same enum."""

    QUESTION_ANSWERED = "question_answered"
    DOMAIN_CONFIRMATION_MET = "domain_confirmation_met"
    REQUIRES_UNAVAILABLE_PERMISSION_OR_APPROVAL = "requires_unavailable_permission_or_approval"
    EVIDENCE_INSUFFICIENT_NO_SAFE_CHECK_REMAINS = "evidence_insufficient_no_safe_check_remains"
    BUDGET_EXHAUSTED = "budget_exhausted"
    NEW_CHECKS_WOULD_REPEAT_EXISTING_EVIDENCE = "new_checks_would_repeat_existing_evidence"
    GUARDRAIL_OR_POLICY_BLOCK = "guardrail_or_policy_block"
    USER_CANCELLED_OR_TASK_EXPIRED = "user_cancelled_or_task_expired"


@dataclass(frozen=True, slots=True)
class ReasoningArtifact:
    """SS22's eleven declared elements. "The artifact is immutable; updates create a new version
    linked to the prior one" -- immutability comes from the dataclass itself being frozen; the
    version-linkage half is enforced by `__post_init__`: version 1 cannot carry a
    `prior_version_id`, and every later version requires one."""

    artifact_id: str
    version: int
    prior_version_id: str | None
    frame: ProblemFrame
    evidence_inventory: tuple[EvidenceUnit, ...]
    quality_assessments: tuple[EvidenceQualityAssessment, ...]
    timeline: tuple[TemporalEvent, ...]
    claims: tuple[ReasoningClaim, ...]
    hypotheses: tuple[ReasoningHypothesis, ...]
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]
    conflicts: tuple[EvidenceConflictRecord, ...]
    excluded_evidence_ids: tuple[str, ...]
    selected_checks: tuple[DiscriminatingCheck, ...]
    check_results: tuple[str, ...]
    confidence: ConfidenceAssessment
    current_conclusion: str
    alternatives: tuple[str, ...]
    stop_reason: StopReason | None
    recommended_next_evidence: str | None
    component_versions: ComponentVersions
    created_at: datetime

    def __post_init__(self) -> None:
        validate_stable_identifier(self.artifact_id, "artifact_id")
        if self.version < 1:
            raise ValueError("a reasoning artifact requires a positive version")
        if self.version == 1 and self.prior_version_id is not None:
            raise ValueError("version 1 of a reasoning artifact cannot have a prior version")
        if self.version > 1 and self.prior_version_id is None:
            raise ValueError("a reasoning artifact beyond version 1 requires prior_version_id")
        if not self.current_conclusion.strip():
            raise ValueError("a reasoning artifact requires a current conclusion")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
