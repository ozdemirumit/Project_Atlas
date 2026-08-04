from __future__ import annotations

import base64
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.config import Settings
from atlas.modules.approvals.application.service import (
    ApprovalAccessContext,
    ApprovalOperationsError,
    ApprovalService,
)
from atlas.modules.approvals.domain.models import ApprovalOutcome, ApprovalState
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationInput,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.rca.adapters.synthetic import SyntheticStorageRcaAssembler
from atlas.modules.rca.application.service import RcaService
from atlas.modules.recommendations.adapters.synthetic import (
    SyntheticStorageRecommendationAssembler,
)
from atlas.modules.recommendations.application.service import RecommendationService

TARGET = "asset.storage.lab.b28"


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []
        self.fail_event: str | None = None

    async def record(self, event: AuditRecord) -> None:
        if event.event_type == self.fail_event:
            raise RuntimeError("approval audit unavailable")
        self.records.append(event)


class BasicIdentityProvider:
    async def authenticate(
        self, authentication_input: AuthenticationInput
    ) -> AuthenticatedSubject | None:
        if authentication_input.authorization_scheme != "basic":
            return None
        credential = authentication_input.credential
        if credential is None:
            return None
        try:
            decoded = base64.b64decode(credential, validate=True).decode()
        except ValueError:
            return None
        if decoded != "operator:correct-password":
            return None
        return subject(
            subject_id="subject.development.operator",
            method=AuthenticationMethod.LDAP,
            assurance=AssuranceLevel.SINGLE_FACTOR,
        )


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "development_identity_enabled": True,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def subject(
    *,
    subject_id: str = "subject.development.operator",
    kind: SubjectKind = SubjectKind.HUMAN,
    method: AuthenticationMethod = AuthenticationMethod.LDAP,
    assurance: AssuranceLevel = AssuranceLevel.SINGLE_FACTOR,
) -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id=subject_id,
        display_name="Approval Reviewer",
        kind=kind,
        provider_id="provider.ldap.test",
        authentication_method=method,
        assurance_level=assurance,
        authenticated_at=datetime.now(UTC),
        organization_id="organization.development",
        role_ids=("role.development.operator",),
    )


def build_services(
    sink: CollectingAuditSink,
) -> tuple[RcaService, RecommendationService, ApprovalService]:
    rca = RcaService(assembler=SyntheticStorageRcaAssembler(), audit_sink=sink)
    recommendation = RecommendationService(
        source_provider=rca,
        assembler=SyntheticStorageRecommendationAssembler(),
        audit_sink=sink,
    )
    approval = ApprovalService(recommendation_provider=recommendation, audit_sink=sink)
    return rca, recommendation, approval


def rca_payload() -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "incident_id": "INC-APPROVAL-001",
        "user_report": "Storage warning appeared during the service window.",
        "expected_behavior": "Storage paths remain healthy and redundant.",
        "actual_behavior": "Controller CTL01 reports a warning.",
        "window_start": (now - timedelta(hours=24)).isoformat(),
        "window_end": now.isoformat(),
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


def create_recommendation(client: TestClient) -> dict[str, Any]:
    case_response = client.post(f"/api/v1/rca/storage/{TARGET}", json=rca_payload())
    assert case_response.status_code == 200
    case = case_response.json()["data"]
    response = client.post(
        f"/api/v1/recommendations/storage/{TARGET}",
        json=recommendation_payload(case["case_id"], case["version"]),
    )
    assert response.status_code == 200
    return response.json()["data"]  # type: ignore[no-any-return]


def create_approval(client: TestClient) -> dict[str, Any]:
    recommendation = create_recommendation(client)
    response = client.post(
        f"/api/v1/approvals/storage/{TARGET}",
        json={
            "recommendation_id": recommendation["recommendation_id"],
            "recommendation_version": recommendation["version"],
            "option_id": recommendation["preferred_option_id"],
            "purpose": "Review the bounded read-only diagnostic plan.",
            "expires_in_minutes": 45,
        },
    )
    assert response.status_code == 201
    return response.json()["data"]  # type: ignore[no-any-return]


def access_context(
    record: dict[str, Any],
    **overrides: object,
) -> ApprovalAccessContext:
    packet = record["packet"]
    assert isinstance(packet, dict)
    values: dict[str, object] = {
        "subject_id": "subject.enterprise.reviewer",
        "actor_type": "human",
        "authentication_method": "ldap",
        "assurance_level": "single_factor",
        "organization_id": packet["organization_id"],
        "environment_id": packet["environment_id"],
        "site_id": packet["site_id"],
        "resource_id": "resource.approval.storage.synthetic",
        "correlation_id": "cor_approval_review",
        "decision_id": "dec_approval_review",
        "requested_at": datetime.now(UTC),
    }
    values.update(overrides)
    return ApprovalAccessContext(**values)  # type: ignore[arg-type]


def test_approval_requires_authentication_and_exact_assignment() -> None:
    payload = {
        "recommendation_id": "recommendation_unknown",
        "recommendation_version": 1,
        "option_id": "option_unknown",
        "purpose": "Review the bounded plan.",
        "expires_in_minutes": 30,
    }
    with TestClient(create_app(Settings(environment="test"))) as client:
        unauthenticated = client.post(f"/api/v1/approvals/storage/{TARGET}", json=payload)
    with TestClient(
        create_app(settings(development_role_ids=()), audit_sink=CollectingAuditSink())
    ) as client:
        unassigned = client.post(f"/api/v1/approvals/storage/{TARGET}", json=payload)

    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["code"] == "authentication_required"
    assert unassigned.status_code == 403
    assert unassigned.json()["code"] == "authorization_denied"


def test_creation_returns_immutable_evidence_and_non_execution_packet() -> None:
    sink = CollectingAuditSink()
    rca, recommendation, approval = build_services(sink)
    with TestClient(
        create_app(
            settings(),
            audit_sink=sink,
            rca_service=rca,
            recommendation_service=recommendation,
            approval_service=approval,
        )
    ) as client:
        data = create_approval(client)
        response = client.get(f"/api/v1/approvals/{data['request_id']}")

    packet = response.json()["data"]["packet"]
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["data"]["state"] == "pending"
    assert response.json()["data"]["execution_authorized"] is False
    assert packet["execution_authorized"] is False
    assert packet["canonicalization_version"] == "atlas-approval-packet.v1"
    assert len(packet["canonical_digest"]) == 64
    assert packet["evidence_references"]
    assert packet["evidence_summaries"]
    assert packet["unknowns"]
    assert packet["plan_steps"]
    assert packet["policy_constraints"]
    assert "credential" not in response.text.lower()
    assert sink.records[-1].event_type == "atlas.approval.request.read"
    stored = approval._records[str(data["request_id"])]
    canonical_values = asdict(stored.packet)
    canonical_digest = canonical_values.pop("canonical_digest")
    assert approval._digest_values(canonical_values) == canonical_digest


@pytest.mark.asyncio
async def test_eligible_separate_human_can_approve_without_execution_authority() -> None:
    sink = CollectingAuditSink()
    rca, recommendation, approval = build_services(sink)
    with TestClient(
        create_app(
            settings(),
            audit_sink=sink,
            rca_service=rca,
            recommendation_service=recommendation,
            approval_service=approval,
        )
    ) as client:
        data = create_approval(client)

    updated = await approval.decide(
        str(data["request_id"]),
        outcome=ApprovalOutcome.APPROVE,
        rationale="The evidence supports this bounded read-only diagnostic plan.",
        expected_version=int(data["version"]),
        idempotency_key="approval-review-key-0001",
        context=access_context(data),
    )

    assert updated.state is ApprovalState.APPROVED
    assert updated.version == 2
    assert updated.decisions[0].reviewer_id == "subject.enterprise.reviewer"
    assert updated.execution_authorized is False
    assert updated.packet.execution_authorized is False
    assert sink.records[-1].result_code == "approval_approve"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"subject_id": "subject.development.operator"}, "approval_separation_required"),
        ({"actor_type": "service"}, "approval_human_reviewer_required"),
        ({"assurance_level": "development"}, "approval_assurance_insufficient"),
    ],
)
async def test_ineligible_reviewer_fails_closed(overrides: dict[str, object], code: str) -> None:
    sink = CollectingAuditSink()
    rca, recommendation, approval = build_services(sink)
    with TestClient(
        create_app(
            settings(),
            audit_sink=sink,
            rca_service=rca,
            recommendation_service=recommendation,
            approval_service=approval,
        )
    ) as client:
        data = create_approval(client)

    with pytest.raises(ApprovalOperationsError, match="cannot decide") as raised:
        await approval.decide(
            str(data["request_id"]),
            outcome=ApprovalOutcome.REJECT,
            rationale="A separated reviewer is required for this packet.",
            expected_version=int(data["version"]),
            idempotency_key=f"approval-review-{code}",
            context=access_context(data, **overrides),
        )

    assert raised.value.code == code
    assert sink.records[-1].result_code == code


@pytest.mark.asyncio
async def test_decision_is_idempotent_and_conflicting_reuse_or_version_is_rejected() -> None:
    sink = CollectingAuditSink()
    rca, recommendation, approval = build_services(sink)
    with TestClient(
        create_app(
            settings(),
            audit_sink=sink,
            rca_service=rca,
            recommendation_service=recommendation,
            approval_service=approval,
        )
    ) as client:
        data = create_approval(client)
    context = access_context(data)
    kwargs = {
        "outcome": ApprovalOutcome.NEEDS_EVIDENCE,
        "rationale": "Current path evidence is required before approval.",
        "expected_version": int(data["version"]),
        "idempotency_key": "approval-review-key-0002",
        "context": context,
    }

    first = await approval.decide(str(data["request_id"]), **kwargs)  # type: ignore[arg-type]
    replay = await approval.decide(str(data["request_id"]), **kwargs)  # type: ignore[arg-type]

    assert replay == first
    assert replay.state is ApprovalState.NEEDS_EVIDENCE
    with pytest.raises(ApprovalOperationsError) as reused:
        await approval.decide(
            str(data["request_id"]),
            outcome=ApprovalOutcome.APPROVE,
            rationale="A different decision cannot reuse the same key.",
            expected_version=int(data["version"]),
            idempotency_key="approval-review-key-0002",
            context=context,
        )
    assert reused.value.code == "approval_idempotency_conflict"
    with pytest.raises(ApprovalOperationsError) as stale:
        await approval.decide(
            str(data["request_id"]),
            outcome=ApprovalOutcome.APPROVE,
            rationale="The stale packet cannot be overwritten.",
            expected_version=int(data["version"]),
            idempotency_key="approval-review-key-0003",
            context=context,
        )
    assert stale.value.code == "approval_state_conflict"


@pytest.mark.asyncio
async def test_expiry_and_digest_substitution_block_decision() -> None:
    sink = CollectingAuditSink()
    rca, recommendation, approval = build_services(sink)
    with TestClient(
        create_app(
            settings(),
            audit_sink=sink,
            rca_service=rca,
            recommendation_service=recommendation,
            approval_service=approval,
        )
    ) as client:
        expired_data = create_approval(client)
        tampered_data = create_approval(client)
        substituted_data = create_approval(client)

    expired_packet = expired_data["packet"]
    assert isinstance(expired_packet, dict)
    expired = await approval.get(
        str(expired_data["request_id"]),
        context=access_context(
            expired_data,
            requested_at=datetime.fromisoformat(str(expired_packet["expires_at"]))
            + timedelta(seconds=1),
        ),
    )
    assert expired.state is ApprovalState.EXPIRED

    stored = approval._records[str(tampered_data["request_id"])]
    approval._records[stored.request_id] = replace(
        stored,
        packet=replace(stored.packet, option_title="Substituted unsafe option"),
    )
    with pytest.raises(ApprovalOperationsError) as mismatch:
        await approval.get(stored.request_id, context=access_context(tampered_data))
    assert mismatch.value.code == "approval_digest_mismatch"
    assert sink.records[-1].result_code == "approval_digest_mismatch"

    source_record = approval._records[str(substituted_data["request_id"])]
    source = recommendation._artifacts[source_record.packet.recommendation_id]
    recommendation._artifacts[source.recommendation_id] = replace(
        source,
        options=tuple(
            replace(option, title="Changed after packet submission")
            if option.option_id == source_record.packet.option_id
            else option
            for option in source.options
        ),
    )
    with pytest.raises(ApprovalOperationsError) as changed:
        await approval.get(
            source_record.request_id,
            context=access_context(substituted_data),
        )
    assert changed.value.code == "approval_source_changed"
    assert sink.records[-1].result_code == "approval_source_changed"


def test_blocked_option_and_missing_source_share_safe_error() -> None:
    sink = CollectingAuditSink()
    rca, recommendation_service, approval = build_services(sink)
    with TestClient(
        create_app(
            settings(),
            audit_sink=sink,
            rca_service=rca,
            recommendation_service=recommendation_service,
            approval_service=approval,
        )
    ) as client:
        recommendation = create_recommendation(client)
        blocked = next(item for item in recommendation["options"] if item["state"] == "blocked")
        base = {
            "recommendation_version": recommendation["version"],
            "purpose": "Review a bounded recommendation option.",
            "expires_in_minutes": 30,
        }
        blocked_response = client.post(
            f"/api/v1/approvals/storage/{TARGET}",
            json={
                **base,
                "recommendation_id": recommendation["recommendation_id"],
                "option_id": blocked["option_id"],
            },
        )
        missing_response = client.post(
            f"/api/v1/approvals/storage/{TARGET}",
            json={
                **base,
                "recommendation_id": "recommendation_missing",
                "option_id": recommendation["preferred_option_id"],
            },
        )

    assert blocked_response.status_code == missing_response.status_code == 404
    assert blocked_response.json()["code"] == missing_response.json()["code"]
    assert blocked_response.json()["detail"] == missing_response.json()["detail"]
    assert "blocked" not in blocked_response.text.lower()


def test_cookie_decision_requires_csrf_then_enforces_separation() -> None:
    sink = CollectingAuditSink()
    rca, recommendation, approval = build_services(sink)
    with TestClient(
        create_app(
            settings(),
            audit_sink=sink,
            rca_service=rca,
            recommendation_service=recommendation,
            approval_service=approval,
        )
    ) as client:
        data = create_approval(client)

    with TestClient(
        create_app(
            settings(),
            audit_sink=sink,
            identity_provider=BasicIdentityProvider(),
            rca_service=rca,
            recommendation_service=recommendation,
            approval_service=approval,
        )
    ) as client:
        login = client.post(
            "/api/v1/authentication/sessions",
            json={"username": "operator", "password": "correct-password"},
        )
        payload = {
            "outcome": "approve",
            "rationale": "This self-review must remain unavailable.",
            "expected_version": data["version"],
        }
        headers = {"Idempotency-Key": "approval-browser-key-0001"}
        missing_csrf = client.post(
            f"/api/v1/approvals/{data['request_id']}/decisions",
            json=payload,
            headers=headers,
        )
        separated = client.post(
            f"/api/v1/approvals/{data['request_id']}/decisions",
            json=payload,
            headers={**headers, "X-CSRF-Token": login.headers["X-CSRF-Token"]},
        )

    assert login.status_code == 201
    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["code"] == "csrf_validation_failed"
    assert separated.status_code == 403
    assert separated.json()["code"] == "approval_separation_required"


@pytest.mark.asyncio
async def test_required_audit_failure_blocks_create_read_and_decision() -> None:
    sink = CollectingAuditSink()
    rca, recommendation, approval = build_services(sink)
    with TestClient(
        create_app(
            settings(),
            audit_sink=sink,
            rca_service=rca,
            recommendation_service=recommendation,
            approval_service=approval,
        )
    ) as client:
        data = create_approval(client)

    sink.fail_event = "atlas.approval.request.read"
    with pytest.raises(RuntimeError, match="approval audit unavailable"):
        await approval.get(str(data["request_id"]), context=access_context(data))

    sink.fail_event = "atlas.approval.decision.recorded"
    with pytest.raises(RuntimeError, match="approval audit unavailable"):
        await approval.decide(
            str(data["request_id"]),
            outcome=ApprovalOutcome.DEFER,
            rationale="The review is deferred until the named evidence is current.",
            expected_version=int(data["version"]),
            idempotency_key="approval-review-key-0004",
            context=access_context(data),
        )
    assert approval._records[str(data["request_id"])].state is ApprovalState.PENDING

    sink.fail_event = "atlas.approval.request.created"
    with TestClient(
        create_app(
            settings(),
            audit_sink=sink,
            rca_service=rca,
            recommendation_service=recommendation,
            approval_service=approval,
        ),
        raise_server_exceptions=False,
    ) as client:
        response = client.post(
            f"/api/v1/approvals/storage/{TARGET}",
            json={
                "recommendation_id": data["packet"]["recommendation_id"],
                "recommendation_version": data["packet"]["recommendation_version"],
                "option_id": data["packet"]["option_id"],
                "purpose": "This creation must fail when audit is unavailable.",
                "expires_in_minutes": 30,
            },
        )
    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
