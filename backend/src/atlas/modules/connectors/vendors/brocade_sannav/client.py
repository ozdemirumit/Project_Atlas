from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta

from atlas.modules.connectors.application.ports import ConnectorSelfTestResult
from atlas.modules.connectors.domain.models import ConnectorHealth, ConnectorInstance
from atlas.modules.connectors.vendors.brocade_sannav.domain import (
    BrocadeFabric,
    BrocadeFaultSummary,
    BrocadeInventoryResult,
    BrocadeSwitch,
)
from atlas.modules.connectors.vendors.brocade_sannav.manifest import PACKAGE_ID
from atlas.modules.connectors.vendors.brocade_sannav.ports import (
    BrocadeSanNavTransport,
    BrocadeTransportError,
)

_PRINCIPAL_SWITCH_WWN = re.compile(r"^[0-9A-Fa-f:]{8,64}$")
_DEFAULT_FAULT_WINDOW = timedelta(hours=2)


class BrocadeConnectorError(Exception):
    def __init__(self, code: str, detail: str, *, retryable: bool = False) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.retryable = retryable


class BrocadeSanNavClient:
    def __init__(
        self,
        *,
        transport: BrocadeSanNavTransport,
        allowed_fabric_wwns: frozenset[str],
        clock: Callable[[], datetime] | None = None,
        maximum_fabrics: int = 500,
        maximum_switches_per_fabric: int = 500,
        maximum_response_bytes: int = 1_048_576,
    ) -> None:
        if maximum_fabrics < 1 or maximum_switches_per_fabric < 1 or maximum_response_bytes < 1:
            raise ValueError("connector collection limits must be positive")
        if not allowed_fabric_wwns:
            raise ValueError("at least one fabric binding is required")
        if any(not _PRINCIPAL_SWITCH_WWN.fullmatch(item) for item in allowed_fabric_wwns):
            raise ValueError("allowed fabric bindings have an invalid format")
        self._transport = transport
        self._allowed_fabric_wwns = allowed_fabric_wwns
        self._clock = clock or (lambda: datetime.now(UTC))
        self._maximum_fabrics = maximum_fabrics
        self._maximum_switches_per_fabric = maximum_switches_per_fabric
        self._maximum_response_bytes = maximum_response_bytes

    async def self_test(self, instance: ConnectorInstance) -> ConnectorSelfTestResult:
        if instance.package_id != PACKAGE_ID:
            return ConnectorSelfTestResult(
                health=ConnectorHealth.INCOMPATIBLE,
                checked_at=self._clock(),
                code="connector_instance_package_mismatch",
            )
        try:
            payload = await self._get("/external-api/v1/discovery/fabrics/")
        except BrocadeConnectorError as exc:
            return ConnectorSelfTestResult(
                health=ConnectorHealth.UNAVAILABLE,
                checked_at=self._clock(),
                code=exc.code,
            )
        compatible = isinstance(payload.get("Fabrics"), list)
        return ConnectorSelfTestResult(
            health=ConnectorHealth.HEALTHY if compatible else ConnectorHealth.INCOMPATIBLE,
            checked_at=self._clock(),
            code="brocade_sannav_api_compatible" if compatible else "product_mismatch",
        )

    async def read_inventory(self) -> BrocadeInventoryResult:
        payload = await self._get("/external-api/v1/discovery/fabrics/")
        raw_fabrics = payload.get("Fabrics")
        if not isinstance(raw_fabrics, list):
            raise BrocadeConnectorError(
                "malformed_vendor_response", "The fabric discovery response is malformed."
            )
        if len(raw_fabrics) > self._maximum_fabrics:
            raise BrocadeConnectorError(
                "vendor_response_limit_exceeded", "The fabric discovery exceeds its item limit."
            )
        fabrics = tuple(
            fabric
            for fabric in (self._parse_fabric(item) for item in raw_fabrics)
            if fabric.principal_switch_wwn in self._allowed_fabric_wwns
        )
        evidence = [self._evidence("discovery/fabrics", payload)]
        switches: list[BrocadeSwitch] = []
        for fabric in fabrics:
            member_payload = await self._get(
                "/external-api/v1/discovery/fabric-members/"
                f"?principalSwitchWWN={fabric.principal_switch_wwn}"
            )
            raw_switches = member_payload.get("Switches")
            if not isinstance(raw_switches, list):
                raise BrocadeConnectorError(
                    "malformed_vendor_response", "The fabric member response is malformed."
                )
            if len(raw_switches) > self._maximum_switches_per_fabric:
                raise BrocadeConnectorError(
                    "vendor_response_limit_exceeded",
                    "The fabric member response exceeds its item limit.",
                )
            switches.extend(
                self._parse_switch(fabric.principal_switch_wwn, item) for item in raw_switches
            )
            evidence.append(
                self._evidence(
                    f"discovery/fabric-members/{fabric.principal_switch_wwn}", member_payload
                )
            )
        return BrocadeInventoryResult(
            fabrics=fabrics,
            switches=tuple(switches),
            observed_at=self._clock(),
            evidence_references=tuple(evidence),
        )

    async def read_fabric_fault_summary(
        self, principal_switch_wwn: str, *, window: timedelta = _DEFAULT_FAULT_WINDOW
    ) -> BrocadeFaultSummary:
        self._require_bound_fabric(principal_switch_wwn)
        now = self._clock()
        start = now - window
        body = {
            "startTime": int(start.timestamp() * 1000),
            "endTime": int(now.timestamp() * 1000),
            "pageSize": 100,
            "startIndex": 0,
            "filters": {
                "filter": [
                    {
                        "includedEvents": [
                            {
                                "category": "SWITCH_EVENT",
                                "eventColumn": "ORIGIN",
                                "value": principal_switch_wwn,
                            }
                        ]
                    }
                ]
            },
        }
        payload = await self._post("/external-api/v2/fault/events/", body)
        event_count = self._count_events(payload)
        return BrocadeFaultSummary(
            fabric_principal_switch_wwn=principal_switch_wwn,
            event_count=event_count,
            observed_at=now,
            evidence_references=(self._evidence(f"fault/events/{principal_switch_wwn}", payload),),
        )

    def _require_bound_fabric(self, principal_switch_wwn: str) -> None:
        if not _PRINCIPAL_SWITCH_WWN.fullmatch(principal_switch_wwn):
            raise BrocadeConnectorError(
                "invalid_fabric_identifier", "The fabric identifier is invalid."
            )
        if principal_switch_wwn not in self._allowed_fabric_wwns:
            raise BrocadeConnectorError(
                "target_not_bound", "The fabric is outside this connector binding."
            )

    async def _get(self, path: str) -> Mapping[str, object]:
        try:
            payload = await self._transport.get(path)
        except BrocadeTransportError as exc:
            raise BrocadeConnectorError(exc.code, exc.detail, retryable=exc.retryable) from exc
        return self._bounded(payload)

    async def _post(self, path: str, body: Mapping[str, object]) -> Mapping[str, object]:
        try:
            payload = await self._transport.post(path, body)
        except BrocadeTransportError as exc:
            raise BrocadeConnectorError(exc.code, exc.detail, retryable=exc.retryable) from exc
        return self._bounded(payload)

    def _bounded(self, payload: object) -> Mapping[str, object]:
        if not isinstance(payload, Mapping):
            raise BrocadeConnectorError(
                "malformed_vendor_response", "The vendor response must be a JSON object."
            )
        try:
            encoded = json.dumps(
                dict(payload), sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise BrocadeConnectorError(
                "malformed_vendor_response", "The vendor response is not valid JSON data."
            ) from exc
        if len(encoded) > self._maximum_response_bytes:
            raise BrocadeConnectorError(
                "vendor_response_limit_exceeded", "The vendor response exceeds its byte limit."
            )
        return payload

    @staticmethod
    def _parse_fabric(value: object) -> BrocadeFabric:
        if not isinstance(value, Mapping):
            raise BrocadeConnectorError(
                "malformed_vendor_response", "A fabric discovery item is malformed."
            )
        principal_switch_wwn = value.get("principalSwitchWwn")
        name = value.get("name")
        if not isinstance(principal_switch_wwn, str) or not isinstance(name, str):
            raise BrocadeConnectorError(
                "malformed_vendor_response", "A fabric discovery item has invalid fields."
            )
        try:
            return BrocadeFabric(principal_switch_wwn=principal_switch_wwn, name=name)
        except ValueError as exc:
            raise BrocadeConnectorError(
                "malformed_vendor_response", "A fabric discovery item failed validation."
            ) from exc

    @staticmethod
    def _parse_switch(fabric_principal_switch_wwn: str, value: object) -> BrocadeSwitch:
        if not isinstance(value, Mapping):
            raise BrocadeConnectorError(
                "malformed_vendor_response", "A fabric member item is malformed."
            )
        ip_address = value.get("ipAddress")
        if not isinstance(ip_address, str):
            raise BrocadeConnectorError(
                "malformed_vendor_response", "A fabric member item has invalid fields."
            )
        try:
            return BrocadeSwitch(
                fabric_principal_switch_wwn=fabric_principal_switch_wwn, ip_address=ip_address
            )
        except ValueError as exc:
            raise BrocadeConnectorError(
                "malformed_vendor_response", "A fabric member item failed validation."
            ) from exc

    @staticmethod
    def _count_events(payload: Mapping[str, object]) -> int:
        # Broadcom's exact response envelope for this endpoint (e.g. whether events are under
        # "events", "data", "Events", or returned as a bare list) was not independently confirmed
        # during connector construction -- counted defensively across the shapes a paginated
        # list-style SANnav response is documented to plausibly take, never raising on an
        # unrecognized shape (falls back to zero rather than guessing a wrong nonzero count).
        for key in ("events", "Events", "data", "Data"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                return len(candidate)
        total = payload.get("totalCount")
        if isinstance(total, int) and not isinstance(total, bool) and total >= 0:
            return total
        return 0

    @staticmethod
    def _evidence(kind: str, payload: Mapping[str, object]) -> str:
        try:
            encoded = json.dumps(
                dict(payload), sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise BrocadeConnectorError(
                "malformed_vendor_response", "The vendor response is not valid JSON data."
            ) from exc
        digest = hashlib.sha256(encoded).hexdigest()
        return f"brocade-sannav://{kind}#sha256:{digest}"
