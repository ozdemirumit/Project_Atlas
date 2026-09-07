from __future__ import annotations

import asyncio

from atlas.modules.platform.domain.bootstrap_rollback import RollbackAttempt, RollbackPlan


class InMemoryBootstrapRollbackRepository:
    def __init__(self) -> None:
        self._plans: dict[str, RollbackPlan] = {}
        self._attempts: dict[str, RollbackAttempt] = {}
        self._lock = asyncio.Lock()

    async def save_plan(self, plan: RollbackPlan) -> None:
        async with self._lock:
            self._plans[plan.plan_id] = plan

    async def get_plan(self, plan_id: str) -> RollbackPlan | None:
        async with self._lock:
            return self._plans.get(plan_id)

    async def save_attempt(self, attempt: RollbackAttempt) -> None:
        async with self._lock:
            self._attempts[attempt.attempt_id] = attempt

    async def get_attempt(self, attempt_id: str) -> RollbackAttempt | None:
        async with self._lock:
            return self._attempts.get(attempt_id)
