from __future__ import annotations

import asyncio
import base64
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.capabilities import CapabilityClass
from atlas.core.config import Settings
from atlas.modules.authorization.application.bootstrap import (
    SECURITY_ADMINISTRATOR_ROLE_ID,
    workload_identity_governance_scope,
    workload_identity_permission_definitions,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import RoleAssignment, RoleDefinition
from atlas.modules.identity.adapters.workload_identities import (
    InMemoryWorkloadIdentityRepository,
)
from atlas.modules.identity.application.workload_identities import (
    WorkloadIdentityError,
    WorkloadIdentityService,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationInput,
    AuthenticationMethod,
    SubjectKind,
)

NOW = datetime(2026, 8, 4, 16, 0, tzinfo=UTC)
ORGANIZATION_ID = "organization.enterprise"
IDENTITY_ID = "workload.atlas.health.scheduler"
AUDIENCE = "service.health-check"


class MutableClock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


class CollectingAuditSink:
    def __init__(self, failing_event: str | None = None) -> None:
        self.records: list[AuditRecord] = []
        self.failing_event = failing_event

    async def record(self, event: AuditRecord) -> None:
        if event.event_type == self.failing_event:
            raise RuntimeError("required workload audit unavailable")
        self.records.append(event)


class MultiUserProvider:
    def __init__(self, subjects: dict[str, AuthenticatedSubject]) -> None:
        self.subjects = subjects

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
        return self.subjects.get(username)


def enterprise_subject(
    subject_id: str, display_name: str, *, roles: tuple[str, ...] = ()
) -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id=subject_id,
        display_name=display_name,
        kind=SubjectKind.HUMAN,
        provider_id="provider.ldap.enterprise",
        authentication_method=AuthenticationMethod.LDAP,
        assurance_level=AssuranceLevel.MULTI_FACTOR,
        authenticated_at=NOW,
        organization_id=ORGANIZATION_ID,
        role_ids=roles,
    )


def workload_authorization(sink: CollectingAuditSink) -> AuthorizationService:
    permissions = workload_identity_permission_definitions()
    role = RoleDefinition(
        role_id=SECURITY_ADMINISTRATOR_ROLE_ID,
        version=3,
        permissions=frozenset(item.permission_id for item in permissions),
    )
    scopes = (
        workload_identity_governance_scope(
            ORGANIZATION_ID, "test", CapabilityClass.C0_INFORMATIONAL
        ),
        workload_identity_governance_scope(ORGANIZATION_ID, "test", CapabilityClass.C2_DIAGNOSTIC),
    )
    return AuthorizationService(
        permissions=permissions,
        roles=(role,),
        assignments=tuple(
            RoleAssignment(
                assignment_id=f"assignment.workload-admin.{index}",
                version=1,
                subject_id="subject.enterprise.admin",
                role_id=SECURITY_ADMINISTRATOR_ROLE_ID,
                scope=scope,
                valid_from=datetime.min.replace(tzinfo=UTC),
            )
            for index, scope in enumerate(scopes, start=1)
        ),
        audit_sink=sink,
        clock=lambda: NOW,
    )


class WorkloadFixture:
    def __init__(self, sink: CollectingAuditSink | None = None) -> None:
        self.sink = sink or CollectingAuditSink()
        self.clock = MutableClock()
        self.repository = InMemoryWorkloadIdentityRepository()
        self.service = WorkloadIdentityService(
            repository=self.repository,
            audit_sink=self.sink,
            environment_id="environment.test",
            signing_keys={7: b"w" * 32},
            clock=self.clock,
        )
        self.admin = enterprise_subject(
            "subject.enterprise.admin",
            "Security Administrator",
            roles=(SECURITY_ADMINISTRATOR_ROLE_ID,),
        )
        self.operator = enterprise_subject("subject.enterprise.operator", "Storage Operator")
        self.provider = MultiUserProvider({"admin": self.admin, "operator": self.operator})
        self.app = create_app(
            Settings(environment="test", development_identity_enabled=False),
            audit_sink=self.sink,
            identity_provider=self.provider,
            authorization_service=workload_authorization(self.sink),
            workload_identity_service=self.service,
        )


def login(client: TestClient, username: str = "admin") -> str:
    response = client.post(
        "/api/v1/authentication/sessions",
        json={"username": username, "password": "correct-password"},
    )
    assert response.status_code == 201
    return str(response.headers["X-CSRF-Token"])


def create_payload() -> dict[str, object]:
    return {
        "identity_id": IDENTITY_ID,
        "display_name": "Health scheduler",
        "service_id": "service.health-scheduler",
        "instance_id": "instance.health-scheduler.local-01",
        "owner_subject_id": "subject.enterprise.platform-owner",
        "purpose": "Run bounded Atlas health-check coordination.",
        "audiences": [AUDIENCE],
        "secret_reference_ids": ["secret.connector.health-readonly"],
        "lifetime_minutes": 10,
        "reason": "Create the dedicated health scheduler workload identity.",
    }


def create_identity(client: TestClient, csrf: str, key: str = "workload-create-0001"):
    return client.post(
        "/api/v1/workload-identities",
        json=create_payload(),
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": key},
    )


def test_create_inventory_and_authentication_are_secret_free_and_non_executing() -> None:
    fixture = WorkloadFixture()
    with TestClient(fixture.app) as client:
        csrf = login(client)
        created = create_identity(client, csrf)
        inventory = client.get("/api/v1/workload-identities?query=health&limit=10")

    assert created.status_code == 201
    body = created.json()["data"]
    token = body["token"]
    assert token.startswith("atlas_wlt_v1.")
    assert body["identity"]["secret_reference_ids"] == ["secret.connector.health-readonly"]
    assert "token_digest" not in created.text
    assert "wwww" not in created.text
    assert inventory.status_code == 200
    assert inventory.headers["Cache-Control"] == "no-store"
    assert token not in inventory.text

    with TestClient(fixture.app) as workload_client:
        current = workload_client.get(
            "/api/v1/workload-identities/current",
            headers={
                "Authorization": f"Workload {token}",
                "X-Atlas-Audience": AUDIENCE,
                "X-Atlas-Environment": "environment.test",
            },
        )
    assert current.status_code == 200
    current_data = current.json()["data"]
    assert current_data["display_name"] == "Health scheduler"
    assert current_data["organization_id"] == ORGANIZATION_ID
    assert current_data["subject_kind"] == "service"
    assert current_data["role_ids"] == []
    assert current_data["execution_authorized"] is False


def test_audience_environment_signature_and_expiry_fail_closed() -> None:
    fixture = WorkloadFixture()
    with TestClient(fixture.app) as client:
        csrf = login(client)
        token = create_identity(client, csrf).json()["data"]["token"]
        headers = {
            "Authorization": f"Workload {token}",
            "X-Atlas-Audience": AUDIENCE,
            "X-Atlas-Environment": "environment.test",
        }
        wrong_audience = client.get(
            "/api/v1/workload-identities/current",
            headers={**headers, "X-Atlas-Audience": "service.reports"},
        )
        wrong_environment = client.get(
            "/api/v1/workload-identities/current",
            headers={**headers, "X-Atlas-Environment": "environment.production"},
        )
        tampered = client.get(
            "/api/v1/workload-identities/current",
            headers={**headers, "Authorization": f"Workload {token[:-1]}A"},
        )
        fixture.clock.now += timedelta(minutes=11)
        expired = client.get("/api/v1/workload-identities/current", headers=headers)

    assert {
        item.status_code for item in (wrong_audience, wrong_environment, tampered, expired)
    } == {401}
    assert {
        item.json()["code"] for item in (wrong_audience, wrong_environment, tampered, expired)
    } == {"workload_authentication_failed"}


def test_future_token_outside_clock_skew_and_wrong_scheme_are_audited_and_denied() -> None:
    fixture = WorkloadFixture()
    with TestClient(fixture.app) as client:
        csrf = login(client)
        token = create_identity(client, csrf).json()["data"]["token"]
        headers = {
            "Authorization": f"Workload {token}",
            "X-Atlas-Audience": AUDIENCE,
            "X-Atlas-Environment": "environment.test",
        }
        fixture.clock.now -= timedelta(seconds=31)
        future = client.get("/api/v1/workload-identities/current", headers=headers)
        wrong_scheme = client.get(
            "/api/v1/workload-identities/current",
            headers={**headers, "Authorization": f"Bearer {token}"},
        )

    assert future.status_code == wrong_scheme.status_code == 401
    denied = [
        record
        for record in fixture.sink.records
        if record.event_type == "atlas.identity.workload.authentication"
        and record.outcome == "denied"
    ]
    assert len(denied) == 2
    assert all("atlas_wlt_v1" not in repr(record) for record in denied)


def test_rotation_has_bounded_overlap_then_retires_old_credential() -> None:
    fixture = WorkloadFixture()
    with TestClient(fixture.app) as client:
        csrf = login(client)
        first = create_identity(client, csrf).json()["data"]
        rotated = client.post(
            f"/api/v1/workload-identities/{IDENTITY_ID}/rotations",
            json={
                "expected_version": first["identity"]["version"],
                "lifetime_minutes": 10,
                "overlap_minutes": 2,
                "reason": "Rotate the scheduler credential on schedule.",
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "workload-rotate-0001"},
        )
        assert rotated.status_code == 201
        second = rotated.json()["data"]
        common = {
            "X-Atlas-Audience": AUDIENCE,
            "X-Atlas-Environment": "environment.test",
        }
        old_during_overlap = client.get(
            "/api/v1/workload-identities/current",
            headers={**common, "Authorization": f"Workload {first['token']}"},
        )
        fixture.clock.now += timedelta(minutes=3)
        old_after_overlap = client.get(
            "/api/v1/workload-identities/current",
            headers={**common, "Authorization": f"Workload {first['token']}"},
        )
        new_after_overlap = client.get(
            "/api/v1/workload-identities/current",
            headers={**common, "Authorization": f"Workload {second['token']}"},
        )

    assert old_during_overlap.status_code == 200
    assert old_after_overlap.status_code == 401
    assert new_after_overlap.status_code == 200
    assert second["credential"]["credential_id"] != first["credential"]["credential_id"]


def test_concurrent_rotations_allow_only_one_expected_version() -> None:
    fixture = WorkloadFixture()

    async def rotate_concurrently() -> list[object]:
        created = await fixture.service.create(
            actor=fixture.admin,
            identity_id=IDENTITY_ID,
            display_name="Health scheduler",
            service_id="service.health-scheduler",
            instance_id="instance.health-scheduler.local-01",
            owner_subject_id="subject.enterprise.platform-owner",
            purpose="Run bounded Atlas health-check coordination.",
            audiences=(AUDIENCE,),
            secret_reference_ids=("secret.connector.health-readonly",),
            lifetime=timedelta(minutes=10),
            reason="Create the dedicated health scheduler workload identity.",
            idempotency_key="workload-create-concurrent",
            correlation_id="correlation.workload.concurrent.create",
        )
        calls = (
            fixture.service.rotate(
                IDENTITY_ID,
                actor=fixture.admin,
                expected_version=created.identity.version,
                lifetime=timedelta(minutes=10),
                overlap=timedelta(minutes=2),
                reason="Rotate concurrently to verify optimistic locking.",
                idempotency_key=f"workload-rotate-concurrent-{index}",
                correlation_id=f"correlation.workload.concurrent.{index}",
            )
            for index in range(2)
        )
        return list(await asyncio.gather(*calls, return_exceptions=True))

    results = asyncio.run(rotate_concurrently())

    assert sum(not isinstance(item, Exception) for item in results) == 1
    failures = [item for item in results if isinstance(item, WorkloadIdentityError)]
    assert len(failures) == 1
    assert failures[0].code == "workload_identity_unavailable"


def test_revocation_is_immediate_idempotent_and_conflict_safe() -> None:
    fixture = WorkloadFixture()
    with TestClient(fixture.app) as client:
        csrf = login(client)
        created = create_identity(client, csrf).json()["data"]
        credential = created["credential"]
        request = {
            "expected_version": credential["version"],
            "reason": "Retire the scheduler instance immediately.",
        }
        headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "workload-revoke-0001"}
        first = client.post(
            f"/api/v1/workload-identities/credentials/{credential['credential_id']}/revocations",
            json=request,
            headers=headers,
        )
        replay = client.post(
            f"/api/v1/workload-identities/credentials/{credential['credential_id']}/revocations",
            json=request,
            headers=headers,
        )
        conflict = client.post(
            f"/api/v1/workload-identities/credentials/{credential['credential_id']}/revocations",
            json={**request, "reason": "A conflicting reason."},
            headers=headers,
        )
        authentication = client.get(
            "/api/v1/workload-identities/current",
            headers={
                "Authorization": f"Workload {created['token']}",
                "X-Atlas-Audience": AUDIENCE,
                "X-Atlas-Environment": "environment.test",
            },
        )

    assert first.status_code == replay.status_code == 200
    assert first.json()["data"] == replay.json()["data"]
    assert conflict.status_code == 409
    assert authentication.status_code == 401


def test_admin_mutations_require_csrf_browser_session_and_exact_role() -> None:
    fixture = WorkloadFixture()
    with TestClient(fixture.app) as client:
        csrf = login(client)
        missing_csrf = client.post(
            "/api/v1/workload-identities",
            json=create_payload(),
            headers={"Idempotency-Key": "workload-no-csrf-0001"},
        )
        client.delete(
            "/api/v1/authentication/sessions/current",
            headers={"X-CSRF-Token": csrf},
        )
        login(client, "operator")
        ordinary = client.get("/api/v1/workload-identities")

    assert missing_csrf.status_code == 403
    assert ordinary.status_code == 403


def test_create_rejects_duplicate_audiences_and_non_opaque_secrets() -> None:
    fixture = WorkloadFixture()
    with TestClient(fixture.app) as client:
        csrf = login(client)
        duplicate_payload = create_payload()
        duplicate_payload["audiences"] = [AUDIENCE, AUDIENCE]
        duplicate = client.post(
            "/api/v1/workload-identities",
            json=duplicate_payload,
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "workload-invalid-duplicate"},
        )
        raw_secret_payload = create_payload()
        raw_secret_payload["secret_reference_ids"] = ["super-secret-password"]
        raw_secret = client.post(
            "/api/v1/workload-identities",
            json=raw_secret_payload,
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "workload-invalid-secret"},
        )

    assert duplicate.status_code == raw_secret.status_code == 422
    assert fixture.repository._identities == {}
    assert fixture.repository._credentials == {}


def test_audit_failure_compensates_created_identity_and_credential() -> None:
    fixture = WorkloadFixture(CollectingAuditSink("atlas.identity.workload.created"))
    with TestClient(fixture.app, raise_server_exceptions=False) as client:
        csrf = login(client)
        failed = create_identity(client, csrf)

    assert failed.status_code == 500
    assert fixture.repository._identities == {}
    assert fixture.repository._credentials == {}
    assert any(
        record.event_type == "atlas.identity.workload.creation_compensated"
        and record.outcome == "failed"
        for record in fixture.sink.records
    )
