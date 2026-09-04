from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.guardrails.domain.input_guardrails import (
    InputLimits,
    InputRateLimiter,
    detect_secret_patterns,
    validate_archive_depth,
    validate_input,
    validate_input_size,
)
from atlas.modules.guardrails.domain.models import GuardrailOutcome

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def limits(**overrides: object) -> InputLimits:
    defaults: dict[str, object] = {
        "max_size_bytes": 1_000_000,
        "max_archive_depth": 3,
        "max_requests_per_window": 5,
        "window_seconds": 60,
    }
    defaults.update(overrides)
    return InputLimits(**defaults)  # type: ignore[arg-type]


def test_detects_an_aws_access_key() -> None:
    detected = detect_secret_patterns("my key is AKIAIOSFODNN7EXAMPLE, keep it safe")
    assert "aws_access_key_id" in detected


def test_detects_a_generic_api_key_assignment() -> None:
    detected = detect_secret_patterns('api_key: "sk_live_abcdefghijklmnop1234"')
    assert "generic_api_key_assignment" in detected


def test_detects_a_private_key_header() -> None:
    detected = detect_secret_patterns("-----BEGIN RSA PRIVATE KEY-----\nMIIE...")
    assert "private_key_header" in detected


def test_detects_a_jwt_like_token() -> None:
    token = (
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0"
        ".dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
    )
    detected = detect_secret_patterns(f"the token is {token}")
    assert "jwt_like_token" in detected


def test_ordinary_text_detects_nothing() -> None:
    assert detect_secret_patterns("Please check whether the storage array is healthy.") == ()


def test_input_within_size_limit_has_no_violations() -> None:
    assert validate_input_size(size_bytes=100, limits=limits(max_size_bytes=1000)) == ()


def test_input_exceeding_size_limit_is_a_violation() -> None:
    violations = validate_input_size(size_bytes=2000, limits=limits(max_size_bytes=1000))
    assert len(violations) == 1
    assert "1000" in violations[0]


def test_archive_depth_within_limit_has_no_violations() -> None:
    assert validate_archive_depth(depth=2, limits=limits(max_archive_depth=3)) == ()


def test_archive_depth_exceeding_limit_is_a_violation() -> None:
    violations = validate_archive_depth(depth=5, limits=limits(max_archive_depth=3))
    assert len(violations) == 1


def test_rate_limiter_allows_requests_within_the_window_limit() -> None:
    limiter = InputRateLimiter()
    window_limits = limits(max_requests_per_window=3, window_seconds=60)
    for _ in range(3):
        assert limiter.check_and_increment(key="actor.example", limits=window_limits, now=NOW)


def test_rate_limiter_blocks_the_request_beyond_the_limit() -> None:
    limiter = InputRateLimiter()
    window_limits = limits(max_requests_per_window=2, window_seconds=60)
    assert limiter.check_and_increment(key="actor.example", limits=window_limits, now=NOW)
    assert limiter.check_and_increment(key="actor.example", limits=window_limits, now=NOW)
    assert not limiter.check_and_increment(key="actor.example", limits=window_limits, now=NOW)


def test_a_denied_request_does_not_itself_count_against_the_window() -> None:
    limiter = InputRateLimiter()
    window_limits = limits(max_requests_per_window=1, window_seconds=60)
    assert limiter.check_and_increment(key="actor.example", limits=window_limits, now=NOW)
    assert not limiter.check_and_increment(key="actor.example", limits=window_limits, now=NOW)
    assert not limiter.check_and_increment(key="actor.example", limits=window_limits, now=NOW)


def test_rate_limiter_resets_after_the_window_elapses() -> None:
    limiter = InputRateLimiter()
    window_limits = limits(max_requests_per_window=1, window_seconds=60)
    assert limiter.check_and_increment(key="actor.example", limits=window_limits, now=NOW)
    assert not limiter.check_and_increment(key="actor.example", limits=window_limits, now=NOW)
    later = NOW + timedelta(seconds=61)
    assert limiter.check_and_increment(key="actor.example", limits=window_limits, now=later)


def test_rate_limiter_tracks_separate_keys_independently() -> None:
    limiter = InputRateLimiter()
    window_limits = limits(max_requests_per_window=1, window_seconds=60)
    assert limiter.check_and_increment(key="actor.a", limits=window_limits, now=NOW)
    assert limiter.check_and_increment(key="actor.b", limits=window_limits, now=NOW)


def test_validate_input_passes_clean_content() -> None:
    decision = validate_input(
        content="Please check whether the storage array is healthy.",
        size_bytes=100,
        archive_depth=0,
        limits=limits(),
        rate_limiter=InputRateLimiter(),
        rate_limit_key="actor.example",
        now=NOW,
        decision_id="guardrail-decision.example",
        correlation_id="correlation.example",
    )
    assert decision.outcome is GuardrailOutcome.PASS


def test_validate_input_blocks_content_with_a_detected_secret() -> None:
    decision = validate_input(
        content="here is my key AKIAIOSFODNN7EXAMPLE",
        size_bytes=100,
        archive_depth=0,
        limits=limits(),
        rate_limiter=InputRateLimiter(),
        rate_limit_key="actor.example",
        now=NOW,
        decision_id="guardrail-decision.example",
        correlation_id="correlation.example",
    )
    assert decision.outcome is GuardrailOutcome.BLOCK
    assert decision.evidence_references == ("aws_access_key_id",)


def test_validate_input_blocks_oversized_content() -> None:
    decision = validate_input(
        content="short",
        size_bytes=10_000_000,
        archive_depth=0,
        limits=limits(max_size_bytes=1000),
        rate_limiter=InputRateLimiter(),
        rate_limit_key="actor.example",
        now=NOW,
        decision_id="guardrail-decision.example",
        correlation_id="correlation.example",
    )
    assert decision.outcome is GuardrailOutcome.BLOCK
    assert "exceeds the maximum size" in decision.detail


def test_limits_reject_non_positive_values() -> None:
    with pytest.raises(ValueError, match="max_size_bytes"):
        limits(max_size_bytes=0)
    with pytest.raises(ValueError, match="max_requests_per_window"):
        limits(max_requests_per_window=0)
    with pytest.raises(ValueError, match="window_seconds"):
        limits(window_seconds=0)
