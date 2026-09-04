from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.policy_engine.adapters.policy_set_memory import InMemoryPolicySetRepository
from atlas.modules.policy_engine.domain.policy_set import (
    PolicyLifecycleState,
    PolicySet,
    PolicySetLayer,
    PolicySetResolutionScope,
    PolicySetScope,
    resolve_policy_sets,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
DIGEST = "f" * 64


def policy_set(
    *,
    set_id: str,
    layer: PolicySetLayer,
    scope: PolicySetScope | None = None,
    lifecycle_state: PolicyLifecycleState = PolicyLifecycleState.ACTIVE,
    version: int = 1,
    effective_from: datetime | None = None,
    effective_until: datetime | None = None,
) -> PolicySet:
    return PolicySet(
        set_id=set_id,
        version=version,
        layer=layer,
        lifecycle_state=lifecycle_state,
        scope=scope if scope is not None else PolicySetScope(),
        rule_document_digest=DIGEST,
        effective_from=effective_from if effective_from is not None else NOW - timedelta(days=1),
        effective_until=effective_until,
    )


def scope(**overrides: object) -> PolicySetResolutionScope:
    defaults: dict[str, object] = {
        "organization_id": "organization.acme",
        "environment_id": "environment.production",
    }
    defaults.update(overrides)
    return PolicySetResolutionScope(**defaults)  # type: ignore[arg-type]


def test_a_platform_layer_set_with_an_empty_scope_matches_every_request() -> None:
    platform = policy_set(set_id="policy-set.platform-baseline", layer=PolicySetLayer.PLATFORM)
    resolved = resolve_policy_sets([platform], scope=scope(), at=NOW)
    assert resolved == (platform,)


def test_an_organization_layer_set_only_matches_its_own_organization() -> None:
    org_set = policy_set(
        set_id="policy-set.acme-org",
        layer=PolicySetLayer.ORGANIZATION,
        scope=PolicySetScope(organization_id="organization.acme"),
    )
    assert resolve_policy_sets([org_set], scope=scope(), at=NOW) == (org_set,)
    other_org_scope = scope(organization_id="organization.other")
    assert resolve_policy_sets([org_set], scope=other_org_scope, at=NOW) == ()


def test_a_workflow_layer_set_requires_an_exact_workflow_match() -> None:
    workflow_set = policy_set(
        set_id="policy-set.upgrade-workflow",
        layer=PolicySetLayer.WORKFLOW,
        scope=PolicySetScope(workflow_id="workflow.governed-upgrade"),
    )
    matching_scope = scope(workflow_id="workflow.governed-upgrade")
    assert resolve_policy_sets([workflow_set], scope=matching_scope, at=NOW) == (workflow_set,)
    # A request with no workflow context at all does not match a workflow-scoped set.
    assert resolve_policy_sets([workflow_set], scope=scope(), at=NOW) == ()


def test_only_active_lifecycle_state_sets_are_resolved() -> None:
    for state in PolicyLifecycleState:
        candidate = policy_set(
            set_id="policy-set.example", layer=PolicySetLayer.PLATFORM, lifecycle_state=state
        )
        resolved = resolve_policy_sets([candidate], scope=scope(), at=NOW)
        if state is PolicyLifecycleState.ACTIVE:
            assert resolved == (candidate,)
        else:
            assert resolved == (), f"{state} must not resolve"


def test_a_set_effective_in_the_future_does_not_resolve_yet() -> None:
    future = policy_set(
        set_id="policy-set.future",
        layer=PolicySetLayer.PLATFORM,
        effective_from=NOW + timedelta(days=1),
    )
    assert resolve_policy_sets([future], scope=scope(), at=NOW) == ()
    assert resolve_policy_sets([future], scope=scope(), at=NOW + timedelta(days=2)) == (future,)


def test_a_set_past_its_effective_until_no_longer_resolves() -> None:
    expiring = policy_set(
        set_id="policy-set.expiring",
        layer=PolicySetLayer.PLATFORM,
        effective_from=NOW - timedelta(days=2),
        effective_until=NOW - timedelta(days=1),
    )
    assert resolve_policy_sets([expiring], scope=scope(), at=NOW) == ()


def test_resolution_orders_from_the_most_general_layer_to_the_most_specific() -> None:
    workflow_set = policy_set(set_id="policy-set.z-workflow", layer=PolicySetLayer.WORKFLOW)
    platform_set = policy_set(set_id="policy-set.a-platform", layer=PolicySetLayer.PLATFORM)
    service_set = policy_set(set_id="policy-set.m-service", layer=PolicySetLayer.SERVICE)
    resolved = resolve_policy_sets([workflow_set, platform_set, service_set], scope=scope(), at=NOW)
    assert resolved == (platform_set, service_set, workflow_set)


def test_resolution_breaks_ties_within_a_layer_by_set_id() -> None:
    second = policy_set(set_id="policy-set.b", layer=PolicySetLayer.PLATFORM)
    first = policy_set(set_id="policy-set.a", layer=PolicySetLayer.PLATFORM)
    resolved = resolve_policy_sets([second, first], scope=scope(), at=NOW)
    assert resolved == (first, second)


def test_policy_set_rejects_a_non_sha256_digest() -> None:
    with pytest.raises(ValueError, match="SHA-256"):
        PolicySet(
            set_id="policy-set.bad-digest",
            version=1,
            layer=PolicySetLayer.PLATFORM,
            lifecycle_state=PolicyLifecycleState.ACTIVE,
            scope=PolicySetScope(),
            rule_document_digest="too-short",
            effective_from=NOW,
        )


def test_policy_set_rejects_effective_until_before_effective_from() -> None:
    with pytest.raises(ValueError, match="later than effective_from"):
        policy_set(
            set_id="policy-set.bad-window",
            layer=PolicySetLayer.PLATFORM,
            effective_from=NOW,
            effective_until=NOW - timedelta(days=1),
        )


def test_version_reference_format() -> None:
    example = policy_set(set_id="policy-set.example", layer=PolicySetLayer.PLATFORM, version=3)
    assert example.version_reference == "policy-set.example:v3"


@pytest.mark.asyncio
async def test_in_memory_repository_stores_multiple_versions_of_the_same_set() -> None:
    v1 = policy_set(set_id="policy-set.example", layer=PolicySetLayer.PLATFORM, version=1)
    v2 = policy_set(set_id="policy-set.example", layer=PolicySetLayer.PLATFORM, version=2)
    repository = InMemoryPolicySetRepository((v1,))
    repository.add(v2)
    stored = await repository.list_all()
    assert set(stored) == {v1, v2}


@pytest.mark.asyncio
async def test_in_memory_repository_replaces_a_set_when_the_same_version_is_added_again() -> None:
    v1 = policy_set(set_id="policy-set.example", layer=PolicySetLayer.PLATFORM, version=1)
    v1_updated = policy_set(
        set_id="policy-set.example",
        layer=PolicySetLayer.PLATFORM,
        version=1,
        lifecycle_state=PolicyLifecycleState.SUSPENDED,
    )
    repository = InMemoryPolicySetRepository((v1,))
    repository.add(v1_updated)
    stored = await repository.list_all()
    assert stored == (v1_updated,)
