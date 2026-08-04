from __future__ import annotations

import asyncio
import hmac
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.identity.application.service import IdentityService
from atlas.modules.identity.application.session_ports import SessionRepository
from atlas.modules.identity.domain.models import AuthenticationInput
from atlas.modules.identity.domain.sessions import (
    CredentialKind,
    IssuedSession,
    SessionContext,
    SessionRecord,
    SessionState,
)


class SessionOperationsError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class SessionService:
    def __init__(
        self,
        *,
        identity_service: IdentityService,
        repository: SessionRepository,
        audit_sink: AuditSink,
        absolute_timeout: timedelta,
        idle_timeout: timedelta,
        max_sessions_per_subject: int,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not timedelta(minutes=5) <= absolute_timeout <= timedelta(hours=24):
            raise ValueError("session absolute timeout is outside platform bounds")
        if not timedelta(minutes=1) <= idle_timeout <= timedelta(hours=4):
            raise ValueError("session idle timeout is outside platform bounds")
        if idle_timeout > absolute_timeout:
            raise ValueError("session idle timeout cannot exceed absolute timeout")
        if not 1 <= max_sessions_per_subject <= 20:
            raise ValueError("session concurrency limit is outside platform bounds")
        self._identity_service = identity_service
        self._repository = repository
        self._audit_sink = audit_sink
        self._absolute_timeout = absolute_timeout
        self._idle_timeout = idle_timeout
        self._max_sessions = max_sessions_per_subject
        self._clock = clock or (lambda: datetime.now(UTC))
        self._creation_lock = asyncio.Lock()

    async def create(
        self,
        authentication_input: AuthenticationInput,
    ) -> IssuedSession:
        subject = await self._identity_service.authenticate(authentication_input)
        if subject is None:
            raise SessionOperationsError("authentication_required")
        async with self._creation_lock:
            now = self._clock()
            active = await self._repository.active_for_subject(subject.subject_id)
            if len(active) >= self._max_sessions:
                await self._audit_denial(
                    "session_limit_exceeded", authentication_input.correlation_id
                )
                raise SessionOperationsError("session_limit_exceeded")
            token = token_urlsafe(32)
            csrf_token = token_urlsafe(32)
            record = SessionRecord(
                session_id=f"session.{uuid4().hex}",
                version=1,
                credential_kind=CredentialKind.BROWSER_SESSION,
                token_digest=self._digest(token),
                csrf_digest=self._digest(csrf_token),
                subject=subject,
                created_at=now,
                last_seen_at=now,
                absolute_expires_at=now + self._absolute_timeout,
                idle_expires_at=min(now + self._idle_timeout, now + self._absolute_timeout),
                state=SessionState.ACTIVE,
            )
            await self._audit(record, "created", authentication_input.correlation_id)
            await self._repository.add(record)
        return IssuedSession(record=record, token=token, csrf_token=csrf_token)

    async def authenticate(
        self,
        token: str,
        *,
        csrf_token: str | None,
        unsafe_request: bool,
        correlation_id: str,
    ) -> SessionContext | None:
        if not 32 <= len(token) <= 256:
            await self._audit_denial("unknown_session", correlation_id)
            return None
        token_digest = self._digest(token)
        for _ in range(3):
            record = await self._repository.get_by_token_digest(token_digest)
            if record is None or record.state is not SessionState.ACTIVE:
                await self._audit_denial("unknown_session", correlation_id)
                return None
            now = self._clock()
            if now >= record.absolute_expires_at or now >= record.idle_expires_at:
                expired = replace(
                    record,
                    version=record.version + 1,
                    state=SessionState.EXPIRED,
                    revoked_at=now,
                    revocation_reason="session_expired",
                )
                if await self._repository.update(expired, expected_version=record.version):
                    await self._audit(expired, "expired", correlation_id)
                    return None
                continue
            if unsafe_request and (
                csrf_token is None
                or not 32 <= len(csrf_token) <= 256
                or not hmac.compare_digest(self._digest(csrf_token), record.csrf_digest)
            ):
                await self._audit_denial("csrf_validation_failed", correlation_id, record)
                raise SessionOperationsError("csrf_validation_failed")
            touched = replace(
                record,
                version=record.version + 1,
                last_seen_at=now,
                idle_expires_at=min(now + self._idle_timeout, record.absolute_expires_at),
            )
            if await self._repository.update(touched, expected_version=record.version):
                return SessionContext(
                    subject=touched.subject,
                    session_id=touched.session_id,
                    credential_kind=touched.credential_kind,
                    absolute_expires_at=touched.absolute_expires_at,
                    idle_expires_at=touched.idle_expires_at,
                )
        await self._audit_denial("session_state_conflict", correlation_id)
        return None

    async def revoke(
        self,
        token: str,
        *,
        csrf_token: str | None,
        correlation_id: str,
    ) -> None:
        context = await self.authenticate(
            token,
            csrf_token=csrf_token,
            unsafe_request=True,
            correlation_id=correlation_id,
        )
        if context is None:
            raise SessionOperationsError("authentication_required")
        token_digest = self._digest(token)
        for _ in range(3):
            record = await self._repository.get_by_token_digest(token_digest)
            if record is None or record.state is not SessionState.ACTIVE:
                raise SessionOperationsError("authentication_required")
            now = self._clock()
            revoked = replace(
                record,
                version=record.version + 1,
                state=SessionState.REVOKED,
                revoked_at=now,
                revocation_reason="user_logout",
            )
            if await self._repository.update(revoked, expected_version=record.version):
                await self._audit(revoked, "revoked", correlation_id)
                return
        await self._audit_denial("session_state_conflict", correlation_id)
        raise SessionOperationsError("authentication_required")

    async def _audit(self, record: SessionRecord, action: str, correlation_id: str) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=f"atlas.identity.session.{action}",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=record.subject.subject_id,
                actor_type=record.subject.kind.value,
                authentication_method=record.subject.authentication_method.value,
                assurance_level=record.subject.assurance_level.value,
                permission_id=None,
                resource_type="resource.identity.session",
                scope_reference=record.session_id,
                decision_id=None,
                outcome="succeeded" if action in {"created", "revoked"} else "denied",
                result_code=f"session_{action}",
            )
        )

    async def _audit_denial(
        self,
        result_code: str,
        correlation_id: str,
        record: SessionRecord | None = None,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.identity.session.denied",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=record.subject.subject_id if record else None,
                actor_type=record.subject.kind.value if record else None,
                authentication_method=(
                    record.subject.authentication_method.value if record else None
                ),
                assurance_level=record.subject.assurance_level.value if record else None,
                permission_id=None,
                resource_type="resource.identity.session",
                scope_reference=record.session_id if record else None,
                decision_id=None,
                outcome="denied",
                result_code=result_code,
            )
        )

    @staticmethod
    def _digest(value: str) -> str:
        return sha256(value.encode()).hexdigest()
