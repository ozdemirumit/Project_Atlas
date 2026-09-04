"""ATLAS-047 SS10: input guardrails.

Covers the deterministic, testable part of SS10's list -- size/rate limits and pattern-based
secret detection. Explicitly does not attempt malware/active-content scanning (needs a real
scanner engine this codebase does not have) or prompt-injection detection (its own slice, since
SS11 treats it as a distinct layer with its own guardrails). SS36's own assumption applies here
too: "some detectors are probabilistic and require deterministic containment around them" --
`detect_secret_patterns` is deterministic but not exhaustive; it recognizes only the shapes
explicitly listed below, nothing more.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.guardrails.domain.models import (
    GuardrailClass,
    GuardrailDecision,
    GuardrailOutcome,
)


class RequestClassification(StrEnum):
    """SS10's six-way request classification."""

    ANALYSIS = "analysis"
    RETRIEVAL = "retrieval"
    DIAGNOSTIC = "diagnostic"
    CHANGE = "change"
    EXPORT = "export"
    ADMINISTRATION = "administration"


@dataclass(frozen=True, slots=True)
class InputLimits:
    max_size_bytes: int
    max_archive_depth: int
    max_requests_per_window: int
    window_seconds: int

    def __post_init__(self) -> None:
        if self.max_size_bytes < 1:
            raise ValueError("max_size_bytes must be positive")
        if self.max_archive_depth < 0:
            raise ValueError("max_archive_depth must not be negative")
        if self.max_requests_per_window < 1:
            raise ValueError("max_requests_per_window must be positive")
        if self.window_seconds < 1:
            raise ValueError("window_seconds must be positive")


_SECRET_PATTERNS: dict[str, re.Pattern[str]] = {
    "aws_access_key_id": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "generic_api_key_assignment": re.compile(
        r"(?i)\b(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-.]{16,}['\"]?"
    ),
    "private_key_header": re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    "jwt_like_token": re.compile(
        r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"
    ),
}


def detect_secret_patterns(text: str) -> tuple[str, ...]:
    return tuple(name for name, pattern in _SECRET_PATTERNS.items() if pattern.search(text))


def validate_input_size(*, size_bytes: int, limits: InputLimits) -> tuple[str, ...]:
    if size_bytes > limits.max_size_bytes:
        return (f"input exceeds the maximum size of {limits.max_size_bytes} bytes",)
    return ()


def validate_archive_depth(*, depth: int, limits: InputLimits) -> tuple[str, ...]:
    if depth > limits.max_archive_depth:
        return (f"input exceeds the maximum archive depth of {limits.max_archive_depth}",)
    return ()


class InputRateLimiter:
    """A fixed-window, same-process rate limiter. A real multi-instance deployment needs a
    distributed backing store; this is the primitive that store would sit behind, not a
    replacement for one."""

    def __init__(self) -> None:
        self._windows: dict[str, tuple[datetime, int]] = {}

    def check_and_increment(self, *, key: str, limits: InputLimits, now: datetime) -> bool:
        """Returns True and records the request if it is within limit; returns False without
        recording it if the window is already at capacity, so a denied request does not itself
        count against the next window."""
        window_start, count = self._windows.get(key, (now, 0))
        if (now - window_start).total_seconds() >= limits.window_seconds:
            window_start, count = now, 0
        if count >= limits.max_requests_per_window:
            self._windows[key] = (window_start, count)
            return False
        self._windows[key] = (window_start, count + 1)
        return True


def validate_input(
    *,
    content: str,
    size_bytes: int,
    archive_depth: int,
    limits: InputLimits,
    rate_limiter: InputRateLimiter,
    rate_limit_key: str,
    now: datetime,
    decision_id: str,
    correlation_id: str,
) -> GuardrailDecision:
    violations = [
        *validate_input_size(size_bytes=size_bytes, limits=limits),
        *validate_archive_depth(depth=archive_depth, limits=limits),
    ]
    if not rate_limiter.check_and_increment(key=rate_limit_key, limits=limits, now=now):
        violations.append("request rate exceeds the configured limit")
    detected_secrets = detect_secret_patterns(content)
    if detected_secrets:
        violations.append(f"content matches known secret patterns: {', '.join(detected_secrets)}")

    if violations:
        return GuardrailDecision(
            decision_id=decision_id,
            decided_at=now,
            rule_id="guardrail-rule.input-validation",
            rule_version=1,
            guardrail_class=GuardrailClass.PLATFORM_MINIMUM,
            input_reference=rate_limit_key,
            outcome=GuardrailOutcome.BLOCK,
            reason_code="input_validation_failed",
            detail="; ".join(violations),
            evidence_references=detected_secrets,
            detector_version="input-guardrails.v1",
            required_next_action="Resubmit within limits and without detectable secret content.",
            correlation_id=correlation_id,
        )
    return GuardrailDecision(
        decision_id=decision_id,
        decided_at=now,
        rule_id="guardrail-rule.input-validation",
        rule_version=1,
        guardrail_class=GuardrailClass.PLATFORM_MINIMUM,
        input_reference=rate_limit_key,
        outcome=GuardrailOutcome.PASS,
        reason_code="input_validation_passed",
        detail="Input is within configured size, depth, and rate limits with no detected secrets.",
        evidence_references=(),
        detector_version="input-guardrails.v1",
        required_next_action="None.",
        correlation_id=correlation_id,
    )
