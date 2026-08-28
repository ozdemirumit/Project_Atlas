from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.config import Settings
from atlas.modules.health_checks.adapters.synthetic import (
    CONTROLLER_DEFINITION_ID,
    SyntheticStorageHealthExecutor,
    build_synthetic_health_check_definitions,
    build_synthetic_latest_runs,
)
from atlas.modules.health_checks.application.ports import (
    HealthCheckExecutionResult,
    HealthCheckExecutor,
)
from atlas.modules.health_checks.application.service import HealthCheckService
from atlas.modules.health_checks.domain.models import (
    HealthCheckDefinition,
    HealthCheckLimits,
    HealthCheckRunState,
)

NOW = datetime(2026, 8, 3, 20, 7, tzinfo=UTC)


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


class AcceptedAuditFailingSink(CollectingAuditSink):
    async def record(self, event: AuditRecord) -> None:
        if event.event_type == "atlas.health_check.run.accepted":
            raise RuntimeError("health-check audit unavailable")
        await super().record(event)


class CountingExecutor(SyntheticStorageHealthExecutor):
    def __init__(self) -> None:
        self.calls = 0

    async def execute(
        self, definition: HealthCheckDefinition, *, started_at: datetime
    ) -> HealthCheckExecutionResult:
        self.calls += 1
        return await super().execute(definition, started_at=started_at)


class SlowExecutor:
    async def execute(
        self, definition: HealthCheckDefinition, *, started_at: datetime
    ) -> HealthCheckExecutionResult:
        await asyncio.sleep(0.05)
        raise AssertionError("timeout did not stop the synthetic executor")


class OverBudgetExecutor:
    async def execute(
        self, definition: HealthCheckDefinition, *, started_at: datetime
    ) -> HealthCheckExecutionResult:
        return HealthCheckExecutionResult(
            state=HealthCheckRunState.COMPLETED,
            completed_at=started_at,
            step_count=definition.limits.max_steps + 1,
            observations=(),
            findings=(),
            evidence=(),
        )


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "development_identity_enabled": True,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def service(
    *,
    audit_sink: CollectingAuditSink,
    executor: HealthCheckExecutor | None = None,
    definition_transform: Callable[[HealthCheckDefinition], HealthCheckDefinition] | None = None,
) -> HealthCheckService:
    definitions = build_synthetic_health_check_definitions(
        organization_id="organization.development",
        environment="test",
        anchor_at=datetime(2026, 8, 3, 0, 0, tzinfo=UTC),
    )
    if definition_transform is not None:
        definitions = tuple(definition_transform(item) for item in definitions)
    return HealthCheckService(
        definitions=definitions,
        latest_runs=build_synthetic_latest_runs(definitions, generated_at=NOW),
        executor=executor or SyntheticStorageHealthExecutor(),
        audit_sink=audit_sink,
    )


def test_health_check_overview_requires_authentication() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get("/api/v1/health-checks/overview")

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_health_check_overview_requires_exact_assignment() -> None:
    with TestClient(
        create_app(settings(development_role_ids=()), audit_sink=CollectingAuditSink())
    ) as client:
        response = client.get("/api/v1/health-checks/overview")

    assert response.status_code == 403
    assert response.json()["code"] == "authorization_denied"
    assert "health" not in response.json()["detail"].lower()


def test_health_check_overview_is_versioned_scheduled_and_evidence_linked() -> None:
    audit_sink = CollectingAuditSink()
    with TestClient(create_app(settings(), audit_sink=audit_sink)) as client:
        response = client.get(
            "/api/v1/health-checks/overview",
            headers={"X-Correlation-ID": "cor_health_overview"},
        )

    payload = response.json()
    data = payload["data"]
    assert response.status_code == 200
    assert payload["meta"]["correlation_id"] == "cor_health_overview"
    assert data["data_profile"] == "synthetic_lab"
    assert len(data["definitions"]) == 3
    assert {item["version"] for item in data["definitions"]} == {1}
    assert {item["capability_class"] for item in data["definitions"]} == {"C1"}
    assert {item["interval_minutes"] for item in data["schedules"]} == {15, 60}
    assert {item["state"] for item in data["latest_runs"]} == {"completed", "partial"}
    assert all(item["evidence"] for item in data["latest_runs"])
    assert "do not authorize" in data["safety_notice"]
    assert audit_sink.records[-1].event_type == "atlas.health_check.overview.read"


def test_manual_health_check_run_is_partial_not_healthy_when_evidence_is_missing() -> None:
    audit_sink = CollectingAuditSink()
    with TestClient(create_app(settings(), audit_sink=audit_sink)) as client:
        response = client.post(
            f"/api/v1/health-checks/{CONTROLLER_DEFINITION_ID}/runs",
            headers={"X-Correlation-ID": "cor_health_run"},
        )

    data = response.json()["data"]
    assert response.status_code == 200
    assert data["trigger"] == "manual"
    assert data["state"] == "partial"
    assert data["partial_reasons"]
    assert data["unknowns"]
    assert {item["state"] for item in data["observations"]} == {"normal", "warning"}
    assert "outage" in " ".join(data["unknowns"]).lower()
    assert [item.event_type for item in audit_sink.records[-2:]] == [
        "atlas.health_check.run.accepted",
        "atlas.health_check.run.completed",
    ]


def test_disabled_health_check_is_not_dispatched() -> None:
    audit_sink = CollectingAuditSink()
    executor = CountingExecutor()
    health_service = service(
        audit_sink=audit_sink,
        executor=executor,
        definition_transform=lambda item: replace(item, enabled=False),
    )
    with TestClient(
        create_app(settings(), audit_sink=audit_sink, health_check_service=health_service)
    ) as client:
        response = client.post(f"/api/v1/health-checks/{CONTROLLER_DEFINITION_ID}/runs")

    assert response.status_code == 409
    assert response.json()["code"] == "health_check_disabled"
    assert executor.calls == 0


def test_unknown_definition_returns_generic_safe_error() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        response = client.post("/api/v1/health-checks/vendor-secret-check/runs")

    assert response.status_code == 404
    assert response.json()["code"] == "health_check_unavailable"
    assert "vendor-secret" not in response.text


def test_timeout_returns_unknown_health_without_observations() -> None:
    audit_sink = CollectingAuditSink()

    def short_timeout(item: HealthCheckDefinition) -> HealthCheckDefinition:
        return replace(
            item,
            limits=replace(item.limits, timeout_seconds=0.01),
        )

    health_service = service(
        audit_sink=audit_sink,
        executor=SlowExecutor(),
        definition_transform=short_timeout,
    )
    with TestClient(
        create_app(settings(), audit_sink=audit_sink, health_check_service=health_service)
    ) as client:
        response = client.post(f"/api/v1/health-checks/{CONTROLLER_DEFINITION_ID}/runs")

    data = response.json()["data"]
    assert response.status_code == 200
    assert data["state"] == "timed_out"
    assert data["observations"] == []
    assert "unknown" in " ".join(data["unknowns"]).lower()


def test_over_budget_result_fails_closed_without_health_observations() -> None:
    audit_sink = CollectingAuditSink()
    health_service = service(audit_sink=audit_sink, executor=OverBudgetExecutor())
    with TestClient(
        create_app(settings(), audit_sink=audit_sink, health_check_service=health_service)
    ) as client:
        response = client.post(f"/api/v1/health-checks/{CONTROLLER_DEFINITION_ID}/runs")

    data = response.json()["data"]
    assert response.status_code == 200
    assert data["state"] == "failed"
    assert data["observations"] == []
    assert "budget" in " ".join(data["partial_reasons"]).lower()


def test_required_acceptance_audit_failure_blocks_connector_dispatch() -> None:
    audit_sink = AcceptedAuditFailingSink()
    executor = CountingExecutor()
    health_service = service(audit_sink=audit_sink, executor=executor)
    with TestClient(
        create_app(settings(), audit_sink=audit_sink, health_check_service=health_service),
        raise_server_exceptions=False,
    ) as client:
        response = client.post(f"/api/v1/health-checks/{CONTROLLER_DEFINITION_ID}/runs")

    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
    assert executor.calls == 0
    assert "controller" not in response.text.lower()


def test_schedule_evaluation_is_deterministic() -> None:
    definition = build_synthetic_health_check_definitions(
        organization_id="organization.development",
        environment="test",
        anchor_at=datetime(2026, 8, 3, 20, 0, tzinfo=UTC),
    )[0]

    last_due, next_due = definition.schedule.due_times(NOW)

    assert last_due == datetime(2026, 8, 3, 20, 0, tzinfo=UTC)
    assert next_due == datetime(2026, 8, 3, 20, 15, tzinfo=UTC)


def test_health_check_limits_reject_non_positive_values() -> None:
    with pytest.raises(ValueError, match="positive"):
        HealthCheckLimits(timeout_seconds=0, max_steps=1, max_evidence_records=1)
