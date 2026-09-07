from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.classification import DataClassification
from atlas.modules.graph.domain.models import EntityType, FreshnessState, GraphEntity
from atlas.modules.graph.domain.reconciliation import (
    GraphManualOverride,
    GraphReconciliationConflict,
    SourceAuthorityRanking,
    a_later_lower_authority_observation_overrides_a_higher_authority_source,
    reconcile_entities,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


def _entity(entity_id: str, *, display_name: str, observed_at: datetime = NOW) -> GraphEntity:
    return GraphEntity(
        entity_id=entity_id,
        entity_type=EntityType.STORAGE_SYSTEM,
        display_name=display_name,
        organization_id="organization.example",
        environment_id="environment.prod",
        site_id="site.primary",
        domain_id="domain.storage",
        observed_at=observed_at,
        valid_from=observed_at,
        valid_to=None,
        freshness=FreshnessState.FRESH,
        confidence_basis="direct vendor observation",
        evidence_references=("evidence.example-001",),
        classification=DataClassification.INTERNAL,
        allowed_principals=frozenset({"role.infrastructure-engineer"}),
    )


def test_absolute_rule_is_false() -> None:
    assert a_later_lower_authority_observation_overrides_a_higher_authority_source() is False


def test_single_source_entity_has_no_conflict() -> None:
    entity = _entity("entity.array-01", display_name="Array 01")
    resolved, conflicts = reconcile_entities(
        (("configured_hitachi", (entity,)),),
        authority=SourceAuthorityRanking(ranks={}),
    )
    assert resolved == (entity,)
    assert conflicts == ()


def test_agreeing_sources_produce_no_conflict() -> None:
    entity_a = _entity("entity.array-01", display_name="Array 01")
    entity_b = _entity("entity.array-01", display_name="Array 01")
    resolved, conflicts = reconcile_entities(
        (
            ("configured_hitachi", (entity_a,)),
            ("configured_brocade_sannav", (entity_b,)),
        ),
        authority=SourceAuthorityRanking(ranks={}),
    )
    assert resolved == (entity_a,)
    assert conflicts == ()


def test_disagreeing_sources_pick_the_higher_authority_source() -> None:
    hitachi = _entity("entity.array-01", display_name="Array 01 (Hitachi)")
    brocade = _entity("entity.array-01", display_name="Array 01 (Brocade)")
    resolved, conflicts = reconcile_entities(
        (
            ("configured_brocade_sannav", (brocade,)),
            ("configured_hitachi", (hitachi,)),
        ),
        authority=SourceAuthorityRanking(
            ranks={"configured_hitachi": 10, "configured_brocade_sannav": 5}
        ),
    )
    assert resolved == (hitachi,)
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert isinstance(conflict, GraphReconciliationConflict)
    assert conflict.identifier == "entity.array-01"
    assert conflict.chosen_source == "configured_hitachi"
    assert conflict.resolution_basis == "higher_authority"
    assert set(conflict.competing_sources) == {"configured_hitachi", "configured_brocade_sannav"}


def test_a_later_lower_authority_source_never_wins() -> None:
    higher_but_earlier = _entity(
        "entity.array-01", display_name="Authoritative", observed_at=NOW - timedelta(hours=1)
    )
    lower_but_later = _entity("entity.array-01", display_name="Stale challenger", observed_at=NOW)
    resolved, conflicts = reconcile_entities(
        (
            ("configured_hitachi", (higher_but_earlier,)),
            ("configured_brocade_sannav", (lower_but_later,)),
        ),
        authority=SourceAuthorityRanking(
            ranks={"configured_hitachi": 10, "configured_brocade_sannav": 5}
        ),
    )
    assert resolved == (higher_but_earlier,)
    assert conflicts[0].chosen_source == "configured_hitachi"


def test_equal_authority_breaks_tie_with_most_recent_observation() -> None:
    older = _entity("entity.array-01", display_name="Older", observed_at=NOW - timedelta(hours=1))
    newer = _entity("entity.array-01", display_name="Newer", observed_at=NOW)
    resolved, conflicts = reconcile_entities(
        (
            ("configured_hitachi", (older,)),
            ("configured_brocade_sannav", (newer,)),
        ),
        authority=SourceAuthorityRanking(ranks={}),
    )
    assert resolved == (newer,)
    assert conflicts[0].resolution_basis == "most_recent_at_equal_authority"


def test_manual_override_takes_precedence_over_computed_authority() -> None:
    hitachi = _entity("entity.array-01", display_name="Array 01 (Hitachi)")
    brocade = _entity("entity.array-01", display_name="Array 01 (Brocade)")
    override = GraphManualOverride(
        identifier="entity.array-01",
        chosen_source="configured_brocade_sannav",
        reviewed_by="subject.reviewer",
        reason="Brocade's fabric-side observation is more current for this array's identity.",
        applied_at=NOW,
    )
    resolved, conflicts = reconcile_entities(
        (
            ("configured_brocade_sannav", (brocade,)),
            ("configured_hitachi", (hitachi,)),
        ),
        authority=SourceAuthorityRanking(
            ranks={"configured_hitachi": 10, "configured_brocade_sannav": 5}
        ),
        overrides=(override,),
    )
    assert resolved == (brocade,)
    assert conflicts[0].chosen_source == "configured_brocade_sannav"
    assert conflicts[0].resolution_basis == "manual_override"


def test_conflict_requires_at_least_two_competing_sources() -> None:
    with pytest.raises(ValueError, match="at least two"):
        GraphReconciliationConflict(
            identifier="entity.array-01",
            competing_sources=("configured_hitachi",),
            chosen_source="configured_hitachi",
            resolution_basis="higher_authority",
        )


def test_conflict_requires_chosen_source_among_competing() -> None:
    with pytest.raises(ValueError, match="must be one of"):
        GraphReconciliationConflict(
            identifier="entity.array-01",
            competing_sources=("configured_hitachi", "configured_brocade_sannav"),
            chosen_source="configured_vcenter",
            resolution_basis="higher_authority",
        )


def test_manual_override_requires_reviewer_and_reason() -> None:
    with pytest.raises(ValueError, match="reviewer and a reason"):
        GraphManualOverride(
            identifier="entity.array-01",
            chosen_source="configured_hitachi",
            reviewed_by="",
            reason="",
            applied_at=NOW,
        )
