from __future__ import annotations

from atlas.modules.release.domain.metrics import (
    ReleaseMetric,
    metrics_can_pressure_teams_to_approve_unsafe_releases,
)


def test_release_metric_has_ten_members() -> None:
    assert len(ReleaseMetric) == 10


def test_metrics_never_pressure_teams_to_approve_unsafe_releases() -> None:
    assert metrics_can_pressure_teams_to_approve_unsafe_releases() is False
