from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.classification import DataClassification
from atlas.modules.ai_agents.domain.context import (
    AssembledContext,
    ContextItem,
    ContextItemLabel,
    ContextSourceKind,
    is_authorized_for,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def item(**overrides: object) -> ContextItem:
    defaults: dict[str, object] = {
        "item_id": "context-item.example",
        "source_kind": ContextSourceKind.HEALTH_AND_CONNECTOR_OBSERVATIONS,
        "source_reference": "observation.controller-b.latency",
        "version": "1",
        "observed_at": NOW,
        "classification": DataClassification.INTERNAL,
        "authorized_principals": frozenset({"role.storage.operator"}),
        "labels": (ContextItemLabel.NONE,),
    }
    defaults.update(overrides)
    return ContextItem(**defaults)  # type: ignore[arg-type]


def test_context_item_accepts_valid_state() -> None:
    assert item().source_kind is ContextSourceKind.HEALTH_AND_CONNECTOR_OBSERVATIONS


def test_context_item_requires_access_policy() -> None:
    with pytest.raises(ValueError, match="access policy"):
        item(authorized_principals=frozenset())


def test_context_item_rejects_duplicate_label() -> None:
    with pytest.raises(ValueError, match="must not repeat a label"):
        item(labels=(ContextItemLabel.STALE, ContextItemLabel.STALE))


def test_context_item_rejects_none_combined_with_other_labels() -> None:
    with pytest.raises(ValueError, match="cannot be combined"):
        item(labels=(ContextItemLabel.NONE, ContextItemLabel.STALE))


def test_context_item_accepts_multiple_real_labels() -> None:
    result = item(labels=(ContextItemLabel.STALE, ContextItemLabel.CONFLICTING))
    assert ContextItemLabel.STALE in result.labels


def test_is_authorized_for_true_for_matching_principal() -> None:
    assert is_authorized_for(item(), principal="role.storage.operator") is True


def test_is_authorized_for_false_for_other_principal() -> None:
    assert is_authorized_for(item(), principal="role.other") is False


def test_assembled_context_requires_at_least_one_item() -> None:
    with pytest.raises(ValueError, match="at least one item"):
        AssembledContext(task_id="task.example", items=(), assembled_at=NOW)


def test_flagged_items_excludes_unlabeled() -> None:
    labeled = item(item_id="context-item.labeled", labels=(ContextItemLabel.STALE,))
    unlabeled = item(item_id="context-item.plain", labels=(ContextItemLabel.NONE,))
    context = AssembledContext(task_id="task.example", items=(labeled, unlabeled), assembled_at=NOW)
    assert context.flagged_items == (labeled,)
