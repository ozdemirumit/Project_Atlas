from __future__ import annotations

import asyncio
import ssl
from collections.abc import Mapping, Sequence
from contextlib import suppress
from pathlib import Path
from typing import Any, cast

from ldap3 import AUTO_BIND_NO_TLS, SUBTREE, Connection, Server, Tls
from ldap3.core.exceptions import LDAPException, LDAPInvalidCredentialsResult
from ldap3.utils.conv import escape_filter_chars

from atlas.core.config import Settings
from atlas.modules.identity.application.directory import (
    DirectoryCredentialRejected,
    DirectoryEndpointUnavailable,
    DirectoryIdentityProvider,
    DirectoryResponseInvalid,
    DirectoryUnavailable,
)
from atlas.modules.identity.application.ports import DirectoryEndpointAuthenticator
from atlas.modules.identity.domain.directory import (
    DirectoryEndpoint,
    DirectoryGroupMapping,
    DirectoryProviderProfile,
    DirectoryUserRecord,
)


def build_directory_identity_provider(settings: Settings) -> DirectoryIdentityProvider:
    profile = DirectoryProviderProfile(
        provider_id=settings.directory_provider_id,
        organization_id=settings.directory_organization_id,
        endpoints=tuple(
            DirectoryEndpoint(
                endpoint_id=f"endpoint.directory.{index}",
                uri=uri,
            )
            for index, uri in enumerate(settings.directory_endpoints, start=1)
        ),
        ca_certificate_file=settings.directory_ca_certificate_file or Path(""),
        user_principal_template=settings.directory_user_principal_template,
        user_search_base=settings.directory_user_search_base,
        user_search_filter=settings.directory_user_search_filter,
        stable_id_attribute=settings.directory_stable_id_attribute,
        display_name_attribute=settings.directory_display_name_attribute,
        group_attribute=settings.directory_group_attribute,
        group_mappings=tuple(
            DirectoryGroupMapping(
                directory_group=item.directory_group,
                atlas_group_id=item.atlas_group_id,
                role_ids=item.role_ids,
            )
            for item in settings.directory_group_mappings
        ),
        max_groups=settings.directory_max_groups,
        nested_group_depth=settings.directory_nested_group_depth,
        connect_timeout_seconds=settings.directory_connect_timeout_seconds,
        response_timeout_seconds=settings.directory_response_timeout_seconds,
    )
    return DirectoryIdentityProvider(
        profile=profile,
        client=FailoverDirectoryClient(
            profile=profile,
            authenticator=Ldap3EndpointAuthenticator(),
        ),
    )


class FailoverDirectoryClient:
    def __init__(
        self,
        *,
        profile: DirectoryProviderProfile,
        authenticator: DirectoryEndpointAuthenticator,
    ) -> None:
        self._profile = profile
        self._authenticator = authenticator

    async def authenticate(self, username: str, password: str) -> DirectoryUserRecord | None:
        unavailable = 0
        for endpoint in self._profile.endpoints:
            try:
                return await asyncio.to_thread(
                    self._authenticator.authenticate,
                    self._profile,
                    endpoint,
                    username,
                    password,
                )
            except DirectoryCredentialRejected:
                return None
            except DirectoryEndpointUnavailable:
                unavailable += 1
        raise DirectoryUnavailable(f"all_directory_endpoints_unavailable:{unavailable}")


class Ldap3EndpointAuthenticator:
    def authenticate(
        self,
        profile: DirectoryProviderProfile,
        endpoint: DirectoryEndpoint,
        username: str,
        password: str,
    ) -> DirectoryUserRecord:
        self._validate_trust_file(profile.ca_certificate_file)
        tls = Tls(
            validate=ssl.CERT_REQUIRED,
            ca_certs_file=str(profile.ca_certificate_file),
            version=ssl.PROTOCOL_TLS_CLIENT,
        )
        server = Server(
            endpoint.hostname,
            port=endpoint.port,
            use_ssl=True,
            tls=tls,
            connect_timeout=profile.connect_timeout_seconds,
        )
        principal = profile.user_principal_template.format(username=username)
        connection: Connection | None = None
        try:
            connection = Connection(
                server,
                user=principal,
                password=password,
                auto_bind=AUTO_BIND_NO_TLS,
                receive_timeout=profile.response_timeout_seconds,
                raise_exceptions=True,
            )
            search_filter = profile.user_search_filter.format(
                username=escape_filter_chars(username)
            )
            connection.search(
                search_base=profile.user_search_base,
                search_filter=search_filter,
                search_scope=SUBTREE,
                attributes=[
                    profile.stable_id_attribute,
                    profile.display_name_attribute,
                    profile.group_attribute,
                ],
                size_limit=2,
            )
            entries = cast(Sequence[Any], connection.entries)
            if len(entries) != 1:
                raise DirectoryResponseInvalid("directory_identity_is_missing_or_ambiguous")
            attributes = cast(Mapping[str, object], entries[0].entry_attributes_as_dict)
            stable_id = self._required_scalar(attributes, profile.stable_id_attribute)
            display_name = self._required_scalar(attributes, profile.display_name_attribute)
            groups = self._string_values(attributes.get(profile.group_attribute, ()))
            if len(groups) > profile.max_groups:
                raise DirectoryResponseInvalid("directory_group_limit_exceeded")
            return DirectoryUserRecord(
                stable_external_id=stable_id,
                display_name=display_name,
                directory_groups=groups,
                endpoint_id=endpoint.endpoint_id,
            )
        except LDAPInvalidCredentialsResult as exc:
            raise DirectoryCredentialRejected("directory_credentials_rejected") from exc
        except DirectoryResponseInvalid:
            raise
        except LDAPException as exc:
            raise DirectoryEndpointUnavailable("directory_endpoint_unavailable") from exc
        finally:
            if connection is not None:
                with suppress(LDAPException):
                    connection.unbind()

    @staticmethod
    def _validate_trust_file(path: Path) -> None:
        if not path.is_file():
            raise DirectoryEndpointUnavailable("directory_trust_file_unavailable")

    @classmethod
    def _required_scalar(cls, attributes: Mapping[str, object], key: str) -> str:
        values = cls._string_values(attributes.get(key, ()))
        if len(values) != 1 or not values[0]:
            raise DirectoryResponseInvalid("directory_required_attribute_invalid")
        return values[0]

    @staticmethod
    def _string_values(value: object) -> tuple[str, ...]:
        if isinstance(value, bytes):
            return (value.hex(),)
        if isinstance(value, str):
            return (value,)
        if not isinstance(value, Sequence):
            return ()
        result: list[str] = []
        for item in value:
            if isinstance(item, bytes):
                result.append(item.hex())
            elif isinstance(item, str):
                result.append(item)
            else:
                raise DirectoryResponseInvalid("directory_attribute_type_invalid")
        return tuple(result)
