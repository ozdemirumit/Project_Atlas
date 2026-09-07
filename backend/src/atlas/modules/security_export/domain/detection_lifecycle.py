"""ATLAS-035 SS16/SS17/SS19: content and integration lifecycle, and the failure/investigation
rules that constrain what a SIEM destination can ever do with Atlas."""

from __future__ import annotations

from enum import StrEnum


class DetectionLifecycleStage(StrEnum):
    """SS19's nine-step content and integration lifecycle."""

    REGISTERED = "registered"
    CONFIGURED_INACTIVE = "configured_inactive"
    VALIDATED = "validated"
    FIXTURES_REPLAYED = "fixtures_replayed"
    VERIFIED = "verified"
    DEPLOYED_TEST_MODE = "deployed_test_mode"
    PRODUCTION_ACTIVE = "production_active"
    MONITORED = "monitored"
    RETIRED = "retired"


_ALLOWED_TRANSITIONS: dict[DetectionLifecycleStage, frozenset[DetectionLifecycleStage]] = {
    DetectionLifecycleStage.REGISTERED: frozenset({DetectionLifecycleStage.CONFIGURED_INACTIVE}),
    DetectionLifecycleStage.CONFIGURED_INACTIVE: frozenset({DetectionLifecycleStage.VALIDATED}),
    DetectionLifecycleStage.VALIDATED: frozenset({DetectionLifecycleStage.FIXTURES_REPLAYED}),
    DetectionLifecycleStage.FIXTURES_REPLAYED: frozenset({DetectionLifecycleStage.VERIFIED}),
    DetectionLifecycleStage.VERIFIED: frozenset({DetectionLifecycleStage.DEPLOYED_TEST_MODE}),
    DetectionLifecycleStage.DEPLOYED_TEST_MODE: frozenset(
        {DetectionLifecycleStage.PRODUCTION_ACTIVE, DetectionLifecycleStage.VALIDATED}
    ),
    DetectionLifecycleStage.PRODUCTION_ACTIVE: frozenset(
        {DetectionLifecycleStage.MONITORED, DetectionLifecycleStage.RETIRED}
    ),
    DetectionLifecycleStage.MONITORED: frozenset(
        {
            DetectionLifecycleStage.PRODUCTION_ACTIVE,
            DetectionLifecycleStage.CONFIGURED_INACTIVE,
            DetectionLifecycleStage.RETIRED,
        }
    ),
    DetectionLifecycleStage.RETIRED: frozenset(),
}


def is_valid_transition(
    current: DetectionLifecycleStage,
    target: DetectionLifecycleStage,
) -> bool:
    return target in _ALLOWED_TRANSITIONS[current]


def siem_alert_can_invoke_atlas_infrastructure_action() -> bool:
    """SS16: "SIEM alerts cannot directly invoke Atlas infrastructure actions.\""""
    return False


def possession_of_investigation_link_grants_access() -> bool:
    """SS17: "Atlas re-authorizes every view; possession of a SIEM link is not access.\""""
    return False


def siem_outage_blocks_atlas_audit_ingestion() -> bool:
    """SS16: "SIEM outage never blocks Atlas audit ingestion.\""""
    return False


def mapping_or_redaction_failure_exports_the_affected_event() -> bool:
    """SS16: "Mapping or redaction failure quarantines affected exports and alerts owners.\""""
    return False
