from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta


class RegisterSiemDetectionDeploymentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detection_id: str = Field(min_length=1, max_length=32)
    destination_id: str = Field(min_length=1, max_length=128)
    owner: str = Field(min_length=1, max_length=256)


class TransitionSiemDetectionDeploymentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_stage: str = Field(min_length=1, max_length=32)


class RecordSiemIncidentHandoffPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alert_reference: str = Field(min_length=1, max_length=256)
    event_references: list[str] = Field(min_length=1)
    confidence: str = Field(min_length=1, max_length=64)
    triage_status: str = Field(min_length=1, max_length=32)
    affected_deployment: str = Field(min_length=1, max_length=256)
    affected_services: list[str] = Field(default_factory=list)
    affected_targets: list[str] = Field(default_factory=list)
    investigation_summary: str = Field(min_length=1, max_length=4000)
    evidence_link_kinds: list[str] = Field(min_length=1)
    ownership: str = Field(min_length=1, max_length=256)
    synchronization_state: str = Field(min_length=1, max_length=256)
    ai_generated_summary: bool = False
    summary_labeled_as_ai_generated: bool = False


class SiemDetectionDeploymentData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deployment_id: str
    detection_id: str
    detection_version: str
    destination_id: str
    stage: str
    owner: str
    registered_by: str
    registered_at: str
    updated_at: str


class SiemDetectionDeploymentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: SiemDetectionDeploymentData
    meta: ResponseMeta


class SiemIncidentHandoffData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detection_id: str
    detection_version: str
    alert_reference: str
    event_references: list[str]
    severity: str
    confidence: str
    triage_status: str
    affected_deployment: str
    affected_services: list[str]
    affected_targets: list[str]
    investigation_summary: str
    evidence_link_kinds: list[str]
    ownership: str
    synchronization_state: str
    ai_generated_summary: bool
    summary_labeled_as_ai_generated: bool


class SiemIncidentHandoffResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: SiemIncidentHandoffData
    meta: ResponseMeta
