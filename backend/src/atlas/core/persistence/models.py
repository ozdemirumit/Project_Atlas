from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RuntimeMetadata(Base):
    __tablename__ = "platform_runtime_metadata"
    __table_args__ = (
        CheckConstraint("revision > 0", name="ck_platform_runtime_metadata_revision_positive"),
    )

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class BootstrapRunModel(Base):
    __tablename__ = "platform_bootstrap_runs"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_platform_bootstrap_runs_version_positive"),
        UniqueConstraint(
            "organization_id",
            "environment_id",
            "site_id",
            name="uq_platform_bootstrap_runs_deployment",
        ),
    )

    run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False)
    release_id: Mapped[str] = mapped_column(String(128), nullable=False)
    profile: Mapped[str] = mapped_column(String(32), nullable=False)
    plan_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    resume_key: Mapped[str] = mapped_column(String(128), nullable=False)
    configuration_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    phase_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    checkpoints: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    artifact_acquisition: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    configuration_rendering: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    trust_provisioning: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    data_initialization: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    service_deployment: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    identity_handoff: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    integration_validation: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    end_to_end_verification: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    operational_handoff: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    idempotency_records: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    lease_holder_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_acquired_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SupportBundleExportModel(Base):
    __tablename__ = "platform_support_bundle_exports"
    __table_args__ = (
        CheckConstraint(
            "source_run_version > 0",
            name="ck_platform_support_bundle_exports_source_version_positive",
        ),
        CheckConstraint(
            "archive_size_bytes > 0",
            name="ck_platform_support_bundle_exports_archive_size_positive",
        ),
        UniqueConstraint(
            "actor_id",
            "idempotency_key",
            name="uq_platform_support_bundle_exports_actor_idempotency",
        ),
    )

    export_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_run_version: Mapped[int] = mapped_column(Integer, nullable=False)
    preview_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    archive_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    archive_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    archive_name: Mapped[str] = mapped_column(String(180), nullable=False)
    included_count: Mapped[int] = mapped_column(Integer, nullable=False)
    excluded_count: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class LogicalBackupModel(Base):
    __tablename__ = "platform_logical_backups"
    __table_args__ = (
        CheckConstraint(
            "source_run_version > 0", name="ck_platform_logical_backups_source_version"
        ),
        CheckConstraint("archive_size_bytes > 0", name="ck_platform_logical_backups_archive_size"),
        UniqueConstraint(
            "actor_id", "idempotency_key", name="uq_platform_logical_backups_actor_idempotency"
        ),
    )

    backup_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_run_version: Mapped[int] = mapped_column(Integer, nullable=False)
    preview_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    archive_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    archive_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    archive_name: Mapped[str] = mapped_column(String(180), nullable=False)
    entry_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RestoreValidationModel(Base):
    __tablename__ = "platform_restore_validations"
    __table_args__ = (
        CheckConstraint("entry_count > 0", name="ck_platform_restore_validations_entry_count"),
        UniqueConstraint(
            "actor_id", "idempotency_key", name="uq_platform_restore_validations_actor_idempotency"
        ),
    )

    validation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    backup_id: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    archive_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    check_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    entry_count: Mapped[int] = mapped_column(Integer, nullable=False)
    validated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
