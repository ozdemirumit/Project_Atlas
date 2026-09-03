from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from atlas.modules.connectors.application.ports import ConnectorSelfTestResult
from atlas.modules.connectors.domain.models import ConnectorHealth, ConnectorInstance
from atlas.modules.connectors.vendors.huawei_pacific.domain import (
    HuaweiPacificClusterInventoryResult,
    HuaweiPacificClusterNode,
    HuaweiPacificPoolCapacity,
    node_running_status_from_value,
    pool_status_from_code,
)
from atlas.modules.connectors.vendors.huawei_pacific.manifest import PACKAGE_ID
from atlas.modules.connectors.vendors.huawei_pacific.ports import (
    HuaweiPacificTransport,
    HuaweiPacificTransportError,
)

_CLUSTER_SERVERS_PATH = "/api/v2/cluster/servers"
_STORAGE_POOL_PATH = "/api/v2/data_service/storagepool"


class HuaweiPacificConnectorError(Exception):
    def __init__(self, code: str, detail: str, *, retryable: bool = False) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.retryable = retryable


class HuaweiPacificClient:
    """Reads one exact, pre-bound OceanStor Pacific cluster's node inventory and storage pool
    capacity. Like Huawei Dorado, there is no allowlist of many targets: the transport is bound
    to one cluster management endpoint, and this client's job is only to parse and bound that one
    cluster's responses safely."""

    def __init__(
        self,
        *,
        transport: HuaweiPacificTransport,
        clock: Callable[[], datetime] | None = None,
        maximum_nodes: int = 256,
        maximum_pools: int = 256,
        maximum_response_bytes: int = 1_048_576,
    ) -> None:
        if maximum_nodes < 1 or maximum_pools < 1 or maximum_response_bytes < 1:
            raise ValueError("connector collection limits must be positive")
        self._transport = transport
        self._clock = clock or (lambda: datetime.now(UTC))
        self._maximum_nodes = maximum_nodes
        self._maximum_pools = maximum_pools
        self._maximum_response_bytes = maximum_response_bytes

    async def self_test(self, instance: ConnectorInstance) -> ConnectorSelfTestResult:
        if instance.package_id != PACKAGE_ID:
            return ConnectorSelfTestResult(
                health=ConnectorHealth.INCOMPATIBLE,
                checked_at=self._clock(),
                code="connector_instance_package_mismatch",
            )
        try:
            payload = await self._get(_CLUSTER_SERVERS_PATH)
        except HuaweiPacificConnectorError as exc:
            return ConnectorSelfTestResult(
                health=ConnectorHealth.UNAVAILABLE,
                checked_at=self._clock(),
                code=exc.code,
            )
        compatible = isinstance(payload.get("data"), list)
        return ConnectorSelfTestResult(
            health=ConnectorHealth.HEALTHY if compatible else ConnectorHealth.INCOMPATIBLE,
            checked_at=self._clock(),
            code="huawei_pacific_api_compatible" if compatible else "product_mismatch",
        )

    async def read_cluster_inventory(self) -> HuaweiPacificClusterInventoryResult:
        payload = await self._get(_CLUSTER_SERVERS_PATH)
        raw_nodes = payload.get("data")
        if not isinstance(raw_nodes, list):
            raise HuaweiPacificConnectorError(
                "malformed_vendor_response", "The cluster node response is malformed."
            )
        if len(raw_nodes) > self._maximum_nodes:
            raise HuaweiPacificConnectorError(
                "vendor_response_limit_exceeded", "The cluster node response exceeds its limit."
            )
        observed_at = self._clock()
        evidence = (self._evidence("cluster/servers", payload),)
        nodes = tuple(self._parse_node(item) for item in raw_nodes)
        return HuaweiPacificClusterInventoryResult(
            nodes=nodes, observed_at=observed_at, evidence_references=evidence
        )

    async def read_pool_capacity(self) -> tuple[HuaweiPacificPoolCapacity, ...]:
        payload = await self._get(_STORAGE_POOL_PATH)
        raw_pools = payload.get("storagePools")
        if not isinstance(raw_pools, list):
            raise HuaweiPacificConnectorError(
                "malformed_vendor_response", "The storage pool response is malformed."
            )
        if len(raw_pools) > self._maximum_pools:
            raise HuaweiPacificConnectorError(
                "vendor_response_limit_exceeded", "The storage pool response exceeds its limit."
            )
        observed_at = self._clock()
        evidence = (self._evidence("data_service/storagepool", payload),)
        return tuple(
            self._parse_pool(item, observed_at=observed_at, evidence=evidence) for item in raw_pools
        )

    @staticmethod
    def _parse_node(value: object) -> HuaweiPacificClusterNode:
        if not isinstance(value, Mapping):
            raise HuaweiPacificConnectorError(
                "malformed_vendor_response", "A cluster node item is malformed."
            )
        node_id = value.get("id")
        name = value.get("name")
        management_ip = value.get("management_ip")
        model = value.get("model")
        in_cluster = value.get("in_cluster")
        if (
            not isinstance(node_id, str)
            or not isinstance(name, str)
            or not isinstance(management_ip, str)
            or not isinstance(model, str)
            or not isinstance(in_cluster, bool)
        ):
            raise HuaweiPacificConnectorError(
                "malformed_vendor_response", "A cluster node item has invalid fields."
            )
        try:
            return HuaweiPacificClusterNode(
                node_id=node_id,
                name=name,
                management_ip=management_ip,
                model=model,
                running_status=node_running_status_from_value(value.get("running_status")),
                in_cluster=in_cluster,
                oam_agent_status=HuaweiPacificClient._optional_str(value.get("oam_agent_status")),
                error_code=HuaweiPacificClient._optional_str(value.get("error_code")),
                warranty_status=HuaweiPacificClient._optional_str(value.get("warranty_status")),
            )
        except ValueError as exc:
            raise HuaweiPacificConnectorError(
                "malformed_vendor_response", "A cluster node item failed validation."
            ) from exc

    @staticmethod
    def _optional_str(value: object) -> str | None:
        """oam_agent_status, error_code, and warranty_status are not confirmed-required fields
        (unlike node_id/name/management_ip/model/in_cluster) -- absent or unrecognized-shape
        values are treated as unavailable (None) rather than failing the whole node read."""
        if isinstance(value, bool):
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        if isinstance(value, int):
            return str(value)
        return None

    def _parse_pool(
        self, value: object, *, observed_at: datetime, evidence: tuple[str, ...]
    ) -> HuaweiPacificPoolCapacity:
        if not isinstance(value, Mapping):
            raise HuaweiPacificConnectorError("malformed_vendor_response", "A pool is malformed.")
        pool_id = value.get("storagePoolId")
        name = value.get("storagePoolName")
        total = self._parsed_capacity(value.get("totalCapacity"))
        used = self._parsed_capacity(value.get("usedCapacity"))
        if (
            not isinstance(pool_id, str | int)
            or isinstance(pool_id, bool)
            or not isinstance(name, str)
            or total is None
            or used is None
        ):
            raise HuaweiPacificConnectorError(
                "malformed_vendor_response", "A pool item has invalid fields."
            )
        try:
            return HuaweiPacificPoolCapacity(
                pool_id=str(pool_id),
                pool_name=name,
                status=pool_status_from_code(value.get("status")),
                total_capacity_mib=total,
                used_capacity_mib=used,
                observed_at=observed_at,
                evidence_references=evidence,
            )
        except ValueError as exc:
            raise HuaweiPacificConnectorError(
                "malformed_vendor_response", "A pool item failed validation."
            ) from exc

    @staticmethod
    def _parsed_capacity(value: object) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.lstrip("-").isdigit():
            return int(value)
        return None

    async def _get(self, path: str) -> Mapping[str, object]:
        try:
            payload = await self._transport.get(path)
        except HuaweiPacificTransportError as exc:
            raise HuaweiPacificConnectorError(
                exc.code, exc.detail, retryable=exc.retryable
            ) from exc
        return self._bounded(payload)

    def _bounded(self, payload: object) -> Mapping[str, object]:
        if not isinstance(payload, Mapping):
            raise HuaweiPacificConnectorError(
                "malformed_vendor_response", "The vendor response must be a JSON object."
            )
        try:
            encoded = json.dumps(
                dict(payload), sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise HuaweiPacificConnectorError(
                "malformed_vendor_response", "The vendor response is not valid JSON data."
            ) from exc
        if len(encoded) > self._maximum_response_bytes:
            raise HuaweiPacificConnectorError(
                "vendor_response_limit_exceeded", "The vendor response exceeds its byte limit."
            )
        # Only the cluster/servers response was confirmed to carry a checkable result.code
        # envelope; the storagepool response's confirmed shape has no such wrapper (see
        # source-provenance.json), so this check is soft: applied only when the field is present.
        result = payload.get("result")
        if isinstance(result, Mapping) and result.get("code") not in (0, "0", None):
            raise HuaweiPacificConnectorError(
                "vendor_error_response", "The vendor reported a logical error for this request."
            )
        return payload

    @staticmethod
    def _evidence(kind: str, payload: Mapping[str, object]) -> str:
        try:
            encoded = json.dumps(
                dict(payload), sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise HuaweiPacificConnectorError(
                "malformed_vendor_response", "The vendor response is not valid JSON data."
            ) from exc
        digest = hashlib.sha256(encoded).hexdigest()
        return f"huawei-pacific://{kind}#sha256:{digest}"
