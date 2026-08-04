from __future__ import annotations

from typing import Protocol

from atlas.modules.platform.domain.bootstrap_end_to_end_verification import (
    BootstrapVerificationPlan,
    EndToEndVerificationReceipt,
    VerificationTargetState,
)


class BootstrapVerificationError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class BootstrapVerificationTarget(Protocol):
    async def inspect(self, *, plan: BootstrapVerificationPlan) -> VerificationTargetState: ...

    async def publish(
        self, *, execution_id: str, plan: BootstrapVerificationPlan, report: bytes
    ) -> EndToEndVerificationReceipt: ...

    async def cleanup_attempt(self, execution_id: str) -> None: ...
