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


class UpgradeSimulationModel(Base):
    __tablename__ = "platform_upgrade_simulations"
    __table_args__ = (
        CheckConstraint("source_run_version > 0", name="ck_platform_upgrade_simulations_source"),
        CheckConstraint(
            "estimated_downtime_minutes > 0",
            name="ck_platform_upgrade_simulations_downtime",
        ),
        UniqueConstraint(
            "actor_id",
            "idempotency_key",
            name="uq_platform_upgrade_simulations_actor_idempotency",
        ),
    )

    simulation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_run_version: Mapped[int] = mapped_column(Integer, nullable=False)
    plan_id: Mapped[str] = mapped_column(String(128), nullable=False)
    plan_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    backup_id: Mapped[str] = mapped_column(String(128), nullable=False)
    restore_validation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    impacted_service_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    post_verification_check_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    abort_injected_at_step_id: Mapped[str] = mapped_column(String(128), nullable=False)
    rollback_decision: Mapped[str] = mapped_column(String(128), nullable=False)
    estimated_downtime_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    simulation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UpgradeChangeReviewPacketModel(Base):
    __tablename__ = "platform_upgrade_change_review_packets"
    __table_args__ = (
        CheckConstraint(
            "source_run_version > 0",
            name="ck_platform_upgrade_change_review_packets_source",
        ),
        UniqueConstraint(
            "actor_id",
            "idempotency_key",
            name="uq_platform_upgrade_change_review_packets_actor_idempotency",
        ),
    )

    packet_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_run_version: Mapped[int] = mapped_column(Integer, nullable=False)
    preview_id: Mapped[str] = mapped_column(String(128), nullable=False)
    preview_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    plan_id: Mapped[str] = mapped_column(String(128), nullable=False)
    plan_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    simulation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    simulation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    backup_id: Mapped[str] = mapped_column(String(128), nullable=False)
    restore_validation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    risk_class: Mapped[str] = mapped_column(String(128), nullable=False)
    change_class: Mapped[str] = mapped_column(String(128), nullable=False)
    impacted_service_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    migration_step_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    abort_criterion_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    rollback_step_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    post_verification_check_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    assumption_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    unknown_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    residual_risk_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    owner_role_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    evidence_digests: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    proposed_window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    proposed_window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estimated_downtime_min_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_downtime_max_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    rollback_window_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    itsm_draft_id: Mapped[str] = mapped_column(String(128), nullable=False)
    itsm_draft_title: Mapped[str] = mapped_column(String(160), nullable=False)
    itsm_draft_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    packet_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class UpgradeChangeHumanReviewModel(Base):
    __tablename__ = "platform_upgrade_change_human_reviews"
    __table_args__ = (
        CheckConstraint("version > 0", name="ck_platform_upgrade_human_reviews_version"),
        UniqueConstraint(
            "requester_id",
            "idempotency_key",
            name="uq_platform_upgrade_human_reviews_requester_idempotency",
        ),
    )

    review_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    packet_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    packet_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    requester_id: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False)
    risk_class: Mapped[str] = mapped_column(String(128), nullable=False)
    change_class: Mapped[str] = mapped_column(String(128), nullable=False)
    impacted_service_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    evidence_digests: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    proposed_window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    proposed_window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    justification: Mapped[str] = mapped_column(String(500), nullable=False)
    required_role_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    stages: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    decisions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class HumanReviewCompletionReceiptModel(Base):
    __tablename__ = "platform_human_review_completion_receipts"
    __table_args__ = (
        CheckConstraint("version = 1", name="ck_platform_review_receipts_version"),
        UniqueConstraint("review_id", name="uq_platform_review_receipts_review"),
        UniqueConstraint(
            "created_by",
            "idempotency_key",
            name="uq_platform_review_receipts_creator_idempotency",
        ),
    )

    receipt_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    review_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    review_version: Mapped[int] = mapped_column(Integer, nullable=False)
    review_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    review_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    packet_id: Mapped[str] = mapped_column(String(128), nullable=False)
    packet_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    requester_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False)
    risk_class: Mapped[str] = mapped_column(String(128), nullable=False)
    change_class: Mapped[str] = mapped_column(String(128), nullable=False)
    impacted_service_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    evidence_digests: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    proposed_window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    proposed_window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stages: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
