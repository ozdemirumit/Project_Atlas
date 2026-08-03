from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol


class HitachiTransportError(Exception):
    def __init__(self, code: str, detail: str, *, retryable: bool) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.retryable = retryable


class HitachiOpsCenterTransport(Protocol):
    """Pre-authenticated, endpoint-bound transport exposed by the isolated runner."""

    async def get(self, path: str) -> Mapping[str, object]: ...
