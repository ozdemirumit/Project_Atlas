from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol


class BrocadeTransportError(Exception):
    def __init__(self, code: str, detail: str, *, retryable: bool) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.retryable = retryable


class BrocadeSanNavTransport(Protocol):
    """Pre-authenticated, endpoint-bound transport. SANnav's session-less REST mode accepts a
    Base64 Basic-auth header on every request, so -- unlike a stateful login/session flow -- this
    matches the same static-per-request-header shape already used for Hitachi, letting Brocade
    reuse the existing ConnectorCredentialMaterializer abstraction without any framework change.
    """

    async def get(self, path: str) -> Mapping[str, object]: ...

    async def post(self, path: str, body: Mapping[str, object]) -> Mapping[str, object]: ...
