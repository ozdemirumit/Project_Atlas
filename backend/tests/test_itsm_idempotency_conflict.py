from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.itsm.domain.idempotency_conflict import (
    ItsmConflictKind,
    ItsmConflictRecord,
    ItsmCreationIntent,
    ItsmCreationIntentState,
    ItsmFieldOwnership,
    a_suspected_duplicate_is_silently_merged,
    automatic_last_write_wins_is_permitted_for_consequential_fields,
    human_owned_content_is_overwritten_on_conflict,
    retry_after_timeout_creates_a_second_record,
    state_transition_conflicts_allow_the_workflow_to_proceed,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


def test_retry_after_timeout_never_creates_a_second_record() -> None:
    assert retry_after_timeout_creates_a_second_record() is False


def test_suspected_duplicate_is_never_silently_merged() -> None:
    assert a_suspected_duplicate_is_silently_merged() is False


def test_human_owned_content_is_never_overwritten_on_conflict() -> None:
    assert human_owned_content_is_overwritten_on_conflict() is False


def test_last_write_wins_is_never_permitted_for_consequential_fields() -> None:
    assert automatic_last_write_wins_is_permitted_for_consequential_fields() is False


def test_state_transition_conflicts_never_allow_the_workflow_to_proceed() -> None:
    assert state_transition_conflicts_allow_the_workflow_to_proceed() is False


def test_pending_intent_builds() -> None:
    intent = ItsmCreationIntent(
        intent_id="intent.example-001",
        idempotency_key="idempotency.example-001",
        profile_id="profile.example-001",
        operation="create_incident_draft",
        deduplication_signature="dedup.example-001",
        state=ItsmCreationIntentState.PENDING,
        created_at=NOW,
        resolved_at=None,
        external_record_id=None,
    )
    assert intent.state is ItsmCreationIntentState.PENDING


def test_confirmed_intent_requires_external_record_id() -> None:
    with pytest.raises(ValueError, match="external record id"):
        ItsmCreationIntent(
            intent_id="intent.example-001",
            idempotency_key="idempotency.example-001",
            profile_id="profile.example-001",
            operation="create_incident_draft",
            deduplication_signature="dedup.example-001",
            state=ItsmCreationIntentState.CONFIRMED_CREATED,
            created_at=NOW,
            resolved_at=NOW,
            external_record_id=None,
        )


def test_resolved_state_requires_resolution_time() -> None:
    with pytest.raises(ValueError, match="resolution time tracks its state"):
        ItsmCreationIntent(
            intent_id="intent.example-001",
            idempotency_key="idempotency.example-001",
            profile_id="profile.example-001",
            operation="create_incident_draft",
            deduplication_signature="dedup.example-001",
            state=ItsmCreationIntentState.RECONCILED_DUPLICATE,
            created_at=NOW,
            resolved_at=None,
            external_record_id=None,
        )


def test_conflict_record_builds_unresolved() -> None:
    conflict = ItsmConflictRecord(
        conflict_id="conflict.example-001",
        profile_id="profile.example-001",
        external_record_id="external.rec-001",
        kind=ItsmConflictKind.STALE_VERSION,
        last_known_source_version="version.1",
        observed_source_version="version.2",
        field_ownership=ItsmFieldOwnership.HUMAN_OWNED,
        detected_at=NOW,
        resolution_summary=None,
        resolved_by=None,
        resolved_at=None,
    )
    assert conflict.kind is ItsmConflictKind.STALE_VERSION


def test_conflict_resolution_requires_all_fields_together() -> None:
    with pytest.raises(ValueError, match="summary, actor, and time"):
        ItsmConflictRecord(
            conflict_id="conflict.example-001",
            profile_id="profile.example-001",
            external_record_id="external.rec-001",
            kind=ItsmConflictKind.STALE_VERSION,
            last_known_source_version="version.1",
            observed_source_version="version.2",
            field_ownership=ItsmFieldOwnership.HUMAN_OWNED,
            detected_at=NOW,
            resolution_summary="resolved by refresh",
            resolved_by=None,
            resolved_at=NOW,
        )


def test_conflict_cannot_resolve_before_it_was_detected() -> None:
    with pytest.raises(ValueError, match="cannot resolve before"):
        ItsmConflictRecord(
            conflict_id="conflict.example-001",
            profile_id="profile.example-001",
            external_record_id="external.rec-001",
            kind=ItsmConflictKind.STALE_VERSION,
            last_known_source_version="version.1",
            observed_source_version="version.2",
            field_ownership=ItsmFieldOwnership.HUMAN_OWNED,
            detected_at=NOW,
            resolution_summary="resolved",
            resolved_by="subject.owner",
            resolved_at=datetime(2026, 9, 6, 12, 0, tzinfo=UTC),
        )
