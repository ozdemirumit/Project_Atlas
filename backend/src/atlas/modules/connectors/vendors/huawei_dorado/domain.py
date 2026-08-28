from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

# OceanStor's system_id is the identifier embedded in every DeviceManager REST URL
# (.../deviceManager/rest/{system_id}/...). Confirmed alphanumeric in every working example found;
# exact vendor-defined character set was not independently confirmed beyond that.
_SYSTEM_ID = re.compile(r"^[A-Za-z0-9]{1,32}$")


class HuaweiHealthStatus(StrEnum):
    """OceanStor's HEALTHSTATUS field. Confirmed via two independent, real monitoring-plugin
    sources (not vendor prose alone): 0=unknown, 1=normal, 2=faulty. Any other raw value is
    treated as UNKNOWN rather than guessed."""

    UNKNOWN = "unknown"
    NORMAL = "normal"
    FAULTY = "faulty"


_HEALTH_STATUS_CODES = {
    "0": HuaweiHealthStatus.UNKNOWN,
    "1": HuaweiHealthStatus.NORMAL,
    "2": HuaweiHealthStatus.FAULTY,
}


def health_status_from_code(raw: object) -> HuaweiHealthStatus:
    return _HEALTH_STATUS_CODES.get(str(raw), HuaweiHealthStatus.UNKNOWN)


@dataclass(frozen=True, slots=True)
class HuaweiSystemIdentity:
    system_id: str
    model: str
    software_version: str
    health_status: HuaweiHealthStatus
    observed_at: datetime
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if not _SYSTEM_ID.fullmatch(self.system_id):
            raise ValueError("system identifier is invalid")
        if not self.model.strip() or not self.evidence_references:
            raise ValueError("system identity requires a model and evidence")


@dataclass(frozen=True, slots=True)
class HuaweiControllerHealth:
    system_id: str
    controller_id: str
    role: str
    health_status: HuaweiHealthStatus
    observed_at: datetime
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if not _SYSTEM_ID.fullmatch(self.system_id):
            raise ValueError("system identifier is invalid")
        if not self.controller_id.strip() or not self.evidence_references:
            raise ValueError("controller health requires an identifier and evidence")


@dataclass(frozen=True, slots=True)
class HuaweiPoolCapacity:
    system_id: str
    pool_id: str
    pool_name: str
    total_capacity_sectors: int
    free_capacity_sectors: int
    health_status: HuaweiHealthStatus
    observed_at: datetime
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if not _SYSTEM_ID.fullmatch(self.system_id):
            raise ValueError("system identifier is invalid")
        if not self.pool_id.strip() or not self.evidence_references:
            raise ValueError("pool capacity requires an identifier and evidence")
        if self.total_capacity_sectors < 0 or self.free_capacity_sectors < 0:
            raise ValueError("pool capacity must not be negative")

    @property
    def used_capacity_percent(self) -> float:
        """OceanStor's storagepool object does not expose a configured warning/depletion
        threshold field the way Hitachi's does (confirmed absent from both working reference
        scripts used to build this connector) -- so this connector computes utilization from raw
        capacity instead of reading a vendor-reported percentage, and health-check thresholds are
        the connector's own fixed policy (see health_checks/adapters/huawei_dorado.py's
        health-check definition), not a value read from the array."""
        if self.total_capacity_sectors == 0:
            return 0.0
        used = self.total_capacity_sectors - self.free_capacity_sectors
        return round((used / self.total_capacity_sectors) * 100, 2)
