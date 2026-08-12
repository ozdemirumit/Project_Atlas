from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
from typing import cast

import pytest
from fastapi.testclient import TestClient
from test_browser_sessions import BasicTestIdentityProvider, login, settings
from test_report_api import TARGET, CollectingAuditSink, create_recommendation, report_payload

from atlas.api.app import create_app
from atlas.core.persistence.models import ItsmHandoffHumanReviewModel
from atlas.modules.authorization.application.bootstrap import (
    ITSM_HANDOFF_REVIEW_DECIDE,
    ITSM_HANDOFF_REVIEW_READ,
    ITSM_REVIEWER_ROLE_ID,
    itsm_handoff_review_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import (
    CapabilityClass,
    PermissionDefinition,
    RoleAssignment,
    RoleDefinition,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.reports.adapters.handoff_review_postgres import (
    PostgreSQLItsmHandoffReviewRepository,
)
from atlas.modules.reports.application.handoff_review_service import (
    ItsmHandoffReviewError,
    ItsmHandoffReviewService,
)
from atlas.modules.reports.domain.handoff_review import ItsmHandoffReviewOutcome

NOW = datetime(2026, 8, 13, 1, 0, tzinfo=UTC)


def reviewer(**overrides: object) -> AuthenticatedSubject:
    values: dict[str, object] = {
        "subject_id": "subject.itsm.reviewer",
        "display_name": "ITSM Reviewer",
        "kind": SubjectKind.HUMAN,
        "provider_id": "provider.ldap.test",
        "authentication_method": AuthenticationMethod.LDAP,
        "assurance_level": AssuranceLevel.MULTI_FACTOR,
        "authenticated_at": NOW,
        "organization_id": "organization.development",
        "role_ids": (ITSM_REVIEWER_ROLE_ID,),
    }
    values.update(overrides)
    return AuthenticatedSubject(**values)  # type: ignore[arg-type]


def reviewer_authorization(
    actor: AuthenticatedSubject, sink: CollectingAuditSink
) -> AuthorizationService:
    permissions = (
        PermissionDefinition(ITSM_HANDOFF_REVIEW_READ, "Read ITSM handoff reviews."),
        PermissionDefinition(ITSM_HANDOFF_REVIEW_DECIDE, "Decide ITSM handoff reviews."),
    )
    role = RoleDefinition(
        role_id=ITSM_REVIEWER_ROLE_ID,
        version=1,
        permissions=frozenset({ITSM_HANDOFF_REVIEW_READ, ITSM_HANDOFF_REVIEW_DECIDE}),
    )
    assignments = tuple(
        RoleAssignment(
            assignment_id=f"assignment.itsm-reviewer.{capability.value.lower()}",
            version=1,
            subject_id=actor.subject_id,
            role_id=ITSM_REVIEWER_ROLE_ID,
            scope=itsm_handoff_review_scope(actor.organization_id, "test", capability),
            valid_from=datetime.min.replace(tzinfo=UTC),
        )
        for capability in (CapabilityClass.C1_READ_ONLY, CapabilityClass.C2_DIAGNOSTIC)
    )
    return AuthorizationService(
        permissions=permissions,
        roles=(role,),
        assignments=assignments,
        audit_sink=sink,
    )


def generated_report(client: TestClient) -> dict[str, object]:
    source = create_recommendation(client)
    response = client.post(
        f"/api/v1/reports/storage/{TARGET}",
        json=report_payload(source["recommendation_id"], source["version"]),
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]  # type: ignore[no-any-return]


def review_payload(report: dict[str, object], **overrides: object) -> dict[str, object]:
    handoff = report["itsm_handoff"]
    assert isinstance(handoff, dict)
    values: dict[str, object] = {
        "report_version": report["version"],
        "report_digest": report["content_digest"],
        "handoff_draft_id": handoff["draft_id"],
        "outcome": "accept",
        "rationale": "Evidence and field mappings are suitable for accountable handoff review.",
        "acknowledged_review_only": True,
    }
    values.update(overrides)
    return values


def test_itsm_handoff_review_api_requires_mfa_role_csrf_and_exact_source() -> None:
    sink = CollectingAuditSink()
    actor = reviewer()
    app = create_app(settings(), audit_sink=sink)
    with TestClient(app) as client:
        report = generated_report(client)
        denied_without_session = client.post(
            f"/api/v1/reports/{report['report_id']}/itsm-handoff/reviews",
            json=review_payload(report),
            headers={"Idempotency-Key": "itsm-review-0001"},
        )
        app.state.authorization_service = reviewer_authorization(actor, sink)
        app.state.identity_service._provider = BasicTestIdentityProvider(actor)
        session = login(client)
        csrf = session.headers["X-CSRF-Token"]
        denied_without_csrf = client.post(
            f"/api/v1/reports/{report['report_id']}/itsm-handoff/reviews",
            json=review_payload(report),
            headers={"Idempotency-Key": "itsm-review-0001"},
        )
        response = client.post(
            f"/api/v1/reports/{report['report_id']}/itsm-handoff/reviews",
            json=review_payload(report),
            headers={
                "Idempotency-Key": "itsm-review-0001",
                "X-CSRF-Token": csrf,
            },
        )
        replay = client.post(
            f"/api/v1/reports/{report['report_id']}/itsm-handoff/reviews",
            json=review_payload(report),
            headers={
                "Idempotency-Key": "itsm-review-0001",
                "X-CSRF-Token": csrf,
            },
        )
        lookup = client.get(
            f"/api/v1/reports/{report['report_id']}/itsm-handoff/review",
            params={"handoff_draft_id": review_payload(report)["handoff_draft_id"]},
        )

    assert denied_without_session.status_code == 403
    assert denied_without_csrf.status_code == 403
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["outcome"] == "accept"
    assert data["review_complete"] is True
    assert data["dispatch_authorized"] is False
    assert data["external_record_mutated"] is False
    assert data["itsm_approval_satisfied"] is False
    assert data["workflow_approved"] is False
    assert data["execution_authorized"] is False
    assert data["infrastructure_mutation_performed"] is False
    assert replay.status_code == 200
    assert replay.json()["data"]["reused"] is True
    assert lookup.status_code == 200
    assert lookup.headers["Cache-Control"] == "no-store"
    assert lookup.json()["data"]["canonical_digest"] == data["canonical_digest"]


@pytest.mark.parametrize("outcome", list(ItsmHandoffReviewOutcome))
def test_review_outcomes_are_immutable_and_never_authorize_dispatch(outcome) -> None:  # type: ignore[no-untyped-def]
    sink = CollectingAuditSink()
    actor = reviewer()
    app = create_app(settings(), audit_sink=sink)
    with TestClient(app) as client:
        report_data = generated_report(client)
        service: ItsmHandoffReviewService = app.state.itsm_handoff_review_service
        handoff = report_data["itsm_handoff"]
        assert isinstance(handoff, dict)
        review = asyncio.run(
            service.decide(
                actor=actor,
                report_id=str(report_data["report_id"]),
                report_version=cast(int, report_data["version"]),
                report_digest=str(report_data["content_digest"]),
                handoff_draft_id=str(handoff["draft_id"]),
                outcome=outcome,
                rationale="Record a bounded evidence-based human review decision.",
                acknowledged_review_only=True,
                idempotency_key=f"review-{outcome.value}-0001",
                correlation_id=f"correlation.review.{outcome.value}",
            )
        )
    assert review.review_complete is (outcome is ItsmHandoffReviewOutcome.ACCEPT)
    assert not any(
        (
            review.dispatch_authorized,
            review.external_record_mutated,
            review.itsm_approval_satisfied,
            review.workflow_approved,
            review.execution_authorized,
            review.infrastructure_mutation_performed,
        )
    )


def test_review_rejects_self_review_insufficient_assurance_and_source_change() -> None:
    sink = CollectingAuditSink()
    app = create_app(settings(), audit_sink=sink)
    with TestClient(app) as client:
        report_data = generated_report(client)
        service: ItsmHandoffReviewService = app.state.itsm_handoff_review_service
        handoff = report_data["itsm_handoff"]
        assert isinstance(handoff, dict)

        def decide(
            actor: AuthenticatedSubject,
            idempotency_key: str,
            *,
            report_digest: str = str(report_data["content_digest"]),
        ) -> object:
            return asyncio.run(
                service.decide(
                    actor=actor,
                    report_id=str(report_data["report_id"]),
                    report_version=cast(int, report_data["version"]),
                    report_digest=report_digest,
                    handoff_draft_id=str(handoff["draft_id"]),
                    outcome=ItsmHandoffReviewOutcome.ACCEPT,
                    rationale="Review the exact generated handoff and its bounded evidence.",
                    acknowledged_review_only=True,
                    idempotency_key=idempotency_key,
                    correlation_id="correlation.review.denied",
                )
            )

        with pytest.raises(ItsmHandoffReviewError, match="assurance_insufficient"):
            decide(
                replace(reviewer(), assurance_level=AssuranceLevel.SINGLE_FACTOR),
                "review-denied-assurance",
            )
        with pytest.raises(ItsmHandoffReviewError, match="separation_required"):
            decide(
                replace(reviewer(), subject_id=str(report_data["requested_by"])),
                "review-denied-separation",
            )
        with pytest.raises(ItsmHandoffReviewError, match="source_changed"):
            decide(reviewer(), "review-denied-source", report_digest="0" * 64)

    denied_codes = {
        record.result_code
        for record in sink.records
        if record.event_type == "atlas.report.itsm-handoff-human-review"
        and record.outcome == "denied"
    }
    assert {
        "itsm_handoff_review_assurance_insufficient",
        "itsm_handoff_review_separation_required",
        "itsm_handoff_review_source_changed",
    } <= denied_codes


def test_postgres_mapping_preserves_review_binding_and_authority_boundary() -> None:
    sink = CollectingAuditSink()
    app = create_app(settings(), audit_sink=sink)
    with TestClient(app) as client:
        report_data = generated_report(client)
        service: ItsmHandoffReviewService = app.state.itsm_handoff_review_service
        handoff = report_data["itsm_handoff"]
        assert isinstance(handoff, dict)
        review = asyncio.run(
            service.decide(
                actor=reviewer(),
                report_id=str(report_data["report_id"]),
                report_version=cast(int, report_data["version"]),
                report_digest=str(report_data["content_digest"]),
                handoff_draft_id=str(handoff["draft_id"]),
                outcome=ItsmHandoffReviewOutcome.NEEDS_EVIDENCE,
                rationale="Additional authoritative incident context is required.",
                acknowledged_review_only=True,
                idempotency_key="review-postgres-map-0001",
                correlation_id="correlation.review.postgres",
            )
        )
    row = ItsmHandoffHumanReviewModel(**PostgreSQLItsmHandoffReviewRepository._values(review))
    restored = PostgreSQLItsmHandoffReviewRepository._to_domain(row)
    assert restored.canonical_digest == review.canonical_digest
    assert restored.handoff_digest == review.handoff_digest
    assert restored.outcome is ItsmHandoffReviewOutcome.NEEDS_EVIDENCE
    assert restored.review_complete is False
    assert restored.execution_authorized is False
