"""ATLAS-IMP-280: `atlas.modules.itsm.domain.dispatch.authorize_outbound_dispatch` was real,
fully-tested domain code with no application service, repository, route, or DI wiring calling it
-- the same "built but structurally unreachable" pattern this session has repeatedly fixed
(Pass 11/12: RCA review/close, Syslog destination administration, Embedding/AI model lifecycle).
These tests exercise the new `POST /itsm/integrations/{profile_id}/dispatch-authorizations`
endpoint through the real HTTP API (`TestClient(create_app(...))`), proving the composition of an
active ITSM integration profile + ready sandbox onboarding + an accepted human handoff review is
now reachable end to end, matches SS9's "consequential external submission requires the role and
review defined by policy," and never authorizes a dispatch without a completed human review.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_itsm_integration_service import (
    ApprovedSandboxOnboardingEvidenceSource,
    ProductionEligibleSandboxAdapter,
)
from test_report_api import TARGET, create_recommendation, report_payload

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.config import Settings
from atlas.modules.authorization.application.bootstrap import ITSM_REVIEWER_ROLE_ID
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.itsm.adapters.memory import InMemoryItsmIntegrationProfileRepository
from atlas.modules.itsm.adapters.onboarding import (
    InMemoryItsmSandboxOnboardingPolicyProvenanceSource,
    InMemoryItsmSandboxOnboardingPolicySource,
    InMemoryItsmSandboxOnboardingPolicyTrustSource,
    build_development_itsm_sandbox_onboarding_policy,
    build_development_itsm_sandbox_onboarding_policy_authenticity,
)
from atlas.modules.itsm.application.service import ItsmIntegrationService
from atlas.modules.itsm.domain.models import ItsmAllowedOperation
from atlas.modules.reports.adapters.synthetic import SyntheticTechnicalReportAssembler
from atlas.modules.reports.application.handoff_review_service import ItsmHandoffReviewService
from atlas.modules.reports.domain.handoff_review import ItsmHandoffReviewOutcome

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
DEVELOPMENT_ORGANIZATION_ID = "organization.development"


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "development_identity_enabled": True,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/authentication/sessions",
        json={"username": "atlas-demo", "password": "local-demo"},
    )
    assert response.status_code == 201
    return str(response.headers["X-CSRF-Token"])


class OutboundOperationAssembler(SyntheticTechnicalReportAssembler):
    """The only `ReportAssembler` in this codebase (`SyntheticTechnicalReportAssembler`) labels
    its synthetic ITSM handoff operation `"append_labeled_analysis"`, which is not a member of
    `ItsmAllowedOperation` -- so no report generated through the default pipeline can ever be
    dispatch-authorized. This test-only subclass relabels the draft's operation to a real
    outbound `ItsmAllowedOperation` member so the accept path is actually reachable."""

    def build(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        report = super().build(*args, **kwargs)  # type: ignore[arg-type]
        if report.itsm_handoff is None:
            return report
        handoff = replace(report.itsm_handoff, operation=ItsmAllowedOperation.APPEND_ANALYSIS.value)
        return replace(report, itsm_handoff=handoff)


def _ready_itsm_integration_service(sink: object) -> ItsmIntegrationService:
    policy = build_development_itsm_sandbox_onboarding_policy(
        organization_id=DEVELOPMENT_ORGANIZATION_ID,
        environment_id="environment.test",
        site_id="site.local",
        now=NOW,
    )
    provenance, trust_key, verifier = build_development_itsm_sandbox_onboarding_policy_authenticity(
        policy
    )
    return ItsmIntegrationService(
        repository=InMemoryItsmIntegrationProfileRepository(),
        audit_sink=sink,  # type: ignore[arg-type]
        environment_id="environment.test",
        sandbox_conformance_adapter=ProductionEligibleSandboxAdapter(),
        sandbox_onboarding_evidence_source=ApprovedSandboxOnboardingEvidenceSource(),
        sandbox_onboarding_policy_source=InMemoryItsmSandboxOnboardingPolicySource((policy,)),
        sandbox_onboarding_policy_provenance_source=(
            InMemoryItsmSandboxOnboardingPolicyProvenanceSource((provenance,))
        ),
        sandbox_onboarding_policy_trust_source=InMemoryItsmSandboxOnboardingPolicyTrustSource(
            (trust_key,)
        ),
        sandbox_onboarding_policy_verifier=verifier,
        clock=lambda: NOW,
    )


class _CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


def _app() -> FastAPI:
    sink = _CollectingAuditSink()
    return create_app(
        _settings(),
        audit_sink=sink,
        itsm_integration_service=_ready_itsm_integration_service(sink),
    )


def _profile_payload() -> dict[str, object]:
    return {
        "schema_version": "atlas.itsm-integration-profile-create-input.v1",
        "profile_key": "itsm.dispatch.primary",
        "display_name": "Dispatch-ready ITSM sandbox",
        "provider_family": "generic_rest",
        "instance_reference": "itsm-instance.dispatch.primary",
        "owner_id": "team.service-management",
        "purpose": "Validate governed outbound dispatch authorization wiring in a sandbox.",
        "endpoint_origin": "https://itsm-dispatch.example.invalid",
        "trust_boundary_reference": "trust-boundary.itsm.dispatch",
        "secret_reference_id": "secret.itsm.dispatch.writer",
        "classification_ceiling": "internal",
        "allowed_operations": ["append_analysis"],
        "mapping_version": 1,
        "field_mappings": [
            {
                "source_field": "work_notes",
                "provider_field": "work_notes",
                "write_semantics": "append_only",
            },
            {
                "source_field": "u_atlas_report_reference",
                "provider_field": "u_atlas_report_reference",
                "write_semantics": "reference_only",
            },
            {
                "source_field": "u_atlas_review_state",
                "provider_field": "u_atlas_review_state",
                "write_semantics": "reference_only",
            },
        ],
        "sandbox_validation_reference": "validation.itsm.dispatch.001",
        "sandbox_validation_digest": "a" * 64,
        "audit_profile_id": "audit-profile.itsm.dispatch",
        "acknowledged_configuration_only": True,
    }


def _create_ready_profile(
    client: TestClient, csrf: str, *, idempotency_key: str
) -> dict[str, object]:
    created = client.post(
        "/api/v1/itsm/integrations",
        json=_profile_payload(),
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": idempotency_key},
    )
    assert created.status_code == 201, created.text
    profile = created.json()["data"]

    conformance = client.post(
        f"/api/v1/itsm/integrations/{profile['profile_id']}/sandbox-conformance-assessments",
        json={
            "schema_version": "atlas.itsm-sandbox-conformance-input.v1",
            "expected_profile_version": profile["version"],
            "acknowledged_diagnostic_only_and_no_dispatch": True,
        },
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": f"{idempotency_key}-conformance"},
    )
    assert conformance.status_code == 201, conformance.text

    readiness = client.get(
        f"/api/v1/itsm/integrations/{profile['profile_id']}/sandbox-onboarding-readiness"
    )
    assert readiness.status_code == 200, readiness.text
    readiness_data = readiness.json()["data"]
    assert readiness_data["state"] == "ready"
    assert readiness_data["sandbox_onboarding_ready"] is True
    return profile  # type: ignore[no-any-return]


def _generate_report(client: TestClient) -> dict[str, object]:
    source = create_recommendation(client)
    response = client.post(
        f"/api/v1/reports/storage/{TARGET}",
        json=report_payload(source["recommendation_id"], source["version"]),
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]  # type: ignore[no-any-return]


def _decide_review(
    app: FastAPI,
    report: dict[str, object],
    *,
    outcome: ItsmHandoffReviewOutcome,
    idempotency_key: str,
) -> None:
    handoff = report["itsm_handoff"]
    assert isinstance(handoff, dict)
    reviewer = AuthenticatedSubject(
        subject_id="subject.itsm.dispatch-reviewer",
        display_name="ITSM Dispatch Reviewer",
        kind=SubjectKind.HUMAN,
        provider_id="provider.development.test",
        authentication_method=AuthenticationMethod.DEVELOPMENT,
        assurance_level=AssuranceLevel.SINGLE_FACTOR,
        authenticated_at=NOW,
        organization_id=DEVELOPMENT_ORGANIZATION_ID,
        role_ids=(ITSM_REVIEWER_ROLE_ID,),
    )
    service: ItsmHandoffReviewService = app.state.itsm_handoff_review_service  # type: ignore[attr-defined]
    review = asyncio.run(
        service.decide(
            actor=reviewer,
            report_id=str(report["report_id"]),
            report_version=int(report["version"]),  # type: ignore[arg-type]
            report_digest=str(report["content_digest"]),
            handoff_draft_id=str(handoff["draft_id"]),
            outcome=outcome,
            rationale="Evidence and field mappings are suitable for dispatch authorization.",
            acknowledged_review_only=True,
            idempotency_key=idempotency_key,
            correlation_id="correlation.itsm.dispatch.review",
        )
    )
    assert review.review_complete is (outcome is ItsmHandoffReviewOutcome.ACCEPT)


def test_itsm_dispatch_authorization_accept_path_is_reachable_through_the_api() -> None:
    app = _app()
    with TestClient(app) as client:
        app.state.report_service._assembler = OutboundOperationAssembler()
        report = _generate_report(client)
        csrf = _login(client)
        profile = _create_ready_profile(client, csrf, idempotency_key="itsm-dispatch-accept-0001")
        _decide_review(
            app,
            report,
            outcome=ItsmHandoffReviewOutcome.ACCEPT,
            idempotency_key="itsm-dispatch-review-accept-0001",
        )
        handoff = report["itsm_handoff"]
        assert isinstance(handoff, dict)

        dispatched = client.post(
            f"/api/v1/itsm/integrations/{profile['profile_id']}/dispatch-authorizations",
            json={
                "schema_version": "atlas.itsm-dispatch-authorization-input.v1",
                "expected_profile_version": profile["version"],
                "report_id": report["report_id"],
                "handoff_draft_id": handoff["draft_id"],
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "itsm-dispatch-authz-0001"},
        )
        replay = client.post(
            f"/api/v1/itsm/integrations/{profile['profile_id']}/dispatch-authorizations",
            json={
                "schema_version": "atlas.itsm-dispatch-authorization-input.v1",
                "expected_profile_version": profile["version"],
                "report_id": report["report_id"],
                "handoff_draft_id": handoff["draft_id"],
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "itsm-dispatch-authz-0001"},
        )

    assert dispatched.status_code == 201, dispatched.text
    assert dispatched.headers["Cache-Control"] == "no-store"
    data = dispatched.json()["data"]
    assert data["dispatch_authorized"] is True
    assert data["denial_reason"] is None
    assert data["profile_id"] == profile["profile_id"]
    assert data["draft_id"] == handoff["draft_id"]
    assert data["operation"] == "append_analysis"
    assert data["human_reviewer_id"] == "subject.itsm.dispatch-reviewer"
    assert data["human_review_completed_at"] is not None
    assert data["reused"] is False

    assert replay.status_code == 201, replay.text
    replay_data = replay.json()["data"]
    assert replay_data["authorization_id"] == data["authorization_id"]
    assert replay_data["dispatch_authorized"] is True
    assert replay_data["reused"] is True


def test_itsm_dispatch_authorization_denies_without_an_accepted_review() -> None:
    app = _app()
    with TestClient(app) as client:
        app.state.report_service._assembler = OutboundOperationAssembler()
        report = _generate_report(client)
        csrf = _login(client)
        profile = _create_ready_profile(client, csrf, idempotency_key="itsm-dispatch-deny-0001")
        _decide_review(
            app,
            report,
            outcome=ItsmHandoffReviewOutcome.REJECT,
            idempotency_key="itsm-dispatch-review-reject-0001",
        )
        handoff = report["itsm_handoff"]
        assert isinstance(handoff, dict)

        denied = client.post(
            f"/api/v1/itsm/integrations/{profile['profile_id']}/dispatch-authorizations",
            json={
                "schema_version": "atlas.itsm-dispatch-authorization-input.v1",
                "expected_profile_version": profile["version"],
                "report_id": report["report_id"],
                "handoff_draft_id": handoff["draft_id"],
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "itsm-dispatch-authz-deny-0001"},
        )

    assert denied.status_code == 409, denied.text
    assert denied.json()["code"] == "itsm_dispatch_review_not_accepted"
    repository = app.state.itsm_dispatch_authorization_service.repository  # type: ignore[attr-defined]
    assert (
        asyncio.run(
            repository.get_by_idempotency_key(
                requested_by="subject.development.operator",
                idempotency_key="itsm-dispatch-authz-deny-0001",
            )
        )
        is None
    )


def test_itsm_dispatch_authorization_requires_csrf_and_permission() -> None:
    app = _app()
    with TestClient(app) as client:
        app.state.report_service._assembler = OutboundOperationAssembler()
        report = _generate_report(client)
        csrf = _login(client)
        profile = _create_ready_profile(client, csrf, idempotency_key="itsm-dispatch-csrf-0001")
        _decide_review(
            app,
            report,
            outcome=ItsmHandoffReviewOutcome.ACCEPT,
            idempotency_key="itsm-dispatch-review-csrf-0001",
        )
        handoff = report["itsm_handoff"]
        assert isinstance(handoff, dict)

        missing_csrf = client.post(
            f"/api/v1/itsm/integrations/{profile['profile_id']}/dispatch-authorizations",
            json={
                "schema_version": "atlas.itsm-dispatch-authorization-input.v1",
                "expected_profile_version": profile["version"],
                "report_id": report["report_id"],
                "handoff_draft_id": handoff["draft_id"],
            },
            headers={"Idempotency-Key": "itsm-dispatch-authz-csrf-0001"},
        )

    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["code"] == "csrf_validation_failed"
