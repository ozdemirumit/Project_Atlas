"""ATLAS-047 SS18: output guardrails.

Reuses slice 3's `detect_secret_patterns` and slice 4's `detect_injection_signals` rather than
re-implementing them for the output side -- the same shapes that must never enter a prompt must
also never leave one. Adds one new heuristic of its own: `detect_unsupported_certainty_language`,
covering SS18's "unsupported certainty, causal, safety, or success language."
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from atlas.modules.guardrails.domain.input_guardrails import detect_secret_patterns
from atlas.modules.guardrails.domain.prompt_injection import detect_injection_signals
from atlas.modules.identity.domain.models import validate_stable_identifier

_UNSUPPORTED_CERTAINTY_PHRASES: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\bguaranteed\b"),
    re.compile(r"(?i)\b100%\s*(?:safe|certain|success)"),
    re.compile(r"(?i)\bwill definitely\b"),
    re.compile(r"(?i)\bno risk\b"),
    re.compile(r"(?i)\balways works?\b"),
    re.compile(r"(?i)\bcertainly (?:will|succeed)"),
)


def detect_unsupported_certainty_language(text: str) -> tuple[str, ...]:
    """A best-effort, deterministic scan for the most common overclaiming phrasings -- like every
    pattern-based detector in this module, not exhaustive."""
    return tuple(
        pattern.pattern for pattern in _UNSUPPORTED_CERTAINTY_PHRASES if pattern.search(text)
    )


@dataclass(frozen=True, slots=True)
class OutputContent:
    content_id: str
    text: str
    required_sections: tuple[str, ...]
    present_sections: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_stable_identifier(self.content_id, "content_id")
        if not self.text.strip():
            raise ValueError("output content requires non-empty text")

    @property
    def missing_sections(self) -> tuple[str, ...]:
        return tuple(
            section for section in self.required_sections if section not in self.present_sections
        )


def validate_output(content: OutputContent) -> tuple[str, ...]:
    violations: list[str] = []
    missing = content.missing_sections
    if missing:
        violations.append(f"output is missing required sections: {', '.join(missing)}")
    detected_secrets = detect_secret_patterns(content.text)
    if detected_secrets:
        violations.append(f"output contains secret-shaped content: {', '.join(detected_secrets)}")
    if detect_injection_signals(content.text):
        violations.append("output contains prompt-injection residue")
    if detect_unsupported_certainty_language(content.text):
        violations.append("output contains unsupported certainty, safety, or success language")
    return tuple(violations)
