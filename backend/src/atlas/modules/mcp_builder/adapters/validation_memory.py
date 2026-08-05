from __future__ import annotations

import asyncio
from dataclasses import replace

from atlas.modules.mcp_builder.domain.validation import McpBuilderValidation


class InMemoryMcpBuilderValidationRepository:
    def __init__(self) -> None:
        self._by_id: dict[str, McpBuilderValidation] = {}
        self._by_project: dict[str, McpBuilderValidation] = {}
        self._by_create_key: dict[tuple[str, str], McpBuilderValidation] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get_by_id(self, *, validation_id: str) -> McpBuilderValidation | None:
        return self._copy(self._by_id.get(validation_id))

    async def get_by_project(self, *, project_id: str) -> McpBuilderValidation | None:
        return self._copy(self._by_project.get(project_id))

    async def get_by_create_key(
        self, *, validated_by: str, idempotency_key: str
    ) -> McpBuilderValidation | None:
        return self._copy(self._by_create_key.get((validated_by, idempotency_key)))

    async def add(self, validation: McpBuilderValidation) -> bool:
        async with self._lock:
            create_key = (validation.validated_by, validation.idempotency_key)
            if (
                validation.validation_id in self._by_id
                or validation.project_id in self._by_project
                or create_key in self._by_create_key
            ):
                return False
            stored = replace(validation, reused=False)
            self._by_id[stored.validation_id] = stored
            self._by_project[stored.project_id] = stored
            self._by_create_key[create_key] = stored
            return True

    async def close(self) -> None:
        return None

    @staticmethod
    def _copy(value: McpBuilderValidation | None) -> McpBuilderValidation | None:
        return replace(value) if value is not None else None
