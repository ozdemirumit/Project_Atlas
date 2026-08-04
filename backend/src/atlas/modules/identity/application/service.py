from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.identity.application.ports import IdentityProvider
from atlas.modules.identity.domain.models import (
    AuthenticatedSubject,
    AuthenticationInput,
    IdentityProviderDenied,
    IdentityProviderFailure,
)


class IdentityService:
    def __init__(
        self,
        *,
        provider: IdentityProvider,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._provider = provider
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))

    async def authenticate(
        self, authentication_input: AuthenticationInput
    ) -> AuthenticatedSubject | None:
        try:
            subject = await self._provider.authenticate(authentication_input)
        except IdentityProviderDenied as exc:
            await self._audit_sink.record(
                AuditRecord(
                    event_id=f"evt_{uuid4().hex}",
                    event_type="atlas.identity.authentication.denied",
                    schema_version="1.0",
                    producer="project-atlas-api",
                    producer_version=__version__,
                    occurred_at=self._clock(),
                    correlation_id=authentication_input.correlation_id,
                    subject_id=None,
                    actor_type=None,
                    authentication_method=exc.authentication_method.value,
                    assurance_level=None,
                    permission_id=None,
                    resource_type="resource.identity.session",
                    scope_reference=exc.provider_id,
                    decision_id=None,
                    outcome="denied",
                    result_code=exc.result_code,
                )
            )
            return None
        except IdentityProviderFailure as exc:
            await self._audit_sink.record(
                AuditRecord(
                    event_id=f"evt_{uuid4().hex}",
                    event_type="atlas.identity.authentication.failed",
                    schema_version="1.0",
                    producer="project-atlas-api",
                    producer_version=__version__,
                    occurred_at=self._clock(),
                    correlation_id=authentication_input.correlation_id,
                    subject_id=None,
                    actor_type=None,
                    authentication_method=exc.authentication_method.value,
                    assurance_level=None,
                    permission_id=None,
                    resource_type="resource.identity.session",
                    scope_reference=exc.provider_id,
                    decision_id=None,
                    outcome="failed",
                    result_code=exc.result_code,
                )
            )
            raise
        succeeded = subject is not None
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=(
                    "atlas.identity.authentication.succeeded"
                    if succeeded
                    else "atlas.identity.authentication.denied"
                ),
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=authentication_input.correlation_id,
                subject_id=subject.subject_id if subject else None,
                actor_type=subject.kind.value if subject else None,
                authentication_method=(subject.authentication_method.value if subject else None),
                assurance_level=subject.assurance_level.value if subject else None,
                permission_id=None,
                resource_type="resource.identity.session",
                scope_reference=subject.provider_id if subject else None,
                decision_id=None,
                outcome="succeeded" if succeeded else "denied",
                result_code=(
                    f"{subject.authentication_method.value}_identity_accepted"
                    if subject
                    else "authentication_required"
                ),
            )
        )
        return subject
