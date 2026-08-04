from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

STABLE_ID = re.compile(r"^[a-z][a-z0-9_.:-]{2,127}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")


class BackupTargetState(StrEnum):
    EMPTY = "empty"
    REUSABLE = "reusable"


class BackupState(StrEnum):
    COMPLETED = "completed"


class RestoreValidationState(StrEnum):
    PASSED = "passed"


@dataclass(frozen=True, slots=True)
class BackupEntry:
    entry_id: str
    file_name: str
    classification: str
    mandatory: bool
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        if not STABLE_ID.fullmatch(self.entry_id):
            raise ValueError("backup entry identifier is invalid")
        if self.classification != "internal":
            raise ValueError("backup entry classification is invalid")
        if not self.file_name.endswith(".json") or any(x in self.file_name for x in ("/", "\\")):
            raise ValueError("backup entry file name is invalid")
        if self.size_bytes < 1 or SHA256.fullmatch(self.sha256) is None:
            raise ValueError("backup entry evidence is invalid")


@dataclass(frozen=True, slots=True)
class BackupPreview:
    preview_id: str
    schema_version: str
    catalog_version: str
    organization_id: str
    environment_id: str
    site_id: str
    source_run_id: str
    source_run_version: int
    release_id: str
    source_evidence_digest: str
    component_ids: tuple[str, ...]
    entries: tuple[BackupEntry, ...]
    content_bytes: int
    max_content_bytes: int
    preview_digest: str
    target_id: str
    target_state: BackupTargetState
    archive_sha256: str
    archive_size_bytes: int
    generated_at: datetime
    expires_at: datetime
    creatable: bool
    external_transfer_performed: bool = False
    active_restore_performed: bool = False
    secret_export_performed: bool = False
    network_request_performed: bool = False
    infrastructure_mutation_performed: bool = False

    def __post_init__(self) -> None:
        identifiers = (
            self.preview_id,
            self.schema_version,
            self.catalog_version,
            self.organization_id,
            self.environment_id,
            self.site_id,
            self.source_run_id,
            self.release_id,
            self.target_id,
        )
        if any(STABLE_ID.fullmatch(value) is None for value in identifiers):
            raise ValueError("backup preview identifier is invalid")
        if any(
            SHA256.fullmatch(value) is None
            for value in (self.source_evidence_digest, self.preview_digest, self.archive_sha256)
        ):
            raise ValueError("backup preview digest is invalid")
        if self.source_run_version < 1 or self.generated_at >= self.expires_at:
            raise ValueError("backup preview source or expiry is invalid")
        if not self.entries or len(self.entries) != len(self.component_ids):
            raise ValueError("backup preview entries are invalid")
        if self.content_bytes < 1 or self.content_bytes > self.max_content_bytes:
            raise ValueError("backup preview content budget is invalid")
        if self.archive_size_bytes < self.content_bytes or not self.creatable:
            raise ValueError("backup preview archive evidence is invalid")
        if any(
            (
                self.external_transfer_performed,
                self.active_restore_performed,
                self.secret_export_performed,
                self.network_request_performed,
                self.infrastructure_mutation_performed,
            )
        ):
            raise ValueError("backup preview violates safety boundaries")


@dataclass(frozen=True, slots=True)
class BackupRecord:
    backup_id: str
    state: BackupState
    actor_id: str
    organization_id: str
    environment_id: str
    site_id: str
    source_run_id: str
    source_run_version: int
    preview_digest: str
    request_fingerprint: str
    idempotency_key: str
    target_id: str
    archive_sha256: str
    archive_size_bytes: int
    archive_name: str
    entry_count: int
    created_at: datetime
    expires_at: datetime
    reused: bool = False

    def __post_init__(self) -> None:
        identifiers = (
            self.backup_id,
            self.actor_id,
            self.organization_id,
            self.environment_id,
            self.site_id,
            self.source_run_id,
            self.target_id,
        )
        if any(STABLE_ID.fullmatch(value) is None for value in identifiers):
            raise ValueError("backup record identifier is invalid")
        if any(
            SHA256.fullmatch(value) is None
            for value in (self.preview_digest, self.request_fingerprint, self.archive_sha256)
        ):
            raise ValueError("backup record digest is invalid")
        if self.source_run_version < 1 or self.archive_size_bytes < 1 or self.entry_count < 1:
            raise ValueError("backup record size or source is invalid")
        if not self.archive_name.endswith(".zip") or "/" in self.archive_name:
            raise ValueError("backup archive name is invalid")
        if self.created_at >= self.expires_at:
            raise ValueError("backup expiry is invalid")


@dataclass(frozen=True, slots=True)
class RestoreValidation:
    validation_id: str
    state: RestoreValidationState
    backup_id: str
    actor_id: str
    request_fingerprint: str
    idempotency_key: str
    archive_sha256: str
    validation_digest: str
    check_ids: tuple[str, ...]
    entry_count: int
    validated_at: datetime
    isolated_target: bool = True
    active_repository_write_performed: bool = False
    operational_recovery_performed: bool = False
    secret_restore_performed: bool = False
    network_request_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        if any(
            STABLE_ID.fullmatch(value) is None
            for value in (self.validation_id, self.backup_id, self.actor_id)
        ):
            raise ValueError("restore validation identifier is invalid")
        if any(
            SHA256.fullmatch(value) is None
            for value in (self.request_fingerprint, self.archive_sha256, self.validation_digest)
        ):
            raise ValueError("restore validation digest is invalid")
        if len(self.check_ids) != 6 or len(set(self.check_ids)) != 6 or self.entry_count < 1:
            raise ValueError("restore validation checks are incomplete")
        if not self.isolated_target or any(
            (
                self.active_repository_write_performed,
                self.operational_recovery_performed,
                self.secret_restore_performed,
                self.network_request_performed,
            )
        ):
            raise ValueError("restore validation violates isolation boundaries")
