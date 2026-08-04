from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import TypedDict

import pytest
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.classification import DataClassification
from atlas.core.config import Settings
from atlas.modules.recommendations.application.service import RecommendationService
from atlas.modules.recommendations.domain.models import RecommendationArtifact
from atlas.modules.reports.adapters.synthetic import SyntheticTechnicalReportAssembler
from atlas.modules.reports.application.service import (
    ReportAccessContext,
    ReportOperationsError,
    ReportService,
)
from atlas.modules.reports.domain.models import (
    ReportAudience,
    ReportRequest,
    ReportType,
)

NOW = datetime(2026, 8, 4, 14, 0, tzinfo=UTC)
TARGET = "asset.storage.lab.b28"


class SourceRecommendationData(TypedDict):
    recommendation_id: str
    version: int


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


class ReportAcceptedAuditFailingSink(CollectingAuditSink):
    async def record(self, event: AuditRecord) -> None:
        if event.event_type == "atlas.report.accepted":
            raise RuntimeError("report audit unavailable")
        await super().record(event)


class CountingRecommendationProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def get_recommendation(
        self,
        recommendation_id: str,
        version: int,
        target_id: str,
    ) -> RecommendationArtifact:
        self.calls += 1
        raise KeyError(recommendation_id)


class TamperedDigestAssembler(SyntheticTechnicalReportAssembler):
    def build(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        report = super().build(*args, **kwargs)  # type: ignore[arg-type]
        object.__setattr__(report, "content_digest", "0" * 64)
        return report


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "development_identity_enabled": True,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def rca_payload() -> dict[str, object]:
    return {
        "incident_id": "INC-2026-0042",
        "user_report": "Storage warning appeared during the service window.",
        "expected_behavior": "Storage paths remain healthy and redundant.",
        "actual_behavior": "Controller CTL01 reports a warning.",
        "window_start": (NOW - timedelta(hours=24)).isoformat(),
        "window_end": NOW.isoformat(),
        "max_evidence_records": 12,
    }


def recommendation_payload(case_id: str, version: int) -> dict[str, object]:
    return {
        "source_case_id": case_id,
        "source_case_version": version,
        "decision_question": "What is the safest next operational choice?",
        "accountable_audience": "Storage Operations",
        "horizon": "immediate_response",
        "constraints": ["No infrastructure change", "C1 read-only maximum"],
        "maximum_capability_class": "C1",
        "max_options": 5,
    }


def report_payload(
    recommendation_id: str = "rec_unknown",
    version: int = 1,
    **overrides: object,
) -> dict[str, object]:
    values: dict[str, object] = {
        "source_recommendation_id": recommendation_id,
        "source_recommendation_version": version,
        "report_type": "technical_decision",
        "audience": "technical_operations",
        "classification": DataClassification.INTERNAL,
        "include_itsm_handoff": True,
        "incident_reference": "INC-2026-0042",
    }
    values.update(overrides)
    return values


def create_recommendation(client: TestClient) -> SourceRecommendationData:
    rca_response = client.post(f"/api/v1/rca/storage/{TARGET}", json=rca_payload())
    assert rca_response.status_code == 200
    case = rca_response.json()["data"]
    response = client.post(
        f"/api/v1/recommendations/storage/{TARGET}",
        json=recommendation_payload(str(case["case_id"]), int(case["version"])),
    )
    assert response.status_code == 200
    data = response.json()["data"]
    return {
        "recommendation_id": str(data["recommendation_id"]),
        "version": int(data["version"]),
    }


def context(**overrides: object) -> ReportAccessContext:
    values: dict[str, object] = {
        "subject_id": "subject.development.operator",
        "actor_type": "human",
        "authentication_method": "development",
        "assurance_level": "development",
        "organization_id": "organization.development",
        "environment_id": "environment.test",
        "site_id": "site.local",
        "resource_id": "resource.report.storage.synthetic",
        "correlation_id": "cor_report",
        "decision_id": "dec_report",
        "requested_at": NOW,
    }
    values.update(overrides)
    return ReportAccessContext(**values)  # type: ignore[arg-type]


def domain_request(**overrides: object) -> ReportRequest:
    values: dict[str, object] = {
        "source_recommendation_id": "rec_unknown",
        "source_recommendation_version": 1,
        "target_id": TARGET,
        "report_type": ReportType.TECHNICAL_DECISION,
        "audience": ReportAudience.TECHNICAL_OPERATIONS,
        "classification": "internal",
        "include_itsm_handoff": True,
        "incident_reference": "INC-2026-0042",
    }
    values.update(overrides)
    return ReportRequest(**values)  # type: ignore[arg-type]


def test_report_requires_authentication() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.post(
            f"/api/v1/reports/storage/{TARGET}",
            json=report_payload(),
        )

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_report_requires_exact_assignment() -> None:
    with TestClient(
        create_app(settings(development_role_ids=()), audit_sink=CollectingAuditSink())
    ) as client:
        response = client.post(
            f"/api/v1/reports/storage/{TARGET}",
            json=report_payload(),
        )

    assert response.status_code == 403
    assert response.json()["code"] == "authorization_denied"
    assert "report" not in response.json()["detail"].lower()


def test_report_is_versioned_evidence_linked_and_audited() -> None:
    audit_sink = CollectingAuditSink()
    with TestClient(create_app(settings(), audit_sink=audit_sink)) as client:
        source = create_recommendation(client)
        response = client.post(
            f"/api/v1/reports/storage/{TARGET}",
            json=report_payload(source["recommendation_id"], source["version"]),
            headers={"X-Correlation-ID": "cor_report_case"},
        )

    data = response.json()["data"]
    assert response.status_code == 200
    assert response.json()["meta"]["correlation_id"] == "cor_report_case"
    assert data["version"] == 1
    assert data["state"] == "ready_for_review"
    assert data["source"]["recommendation_id"] == source["recommendation_id"]
    assert data["source"]["recommendation_version"] == 1
    assert data["source"]["rca_case_version"] == 1
    assert data["source"]["evidence_ids"]
    assert data["review"]["status"] == "pending"
    assert data["redaction_state"] == "complete"
    assert data["execution_authorized"] is False
    assert data["external_mutation_authorized"] is False
    assert [record.event_type for record in audit_sink.records[-2:]] == [
        "atlas.report.accepted",
        "atlas.report.completed",
    ]


def test_report_sections_preserve_partial_state_evidence_and_limitations() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        source = create_recommendation(client)
        data = client.post(
            f"/api/v1/reports/storage/{TARGET}",
            json=report_payload(source["recommendation_id"], source["version"]),
        ).json()["data"]

    sections = {section["section_id"]: section for section in data["sections"]}
    assert set(sections) == {
        "report.section.scope",
        "report.section.decision-context",
        "report.section.preference",
        "report.section.alternatives",
        "report.section.risk-impact-recovery",
        "report.section.governance",
    }
    assert sections["report.section.scope"]["state"] == "complete"
    assert sections["report.section.preference"]["state"] == "partial"
    assert sections["report.section.preference"]["evidence_references"]
    assert sections["report.section.preference"]["limitations"]
    assert sections["report.section.alternatives"]["limitations"]
    source_evidence = set(data["source"]["evidence_ids"])
    assert all(
        set(section["evidence_references"]) <= source_evidence for section in data["sections"]
    )


def test_markdown_is_integrity_bound_and_repeats_safety_boundary() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        source = create_recommendation(client)
        data = client.post(
            f"/api/v1/reports/storage/{TARGET}",
            json=report_payload(source["recommendation_id"], source["version"]),
        ).json()["data"]

    markdown = data["rendered_markdown"]
    assert data["content_digest"] == sha256(markdown.encode("utf-8")).hexdigest()
    assert "# Atlas Technical Decision Report" in markdown
    assert source["recommendation_id"] in markdown
    assert "No Atlas execution authority is present" in markdown
    assert "do not authorize Atlas" in data["safety_notice"]


def test_itsm_handoff_is_idempotent_review_only_and_non_dispatching() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        source = create_recommendation(client)
        payload = report_payload(source["recommendation_id"], source["version"])
        first = client.post(f"/api/v1/reports/storage/{TARGET}", json=payload).json()["data"]
        second = client.post(f"/api/v1/reports/storage/{TARGET}", json=payload).json()["data"]

    assert second["report_id"] == first["report_id"]
    assert second["version"] == first["version"] == 1
    assert second["content_digest"] == first["content_digest"]
    handoff = first["itsm_handoff"]
    assert handoff["state"] == "review_required"
    assert handoff["incident_reference"] == "INC-2026-0042"
    assert handoff["human_review_required"] is True
    assert handoff["dispatch_authorized"] is False
    assert handoff["external_record_mutated"] is False
    assert len(handoff["idempotency_key"]) == 64
    assert handoff["field_mappings"]
    assert handoff["artifact_references"]


def test_report_can_omit_itsm_handoff_without_implying_dispatch() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        source = create_recommendation(client)
        response = client.post(
            f"/api/v1/reports/storage/{TARGET}",
            json=report_payload(
                source["recommendation_id"],
                source["version"],
                include_itsm_handoff=False,
                incident_reference=None,
            ),
        )

    data = response.json()["data"]
    assert response.status_code == 200
    assert data["itsm_handoff"] is None
    assert data["external_mutation_authorized"] is False


def test_new_recommendation_creates_linked_report_version() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        first_source = create_recommendation(client)
        first = client.post(
            f"/api/v1/reports/storage/{TARGET}",
            json=report_payload(first_source["recommendation_id"], first_source["version"]),
        ).json()["data"]
        second_source = create_recommendation(client)
        second = client.post(
            f"/api/v1/reports/storage/{TARGET}",
            json=report_payload(second_source["recommendation_id"], second_source["version"]),
        ).json()["data"]

    assert first["version"] == 1
    assert second["version"] == 2
    assert second["prior_version_id"] == first["report_id"]
    assert second["report_id"] != first["report_id"]


def test_missing_and_mismatched_sources_return_same_safe_error() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        source = create_recommendation(client)
        missing = client.post(
            f"/api/v1/reports/storage/{TARGET}",
            json=report_payload("rec_missing"),
        )
        wrong_version = client.post(
            f"/api/v1/reports/storage/{TARGET}",
            json=report_payload(source["recommendation_id"], 99),
        )

    assert missing.status_code == wrong_version.status_code == 404
    assert missing.json()["code"] == wrong_version.json()["code"] == "report_source_unavailable"
    assert missing.json()["detail"] == wrong_version.json()["detail"]
    assert "missing" not in missing.text.lower()


def test_invalid_incident_reference_is_rejected_before_report_service() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        response = client.post(
            f"/api/v1/reports/storage/{TARGET}",
            json=report_payload(incident_reference="CHANGE-42"),
        )

    assert response.status_code == 422
    assert "rec_unknown" not in response.text


def test_required_acceptance_audit_failure_blocks_source_read() -> None:
    audit_sink = ReportAcceptedAuditFailingSink()
    provider = CountingRecommendationProvider()
    service = ReportService(
        source_provider=provider,
        assembler=SyntheticTechnicalReportAssembler(),
        audit_sink=audit_sink,
    )
    with TestClient(
        create_app(settings(), audit_sink=audit_sink, report_service=service),
        raise_server_exceptions=False,
    ) as client:
        response = client.post(
            f"/api/v1/reports/storage/{TARGET}",
            json=report_payload(),
        )

    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
    assert provider.calls == 0
    assert "controller" not in response.text.lower()


def test_content_digest_mismatch_fails_closed() -> None:
    audit_sink = CollectingAuditSink()
    app = create_app(settings(), audit_sink=audit_sink)
    with TestClient(app) as source_client:
        source = create_recommendation(source_client)
        source_service: RecommendationService = app.state.recommendation_service
        report_service = ReportService(
            source_provider=source_service,
            assembler=TamperedDigestAssembler(),
            audit_sink=audit_sink,
        )
        app.state.report_service = report_service
        response = source_client.post(
            f"/api/v1/reports/storage/{TARGET}",
            json=report_payload(source["recommendation_id"], source["version"]),
        )

    assert response.status_code == 409
    assert response.json()["code"] == "report_digest_mismatch"
    assert "0" * 16 not in response.text


@pytest.mark.asyncio
async def test_report_scope_mismatch_is_rejected_before_audit() -> None:
    audit_sink = CollectingAuditSink()
    provider = CountingRecommendationProvider()
    service = ReportService(
        source_provider=provider,
        assembler=SyntheticTechnicalReportAssembler(),
        audit_sink=audit_sink,
    )

    with pytest.raises(ReportOperationsError, match="outside the authorized scope"):
        await service.create(
            domain_request(),
            context=context(resource_id="resource.report.other"),
        )

    assert provider.calls == 0
    assert audit_sink.records == []
