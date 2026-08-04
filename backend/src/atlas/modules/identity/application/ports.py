from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.directory import (
    DirectoryEndpoint,
    DirectoryProviderProfile,
    DirectoryUserRecord,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject, AuthenticationInput


class IdentityProvider(Protocol):
    async def authenticate(
        self, authentication_input: AuthenticationInput
    ) -> AuthenticatedSubject | None: ...


class DirectoryClient(Protocol):
    async def authenticate(self, username: str, password: str) -> DirectoryUserRecord | None: ...


class DirectoryEndpointAuthenticator(Protocol):
    def authenticate(
        self,
        profile: DirectoryProviderProfile,
        endpoint: DirectoryEndpoint,
        username: str,
        password: str,
    ) -> DirectoryUserRecord: ...
