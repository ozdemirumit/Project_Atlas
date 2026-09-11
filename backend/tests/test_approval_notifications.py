"""pass 38: real HTTP-level coverage for the approval inbox (`GET /approvals`) and the real,
durable, pull-based notification pipeline (`GET /notifications`,
`POST /notifications/{id}/read`) -- both new in this pass. Deliberately a separate file from
`test_approval_api.py`/`test_approval_stages.py` (left unmodified) so those two suites' existing,
already-tested behavior is provably unaffected by this pass's changes.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.capabilities import CapabilityClass
from atlas.core.config import Settings
from atlas.modules.authorization.application.bootstrap import (
    DEVELOPMENT_ROLE_ID,
    approval_scope,
    build_development_authorization_service,
    notification_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import RoleAssignment
from atlas.modules.identity.adapters.development import DevelopmentIdentityProvider
from atlas.modules.identity.application.composite import CompositeIdentityProvider
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationInput,
    AuthenticationMethod,
    SubjectKind,
)

TARGET = "asset.storage.lab.b28"
EPOCH = datetime.min.replace(tzinfo=UTC)


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "development_identity_enabled": True,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def reviewer_subject(*, subject_id: str = "subject.reviewer.example") -> AuthenticatedSubject:
    # AuthorizationService.evaluate() requires a matched RoleAssignment's role_id to also be
    # present in the presented subject's own `role_ids` claim (see
    # `atlas.modules.authorization.application.service.AuthorizationService.evaluate`) -- so a
    # distinct reviewer identity granted extra RoleAssignments against the real
    # `DEVELOPMENT_ROLE_ID` (below, in `build_combined_app_client`) must itself present that same
    # role id, the same way
    # `test_approval_api.py`'s `stage_reviewer()` presents the exact role its own bespoke
    # `RoleAssignment` grants.
    return AuthenticatedSubject(
        subject_id=subject_id,
        display_name="Independent Reviewer",
        kind=SubjectKind.HUMAN,
        provider_id="provider.reviewer.test",
        authentication_method=AuthenticationMethod.LDAP,
        assurance_level=AssuranceLevel.SINGLE_FACTOR,
        authenticated_at=datetime.now(UTC),
        organization_id="organization.development",
        role_ids=(DEVELOPMENT_ROLE_ID,),
    )


class ReviewerIdentityProvider:
    """Authenticates exactly one named reviewer over HTTP basic auth. Combined with the real
    `DevelopmentIdentityProvider` through `CompositeIdentityProvider` so a single app/TestClient
    genuinely serves both the header-less dev/requester identity AND a distinct, real reviewer
    identity -- necessary here (unlike `test_approval_api.py`'s per-reviewer separate `create_app`
    instances) because the notification pipeline requires both identities to reach the SAME
    `ApprovalService`/event bus/`NotificationService` for a real create -> subscribe -> notify ->
    read chain to be observable at all.
    """

    def __init__(self, reviewer: AuthenticatedSubject, *, password: str) -> None:
        self._reviewer = reviewer
        self._password = password

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
        if separator != ":" or username != self._reviewer.subject_id or password != self._password:
            return None
        return self._reviewer


def reviewer_authorization_header(reviewer: AuthenticatedSubject, password: str) -> dict[str, str]:
    token = base64.b64encode(f"{reviewer.subject_id}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def build_combined_app_client(
    sink: CollectingAuditSink,
    reviewer: AuthenticatedSubject,
    *,
    password: str = "correct-password",
    development_role_ids: tuple[str, ...] | None = None,
) -> TestClient:
    """One real app where the header-less request authenticates as the dev/requester identity
    and a `Basic` request authenticates as `reviewer` -- both wired through the same real
    `ApprovalService`/event bus/`AuthorizationService`/`NotificationService`, so an approval
    created by one and a decision made by the other genuinely exchange real domain events and
    real notifications through this one app."""
    app_settings = (
        settings(development_role_ids=development_role_ids)
        if development_role_ids is not None
        else settings()
    )
    base_authorization = build_development_authorization_service(app_settings, sink)
    combined_authorization = AuthorizationService(
        permissions=tuple(base_authorization._permissions.values()),
        roles=tuple(base_authorization._roles.values()),
        assignments=(
            *base_authorization._assignments,
            RoleAssignment(
                assignment_id="assignment.reviewer.approval-decide",
                version=1,
                subject_id=reviewer.subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=approval_scope(
                    reviewer.organization_id, "test", CapabilityClass.C2_DIAGNOSTIC
                ),
                valid_from=EPOCH,
            ),
            RoleAssignment(
                assignment_id="assignment.reviewer.notification-read",
                version=1,
                subject_id=reviewer.subject_id,
                role_id=DEVELOPMENT_ROLE_ID,
                scope=notification_scope(reviewer.organization_id, "test"),
                valid_from=EPOCH,
            ),
        ),
        audit_sink=sink,
    )
    identity_provider = CompositeIdentityProvider(
        (
            ReviewerIdentityProvider(reviewer, password=password),
            DevelopmentIdentityProvider(app_settings),
        )
    )
    app = create_app(
        app_settings,
        audit_sink=sink,
        identity_provider=identity_provider,
        authorization_service=combined_authorization,
    )
    return TestClient(app)


def rca_payload() -> dict[str, object]:
    now = datetime.now(UTC)
    return {
        "incident_id": "INC-NOTIFY-001",
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
    assert case_response.status_code == 200, case_response.text
    case = case_response.json()["data"]
    response = client.post(
        f"/api/v1/recommendations/storage/{TARGET}",
        json=recommendation_payload(case["case_id"], case["version"]),
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]  # type: ignore[no-any-return]


def create_approval(client: TestClient, **overrides: object) -> dict[str, Any]:
    recommendation = create_recommendation(client)
    payload: dict[str, object] = {
        "recommendation_id": recommendation["recommendation_id"],
        "recommendation_version": recommendation["version"],
        "option_id": recommendation["preferred_option_id"],
        "purpose": "Review the bounded read-only diagnostic plan.",
        "expires_in_minutes": 45,
    }
    payload.update(overrides)
    response = client.post(f"/api/v1/approvals/storage/{TARGET}", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["data"]  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Denial coverage: real 401 (no identity) and real 403 (authenticated, unauthorized).
# ---------------------------------------------------------------------------


def test_list_approvals_requires_authentication_and_permission() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        unauthenticated = client.get("/api/v1/approvals")
    with TestClient(
        create_app(settings(development_role_ids=()), audit_sink=CollectingAuditSink())
    ) as client:
        unauthorized = client.get("/api/v1/approvals")

    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["code"] == "authentication_required"
    assert unauthorized.status_code == 403
    assert unauthorized.json()["code"] == "authorization_denied"


def test_list_notifications_requires_authentication_and_permission() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        unauthenticated = client.get("/api/v1/notifications")
    with TestClient(
        create_app(settings(development_role_ids=()), audit_sink=CollectingAuditSink())
    ) as client:
        unauthorized = client.get("/api/v1/notifications")

    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["code"] == "authentication_required"
    assert unauthorized.status_code == 403
    assert unauthorized.json()["code"] == "authorization_denied"


def test_mark_notification_read_requires_authentication_and_permission() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        unauthenticated = client.post("/api/v1/notifications/notification_test/read")
    with TestClient(
        create_app(settings(development_role_ids=()), audit_sink=CollectingAuditSink())
    ) as client:
        unauthorized = client.post("/api/v1/notifications/notification_test/read")

    assert unauthenticated.status_code == 401
    assert unauthenticated.json()["code"] == "authentication_required"
    assert unauthorized.status_code == 403
    assert unauthorized.json()["code"] == "authorization_denied"


# ---------------------------------------------------------------------------
# End-to-end: create -> subscriber fires -> real eligible approver can read a real notification.
# ---------------------------------------------------------------------------


def test_creating_an_approval_notifies_the_real_eligible_approver() -> None:
    sink = CollectingAuditSink()
    reviewer = reviewer_subject()
    with build_combined_app_client(sink, reviewer) as client:
        data = create_approval(client)

        reviewer_notifications = client.get(
            "/api/v1/notifications",
            headers=reviewer_authorization_header(reviewer, "correct-password"),
        )
        assert reviewer_notifications.status_code == 200
        items = reviewer_notifications.json()["data"]["items"]
        matching = [item for item in items if item["reference_id"] == data["request_id"]]
        assert len(matching) == 1
        notification = matching[0]
        assert notification["notification_type"] == "notification.approval-request-created"
        assert notification["recipient_subject_id"] == reviewer.subject_id
        assert notification["read_at"] is None
        assert data["packet"]["option_title"] in notification["summary"]
        assert "credential" not in reviewer_notifications.text.lower()


def test_full_grant_notifies_the_real_requester() -> None:
    sink = CollectingAuditSink()
    reviewer = reviewer_subject()
    with build_combined_app_client(sink, reviewer) as client:
        data = create_approval(client)
        decide_response = client.post(
            f"/api/v1/approvals/{data['request_id']}/decisions",
            json={
                "outcome": "approve",
                "rationale": "The evidence supports this bounded read-only diagnostic plan.",
                "expected_version": data["version"],
            },
            headers={
                "Idempotency-Key": "approval-notify-decide-key-01",
                **reviewer_authorization_header(reviewer, "correct-password"),
            },
        )
        assert decide_response.status_code == 200, decide_response.text
        assert decide_response.json()["data"]["state"] == "approved"

        requester_notifications = client.get("/api/v1/notifications")
        assert requester_notifications.status_code == 200
        items = requester_notifications.json()["data"]["items"]
        granted = [
            item
            for item in items
            if item["reference_id"] == data["request_id"]
            and item["notification_type"] == "notification.approval-granted"
        ]
        assert len(granted) == 1
        assert granted[0]["recipient_subject_id"] == data["packet"]["requested_by"]


def test_mark_read_is_idempotent_and_subject_isolated() -> None:
    sink = CollectingAuditSink()
    reviewer = reviewer_subject()
    with build_combined_app_client(sink, reviewer) as client:
        data = create_approval(client)
        reviewer_headers = reviewer_authorization_header(reviewer, "correct-password")

        listed = client.get("/api/v1/notifications", headers=reviewer_headers)
        notification_id = next(
            item["notification_id"]
            for item in listed.json()["data"]["items"]
            if item["reference_id"] == data["request_id"]
        )

        # A different subject (the header-less dev/requester identity) cannot read or mark read
        # a notification addressed to the reviewer -- indistinguishable from not existing.
        foreign_get = client.get("/api/v1/notifications", headers={})
        foreign_ids = {item["notification_id"] for item in foreign_get.json()["data"]["items"]}
        assert notification_id not in foreign_ids
        foreign_mark = client.post(f"/api/v1/notifications/{notification_id}/read")
        assert foreign_mark.status_code == 404
        assert foreign_mark.json()["code"] == "notification_not_found"

        first = client.post(
            f"/api/v1/notifications/{notification_id}/read", headers=reviewer_headers
        )
        assert first.status_code == 200
        first_read_at = first.json()["data"]["read_at"]
        assert first_read_at is not None

        second = client.post(
            f"/api/v1/notifications/{notification_id}/read", headers=reviewer_headers
        )
        assert second.status_code == 200
        assert second.json()["data"]["read_at"] == first_read_at


# ---------------------------------------------------------------------------
# GET /approvals: real filtering and pagination.
# ---------------------------------------------------------------------------


def test_list_approvals_filters_by_state_owner_and_expiry() -> None:
    sink = CollectingAuditSink()
    with TestClient(create_app(settings(), audit_sink=sink)) as client:
        data = create_approval(client)

        by_state = client.get("/api/v1/approvals", params={"state": "pending"})
        assert by_state.status_code == 200
        assert any(
            item["request_id"] == data["request_id"] for item in by_state.json()["data"]["items"]
        )

        wrong_state = client.get("/api/v1/approvals", params={"state": "approved"})
        assert wrong_state.status_code == 200
        assert not any(
            item["request_id"] == data["request_id"] for item in wrong_state.json()["data"]["items"]
        )

        own_owner = client.get(
            "/api/v1/approvals", params={"owner_subject_id": data["packet"]["requested_by"]}
        )
        assert own_owner.status_code == 200
        assert any(
            item["request_id"] == data["request_id"] for item in own_owner.json()["data"]["items"]
        )

        other_owner = client.get(
            "/api/v1/approvals", params={"owner_subject_id": "subject.someone-else"}
        )
        assert other_owner.status_code == 403
        assert other_owner.json()["code"] == "approval_list_owner_forbidden"

        expiring_soon = client.get(
            "/api/v1/approvals",
            params={"expiring_before": (datetime.now(UTC) + timedelta(minutes=1)).isoformat()},
        )
        assert expiring_soon.status_code == 200
        assert not any(
            item["request_id"] == data["request_id"]
            for item in expiring_soon.json()["data"]["items"]
        )

        expiring_later = client.get(
            "/api/v1/approvals",
            params={"expiring_before": (datetime.now(UTC) + timedelta(hours=1)).isoformat()},
        )
        assert expiring_later.status_code == 200
        assert any(
            item["request_id"] == data["request_id"]
            for item in expiring_later.json()["data"]["items"]
        )


def test_list_approvals_role_filter_excludes_non_staged_records() -> None:
    sink = CollectingAuditSink()
    with TestClient(create_app(settings(), audit_sink=sink)) as client:
        create_approval(client)
        by_role = client.get("/api/v1/approvals", params={"role_id": "role.development.operator"})
        assert by_role.status_code == 200
        # A non-staged request has no discrete required role, so a role_id filter -- even one the
        # caller genuinely holds -- excludes it (see ApprovalService.list()/_matches_scope_reference
        # and list()'s own role_id branch).
        assert by_role.json()["data"]["items"] == []

        forbidden_role = client.get("/api/v1/approvals", params={"role_id": "role.not-mine"})
        assert forbidden_role.status_code == 403
        assert forbidden_role.json()["code"] == "approval_list_role_forbidden"


def test_list_approvals_paginates_with_a_cursor() -> None:
    sink = CollectingAuditSink()
    with TestClient(create_app(settings(), audit_sink=sink)) as client:
        first = create_approval(client)
        second = create_approval(client)

        page_one = client.get("/api/v1/approvals", params={"limit": 1})
        assert page_one.status_code == 200
        page_one_body = page_one.json()["data"]
        assert len(page_one_body["items"]) == 1
        assert page_one_body["next_cursor"] is not None

        page_two = client.get(
            "/api/v1/approvals",
            params={"limit": 1, "cursor": page_one_body["next_cursor"]},
        )
        assert page_two.status_code == 200
        page_two_body = page_two.json()["data"]
        assert len(page_two_body["items"]) == 1

        seen_ids = {
            page_one_body["items"][0]["request_id"],
            page_two_body["items"][0]["request_id"],
        }
        assert seen_ids == {first["request_id"], second["request_id"]}

        bad_cursor = client.get("/api/v1/approvals", params={"cursor": "not-a-real-cursor"})
        assert bad_cursor.status_code == 422
        assert bad_cursor.json()["code"] == "approval_list_cursor_invalid"


# ---------------------------------------------------------------------------
# Regression: the pre-existing approval suites are unaffected by this pass's service changes.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_existing_approval_suites_still_pass() -> None:
    """A cheap in-process smoke check (the real, full regression run is
    `test_approval_api.py`/`test_approval_stages.py` themselves, run standalone in CI) -- proves
    `create()`/`decide()` still return the exact same real record shape when no subscriber is
    registered on their own private event bus (the two suites' own `build_services()` never wires
    a notification subscriber)."""
    from atlas.modules.approvals.application.service import ApprovalService
    from atlas.modules.rca.adapters.synthetic import SyntheticStorageRcaAssembler
    from atlas.modules.rca.application.service import RcaService
    from atlas.modules.recommendations.adapters.synthetic import (
        SyntheticStorageRecommendationAssembler,
    )
    from atlas.modules.recommendations.application.service import RecommendationService

    sink = CollectingAuditSink()
    rca = RcaService(assembler=SyntheticStorageRcaAssembler(), audit_sink=sink)
    recommendation = RecommendationService(
        source_provider=rca,
        assembler=SyntheticStorageRecommendationAssembler(),
        audit_sink=sink,
    )
    approval = ApprovalService(recommendation_provider=recommendation, audit_sink=sink)
    assert approval._event_bus.published == []
    assert hasattr(approval, "list")
    assert hasattr(approval, "get_record_unchecked")
    assert await approval.get_record_unchecked("approval_does_not_exist") is None
