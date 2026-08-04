from __future__ import annotations

from typing import Protocol

from atlas.modules.platform.domain.bootstrap_operational_handoff import (
    BootstrapHandoffPlan,
    HandoffTargetState,
    OperationalHandoffReceipt,
)


class BootstrapHandoffError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class BootstrapHandoffTarget(Protocol):
    async def inspect(self, *, plan: BootstrapHandoffPlan) -> HandoffTargetState: ...

    async def publish(
        self, *, execution_id: str, plan: BootstrapHandoffPlan, report: bytes
    ) -> OperationalHandoffReceipt: ...

    async def cleanup_attempt(self, execution_id: str) -> None: ...
