from __future__ import annotations

from typing import Protocol

from atlas.modules.itsm.domain.cmdb_reconciliation import (
    ItsmCiMappingRule,
    ItsmCiReconciliationConflict,
)


class ItsmCiMappingRuleRepository(Protocol):
    async def get(self, rule_id: str) -> ItsmCiMappingRule | None: ...

    async def save(self, rule: ItsmCiMappingRule) -> None: ...

    async def close(self) -> None: ...


class ItsmCiReconciliationConflictRepository(Protocol):
    async def get(self, conflict_id: str) -> ItsmCiReconciliationConflict | None: ...

    async def save(self, conflict: ItsmCiReconciliationConflict) -> None: ...

    async def close(self) -> None: ...
