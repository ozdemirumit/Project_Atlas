from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from atlas.modules.connectors.vendors.brocade_sannav.ports import BrocadeTransportError


class SyntheticBrocadeFault(StrEnum):
    DENIED = "denied"
    TIMEOUT = "timeout"
    THROTTLED = "throttled"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class SyntheticBrocadeResponse:
    payload: Mapping[str, object] | None = None
    fault: SyntheticBrocadeFault | None = None

    def __post_init__(self) -> None:
        if (self.payload is None) == (self.fault is None):
            raise ValueError("synthetic response requires exactly one payload or fault")
        if self.payload is not None:
            object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


class SyntheticBrocadeSanNavTransport:
    """Deterministic transport that cannot perform network or secret access."""

    network_access = False
    secret_access = False

    def __init__(self, routes: Mapping[str, SyntheticBrocadeResponse]) -> None:
        self._routes = MappingProxyType(dict(routes))
        self.requests: list[str] = []

    async def get(self, path: str) -> Mapping[str, object]:
        return self._resolve(path)

    async def post(self, path: str, body: Mapping[str, object]) -> Mapping[str, object]:
        del body
        return self._resolve(path)

    def _resolve(self, path: str) -> Mapping[str, object]:
        self.requests.append(path)
        response = self._routes.get(path)
        if response is None:
            raise BrocadeTransportError(
                "synthetic_route_not_found",
                "The synthetic route is not configured.",
                retryable=False,
            )
        if response.payload is not None:
            return response.payload
        if response.fault is SyntheticBrocadeFault.DENIED:
            raise BrocadeTransportError(
                "vendor_permission_denied", "The vendor denied this read request.", retryable=False
            )
        if response.fault is SyntheticBrocadeFault.TIMEOUT:
            raise BrocadeTransportError(
                "target_timeout", "The vendor request timed out.", retryable=True
            )
        if response.fault is SyntheticBrocadeFault.THROTTLED:
            raise BrocadeTransportError(
                "vendor_rate_limited", "The vendor rate limit was reached.", retryable=True
            )
        raise BrocadeTransportError(
            "target_unavailable", "The vendor endpoint is unavailable.", retryable=True
        )
