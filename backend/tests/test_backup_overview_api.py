from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.config import Settings
from atlas.modules.backup_operations.adapters.synthetic import SyntheticBackupOverviewProvider
from atlas.modules.backup_operations.application.service import (
    BackupOperationsError,
    BackupOperationsService,
    BackupReadContext,
)

NOW = datetime(2026, 8, 31, 18, 0, tzinfo=UTC)


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


class BackupAuditFailingSink(CollectingAuditSink):
    async def record(self, event: AuditRecord) -> None:
        if event.event_type == "atlas.backup.overview.read":
            raise RuntimeError("backup audit unavailable")
        await super().record(event)


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "development_identity_enabled": True,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_backup_overview_requires_authentication() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get("/api/v1/backup/overview")

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_backup_overview_requires_exact_assignment() -> None:
    with TestClient(
        create_app(settings(development_role_ids=()), audit_sink=CollectingAuditSink())
    ) as client:
        response = client.get("/api/v1/backup/overview")

    assert response.status_code == 403
    assert response.json()["code"] == "authorization_denied"
    assert "backup" not in response.json()["detail"].lower()


def test_backup_overview_returns_evidence_linked_synthetic_vertical_slice() -> None:
    audit_sink = CollectingAuditSink()
    with TestClient(create_app(settings(), audit_sink=audit_sink)) as client:
        response = client.get(
            "/api/v1/backup/overview",
            headers={"X-Correlation-ID": "cor_backup_overview"},
        )

    payload = response.json()
    data = payload["data"]
    assert response.status_code == 200
    assert payload["meta"]["correlation_id"] == "cor_backup_overview"
    assert data["data_profile"] == "synthetic_lab"
    assert len(data["clients"]) == 2
    assert len(data["policies"]) == 2
    assert data["investigation"]["state"] == "provisional"
    assert data["investigation"]["unknowns"]
    assert "Decision support only" in data["report"]["safety_notice"]

    evidence_ids = {item["reference"] for item in data["evidence"]}
    referenced_ids = {
        reference for client in data["clients"] for reference in client["evidence_references"]
    }
    assert referenced_ids <= evidence_ids
    assert [record.event_type for record in audit_sink.records] == [
        "atlas.identity.authentication.succeeded",
        "atlas.authorization.access.allowed",
        "atlas.backup.overview.read",
    ]


def test_backup_audit_failure_blocks_data_response() -> None:
    with TestClient(
        create_app(settings(), audit_sink=BackupAuditFailingSink()),
        raise_server_exceptions=False,
    ) as client:
        response = client.get("/api/v1/backup/overview")

    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"


@pytest.mark.asyncio
async def test_backup_service_rejects_scope_mismatch_before_audit() -> None:
    audit_sink = CollectingAuditSink()
    service = BackupOperationsService(
        provider=SyntheticBackupOverviewProvider(
            organization_id="organization.development",
            environment="test",
        ),
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.local",
        audit_sink=audit_sink,
    )
    context = BackupReadContext(
        subject_id="subject.development.operator",
        actor_type="human",
        authentication_method="development",
        assurance_level="development",
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.other",
        resource_id="resource.backup.lab-overview",
        correlation_id="cor_wrong_scope",
        decision_id="dec_wrong_scope",
        requested_at=NOW,
    )

    try:
        await service.get_overview(context)
    except BackupOperationsError as error:
        assert error.code == "backup_scope_mismatch"
    else:
        raise AssertionError("scope mismatch unexpectedly returned backup data")

    assert audit_sink.records == []
