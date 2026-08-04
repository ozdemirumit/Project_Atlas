from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from atlas.api.schemas import ResponseMeta
from atlas.modules.support.domain.support_bundle import (
    SupportBundleExport,
    SupportBundlePreview,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class SupportBundlePreviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="atlas.support-bundle-preview-request.v1", pattern=STABLE_ID
    )
    source_run_id: str = Field(pattern=STABLE_ID)
    component_ids: tuple[str, ...] = Field(min_length=2, max_length=5)
    lookback_hours: int = Field(default=24, ge=1, le=168)

    @field_validator("component_ids")
    @classmethod
    def unique_components(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)) or any(len(item) > 128 for item in value):
            raise ValueError("support component selection is invalid")
        return value


class SupportBundleEntryData(BaseModel):
    entry_id: str
    file_name: str
    classification: str
    mandatory: bool
    disposition: str
    reason_code: str
    size_bytes: int
    sha256: str | None


class SupportBundlePreviewData(BaseModel):
    preview_id: str
    schema_version: str
    catalog_version: str
    source_run_id: str
    source_run_version: int
    release_id: str
    handoff_report_digest: str
    source_evidence_digest: str
    component_ids: list[str]
    lookback_hours: int
    window_start: datetime
    window_end: datetime
    entries: list[SupportBundleEntryData]
    included_count: int
    excluded_count: int
    content_bytes: int
    max_content_bytes: int
    redaction_check_count: int
    preview_digest: str
    target_id: str
    target_state: str
    archive_sha256: str
    archive_size_bytes: int
    generated_at: datetime
    expires_at: datetime
    exportable: bool
    external_transfer_performed: bool
    arbitrary_file_collection_performed: bool
    network_request_performed: bool
    model_inference_performed: bool
    infrastructure_mutation_performed: bool

    @classmethod
    def from_domain(cls, item: SupportBundlePreview) -> SupportBundlePreviewData:
        return cls(
            **{
                field: getattr(item, field)
                for field in cls.model_fields
                if field not in {"entries", "component_ids", "target_state"}
            },
            component_ids=list(item.component_ids),
            target_state=item.target_state.value,
            entries=[
                SupportBundleEntryData(
                    entry_id=entry.entry_id,
                    file_name=entry.file_name,
                    classification=entry.classification,
                    mandatory=entry.mandatory,
                    disposition=entry.disposition.value,
                    reason_code=entry.reason_code,
                    size_bytes=entry.size_bytes,
                    sha256=entry.sha256,
                )
                for entry in item.entries
            ],
        )


class SupportBundlePreviewResponse(BaseModel):
    data: SupportBundlePreviewData
    meta: ResponseMeta


class SupportBundleExportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="atlas.support-bundle-export-request.v1", pattern=STABLE_ID)
    source_run_version: int = Field(ge=1)
    component_ids: tuple[str, ...] = Field(min_length=2, max_length=5)
    lookback_hours: int = Field(ge=1, le=168)
    preview_digest: str = Field(pattern=DIGEST)
    archive_sha256: str = Field(pattern=DIGEST)
    target_id: str = Field(pattern=STABLE_ID)
    expected_target_state: str = Field(pattern=r"^(empty|reusable)$")
    justification: str = Field(min_length=12, max_length=500)
    confirmed: bool


class SupportBundleExportData(BaseModel):
    export_id: str
    state: str
    source_run_id: str
    source_run_version: int
    preview_digest: str
    archive_sha256: str
    archive_size_bytes: int
    archive_name: str
    included_count: int
    excluded_count: int
    created_at: datetime
    expires_at: datetime
    reused: bool
    external_transfer_performed: bool

    @classmethod
    def from_domain(cls, item: SupportBundleExport) -> SupportBundleExportData:
        return cls(
            export_id=item.export_id,
            state=item.state.value,
            source_run_id=item.source_run_id,
            source_run_version=item.source_run_version,
            preview_digest=item.preview_digest,
            archive_sha256=item.archive_sha256,
            archive_size_bytes=item.archive_size_bytes,
            archive_name=item.archive_name,
            included_count=item.included_count,
            excluded_count=item.excluded_count,
            created_at=item.created_at,
            expires_at=item.expires_at,
            reused=item.reused,
            external_transfer_performed=item.external_transfer_performed,
        )


class SupportBundleExportResponse(BaseModel):
    data: SupportBundleExportData
    meta: ResponseMeta
