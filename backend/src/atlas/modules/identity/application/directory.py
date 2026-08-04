from __future__ import annotations

import base64
import binascii
import re
from datetime import UTC, datetime
from hashlib import sha256

from atlas.modules.identity.application.ports import DirectoryClient
from atlas.modules.identity.domain.directory import DirectoryProviderProfile
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationInput,
    AuthenticationMethod,
    IdentityProviderDenied,
    IdentityProviderFailure,
    SubjectKind,
)

USERNAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class DirectoryIdentityProvider:
    def __init__(
        self,
        *,
        profile: DirectoryProviderProfile,
        client: DirectoryClient,
    ) -> None:
        self._profile = profile
        self._client = client
        self._mapping = {item.directory_group.casefold(): item for item in profile.group_mappings}

    async def authenticate(
        self, authentication_input: AuthenticationInput
    ) -> AuthenticatedSubject | None:
        credentials = self._decode_basic(authentication_input)
        if credentials is None:
            return None
        username, password = credentials
        try:
            record = await self._client.authenticate(username, password)
        except DirectoryUnavailable as exc:
            raise IdentityProviderFailure(
                provider_id=self._profile.provider_id,
                authentication_method=AuthenticationMethod.LDAP,
                result_code="identity_provider_unavailable",
            ) from exc
        except DirectoryResponseInvalid as exc:
            raise IdentityProviderFailure(
                provider_id=self._profile.provider_id,
                authentication_method=AuthenticationMethod.LDAP,
                result_code="identity_provider_response_invalid",
            ) from exc
        if record is None:
            raise IdentityProviderDenied(
                provider_id=self._profile.provider_id,
                authentication_method=AuthenticationMethod.LDAP,
            )
        if len(record.directory_groups) > self._profile.max_groups:
            raise IdentityProviderFailure(
                provider_id=self._profile.provider_id,
                authentication_method=AuthenticationMethod.LDAP,
                result_code="identity_provider_response_invalid",
            )

        matched = tuple(
            self._mapping[group.casefold()]
            for group in record.directory_groups
            if group.casefold() in self._mapping
        )
        group_ids = tuple(sorted({item.atlas_group_id for item in matched}))
        role_ids = tuple(sorted({role for item in matched for role in item.role_ids}))
        subject_digest = sha256(
            f"{self._profile.provider_id}\0{record.stable_external_id}".encode()
        ).hexdigest()[:32]
        return AuthenticatedSubject(
            subject_id=f"subject.ldap.{subject_digest}",
            display_name=record.display_name,
            kind=SubjectKind.HUMAN,
            provider_id=self._profile.provider_id,
            authentication_method=AuthenticationMethod.LDAP,
            assurance_level=AssuranceLevel.SINGLE_FACTOR,
            authenticated_at=datetime.now(UTC),
            organization_id=self._profile.organization_id,
            role_ids=role_ids,
            group_ids=group_ids,
        )

    @staticmethod
    def _decode_basic(authentication_input: AuthenticationInput) -> tuple[str, str] | None:
        if authentication_input.authorization_scheme != "basic":
            return None
        encoded = authentication_input.credential
        if encoded is None or not 1 <= len(encoded) <= 4096:
            return None
        try:
            raw = base64.b64decode(encoded, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            return None
        username, separator, password = raw.partition(":")
        if (
            separator != ":"
            or not USERNAME.fullmatch(username)
            or not 1 <= len(password) <= 1024
            or any(ord(character) < 32 for character in password)
        ):
            return None
        return username, password


class DirectoryAuthenticationError(RuntimeError):
    pass


class DirectoryCredentialRejected(DirectoryAuthenticationError):
    pass


class DirectoryEndpointUnavailable(DirectoryAuthenticationError):
    pass


class DirectoryUnavailable(DirectoryAuthenticationError):
    pass


class DirectoryResponseInvalid(DirectoryAuthenticationError):
    pass
