from __future__ import annotations

from typing import Protocol

from atlas.modules.ai.domain.models import ModelInvocation, ProviderCompletion


class ModelTransportError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class ModelTransport(Protocol):
    async def complete(self, invocation: ModelInvocation) -> ProviderCompletion: ...
