from __future__ import annotations

from typing import Protocol

from atlas.modules.notifications.domain.models import Notification


class NotificationError(Exception):
    def __init__(self, code: str, detail: str | None = None) -> None:
        super().__init__(detail or code)
        self.code = code
        self.detail = detail or code


class NotificationRepository(Protocol):
    async def add(self, notification: Notification) -> bool:
        """Insert-only; returns False on a colliding `notification_id` (should not happen given
        the uuid4-derived id, but mirrors every sibling repository's own defensive contract)."""
        ...

    async def get(
        self, *, notification_id: str, organization_id: str, environment_id: str
    ) -> Notification | None: ...

    async def update(self, *, expected: Notification, replacement: Notification) -> bool:
        """Compare-and-swap write, used only by `mark_read` -- mirrors
        `DocumentKnowledgeLifecycleRepository.put_lifecycle`'s CAS shape."""
        ...

    async def list_candidates(
        self,
        *,
        recipient_subject_id: str,
        organization_id: str,
        environment_id: str,
        unread_only: bool,
        limit: int,
    ) -> tuple[Notification, ...]:
        """Every notification (up to `limit`) addressed to this recipient in this scope,
        filtered by `unread_only` if set. Ordering is not guaranteed by this Protocol -- the
        caller (`NotificationService.list_for_subject`) applies its own deterministic sort and
        cursor pagination over the returned candidates, the same "bounded scan, service-side
        pagination" shape `HumanReviewService.inbox()` already uses in this codebase."""
        ...

    async def close(self) -> None: ...
