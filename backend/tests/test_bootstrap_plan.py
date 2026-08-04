from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.config import Settings
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.platform.application.bootstrap_plan import (
    BootstrapPlanScopeError,
    BootstrapPlanService,
)
from atlas.modules.platform.domain.bootstrap_plan import (
    BootstrapPhaseState,
    BootstrapPlanRequest,
    BootstrapPlanState,
)
from atlas.modules.platform.domain.release_preflight import DeploymentProfile


class AuditSink:
    def __init__(self, fail: bool = False) -> None:
        self.records: list[AuditRecord] = []
        self.fail = fail

    async def record(self, event: AuditRecord) -> None:
        if self.fail and event.event_type == "atlas.platform.bootstrap-plan.read":
            raise RuntimeError("audit unavailable")
        self.records.append(event)


def actor() -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id="subject.enterprise.operator",
        display_name="Operator",
        kind=SubjectKind.HUMAN,
        provider_id="provider.ldap.enterprise",
        authentication_method=AuthenticationMethod.LDAP,
        assurance_level=AssuranceLevel.MULTI_FACTOR,
        authenticated_at=datetime(2026, 8, 4, tzinfo=UTC),
        organization_id="organization.enterprise",
        role_ids=("role.operator",),
    )


def request() -> BootstrapPlanRequest:
    return BootstrapPlanRequest(
        schema_version="atlas.bootstrap-plan-request.v1",
        release_id="release.atlas.lab-0.1.0",
        profile=DeploymentProfile.LINUX_LAB,
        organization_id="organization.enterprise",
        environment_id="environment.test",
        site_id="site.local",
        preflight_report_id="preflight.valid.001",
        manifest_digest="a" * 64,
        preflight_state="passed",
        configuration_preview_id="configuration-preview.valid.001",
        configuration_digest="b" * 64,
        configuration_state="passed",
    )


def service(sink: AuditSink | None = None) -> BootstrapPlanService:
    return BootstrapPlanService(
        environment_id="environment.test", site_id="site.local", audit_sink=sink or AuditSink()
    )


@pytest.mark.asyncio
async def test_ready_plan_is_deterministic_ordered_and_non_executing() -> None:
    first = await service().build(
        actor=actor(), request=request(), correlation_id="correlation.plan.first"
    )
    second = await service().build(
        actor=actor(), request=request(), correlation_id="correlation.plan.second"
    )
    assert first.state is BootstrapPlanState.READY
    assert first.plan_digest == second.plan_digest
    assert first.resume_key == second.resume_key
    assert [item.sequence for item in first.phases] == list(range(1, 10))
    assert first.phases[-1].dependencies == ("phase.verify",)
    assert first.mutation_authorized is False and first.execution_authorized is False


@pytest.mark.asyncio
async def test_failed_gate_blocks_every_phase() -> None:
    plan = await service().build(
        actor=actor(),
        request=replace(request(), preflight_state="failed"),
        correlation_id="correlation.plan.blocked",
    )
    assert plan.state is BootstrapPlanState.BLOCKED
    assert all(item.state is BootstrapPhaseState.BLOCKED for item in plan.phases)


@pytest.mark.asyncio
async def test_foreign_scope_and_audit_failure_fail_closed() -> None:
    foreign_sink = AuditSink()
    with pytest.raises(BootstrapPlanScopeError):
        await service(foreign_sink).build(
            actor=actor(),
            request=replace(request(), site_id="site.foreign"),
            correlation_id="correlation.plan.foreign",
        )
    assert foreign_sink.records[-1].outcome == "denied"
    assert foreign_sink.records[-1].scope_reference == "scope.redacted"
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await service(AuditSink(fail=True)).build(
            actor=actor(), request=request(), correlation_id="correlation.plan.audit"
        )


def payload() -> dict[str, object]:
    return {
        "schema_version": "atlas.bootstrap-plan-request.v1",
        "release_id": "release.atlas.lab-0.1.0",
        "profile": "linux_lab",
        "organization_id": "organization.development",
        "environment_id": "environment.test",
        "site_id": "site.local",
        "preflight_report_id": "preflight.valid.001",
        "manifest_digest": "a" * 64,
        "preflight_state": "passed",
        "configuration_preview_id": "configuration-preview.valid.001",
        "configuration_digest": "b" * 64,
        "configuration_state": "passed",
    }


def test_api_authorization_strict_parsing_and_audit_failure() -> None:
    sink = AuditSink()
    app = create_app(
        Settings(environment="test", development_identity_enabled=True), audit_sink=sink
    )
    with TestClient(app) as client:
        response = client.post("/api/v1/platform/bootstrap-plan", json=payload())
        malformed = client.post(
            "/api/v1/platform/bootstrap-plan", json={**payload(), "unknown": True}
        )
    assert response.status_code == 200 and response.json()["data"]["state"] == "ready"
    assert malformed.status_code == 422
    assert any(item.event_type == "atlas.platform.bootstrap-plan.read" for item in sink.records)

    denied = create_app(
        Settings(environment="test", development_identity_enabled=True, development_role_ids=())
    )
    with TestClient(denied) as client:
        denied_response = client.post("/api/v1/platform/bootstrap-plan", json=payload())
    assert denied_response.status_code == 403 and "phase.acquire" not in denied_response.text

    failing_sink = AuditSink(fail=True)
    failing = create_app(
        Settings(environment="test", development_identity_enabled=True),
        audit_sink=failing_sink,
        bootstrap_plan_service=service(failing_sink),
    )
    with TestClient(failing, raise_server_exceptions=False) as client:
        failed = client.post("/api/v1/platform/bootstrap-plan", json=payload())
    assert failed.status_code == 500 and "phase.acquire" not in failed.text
