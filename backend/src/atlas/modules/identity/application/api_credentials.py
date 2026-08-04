from __future__ import annotations

import asyncio
import hmac
import re
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.identity.application.api_credential_ports import ApiCredentialRepository
from atlas.modules.identity.domain.api_credentials import (
    ApiCredentialContext,
    ApiCredentialInventory,
    ApiCredentialRecord,
    ApiCredentialState,
    IssuedApiCredential,
)
from atlas.modules.identity.domain.models import (
    AuthenticatedSubject,
    AuthenticationMethod,
    CredentialGrant,
    SubjectKind,
)

TOKEN_PATTERN = re.compile(r"^atlas_pat_[A-Za-z0-9_-]{40,128}$")


class ApiCredentialOperationsError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ApiCredentialService:
    def __init__(
        self,
        *,
        repository: ApiCredentialRepository,
        audit_sink: AuditSink,
        max_lifetime: timedelta = timedelta(minutes=60),
        max_active_per_subject: int = 10,
        clock: Callable[[], datetime] | None = None,
        token_factory: Callable[[], str] | None = None,
    ) -> None:
        if not timedelta(minutes=5) <= max_lifetime <= timedelta(minutes=60):
            raise ValueError("API credential lifetime is outside platform bounds")
        if not 1 <= max_active_per_subject <= 20:
            raise ValueError("API credential active limit is outside platform bounds")
        self._repository = repository
        self._audit_sink = audit_sink
        self._max_lifetime = max_lifetime
        self._max_active = max_active_per_subject
        self._clock = clock or (lambda: datetime.now(UTC))
        self._token_factory = token_factory or (lambda: f"atlas_pat_{token_urlsafe(32)}")
        self._creation_lock = asyncio.Lock()

    async def issue(
        self,
        *,
        subject: AuthenticatedSubject,
        display_name: str,
        purpose: str,
        lifetime: timedelta,
        grants: tuple[CredentialGrant, ...],
        correlation_id: str,
    ) -> IssuedApiCredential:
        if subject.kind is not SubjectKind.HUMAN:
            await self._audit_denial("credential_human_required", correlation_id, subject=subject)
            raise ApiCredentialOperationsError("credential_human_required")
        if not timedelta(minutes=5) <= lifetime <= self._max_lifetime:
            raise ApiCredentialOperationsError("credential_lifetime_invalid")
        if not 1 <= len(display_name.strip()) <= 80 or not 1 <= len(purpose.strip()) <= 240:
            raise ApiCredentialOperationsError("credential_metadata_invalid")
        ordered_grants = tuple(
            sorted(set(grants), key=lambda item: (item.permission_id, item.scope_reference))
        )
        if not ordered_grants or len(ordered_grants) != len(grants) or len(grants) > 10:
            raise ApiCredentialOperationsError("credential_grants_invalid")

        async with self._creation_lock:
            now = self._clock()
            await self._normalize_expired(subject.subject_id, now, correlation_id)
            active = await self._repository.active_for_subject(subject.subject_id)
            if len(active) >= self._max_active:
                await self._audit_denial(
                    "credential_limit_exceeded", correlation_id, subject=subject
                )
                raise ApiCredentialOperationsError("credential_limit_exceeded")
            token = ""
            for _ in range(3):
                candidate = self._token_factory()
                if TOKEN_PATTERN.fullmatch(candidate) is None:
                    raise RuntimeError("credential token factory returned an invalid value")
                if await self._repository.get_by_digest(self._digest(candidate)) is None:
                    token = candidate
                    break
            if not token:
                raise RuntimeError("could not generate a unique API credential")
            record = ApiCredentialRecord(
                credential_id=f"credential.{uuid4().hex}",
                version=1,
                token_digest=self._digest(token),
                subject=replace(subject, credential_grants=None),
                display_name=display_name.strip(),
                purpose=purpose.strip(),
                grants=ordered_grants,
                created_at=now,
                expires_at=now + lifetime,
                state=ApiCredentialState.ACTIVE,
            )
            await self._audit(record, "issued", correlation_id)
            await self._repository.add(record)
        return IssuedApiCredential(record=record, token=token)

    async def authenticate(
        self,
        token: str,
        *,
        unsafe_request: bool,
        correlation_id: str,
    ) -> ApiCredentialContext | None:
        if TOKEN_PATTERN.fullmatch(token) is None:
            await self._audit_denial("credential_unknown", correlation_id)
            return None
        digest = self._digest(token)
        for _ in range(3):
            record = await self._repository.get_by_digest(digest)
            if (
                record is None
                or not hmac.compare_digest(digest, record.token_digest)
                or record.state is not ApiCredentialState.ACTIVE
            ):
                await self._audit_denial("credential_unknown", correlation_id)
                return None
            now = self._clock()
            if now >= record.expires_at:
                if await self._expire(record, now, correlation_id):
                    return None
                continue
            if unsafe_request:
                await self._audit_denial(
                    "credential_unsafe_method_denied",
                    correlation_id,
                    record=record,
                    subject=replace(
                        record.subject,
                        authentication_method=AuthenticationMethod.API_TOKEN,
                    ),
                )
                raise ApiCredentialOperationsError("credential_unsafe_method_denied")
            touched = replace(
                record,
                version=record.version + 1,
                last_used_at=now,
            )
            if await self._repository.update(touched, expected_version=record.version):
                await self._audit(touched, "authenticated", correlation_id)
                grants = frozenset(touched.grants)
                return ApiCredentialContext(
                    subject=replace(
                        touched.subject,
                        authentication_method=AuthenticationMethod.API_TOKEN,
                        authenticated_at=now,
                        credential_grants=grants,
                    ),
                    credential_id=touched.credential_id,
                    grants=grants,
                    expires_at=touched.expires_at,
                )
        await self._audit_denial("credential_state_conflict", correlation_id)
        return None

    async def inventory(
        self,
        subject_id: str,
        *,
        correlation_id: str,
        limit: int = 50,
    ) -> ApiCredentialInventory:
        if not 1 <= limit <= 100:
            raise ValueError("credential inventory limit is outside platform bounds")
        await self._normalize_expired(subject_id, self._clock(), correlation_id)
        records = sorted(
            await self._repository.for_subject(subject_id),
            key=lambda item: (item.created_at, item.credential_id),
            reverse=True,
        )
        await self._audit_inventory(subject_id, correlation_id)
        return ApiCredentialInventory(
            records=tuple(records[:limit]),
            truncated=len(records) > limit,
        )

    async def revoke(
        self,
        credential_id: str,
        *,
        subject_id: str,
        correlation_id: str,
    ) -> ApiCredentialRecord:
        for _ in range(3):
            record = await self._repository.get_by_id(credential_id)
            if (
                record is None
                or record.subject.subject_id != subject_id
                or record.state is not ApiCredentialState.ACTIVE
            ):
                await self._audit_denial("credential_not_found", correlation_id)
                raise ApiCredentialOperationsError("credential_not_found")
            now = self._clock()
            if now >= record.expires_at:
                if await self._expire(record, now, correlation_id):
                    raise ApiCredentialOperationsError("credential_not_found")
                continue
            revoked = replace(
                record,
                version=record.version + 1,
                state=ApiCredentialState.REVOKED,
                revoked_at=now,
                revocation_reason="self_service_revocation",
            )
            await self._audit(revoked, "revoked", correlation_id)
            if await self._repository.update(revoked, expected_version=record.version):
                return revoked
        await self._audit_denial("credential_state_conflict", correlation_id)
        raise ApiCredentialOperationsError("credential_not_found")

    async def _normalize_expired(self, subject_id: str, now: datetime, correlation_id: str) -> None:
        for record in await self._repository.active_for_subject(subject_id):
            if now >= record.expires_at:
                await self._expire(record, now, correlation_id)

    async def _expire(
        self, record: ApiCredentialRecord, now: datetime, correlation_id: str
    ) -> bool:
        expired = replace(
            record,
            version=record.version + 1,
            state=ApiCredentialState.EXPIRED,
            revoked_at=now,
            revocation_reason="credential_expired",
        )
        await self._audit(expired, "expired", correlation_id)
        return await self._repository.update(expired, expected_version=record.version)

    async def _audit(self, record: ApiCredentialRecord, action: str, correlation_id: str) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=f"atlas.identity.api_credential.{action}",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=record.subject.subject_id,
                actor_type=record.subject.kind.value,
                authentication_method=(
                    AuthenticationMethod.API_TOKEN.value
                    if action == "authenticated"
                    else record.subject.authentication_method.value
                ),
                assurance_level=record.subject.assurance_level.value,
                permission_id=None,
                resource_type="resource.identity.api-credential",
                scope_reference=record.credential_id,
                decision_id=None,
                outcome="succeeded",
                result_code=f"credential_{action}",
            )
        )

    async def _audit_inventory(self, subject_id: str, correlation_id: str) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.identity.api_credential.inventory_read",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=subject_id,
                actor_type=SubjectKind.HUMAN.value,
                authentication_method=None,
                assurance_level=None,
                permission_id=None,
                resource_type="resource.identity.api-credential",
                scope_reference="self",
                decision_id=None,
                outcome="succeeded",
                result_code="credential_inventory_read",
            )
        )

    async def _audit_denial(
        self,
        result_code: str,
        correlation_id: str,
        *,
        record: ApiCredentialRecord | None = None,
        subject: AuthenticatedSubject | None = None,
    ) -> None:
        resolved_subject = subject or (record.subject if record is not None else None)
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.identity.api_credential.denied",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=(resolved_subject.subject_id if resolved_subject else None),
                actor_type=(resolved_subject.kind.value if resolved_subject else None),
                authentication_method=(
                    resolved_subject.authentication_method.value if resolved_subject else None
                ),
                assurance_level=(
                    resolved_subject.assurance_level.value if resolved_subject else None
                ),
                permission_id=None,
                resource_type="resource.identity.api-credential",
                scope_reference=record.credential_id if record else None,
                decision_id=None,
                outcome="denied",
                result_code=result_code,
            )
        )

    @staticmethod
    def _digest(value: str) -> str:
        return sha256(value.encode()).hexdigest()
