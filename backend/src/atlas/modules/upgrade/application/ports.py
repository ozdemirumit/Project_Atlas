from __future__ import annotations

from typing import Protocol

from atlas.modules.upgrade.domain.upgrade import UpgradeSimulation


class UpgradeError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class UpgradeSimulationRepository(Protocol):
    @property
    def durable(self) -> bool: ...
    async def get(self, *, actor_id: str, idempotency_key: str) -> UpgradeSimulation | None: ...
    async def get_by_id(self, *, actor_id: str, simulation_id: str) -> UpgradeSimulation | None: ...
    async def add(self, record: UpgradeSimulation) -> bool: ...
    async def close(self) -> None: ...
