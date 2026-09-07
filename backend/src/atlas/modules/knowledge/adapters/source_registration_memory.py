from __future__ import annotations

import asyncio

from atlas.modules.knowledge.domain.source_registration import KnowledgeSourceRegistration


class InMemoryKnowledgeSourceRegistrationRepository:
    def __init__(self) -> None:
        self._records: dict[str, KnowledgeSourceRegistration] = {}
        self._lock = asyncio.Lock()

    async def create(self, registration: KnowledgeSourceRegistration) -> bool:
        async with self._lock:
            if registration.source_id in self._records:
                return False
            self._records[registration.source_id] = registration
            return True

    async def get(self, source_id: str) -> KnowledgeSourceRegistration | None:
        async with self._lock:
            return self._records.get(source_id)

    async def update(self, registration: KnowledgeSourceRegistration) -> None:
        async with self._lock:
            if registration.source_id not in self._records:
                raise ValueError("knowledge source registration does not exist")
            self._records[registration.source_id] = registration
