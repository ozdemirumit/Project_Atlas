from __future__ import annotations

from typing import Protocol

from atlas.modules.support.domain.support_bundle import SupportBundleExport


class SupportBundleError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class SupportBundleExportRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get(self, *, actor_id: str, idempotency_key: str) -> SupportBundleExport | None: ...

    async def add(self, record: SupportBundleExport) -> bool: ...

    async def close(self) -> None: ...


class SupportBundlePublisher(Protocol):
    async def inspect(self, *, target_id: str, expected: bytes) -> str: ...

    async def publish(
        self, *, export_id: str, target_id: str, expected: bytes
    ) -> tuple[str, int, str, bool]: ...
