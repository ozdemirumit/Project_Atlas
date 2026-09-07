from __future__ import annotations

from typing import Protocol

from atlas.modules.knowledge.domain.source_registration import KnowledgeSourceRegistration


class KnowledgeSourceRegistrationRepository(Protocol):
    async def create(self, registration: KnowledgeSourceRegistration) -> bool:
        """Returns False if a registration already exists for `registration.source_id`."""
        ...

    async def get(self, source_id: str) -> KnowledgeSourceRegistration | None: ...

    async def update(self, registration: KnowledgeSourceRegistration) -> None: ...
