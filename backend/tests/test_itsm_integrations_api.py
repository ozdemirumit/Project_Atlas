from __future__ import annotations

import base64
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.capabilities import CapabilityClass
from atlas.core.config import Settings
from atlas.modules.authorization.application.bootstrap import (
    itsm_integration_permission_definitions,
    itsm_integration_scope,
)
from atlas.modules.authorization.application.service import AuthorizationService
from atlas.modules.authorization.domain.models import RoleAssignment, RoleDefinition
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationInput,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.itsm.adapters.memory import InMemoryItsmIntegrationProfileRepository
from atlas.modules.itsm.adapters.onboarding import (
    DeterministicDevelopmentItsmSandboxOnboardingEvidenceSource,
)
from atlas.modules.itsm.adapters.sandbox import (
    DeterministicNoNetworkItsmSandboxConformanceAdapter,
)
from atlas.modules.itsm.application.service import ItsmIntegrationService

NOW = datetime(2026, 8, 13, 5, 0, tzinfo=UTC)
ORGANIZATION_ID = "organization.enterprise"
ROLE_ID = "role.itsm-integration-administrator"


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


class EnterpriseProvider:
    def __init__(self, subject: AuthenticatedSubject) -> None:
        self.subject = subject

    async def authenticate(
        self, authentication_input: AuthenticationInput
    ) -> AuthenticatedSubject | None:
        if (
            authentication_input.authorization_scheme != "basic"
            or authentication_input.credential is None
        ):
            return None
        decoded = base64.b64decode(authentication_input.credential).decode()
        return self.subject if decoded == "itsm-admin:correct-password" else None


def subject(*, roles: tuple[str, ...] = (ROLE_ID,)) -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id="subject.enterprise.itsm-admin",
        display_name="ITSM Integration Administrator",
        kind=SubjectKind.HUMAN,
        provider_id="provider.ldap.enterprise",
        authentication_method=AuthenticationMethod.LDAP,
        assurance_level=AssuranceLevel.MULTI_FACTOR,
        authenticated_at=NOW,
        organization_id=ORGANIZATION_ID,
        role_ids=roles,
    )


def authorization(sink: CollectingAuditSink) -> AuthorizationService:
    permissions = itsm_integration_permission_definitions()
    role = RoleDefinition(
        role_id=ROLE_ID,
        version=1,
        permissions=frozenset(item.permission_id for item in permissions),
    )
    return AuthorizationService(
        permissions=permissions,
        roles=(role,),
        assignments=tuple(
            RoleAssignment(
                assignment_id=f"assignment.itsm-admin.{index}",
                version=1,
                subject_id="subject.enterprise.itsm-admin",
                role_id=ROLE_ID,
                scope=itsm_integration_scope(ORGANIZATION_ID, "test", capability_class),
                valid_from=datetime.min.replace(tzinfo=UTC),
            )
            for index, capability_class in enumerate(
                (CapabilityClass.C1_READ_ONLY, CapabilityClass.C2_DIAGNOSTIC), start=1
            )
        ),
        audit_sink=sink,
        clock=lambda: NOW,
    )


class ItsmFixture:
    def __init__(self, *, roles: tuple[str, ...] = (ROLE_ID,)) -> None:
        self.sink = CollectingAuditSink()
        self.repository = InMemoryItsmIntegrationProfileRepository()
        self.service = ItsmIntegrationService(
            repository=self.repository,
            audit_sink=self.sink,
            environment_id="environment.test",
            sandbox_conformance_adapter=DeterministicNoNetworkItsmSandboxConformanceAdapter(),
            sandbox_onboarding_evidence_source=(
                DeterministicDevelopmentItsmSandboxOnboardingEvidenceSource()
            ),
            clock=lambda: NOW,
        )
        self.app = create_app(
            Settings(environment="test", development_identity_enabled=False),
            audit_sink=self.sink,
            identity_provider=EnterpriseProvider(subject(roles=roles)),
            authorization_service=authorization(self.sink),
            itsm_integration_service=self.service,
        )


def login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/authentication/sessions",
        json={"username": "itsm-admin", "password": "correct-password"},
    )
    assert response.status_code == 201
    return str(response.headers["X-CSRF-Token"])


def create_payload(*, sandbox_evidence: bool = False) -> dict[str, object]:
    return {
        "schema_version": "atlas.itsm-integration-profile-create-input.v1",
        "profile_key": "itsm.sandbox.primary",
        "display_name": "Primary ITSM sandbox",
        "provider_family": "generic_rest",
        "instance_reference": "itsm-instance.sandbox.primary",
        "owner_id": "team.service-management",
        "purpose": "Validate governed report handoff mappings in an isolated ITSM sandbox.",
        "endpoint_origin": "https://itsm-sandbox.example.invalid",
        "trust_boundary_reference": "trust-boundary.itsm.sandbox",
        "secret_reference_id": "secret.itsm.sandbox.writer",
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
        "sandbox_validation_reference": (
            "validation.itsm.sandbox.001" if sandbox_evidence else None
        ),
        "sandbox_validation_digest": "a" * 64 if sandbox_evidence else None,
        "audit_profile_id": "audit-profile.itsm.sandbox",
        "acknowledged_configuration_only": True,
    }


def test_itsm_profile_requires_authorized_browser_session() -> None:
    fixture = ItsmFixture()
    basic = base64.b64encode(b"itsm-admin:correct-password").decode()
    with TestClient(fixture.app) as client:
        unauthenticated = client.get("/api/v1/itsm/integrations")
        direct = client.post(
            "/api/v1/itsm/integrations",
            json=create_payload(),
            headers={"Authorization": f"Basic {basic}", "Idempotency-Key": "itsm-direct-1"},
        )
    assert unauthenticated.status_code == 401
    assert direct.status_code == 403
    assert direct.json()["code"] == "browser_session_required"

    denied_fixture = ItsmFixture(roles=())
    with TestClient(denied_fixture.app) as client:
        login(client)
        denied = client.get("/api/v1/itsm/integrations")
    assert denied.status_code == 403
    assert denied.json()["code"] == "authorization_denied"


def test_profile_inventory_is_secret_free_and_never_grants_authority() -> None:
    fixture = ItsmFixture()
    with TestClient(fixture.app) as client:
        csrf = login(client)
        created = client.post(
            "/api/v1/itsm/integrations",
            json=create_payload(sandbox_evidence=True),
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "itsm-create-0001"},
        )
        inventory = client.get("/api/v1/itsm/integrations?lifecycle=active")
    assert created.status_code == 201
    assert created.headers["Cache-Control"] == "no-store"
    profile = created.json()["data"]
    assert profile["credential_reference_configured"] is True
    assert profile["readiness"]["state"] == "ready_for_sandbox"
    assert all(
        profile["readiness"][field] is False
        for field in (
            "dispatch_authorized",
            "external_record_mutation_authorized",
            "workflow_approved",
            "execution_authorized",
        )
    )
    assert "secret_reference_id" not in created.text
    assert "secret.itsm.sandbox.writer" not in created.text
    assert "idempotency" not in created.text
    assert inventory.status_code == 200
    assert inventory.headers["Cache-Control"] == "no-store"
    assert inventory.json()["data"]["profiles"][0]["profile_id"] == profile["profile_id"]


def test_create_is_idempotent_and_retirement_is_version_bound() -> None:
    fixture = ItsmFixture()
    with TestClient(fixture.app) as client:
        csrf = login(client)
        headers = {"X-CSRF-Token": csrf, "Idempotency-Key": "itsm-create-0002"}
        first = client.post("/api/v1/itsm/integrations", json=create_payload(), headers=headers)
        replay = client.post("/api/v1/itsm/integrations", json=create_payload(), headers=headers)
        profile = first.json()["data"]
        stale = client.post(
            f"/api/v1/itsm/integrations/{profile['profile_id']}/retirements",
            json={
                "schema_version": "atlas.itsm-integration-profile-retirement-input.v1",
                "expected_version": 9,
                "reason": "Retire the sandbox profile after replacing its mapping contract.",
                "acknowledged_history_preserved_and_dispatch_absent": True,
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "itsm-retire-stale"},
        )
        retired = client.post(
            f"/api/v1/itsm/integrations/{profile['profile_id']}/retirements",
            json={
                "schema_version": "atlas.itsm-integration-profile-retirement-input.v1",
                "expected_version": 1,
                "reason": "Retire the sandbox profile after replacing its mapping contract.",
                "acknowledged_history_preserved_and_dispatch_absent": True,
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "itsm-retire-0001"},
        )
        inventory = client.get("/api/v1/itsm/integrations?lifecycle=retired")
    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.json()["data"]["reused"] is True
    assert stale.status_code == 409
    assert stale.json()["code"] == "itsm_integration_version_conflict"
    assert retired.status_code == 200
    assert retired.json()["data"]["lifecycle"] == "retired"
    assert inventory.status_code == 200
    assert {item.result_code for item in fixture.sink.records} >= {
        "itsm_integration_created",
        "itsm_integration_inventory_read",
        "itsm_integration_retired",
    }


def test_sandbox_conformance_requires_csrf_and_returns_secret_free_evidence() -> None:
    fixture = ItsmFixture()
    with TestClient(fixture.app) as client:
        csrf = login(client)
        created = client.post(
            "/api/v1/itsm/integrations",
            json=create_payload(),
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "itsm-create-conformance"},
        )
        profile = created.json()["data"]
        path = f"/api/v1/itsm/integrations/{profile['profile_id']}/sandbox-conformance-assessments"
        missing_csrf = client.post(
            path,
            json={
                "schema_version": "atlas.itsm-sandbox-conformance-input.v1",
                "expected_profile_version": profile["version"],
                "acknowledged_diagnostic_only_and_no_dispatch": True,
            },
            headers={"Idempotency-Key": "itsm-sandbox-missing-csrf"},
        )
        assessed = client.post(
            path,
            json={
                "schema_version": "atlas.itsm-sandbox-conformance-input.v1",
                "expected_profile_version": profile["version"],
                "acknowledged_diagnostic_only_and_no_dispatch": True,
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "itsm-sandbox-api-0001"},
        )
        replay = client.post(
            path,
            json={
                "schema_version": "atlas.itsm-sandbox-conformance-input.v1",
                "expected_profile_version": profile["version"],
                "acknowledged_diagnostic_only_and_no_dispatch": True,
            },
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "itsm-sandbox-api-0001"},
        )
        latest = client.get(f"{path}/latest")

    assert missing_csrf.status_code == 403
    assert missing_csrf.json()["code"] == "csrf_validation_failed"
    assert assessed.status_code == 201
    assert assessed.headers["Cache-Control"] == "no-store"
    data = assessed.json()["data"]
    assert data["state"] == "conformant"
    assert data["sandbox_conformant"] is True
    assert all(
        data[field] is False
        for field in (
            "production_ready",
            "dispatch_authorized",
            "external_record_mutation_authorized",
            "workflow_approved",
            "execution_authorized",
            "infrastructure_mutation_performed",
        )
    )
    assert replay.status_code == 201
    assert replay.json()["data"]["reused"] is True
    assert latest.status_code == 200
    assert latest.headers["Cache-Control"] == "no-store"
    assert latest.json()["data"]["assessment_id"] == data["assessment_id"]
    assert "secret_reference" not in assessed.text
    assert "endpoint" not in assessed.text
    assert "idempotency" not in assessed.text


def test_sandbox_onboarding_readiness_is_read_only_blocked_and_non_disclosing() -> None:
    fixture = ItsmFixture()
    with TestClient(fixture.app) as client:
        csrf = login(client)
        created = client.post(
            "/api/v1/itsm/integrations",
            json=create_payload(),
            headers={"X-CSRF-Token": csrf, "Idempotency-Key": "itsm-create-onboarding"},
        )
        profile = created.json()["data"]
        assessments = (
            f"/api/v1/itsm/integrations/{profile['profile_id']}/sandbox-conformance-assessments"
        )
        assessed = client.post(
            assessments,
            json={
                "schema_version": "atlas.itsm-sandbox-conformance-input.v1",
                "expected_profile_version": profile["version"],
                "acknowledged_diagnostic_only_and_no_dispatch": True,
            },
            headers={
                "X-CSRF-Token": csrf,
                "Idempotency-Key": "itsm-sandbox-onboarding-api",
            },
        )
        readiness = client.get(
            f"/api/v1/itsm/integrations/{profile['profile_id']}/sandbox-onboarding-readiness"
        )

    assert assessed.status_code == 201
    assert readiness.status_code == 200
    assert readiness.headers["Cache-Control"] == "no-store"
    data = readiness.json()["data"]
    assert data["schema_version"] == "atlas.itsm-sandbox-onboarding-readiness.v1"
    assert data["state"] == "blocked"
    assert data["profile_digest"] == profile["canonical_digest"]
    assert data["conformance_assessment_id"] == assessed.json()["data"]["assessment_id"]
    assert len(data["requirements"]) == 12
    assert all(
        data[field] is False
        for field in (
            "sandbox_onboarding_ready",
            "production_ready",
            "dispatch_authorized",
            "external_record_mutation_authorized",
            "workflow_approved",
            "execution_authorized",
            "infrastructure_mutation_performed",
        )
    )
    assert "secret_reference" not in readiness.text
    assert "endpoint_origin" not in readiness.text
    assert "idempotency" not in readiness.text
    assert fixture.sink.records[-1].permission_id == ("itsm.integrations.sandbox-onboarding.read")
