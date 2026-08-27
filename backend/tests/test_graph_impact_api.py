from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.classification import DataClassification
from atlas.core.config import Settings
from atlas.modules.graph.adapters.synthetic import (
    SyntheticGraphSnapshotProvider,
    build_synthetic_graph_snapshot,
)
from atlas.modules.graph.application.engine import (
    GraphAccessContext,
    GraphImpactError,
    InMemoryGraphImpactAnalyzer,
)
from atlas.modules.graph.application.service import (
    GraphImpactService,
    GraphReadContext,
)

NOW = datetime(2026, 8, 3, 18, 0, tzinfo=UTC)


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


class GraphAuditFailingSink(CollectingAuditSink):
    async def record(self, event: AuditRecord) -> None:
        if event.event_type == "atlas.graph.storage_impact.read":
            raise RuntimeError("graph audit unavailable")
        await super().record(event)


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "development_identity_enabled": True,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def test_storage_impact_requires_authentication() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get("/api/v1/graph/storage-impact/asset.storage.lab.b28")

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_storage_impact_requires_exact_assignment() -> None:
    with TestClient(
        create_app(settings(development_role_ids=()), audit_sink=CollectingAuditSink())
    ) as client:
        response = client.get("/api/v1/graph/storage-impact/asset.storage.lab.b28")

    assert response.status_code == 403
    assert response.json()["code"] == "authorization_denied"
    assert "graph" not in response.json()["detail"].lower()


def test_storage_impact_returns_bounded_evidence_linked_dependency_paths() -> None:
    audit_sink = CollectingAuditSink()
    with TestClient(create_app(settings(), audit_sink=audit_sink)) as client:
        response = client.get(
            "/api/v1/graph/storage-impact/asset.storage.lab.b28?max_depth=5",
            headers={"X-Correlation-ID": "cor_graph_impact"},
        )

    payload = response.json()
    data = payload["data"]
    assert response.status_code == 200
    assert payload["meta"]["correlation_id"] == "cor_graph_impact"
    assert data["data_profile"] == "synthetic_lab"
    assert data["completeness"] == "partial"
    assert data["outage_confirmed"] is False
    assert data["digital_twin_maturity"] == "D0-D1 dependency analysis"
    assert len(data["paths"]) == 5
    assert len(data["paths"][-1]["entity_ids"]) == 6
    assert data["direct_entity_ids"] == ["entity.volume.erp.prod"]
    assert data["business_service_ids"] == ["entity.business-service.erp"]
    assert data["unknowns"]
    assert data["known_gaps"]
    assert "Restricted Business Service" not in response.text
    assert "entity.business-service.restricted" not in response.text

    evidence_ids = {item["reference"] for item in data["evidence"]}
    path_evidence = {
        reference for path in data["paths"] for reference in path["evidence_references"]
    }
    assert path_evidence <= evidence_ids
    assert [record.event_type for record in audit_sink.records] == [
        "atlas.identity.authentication.succeeded",
        "atlas.authorization.access.allowed",
        "atlas.graph.storage_impact.read",
    ]


def test_hidden_and_missing_graph_targets_return_same_safe_error() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        hidden = client.get("/api/v1/graph/storage-impact/entity.business-service.restricted")
        missing = client.get("/api/v1/graph/storage-impact/entity.missing")

    assert hidden.status_code == missing.status_code == 404
    assert hidden.json()["code"] == missing.json()["code"] == "graph_target_unavailable"
    assert hidden.json()["detail"] == missing.json()["detail"]
    assert "restricted" not in hidden.text.lower()


def test_graph_depth_is_bounded_by_api_contract() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        response = client.get("/api/v1/graph/storage-impact/asset.storage.lab.b28?max_depth=6")

    assert response.status_code == 422


def test_authorization_filter_runs_before_traversal() -> None:
    analyzer = InMemoryGraphImpactAnalyzer(
        snapshot=build_synthetic_graph_snapshot(
            organization_id="organization.development", environment="test"
        )
    )
    access = GraphAccessContext(
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.local",
        principals=frozenset({"role.development.operator"}),
        classification_ceiling=DataClassification.INTERNAL,
    )

    result = analyzer.analyze(start_entity_id="asset.storage.lab.b28", access=access, max_depth=5)

    assert len(result.entities) == 6
    assert len(result.relationships) == 5
    assert all("restricted" not in item.entity_id for item in result.entities)
    assert all("restricted" not in item.relationship_id for item in result.relationships)


@pytest.mark.asyncio
async def test_graph_scope_mismatch_is_rejected_before_audit() -> None:
    audit_sink = CollectingAuditSink()
    service = GraphImpactService(
        provider=SyntheticGraphSnapshotProvider(
            organization_id="organization.development", environment="test"
        ),
        audit_sink=audit_sink,
    )
    context = GraphReadContext(
        subject_id="subject.development.operator",
        actor_type="human",
        authentication_method="development",
        assurance_level="development",
        organization_id="organization.development",
        environment_id="environment.test",
        site_id="site.local",
        resource_id="resource.graph.other",
        role_ids=("role.development.operator",),
        group_ids=(),
        correlation_id="cor_wrong_scope",
        decision_id="dec_wrong_scope",
        requested_at=NOW,
    )

    with pytest.raises(GraphImpactError, match="outside the authorized scope"):
        await service.analyze_storage_impact(
            entity_id="asset.storage.lab.b28", max_depth=5, context=context
        )

    assert audit_sink.records == []


def test_graph_audit_failure_blocks_data_response() -> None:
    with TestClient(
        create_app(settings(), audit_sink=GraphAuditFailingSink()),
        raise_server_exceptions=False,
    ) as client:
        response = client.get("/api/v1/graph/storage-impact/asset.storage.lab.b28")

    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
    assert "ERP" not in response.text
