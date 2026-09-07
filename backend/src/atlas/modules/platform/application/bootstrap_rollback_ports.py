from __future__ import annotations

from typing import Protocol

from atlas.modules.platform.domain.bootstrap_rollback import RollbackAttempt, RollbackPlan


class BootstrapRollbackRepository(Protocol):
    async def save_plan(self, plan: RollbackPlan) -> None: ...

    async def get_plan(self, plan_id: str) -> RollbackPlan | None: ...

    async def save_attempt(self, attempt: RollbackAttempt) -> None: ...

    async def get_attempt(self, attempt_id: str) -> RollbackAttempt | None: ...
