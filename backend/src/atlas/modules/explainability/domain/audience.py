"""ATLAS-046 SS10/SS11: explanation levels and audience profiles.

`adapt_detail_level` and `adapt_audience` are deliberately trivial: each only ever changes the
one field it names, via `dataclasses.replace`, so there is no code path where adapting for a
level or audience could also change a claim, an evidence link, or the summary. SS10: "users can
move between levels without generating a different underlying conclusion." SS11: "audience
profiles change vocabulary and order, not facts."
"""

from __future__ import annotations

from dataclasses import replace
from enum import StrEnum

from atlas.modules.explainability.domain.models import (
    AudienceProfile,
    Explanation,
    ExplanationDetailLevel,
)


class EmphasisField(StrEnum):
    """The union of every named emphasis item across SS11's five audience profiles."""

    CURRENT_OBSERVATIONS = "current_observations"
    TOPOLOGY = "topology"
    VERSIONS = "versions"
    HYPOTHESES = "hypotheses"
    DIAGNOSTICS = "diagnostics"
    PARAMETERS = "parameters"
    TECHNICAL_IMPACT = "technical_impact"
    VALIDATION = "validation"
    ACTIVE_SYMPTOMS = "active_symptoms"
    SERVICE_STATE = "service_state"
    SEVERITY = "severity"
    IMMEDIATE_SAFE_CHECKS = "immediate_safe_checks"
    ESCALATION = "escalation"
    OWNERSHIP = "ownership"
    TIMELINE = "timeline"
    EXACT_PROPOSAL = "exact_proposal"
    EVIDENCE_QUALITY = "evidence_quality"
    ALTERNATIVES = "alternatives"
    RISK = "risk"
    BLAST_RADIUS = "blast_radius"
    INTERRUPTION = "interruption"
    DURATION = "duration"
    READINESS = "readiness"
    ROLLBACK = "rollback"
    RESIDUAL_RISK = "residual_risk"
    EXPIRY = "expiry"
    AFFECTED_SERVICE = "affected_service"
    USER_OR_BUSINESS_EFFECT = "user_or_business_effect"
    UNCERTAINTY = "uncertainty"
    RESTORATION_RANGE = "restoration_range"
    CHOICES = "choices"
    ACCOUNTABILITY = "accountability"
    IDENTITIES = "identities"
    AUTHORITY = "authority"
    POLICY = "policy"
    GUARDRAILS = "guardrails"
    EVIDENCE_LINEAGE = "evidence_lineage"
    DATA_ACCESS = "data_access"
    DECISIONS = "decisions"
    AUDIT_REFERENCES = "audit_references"


_AUDIENCE_EMPHASIS: dict[AudienceProfile, tuple[EmphasisField, ...]] = {
    AudienceProfile.INFRASTRUCTURE_ENGINEER: (
        EmphasisField.CURRENT_OBSERVATIONS,
        EmphasisField.TOPOLOGY,
        EmphasisField.VERSIONS,
        EmphasisField.HYPOTHESES,
        EmphasisField.DIAGNOSTICS,
        EmphasisField.PARAMETERS,
        EmphasisField.TECHNICAL_IMPACT,
        EmphasisField.VALIDATION,
    ),
    AudienceProfile.OPERATIONS_OR_NOC_ANALYST: (
        EmphasisField.ACTIVE_SYMPTOMS,
        EmphasisField.SERVICE_STATE,
        EmphasisField.SEVERITY,
        EmphasisField.IMMEDIATE_SAFE_CHECKS,
        EmphasisField.ESCALATION,
        EmphasisField.OWNERSHIP,
        EmphasisField.TIMELINE,
    ),
    AudienceProfile.APPROVER_OR_CHANGE_AUTHORITY: (
        EmphasisField.EXACT_PROPOSAL,
        EmphasisField.EVIDENCE_QUALITY,
        EmphasisField.ALTERNATIVES,
        EmphasisField.RISK,
        EmphasisField.BLAST_RADIUS,
        EmphasisField.INTERRUPTION,
        EmphasisField.DURATION,
        EmphasisField.READINESS,
        EmphasisField.ROLLBACK,
        EmphasisField.RESIDUAL_RISK,
        EmphasisField.EXPIRY,
    ),
    AudienceProfile.SERVICE_OWNER_OR_MANAGER: (
        EmphasisField.AFFECTED_SERVICE,
        EmphasisField.USER_OR_BUSINESS_EFFECT,
        EmphasisField.UNCERTAINTY,
        EmphasisField.RESTORATION_RANGE,
        EmphasisField.CHOICES,
        EmphasisField.ACCOUNTABILITY,
    ),
    AudienceProfile.SECURITY_OR_AUDIT_REVIEWER: (
        EmphasisField.IDENTITIES,
        EmphasisField.AUTHORITY,
        EmphasisField.POLICY,
        EmphasisField.GUARDRAILS,
        EmphasisField.EVIDENCE_LINEAGE,
        EmphasisField.DATA_ACCESS,
        EmphasisField.VERSIONS,
        EmphasisField.DECISIONS,
        EmphasisField.AUDIT_REFERENCES,
    ),
}


def emphasis_for(audience: AudienceProfile) -> tuple[EmphasisField, ...]:
    return _AUDIENCE_EMPHASIS[audience]


def adapt_detail_level(
    explanation: Explanation, *, target_level: ExplanationDetailLevel
) -> Explanation:
    return replace(explanation, detail_level=target_level)


def adapt_audience(explanation: Explanation, *, target_audience: AudienceProfile) -> Explanation:
    return replace(explanation, audience=target_audience)
