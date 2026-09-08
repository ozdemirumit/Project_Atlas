from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta


class UpsertItsmIncidentRecordPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str = Field(min_length=1, max_length=256)
    external_system: str = Field(min_length=1, max_length=128)
    external_instance: str = Field(min_length=1, max_length=128)
    external_record_id: str = Field(min_length=1, max_length=256)
    display_number: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=500)
    sanitized_summary: str = Field(min_length=1, max_length=4000)
    state: str = Field(min_length=1, max_length=64)
    priority: str = Field(min_length=1, max_length=64)
    impact: str = Field(min_length=1, max_length=64)
    urgency: str = Field(min_length=1, max_length=64)
    severity: str = Field(min_length=1, max_length=64)
    assignment_group: str | None = Field(default=None, max_length=256)
    owner_reference: str | None = Field(default=None, max_length=256)
    requester_reference: str | None = Field(default=None, max_length=256)
    approver_reference: str | None = Field(default=None, max_length=256)
    service_reference: str | None = Field(default=None, max_length=256)
    configuration_item_reference: str | None = Field(default=None, max_length=256)
    environment_id: str = Field(min_length=1, max_length=128)
    site_id: str = Field(min_length=1, max_length=128)
    organizational_scope: str = Field(min_length=1, max_length=128)
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    planned_start_at: datetime | None = None
    planned_end_at: datetime | None = None
    classification: str = Field(min_length=1, max_length=32)
    access_policy_reference: str = Field(min_length=1, max_length=128)
    retention_reference: str = Field(min_length=1, max_length=128)
    external_version: str = Field(min_length=1, max_length=256)
    last_synchronized_at: datetime
    last_synchronization_status: str = Field(min_length=1, max_length=64)
    detection_source: str = Field(min_length=1, max_length=256)
    first_observed_at: datetime
    symptoms: str = Field(min_length=1, max_length=4000)
    affected_services: list[str] = Field(default_factory=list)
    current_impact_summary: str = Field(min_length=1, max_length=4000)
    evidence_references: list[str] = Field(default_factory=list)
    investigation_references: list[str] = Field(default_factory=list)
    probable_causes: list[str] = Field(default_factory=list)
    probable_cause_confidence: str | None = Field(default=None, max_length=64)
    workaround_summary: str | None = Field(default=None, max_length=4000)
    remediation_recommendation_reference: str | None = Field(default=None, max_length=256)
    current_status_summary: str = Field(min_length=1, max_length=4000)
    resolution_summary: str | None = Field(default=None, max_length=4000)
    confirmed_cause: str | None = Field(default=None, max_length=4000)
    validation_outcome: str | None = Field(default=None, max_length=64)


class ItsmIncidentRecordData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    integration_reference: str
    profile_id: str
    external_system: str
    external_instance: str
    external_record_id: str
    display_number: str
    title: str
    state: str
    priority: str
    severity: str
    environment_id: str
    site_id: str
    classification: str
    external_version: str
    last_synchronized_at: str
    detection_source: str
    symptoms: str
    current_status_summary: str
    resolution_summary: str | None


class ItsmIncidentRecordResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ItsmIncidentRecordData
    meta: ResponseMeta
