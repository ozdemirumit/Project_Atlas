from __future__ import annotations

import asyncio

from atlas.modules.mcp_builder.domain.draft_and_supersession import (
    BuilderProjectDraft,
    BuilderProjectSupersession,
)


class InMemoryBuilderDraftRepository:
    def __init__(self) -> None:
        self._drafts: dict[str, BuilderProjectDraft] = {}
        self._supersessions_by_superseded: dict[str, BuilderProjectSupersession] = {}
        self._lock = asyncio.Lock()

    async def save_draft(self, draft: BuilderProjectDraft) -> None:
        async with self._lock:
            self._drafts[draft.draft_id] = draft

    async def get_draft(self, draft_id: str) -> BuilderProjectDraft | None:
        async with self._lock:
            return self._drafts.get(draft_id)

    async def save_supersession(self, supersession: BuilderProjectSupersession) -> None:
        async with self._lock:
            self._supersessions_by_superseded[supersession.superseded_project_id] = supersession

    async def get_supersession_for(
        self, superseded_project_id: str
    ) -> BuilderProjectSupersession | None:
        async with self._lock:
            return self._supersessions_by_superseded.get(superseded_project_id)
