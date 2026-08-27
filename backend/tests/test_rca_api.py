from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.config import Settings
from atlas.modules.rca.adapters.synthetic import SyntheticStorageRcaAssembler
from atlas.modules.rca.application.service import (
    RcaAccessContext,
    RcaOperationsError,
    RcaService,
)
from atlas.modules.rca.domain.models import RcaCreateRequest

NOW = datetime(2026, 8, 4, 10, 0, tzinfo=UTC)
TARGET = "asset.storage.lab.b28"


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


class AcceptedAuditFailingSink(CollectingAuditSink):
    async def record(self, event: AuditRecord) -> None:
        if event.event_type == "atlas.rca.accepted":
            raise RuntimeError("RCA audit unavailable")
        await super().record(event)


class CountingAssembler(SyntheticStorageRcaAssembler):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    async def build(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        self.calls += 1
        return await super().build(*args, **kwargs)  # type: ignore[arg-type]


class UnsafeDiagnosticAssembler(SyntheticStorageRcaAssembler):
    async def build(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        case = await super().build(*args, **kwargs)  # type: ignore[arg-type]
        hypothesis = case.hypotheses[0]
        diagnostic = replace(hypothesis.diagnostic_steps[0], capability_id="vendor.storage.restart")
        return replace(
            case,
            hypotheses=(
                replace(hypothesis, diagnostic_steps=(diagnostic,)),
                *case.hypotheses[1:],
            ),
        )


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "development_identity_enabled": True,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def payload(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "incident_id": "INC-2026-0042",
        "user_report": "Storage warning appeared during the service window.",
        "expected_behavior": "Storage paths remain healthy and redundant.",
        "actual_behavior": "Controller CTL01 reports a warning.",
        "window_start": (NOW - timedelta(hours=24)).isoformat(),
        "window_end": NOW.isoformat(),
        "max_evidence_records": 12,
    }
    values.update(overrides)
    return values


def context(**overrides: object) -> RcaAccessContext:
    values: dict[str, object] = {
        "subject_id": "subject.development.operator",
        "actor_type": "human",
        "authentication_method": "development",
        "assurance_level": "development",
        "organization_id": "organization.development",
        "environment_id": "environment.test",
        "site_id": "site.local",
        "resource_id": "resource.rca.storage.synthetic",
        "correlation_id": "cor_rca",
        "decision_id": "dec_rca",
        "requested_at": NOW,
    }
    values.update(overrides)
    return RcaAccessContext(**values)  # type: ignore[arg-type]


def domain_request(**overrides: object) -> RcaCreateRequest:
    values: dict[str, object] = {
        "incident_id": "INC-2026-0042",
        "target_id": TARGET,
        "user_report": "Storage warning appeared during the service window.",
        "expected_behavior": "Storage paths remain healthy and redundant.",
        "actual_behavior": "Controller CTL01 reports a warning.",
        "window_start": NOW - timedelta(hours=24),
        "window_end": NOW,
        "max_evidence_records": 12,
    }
    values.update(overrides)
    return RcaCreateRequest(**values)  # type: ignore[arg-type]


def test_rca_requires_authentication() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.post(f"/api/v1/rca/storage/{TARGET}", json=payload())

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_rca_requires_exact_assignment() -> None:
    with TestClient(
        create_app(settings(development_role_ids=()), audit_sink=CollectingAuditSink())
    ) as client:
        response = client.post(f"/api/v1/rca/storage/{TARGET}", json=payload())

    assert response.status_code == 403
    assert response.json()["code"] == "authorization_denied"
    assert "RCA" not in response.json()["detail"]


def test_rca_returns_provisional_ranked_evidence_grounded_case() -> None:
    audit_sink = CollectingAuditSink()
    with TestClient(create_app(settings(), audit_sink=audit_sink)) as client:
        response = client.post(
            f"/api/v1/rca/storage/{TARGET}",
            json=payload(),
            headers={"X-Correlation-ID": "cor_rca_case"},
        )

    data = response.json()["data"]
    assert response.status_code == 200
    assert response.json()["meta"]["correlation_id"] == "cor_rca_case"
    assert data["version"] == 1
    assert data["state"] == "provisional"
    assert data["human_review"]["status"] == "pending"
    assert data["root_cause_confirmed"] is False
    assert data["impact_scope"]["impact_confirmed"] is False
    assert [item["rank"] for item in data["hypotheses"]] == [1, 2]
    assert {item["cause_type"] for item in data["hypotheses"]} == {
        "contributing_cause",
        "observation_failure",
    }
    assert "No root cause is confirmed" in data["provisional_statement"]["statement"]
    assert data["evidence_gaps"] and data["blocker"] and data["safest_next_step"]
    assert [item.event_type for item in audit_sink.records[-2:]] == [
        "atlas.rca.accepted",
        "atlas.rca.completed",
    ]


def test_rca_keeps_affected_unaffected_and_possible_service_scope_separate() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        data = client.post(f"/api/v1/rca/storage/{TARGET}", json=payload()).json()["data"]

    impact = data["impact_scope"]
    assert TARGET in impact["affected_entities"]
    assert "CTL02" in impact["explicitly_unaffected_entities"]
    assert "Enterprise Resource Planning" in impact["possibly_affected_services"]
    assert "Graph reachability" in " ".join(impact["limitations"])


def test_repeated_rca_creates_immutable_incident_target_version_lineage() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        first = client.post(f"/api/v1/rca/storage/{TARGET}", json=payload()).json()["data"]
        second = client.post(f"/api/v1/rca/storage/{TARGET}", json=payload()).json()["data"]
        other_incident = client.post(
            f"/api/v1/rca/storage/{TARGET}", json=payload(incident_id="INC-OTHER")
        ).json()["data"]

    assert first["version"] == 1
    assert second["version"] == 2
    assert second["prior_version_id"] == first["case_id"]
    assert other_incident["version"] == 1
    assert other_incident["prior_version_id"] is None


def test_rca_timeline_and_hypotheses_preserve_evidence_balance() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        data = client.post(f"/api/v1/rca/storage/{TARGET}", json=payload()).json()["data"]

    evidence_ids = {item["evidence_id"] for item in data["evidence"]}
    for event in data["timeline"]:
        assert event["occurred_at"] <= event["observed_at"] <= event["ingested_at"]
    for hypothesis in data["hypotheses"]:
        assert set(hypothesis["supporting_evidence"]) <= evidence_ids
        assert set(hypothesis["contradicting_evidence"]) <= evidence_ids
        assert hypothesis["missing_expected_observations"]
        assert hypothesis["confounders"]
        assert hypothesis["assumptions"]
        assert all(step["capability_class"] == "C1" for step in hypothesis["diagnostic_steps"])


def test_hidden_and_missing_rca_targets_return_same_safe_error() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        hidden = client.post("/api/v1/rca/storage/asset.storage.lab.restricted", json=payload())
        missing = client.post("/api/v1/rca/storage/asset.storage.lab.missing", json=payload())

    assert hidden.status_code == missing.status_code == 404
    assert hidden.json()["code"] == missing.json()["code"] == "rca_target_unavailable"
    assert hidden.json()["detail"] == missing.json()["detail"]
    assert "restricted" not in hidden.text.lower()


def test_rca_evidence_budget_fails_closed() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        response = client.post(
            f"/api/v1/rca/storage/{TARGET}", json=payload(max_evidence_records=3)
        )

    assert response.status_code == 409
    assert response.json()["code"] == "rca_evidence_budget_exceeded"
    assert "VSP" not in response.text


def test_required_rca_acceptance_audit_failure_blocks_assembly() -> None:
    audit_sink = AcceptedAuditFailingSink()
    assembler = CountingAssembler()
    service = RcaService(assembler=assembler, audit_sink=audit_sink)
    with TestClient(
        create_app(settings(), audit_sink=audit_sink, rca_service=service),
        raise_server_exceptions=False,
    ) as client:
        response = client.post(f"/api/v1/rca/storage/{TARGET}", json=payload())

    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
    assert assembler.calls == 0
    assert "controller" not in response.text.lower()


def test_non_allowlisted_rca_diagnostic_is_rejected() -> None:
    service = RcaService(assembler=UnsafeDiagnosticAssembler(), audit_sink=CollectingAuditSink())
    with TestClient(
        create_app(settings(), audit_sink=CollectingAuditSink(), rca_service=service)
    ) as client:
        response = client.post(f"/api/v1/rca/storage/{TARGET}", json=payload())

    assert response.status_code == 409
    assert response.json()["code"] == "rca_diagnostic_denied"
    assert "restart" not in response.text.lower()


@pytest.mark.asyncio
async def test_rca_scope_mismatch_is_rejected_before_audit() -> None:
    audit_sink = CollectingAuditSink()
    service = RcaService(assembler=SyntheticStorageRcaAssembler(), audit_sink=audit_sink)

    with pytest.raises(RcaOperationsError, match="outside the authorized scope"):
        await service.create(
            domain_request(),
            context=context(resource_id="resource.rca.other"),
        )

    assert audit_sink.records == []
