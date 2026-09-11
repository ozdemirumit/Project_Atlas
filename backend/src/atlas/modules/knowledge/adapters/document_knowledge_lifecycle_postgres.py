from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from atlas.core.persistence.models import (
    DocumentKnowledgeConflictModel,
    DocumentKnowledgeItemLifecycleModel,
)
from atlas.modules.knowledge.domain.document_knowledge_lifecycle import (
    DocumentKnowledgeConflict,
    DocumentKnowledgeItemLifecycleRecord,
    DocumentKnowledgeItemLifecycleState,
)

_LIFECYCLE_DATETIME_FIELDS = {"created_at", "updated_at"}
_CONFLICT_DATETIME_FIELDS = {"detected_at", "resolved_at"}


def _normalize(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def _restore(payload: dict[str, Any], *, datetime_fields: set[str]) -> dict[str, Any]:
    restored = dict(payload)
    for field in datetime_fields:
        if restored.get(field) is not None:
            restored[field] = datetime.fromisoformat(str(restored[field]))
    return restored


class PostgreSQLDocumentKnowledgeLifecycleRepository:
    """Real Postgres-backed lifecycle/conflict repository. See
    atlas.modules.knowledge.application.document_knowledge_lifecycle_ports for the Protocol this
    implements.

    `put_lifecycle` uses `SELECT ... FOR UPDATE` inside one transaction to make its
    compare-and-swap genuinely race-safe against concurrent writers on the same item -- unlike
    the insert-only `add_*` methods on the sibling `document_knowledge_postgres.py` repository,
    this table is a mutable "current state" row, so its CAS write needs a real row lock, not just
    an `IntegrityError` catch on a unique constraint.
    """

    def __init__(
        self,
        *,
        engine: AsyncEngine,
        session_factory: Callable[[], AsyncSession] | None = None,
    ) -> None:
        self._engine = engine
        self._sessions = session_factory or async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLDocumentKnowledgeLifecycleRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True))

    @staticmethod
    def _restore_lifecycle(
        row: DocumentKnowledgeItemLifecycleModel,
    ) -> DocumentKnowledgeItemLifecycleRecord:
        return DocumentKnowledgeItemLifecycleRecord(
            **cast(Any, _restore(row.payload, datetime_fields=_LIFECYCLE_DATETIME_FIELDS))
        )

    @staticmethod
    def _restore_conflict(row: DocumentKnowledgeConflictModel) -> DocumentKnowledgeConflict:
        return DocumentKnowledgeConflict(
            **cast(Any, _restore(row.payload, datetime_fields=_CONFLICT_DATETIME_FIELDS))
        )

    async def get_lifecycle(
        self, *, knowledge_item_id: str, organization_id: str, environment_id: str
    ) -> DocumentKnowledgeItemLifecycleRecord | None:
        async with self._sessions() as session:
            row = await session.get(
                DocumentKnowledgeItemLifecycleModel,
                (knowledge_item_id, organization_id, environment_id),
            )
        return self._restore_lifecycle(row) if row is not None else None

    async def put_lifecycle(
        self,
        *,
        expected: DocumentKnowledgeItemLifecycleRecord | None,
        replacement: DocumentKnowledgeItemLifecycleRecord,
    ) -> bool:
        try:
            async with self._sessions() as session, session.begin():
                stmt = (
                    select(DocumentKnowledgeItemLifecycleModel)
                    .where(
                        DocumentKnowledgeItemLifecycleModel.knowledge_item_id
                        == replacement.knowledge_item_id,
                        DocumentKnowledgeItemLifecycleModel.organization_id
                        == replacement.organization_id,
                        DocumentKnowledgeItemLifecycleModel.environment_id
                        == replacement.environment_id,
                    )
                    .with_for_update()
                )
                row = await session.scalar(stmt)
                current = self._restore_lifecycle(row) if row is not None else None
                if current != expected:
                    return False
                payload = cast(Any, _normalize(asdict(replacement)))
                if row is None:
                    session.add(
                        DocumentKnowledgeItemLifecycleModel(
                            knowledge_item_id=replacement.knowledge_item_id,
                            organization_id=replacement.organization_id,
                            environment_id=replacement.environment_id,
                            state=replacement.state.value,
                            payload=payload,
                        )
                    )
                else:
                    row.state = replacement.state.value
                    row.payload = payload
            return True
        except IntegrityError:
            return False

    async def get_active_states(
        self,
        *,
        knowledge_item_ids: Sequence[str],
        organization_id: str,
        environment_id: str,
    ) -> frozenset[str]:
        requested = set(knowledge_item_ids)
        if not requested:
            return frozenset()
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(DocumentKnowledgeItemLifecycleModel).where(
                        DocumentKnowledgeItemLifecycleModel.knowledge_item_id.in_(requested),
                        DocumentKnowledgeItemLifecycleModel.organization_id == organization_id,
                        DocumentKnowledgeItemLifecycleModel.environment_id == environment_id,
                    )
                )
            ).all()
        non_active = {
            row.knowledge_item_id
            for row in rows
            if row.state != DocumentKnowledgeItemLifecycleState.ACTIVE.value
        }
        # Any requested id with no row at all is implicitly ACTIVE (SS8's "Published" default).
        return frozenset(requested - non_active)

    async def add_conflict(self, conflict: DocumentKnowledgeConflict) -> bool:
        try:
            async with self._sessions() as session:
                session.add(
                    DocumentKnowledgeConflictModel(
                        conflict_id=conflict.conflict_id,
                        organization_id=conflict.organization_id,
                        environment_id=conflict.environment_id,
                        knowledge_item_id_a=conflict.knowledge_item_id_a,
                        knowledge_item_id_b=conflict.knowledge_item_id_b,
                        payload=cast(Any, _normalize(asdict(conflict))),
                    )
                )
                await session.commit()
            return True
        except IntegrityError:
            return False

    async def get_conflict(
        self, *, conflict_id: str, organization_id: str, environment_id: str
    ) -> DocumentKnowledgeConflict | None:
        async with self._sessions() as session:
            row = await session.get(DocumentKnowledgeConflictModel, conflict_id)
        if (
            row is None
            or row.organization_id != organization_id
            or row.environment_id != environment_id
        ):
            return None
        return self._restore_conflict(row)

    async def update_conflict(
        self,
        *,
        expected: DocumentKnowledgeConflict,
        replacement: DocumentKnowledgeConflict,
    ) -> bool:
        async with self._sessions() as session, session.begin():
            stmt = (
                select(DocumentKnowledgeConflictModel)
                .where(DocumentKnowledgeConflictModel.conflict_id == expected.conflict_id)
                .with_for_update()
            )
            row = await session.scalar(stmt)
            if row is None or self._restore_conflict(row) != expected:
                return False
            row.payload = cast(Any, _normalize(asdict(replacement)))
        return True

    async def list_conflicts_for_item(
        self, *, knowledge_item_id: str, organization_id: str, environment_id: str
    ) -> tuple[DocumentKnowledgeConflict, ...]:
        async with self._sessions() as session:
            rows = (
                await session.scalars(
                    select(DocumentKnowledgeConflictModel).where(
                        DocumentKnowledgeConflictModel.organization_id == organization_id,
                        DocumentKnowledgeConflictModel.environment_id == environment_id,
                        (DocumentKnowledgeConflictModel.knowledge_item_id_a == knowledge_item_id)
                        | (DocumentKnowledgeConflictModel.knowledge_item_id_b == knowledge_item_id),
                    )
                )
            ).all()
        return tuple(self._restore_conflict(row) for row in rows)

    async def close(self) -> None:
        await self._engine.dispose()
