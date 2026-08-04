from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from atlas.api.schemas import ResponseMeta
from atlas.modules.recovery.domain.backup import BackupPreview, BackupRecord, RestoreValidation

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
DIGEST = r"^[a-f0-9]{64}$"


class BackupPreviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(
        default="atlas.logical-backup-preview-request.v1", pattern=STABLE_ID
    )
    source_run_id: str = Field(pattern=STABLE_ID)
    component_ids: tuple[str, ...] = Field(min_length=5, max_length=7)

    @field_validator("component_ids")
    @classmethod
    def unique_components(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)) or any(len(item) > 128 for item in value):
            raise ValueError("backup component selection is invalid")
        return value


class BackupEntryData(BaseModel):
    entry_id: str
    file_name: str
    classification: str
    mandatory: bool
    size_bytes: int
    sha256: str


class BackupPreviewData(BaseModel):
    preview_id: str
    schema_version: str
    catalog_version: str
    source_run_id: str
    source_run_version: int
    release_id: str
    source_evidence_digest: str
    component_ids: list[str]
    entries: list[BackupEntryData]
    content_bytes: int
    max_content_bytes: int
    preview_digest: str
    target_id: str
    target_state: str
    archive_sha256: str
    archive_size_bytes: int
    generated_at: datetime
    expires_at: datetime
    creatable: bool
    external_transfer_performed: bool
    active_restore_performed: bool
    secret_export_performed: bool
    network_request_performed: bool
    infrastructure_mutation_performed: bool

    @classmethod
    def from_domain(cls, item: BackupPreview) -> BackupPreviewData:
        return cls(
            **{
                field: getattr(item, field)
                for field in cls.model_fields
                if field not in {"component_ids", "entries", "target_state"}
            },
            component_ids=list(item.component_ids),
            target_state=item.target_state.value,
            entries=[
                BackupEntryData(
                    entry_id=entry.entry_id,
                    file_name=entry.file_name,
                    classification=entry.classification,
                    mandatory=entry.mandatory,
                    size_bytes=entry.size_bytes,
                    sha256=entry.sha256,
                )
                for entry in item.entries
            ],
        )


class BackupPreviewResponse(BaseModel):
    data: BackupPreviewData
    meta: ResponseMeta


class BackupCreateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(default="atlas.logical-backup-create-request.v1", pattern=STABLE_ID)
    source_run_version: int = Field(ge=1)
    component_ids: tuple[str, ...] = Field(min_length=5, max_length=7)
    preview_digest: str = Field(pattern=DIGEST)
    archive_sha256: str = Field(pattern=DIGEST)
    target_id: str = Field(pattern=STABLE_ID)
    expected_target_state: str = Field(pattern=r"^(empty|reusable)$")
    justification: str = Field(min_length=12, max_length=500)
    confirmed: bool


class BackupData(BaseModel):
    backup_id: str
    state: str
    source_run_id: str
    source_run_version: int
    preview_digest: str
    target_id: str
    archive_sha256: str
    archive_size_bytes: int
    archive_name: str
    entry_count: int
    created_at: datetime
    expires_at: datetime
    reused: bool
    external_transfer_performed: bool = False
    active_restore_performed: bool = False

    @classmethod
    def from_domain(cls, item: BackupRecord) -> BackupData:
        return cls(
            backup_id=item.backup_id,
            state=item.state.value,
            source_run_id=item.source_run_id,
            source_run_version=item.source_run_version,
            preview_digest=item.preview_digest,
            target_id=item.target_id,
            archive_sha256=item.archive_sha256,
            archive_size_bytes=item.archive_size_bytes,
            archive_name=item.archive_name,
            entry_count=item.entry_count,
            created_at=item.created_at,
            expires_at=item.expires_at,
            reused=item.reused,
        )


class BackupResponse(BaseModel):
    data: BackupData
    meta: ResponseMeta


class RestoreValidationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = Field(
        default="atlas.isolated-restore-validation-request.v1", pattern=STABLE_ID
    )
    archive_sha256: str = Field(pattern=DIGEST)
    confirmed_isolated: bool


class RestoreValidationData(BaseModel):
    validation_id: str
    state: str
    backup_id: str
    archive_sha256: str
    validation_digest: str
    check_ids: list[str]
    entry_count: int
    validated_at: datetime
    isolated_target: bool
    active_repository_write_performed: bool
    operational_recovery_performed: bool
    secret_restore_performed: bool
    network_request_performed: bool
    reused: bool

    @classmethod
    def from_domain(cls, item: RestoreValidation) -> RestoreValidationData:
        return cls(
            **{
                field: getattr(item, field)
                for field in cls.model_fields
                if field not in {"state", "check_ids"}
            },
            state=item.state.value,
            check_ids=list(item.check_ids),
        )


class RestoreValidationResponse(BaseModel):
    data: RestoreValidationData
    meta: ResponseMeta
