from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class HuaweiPacificNodeRunningStatus(StrEnum):
    """OceanStor Pacific's cluster/servers running_status field. Confirmed via a real,
    independently-maintained monitoring-plugin library as a lower-case string, not a numeric code
    (unlike Dorado's HEALTHSTATUS): 'online' and 'offline' are the only two confirmed values;
    anything else, including a missing field, is treated as UNKNOWN rather than guessed --
    matching that same library's own documented choice to treat an unrecognized value as a
    warning rather than assuming it is safe."""

    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


def node_running_status_from_value(raw: object) -> HuaweiPacificNodeRunningStatus:
    if raw is None:
        return HuaweiPacificNodeRunningStatus.UNKNOWN
    normalized = str(raw).strip().lower()
    if normalized == "online":
        return HuaweiPacificNodeRunningStatus.ONLINE
    if normalized == "offline":
        return HuaweiPacificNodeRunningStatus.OFFLINE
    return HuaweiPacificNodeRunningStatus.UNKNOWN


class HuaweiPacificPoolStatus(StrEnum):
    """OceanStor Pacific's data_service/storagepool status field. Confirmed via the same real
    monitoring-plugin source as a numeric code with a published mapping."""

    NORMAL = "normal"
    FAULTY = "faulty"
    WRITE_PROTECTED = "write_protected"
    STOPPED = "stopped"
    FAULTY_AND_WRITE_PROTECTED = "faulty_and_write_protected"
    MIGRATING = "migrating"
    DEGRADED = "degraded"
    REBUILDING = "rebuilding"
    UNKNOWN = "unknown"


_POOL_STATUS_CODES = {
    "0": HuaweiPacificPoolStatus.NORMAL,
    "1": HuaweiPacificPoolStatus.FAULTY,
    "2": HuaweiPacificPoolStatus.WRITE_PROTECTED,
    "3": HuaweiPacificPoolStatus.STOPPED,
    "4": HuaweiPacificPoolStatus.FAULTY_AND_WRITE_PROTECTED,
    "5": HuaweiPacificPoolStatus.MIGRATING,
    "7": HuaweiPacificPoolStatus.DEGRADED,
    "8": HuaweiPacificPoolStatus.REBUILDING,
}


def pool_status_from_code(raw: object) -> HuaweiPacificPoolStatus:
    return _POOL_STATUS_CODES.get(str(raw), HuaweiPacificPoolStatus.UNKNOWN)


@dataclass(frozen=True, slots=True)
class HuaweiPacificClusterNode:
    node_id: str
    name: str
    management_ip: str
    model: str
    running_status: HuaweiPacificNodeRunningStatus
    in_cluster: bool

    def __post_init__(self) -> None:
        if not self.node_id.strip() or not self.name.strip():
            raise ValueError("cluster node requires an identifier and name")


@dataclass(frozen=True, slots=True)
class HuaweiPacificClusterInventoryResult:
    nodes: tuple[HuaweiPacificClusterNode, ...]
    observed_at: datetime
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.evidence_references:
            raise ValueError("cluster inventory requires evidence")


@dataclass(frozen=True, slots=True)
class HuaweiPacificPoolCapacity:
    pool_id: str
    pool_name: str
    status: HuaweiPacificPoolStatus
    total_capacity_mib: int
    used_capacity_mib: int
    observed_at: datetime
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.pool_id.strip() or not self.evidence_references:
            raise ValueError("pool capacity requires an identifier and evidence")
        if self.total_capacity_mib < 0 or self.used_capacity_mib < 0:
            raise ValueError("pool capacity must not be negative")

    @property
    def used_capacity_percent(self) -> float:
        if self.total_capacity_mib == 0:
            return 0.0
        return round((self.used_capacity_mib / self.total_capacity_mib) * 100, 2)
