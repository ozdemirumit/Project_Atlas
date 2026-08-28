from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol


class CommvaultTransportError(Exception):
    def __init__(self, code: str, detail: str, *, retryable: bool) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.retryable = retryable


class CommvaultTransport(Protocol):
    """Pre-authenticated, endpoint-bound transport for one Commvault CommServe.

    Commvault's real REST API is session-based: `POST webservice/Login` (JSON body with
    `username`/`password`, password Base64-encoded) returns a token in the response body's
    `token` field, which must be presented on every subsequent request via the `Authtoken`
    header (not `Authorization: Bearer`) -- a genuine, confirmed difference from every other
    connector built for this project. `POST webservice/Logout` ends it. `get()` performs a
    complete, bounded login -> read -> logout cycle for every call, the same pattern used for
    both Huawei connectors and vCenter, so no session ever outlives one bounded operation.
    """

    async def get(self, path: str) -> Mapping[str, object]: ...
