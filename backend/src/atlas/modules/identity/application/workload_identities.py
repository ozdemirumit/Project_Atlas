from __future__ import annotations

import asyncio
import base64
import hmac
import json
import secrets
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.identity.application.workload_identity_ports import (
    WorkloadIdentityRepository,
)
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.identity.domain.workload_identities import (
    IssuedWorkloadCredential,
    WorkloadCredentialRecord,
    WorkloadCredentialState,
    WorkloadIdentityInventory,
    WorkloadIdentityRecord,
    WorkloadIdentityState,
)

ENTERPRISE_METHODS = frozenset(
    {AuthenticationMethod.LDAP, AuthenticationMethod.OIDC, AuthenticationMethod.SAML}
)


class WorkloadIdentityError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class WorkloadIdentityService:
    def __init__(
        self,
        *,
        repository: WorkloadIdentityRepository,
        audit_sink: AuditSink,
        environment_id: str,
        signing_keys: dict[int, bytes] | None = None,
        clock: Callable[[], datetime] | None = None,
        max_lifetime: timedelta = timedelta(minutes=30),
        max_overlap: timedelta = timedelta(minutes=5),
        clock_skew: timedelta = timedelta(seconds=30),
    ) -> None:
        self._repository = repository
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._max_lifetime = max_lifetime
        self._max_overlap = max_overlap
        self._clock_skew = clock_skew
        self._signing_keys = signing_keys or {1: secrets.token_bytes(32)}
        if not self._signing_keys or any(version < 1 for version in self._signing_keys):
            raise ValueError("workload signing keys are invalid")
        if any(len(key) < 32 for key in self._signing_keys.values()):
            raise ValueError("workload signing keys must contain at least 256 bits")
        self._active_key_version = max(self._signing_keys)
        self._lock = asyncio.Lock()
        self._idempotent_results: dict[
            str, tuple[str, IssuedWorkloadCredential | WorkloadCredentialRecord]
        ] = {}

    async def inventory(
        self,
        *,
        actor: AuthenticatedSubject,
        query: str | None,
        limit: int,
        correlation_id: str,
    ) -> WorkloadIdentityInventory:
        self._require_enterprise_human(actor)
        if not 1 <= limit <= 100:
            raise ValueError("workload inventory limit is outside platform bounds")
        normalized_query = (query or "").strip().casefold()
        if len(normalized_query) > 128:
            raise ValueError("workload inventory query is outside platform bounds")
        now = self._clock()
        identities = [
            record
            for record in await self._repository.all_identities()
            if record.organization_id == actor.organization_id
            and record.environment_id == self._environment_id
            and self._matches_identity(record, normalized_query)
        ]
        visible_ids = {record.identity_id for record in identities}
        credentials = [
            self._effective_credential(record, now)
            for record in await self._repository.all_credentials()
            if record.identity_id in visible_ids
            and self._matches_credential(record, normalized_query)
        ]
        identities.sort(key=lambda item: (item.display_name.casefold(), item.identity_id))
        credentials.sort(key=lambda item: (item.issued_at, item.credential_id), reverse=True)
        result = WorkloadIdentityInventory(
            identities=tuple(identities[:limit]),
            credentials=tuple(credentials[:limit]),
            truncated=len(identities) > limit or len(credentials) > limit,
        )
        await self._audit(
            actor=actor,
            action="inventory_read",
            correlation_id=correlation_id,
            outcome="succeeded",
            result_code="workload_identity_inventory_read",
            metadata=(
                ("identity_count", str(len(result.identities))),
                ("credential_count", str(len(result.credentials))),
                ("filtered", str(bool(normalized_query)).lower()),
                ("truncated", str(result.truncated).lower()),
            ),
        )
        return result

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        identity_id: str,
        display_name: str,
        service_id: str,
        instance_id: str,
        owner_subject_id: str,
        purpose: str,
        audiences: tuple[str, ...],
        secret_reference_ids: tuple[str, ...],
        lifetime: timedelta,
        reason: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> IssuedWorkloadCredential:
        self._require_enterprise_human(actor)
        self._validate_lifetime(lifetime)
        self._validate_reason(reason)
        fingerprint = self._fingerprint(
            "create",
            actor.subject_id,
            identity_id,
            display_name,
            service_id,
            instance_id,
            owner_subject_id,
            purpose,
            audiences,
            secret_reference_ids,
            int(lifetime.total_seconds()),
            reason,
        )
        async with self._lock:
            replay = self._replay(idempotency_key, fingerprint)
            if replay is not None:
                if not isinstance(replay, IssuedWorkloadCredential):
                    raise WorkloadIdentityError("workload_idempotency_conflict")
                await self._audit(
                    actor=actor,
                    action="creation_replayed",
                    correlation_id=correlation_id,
                    outcome="succeeded",
                    result_code="workload_identity_creation_replayed",
                    target_subject_id=replay.identity.identity_id,
                    reason=reason,
                    idempotency_key=idempotency_key,
                )
                return replay
            if await self._repository.get_identity(identity_id) is not None:
                await self._deny(
                    actor, correlation_id, "workload_identity_unavailable", reason, idempotency_key
                )
            now = self._clock()
            identity = WorkloadIdentityRecord(
                identity_id=identity_id,
                version=1,
                display_name=display_name.strip(),
                service_id=service_id,
                instance_id=instance_id,
                owner_subject_id=owner_subject_id,
                purpose=purpose.strip(),
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
                audiences=tuple(sorted(audiences)),
                secret_reference_ids=tuple(sorted(secret_reference_ids)),
                state=WorkloadIdentityState.ACTIVE,
                created_at=now,
                updated_at=now,
            )
            issued = self._issue(identity, lifetime, now)
            if not await self._repository.add_identity(identity):
                await self._deny(
                    actor, correlation_id, "workload_identity_unavailable", reason, idempotency_key
                )
            if not await self._repository.add_credential(issued.credential):
                await self._repository.delete_identity(identity.identity_id, expected_version=1)
                await self._audit(
                    actor=actor,
                    action="creation_compensated",
                    correlation_id=correlation_id,
                    outcome="failed",
                    result_code="workload_identity_creation_compensated",
                    target_subject_id=identity.identity_id,
                    reason=reason,
                    idempotency_key=idempotency_key,
                    metadata=self._safe_metadata(identity, issued.credential),
                )
                raise WorkloadIdentityError("workload_identity_unavailable")
            try:
                await self._audit(
                    actor=actor,
                    action="created",
                    correlation_id=correlation_id,
                    outcome="succeeded",
                    result_code="workload_identity_created",
                    target_subject_id=identity.identity_id,
                    reason=reason,
                    idempotency_key=idempotency_key,
                    metadata=self._safe_metadata(identity, issued.credential),
                )
            except Exception:
                await self._repository.delete_credential(
                    issued.credential.credential_id, expected_version=1
                )
                await self._repository.delete_identity(identity.identity_id, expected_version=1)
                await self._audit(
                    actor=actor,
                    action="creation_compensated",
                    correlation_id=correlation_id,
                    outcome="failed",
                    result_code="workload_identity_creation_compensated",
                    target_subject_id=identity.identity_id,
                    reason=reason,
                    idempotency_key=idempotency_key,
                    metadata=self._safe_metadata(identity, issued.credential),
                )
                raise
            self._idempotent_results[idempotency_key] = (fingerprint, issued)
            return issued

    async def rotate(
        self,
        identity_id: str,
        *,
        actor: AuthenticatedSubject,
        expected_version: int,
        lifetime: timedelta,
        overlap: timedelta,
        reason: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> IssuedWorkloadCredential:
        self._require_enterprise_human(actor)
        self._validate_lifetime(lifetime)
        self._validate_reason(reason)
        if overlap < timedelta(0) or overlap > self._max_overlap:
            raise ValueError("workload rotation overlap is outside platform bounds")
        fingerprint = self._fingerprint(
            "rotate",
            actor.subject_id,
            identity_id,
            expected_version,
            int(lifetime.total_seconds()),
            int(overlap.total_seconds()),
            reason,
        )
        async with self._lock:
            replay = self._replay(idempotency_key, fingerprint)
            if replay is not None:
                if not isinstance(replay, IssuedWorkloadCredential):
                    raise WorkloadIdentityError("workload_idempotency_conflict")
                await self._audit(
                    actor=actor,
                    action="rotation_replayed",
                    correlation_id=correlation_id,
                    outcome="succeeded",
                    result_code="workload_credential_rotation_replayed",
                    target_subject_id=replay.identity.identity_id,
                    reason=reason,
                    idempotency_key=idempotency_key,
                )
                return replay
            identity = await self._available_identity(
                identity_id, actor, expected_version, correlation_id, reason, idempotency_key
            )
            now = self._clock()
            updated_identity = replace(identity, version=identity.version + 1, updated_at=now)
            issued = self._issue(updated_identity, lifetime, now)
            originals = tuple(
                record
                for record in await self._repository.all_credentials()
                if record.identity_id == identity_id
                and record.state is WorkloadCredentialState.ACTIVE
                and now < record.expires_at
            )
            retiring = tuple(
                replace(
                    record,
                    version=record.version + 1,
                    state=WorkloadCredentialState.RETIRING,
                    retire_at=min(record.expires_at, now + overlap),
                )
                for record in originals
                if overlap > timedelta(0)
            )
            revoked = tuple(
                replace(
                    record,
                    version=record.version + 1,
                    state=WorkloadCredentialState.REVOKED,
                    revoked_at=now,
                    revocation_reason="rotated_without_overlap",
                )
                for record in originals
                if overlap == timedelta(0)
            )
            changed = retiring + revoked
            applied: list[tuple[WorkloadCredentialRecord, WorkloadCredentialRecord]] = []
            identity_applied = False
            credential_added = False
            try:
                for original, replacement in zip(originals, changed, strict=True):
                    if not await self._repository.update_credential(
                        replacement, expected_version=original.version
                    ):
                        raise RuntimeError("workload credential rotation conflicted")
                    applied.append((original, replacement))
                if not await self._repository.update_identity(
                    updated_identity, expected_version=identity.version
                ):
                    raise RuntimeError("workload identity rotation conflicted")
                identity_applied = True
                if not await self._repository.add_credential(issued.credential):
                    raise RuntimeError("workload credential issuance conflicted")
                credential_added = True
                await self._audit(
                    actor=actor,
                    action="rotated",
                    correlation_id=correlation_id,
                    outcome="succeeded",
                    result_code="workload_credential_rotated",
                    target_subject_id=identity.identity_id,
                    reason=reason,
                    idempotency_key=idempotency_key,
                    metadata=(
                        *self._safe_metadata(updated_identity, issued.credential),
                        ("prior_credential_count", str(len(changed))),
                    ),
                )
            except Exception as exc:
                if credential_added:
                    await self._repository.delete_credential(
                        issued.credential.credential_id, expected_version=1
                    )
                if identity_applied:
                    await self._repository.update_identity(
                        identity, expected_version=updated_identity.version
                    )
                for original, replacement in reversed(applied):
                    await self._repository.update_credential(
                        original, expected_version=replacement.version
                    )
                await self._audit(
                    actor=actor,
                    action="rotation_compensated",
                    correlation_id=correlation_id,
                    outcome="failed",
                    result_code="workload_credential_rotation_compensated",
                    target_subject_id=identity.identity_id,
                    reason=reason,
                    idempotency_key=idempotency_key,
                    metadata=self._safe_metadata(identity, None),
                )
                raise WorkloadIdentityError("workload_rotation_unavailable") from exc
            self._idempotent_results[idempotency_key] = (fingerprint, issued)
            return issued

    async def revoke(
        self,
        credential_id: str,
        *,
        actor: AuthenticatedSubject,
        expected_version: int,
        reason: str,
        idempotency_key: str,
        correlation_id: str,
    ) -> WorkloadCredentialRecord:
        self._require_enterprise_human(actor)
        self._validate_reason(reason)
        fingerprint = self._fingerprint(
            "revoke", actor.subject_id, credential_id, expected_version, reason
        )
        async with self._lock:
            replay = self._replay(idempotency_key, fingerprint)
            if replay is not None:
                if not isinstance(replay, WorkloadCredentialRecord):
                    raise WorkloadIdentityError("workload_idempotency_conflict")
                replay_identity = await self._repository.get_identity(replay.identity_id)
                await self._audit(
                    actor=actor,
                    action="revocation_replayed",
                    correlation_id=correlation_id,
                    outcome="succeeded",
                    result_code="workload_credential_revocation_replayed",
                    target_subject_id=replay.identity_id,
                    reason=reason,
                    idempotency_key=idempotency_key,
                    metadata=(
                        self._safe_metadata(replay_identity, replay)
                        if replay_identity is not None
                        else (("credential_id", replay.credential_id),)
                    ),
                )
                return replay
            record = await self._repository.get_credential(credential_id)
            identity = (
                await self._repository.get_identity(record.identity_id)
                if record is not None
                else None
            )
            if (
                record is None
                or identity is None
                or identity.organization_id != actor.organization_id
                or identity.environment_id != self._environment_id
                or record.version != expected_version
                or record.state
                not in {WorkloadCredentialState.ACTIVE, WorkloadCredentialState.RETIRING}
            ):
                await self._deny(
                    actor,
                    correlation_id,
                    "workload_credential_unavailable",
                    reason,
                    idempotency_key,
                )
            assert record is not None and identity is not None
            revoked = replace(
                record,
                version=record.version + 1,
                state=WorkloadCredentialState.REVOKED,
                retire_at=None,
                revoked_at=self._clock(),
                revocation_reason=reason,
            )
            if not await self._repository.update_credential(
                revoked, expected_version=record.version
            ):
                await self._deny(
                    actor,
                    correlation_id,
                    "workload_credential_unavailable",
                    reason,
                    idempotency_key,
                )
            try:
                await self._audit(
                    actor=actor,
                    action="credential_revoked",
                    correlation_id=correlation_id,
                    outcome="succeeded",
                    result_code="workload_credential_revoked",
                    target_subject_id=identity.identity_id,
                    reason=reason,
                    idempotency_key=idempotency_key,
                    metadata=self._safe_metadata(identity, revoked),
                )
            except Exception:
                await self._repository.update_credential(record, expected_version=revoked.version)
                await self._audit(
                    actor=actor,
                    action="revocation_compensated",
                    correlation_id=correlation_id,
                    outcome="failed",
                    result_code="workload_credential_revocation_compensated",
                    target_subject_id=identity.identity_id,
                    reason=reason,
                    idempotency_key=idempotency_key,
                    metadata=self._safe_metadata(identity, record),
                )
                raise
            self._idempotent_results[idempotency_key] = (fingerprint, revoked)
            return revoked

    async def authenticate(
        self,
        token: str,
        *,
        audience: str,
        environment_id: str,
        correlation_id: str,
    ) -> AuthenticatedSubject:
        try:
            payload = self._decode_token(token)
            credential_id = str(payload["credential_id"])
            identity_id = str(payload["identity_id"])
            record = await self._repository.get_credential(credential_id)
            identity = await self._repository.get_identity(identity_id)
            now = self._clock()
            if record is None or identity is None:
                raise ValueError("unknown credential")
            digest = sha256(token.encode()).hexdigest()
            retire_at = record.retire_at
            allowed_state = record.state is WorkloadCredentialState.ACTIVE or (
                record.state is WorkloadCredentialState.RETIRING
                and retire_at is not None
                and now < retire_at
            )
            expected_claims = {
                "credential_id": record.credential_id,
                "identity_id": identity.identity_id,
                "service_id": identity.service_id,
                "instance_id": identity.instance_id,
                "organization_id": identity.organization_id,
                "environment_id": identity.environment_id,
                "audiences": list(record.audiences),
                "issued_at": int(record.issued_at.timestamp()),
                "expires_at": int(record.expires_at.timestamp()),
                "key_version": record.key_version,
            }
            if (
                payload != expected_claims
                or not hmac.compare_digest(digest, record.token_digest)
                or not allowed_state
                or identity.state is not WorkloadIdentityState.ACTIVE
                or environment_id != identity.environment_id
                or audience not in record.audiences
                or now >= record.expires_at
                or now + self._clock_skew < record.issued_at
            ):
                raise ValueError("credential rejected")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            await self._audit_authentication(
                correlation_id=correlation_id,
                outcome="denied",
                result_code="workload_credential_rejected",
            )
            raise WorkloadIdentityError("workload_authentication_failed") from exc
        subject = AuthenticatedSubject(
            subject_id=identity.identity_id,
            display_name=identity.display_name,
            kind=SubjectKind.SERVICE,
            provider_id="provider.workload.atlas",
            authentication_method=AuthenticationMethod.WORKLOAD_TOKEN,
            assurance_level=AssuranceLevel.SINGLE_FACTOR,
            authenticated_at=now,
            organization_id=identity.organization_id,
            role_ids=(),
        )
        await self._audit_authentication(
            correlation_id=correlation_id,
            outcome="succeeded",
            result_code="workload_credential_authenticated",
            subject=subject,
            credential_id=record.credential_id,
            audience=audience,
        )
        return subject

    async def target_audit_fields(
        self, target_kind: str, target_reference: str
    ) -> tuple[str | None, tuple[tuple[str, str], ...]]:
        if target_kind == "workload_identity":
            identity = await self._repository.get_identity(target_reference)
            return (
                (identity.identity_id, self._safe_metadata(identity, None))
                if identity is not None
                else (None, (("target_kind", target_kind),))
            )
        if target_kind == "workload_credential":
            credential = await self._repository.get_credential(target_reference)
            identity = (
                await self._repository.get_identity(credential.identity_id)
                if credential is not None
                else None
            )
            return (
                (identity.identity_id, self._safe_metadata(identity, credential))
                if identity is not None and credential is not None
                else (None, (("target_kind", target_kind),))
            )
        raise ValueError("unsupported workload target kind")

    def _issue(
        self, identity: WorkloadIdentityRecord, lifetime: timedelta, now: datetime
    ) -> IssuedWorkloadCredential:
        credential_id = f"credential.workload.{uuid4().hex}"
        expires_at = now + lifetime
        payload = {
            "credential_id": credential_id,
            "identity_id": identity.identity_id,
            "service_id": identity.service_id,
            "instance_id": identity.instance_id,
            "organization_id": identity.organization_id,
            "environment_id": identity.environment_id,
            "audiences": list(identity.audiences),
            "issued_at": int(now.timestamp()),
            "expires_at": int(expires_at.timestamp()),
            "key_version": self._active_key_version,
        }
        encoded = self._b64(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
        signature = self._b64(
            hmac.digest(self._signing_keys[self._active_key_version], encoded.encode(), "sha256")
        )
        token = f"atlas_wlt_v1.{encoded}.{signature}"
        credential = WorkloadCredentialRecord(
            credential_id=credential_id,
            version=1,
            identity_id=identity.identity_id,
            token_digest=sha256(token.encode()).hexdigest(),
            key_version=self._active_key_version,
            audiences=identity.audiences,
            issued_at=now,
            expires_at=expires_at,
            state=WorkloadCredentialState.ACTIVE,
        )
        return IssuedWorkloadCredential(identity=identity, credential=credential, token=token)

    def _decode_token(self, token: str) -> dict[str, object]:
        prefix, encoded, signature = token.split(".", maxsplit=2)
        if prefix != "atlas_wlt_v1" or len(token) > 4096:
            raise ValueError("invalid workload token")
        payload = json.loads(self._unb64(encoded))
        if not isinstance(payload, dict):
            raise ValueError("invalid workload claims")
        key_version = payload.get("key_version")
        if not isinstance(key_version, int) or key_version not in self._signing_keys:
            raise ValueError("unknown signing key")
        expected = self._b64(
            hmac.digest(self._signing_keys[key_version], encoded.encode(), "sha256")
        )
        if not hmac.compare_digest(signature, expected):
            raise ValueError("invalid workload signature")
        return payload

    async def _available_identity(
        self,
        identity_id: str,
        actor: AuthenticatedSubject,
        expected_version: int,
        correlation_id: str,
        reason: str,
        idempotency_key: str,
    ) -> WorkloadIdentityRecord:
        record = await self._repository.get_identity(identity_id)
        if (
            record is None
            or record.organization_id != actor.organization_id
            or record.environment_id != self._environment_id
            or record.version != expected_version
            or record.state is not WorkloadIdentityState.ACTIVE
        ):
            await self._deny(
                actor, correlation_id, "workload_identity_unavailable", reason, idempotency_key
            )
        assert record is not None
        return record

    async def _deny(
        self,
        actor: AuthenticatedSubject,
        correlation_id: str,
        code: str,
        reason: str,
        idempotency_key: str,
    ) -> None:
        await self._audit(
            actor=actor,
            action="mutation_denied",
            correlation_id=correlation_id,
            outcome="denied",
            result_code=code,
            reason=reason,
            idempotency_key=idempotency_key,
        )
        raise WorkloadIdentityError(code)

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        action: str,
        correlation_id: str,
        outcome: str,
        result_code: str,
        target_subject_id: str | None = None,
        reason: str | None = None,
        idempotency_key: str | None = None,
        metadata: tuple[tuple[str, str], ...] = (),
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=f"atlas.identity.workload.{action}",
                schema_version="1.0",
                producer="atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id=None,
                resource_type="resource.identity.workload",
                scope_reference=(
                    f"{actor.organization_id}/{self._environment_id}/site.local/"
                    "domain.workload-identity/resource.identity.workloads/C2"
                ),
                decision_id=None,
                outcome=outcome,
                result_code=result_code,
                target_subject_id=target_subject_id,
                reason=reason,
                idempotency_key=idempotency_key,
                target_metadata=metadata,
            )
        )

    async def _audit_authentication(
        self,
        *,
        correlation_id: str,
        outcome: str,
        result_code: str,
        subject: AuthenticatedSubject | None = None,
        credential_id: str | None = None,
        audience: str | None = None,
    ) -> None:
        metadata_items: list[tuple[str, str]] = []
        if credential_id is not None:
            metadata_items.append(("credential_id", credential_id))
        if audience is not None:
            metadata_items.append(("audience", audience))
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.identity.workload.authentication",
                schema_version="1.0",
                producer="atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=subject.subject_id if subject else None,
                actor_type=subject.kind.value if subject else "service",
                authentication_method=AuthenticationMethod.WORKLOAD_TOKEN.value,
                assurance_level=subject.assurance_level.value if subject else None,
                permission_id=None,
                resource_type="resource.identity.workload",
                scope_reference=None,
                decision_id=None,
                outcome=outcome,
                result_code=result_code,
                target_metadata=tuple(metadata_items),
            )
        )

    @staticmethod
    def _safe_metadata(
        identity: WorkloadIdentityRecord,
        credential: WorkloadCredentialRecord | None,
    ) -> tuple[tuple[str, str], ...]:
        metadata = (
            ("service_id", identity.service_id),
            ("instance_id", identity.instance_id),
            ("owner_subject_id", identity.owner_subject_id),
            ("environment_id", identity.environment_id),
            ("audience_count", str(len(identity.audiences))),
            ("secret_reference_count", str(len(identity.secret_reference_ids))),
        )
        if credential is None:
            return metadata
        return (
            *metadata,
            ("credential_id", credential.credential_id),
            ("key_version", str(credential.key_version)),
            ("credential_state", credential.state.value),
        )

    @staticmethod
    def _effective_credential(
        record: WorkloadCredentialRecord, now: datetime
    ) -> WorkloadCredentialRecord:
        if record.state is WorkloadCredentialState.REVOKED:
            return record
        if now >= record.expires_at or (
            record.state is WorkloadCredentialState.RETIRING
            and record.retire_at is not None
            and now >= record.retire_at
        ):
            return replace(record, state=WorkloadCredentialState.EXPIRED, retire_at=None)
        return record

    @staticmethod
    def _matches_identity(record: WorkloadIdentityRecord, query: str) -> bool:
        if not query:
            return True
        return (
            query
            in " ".join(
                (
                    record.identity_id,
                    record.display_name,
                    record.service_id,
                    record.instance_id,
                    record.owner_subject_id,
                    record.purpose,
                    *record.audiences,
                    *record.secret_reference_ids,
                )
            ).casefold()
        )

    @staticmethod
    def _matches_credential(record: WorkloadCredentialRecord, query: str) -> bool:
        return (
            not query
            or query
            in " ".join((record.credential_id, record.identity_id, *record.audiences)).casefold()
        )

    @staticmethod
    def _require_enterprise_human(actor: AuthenticatedSubject) -> None:
        if (
            actor.kind is not SubjectKind.HUMAN
            or actor.authentication_method not in ENTERPRISE_METHODS
        ):
            raise WorkloadIdentityError("enterprise_human_required")

    def _validate_lifetime(self, lifetime: timedelta) -> None:
        if lifetime < timedelta(minutes=1) or lifetime > self._max_lifetime:
            raise ValueError("workload credential lifetime is outside platform bounds")

    @staticmethod
    def _validate_reason(reason: str) -> None:
        if not 1 <= len(reason.strip()) <= 240 or any(ord(character) < 32 for character in reason):
            raise ValueError("workload governance reason is outside platform bounds")

    def _replay(
        self, idempotency_key: str, fingerprint: str
    ) -> IssuedWorkloadCredential | WorkloadCredentialRecord | None:
        existing = self._idempotent_results.get(idempotency_key)
        if existing is None:
            return None
        if not hmac.compare_digest(existing[0], fingerprint):
            raise WorkloadIdentityError("workload_idempotency_conflict")
        return existing[1]

    @staticmethod
    def _fingerprint(*parts: object) -> str:
        return sha256(
            json.dumps(parts, sort_keys=True, separators=(",", ":"), default=list).encode()
        ).hexdigest()

    @staticmethod
    def _b64(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode()

    @staticmethod
    def _unb64(value: str) -> bytes:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
