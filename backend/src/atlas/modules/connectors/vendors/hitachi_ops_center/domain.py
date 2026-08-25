from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

_STORAGE_DEVICE_ID = re.compile(r"^[A-Za-z0-9]{6,32}$")


class HealthSeverity(StrEnum):
    NORMAL = "normal"
    WARNING = "warning"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class HitachiApiVersion:
    product_name: str
    api_version: str


@dataclass(frozen=True, slots=True)
class HitachiStorageArray:
    storage_device_id: str
    model: str
    serial_number: int

    def __post_init__(self) -> None:
        if not _STORAGE_DEVICE_ID.fullmatch(self.storage_device_id):
            raise ValueError("storage_device_id has an invalid format")
        if not self.model.strip():
            raise ValueError("model must not be empty")
        if self.serial_number < 0:
            raise ValueError("serial_number must not be negative")


@dataclass(frozen=True, slots=True)
class HitachiComponentHealth:
    category: str
    location: str
    vendor_status: str
    severity: HealthSeverity


@dataclass(frozen=True, slots=True)
class HitachiPoolCapacity:
    storage_device_id: str
    pool_id: int
    pool_name: str
    used_capacity_rate: int
    warning_threshold: int
    depletion_threshold: int

    def __post_init__(self) -> None:
        if (
            not _STORAGE_DEVICE_ID.fullmatch(self.storage_device_id)
            or self.pool_id < 0
            or not self.pool_name.strip()
            or not 0 <= self.used_capacity_rate <= 100
            or not 0 <= self.warning_threshold <= self.depletion_threshold <= 100
        ):
            raise ValueError("pool capacity has invalid fields")


@dataclass(frozen=True, slots=True)
class HitachiInventoryResult:
    arrays: tuple[HitachiStorageArray, ...]
    observed_at: datetime
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.evidence_references:
            raise ValueError("inventory results require evidence")


@dataclass(frozen=True, slots=True)
class HitachiHealthResult:
    storage_device_id: str
    overall_severity: HealthSeverity
    components: tuple[HitachiComponentHealth, ...]
    observed_at: datetime
    evidence_references: tuple[str, ...]
    warnings: tuple[str, ...]

    def __post_init__(self) -> None:
        if not _STORAGE_DEVICE_ID.fullmatch(self.storage_device_id):
            raise ValueError("storage_device_id has an invalid format")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.evidence_references:
            raise ValueError("health results require evidence")


@dataclass(frozen=True, slots=True)
class HitachiCapacityResult:
    storage_device_id: str
    pools: tuple[HitachiPoolCapacity, ...]
    observed_at: datetime
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if not _STORAGE_DEVICE_ID.fullmatch(self.storage_device_id):
            raise ValueError("storage_device_id has an invalid format")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.evidence_references:
            raise ValueError("capacity results require evidence")
