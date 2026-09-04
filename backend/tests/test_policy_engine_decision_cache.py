from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.policy_engine.domain.decision_cache import (
    PolicyDecisionCache,
    PolicyDecisionCacheKey,
)
from atlas.modules.policy_engine.domain.models import (
    PolicyDecision,
    PolicyDecisionOutcome,
    PolicyReason,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def decision(
    *, actor_id: str = "subject.example", operation_id: str = "operation.example"
) -> PolicyDecision:
    return PolicyDecision(
        decision_id="policy-decision.example",
        decided_at=NOW,
        outcome=PolicyDecisionOutcome.ALLOW,
        reasons=(),
        decision_request_id="policy-decision-request.example",
        correlation_id="correlation.example",
        actor_id=actor_id,
        operation_id=operation_id,
        non_overridable_rule_references=(),
    )


def deny_decision() -> PolicyDecision:
    return PolicyDecision(
        decision_id="policy-decision.example",
        decided_at=NOW,
        outcome=PolicyDecisionOutcome.DENY,
        reasons=(PolicyReason(summary="Example denial."),),
        decision_request_id="policy-decision-request.example",
        correlation_id="correlation.example",
        actor_id="subject.example",
        operation_id="operation.example",
        non_overridable_rule_references=(),
    )


def key(**overrides: object) -> PolicyDecisionCacheKey:
    defaults: dict[str, object] = {
        "policy_set_versions": ("policy-set.platform:v1",),
        "actor_id": "subject.example",
        "operation_id": "operation.example",
        "target_id": "target.example",
        "parameter_digest": "c" * 64,
    }
    defaults.update(overrides)
    return PolicyDecisionCacheKey(**defaults)  # type: ignore[arg-type]


def test_a_miss_returns_none() -> None:
    cache = PolicyDecisionCache()
    assert cache.get(key(), now=NOW) is None


def test_a_put_decision_is_returned_by_a_matching_key() -> None:
    cache = PolicyDecisionCache()
    cache.put(key(), decision(), now=NOW, ttl=timedelta(minutes=1))
    assert cache.get(key(), now=NOW) is not None


def test_a_different_key_is_a_miss() -> None:
    cache = PolicyDecisionCache()
    cache.put(key(), decision(), now=NOW, ttl=timedelta(minutes=1))
    assert cache.get(key(target_id="target.other"), now=NOW) is None


def test_an_entry_expires_after_its_ttl() -> None:
    cache = PolicyDecisionCache()
    cache.put(key(), decision(), now=NOW, ttl=timedelta(seconds=30))
    assert cache.get(key(), now=NOW + timedelta(seconds=29)) is not None
    assert cache.get(key(), now=NOW + timedelta(seconds=31)) is None


def test_an_expired_entry_is_evicted_not_just_hidden() -> None:
    cache = PolicyDecisionCache()
    cache.put(key(), decision(), now=NOW, ttl=timedelta(seconds=1))
    assert cache.get(key(), now=NOW + timedelta(seconds=2)) is None
    assert cache.size() == 0


def test_put_rejects_a_non_positive_ttl() -> None:
    cache = PolicyDecisionCache()
    with pytest.raises(ValueError, match="positive ttl"):
        cache.put(key(), decision(), now=NOW, ttl=timedelta(seconds=0))


def test_put_rejects_a_decision_that_does_not_match_its_own_key() -> None:
    cache = PolicyDecisionCache()
    with pytest.raises(ValueError, match="must match"):
        cache.put(key(), decision(actor_id="subject.other"), now=NOW, ttl=timedelta(minutes=1))


def test_a_deny_decision_can_be_cached_the_same_way() -> None:
    cache = PolicyDecisionCache()
    cache.put(key(), deny_decision(), now=NOW, ttl=timedelta(seconds=10))
    cached = cache.get(key(), now=NOW)
    assert cached is not None
    assert cached.outcome is PolicyDecisionOutcome.DENY


def test_invalidate_for_actor_removes_only_that_actors_entries() -> None:
    cache = PolicyDecisionCache()
    cache.put(
        key(actor_id="subject.a"), decision(actor_id="subject.a"), now=NOW, ttl=timedelta(minutes=1)
    )
    cache.put(
        key(actor_id="subject.b"), decision(actor_id="subject.b"), now=NOW, ttl=timedelta(minutes=1)
    )
    cache.invalidate_for_actor("subject.a")
    assert cache.get(key(actor_id="subject.a"), now=NOW) is None
    assert cache.get(key(actor_id="subject.b"), now=NOW) is not None


def test_invalidate_all_clears_every_entry() -> None:
    cache = PolicyDecisionCache()
    cache.put(key(), decision(), now=NOW, ttl=timedelta(minutes=1))
    cache.invalidate_all()
    assert cache.size() == 0
    assert cache.get(key(), now=NOW) is None
