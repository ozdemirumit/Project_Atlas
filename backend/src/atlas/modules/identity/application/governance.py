from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.identity.application.api_credential_ports import ApiCredentialRepository
from atlas.modules.identity.application.session_ports import SessionRepository
from atlas.modules.identity.domain.api_credentials import ApiCredentialRecord, ApiCredentialState
from atlas.modules.identity.domain.governance import IdentityGovernanceInventory
from atlas.modules.identity.domain.models import (
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.identity.domain.sessions import SessionRecord, SessionState

ENTERPRISE_AUTHENTICATION_METHODS = frozenset(
    {
        AuthenticationMethod.LDAP,
        AuthenticationMethod.OIDC,
        AuthenticationMethod.SAML,
    }
)


class IdentityGovernanceError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class IdentityGovernanceService:
    def __init__(
        self,
        *,
        session_repository: SessionRepository,
        api_credential_repository: ApiCredentialRepository,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._sessions = session_repository
        self._api_credentials = api_credential_repository
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()
        self._idempotent_results: dict[str, tuple[str, SessionRecord | ApiCredentialRecord]] = {}

    async def target_audit_fields(
        self, target_kind: str, target_reference: str
    ) -> tuple[str | None, tuple[tuple[str, str], ...]]:
        target: SessionRecord | ApiCredentialRecord | None
        if target_kind == "browser_session":
            target = await self._sessions.get_by_session_id(target_reference)
        elif target_kind == "personal_api_credential":
            target = await self._api_credentials.get_by_id(target_reference)
        else:
            raise ValueError("unsupported identity governance target kind")
        if target is None:
            return None, (("target_kind", target_kind),)
        return target.subject.subject_id, self._safe_target_metadata(target_kind, target)

    async def inventory(
        self,
        *,
        actor: AuthenticatedSubject,
        query: str | None,
        limit: int,
        correlation_id: str,
    ) -> IdentityGovernanceInventory:
        await self._require_enterprise_human(actor, correlation_id)
        if not 1 <= limit <= 100:
            raise ValueError("identity governance limit is outside platform bounds")
        normalized_query = (query or "").strip().casefold()
        if len(normalized_query) > 128:
            raise ValueError("identity governance query is outside platform bounds")
        now = self._clock()
        sessions = [
            record
            for record in await self._sessions.all_records()
            if record.subject.organization_id == actor.organization_id
            and record.subject.subject_id != actor.subject_id
            and record.state is SessionState.ACTIVE
            and now < record.absolute_expires_at
            and now < record.idle_expires_at
            and self._matches_session(record, normalized_query)
        ]
        api_credentials = [
            record
            for record in await self._api_credentials.all_records()
            if record.subject.organization_id == actor.organization_id
            and record.subject.subject_id != actor.subject_id
            and record.state is ApiCredentialState.ACTIVE
            and now < record.expires_at
            and self._matches_api_credential(record, normalized_query)
        ]
        sessions.sort(key=lambda item: (item.created_at, item.session_id), reverse=True)
        api_credentials.sort(key=lambda item: (item.created_at, item.credential_id), reverse=True)
        inventory = IdentityGovernanceInventory(
            sessions=tuple(sessions[:limit]),
            api_credentials=tuple(api_credentials[:limit]),
            truncated=len(sessions) > limit or len(api_credentials) > limit,
        )
        await self._audit(
            actor=actor,
            action="inventory_read",
            correlation_id=correlation_id,
            outcome="succeeded",
            result_code="identity_governance_inventory_read",
            metadata=(
                ("session_count", str(len(inventory.sessions))),
                ("api_credential_count", str(len(inventory.api_credentials))),
                ("filtered", str(bool(normalized_query)).lower()),
                ("truncated", str(inventory.truncated).lower()),
            ),
        )
        return inventory

    async def revoke_session(
        self,
        session_id: str,
        *,
        actor: AuthenticatedSubject,
        current_session_id: str,
        expected_version: int,
        reason: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> SessionRecord:
        await self._require_enterprise_human(actor, correlation_id)
        if session_id == current_session_id:
            await self._audit_denial(
                actor=actor,
                correlation_id=correlation_id,
                result_code="current_admin_session_protected",
                idempotency_key=idempotency_key,
                resource_type="resource.identity.session",
                scope_reference=session_id,
                target_subject_id=actor.subject_id,
                reason=reason,
                metadata=(("target_kind", "browser_session"), ("current_session", "true")),
            )
            raise IdentityGovernanceError("current_admin_session_protected")
        fingerprint = self._fingerprint(
            "session", session_id, expected_version, reason, actor.subject_id
        )
        async with self._mutation_lock:
            replay = await self._replay(
                idempotency_key=idempotency_key,
                fingerprint=fingerprint,
                actor=actor,
                correlation_id=correlation_id,
            )
            if replay is not None:
                if not isinstance(replay, SessionRecord):
                    raise IdentityGovernanceError("governance_idempotency_conflict")
                return replay
            record = await self._sessions.get_by_session_id(session_id)
            now = self._clock()
            if (
                record is None
                or record.subject.organization_id != actor.organization_id
                or record.subject.subject_id == actor.subject_id
                or record.state is not SessionState.ACTIVE
                or now >= record.absolute_expires_at
                or now >= record.idle_expires_at
                or record.version != expected_version
            ):
                await self._target_unavailable(
                    actor,
                    correlation_id,
                    idempotency_key,
                    target_kind="browser_session",
                    target_reference=session_id,
                    target=record,
                    reason=reason,
                )
            assert record is not None
            revoked = replace(
                record,
                version=record.version + 1,
                state=SessionState.REVOKED,
                revoked_at=now,
                revocation_reason="administrative_revocation",
            )
            await self._audit_revoke(
                actor=actor,
                target=record,
                reason=reason,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )
            if not await self._sessions.update(revoked, expected_version=record.version):
                await self._target_unavailable(
                    actor,
                    correlation_id,
                    idempotency_key,
                    target_kind="browser_session",
                    target_reference=session_id,
                    target=record,
                    reason=reason,
                )
            self._idempotent_results[idempotency_key] = (fingerprint, revoked)
            return revoked

    async def revoke_api_credential(
        self,
        credential_id: str,
        *,
        actor: AuthenticatedSubject,
        expected_version: int,
        reason: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> ApiCredentialRecord:
        await self._require_enterprise_human(actor, correlation_id)
        fingerprint = self._fingerprint(
            "api_credential", credential_id, expected_version, reason, actor.subject_id
        )
        async with self._mutation_lock:
            replay = await self._replay(
                idempotency_key=idempotency_key,
                fingerprint=fingerprint,
                actor=actor,
                correlation_id=correlation_id,
            )
            if replay is not None:
                if not isinstance(replay, ApiCredentialRecord):
                    raise IdentityGovernanceError("governance_idempotency_conflict")
                return replay
            record = await self._api_credentials.get_by_id(credential_id)
            now = self._clock()
            if (
                record is None
                or record.subject.organization_id != actor.organization_id
                or record.subject.subject_id == actor.subject_id
                or record.state is not ApiCredentialState.ACTIVE
                or now >= record.expires_at
                or record.version != expected_version
            ):
                await self._target_unavailable(
                    actor,
                    correlation_id,
                    idempotency_key,
                    target_kind="personal_api_credential",
                    target_reference=credential_id,
                    target=record,
                    reason=reason,
                )
            assert record is not None
            revoked = replace(
                record,
                version=record.version + 1,
                state=ApiCredentialState.REVOKED,
                revoked_at=now,
                revocation_reason="administrative_revocation",
            )
            await self._audit_revoke(
                actor=actor,
                target=record,
                reason=reason,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
            )
            if not await self._api_credentials.update(revoked, expected_version=record.version):
                await self._target_unavailable(
                    actor,
                    correlation_id,
                    idempotency_key,
                    target_kind="personal_api_credential",
                    target_reference=credential_id,
                    target=record,
                    reason=reason,
                )
            self._idempotent_results[idempotency_key] = (fingerprint, revoked)
            return revoked

    async def _replay(
        self,
        *,
        idempotency_key: str,
        fingerprint: str,
        actor: AuthenticatedSubject,
        correlation_id: str,
    ) -> SessionRecord | ApiCredentialRecord | None:
        prior = self._idempotent_results.get(idempotency_key)
        if prior is None:
            return None
        if prior[0] != fingerprint:
            await self._audit_denial(
                actor=actor,
                correlation_id=correlation_id,
                result_code="governance_idempotency_conflict",
                idempotency_key=idempotency_key,
            )
            raise IdentityGovernanceError("governance_idempotency_conflict")
        await self._audit(
            actor=actor,
            action="revocation_replayed",
            correlation_id=correlation_id,
            outcome="succeeded",
            result_code="identity_governance_revocation_replayed",
            idempotency_key=idempotency_key,
        )
        return prior[1]

    async def _target_unavailable(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        idempotency_key: str,
        *,
        target_kind: str,
        target_reference: str,
        target: SessionRecord | ApiCredentialRecord | None,
        reason: str,
    ) -> None:
        resource_type = (
            "resource.identity.session"
            if target_kind == "browser_session"
            else "resource.identity.api-credential"
        )
        metadata = (
            (("target_kind", target_kind),)
            if target is None
            else self._safe_target_metadata(target_kind, target)
        )
        await self._audit_denial(
            actor=actor,
            correlation_id=correlation_id,
            result_code="governance_target_unavailable",
            idempotency_key=idempotency_key,
            resource_type=resource_type,
            scope_reference=target_reference,
            target_subject_id=target.subject.subject_id if target is not None else None,
            reason=reason,
            metadata=metadata,
        )
        raise IdentityGovernanceError("governance_target_unavailable")

    async def _audit_revoke(
        self,
        *,
        actor: AuthenticatedSubject,
        target: SessionRecord | ApiCredentialRecord,
        reason: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> None:
        if isinstance(target, SessionRecord):
            action = "session_revoked"
            resource_type = "resource.identity.session"
            scope_reference = target.session_id
            metadata: tuple[tuple[str, str], ...] = (
                ("credential_kind", target.credential_kind.value),
                ("provider_id", target.subject.provider_id),
                ("created_at", target.created_at.isoformat()),
                ("absolute_expires_at", target.absolute_expires_at.isoformat()),
                ("idle_expires_at", target.idle_expires_at.isoformat()),
                ("target_version", str(target.version)),
            )
        else:
            action = "api_credential_revoked"
            resource_type = "resource.identity.api-credential"
            scope_reference = target.credential_id
            metadata = (
                ("display_name", target.display_name),
                ("grant_count", str(len(target.grants))),
                ("provider_id", target.subject.provider_id),
                ("created_at", target.created_at.isoformat()),
                ("expires_at", target.expires_at.isoformat()),
                ("target_version", str(target.version)),
            )
        await self._audit(
            actor=actor,
            action=action,
            correlation_id=correlation_id,
            outcome="succeeded",
            result_code=f"identity_governance_{action}",
            resource_type=resource_type,
            scope_reference=scope_reference,
            target_subject_id=target.subject.subject_id,
            reason=reason,
            idempotency_key=idempotency_key,
            metadata=metadata,
        )

    async def _audit_denial(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
        idempotency_key: str | None = None,
        resource_type: str = "resource.identity.governance",
        scope_reference: str | None = None,
        target_subject_id: str | None = None,
        reason: str | None = None,
        metadata: tuple[tuple[str, str], ...] = (),
    ) -> None:
        await self._audit(
            actor=actor,
            action="denied",
            correlation_id=correlation_id,
            outcome="denied",
            result_code=result_code,
            idempotency_key=idempotency_key,
            resource_type=resource_type,
            scope_reference=scope_reference,
            target_subject_id=target_subject_id,
            reason=reason,
            metadata=metadata,
        )

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        action: str,
        correlation_id: str,
        outcome: str,
        result_code: str,
        resource_type: str = "resource.identity.governance",
        scope_reference: str | None = None,
        target_subject_id: str | None = None,
        reason: str | None = None,
        idempotency_key: str | None = None,
        metadata: tuple[tuple[str, str], ...] = (),
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=f"atlas.identity.governance.{action}",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id=None,
                resource_type=resource_type,
                scope_reference=scope_reference,
                decision_id=None,
                outcome=outcome,
                result_code=result_code,
                target_subject_id=target_subject_id,
                reason=reason,
                idempotency_key=idempotency_key,
                target_metadata=metadata,
            )
        )

    async def _require_enterprise_human(
        self, actor: AuthenticatedSubject, correlation_id: str
    ) -> None:
        if (
            actor.kind is not SubjectKind.HUMAN
            or actor.authentication_method not in ENTERPRISE_AUTHENTICATION_METHODS
        ):
            await self._audit_denial(
                actor=actor,
                correlation_id=correlation_id,
                result_code="enterprise_human_required",
            )
            raise IdentityGovernanceError("enterprise_human_required")

    @staticmethod
    def _matches_session(record: SessionRecord, query: str) -> bool:
        if not query:
            return True
        return any(
            query in value.casefold()
            for value in (
                record.session_id,
                record.subject.subject_id,
                record.subject.display_name,
                record.subject.provider_id,
            )
        )

    @staticmethod
    def _matches_api_credential(record: ApiCredentialRecord, query: str) -> bool:
        if not query:
            return True
        return any(
            query in value.casefold()
            for value in (
                record.credential_id,
                record.subject.subject_id,
                record.subject.display_name,
                record.subject.provider_id,
                record.display_name,
                record.purpose,
            )
        )

    @staticmethod
    def _fingerprint(
        resource_kind: str,
        resource_id: str,
        expected_version: int,
        reason: str,
        actor_subject_id: str,
    ) -> str:
        material = "\x1f".join(
            (resource_kind, resource_id, str(expected_version), reason, actor_subject_id)
        )
        return sha256(material.encode()).hexdigest()

    @staticmethod
    def _safe_target_metadata(
        target_kind: str, target: SessionRecord | ApiCredentialRecord
    ) -> tuple[tuple[str, str], ...]:
        if isinstance(target, SessionRecord):
            return (
                ("target_kind", target_kind),
                ("target_version", str(target.version)),
                ("provider_id", target.subject.provider_id),
                ("state", target.state.value),
                ("credential_kind", target.credential_kind.value),
                ("created_at", target.created_at.isoformat()),
                ("absolute_expires_at", target.absolute_expires_at.isoformat()),
                ("idle_expires_at", target.idle_expires_at.isoformat()),
            )
        return (
            ("target_kind", target_kind),
            ("target_version", str(target.version)),
            ("provider_id", target.subject.provider_id),
            ("state", target.state.value),
            ("display_name", target.display_name),
            ("grant_count", str(len(target.grants))),
            ("created_at", target.created_at.isoformat()),
            ("expires_at", target.expires_at.isoformat()),
        )
