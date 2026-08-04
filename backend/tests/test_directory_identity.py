from __future__ import annotations

import base64
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.config import DirectoryGroupMappingSetting, Settings
from atlas.modules.identity.adapters.directory import (
    FailoverDirectoryClient,
    Ldap3EndpointAuthenticator,
)
from atlas.modules.identity.application.directory import (
    DirectoryCredentialRejected,
    DirectoryEndpointUnavailable,
    DirectoryIdentityProvider,
    DirectoryUnavailable,
)
from atlas.modules.identity.application.service import IdentityService
from atlas.modules.identity.domain.directory import (
    DirectoryEndpoint,
    DirectoryGroupMapping,
    DirectoryProviderProfile,
    DirectoryUserRecord,
)
from atlas.modules.identity.domain.models import AuthenticationInput, IdentityProviderFailure

NOW = datetime(2026, 8, 4, 12, 0, tzinfo=UTC)


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


class StaticDirectoryClient:
    def __init__(self, result: DirectoryUserRecord | None) -> None:
        self.result = result
        self.calls = 0
        self.password_lengths: list[int] = []

    async def authenticate(self, username: str, password: str) -> DirectoryUserRecord | None:
        self.calls += 1
        self.password_lengths.append(len(password))
        return self.result


class ScriptedEndpointAuthenticator:
    def __init__(self, outcomes: dict[str, DirectoryUserRecord | Exception]) -> None:
        self.outcomes = outcomes
        self.endpoint_calls: list[str] = []

    def authenticate(
        self,
        profile: DirectoryProviderProfile,
        endpoint: DirectoryEndpoint,
        username: str,
        password: str,
    ) -> DirectoryUserRecord:
        self.endpoint_calls.append(endpoint.endpoint_id)
        outcome = self.outcomes[endpoint.endpoint_id]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def profile(
    *,
    endpoints: tuple[DirectoryEndpoint, ...] | None = None,
    mappings: tuple[DirectoryGroupMapping, ...] | None = None,
    max_groups: int = 100,
) -> DirectoryProviderProfile:
    return DirectoryProviderProfile(
        provider_id="provider.ldap.enterprise",
        organization_id="organization.development",
        endpoints=endpoints
        or (DirectoryEndpoint("endpoint.directory.primary", "ldaps://dc01.example.test:636"),),
        ca_certificate_file=Path("enterprise-ca.pem"),
        user_principal_template="{username}@example.test",
        user_search_base="OU=People,DC=example,DC=test",
        user_search_filter="(&(objectClass=user)(sAMAccountName={username}))",
        group_mappings=mappings or (),
        max_groups=max_groups,
    )


def user_record(
    *,
    groups: tuple[str, ...] = (),
    endpoint_id: str = "endpoint.directory.primary",
) -> DirectoryUserRecord:
    return DirectoryUserRecord(
        stable_external_id="a0f36e1d-252a-4d57-8e53-01027c28f72f",
        display_name="Directory Operator",
        directory_groups=groups,
        endpoint_id=endpoint_id,
    )


def basic(username: str, password: str) -> AuthenticationInput:
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
    return AuthenticationInput(
        correlation_id="cor_directory",
        authorization_scheme="basic",
        credential=encoded,
    )


@pytest.mark.asyncio
async def test_directory_identity_is_normalized_and_only_allowlisted_groups_map() -> None:
    mapping = DirectoryGroupMapping(
        directory_group="CN=Atlas Operators,OU=Groups,DC=example,DC=test",
        atlas_group_id="group.ldap.atlas-operators",
        role_ids=("role.development.operator",),
    )
    client = StaticDirectoryClient(
        user_record(
            groups=(
                "cn=atlas operators,ou=groups,dc=example,dc=test",
                "CN=Unmapped Administrators,OU=Groups,DC=example,DC=test",
            )
        )
    )
    provider = DirectoryIdentityProvider(profile=profile(mappings=(mapping,)), client=client)

    subject = await provider.authenticate(basic("uozdemir", "correct-password"))

    assert subject is not None
    assert subject.subject_id.startswith("subject.ldap.")
    assert "a0f36e1d" not in subject.subject_id
    assert subject.authentication_method.value == "ldap"
    assert subject.assurance_level.value == "single_factor"
    assert subject.group_ids == ("group.ldap.atlas-operators",)
    assert subject.role_ids == ("role.development.operator",)
    assert client.password_lengths == [16]
    assert "correct-password" not in repr(subject)


@pytest.mark.asyncio
async def test_malformed_basic_credentials_fail_before_directory_access() -> None:
    client = StaticDirectoryClient(user_record())
    provider = DirectoryIdentityProvider(profile=profile(), client=client)

    malformed = await provider.authenticate(
        AuthenticationInput(
            correlation_id="cor_malformed",
            authorization_scheme="basic",
            credential="not-base64!",
        )
    )
    injected_username = await provider.authenticate(basic("admin)(objectClass=*)", "password"))
    bearer = await provider.authenticate(
        AuthenticationInput(
            correlation_id="cor_bearer",
            authorization_scheme="bearer",
            credential="opaque-token",
        )
    )

    assert malformed is None
    assert injected_username is None
    assert bearer is None
    assert client.calls == 0
    assert "opaque-token" not in repr(
        AuthenticationInput(
            correlation_id="cor_repr",
            authorization_scheme="bearer",
            credential="opaque-token",
        )
    )


@pytest.mark.asyncio
async def test_rejected_credentials_do_not_fail_over_to_another_endpoint() -> None:
    endpoints = (
        DirectoryEndpoint("endpoint.directory.primary", "ldaps://dc01.example.test"),
        DirectoryEndpoint("endpoint.directory.secondary", "ldaps://dc02.example.test"),
    )
    authenticator = ScriptedEndpointAuthenticator(
        {
            "endpoint.directory.primary": DirectoryCredentialRejected("rejected"),
            "endpoint.directory.secondary": user_record(endpoint_id="endpoint.directory.secondary"),
        }
    )
    client = FailoverDirectoryClient(
        profile=profile(endpoints=endpoints), authenticator=authenticator
    )

    result = await client.authenticate("uozdemir", "wrong-password")

    assert result is None
    assert authenticator.endpoint_calls == ["endpoint.directory.primary"]


@pytest.mark.asyncio
async def test_unavailable_endpoint_fails_over_deterministically() -> None:
    endpoints = (
        DirectoryEndpoint("endpoint.directory.primary", "ldaps://dc01.example.test"),
        DirectoryEndpoint("endpoint.directory.secondary", "ldaps://dc02.example.test"),
    )
    secondary = user_record(endpoint_id="endpoint.directory.secondary")
    authenticator = ScriptedEndpointAuthenticator(
        {
            "endpoint.directory.primary": DirectoryEndpointUnavailable("offline"),
            "endpoint.directory.secondary": secondary,
        }
    )
    client = FailoverDirectoryClient(
        profile=profile(endpoints=endpoints), authenticator=authenticator
    )

    result = await client.authenticate("uozdemir", "password")

    assert result == secondary
    assert authenticator.endpoint_calls == [
        "endpoint.directory.primary",
        "endpoint.directory.secondary",
    ]


@pytest.mark.asyncio
async def test_all_unavailable_endpoints_fail_closed() -> None:
    endpoints = (
        DirectoryEndpoint("endpoint.directory.primary", "ldaps://dc01.example.test"),
        DirectoryEndpoint("endpoint.directory.secondary", "ldaps://dc02.example.test"),
    )
    authenticator = ScriptedEndpointAuthenticator(
        {item.endpoint_id: DirectoryEndpointUnavailable("offline") for item in endpoints}
    )
    client = FailoverDirectoryClient(
        profile=profile(endpoints=endpoints), authenticator=authenticator
    )

    with pytest.raises(DirectoryUnavailable, match="all_directory_endpoints_unavailable:2"):
        await client.authenticate("uozdemir", "password")


@pytest.mark.asyncio
async def test_group_overflow_fails_closed_without_partial_mapping() -> None:
    client = StaticDirectoryClient(user_record(groups=("group-one", "group-two")))
    provider = DirectoryIdentityProvider(profile=profile(max_groups=1), client=client)

    with pytest.raises(IdentityProviderFailure, match="identity_provider_response_invalid"):
        await provider.authenticate(basic("uozdemir", "password"))


@pytest.mark.asyncio
async def test_provider_outage_is_audited_with_generic_failure_context() -> None:
    endpoints = (DirectoryEndpoint("endpoint.directory.primary", "ldaps://dc01.example.test"),)
    endpoint_authenticator = ScriptedEndpointAuthenticator(
        {"endpoint.directory.primary": DirectoryEndpointUnavailable("offline-secret-detail")}
    )
    directory_profile = profile(endpoints=endpoints)
    provider = DirectoryIdentityProvider(
        profile=directory_profile,
        client=FailoverDirectoryClient(
            profile=directory_profile,
            authenticator=endpoint_authenticator,
        ),
    )
    sink = CollectingAuditSink()
    identity_service = IdentityService(provider=provider, audit_sink=sink, clock=lambda: NOW)

    with pytest.raises(IdentityProviderFailure, match="identity_provider_unavailable"):
        await identity_service.authenticate(basic("uozdemir", "password"))

    assert sink.records[0].event_type == "atlas.identity.authentication.failed"
    assert sink.records[0].authentication_method == "ldap"
    assert sink.records[0].scope_reference == "provider.ldap.enterprise"
    assert sink.records[0].result_code == "identity_provider_unavailable"
    assert "offline-secret-detail" not in repr(sink.records)


@pytest.mark.asyncio
async def test_authentication_audit_uses_generic_ldap_result_without_credentials() -> None:
    password = "never-audit-this-password"
    sink = CollectingAuditSink()
    provider = DirectoryIdentityProvider(
        profile=profile(), client=StaticDirectoryClient(user_record())
    )
    service = IdentityService(provider=provider, audit_sink=sink, clock=lambda: NOW)

    subject = await service.authenticate(basic("uozdemir", password))

    assert subject is not None
    assert sink.records[0].result_code == "ldap_identity_accepted"
    assert sink.records[0].authentication_method == "ldap"
    assert password not in repr(sink.records)


@pytest.mark.asyncio
async def test_rejected_directory_credentials_are_denied_with_provider_context() -> None:
    sink = CollectingAuditSink()
    provider = DirectoryIdentityProvider(profile=profile(), client=StaticDirectoryClient(None))
    service = IdentityService(provider=provider, audit_sink=sink, clock=lambda: NOW)

    subject = await service.authenticate(basic("uozdemir", "wrong-password"))

    assert subject is None
    assert sink.records[0].event_type == "atlas.identity.authentication.denied"
    assert sink.records[0].authentication_method == "ldap"
    assert sink.records[0].scope_reference == "provider.ldap.enterprise"
    assert sink.records[0].result_code == "credentials_rejected"
    assert "wrong-password" not in repr(sink.records)


def test_successful_directory_authentication_does_not_bypass_exact_scope_rbac() -> None:
    mapping = DirectoryGroupMapping(
        directory_group="CN=Atlas Operators,OU=Groups,DC=example,DC=test",
        atlas_group_id="group.ldap.atlas-operators",
        role_ids=("role.development.operator",),
    )
    provider = DirectoryIdentityProvider(
        profile=profile(mappings=(mapping,)),
        client=StaticDirectoryClient(
            user_record(groups=("CN=Atlas Operators,OU=Groups,DC=example,DC=test",))
        ),
    )
    sink = CollectingAuditSink()
    encoded = basic("uozdemir", "password").credential
    assert encoded is not None
    with TestClient(
        create_app(
            Settings(environment="test", development_identity_enabled=True),
            identity_provider=provider,
            audit_sink=sink,
        )
    ) as client:
        response = client.get(
            "/api/v1/identity/me",
            headers={"Authorization": f"Basic {encoded}"},
        )

    assert response.status_code == 403
    assert response.json()["code"] == "authorization_denied"
    assert [item.event_type for item in sink.records[-2:]] == [
        "atlas.identity.authentication.succeeded",
        "atlas.authorization.access.denied",
    ]


def test_directory_configuration_requires_tls_trust_and_exclusive_provider() -> None:
    mapping = DirectoryGroupMappingSetting(
        directory_group="CN=Atlas Operators,OU=Groups,DC=example,DC=test",
        atlas_group_id="group.ldap.atlas-operators",
        role_ids=("role.development.operator",),
    )
    with pytest.raises(ValidationError, match="development and directory"):
        Settings(
            environment="test",
            development_identity_enabled=True,
            directory_identity_enabled=True,
            directory_endpoints=("ldaps://dc01.example.test",),
            directory_ca_certificate_file=Path("ca.pem"),
            directory_user_search_base="OU=People,DC=example,DC=test",
            directory_group_mappings=(mapping,),
        )
    with pytest.raises(ValidationError, match="ldaps"):
        Settings(
            environment="test",
            directory_identity_enabled=True,
            directory_endpoints=("ldap://dc01.example.test",),
            directory_ca_certificate_file=Path("ca.pem"),
            directory_user_search_base="OU=People,DC=example,DC=test",
        )
    with pytest.raises(ValidationError, match="CA certificate"):
        Settings(
            environment="test",
            directory_identity_enabled=True,
            directory_endpoints=("ldaps://dc01.example.test",),
            directory_user_search_base="OU=People,DC=example,DC=test",
        )


def test_directory_domain_rejects_plain_ldap_and_nested_group_expansion() -> None:
    with pytest.raises(ValueError, match="ldaps"):
        DirectoryEndpoint("endpoint.directory.insecure", "ldap://dc01.example.test")
    with pytest.raises(ValueError, match="nested directory groups"):
        DirectoryProviderProfile(
            provider_id="provider.ldap.enterprise",
            organization_id="organization.development",
            endpoints=(
                DirectoryEndpoint("endpoint.directory.primary", "ldaps://dc01.example.test"),
            ),
            ca_certificate_file=Path("enterprise-ca.pem"),
            user_principal_template="{username}@example.test",
            user_search_base="OU=People,DC=example,DC=test",
            user_search_filter="(sAMAccountName={username})",
            nested_group_depth=1,
        )


def test_ldap_adapter_rejects_missing_trust_file_before_network_access() -> None:
    directory_profile = profile()

    with pytest.raises(DirectoryEndpointUnavailable, match="directory_trust_file_unavailable"):
        Ldap3EndpointAuthenticator().authenticate(
            directory_profile,
            directory_profile.endpoints[0],
            "uozdemir",
            "password",
        )
