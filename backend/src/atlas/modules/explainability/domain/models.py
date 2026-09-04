"""ATLAS-046 SS6/SS8: the explanation object and claim-to-evidence mapping.

"The explanation is a view over authoritative versioned artifacts... it does not become a
separate hidden decision source" (SS5) -- this module holds no decision logic of its own, only
the shape of what gets rendered from artifacts already produced elsewhere (RCA, recommendations,
policy decisions, approvals). Reuses `guardrails.domain.reasoning_guardrails.ClaimType` and
`ConfidenceLevel` rather than inventing a second taxonomy for the same idea.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.guardrails.domain.reasoning_guardrails import ClaimType, ConfidenceLevel
from atlas.modules.identity.domain.models import validate_stable_identifier


class ExplanationChannel(StrEnum):
    """SS19-SS22's five presentation channels."""

    CHAT = "chat"
    INVESTIGATION = "investigation"
    APPROVAL = "approval"
    REPORT = "report"
    API = "api"


class ExplanationDetailLevel(StrEnum):
    """SS10's four levels."""

    L0_STATUS = "l0_status"
    L1_SUMMARY = "l1_summary"
    L2_TECHNICAL = "l2_technical"
    L3_GOVERNANCE = "l3_governance"


class AudienceProfile(StrEnum):
    """SS11's five profiles."""

    INFRASTRUCTURE_ENGINEER = "infrastructure_engineer"
    OPERATIONS_OR_NOC_ANALYST = "operations_or_noc_analyst"
    APPROVER_OR_CHANGE_AUTHORITY = "approver_or_change_authority"
    SERVICE_OWNER_OR_MANAGER = "service_owner_or_manager"
    SECURITY_OR_AUDIT_REVIEWER = "security_or_audit_reviewer"


@dataclass(frozen=True, slots=True)
class EvidenceLink:
    """SS8: "evidence links identify source, version, target, timestamp, authority, and
    applicability.\""""

    reference: str
    source: str
    version: str
    target_id: str
    observed_at: datetime
    authority: str
    applicability: str

    def __post_init__(self) -> None:
        if not self.reference.strip():
            raise ValueError("an evidence link requires a non-empty reference")
        if not self.source.strip():
            raise ValueError("an evidence link requires a source")
        if not self.version.strip():
            raise ValueError("an evidence link requires a version")
        validate_stable_identifier(self.target_id, "target_id")
        if not self.authority.strip():
            raise ValueError("an evidence link requires an authority")
        if not self.applicability.strip():
            raise ValueError("an evidence link requires an applicability statement")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class ExplanationClaim:
    """SS8: "every material claim has a stable claim ID." "Missing evidence is represented as a
    gap, not an empty citation" -- `is_evidence_gap` makes that state a first-class, checkable
    property rather than something a caller has to notice by counting an empty tuple."""

    claim_id: str
    claim_type: ClaimType
    statement: str
    confidence: ConfidenceLevel | None
    evidence_references: tuple[str, ...]
    contradicting_evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.claim_id, "claim_id")
        if not self.statement.strip():
            raise ValueError("an explanation claim requires a non-empty statement")

    @property
    def is_evidence_gap(self) -> bool:
        return not self.evidence_references

    @property
    def has_contradicting_evidence(self) -> bool:
        return bool(self.contradicting_evidence_references)


@dataclass(frozen=True, slots=True)
class Explanation:
    """SS6's explanation object -- every field it lists, except renderer/model/prompt/template
    versions (deferred to the rendering-pipeline slice, since no renderer exists yet to version)."""

    explanation_id: str
    version: int
    created_at: datetime
    freshness_boundary: datetime | None
    source_artifact_ids: tuple[str, ...]
    source_artifact_versions: tuple[str, ...]
    audience: AudienceProfile
    channel: ExplanationChannel
    detail_level: ExplanationDetailLevel
    summary: str
    claims: tuple[ExplanationClaim, ...]
    evidence_links: tuple[EvidenceLink, ...]
    unknowns: tuple[str, ...]
    alternatives: tuple[str, ...]
    recommended_next_step: str
    redacted: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.explanation_id, "explanation_id")
        if self.version < 1:
            raise ValueError("explanation version must be positive")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        if self.freshness_boundary is not None and self.freshness_boundary.tzinfo is None:
            raise ValueError("freshness_boundary must be timezone-aware")
        if not self.source_artifact_ids:
            raise ValueError(
                "an explanation requires at least one source artifact (SS5: a view over"
                " authoritative artifacts, never a standalone source)"
            )
        if len(self.source_artifact_ids) != len(self.source_artifact_versions):
            raise ValueError("every source artifact requires exactly one recorded version")
        if not self.summary.strip():
            raise ValueError("an explanation requires a non-empty summary")
        if not self.recommended_next_step.strip():
            raise ValueError("an explanation requires a recommended next step")

    @property
    def evidence_gaps(self) -> tuple[ExplanationClaim, ...]:
        return tuple(claim for claim in self.claims if claim.is_evidence_gap)

    def is_stale(self, *, at: datetime) -> bool:
        """SS14: "stale data has a visible warning." Takes `at` explicitly rather than reading
        the wall clock -- deterministic and testable, matching every other freshness check in
        this codebase (e.g. `policy_engine.domain.policy_set.PolicySet.is_active_at`)."""
        return self.freshness_boundary is not None and at > self.freshness_boundary
