from __future__ import annotations

import asyncio
from datetime import datetime

from atlas.modules.authorization.domain.models import RoleAssignment


class InMemoryRoleAssignmentRepository:
    """Process-local development/test store for dynamically-granted role assignments. Never
    used in production -- see `PostgreSQLRoleAssignmentRepository`."""

    def __init__(self) -> None:
        self._assignments: dict[str, RoleAssignment] = {}
        self._lock = asyncio.Lock()

    async def list_active_for_subject(
        self, *, subject_id: str, at: datetime
    ) -> tuple[RoleAssignment, ...]:
        async with self._lock:
            return tuple(
                assignment
                for assignment in self._assignments.values()
                if assignment.subject_id == subject_id and assignment.is_active(at)
            )

    async def create(self, assignment: RoleAssignment) -> bool:
        async with self._lock:
            if assignment.assignment_id in self._assignments:
                return False
            self._assignments[assignment.assignment_id] = assignment
            return True
