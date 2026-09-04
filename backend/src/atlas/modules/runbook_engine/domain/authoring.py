"""ATLAS-045 SS14/SS15: authoring and AI-assisted structuring.

Reuses Guardrails' `detect_secret_patterns` (a fifth reuse across this session) for the
secret-value portion of SS14's "authors cannot embed secret values, unrestricted commands, or
dynamic code as trusted executable content" -- "unrestricted commands" and "dynamic code" have no
existing detector anywhere in this codebase to reuse, stated as an open gap rather than
fabricated. Reuses Guardrails' `ConfidenceLevel` for SS15's "generated fields retain ...
confidence" rather than a second confidence scale.
"""

from __future__ import annotations

from dataclasses import dataclass

from atlas.modules.guardrails.domain.input_guardrails import detect_secret_patterns
from atlas.modules.guardrails.domain.reasoning_guardrails import ConfidenceLevel
from atlas.modules.identity.domain.models import validate_stable_identifier


@dataclass(frozen=True, slots=True)
class SubprocedureReference:
    """SS14: "reusable approved subprocedures with pinned versions.\""""

    subprocedure_runbook_id: str
    pinned_version_id: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.subprocedure_runbook_id, "subprocedure_runbook_id")
        validate_stable_identifier(self.pinned_version_id, "pinned_version_id")


@dataclass(frozen=True, slots=True)
class ChangeDiff:
    """SS14: "change diff and migration impact.\""""

    from_version_id: str
    to_version_id: str
    changed_step_ids: tuple[str, ...]
    migration_impact: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.from_version_id, "from_version_id")
        validate_stable_identifier(self.to_version_id, "to_version_id")
        if self.from_version_id == self.to_version_id:
            raise ValueError("a change diff requires two distinct versions")
        if not self.migration_impact.strip():
            raise ValueError("a change diff requires a migration impact statement")


def scan_authored_content_for_prohibited_material(content: str) -> tuple[str, ...]:
    """SS14: the secret-value portion of "authors cannot embed secret values, unrestricted
    commands, or dynamic code as trusted executable content.\""""
    return detect_secret_patterns(content)


@dataclass(frozen=True, slots=True)
class AiProposedField:
    """SS15: "generated fields retain source spans and confidence." Requiring a non-blank
    `source_span` on every instance structurally rules out a field that has no grounding in the
    source material -- SS15's "AI does not invent missing vendor facts" applied to the field's
    own shape, not just documented as a convention."""

    field_name: str
    proposed_value: str
    source_span: str
    confidence: ConfidenceLevel

    def __post_init__(self) -> None:
        if not self.field_name.strip():
            raise ValueError("an AI-proposed field requires a field name")
        if not self.proposed_value.strip():
            raise ValueError("an AI-proposed field requires a proposed value")
        if not self.source_span.strip():
            raise ValueError(
                "SS15: generated fields retain source spans -- source_span is required"
            )


def can_ai_directly_approve_or_publish() -> bool:
    """SS15: "AI does not invent missing vendor facts, approve its output, or publish directly."
    Always `False` -- a concrete call site for the approve-or-publish half of that rule, not just
    a convention a caller has to remember."""
    return False
