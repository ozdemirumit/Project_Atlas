from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.guardrails.domain.context_guardrails import (
    ContextItem,
    ContextTrustState,
    assemble_context_window,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def item(**overrides: object) -> ContextItem:
    defaults: dict[str, object] = {
        "content": "The storage array reports a healthy status.",
        "source": "health-check.example",
        "version": "1",
        "classification": "internal",
        "organization_id": "organization.example",
        "environment_id": "environment.production",
        "observed_at": NOW,
        "trust_state": ContextTrustState.CURRENT,
    }
    defaults.update(overrides)
    return ContextItem(**defaults)  # type: ignore[arg-type]


def test_a_well_formed_item_constructs_cleanly() -> None:
    example = item()
    assert example.is_excludable_by_policy is False


@pytest.mark.parametrize(
    "trust_state",
    [
        ContextTrustState.STALE,
        ContextTrustState.GENERATED,
        ContextTrustState.CONFLICTING,
        ContextTrustState.UNAPPROVED,
    ],
)
def test_non_current_trust_states_are_excludable(trust_state: ContextTrustState) -> None:
    example = item(trust_state=trust_state)
    assert example.is_excludable_by_policy is True


def test_an_item_containing_a_secret_pattern_cannot_be_constructed() -> None:
    with pytest.raises(ValueError, match="secret pattern"):
        item(content="here is my key AKIAIOSFODNN7EXAMPLE")


def test_rejects_blank_required_fields() -> None:
    with pytest.raises(ValueError, match="content"):
        item(content="   ")
    with pytest.raises(ValueError, match="source"):
        item(source="   ")
    with pytest.raises(ValueError, match="version"):
        item(version="   ")
    with pytest.raises(ValueError, match="classification"):
        item(classification="   ")


def test_rejects_a_naive_observed_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        item(observed_at=datetime(2026, 9, 4, 12, 0))


def test_assembly_excludes_a_different_organization() -> None:
    window = assemble_context_window(
        (item(organization_id="organization.other"),),
        organization_id="organization.example",
        environment_id="environment.production",
        max_size_bytes=10_000,
    )
    assert window.items == ()


def test_assembly_excludes_a_different_environment() -> None:
    window = assemble_context_window(
        (item(environment_id="environment.staging"),),
        organization_id="organization.example",
        environment_id="environment.production",
        max_size_bytes=10_000,
    )
    assert window.items == ()


def test_assembly_includes_a_matching_current_item() -> None:
    example = item()
    window = assemble_context_window(
        (example,),
        organization_id="organization.example",
        environment_id="environment.production",
        max_size_bytes=10_000,
    )
    assert window.items == (example,)


def test_assembly_excludes_non_current_items_by_default() -> None:
    stale = item(trust_state=ContextTrustState.STALE)
    window = assemble_context_window(
        (stale,),
        organization_id="organization.example",
        environment_id="environment.production",
        max_size_bytes=10_000,
    )
    assert window.items == ()


def test_assembly_can_include_non_current_items_when_asked() -> None:
    stale = item(trust_state=ContextTrustState.STALE)
    window = assemble_context_window(
        (stale,),
        organization_id="organization.example",
        environment_id="environment.production",
        max_size_bytes=10_000,
        exclude_non_current=False,
    )
    assert window.items == (stale,)


def test_assembly_orders_most_recently_observed_first() -> None:
    older = item(source="a", observed_at=NOW - timedelta(hours=2))
    newer = item(source="b", observed_at=NOW)
    window = assemble_context_window(
        (older, newer),
        organization_id="organization.example",
        environment_id="environment.production",
        max_size_bytes=10_000,
    )
    assert window.items == (newer, older)


def test_assembly_is_bounded_by_size_and_greedily_packs_what_fits() -> None:
    big = item(source="big", content="x" * 100, observed_at=NOW)
    small = item(source="small", content="y" * 10, observed_at=NOW - timedelta(hours=1))
    window = assemble_context_window(
        (big, small),
        organization_id="organization.example",
        environment_id="environment.production",
        max_size_bytes=50,
    )
    # "big" is ordered first (more recent) but does not fit within 50 bytes; "small" does.
    assert window.items == (small,)
    assert window.total_size_bytes == 10


def test_assembly_rejects_a_non_positive_max_size() -> None:
    with pytest.raises(ValueError, match="max_size_bytes must be positive"):
        assemble_context_window(
            (),
            organization_id="organization.example",
            environment_id="environment.production",
            max_size_bytes=0,
        )
