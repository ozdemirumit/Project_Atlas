from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime

from atlas.modules.connectors.application.ports import ConnectorSelfTestResult
from atlas.modules.connectors.domain.models import ConnectorHealth, ConnectorInstance
from atlas.modules.connectors.vendors.hitachi_ops_center.domain import (
    HealthSeverity,
    HitachiApiVersion,
    HitachiComponentHealth,
    HitachiHealthResult,
    HitachiInventoryResult,
    HitachiStorageArray,
)
from atlas.modules.connectors.vendors.hitachi_ops_center.manifest import PACKAGE_ID
from atlas.modules.connectors.vendors.hitachi_ops_center.ports import (
    HitachiOpsCenterTransport,
    HitachiTransportError,
)

_STORAGE_DEVICE_ID = re.compile(r"^[A-Za-z0-9]{6,32}$")
_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
_COMPONENT_COLLECTIONS = frozenset(
    {
        "batteries",
        "bkmfs",
        "cacheFlashMemories",
        "cacheMemories",
        "chbs",
        "ctls",
        "dbps",
        "dkbs",
        "dkcs",
        "dkcpss",
        "driveBoxes",
        "drives",
        "encs",
        "fans",
        "hsnbxs",
        "iswFans",
        "iswpss",
        "isws",
        "lanbs",
        "pcps",
        "pecbs",
        "sfps",
        "smFunctions",
        "swpks",
        "xPaths",
        "chbbfans",
        "chbbps",
    }
)
_SEVERITY = {
    "normal": HealthSeverity.NORMAL,
    "warning": HealthSeverity.WARNING,
    "service": HealthSeverity.WARNING,
    "moderate": HealthSeverity.DEGRADED,
    "blocked": HealthSeverity.DEGRADED,
    "serious": HealthSeverity.CRITICAL,
    "acute": HealthSeverity.CRITICAL,
    "failed": HealthSeverity.CRITICAL,
}
_SEVERITY_ORDER = {
    HealthSeverity.NORMAL: 0,
    HealthSeverity.WARNING: 1,
    HealthSeverity.DEGRADED: 2,
    HealthSeverity.UNKNOWN: 3,
    HealthSeverity.CRITICAL: 4,
}


class HitachiConnectorError(Exception):
    def __init__(self, code: str, detail: str, *, retryable: bool = False) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.retryable = retryable


class HitachiOpsCenterClient:
    def __init__(
        self,
        *,
        transport: HitachiOpsCenterTransport,
        allowed_storage_device_ids: frozenset[str],
        clock: Callable[[], datetime] | None = None,
        maximum_arrays: int = 500,
        maximum_components: int = 5_000,
        maximum_response_bytes: int = 1_048_576,
    ) -> None:
        if maximum_arrays < 1 or maximum_components < 1 or maximum_response_bytes < 1:
            raise ValueError("connector collection limits must be positive")
        if not allowed_storage_device_ids:
            raise ValueError("at least one storage device binding is required")
        if any(not _STORAGE_DEVICE_ID.fullmatch(item) for item in allowed_storage_device_ids):
            raise ValueError("allowed storage device bindings have an invalid format")
        self._transport = transport
        self._allowed_storage_device_ids = allowed_storage_device_ids
        self._clock = clock or (lambda: datetime.now(UTC))
        self._maximum_arrays = maximum_arrays
        self._maximum_components = maximum_components
        self._maximum_response_bytes = maximum_response_bytes

    async def self_test(self, instance: ConnectorInstance) -> ConnectorSelfTestResult:
        if instance.package_id != PACKAGE_ID:
            return ConnectorSelfTestResult(
                health=ConnectorHealth.INCOMPATIBLE,
                checked_at=self._clock(),
                code="connector_instance_package_mismatch",
            )
        try:
            version = await self.read_api_version()
        except HitachiConnectorError as exc:
            return ConnectorSelfTestResult(
                health=ConnectorHealth.UNAVAILABLE,
                checked_at=self._clock(),
                code=exc.code,
            )
        health = (
            ConnectorHealth.HEALTHY
            if version.product_name == "Configuration Manager REST API"
            else ConnectorHealth.INCOMPATIBLE
        )
        return ConnectorSelfTestResult(
            health=health,
            checked_at=self._clock(),
            code=(
                "hitachi_api_compatible"
                if health is ConnectorHealth.HEALTHY
                else "product_mismatch"
            ),
        )

    async def read_api_version(self) -> HitachiApiVersion:
        payload = await self._get("/configuration/version")
        product_name = payload.get("productName")
        api_version = payload.get("apiVersion")
        if not isinstance(product_name, str) or not isinstance(api_version, str):
            raise HitachiConnectorError(
                "malformed_vendor_response", "The API version response is malformed."
            )
        if not _VERSION.fullmatch(api_version):
            raise HitachiConnectorError(
                "unsupported_vendor_version", "The API version is not a supported version format."
            )
        return HitachiApiVersion(product_name=product_name, api_version=api_version)

    async def read_inventory(self) -> HitachiInventoryResult:
        payload = await self._get("/v1/objects/storages")
        raw_items = payload.get("data")
        if not isinstance(raw_items, list):
            raise HitachiConnectorError(
                "malformed_vendor_response", "The storage inventory response is malformed."
            )
        if len(raw_items) > self._maximum_arrays:
            raise HitachiConnectorError(
                "vendor_response_limit_exceeded", "The storage inventory exceeds its item limit."
            )
        arrays = tuple(
            array
            for array in (self._parse_array(item) for item in raw_items)
            if array.storage_device_id in self._allowed_storage_device_ids
        )
        return HitachiInventoryResult(
            arrays=arrays,
            observed_at=self._clock(),
            evidence_references=(self._evidence("inventory", payload),),
        )

    async def read_hardware_health(self, storage_device_id: str) -> HitachiHealthResult:
        if not _STORAGE_DEVICE_ID.fullmatch(storage_device_id):
            raise HitachiConnectorError(
                "invalid_storage_device_id", "The storage device identifier is invalid."
            )
        if storage_device_id not in self._allowed_storage_device_ids:
            raise HitachiConnectorError(
                "target_not_bound", "The storage device is outside this connector binding."
            )
        path = f"/v1/objects/storages/{storage_device_id}/components/instance"
        payload = await self._get(path)
        components: list[HitachiComponentHealth] = []
        warnings: list[str] = []
        self._collect_components(payload, components, warnings, collection="root", depth=0)
        if len(components) > self._maximum_components:
            raise HitachiConnectorError(
                "vendor_response_limit_exceeded", "The hardware response exceeds its item limit."
            )
        if not components:
            warnings.append("no_supported_component_status_returned")
        overall = max(
            (component.severity for component in components),
            key=_SEVERITY_ORDER.__getitem__,
            default=HealthSeverity.UNKNOWN,
        )
        return HitachiHealthResult(
            storage_device_id=storage_device_id,
            overall_severity=overall,
            components=tuple(components),
            observed_at=self._clock(),
            evidence_references=(self._evidence(f"health/{storage_device_id}", payload),),
            warnings=tuple(dict.fromkeys(warnings)),
        )

    async def _get(self, path: str) -> Mapping[str, object]:
        try:
            payload = await self._transport.get(path)
        except HitachiTransportError as exc:
            raise HitachiConnectorError(exc.code, exc.detail, retryable=exc.retryable) from exc
        if not isinstance(payload, Mapping):
            raise HitachiConnectorError(
                "malformed_vendor_response", "The vendor response must be a JSON object."
            )
        try:
            encoded = json.dumps(
                dict(payload), sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise HitachiConnectorError(
                "malformed_vendor_response", "The vendor response is not valid JSON data."
            ) from exc
        if len(encoded) > self._maximum_response_bytes:
            raise HitachiConnectorError(
                "vendor_response_limit_exceeded", "The vendor response exceeds its byte limit."
            )
        return payload

    @staticmethod
    def _parse_array(value: object) -> HitachiStorageArray:
        if not isinstance(value, Mapping):
            raise HitachiConnectorError(
                "malformed_vendor_response", "A storage inventory item is malformed."
            )
        storage_device_id = value.get("storageDeviceId")
        model = value.get("model")
        serial_number = value.get("serialNumber")
        if (
            not isinstance(storage_device_id, str)
            or not isinstance(model, str)
            or not isinstance(serial_number, int)
            or isinstance(serial_number, bool)
        ):
            raise HitachiConnectorError(
                "malformed_vendor_response", "A storage inventory item has invalid fields."
            )
        try:
            return HitachiStorageArray(
                storage_device_id=storage_device_id,
                model=model,
                serial_number=serial_number,
            )
        except ValueError as exc:
            raise HitachiConnectorError(
                "malformed_vendor_response", "A storage inventory item failed validation."
            ) from exc

    def _collect_components(
        self,
        value: object,
        components: list[HitachiComponentHealth],
        warnings: list[str],
        *,
        collection: str,
        depth: int,
    ) -> None:
        if depth > 8:
            raise HitachiConnectorError(
                "vendor_response_limit_exceeded", "The hardware response nesting is too deep."
            )
        if isinstance(value, Mapping):
            self._append_status(value, components, warnings, collection)
            if len(components) > self._maximum_components:
                raise HitachiConnectorError(
                    "vendor_response_limit_exceeded",
                    "The hardware response exceeds its item limit.",
                )
            for key, nested in value.items():
                if key in _COMPONENT_COLLECTIONS:
                    self._collect_components(
                        nested,
                        components,
                        warnings,
                        collection=key,
                        depth=depth + 1,
                    )
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            if len(value) > self._maximum_components:
                raise HitachiConnectorError(
                    "vendor_response_limit_exceeded", "A hardware collection is too large."
                )
            for nested in value:
                self._collect_components(
                    nested,
                    components,
                    warnings,
                    collection=collection,
                    depth=depth + 1,
                )

    @staticmethod
    def _append_status(
        value: Mapping[str, object],
        components: list[HitachiComponentHealth],
        warnings: list[str],
        collection: str,
    ) -> None:
        location_value = value.get("location", value.get("portId", "instance"))
        location = location_value if isinstance(location_value, str) else "instance"
        for status_key, category_suffix in (("status", ""), ("temperatureStatus", ".temperature")):
            status = value.get(status_key)
            if not isinstance(status, str):
                continue
            normalized_status = status.strip().lower()
            normalized = (
                HealthSeverity.WARNING
                if normalized_status.startswith("warning")
                else _SEVERITY.get(normalized_status, HealthSeverity.UNKNOWN)
            )
            if normalized is HealthSeverity.UNKNOWN:
                warnings.append(f"unknown_vendor_status:{collection}:{status}")
            components.append(
                HitachiComponentHealth(
                    category=f"{collection}{category_suffix}",
                    location=location,
                    vendor_status=status,
                    severity=normalized,
                )
            )

    @staticmethod
    def _evidence(kind: str, payload: Mapping[str, object]) -> str:
        try:
            encoded = json.dumps(
                dict(payload), sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise HitachiConnectorError(
                "malformed_vendor_response", "The vendor response is not valid JSON data."
            ) from exc
        digest = hashlib.sha256(encoded).hexdigest()
        return f"hitachi-ops-center://{kind}#sha256:{digest}"
