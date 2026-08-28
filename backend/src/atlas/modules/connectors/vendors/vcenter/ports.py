from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class VCenterTransportError(Exception):
    def __init__(self, code: str, detail: str, *, retryable: bool) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.retryable = retryable


class VCenterTransport(Protocol):
    """Pre-authenticated, endpoint-bound transport for one vCenter Server.

    vSphere Automation API's confirmed real session lifecycle: `POST /api/session` (HTTP Basic
    auth, empty body) returns the session token in the `vmware-api-session-id` response header --
    not the response body -- which must be presented on every subsequent request via the same
    header name, and `DELETE /api/session` ends it. `get()` performs a complete, bounded
    login -> read -> logout cycle for every call, the same pattern used for Huawei Dorado and
    Huawei Pacific, so no session ever outlives one bounded operation. Unlike either Huawei
    connector, vCenter's inventory list endpoints (`/api/vcenter/host`, `/api/vcenter/cluster`,
    `/api/vcenter/vm`) each return a JSON array directly at the top level, not an object wrapping
    a `data` or `result` field.
    """

    async def get(self, path: str) -> Sequence[object]: ...
