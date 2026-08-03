from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.config import Settings
from atlas.modules.investigations.adapters.synthetic import SyntheticInvestigationAssembler
from atlas.modules.investigations.application.service import (
    InvestigationAccessContext,
    InvestigationOperationsError,
    InvestigationService,
)
from atlas.modules.investigations.domain.models import InvestigationRequest

NOW = datetime(2026, 8, 3, 21, 30, tzinfo=UTC)
TARGET = "asset.storage.lab.b28"


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


class AcceptedAuditFailingSink(CollectingAuditSink):
    async def record(self, event: AuditRecord) -> None:
        if event.event_type == "atlas.investigation.accepted":
            raise RuntimeError("investigation audit unavailable")
        await super().record(event)


class CountingAssembler(SyntheticInvestigationAssembler):
    def __init__(self) -> None:
        self.calls = 0

    def build(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        self.calls += 1
        return super().build(*args, **kwargs)  # type: ignore[arg-type]


class UnsafeCheckAssembler(SyntheticInvestigationAssembler):
    def build(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        artifact = super().build(*args, **kwargs)  # type: ignore[arg-type]
        hypothesis = artifact.hypotheses[0]
        check = replace(hypothesis.discriminating_checks[0], capability_id="vendor.storage.restart")
        return replace(
            artifact,
            hypotheses=(
                replace(hypothesis, discriminating_checks=(check,)),
                *artifact.hypotheses[1:],
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
        "question": "What evidence explains the storage warning?",
        "intended_decision": "Decide which read-only evidence to collect next.",
        "window_start": (NOW - timedelta(hours=24)).isoformat(),
        "window_end": NOW.isoformat(),
        "max_evidence_records": 12,
    }
    values.update(overrides)
    return values


def context(**overrides: object) -> InvestigationAccessContext:
    values: dict[str, object] = {
        "subject_id": "subject.development.operator",
        "actor_type": "human",
        "authentication_method": "development",
        "assurance_level": "development",
        "organization_id": "organization.development",
        "environment_id": "environment.test",
        "site_id": "site.local",
        "resource_id": "resource.investigation.storage.synthetic",
        "correlation_id": "cor_investigation",
        "decision_id": "dec_investigation",
        "requested_at": NOW,
    }
    values.update(overrides)
    return InvestigationAccessContext(**values)  # type: ignore[arg-type]


def domain_request(**overrides: object) -> InvestigationRequest:
    values: dict[str, object] = {
        "target_id": TARGET,
        "question": "What evidence explains the storage warning?",
        "intended_decision": "Decide which read-only evidence to collect next.",
        "window_start": NOW - timedelta(hours=24),
        "window_end": NOW,
        "max_evidence_records": 12,
    }
    values.update(overrides)
    return InvestigationRequest(**values)  # type: ignore[arg-type]


def test_investigation_requires_authentication() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.post(f"/api/v1/investigations/storage/{TARGET}", json=payload())

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_investigation_requires_exact_assignment() -> None:
    with TestClient(
        create_app(settings(development_role_ids=()), audit_sink=CollectingAuditSink())
    ) as client:
        response = client.post(f"/api/v1/investigations/storage/{TARGET}", json=payload())

    assert response.status_code == 403
    assert response.json()["code"] == "authorization_denied"
    assert "investigation" not in response.json()["detail"].lower()


def test_investigation_returns_versioned_typed_evidence_grounded_artifact() -> None:
    audit_sink = CollectingAuditSink()
    with TestClient(create_app(settings(), audit_sink=audit_sink)) as client:
        response = client.post(
            f"/api/v1/investigations/storage/{TARGET}",
            json=payload(),
            headers={"X-Correlation-ID": "cor_reasoning"},
        )

    data = response.json()["data"]
    assert response.status_code == 200
    assert response.json()["meta"]["correlation_id"] == "cor_reasoning"
    assert data["version"] == 1
    assert data["prior_version_id"] is None
    assert data["data_profile"] == "synthetic_lab"
    assert data["root_cause_confirmed"] is False
    assert data["outage_confirmed"] is False
    assert data["unknowns"] and data["conflicts"]
    assert {item["epistemic_type"] for item in data["claims"]} == {
        "observation",
        "retrieved_fact",
        "calculated_finding",
        "correlation",
        "inference",
        "assumption",
        "unknown",
        "recommendation",
    }
    evidence_ids = {item["evidence_id"] for item in data["evidence"]}
    claim_evidence = {
        reference
        for claim in data["claims"]
        for reference in claim["supporting_evidence"] + claim["contradicting_evidence"]
    }
    assert claim_evidence <= evidence_ids
    assert [item.event_type for item in audit_sink.records[-2:]] == [
        "atlas.investigation.accepted",
        "atlas.investigation.completed",
    ]


def test_repeated_investigation_creates_immutable_linked_version() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        first = client.post(f"/api/v1/investigations/storage/{TARGET}", json=payload()).json()[
            "data"
        ]
        second = client.post(f"/api/v1/investigations/storage/{TARGET}", json=payload()).json()[
            "data"
        ]

    assert first["version"] == 1
    assert second["version"] == 2
    assert second["prior_version_id"] == first["artifact_id"]
    assert second["artifact_id"] != first["artifact_id"]


def test_timeline_preserves_distinct_times_without_causal_confirmation() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        data = client.post(f"/api/v1/investigations/storage/{TARGET}", json=payload()).json()[
            "data"
        ]

    for event in data["timeline"]:
        assert event["occurred_at"] <= event["observed_at"] <= event["ingested_at"]
    correlation = next(item for item in data["claims"] if item["epistemic_type"] == "correlation")
    assert "causality" in " ".join(correlation["limiting_factors"]).lower()
    assert "root cause" in data["summary"]["unsupported_decision"].lower()


def test_hidden_and_missing_targets_return_same_safe_error() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        hidden = client.post(
            "/api/v1/investigations/storage/asset.storage.lab.restricted", json=payload()
        )
        missing = client.post(
            "/api/v1/investigations/storage/asset.storage.lab.missing", json=payload()
        )

    assert hidden.status_code == missing.status_code == 404
    assert hidden.json()["code"] == missing.json()["code"] == "investigation_target_unavailable"
    assert hidden.json()["detail"] == missing.json()["detail"]
    assert "restricted" not in hidden.text.lower()


def test_evidence_budget_fails_closed() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        response = client.post(
            f"/api/v1/investigations/storage/{TARGET}",
            json=payload(max_evidence_records=3),
        )

    assert response.status_code == 409
    assert response.json()["code"] == "investigation_evidence_budget_exceeded"
    assert "VSP" not in response.text


def test_required_acceptance_audit_failure_blocks_assembly() -> None:
    audit_sink = AcceptedAuditFailingSink()
    assembler = CountingAssembler()
    service = InvestigationService(assembler=assembler, audit_sink=audit_sink)
    with TestClient(
        create_app(settings(), audit_sink=audit_sink, investigation_service=service),
        raise_server_exceptions=False,
    ) as client:
        response = client.post(f"/api/v1/investigations/storage/{TARGET}", json=payload())

    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
    assert assembler.calls == 0
    assert "controller" not in response.text.lower()


def test_non_allowlisted_discriminating_check_is_rejected() -> None:
    service = InvestigationService(
        assembler=UnsafeCheckAssembler(), audit_sink=CollectingAuditSink()
    )
    with TestClient(
        create_app(settings(), audit_sink=CollectingAuditSink(), investigation_service=service)
    ) as client:
        response = client.post(f"/api/v1/investigations/storage/{TARGET}", json=payload())

    assert response.status_code == 409
    assert response.json()["code"] == "investigation_check_denied"
    assert "restart" not in response.text.lower()


@pytest.mark.asyncio
async def test_scope_mismatch_is_rejected_before_audit() -> None:
    audit_sink = CollectingAuditSink()
    service = InvestigationService(
        assembler=SyntheticInvestigationAssembler(), audit_sink=audit_sink
    )

    with pytest.raises(InvestigationOperationsError, match="outside the authorized scope"):
        await service.create(
            domain_request(),
            context=context(resource_id="resource.investigation.other"),
        )

    assert audit_sink.records == []
