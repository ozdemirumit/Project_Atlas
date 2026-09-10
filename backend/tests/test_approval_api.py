from __future__ import annotations

import base64
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.capabilities import CapabilityClass
from atlas.core.config import Settings
from atlas.core.event_catalog import (
    AIRecommendationGenerated,
    ApprovalGranted,
    ApprovalRequestCreated,
)
from atlas.core.events import InMemoryDomainEventBus
from atlas.modules.approvals.application.service import (
    ApprovalAccessContext,
    ApprovalOperationsError,
    ApprovalService,
)
from atlas.modules.approvals.domain.models import ApprovalOutcome, ApprovalState
from atlas.modules.authorization.application.bootstrap import (
    APPROVAL_REQUEST_DECIDE,
    approval_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import (
    PermissionDefinition,
    RoleAssignment,
    RoleDefinition,
)
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
async def test_development_separate_human_can_approve_without_execution_authority() -> None:
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
        context=access_context(data, assurance_level="development"),
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
        ({"assurance_level": "unknown"}, "approval_assurance_insufficient"),
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


@pytest.mark.asyncio
async def test_requester_can_cancel_a_pending_request() -> None:
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

    updated = await approval.cancel(
        str(data["request_id"]),
        rationale="The requester no longer needs this reviewed.",
        expected_version=int(data["version"]),
        idempotency_key="approval-cancel-key-0001",
        context=access_context(data, subject_id="subject.development.operator"),
    )

    assert updated.state is ApprovalState.CANCELLED
    assert updated.decisions[0].outcome is ApprovalOutcome.CANCEL
    assert updated.decisions[0].reviewer_id == "subject.development.operator"
    assert sink.records[-1].result_code == "approval_cancelled"


@pytest.mark.asyncio
async def test_non_requester_cannot_cancel() -> None:
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

    with pytest.raises(ApprovalOperationsError) as raised:
        await approval.cancel(
            str(data["request_id"]),
            rationale="Someone other than the requester tries to cancel.",
            expected_version=int(data["version"]),
            idempotency_key="approval-cancel-key-0002",
            context=access_context(data),
        )

    assert raised.value.code == "approval_cancel_not_requester"


@pytest.mark.asyncio
async def test_cancel_requires_a_rationale() -> None:
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

    with pytest.raises(ApprovalOperationsError) as raised:
        await approval.cancel(
            str(data["request_id"]),
            rationale="   ",
            expected_version=int(data["version"]),
            idempotency_key="approval-cancel-key-0003",
            context=access_context(data, subject_id="subject.development.operator"),
        )

    assert raised.value.code == "approval_rationale_required"


@pytest.mark.asyncio
async def test_cancel_is_idempotent_and_a_decided_request_cannot_be_cancelled() -> None:
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
    context = access_context(data, subject_id="subject.development.operator")

    first = await approval.cancel(
        str(data["request_id"]),
        rationale="Withdrawing this request.",
        expected_version=int(data["version"]),
        idempotency_key="approval-cancel-key-0004",
        context=context,
    )
    replay = await approval.cancel(
        str(data["request_id"]),
        rationale="Withdrawing this request.",
        expected_version=int(data["version"]),
        idempotency_key="approval-cancel-key-0004",
        context=context,
    )
    assert replay == first

    with pytest.raises(ApprovalOperationsError) as stale:
        await approval.cancel(
            str(data["request_id"]),
            rationale="A second, distinct cancellation attempt.",
            expected_version=int(data["version"]),
            idempotency_key="approval-cancel-key-0005",
            context=context,
        )
    assert stale.value.code == "approval_state_conflict"


@pytest.mark.asyncio
async def test_governance_identity_can_revoke_an_approved_request() -> None:
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
    approved = await approval.decide(
        str(data["request_id"]),
        outcome=ApprovalOutcome.APPROVE,
        rationale="The evidence supports this bounded read-only diagnostic plan.",
        expected_version=int(data["version"]),
        idempotency_key="approval-revoke-decide-key-0001",
        context=access_context(data),
    )

    revoked = await approval.revoke(
        str(data["request_id"]),
        rationale="New information invalidates this approval before handoff.",
        expected_version=approved.version,
        idempotency_key="approval-revoke-key-0001",
        context=access_context(data),
    )

    assert revoked.state is ApprovalState.REVOKED
    assert revoked.decisions[-1].outcome is ApprovalOutcome.REVOKE
    assert sink.records[-1].result_code == "approval_revoked"


@pytest.mark.asyncio
async def test_requester_cannot_revoke_their_own_approval() -> None:
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
    approved = await approval.decide(
        str(data["request_id"]),
        outcome=ApprovalOutcome.APPROVE,
        rationale="The evidence supports this bounded read-only diagnostic plan.",
        expected_version=int(data["version"]),
        idempotency_key="approval-revoke-decide-key-0002",
        context=access_context(data),
    )

    with pytest.raises(ApprovalOperationsError) as raised:
        await approval.revoke(
            str(data["request_id"]),
            rationale="The requester tries to revoke their own approved request.",
            expected_version=approved.version,
            idempotency_key="approval-revoke-key-0002",
            context=access_context(data, subject_id="subject.development.operator"),
        )

    assert raised.value.code == "approval_separation_required"


@pytest.mark.asyncio
async def test_decide_rejects_cancel_and_revoke_outcomes() -> None:
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

    for outcome in (ApprovalOutcome.CANCEL, ApprovalOutcome.REVOKE):
        with pytest.raises(ApprovalOperationsError) as raised:
            await approval.decide(
                str(data["request_id"]),
                outcome=outcome,
                rationale="decide() should reject this outcome.",
                expected_version=int(data["version"]),
                idempotency_key=f"approval-wrong-op-{outcome.value}",
                context=access_context(data),
            )
        assert raised.value.code == "approval_wrong_operation"


def test_cancel_endpoint_is_reachable_over_http() -> None:
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
        response = client.post(
            f"/api/v1/approvals/{data['request_id']}/cancel",
            json={
                "rationale": "Withdrawing via the HTTP API.",
                "expected_version": data["version"],
            },
            headers={"Idempotency-Key": "approval-cancel-http-key-0001"},
        )

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["data"]["state"] == "cancelled"


@pytest.mark.asyncio
async def test_creation_publishes_recommendation_and_approval_created_events() -> None:
    sink = CollectingAuditSink()
    bus = InMemoryDomainEventBus()
    rca = RcaService(assembler=SyntheticStorageRcaAssembler(), audit_sink=sink)
    recommendation = RecommendationService(
        source_provider=rca,
        assembler=SyntheticStorageRecommendationAssembler(),
        audit_sink=sink,
        event_bus=bus,
    )
    approval = ApprovalService(
        recommendation_provider=recommendation, audit_sink=sink, event_bus=bus
    )
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

    assert [envelope.event_type for envelope in bus.published] == [
        "AIRecommendationGenerated",
        "ApprovalRequestCreated",
    ]
    generated, created = bus.published
    assert isinstance(generated.payload, AIRecommendationGenerated)
    assert generated.payload.recommendation_id == data["packet"]["recommendation_id"]
    assert generated.payload.option_count >= 1
    assert created.event_type == "ApprovalRequestCreated"
    assert created.subject_id == data["request_id"]
    assert isinstance(created.payload, ApprovalRequestCreated)
    assert created.payload.request_id == data["request_id"]
    assert created.payload.requested_by == "subject.development.operator"


@pytest.mark.asyncio
async def test_approval_publishes_approval_granted_event_but_rejection_does_not() -> None:
    sink = CollectingAuditSink()
    bus = InMemoryDomainEventBus()
    rca = RcaService(assembler=SyntheticStorageRcaAssembler(), audit_sink=sink)
    recommendation = RecommendationService(
        source_provider=rca,
        assembler=SyntheticStorageRecommendationAssembler(),
        audit_sink=sink,
    )
    approval = ApprovalService(
        recommendation_provider=recommendation, audit_sink=sink, event_bus=bus
    )
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

    granted = await approval.decide(
        str(data["request_id"]),
        outcome=ApprovalOutcome.APPROVE,
        rationale="The evidence supports this bounded read-only diagnostic plan.",
        expected_version=int(data["version"]),
        idempotency_key="approval-event-key-0001",
        context=access_context(data),
    )

    assert granted.state is ApprovalState.APPROVED
    granted_events = [event for event in bus.published if event.event_type == "ApprovalGranted"]
    assert len(granted_events) == 1
    assert isinstance(granted_events[0].payload, ApprovalGranted)
    assert granted_events[0].payload.request_id == data["request_id"]
    assert granted_events[0].payload.reviewer_id == "subject.enterprise.reviewer"

    # A second, separate request that is rejected must never publish ApprovalGranted.
    with TestClient(
        create_app(
            settings(),
            audit_sink=sink,
            rca_service=rca,
            recommendation_service=recommendation,
            approval_service=approval,
        )
    ) as client:
        second_data = create_approval(client)
    await approval.decide(
        str(second_data["request_id"]),
        outcome=ApprovalOutcome.REJECT,
        rationale="This bounded read-only diagnostic plan is not needed.",
        expected_version=int(second_data["version"]),
        idempotency_key="approval-event-key-0002",
        context=access_context(second_data),
    )
    granted_events_after_rejection = [
        event for event in bus.published if event.event_type == "ApprovalGranted"
    ]
    assert len(granted_events_after_rejection) == 1


class GovernanceApprovalIdentityProvider:
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
        return subject(subject_id="subject.approval-governance-reviewer")


def test_revoke_endpoint_is_reachable_over_http() -> None:
    """``POST /approvals/{request_id}/revoke`` had zero HTTP coverage --
    ``test_governance_identity_can_revoke_an_approved_request`` and
    ``test_requester_cannot_revoke_their_own_approval`` above exercise ``ApprovalService.revoke``
    only through a direct ``await approval.revoke(...)`` service call, never through the actual
    route, even though the sibling ``/decisions`` endpoint is HTTP-tested right next to it
    (``test_cookie_decision_requires_csrf_then_enforces_separation``) and the sibling ``/cancel``
    endpoint has its own dedicated HTTP test (``test_cancel_endpoint_is_reachable_over_http``
    above). This drives a decision and a revocation through the real HTTP API using a governance
    identity distinct from the implicit default requester identity, and confirms both that the
    requester cannot revoke their own approval and that an already-revoked request cannot be
    revoked again -- both real ``ApprovalService.revoke`` rules, exercised here over HTTP.
    """
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

        self_revoke_denied = client.post(
            f"/api/v1/approvals/{data['request_id']}/revoke",
            json={
                "rationale": "The original requester tries to revoke via the HTTP API.",
                "expected_version": data["version"],
            },
            headers={"Idempotency-Key": "approval-revoke-http-self-0001"},
        )
    assert self_revoke_denied.status_code == 403, self_revoke_denied.text
    assert self_revoke_denied.json()["code"] == "approval_separation_required"

    with TestClient(
        create_app(
            settings(development_subject_id="subject.approval-governance-reviewer"),
            audit_sink=sink,
            identity_provider=GovernanceApprovalIdentityProvider(),
            rca_service=rca,
            recommendation_service=recommendation,
            approval_service=approval,
        )
    ) as client:
        login_response = client.post(
            "/api/v1/authentication/sessions",
            json={"username": "operator", "password": "correct-password"},
        )
        assert login_response.status_code == 201
        csrf = login_response.headers["X-CSRF-Token"]

        decided = client.post(
            f"/api/v1/approvals/{data['request_id']}/decisions",
            json={
                "outcome": "approve",
                "rationale": "The evidence supports this bounded read-only diagnostic plan.",
                "expected_version": data["version"],
            },
            headers={
                "Idempotency-Key": "approval-revoke-http-decide-0001",
                "X-CSRF-Token": csrf,
            },
        )
        assert decided.status_code == 200, decided.text
        approved = decided.json()["data"]
        assert approved["state"] == "approved"

        revoked = client.post(
            f"/api/v1/approvals/{data['request_id']}/revoke",
            json={
                "rationale": "New information invalidates this approval before handoff.",
                "expected_version": approved["version"],
            },
            headers={"Idempotency-Key": "approval-revoke-http-0001", "X-CSRF-Token": csrf},
        )
        assert revoked.status_code == 200, revoked.text
        assert revoked.headers["Cache-Control"] == "no-store"
        revoked_data = revoked.json()["data"]
        assert revoked_data["state"] == "revoked"
        assert revoked_data["decisions"][-1]["outcome"] == "revoke"
        assert (
            revoked_data["decisions"][-1]["reviewer_id"] == "subject.approval-governance-reviewer"
        )

        already_revoked = client.post(
            f"/api/v1/approvals/{data['request_id']}/revoke",
            json={
                "rationale": "A second, distinct revocation attempt after the first succeeded.",
                "expected_version": approved["version"],
            },
            headers={"Idempotency-Key": "approval-revoke-http-0002", "X-CSRF-Token": csrf},
        )

    assert already_revoked.status_code == 409, already_revoked.text
    assert already_revoked.json()["code"] == "approval_state_conflict"


# --- Pass 27: multi-stage approval and ITSM external-approval binding wiring ----------------
#
# docs/037_Approval_Workflow.md's MVP-included scope lists "single and multi-stage human
# approval states" and "ITSM change and window references" as included. The multi-stage
# evaluator (`approvals/domain/stages.py`) and the ITSM approval-sync binding
# (`itsm/domain/approval_sync.py`) were both real, independently tested domain code with zero
# callers anywhere outside their own tests -- `ApprovalService` only ever did single-stage
# approval, and no approval request could reference an external ITSM authority. Per the user's
# explicit decision (pass 27 of this session's standing audit loop), both are now wired into the
# real, live `ApprovalService`/`/api/v1/approvals` routes. These tests drive that wiring through
# real HTTP calls, proving the staged decision flow and the ITSM binding are genuinely reachable
# -- not just that the underlying domain functions work in isolation (that coverage already
# existed and is unchanged).


class MultiRoleIdentityProvider:
    """Authenticates any of several named reviewers, each with their own role_ids -- used to
    prove a multi-stage plan's per-stage role requirement is enforced by the real identity
    presented over HTTP, not by test-only bookkeeping."""

    def __init__(self, subjects: dict[str, AuthenticatedSubject]) -> None:
        self._subjects = subjects

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
        username, separator, password = decoded.partition(":")
        if separator != ":" or password != "correct-password":
            return None
        return self._subjects.get(username)


def stage_reviewer(username: str, role_id: str) -> AuthenticatedSubject:
    return replace(
        subject(subject_id=f"subject.stage-reviewer.{username}"),
        role_ids=(role_id,),
    )


def _reviewer_authorization(reviewer: AuthenticatedSubject, role_id: str) -> AuthorizationService:
    """The real `authorize_approval_decide` route dependency is a separate RBAC permission
    check the stage-role check in `ApprovalService.decide()` sits *behind*, not in place of --
    the standard dev `RoleAssignment` is bound to one fixed subject_id, so a distinct stage
    reviewer identity needs its own real `AuthorizationService` grant, the same pattern already
    used by this session's `test_recommendation_protected_content.py`/
    `test_recommendation_protected_inspection.py`. Only `APPROVAL_REQUEST_DECIDE` is needed --
    these reviewers only ever call `POST /decisions` through their own client."""
    return AuthorizationService(
        permissions=(
            PermissionDefinition(
                permission_id=APPROVAL_REQUEST_DECIDE, description=APPROVAL_REQUEST_DECIDE
            ),
        ),
        roles=(
            RoleDefinition(
                role_id=role_id, version=1, permissions=frozenset({APPROVAL_REQUEST_DECIDE})
            ),
        ),
        assignments=(
            RoleAssignment(
                assignment_id="assignment.stage-reviewer-decide",
                version=1,
                subject_id=reviewer.subject_id,
                role_id=role_id,
                scope=approval_scope(
                    reviewer.organization_id, "test", CapabilityClass.C2_DIAGNOSTIC
                ),
                valid_from=datetime.min.replace(tzinfo=UTC),
            ),
        ),
        audit_sink=CollectingAuditSink(),
    )


def two_stage_requirements() -> list[dict[str, object]]:
    return [
        {
            "stage_id": "stage.technical-review",
            "required_role": "role.stage.technical-reviewer",
            "required_scope_reference": "resource.approval.storage.synthetic",
            "sequence": 1,
            "quorum": 1,
            "expiry_minutes": 60,
        },
        {
            "stage_id": "stage.governance-review",
            "required_role": "role.stage.governance-reviewer",
            "required_scope_reference": "resource.approval.storage.synthetic",
            "sequence": 2,
            "quorum": 1,
            "expiry_minutes": 60,
        },
    ]


def create_staged_approval(
    client: TestClient, stage_requirements: list[dict[str, object]]
) -> dict[str, Any]:
    recommendation = create_recommendation(client)
    response = client.post(
        f"/api/v1/approvals/storage/{TARGET}",
        json={
            "recommendation_id": recommendation["recommendation_id"],
            "recommendation_version": recommendation["version"],
            "option_id": recommendation["preferred_option_id"],
            "purpose": "Review the bounded read-only diagnostic plan through a staged process.",
            "expires_in_minutes": 45,
            "stage_requirements": stage_requirements,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]  # type: ignore[no-any-return]


def _reviewer_client(
    sink: CollectingAuditSink,
    rca: RcaService,
    recommendation: RecommendationService,
    approval: ApprovalService,
    reviewer: AuthenticatedSubject,
) -> TestClient:
    """A client authenticated as one specific stage reviewer -- creation of the underlying
    recommendation/approval must NOT go through this client, since `MultiRoleIdentityProvider`
    (unlike the default dev-identity provider) requires real basic-auth credentials on every
    request and has no credential-less fallback."""
    return TestClient(
        create_app(
            settings(),
            audit_sink=sink,
            identity_provider=MultiRoleIdentityProvider({"reviewer": reviewer}),
            authorization_service=_reviewer_authorization(reviewer, reviewer.role_ids[0]),
            rca_service=rca,
            recommendation_service=recommendation,
            approval_service=approval,
        )
    )


def _login_as_reviewer(client: TestClient) -> str:
    response = client.post(
        "/api/v1/authentication/sessions",
        json={"username": "reviewer", "password": "correct-password"},
    )
    assert response.status_code == 201, response.text
    return str(response.headers["X-CSRF-Token"])


def test_two_stage_sequential_approval_reaches_approved_only_after_both_stages() -> None:
    sink = CollectingAuditSink()
    rca, recommendation, approval = build_services(sink)
    technical = stage_reviewer("technical", "role.stage.technical-reviewer")
    governance = stage_reviewer("governance", "role.stage.governance-reviewer")

    with TestClient(
        create_app(
            settings(),
            audit_sink=sink,
            rca_service=rca,
            recommendation_service=recommendation,
            approval_service=approval,
        )
    ) as client:
        data = create_staged_approval(client, two_stage_requirements())
    assert data["stage_plan"]["stages"][0]["stage_id"] == "stage.technical-review"
    assert data["stage_decisions"] == []

    with _reviewer_client(sink, rca, recommendation, approval, technical) as client:
        csrf = _login_as_reviewer(client)
        first = client.post(
            f"/api/v1/approvals/{data['request_id']}/decisions",
            json={
                "outcome": "approve",
                "rationale": "The technical review confirms this bounded plan is sound.",
                "expected_version": data["version"],
                "stage_id": "stage.technical-review",
            },
            headers={"Idempotency-Key": "approval-stage-decide-0001", "X-CSRF-Token": csrf},
        )
    assert first.status_code == 200, first.text
    after_first = first.json()["data"]
    assert after_first["state"] == "partially_approved"
    assert len(after_first["stage_decisions"]) == 1
    assert after_first["stage_decisions"][0]["stage_id"] == "stage.technical-review"

    with _reviewer_client(sink, rca, recommendation, approval, governance) as client:
        csrf = _login_as_reviewer(client)
        second = client.post(
            f"/api/v1/approvals/{data['request_id']}/decisions",
            json={
                "outcome": "approve",
                "rationale": "Governance review confirms this bounded plan may proceed.",
                "expected_version": after_first["version"],
                "stage_id": "stage.governance-review",
            },
            headers={"Idempotency-Key": "approval-stage-decide-0002", "X-CSRF-Token": csrf},
        )
    assert second.status_code == 200, second.text
    after_second = second.json()["data"]
    assert after_second["state"] == "approved"
    assert len(after_second["stage_decisions"]) == 2


def test_rejection_at_a_reached_stage_stops_the_whole_plan() -> None:
    sink = CollectingAuditSink()
    rca, recommendation, approval = build_services(sink)
    technical = stage_reviewer("technical", "role.stage.technical-reviewer")

    with TestClient(
        create_app(
            settings(),
            audit_sink=sink,
            rca_service=rca,
            recommendation_service=recommendation,
            approval_service=approval,
        )
    ) as client:
        data = create_staged_approval(client, two_stage_requirements())

    with _reviewer_client(sink, rca, recommendation, approval, technical) as client:
        csrf = _login_as_reviewer(client)
        response = client.post(
            f"/api/v1/approvals/{data['request_id']}/decisions",
            json={
                "outcome": "reject",
                "rationale": "The technical review finds this bounded plan unsafe.",
                "expected_version": data["version"],
                "stage_id": "stage.technical-review",
            },
            headers={"Idempotency-Key": "approval-stage-reject-0001", "X-CSRF-Token": csrf},
        )

    assert response.status_code == 200, response.text
    assert response.json()["data"]["state"] == "rejected"


def test_stage_role_mismatch_is_denied_by_the_real_authorization_service() -> None:
    sink = CollectingAuditSink()
    rca, recommendation, approval = build_services(sink)
    wrong_role_reviewer = stage_reviewer("outsider", "role.stage.governance-reviewer")

    with TestClient(
        create_app(
            settings(),
            audit_sink=sink,
            rca_service=rca,
            recommendation_service=recommendation,
            approval_service=approval,
        )
    ) as client:
        data = create_staged_approval(client, two_stage_requirements())

    with _reviewer_client(sink, rca, recommendation, approval, wrong_role_reviewer) as client:
        csrf = _login_as_reviewer(client)
        response = client.post(
            f"/api/v1/approvals/{data['request_id']}/decisions",
            json={
                "outcome": "approve",
                "rationale": "An identity without the technical-reviewer role attempts this.",
                "expected_version": data["version"],
                "stage_id": "stage.technical-review",
            },
            headers={"Idempotency-Key": "approval-stage-wrong-role-0001", "X-CSRF-Token": csrf},
        )

    assert response.status_code == 403, response.text
    assert response.json()["code"] == "approval_stage_role_mismatch"


def test_missing_or_unknown_stage_id_is_rejected() -> None:
    sink = CollectingAuditSink()
    rca, recommendation, approval = build_services(sink)
    technical = stage_reviewer("technical", "role.stage.technical-reviewer")

    with TestClient(
        create_app(
            settings(),
            audit_sink=sink,
            rca_service=rca,
            recommendation_service=recommendation,
            approval_service=approval,
        )
    ) as client:
        data = create_staged_approval(client, two_stage_requirements())

    with _reviewer_client(sink, rca, recommendation, approval, technical) as client:
        csrf = _login_as_reviewer(client)
        missing = client.post(
            f"/api/v1/approvals/{data['request_id']}/decisions",
            json={
                "outcome": "approve",
                "rationale": "No stage_id is supplied for a staged request.",
                "expected_version": data["version"],
            },
            headers={"Idempotency-Key": "approval-stage-missing-0001", "X-CSRF-Token": csrf},
        )
        unknown = client.post(
            f"/api/v1/approvals/{data['request_id']}/decisions",
            json={
                "outcome": "approve",
                "rationale": "An unknown stage_id is supplied.",
                "expected_version": data["version"],
                "stage_id": "stage.does-not-exist",
            },
            headers={"Idempotency-Key": "approval-stage-unknown-0001", "X-CSRF-Token": csrf},
        )

    assert missing.status_code == 422, missing.text
    assert missing.json()["code"] == "approval_stage_required"
    assert unknown.status_code == 422, unknown.text
    assert unknown.json()["code"] == "approval_stage_unknown"


def test_needs_evidence_and_defer_are_rejected_on_a_staged_request() -> None:
    sink = CollectingAuditSink()
    rca, recommendation, approval = build_services(sink)
    technical = stage_reviewer("technical", "role.stage.technical-reviewer")

    with TestClient(
        create_app(
            settings(),
            audit_sink=sink,
            rca_service=rca,
            recommendation_service=recommendation,
            approval_service=approval,
        )
    ) as client:
        data = create_staged_approval(client, two_stage_requirements())

    with _reviewer_client(sink, rca, recommendation, approval, technical) as client:
        csrf = _login_as_reviewer(client)
        for outcome in ("needs_evidence", "defer"):
            response = client.post(
                f"/api/v1/approvals/{data['request_id']}/decisions",
                json={
                    "outcome": outcome,
                    "rationale": "Staged requests do not model this outcome at a stage.",
                    "expected_version": data["version"],
                    "stage_id": "stage.technical-review",
                },
                headers={
                    "Idempotency-Key": f"approval-stage-{outcome}-0001",
                    "X-CSRF-Token": csrf,
                },
            )
            assert response.status_code == 422, response.text
            assert response.json()["code"] == "approval_wrong_operation"


def test_itsm_binding_attaches_to_a_pending_request_and_is_visible_on_read() -> None:
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
        attached = client.post(
            f"/api/v1/approvals/{data['request_id']}/itsm-binding",
            json={
                "binding_id": "binding.itsm-change-0001",
                "profile_id": "profile.itsm-change-default",
                "external_approval_record_id": "change.CHG0012345",
                "external_record_version": "version.3",
                "eligible_approver_reference": "subject.itsm.change-manager",
                "approving_subject_reference": "subject.itsm.change-manager",
                "exact_plan_reference": data["request_id"],
                "exact_plan_version": "version.1",
            },
            headers={"Idempotency-Key": "approval-itsm-binding-0001"},
        )
        assert attached.status_code == 200, attached.text
        binding = attached.json()["data"]["itsm_binding"]
        assert binding is not None
        assert binding["binding_id"] == "binding.itsm-change-0001"
        assert binding["atlas_approval_reference"] == data["request_id"]

        read = client.get(f"/api/v1/approvals/{data['request_id']}")

    assert read.status_code == 200
    assert read.json()["data"]["itsm_binding"]["binding_id"] == "binding.itsm-change-0001"


def test_itsm_binding_with_mismatched_plan_reference_is_rejected() -> None:
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
        mismatched = client.post(
            f"/api/v1/approvals/{data['request_id']}/itsm-binding",
            json={
                "binding_id": "binding.itsm-change-0002",
                "profile_id": "profile.itsm-change-default",
                "external_approval_record_id": "change.CHG0012346",
                "external_record_version": "version.1",
                "eligible_approver_reference": "subject.itsm.change-manager",
                "approving_subject_reference": "subject.itsm.change-manager",
                "exact_plan_reference": "approval_some-other-request",
                "exact_plan_version": "version.1",
            },
            headers={"Idempotency-Key": "approval-itsm-binding-0002"},
        )

    assert mismatched.status_code == 422, mismatched.text
    assert mismatched.json()["code"] == "approval_itsm_binding_mismatch"
