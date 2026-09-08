"""ATLAS-036 SS13: CMDB and Graph reconciliation.

This is the initial CI-to-Atlas entity cross-reference SS26's MVP scope names -- versioned
mapping rules from an external CI class to an Atlas entity type, and an explicit conflict record
when the CMDB and a live observation disagree. Neither side silently wins.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class ItsmCiMatchState(StrEnum):
    """SS13: "Unmatched, duplicate, stale, or ambiguous CI mappings enter a review queue.\""""

    MATCHED = "matched"
    UNMATCHED = "unmatched"
    DUPLICATE = "duplicate"
    STALE = "stale"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class ItsmCiMappingRule:
    """SS13: "ITSM CI classes map to Atlas entity and relationship types through versioned
    rules.\""""

    rule_id: str
    version: int
    external_ci_class: str
    atlas_entity_type: str
    profile_id: str

    def __post_init__(self) -> None:
        for value in (
            self.rule_id,
            self.external_ci_class,
            self.atlas_entity_type,
            self.profile_id,
        ):
            validate_stable_identifier(value, "ITSM CI mapping rule identifier")
        if self.version < 1:
            raise ValueError("an ITSM CI mapping rule requires a positive version")


class ItsmCiConflictField(StrEnum):
    LIFECYCLE_STATE = "lifecycle_state"
    CRITICALITY = "criticality"
    OWNER = "owner"
    ENVIRONMENT = "environment"
    RELATIONSHIP = "relationship"


class ItsmCiConflictAuthority(StrEnum):
    CMDB = "cmdb"
    LIVE_OBSERVATION = "live_observation"


@dataclass(frozen=True, slots=True)
class ItsmCiReconciliationConflict:
    """SS13's required conflict shape: "field, source, observation time, authority, and
    confidence.\""""

    conflict_id: str
    external_ci_id: str
    mapped_atlas_entity_id: str
    field: ItsmCiConflictField
    cmdb_value: str
    cmdb_observed_at: datetime
    live_value: str
    live_observed_at: datetime
    proposed_authority: ItsmCiConflictAuthority
    confidence: float
    match_state: ItsmCiMatchState

    def __post_init__(self) -> None:
        for value in (self.conflict_id, self.mapped_atlas_entity_id):
            validate_stable_identifier(value, "ITSM CI reconciliation conflict identifier")
        if not self.external_ci_id.strip():
            raise ValueError(
                "an ITSM CI reconciliation conflict requires the vendor's own CI identifier"
            )
        if self.cmdb_observed_at.tzinfo is None or self.live_observed_at.tzinfo is None:
            raise ValueError("ITSM CI reconciliation observation times must be timezone-aware")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("ITSM CI reconciliation confidence must be between 0 and 1")
        if self.cmdb_value == self.live_value:
            raise ValueError("an ITSM CI reconciliation conflict requires disagreeing values")


def discovery_observation_silently_modifies_the_cmdb() -> bool:
    """SS13: "Discovery observations do not silently modify the CMDB.\""""
    return False


def cmdb_value_silently_overrides_a_live_observation() -> bool:
    """SS13: "CMDB values do not silently override current live observations.\""""
    return False


def write_back_to_the_cmdb_is_enabled_by_default() -> bool:
    """SS13: "Write-back, if enabled later, is a separately authorized connector
    capability.\""""
    return False
