from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier

_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_DEVICE_KEY = re.compile(r"^[a-z][a-z0-9_.:-]{2,127}$")
_MANAGEMENT_ADDRESS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.:-]{0,252}$")


class InventoryDeviceType(StrEnum):
    STORAGE = "storage"
    SAN_SWITCH = "san_switch"
    VIRTUALIZATION = "virtualization"
    SERVER = "server"
    BACKUP = "backup"
    NETWORK = "network"
    OTHER = "other"


class InventoryDeviceLifecycle(StrEnum):
    ACTIVE = "active"
    RETIRED = "retired"


@dataclass(frozen=True, slots=True)
class InventoryDeviceRecord:
    device_id: str
    schema_version: str
    version: int
    organization_id: str
    environment_id: str
    site_id: str
    device_key: str
    display_name: str
    device_type: InventoryDeviceType
    vendor: str
    model: str
    serial_number: str | None
    management_address: str | None
    source: str
    lifecycle: InventoryDeviceLifecycle
    purpose: str
    created_by: str
    created_at: datetime
    updated_by: str
    updated_at: datetime
    retired_by: str | None
    retired_at: datetime | None
    retirement_reason: str | None
    canonical_digest: str
    create_request_fingerprint: str
    create_idempotency_key: str
    retirement_request_fingerprint: str | None = None
    retirement_idempotency_key: str | None = None
    reused: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.device_id,
            self.schema_version,
            self.organization_id,
            self.environment_id,
            self.site_id,
            self.device_key,
            self.source,
            self.created_by,
            self.updated_by,
        ):
            validate_stable_identifier(value, "inventory device identifier")
        if self.retired_by is not None:
            validate_stable_identifier(self.retired_by, "inventory device retirement actor")
        if (
            self.version < 1
            or _DEVICE_KEY.fullmatch(self.device_key) is None
            or not 3 <= len(self.display_name.strip()) <= 160
            or not 2 <= len(self.vendor.strip()) <= 120
            or not 1 <= len(self.model.strip()) <= 160
            or (self.serial_number is not None and not 1 <= len(self.serial_number.strip()) <= 160)
            or (
                self.management_address is not None
                and _MANAGEMENT_ADDRESS.fullmatch(self.management_address) is None
            )
            or self.source != "manual"
            or not 20 <= len(self.purpose.strip()) <= 1000
            or self.created_at.tzinfo is None
            or self.updated_at.tzinfo is None
            or self.updated_at < self.created_at
            or _DIGEST.fullmatch(self.canonical_digest) is None
            or _DIGEST.fullmatch(self.create_request_fingerprint) is None
            or not 8 <= len(self.create_idempotency_key) <= 128
        ):
            raise ValueError("Inventory device record is invalid")
        retired = self.lifecycle is InventoryDeviceLifecycle.RETIRED
        retirement_values = (
            self.retired_by,
            self.retired_at,
            self.retirement_reason,
            self.retirement_request_fingerprint,
            self.retirement_idempotency_key,
        )
        if retired != all(value is not None for value in retirement_values):
            raise ValueError("Inventory device retirement metadata is incomplete")
        if retired and (
            self.version < 2
            or self.retired_at is None
            or self.retired_at != self.updated_at
            or self.retirement_reason is None
            or not 20 <= len(self.retirement_reason.strip()) <= 1000
            or self.retirement_request_fingerprint is None
            or _DIGEST.fullmatch(self.retirement_request_fingerprint) is None
            or self.retirement_idempotency_key is None
            or not 8 <= len(self.retirement_idempotency_key) <= 128
        ):
            raise ValueError("Inventory device retirement metadata is invalid")
