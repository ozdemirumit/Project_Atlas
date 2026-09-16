from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from enum import Enum
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import RoleAssignmentModel
from atlas.modules.authorization.domain.models import CapabilityClass, ResourceScope, RoleAssignment


def _normalize(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


class PostgreSQLRoleAssignmentRepository:
    """Durable counterpart to the static, code-level `RoleAssignment` list
    `AuthorizationService` is otherwise built from entirely at startup -- see
    `AuthorizationService.evaluate()`'s additive dynamic-lookup path."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLRoleAssignmentRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    async def list_active_for_subject(
        self, *, subject_id: str, at: datetime
    ) -> tuple[RoleAssignment, ...]:
        async with self._sessions() as session:
            rows = await session.scalars(
                select(RoleAssignmentModel).where(RoleAssignmentModel.subject_id == subject_id)
            )
            assignments = (self._to_domain(row.payload) for row in rows)
            return tuple(assignment for assignment in assignments if assignment.is_active(at))

    async def create(self, assignment: RoleAssignment) -> bool:
        payload = cast(dict[str, Any], _normalize(asdict(assignment)))
        try:
            async with self._sessions.begin() as session:
                session.add(
                    RoleAssignmentModel(
                        assignment_id=assignment.assignment_id,
                        subject_id=assignment.subject_id,
                        role_id=assignment.role_id,
                        payload=payload,
                    )
                )
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _to_domain(raw: dict[str, object]) -> RoleAssignment:
        payload = dict(raw)
        scope_payload = dict(cast(dict[str, object], payload["scope"]))
        scope_payload["capability_class"] = CapabilityClass(str(scope_payload["capability_class"]))
        payload["scope"] = ResourceScope(**cast(Any, scope_payload))
        payload["valid_from"] = datetime.fromisoformat(str(payload["valid_from"]))
        if payload.get("expires_at") is not None:
            payload["expires_at"] = datetime.fromisoformat(str(payload["expires_at"]))
        return RoleAssignment(**cast(Any, payload))
