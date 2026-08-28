from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime

from atlas.modules.connectors.application.ports import ConnectorSelfTestResult
from atlas.modules.connectors.domain.models import ConnectorHealth, ConnectorInstance
from atlas.modules.connectors.vendors.huawei_dorado.domain import (
    HuaweiControllerHealth,
    HuaweiPoolCapacity,
    HuaweiSystemIdentity,
    health_status_from_code,
)
from atlas.modules.connectors.vendors.huawei_dorado.manifest import PACKAGE_ID
from atlas.modules.connectors.vendors.huawei_dorado.ports import (
    HuaweiDoradoTransport,
    HuaweiTransportError,
)

_SYSTEM_PATH = "/system/"
_CONTROLLER_PATH = "/controller"
_STORAGE_POOL_PATH = "/storagepool"


class HuaweiConnectorError(Exception):
    def __init__(self, code: str, detail: str, *, retryable: bool = False) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.retryable = retryable


class HuaweiDoradoClient:
    """Reads one exact, pre-bound OceanStor Dorado system's identity, controller health, and
    storage pool capacity. Unlike Hitachi and Brocade, there is no allowlist of many targets to
    filter -- the transport is already bound to exactly one `system_id` (see ports.py), and this
    client's job is only to parse and bound that one system's responses safely."""

    def __init__(
        self,
        *,
        transport: HuaweiDoradoTransport,
        system_id: str,
        clock: Callable[[], datetime] | None = None,
        maximum_controllers: int = 64,
        maximum_pools: int = 256,
        maximum_response_bytes: int = 1_048_576,
    ) -> None:
        if maximum_controllers < 1 or maximum_pools < 1 or maximum_response_bytes < 1:
            raise ValueError("connector collection limits must be positive")
        if not system_id:
            raise ValueError("system_id is required")
        self._transport = transport
        self._system_id = system_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._maximum_controllers = maximum_controllers
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
            payload = await self._get(_SYSTEM_PATH)
        except HuaweiConnectorError as exc:
            return ConnectorSelfTestResult(
                health=ConnectorHealth.UNAVAILABLE,
                checked_at=self._clock(),
                code=exc.code,
            )
        data = payload.get("data")
        compatible = isinstance(data, Mapping) and isinstance(data.get("MODEL"), str)
        return ConnectorSelfTestResult(
            health=ConnectorHealth.HEALTHY if compatible else ConnectorHealth.INCOMPATIBLE,
            checked_at=self._clock(),
            code="huawei_dorado_api_compatible" if compatible else "product_mismatch",
        )

    async def read_system_identity(self) -> HuaweiSystemIdentity:
        payload = await self._get(_SYSTEM_PATH)
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise HuaweiConnectorError(
                "malformed_vendor_response", "The system identity response is malformed."
            )
        model = data.get("MODEL")
        software_version = data.get("SOFTWAREVERSION")
        if not isinstance(model, str) or not isinstance(software_version, str):
            raise HuaweiConnectorError(
                "malformed_vendor_response", "The system identity response is malformed."
            )
        try:
            return HuaweiSystemIdentity(
                system_id=self._system_id,
                model=model,
                software_version=software_version,
                health_status=health_status_from_code(data.get("HEALTHSTATUS")),
                observed_at=self._clock(),
                evidence_references=(self._evidence("system", payload),),
            )
        except ValueError as exc:
            raise HuaweiConnectorError(
                "malformed_vendor_response", "The system identity response failed validation."
            ) from exc

    async def read_controller_health(self) -> tuple[HuaweiControllerHealth, ...]:
        payload = await self._get(_CONTROLLER_PATH)
        raw_controllers = payload.get("data")
        if not isinstance(raw_controllers, list):
            raise HuaweiConnectorError(
                "malformed_vendor_response", "The controller response is malformed."
            )
        if len(raw_controllers) > self._maximum_controllers:
            raise HuaweiConnectorError(
                "vendor_response_limit_exceeded", "The controller response exceeds its item limit."
            )
        observed_at = self._clock()
        evidence = (self._evidence("controller", payload),)
        return tuple(
            self._parse_controller(item, observed_at=observed_at, evidence=evidence)
            for item in raw_controllers
        )

    async def read_pool_capacity(self) -> tuple[HuaweiPoolCapacity, ...]:
        payload = await self._get(_STORAGE_POOL_PATH)
        raw_pools = payload.get("data")
        if not isinstance(raw_pools, list):
            raise HuaweiConnectorError(
                "malformed_vendor_response", "The storage pool response is malformed."
            )
        if len(raw_pools) > self._maximum_pools:
            raise HuaweiConnectorError(
                "vendor_response_limit_exceeded",
                "The storage pool response exceeds its item limit.",
            )
        observed_at = self._clock()
        evidence = (self._evidence("storagepool", payload),)
        return tuple(
            self._parse_pool(item, observed_at=observed_at, evidence=evidence) for item in raw_pools
        )

    def _parse_controller(
        self, value: object, *, observed_at: datetime, evidence: tuple[str, ...]
    ) -> HuaweiControllerHealth:
        if not isinstance(value, Mapping):
            raise HuaweiConnectorError(
                "malformed_vendor_response", "A controller item is malformed."
            )
        controller_id = value.get("ID")
        role = value.get("ROLE")
        if not isinstance(controller_id, str) or not isinstance(role, str):
            raise HuaweiConnectorError(
                "malformed_vendor_response", "A controller item has invalid fields."
            )
        try:
            return HuaweiControllerHealth(
                system_id=self._system_id,
                controller_id=controller_id,
                role=role,
                health_status=health_status_from_code(value.get("HEALTHSTATUS")),
                observed_at=observed_at,
                evidence_references=evidence,
            )
        except ValueError as exc:
            raise HuaweiConnectorError(
                "malformed_vendor_response", "A controller item failed validation."
            ) from exc

    def _parse_pool(
        self, value: object, *, observed_at: datetime, evidence: tuple[str, ...]
    ) -> HuaweiPoolCapacity:
        if not isinstance(value, Mapping):
            raise HuaweiConnectorError("malformed_vendor_response", "A pool item is malformed.")
        name = value.get("NAME")
        total = self._parsed_capacity(value.get("USERTOTALCAPACITY"))
        free = self._parsed_capacity(value.get("USERFREECAPACITY"))
        if not isinstance(name, str) or total is None or free is None:
            raise HuaweiConnectorError(
                "malformed_vendor_response", "A pool item has invalid fields."
            )
        try:
            return HuaweiPoolCapacity(
                system_id=self._system_id,
                # OceanStor's storagepool object exposes no separate confirmed identifier field
                # in either working reference source used to build this connector -- NAME is the
                # only field confirmed unique enough to serve as an identity, so it is reused here
                # rather than trusting an unconfirmed ID field.
                pool_id=name,
                pool_name=name,
                total_capacity_sectors=total,
                free_capacity_sectors=free,
                health_status=health_status_from_code(value.get("HEALTHSTATUS")),
                observed_at=observed_at,
                evidence_references=evidence,
            )
        except ValueError as exc:
            raise HuaweiConnectorError(
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
        except HuaweiTransportError as exc:
            raise HuaweiConnectorError(exc.code, exc.detail, retryable=exc.retryable) from exc
        return self._bounded(payload)

    def _bounded(self, payload: object) -> Mapping[str, object]:
        if not isinstance(payload, Mapping):
            raise HuaweiConnectorError(
                "malformed_vendor_response", "The vendor response must be a JSON object."
            )
        try:
            encoded = json.dumps(
                dict(payload), sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise HuaweiConnectorError(
                "malformed_vendor_response", "The vendor response is not valid JSON data."
            ) from exc
        if len(encoded) > self._maximum_response_bytes:
            raise HuaweiConnectorError(
                "vendor_response_limit_exceeded", "The vendor response exceeds its byte limit."
            )
        error = payload.get("error")
        if isinstance(error, Mapping) and error.get("code") not in (0, "0", None):
            raise HuaweiConnectorError(
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
            raise HuaweiConnectorError(
                "malformed_vendor_response", "The vendor response is not valid JSON data."
            ) from exc
        digest = hashlib.sha256(encoded).hexdigest()
        return f"huawei-dorado://{kind}#sha256:{digest}"
