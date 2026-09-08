from __future__ import annotations

from typing import Protocol

from atlas.modules.itsm.domain.idempotency_conflict import ItsmConflictRecord, ItsmCreationIntent


class ItsmCreationIntentRepository(Protocol):
    async def get(self, intent_id: str) -> ItsmCreationIntent | None: ...

    async def get_by_idempotency_key(
        self, *, profile_id: str, idempotency_key: str
    ) -> ItsmCreationIntent | None: ...

    async def save(self, intent: ItsmCreationIntent) -> None: ...

    async def close(self) -> None: ...


class ItsmConflictRecordRepository(Protocol):
    async def get(self, conflict_id: str) -> ItsmConflictRecord | None: ...

    async def save(self, conflict: ItsmConflictRecord) -> None: ...

    async def close(self) -> None: ...
