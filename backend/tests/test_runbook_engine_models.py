from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.capabilities import CapabilityClass
from atlas.core.classification import DataClassification
from atlas.modules.runbook_engine.domain.models import (
    RunbookClass,
    RunbookLifecycleState,
    RunbookVersionMetadata,
    is_allowed_lifecycle_transition,
    typical_capability_ceiling,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def metadata(**overrides: object) -> RunbookVersionMetadata:
    defaults: dict[str, object] = {
        "runbook_id": "runbook.example",
        "version_id": "runbook-version.example",
        "title": "Restart a degraded storage controller.",
        "purpose": "Restore redundancy after a single-controller degradation event.",
        "runbook_class": RunbookClass.RESTORATION,
        "owner": "subject.owner",
        "steward": "subject.steward",
        "authored_by": "subject.author",
        "ai_generated": False,
        "reviewers": ("subject.domain-reviewer",),
        "approver": "subject.approver",
        "state": RunbookLifecycleState.PUBLISHED,
        "capability_class_ceiling": CapabilityClass.C3_CONTROLLED_CHANGE,
        "classification": DataClassification.INTERNAL,
        "source_reference": "vendor-kb.example/12345",
        "derived_from_version_id": None,
        "superseded_by_version_id": None,
        "created_at": NOW,
        "tested_at": NOW,
        "test_environment": "lab.example",
        "test_result": "pass",
        "review_due_at": NOW + timedelta(days=180),
        "expires_at": NOW + timedelta(days=365),
    }
    defaults.update(overrides)
    return RunbookVersionMetadata(**defaults)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "runbook_class",
    [
        RunbookClass.INFORMATIONAL,
        RunbookClass.HEALTH_CHECK,
        RunbookClass.DIAGNOSTIC,
        RunbookClass.RESTORATION,
        RunbookClass.MAINTENANCE,
        RunbookClass.RECOVERY,
        RunbookClass.SECURITY_RESPONSE,
        RunbookClass.VALIDATION,
    ],
)
def test_typical_capability_ceiling_is_defined_for_every_class(
    runbook_class: RunbookClass,
) -> None:
    typical_capability_ceiling(runbook_class)


def test_security_response_has_no_fixed_ceiling() -> None:
    assert typical_capability_ceiling(RunbookClass.SECURITY_RESPONSE) == ()


def test_recovery_ceiling_reaches_c5() -> None:
    assert CapabilityClass.C5_DESTRUCTIVE in typical_capability_ceiling(RunbookClass.RECOVERY)


@pytest.mark.parametrize(
    ("current", "target", "allowed"),
    [
        (RunbookLifecycleState.DRAFT, RunbookLifecycleState.REVIEW, True),
        (RunbookLifecycleState.DRAFT, RunbookLifecycleState.PUBLISHED, False),
        (RunbookLifecycleState.REVIEW, RunbookLifecycleState.DRAFT, True),
        (RunbookLifecycleState.REVIEW, RunbookLifecycleState.APPROVED, True),
        (RunbookLifecycleState.APPROVED, RunbookLifecycleState.PUBLISHED, True),
        (RunbookLifecycleState.APPROVED, RunbookLifecycleState.DRAFT, False),
        (RunbookLifecycleState.PUBLISHED, RunbookLifecycleState.SUSPENDED, True),
        (RunbookLifecycleState.PUBLISHED, RunbookLifecycleState.SUPERSEDED, True),
        (RunbookLifecycleState.PUBLISHED, RunbookLifecycleState.EXPIRED, True),
        (RunbookLifecycleState.PUBLISHED, RunbookLifecycleState.RETIRED, False),
        (RunbookLifecycleState.SUSPENDED, RunbookLifecycleState.PUBLISHED, True),
        (RunbookLifecycleState.SUSPENDED, RunbookLifecycleState.RETIRED, True),
        (RunbookLifecycleState.SUPERSEDED, RunbookLifecycleState.RETIRED, True),
        (RunbookLifecycleState.EXPIRED, RunbookLifecycleState.REVIEW, True),
        (RunbookLifecycleState.EXPIRED, RunbookLifecycleState.RETIRED, True),
        (RunbookLifecycleState.RETIRED, RunbookLifecycleState.DRAFT, False),
    ],
)
def test_lifecycle_transitions_match_the_ss19_diagram(
    current: RunbookLifecycleState, target: RunbookLifecycleState, allowed: bool
) -> None:
    assert is_allowed_lifecycle_transition(current=current, target=target) is allowed


def test_retired_is_terminal() -> None:
    for target in RunbookLifecycleState:
        assert (
            is_allowed_lifecycle_transition(current=RunbookLifecycleState.RETIRED, target=target)
            is False
        )


def test_a_well_formed_metadata_constructs_cleanly() -> None:
    example = metadata()
    assert example.state is RunbookLifecycleState.PUBLISHED


def test_rejects_blank_title() -> None:
    with pytest.raises(ValueError, match="title"):
        metadata(title="   ")


def test_rejects_blank_purpose() -> None:
    with pytest.raises(ValueError, match="purpose"):
        metadata(purpose="   ")


def test_rejects_naive_created_at() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        metadata(created_at=NOW.replace(tzinfo=None))


def test_approved_state_requires_an_approver() -> None:
    with pytest.raises(ValueError, match="requires an approver"):
        metadata(state=RunbookLifecycleState.APPROVED, approver=None)


def test_published_state_requires_an_approver() -> None:
    with pytest.raises(ValueError, match="requires an approver"):
        metadata(state=RunbookLifecycleState.PUBLISHED, approver=None)


def test_draft_state_does_not_require_an_approver() -> None:
    example = metadata(state=RunbookLifecycleState.DRAFT, approver=None)
    assert example.approver is None


def test_approver_cannot_be_the_author() -> None:
    with pytest.raises(ValueError, match="cannot be the sole approver"):
        metadata(authored_by="subject.same", approver="subject.same")


def test_superseded_state_requires_the_superseding_version() -> None:
    with pytest.raises(ValueError, match="version that superseded it"):
        metadata(state=RunbookLifecycleState.SUPERSEDED, superseded_by_version_id=None)


def test_superseded_state_constructs_with_the_superseding_version() -> None:
    example = metadata(
        state=RunbookLifecycleState.SUPERSEDED, superseded_by_version_id="runbook-version.next"
    )
    assert example.superseded_by_version_id == "runbook-version.next"
