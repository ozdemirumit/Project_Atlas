"""ATLAS-047 SS12: context guardrails.

Reuses `input_guardrails.detect_secret_patterns` (slice 3) to enforce "secret references are not
resolved into model-visible values" at construction time -- a `ContextItem` simply cannot be
built if its content matches a known secret shape, rather than relying on every call site to
remember to check.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.guardrails.domain.input_guardrails import detect_secret_patterns
from atlas.modules.identity.domain.models import validate_stable_identifier


class ContextTrustState(StrEnum):
    """SS12: "stale, generated, conflicting, or unapproved content is labeled and can be
    excluded by policy." CURRENT is the only state that is never excludable by that clause."""

    CURRENT = "current"
    STALE = "stale"
    GENERATED = "generated"
    CONFLICTING = "conflicting"
    UNAPPROVED = "unapproved"


@dataclass(frozen=True, slots=True)
class ContextItem:
    """SS12: "every item carries source, version, classification, scope, time, and trust
    state.\""""

    content: str
    source: str
    version: str
    classification: str
    organization_id: str
    environment_id: str
    observed_at: datetime
    trust_state: ContextTrustState

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValueError("a context item requires non-empty content")
        if not self.source.strip():
            raise ValueError("a context item requires a source")
        if not self.version.strip():
            raise ValueError("a context item requires a version")
        if not self.classification.strip():
            raise ValueError("a context item requires a classification")
        validate_stable_identifier(self.organization_id, "organization_id")
        validate_stable_identifier(self.environment_id, "environment_id")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        detected = detect_secret_patterns(self.content)
        if detected:
            raise ValueError(
                "a context item's content matches a known secret pattern and cannot be included"
                f" as model-visible context: {', '.join(detected)}"
            )

    @property
    def is_excludable_by_policy(self) -> bool:
        return self.trust_state is not ContextTrustState.CURRENT


@dataclass(frozen=True, slots=True)
class ContextWindow:
    items: tuple[ContextItem, ...]
    total_size_bytes: int


def assemble_context_window(
    candidates: tuple[ContextItem, ...],
    *,
    organization_id: str,
    environment_id: str,
    max_size_bytes: int,
    exclude_non_current: bool = True,
) -> ContextWindow:
    """SS12: just-in-time assembly from authorized sources only. Cross-organization and
    cross-environment items are never mixed in (SS12's "cross-user and cross-organization
    conversation state is isolated," applied at the scope level this type can actually check).
    Bounded size with deterministic prioritization: authorized, in-scope candidates are ordered
    most-recently-observed first, then packed greedily up to `max_size_bytes` -- the same
    candidate set always assembles the same window, in the same order, every time."""
    if max_size_bytes < 1:
        raise ValueError("max_size_bytes must be positive")
    authorized = [
        item
        for item in candidates
        if item.organization_id == organization_id and item.environment_id == environment_id
    ]
    if exclude_non_current:
        authorized = [item for item in authorized if item.trust_state is ContextTrustState.CURRENT]
    ordered = sorted(authorized, key=lambda item: item.observed_at, reverse=True)

    selected: list[ContextItem] = []
    running_size = 0
    for item in ordered:
        item_size = len(item.content.encode("utf-8"))
        if running_size + item_size > max_size_bytes:
            continue
        selected.append(item)
        running_size += item_size
    return ContextWindow(items=tuple(selected), total_size_bytes=running_size)
