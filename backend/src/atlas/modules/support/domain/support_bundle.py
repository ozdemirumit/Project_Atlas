from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

STABLE_ID = re.compile(r"^[a-z][a-z0-9_.:-]{2,127}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")


class SupportEntryDisposition(StrEnum):
    INCLUDED = "included"
    EXCLUDED = "excluded"


class SupportTargetState(StrEnum):
    EMPTY = "empty"
    REUSABLE = "reusable"


class SupportExportState(StrEnum):
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class SupportBundleEntry:
    entry_id: str
    file_name: str
    classification: str
    mandatory: bool
    disposition: SupportEntryDisposition
    reason_code: str
    size_bytes: int
    sha256: str | None

    def __post_init__(self) -> None:
        if not STABLE_ID.fullmatch(self.entry_id):
            raise ValueError("support entry identifier is invalid")
        if self.classification not in {"internal", "restricted"}:
            raise ValueError("support entry classification is invalid")
        if not self.file_name.endswith(".json") or "/" in self.file_name or "\\" in self.file_name:
            raise ValueError("support entry file name is invalid")
        if self.size_bytes < 0:
            raise ValueError("support entry size is invalid")
        if self.disposition is SupportEntryDisposition.INCLUDED:
            if self.sha256 is None or SHA256.fullmatch(self.sha256) is None:
                raise ValueError("included support entry requires a digest")
        elif self.sha256 is not None or self.size_bytes != 0:
            raise ValueError("excluded support entry cannot expose content metadata")


@dataclass(frozen=True, slots=True)
class SupportBundlePreview:
    preview_id: str
    schema_version: str
    catalog_version: str
    organization_id: str
    environment_id: str
    site_id: str
    source_run_id: str
    source_run_version: int
    release_id: str
    handoff_report_digest: str
    source_evidence_digest: str
    component_ids: tuple[str, ...]
    lookback_hours: int
    window_start: datetime
    window_end: datetime
    entries: tuple[SupportBundleEntry, ...]
    included_count: int
    excluded_count: int
    content_bytes: int
    max_content_bytes: int
    redaction_check_count: int
    preview_digest: str
    target_id: str
    target_state: SupportTargetState
    archive_sha256: str
    archive_size_bytes: int
    generated_at: datetime
    expires_at: datetime
    exportable: bool
    external_transfer_performed: bool = False
    arbitrary_file_collection_performed: bool = False
    network_request_performed: bool = False
    model_inference_performed: bool = False
    infrastructure_mutation_performed: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.preview_id,
            self.schema_version,
            self.catalog_version,
            self.organization_id,
            self.environment_id,
            self.site_id,
            self.source_run_id,
            self.release_id,
            self.target_id,
        ):
            if not STABLE_ID.fullmatch(value):
                raise ValueError("support preview identifier is invalid")
        for digest in (
            self.handoff_report_digest,
            self.source_evidence_digest,
            self.preview_digest,
            self.archive_sha256,
        ):
            if SHA256.fullmatch(digest) is None:
                raise ValueError("support preview digest is invalid")
        if self.source_run_version < 1 or not 1 <= self.lookback_hours <= 168:
            raise ValueError("support preview source or window is invalid")
        if self.window_start >= self.window_end or self.generated_at >= self.expires_at:
            raise ValueError("support preview timestamps are invalid")
        if self.included_count + self.excluded_count != len(self.entries):
            raise ValueError("support preview entry counts are inconsistent")
        if self.content_bytes < 1 or self.content_bytes > self.max_content_bytes:
            raise ValueError("support preview content budget is invalid")
        if self.archive_size_bytes < self.content_bytes or self.redaction_check_count < 1:
            raise ValueError("support preview archive evidence is invalid")
        if not self.exportable or any(
            (
                self.external_transfer_performed,
                self.arbitrary_file_collection_performed,
                self.network_request_performed,
                self.model_inference_performed,
                self.infrastructure_mutation_performed,
            )
        ):
            raise ValueError("support preview violates the local-only safety boundary")


@dataclass(frozen=True, slots=True)
class SupportBundleExport:
    export_id: str
    state: SupportExportState
    actor_id: str
    organization_id: str
    environment_id: str
    site_id: str
    source_run_id: str
    source_run_version: int
    preview_digest: str
    request_fingerprint: str
    idempotency_key: str
    archive_sha256: str
    archive_size_bytes: int
    archive_name: str
    included_count: int
    excluded_count: int
    created_at: datetime
    expires_at: datetime
    reused: bool
    external_transfer_performed: bool = False

    def __post_init__(self) -> None:
        for value in (
            self.export_id,
            self.actor_id,
            self.organization_id,
            self.environment_id,
            self.site_id,
            self.source_run_id,
        ):
            if not STABLE_ID.fullmatch(value):
                raise ValueError("support export identifier is invalid")
        for digest in (self.preview_digest, self.request_fingerprint, self.archive_sha256):
            if SHA256.fullmatch(digest) is None:
                raise ValueError("support export digest is invalid")
        if not self.archive_name.endswith(".zip") or "/" in self.archive_name:
            raise ValueError("support archive name is invalid")
        if self.archive_size_bytes < 1 or self.source_run_version < 1:
            raise ValueError("support export size or source version is invalid")
        if self.created_at >= self.expires_at or self.external_transfer_performed:
            raise ValueError("support export safety or expiry is invalid")
