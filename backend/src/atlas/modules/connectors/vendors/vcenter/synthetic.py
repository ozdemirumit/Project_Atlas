from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.connectors.vendors.vcenter.ports import VCenterTransportError


class SyntheticVCenterFault(StrEnum):
    DENIED = "denied"
    TIMEOUT = "timeout"
    THROTTLED = "throttled"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class SyntheticVCenterResponse:
    payload: Sequence[object] | None = None
    fault: SyntheticVCenterFault | None = None

    def __post_init__(self) -> None:
        if (self.payload is None) == (self.fault is None):
            raise ValueError("synthetic response requires exactly one payload or fault")
        if self.payload is not None:
            object.__setattr__(self, "payload", tuple(self.payload))


class SyntheticVCenterTransport:
    """Deterministic transport that cannot perform network or secret access.

    Routes only by the read path (`/api/vcenter/host`, `/api/vcenter/cluster`,
    `/api/vcenter/vm`) -- the real vendor session lifecycle (login/read/logout) is entirely
    internal to VCenterHttpsTransport and not part of this port's surface, so it has nothing to
    simulate here."""

    network_access = False
    secret_access = False

    def __init__(self, routes: dict[str, SyntheticVCenterResponse]) -> None:
        self._routes = dict(routes)
        self.requests: list[str] = []

    async def get(self, path: str) -> Sequence[object]:
        self.requests.append(path)
        response = self._routes.get(path)
        if response is None:
            raise VCenterTransportError(
                "synthetic_route_not_found",
                "The synthetic route is not configured.",
                retryable=False,
            )
        if response.payload is not None:
            return response.payload
        if response.fault is SyntheticVCenterFault.DENIED:
            raise VCenterTransportError(
                "vendor_permission_denied", "The vendor denied this read request.", retryable=False
            )
        if response.fault is SyntheticVCenterFault.TIMEOUT:
            raise VCenterTransportError(
                "target_timeout", "The vendor request timed out.", retryable=True
            )
        if response.fault is SyntheticVCenterFault.THROTTLED:
            raise VCenterTransportError(
                "vendor_rate_limited", "The vendor rate limit was reached.", retryable=True
            )
        raise VCenterTransportError(
            "target_unavailable", "The vendor endpoint is unavailable.", retryable=True
        )
