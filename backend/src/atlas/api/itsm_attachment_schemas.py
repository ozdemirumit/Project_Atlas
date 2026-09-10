from __future__ import annotations

import base64
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from atlas.api.schemas import ResponseMeta

_STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"
_MEDIA_TYPE = r"^[a-z]+/[a-z0-9.+-]+$"


def _decodable_base64(value: str) -> str:
    try:
        base64.b64decode(value, validate=True)
    except Exception as exc:
        raise ValueError("content_base64 must be valid base64") from exc
    return value


class ItsmAttachmentUploadPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_ticket_id: str = Field(min_length=1, max_length=256)
    filename: str = Field(min_length=1, max_length=255)
    media_type: str = Field(pattern=_MEDIA_TYPE)
    classification: str = Field(pattern=_STABLE_ID)
    content_base64: str = Field(min_length=1)

    @field_validator("content_base64")
    @classmethod
    def _content_base64_decodable(cls, value: str) -> str:
        return _decodable_base64(value)

    def content_bytes(self) -> bytes:
        return base64.b64decode(self.content_base64, validate=True)


class ItsmAttachmentReplacePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=255)
    media_type: str = Field(pattern=_MEDIA_TYPE)
    classification: str = Field(pattern=_STABLE_ID)
    content_base64: str = Field(min_length=1)

    @field_validator("content_base64")
    @classmethod
    def _content_base64_decodable(cls, value: str) -> str:
        return _decodable_base64(value)

    def content_bytes(self) -> bytes:
        return base64.b64decode(self.content_base64, validate=True)


class ItsmAttachmentData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attachment_id: str
    external_ticket_id: str
    filename: str
    media_type: str
    size_bytes: int
    content_digest: str
    classification: str
    uploaded_by: str
    uploaded_at: str
    scan_state: str
    transferable: bool
    allowlist_check_completed: bool
    size_check_completed: bool
    active_content_policy_scan_completed: bool
    secret_pattern_scan_completed: bool
    malware_signature_scan_completed: bool


class ItsmAttachmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ItsmAttachmentData
    meta: ResponseMeta


class ItsmEvidencePackageCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_ticket_id: str = Field(min_length=1, max_length=256)
    attachment_ids: list[str] = Field(min_length=1, max_length=50)
    artifact_versions: list[str] = Field(min_length=1, max_length=50)
    classification: str = Field(pattern=_STABLE_ID)
    expires_at: datetime | None = None


class ItsmEvidencePackageData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_id: str
    external_ticket_id: str
    attachment_ids: list[str]
    manifest_digest: str
    artifact_versions: list[str]
    classification: str
    custodied_by: str
    created_by: str
    created_at: str
    expires_at: str | None


class ItsmEvidencePackageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ItsmEvidencePackageData
    meta: ResponseMeta


class ItsmAttachmentDownloadLinkCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attachment_id: str = Field(pattern=_STABLE_ID)
    ttl_seconds: int = Field(ge=60, le=86_400)


class ItsmAttachmentDownloadLinkData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    link_id: str
    attachment_id: str
    issued_to_subject_id: str
    issued_at: str
    expires_at: str
    consumed_at: str | None


class ItsmAttachmentDownloadLinkResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ItsmAttachmentDownloadLinkData
    meta: ResponseMeta


class ItsmAttachmentDownloadData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attachment: ItsmAttachmentData
    content_base64: str


class ItsmAttachmentDownloadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ItsmAttachmentDownloadData
    meta: ResponseMeta
