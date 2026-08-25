from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import asdict, replace
from datetime import UTC, datetime
from enum import Enum
from hashlib import sha256
from typing import cast
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.identity.domain.models import AuthenticatedSubject, SubjectKind
from atlas.modules.inventory.application.ports import InventoryDeviceRepository
from atlas.modules.inventory.domain.devices import (
    InventoryDeviceLifecycle,
    InventoryDeviceRecord,
    InventoryDeviceType,
)

INVENTORY_DEVICE_READ_PERMISSION = "inventory.devices.read"
INVENTORY_DEVICE_CREATE_PERMISSION = "inventory.devices.create"
INVENTORY_DEVICE_RETIRE_PERMISSION = "inventory.devices.retire"
INVENTORY_DEVICE_SCHEMA = "atlas.inventory-device-record.v1"


class InventoryDeviceError(RuntimeError):
    pass


class InventoryDeviceService:
    def __init__(
        self,
        *,
        repository: InventoryDeviceRepository,
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
        self._mutation_lock = asyncio.Lock()

    @property
    def repository(self) -> InventoryDeviceRepository:
        return self._repository

    async def list_devices(
        self,
        *,
        actor: AuthenticatedSubject,
        lifecycle: InventoryDeviceLifecycle | None,
        query: str | None,
        limit: int,
        correlation_id: str,
    ) -> tuple[InventoryDeviceRecord, ...]:
        normalized_query = query.strip() if query and query.strip() else None
        records = await self._repository.list_scope(
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            lifecycle=lifecycle,
            query=normalized_query,
            limit=limit,
        )
        for record in records:
            self._verify_record(record)
            self._require_scope(actor, record)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=INVENTORY_DEVICE_READ_PERMISSION,
            result_code="inventory_device_inventory_read",
            scope_reference="resource.inventory.devices",
            idempotency_key=None,
            metadata=(("result_count", str(len(records))),),
        )
        return records

    async def get(
        self, *, actor: AuthenticatedSubject, device_id: str, correlation_id: str
    ) -> InventoryDeviceRecord:
        record = await self._repository.get(device_id=device_id)
        if record is None:
            raise InventoryDeviceError("inventory_device_not_found")
        self._verify_record(record)
        self._require_scope(actor, record)
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=INVENTORY_DEVICE_READ_PERMISSION,
            result_code="inventory_device_read",
            scope_reference=record.device_id,
            idempotency_key=None,
            metadata=(("lifecycle", record.lifecycle.value),),
        )
        return record

    async def create(
        self,
        *,
        actor: AuthenticatedSubject,
        device_key: str,
        display_name: str,
        device_type: InventoryDeviceType,
        vendor: str,
        model: str,
        serial_number: str | None,
        management_address: str | None,
        purpose: str,
        acknowledged_no_credentials_or_infrastructure_action: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> InventoryDeviceRecord:
        self._require_human(actor)
        if not acknowledged_no_credentials_or_infrastructure_action:
            raise InventoryDeviceError("inventory_device_acknowledgement_required")
        device_key = device_key.strip().lower()
        display_name = display_name.strip()
        vendor = vendor.strip()
        model = model.strip()
        serial_number = serial_number.strip() if serial_number and serial_number.strip() else None
        management_address = (
            management_address.strip().lower()
            if management_address and management_address.strip()
            else None
        )
        purpose = purpose.strip()
        if not 8 <= len(idempotency_key) <= 128:
            raise InventoryDeviceError("inventory_device_request_invalid")
        fingerprint = self._digest(
            {
                "device_key": device_key,
                "display_name": display_name,
                "device_type": device_type.value,
                "vendor": vendor,
                "model": model,
                "serial_number": serial_number,
                "management_address": management_address,
                "purpose": purpose,
            }
        )
        existing = await self._repository.get_by_create_key(
            created_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if existing is not None:
            if existing.create_request_fingerprint != fingerprint:
                raise InventoryDeviceError("inventory_device_idempotency_conflict")
            self._verify_record(existing)
            self._require_scope(actor, existing)
            return replace(existing, reused=True)

        now = self._clock()
        seed = self._digest(
            [actor.organization_id, self._environment_id, self._site_id, device_key]
        )
        record = InventoryDeviceRecord(
            device_id=f"inventory-device.{seed[:24]}",
            schema_version=INVENTORY_DEVICE_SCHEMA,
            version=1,
            organization_id=actor.organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
            device_key=device_key,
            display_name=display_name,
            device_type=device_type,
            vendor=vendor,
            model=model,
            serial_number=serial_number,
            management_address=management_address,
            source="manual",
            lifecycle=InventoryDeviceLifecycle.ACTIVE,
            purpose=purpose,
            created_by=actor.subject_id,
            created_at=now,
            updated_by=actor.subject_id,
            updated_at=now,
            retired_by=None,
            retired_at=None,
            retirement_reason=None,
            canonical_digest="0" * 64,
            create_request_fingerprint=fingerprint,
            create_idempotency_key=idempotency_key,
        )
        record = replace(record, canonical_digest=self._digest(self._record_payload(record)))
        async with self._mutation_lock:
            prior = await self._repository.get_by_scope_key(
                organization_id=actor.organization_id,
                environment_id=self._environment_id,
                device_key=device_key,
            )
            if prior is not None:
                raise InventoryDeviceError("inventory_device_key_conflict")
            await self._audit(
                actor=actor,
                correlation_id=correlation_id,
                permission_id=INVENTORY_DEVICE_CREATE_PERMISSION,
                result_code="inventory_device_create_requested",
                scope_reference=record.device_id,
                idempotency_key=idempotency_key,
                metadata=(("device_key", device_key), ("device_type", device_type.value)),
            )
            if not await self._repository.add(record):
                raise InventoryDeviceError("inventory_device_concurrency_conflict")
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=INVENTORY_DEVICE_CREATE_PERMISSION,
            result_code="inventory_device_created",
            scope_reference=record.device_id,
            idempotency_key=idempotency_key,
            metadata=(("lifecycle", record.lifecycle.value),),
        )
        return record

    async def retire(
        self,
        *,
        actor: AuthenticatedSubject,
        device_id: str,
        expected_version: int,
        reason: str,
        acknowledged_retirement_preserves_history_and_stops_active_use: bool,
        idempotency_key: str,
        correlation_id: str,
    ) -> InventoryDeviceRecord:
        self._require_human(actor)
        if not acknowledged_retirement_preserves_history_and_stops_active_use:
            raise InventoryDeviceError("inventory_device_retirement_acknowledgement_required")
        reason = reason.strip()
        if not 20 <= len(reason) <= 1000 or not 8 <= len(idempotency_key) <= 128:
            raise InventoryDeviceError("inventory_device_retirement_request_invalid")
        fingerprint = self._digest(
            {"device_id": device_id, "expected_version": expected_version, "reason": reason}
        )
        replay = await self._repository.get_by_retirement_key(
            retired_by=actor.subject_id, idempotency_key=idempotency_key
        )
        if replay is not None:
            if replay.retirement_request_fingerprint != fingerprint:
                raise InventoryDeviceError("inventory_device_idempotency_conflict")
            self._verify_record(replay)
            self._require_scope(actor, replay)
            return replace(replay, reused=True)

        async with self._mutation_lock:
            current = await self._repository.get(device_id=device_id)
            if current is None:
                raise InventoryDeviceError("inventory_device_not_found")
            self._verify_record(current)
            self._require_scope(actor, current)
            if current.lifecycle is InventoryDeviceLifecycle.RETIRED:
                raise InventoryDeviceError("inventory_device_already_retired")
            if current.version != expected_version:
                raise InventoryDeviceError("inventory_device_version_conflict")
            now = self._clock()
            retired = replace(
                current,
                version=current.version + 1,
                lifecycle=InventoryDeviceLifecycle.RETIRED,
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
                actor=actor,
                correlation_id=correlation_id,
                permission_id=INVENTORY_DEVICE_RETIRE_PERMISSION,
                result_code="inventory_device_retirement_requested",
                scope_reference=device_id,
                idempotency_key=idempotency_key,
                metadata=(("expected_version", str(expected_version)),),
            )
            if not await self._repository.update(retired, expected_version=expected_version):
                raise InventoryDeviceError("inventory_device_version_conflict")
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=INVENTORY_DEVICE_RETIRE_PERMISSION,
            result_code="inventory_device_retired",
            scope_reference=device_id,
            idempotency_key=idempotency_key,
            metadata=(("lifecycle", retired.lifecycle.value),),
        )
        return retired

    async def update_device(
        self,
        *,
        actor: AuthenticatedSubject,
        device_id: str,
        expected_version: int,
        changes: dict[str, object],
        correlation_id: str,
    ) -> InventoryDeviceRecord:
        self._require_human(actor)
        allowed_fields = {
            "display_name",
            "device_type",
            "vendor",
            "model",
            "serial_number",
            "management_address",
            "purpose",
        }
        if not changes or not set(changes).issubset(allowed_fields):
            raise InventoryDeviceError("inventory_device_update_request_invalid")

        async with self._mutation_lock:
            current = await self._repository.get(device_id=device_id)
            if current is None:
                raise InventoryDeviceError("inventory_device_not_found")
            self._verify_record(current)
            self._require_scope(actor, current)
            if current.lifecycle is not InventoryDeviceLifecycle.ACTIVE:
                raise InventoryDeviceError("inventory_device_not_active")
            if current.version != expected_version:
                raise InventoryDeviceError("inventory_device_version_conflict")

            normalized = self._normalize_update_changes(changes)
            now = self._clock()
            try:
                updated = replace(
                    current,
                    **normalized,
                    version=current.version + 1,
                    updated_by=actor.subject_id,
                    updated_at=now,
                    canonical_digest="0" * 64,
                    reused=False,
                )
            except ValueError as error:
                raise InventoryDeviceError("inventory_device_update_request_invalid") from error
            updated = replace(updated, canonical_digest=self._digest(self._record_payload(updated)))
            await self._audit(
                actor=actor,
                correlation_id=correlation_id,
                permission_id=INVENTORY_DEVICE_CREATE_PERMISSION,
                result_code="inventory_device_update_requested",
                scope_reference=device_id,
                idempotency_key=None,
                metadata=(
                    ("expected_version", str(expected_version)),
                    ("updated_fields", ",".join(sorted(normalized))),
                ),
            )
            if not await self._repository.update(updated, expected_version=expected_version):
                raise InventoryDeviceError("inventory_device_version_conflict")
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=INVENTORY_DEVICE_CREATE_PERMISSION,
            result_code="inventory_device_updated",
            scope_reference=device_id,
            idempotency_key=None,
            metadata=(("version", str(updated.version)),),
        )
        return updated

    async def reactivate(
        self,
        *,
        actor: AuthenticatedSubject,
        device_id: str,
        expected_version: int,
        correlation_id: str,
    ) -> InventoryDeviceRecord:
        self._require_human(actor)
        async with self._mutation_lock:
            current = await self._repository.get(device_id=device_id)
            if current is None:
                raise InventoryDeviceError("inventory_device_not_found")
            self._verify_record(current)
            self._require_scope(actor, current)
            if current.lifecycle is not InventoryDeviceLifecycle.RETIRED:
                raise InventoryDeviceError("inventory_device_already_active")
            if current.version != expected_version:
                raise InventoryDeviceError("inventory_device_version_conflict")

            now = self._clock()
            reactivated = replace(
                current,
                version=current.version + 1,
                lifecycle=InventoryDeviceLifecycle.ACTIVE,
                updated_by=actor.subject_id,
                updated_at=now,
                retired_by=None,
                retired_at=None,
                retirement_reason=None,
                retirement_request_fingerprint=None,
                retirement_idempotency_key=None,
                canonical_digest="0" * 64,
                reused=False,
            )
            reactivated = replace(
                reactivated,
                canonical_digest=self._digest(self._record_payload(reactivated)),
            )
            await self._audit(
                actor=actor,
                correlation_id=correlation_id,
                permission_id=INVENTORY_DEVICE_CREATE_PERMISSION,
                result_code="inventory_device_reactivation_requested",
                scope_reference=device_id,
                idempotency_key=None,
                metadata=(("expected_version", str(expected_version)),),
            )
            if not await self._repository.update(reactivated, expected_version=expected_version):
                raise InventoryDeviceError("inventory_device_version_conflict")
        await self._audit(
            actor=actor,
            correlation_id=correlation_id,
            permission_id=INVENTORY_DEVICE_CREATE_PERMISSION,
            result_code="inventory_device_reactivated",
            scope_reference=device_id,
            idempotency_key=None,
            metadata=(("lifecycle", reactivated.lifecycle.value),),
        )
        return reactivated

    async def close(self) -> None:
        await self._repository.close()

    def _require_scope(self, actor: AuthenticatedSubject, record: InventoryDeviceRecord) -> None:
        if (
            record.organization_id != actor.organization_id
            or record.environment_id != self._environment_id
            or record.site_id != self._site_id
        ):
            raise InventoryDeviceError("inventory_device_not_found")

    @staticmethod
    def _require_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise InventoryDeviceError("inventory_device_human_required")

    @staticmethod
    def _normalize_update_changes(changes: dict[str, object]) -> dict[str, object]:
        normalized = dict(changes)
        for field in ("display_name", "vendor", "model", "purpose"):
            value = normalized.get(field)
            if value is not None:
                if not isinstance(value, str):
                    raise InventoryDeviceError("inventory_device_update_request_invalid")
                normalized[field] = value.strip()
        for field in ("serial_number", "management_address"):
            if field not in normalized:
                continue
            value = normalized[field]
            if value is not None and not isinstance(value, str):
                raise InventoryDeviceError("inventory_device_update_request_invalid")
            normalized[field] = value.strip() if isinstance(value, str) else None
        management_address = normalized.get("management_address")
        if isinstance(management_address, str):
            normalized["management_address"] = management_address.lower()
        device_type = normalized.get("device_type")
        if device_type is not None:
            try:
                normalized["device_type"] = InventoryDeviceType(device_type)
            except (TypeError, ValueError) as error:
                raise InventoryDeviceError("inventory_device_update_request_invalid") from error
        return normalized

    @classmethod
    def _verify_record(cls, record: InventoryDeviceRecord) -> None:
        if cls._digest(cls._record_payload(record)) != record.canonical_digest:
            raise InventoryDeviceError("inventory_device_integrity_failed")

    @classmethod
    def _record_payload(cls, record: InventoryDeviceRecord) -> dict[str, object]:
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
        if isinstance(value, dict):
            return {str(key): cls._normalize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._normalize(item) for item in value]
        return value

    @staticmethod
    def _digest(payload: object) -> str:
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
                "ascii"
            )
        ).hexdigest()

    async def _audit(
        self,
        *,
        actor: AuthenticatedSubject,
        correlation_id: str,
        permission_id: str,
        result_code: str,
        scope_reference: str,
        idempotency_key: str | None,
        metadata: tuple[tuple[str, str], ...],
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.inventory.device",
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
                resource_type="resource.inventory.device",
                scope_reference=scope_reference,
                decision_id=None,
                outcome="succeeded",
                result_code=result_code,
                idempotency_key=idempotency_key,
                target_metadata=metadata,
            )
        )
