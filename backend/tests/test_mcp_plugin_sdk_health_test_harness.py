from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.modules.connectors.domain.models import ConnectorHealth
from atlas.modules.mcp_plugin_sdk.domain.health_test_harness import (
    HarnessCapability,
    HarnessDeclaration,
    HealthCheckKind,
    HealthCheckResult,
    HealthReport,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def check(
    kind: HealthCheckKind, status: ConnectorHealth = ConnectorHealth.HEALTHY
) -> HealthCheckResult:
    return HealthCheckResult(kind=kind, status=status, detail="checked", checked_at=NOW)


def full_report(overrides: dict[HealthCheckKind, ConnectorHealth] | None = None) -> HealthReport:
    statuses = {kind: ConnectorHealth.HEALTHY for kind in HealthCheckKind}
    if overrides is not None:
        statuses.update(overrides)
    results = tuple(check(kind, status) for kind, status in statuses.items())
    return HealthReport(instance_id="connector-instance.example", results=results)


def test_health_check_result_requires_detail() -> None:
    with pytest.raises(ValueError, match="requires a detail"):
        HealthCheckResult(
            kind=HealthCheckKind.AUTHENTICATION,
            status=ConnectorHealth.HEALTHY,
            detail="",
            checked_at=NOW,
        )


def test_health_report_requires_every_check_kind() -> None:
    with pytest.raises(ValueError, match="every health check kind"):
        HealthReport(
            instance_id="connector-instance.example",
            results=(check(HealthCheckKind.AUTHENTICATION),),
        )


def test_health_report_rejects_duplicate_kind() -> None:
    duplicated = (check(HealthCheckKind.AUTHENTICATION),) * len(HealthCheckKind)
    with pytest.raises(ValueError, match="must not repeat"):
        HealthReport(instance_id="connector-instance.example", results=duplicated)


def test_is_fully_healthy_true_when_all_healthy() -> None:
    assert full_report().is_fully_healthy is True


def test_is_fully_healthy_false_when_one_degraded() -> None:
    report = full_report({HealthCheckKind.SECRET_AVAILABILITY: ConnectorHealth.DEGRADED})
    assert report.is_fully_healthy is False


def test_test_harness_declaration_requires_every_capability() -> None:
    with pytest.raises(ValueError, match="must provide every capability"):
        HarnessDeclaration(
            harness_id="test-harness.sdk",
            provided_capabilities=frozenset({HarnessCapability.FAULT_INJECTION}),
        )


def test_test_harness_declaration_accepts_full_capability_set() -> None:
    declaration = HarnessDeclaration(
        harness_id="test-harness.sdk", provided_capabilities=frozenset(HarnessCapability)
    )
    assert declaration.harness_id == "test-harness.sdk"
