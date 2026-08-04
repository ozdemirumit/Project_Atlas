from __future__ import annotations

import asyncio
import base64
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.config import Settings
from atlas.modules.authorization.application.bootstrap import (
    STORAGE_OVERVIEW_READ,
    personal_api_grant_catalog,
)
from atlas.modules.health_checks.adapters.synthetic import CONTROLLER_DEFINITION_ID
from atlas.modules.identity.adapters.api_credentials import InMemoryApiCredentialRepository
from atlas.modules.identity.application.api_credentials import (
    ApiCredentialOperationsError,
    ApiCredentialService,
)
from atlas.modules.identity.domain.api_credentials import ApiCredentialState
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationInput,
    AuthenticationMethod,
    SubjectKind,
)

NOW = datetime(2026, 8, 4, 14, 0, tzinfo=UTC)


class MutableClock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


class SelectiveFailingAuditSink(CollectingAuditSink):
    def __init__(self, event_types: set[str]) -> None:
        super().__init__()
        self._event_types = event_types

    async def record(self, event: AuditRecord) -> None:
        if event.event_type in self._event_types:
            raise RuntimeError("API credential audit unavailable")
        await super().record(event)


class BasicTestIdentityProvider:
    def __init__(self, authenticated_subject: AuthenticatedSubject | None = None) -> None:
        self.calls = 0
        self._subject = authenticated_subject or subject()

    async def authenticate(
        self, authentication_input: AuthenticationInput
    ) -> AuthenticatedSubject | None:
        self.calls += 1
        if authentication_input.authorization_scheme != "basic":
            return None
        credential = authentication_input.credential
        if credential is None:
            return None
        try:
            decoded = base64.b64decode(credential, validate=True).decode()
        except ValueError:
            return None
        return self._subject if decoded == "operator:correct-password" else None


def subject(subject_id: str = "subject.development.operator") -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id=subject_id,
        display_name="API Operator",
        kind=SubjectKind.HUMAN,
        provider_id="provider.ldap.test",
        authentication_method=AuthenticationMethod.LDAP,
        assurance_level=AssuranceLevel.SINGLE_FACTOR,
        authenticated_at=NOW,
        organization_id="organization.development",
        role_ids=("role.development.operator",),
    )


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "development_identity_enabled": True,
        "session_absolute_timeout_minutes": 60,
        "session_idle_timeout_minutes": 15,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/authentication/sessions",
        json={"username": "operator", "password": "correct-password"},
    )
    assert response.status_code == 201
    return str(response.headers["X-CSRF-Token"])


def service_fixture(
    *,
    sink: CollectingAuditSink | None = None,
    clock: MutableClock | None = None,
    max_active: int = 10,
) -> tuple[
    ApiCredentialService,
    InMemoryApiCredentialRepository,
    CollectingAuditSink,
    MutableClock,
]:
    resolved_sink = sink or CollectingAuditSink()
    resolved_clock = clock or MutableClock()
    repository = InMemoryApiCredentialRepository()
    sequence = iter(range(1, 100))
    service = ApiCredentialService(
        repository=repository,
        audit_sink=resolved_sink,
        max_active_per_subject=max_active,
        clock=resolved_clock,
        token_factory=lambda: f"atlas_pat_{next(sequence):043d}",
    )
    return service, repository, resolved_sink, resolved_clock


def create_payload() -> dict[str, object]:
    return {
        "display_name": "Read-only operations client",
        "purpose": "Retrieve the bounded storage overview from an operator workstation.",
        "expires_in_minutes": 30,
        "permission_ids": [STORAGE_OVERVIEW_READ],
    }


def test_browser_issuance_discloses_token_once_and_persists_only_digest() -> None:
    sink = CollectingAuditSink()
    service, repository, _, _ = service_fixture(sink=sink)
    with TestClient(
        create_app(
            settings(),
            identity_provider=BasicTestIdentityProvider(),
            audit_sink=sink,
            api_credential_service=service,
        )
    ) as client:
        csrf = login(client)
        missing_csrf = client.post("/api/v1/authentication/api-credentials", json=create_payload())
        created = client.post(
            "/api/v1/authentication/api-credentials",
            json=create_payload(),
            headers={"X-CSRF-Token": csrf},
        )
        inventory = client.get("/api/v1/authentication/api-credentials")

    assert missing_csrf.status_code == 403
    assert created.status_code == 201
    assert created.headers["Cache-Control"] == "no-store"
    token = created.json()["data"]["token"]
    credential_id = created.json()["data"]["credential_id"]
    assert token.startswith("atlas_pat_")
    assert inventory.status_code == 200
    assert inventory.headers["Cache-Control"] == "no-store"
    assert token not in inventory.text
    assert "token_digest" not in inventory.text
    assert inventory.json()["data"]["credentials"][0]["grants"][0]["permission_id"] == (
        STORAGE_OVERVIEW_READ
    )
    stored = asyncio.run(repository.get_by_id(credential_id))
    assert stored is not None
    assert len(stored.token_digest) == 64
    assert token not in repr(stored)
    assert [item.event_type for item in sink.records].count(
        "atlas.identity.api_credential.issued"
    ) == 1


def test_bearer_read_requires_exact_credential_grant_and_current_rbac() -> None:
    sink = CollectingAuditSink()
    provider = BasicTestIdentityProvider()
    service, _, _, _ = service_fixture(sink=sink)
    with TestClient(
        create_app(
            settings(),
            identity_provider=provider,
            audit_sink=sink,
            api_credential_service=service,
        )
    ) as client:
        csrf = login(client)
        created = client.post(
            "/api/v1/authentication/api-credentials",
            json=create_payload(),
            headers={"X-CSRF-Token": csrf},
        )
        token = created.json()["data"]["token"]
        ambiguous = client.get(
            "/api/v1/storage/overview",
            headers={"Authorization": f"Bearer {token}"},
        )
        client.cookies.clear()
        storage = client.get(
            "/api/v1/storage/overview",
            headers={"Authorization": f"Bearer {token}"},
        )
        identity = client.get(
            "/api/v1/identity/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        unsafe = client.post(
            f"/api/v1/health-checks/{CONTROLLER_DEFINITION_ID}/runs",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert ambiguous.status_code == 400
    assert ambiguous.json()["code"] == "ambiguous_authentication"
    assert storage.status_code == 200
    assert storage.headers["Cache-Control"] == "no-store"
    assert identity.status_code == 403
    assert identity.json()["code"] == "authorization_denied"
    assert unsafe.status_code == 403
    assert unsafe.json()["code"] == "credential_unsafe_method_denied"
    assert provider.calls == 1
    assert any(item.result_code == "credential_scope_denied" for item in sink.records)
    assert any(
        item.authentication_method == AuthenticationMethod.API_TOKEN.value
        for item in sink.records
        if item.event_type == "atlas.identity.api_credential.authenticated"
    )


def test_invalid_bearer_never_falls_back_to_identity_provider() -> None:
    provider = BasicTestIdentityProvider()
    sink = CollectingAuditSink()
    service, _, _, _ = service_fixture(sink=sink)
    with TestClient(
        create_app(
            settings(),
            identity_provider=provider,
            audit_sink=sink,
            api_credential_service=service,
        )
    ) as client:
        response = client.get(
            "/api/v1/storage/overview",
            headers={"Authorization": "Bearer atlas_pat_invalid"},
        )

    assert response.status_code == 401
    assert provider.calls == 0
    assert "atlas_pat_invalid" not in repr(sink.records)
    assert sink.records[-1].result_code == "credential_unknown"


def test_token_grant_cannot_replace_a_missing_current_role_assignment() -> None:
    sink = CollectingAuditSink()
    service, _, _, _ = service_fixture(sink=sink)
    grant = personal_api_grant_catalog("organization.development", "test")[STORAGE_OVERVIEW_READ]
    issued = asyncio.run(
        service.issue(
            subject=subject("subject.enterprise.unassigned"),
            display_name="Former operator client",
            purpose="Verify current RBAC remains authoritative",
            lifetime=timedelta(minutes=30),
            grants=(grant,),
            correlation_id="cor_unassigned_issue",
        )
    )
    with TestClient(
        create_app(
            settings(),
            identity_provider=BasicTestIdentityProvider(),
            audit_sink=sink,
            api_credential_service=service,
        )
    ) as client:
        response = client.get(
            "/api/v1/storage/overview",
            headers={"Authorization": f"Bearer {issued.token}"},
        )

    assert response.status_code == 403
    assert response.json()["code"] == "authorization_denied"
    assert any(item.result_code == "no_matching_assignment" for item in sink.records)


def test_browser_can_revoke_credential_and_repeated_or_bearer_management_fails_closed() -> None:
    sink = CollectingAuditSink()
    service, _, _, _ = service_fixture(sink=sink)
    with TestClient(
        create_app(
            settings(),
            identity_provider=BasicTestIdentityProvider(),
            audit_sink=sink,
            api_credential_service=service,
        )
    ) as client:
        csrf = login(client)
        created = client.post(
            "/api/v1/authentication/api-credentials",
            json=create_payload(),
            headers={"X-CSRF-Token": csrf},
        )
        token = created.json()["data"]["token"]
        credential_id = created.json()["data"]["credential_id"]
        bearer_management = client.get(
            "/api/v1/authentication/api-credentials",
            headers={"Authorization": f"Bearer {token}"},
        )
        revoked = client.delete(
            f"/api/v1/authentication/api-credentials/{credential_id}",
            headers={"X-CSRF-Token": csrf},
        )
        repeated = client.delete(
            f"/api/v1/authentication/api-credentials/{credential_id}",
            headers={"X-CSRF-Token": csrf},
        )
        client.cookies.clear()
        after_revoke = client.get(
            "/api/v1/storage/overview",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert bearer_management.status_code == 400
    assert revoked.status_code == 204
    assert repeated.status_code == 404
    assert after_revoke.status_code == 401
    assert token not in repr(sink.records)


@pytest.mark.asyncio
async def test_service_enforces_lifetime_count_expiry_and_subject_isolation() -> None:
    service, repository, _, clock = service_fixture(max_active=1)
    grant = personal_api_grant_catalog("organization.development", "test")[STORAGE_OVERVIEW_READ]
    with pytest.raises(ApiCredentialOperationsError, match="credential_lifetime_invalid"):
        await service.issue(
            subject=subject(),
            display_name="Too long",
            purpose="Invalid lifetime",
            lifetime=timedelta(minutes=61),
            grants=(grant,),
            correlation_id="cor_invalid_lifetime",
        )
    issued = await service.issue(
        subject=subject(),
        display_name="Bounded client",
        purpose="Read one exact storage scope",
        lifetime=timedelta(minutes=5),
        grants=(grant,),
        correlation_id="cor_issue",
    )
    with pytest.raises(ApiCredentialOperationsError, match="credential_limit_exceeded"):
        await service.issue(
            subject=subject(),
            display_name="Second client",
            purpose="Exceeds the active count",
            lifetime=timedelta(minutes=5),
            grants=(grant,),
            correlation_id="cor_limit",
        )
    foreign = replace(subject(), subject_id="subject.enterprise.foreign")
    with pytest.raises(ApiCredentialOperationsError, match="credential_not_found"):
        await service.revoke(
            issued.record.credential_id,
            subject_id=foreign.subject_id,
            correlation_id="cor_foreign",
        )
    clock.now = NOW + timedelta(minutes=5)
    assert (
        await service.authenticate(
            issued.token,
            unsafe_request=False,
            correlation_id="cor_expired",
        )
        is None
    )
    stored = await repository.get_by_id(issued.record.credential_id)
    assert stored is not None and stored.state is ApiCredentialState.EXPIRED


@pytest.mark.asyncio
async def test_stale_update_cannot_resurrect_revoked_credential() -> None:
    service, repository, _, _ = service_fixture()
    grant = personal_api_grant_catalog("organization.development", "test")[STORAGE_OVERVIEW_READ]
    issued = await service.issue(
        subject=subject(),
        display_name="Race client",
        purpose="Exercise optimistic concurrency",
        lifetime=timedelta(minutes=30),
        grants=(grant,),
        correlation_id="cor_race_issue",
    )
    original = issued.record
    revoked = replace(
        original,
        version=2,
        state=ApiCredentialState.REVOKED,
        revoked_at=NOW,
        revocation_reason="self_service_revocation",
    )
    stale_touch = replace(original, version=2, last_used_at=NOW + timedelta(seconds=1))

    assert await repository.update(revoked, expected_version=1) is True
    assert await repository.update(stale_touch, expected_version=1) is False
    stored = await repository.get_by_id(original.credential_id)
    assert stored is not None and stored.state is ApiCredentialState.REVOKED


def test_required_audit_failure_blocks_issuance_inventory_and_revocation() -> None:
    sink = SelectiveFailingAuditSink({"atlas.identity.api_credential.issued"})
    service, repository, _, _ = service_fixture(sink=sink)
    with TestClient(
        create_app(
            settings(),
            identity_provider=BasicTestIdentityProvider(),
            audit_sink=sink,
            api_credential_service=service,
        ),
        raise_server_exceptions=False,
    ) as client:
        csrf = login(client)
        response = client.post(
            "/api/v1/authentication/api-credentials",
            json=create_payload(),
            headers={"X-CSRF-Token": csrf},
        )

    assert response.status_code == 500
    assert asyncio.run(repository.for_subject(subject().subject_id)) == ()
    assert "atlas_pat_" not in response.text


def test_required_authentication_audit_failure_blocks_bearer_request() -> None:
    sink = SelectiveFailingAuditSink(set())
    service, _, _, _ = service_fixture(sink=sink)
    grant = personal_api_grant_catalog("organization.development", "test")[STORAGE_OVERVIEW_READ]
    issued = asyncio.run(
        service.issue(
            subject=subject(),
            display_name="Audited bearer",
            purpose="Verify required authentication audit",
            lifetime=timedelta(minutes=30),
            grants=(grant,),
            correlation_id="cor_auth_audit_issue",
        )
    )
    sink._event_types = {"atlas.identity.api_credential.authenticated"}
    with TestClient(
        create_app(
            settings(),
            identity_provider=BasicTestIdentityProvider(),
            audit_sink=sink,
            api_credential_service=service,
        ),
        raise_server_exceptions=False,
    ) as client:
        response = client.get(
            "/api/v1/storage/overview",
            headers={"Authorization": f"Bearer {issued.token}"},
        )

    assert response.status_code == 500
    assert "storage" not in response.text.lower()


@pytest.mark.asyncio
async def test_lifecycle_audit_failures_block_protected_results_and_mutations() -> None:
    grant = personal_api_grant_catalog("organization.development", "test")[STORAGE_OVERVIEW_READ]
    sink = SelectiveFailingAuditSink(set())
    service, repository, _, _ = service_fixture(sink=sink)
    issued = await service.issue(
        subject=subject(),
        display_name="Audit client",
        purpose="Exercise required lifecycle audit",
        lifetime=timedelta(minutes=30),
        grants=(grant,),
        correlation_id="cor_audit_issue",
    )
    sink._event_types = {"atlas.identity.api_credential.inventory_read"}
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await service.inventory(subject().subject_id, correlation_id="cor_audit_inventory")
    sink._event_types = {"atlas.identity.api_credential.revoked"}
    with pytest.raises(RuntimeError, match="audit unavailable"):
        await service.revoke(
            issued.record.credential_id,
            subject_id=subject().subject_id,
            correlation_id="cor_audit_revoke",
        )
    stored = await repository.get_by_id(issued.record.credential_id)
    assert stored is not None and stored.state is ApiCredentialState.ACTIVE
