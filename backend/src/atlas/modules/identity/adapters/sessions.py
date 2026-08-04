from __future__ import annotations

import asyncio

from atlas.modules.identity.domain.sessions import SessionRecord, SessionState


class InMemorySessionRepository:
    def __init__(self) -> None:
        self._records: dict[str, SessionRecord] = {}
        self._lock = asyncio.Lock()

    async def get_by_token_digest(self, token_digest: str) -> SessionRecord | None:
        async with self._lock:
            return self._records.get(token_digest)

    async def add(self, record: SessionRecord) -> None:
        async with self._lock:
            if record.token_digest in self._records:
                raise ValueError("session token digest already exists")
            self._records[record.token_digest] = record

    async def update(self, record: SessionRecord, *, expected_version: int) -> bool:
        async with self._lock:
            current = self._records.get(record.token_digest)
            if current is None or current.version != expected_version:
                return False
            self._records[record.token_digest] = record
            return True

    async def active_for_subject(self, subject_id: str) -> tuple[SessionRecord, ...]:
        async with self._lock:
            return tuple(
                item
                for item in self._records.values()
                if item.subject.subject_id == subject_id and item.state is SessionState.ACTIVE
            )
