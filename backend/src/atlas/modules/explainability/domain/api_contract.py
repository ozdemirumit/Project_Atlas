"""ATLAS-046 SS22: API explanation contract.

Assembles SS22's eight machine-consumable fields from pieces already built across this subsystem
-- `Explanation` (claims, evidence, alternatives, unknowns, source-artifact versions),
`ConfidenceExplanation` (SS12), `RiskImpactExplanation` (SS16), `PolicyDenialExplanation` (SS17,
policy outcome and safe reason codes) -- rather than a new capture of the same facts. SS22's
"consumers must not parse prose to determine authorization or workflow state" is enforced by
construction: `required_human_review` and `policy` carry a typed bool and a typed
`PolicyDecisionOutcome`/reason code, never strings a consumer would need to interpret.

Renderer version is not modeled here -- `Explanation`'s own docstring already defers it until a
rendering pipeline exists (slice 1); this contract carries that same, honestly-stated gap rather
than fabricating one.
"""

from __future__ import annotations

from dataclasses import dataclass

from atlas.modules.explainability.domain.confidence import ConfidenceExplanation
from atlas.modules.explainability.domain.models import (
    EvidenceLink,
    Explanation,
    ExplanationChannel,
    ExplanationClaim,
)
from atlas.modules.explainability.domain.policy_denial import PolicyDenialExplanation
from atlas.modules.explainability.domain.risk_impact import RiskImpactExplanation


@dataclass(frozen=True, slots=True)
class ApiExplanationContract:
    """SS22's structured, machine-consumable explanation -- every field is typed, not prose."""

    explanation_id: str
    explanation_version: int
    claims: tuple[ExplanationClaim, ...]
    evidence_links: tuple[EvidenceLink, ...]
    confidence: ConfidenceExplanation
    alternatives: tuple[str, ...]
    unknowns: tuple[str, ...]
    risk_impact: RiskImpactExplanation | None
    policy: PolicyDenialExplanation | None
    required_human_review: bool
    source_artifact_ids: tuple[str, ...]
    source_artifact_versions: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.explanation_version < 1:
            raise ValueError("an API explanation contract requires a positive explanation version")
        if len(self.source_artifact_ids) != len(self.source_artifact_versions):
            raise ValueError("every source artifact requires exactly one recorded version")


def build_api_explanation_contract(
    explanation: Explanation,
    *,
    confidence: ConfidenceExplanation,
    risk_impact: RiskImpactExplanation | None,
    policy: PolicyDenialExplanation | None,
    required_human_review: bool,
) -> ApiExplanationContract:
    if explanation.channel is not ExplanationChannel.API:
        raise ValueError(
            "an API explanation contract can only be built from an API-channel explanation"
        )
    return ApiExplanationContract(
        explanation_id=explanation.explanation_id,
        explanation_version=explanation.version,
        claims=explanation.claims,
        evidence_links=explanation.evidence_links,
        confidence=confidence,
        alternatives=explanation.alternatives,
        unknowns=explanation.unknowns,
        risk_impact=risk_impact,
        policy=policy,
        required_human_review=required_human_review,
        source_artifact_ids=explanation.source_artifact_ids,
        source_artifact_versions=explanation.source_artifact_versions,
    )
