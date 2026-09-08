from __future__ import annotations

from atlas.modules.itsm.domain.cmdb_reconciliation import (
    ItsmCiMappingRule,
    ItsmCiReconciliationConflict,
)


class InMemoryItsmCiMappingRuleRepository:
    def __init__(self) -> None:
        self._rules: dict[str, ItsmCiMappingRule] = {}

    async def get(self, rule_id: str) -> ItsmCiMappingRule | None:
        return self._rules.get(rule_id)

    async def save(self, rule: ItsmCiMappingRule) -> None:
        self._rules[rule.rule_id] = rule

    async def close(self) -> None:
        return None


class InMemoryItsmCiReconciliationConflictRepository:
    def __init__(self) -> None:
        self._conflicts: dict[str, ItsmCiReconciliationConflict] = {}

    async def get(self, conflict_id: str) -> ItsmCiReconciliationConflict | None:
        return self._conflicts.get(conflict_id)

    async def save(self, conflict: ItsmCiReconciliationConflict) -> None:
        self._conflicts[conflict.conflict_id] = conflict

    async def close(self) -> None:
        return None
