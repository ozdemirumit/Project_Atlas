from __future__ import annotations

from datetime import datetime
from typing import Protocol

from atlas.modules.authorization.domain.models import RoleAssignment


class RoleAssignmentRepository(Protocol):
    async def list_active_for_subject(
        self, *, subject_id: str, at: datetime
    ) -> tuple[RoleAssignment, ...]: ...

    async def create(self, assignment: RoleAssignment) -> bool: ...
