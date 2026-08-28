from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from atlas.modules.connectors.vendors.commvault.ports import CommvaultTransportError


class SyntheticCommvaultFault(StrEnum):
    DENIED = "denied"
    TIMEOUT = "timeout"
    THROTTLED = "throttled"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class SyntheticCommvaultResponse:
    payload: Mapping[str, object] | None = None
    fault: SyntheticCommvaultFault | None = None

    def __post_init__(self) -> None:
        if (self.payload is None) == (self.fault is None):
            raise ValueError("synthetic response requires exactly one payload or fault")
        if self.payload is not None:
            object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))


class SyntheticCommvaultTransport:
    """Deterministic transport that cannot perform network or secret access.

    Routes only by the read path (the exact `webservice/Job?...` query string) -- the real vendor
    session lifecycle (login/read/logout) is entirely internal to CommvaultHttpsTransport and not
    part of this port's surface, so it has nothing to simulate here."""

    network_access = False
    secret_access = False

    def __init__(self, routes: Mapping[str, SyntheticCommvaultResponse]) -> None:
        self._routes = MappingProxyType(dict(routes))
        self.requests: list[str] = []

    async def get(self, path: str) -> Mapping[str, object]:
        self.requests.append(path)
        response = self._routes.get(path)
        if response is None:
            raise CommvaultTransportError(
                "synthetic_route_not_found",
                "The synthetic route is not configured.",
                retryable=False,
            )
        if response.payload is not None:
            return response.payload
        if response.fault is SyntheticCommvaultFault.DENIED:
            raise CommvaultTransportError(
                "vendor_permission_denied", "The vendor denied this read request.", retryable=False
            )
        if response.fault is SyntheticCommvaultFault.TIMEOUT:
            raise CommvaultTransportError(
                "target_timeout", "The vendor request timed out.", retryable=True
            )
        if response.fault is SyntheticCommvaultFault.THROTTLED:
            raise CommvaultTransportError(
                "vendor_rate_limited", "The vendor rate limit was reached.", retryable=True
            )
        raise CommvaultTransportError(
            "target_unavailable", "The vendor endpoint is unavailable.", retryable=True
        )
