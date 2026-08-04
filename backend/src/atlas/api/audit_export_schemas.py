from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from atlas.api.schemas import ResponseMeta
from atlas.api.security_export_schemas import DeliveryRecordData, DestinationHealthData
from atlas.modules.security_export.domain.models import (
    AuditEventPage,
    AuditExportOverview,
    AuditRetryResult,
)


class AuditEventData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    sequence: int
    event_id: str
    event_type: str
    schema_version: str
    occurred_at: datetime
    accepted_at: datetime
    correlation_id: str
    subject_id: str | None
    actor_type: str | None
    authentication_method: str | None
    assurance_level: str | None
    permission_id: str | None
    resource_type: str | None
    scope_reference: str
    decision_id: str | None
    outcome: str
    result_code: str
    target_subject_id: str | None


class AuditEventPageData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    events: list[AuditEventData]
    limit: int
    next_cursor: str | None
    has_more: bool

    @classmethod
    def from_domain(cls, page: AuditEventPage) -> AuditEventPageData:
        return cls.model_validate(page)


class AuditExportOverviewData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    generated_at: datetime
    page: AuditEventPageData
    health: list[DestinationHealthData]
    recent_deliveries: list[DeliveryRecordData]
    safety_notice: str

    @classmethod
    def from_domain(cls, overview: AuditExportOverview) -> AuditExportOverviewData:
        return cls.model_validate(overview)


class AuditExportOverviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: AuditExportOverviewData
    meta: ResponseMeta


class AuditRetryData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    attempted: int
    delivered: int
    retrying: int
    dead_letter: int
    generated_at: datetime

    @classmethod
    def from_domain(cls, result: AuditRetryResult) -> AuditRetryData:
        return cls.model_validate(result)


class AuditRetryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: AuditRetryData
    meta: ResponseMeta
