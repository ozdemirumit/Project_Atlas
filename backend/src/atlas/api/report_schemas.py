from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.reports.domain.models import TechnicalReport


class ReportCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_recommendation_id: str = Field(min_length=1, max_length=120)
    source_recommendation_version: int = Field(ge=1)
    report_type: Literal["technical_decision"] = "technical_decision"
    audience: Literal["technical_operations", "management"] = "technical_operations"
    classification: Literal["public", "internal"] = "internal"
    include_itsm_handoff: bool = True
    incident_reference: str | None = Field(
        default=None,
        min_length=5,
        max_length=80,
        pattern=r"^INC-[A-Za-z0-9._-]+$",
    )


class ReportSourceLineageData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommendation_id: str
    recommendation_version: int
    recommendation_state: str
    recommendation_created_at: datetime
    recommendation_expires_at: datetime
    rca_case_id: str
    rca_case_version: int
    target_id: str
    evidence_ids: list[str]
    component_versions: list[str]


class ReportSectionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_id: str
    title: str
    state: str
    statements: list[str]
    evidence_references: list[str]
    limitations: list[str]


class ReportReviewData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    reviewer_id: str | None
    reviewed_at: datetime | None
    rationale: str | None


class ItsmFieldMappingData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    value: str
    source_reference: str


class ItsmHandoffDraftData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: str
    idempotency_key: str
    state: str
    external_system: str
    operation: str
    incident_reference: str
    report_id: str
    report_version: int
    generated_content_label: str
    field_mappings: list[ItsmFieldMappingData]
    artifact_references: list[str]
    classification: str
    redaction_state: str
    human_review_required: bool
    dispatch_authorized: bool
    external_record_mutated: bool


class TechnicalReportData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: str
    version: int
    prior_version_id: str | None
    owner: str
    state: str
    requested_by: str
    created_at: datetime
    expires_at: datetime
    organization_id: str
    environment_id: str
    site_id: str
    target_id: str
    report_type: str
    audience: str
    classification: str
    redaction_state: str
    source: ReportSourceLineageData
    sections: list[ReportSectionData]
    review: ReportReviewData
    itsm_handoff: ItsmHandoffDraftData | None
    rendered_markdown: str
    content_digest: str
    component_versions: list[str]
    data_profile: str
    execution_authorized: bool
    external_mutation_authorized: bool
    safety_notice: str

    @classmethod
    def from_domain(cls, report: TechnicalReport) -> TechnicalReportData:
        return cls.model_validate(report, from_attributes=True)


class TechnicalReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: TechnicalReportData
    meta: ResponseMeta
