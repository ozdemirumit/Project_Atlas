"""ATLAS-041 SS4/SS5: epistemic types and evidence unit.

`EpistemicType` is deliberately its own nine-value taxonomy rather than a reuse of Guardrails'
`ClaimType` (seven values): SS4 draws a distinction `ClaimType` does not -- OBSERVATION ("direct
time-stamped source or connector result") versus RETRIEVED_FACT ("statement from a cited
governed source") are one merged `FACT` in `ClaimType`, and SS4 also names RECOMMENDATION, which
`ClaimType` has no equivalent for at all. `ClaimType` is not modified to match it -- it is already
used by Explainability's shipped, tested `ExplanationClaim` -- so this module establishes its own
canonical epistemic taxonomy rather than force-fitting an existing, narrower one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.core.classification import DataClassification
from atlas.modules.identity.domain.models import validate_stable_identifier


class EpistemicType(StrEnum):
    """SS4's nine epistemic types. "Language and output structure must not convert one type into
    another" is enforced by the type system itself: nothing in this module can reclassify one
    member as another."""

    OBSERVATION = "observation"
    RETRIEVED_FACT = "retrieved_fact"
    CALCULATED_FINDING = "calculated_finding"
    CORRELATION = "correlation"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"
    ASSUMPTION = "assumption"
    UNKNOWN = "unknown"
    RECOMMENDATION = "recommendation"


@dataclass(frozen=True, slots=True)
class EvidenceUnit:
    """SS5's ten declared elements."""

    evidence_id: str
    artifact_version: str
    source_type: str
    source_system: str
    owner: str | None
    authority_class: str
    collected_at: datetime
    applicable_from: datetime
    applicable_to: datetime | None
    target_id: str
    environment_id: str
    site_id: str | None
    classification: DataClassification
    authorization_reference: str
    observation_or_retrieval_method: str
    normalized_content: str
    integrity_confirmed: bool
    completeness_confirmed: bool
    is_fresh: bool
    conflicts_with_evidence_ids: tuple[str, ...]
    superseded_by_evidence_id: str | None
    citation_reference: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.evidence_id, "evidence_id")
        validate_stable_identifier(self.target_id, "target_id")
        validate_stable_identifier(self.environment_id, "environment_id")
        if not self.artifact_version.strip():
            raise ValueError("an evidence unit requires an artifact version")
        if not self.source_type.strip() or not self.source_system.strip():
            raise ValueError("an evidence unit requires a source type and source system")
        if not self.authority_class.strip():
            raise ValueError("an evidence unit requires an authority class")
        if self.collected_at.tzinfo is None:
            raise ValueError("collected_at must be timezone-aware")
        if self.applicable_from.tzinfo is None:
            raise ValueError("applicable_from must be timezone-aware")
        if self.applicable_to is not None and self.applicable_to.tzinfo is None:
            raise ValueError("applicable_to must be timezone-aware")
        if self.applicable_to is not None and self.applicable_to < self.applicable_from:
            raise ValueError("applicable_to must not precede applicable_from")
        if not self.authorization_reference.strip():
            raise ValueError("an evidence unit requires an authorization reference")
        if not self.observation_or_retrieval_method.strip():
            raise ValueError("an evidence unit requires its observation or retrieval method")
        if not self.normalized_content.strip():
            raise ValueError("an evidence unit requires normalized content or a bounded excerpt")
        if not self.citation_reference.strip():
            raise ValueError("an evidence unit requires a citation reference")

    @property
    def can_support_a_consequential_claim(self) -> bool:
        """SS5: "evidence without required scope, time, provenance, or access metadata cannot
        support a consequential claim without an explicit limitation." Scope (`target_id`/
        `environment_id`), time (`collected_at`), provenance (`source_system`/`authority_class`),
        and access (`authorization_reference`) are all required, non-optional fields, so a
        well-formed `EvidenceUnit` already has them; only integrity and completeness remain as
        conditions this property checks."""
        return self.integrity_confirmed and self.completeness_confirmed
