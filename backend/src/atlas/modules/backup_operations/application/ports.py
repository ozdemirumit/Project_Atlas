from __future__ import annotations

from datetime import datetime
from typing import Protocol

from atlas.modules.backup_operations.domain.models import BackupOverview


class BackupOverviewProvider(Protocol):
    async def get_overview(self, *, requested_at: datetime) -> BackupOverview: ...
