from __future__ import annotations

from collections.abc import Callable
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

from atlas.core.persistence.models import NotificationModel
from atlas.modules.notifications.domain.models import Notification

_DATETIME_FIELDS = {"created_at", "read_at", "expires_at"}


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


class PostgreSQLNotificationRepository:
    """Real Postgres-backed notification repository. See
    atlas.modules.notifications.application.ports for the Protocol this implements, and
    atlas.modules.knowledge.adapters.document_knowledge_lifecycle_postgres for the sibling
    adapter this one's `_normalize`/`_restore`/CAS-update shape mirrors.
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
    def from_url(cls, database_url: str) -> PostgreSQLNotificationRepository:
        return cls(engine=create_async_engine(database_url, pool_pre_ping=True))

    @staticmethod
    def _restore_notification(row: NotificationModel) -> Notification:
        return Notification(**cast(Any, _restore(row.payload, datetime_fields=_DATETIME_FIELDS)))

    async def add(self, notification: Notification) -> bool:
        try:
            async with self._sessions() as session:
                session.add(
                    NotificationModel(
                        notification_id=notification.notification_id,
                        recipient_subject_id=notification.recipient_subject_id,
                        organization_id=notification.organization_id,
                        environment_id=notification.environment_id,
                        created_at=notification.created_at,
                        read_at=notification.read_at,
                        payload=cast(Any, _normalize(asdict(notification))),
                    )
                )
                await session.commit()
            return True
        except IntegrityError:
            return False

    async def get(
        self, *, notification_id: str, organization_id: str, environment_id: str
    ) -> Notification | None:
        async with self._sessions() as session:
            row = await session.get(NotificationModel, notification_id)
        if (
            row is None
            or row.organization_id != organization_id
            or row.environment_id != environment_id
        ):
            return None
        return self._restore_notification(row)

    async def update(self, *, expected: Notification, replacement: Notification) -> bool:
        async with self._sessions() as session, session.begin():
            row = await session.get(
                NotificationModel, expected.notification_id, with_for_update=True
            )
            if row is None or self._restore_notification(row) != expected:
                return False
            row.read_at = replacement.read_at
            row.payload = cast(Any, _normalize(asdict(replacement)))
        return True

    async def list_candidates(
        self,
        *,
        recipient_subject_id: str,
        organization_id: str,
        environment_id: str,
        unread_only: bool,
        limit: int,
    ) -> tuple[Notification, ...]:
        stmt = select(NotificationModel).where(
            NotificationModel.recipient_subject_id == recipient_subject_id,
            NotificationModel.organization_id == organization_id,
            NotificationModel.environment_id == environment_id,
        )
        if unread_only:
            stmt = stmt.where(NotificationModel.read_at.is_(None))
        stmt = stmt.limit(limit)
        async with self._sessions() as session:
            rows = (await session.scalars(stmt)).all()
        return tuple(self._restore_notification(row) for row in rows)

    async def close(self) -> None:
        await self._engine.dispose()
