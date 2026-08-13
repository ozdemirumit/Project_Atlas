from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import asdict, is_dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from hashlib import sha256
from typing import cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.core.classification import DataClassification
from atlas.modules.identity.domain.models import AuthenticatedSubject, SubjectKind
from atlas.modules.itsm.application.ports import ItsmIntegrationProfileRepository
from atlas.modules.itsm.domain.models import (
    ItsmAllowedOperation,
    ItsmCheckState,
    ItsmFieldMapping,
    ItsmIntegrationProfile,
    ItsmProfileLifecycle,
    ItsmProviderFamily,
    ItsmReadinessAssessment,
    ItsmReadinessCheck,
    ItsmReadinessState,
)

ITSM_PROFILE_SCHEMA = "atlas.itsm-integration-profile.v1"
ITSM_READ = "itsm.integrations.read"
ITSM_CREATE = "itsm.integrations.create"
ITSM_RETIRE = "itsm.integrations.retire"


class ItsmIntegrationError(RuntimeError):
    pass


class ItsmIntegrationService:
    def __init__(
        self,
        *,
        repository: ItsmIntegrationProfileRepository,
        audit_sink: AuditSink,
        environment_id: str,
        site_id: str = "site.local",
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._audit_sink = audit_sink
        self._environment_id = environment_id
        self._site_id = site_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._lock = asyncio.Lock()

    @property
    def repository(self) -> ItsmIntegrationProfileRepository:
        return self._repository

    async def list_profiles(
        self,
        *,
        actor: AuthenticatedSubject,
        lifecycle: ItsmProfileLifecycle | None,
        limit: int,
        correlation_id: str,
    ) -> tuple[ItsmIntegrationProfile, ...]:
        records = await self._repository.list_scope(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            lifecycle=lifecycle,
            limit=limit,
        )
        for record in records:
            self._validate_record(record)
            self._require_scope(actor, record)
        await self._audit(
            actor,
            correlation_id=correlation_id,
            permission_id=ITSM_READ,
            result_code="itsm_integration_inventory_read",
            scope_reference="resource.itsm.integrations",
            idempotency_key=None,
        )
        return records

    async def get(
        self, *, actor: AuthenticatedSubject, profile_id: str, correlation_id: str
    ) -> ItsmIntegrationProfile:
        record = await self._repository.get(profile_id=profile_id)
        if record is None:
            raise ItsmIntegrationError("itsm_integration_not_found")
        self._validate_record(record)
        self._require_scope(actor, record)
        await self._audit(
            actor,
            correlation_id=correlation_id,
            permission_id=ITSM_READ,
            result_code="itsm_integration_read",
            scope_reference=record.profile_id,
            idempotency_key=None,
        )
        return record

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        profile_key: str,
        display_name: str,
        provider_family: ItsmProviderFamily,
        instance_reference: str,
        owner_id: str,
        purpose: str,
        endpoint_origin: str,
        trust_boundary_reference: str,
        secret_reference_id: str,
        classification_ceiling: DataClassification,
        allowed_operations: tuple[ItsmAllowedOperation, ...],
        mapping_version: int,
        field_mappings: tuple[ItsmFieldMapping, ...],
        sandbox_validation_reference: str | None,
        sandbox_validation_digest: str | None,
        audit_profile_id: str,
        acknowledged_configuration_only: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ItsmIntegrationProfile:
        self._require_human(actor)
        if not acknowledged_configuration_only:
            raise ItsmIntegrationError("itsm_integration_acknowledgement_required")
        if not 8 <= len(idempotency_key) <= 128:
            raise ItsmIntegrationError("itsm_integration_request_invalid")
        profile_key = profile_key.strip().lower()
        display_name = display_name.strip()
        endpoint_origin = endpoint_origin.strip().rstrip("/")
        purpose = purpose.strip()
        request_payload = {
            "profile_key": profile_key,
            "display_name": display_name,
            "provider_family": provider_family,
            "instance_reference": instance_reference,
            "owner_id": owner_id,
            "purpose": purpose,
            "endpoint_origin": endpoint_origin,
            "trust_boundary_reference": trust_boundary_reference,
            "secret_reference_id": secret_reference_id,
            "classification_ceiling": classification_ceiling,
            "allowed_operations": allowed_operations,
            "mapping_version": mapping_version,
            "field_mappings": field_mappings,
            "sandbox_validation_reference": sandbox_validation_reference,
            "sandbox_validation_digest": sandbox_validation_digest,
            "audit_profile_id": audit_profile_id,
        }
        fingerprint = self._digest(request_payload)
        replay = await self._repository.get_by_create_key(
            created_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if replay is not None:
            if replay.create_request_fingerprint != fingerprint:
                raise ItsmIntegrationError("itsm_integration_idempotency_conflict")
            self._validate_record(replay)
            self._require_scope(actor, replay)
            return replace(replay, reused=True)

        now = self._clock()
        readiness = self._assess(
            owner_id=owner_id,
            endpoint_origin=endpoint_origin,
            trust_boundary_reference=trust_boundary_reference,
            secret_reference_id=secret_reference_id,
            field_mappings=field_mappings,
            sandbox_validation_reference=sandbox_validation_reference,
            sandbox_validation_digest=sandbox_validation_digest,
            audit_profile_id=audit_profile_id,
            assessed_at=now,
        )
        seed = self._digest(
            [actor.organization_id, self._environment_id, self._site_id, profile_key]
        )
        record = ItsmIntegrationProfile(
            profile_id=f"itsm-integration.{seed[:24]}",
            schema_version=ITSM_PROFILE_SCHEMA,
            version=1,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
            profile_key=profile_key,
            display_name=display_name,
            provider_family=provider_family,
            instance_reference=instance_reference,
            owner_id=owner_id,
            purpose=purpose,
            endpoint_origin=endpoint_origin,
            trust_boundary_reference=trust_boundary_reference,
            secret_reference_id=secret_reference_id,
            classification_ceiling=classification_ceiling,
            allowed_operations=allowed_operations,
            mapping_version=mapping_version,
            field_mappings=field_mappings,
            sandbox_validation_reference=sandbox_validation_reference,
            sandbox_validation_digest=sandbox_validation_digest,
            audit_profile_id=audit_profile_id,
            lifecycle=ItsmProfileLifecycle.ACTIVE,
            readiness=readiness,
            created_by=actor.subject_id,
            created_at=now,
            updated_by=actor.subject_id,
            updated_at=now,
            canonical_digest="0" * 64,
            create_request_fingerprint=fingerprint,
            create_idempotency_key=idempotency_key,
        )
        record = replace(record, canonical_digest=self._digest(self._record_payload(record)))
        async with self._lock:
            prior = await self._repository.get_by_scope_key(
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
                profile_key=profile_key,
            )
            if prior is not None:
                raise ItsmIntegrationError("itsm_integration_key_conflict")
            await self._audit(
                actor,
                correlation_id=correlation_id,
                permission_id=ITSM_CREATE,
                result_code="itsm_integration_create_requested",
                scope_reference=record.profile_id,
                idempotency_key=idempotency_key,
            )
            if not await self._repository.add(record):
                raise ItsmIntegrationError("itsm_integration_concurrency_conflict")
        await self._audit(
            actor,
            correlation_id=correlation_id,
            permission_id=ITSM_CREATE,
            result_code="itsm_integration_created",
            scope_reference=record.profile_id,
            idempotency_key=idempotency_key,
        )
        return record

    async def retire(
        self,
        *,
        actor: AuthenticatedSubject,
        profile_id: str,
        expected_version: int,
        reason: str,
        acknowledged_history_preserved_and_dispatch_absent: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> ItsmIntegrationProfile:
        self._require_human(actor)
        if not acknowledged_history_preserved_and_dispatch_absent:
            raise ItsmIntegrationError("itsm_integration_retirement_acknowledgement_required")
        reason = reason.strip()
        if not 20 <= len(reason) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise ItsmIntegrationError("itsm_integration_retirement_request_invalid")
        fingerprint = self._digest(
            {"profile_id": profile_id, "expected_version": expected_version, "reason": reason}
        )
        replay = await self._repository.get_by_retirement_key(
            retired_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if replay is not None:
            if replay.retirement_request_fingerprint != fingerprint:
                raise ItsmIntegrationError("itsm_integration_idempotency_conflict")
            self._validate_record(replay)
            self._require_scope(actor, replay)
            return replace(replay, reused=True)
        async with self._lock:
            current = await self._repository.get(profile_id=profile_id)
            if current is None:
                raise ItsmIntegrationError("itsm_integration_not_found")
            self._validate_record(current)
            self._require_scope(actor, current)
            if current.lifecycle is ItsmProfileLifecycle.RETIRED:
                raise ItsmIntegrationError("itsm_integration_already_retired")
            if current.version != expected_version:
                raise ItsmIntegrationError("itsm_integration_version_conflict")
            now = self._clock()
            retired = replace(
                current,
                version=current.version + 1,
                lifecycle=ItsmProfileLifecycle.RETIRED,
                updated_by=actor.subject_id,
                updated_at=now,
                retired_by=actor.subject_id,
                retired_at=now,
                retirement_reason=reason,
                retirement_request_fingerprint=fingerprint,
                retirement_idempotency_key=idempotency_key,
                canonical_digest="0" * 64,
            )
            retired = replace(retired, canonical_digest=self._digest(self._record_payload(retired)))
            await self._audit(
                actor,
                correlation_id=correlation_id,
                permission_id=ITSM_RETIRE,
                result_code="itsm_integration_retirement_requested",
                scope_reference=profile_id,
                idempotency_key=idempotency_key,
            )
            if not await self._repository.update(retired, expected_version=expected_version):
                raise ItsmIntegrationError("itsm_integration_version_conflict")
        await self._audit(
            actor,
            correlation_id=correlation_id,
            permission_id=ITSM_RETIRE,
            result_code="itsm_integration_retired",
            scope_reference=profile_id,
            idempotency_key=idempotency_key,
        )
        return retired

    async def close(self) -> None:
        await self._repository.close()

    def _require_scope(self, actor: AuthenticatedSubject, record: ItsmIntegrationProfile) -> None:
        if (
            record.organization_id != actor.organization_id
            or record.environment_id != self._environment_id
            or record.site_id != self._site_id
        ):
            raise ItsmIntegrationError("itsm_integration_not_found")

    @staticmethod
    def _require_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise ItsmIntegrationError("itsm_integration_human_required")

    @classmethod
    def _validate_record(cls, record: ItsmIntegrationProfile) -> None:
        if cls._digest(cls._record_payload(record)) != record.canonical_digest:
            raise ItsmIntegrationError("itsm_integration_integrity_failed")

    @classmethod
    def _record_payload(cls, record: ItsmIntegrationProfile) -> dict[str, object]:
        payload = cast(dict[str, object], asdict(record))
        for field in (
            "canonical_digest",
            "create_request_fingerprint",
            "create_idempotency_key",
            "retirement_request_fingerprint",
            "retirement_idempotency_key",
            "reused",
        ):
            payload.pop(field)
        return cast(dict[str, object], cls._normalize(payload))

    @classmethod
    def _normalize(cls, value: object) -> object:
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        if is_dataclass(value) and not isinstance(value, type):
            return cls._normalize(asdict(value))
        if isinstance(value, dict):
            return {str(key): cls._normalize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._normalize(item) for item in value]
        return value

    @classmethod
    def _digest(cls, payload: object) -> str:
        return sha256(
            json.dumps(
                cls._normalize(payload),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
            ).encode("ascii")
        ).hexdigest()

    @classmethod
    def _assess(
        cls,
        *,
        owner_id: str,
        endpoint_origin: str,
        trust_boundary_reference: str,
        secret_reference_id: str,
        field_mappings: tuple[ItsmFieldMapping, ...],
        sandbox_validation_reference: str | None,
        sandbox_validation_digest: str | None,
        audit_profile_id: str,
        assessed_at: datetime,
    ) -> ItsmReadinessAssessment:
        conditions = (
            ("itsm.readiness.ownership", bool(owner_id), "itsm.readiness.owner_missing"),
            (
                "itsm.readiness.network-trust",
                endpoint_origin.startswith("https://") and bool(trust_boundary_reference),
                "itsm.readiness.network_trust_missing",
            ),
            (
                "itsm.readiness.credential-reference",
                secret_reference_id.startswith("secret."),
                "itsm.readiness.credential_reference_missing",
            ),
            (
                "itsm.readiness.mapping",
                {item.source_field for item in field_mappings}
                >= {"work_notes", "u_atlas_report_reference", "u_atlas_review_state"},
                "itsm.readiness.mapping_incomplete",
            ),
            (
                "itsm.readiness.sandbox-validation",
                sandbox_validation_reference is not None and sandbox_validation_digest is not None,
                "itsm.readiness.sandbox_validation_missing",
            ),
            ("itsm.readiness.audit", bool(audit_profile_id), "itsm.readiness.audit_missing"),
        )
        checks = tuple(
            ItsmReadinessCheck(
                check_id=check_id,
                state=ItsmCheckState.SATISFIED if satisfied else ItsmCheckState.BLOCKED,
                reason_code="itsm.readiness.satisfied" if satisfied else reason,
            )
            for check_id, satisfied, reason in conditions
        )
        state = (
            ItsmReadinessState.READY_FOR_SANDBOX
            if all(item.state is ItsmCheckState.SATISFIED for item in checks)
            else ItsmReadinessState.BLOCKED
        )
        payload = {
            "state": state,
            "checks": checks,
            "assessed_at": assessed_at,
            "authority": False,
        }
        return ItsmReadinessAssessment(
            state=state,
            checks=checks,
            assessed_at=assessed_at,
            canonical_digest=cls._digest(payload),
        )

    async def _audit(
        self,
        actor: AuthenticatedSubject,
        *,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        scope_reference: str,
        idempotency_key: str | None,
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.itsm.integration-profile",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor.subject_id,
                actor_type=actor.kind.value,
                authentication_method=actor.authentication_method.value,
                assurance_level=actor.assurance_level.value,
                permission_id=permission_id,
                resource_type="resource.itsm.integration",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
            )
        )
