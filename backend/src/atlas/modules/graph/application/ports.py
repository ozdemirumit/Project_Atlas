from __future__ import annotations

from typing import Protocol

from atlas.modules.graph.domain.models import GraphSnapshot


class GraphSnapshotProvider(Protocol):
    async def get_snapshot(self) -> GraphSnapshot: ...
