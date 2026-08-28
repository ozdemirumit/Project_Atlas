from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol


class HuaweiTransportError(Exception):
    def __init__(self, code: str, detail: str, *, retryable: bool) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.retryable = retryable


class HuaweiDoradoTransport(Protocol):
    """Pre-authenticated, endpoint-bound transport for one OceanStor Dorado system.

    Unlike Hitachi (a static per-request Authorization header) and Brocade SANnav (session-less
    Basic auth on every request), OceanStor's real DeviceManager REST API is session-based: a
    client must first `POST .../sessions` with a username/password to receive an `iBaseToken`
    plus a session cookie, present both on every subsequent request, and `DELETE .../sessions` to
    log out. That whole lifecycle is intentionally hidden inside the transport implementation, not
    exposed here -- `get()` performs a complete, bounded login -> read -> logout cycle for every
    call, so the client above this port stays as simple as Hitachi's and Brocade's (a single
    `get(path)` call), and no partial, cached session can leak between reads. This trades some
    request volume (up to three physical HTTP calls per logical read) for never holding a live
    session open longer than one bounded operation -- the same safety-over-efficiency choice this
    project has made everywhere else.

    The `system_id` that OceanStor's REST API requires in every URL, including login, is baked
    into the transport at construction (like hostname and port), not passed per call: one
    configured connector instance manages exactly one Dorado system, unlike Hitachi's single
    Configuration Manager fronting many arrays.
    """

    async def get(self, path: str) -> Mapping[str, object]: ...
