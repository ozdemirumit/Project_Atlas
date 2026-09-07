from __future__ import annotations

from atlas.modules.identity.application.ports import IdentityProvider
from atlas.modules.identity.domain.models import AuthenticatedSubject, AuthenticationInput


class CompositeIdentityProvider:
    """SS21 MVP scope lists "secure local bootstrap and recovery identity" alongside "one LDAP
    or Active Directory provider" as separate, co-existing capabilities, not alternatives. Tries
    each provider in order and returns the first non-`None` result; `IdentityProviderDenied`/
    `IdentityProviderFailure` from a provider propagate immediately rather than falling through,
    since those carry a specific, audited denial/failure reason for that provider."""

    def __init__(self, providers: tuple[IdentityProvider, ...]) -> None:
        if not providers:
            raise ValueError("a composite identity provider requires at least one provider")
        self._providers = providers

    async def authenticate(
        self, authentication_input: AuthenticationInput
    ) -> AuthenticatedSubject | None:
        for provider in self._providers:
            subject = await provider.authenticate(authentication_input)
            if subject is not None:
                return subject
        return None
