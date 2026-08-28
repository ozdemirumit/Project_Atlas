from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol


class HuaweiPacificTransportError(Exception):
    def __init__(self, code: str, detail: str, *, retryable: bool) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.retryable = retryable


class HuaweiPacificTransport(Protocol):
    """Pre-authenticated, endpoint-bound transport for one OceanStor Pacific cluster.

    Mirrors HuaweiDoradoTransport's rationale exactly: OceanStor Pacific's real cluster-manager
    REST API (`/api/v2/...`) is also session-based -- `POST .../aa/sessions` returns an
    `X-Auth-Token`, which must be presented on every subsequent request, and `DELETE
    .../aa/sessions` ends it. `get()` performs a complete, bounded login -> read -> logout cycle
    for every call, so no session ever outlives one bounded operation. Simpler than Dorado's
    transport in one respect: Pacific's confirmed auth only needs a header token, not a
    cookie, and its endpoints are not scoped by a per-system path segment -- one configured
    connector instance still manages exactly one Pacific cluster, identified by its management
    endpoint alone.
    """

    async def get(self, path: str) -> Mapping[str, object]: ...
