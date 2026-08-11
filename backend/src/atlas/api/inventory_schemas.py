from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.inventory.domain.devices import (
    InventoryDeviceLifecycle,
    InventoryDeviceRecord,
    InventoryDeviceType,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
MANAGEMENT_ADDRESS = r"^[A-Za-z0-9][A-Za-z0-9.:-]{0,252}$"


class CreateInventoryDeviceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="atlas.inventory-device-create-input.v1", pattern=STABLE_ID)
    device_key: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    display_name: str = Field(min_length=3, max_length=160)
    device_type: InventoryDeviceType
    vendor: str = Field(min_length=2, max_length=120)
    model: str = Field(min_length=1, max_length=160)
    serial_number: str | None = Field(default=None, min_length=1, max_length=160)
    management_address: str | None = Field(
        default=None, min_length=1, max_length=253, pattern=MANAGEMENT_ADDRESS
    )
    purpose: str = Field(min_length=20, max_length=1000)
    acknowledged_no_credentials_or_infrastructure_action: bool


class RetireInventoryDeviceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.inventory-device-retirement-input.v1", pattern=STABLE_ID
    )
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=20, max_length=1000)
    acknowledged_retirement_preserves_history_and_stops_active_use: bool


class InventoryDeviceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

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
    reused: bool

    @classmethod
    def from_domain(cls, record: InventoryDeviceRecord) -> InventoryDeviceData:
        return cls(**{field: getattr(record, field) for field in cls.model_fields})


class InventoryDeviceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: InventoryDeviceData
    meta: ResponseMeta


class InventoryDeviceInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    devices: list[InventoryDeviceData]
    durable: bool
    truncated: bool


class InventoryDeviceInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: InventoryDeviceInventoryData
    meta: ResponseMeta
