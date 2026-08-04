from __future__ import annotations

import asyncio
import base64
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.capabilities import CapabilityClass
from atlas.core.config import Settings
from atlas.modules.authorization.application.bootstrap import (
    SECURITY_ADMINISTRATOR_ROLE_ID,
    STORAGE_OVERVIEW_READ,
    identity_governance_permission_definitions,
    identity_governance_scope,
    personal_api_grant_catalog,
    security_administrator_role_definition,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import RoleAssignment
from atlas.modules.identity.adapters.api_credentials import InMemoryApiCredentialRepository
from atlas.modules.identity.adapters.sessions import InMemorySessionRepository
from atlas.modules.identity.application.api_credentials import ApiCredentialService
from atlas.modules.identity.application.governance import (
    IdentityGovernanceError,
    IdentityGovernanceService,
)
from atlas.modules.identity.application.service import IdentityService
from atlas.modules.identity.application.sessions import SessionService
from atlas.modules.identity.domain.api_credentials import (
    ApiCredentialState,
    IssuedApiCredential,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationInput,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.identity.domain.sessions import IssuedSession, SessionState

NOW = datetime(2026, 8, 4, 15, 0, tzinfo=UTC)
ORGANIZATION_ID = "organization.enterprise"
ADMIN_TOKEN_KEY = "admin-revoke-token-0001"
ADMIN_SESSION_KEY = "admin-revoke-session-0001"


class CollectingAuditSink:
    def __init__(self, failing_events: set[str] | None = None) -> None:
        self.records: list[AuditRecord] = []
        self._failing_events = failing_events or set()

    async def record(self, event: AuditRecord) -> None:
        if event.event_type in self._failing_events:
            raise RuntimeError("identity governance audit unavailable")
        self.records.append(event)


class MultiUserIdentityProvider:
    def __init__(self, subjects: dict[str, AuthenticatedSubject]) -> None:
        self._subjects = subjects

    async def authenticate(
        self, authentication_input: AuthenticationInput
    ) -> AuthenticatedSubject | None:
        if (
            authentication_input.authorization_scheme != "basic"
            or authentication_input.credential is None
        ):
            return None
        try:
            decoded = base64.b64decode(authentication_input.credential, validate=True).decode()
        except (ValueError, UnicodeDecodeError):
            return None
        username, separator, password = decoded.partition(":")
        if separator != ":" or password != "correct-password":
            return None
        return self._subjects.get(username)


def subject(
    subject_id: str,
    display_name: str,
    *,
    organization_id: str = ORGANIZATION_ID,
    method: AuthenticationMethod = AuthenticationMethod.LDAP,
    kind: SubjectKind = SubjectKind.HUMAN,
    roles: tuple[str, ...] = (),
) -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id=subject_id,
        display_name=display_name,
        kind=kind,
        provider_id="provider.ldap.enterprise",
        authentication_method=method,
        assurance_level=AssuranceLevel.MULTI_FACTOR,
        authenticated_at=NOW,
        organization_id=organization_id,
        role_ids=roles,
    )


def build_settings() -> Settings:
    return Settings(
        environment="test",
        development_identity_enabled=False,
        session_absolute_timeout_minutes=60,
        session_idle_timeout_minutes=30,
        session_max_per_subject=10,
    )


def governance_authorization(
    sink: CollectingAuditSink,
    *,
    admin_subject_id: str = "subject.enterprise.admin",
    environment: str = "test",
) -> AuthorizationService:
    scopes = (
        identity_governance_scope(ORGANIZATION_ID, environment, CapabilityClass.C0_INFORMATIONAL),
        identity_governance_scope(ORGANIZATION_ID, environment, CapabilityClass.C2_DIAGNOSTIC),
    )
    return AuthorizationService(
        permissions=identity_governance_permission_definitions(),
        roles=(security_administrator_role_definition(),),
        assignments=tuple(
            RoleAssignment(
                assignment_id=f"assignment.security-admin.{index}",
                version=1,
                subject_id=admin_subject_id,
                role_id=SECURITY_ADMINISTRATOR_ROLE_ID,
                scope=scope,
                valid_from=datetime.min.replace(tzinfo=UTC),
            )
            for index, scope in enumerate(scopes, start=1)
        ),
        audit_sink=sink,
        clock=lambda: NOW,
    )


class GovernanceFixture:
    def __init__(self, sink: CollectingAuditSink | None = None) -> None:
        self.sink = sink or CollectingAuditSink()
        self.admin = subject(
            "subject.enterprise.admin",
            "Security Administrator",
            roles=(SECURITY_ADMINISTRATOR_ROLE_ID,),
        )
        self.operator = subject("subject.enterprise.operator", "Storage Operator")
        self.foreign = subject(
            "subject.foreign.operator",
            "Foreign Operator",
            organization_id="organization.foreign",
        )
        self.provider = MultiUserIdentityProvider(
            {"admin": self.admin, "operator": self.operator, "foreign": self.foreign}
        )
        self.session_repository = InMemorySessionRepository()
        self.api_repository = InMemoryApiCredentialRepository()
        self.identity_service = IdentityService(
            provider=self.provider,
            audit_sink=self.sink,
            clock=lambda: NOW,
        )
        self.session_service = SessionService(
            identity_service=self.identity_service,
            repository=self.session_repository,
            audit_sink=self.sink,
            absolute_timeout=timedelta(hours=1),
            idle_timeout=timedelta(minutes=30),
            max_sessions_per_subject=10,
            clock=lambda: NOW,
        )
        token_sequence = iter(range(1, 20))
        self.api_service = ApiCredentialService(
            repository=self.api_repository,
            audit_sink=self.sink,
            clock=lambda: NOW,
            token_factory=lambda: f"atlas_pat_{next(token_sequence):043d}",
        )
        self.governance_service = IdentityGovernanceService(
            session_repository=self.session_repository,
            api_credential_repository=self.api_repository,
            audit_sink=self.sink,
            clock=lambda: NOW,
        )
        self.app = create_app(
            build_settings(),
            audit_sink=self.sink,
            identity_provider=self.provider,
            authorization_service=governance_authorization(self.sink),
            session_service=self.session_service,
            api_credential_service=self.api_service,
            identity_governance_service=self.governance_service,
        )

    def create_session(self, username: str) -> IssuedSession:
        credential = base64.b64encode(f"{username}:correct-password".encode()).decode()
        return asyncio.run(
            self.session_service.create(
                AuthenticationInput(
                    correlation_id=f"cor_create_{username}",
                    authorization_scheme="basic",
                    credential=credential,
                )
            )
        )

    def issue_operator_credential(self) -> IssuedApiCredential:
        grant = personal_api_grant_catalog(ORGANIZATION_ID, "test")[STORAGE_OVERVIEW_READ]
        return asyncio.run(
            self.api_service.issue(
                subject=self.operator,
                display_name="Storage dashboard reader",
                purpose="Read the bounded storage overview from an operator workstation.",
                lifetime=timedelta(minutes=30),
                grants=(grant,),
                correlation_id="cor_issue_operator_token",
            )
        )


def login(client: TestClient, username: str = "admin") -> tuple[str, str]:
    response = client.post(
        "/api/v1/authentication/sessions",
        json={"username": username, "password": "correct-password"},
    )
    assert response.status_code == 201
    return str(response.headers["X-CSRF-Token"]), str(response.json()["data"]["session_id"])


def error_identity(response: Response) -> tuple[int, str, str, str]:
    body = response.json()
    return response.status_code, body["code"], body["title"], body["detail"]


def test_authorized_inventory_is_bounded_filterable_secret_free_and_excludes_self() -> None:
    fixture = GovernanceFixture()
    target_session = fixture.create_session("operator")
    own_session = fixture.create_session("admin")
    target_credential = fixture.issue_operator_credential()
    with TestClient(fixture.app) as client:
        client.cookies.set("atlas_session", own_session.token, path="/api")
        client.cookies.set("atlas_csrf", own_session.csrf_token, path="/")
        response = client.get(
            "/api/v1/identity-governance?query=dashboard&limit=1",
            headers={"X-Correlation-ID": "cor_inventory"},
        )

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    data = response.json()["data"]
    assert data["sessions"] == []
    assert [item["credential_id"] for item in data["api_credentials"]] == [
        target_credential.record.credential_id
    ]
    assert target_credential.token not in response.text
    assert target_session.token not in response.text
    assert "token_digest" not in response.text
    assert own_session.record.session_id not in response.text
    event = next(
        item
        for item in fixture.sink.records
        if item.event_type == "atlas.identity.governance.inventory_read"
    )
    assert event.subject_id == fixture.admin.subject_id
    assert dict(event.target_metadata) == {
        "session_count": "0",
        "api_credential_count": "1",
        "filtered": "true",
        "truncated": "false",
    }


def test_admin_revokes_foreign_session_and_token_without_ending_current_session() -> None:
    fixture = GovernanceFixture()
    target_session = fixture.create_session("operator")
    target_credential = fixture.issue_operator_credential()
    with TestClient(fixture.app) as admin_client:
        csrf, admin_session_id = login(admin_client)
        inventory = admin_client.get("/api/v1/identity-governance")
        assert inventory.status_code == 200
        session_item = next(
            item
            for item in inventory.json()["data"]["sessions"]
            if item["session_id"] == target_session.record.session_id
        )
        credential_item = next(
            item
            for item in inventory.json()["data"]["api_credentials"]
            if item["credential_id"] == target_credential.record.credential_id
        )
        session_revoked = admin_client.post(
            f"/api/v1/identity-governance/sessions/{target_session.record.session_id}/revocations",
            json={
                "expected_version": session_item["version"],
                "reason": "Operator access is no longer required.",
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": ADMIN_SESSION_KEY},
        )
        credential_revoked = admin_client.post(
            f"/api/v1/identity-governance/api-credentials/{target_credential.record.credential_id}/revocations",
            json={
                "expected_version": credential_item["version"],
                "reason": "The workstation integration has been retired.",
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": ADMIN_TOKEN_KEY},
        )
        admin_still_active = admin_client.get("/api/v1/identity-governance")

        with TestClient(fixture.app) as old_session_client:
            old_session_client.cookies.set("atlas_session", target_session.token, path="/api")
            old_session = old_session_client.get("/api/v1/identity-governance")
        with TestClient(fixture.app) as old_token_client:
            old_token = old_token_client.get(
                "/api/v1/identity-governance",
                headers={"Authorization": f"Bearer {target_credential.token}"},
            )

    assert session_revoked.status_code == 200
    assert credential_revoked.status_code == 200
    assert session_revoked.headers["Cache-Control"] == "no-store"
    assert credential_revoked.headers["Cache-Control"] == "no-store"
    assert admin_still_active.status_code == 200
    assert admin_session_id not in admin_still_active.text
    assert old_session.status_code == 401
    assert old_token.status_code == 401
    stored_session = asyncio.run(
        fixture.session_repository.get_by_session_id(target_session.record.session_id)
    )
    stored_credential = asyncio.run(
        fixture.api_repository.get_by_id(target_credential.record.credential_id)
    )
    assert stored_session is not None and stored_session.state is SessionState.REVOKED
    assert stored_credential is not None
    assert stored_credential.state is ApiCredentialState.REVOKED
    revoke_events = [
        item
        for item in fixture.sink.records
        if item.event_type
        in {
            "atlas.identity.governance.session_revoked",
            "atlas.identity.governance.api_credential_revoked",
        }
    ]
    assert {item.target_subject_id for item in revoke_events} == {fixture.operator.subject_id}
    assert {item.idempotency_key for item in revoke_events} == {
        ADMIN_SESSION_KEY,
        ADMIN_TOKEN_KEY,
    }
    assert all(item.reason and item.correlation_id for item in revoke_events)
    assert target_credential.token not in repr(revoke_events)
    authorization_events = [
        item
        for item in fixture.sink.records
        if item.event_type == "atlas.authorization.access.allowed"
        and item.idempotency_key in {ADMIN_SESSION_KEY, ADMIN_TOKEN_KEY}
    ]
    assert {item.target_subject_id for item in authorization_events} == {
        fixture.operator.subject_id
    }
    assert all(item.reason and item.target_metadata for item in authorization_events)
    assert target_credential.token not in repr(authorization_events)


def test_csrf_browser_session_and_unsafe_bearer_invariants_are_enforced() -> None:
    fixture = GovernanceFixture()
    target = fixture.issue_operator_credential()
    with TestClient(fixture.app) as client:
        csrf, _ = login(client)
        inventory = client.get("/api/v1/identity-governance").json()["data"]
        version = inventory["api_credentials"][0]["version"]
        missing_csrf = client.post(
            f"/api/v1/identity-governance/api-credentials/{target.record.credential_id}/revocations",
            json={"expected_version": version, "reason": "Administrative review."},
            headers={"Idempotency-Key": ADMIN_TOKEN_KEY},
        )
        client.cookies.clear()
        unsafe_bearer = client.post(
            f"/api/v1/identity-governance/api-credentials/{target.record.credential_id}/revocations",
            json={"expected_version": version, "reason": "Administrative review."},
            headers={
                "Authorization": f"Bearer {target.token}",
                "Idempotency-Key": ADMIN_TOKEN_KEY,
                "X-CSRF-Token": csrf,
            },
        )

    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["code"] == "csrf_validation_failed"
    assert unsafe_bearer.status_code == 403
    assert unsafe_bearer.json()["code"] == "credential_unsafe_method_denied"


def test_hidden_missing_foreign_inactive_and_stale_targets_are_indistinguishable() -> None:
    fixture = GovernanceFixture()
    active = fixture.create_session("operator")
    foreign = fixture.create_session("foreign")
    with TestClient(fixture.app) as client:
        csrf, _ = login(client)
        inventory = client.get("/api/v1/identity-governance").json()["data"]
        visible = next(
            item for item in inventory["sessions"] if item["session_id"] == active.record.session_id
        )
        base_headers = {
            "X-CSRF-Token": csrf,
            "Idempotency-Key": "governance-hidden-0001",
        }
        missing = client.post(
            "/api/v1/identity-governance/sessions/session.missing/revocations",
            json={"expected_version": 1, "reason": "Administrative review."},
            headers=base_headers,
        )
        foreign_response = client.post(
            f"/api/v1/identity-governance/sessions/{foreign.record.session_id}/revocations",
            json={"expected_version": 1, "reason": "Administrative review."},
            headers={**base_headers, "Idempotency-Key": "governance-hidden-0002"},
        )
        stale = client.post(
            f"/api/v1/identity-governance/sessions/{active.record.session_id}/revocations",
            json={
                "expected_version": visible["version"] + 10,
                "reason": "Administrative review.",
            },
            headers={**base_headers, "Idempotency-Key": "governance-hidden-0003"},
        )
        revoked = client.post(
            f"/api/v1/identity-governance/sessions/{active.record.session_id}/revocations",
            json={
                "expected_version": visible["version"],
                "reason": "Administrative review.",
            },
            headers={**base_headers, "Idempotency-Key": "governance-hidden-0004"},
        )
        inactive = client.post(
            f"/api/v1/identity-governance/sessions/{active.record.session_id}/revocations",
            json={
                "expected_version": revoked.json()["data"]["version"],
                "reason": "Administrative review.",
            },
            headers={**base_headers, "Idempotency-Key": "governance-hidden-0005"},
        )

    identities = {
        error_identity(response) for response in (missing, foreign_response, stale, inactive)
    }
    assert identities == {
        (
            404,
            "governance_target_unavailable",
            "Identity resource unavailable",
            "The requested identity resource is unavailable.",
        )
    }


def test_revocation_is_idempotent_conflict_safe_and_cannot_resurrect() -> None:
    fixture = GovernanceFixture()
    target = fixture.issue_operator_credential()
    original = target.record
    with TestClient(fixture.app) as client:
        csrf, _ = login(client)
        headers = {"X-CSRF-Token": csrf, "Idempotency-Key": ADMIN_TOKEN_KEY}
        payload = {
            "expected_version": original.version,
            "reason": "Administrative review completed.",
        }
        first = client.post(
            f"/api/v1/identity-governance/api-credentials/{original.credential_id}/revocations",
            json=payload,
            headers=headers,
        )
        replay = client.post(
            f"/api/v1/identity-governance/api-credentials/{original.credential_id}/revocations",
            json=payload,
            headers=headers,
        )
        conflict = client.post(
            f"/api/v1/identity-governance/api-credentials/{original.credential_id}/revocations",
            json={**payload, "reason": "A different administrative reason."},
            headers=headers,
        )

    assert first.status_code == replay.status_code == 200
    assert first.json()["data"] == replay.json()["data"]
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "governance_idempotency_conflict"
    resurrected = replace(original, version=original.version + 1)
    assert (
        asyncio.run(fixture.api_repository.update(resurrected, expected_version=original.version))
        is False
    )
    stored = asyncio.run(fixture.api_repository.get_by_id(original.credential_id))
    assert stored is not None and stored.state is ApiCredentialState.REVOKED


def test_current_administrator_session_is_protected() -> None:
    fixture = GovernanceFixture()
    with TestClient(fixture.app) as client:
        csrf, current_session_id = login(client)
        current = asyncio.run(fixture.session_repository.get_by_session_id(current_session_id))
        assert current is not None
        response = client.post(
            f"/api/v1/identity-governance/sessions/{current_session_id}/revocations",
            json={
                "expected_version": current.version,
                "reason": "Accidental current-session request.",
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": ADMIN_SESSION_KEY},
        )
        still_active = client.get("/api/v1/identity-governance")

    assert response.status_code == 409
    assert response.json()["code"] == "current_admin_session_protected"
    assert still_active.status_code == 200


def test_ordinary_enterprise_and_development_identities_have_no_admin_surface() -> None:
    fixture = GovernanceFixture()
    protected_admin_session = fixture.create_session("admin")
    with TestClient(fixture.app) as client:
        csrf, _ = login(client, "operator")
        ordinary = client.get("/api/v1/identity-governance")
        denied_mutation = client.post(
            f"/api/v1/identity-governance/sessions/"
            f"{protected_admin_session.record.session_id}/revocations",
            json={
                "expected_version": protected_admin_session.record.version,
                "reason": "Unauthorized administrative attempt.",
            },
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "ordinary-admin-denial-0001",
            },
        )

    assert ordinary.status_code == 403
    assert ordinary.json()["code"] == "authorization_denied"
    assert denied_mutation.status_code == 403
    denied_event = next(
        item
        for item in reversed(fixture.sink.records)
        if item.event_type == "atlas.authorization.access.denied"
        and item.idempotency_key == "ordinary-admin-denial-0001"
    )
    assert denied_event.subject_id == fixture.operator.subject_id
    assert denied_event.target_subject_id == fixture.admin.subject_id
    assert denied_event.reason == "Unauthorized administrative attempt."
    assert dict(denied_event.target_metadata)["target_kind"] == "browser_session"

    development = subject(
        "subject.enterprise.admin",
        "Development Administrator",
        method=AuthenticationMethod.DEVELOPMENT,
        roles=(SECURITY_ADMINISTRATOR_ROLE_ID,),
    )
    sink = CollectingAuditSink()
    service = IdentityGovernanceService(
        session_repository=InMemorySessionRepository(),
        api_credential_repository=InMemoryApiCredentialRepository(),
        audit_sink=sink,
        clock=lambda: NOW,
    )
    with pytest.raises(IdentityGovernanceError, match="enterprise_human_required"):
        asyncio.run(
            service.inventory(
                actor=development,
                query=None,
                limit=50,
                correlation_id="cor_development_denied",
            )
        )
    assert sink.records[-1].result_code == "enterprise_human_required"
    assert sink.records[-1].outcome == "denied"


def test_nonhuman_identity_is_denied_even_with_the_administrator_role() -> None:
    sink = CollectingAuditSink()
    service = IdentityGovernanceService(
        session_repository=InMemorySessionRepository(),
        api_credential_repository=InMemoryApiCredentialRepository(),
        audit_sink=sink,
        clock=lambda: NOW,
    )
    nonhuman = subject(
        "subject.enterprise.automation",
        "Automation Identity",
        method=AuthenticationMethod.MUTUAL_TLS,
        kind=SubjectKind.SERVICE,
        roles=(SECURITY_ADMINISTRATOR_ROLE_ID,),
    )
    with pytest.raises(IdentityGovernanceError, match="enterprise_human_required"):
        asyncio.run(
            service.inventory(
                actor=nonhuman,
                query=None,
                limit=50,
                correlation_id="cor_nonhuman_denied",
            )
        )
    assert sink.records[-1].subject_id == nonhuman.subject_id
    assert sink.records[-1].result_code == "enterprise_human_required"


def test_exact_scope_mismatch_denies_administrator() -> None:
    fixture = GovernanceFixture()
    with TestClient(fixture.app) as client:
        login(client)
        fixture.app.state.authorization_service = governance_authorization(
            fixture.sink, environment="development"
        )
        response = client.get("/api/v1/identity-governance")

    assert response.status_code == 403
    assert response.json()["code"] == "authorization_denied"
    decision = next(
        item
        for item in reversed(fixture.sink.records)
        if item.event_type == "atlas.authorization.access.denied"
    )
    assert decision.result_code == "no_matching_assignment"


def test_audit_failure_blocks_inventory_and_revocation_state_change() -> None:
    inventory_fixture = GovernanceFixture(
        CollectingAuditSink({"atlas.identity.governance.inventory_read"})
    )
    inventory_fixture.create_session("operator")
    with TestClient(inventory_fixture.app, raise_server_exceptions=False) as client:
        login(client)
        inventory = client.get("/api/v1/identity-governance")
    assert inventory.status_code == 500

    revoke_fixture = GovernanceFixture(
        CollectingAuditSink({"atlas.identity.governance.api_credential_revoked"})
    )
    target = revoke_fixture.issue_operator_credential()
    with TestClient(revoke_fixture.app, raise_server_exceptions=False) as client:
        csrf, _ = login(client)
        response = client.post(
            f"/api/v1/identity-governance/api-credentials/{target.record.credential_id}/revocations",
            json={
                "expected_version": target.record.version,
                "reason": "Administrative review.",
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": ADMIN_TOKEN_KEY},
        )
    assert response.status_code == 500
    stored = asyncio.run(revoke_fixture.api_repository.get_by_id(target.record.credential_id))
    assert stored is not None and stored.state is ApiCredentialState.ACTIVE
