from __future__ import annotations

import asyncio
import base64
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.capabilities import CapabilityClass
from atlas.core.config import Settings
from atlas.modules.authorization.application.bootstrap import (
    AUDIT_EXPORT,
    SECURITY_ADMINISTRATOR_ROLE_ID,
    SECURITY_AUDITOR_ROLE_ID,
    audit_export_scope,
    audit_permission_definitions,
    security_auditor_role_definition,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import RoleAssignment
from atlas.modules.identity.adapters.api_credentials import InMemoryApiCredentialRepository
from atlas.modules.identity.adapters.sessions import InMemorySessionRepository
from atlas.modules.identity.application.api_credentials import ApiCredentialService
from atlas.modules.identity.application.service import IdentityService
from atlas.modules.identity.application.sessions import SessionService
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationInput,
    AuthenticationMethod,
    CredentialGrant,
    SubjectKind,
)
from atlas.modules.security_export.adapters.synthetic import (
    SyntheticTlsSyslogTransport,
    build_synthetic_syslog_destinations,
)
from atlas.modules.security_export.application.service import SecurityExportService

NOW = datetime(2026, 8, 4, 16, 0, tzinfo=UTC)
ORGANIZATION_ID = "organization.enterprise"


class CollectingAuditSink:
    def __init__(self, *, failing_event_type: str | None = None) -> None:
        self.records: list[AuditRecord] = []
        self._failing_event_type = failing_event_type

    async def record(self, event: AuditRecord) -> None:
        if event.event_type == self._failing_event_type:
            raise RuntimeError("required audit unavailable")
        self.records.append(event)


class EnterpriseIdentityProvider:
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


def enterprise_subject(
    subject_id: str,
    display_name: str,
    *,
    role_ids: tuple[str, ...] = (),
    organization_id: str = ORGANIZATION_ID,
    method: AuthenticationMethod = AuthenticationMethod.LDAP,
    kind: SubjectKind = SubjectKind.HUMAN,
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
        role_ids=role_ids,
    )


def audit_record(index: int, **overrides: object) -> AuditRecord:
    values: dict[str, object] = {
        "event_id": f"evt_audit_{index}",
        "event_type": "atlas.authorization.decision",
        "schema_version": "1.0",
        "producer": "project-atlas-api",
        "producer_version": "0.1.0",
        "occurred_at": NOW + timedelta(seconds=index),
        "correlation_id": f"cor_audit_{index}",
        "subject_id": "subject.enterprise.operator",
        "actor_type": "human",
        "authentication_method": "ldap",
        "assurance_level": "multi_factor",
        "permission_id": "storage.overview.read",
        "resource_type": "resource.storage.overview",
        "scope_reference": (
            "organization.enterprise/environment.test/site.local/"
            "domain.storage/resource.storage.lab-overview/C1"
        ),
        "decision_id": f"decision.audit.{index}",
        "outcome": "allowed" if index % 2 else "denied",
        "result_code": "matching_assignment" if index % 2 else "no_matching_assignment",
    }
    values.update(overrides)
    return AuditRecord(**values)  # type: ignore[arg-type]


class AuditFixture:
    def __init__(
        self,
        *,
        sink: CollectingAuditSink | None = None,
        transport: SyntheticTlsSyslogTransport | None = None,
    ) -> None:
        self.sink = sink or CollectingAuditSink()
        self.transport = transport or SyntheticTlsSyslogTransport()
        self.export_service = SecurityExportService(
            delegate=self.sink,
            destinations=build_synthetic_syslog_destinations(),
            transport=self.transport,
            environment_id="environment.test",
            site_id="site.local",
        )
        self.auditor = enterprise_subject(
            "subject.enterprise.auditor",
            "Security Auditor",
            role_ids=(SECURITY_AUDITOR_ROLE_ID,),
        )
        self.security_admin = enterprise_subject(
            "subject.enterprise.security-admin",
            "Security Administrator",
            role_ids=(SECURITY_ADMINISTRATOR_ROLE_ID,),
        )
        self.operator = enterprise_subject("subject.enterprise.operator", "Storage Operator")
        self.foreign_auditor = enterprise_subject(
            "subject.foreign.auditor",
            "Foreign Security Auditor",
            role_ids=(SECURITY_AUDITOR_ROLE_ID,),
            organization_id="organization.foreign",
        )
        self.provider = EnterpriseIdentityProvider(
            {
                "auditor": self.auditor,
                "admin": self.security_admin,
                "operator": self.operator,
                "foreign": self.foreign_auditor,
            }
        )
        identity_service = IdentityService(provider=self.provider, audit_sink=self.export_service)
        self.session_service = SessionService(
            identity_service=identity_service,
            repository=InMemorySessionRepository(),
            audit_sink=self.export_service,
            absolute_timeout=timedelta(hours=1),
            idle_timeout=timedelta(minutes=30),
            max_sessions_per_subject=10,
            clock=lambda: NOW,
        )
        token_counter = iter(range(1, 10))
        self.api_service = ApiCredentialService(
            repository=InMemoryApiCredentialRepository(),
            audit_sink=self.export_service,
            clock=lambda: NOW,
            token_factory=lambda: f"atlas_pat_{next(token_counter):043d}",
        )
        scopes = (
            audit_export_scope(ORGANIZATION_ID, "test", CapabilityClass.C0_INFORMATIONAL),
            audit_export_scope(ORGANIZATION_ID, "test", CapabilityClass.C2_DIAGNOSTIC),
        )
        authorization = AuthorizationService(
            permissions=audit_permission_definitions(),
            roles=(security_auditor_role_definition(),),
            assignments=tuple(
                RoleAssignment(
                    assignment_id=f"assignment.security-auditor.{index}",
                    version=1,
                    subject_id=self.auditor.subject_id,
                    role_id=SECURITY_AUDITOR_ROLE_ID,
                    scope=scope,
                    valid_from=datetime.min.replace(tzinfo=UTC),
                )
                for index, scope in enumerate(scopes, start=1)
            ),
            audit_sink=self.export_service,
            clock=lambda: NOW,
        )
        settings = Settings(environment="test", development_identity_enabled=False)
        self.app = create_app(
            settings,
            audit_sink=self.sink,
            security_export_service=self.export_service,
            identity_provider=self.provider,
            authorization_service=authorization,
            session_service=self.session_service,
            api_credential_service=self.api_service,
        )

    def record(self, count: int) -> None:
        for index in range(1, count + 1):
            asyncio.run(self.export_service.record(audit_record(index)))

    def issue_auditor_bearer(self) -> str:
        scope = audit_export_scope(
            ORGANIZATION_ID,
            "test",
            CapabilityClass.C2_DIAGNOSTIC,
        )
        issued = asyncio.run(
            self.api_service.issue(
                subject=self.auditor,
                display_name="Audit export reader",
                purpose="Bounded audit export test credential.",
                lifetime=timedelta(minutes=10),
                grants=(
                    CredentialGrant(
                        permission_id=AUDIT_EXPORT,
                        scope_reference=scope.reference,
                    ),
                ),
                correlation_id="cor_issue_audit_bearer",
            )
        )
        return issued.token


def login(client: TestClient, username: str) -> str:
    response = client.post(
        "/api/v1/authentication/sessions",
        json={"username": username, "password": "correct-password"},
    )
    assert response.status_code == 201
    return str(response.headers["X-CSRF-Token"])


def test_audit_overview_requires_browser_authentication_and_no_store() -> None:
    fixture = AuditFixture()
    with TestClient(fixture.app) as client:
        response = client.get("/api/v1/audit-export/overview")

    assert response.status_code == 401
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("username", ["admin", "operator", "foreign"])
def test_security_admin_operator_and_foreign_scope_have_no_implicit_audit_access(
    username: str,
) -> None:
    fixture = AuditFixture()
    with TestClient(fixture.app) as client:
        login(client, username)
        response = client.get("/api/v1/audit-export/overview")

    assert response.status_code == 403
    assert response.json()["code"] == "authorization_denied"
    assert "audit" not in response.json()["detail"].lower()


def test_auditor_reads_bounded_secret_free_inventory_and_access_is_audited() -> None:
    fixture = AuditFixture()
    fixture.record(4)
    with TestClient(fixture.app) as client:
        login(client, "auditor")
        response = client.get(
            "/api/v1/audit-export/overview?limit=3&outcome=allowed",
            headers={"X-Correlation-ID": "cor_auditor_inventory"},
        )

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    data = response.json()["data"]
    assert data["page"]["limit"] == 3
    assert len(data["page"]["events"]) <= 3
    assert all(item["outcome"] == "allowed" for item in data["page"]["events"])
    assert "content_digest" not in response.text
    assert "payload" not in response.text
    assert any(item.event_type == "atlas.audit.inventory.read" for item in fixture.sink.records)


def test_signed_cursor_pages_without_duplicates_and_rejects_tampering() -> None:
    fixture = AuditFixture()
    fixture.record(7)
    with TestClient(fixture.app) as client:
        login(client, "auditor")
        first = client.get("/api/v1/audit-export/overview?limit=3").json()["data"]["page"]
        assert first["has_more"] is True
        cursor = first["next_cursor"]
        second_response = client.get(f"/api/v1/audit-export/overview?limit=3&cursor={cursor}")
        tampered = client.get(f"/api/v1/audit-export/overview?limit=3&cursor={cursor[:-1]}x")

    assert second_response.status_code == 200, second_response.text
    second = second_response.json()["data"]["page"]
    assert {item["event_id"] for item in first["events"]}.isdisjoint(
        item["event_id"] for item in second["events"]
    )
    assert tampered.status_code == 400
    assert "count" not in tampered.text.lower()


def test_query_normalizes_controls_and_redacts_secret_assignments() -> None:
    fixture = AuditFixture()
    asyncio.run(
        fixture.export_service.record(
            audit_record(
                1,
                event_id="evt_token_rotation_1",
                event_type="atlas.audit\ninjected",
                result_code="password=do-not-export",
            )
        )
    )
    with TestClient(fixture.app) as client:
        login(client, "auditor")
        response = client.get("/api/v1/audit-export/overview?query=token_rotation")

    assert response.status_code == 200
    event = next(
        item
        for item in response.json()["data"]["page"]["events"]
        if item["event_id"] == "evt_token_rotation_1"
    )
    assert event["event_type"] == "atlas.audit injected"
    assert event["result_code"] == "redacted"
    assert "do-not-export" not in response.text
    assert all("\n" not in message.payload for message in fixture.transport.messages)


def test_required_audit_failure_blocks_inventory_disclosure() -> None:
    fixture = AuditFixture(
        sink=CollectingAuditSink(failing_event_type="atlas.audit.inventory.read")
    )
    fixture.record(1)
    with TestClient(fixture.app, raise_server_exceptions=False) as client:
        login(client, "auditor")
        response = client.get("/api/v1/audit-export/overview")

    assert response.status_code == 500
    assert response.headers["Cache-Control"] == "no-store"
    assert "evt_audit_1" not in response.text


def test_retry_requires_csrf_and_personal_bearer_cannot_mutate() -> None:
    fixture = AuditFixture(transport=SyntheticTlsSyslogTransport(fail_attempts=1))
    bearer = fixture.issue_auditor_bearer()
    with TestClient(fixture.app) as client:
        csrf = login(client, "auditor")
        missing_csrf = client.post("/api/v1/audit-export/retry")
        allowed = client.post(
            "/api/v1/audit-export/retry",
            headers={"X-CSRF-Token": csrf},
        )
    with TestClient(fixture.app) as bearer_client:
        bearer_response = bearer_client.post(
            "/api/v1/audit-export/retry",
            headers={"Authorization": f"Bearer {bearer}"},
        )

    assert missing_csrf.status_code == 403
    assert allowed.status_code == 200
    assert allowed.headers["Cache-Control"] == "no-store"
    assert bearer_response.status_code == 403
    assert bearer_response.json()["code"] == "credential_unsafe_method_denied"


@pytest.mark.asyncio
async def test_duplicate_identity_is_idempotent_and_conflict_fails_closed() -> None:
    fixture = AuditFixture()
    record = audit_record(1)
    await fixture.export_service.record(record)
    delivered = len(fixture.transport.messages)
    await fixture.export_service.record(record)

    assert len(fixture.transport.messages) == delivered
    with pytest.raises(RuntimeError, match="identity_conflict"):
        await fixture.export_service.record(audit_record(1, result_code="conflicting_result"))
