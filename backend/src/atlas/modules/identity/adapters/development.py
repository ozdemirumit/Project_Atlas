from __future__ import annotations

from datetime import UTC, datetime

from atlas.core.config import Settings
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationInput,
    AuthenticationMethod,
    SubjectKind,
)


class DevelopmentIdentityProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def authenticate(
        self, authentication_input: AuthenticationInput
    ) -> AuthenticatedSubject | None:
        if not self._settings.development_identity_enabled:
            return None
        if self._settings.environment not in {"development", "test"}:
            return None
        if authentication_input.authorization_scheme is not None:
            return None

        return AuthenticatedSubject(
            subject_id=self._settings.development_subject_id,
            display_name=self._settings.development_display_name,
            kind=SubjectKind.HUMAN,
            provider_id="provider.development.local",
            authentication_method=AuthenticationMethod.DEVELOPMENT,
            assurance_level=AssuranceLevel.DEVELOPMENT,
            authenticated_at=datetime.now(UTC),
            organization_id=self._settings.development_organization_id,
            role_ids=self._settings.development_role_ids,
        )
