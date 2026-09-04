from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.guardrails.domain.model_endpoint_guardrails import (
    ModelEndpoint,
    ModelEndpointHealthState,
    ModelRequestLimits,
    is_request_within_limits,
    select_fallback_endpoint,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def endpoint(**overrides: object) -> ModelEndpoint:
    defaults: dict[str, object] = {
        "endpoint_id": "model-endpoint.example",
        "model_id": "model.example",
        "model_version": "1.0",
        "trust_tier": 5,
        "context_limit_tokens": 8000,
        "data_handling_profile": "internal-only",
        "health_state": ModelEndpointHealthState.HEALTHY,
        "registered_at": NOW,
    }
    defaults.update(overrides)
    return ModelEndpoint(**defaults)  # type: ignore[arg-type]


def test_a_healthy_equally_trusted_candidate_is_a_valid_fallback() -> None:
    primary = endpoint(endpoint_id="model-endpoint.primary", trust_tier=5)
    candidate = endpoint(endpoint_id="model-endpoint.candidate", trust_tier=5)
    result = select_fallback_endpoint(primary, (candidate,))
    assert result is candidate


def test_a_more_trusted_healthy_candidate_is_selected() -> None:
    primary = endpoint(endpoint_id="model-endpoint.primary", trust_tier=5)
    candidate = endpoint(endpoint_id="model-endpoint.candidate", trust_tier=9)
    result = select_fallback_endpoint(primary, (candidate,))
    assert result is candidate


def test_a_less_trusted_candidate_is_never_selected() -> None:
    primary = endpoint(endpoint_id="model-endpoint.primary", trust_tier=5)
    less_trusted = endpoint(endpoint_id="model-endpoint.less-trusted", trust_tier=1)
    result = select_fallback_endpoint(primary, (less_trusted,))
    assert result is None


def test_an_unhealthy_candidate_is_never_selected_even_if_more_trusted() -> None:
    primary = endpoint(endpoint_id="model-endpoint.primary", trust_tier=5)
    unhealthy = endpoint(
        endpoint_id="model-endpoint.unhealthy",
        trust_tier=9,
        health_state=ModelEndpointHealthState.UNAVAILABLE,
    )
    result = select_fallback_endpoint(primary, (unhealthy,))
    assert result is None


def test_no_candidates_resolves_to_deterministic_unavailability() -> None:
    primary = endpoint()
    assert select_fallback_endpoint(primary, ()) is None


def test_the_most_trusted_eligible_candidate_is_chosen_among_several() -> None:
    primary = endpoint(endpoint_id="model-endpoint.primary", trust_tier=5)
    mid = endpoint(endpoint_id="model-endpoint.mid", trust_tier=6)
    high = endpoint(endpoint_id="model-endpoint.high", trust_tier=8)
    result = select_fallback_endpoint(primary, (mid, high))
    assert result is high


def test_endpoint_rejects_blank_required_fields() -> None:
    with pytest.raises(ValueError, match="model_id"):
        endpoint(model_id="   ")
    with pytest.raises(ValueError, match="model_version"):
        endpoint(model_version="   ")
    with pytest.raises(ValueError, match="data_handling_profile"):
        endpoint(data_handling_profile="   ")


def test_endpoint_rejects_a_non_positive_context_limit() -> None:
    with pytest.raises(ValueError, match="context_limit_tokens"):
        endpoint(context_limit_tokens=0)


def test_endpoint_rejects_a_naive_registered_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        endpoint(registered_at=datetime(2026, 9, 4, 12, 0))


def test_request_within_limits() -> None:
    limits = ModelRequestLimits(
        timeout_seconds=30, max_concurrency=4, max_retries=2, max_tokens=4000
    )
    assert is_request_within_limits(requested_tokens=2000, retries_so_far=1, limits=limits)


def test_request_exceeding_token_limit_is_rejected() -> None:
    limits = ModelRequestLimits(
        timeout_seconds=30, max_concurrency=4, max_retries=2, max_tokens=4000
    )
    assert not is_request_within_limits(requested_tokens=5000, retries_so_far=0, limits=limits)


def test_request_exceeding_retry_limit_is_rejected() -> None:
    limits = ModelRequestLimits(
        timeout_seconds=30, max_concurrency=4, max_retries=2, max_tokens=4000
    )
    assert not is_request_within_limits(requested_tokens=100, retries_so_far=3, limits=limits)


def test_request_limits_reject_non_positive_values() -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        ModelRequestLimits(timeout_seconds=0, max_concurrency=1, max_retries=0, max_tokens=1)
    with pytest.raises(ValueError, match="max_concurrency"):
        ModelRequestLimits(timeout_seconds=1, max_concurrency=0, max_retries=0, max_tokens=1)
    with pytest.raises(ValueError, match="max_retries"):
        ModelRequestLimits(timeout_seconds=1, max_concurrency=1, max_retries=-1, max_tokens=1)
    with pytest.raises(ValueError, match="max_tokens"):
        ModelRequestLimits(timeout_seconds=1, max_concurrency=1, max_retries=0, max_tokens=0)
