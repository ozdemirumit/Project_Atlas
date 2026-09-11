from __future__ import annotations

from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict

from atlas.api.schemas import ResponseMeta
from atlas.modules.notifications.domain.models import Notification


class NotificationData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notification_id: str
    recipient_subject_id: str
    organization_id: str
    environment_id: str
    notification_type: str
    reference_id: str
    summary: str
    created_at: datetime
    read_at: datetime | None
    expires_at: datetime | None

    @classmethod
    def from_domain(cls, notification: Notification) -> Self:
        return cls.model_validate(notification, from_attributes=True)


class NotificationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: NotificationData
    meta: ResponseMeta


class NotificationListData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[NotificationData]
    next_cursor: str | None
    limit: int


class NotificationListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: NotificationListData
    meta: ResponseMeta
