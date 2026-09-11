from __future__ import annotations

import asyncio

from atlas.modules.notifications.domain.models import Notification


class InMemoryNotificationRepository:
    def __init__(self) -> None:
        self._notifications: dict[str, Notification] = {}
        self._lock = asyncio.Lock()

    async def add(self, notification: Notification) -> bool:
        async with self._lock:
            if notification.notification_id in self._notifications:
                return False
            self._notifications[notification.notification_id] = notification
            return True

    async def get(
        self, *, notification_id: str, organization_id: str, environment_id: str
    ) -> Notification | None:
        record = self._notifications.get(notification_id)
        if (
            record is None
            or record.organization_id != organization_id
            or record.environment_id != environment_id
        ):
            return None
        return record

    async def update(self, *, expected: Notification, replacement: Notification) -> bool:
        async with self._lock:
            if self._notifications.get(expected.notification_id) != expected:
                return False
            self._notifications[expected.notification_id] = replacement
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
        results = [
            record
            for record in self._notifications.values()
            if record.recipient_subject_id == recipient_subject_id
            and record.organization_id == organization_id
            and record.environment_id == environment_id
            and (not unread_only or not record.is_read)
        ]
        return tuple(results[:limit])

    async def close(self) -> None:
        return None
