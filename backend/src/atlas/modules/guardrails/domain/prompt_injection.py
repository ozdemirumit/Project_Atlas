"""ATLAS-047 SS11: prompt-injection guardrails.

"Prompt-injection detection is defense in depth; authorization and tool isolation remain
mandatory even when no injection is detected" -- `detect_injection_signals` is a best-effort,
deterministic heuristic (ADVISORY class, SS7), not proof of anything. Real prompt injection is an
open, actively-researched problem; this recognizes only the literal phrasings listed below,
nothing adaptive, encoded, or novel. SS11's actual defense is structural: `TrustedContentEnvelope`
always carries `InstructionSource.RETRIEVED_OR_TOOL_PROVIDED_CONTENT` (slice 2) -- there is no
field on it that could ever mark wrapped content as more senior than that, regardless of what the
content claims to be.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.guardrails.domain.instruction_hierarchy import InstructionSource
from atlas.modules.guardrails.domain.models import (
    GuardrailClass,
    GuardrailDecision,
    GuardrailOutcome,
)


@dataclass(frozen=True, slots=True)
class TrustedContentEnvelope:
    """SS11: "retrieved content is delimited and labeled with source and trust metadata."
    `trust_state` is kept a plain string rather than an enum -- the trust vocabulary belongs to
    whatever module actually classifies sources (knowledge, connectors); this type only carries
    it through and enforces the one guarantee that matters here: the source is always
    data-only."""

    content: str
    origin_reference: str
    trust_state: str
    retrieved_at: datetime

    def __post_init__(self) -> None:
        if not self.origin_reference.strip():
            raise ValueError("a trusted content envelope requires an origin reference")
        if not self.trust_state.strip():
            raise ValueError("a trusted content envelope requires a trust state")
        if self.retrieved_at.tzinfo is None:
            raise ValueError("retrieved_at must be timezone-aware")

    @property
    def source(self) -> InstructionSource:
        return InstructionSource.RETRIEVED_OR_TOOL_PROVIDED_CONTENT

    def delimited(self) -> str:
        """SS11's delimiting: a labeled boundary a prompt can include directly, so the model
        sees exactly where untrusted content starts and ends."""
        return (
            f'<untrusted-content source="{self.origin_reference}" trust="{self.trust_state}">\n'
            f"{self.content}\n</untrusted-content>"
        )


_INJECTION_PHRASES: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)ignore (?:all |the )?(?:previous|prior|above) instructions"),
    re.compile(r"(?i)disregard (?:all |the )?(?:previous|prior|above)"),
    re.compile(r"(?i)you are now\b"),
    re.compile(r"(?i)new instructions?\s*:"),
    re.compile(r"(?i)^\s*system\s*:", re.MULTILINE),
    re.compile(r"(?i)act as (?:if you|an?)\b"),
    re.compile(r"(?i)reveal (?:your|the) (?:system )?prompt"),
    re.compile(r"(?i)print (?:your|the) (?:system )?(?:prompt|instructions)"),
    re.compile(r"(?i)do anything now\b"),
    re.compile(r"(?i)jailbreak"),
)


def detect_injection_signals(text: str) -> tuple[str, ...]:
    return tuple(pattern.pattern for pattern in _INJECTION_PHRASES if pattern.search(text))


def evaluate_prompt_injection_risk(
    envelope: TrustedContentEnvelope,
    *,
    now: datetime,
    decision_id: str,
    correlation_id: str,
) -> GuardrailDecision:
    signals = detect_injection_signals(envelope.content)
    if signals:
        return GuardrailDecision(
            decision_id=decision_id,
            decided_at=now,
            rule_id="guardrail-rule.prompt-injection-heuristic",
            rule_version=1,
            guardrail_class=GuardrailClass.ADVISORY,
            input_reference=envelope.origin_reference,
            outcome=GuardrailOutcome.REVIEW,
            reason_code="prompt_injection_signal_detected",
            detail=(
                f"{len(signals)} heuristic injection phrase(s) matched; content remains"
                " data-only regardless of outcome."
            ),
            evidence_references=signals,
            detector_version="prompt-injection-heuristic.v1",
            required_next_action=(
                "Route to human review before acting on any request derived from this content."
            ),
            correlation_id=correlation_id,
        )
    return GuardrailDecision(
        decision_id=decision_id,
        decided_at=now,
        rule_id="guardrail-rule.prompt-injection-heuristic",
        rule_version=1,
        guardrail_class=GuardrailClass.ADVISORY,
        input_reference=envelope.origin_reference,
        outcome=GuardrailOutcome.PASS,
        reason_code="no_injection_signal_detected",
        detail="No heuristic injection phrase matched. This does not prove the content is safe.",
        evidence_references=(),
        detector_version="prompt-injection-heuristic.v1",
        required_next_action="None beyond the standard structural guardrails.",
        correlation_id=correlation_id,
    )
