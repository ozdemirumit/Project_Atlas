"""ATLAS-047 SS29: Security Incident Handling."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import SubjectKind, validate_stable_identifier


class IncidentTrigger(StrEnum):
    """SS29's named triggering events."""

    SUSPECTED_EXFILTRATION = "suspected_exfiltration"
    CROSS_BOUNDARY_LEAKAGE = "cross_boundary_leakage"
    REPEATED_TOOL_BYPASS = "repeated_tool_bypass"
    MALICIOUS_EXTENSION = "malicious_extension"
    AUDIT_TAMPERING = "audit_tampering"
    MODEL_COMPROMISE = "model_compromise"


@dataclass(frozen=True, slots=True)
class SecurityIncidentRecord:
    """SS29's seven-step response. "The AI may summarize evidence but does not decide incident
    closure" -- `closer_kind` requires `SubjectKind.HUMAN` whenever the incident is closed."""

    incident_id: str
    trigger: IncidentTrigger
    detected_at: datetime
    affected_references: tuple[str, ...]
    contained_at: datetime | None = None
    evidence_preserved: bool = False
    alert_reference: str | None = None
    credentials_revoked: bool = False
    scope_assessment: str | None = None
    recovery_validated_at: datetime | None = None
    improvement_reference: str | None = None
    closed_at: datetime | None = None
    closed_by: str | None = None
    closer_kind: SubjectKind | None = None

    def __post_init__(self) -> None:
        validate_stable_identifier(self.incident_id, "incident_id")
        if not self.affected_references:
            raise ValueError("a security incident requires at least one affected reference")
        if self.detected_at.tzinfo is None:
            raise ValueError("security incident detection time must be timezone-aware")
        for value in (
            self.contained_at,
            self.recovery_validated_at,
            self.closed_at,
        ):
            if value is not None and value.tzinfo is None:
                raise ValueError("security incident timestamps must be timezone-aware")
        if self.contained_at is not None and self.contained_at < self.detected_at:
            raise ValueError("containment cannot precede detection")
        closure_fields = (self.closed_at, self.closed_by, self.closer_kind)
        if any(value is not None for value in closure_fields):
            if any(value is None for value in closure_fields):
                raise ValueError("closing an incident requires a time, a closer, and their kind")
            if self.closer_kind is not SubjectKind.HUMAN:
                raise ValueError(
                    "a security incident can only be closed by a human -- the AI may summarize "
                    "evidence but does not decide incident closure"
                )
            if self.contained_at is None or not self.evidence_preserved:
                raise ValueError(
                    "a closed incident requires containment and evidence preservation to have"
                    " occurred first"
                )
            if self.recovery_validated_at is None:
                raise ValueError("a closed incident requires validated recovery")


def an_ai_agent_closes_a_security_incident() -> bool:
    """SS29: "The AI may summarize evidence but does not decide incident closure."
    `SecurityIncidentRecord` makes closure by anything other than `SubjectKind.HUMAN`
    unconstructable."""
    return False
