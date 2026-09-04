"""ATLAS-025 SS19: decision validity and caching.

"Decisions are short-lived and bound to exact input context" -- this cache is a single
evaluation process's own short-lived memoization, not a persistent or distributed store. Any
invalidation call removes matching entries outright rather than marking them stale, since a
lingering stale Allow entry is exactly what SS19 warns against ("deny decisions may be cached
only without hiding urgent policy change").
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from atlas.modules.policy_engine.domain.models import PolicyDecision


@dataclass(frozen=True, slots=True)
class PolicyDecisionCacheKey:
    """SS19: "Allow caching requires policy version, actor, operation, target, parameter digest,
    and expiry" -- expiry is a TTL on the cache entry, not part of the key; everything else forms
    it. Used uniformly for Allow and Deny entries alike -- SS19 only requires this exact binding
    for Allow, but applying it to Deny too is strictly safer, never wrong."""

    policy_set_versions: tuple[str, ...]
    actor_id: str
    operation_id: str
    target_id: str
    parameter_digest: str


@dataclass(frozen=True, slots=True)
class _CacheEntry:
    decision: PolicyDecision
    expires_at: datetime


class PolicyDecisionCache:
    def __init__(self) -> None:
        self._entries: dict[PolicyDecisionCacheKey, _CacheEntry] = {}

    def get(self, key: PolicyDecisionCacheKey, *, now: datetime) -> PolicyDecision | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        if entry.expires_at <= now:
            del self._entries[key]
            return None
        return entry.decision

    def put(
        self,
        key: PolicyDecisionCacheKey,
        decision: PolicyDecision,
        *,
        now: datetime,
        ttl: timedelta,
    ) -> None:
        if ttl.total_seconds() <= 0:
            raise ValueError("a cache entry requires a positive ttl")
        if decision.actor_id != key.actor_id or decision.operation_id != key.operation_id:
            raise ValueError("a cached decision must match its own cache key")
        self._entries[key] = _CacheEntry(decision=decision, expires_at=now + ttl)

    def invalidate_for_actor(self, actor_id: str) -> None:
        """Connector, approval, security, or target-state changes can invalidate decisions
        (SS19); this is the coarse-grained primitive a caller uses for "this actor's cached
        decisions may no longer be valid" -- e.g. their approval was revoked, their role
        changed. Finer-grained invalidation (by target, by connector) is a caller concern until
        a real need for it is demonstrated."""
        stale_keys = [key for key in self._entries if key.actor_id == actor_id]
        for key in stale_keys:
            del self._entries[key]

    def invalidate_all(self) -> None:
        self._entries.clear()

    def size(self) -> int:
        return len(self._entries)
