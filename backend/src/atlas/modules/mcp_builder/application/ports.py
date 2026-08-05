from __future__ import annotations

from typing import Protocol

from atlas.modules.mcp_builder.domain.models import McpBuilderProject


class McpBuilderError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class McpBuilderProjectRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get(self, *, owner_id: str, idempotency_key: str) -> McpBuilderProject | None: ...

    async def get_by_id(self, *, owner_id: str, project_id: str) -> McpBuilderProject | None: ...

    async def add(self, project: McpBuilderProject) -> bool: ...

    async def close(self) -> None: ...
