"""ATLAS-041 SS25: safety and security.

Reuses Guardrails' `instruction_hierarchy.InstructionSource`/`can_override` directly for
"retrieved text and tool output cannot change instruction priority or authorize tools" -- the
same reuse Runbook Engine's `ingestion_and_security.py` already established for its own retrieved
content -- and `detect_secret_patterns` (an eighth reuse this session) for "secrets and raw
credentials never enter model context." "Generated queries and checks are schema-validated and
capability-limited" needs no new code: schema validation is a rendering/execution-layer concern
with nothing to validate yet, and capability-limiting is already `discriminating_checks.
is_within_capability_ceiling` (slice 8).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.guardrails.domain.input_guardrails import detect_secret_patterns
from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.reasoning.domain.models import EvidenceUnit


def model_context_may_contain_secrets() -> bool:
    """SS25: "secrets and raw credentials never enter model context." Always `False`."""
    return False


def scan_for_secrets_before_model_context(text: str) -> tuple[str, ...]:
    """SS25: the detection half of "secrets and raw credentials never enter model context" --
    text is scanned before it is allowed into model context."""
    return detect_secret_patterns(text)


def recommendation_is_executable_without_independent_controls() -> bool:
    """SS25: "a plausible recommendation remains non-executable until independent controls are
    satisfied." Always `False`."""
    return False


def high_impact_conclusion_requires_current_evidence(
    evidence_units: tuple[EvidenceUnit, ...],
) -> bool:
    """SS25: "high-impact conclusions require current and applicable evidence." Reuses slice 1's
    `EvidenceUnit.can_support_a_consequential_claim` rather than a second freshness/applicability
    check -- `True` only when at least one evidence unit qualifies."""
    return any(unit.can_support_a_consequential_claim for unit in evidence_units)


class SecurityFindingKind(StrEnum):
    PROMPT_INJECTION = "prompt_injection"
    MALICIOUS_CONTENT = "malicious_content"


@dataclass(frozen=True, slots=True)
class SecurityEvidenceRecord:
    """SS25: "prompt injection and malicious-content findings are preserved as security
    evidence.\""""

    finding_id: str
    kind: SecurityFindingKind
    detected_signal: str
    source_reference: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.finding_id, "finding_id")
        if not self.detected_signal.strip():
            raise ValueError("a security evidence record requires the detected signal")
        if not self.source_reference.strip():
            raise ValueError("a security evidence record requires a source reference")
