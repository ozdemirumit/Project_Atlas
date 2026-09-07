from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.itsm.domain.cmdb_reconciliation import (
    ItsmCiConflictAuthority,
    ItsmCiConflictField,
    ItsmCiMappingRule,
    ItsmCiMatchState,
    ItsmCiReconciliationConflict,
    cmdb_value_silently_overrides_a_live_observation,
    discovery_observation_silently_modifies_the_cmdb,
    write_back_to_the_cmdb_is_enabled_by_default,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


def test_discovery_observation_never_silently_modifies_the_cmdb() -> None:
    assert discovery_observation_silently_modifies_the_cmdb() is False


def test_cmdb_value_never_silently_overrides_a_live_observation() -> None:
    assert cmdb_value_silently_overrides_a_live_observation() is False


def test_write_back_is_never_enabled_by_default() -> None:
    assert write_back_to_the_cmdb_is_enabled_by_default() is False


def test_mapping_rule_builds() -> None:
    rule = ItsmCiMappingRule(
        rule_id="rule.example-001",
        version=1,
        external_ci_class="storage_array",
        atlas_entity_type="storage_system",
        profile_id="profile.example-001",
    )
    assert rule.version == 1


def test_mapping_rule_requires_positive_version() -> None:
    with pytest.raises(ValueError, match="positive version"):
        ItsmCiMappingRule(
            rule_id="rule.example-001",
            version=0,
            external_ci_class="storage_array",
            atlas_entity_type="storage_system",
            profile_id="profile.example-001",
        )


def _conflict(**overrides: object) -> ItsmCiReconciliationConflict:
    defaults: dict[str, object] = {
        "conflict_id": "conflict.example-001",
        "external_ci_id": "external.ci-001",
        "mapped_atlas_entity_id": "entity.example-001",
        "field": ItsmCiConflictField.CRITICALITY,
        "cmdb_value": "medium",
        "cmdb_observed_at": NOW,
        "live_value": "high",
        "live_observed_at": NOW,
        "proposed_authority": ItsmCiConflictAuthority.LIVE_OBSERVATION,
        "confidence": 0.8,
        "match_state": ItsmCiMatchState.MATCHED,
    }
    defaults.update(overrides)
    return ItsmCiReconciliationConflict(**defaults)  # type: ignore[arg-type]


def test_conflict_builds() -> None:
    conflict = _conflict()
    assert conflict.proposed_authority is ItsmCiConflictAuthority.LIVE_OBSERVATION


def test_conflict_requires_disagreeing_values() -> None:
    with pytest.raises(ValueError, match="disagreeing values"):
        _conflict(live_value="medium")


def test_conflict_requires_confidence_in_range() -> None:
    with pytest.raises(ValueError, match="between 0 and 1"):
        _conflict(confidence=1.5)
