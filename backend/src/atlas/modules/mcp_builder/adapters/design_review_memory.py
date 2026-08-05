from __future__ import annotations

import asyncio

from atlas.modules.mcp_builder.domain.design_review import McpBuilderDesignCheckpoint


class InMemoryMcpBuilderDesignCheckpointRepository:
    def __init__(self) -> None:
        self._records: dict[str, McpBuilderDesignCheckpoint] = {}
        self._projects: dict[str, str] = {}
        self._create_keys: dict[tuple[str, str], str] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get_by_id(self, *, checkpoint_id: str) -> McpBuilderDesignCheckpoint | None:
        return self._records.get(checkpoint_id)

    async def get_by_project(self, *, project_id: str) -> McpBuilderDesignCheckpoint | None:
        checkpoint_id = self._projects.get(project_id)
        return self._records.get(checkpoint_id) if checkpoint_id is not None else None

    async def get_by_create_key(
        self, *, reviewer_id: str, idempotency_key: str
    ) -> McpBuilderDesignCheckpoint | None:
        checkpoint_id = self._create_keys.get((reviewer_id, idempotency_key))
        return self._records.get(checkpoint_id) if checkpoint_id is not None else None

    async def add(self, checkpoint: McpBuilderDesignCheckpoint) -> bool:
        async with self._lock:
            key = (checkpoint.reviewer_id, checkpoint.idempotency_key)
            if (
                checkpoint.checkpoint_id in self._records
                or checkpoint.project_id in self._projects
                or key in self._create_keys
            ):
                return False
            self._records[checkpoint.checkpoint_id] = checkpoint
            self._projects[checkpoint.project_id] = checkpoint.checkpoint_id
            self._create_keys[key] = checkpoint.checkpoint_id
            return True

    async def close(self) -> None:
        return None
