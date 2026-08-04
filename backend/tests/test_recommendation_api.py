from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import TypedDict

import pytest
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.config import Settings
from atlas.modules.rca.adapters.synthetic import SyntheticStorageRcaAssembler
from atlas.modules.rca.application.service import RcaService
from atlas.modules.rca.domain.models import RcaCase
from atlas.modules.recommendations.adapters.synthetic import (
    SyntheticStorageRecommendationAssembler,
)
from atlas.modules.recommendations.application.service import (
    RecommendationAccessContext,
    RecommendationOperationsError,
    RecommendationService,
)
from atlas.modules.recommendations.domain.models import RecommendationRequest

NOW = datetime(2026, 8, 4, 14, 0, tzinfo=UTC)
TARGET = "asset.storage.lab.b28"


class SourceCaseData(TypedDict):
    case_id: str
    version: int


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


class AcceptedAuditFailingSink(CollectingAuditSink):
    async def record(self, event: AuditRecord) -> None:
        if event.event_type == "atlas.recommendation.accepted":
            raise RuntimeError("recommendation audit unavailable")
        await super().record(event)


class CountingProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def get_case(self, case_id: str, version: int, target_id: str) -> RcaCase:
        self.calls += 1
        raise KeyError(case_id)


class UnsafeCapabilityAssembler(SyntheticStorageRecommendationAssembler):
    def build(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        artifact = super().build(*args, **kwargs)  # type: ignore[arg-type]
        option = artifact.options[0]
        step = replace(option.plan_steps[0], capability_id="vendor.storage.restart")
        return replace(
            artifact,
            options=(
                replace(option, plan_steps=(step, *option.plan_steps[1:])),
                *artifact.options[1:],
            ),
        )


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


def recommendation_payload(
    case_id: str = "rca_unknown",
    version: int = 1,
    **overrides: object,
) -> dict[str, object]:
    values: dict[str, object] = {
        "source_case_id": case_id,
        "source_case_version": version,
        "decision_question": "What is the safest next operational choice?",
        "accountable_audience": "Storage Operations",
        "horizon": "immediate_response",
        "constraints": ["No infrastructure change", "C1 read-only maximum"],
        "maximum_capability_class": "C1",
        "max_options": 5,
    }
    values.update(overrides)
    return values


def create_source(client: TestClient) -> SourceCaseData:
    response = client.post(f"/api/v1/rca/storage/{TARGET}", json=rca_payload())
    assert response.status_code == 200
    data = response.json()["data"]
    return {"case_id": str(data["case_id"]), "version": int(data["version"])}


def context(**overrides: object) -> RecommendationAccessContext:
    values: dict[str, object] = {
        "subject_id": "subject.development.operator",
        "actor_type": "human",
        "authentication_method": "development",
        "assurance_level": "development",
        "organization_id": "organization.development",
        "environment_id": "environment.test",
        "site_id": "site.local",
        "resource_id": "resource.recommendation.storage.synthetic",
        "correlation_id": "cor_recommendation",
        "decision_id": "dec_recommendation",
        "requested_at": NOW,
    }
    values.update(overrides)
    return RecommendationAccessContext(**values)  # type: ignore[arg-type]


def domain_request(**overrides: object) -> RecommendationRequest:
    values: dict[str, object] = {
        "source_case_id": "rca_unknown",
        "source_case_version": 1,
        "target_id": TARGET,
        "decision_question": "What is the safest next operational choice?",
        "accountable_audience": "Storage Operations",
        "horizon": "immediate_response",
        "constraints": ("No infrastructure change",),
        "maximum_capability_class": "C1",
        "max_options": 5,
    }
    values.update(overrides)
    return RecommendationRequest(**values)  # type: ignore[arg-type]


def test_recommendation_requires_authentication() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.post(
            f"/api/v1/recommendations/storage/{TARGET}",
            json=recommendation_payload(),
        )

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_recommendation_requires_exact_assignment() -> None:
    with TestClient(
        create_app(settings(development_role_ids=()), audit_sink=CollectingAuditSink())
    ) as client:
        response = client.post(
            f"/api/v1/recommendations/storage/{TARGET}",
            json=recommendation_payload(),
        )

    assert response.status_code == 403
    assert response.json()["code"] == "authorization_denied"
    assert "recommendation" not in response.json()["detail"].lower()


def test_recommendation_returns_versioned_compared_human_governed_options() -> None:
    audit_sink = CollectingAuditSink()
    with TestClient(create_app(settings(), audit_sink=audit_sink)) as client:
        source = create_source(client)
        response = client.post(
            f"/api/v1/recommendations/storage/{TARGET}",
            json=recommendation_payload(str(source["case_id"]), int(source["version"])),
            headers={"X-Correlation-ID": "cor_recommendation_case"},
        )

    data = response.json()["data"]
    assert response.status_code == 200
    assert response.json()["meta"]["correlation_id"] == "cor_recommendation_case"
    assert data["version"] == 1
    assert data["source_case_id"] == source["case_id"]
    assert data["source_case_version"] == 1
    assert data["source_case_state"] == "provisional"
    assert data["state"] == "ready_for_review"
    assert data["human_review"]["status"] == "pending"
    assert data["execution_authorized"] is False
    assert len(data["options"]) == 5
    assert {item["category"] for item in data["options"]} == {
        "investigate",
        "escalate",
        "defer_no_action",
        "restoration_planning",
        "remediation_planning",
    }
    assert {item["dimension"] for item in data["comparisons"]} == {
        "evidence_strength",
        "risk_and_interruption",
        "reversibility",
        "duration",
        "policy_and_readiness",
    }
    assert [item.event_type for item in audit_sink.records[-2:]] == [
        "atlas.recommendation.accepted",
        "atlas.recommendation.completed",
    ]


def test_preference_is_read_only_reversible_and_evidence_supported() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        source = create_source(client)
        data = client.post(
            f"/api/v1/recommendations/storage/{TARGET}",
            json=recommendation_payload(str(source["case_id"]), int(source["version"])),
        ).json()["data"]

    preferred = next(
        option for option in data["options"] if option["option_id"] == data["preferred_option_id"]
    )
    assert preferred["category"] == "investigate"
    assert preferred["state"] == "viable"
    assert preferred["preference"] == "preferred"
    assert preferred["overall_risk"] == "low"
    assert preferred["recovery"]["rollback_feasible"] is True
    assert preferred["supporting_evidence"]
    assert all(step["capability_class"] == "C1" for step in preferred["plan_steps"])
    assert all(step["executable_by_atlas"] is False for step in preferred["plan_steps"])
    assert "read-only" in data["preference_rationale"].lower()


def test_consequential_planning_options_are_visible_but_blocked() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        source = create_source(client)
        data = client.post(
            f"/api/v1/recommendations/storage/{TARGET}",
            json=recommendation_payload(str(source["case_id"]), int(source["version"])),
        ).json()["data"]

    blocked = [option for option in data["options"] if option["state"] == "blocked"]
    assert {item["category"] for item in blocked} == {
        "restoration_planning",
        "remediation_planning",
    }
    assert set(data["excluded_option_ids"]) == {item["option_id"] for item in blocked}
    assert all(item["preference"] == "ineligible" for item in blocked)
    assert all(item["exclusion_reasons"] for item in blocked)
    assert any(
        "Root cause is not confirmed" in reason
        for item in blocked
        for reason in item["exclusion_reasons"]
    )
    assert all(
        step["executable_by_atlas"] is False for item in blocked for step in item["plan_steps"]
    )


def test_defer_option_has_trigger_expiry_and_residual_risk() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        source = create_source(client)
        data = client.post(
            f"/api/v1/recommendations/storage/{TARGET}",
            json=recommendation_payload(str(source["case_id"]), int(source["version"])),
        ).json()["data"]

    defer = next(item for item in data["options"] if item["category"] == "defer_no_action")
    assert defer["stop_conditions"]
    assert defer["residual_risk"]
    assert defer["policy_outcome"] == "permitted_with_expiry_and_trigger"
    assert data["expires_at"] > data["created_at"]


def test_repeated_recommendation_creates_immutable_linked_version() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        source = create_source(client)
        payload = recommendation_payload(str(source["case_id"]), int(source["version"]))
        first = client.post(f"/api/v1/recommendations/storage/{TARGET}", json=payload).json()[
            "data"
        ]
        second = client.post(f"/api/v1/recommendations/storage/{TARGET}", json=payload).json()[
            "data"
        ]

    assert first["version"] == 1
    assert second["version"] == 2
    assert second["prior_version_id"] == first["recommendation_id"]
    assert second["recommendation_id"] != first["recommendation_id"]


def test_missing_and_mismatched_sources_return_same_safe_error() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        source = create_source(client)
        missing = client.post(
            f"/api/v1/recommendations/storage/{TARGET}",
            json=recommendation_payload("rca_missing"),
        )
        wrong_version = client.post(
            f"/api/v1/recommendations/storage/{TARGET}",
            json=recommendation_payload(str(source["case_id"]), 99),
        )

    assert missing.status_code == wrong_version.status_code == 404
    assert (
        missing.json()["code"]
        == wrong_version.json()["code"]
        == "recommendation_source_unavailable"
    )
    assert missing.json()["detail"] == wrong_version.json()["detail"]
    assert "missing" not in missing.text.lower()


def test_required_acceptance_audit_failure_blocks_source_read() -> None:
    audit_sink = AcceptedAuditFailingSink()
    provider = CountingProvider()
    service = RecommendationService(
        source_provider=provider,
        assembler=SyntheticStorageRecommendationAssembler(),
        audit_sink=audit_sink,
    )
    with TestClient(
        create_app(settings(), audit_sink=audit_sink, recommendation_service=service),
        raise_server_exceptions=False,
    ) as client:
        response = client.post(
            f"/api/v1/recommendations/storage/{TARGET}",
            json=recommendation_payload(),
        )

    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
    assert provider.calls == 0
    assert "controller" not in response.text.lower()


def test_non_allowlisted_capability_fails_closed() -> None:
    audit_sink = CollectingAuditSink()
    rca_service = RcaService(
        assembler=SyntheticStorageRcaAssembler(),
        audit_sink=audit_sink,
    )
    recommendation_service = RecommendationService(
        source_provider=rca_service,
        assembler=UnsafeCapabilityAssembler(),
        audit_sink=audit_sink,
    )
    with TestClient(
        create_app(
            settings(),
            audit_sink=audit_sink,
            rca_service=rca_service,
            recommendation_service=recommendation_service,
        )
    ) as client:
        source = create_source(client)
        response = client.post(
            f"/api/v1/recommendations/storage/{TARGET}",
            json=recommendation_payload(str(source["case_id"]), int(source["version"])),
        )

    assert response.status_code == 409
    assert response.json()["code"] == "recommendation_capability_denied"
    assert "restart" not in response.text.lower()


def test_option_budget_is_bounded_and_keeps_safe_preference() -> None:
    with TestClient(create_app(settings(), audit_sink=CollectingAuditSink())) as client:
        source = create_source(client)
        response = client.post(
            f"/api/v1/recommendations/storage/{TARGET}",
            json=recommendation_payload(
                str(source["case_id"]),
                int(source["version"]),
                max_options=3,
            ),
        )

    data = response.json()["data"]
    assert response.status_code == 200
    assert len(data["options"]) == 3
    assert data["preferred_option_id"] == "recommendation.option.investigate"
    assert data["excluded_option_ids"] == []


@pytest.mark.asyncio
async def test_recommendation_scope_mismatch_is_rejected_before_audit() -> None:
    audit_sink = CollectingAuditSink()
    provider = CountingProvider()
    service = RecommendationService(
        source_provider=provider,
        assembler=SyntheticStorageRecommendationAssembler(),
        audit_sink=audit_sink,
    )

    with pytest.raises(RecommendationOperationsError, match="outside the authorized scope"):
        await service.create(
            domain_request(),
            context=context(resource_id="resource.recommendation.other"),
        )

    assert provider.calls == 0
    assert audit_sink.records == []
