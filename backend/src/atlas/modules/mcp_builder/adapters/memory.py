from __future__ import annotations

import asyncio

from atlas.modules.mcp_builder.domain.models import McpBuilderProject


class InMemoryMcpBuilderProjectRepository:
    def __init__(self) -> None:
        self._projects: dict[tuple[str, str], McpBuilderProject] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get(self, *, owner_id: str, idempotency_key: str) -> McpBuilderProject | None:
        return self._projects.get((owner_id, idempotency_key))

    async def get_by_id(self, *, owner_id: str, project_id: str) -> McpBuilderProject | None:
        return next(
            (
                project
                for (stored_owner, _), project in self._projects.items()
                if stored_owner == owner_id and project.project_id == project_id
            ),
            None,
        )

    async def get_by_id_for_scope(self, *, project_id: str) -> McpBuilderProject | None:
        return next(
            (project for project in self._projects.values() if project.project_id == project_id),
            None,
        )

    async def add(self, project: McpBuilderProject) -> bool:
        async with self._lock:
            key = (project.owner_id, project.idempotency_key)
            if key in self._projects:
                return False
            self._projects[key] = project
            return True

    async def close(self) -> None:
        return None
