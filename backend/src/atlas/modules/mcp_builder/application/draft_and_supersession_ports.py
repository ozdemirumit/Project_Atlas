from __future__ import annotations

from typing import Protocol

from atlas.modules.mcp_builder.domain.draft_and_supersession import (
    BuilderProjectDraft,
    BuilderProjectSupersession,
)


class BuilderDraftRepository(Protocol):
    async def save_draft(self, draft: BuilderProjectDraft) -> None: ...

    async def get_draft(self, draft_id: str) -> BuilderProjectDraft | None: ...

    async def save_supersession(self, supersession: BuilderProjectSupersession) -> None: ...

    async def get_supersession_for(
        self, superseded_project_id: str
    ) -> BuilderProjectSupersession | None: ...
