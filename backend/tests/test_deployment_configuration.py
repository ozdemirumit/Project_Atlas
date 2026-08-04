from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.config import Settings
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.platform.application.deployment_configuration import (
    DeploymentConfigurationScopeError,
    DeploymentConfigurationService,
)
from atlas.modules.platform.domain.deployment_configuration import (
    ConfigurationState,
    ConfigurationValueSource,
    DeploymentConfigurationOverlay,
    DeploymentConfigurationRequest,
    NamedBooleanValue,
    NamedStringValue,
)
from atlas.modules.platform.domain.release_preflight import DeploymentProfile


class CollectingAuditSink:
    def __init__(self, *, fail_preview: bool = False) -> None:
        self.records: list[AuditRecord] = []
        self.fail_preview = fail_preview

    async def record(self, event: AuditRecord) -> None:
        if self.fail_preview and event.event_type.endswith("deployment-configuration.preview"):
            raise RuntimeError("required configuration audit unavailable")
        self.records.append(event)


def actor() -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id="subject.enterprise.platform-operator",
        display_name="Platform Operator",
        kind=SubjectKind.HUMAN,
        provider_id="provider.ldap.enterprise",
        authentication_method=AuthenticationMethod.LDAP,
        assurance_level=AssuranceLevel.MULTI_FACTOR,
        authenticated_at=datetime(2026, 8, 4, 12, 0, tzinfo=UTC),
        organization_id="organization.enterprise",
        role_ids=("role.platform-operator",),
    )


def request(
    *,
    profile: DeploymentProfile = DeploymentProfile.LINUX_LAB,
    overlay: DeploymentConfigurationOverlay | None = None,
) -> DeploymentConfigurationRequest:
    return DeploymentConfigurationRequest(
        schema_version="atlas.deployment-configuration-request.v1",
        release_id="release.atlas.lab-0.1.0",
        profile=profile,
        organization_id="organization.enterprise",
        environment_id="environment.test",
        site_id="site.local",
        overlay=overlay or DeploymentConfigurationOverlay(),
    )


def service(sink: CollectingAuditSink | None = None) -> DeploymentConfigurationService:
    return DeploymentConfigurationService(
        release_id="release.atlas.lab-0.1.0",
        environment_id="environment.test",
        site_id="site.local",
        audit_sink=sink or CollectingAuditSink(),
    )


@pytest.mark.asyncio
async def test_default_preview_is_deterministic_safe_and_read_only() -> None:
    sink = CollectingAuditSink()
    selected_service = service(sink)
    first = await selected_service.preview(
        actor=actor(), request=request(), correlation_id="correlation.configuration.first"
    )
    second = await selected_service.preview(
        actor=actor(), request=request(), correlation_id="correlation.configuration.second"
    )

    assert first.state is ConfigurationState.PASSED
    assert first.configuration_digest == second.configuration_digest
    assert first.mutation_authorized is False
    assert first.execution_authorized is False
    assert all(item.source is ConfigurationValueSource.RELEASE_DEFAULT for item in first.fields)
    assert all("secret.database.atlas" not in item.display_value for item in first.fields)
    assert len(sink.records) == 2


@pytest.mark.asyncio
async def test_reordered_overlay_has_same_digest_and_records_precedence() -> None:
    components = (
        NamedStringValue("component.worker", "registry/worker@sha256:" + "3" * 64),
        NamedStringValue("component.api", "registry/api@sha256:" + "4" * 64),
    )
    first = await service().preview(
        actor=actor(),
        request=request(
            overlay=DeploymentConfigurationOverlay(
                cors_origins=("https://b.example", "https://a.example"),
                component_references=components,
                resource_names=("atlas-worker", "atlas-api"),
            )
        ),
        correlation_id="correlation.configuration.order-one",
    )
    second = await service().preview(
        actor=actor(),
        request=request(
            overlay=DeploymentConfigurationOverlay(
                cors_origins=("https://a.example", "https://b.example"),
                component_references=tuple(reversed(components)),
                resource_names=("atlas-api", "atlas-worker"),
            )
        ),
        correlation_id="correlation.configuration.order-two",
    )

    assert first.configuration_digest == second.configuration_digest
    assert next(item for item in first.fields if item.path == "components").source is (
        ConfigurationValueSource.OVERLAY
    )


@pytest.mark.asyncio
async def test_unsafe_overlay_fails_without_disclosing_secret_or_url_credentials() -> None:
    raw_secret = "top-secret-value"
    preview = await service().preview(
        actor=actor(),
        request=request(
            overlay=DeploymentConfigurationOverlay(
                api_bind="0.0.0.0",
                public_url="https://operator:password@atlas.invalid/?token=value",
                cors_origins=("https://atlas.invalid", "https://atlas.invalid"),
                component_references=(
                    NamedStringValue("component.backend", "registry/backend:latest"),
                ),
                feature_flags=(NamedBooleanValue("feature.autonomous-execution", True),),
                integration_endpoints=(
                    NamedStringValue(
                        "integration.model", "https://reader:password@model.invalid/v1"
                    ),
                ),
                resource_names=("atlas-api", "atlas-api"),
                secret_references=(NamedStringValue("secret.database", raw_secret),),
            )
        ),
        correlation_id="correlation.configuration.unsafe",
    )

    assert preview.state is ConfigurationState.FAILED
    assert sum(item.state is ConfigurationState.FAILED for item in preview.validations) == 8
    assert raw_secret not in repr(preview)
    assert "password" not in repr(preview)
    assert next(item for item in preview.fields if item.path == "api.public_url").display_value == (
        "<invalid-url>"
    )

    alternate = await service().preview(
        actor=actor(),
        request=request(
            overlay=DeploymentConfigurationOverlay(
                api_bind="0.0.0.0",
                public_url="https://different:credential@atlas.invalid/?token=other",
                cors_origins=("https://atlas.invalid", "https://atlas.invalid"),
                component_references=(
                    NamedStringValue("component.backend", "registry/backend:latest"),
                ),
                feature_flags=(NamedBooleanValue("feature.autonomous-execution", True),),
                integration_endpoints=(
                    NamedStringValue("integration.model", "https://other:secret@model.invalid/v1"),
                ),
                resource_names=("atlas-api", "atlas-api"),
                secret_references=(NamedStringValue("secret.database", "different-raw-secret"),),
            )
        ),
        correlation_id="correlation.configuration.unsafe-alternate",
    )
    assert alternate.configuration_digest == preview.configuration_digest


@pytest.mark.asyncio
async def test_foreign_scope_fails_closed_and_is_audited() -> None:
    sink = CollectingAuditSink()
    with pytest.raises(DeploymentConfigurationScopeError):
        await service(sink).preview(
            actor=actor(),
            request=replace(request(), environment_id="environment.foreign"),
            correlation_id="correlation.configuration.foreign",
        )

    assert sink.records[-1].outcome == "denied"
    assert sink.records[-1].scope_reference == "scope.redacted"


def api_payload() -> dict[str, object]:
    return {
        "schema_version": "atlas.deployment-configuration-request.v1",
        "release_id": "release.atlas.lab-0.1.0",
        "profile": "linux_lab",
        "organization_id": "organization.development",
        "environment_id": "environment.test",
        "site_id": "site.local",
        "overlay": {},
    }


def test_authorized_api_returns_redacted_preview_and_required_audit() -> None:
    sink = CollectingAuditSink()
    app = create_app(
        Settings(environment="test", development_identity_enabled=True), audit_sink=sink
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/platform/deployment-configuration/preview", json=api_payload()
        )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["state"] == "passed"
    assert data["mutation_authorized"] is False
    assert data["execution_authorized"] is False
    assert "secret.database.atlas" not in response.text
    assert any(
        item.event_type.endswith("deployment-configuration.preview") for item in sink.records
    )


def test_api_rejects_unknown_fields_and_missing_exact_assignment() -> None:
    authorized = create_app(Settings(environment="test", development_identity_enabled=True))
    malformed = api_payload()
    malformed["unexpected"] = True
    with TestClient(authorized) as client:
        malformed_response = client.post(
            "/api/v1/platform/deployment-configuration/preview", json=malformed
        )
    assert malformed_response.status_code == 422

    malformed_nested = api_payload()
    malformed_nested["overlay"] = {
        "integration_endpoints": [{"name": "INVALID NAME", "value": "https://model.invalid"}]
    }
    with TestClient(authorized) as client:
        malformed_nested_response = client.post(
            "/api/v1/platform/deployment-configuration/preview", json=malformed_nested
        )
    assert malformed_nested_response.status_code == 422
    assert "INVALID NAME" not in malformed_nested_response.text

    denied = create_app(
        Settings(environment="test", development_identity_enabled=True, development_role_ids=())
    )
    with TestClient(denied) as client:
        denied_response = client.post(
            "/api/v1/platform/deployment-configuration/preview", json=api_payload()
        )
    assert denied_response.status_code == 403
    assert "configuration_digest" not in denied_response.text


def test_foreign_api_scope_and_required_audit_failure_disclose_no_preview() -> None:
    sink = CollectingAuditSink()
    selected_service = service(sink)
    app = create_app(
        Settings(environment="test", development_identity_enabled=True),
        audit_sink=sink,
        deployment_configuration_service=selected_service,
    )
    foreign = api_payload()
    foreign["organization_id"] = "organization.foreign"
    with TestClient(app) as client:
        response = client.post("/api/v1/platform/deployment-configuration/preview", json=foreign)
    assert response.status_code == 403
    assert "configuration_digest" not in response.text

    failing_sink = CollectingAuditSink(fail_preview=True)
    failing_app = create_app(
        Settings(environment="test", development_identity_enabled=True),
        audit_sink=failing_sink,
        deployment_configuration_service=service(failing_sink),
    )
    with TestClient(failing_app, raise_server_exceptions=False) as client:
        failed_response = client.post(
            "/api/v1/platform/deployment-configuration/preview", json=api_payload()
        )
    assert failed_response.status_code == 500
    assert "configuration_digest" not in failed_response.text
