from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from atlas.modules.connectors.vendors.huawei_dorado.ports import HuaweiTransportError


class SyntheticHuaweiFault(StrEnum):
    DENIED = "denied"
    TIMEOUT = "timeout"
    THROTTLED = "throttled"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class SyntheticHuaweiResponse:
    payload: Mapping[str, object] | None = None
    fault: SyntheticHuaweiFault | None = None

    def __post_init__(self) -> None:
        if (self.payload is None) == (self.fault is None):
            raise ValueError("synthetic response requires exactly one payload or fault")
        if self.payload is not None:
            object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


class SyntheticHuaweiDoradoTransport:
    """Deterministic transport that cannot perform network or secret access.

    Routes only by the read path (`/system/`, `/controller`, `/storagepool`) -- the real vendor
    session lifecycle (login/read/logout) is entirely internal to HuaweiDoradoHttpsTransport and
    not part of this port's surface, so it has nothing to simulate here."""

    network_access = False
    secret_access = False

    def __init__(self, routes: Mapping[str, SyntheticHuaweiResponse]) -> None:
        self._routes = MappingProxyType(dict(routes))
        self.requests: list[str] = []

    async def get(self, path: str) -> Mapping[str, object]:
        self.requests.append(path)
        response = self._routes.get(path)
        if response is None:
            raise HuaweiTransportError(
                "synthetic_route_not_found",
                "The synthetic route is not configured.",
                retryable=False,
            )
        if response.payload is not None:
            return response.payload
        if response.fault is SyntheticHuaweiFault.DENIED:
            raise HuaweiTransportError(
                "vendor_permission_denied", "The vendor denied this read request.", retryable=False
            )
        if response.fault is SyntheticHuaweiFault.TIMEOUT:
            raise HuaweiTransportError(
                "target_timeout", "The vendor request timed out.", retryable=True
            )
        if response.fault is SyntheticHuaweiFault.THROTTLED:
            raise HuaweiTransportError(
                "vendor_rate_limited", "The vendor rate limit was reached.", retryable=True
            )
        raise HuaweiTransportError(
            "target_unavailable", "The vendor endpoint is unavailable.", retryable=True
        )
