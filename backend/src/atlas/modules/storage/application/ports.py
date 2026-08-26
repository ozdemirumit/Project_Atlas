from __future__ import annotations

from datetime import datetime
from typing import Protocol

from atlas.modules.storage.domain.models import StorageOverview


class StorageOverviewProvider(Protocol):
    async def get_overview(self, *, requested_at: datetime) -> StorageOverview: ...
