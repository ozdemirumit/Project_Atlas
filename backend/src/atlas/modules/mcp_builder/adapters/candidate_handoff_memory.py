from __future__ import annotations

import asyncio

from atlas.modules.mcp_builder.domain.candidate_handoff import McpBuilderCandidateHandoff


class InMemoryMcpBuilderCandidateHandoffRepository:
    durable = False

    def __init__(self) -> None:
        self._records: dict[str, McpBuilderCandidateHandoff] = {}
        self._lock = asyncio.Lock()

    async def get_by_id(self, *, handoff_id: str) -> McpBuilderCandidateHandoff | None:
        return self._records.get(handoff_id)

    async def get_by_project(self, *, project_id: str) -> McpBuilderCandidateHandoff | None:
        return next(
            (item for item in self._records.values() if item.project_id == project_id), None
        )

    async def get_by_lab_validation(
        self, *, lab_validation_id: str
    ) -> McpBuilderCandidateHandoff | None:
        return next(
            (
                item
                for item in self._records.values()
                if item.lab_validation_id == lab_validation_id
            ),
            None,
        )

    async def get_by_create_key(
        self, *, custodied_by: str, idempotency_key: str
    ) -> McpBuilderCandidateHandoff | None:
        return next(
            (
                item
                for item in self._records.values()
                if item.custodied_by == custodied_by and item.idempotency_key == idempotency_key
            ),
            None,
        )

    async def add(self, handoff: McpBuilderCandidateHandoff) -> bool:
        async with self._lock:
            if handoff.handoff_id in self._records:
                return False
            if any(
                item.project_id == handoff.project_id
                or item.lab_validation_id == handoff.lab_validation_id
                or (
                    item.custodied_by == handoff.custodied_by
                    and item.idempotency_key == handoff.idempotency_key
                )
                for item in self._records.values()
            ):
                return False
            self._records[handoff.handoff_id] = handoff
            return True

    async def close(self) -> None:
        return None
