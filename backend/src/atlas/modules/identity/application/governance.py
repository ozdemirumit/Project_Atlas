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
from atlas.modules.identity.application.identity_status_ports import IdentityStatusRepository
from atlas.modules.identity.application.session_ports import SessionRepository
from atlas.modules.identity.domain.api_credentials import ApiCredentialRecord, ApiCredentialState
from atlas.modules.identity.domain.governance import (
    IdentityGovernanceInventory,
    IdentityGovernanceSubject,
)
from atlas.modules.identity.domain.identity_status import (
    IdentityDisablementResult,
    IdentityLifecycleState,
    IdentityStatusRecord,
)
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
        identity_status_repository: IdentityStatusRepository | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._sessions = session_repository
        self._api_credentials = api_credential_repository
        self._identity_statuses = identity_status_repository
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))
        self._mutation_lock = asyncio.Lock()
        self._idempotent_results: dict[
            str,
            tuple[str, SessionRecord | ApiCredentialRecord | IdentityDisablementResult],
        ] = {}

    async def target_audit_fields(
        self, target_kind: str, target_reference: str
    ) -> tuple[str | None, tuple[tuple[str, str], ...]]:
        target: SessionRecord | ApiCredentialRecord | None
        if target_kind == "browser_session":
            target = await self._sessions.get_by_session_id(target_reference)
        elif target_kind == "personal_api_credential":
            target = await self._api_credentials.get_by_id(target_reference)
        elif target_kind == "identity_subject":
            if self._identity_statuses is None:
                return None, (("target_kind", target_kind),)
            status = await self._identity_statuses.get(target_reference)
            if status is None:
                return None, (("target_kind", target_kind),)
            return status.subject.subject_id, self._safe_identity_metadata(status)
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
        status_records = (
            await self._identity_statuses.all_records()
            if self._identity_statuses is not None
            else ()
        )
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
        subjects = [
            IdentityGovernanceSubject(
                status=status,
                active_session_count=sum(
                    1
                    for record in sessions
                    if record.subject.subject_id == status.subject.subject_id
                ),
                active_api_credential_count=sum(
                    1
                    for record in api_credentials
                    if record.subject.subject_id == status.subject.subject_id
                ),
            )
            for status in status_records
            if status.subject.organization_id == actor.organization_id
            and status.subject.subject_id != actor.subject_id
            and self._matches_identity_status(status, normalized_query)
        ]
        subjects.sort(
            key=lambda item: (
                item.status.subject.display_name.casefold(),
                item.status.subject.subject_id,
            )
        )
        inventory = IdentityGovernanceInventory(
            subjects=tuple(subjects[:limit]),
            sessions=tuple(sessions[:limit]),
            api_credentials=tuple(api_credentials[:limit]),
            truncated=(
                len(subjects) > limit or len(sessions) > limit or len(api_credentials) > limit
            ),
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
                ("subject_count", str(len(inventory.subjects))),
                ("filtered", str(bool(normalized_query)).lower()),
                ("truncated", str(inventory.truncated).lower()),
            ),
        )
        return inventory

    async def disable_identity(
        self,
        subject_id: str,
        *,
        actor: AuthenticatedSubject,
        expected_version: int,
        reason: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> IdentityDisablementResult:
        await self._require_enterprise_human(actor, correlation_id)
        if subject_id == actor.subject_id:
            await self._audit_denial(
                actor=actor,
                correlation_id=correlation_id,
                result_code="current_admin_identity_protected",
                idempotency_key=idempotency_key,
                resource_type="resource.identity.subject",
                scope_reference=subject_id,
                target_subject_id=subject_id,
                reason=reason,
                metadata=(("target_kind", "identity_subject"),),
            )
            raise IdentityGovernanceError("current_admin_identity_protected")
        if self._identity_statuses is None:
            raise RuntimeError("identity status repository is required for disablement")
        fingerprint = self._fingerprint(
            "identity_subject", subject_id, expected_version, reason, actor.subject_id
        )
        async with self._mutation_lock:
            replay = await self._replay(
                idempotency_key=idempotency_key,
                fingerprint=fingerprint,
                actor=actor,
                correlation_id=correlation_id,
                action="disablement_replayed",
                target_subject_id=subject_id,
                reason=reason,
            )
            if replay is not None:
                if not isinstance(replay, IdentityDisablementResult):
                    raise IdentityGovernanceError("governance_idempotency_conflict")
                return replay

            status = await self._identity_statuses.get(subject_id)
            if (
                status is None
                or status.subject.organization_id != actor.organization_id
                or status.subject.kind is not SubjectKind.HUMAN
                or status.subject.authentication_method not in ENTERPRISE_AUTHENTICATION_METHODS
                or status.state is not IdentityLifecycleState.ACTIVE
                or status.version != expected_version
            ):
                await self._identity_target_unavailable(
                    actor=actor,
                    target=status,
                    target_reference=subject_id,
                    reason=reason,
                    idempotency_key=idempotency_key,
                    correlation_id=correlation_id,
                )
            assert status is not None
            now = self._clock()
            active_sessions = tuple(await self._sessions.active_for_subject(subject_id))
            active_api_credentials = tuple(
                await self._api_credentials.active_for_subject(subject_id)
            )
            revoked_sessions = tuple(
                replace(
                    record,
                    version=record.version + 1,
                    state=SessionState.REVOKED,
                    revoked_at=now,
                    revocation_reason="identity_disabled",
                )
                for record in active_sessions
            )
            revoked_api_credentials = tuple(
                replace(
                    record,
                    version=record.version + 1,
                    state=ApiCredentialState.REVOKED,
                    revoked_at=now,
                    revocation_reason="identity_disabled",
                )
                for record in active_api_credentials
            )
            disabled = replace(
                status,
                version=status.version + 1,
                state=IdentityLifecycleState.DISABLED,
                disabled_at=now,
                disabled_by=actor.subject_id,
                disable_reason=reason,
            )
            counts = (
                ("revoked_session_count", str(len(revoked_sessions))),
                ("revoked_api_credential_count", str(len(revoked_api_credentials))),
            )
            await self._audit(
                actor=actor,
                action="disablement_started",
                correlation_id=correlation_id,
                outcome="started",
                result_code="identity_disablement_started",
                resource_type="resource.identity.subject",
                scope_reference=subject_id,
                target_subject_id=subject_id,
                reason=reason,
                idempotency_key=idempotency_key,
                metadata=self._safe_identity_metadata(status) + counts,
            )

            applied_sessions: list[tuple[SessionRecord, SessionRecord]] = []
            applied_credentials: list[tuple[ApiCredentialRecord, ApiCredentialRecord]] = []
            status_applied = False
            try:
                for original_session, revoked_session in zip(
                    active_sessions, revoked_sessions, strict=True
                ):
                    if not await self._sessions.update(
                        revoked_session, expected_version=original_session.version
                    ):
                        raise RuntimeError("session fan-out update conflicted")
                    applied_sessions.append((original_session, revoked_session))
                for original_credential, revoked_credential in zip(
                    active_api_credentials, revoked_api_credentials, strict=True
                ):
                    if not await self._api_credentials.update(
                        revoked_credential, expected_version=original_credential.version
                    ):
                        raise RuntimeError("API credential fan-out update conflicted")
                    applied_credentials.append((original_credential, revoked_credential))
                if not await self._identity_statuses.update(
                    disabled, expected_version=status.version
                ):
                    raise RuntimeError("identity status update conflicted")
                status_applied = True
                result = IdentityDisablementResult(
                    status=disabled,
                    revoked_session_count=len(revoked_sessions),
                    revoked_api_credential_count=len(revoked_api_credentials),
                )
                await self._audit(
                    actor=actor,
                    action="disabled",
                    correlation_id=correlation_id,
                    outcome="succeeded",
                    result_code="identity_disabled",
                    resource_type="resource.identity.subject",
                    scope_reference=subject_id,
                    target_subject_id=subject_id,
                    reason=reason,
                    idempotency_key=idempotency_key,
                    metadata=self._safe_identity_metadata(disabled) + counts,
                )
            except Exception as exc:
                await self._compensate_disablement(
                    original_status=status,
                    disabled_status=disabled if status_applied else None,
                    sessions=applied_sessions,
                    api_credentials=applied_credentials,
                )
                await self._audit(
                    actor=actor,
                    action="disablement_compensated",
                    correlation_id=correlation_id,
                    outcome="compensated",
                    result_code="identity_disablement_compensated",
                    resource_type="resource.identity.subject",
                    scope_reference=subject_id,
                    target_subject_id=subject_id,
                    reason=reason,
                    idempotency_key=idempotency_key,
                    metadata=(
                        ("restored_session_count", str(len(applied_sessions))),
                        ("restored_api_credential_count", str(len(applied_credentials))),
                    ),
                )
                raise IdentityGovernanceError("identity_disablement_unavailable") from exc
            self._idempotent_results[idempotency_key] = (fingerprint, result)
            return result

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
        action: str = "revocation_replayed",
        target_subject_id: str | None = None,
        reason: str | None = None,
    ) -> SessionRecord | ApiCredentialRecord | IdentityDisablementResult | None:
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
        metadata: tuple[tuple[str, str], ...] = ()
        scope_reference: str | None = None
        resource_type = "resource.identity.governance"
        if isinstance(prior[1], IdentityDisablementResult):
            scope_reference = prior[1].status.subject.subject_id
            resource_type = "resource.identity.subject"
            metadata = (
                ("revoked_session_count", str(prior[1].revoked_session_count)),
                (
                    "revoked_api_credential_count",
                    str(prior[1].revoked_api_credential_count),
                ),
            )
        await self._audit(
            actor=actor,
            action=action,
            correlation_id=correlation_id,
            outcome="succeeded",
            result_code=f"identity_governance_{action}",
            idempotency_key=idempotency_key,
            target_subject_id=target_subject_id,
            reason=reason,
            resource_type=resource_type,
            scope_reference=scope_reference,
            metadata=metadata,
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

    async def _identity_target_unavailable(
        self,
        *,
        actor: AuthenticatedSubject,
        target: IdentityStatusRecord | None,
        target_reference: str,
        reason: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> None:
        await self._audit_denial(
            actor=actor,
            correlation_id=correlation_id,
            result_code="governance_target_unavailable",
            idempotency_key=idempotency_key,
            resource_type="resource.identity.subject",
            scope_reference=target_reference,
            target_subject_id=target.subject.subject_id if target is not None else None,
            reason=reason,
            metadata=(
                (("target_kind", "identity_subject"),)
                if target is None
                else self._safe_identity_metadata(target)
            ),
        )
        raise IdentityGovernanceError("governance_target_unavailable")

    async def _compensate_disablement(
        self,
        *,
        original_status: IdentityStatusRecord,
        disabled_status: IdentityStatusRecord | None,
        sessions: list[tuple[SessionRecord, SessionRecord]],
        api_credentials: list[tuple[ApiCredentialRecord, ApiCredentialRecord]],
    ) -> None:
        for original_credential, revoked_credential in reversed(api_credentials):
            restored_credential = replace(
                original_credential, version=revoked_credential.version + 1
            )
            if not await self._api_credentials.update(
                restored_credential, expected_version=revoked_credential.version
            ):
                raise RuntimeError("API credential compensation failed")
        for original_session, revoked_session in reversed(sessions):
            restored_session = replace(original_session, version=revoked_session.version + 1)
            if not await self._sessions.update(
                restored_session, expected_version=revoked_session.version
            ):
                raise RuntimeError("session compensation failed")
        if disabled_status is not None:
            assert self._identity_statuses is not None
            restored_status = replace(original_status, version=disabled_status.version + 1)
            if not await self._identity_statuses.update(
                restored_status, expected_version=disabled_status.version
            ):
                raise RuntimeError("identity status compensation failed")

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
    def _matches_identity_status(record: IdentityStatusRecord, query: str) -> bool:
        if not query:
            return True
        return any(
            query in value.casefold()
            for value in (
                record.subject.subject_id,
                record.subject.display_name,
                record.subject.provider_id,
                record.state.value,
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

    @staticmethod
    def _safe_identity_metadata(
        status: IdentityStatusRecord,
    ) -> tuple[tuple[str, str], ...]:
        metadata: tuple[tuple[str, str], ...] = (
            ("target_kind", "identity_subject"),
            ("target_version", str(status.version)),
            ("provider_id", status.subject.provider_id),
            ("subject_kind", status.subject.kind.value),
            ("authentication_method", status.subject.authentication_method.value),
            ("state", status.state.value),
            ("observed_at", status.observed_at.isoformat()),
        )
        if status.disabled_at is not None:
            metadata += (("disabled_at", status.disabled_at.isoformat()),)
        return metadata
