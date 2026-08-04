from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from atlas.api.schemas import ResponseMeta
from atlas.modules.security_export.domain.models import (
    DeliveryRecord,
    SecurityExportOverview,
)


class SecurityExportDestinationData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    destination_id: str
    version: int
    name: str
    state: str
    transport: str
    host: str
    port: int
    tls_server_authentication: bool
    tls_hostname_validation: bool
    certificate_not_after: datetime
    facility: int
    selected_categories: list[str]
    classification_ceiling: str
    max_queue_records: int
    max_attempts: int


class TransportReceiptData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    receipt_id: str
    destination_id: str
    event_id: str
    accepted_at: datetime
    transport: str
    collector_acknowledged: bool
    siem_ingestion_confirmed: bool


class DeliveryRecordData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    delivery_id: str
    destination_id: str
    event_id: str
    state: str
    attempts: int
    queued_at: datetime
    updated_at: datetime
    next_attempt_at: datetime | None
    last_error_code: str | None
    receipt: TransportReceiptData | None

    @classmethod
    def from_domain(cls, delivery: DeliveryRecord) -> DeliveryRecordData:
        return cls.model_validate(delivery)


class DestinationHealthData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    destination_id: str
    state: str
    queue_depth: int
    delivered_count: int
    retrying_count: int
    dead_letter_count: int
    certificate_days_remaining: int
    last_transport_handoff_at: datetime | None
    collector_acknowledgement_available: bool
    siem_ingestion_confirmed: bool
    limitations: list[str]


class NormalizedSecurityEventData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    event_id: str
    event_type: str
    source_schema_version: str
    normalized_schema_version: str
    occurred_at: datetime
    correlation_id: str
    category: str
    severity: str
    severity_reason: str
    producer: str
    producer_version: str
    environment_id: str
    site_id: str
    subject_id: str | None
    actor_type: str | None
    permission_id: str | None
    resource_type: str | None
    sanitized_scope_reference: str | None
    outcome: str
    result_code: str
    classification: str
    redaction_state: str
    mapping_version: str


class SyslogMessageData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    event_id: str
    priority: int
    facility: int
    severity_code: int
    timestamp: datetime
    hostname: str
    app_name: str
    message_id: str
    structured_data: str
    summary: str
    payload: str
    payload_bytes: int
    content_digest: str


class SecurityExportOverviewData(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    generated_at: datetime
    mapping_version: str
    normalized_schema_version: str
    destinations: list[SecurityExportDestinationData]
    health: list[DestinationHealthData]
    recent_deliveries: list[DeliveryRecordData]
    preview_event: NormalizedSecurityEventData
    preview_message: SyslogMessageData
    safety_notice: str

    @classmethod
    def from_domain(cls, overview: SecurityExportOverview) -> SecurityExportOverviewData:
        return cls.model_validate(overview)


class SecurityExportOverviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: SecurityExportOverviewData
    meta: ResponseMeta


class SecurityExportTestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: DeliveryRecordData
    meta: ResponseMeta
