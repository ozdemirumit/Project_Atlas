from __future__ import annotations

import asyncio
from dataclasses import replace

from atlas.modules.mcp_builder.domain.lab_validation import McpBuilderLabValidation


class InMemoryMcpBuilderLabValidationRepository:
    def __init__(self) -> None:
        self._by_id: dict[str, McpBuilderLabValidation] = {}
        self._by_project: dict[str, McpBuilderLabValidation] = {}
        self._by_security_review: dict[str, McpBuilderLabValidation] = {}
        self._by_create_key: dict[tuple[str, str], McpBuilderLabValidation] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get_by_id(self, *, lab_validation_id: str) -> McpBuilderLabValidation | None:
        return self._copy(self._by_id.get(lab_validation_id))

    async def get_by_project(self, *, project_id: str) -> McpBuilderLabValidation | None:
        return self._copy(self._by_project.get(project_id))

    async def get_by_security_review(
        self, *, security_review_id: str
    ) -> McpBuilderLabValidation | None:
        return self._copy(self._by_security_review.get(security_review_id))

    async def get_by_create_key(
        self, *, operated_by: str, idempotency_key: str
    ) -> McpBuilderLabValidation | None:
        return self._copy(self._by_create_key.get((operated_by, idempotency_key)))

    async def add(self, validation: McpBuilderLabValidation) -> bool:
        async with self._lock:
            create_key = (validation.operated_by, validation.idempotency_key)
            if (
                validation.lab_validation_id in self._by_id
                or validation.project_id in self._by_project
                or validation.security_review_id in self._by_security_review
                or create_key in self._by_create_key
            ):
                return False
            stored = replace(validation, reused=False)
            self._by_id[stored.lab_validation_id] = stored
            self._by_project[stored.project_id] = stored
            self._by_security_review[stored.security_review_id] = stored
            self._by_create_key[create_key] = stored
            return True

    async def close(self) -> None:
        return None

    @staticmethod
    def _copy(value: McpBuilderLabValidation | None) -> McpBuilderLabValidation | None:
        return replace(value) if value is not None else None
