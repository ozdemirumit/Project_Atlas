"""ATLAS-047 SS20: model endpoint guardrails.

`select_fallback_endpoint` is the load-bearing function: SS20: "fallback cannot route data to a
less trusted endpoint silently." It only ever returns a healthy candidate whose trust tier is at
least the primary's own, and returns None -- deterministic unavailability, SS20's own required
behavior on outage -- rather than ever silently picking something less trusted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class ModelEndpointHealthState(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ModelEndpoint:
    """SS20: "approved model IDs, versions, features, context limits, and data-handling
    profiles are explicit." `trust_tier` is a plain ordering (higher is more trusted) a caller
    assigns; this type does not itself decide what makes one endpoint more trusted than another,
    only enforces that fallback never moves to a lower one."""

    endpoint_id: str
    model_id: str
    model_version: str
    trust_tier: int
    context_limit_tokens: int
    data_handling_profile: str
    health_state: ModelEndpointHealthState
    registered_at: datetime

    def __post_init__(self) -> None:
        validate_stable_identifier(self.endpoint_id, "endpoint_id")
        if not self.model_id.strip():
            raise ValueError("a model endpoint requires a model_id")
        if not self.model_version.strip():
            raise ValueError("a model endpoint requires a model_version")
        if not self.data_handling_profile.strip():
            raise ValueError("a model endpoint requires a data_handling_profile")
        if self.context_limit_tokens < 1:
            raise ValueError("context_limit_tokens must be positive")
        if self.registered_at.tzinfo is None:
            raise ValueError("registered_at must be timezone-aware")


def select_fallback_endpoint(
    primary: ModelEndpoint, candidates: tuple[ModelEndpoint, ...]
) -> ModelEndpoint | None:
    eligible = [
        candidate
        for candidate in candidates
        if candidate.health_state is ModelEndpointHealthState.HEALTHY
        and candidate.trust_tier >= primary.trust_tier
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda candidate: candidate.trust_tier)


@dataclass(frozen=True, slots=True)
class ModelRequestLimits:
    """SS20: "requests use timeouts, concurrency, rate, token, and retry bounds.\""""

    timeout_seconds: int
    max_concurrency: int
    max_retries: int
    max_tokens: int

    def __post_init__(self) -> None:
        if self.timeout_seconds < 1:
            raise ValueError("timeout_seconds must be positive")
        if self.max_concurrency < 1:
            raise ValueError("max_concurrency must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries must not be negative")
        if self.max_tokens < 1:
            raise ValueError("max_tokens must be positive")


def is_request_within_limits(
    *, requested_tokens: int, retries_so_far: int, limits: ModelRequestLimits
) -> bool:
    return requested_tokens <= limits.max_tokens and retries_so_far <= limits.max_retries
