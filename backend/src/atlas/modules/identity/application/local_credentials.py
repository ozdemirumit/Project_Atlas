"""ATLAS-030 SS6.3 / SS11: local bootstrap and recovery credential lifecycle."""

from __future__ import annotations

import base64
import binascii
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.identity.application.local_credential_ports import LocalCredentialRepository
from atlas.modules.identity.domain.local_credentials import (
    DEFAULT_LOCAL_CREDENTIAL_LOCKOUT_POLICY,
    LocalCredentialKind,
    LocalCredentialLockoutPolicy,
    LocalCredentialRecord,
    LocalCredentialState,
    LocalRecoveryActivation,
    hash_local_password,
    verify_local_password,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationInput,
    AuthenticationMethod,
    SubjectKind,
)

BOOTSTRAP_SETUP_ROLE_ID = "role.platform.bootstrap-setup"
LOCAL_PROVIDER_ID = "provider.local.bootstrap-recovery"


class LocalCredentialError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class LocalCredentialService:
    """Owns the local bootstrap-administrator and recovery credential lifecycle: creation,
    authentication (with lockout), rotation, disablement, and time-bound recovery activation
    (SS6.3, SS11). Not an `IdentityProvider` itself -- see `LocalCredentialIdentityProvider`."""

    def __init__(
        self,
        *,
        repository: LocalCredentialRepository,
        audit_sink: AuditSink,
        lockout_policy: LocalCredentialLockoutPolicy = DEFAULT_LOCAL_CREDENTIAL_LOCKOUT_POLICY,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._audit_sink = audit_sink
        self._lockout_policy = lockout_policy
        self._clock = clock or (lambda: datetime.now(UTC))

    async def bootstrap_administrator(
        self,
        *,
        subject_id: str,
        organization_id: str,
        display_name: str,
        role_ids: tuple[str, ...],
        password: str,
        deployment_ownership_verified: bool,
        correlation_id: str,
    ) -> LocalCredentialRecord:
        """SS11 steps 1-4: verify deployment ownership, accept the first credential without
        logging it, and require its replacement before the administrator's real role grants
        apply (`authenticate` enforces the restricted `BOOTSTRAP_SETUP_ROLE_ID` scope while the
        record remains `MUST_REPLACE`)."""
        if not deployment_ownership_verified:
            raise LocalCredentialError("local_bootstrap_ownership_unverified")
        record = await self._create(
            subject_id=subject_id,
            kind=LocalCredentialKind.BOOTSTRAP_ADMINISTRATOR,
            organization_id=organization_id,
            display_name=display_name,
            role_ids=role_ids,
            password=password,
            state=LocalCredentialState.MUST_REPLACE,
        )
        await self._audit(
            correlation_id=correlation_id,
            event_type="atlas.identity.local-credential.created",
            subject_id=subject_id,
            result_code="local_credential_created",
        )
        return record

    async def create_recovery_credential(
        self,
        *,
        subject_id: str,
        organization_id: str,
        display_name: str,
        role_ids: tuple[str, ...],
        password: str,
        correlation_id: str,
    ) -> LocalCredentialRecord:
        """The recovery credential itself carries no forced replacement -- it is inert by
        default and only usable during an explicit `activate_recovery` window (SS11)."""
        record = await self._create(
            subject_id=subject_id,
            kind=LocalCredentialKind.RECOVERY,
            organization_id=organization_id,
            display_name=display_name,
            role_ids=role_ids,
            password=password,
            state=LocalCredentialState.ACTIVE,
        )
        await self._audit(
            correlation_id=correlation_id,
            event_type="atlas.identity.local-credential.created",
            subject_id=subject_id,
            result_code="local_credential_created",
        )
        return record

    async def _create(
        self,
        *,
        subject_id: str,
        kind: LocalCredentialKind,
        organization_id: str,
        display_name: str,
        role_ids: tuple[str, ...],
        password: str,
        state: LocalCredentialState,
    ) -> LocalCredentialRecord:
        now = self._clock()
        try:
            record = LocalCredentialRecord(
                subject_id=subject_id,
                kind=kind,
                organization_id=organization_id,
                display_name=display_name,
                role_ids=role_ids,
                password_hash=hash_local_password(password),
                state=state,
                version=1,
                created_at=now,
                updated_at=now,
            )
        except ValueError as error:
            raise LocalCredentialError("local_credential_invalid") from error
        if not await self._repository.create(record):
            raise LocalCredentialError("local_credential_already_exists")
        return record

    async def authenticate(
        self, *, subject_id: str, password: str, correlation_id: str
    ) -> AuthenticatedSubject | None:
        """SS13: "generic invalid-credential responses" -- every denial path returns `None` with
        the same audited `result_code`, whether the subject is unknown, disabled, locked,
        recovery-inactive, or simply wrong on the password, so no path leaks which case applied
        to a caller. A distinct, audit-only `local_credential_lockout` event still records when a
        lockout is newly triggered (SS16)."""
        now = self._clock()
        record = await self._repository.get(subject_id)
        if record is None:
            await self._deny(correlation_id, subject_id)
            return None
        if record.state is LocalCredentialState.DISABLED:
            await self._deny(correlation_id, subject_id)
            return None
        if record.kind is LocalCredentialKind.RECOVERY:
            activation = await self._repository.get_recovery_activation(subject_id)
            if activation is None or not activation.is_active_at(now):
                await self._deny(correlation_id, subject_id)
                return None
        effective = record
        if record.state is LocalCredentialState.LOCKED:
            if record.locked_until is not None and now < record.locked_until:
                await self._deny(correlation_id, subject_id)
                return None
            effective = replace(
                record,
                state=LocalCredentialState.ACTIVE,
                failed_attempt_count=0,
                locked_until=None,
            )
        if not verify_local_password(password, record.password_hash):
            await self._record_failure(effective, now, correlation_id)
            await self._deny(correlation_id, subject_id)
            return None
        updated = replace(
            effective,
            failed_attempt_count=0,
            locked_until=None,
            last_used_at=now,
            updated_at=now,
        )
        if not await self._repository.update(updated, expected_version=record.version):
            await self._deny(correlation_id, subject_id)
            return None
        if record.kind is LocalCredentialKind.RECOVERY:
            activation = await self._repository.get_recovery_activation(subject_id)
            if activation is not None and activation.used_at is None:
                await self._repository.save_recovery_activation(replace(activation, used_at=now))
                await self._audit(
                    correlation_id=correlation_id,
                    event_type="atlas.identity.local-recovery.used",
                    subject_id=subject_id,
                    result_code="local_recovery_used",
                )
        role_ids = (
            (BOOTSTRAP_SETUP_ROLE_ID,)
            if updated.state is LocalCredentialState.MUST_REPLACE
            else updated.role_ids
        )
        await self._audit(
            correlation_id=correlation_id,
            event_type="atlas.identity.authentication.succeeded",
            subject_id=subject_id,
            result_code="local_identity_accepted",
        )
        return AuthenticatedSubject(
            subject_id=updated.subject_id,
            display_name=updated.display_name,
            kind=SubjectKind.HUMAN,
            provider_id=LOCAL_PROVIDER_ID,
            authentication_method=AuthenticationMethod.LOCAL,
            assurance_level=AssuranceLevel.SINGLE_FACTOR,
            authenticated_at=now,
            organization_id=updated.organization_id,
            role_ids=role_ids,
        )

    async def _record_failure(
        self, record: LocalCredentialRecord, now: datetime, correlation_id: str
    ) -> None:
        failed_attempt_count = record.failed_attempt_count + 1
        locked = failed_attempt_count >= self._lockout_policy.max_failed_attempts
        updated = replace(
            record,
            state=LocalCredentialState.LOCKED if locked else record.state,
            failed_attempt_count=failed_attempt_count,
            locked_until=(now + self._lockout_policy.lockout_duration) if locked else None,
            updated_at=now,
        )
        if await self._repository.update(updated, expected_version=record.version) and locked:
            await self._audit(
                correlation_id=correlation_id,
                event_type="atlas.identity.local-credential.lockout",
                subject_id=record.subject_id,
                result_code="local_credential_lockout",
            )

    async def replace_credential(
        self,
        *,
        subject_id: str,
        current_password: str,
        new_password: str,
        correlation_id: str,
    ) -> LocalCredentialRecord:
        """SS11: "The bootstrap credential must be changed or replaced before normal use." Also
        serves SS6.3's "rotation" for a routine, already-active local credential."""
        now = self._clock()
        record = await self._repository.get(subject_id)
        if record is None or record.state is LocalCredentialState.DISABLED:
            raise LocalCredentialError("local_credential_unavailable")
        if (
            record.state is LocalCredentialState.LOCKED
            and record.locked_until is not None
            and now < record.locked_until
        ):
            raise LocalCredentialError("local_credential_locked")
        if not verify_local_password(current_password, record.password_hash):
            raise LocalCredentialError("local_credential_invalid")
        if verify_local_password(new_password, record.password_hash):
            raise LocalCredentialError("local_credential_reuse_denied")
        try:
            new_hash = hash_local_password(new_password)
        except ValueError as error:
            raise LocalCredentialError("local_credential_invalid") from error
        updated = replace(
            record,
            password_hash=new_hash,
            state=LocalCredentialState.ACTIVE,
            failed_attempt_count=0,
            locked_until=None,
            updated_at=now,
            version=record.version + 1,
        )
        if not await self._repository.update(updated, expected_version=record.version):
            raise LocalCredentialError("local_credential_conflict")
        await self._audit(
            correlation_id=correlation_id,
            event_type="atlas.identity.local-credential.replaced",
            subject_id=subject_id,
            result_code="local_credential_replaced",
        )
        return updated

    async def disable(
        self, *, subject_id: str, disabled_by: str, reason: str, correlation_id: str
    ) -> LocalCredentialRecord:
        """SS6.3: "disablement." Preserving a `RECOVERY`-kind credential's own ability to be
        disabled independently of the bootstrap administrator credential is how "disabling
        routine local access must preserve a separately governed recovery path" (SS6.3) stays
        possible -- disabling one kind never touches the other subject's record."""
        record = await self._repository.get(subject_id)
        if record is None:
            raise LocalCredentialError("local_credential_unavailable")
        if record.state is LocalCredentialState.DISABLED:
            raise LocalCredentialError("local_credential_already_disabled")
        if not reason.strip():
            raise LocalCredentialError("local_credential_disable_reason_required")
        now = self._clock()
        updated = replace(
            record,
            state=LocalCredentialState.DISABLED,
            failed_attempt_count=0,
            locked_until=None,
            disabled_at=now,
            disabled_by=disabled_by,
            disable_reason=reason.strip(),
            updated_at=now,
            version=record.version + 1,
        )
        if not await self._repository.update(updated, expected_version=record.version):
            raise LocalCredentialError("local_credential_conflict")
        await self._audit(
            correlation_id=correlation_id,
            event_type="atlas.identity.local-credential.disabled",
            subject_id=subject_id,
            actor_subject_id=disabled_by,
            result_code="local_credential_disabled",
        )
        return updated

    async def activate_recovery(
        self,
        *,
        subject_id: str,
        justification: str,
        activated_by: str,
        ttl: timedelta,
        correlation_id: str,
    ) -> LocalRecoveryActivation:
        """SS11: "documented justification, time-bound activation." Refuses to open a second
        overlapping window for the same recovery subject."""
        record = await self._repository.get(subject_id)
        if record is None or record.kind is not LocalCredentialKind.RECOVERY:
            raise LocalCredentialError("local_recovery_unavailable")
        if record.state is LocalCredentialState.DISABLED:
            raise LocalCredentialError("local_recovery_unavailable")
        now = self._clock()
        existing = await self._repository.get_recovery_activation(subject_id)
        if existing is not None and existing.is_active_at(now):
            raise LocalCredentialError("local_recovery_already_active")
        try:
            activation = LocalRecoveryActivation(
                activation_id=f"activation.{uuid4().hex}",
                subject_id=subject_id,
                justification=justification,
                activated_by=activated_by,
                activated_at=now,
                expires_at=now + ttl,
            )
        except ValueError as error:
            raise LocalCredentialError("local_recovery_activation_invalid") from error
        await self._repository.save_recovery_activation(activation)
        await self._audit(
            correlation_id=correlation_id,
            event_type="atlas.identity.local-recovery.activated",
            subject_id=subject_id,
            actor_subject_id=activated_by,
            result_code="local_recovery_activated",
        )
        return activation

    async def review_recovery(
        self, *, subject_id: str, reviewed_by: str, notes: str, correlation_id: str
    ) -> LocalRecoveryActivation:
        """SS11: "post-use review." Only a used activation can be reviewed, and only once."""
        activation = await self._repository.get_recovery_activation(subject_id)
        if activation is None or activation.used_at is None:
            raise LocalCredentialError("local_recovery_review_unavailable")
        if activation.reviewed_at is not None:
            raise LocalCredentialError("local_recovery_already_reviewed")
        now = self._clock()
        updated = replace(
            activation,
            reviewed_at=now,
            reviewed_by=reviewed_by,
            review_notes=notes.strip() or None,
        )
        await self._repository.save_recovery_activation(updated)
        await self._audit(
            correlation_id=correlation_id,
            event_type="atlas.identity.local-recovery.reviewed",
            subject_id=subject_id,
            actor_subject_id=reviewed_by,
            result_code="local_recovery_reviewed",
        )
        return updated

    async def _audit(
        self,
        *,
        correlation_id: str,
        event_type: str,
        subject_id: str,
        result_code: str,
        actor_subject_id: str | None = None,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=event_type,
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor_subject_id or subject_id,
                actor_type=None,
                authentication_method=AuthenticationMethod.LOCAL.value,
                assurance_level=None,
                permission_id=None,
                resource_type="resource.identity.local-credential",
                scope_reference=subject_id,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                target_subject_id=subject_id,
            )
        )

    async def _deny(self, correlation_id: str, subject_id: str) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.identity.authentication.denied",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=None,
                actor_type=None,
                authentication_method=AuthenticationMethod.LOCAL.value,
                assurance_level=None,
                permission_id=None,
                resource_type="resource.identity.session",
                scope_reference=LOCAL_PROVIDER_ID,
                decision_id=None,
                outcome="denied",
                result_code="local_credential_invalid",
            )
        )


class LocalCredentialIdentityProvider:
    """`IdentityProvider` over `LocalCredentialService`. The HTTP Basic username IS the
    credential's `subject_id` -- local bootstrap/recovery accounts are administrative,
    stable-identifier-named accounts (e.g. `subject.bootstrap-administrator.primary`), not
    general end-user logins."""

    def __init__(self, service: LocalCredentialService) -> None:
        self._service = service

    async def authenticate(
        self, authentication_input: AuthenticationInput
    ) -> AuthenticatedSubject | None:
        if (
            authentication_input.authorization_scheme != "basic"
            or authentication_input.credential is None
        ):
            return None
        try:
            decoded = base64.b64decode(authentication_input.credential, validate=True).decode(
                "utf-8"
            )
        except (binascii.Error, UnicodeDecodeError):
            return None
        subject_id, separator, password = decoded.partition(":")
        if separator != ":" or not subject_id:
            return None
        return await self._service.authenticate(
            subject_id=subject_id,
            password=password,
            correlation_id=authentication_input.correlation_id,
        )
