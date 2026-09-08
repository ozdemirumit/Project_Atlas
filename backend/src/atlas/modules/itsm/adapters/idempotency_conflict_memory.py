from __future__ import annotations

from atlas.modules.itsm.domain.idempotency_conflict import ItsmConflictRecord, ItsmCreationIntent


class InMemoryItsmCreationIntentRepository:
    def __init__(self) -> None:
        self._intents: dict[str, ItsmCreationIntent] = {}

    async def get(self, intent_id: str) -> ItsmCreationIntent | None:
        return self._intents.get(intent_id)

    async def get_by_idempotency_key(
        self, *, profile_id: str, idempotency_key: str
    ) -> ItsmCreationIntent | None:
        for intent in self._intents.values():
            if intent.profile_id == profile_id and intent.idempotency_key == idempotency_key:
                return intent
        return None

    async def save(self, intent: ItsmCreationIntent) -> None:
        self._intents[intent.intent_id] = intent

    async def close(self) -> None:
        return None


class InMemoryItsmConflictRecordRepository:
    def __init__(self) -> None:
        self._conflicts: dict[str, ItsmConflictRecord] = {}

    async def get(self, conflict_id: str) -> ItsmConflictRecord | None:
        return self._conflicts.get(conflict_id)

    async def save(self, conflict: ItsmConflictRecord) -> None:
        self._conflicts[conflict.conflict_id] = conflict

    async def close(self) -> None:
        return None
