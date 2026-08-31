from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class VCenterHostConnectionState(StrEnum):
    """vCenter's GET /api/vcenter/host Summary.connection_state field. Confirmed via the real
    generated Python client source (com.vmware.vcenter_client.Host.ConnectionState) shipped in
    VMware's own vsphere-automation-sdk-python repository: exactly three members, no numeric
    codes."""

    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    NOT_RESPONDING = "NOT_RESPONDING"
    UNKNOWN = "UNKNOWN"


def host_connection_state_from_value(raw: object) -> VCenterHostConnectionState:
    if isinstance(raw, str):
        try:
            return VCenterHostConnectionState(raw)
        except ValueError:
            return VCenterHostConnectionState.UNKNOWN
    return VCenterHostConnectionState.UNKNOWN


class VCenterHostPowerState(StrEnum):
    """vCenter's GET /api/vcenter/host Summary.power_state field. Confirmed via the same real
    generated client source as VCenterHostConnectionState (Host.PowerState); the field is
    optional on the wire (a disconnected host may omit it), so a missing value maps to UNKNOWN
    rather than a guessed default."""

    POWERED_ON = "POWERED_ON"
    POWERED_OFF = "POWERED_OFF"
    STANDBY = "STANDBY"
    UNKNOWN = "UNKNOWN"


def host_power_state_from_value(raw: object) -> VCenterHostPowerState:
    if isinstance(raw, str):
        try:
            return VCenterHostPowerState(raw)
        except ValueError:
            return VCenterHostPowerState.UNKNOWN
    return VCenterHostPowerState.UNKNOWN


class VCenterVmPowerState(StrEnum):
    """vCenter's GET /api/vcenter/vm Summary.power_state field. Confirmed via the real
    generated client source (com.vmware.vcenter.vm_client.Power.State): exactly three members."""

    POWERED_OFF = "POWERED_OFF"
    POWERED_ON = "POWERED_ON"
    SUSPENDED = "SUSPENDED"
    UNKNOWN = "UNKNOWN"


def vm_power_state_from_value(raw: object) -> VCenterVmPowerState:
    if isinstance(raw, str):
        try:
            return VCenterVmPowerState(raw)
        except ValueError:
            return VCenterVmPowerState.UNKNOWN
    return VCenterVmPowerState.UNKNOWN


@dataclass(frozen=True, slots=True)
class VCenterHost:
    host_id: str
    name: str
    connection_state: VCenterHostConnectionState
    power_state: VCenterHostPowerState

    def __post_init__(self) -> None:
        if not self.host_id.strip() or not self.name.strip():
            raise ValueError("host requires an identifier and name")


@dataclass(frozen=True, slots=True)
class VCenterCluster:
    cluster_id: str
    name: str
    ha_enabled: bool
    drs_enabled: bool

    def __post_init__(self) -> None:
        if not self.cluster_id.strip() or not self.name.strip():
            raise ValueError("cluster requires an identifier and name")


@dataclass(frozen=True, slots=True)
class VCenterVirtualMachine:
    vm_id: str
    name: str
    power_state: VCenterVmPowerState
    cpu_count: int
    memory_size_mib: int

    def __post_init__(self) -> None:
        if not self.vm_id.strip() or not self.name.strip():
            raise ValueError("virtual machine requires an identifier and name")
        if self.cpu_count < 0 or self.memory_size_mib < 0:
            raise ValueError("virtual machine hardware sizes must not be negative")


@dataclass(frozen=True, slots=True)
class VCenterHostInventoryResult:
    hosts: tuple[VCenterHost, ...]
    observed_at: datetime
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.evidence_references:
            raise ValueError("host inventory results require evidence")


@dataclass(frozen=True, slots=True)
class VCenterClusterInventoryResult:
    clusters: tuple[VCenterCluster, ...]
    observed_at: datetime
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.evidence_references:
            raise ValueError("cluster inventory results require evidence")


@dataclass(frozen=True, slots=True)
class VCenterVmInventoryResult:
    virtual_machines: tuple[VCenterVirtualMachine, ...]
    observed_at: datetime
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.evidence_references:
            raise ValueError("virtual machine inventory results require evidence")


@dataclass(frozen=True, slots=True)
class VCenterClusterMembershipResult:
    """One cluster's real host membership, read via vCenter's confirmed
    Host.FilterSpec.clusters filter -- not asserted from the plain host/cluster list reads, which
    carry no parent-cluster field on either side (see graph adapter known_gaps)."""

    cluster_id: str
    host_ids: tuple[str, ...]
    observed_at: datetime
    evidence_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.cluster_id.strip():
            raise ValueError("cluster membership requires a cluster identifier")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.evidence_references:
            raise ValueError("cluster membership results require evidence")
