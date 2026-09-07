from __future__ import annotations

from itertools import pairwise

import pytest

from atlas.modules.security_export.domain.detection_lifecycle import (
    DetectionLifecycleStage,
    is_valid_transition,
    mapping_or_redaction_failure_exports_the_affected_event,
    possession_of_investigation_link_grants_access,
    siem_alert_can_invoke_atlas_infrastructure_action,
    siem_outage_blocks_atlas_audit_ingestion,
)


def test_lifecycle_has_nine_stages() -> None:
    assert len(DetectionLifecycleStage) == 9


def test_siem_alert_can_never_invoke_infrastructure_action() -> None:
    assert siem_alert_can_invoke_atlas_infrastructure_action() is False


def test_investigation_link_possession_is_never_access() -> None:
    assert possession_of_investigation_link_grants_access() is False


def test_siem_outage_never_blocks_audit_ingestion() -> None:
    assert siem_outage_blocks_atlas_audit_ingestion() is False


def test_mapping_or_redaction_failure_never_exports_affected_event() -> None:
    assert mapping_or_redaction_failure_exports_the_affected_event() is False


def test_full_happy_path_is_valid() -> None:
    path = [
        DetectionLifecycleStage.REGISTERED,
        DetectionLifecycleStage.CONFIGURED_INACTIVE,
        DetectionLifecycleStage.VALIDATED,
        DetectionLifecycleStage.FIXTURES_REPLAYED,
        DetectionLifecycleStage.VERIFIED,
        DetectionLifecycleStage.DEPLOYED_TEST_MODE,
        DetectionLifecycleStage.PRODUCTION_ACTIVE,
        DetectionLifecycleStage.MONITORED,
        DetectionLifecycleStage.RETIRED,
    ]
    for current, target in pairwise(path):
        assert is_valid_transition(current, target)


def test_monitored_can_return_to_production_active_for_tuning() -> None:
    assert is_valid_transition(
        DetectionLifecycleStage.MONITORED, DetectionLifecycleStage.PRODUCTION_ACTIVE
    )


def test_retired_is_terminal() -> None:
    for stage in DetectionLifecycleStage:
        assert not is_valid_transition(DetectionLifecycleStage.RETIRED, stage)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (DetectionLifecycleStage.REGISTERED, DetectionLifecycleStage.PRODUCTION_ACTIVE),
        (DetectionLifecycleStage.CONFIGURED_INACTIVE, DetectionLifecycleStage.RETIRED),
        (DetectionLifecycleStage.VERIFIED, DetectionLifecycleStage.PRODUCTION_ACTIVE),
    ],
)
def test_skipping_a_stage_is_invalid(
    current: DetectionLifecycleStage, target: DetectionLifecycleStage
) -> None:
    assert not is_valid_transition(current, target)
