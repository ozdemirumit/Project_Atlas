from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.config import Settings
from atlas.modules.storage.adapters.synthetic import SyntheticStorageOverviewProvider
from atlas.modules.storage.application.service import (
    StorageOperationsError,
    StorageOperationsService,
    StorageReadContext,
)

NOW = datetime(2026, 8, 3, 18, 0, tzinfo=UTC)


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


class StorageAuditFailingSink(CollectingAuditSink):
    async def record(self, event: AuditRecord) -> None:
        if event.event_type == "atlas.storage.overview.read":
            raise RuntimeError("storage audit unavailable")
        await super().record(event)


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "development_identity_enabled": True,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_storage_overview_requires_authentication() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get("/api/v1/storage/overview")

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_storage_overview_requires_exact_assignment() -> None:
    with TestClient(
        create_app(settings(development_role_ids=()), audit_sink=CollectingAuditSink())
    ) as client:
        response = client.get("/api/v1/storage/overview")

    assert response.status_code == 403
    assert response.json()["code"] == "authorization_denied"
    assert "storage" not in response.json()["detail"].lower()


def test_storage_overview_returns_evidence_linked_synthetic_vertical_slice() -> None:
    audit_sink = CollectingAuditSink()
    with TestClient(create_app(settings(), audit_sink=audit_sink)) as client:
        response = client.get(
            "/api/v1/storage/overview",
            headers={"X-Correlation-ID": "cor_storage_overview"},
        )

    payload = response.json()
    data = payload["data"]
    assert response.status_code == 200
    assert payload["meta"]["correlation_id"] == "cor_storage_overview"
    assert data["data_profile"] == "synthetic_lab"
    assert len(data["assets"]) == 2
    assert {asset["health"] for asset in data["assets"]} == {"healthy", "warning"}
    assert data["investigation"]["state"] == "provisional"
    assert data["investigation"]["unknowns"]
    assert "No root cause" in data["investigation"]["summary"]
    assert "Decision support only" in data["report"]["safety_notice"]
    assert "192.0.2" not in response.text

    evidence_ids = {item["reference"] for item in data["evidence"]}
    referenced_ids = {
        reference for asset in data["assets"] for reference in asset["evidence_references"]
    }
    assert referenced_ids <= evidence_ids
    assert [record.event_type for record in audit_sink.records] == [
        "atlas.identity.authentication.succeeded",
        "atlas.authorization.access.allowed",
        "atlas.storage.overview.read",
    ]


def test_storage_audit_failure_blocks_data_response() -> None:
    with TestClient(
        create_app(settings(), audit_sink=StorageAuditFailingSink()),
        raise_server_exceptions=False,
    ) as client:
        response = client.get("/api/v1/storage/overview")

    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
    assert "VSP" not in response.text


@pytest.mark.asyncio
async def test_storage_service_rejects_scope_mismatch_before_audit() -> None:
    audit_sink = CollectingAuditSink()
    service = StorageOperationsService(
        provider=SyntheticStorageOverviewProvider(
            organization_id="organization.development",
            environment="test",
        ),
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.local",
        audit_sink=audit_sink,
    )
    context = StorageReadContext(
        subject_id="subject.development.operator",
        actor_type="human",
        authentication_method="development",
        assurance_level="development",
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.other",
        resource_id="resource.storage.lab-overview",
        correlation_id="cor_wrong_scope",
        decision_id="dec_wrong_scope",
        requested_at=NOW,
    )

    try:
        await service.get_overview(context)
    except StorageOperationsError as error:
        assert error.code == "storage_scope_mismatch"
    else:
        raise AssertionError("scope mismatch unexpectedly returned storage data")

    assert audit_sink.records == []
