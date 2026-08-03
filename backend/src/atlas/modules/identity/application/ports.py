from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.models import AuthenticatedSubject, AuthenticationInput


class IdentityProvider(Protocol):
    async def authenticate(
        self, authentication_input: AuthenticationInput
    ) -> AuthenticatedSubject | None: ...
