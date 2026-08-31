from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime

from atlas.modules.connectors.application.ports import ConnectorSelfTestResult
from atlas.modules.connectors.domain.models import ConnectorHealth, ConnectorInstance
from atlas.modules.connectors.vendors.vcenter.domain import (
    VCenterCluster,
    VCenterClusterInventoryResult,
    VCenterClusterMembershipResult,
    VCenterHost,
    VCenterHostInventoryResult,
    VCenterVirtualMachine,
    VCenterVmInventoryResult,
    host_connection_state_from_value,
    host_power_state_from_value,
    vm_power_state_from_value,
)
from atlas.modules.connectors.vendors.vcenter.manifest import PACKAGE_ID
from atlas.modules.connectors.vendors.vcenter.ports import VCenterTransport, VCenterTransportError

_HOST_PATH = "/api/vcenter/host"
_CLUSTER_PATH = "/api/vcenter/cluster"
_VM_PATH = "/api/vcenter/vm"
# vCenter's real object identifiers (e.g. "domain-c8", "host-21") are alphanumeric with hyphens
# and underscores; validated here before being embedded in a query string.
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class VCenterConnectorError(Exception):
    def __init__(self, code: str, detail: str, *, retryable: bool = False) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.retryable = retryable


class VCenterClient:
    """Reads one exact, pre-bound vCenter Server's host, cluster, and virtual machine inventory.
    There is no allowlist of many targets: the transport is bound to one vCenter management
    endpoint, and this client's job is only to parse and bound that one vCenter's responses
    safely."""

    def __init__(
        self,
        *,
        transport: VCenterTransport,
        clock: Callable[[], datetime] | None = None,
        maximum_hosts: int = 1024,
        maximum_clusters: int = 256,
        maximum_vms: int = 8192,
        maximum_response_bytes: int = 1_048_576,
    ) -> None:
        if (
            maximum_hosts < 1
            or maximum_clusters < 1
            or maximum_vms < 1
            or maximum_response_bytes < 1
        ):
            raise ValueError("connector collection limits must be positive")
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(UTC))
        self._maximum_hosts = maximum_hosts
        self._maximum_clusters = maximum_clusters
        self._maximum_vms = maximum_vms
        self._maximum_response_bytes = maximum_response_bytes

    async def self_test(self, instance: ConnectorInstance) -> ConnectorSelfTestResult:
        if instance.package_id != PACKAGE_ID:
            return ConnectorSelfTestResult(
                health=ConnectorHealth.INCOMPATIBLE,
                checked_at=self._clock(),
                code="connector_instance_package_mismatch",
            )
        try:
            payload = await self._get(_HOST_PATH)
        except VCenterConnectorError as exc:
            return ConnectorSelfTestResult(
                health=ConnectorHealth.UNAVAILABLE,
                checked_at=self._clock(),
                code=exc.code,
            )
        compatible = isinstance(payload, Sequence) and not isinstance(payload, str | bytes)
        return ConnectorSelfTestResult(
            health=ConnectorHealth.HEALTHY if compatible else ConnectorHealth.INCOMPATIBLE,
            checked_at=self._clock(),
            code="vcenter_api_compatible" if compatible else "product_mismatch",
        )

    async def read_host_inventory(self) -> VCenterHostInventoryResult:
        payload = await self._get(_HOST_PATH)
        if len(payload) > self._maximum_hosts:
            raise VCenterConnectorError(
                "vendor_response_limit_exceeded", "The host response exceeds its limit."
            )
        observed_at = self._clock()
        evidence = (self._evidence("vcenter/host", payload),)
        hosts = tuple(self._parse_host(item) for item in payload)
        return VCenterHostInventoryResult(
            hosts=hosts, observed_at=observed_at, evidence_references=evidence
        )

    async def read_cluster_inventory(self) -> VCenterClusterInventoryResult:
        payload = await self._get(_CLUSTER_PATH)
        if len(payload) > self._maximum_clusters:
            raise VCenterConnectorError(
                "vendor_response_limit_exceeded", "The cluster response exceeds its limit."
            )
        observed_at = self._clock()
        evidence = (self._evidence("vcenter/cluster", payload),)
        clusters = tuple(self._parse_cluster(item) for item in payload)
        return VCenterClusterInventoryResult(
            clusters=clusters, observed_at=observed_at, evidence_references=evidence
        )

    async def read_vm_inventory(self) -> VCenterVmInventoryResult:
        payload = await self._get(_VM_PATH)
        if len(payload) > self._maximum_vms:
            raise VCenterConnectorError(
                "vendor_response_limit_exceeded", "The virtual machine response exceeds its limit."
            )
        observed_at = self._clock()
        evidence = (self._evidence("vcenter/vm", payload),)
        virtual_machines = tuple(self._parse_vm(item) for item in payload)
        return VCenterVmInventoryResult(
            virtual_machines=virtual_machines,
            observed_at=observed_at,
            evidence_references=evidence,
        )

    async def read_cluster_membership(self, cluster_id: str) -> VCenterClusterMembershipResult:
        """Reads the hosts that are real members of one exact cluster, using vCenter's confirmed
        Host.FilterSpec `clusters` query filter -- the plain host/cluster list reads carry no
        parent-cluster field on either side to resolve this from."""
        if not _SAFE_IDENTIFIER.fullmatch(cluster_id):
            raise VCenterConnectorError(
                "malformed_vendor_response", "The cluster identifier is not safe to query."
            )
        payload = await self._get(f"{_HOST_PATH}?filter.clusters={cluster_id}")
        if len(payload) > self._maximum_hosts:
            raise VCenterConnectorError(
                "vendor_response_limit_exceeded", "The host response exceeds its limit."
            )
        observed_at = self._clock()
        evidence = (self._evidence(f"vcenter/host?filter.clusters={cluster_id}", payload),)
        host_ids = tuple(self._parse_host(item).host_id for item in payload)
        return VCenterClusterMembershipResult(
            cluster_id=cluster_id,
            host_ids=host_ids,
            observed_at=observed_at,
            evidence_references=evidence,
        )

    @staticmethod
    def _parse_host(value: object) -> VCenterHost:
        if not isinstance(value, Mapping):
            raise VCenterConnectorError("malformed_vendor_response", "A host item is malformed.")
        host_id = value.get("host")
        name = value.get("name")
        if not isinstance(host_id, str) or not isinstance(name, str):
            raise VCenterConnectorError(
                "malformed_vendor_response", "A host item has invalid fields."
            )
        try:
            return VCenterHost(
                host_id=host_id,
                name=name,
                connection_state=host_connection_state_from_value(value.get("connection_state")),
                power_state=host_power_state_from_value(value.get("power_state")),
            )
        except ValueError as exc:
            raise VCenterConnectorError(
                "malformed_vendor_response", "A host item failed validation."
            ) from exc

    @staticmethod
    def _parse_cluster(value: object) -> VCenterCluster:
        if not isinstance(value, Mapping):
            raise VCenterConnectorError("malformed_vendor_response", "A cluster item is malformed.")
        cluster_id = value.get("cluster")
        name = value.get("name")
        ha_enabled = value.get("ha_enabled")
        drs_enabled = value.get("drs_enabled")
        if (
            not isinstance(cluster_id, str)
            or not isinstance(name, str)
            or not isinstance(ha_enabled, bool)
            or not isinstance(drs_enabled, bool)
        ):
            raise VCenterConnectorError(
                "malformed_vendor_response", "A cluster item has invalid fields."
            )
        try:
            return VCenterCluster(
                cluster_id=cluster_id, name=name, ha_enabled=ha_enabled, drs_enabled=drs_enabled
            )
        except ValueError as exc:
            raise VCenterConnectorError(
                "malformed_vendor_response", "A cluster item failed validation."
            ) from exc

    @staticmethod
    def _parse_vm(value: object) -> VCenterVirtualMachine:
        if not isinstance(value, Mapping):
            raise VCenterConnectorError("malformed_vendor_response", "A VM item is malformed.")
        vm_id = value.get("vm")
        name = value.get("name")
        cpu_count = value.get("cpu_count")
        memory_size_mib = value.get("memory_size_MiB")
        if (
            not isinstance(vm_id, str)
            or not isinstance(name, str)
            or not isinstance(cpu_count, int)
            or isinstance(cpu_count, bool)
            or not isinstance(memory_size_mib, int)
            or isinstance(memory_size_mib, bool)
        ):
            raise VCenterConnectorError(
                "malformed_vendor_response", "A VM item has invalid fields."
            )
        try:
            return VCenterVirtualMachine(
                vm_id=vm_id,
                name=name,
                power_state=vm_power_state_from_value(value.get("power_state")),
                cpu_count=cpu_count,
                memory_size_mib=memory_size_mib,
            )
        except ValueError as exc:
            raise VCenterConnectorError(
                "malformed_vendor_response", "A VM item failed validation."
            ) from exc

    async def _get(self, path: str) -> Sequence[object]:
        try:
            payload = await self._transport.get(path)
        except VCenterTransportError as exc:
            raise VCenterConnectorError(exc.code, exc.detail, retryable=exc.retryable) from exc
        return self._bounded(payload)

    def _bounded(self, payload: object) -> Sequence[object]:
        # Accepts any non-str/bytes Sequence, not just a literal list: the real HTTPS transport
        # always decodes JSON arrays to a list, but the synthetic transport stores its fixture
        # payload as an immutable tuple, matching this project's established immutability
        # convention for synthetic fixtures (e.g. Pacific's MappingProxyType-backed payload).
        if not isinstance(payload, Sequence) or isinstance(payload, str | bytes):
            raise VCenterConnectorError(
                "malformed_vendor_response", "The vendor response must be a JSON array."
            )
        try:
            encoded = json.dumps(
                list(payload), sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise VCenterConnectorError(
                "malformed_vendor_response", "The vendor response is not valid JSON data."
            ) from exc
        if len(encoded) > self._maximum_response_bytes:
            raise VCenterConnectorError(
                "vendor_response_limit_exceeded", "The vendor response exceeds its byte limit."
            )
        return payload

    @staticmethod
    def _evidence(kind: str, payload: Sequence[object]) -> str:
        try:
            encoded = json.dumps(
                list(payload), sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise VCenterConnectorError(
                "malformed_vendor_response", "The vendor response is not valid JSON data."
            ) from exc
        digest = hashlib.sha256(encoded).hexdigest()
        return f"vcenter://{kind}#sha256:{digest}"
