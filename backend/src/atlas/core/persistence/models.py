from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class McpBuilderProjectModel(Base):
    __tablename__ = "mcp_builder_projects"
    __table_args__ = (
        CheckConstraint("version = 1", name="ck_mcp_builder_projects_version"),
        UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_mcp_builder_projects_owner_idempotency"
        ),
    )

    project_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    vendor: Mapped[str] = mapped_column(String(200), nullable=False)
    product: Mapped[str] = mapped_column(String(200), nullable=False)
    intended_product_versions: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    target_environment: Mapped[str] = mapped_column(String(200), nullable=False)
    sdk_profile: Mapped[str] = mapped_column(String(128), nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    source_authority: Mapped[str] = mapped_column(String(200), nullable=False)
    source_owner: Mapped[str] = mapped_column(String(200), nullable=False)
    documentation_version: Mapped[str] = mapped_column(String(200), nullable=False)
    publication_date: Mapped[date] = mapped_column(Date, nullable=False)
    license_id: Mapped[str] = mapped_column(String(200), nullable=False)
    redistribution_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    classification: Mapped[str] = mapped_column(String(32), nullable=False)
    openapi_version: Mapped[str] = mapped_column(String(32), nullable=False)
    api_title: Mapped[str] = mapped_column(String(160), nullable=False)
    api_version: Mapped[str] = mapped_column(String(80), nullable=False)
    source_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_source_json: Mapped[str] = mapped_column(Text, nullable=False)
    declared_servers: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    authentication_schemes: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    capability_candidates: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class McpBuilderDesignCheckpointModel(Base):
    __tablename__ = "mcp_builder_design_checkpoints"
    __table_args__ = (
        CheckConstraint("version = 1", name="ck_mcp_builder_design_checkpoints_version"),
        UniqueConstraint("project_id", name="uq_mcp_builder_design_checkpoints_project"),
        UniqueConstraint(
            "reviewer_id",
            "idempotency_key",
            name="uq_mcp_builder_design_checkpoints_reviewer_idempotency",
        ),
    )

    checkpoint_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    project_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    project_version: Mapped[int] = mapped_column(Integer, nullable=False)
    project_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    reviewer_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    connector_boundary: Mapped[str] = mapped_column(Text, nullable=False)
    target_products: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    network_destinations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    configuration_keys: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    secret_reference_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    entity_mappings: Mapped[list[dict[str, str]]] = mapped_column(JSONB, nullable=False)
    capability_decisions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class McpBuilderGenerationModel(Base):
    __tablename__ = "mcp_builder_generations"
    __table_args__ = (
        CheckConstraint("version = 1", name="ck_mcp_builder_generations_version"),
        UniqueConstraint("project_id", name="uq_mcp_builder_generations_project"),
        UniqueConstraint(
            "requested_by",
            "idempotency_key",
            name="uq_mcp_builder_generations_requester_idempotency",
        ),
    )

    generation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    project_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    project_version: Mapped[int] = mapped_column(Integer, nullable=False)
    project_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    checkpoint_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    checkpoint_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    requested_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    language_profile: Mapped[str] = mapped_column(String(128), nullable=False)
    template_version: Mapped[str] = mapped_column(String(128), nullable=False)
    artifact_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    files: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class McpBuilderValidationModel(Base):
    __tablename__ = "mcp_builder_validations"
    __table_args__ = (
        CheckConstraint("version = 1", name="ck_mcp_builder_validations_version"),
        UniqueConstraint("project_id", name="uq_mcp_builder_validations_project"),
        UniqueConstraint("generation_id", name="uq_mcp_builder_validations_generation"),
        UniqueConstraint(
            "validated_by",
            "idempotency_key",
            name="uq_mcp_builder_validations_validator_idempotency",
        ),
    )

    validation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    project_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    project_version: Mapped[int] = mapped_column(Integer, nullable=False)
    project_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    checkpoint_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    checkpoint_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    generation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    generation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    validated_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    language_profile: Mapped[str] = mapped_column(String(128), nullable=False)
    template_version: Mapped[str] = mapped_column(String(128), nullable=False)
    validation_profile: Mapped[str] = mapped_column(String(128), nullable=False)
    validator_version: Mapped[str] = mapped_column(String(128), nullable=False)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    passed_count: Mapped[int] = mapped_column(Integer, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class McpBuilderDomainReviewModel(Base):
    __tablename__ = "mcp_builder_domain_reviews"
    __table_args__ = (
        CheckConstraint("version = 1", name="ck_mcp_builder_domain_reviews_version"),
        UniqueConstraint("project_id", name="uq_mcp_builder_domain_reviews_project"),
        UniqueConstraint("validation_id", name="uq_mcp_builder_domain_reviews_validation"),
        UniqueConstraint(
            "reviewed_by",
            "idempotency_key",
            name="uq_mcp_builder_domain_reviews_reviewer_idempotency",
        ),
    )

    review_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    project_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    project_version: Mapped[int] = mapped_column(Integer, nullable=False)
    project_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    checkpoint_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    checkpoint_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    generation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    generation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    validation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_profile: Mapped[str] = mapped_column(String(128), nullable=False)
    validator_version: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    review_profile: Mapped[str] = mapped_column(String(128), nullable=False)
    reviewer_contract_version: Mapped[str] = mapped_column(String(128), nullable=False)
    capability_decisions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    accepted_count: Mapped[int] = mapped_column(Integer, nullable=False)
    needs_evidence_count: Mapped[int] = mapped_column(Integer, nullable=False)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class McpBuilderSecurityReviewModel(Base):
    __tablename__ = "mcp_builder_security_reviews"
    __table_args__ = (
        CheckConstraint("version = 1", name="ck_mcp_builder_security_reviews_version"),
        UniqueConstraint("project_id", name="uq_mcp_builder_security_reviews_project"),
        UniqueConstraint("domain_review_id", name="uq_mcp_builder_security_reviews_domain_review"),
        UniqueConstraint(
            "reviewed_by",
            "idempotency_key",
            name="uq_mcp_builder_security_reviews_reviewer_idempotency",
        ),
    )

    review_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    project_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    project_version: Mapped[int] = mapped_column(Integer, nullable=False)
    project_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    checkpoint_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    checkpoint_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    generation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    generation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    validation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_profile: Mapped[str] = mapped_column(String(128), nullable=False)
    validator_version: Mapped[str] = mapped_column(String(128), nullable=False)
    domain_review_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    domain_review_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    domain_review_profile: Mapped[str] = mapped_column(String(128), nullable=False)
    domain_reviewer_contract_version: Mapped[str] = mapped_column(String(128), nullable=False)
    domain_reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    review_profile: Mapped[str] = mapped_column(String(128), nullable=False)
    reviewer_contract_version: Mapped[str] = mapped_column(String(128), nullable=False)
    control_assessments: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    accepted_count: Mapped[int] = mapped_column(Integer, nullable=False)
    needs_remediation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class McpBuilderLabValidationModel(Base):
    __tablename__ = "mcp_builder_lab_validations"
    __table_args__ = (
        CheckConstraint("version = 1", name="ck_mcp_builder_lab_validations_version"),
        UniqueConstraint("project_id", name="uq_mcp_builder_lab_validations_project"),
        UniqueConstraint(
            "security_review_id", name="uq_mcp_builder_lab_validations_security_review"
        ),
        UniqueConstraint(
            "operated_by",
            "idempotency_key",
            name="uq_mcp_builder_lab_validations_operator_idempotency",
        ),
    )

    lab_validation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    project_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    project_version: Mapped[int] = mapped_column(Integer, nullable=False)
    project_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    checkpoint_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    checkpoint_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    generation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    generation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    validation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    domain_review_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    domain_review_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    domain_reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    security_review_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    security_review_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    security_reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    operated_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    lab_profile: Mapped[str] = mapped_column(String(128), nullable=False)
    runner_contract_version: Mapped[str] = mapped_column(String(128), nullable=False)
    runtime_version: Mapped[str] = mapped_column(String(128), nullable=False)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    passed_count: Mapped[int] = mapped_column(Integer, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False)
    child_started: Mapped[bool] = mapped_column(Boolean, nullable=False)
    child_exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    output_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    output_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_file_count: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    workspace_removed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class McpBuilderCandidateHandoffModel(Base):
    __tablename__ = "mcp_builder_candidate_handoffs"
    __table_args__ = (
        CheckConstraint("version = 1", name="ck_mcp_builder_candidate_handoffs_version"),
        UniqueConstraint("project_id", name="uq_mcp_builder_candidate_handoffs_project"),
        UniqueConstraint(
            "lab_validation_id", name="uq_mcp_builder_candidate_handoffs_lab_validation"
        ),
        UniqueConstraint(
            "custodied_by",
            "idempotency_key",
            name="uq_mcp_builder_candidate_handoffs_custodian_idempotency",
        ),
    )

    handoff_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    project_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    project_version: Mapped[int] = mapped_column(Integer, nullable=False)
    project_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    checkpoint_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    checkpoint_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    generation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    generation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    validation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    domain_review_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    domain_review_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    domain_reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    security_review_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    security_review_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    security_reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    lab_validation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    lab_validation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    lab_operated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    custodied_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    handoff_profile: Mapped[str] = mapped_column(String(128), nullable=False)
    archive_contract_version: Mapped[str] = mapped_column(String(128), nullable=False)
    package_filename: Mapped[str] = mapped_column(String(132), nullable=False)
    package_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    package_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    package_entry_count: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_file_count: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    envelope_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    signature_state: Mapped[str] = mapped_column(String(32), nullable=False)
    capabilities: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    network_destinations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    unsupported_behavior: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    manual_change_count: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConnectorPackageAcquisitionModel(Base):
    __tablename__ = "connector_package_acquisitions"
    __table_args__ = (
        CheckConstraint("version = 1", name="ck_connector_package_acquisitions_version"),
        UniqueConstraint(
            "source_handoff_id", name="uq_connector_package_acquisitions_source_handoff"
        ),
        UniqueConstraint(
            "acquired_by",
            "idempotency_key",
            name="uq_connector_package_acquisitions_actor_idempotency",
        ),
    )

    acquisition_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_handoff_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_handoff_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_project_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_custodied_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_domain_reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_security_reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_lab_operated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    acquired_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    acquisition_profile: Mapped[str] = mapped_column(String(128), nullable=False)
    archive_contract_version: Mapped[str] = mapped_column(String(128), nullable=False)
    package_filename: Mapped[str] = mapped_column(String(132), nullable=False)
    package_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    package_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    publisher_identity: Mapped[str] = mapped_column(String(128), nullable=False)
    signature_state: Mapped[str] = mapped_column(String(32), nullable=False)
    attestation_state: Mapped[str] = mapped_column(String(32), nullable=False)
    capabilities: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConnectorPackageValidationModel(Base):
    __tablename__ = "connector_package_validations"
    __table_args__ = (
        CheckConstraint("version = 1", name="ck_connector_package_validations_version"),
        UniqueConstraint(
            "source_acquisition_id",
            name="uq_connector_package_validations_source_acquisition",
        ),
        UniqueConstraint(
            "validated_by",
            "idempotency_key",
            name="uq_connector_package_validations_actor_idempotency",
        ),
    )

    validation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    source_acquisition_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_acquisition_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_handoff_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_handoff_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_project_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_acquired_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_custodied_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_domain_reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_security_reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_lab_operated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    validated_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    validation_profile: Mapped[str] = mapped_column(String(128), nullable=False)
    validator_version: Mapped[str] = mapped_column(String(128), nullable=False)
    package_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    package_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    manifest_path: Mapped[str] = mapped_column(String(300), nullable=False)
    manifest_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    capability_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    schema_evidence: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    validated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConnectorPackageSupplyChainInventoryModel(Base):
    __tablename__ = "connector_package_supply_chain_inventories"
    __table_args__ = (
        CheckConstraint(
            "version = 1", name="ck_connector_package_supply_chain_inventories_version"
        ),
        UniqueConstraint(
            "source_validation_id",
            name="uq_connector_package_supply_chain_inventories_source_validation",
        ),
        UniqueConstraint(
            "inventoried_by",
            "idempotency_key",
            name="uq_connector_package_supply_chain_inventories_actor_idempotency",
        ),
    )

    inventory_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    source_validation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_validation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_acquisition_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_acquisition_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_handoff_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_project_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_acquired_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_validated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_custodied_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_domain_reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_security_reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_lab_operated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    inventoried_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    inventory_profile: Mapped[str] = mapped_column(String(128), nullable=False)
    inspector_version: Mapped[str] = mapped_column(String(128), nullable=False)
    package_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    package_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    files: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    dependencies: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    inventory_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    dependency_set_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    runtime_dependency_count: Mapped[int] = mapped_column(Integer, nullable=False)
    build_dependency_count: Mapped[int] = mapped_column(Integer, nullable=False)
    dependency_lock_present: Mapped[bool] = mapped_column(Boolean, nullable=False)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    inventoried_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConnectorPackageContentPolicyScanModel(Base):
    __tablename__ = "connector_package_content_policy_scans"
    __table_args__ = (
        CheckConstraint("version = 1", name="ck_connector_package_content_policy_scans_version"),
        UniqueConstraint(
            "source_inventory_id",
            name="uq_connector_package_content_policy_scans_source_inventory",
        ),
        UniqueConstraint(
            "scanned_by",
            "idempotency_key",
            name="uq_connector_package_content_policy_scans_actor_idempotency",
        ),
    )

    scan_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    source_inventory_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_inventory_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_validation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_validation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_acquisition_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_acquisition_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_handoff_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_project_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_acquired_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_validated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_inventoried_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_custodied_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_domain_reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_security_reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_lab_operated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    scanned_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    scan_profile: Mapped[str] = mapped_column(String(128), nullable=False)
    scanner_version: Mapped[str] = mapped_column(String(128), nullable=False)
    package_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    package_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    inventory_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    dependency_set_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    scanned_file_count: Mapped[int] = mapped_column(Integer, nullable=False)
    findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    finding_set_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    content_scan_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    promotion_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    scanned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConnectorPackageSchemaSemanticsValidationModel(Base):
    __tablename__ = "connector_package_schema_semantics_validations"
    __table_args__ = (
        CheckConstraint(
            "version = 1", name="ck_connector_package_schema_semantics_validations_version"
        ),
        UniqueConstraint(
            "source_content_policy_scan_id",
            name="uq_connector_package_schema_semantics_validations_source_scan",
        ),
        UniqueConstraint(
            "validated_by",
            "idempotency_key",
            name="uq_pkg_schema_sem_actor_idem",
        ),
    )

    validation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    source_content_policy_scan_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    source_content_policy_scan_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_inventory_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_inventory_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_validation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_validation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_acquisition_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_acquisition_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_handoff_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_project_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_acquired_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_manifest_validated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_inventoried_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_content_scanned_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_custodied_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_domain_reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_security_reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_lab_operated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    validated_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    validation_profile: Mapped[str] = mapped_column(String(128), nullable=False)
    validator_version: Mapped[str] = mapped_column(String(128), nullable=False)
    package_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    package_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    inventory_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    content_scan_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    schemas: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    schema_set_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    finding_set_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    semantic_validation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    promotion_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    validated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConnectorPackageAuthorityBehaviorValidationModel(Base):
    __tablename__ = "connector_package_authority_behavior_validations"
    __table_args__ = (
        CheckConstraint(
            "version = 1", name="ck_connector_package_authority_behavior_validations_version"
        ),
        UniqueConstraint(
            "source_schema_semantics_validation_id",
            name="uq_connector_package_authority_behavior_validations_source",
        ),
        UniqueConstraint(
            "validated_by",
            "idempotency_key",
            name="uq_pkg_auth_behavior_actor_idem",
        ),
    )

    validation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    source_schema_semantics_validation_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    source_schema_semantics_validation_digest: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    source_content_policy_scan_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    source_inventory_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_validation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_acquisition_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_handoff_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_project_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_acquired_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_manifest_validated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_inventoried_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_content_scanned_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_schema_validated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_custodied_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_domain_reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_security_reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_lab_operated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    validated_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    validation_profile: Mapped[str] = mapped_column(String(128), nullable=False)
    analyzer_version: Mapped[str] = mapped_column(String(128), nullable=False)
    package_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    package_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    inventory_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    semantic_validation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    capabilities: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    capability_set_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    finding_set_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    behavior_validation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    promotion_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    validated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConnectorPackageStaticDependencyAnalysisModel(Base):
    __tablename__ = "connector_package_static_dependency_analyses"
    __table_args__ = (
        CheckConstraint(
            "version = 1", name="ck_connector_package_static_dependency_analyses_version"
        ),
        UniqueConstraint(
            "source_authority_behavior_validation_id",
            name="uq_connector_package_static_dependency_analyses_source",
        ),
        UniqueConstraint(
            "analyzed_by",
            "idempotency_key",
            name="uq_pkg_static_dep_actor_idem",
        ),
    )

    analysis_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    source_authority_behavior_validation_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    source_authority_behavior_validation_digest: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    source_schema_semantics_validation_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    source_content_policy_scan_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    source_inventory_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_validation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_acquisition_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_handoff_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_project_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_acquired_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_manifest_validated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_inventoried_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_content_scanned_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_schema_validated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_authority_validated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_custodied_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_domain_reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_security_reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_lab_operated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    analyzed_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    analysis_profile: Mapped[str] = mapped_column(String(128), nullable=False)
    analyzer_version: Mapped[str] = mapped_column(String(128), nullable=False)
    package_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    package_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    inventory_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    dependency_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    finding_set_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    analysis_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    promotion_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConnectorPackageVulnerabilityAnalysisModel(Base):
    __tablename__ = "connector_package_vulnerability_analyses"
    __table_args__ = (
        CheckConstraint("version = 1", name="ck_connector_package_vulnerability_analyses_version"),
        UniqueConstraint(
            "source_static_dependency_analysis_id",
            name="uq_connector_package_vulnerability_analyses_source",
        ),
        UniqueConstraint(
            "analyzed_by",
            "idempotency_key",
            name="uq_connector_package_vulnerability_analyses_actor_idempotency",
        ),
    )

    analysis_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    source_static_dependency_analysis_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    source_static_dependency_analysis_digest: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    source_authority_behavior_validation_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    source_schema_semantics_validation_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    source_content_policy_scan_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    source_inventory_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_validation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_acquisition_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_handoff_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_project_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_acquired_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_manifest_validated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_inventoried_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_content_scanned_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_schema_validated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_authority_validated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_static_analyzed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_custodied_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_domain_reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_security_reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_lab_operated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    analyzed_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    analysis_profile: Mapped[str] = mapped_column(String(128), nullable=False)
    analyzer_version: Mapped[str] = mapped_column(String(128), nullable=False)
    package_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    package_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    inventory_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    advisory_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    subject_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    finding_set_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    analysis_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    promotion_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConnectorPackageMalwareAnalysisModel(Base):
    __tablename__ = "connector_package_malware_analyses"
    __table_args__ = (
        CheckConstraint("version = 1", name="ck_connector_package_malware_analyses_version"),
        UniqueConstraint(
            "source_vulnerability_analysis_id",
            name="uq_connector_package_malware_analyses_source",
        ),
        UniqueConstraint(
            "analyzed_by",
            "idempotency_key",
            name="uq_connector_package_malware_analyses_actor_idempotency",
        ),
    )

    analysis_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    source_vulnerability_analysis_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    source_vulnerability_analysis_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_static_dependency_analysis_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    source_static_dependency_analysis_digest: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    source_authority_behavior_validation_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    source_schema_semantics_validation_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    source_content_policy_scan_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    source_inventory_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_validation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_acquisition_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_handoff_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_project_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_acquired_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_manifest_validated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_inventoried_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_content_scanned_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_schema_validated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_authority_validated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_static_analyzed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_vulnerability_analyzed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_custodied_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_domain_reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_security_reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_lab_operated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    analyzed_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    analysis_profile: Mapped[str] = mapped_column(String(128), nullable=False)
    scanner_version: Mapped[str] = mapped_column(String(128), nullable=False)
    package_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    package_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    inventory_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    definition_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    subject_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    finding_set_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    analysis_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    promotion_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConnectorPackageLicenseAnalysisModel(Base):
    __tablename__ = "connector_package_license_analyses"
    __table_args__ = (
        CheckConstraint("version = 1", name="ck_connector_package_license_analyses_version"),
        UniqueConstraint(
            "source_malware_analysis_id",
            name="uq_connector_package_license_analyses_source",
        ),
        UniqueConstraint(
            "analyzed_by",
            "idempotency_key",
            name="uq_connector_package_license_analyses_actor_idempotency",
        ),
    )

    analysis_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    source_malware_analysis_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_malware_analysis_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_vulnerability_analysis_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    source_vulnerability_analysis_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_static_dependency_analysis_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    source_static_dependency_analysis_digest: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    source_authority_behavior_validation_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    source_schema_semantics_validation_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    source_content_policy_scan_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    source_inventory_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_validation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_acquisition_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_handoff_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_project_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_acquired_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_manifest_validated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_inventoried_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_content_scanned_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_schema_validated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_authority_validated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_static_analyzed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_vulnerability_analyzed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_malware_analyzed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_custodied_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_domain_reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_security_reviewed_by: Mapped[str] = mapped_column(String(128), nullable=False)
    source_lab_operated_by: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    analyzed_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    analysis_profile: Mapped[str] = mapped_column(String(128), nullable=False)
    analyzer_version: Mapped[str] = mapped_column(String(128), nullable=False)
    package_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    package_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    inventory_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    dependency_set_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    subject_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    finding_set_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    analysis_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    promotion_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConnectorPackageContractValidationModel(Base):
    __tablename__ = "connector_package_contract_validations"
    __table_args__ = (
        UniqueConstraint(
            "source_license_analysis_id",
            name="uq_connector_package_contract_validations_source",
        ),
        UniqueConstraint(
            "validated_by",
            "idempotency_key",
            name="uq_connector_package_contract_validations_actor_idempotency",
        ),
    )

    validation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_license_analysis_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    validated_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorPackageRunnerValidationModel(Base):
    __tablename__ = "connector_package_runner_validations"
    __table_args__ = (
        UniqueConstraint(
            "source_contract_validation_id",
            name="uq_connector_package_runner_validations_source",
        ),
        UniqueConstraint(
            "validated_by",
            "idempotency_key",
            name="uq_connector_package_runner_validations_actor_idempotency",
        ),
    )

    validation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_contract_validation_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    validated_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorPackageLabSelfTestModel(Base):
    __tablename__ = "connector_package_lab_self_tests"
    __table_args__ = (
        UniqueConstraint(
            "source_runner_validation_id",
            name="uq_connector_package_lab_self_tests_source",
        ),
        UniqueConstraint(
            "validated_by",
            "idempotency_key",
            name="uq_connector_package_lab_self_tests_actor_idempotency",
        ),
    )

    self_test_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_runner_validation_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    validated_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorPackageFinalValidationModel(Base):
    __tablename__ = "connector_package_final_validations"
    __table_args__ = (
        UniqueConstraint(
            "source_lab_self_test_id",
            name="uq_connector_package_final_validations_source",
        ),
        UniqueConstraint(
            "validated_by",
            "idempotency_key",
            name="uq_connector_package_final_validations_actor_idempotency",
        ),
    )

    validation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_lab_self_test_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    validated_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorPackageApprovalRequestModel(Base):
    __tablename__ = "connector_package_approval_requests"
    __table_args__ = (
        UniqueConstraint(
            "source_final_validation_id",
            name="uq_connector_package_approval_requests_source",
        ),
        UniqueConstraint(
            "requested_by",
            "idempotency_key",
            name="uq_connector_package_approval_requests_actor_idempotency",
        ),
    )

    request_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_final_validation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    requested_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorPackageApprovalDecisionModel(Base):
    __tablename__ = "connector_package_approval_decisions"
    __table_args__ = (
        UniqueConstraint(
            "request_id",
            name="uq_connector_package_approval_decisions_request",
        ),
        UniqueConstraint(
            "decided_by",
            "idempotency_key",
            name="uq_connector_package_approval_decisions_actor_idempotency",
        ),
    )

    decision_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    decided_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorPublisherAttestationModel(Base):
    __tablename__ = "connector_publisher_attestations"
    __table_args__ = (
        UniqueConstraint(
            "source_approval_request_id",
            name="uq_connector_publisher_attestations_approval",
        ),
        UniqueConstraint(
            "verified_by",
            "idempotency_key",
            name="uq_connector_publisher_attestations_actor_idempotency",
        ),
    )

    report_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_approval_request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    verified_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorPackageSigningReceiptModel(Base):
    __tablename__ = "connector_package_signing_receipts"
    __table_args__ = (
        UniqueConstraint(
            "source_attestation_report_id",
            name="uq_connector_package_signing_receipts_attestation",
        ),
        UniqueConstraint(
            "requested_by",
            "idempotency_key",
            name="uq_connector_package_signing_receipts_actor_idempotency",
        ),
    )

    receipt_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_attestation_report_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    requested_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorRegistryPublicationReceiptModel(Base):
    __tablename__ = "connector_registry_publication_receipts"
    __table_args__ = (
        UniqueConstraint(
            "source_signing_receipt_id",
            name="uq_connector_registry_publication_receipts_signing",
        ),
        UniqueConstraint(
            "requested_by",
            "idempotency_key",
            name="uq_connector_registry_publication_receipts_actor_idempotency",
        ),
    )

    receipt_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_signing_receipt_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    requested_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorPackageRegistrationRecordModel(Base):
    __tablename__ = "connector_package_registration_records"
    __table_args__ = (
        UniqueConstraint(
            "source_publication_receipt_id",
            name="uq_connector_package_registration_records_publication",
        ),
        UniqueConstraint(
            "connector_id",
            "release_version",
            name="uq_connector_package_registration_records_release",
        ),
        UniqueConstraint(
            "registered_by",
            "idempotency_key",
            name="uq_connector_package_registration_records_actor_idempotency",
        ),
    )

    record_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_publication_receipt_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    connector_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    release_version: Mapped[str] = mapped_column(String(128), nullable=False)
    registered_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorPackageInstallationReceiptModel(Base):
    __tablename__ = "connector_package_installation_receipts"
    __table_args__ = (
        UniqueConstraint(
            "source_registration_record_id",
            name="uq_connector_package_installation_receipts_registration",
        ),
        UniqueConstraint(
            "connector_id",
            "release_version",
            name="uq_connector_package_installation_receipts_release",
        ),
        UniqueConstraint(
            "installed_by",
            "idempotency_key",
            name="uq_connector_package_installation_receipts_actor_idempotency",
        ),
    )

    receipt_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_registration_record_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    connector_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    release_version: Mapped[str] = mapped_column(String(128), nullable=False)
    installation_store_profile_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    installed_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorInstanceRecordModel(Base):
    __tablename__ = "connector_instance_records"
    __table_args__ = (
        UniqueConstraint("instance_id", name="uq_connector_instance_records_instance"),
        UniqueConstraint(
            "organization_id",
            "environment_id",
            "instance_key",
            name="uq_connector_instance_records_scope_key",
        ),
        UniqueConstraint(
            "created_by",
            "idempotency_key",
            name="uq_connector_instance_records_actor_idempotency",
        ),
    )

    record_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    instance_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    instance_key: Mapped[str] = mapped_column(String(128), nullable=False)
    source_installation_receipt_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    connector_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    release_version: Mapped[str] = mapped_column(String(128), nullable=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    instance_state: Mapped[str] = mapped_column(
        String(32), nullable=False, default="disabled_unconfigured", index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    retired_by: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    retirement_idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorTargetConfigurationBindingModel(Base):
    __tablename__ = "connector_target_configuration_bindings"
    __table_args__ = (
        UniqueConstraint(
            "source_instance_record_id",
            name="uq_connector_target_configuration_bindings_instance",
        ),
        UniqueConstraint(
            "bound_by",
            "idempotency_key",
            name="uq_connector_target_configuration_bindings_actor_idempotency",
        ),
    )

    binding_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_instance_record_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    instance_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_profile_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    bound_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorUpgradeApprovalRequestModel(Base):
    __tablename__ = "connector_upgrade_approval_requests"
    __table_args__ = (
        UniqueConstraint("plan_digest", name="uq_connector_upgrade_approval_requests_plan"),
        UniqueConstraint(
            "requested_by",
            "idempotency_key",
            name="uq_connector_upgrade_approval_requests_actor_idempotency",
        ),
    )

    request_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_record_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    instance_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    connector_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    plan_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_receipt_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    requested_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorUpgradeApprovalDecisionModel(Base):
    __tablename__ = "connector_upgrade_approval_decisions"
    __table_args__ = (
        UniqueConstraint(
            "request_id",
            name="uq_connector_upgrade_approval_decisions_request",
        ),
        UniqueConstraint(
            "decided_by",
            "idempotency_key",
            name="uq_connector_upgrade_approval_decisions_actor_idempotency",
        ),
    )

    decision_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    decided_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorUpgradeApprovalRevalidationModel(Base):
    __tablename__ = "connector_upgrade_approval_revalidations"
    __table_args__ = (
        UniqueConstraint(
            "revalidated_by",
            "idempotency_key",
            name="uq_connector_upgrade_approval_revalidations_actor_idempotency",
        ),
    )

    revalidation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    decision_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    revalidated_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    revalidated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorUpgradeChangeContextDraftModel(Base):
    __tablename__ = "connector_upgrade_change_context_drafts"
    __table_args__ = (
        UniqueConstraint(
            "created_by",
            "idempotency_key",
            name="uq_connector_upgrade_change_context_drafts_actor_idempotency",
        ),
    )

    draft_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    revalidation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    readiness_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorUpgradeSigningProviderConformanceModel(Base):
    __tablename__ = "connector_upgrade_signing_provider_conformance_assessments"
    __table_args__ = (
        UniqueConstraint(
            "assessed_by",
            "idempotency_key",
            name="uq_connector_upgrade_signing_conformance_actor_idem",
        ),
    )

    assessment_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    assessed_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    provider_class: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorCredentialAssignmentModel(Base):
    __tablename__ = "connector_credential_assignments"
    __table_args__ = (
        UniqueConstraint(
            "source_target_binding_id",
            name="uq_connector_credential_assignments_target_binding",
        ),
        UniqueConstraint(
            "assigned_by",
            "idempotency_key",
            name="uq_connector_credential_assignments_actor_idempotency",
        ),
    )

    assignment_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_target_binding_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    instance_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    credential_profile_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    assigned_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorConfigurationValidationModel(Base):
    __tablename__ = "connector_configuration_validations"
    __table_args__ = (
        UniqueConstraint(
            "source_assignment_id",
            name="uq_connector_configuration_validations_assignment",
        ),
        UniqueConstraint(
            "validated_by",
            "idempotency_key",
            name="uq_connector_configuration_validations_actor_idempotency",
        ),
    )

    validation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_assignment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    instance_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    evidence_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    validated_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorCapabilityEnablementModel(Base):
    __tablename__ = "connector_capability_enablements"
    __table_args__ = (
        UniqueConstraint(
            "source_validation_id",
            name="uq_connector_capability_enablements_validation",
        ),
        UniqueConstraint(
            "enabled_by",
            "idempotency_key",
            name="uq_connector_capability_enablements_actor_idempotency",
        ),
    )

    enablement_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_validation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    instance_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    capability_profile_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    enabled_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorRuntimeTrustGrantModel(Base):
    __tablename__ = "connector_runtime_trust_grants"
    __table_args__ = (
        UniqueConstraint(
            "source_enablement_id",
            name="uq_connector_runtime_trust_grants_enablement",
        ),
        UniqueConstraint(
            "granted_by",
            "idempotency_key",
            name="uq_connector_runtime_trust_grants_actor_idempotency",
        ),
    )

    grant_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_enablement_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    instance_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    runtime_profile_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    granted_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorSecretBrokerageAuthorizationModel(Base):
    __tablename__ = "connector_secret_brokerage_authorizations"
    __table_args__ = (
        UniqueConstraint(
            "source_runtime_trust_grant_id",
            name="uq_connector_secret_brokerage_authorizations_runtime_trust",
        ),
        UniqueConstraint(
            "authorized_by",
            "idempotency_key",
            name="uq_connector_secret_brokerage_authorizations_actor_idempotency",
        ),
    )

    authorization_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_runtime_trust_grant_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    instance_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    brokerage_profile_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    authorized_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


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


class ItsmHandoffHumanReviewModel(Base):
    __tablename__ = "report_itsm_handoff_human_reviews"
    __table_args__ = (
        CheckConstraint("version = 1", name="ck_report_itsm_handoff_reviews_version"),
        UniqueConstraint("handoff_draft_id", name="uq_report_itsm_handoff_reviews_handoff"),
        UniqueConstraint(
            "reviewer_id",
            "idempotency_key",
            name="uq_report_itsm_handoff_reviews_reviewer_idempotency",
        ),
    )

    review_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    report_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    report_version: Mapped[int] = mapped_column(Integer, nullable=False)
    report_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    handoff_draft_id: Mapped[str] = mapped_column(String(128), nullable=False)
    handoff_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    handoff_idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    incident_reference: Mapped[str] = mapped_column(String(80), nullable=False)
    operation: Mapped[str] = mapped_column(String(128), nullable=False)
    requester_id: Mapped[str] = mapped_column(String(128), nullable=False)
    reviewer_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    reviewer_role_id: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False)
    rationale: Mapped[str] = mapped_column(String(1000), nullable=False)
    acknowledged_review_only: Mapped[bool] = mapped_column(Boolean, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TechnicalReportModel(Base):
    __tablename__ = "technical_reports"
    __table_args__ = (
        UniqueConstraint("request_fingerprint", name="uq_technical_reports_request"),
        UniqueConstraint(
            "lineage_fingerprint",
            "version",
            name="uq_technical_reports_lineage_version",
        ),
    )

    report_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    lineage_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    prior_version_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    requested_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorRuntimeActivationModel(Base):
    __tablename__ = "connector_runtime_activations"
    __table_args__ = (
        UniqueConstraint(
            "source_brokerage_authorization_id",
            name="uq_connector_runtime_activations_brokerage_authorization",
        ),
        UniqueConstraint(
            "activated_by",
            "idempotency_key",
            name="uq_connector_runtime_activations_actor_idempotency",
        ),
    )

    activation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_brokerage_authorization_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    instance_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    activation_profile_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    activated_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorTargetSessionVerificationModel(Base):
    __tablename__ = "connector_target_session_verifications"
    __table_args__ = (
        UniqueConstraint(
            "source_runtime_activation_id",
            name="uq_connector_target_sessions_runtime_activation",
        ),
        UniqueConstraint(
            "verified_by",
            "idempotency_key",
            name="uq_connector_target_sessions_actor_idempotency",
        ),
    )

    verification_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_runtime_activation_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    instance_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    session_profile_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    verified_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorInvocationAuthorizationModel(Base):
    __tablename__ = "connector_invocation_authorizations"
    __table_args__ = (
        UniqueConstraint(
            "source_target_session_verification_id",
            name="uq_connector_invocation_authorizations_target_session",
        ),
        UniqueConstraint(
            "authorized_by",
            "idempotency_key",
            name="uq_connector_invocation_authorizations_actor_idempotency",
        ),
    )

    authorization_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_target_session_verification_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    instance_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    capability_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    authorized_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorInvocationConsumptionClaimModel(Base):
    __tablename__ = "connector_invocation_consumption_claims"
    __table_args__ = (
        UniqueConstraint(
            "source_authorization_id",
            name="uq_connector_invocation_claims_authorization",
        ),
        UniqueConstraint(
            "claimed_by",
            "idempotency_digest",
            name="uq_connector_invocation_claims_actor_idempotency",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_authorization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    invocation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorBoundedInvocationModel(Base):
    __tablename__ = "connector_bounded_invocations"
    __table_args__ = (
        UniqueConstraint(
            "source_authorization_id",
            name="uq_connector_bounded_invocations_authorization",
        ),
        UniqueConstraint(
            "consumption_claim_id",
            name="uq_connector_bounded_invocations_claim",
        ),
    )

    invocation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    consumption_claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_authorization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    instance_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    capability_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    invoked_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorInvocationEvidenceClaimModel(Base):
    __tablename__ = "connector_invocation_evidence_claims"
    __table_args__ = (
        UniqueConstraint(
            "source_invocation_id",
            name="uq_connector_invocation_evidence_claims_source",
        ),
        UniqueConstraint(
            "claimed_by",
            "idempotency_digest",
            name="uq_connector_invocation_evidence_claims_actor_idempotency",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_invocation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    ingestion_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ConnectorInvocationEvidenceModel(Base):
    __tablename__ = "connector_invocation_evidence_ingestions"
    __table_args__ = (
        UniqueConstraint(
            "source_invocation_id",
            name="uq_connector_invocation_evidence_source",
        ),
        UniqueConstraint(
            "claim_id",
            name="uq_connector_invocation_evidence_claim",
        ),
    )

    ingestion_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_invocation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    instance_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    capability_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    evidence_package_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    ingested_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalEvidenceKnowledgeDraftClaimModel(Base):
    __tablename__ = "operational_evidence_knowledge_draft_claims"
    __table_args__ = (
        UniqueConstraint(
            "source_ingestion_id",
            name="uq_operational_evidence_knowledge_draft_claims_source",
        ),
        UniqueConstraint(
            "claimed_by",
            "idempotency_digest",
            name="uq_ok_draft_claim_actor_idem",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_ingestion_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    draft_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalEvidenceKnowledgeDraftModel(Base):
    __tablename__ = "operational_evidence_knowledge_drafts"
    __table_args__ = (
        UniqueConstraint(
            "source_ingestion_id",
            name="uq_operational_evidence_knowledge_drafts_source",
        ),
        UniqueConstraint(
            "claim_id",
            name="uq_operational_evidence_knowledge_drafts_claim",
        ),
    )

    draft_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_ingestion_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    instance_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    capability_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    evidence_package_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    curated_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeReviewRequestClaimModel(Base):
    __tablename__ = "operational_knowledge_review_request_claims"
    __table_args__ = (
        UniqueConstraint(
            "source_draft_id",
            name="uq_operational_knowledge_review_request_claims_source",
        ),
        UniqueConstraint(
            "claimed_by",
            "idempotency_digest",
            name="uq_ok_review_req_claim_actor_idem",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_draft_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    review_request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeReviewRequestModel(Base):
    __tablename__ = "operational_knowledge_review_requests"
    __table_args__ = (
        UniqueConstraint(
            "source_draft_id",
            name="uq_operational_knowledge_review_requests_source",
        ),
        UniqueConstraint(
            "claim_id",
            name="uq_operational_knowledge_review_requests_claim",
        ),
    )

    review_request_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_draft_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    knowledge_item_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    requested_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeReviewerAssignmentClaimModel(Base):
    __tablename__ = "operational_knowledge_reviewer_assignment_claims"
    __table_args__ = (
        UniqueConstraint(
            "source_review_request_id",
            name="uq_operational_knowledge_reviewer_assignment_claims_source",
        ),
        UniqueConstraint(
            "claimed_by",
            "idempotency_digest",
            name="uq_ok_assign_claim_actor_idem",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_review_request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    assignment_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeReviewerAssignmentModel(Base):
    __tablename__ = "operational_knowledge_reviewer_assignments"
    __table_args__ = (
        UniqueConstraint(
            "source_review_request_id",
            name="uq_operational_knowledge_reviewer_assignments_source",
        ),
        UniqueConstraint(
            "claim_id",
            name="uq_operational_knowledge_reviewer_assignments_claim",
        ),
    )

    assignment_set_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_review_request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    knowledge_item_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    requested_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeProtectedInspectionClaimModel(Base):
    __tablename__ = "operational_knowledge_protected_inspection_claims"
    __table_args__ = (
        UniqueConstraint(
            "source_assignment_set_id",
            "track_code",
            name="uq_ok_inspect_claim_source_track",
        ),
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_ok_inspect_claim_actor_idem",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_assignment_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    track_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    lease_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeProtectedInspectionModel(Base):
    __tablename__ = "operational_knowledge_protected_inspection_leases"
    __table_args__ = (
        UniqueConstraint(
            "source_assignment_set_id",
            "track_code",
            name="uq_ok_inspect_lease_source_track",
        ),
        UniqueConstraint(
            "claim_id",
            name="uq_operational_knowledge_protected_inspection_leases_claim",
        ),
    )

    lease_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_assignment_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    track_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    knowledge_item_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    lease_holder_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeProtectedContentClaimModel(Base):
    __tablename__ = "operational_knowledge_protected_content_claims"
    __table_args__ = (
        UniqueConstraint(
            "source_lease_id",
            name="uq_operational_knowledge_protected_content_claims_source_lease",
        ),
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_ok_content_claim_actor_idem",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_lease_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    presentation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeProtectedContentModel(Base):
    __tablename__ = "operational_knowledge_protected_content_presentations"
    __table_args__ = (
        UniqueConstraint(
            "source_lease_id",
            name="uq_ok_content_present_source_lease",
        ),
        UniqueConstraint(
            "claim_id",
            name="uq_operational_knowledge_protected_content_presentations_claim",
        ),
    )

    presentation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_lease_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_assignment_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    track_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    knowledge_item_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    lease_holder_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    presented_content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    content_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeReviewFindingClaimModel(Base):
    __tablename__ = "operational_knowledge_review_finding_claims"
    __table_args__ = (
        UniqueConstraint(
            "source_presentation_id",
            name="uq_ok_finding_claim_source_present",
        ),
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_ok_finding_claim_actor_idem",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_presentation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    finding_packet_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    track_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeReviewFindingModel(Base):
    __tablename__ = "operational_knowledge_review_findings"
    __table_args__ = (
        UniqueConstraint(
            "source_presentation_id",
            name="uq_operational_knowledge_review_findings_source_presentation",
        ),
        UniqueConstraint(
            "claim_id",
            name="uq_operational_knowledge_review_findings_claim",
        ),
    )

    finding_packet_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_lease_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_presentation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_assignment_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    track_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    knowledge_item_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    lease_holder_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    finding_content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    finding_count: Mapped[int] = mapped_column(Integer, nullable=False)
    finding_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeFindingPresentationClaimModel(Base):
    __tablename__ = "operational_knowledge_finding_presentation_claims"
    __table_args__ = (
        UniqueConstraint(
            "source_finding_packet_id",
            name="uq_ok_finding_present_claim_source",
        ),
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_ok_finding_present_claim_actor_idem",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_finding_packet_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    finding_presentation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    track_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeFindingPresentationModel(Base):
    __tablename__ = "operational_knowledge_finding_presentations"
    __table_args__ = (
        UniqueConstraint(
            "source_finding_packet_id",
            name="uq_operational_knowledge_finding_presentations_source_finding",
        ),
        UniqueConstraint(
            "claim_id",
            name="uq_operational_knowledge_finding_presentations_claim",
        ),
    )

    finding_presentation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_finding_packet_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_lease_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_content_presentation_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    source_assignment_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    track_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    knowledge_item_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    lease_holder_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    finding_content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    finding_count: Mapped[int] = mapped_column(Integer, nullable=False)
    finding_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeTrackReviewDecisionClaimModel(Base):
    __tablename__ = "operational_knowledge_track_review_decision_claims"
    __table_args__ = (
        UniqueConstraint(
            "source_finding_presentation_id",
            name="uq_ok_trd_claim_source_present",
        ),
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_ok_trd_claim_actor_idem",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_finding_presentation_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    decision_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    track_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    disposition_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeTrackReviewDecisionModel(Base):
    __tablename__ = "operational_knowledge_track_review_decisions"
    __table_args__ = (
        UniqueConstraint(
            "source_finding_presentation_id",
            name="uq_ok_trd_source_present",
        ),
        UniqueConstraint(
            "claim_id",
            name="uq_ok_trd_claim",
        ),
    )

    decision_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_finding_presentation_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    source_lease_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_assignment_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    review_request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    track_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    disposition_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    knowledge_item_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    decided_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeCorrectionClaimModel(Base):
    __tablename__ = "operational_knowledge_correction_claims"
    __table_args__ = (
        UniqueConstraint(
            "source_review_request_id",
            name="uq_ok_correction_claim_source_request",
        ),
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_ok_correction_claim_actor_idem",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_review_request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    correction_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeCorrectionModel(Base):
    __tablename__ = "operational_knowledge_corrections"
    __table_args__ = (
        UniqueConstraint(
            "source_review_request_id",
            name="uq_ok_correction_source_request",
        ),
        UniqueConstraint("claim_id", name="uq_ok_correction_claim"),
        UniqueConstraint("new_draft_id", name="uq_ok_correction_new_draft"),
        UniqueConstraint("new_review_request_id", name="uq_ok_correction_new_request"),
    )

    correction_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_review_request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_draft_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    knowledge_item_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    new_draft_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    new_review_request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    corrected_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeFinalResolutionClaimModel(Base):
    __tablename__ = "operational_knowledge_final_resolution_claims"
    __table_args__ = (
        UniqueConstraint("review_request_id", name="uq_ok_final_claim_request"),
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_ok_final_claim_actor_idem",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    review_request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resolution_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeFinalResolutionModel(Base):
    __tablename__ = "operational_knowledge_final_resolutions"
    __table_args__ = (
        UniqueConstraint("review_request_id", name="uq_ok_final_request"),
        UniqueConstraint("claim_id", name="uq_ok_final_claim"),
    )

    resolution_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    review_request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_draft_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    knowledge_item_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    disposition_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    approved_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgePublicationPreparationClaimModel(Base):
    __tablename__ = "operational_knowledge_publication_preparation_claims"
    __table_args__ = (
        UniqueConstraint("resolution_id", name="uq_ok_pub_prep_claim_resolution"),
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_ok_pub_prep_claim_actor_idem",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    resolution_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    preparation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgePublicationPreparationModel(Base):
    __tablename__ = "operational_knowledge_publication_preparations"
    __table_args__ = (
        UniqueConstraint("resolution_id", name="uq_ok_pub_prep_resolution"),
        UniqueConstraint("claim_id", name="uq_ok_pub_prep_claim"),
    )

    preparation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resolution_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    review_request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_draft_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    knowledge_item_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    prepared_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeSourceMaterializationClaimModel(Base):
    __tablename__ = "operational_knowledge_source_materialization_claims"
    __table_args__ = (
        UniqueConstraint("preparation_id", name="uq_ok_source_mat_claim_preparation"),
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_ok_source_mat_claim_actor_idem",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    preparation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    materialization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeSourceMaterializationModel(Base):
    __tablename__ = "operational_knowledge_source_materializations"
    __table_args__ = (
        UniqueConstraint("preparation_id", name="uq_ok_source_mat_preparation"),
        UniqueConstraint("claim_id", name="uq_ok_source_mat_claim"),
    )

    materialization_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    preparation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resolution_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_draft_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    knowledge_item_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    materialized_by_subject_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeChunkingClaimModel(Base):
    __tablename__ = "operational_knowledge_chunking_claims"
    __table_args__ = (
        UniqueConstraint("materialization_id", name="uq_ok_chunk_claim_materialization"),
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_ok_chunk_claim_actor_idem",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    materialization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    chunk_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeChunkSetModel(Base):
    __tablename__ = "operational_knowledge_chunk_sets"
    __table_args__ = (
        UniqueConstraint("materialization_id", name="uq_ok_chunk_set_materialization"),
        UniqueConstraint("claim_id", name="uq_ok_chunk_set_claim"),
    )

    chunk_set_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    materialization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    preparation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resolution_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_draft_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    knowledge_item_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    chunked_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeEmbeddingClaimModel(Base):
    __tablename__ = "operational_knowledge_embedding_claims"
    __table_args__ = (
        UniqueConstraint("chunk_set_id", name="uq_ok_embed_claim_chunk_set"),
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_ok_embed_claim_actor_idem",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    chunk_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    embedding_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeEmbeddingSetModel(Base):
    __tablename__ = "operational_knowledge_embedding_sets"
    __table_args__ = (
        UniqueConstraint("chunk_set_id", name="uq_ok_embed_set_chunk_set"),
        UniqueConstraint("claim_id", name="uq_ok_embed_set_claim"),
    )

    embedding_set_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    chunk_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    materialization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    preparation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    knowledge_item_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    embedded_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeIndexClaimModel(Base):
    __tablename__ = "operational_knowledge_index_claims"
    __table_args__ = (
        UniqueConstraint("embedding_set_id", name="uq_ok_index_claim_embedding"),
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_ok_index_claim_actor_idem",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    embedding_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    index_staging_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeIndexStagingModel(Base):
    __tablename__ = "operational_knowledge_index_stagings"
    __table_args__ = (
        UniqueConstraint("embedding_set_id", name="uq_ok_index_staging_embedding"),
        UniqueConstraint("claim_id", name="uq_ok_index_staging_claim"),
    )

    index_staging_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    embedding_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    chunk_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    knowledge_item_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    index_steward_subject_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeRetrievalPublicationClaimModel(Base):
    __tablename__ = "operational_knowledge_retrieval_publication_claims"
    __table_args__ = (
        UniqueConstraint("index_staging_id", name="uq_ok_retrieval_pub_claim_staging"),
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_ok_retrieval_pub_claim_actor_idem",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    index_staging_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    publication_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeRetrievalPublicationModel(Base):
    __tablename__ = "operational_knowledge_retrieval_publications"
    __table_args__ = (
        UniqueConstraint("index_staging_id", name="uq_ok_retrieval_pub_staging"),
        UniqueConstraint("claim_id", name="uq_ok_retrieval_pub_claim"),
    )

    publication_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    index_staging_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    knowledge_item_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    publication_steward_subject_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeRetrievalClaimModel(Base):
    __tablename__ = "operational_knowledge_retrieval_claims"
    __table_args__ = (
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_ok_retrieval_claim_actor_idem",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    retrieval_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    publication_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalKnowledgeRetrievalModel(Base):
    __tablename__ = "operational_knowledge_retrievals"
    __table_args__ = (
        UniqueConstraint("claim_id", name="uq_ok_retrieval_claim"),
        UniqueConstraint("protected_artifact_reference", name="uq_ok_retrieval_artifact"),
    )

    retrieval_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    publication_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    knowledge_item_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    consumer_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    protected_artifact_reference: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ProtectedModelContextClaimModel(Base):
    __tablename__ = "protected_model_context_claims"
    __table_args__ = (
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_protected_model_context_claim_actor_idem",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    context_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    retrieval_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ProtectedModelContextModel(Base):
    __tablename__ = "protected_model_contexts"
    __table_args__ = (
        UniqueConstraint("claim_id", name="uq_protected_model_context_claim"),
        UniqueConstraint(
            "protected_artifact_reference", name="uq_protected_model_context_artifact"
        ),
    )

    context_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    retrieval_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    publication_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    consumer_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    protected_artifact_reference: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ProtectedModelInvocationClaimModel(Base):
    __tablename__ = "protected_model_invocation_claims"
    __table_args__ = (
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_protected_model_invocation_claim_actor_idem",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    invocation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    context_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ProtectedModelInvocationModel(Base):
    __tablename__ = "protected_model_invocations"
    __table_args__ = (
        UniqueConstraint("claim_id", name="uq_protected_model_invocation_claim"),
        UniqueConstraint("protected_draft_reference", name="uq_protected_model_invocation_draft"),
    )

    invocation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    context_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    consumer_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    protected_draft_reference: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ProtectedDraftAdjudicationClaimModel(Base):
    __tablename__ = "protected_draft_adjudication_claims"
    __table_args__ = (
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_protected_draft_adjudication_claim_actor_idem",
        ),
    )
    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    adjudication_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    invocation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ProtectedDraftAdjudicationModel(Base):
    __tablename__ = "protected_draft_adjudications"
    __table_args__ = (
        UniqueConstraint("claim_id", name="uq_protected_draft_adjudication_claim"),
        UniqueConstraint(
            "protected_report_reference", name="uq_protected_draft_adjudication_report"
        ),
    )
    adjudication_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    invocation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    consumer_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    protected_report_reference: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ProtectedAnswerPresentationClaimModel(Base):
    __tablename__ = "protected_answer_presentation_claims"
    __table_args__ = (
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_protected_answer_presentation_claim_actor_idem",
        ),
        UniqueConstraint(
            "adjudication_id", name="uq_protected_answer_presentation_claim_adjudication"
        ),
    )
    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    presentation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    adjudication_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ProtectedAnswerPresentationModel(Base):
    __tablename__ = "protected_answer_presentations"
    __table_args__ = (
        UniqueConstraint("claim_id", name="uq_protected_answer_presentation_claim"),
        UniqueConstraint("adjudication_id", name="uq_protected_answer_presentation_adjudication"),
    )
    presentation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    adjudication_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    consumer_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ProtectedRecommendationCandidateClaimModel(Base):
    __tablename__ = "protected_recommendation_candidate_claims"
    __table_args__ = (
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_protected_recommendation_candidate_claim_actor_idem",
        ),
        UniqueConstraint(
            "presentation_id", name="uq_protected_recommendation_candidate_claim_presentation"
        ),
    )
    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    candidate_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    presentation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ProtectedRecommendationCandidateModel(Base):
    __tablename__ = "protected_recommendation_candidate_sets"
    __table_args__ = (
        UniqueConstraint("claim_id", name="uq_protected_recommendation_candidate_claim"),
        UniqueConstraint(
            "presentation_id", name="uq_protected_recommendation_candidate_presentation"
        ),
    )
    candidate_set_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    presentation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    consumer_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ProtectedCandidateImpactClaimModel(Base):
    __tablename__ = "protected_candidate_impact_claims"
    __table_args__ = (
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_protected_candidate_impact_claim_actor_idem",
        ),
        UniqueConstraint(
            "candidate_set_id", name="uq_protected_candidate_impact_claim_candidate_set"
        ),
    )
    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    impact_analysis_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    candidate_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ProtectedCandidateImpactModel(Base):
    __tablename__ = "protected_candidate_impact_analyses"
    __table_args__ = (
        UniqueConstraint("claim_id", name="uq_protected_candidate_impact_claim"),
        UniqueConstraint("candidate_set_id", name="uq_protected_candidate_impact_candidate_set"),
    )
    impact_analysis_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    candidate_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    consumer_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ProtectedCandidateRiskRecoveryClaimModel(Base):
    __tablename__ = "protected_candidate_risk_recovery_claims"
    __table_args__ = (
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_protected_candidate_risk_recovery_claim_actor_idem",
        ),
        UniqueConstraint(
            "impact_analysis_id",
            name="uq_protected_candidate_risk_recovery_claim_impact",
        ),
    )
    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    completion_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    impact_analysis_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ProtectedCandidateRiskRecoveryModel(Base):
    __tablename__ = "protected_candidate_risk_recovery_completions"
    __table_args__ = (
        UniqueConstraint("claim_id", name="uq_protected_candidate_risk_recovery_claim"),
        UniqueConstraint(
            "impact_analysis_id",
            name="uq_protected_candidate_risk_recovery_impact",
        ),
    )
    completion_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    impact_analysis_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    candidate_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    consumer_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ProtectedRecommendationAdjudicationClaimModel(Base):
    __tablename__ = "protected_recommendation_adjudication_claims"
    __table_args__ = (
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_protected_recommendation_adjudication_claim_actor_idem",
        ),
        UniqueConstraint(
            "completion_id",
            name="uq_protected_recommendation_adjudication_claim_completion",
        ),
    )
    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    adjudication_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    completion_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ProtectedRecommendationAdjudicationModel(Base):
    __tablename__ = "protected_recommendation_adjudications"
    __table_args__ = (
        UniqueConstraint("claim_id", name="uq_protected_recommendation_adjudication_claim"),
        UniqueConstraint(
            "completion_id", name="uq_protected_recommendation_adjudication_completion"
        ),
    )
    adjudication_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    completion_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    candidate_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    consumer_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ProtectedRecommendationPresentationClaimModel(Base):
    __tablename__ = "protected_recommendation_presentation_claims"
    __table_args__ = (
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_protected_recommendation_presentation_claim_actor_idem",
        ),
        UniqueConstraint(
            "adjudication_id",
            name="uq_protected_recommendation_presentation_claim_adjudication",
        ),
    )
    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    presentation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    adjudication_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ProtectedRecommendationPresentationModel(Base):
    __tablename__ = "protected_recommendation_presentations"
    __table_args__ = (
        UniqueConstraint("claim_id", name="uq_protected_recommendation_presentation_claim"),
        UniqueConstraint(
            "adjudication_id", name="uq_protected_recommendation_presentation_adjudication"
        ),
    )
    presentation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    adjudication_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    consumer_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class RecommendationPromotionClaimModel(Base):
    __tablename__ = "recommendation_promotion_claims"
    __table_args__ = (
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_recommendation_promotion_claim_actor_idem",
        ),
        UniqueConstraint("presentation_id", name="uq_recommendation_promotion_claim_presentation"),
    )
    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    promotion_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    recommendation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    presentation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class PromotedRecommendationArtifactModel(Base):
    __tablename__ = "promoted_recommendation_artifacts"
    __table_args__ = (
        UniqueConstraint("claim_id", name="uq_promoted_recommendation_artifact_claim"),
        UniqueConstraint(
            "presentation_id", name="uq_promoted_recommendation_artifact_presentation"
        ),
        UniqueConstraint("promotion_id", name="uq_promoted_recommendation_artifact_promotion"),
    )
    recommendation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    promotion_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    presentation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    consumer_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class RecommendationReadinessClaimModel(Base):
    __tablename__ = "recommendation_readiness_claims"
    __table_args__ = (
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_recommendation_readiness_claim_actor_idem",
        ),
        UniqueConstraint(
            "recommendation_id", name="uq_recommendation_readiness_claim_recommendation"
        ),
    )
    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    assessment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    recommendation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class RecommendationReadinessAssessmentModel(Base):
    __tablename__ = "recommendation_readiness_assessments"
    __table_args__ = (
        UniqueConstraint("claim_id", name="uq_recommendation_readiness_assessment_claim"),
        UniqueConstraint(
            "recommendation_id",
            name="uq_recommendation_readiness_assessment_recommendation",
        ),
    )
    assessment_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    recommendation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    promotion_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    consumer_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    evaluation_outcome: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class RecommendationReviewRequestClaimModel(Base):
    __tablename__ = "recommendation_review_request_claims"
    __table_args__ = (
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_recommendation_review_request_claim_actor_idem",
        ),
        UniqueConstraint(
            "readiness_assessment_id",
            name="uq_recommendation_review_request_claim_assessment",
        ),
    )
    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    review_request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    recommendation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    readiness_assessment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class RecommendationReviewRequestRecordModel(Base):
    __tablename__ = "recommendation_review_requests"
    __table_args__ = (
        UniqueConstraint("claim_id", name="uq_recommendation_review_request_record_claim"),
        UniqueConstraint(
            "readiness_assessment_id",
            name="uq_recommendation_review_request_record_assessment",
        ),
    )
    review_request_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    recommendation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    readiness_assessment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    promotion_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    requester_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class RecommendationReviewerAssignmentClaimModel(Base):
    __tablename__ = "recommendation_reviewer_assignment_claims"
    __table_args__ = (
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_recommendation_reviewer_assignment_claim_actor_idem",
        ),
        UniqueConstraint(
            "review_request_id",
            name="uq_recommendation_reviewer_assignment_claim_request",
        ),
    )
    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    assignment_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    review_request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class RecommendationReviewerAssignmentRecordModel(Base):
    __tablename__ = "recommendation_reviewer_assignments"
    __table_args__ = (
        UniqueConstraint("claim_id", name="uq_recommendation_reviewer_assignment_record_claim"),
        UniqueConstraint(
            "review_request_id",
            name="uq_recommendation_reviewer_assignment_record_request",
        ),
    )
    assignment_set_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    review_request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    recommendation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class RecommendationProtectedInspectionClaimModel(Base):
    __tablename__ = "recommendation_protected_inspection_claims"
    __table_args__ = (
        UniqueConstraint(
            "source_assignment_set_id",
            "track_code",
            name="uq_recommendation_inspection_claim_source_track",
        ),
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_recommendation_inspection_claim_actor_idem",
        ),
    )
    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_assignment_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    track_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    lease_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class RecommendationProtectedInspectionRecordModel(Base):
    __tablename__ = "recommendation_protected_inspection_leases"
    __table_args__ = (
        UniqueConstraint(
            "source_assignment_set_id",
            "track_code",
            name="uq_recommendation_inspection_lease_source_track",
        ),
        UniqueConstraint("claim_id", name="uq_recommendation_inspection_lease_claim"),
    )
    lease_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_assignment_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    recommendation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    track_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    lease_holder_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class RecommendationProtectedContentClaimModel(Base):
    __tablename__ = "recommendation_protected_content_claims"
    __table_args__ = (
        UniqueConstraint(
            "source_lease_id", name="uq_recommendation_protected_content_claim_source_lease"
        ),
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_recommendation_content_claim_actor_idem",
        ),
    )
    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_lease_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    presentation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class RecommendationProtectedContentModel(Base):
    __tablename__ = "recommendation_protected_content_presentations"
    __table_args__ = (
        UniqueConstraint("source_lease_id", name="uq_recommendation_content_present_source_lease"),
        UniqueConstraint("claim_id", name="uq_recommendation_content_present_claim"),
    )
    presentation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_lease_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_assignment_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    recommendation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    track_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    lease_holder_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    presented_content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    content_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class RecommendationHumanReviewFindingClaimModel(Base):
    __tablename__ = "recommendation_human_review_finding_claims"
    __table_args__ = (
        UniqueConstraint(
            "source_presentation_id", name="uq_recommendation_finding_claim_source_present"
        ),
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_recommendation_finding_claim_actor_idem",
        ),
    )
    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_presentation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    finding_packet_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    track_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class RecommendationHumanReviewFindingModel(Base):
    __tablename__ = "recommendation_human_review_findings"
    __table_args__ = (
        UniqueConstraint(
            "source_presentation_id", name="uq_recommendation_findings_source_presentation"
        ),
        UniqueConstraint("claim_id", name="uq_recommendation_findings_claim"),
    )
    finding_packet_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_lease_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_presentation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_assignment_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    recommendation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    track_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    lease_holder_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    finding_content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    finding_count: Mapped[int] = mapped_column(Integer, nullable=False)
    finding_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class RecommendationFindingPresentationClaimModel(Base):
    __tablename__ = "recommendation_finding_presentation_claims"
    __table_args__ = (
        UniqueConstraint(
            "source_finding_packet_id", name="uq_recommendation_finding_present_claim_source"
        ),
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_recommendation_finding_present_claim_actor_idem",
        ),
    )
    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_finding_packet_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    finding_presentation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    track_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class RecommendationFindingPresentationModel(Base):
    __tablename__ = "recommendation_finding_presentations"
    __table_args__ = (
        UniqueConstraint(
            "source_finding_packet_id", name="uq_recommendation_finding_present_source"
        ),
        UniqueConstraint("claim_id", name="uq_recommendation_finding_present_claim"),
    )
    finding_presentation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_finding_packet_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_lease_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_presentation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_assignment_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    recommendation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    track_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    lease_holder_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    finding_content_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    finding_count: Mapped[int] = mapped_column(Integer, nullable=False)
    finding_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class RecommendationTrackReviewDecisionClaimModel(Base):
    __tablename__ = "recommendation_track_review_decision_claims"
    __table_args__ = (
        UniqueConstraint(
            "source_finding_presentation_id",
            name="uq_rec_track_dec_claim_source",
        ),
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_rec_track_dec_claim_actor_idem",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_finding_presentation_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    decision_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    track_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    disposition_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class RecommendationTrackReviewDecisionModel(Base):
    __tablename__ = "recommendation_track_review_decisions"
    __table_args__ = (
        UniqueConstraint(
            "source_finding_presentation_id",
            name="uq_rec_track_dec_source",
        ),
        UniqueConstraint("claim_id", name="uq_rec_track_dec_claim"),
    )

    decision_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_finding_presentation_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    source_lease_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_assignment_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    review_request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    track_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    disposition_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    recommendation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    decided_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class RecommendationCorrectionClaimModel(Base):
    __tablename__ = "recommendation_correction_claims"
    __table_args__ = (
        UniqueConstraint("source_review_request_id", name="uq_rec_corr_claim_source"),
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_rec_corr_claim_actor_idem",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source_review_request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    correction_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class RecommendationCorrectionModel(Base):
    __tablename__ = "recommendation_corrections"
    __table_args__ = (
        UniqueConstraint("source_review_request_id", name="uq_rec_corr_source"),
        UniqueConstraint("claim_id", name="uq_rec_corr_claim"),
        UniqueConstraint("new_recommendation_id", name="uq_rec_corr_new_rec"),
    )

    correction_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_review_request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_recommendation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    new_recommendation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    new_promotion_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    corrected_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class FinalRecommendationDispositionClaimModel(Base):
    __tablename__ = "final_recommendation_disposition_claims"
    __table_args__ = (
        UniqueConstraint("review_request_id", name="uq_rec_final_claim_request"),
        UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_rec_final_claim_actor_idem",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    review_request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    disposition_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    claimed_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class FinalRecommendationDispositionModel(Base):
    __tablename__ = "final_recommendation_dispositions"
    __table_args__ = (
        UniqueConstraint("review_request_id", name="uq_rec_final_request"),
        UniqueConstraint("claim_id", name="uq_rec_final_claim"),
    )

    disposition_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    review_request_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    recommendation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    disposition_code: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    approved_by_subject_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class InventoryDeviceRecordModel(Base):
    __tablename__ = "inventory_device_records"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "environment_id",
            "device_key",
            name="uq_inventory_device_records_scope_key",
        ),
        UniqueConstraint(
            "created_by",
            "create_idempotency_key",
            name="uq_inventory_device_records_actor_create_idem",
        ),
        UniqueConstraint(
            "retired_by",
            "retirement_idempotency_key",
            name="uq_inventory_device_records_actor_retire_idem",
        ),
    )

    device_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    device_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    device_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    vendor: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    serial_number: Mapped[str | None] = mapped_column(String(160), nullable=True)
    management_address: Mapped[str | None] = mapped_column(String(253), nullable=True)
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    create_idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retired_by: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    retirement_idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ItsmIntegrationProfileModel(Base):
    __tablename__ = "itsm_integration_profiles"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "environment_id",
            "profile_key",
            name="uq_itsm_integration_profiles_scope_key",
        ),
        UniqueConstraint(
            "created_by",
            "create_idempotency_key",
            name="uq_itsm_integration_profiles_actor_create_idem",
        ),
        UniqueConstraint(
            "retired_by",
            "retirement_idempotency_key",
            name="uq_itsm_integration_profiles_actor_retire_idem",
        ),
    )

    profile_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    profile_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    provider_family: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    readiness_state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    create_idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retired_by: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    retirement_idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ItsmSandboxConformanceModel(Base):
    __tablename__ = "itsm_sandbox_conformance_assessments"
    __table_args__ = (
        UniqueConstraint(
            "assessed_by",
            "idempotency_key",
            name="uq_itsm_sandbox_conformance_actor_idem",
        ),
    )

    assessment_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    assessed_by: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalConversationModel(Base):
    __tablename__ = "operational_conversations"
    __table_args__ = (CheckConstraint("version >= 1", name="ck_operational_conversation_version"),)

    conversation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    lifecycle: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    owner_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalConversationTurnModel(Base):
    __tablename__ = "operational_conversation_turns"
    __table_args__ = (
        UniqueConstraint(
            "conversation_id",
            "ordinal",
            name="uq_operational_conversation_turn_ordinal",
        ),
        CheckConstraint("ordinal >= 1", name="ck_operational_conversation_turn_ordinal"),
    )

    turn_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("operational_conversations.conversation_id"),
        nullable=False,
        index=True,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class OperationalConversationIdempotencyModel(Base):
    __tablename__ = "operational_conversation_idempotency_records"
    __table_args__ = (
        UniqueConstraint(
            "operation",
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_operational_conversation_operation_scope_idem",
        ),
        CheckConstraint("result_version >= 1", name="ck_operational_conversation_idem_version"),
    )

    record_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    operation: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    idempotency_scope_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    owner_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("operational_conversations.conversation_id"),
        nullable=False,
        index=True,
    )
    result_version: Mapped[int] = mapped_column(Integer, nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowDefinitionModel(Base):
    __tablename__ = "workflow_definitions"
    __table_args__ = (
        UniqueConstraint(
            "definition_id",
            "definition_version",
            name="uq_workflow_definition_identity_version",
        ),
        CheckConstraint("definition_version >= 1", name="ck_workflow_definition_version"),
    )

    record_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    definition_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    definition_version: Mapped[int] = mapped_column(Integer, nullable=False)
    definition_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    input_schema_version: Mapped[str] = mapped_column(String(128), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowRunPlanModel(Base):
    __tablename__ = "workflow_run_plans"
    __table_args__ = (
        CheckConstraint("definition_version >= 1", name="ck_workflow_run_plan_definition_version"),
        CheckConstraint(
            "state IN ('planned', 'cancelled')",
            name="ck_workflow_run_plan_state",
        ),
        CheckConstraint("state_version >= 1", name="ck_workflow_run_plan_state_version"),
        UniqueConstraint("canonical_digest", name="uq_workflow_run_plan_digest"),
    )

    plan_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    definition_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    definition_version: Mapped[int] = mapped_column(Integer, nullable=False)
    definition_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    creator_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    canonical_input_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowPlanTransitionModel(Base):
    __tablename__ = "workflow_plan_transitions"
    __table_args__ = (
        UniqueConstraint(
            "plan_id",
            "sequence",
            name="uq_workflow_plan_transition_sequence",
        ),
        UniqueConstraint(
            "canonical_digest",
            name="uq_workflow_plan_transition_digest",
        ),
        CheckConstraint("sequence >= 1", name="ck_workflow_plan_transition_sequence"),
        CheckConstraint(
            "from_state = 'planned' AND to_state = 'cancelled'",
            name="ck_workflow_plan_transition_states",
        ),
    )

    transition_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_run_plans.plan_id"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    from_state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    to_state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    actor_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    reason_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowIdempotencyModel(Base):
    __tablename__ = "workflow_idempotency_records"
    __table_args__ = (
        UniqueConstraint(
            "operation",
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_workflow_operation_scope_idem",
        ),
    )

    record_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    operation: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    idempotency_scope_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_run_plans.plan_id"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    creator_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowOrchestrationLeaseModel(Base):
    __tablename__ = "workflow_orchestration_leases"
    __table_args__ = (
        UniqueConstraint("plan_id", name="uq_workflow_orchestration_lease_plan"),
        UniqueConstraint(
            "canonical_digest",
            name="uq_workflow_orchestration_lease_digest",
        ),
        CheckConstraint(
            "state IN ('active', 'released')",
            name="ck_workflow_orchestration_lease_state",
        ),
        CheckConstraint(
            "fencing_token >= 1",
            name="ck_workflow_orchestration_lease_fencing_token",
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_workflow_orchestration_lease_version",
        ),
        CheckConstraint(
            "last_heartbeat_at >= acquired_at",
            name="ck_workflow_orchestration_lease_heartbeat_time",
        ),
        CheckConstraint(
            "expires_at > last_heartbeat_at",
            name="ck_workflow_orchestration_lease_expiry_time",
        ),
    )

    lease_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_run_plans.plan_id"),
        nullable=False,
        index=True,
    )
    plan_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    worker_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowLeaseIdempotencyModel(Base):
    __tablename__ = "workflow_lease_idempotency_records"
    __table_args__ = (
        UniqueConstraint(
            "operation",
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_workflow_lease_operation_scope_idem",
        ),
        CheckConstraint(
            "operation IN ('acquire', 'heartbeat', 'release')",
            name="ck_workflow_lease_idempotency_operation",
        ),
    )

    record_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    operation: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    idempotency_scope_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    # Historical idempotency records retain the exact lease snapshot after a
    # newer fencing generation replaces the plan's current lease row.
    lease_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_run_plans.plan_id"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    worker_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowExecutionRunModel(Base):
    __tablename__ = "workflow_execution_runs"
    __table_args__ = (
        UniqueConstraint("plan_id", name="uq_workflow_execution_run_plan"),
        UniqueConstraint("canonical_digest", name="uq_workflow_execution_run_digest"),
        CheckConstraint(
            "definition_version >= 1", name="ck_workflow_execution_run_definition_version"
        ),
        CheckConstraint("lease_fencing_token >= 1", name="ck_workflow_execution_run_fencing_token"),
        CheckConstraint("state = 'created'", name="ck_workflow_execution_run_state"),
    )

    run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_run_plans.plan_id"),
        nullable=False,
        index=True,
    )
    plan_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    definition_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    definition_version: Mapped[int] = mapped_column(Integer, nullable=False)
    definition_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    # Historical lease binding deliberately has no FK to the mutable current-lease row.
    # A fencing takeover replaces that row's lease_id while immutable runs retain this snapshot.
    lease_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    lease_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    lease_fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)
    materialized_by_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowExecutionStepRunModel(Base):
    __tablename__ = "workflow_execution_step_runs"
    __table_args__ = (
        UniqueConstraint("run_id", "step_id", name="uq_workflow_step_run_step"),
        UniqueConstraint("run_id", "ordinal", name="uq_workflow_step_run_ordinal"),
        UniqueConstraint("canonical_digest", name="uq_workflow_step_run_digest"),
        CheckConstraint("ordinal >= 1", name="ck_workflow_step_run_ordinal"),
        CheckConstraint(
            "capability_class IN ('C0', 'C1', 'C2')",
            name="ck_workflow_step_run_capability_class",
        ),
        CheckConstraint(
            "timeout_seconds BETWEEN 1 AND 3600",
            name="ck_workflow_step_run_timeout",
        ),
        CheckConstraint("state = 'not_started'", name="ck_workflow_step_run_state"),
    )

    step_run_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    capability_class: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    depends_on: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowRunMaterializationClaimModel(Base):
    __tablename__ = "workflow_run_materialization_claims"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_workflow_run_materialization_scope_idem",
        ),
        UniqueConstraint("run_id", name="uq_workflow_run_materialization_claim_run"),
        UniqueConstraint("canonical_digest", name="uq_workflow_run_materialization_claim_digest"),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    idempotency_scope_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_runs.run_id"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_run_plans.plan_id"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    worker_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowExecutionAttemptModel(Base):
    __tablename__ = "workflow_execution_attempts"
    __table_args__ = (
        UniqueConstraint("step_run_id", name="uq_workflow_execution_attempt_step_run"),
        UniqueConstraint("canonical_digest", name="uq_workflow_execution_attempt_digest"),
        CheckConstraint("attempt_number = 1", name="ck_workflow_execution_attempt_number"),
        CheckConstraint(
            "definition_version >= 1",
            name="ck_workflow_execution_attempt_definition_version",
        ),
        CheckConstraint(
            "lease_fencing_token >= 1",
            name="ck_workflow_execution_attempt_fencing_token",
        ),
        CheckConstraint("state = 'created'", name="ck_workflow_execution_attempt_state"),
    )

    attempt_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_runs.run_id"),
        nullable=False,
        index=True,
    )
    run_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_step_runs.step_run_id"),
        nullable=False,
        index=True,
    )
    step_run_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_run_plans.plan_id"),
        nullable=False,
        index=True,
    )
    plan_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    definition_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    definition_version: Mapped[int] = mapped_column(Integer, nullable=False)
    definition_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    # The current lease row is replaceable during fencing takeover. Attempts retain
    # the exact historical identity and therefore deliberately have no lease FK.
    lease_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    lease_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    lease_fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)
    materialized_by_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowAttemptMaterializationClaimModel(Base):
    __tablename__ = "workflow_attempt_materialization_claims"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_workflow_attempt_materialization_scope_idem",
        ),
        UniqueConstraint("attempt_id", name="uq_workflow_attempt_materialization_claim_attempt"),
        UniqueConstraint(
            "canonical_digest",
            name="uq_workflow_attempt_materialization_claim_digest",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    idempotency_scope_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_attempts.attempt_id"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_runs.run_id"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_run_plans.plan_id"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    worker_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowDispatchIntentModel(Base):
    __tablename__ = "workflow_dispatch_intents"
    __table_args__ = (
        UniqueConstraint("attempt_id", name="uq_workflow_dispatch_intent_attempt"),
        UniqueConstraint("canonical_digest", name="uq_workflow_dispatch_intent_digest"),
        CheckConstraint("attempt_number = 1", name="ck_workflow_dispatch_intent_attempt_number"),
        CheckConstraint(
            "lease_fencing_token >= 1",
            name="ck_workflow_dispatch_intent_fencing_token",
        ),
        CheckConstraint("state = 'staged'", name="ck_workflow_dispatch_intent_state"),
    )

    dispatch_intent_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_run_plans.plan_id"),
        nullable=False,
        index=True,
    )
    plan_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_runs.run_id"),
        nullable=False,
        index=True,
    )
    run_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_step_runs.step_run_id"),
        nullable=False,
        index=True,
    )
    step_run_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_attempts.attempt_id"),
        nullable=False,
        index=True,
    )
    attempt_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    # The current lease row is replaceable during fencing takeover. Dispatch intents
    # retain the exact historical identity and therefore deliberately have no lease FK.
    lease_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    lease_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    lease_fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    staged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowDispatchOutboxEntryModel(Base):
    __tablename__ = "workflow_dispatch_outbox_entries"
    __table_args__ = (
        UniqueConstraint(
            "dispatch_intent_id",
            name="uq_workflow_dispatch_outbox_source_intent",
        ),
        UniqueConstraint(
            "canonical_digest",
            name="uq_workflow_dispatch_outbox_digest",
        ),
        CheckConstraint(
            "attempt_number = 1",
            name="ck_workflow_dispatch_outbox_attempt_number",
        ),
        CheckConstraint(
            "lease_fencing_token >= 1",
            name="ck_workflow_dispatch_outbox_fencing_token",
        ),
        CheckConstraint(
            "state = 'pending_publication'",
            name="ck_workflow_dispatch_outbox_state",
        ),
        CheckConstraint(
            "NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted",
            name="ck_workflow_dispatch_outbox_zero_authority",
        ),
    )

    outbox_entry_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    dispatch_intent_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_dispatch_intents.dispatch_intent_id"),
        nullable=False,
        index=True,
    )
    dispatch_intent_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_run_plans.plan_id"),
        nullable=False,
        index=True,
    )
    plan_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_runs.run_id"),
        nullable=False,
        index=True,
    )
    run_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_step_runs.step_run_id"),
        nullable=False,
        index=True,
    )
    step_run_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_attempts.attempt_id"),
        nullable=False,
        index=True,
    )
    attempt_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    # Lease rows are replaceable during fencing takeover; this immutable snapshot
    # deliberately stores the exact historical lease identity without a lease FK.
    lease_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    lease_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    lease_fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)
    worker_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    admitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowOutboxPublicationLeaseModel(Base):
    __tablename__ = "workflow_dispatch_outbox_publication_leases"
    __table_args__ = (
        UniqueConstraint(
            "outbox_entry_id",
            name="uq_workflow_dispatch_outbox_publication_lease_entry",
        ),
        UniqueConstraint(
            "canonical_digest",
            name="uq_workflow_dispatch_outbox_publication_lease_digest",
        ),
        CheckConstraint(
            "publication_fencing_token >= 1",
            name="ck_workflow_dispatch_outbox_publication_lease_fence",
        ),
        CheckConstraint(
            "orchestration_fencing_token >= 1",
            name="ck_workflow_dispatch_outbox_publication_orchestration_fence",
        ),
        CheckConstraint(
            "attempt_number = 1",
            name="ck_workflow_dispatch_outbox_publication_attempt_number",
        ),
        CheckConstraint(
            "state IN ('active', 'released')",
            name="ck_workflow_dispatch_outbox_publication_lease_state",
        ),
        CheckConstraint(
            "version >= 1",
            name="ck_workflow_dispatch_outbox_publication_lease_version",
        ),
        CheckConstraint(
            "last_heartbeat_at >= acquired_at",
            name="ck_workflow_dispatch_outbox_publication_lease_heartbeat_time",
        ),
        CheckConstraint(
            "expires_at > last_heartbeat_at",
            name="ck_workflow_dispatch_outbox_publication_lease_expiry_time",
        ),
    )

    publication_lease_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    outbox_entry_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_dispatch_outbox_entries.outbox_entry_id"),
        nullable=False,
        index=True,
    )
    outbox_entry_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    dispatch_intent_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_dispatch_intents.dispatch_intent_id"),
        nullable=False,
        index=True,
    )
    dispatch_intent_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_run_plans.plan_id"),
        nullable=False,
        index=True,
    )
    plan_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_runs.run_id"),
        nullable=False,
        index=True,
    )
    run_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_step_runs.step_run_id"),
        nullable=False,
        index=True,
    )
    step_run_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_attempts.attempt_id"),
        nullable=False,
        index=True,
    )
    attempt_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    # The orchestration lease is a replaceable current row. This publication lease
    # retains its exact lineage snapshot without an FK to that mutable identity.
    orchestration_lease_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    orchestration_lease_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    orchestration_fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)
    publisher_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    publication_fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowOutboxPublicationLeaseAcquireClaimModel(Base):
    __tablename__ = "workflow_dispatch_outbox_publication_lease_acquire_claims"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_workflow_dispatch_outbox_publication_lease_scope_idem",
        ),
        UniqueConstraint(
            "publication_lease_id",
            name="uq_workflow_dispatch_outbox_publication_lease_claim_lease",
        ),
        UniqueConstraint(
            "canonical_digest",
            name="uq_workflow_dispatch_outbox_publication_lease_claim_digest",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    idempotency_scope_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    # No FK to the replaceable current publication-lease row: this claim is an
    # immutable acquisition result retained across fencing takeovers.
    publication_lease_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    outbox_entry_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_dispatch_outbox_entries.outbox_entry_id"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_run_plans.plan_id"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    publisher_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowDispatchEventEnvelopeModel(Base):
    __tablename__ = "workflow_dispatch_event_envelopes"
    __table_args__ = (
        UniqueConstraint(
            "outbox_entry_id",
            name="uq_workflow_dispatch_event_envelope_outbox",
        ),
        UniqueConstraint(
            "event_id",
            name="uq_workflow_dispatch_event_envelope_event",
        ),
        UniqueConstraint(
            "canonical_digest",
            name="uq_workflow_dispatch_event_envelope_digest",
        ),
        CheckConstraint(
            "attempt_number = 1",
            name="ck_workflow_dispatch_event_envelope_attempt_number",
        ),
        CheckConstraint(
            "orchestration_fencing_token >= 1",
            name="ck_workflow_dispatch_event_envelope_orchestration_fence",
        ),
        CheckConstraint(
            "publication_fencing_token >= 1",
            name="ck_workflow_dispatch_event_envelope_publication_fence",
        ),
        CheckConstraint(
            "state = 'prepared'",
            name="ck_workflow_dispatch_event_envelope_state",
        ),
        CheckConstraint(
            "NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted",
            name="ck_workflow_dispatch_event_envelope_zero_authority",
        ),
    )

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_version: Mapped[str] = mapped_column(String(32), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    producer: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    producer_version: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    subject_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    correlation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    causation_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    workflow_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    data_classification: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    schema_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    outbox_entry_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_dispatch_outbox_entries.outbox_entry_id"),
        nullable=False,
        index=True,
    )
    outbox_entry_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    dispatch_intent_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_dispatch_intents.dispatch_intent_id"),
        nullable=False,
        index=True,
    )
    dispatch_intent_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_run_plans.plan_id"),
        nullable=False,
        index=True,
    )
    plan_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_runs.run_id"),
        nullable=False,
        index=True,
    )
    run_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_step_runs.step_run_id"),
        nullable=False,
        index=True,
    )
    step_run_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_attempts.attempt_id"),
        nullable=False,
        index=True,
    )
    attempt_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    # Both lease tables hold replaceable current ownership. The envelope is immutable
    # historical evidence and deliberately snapshots their exact identities without FKs.
    orchestration_lease_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    orchestration_lease_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    orchestration_fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)
    publication_lease_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    publication_lease_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    publication_fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)
    publisher_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    prepared_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowDispatchEventEnvelopePreparationClaimModel(Base):
    __tablename__ = "workflow_dispatch_event_envelope_preparation_claims"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_workflow_dispatch_event_envelope_scope_idem",
        ),
        UniqueConstraint(
            "event_id",
            name="uq_workflow_dispatch_event_envelope_claim_event",
        ),
        UniqueConstraint(
            "outbox_entry_id",
            name="uq_workflow_dispatch_event_envelope_claim_outbox",
        ),
        UniqueConstraint(
            "canonical_digest",
            name="uq_workflow_dispatch_event_envelope_claim_digest",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    idempotency_scope_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    outbox_entry_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_dispatch_outbox_entries.outbox_entry_id"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_run_plans.plan_id"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    publisher_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventTransportAdmissionModel(Base):
    __tablename__ = "workflow_event_transport_admissions"
    __table_args__ = (
        UniqueConstraint(
            "event_id",
            name="uq_workflow_event_transport_admission_event",
        ),
        UniqueConstraint(
            "outbox_entry_id",
            name="uq_workflow_event_transport_admission_outbox",
        ),
        UniqueConstraint(
            "canonical_digest",
            name="uq_workflow_event_transport_admission_digest",
        ),
        CheckConstraint(
            "attempt_number = 1",
            name="ck_workflow_event_transport_admission_attempt_number",
        ),
        CheckConstraint(
            "canonical_byte_count >= 1 AND canonical_byte_count <= maximum_canonical_byte_count",
            name="ck_workflow_event_transport_admission_byte_count",
        ),
        CheckConstraint(
            "orchestration_fencing_token >= 1",
            name="ck_workflow_event_transport_admission_orchestration_fence",
        ),
        CheckConstraint(
            "publication_fencing_token >= 1",
            name="ck_workflow_event_transport_admission_publication_fence",
        ),
        CheckConstraint(
            "state = 'admitted'",
            name="ck_workflow_event_transport_admission_state",
        ),
        CheckConstraint(
            "NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted",
            name="ck_workflow_event_transport_admission_zero_authority",
        ),
    )

    admission_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_dispatch_event_envelopes.event_id"),
        nullable=False,
        index=True,
    )
    event_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    outbox_entry_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_dispatch_outbox_entries.outbox_entry_id"),
        nullable=False,
        index=True,
    )
    outbox_entry_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    dispatch_intent_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_dispatch_intents.dispatch_intent_id"),
        nullable=False,
        index=True,
    )
    dispatch_intent_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_run_plans.plan_id"),
        nullable=False,
        index=True,
    )
    plan_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_runs.run_id"),
        nullable=False,
        index=True,
    )
    run_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_step_runs.step_run_id"),
        nullable=False,
        index=True,
    )
    step_run_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_attempts.attempt_id"),
        nullable=False,
        index=True,
    )
    attempt_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    event_version: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    data_classification: Mapped[str] = mapped_column(String(64), nullable=False)
    representation_name: Mapped[str] = mapped_column(String(64), nullable=False)
    encoding: Mapped[str] = mapped_column(String(32), nullable=False)
    maximum_canonical_byte_count: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_byte_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # Both leases are replaceable current ownership. Admission preserves their
    # exact immutable evidence without coupling it to those mutable rows.
    orchestration_lease_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    orchestration_lease_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    orchestration_fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)
    publication_lease_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    publication_lease_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    publication_fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)
    publisher_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    admitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventTransportAdmissionClaimModel(Base):
    __tablename__ = "workflow_event_transport_admission_claims"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_workflow_event_transport_admission_scope_idem",
        ),
        UniqueConstraint(
            "admission_id",
            name="uq_workflow_event_transport_admission_claim_admission",
        ),
        UniqueConstraint(
            "event_id",
            name="uq_workflow_event_transport_admission_claim_event",
        ),
        UniqueConstraint(
            "outbox_entry_id",
            name="uq_workflow_event_transport_admission_claim_outbox",
        ),
        UniqueConstraint(
            "canonical_digest",
            name="uq_workflow_event_transport_admission_claim_digest",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    idempotency_scope_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    admission_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_dispatch_event_envelopes.event_id"),
        nullable=False,
        index=True,
    )
    outbox_entry_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_dispatch_outbox_entries.outbox_entry_id"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_run_plans.plan_id"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    publisher_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventByteArtifactModel(Base):
    __tablename__ = "workflow_event_byte_artifacts"
    __table_args__ = (
        UniqueConstraint("admission_id", name="uq_workflow_event_byte_artifact_admission"),
        UniqueConstraint("event_id", name="uq_workflow_event_byte_artifact_event"),
        UniqueConstraint("outbox_entry_id", name="uq_workflow_event_byte_artifact_outbox"),
        UniqueConstraint("content_sha256", name="uq_workflow_event_byte_artifact_content"),
        UniqueConstraint("canonical_digest", name="uq_workflow_event_byte_artifact_digest"),
        CheckConstraint(
            "attempt_number = 1",
            name="ck_workflow_event_byte_artifact_attempt_number",
        ),
        CheckConstraint(
            "canonical_byte_count >= 1 AND canonical_byte_count <= maximum_canonical_byte_count",
            name="ck_workflow_event_byte_artifact_byte_count",
        ),
        CheckConstraint(
            "octet_length(canonical_bytes) = canonical_byte_count",
            name="ck_workflow_event_byte_artifact_binary_length",
        ),
        CheckConstraint(
            "orchestration_fencing_token >= 1",
            name="ck_workflow_event_byte_artifact_orchestration_fence",
        ),
        CheckConstraint(
            "publication_fencing_token >= 1",
            name="ck_workflow_event_byte_artifact_publication_fence",
        ),
        CheckConstraint(
            "state = 'materialized'",
            name="ck_workflow_event_byte_artifact_state",
        ),
        CheckConstraint(
            "NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted",
            name="ck_workflow_event_byte_artifact_zero_authority",
        ),
    )

    artifact_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    admission_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_transport_admissions.admission_id"),
        nullable=False,
        index=True,
    )
    admission_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_dispatch_event_envelopes.event_id"),
        nullable=False,
        index=True,
    )
    event_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    event_version: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    data_classification: Mapped[str] = mapped_column(String(64), nullable=False)
    outbox_entry_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_dispatch_outbox_entries.outbox_entry_id"),
        nullable=False,
        index=True,
    )
    outbox_entry_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    dispatch_intent_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_dispatch_intents.dispatch_intent_id"),
        nullable=False,
        index=True,
    )
    dispatch_intent_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_run_plans.plan_id"),
        nullable=False,
        index=True,
    )
    plan_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_runs.run_id"), nullable=False, index=True
    )
    run_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_step_runs.step_run_id"), nullable=False, index=True
    )
    step_run_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_attempts.attempt_id"), nullable=False, index=True
    )
    attempt_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    representation_name: Mapped[str] = mapped_column(String(64), nullable=False)
    encoding: Mapped[str] = mapped_column(String(32), nullable=False)
    maximum_canonical_byte_count: Mapped[int] = mapped_column(Integer, nullable=False)
    canonical_byte_count: Mapped[int] = mapped_column(Integer, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Lease ownership rows are replaceable; preserve exact immutable fencing
    # evidence without foreign keys to those mutable rows.
    orchestration_lease_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    orchestration_lease_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    orchestration_fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)
    publication_lease_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    publication_lease_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    publication_fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)
    publisher_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    materialized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventByteArtifactClaimModel(Base):
    __tablename__ = "workflow_event_byte_artifact_claims"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_workflow_event_byte_artifact_scope_idem",
        ),
        UniqueConstraint("artifact_id", name="uq_workflow_event_byte_artifact_claim_artifact"),
        UniqueConstraint("admission_id", name="uq_workflow_event_byte_artifact_claim_admission"),
        UniqueConstraint("event_id", name="uq_workflow_event_byte_artifact_claim_event"),
        UniqueConstraint("outbox_entry_id", name="uq_workflow_event_byte_artifact_claim_outbox"),
        UniqueConstraint("canonical_digest", name="uq_workflow_event_byte_artifact_claim_digest"),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    idempotency_scope_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    artifact_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    admission_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_transport_admissions.admission_id"),
        nullable=False,
        index=True,
    )
    event_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_dispatch_event_envelopes.event_id"),
        nullable=False,
        index=True,
    )
    outbox_entry_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_dispatch_outbox_entries.outbox_entry_id"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_run_plans.plan_id"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    publisher_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventLogicalChannelBindingModel(Base):
    __tablename__ = "workflow_event_channel_bindings"
    __table_args__ = (
        UniqueConstraint("artifact_id", name="uq_wf_event_channel_binding_artifact"),
        UniqueConstraint("canonical_digest", name="uq_wf_event_channel_binding_digest"),
        CheckConstraint("attempt_number = 1", name="ck_wf_event_channel_binding_attempt"),
        CheckConstraint(
            "canonical_byte_count >= 1 AND canonical_byte_count <= maximum_canonical_byte_count",
            name="ck_wf_event_channel_binding_byte_count",
        ),
        CheckConstraint(
            "orchestration_fencing_token >= 1",
            name="ck_wf_event_channel_binding_orch_fence",
        ),
        CheckConstraint(
            "publication_fencing_token >= 1",
            name="ck_wf_event_channel_binding_pub_fence",
        ),
        CheckConstraint("state = 'bound'", name="ck_wf_event_channel_binding_state"),
        CheckConstraint(
            "NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted",
            name="ck_wf_event_channel_binding_zero_auth",
        ),
    )

    binding_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    artifact_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_byte_artifacts.artifact_id"), nullable=False, index=True
    )
    artifact_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    canonical_byte_count: Mapped[int] = mapped_column(Integer, nullable=False)
    admission_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_transport_admissions.admission_id"),
        nullable=False,
        index=True,
    )
    admission_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_dispatch_event_envelopes.event_id"), nullable=False, index=True
    )
    event_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    event_version: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    outbox_entry_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_dispatch_outbox_entries.outbox_entry_id"),
        nullable=False,
        index=True,
    )
    outbox_entry_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    dispatch_intent_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_dispatch_intents.dispatch_intent_id"), nullable=False, index=True
    )
    dispatch_intent_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_run_plans.plan_id"), nullable=False, index=True
    )
    plan_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_runs.run_id"), nullable=False, index=True
    )
    run_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_step_runs.step_run_id"), nullable=False, index=True
    )
    step_run_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_attempts.attempt_id"), nullable=False, index=True
    )
    attempt_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    logical_channel_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    logical_channel_version: Mapped[str] = mapped_column(String(64), nullable=False)
    data_classification: Mapped[str] = mapped_column(String(64), nullable=False)
    representation_name: Mapped[str] = mapped_column(String(64), nullable=False)
    encoding: Mapped[str] = mapped_column(String(32), nullable=False)
    delivery_semantics: Mapped[str] = mapped_column(String(64), nullable=False)
    durability_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ordering_key_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    ordering_key_value: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    retention_class: Mapped[str] = mapped_column(String(64), nullable=False)
    maximum_canonical_byte_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # Current lease rows are replaceable. These columns preserve immutable
    # historical evidence and deliberately have no foreign keys.
    orchestration_lease_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    orchestration_lease_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    orchestration_fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)
    publication_lease_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    publication_lease_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    publication_fencing_token: Mapped[int] = mapped_column(Integer, nullable=False)
    publisher_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    bound_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventLogicalChannelBindingClaimModel(Base):
    __tablename__ = "workflow_event_channel_binding_claims"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_event_channel_claim_scope_idem",
        ),
        UniqueConstraint("binding_id", name="uq_wf_event_channel_claim_binding"),
        UniqueConstraint("artifact_id", name="uq_wf_event_channel_claim_artifact"),
        UniqueConstraint("canonical_digest", name="uq_wf_event_channel_claim_digest"),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    idempotency_scope_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    binding_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_channel_bindings.binding_id"), nullable=False, index=True
    )
    artifact_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_byte_artifacts.artifact_id"), nullable=False, index=True
    )
    admission_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_transport_admissions.admission_id"),
        nullable=False,
        index=True,
    )
    event_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_dispatch_event_envelopes.event_id"), nullable=False, index=True
    )
    outbox_entry_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_dispatch_outbox_entries.outbox_entry_id"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_run_plans.plan_id"), nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    publisher_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class EventPhysicalTransportProfileSnapshotModel(Base):
    __tablename__ = "event_transport_profile_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "transport_profile_id",
            "transport_profile_revision",
            name="uq_event_transport_profile_snapshot_revision",
        ),
        UniqueConstraint(
            "source_profile_digest",
            name="uq_event_transport_profile_snapshot_source_digest",
        ),
        UniqueConstraint(
            "canonical_digest",
            name="uq_event_transport_profile_snapshot_digest",
        ),
        CheckConstraint(
            "maximum_message_byte_count >= 1",
            name="ck_event_transport_profile_snapshot_max_bytes",
        ),
        CheckConstraint(
            "state = 'snapshotted'",
            name="ck_event_transport_profile_snapshot_state",
        ),
        CheckConstraint(
            "NOT route_selection_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted",
            name="ck_event_transport_profile_snapshot_zero_auth",
        ),
    )

    snapshot_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    # The deployment profile is mutable outside this boundary. Preserve its
    # exact historical identity without a foreign key to the current source row.
    transport_profile_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    transport_profile_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    source_profile_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    deployment_release_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    deployment_profile: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    transport_resource_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    transport_resource_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    transport_implementation_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    transport_implementation_version: Mapped[str] = mapped_column(String(64), nullable=False)
    adapter_contract_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    adapter_contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    adapter_contract_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    supported_event_contracts: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    supported_classifications: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    supported_representations: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    supported_encodings: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    supported_delivery_semantics: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    durable_delivery_supported: Mapped[bool] = mapped_column(Boolean, nullable=False)
    supported_ordering_key_kinds: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    supported_retention_classes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    maximum_message_byte_count: Mapped[int] = mapped_column(Integer, nullable=False)
    transport_encryption_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    restricted_network_supported: Mapped[bool] = mapped_column(Boolean, nullable=False)
    snapshotter_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    route_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class EventPhysicalTransportProfileSnapshotClaimModel(Base):
    __tablename__ = "event_transport_profile_snapshot_claims"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_event_transport_profile_claim_scope_idem",
        ),
        UniqueConstraint(
            "snapshot_id",
            name="uq_event_transport_profile_claim_snapshot",
        ),
        UniqueConstraint(
            "transport_profile_id",
            "transport_profile_revision",
            name="uq_event_transport_profile_claim_revision",
        ),
        UniqueConstraint(
            "canonical_digest",
            name="uq_event_transport_profile_claim_digest",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    idempotency_scope_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("event_transport_profile_snapshots.snapshot_id"),
        nullable=False,
        index=True,
    )
    # These fields are immutable history, not references to mutable deployment rows.
    transport_profile_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    transport_profile_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    source_profile_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    snapshotter_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class DeploymentEventTransportCredentialAssignmentModel(Base):
    __tablename__ = "deployment_event_transport_credential_assignments"
    __table_args__ = (
        UniqueConstraint(
            "source_assignment_digest",
            name="uq_deploy_transport_credential_assignment_source_digest",
        ),
        UniqueConstraint(
            "canonical_digest",
            name="uq_deploy_transport_credential_assignment_digest",
        ),
        UniqueConstraint(
            "assignment_id",
            "rotation_epoch",
            "credential_generation",
            name="uq_deploy_transport_credential_assignment_head_rank",
        ),
        CheckConstraint(
            "credential_generation > 0 AND rotation_epoch > 0",
            name="ck_deploy_transport_credential_assignment_generations",
        ),
        CheckConstraint(
            "activated_at < expires_at",
            name="ck_deploy_transport_credential_assignment_window",
        ),
        CheckConstraint(
            "NOT (active AND revoked)",
            name="ck_deploy_transport_credential_assignment_lifecycle",
        ),
    )

    assignment_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    assignment_revision: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_assignment_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    route_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    route_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    source_route_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    credential_requirement_profile_id: Mapped[str] = mapped_column(String(128), nullable=False)
    credential_requirement_profile_version: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_requirement_profile_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_profile_id: Mapped[str] = mapped_column(String(128), nullable=False)
    credential_profile_version: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_profile_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    authentication_mechanism_class: Mapped[str] = mapped_column(String(64), nullable=False)
    principal_class: Mapped[str] = mapped_column(String(64), nullable=False)
    privilege_class: Mapped[str] = mapped_column(String(64), nullable=False)
    target_scope_commitment: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_generation: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    rotation_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    revoked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    broker_policy_id: Mapped[str] = mapped_column(String(128), nullable=False)
    broker_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    broker_policy_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class EventPhysicalTransportCredentialAssignmentSnapshotModel(Base):
    __tablename__ = "event_transport_credential_assignment_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "assignment_id",
            "assignment_revision",
            name="uq_event_transport_credential_snapshot_revision",
        ),
        UniqueConstraint(
            "source_assignment_digest",
            name="uq_event_transport_credential_snapshot_source_digest",
        ),
        UniqueConstraint(
            "canonical_digest",
            name="uq_event_transport_credential_snapshot_digest",
        ),
        CheckConstraint(
            "credential_generation > 0 AND rotation_epoch > 0",
            name="ck_event_transport_credential_snapshot_generations",
        ),
        CheckConstraint(
            "activated_at <= captured_at AND captured_at < expires_at",
            name="ck_event_transport_credential_snapshot_window",
        ),
        CheckConstraint(
            "state = 'snapshotted' AND source_non_revoked",
            name="ck_event_transport_credential_snapshot_state",
        ),
        CheckConstraint(
            "NOT endpoint_resolution_authority_granted "
            "AND NOT protected_artifact_access_authority_granted "
            "AND NOT credential_selection_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT credential_brokerage_authority_granted "
            "AND NOT credential_resolution_authority_granted "
            "AND NOT credential_delivery_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted "
            "AND NOT infrastructure_mutation_authority_granted",
            name="ck_event_transport_credential_snapshot_zero_auth",
        ),
    )

    snapshot_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    assignment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    assignment_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    source_assignment_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    route_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("event_transport_route_snapshots.snapshot_id"), nullable=False, index=True
    )
    route_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    route_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    source_route_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    credential_requirement_profile_id: Mapped[str] = mapped_column(String(128), nullable=False)
    credential_requirement_profile_version: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_requirement_profile_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_profile_id: Mapped[str] = mapped_column(String(128), nullable=False)
    credential_profile_version: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_profile_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    authentication_mechanism_class: Mapped[str] = mapped_column(String(64), nullable=False)
    principal_class: Mapped[str] = mapped_column(String(64), nullable=False)
    privilege_class: Mapped[str] = mapped_column(String(64), nullable=False)
    target_scope_commitment: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_generation: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    rotation_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    source_non_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    broker_policy_id: Mapped[str] = mapped_column(String(128), nullable=False)
    broker_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    broker_policy_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshotter_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    endpoint_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    protected_artifact_access_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_brokerage_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    readiness_probe_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    infrastructure_mutation_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class EventPhysicalTransportCredentialAssignmentSnapshotClaimModel(Base):
    __tablename__ = "event_transport_credential_assignment_snapshot_claims"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_event_transport_credential_claim_scope_idem",
        ),
        UniqueConstraint(
            "snapshot_id",
            name="uq_event_transport_credential_claim_snapshot",
        ),
        UniqueConstraint(
            "assignment_id",
            "assignment_revision",
            name="uq_event_transport_credential_claim_revision",
        ),
        UniqueConstraint(
            "canonical_digest",
            name="uq_event_transport_credential_claim_digest",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    idempotency_scope_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("event_transport_credential_assignment_snapshots.snapshot_id"),
        nullable=False,
        index=True,
    )
    assignment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    assignment_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    source_assignment_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    snapshotter_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class EventPhysicalTransportRouteSnapshotModel(Base):
    __tablename__ = "event_transport_route_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "route_id",
            "route_revision",
            name="uq_event_transport_route_snapshot_revision",
        ),
        UniqueConstraint(
            "source_route_digest",
            name="uq_event_transport_route_snapshot_source_digest",
        ),
        UniqueConstraint(
            "canonical_digest",
            name="uq_event_transport_route_snapshot_digest",
        ),
        CheckConstraint(
            "state = 'snapshotted'",
            name="ck_event_transport_route_snapshot_state",
        ),
        CheckConstraint(
            "NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT endpoint_resolution_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted",
            name="ck_event_transport_route_snapshot_zero_auth",
        ),
    )

    snapshot_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    # The deployment route is mutable outside this boundary. Preserve its
    # exact historical identity without linking to the current source row.
    route_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    route_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    route_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    route_set_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    selection_epoch_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    selection_epoch_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    source_route_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    deployment_release_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    deployment_profile: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    transport_profile_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    transport_profile_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    transport_resource_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    transport_resource_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    transport_implementation_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True
    )
    transport_implementation_version: Mapped[str] = mapped_column(String(64), nullable=False)
    adapter_contract_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    adapter_contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    adapter_contract_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    route_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    endpoint_set_id: Mapped[str] = mapped_column(String(128), nullable=False)
    endpoint_set_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    destination_id: Mapped[str] = mapped_column(String(128), nullable=False)
    destination_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    routing_contract_id: Mapped[str] = mapped_column(String(128), nullable=False)
    routing_contract_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    private_route_descriptor_commitment: Mapped[str] = mapped_column(String(64), nullable=False)
    transport_security_policy_id: Mapped[str] = mapped_column(String(128), nullable=False)
    transport_security_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    transport_security_policy_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    minimum_tls_version: Mapped[str] = mapped_column(String(32), nullable=False)
    server_authentication_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    client_authentication_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    plaintext_fallback_prohibited: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network_policy_id: Mapped[str] = mapped_column(String(128), nullable=False)
    network_policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    network_policy_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    source_zone_class: Mapped[str] = mapped_column(String(64), nullable=False)
    destination_zone_class: Mapped[str] = mapped_column(String(64), nullable=False)
    restricted_network_enforced: Mapped[bool] = mapped_column(Boolean, nullable=False)
    public_egress_prohibited: Mapped[bool] = mapped_column(Boolean, nullable=False)
    proxy_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    credential_requirement_profile_id: Mapped[str] = mapped_column(String(128), nullable=False)
    credential_requirement_profile_version: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_requirement_profile_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    authentication_mechanism_class: Mapped[str] = mapped_column(String(64), nullable=False)
    principal_class: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshotter_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    route_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_binding_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    endpoint_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    readiness_probe_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class EventPhysicalTransportRouteSnapshotClaimModel(Base):
    __tablename__ = "event_transport_route_snapshot_claims"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_event_transport_route_claim_scope_idem",
        ),
        UniqueConstraint("snapshot_id", name="uq_event_transport_route_claim_snapshot"),
        UniqueConstraint(
            "route_id",
            "route_revision",
            name="uq_event_transport_route_claim_revision",
        ),
        UniqueConstraint(
            "canonical_digest",
            name="uq_event_transport_route_claim_digest",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    idempotency_scope_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("event_transport_route_snapshots.snapshot_id"), nullable=False, index=True
    )
    route_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    route_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    source_route_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    snapshotter_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventTransportCompatibilityAdmissionModel(Base):
    __tablename__ = "workflow_event_transport_compatibility_admissions"
    __table_args__ = (
        UniqueConstraint(
            "logical_channel_binding_id",
            "transport_profile_snapshot_id",
            "policy_digest",
            name="uq_wf_transport_compat_binding_profile_policy",
        ),
        UniqueConstraint(
            "canonical_digest",
            name="uq_wf_transport_compat_admission_digest",
        ),
        CheckConstraint(
            "state = 'admitted'",
            name="ck_wf_transport_compat_admission_state",
        ),
        CheckConstraint(
            "logical_maximum_byte_count >= 1 "
            "AND artifact_byte_count >= 1 "
            "AND artifact_byte_count <= logical_maximum_byte_count "
            "AND logical_maximum_byte_count <= profile_maximum_message_byte_count",
            name="ck_wf_transport_compat_admission_bytes",
        ),
        CheckConstraint(
            "NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted",
            name="ck_wf_transport_compat_admission_zero_auth",
        ),
    )

    compatibility_admission_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    logical_channel_binding_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_channel_bindings.binding_id"), nullable=False, index=True
    )
    logical_channel_binding_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    transport_profile_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("event_transport_profile_snapshots.snapshot_id"), nullable=False, index=True
    )
    transport_profile_snapshot_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    transport_profile_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    transport_profile_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    event_version: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_uri: Mapped[str] = mapped_column(String(512), nullable=False)
    data_classification: Mapped[str] = mapped_column(String(64), nullable=False)
    representation_name: Mapped[str] = mapped_column(String(64), nullable=False)
    encoding: Mapped[str] = mapped_column(String(32), nullable=False)
    delivery_semantics: Mapped[str] = mapped_column(String(64), nullable=False)
    durability_required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ordering_key_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    retention_class: Mapped[str] = mapped_column(String(64), nullable=False)
    logical_maximum_byte_count: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_byte_count: Mapped[int] = mapped_column(Integer, nullable=False)
    profile_maximum_message_byte_count: Mapped[int] = mapped_column(Integer, nullable=False)
    admitter_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    admitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    route_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_binding_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventTransportCompatibilityAdmissionClaimModel(Base):
    __tablename__ = "workflow_event_transport_compatibility_admission_claims"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_transport_compat_claim_scope_idem",
        ),
        UniqueConstraint(
            "compatibility_admission_id",
            name="uq_wf_transport_compat_claim_admission",
        ),
        UniqueConstraint(
            "canonical_digest",
            name="uq_wf_transport_compat_claim_digest",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    idempotency_scope_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    compatibility_admission_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_transport_compatibility_admissions.compatibility_admission_id"),
        nullable=False,
        index=True,
    )
    logical_channel_binding_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_channel_bindings.binding_id"), nullable=False, index=True
    )
    transport_profile_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("event_transport_profile_snapshots.snapshot_id"), nullable=False, index=True
    )
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    admitter_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventPhysicalTransportRouteBindingModel(Base):
    __tablename__ = "workflow_event_physical_transport_route_bindings"
    __table_args__ = (
        UniqueConstraint(
            "logical_channel_binding_id",
            name="uq_wf_physical_route_binding_logical_binding",
        ),
        UniqueConstraint(
            "canonical_digest",
            name="uq_wf_physical_route_binding_digest",
        ),
        CheckConstraint(
            "state = 'bound'",
            name="ck_wf_physical_route_binding_state",
        ),
        CheckConstraint(
            "NOT endpoint_resolution_authority_granted "
            "AND NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted",
            name="ck_wf_physical_route_binding_zero_auth",
        ),
    )

    binding_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    logical_channel_binding_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_channel_bindings.binding_id"), nullable=False, index=True
    )
    logical_channel_binding_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    transport_compatibility_admission_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_transport_compatibility_admissions.compatibility_admission_id"),
        nullable=False,
        index=True,
    )
    transport_compatibility_admission_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    transport_profile_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("event_transport_profile_snapshots.snapshot_id"), nullable=False, index=True
    )
    transport_profile_snapshot_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    transport_route_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("event_transport_route_snapshots.snapshot_id"), nullable=False, index=True
    )
    transport_route_snapshot_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    binder_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    bound_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    endpoint_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_binding_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    readiness_probe_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventPhysicalTransportRouteBindingClaimModel(Base):
    __tablename__ = "workflow_event_physical_transport_route_binding_claims"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_physical_route_binding_claim_scope_idem",
        ),
        UniqueConstraint(
            "binding_id",
            name="uq_wf_physical_route_binding_claim_binding",
        ),
        UniqueConstraint(
            "canonical_digest",
            name="uq_wf_physical_route_binding_claim_digest",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    idempotency_scope_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    binding_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_physical_transport_route_bindings.binding_id"),
        nullable=False,
        index=True,
    )
    logical_channel_binding_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_channel_bindings.binding_id"), nullable=False, index=True
    )
    transport_compatibility_admission_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_transport_compatibility_admissions.compatibility_admission_id"),
        nullable=False,
        index=True,
    )
    transport_profile_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("event_transport_profile_snapshots.snapshot_id"), nullable=False, index=True
    )
    transport_route_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("event_transport_route_snapshots.snapshot_id"), nullable=False, index=True
    )
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    binder_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventPhysicalTransportCredentialAssignmentBindingModel(Base):
    __tablename__ = "workflow_event_physical_transport_credential_bindings"
    __table_args__ = (
        UniqueConstraint(
            "physical_transport_route_binding_id",
            "credential_assignment_snapshot_id",
            name="uq_wf_transport_credential_binding_pair",
        ),
        UniqueConstraint(
            "canonical_digest",
            name="uq_wf_transport_credential_binding_digest",
        ),
        CheckConstraint(
            "state = 'bound'",
            name="ck_wf_transport_credential_binding_state",
        ),
        CheckConstraint(
            "NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT endpoint_resolution_authority_granted "
            "AND NOT protected_artifact_access_authority_granted "
            "AND NOT credential_selection_authority_granted "
            "AND NOT credential_assignment_binding_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT credential_brokerage_authority_granted "
            "AND NOT credential_resolution_authority_granted "
            "AND NOT credential_delivery_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted "
            "AND NOT infrastructure_mutation_authority_granted",
            name="ck_wf_transport_credential_binding_zero_auth",
        ),
    )

    binding_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    physical_transport_route_binding_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_physical_transport_route_bindings.binding_id"),
        nullable=False,
        index=True,
    )
    physical_transport_route_binding_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    transport_route_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("event_transport_route_snapshots.snapshot_id"), nullable=False, index=True
    )
    transport_route_snapshot_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    credential_assignment_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("event_transport_credential_assignment_snapshots.snapshot_id"),
        nullable=False,
        index=True,
    )
    credential_assignment_snapshot_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    binder_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    bound_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    route_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_binding_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    endpoint_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    protected_artifact_access_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_assignment_binding_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_brokerage_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    readiness_probe_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    infrastructure_mutation_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventPhysicalTransportCredentialAssignmentBindingClaimModel(Base):
    __tablename__ = "workflow_event_physical_transport_credential_binding_claims"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_transport_credential_claim_scope_idem",
        ),
        UniqueConstraint(
            "binding_id",
            name="uq_wf_transport_credential_claim_binding",
        ),
        UniqueConstraint(
            "canonical_digest",
            name="uq_wf_transport_credential_claim_digest",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    idempotency_scope_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    binding_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_physical_transport_credential_bindings.binding_id"),
        nullable=False,
        index=True,
    )
    physical_transport_route_binding_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_physical_transport_route_bindings.binding_id"),
        nullable=False,
        index=True,
    )
    transport_route_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("event_transport_route_snapshots.snapshot_id"), nullable=False, index=True
    )
    credential_assignment_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("event_transport_credential_assignment_snapshots.snapshot_id"),
        nullable=False,
        index=True,
    )
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    binder_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventPhysicalTransportCredentialAssignmentFreshnessAdmissionModel(Base):
    __tablename__ = "workflow_event_transport_credential_freshness_admissions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["assignment_id", "assignment_revision"],
            [
                "deployment_event_transport_credential_assignments.assignment_id",
                "deployment_event_transport_credential_assignments.assignment_revision",
            ],
            name="fk_wf_cred_fresh_assignment",
        ),
        UniqueConstraint("canonical_digest", name="uq_wf_cred_fresh_digest"),
        CheckConstraint(
            "credential_generation > 0 AND rotation_epoch > 0",
            name="ck_wf_cred_fresh_rank",
        ),
        CheckConstraint("state = 'admitted_current'", name="ck_wf_cred_fresh_state"),
        CheckConstraint(
            "assignment_activated_at <= evaluated_at "
            "AND evaluated_at < valid_until "
            "AND valid_until <= assignment_expires_at "
            "AND valid_until <= evaluated_at + INTERVAL '60 seconds'",
            name="ck_wf_cred_fresh_window",
        ),
        CheckConstraint(
            "assignment_active AND assignment_non_revoked",
            name="ck_wf_cred_fresh_lifecycle",
        ),
        CheckConstraint(
            "NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT endpoint_resolution_authority_granted "
            "AND NOT protected_artifact_access_authority_granted "
            "AND NOT credential_selection_authority_granted "
            "AND NOT credential_assignment_binding_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT credential_brokerage_authority_granted "
            "AND NOT credential_resolution_authority_granted "
            "AND NOT credential_delivery_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted "
            "AND NOT infrastructure_mutation_authority_granted",
            name="ck_wf_cred_fresh_zero_auth",
        ),
    )

    freshness_admission_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    credential_assignment_binding_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_physical_transport_credential_bindings.binding_id"),
        nullable=False,
        index=True,
    )
    credential_assignment_binding_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    credential_assignment_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("event_transport_credential_assignment_snapshots.snapshot_id"),
        nullable=False,
        index=True,
    )
    credential_assignment_snapshot_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    assignment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    assignment_revision: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_assignment_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    credential_generation: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    rotation_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    assignment_activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    assignment_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    assignment_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    assignment_non_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    admitter_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    route_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_binding_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    endpoint_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    protected_artifact_access_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_assignment_binding_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_brokerage_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    readiness_probe_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    infrastructure_mutation_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventPhysicalTransportCredentialAssignmentFreshnessClaimModel(Base):
    __tablename__ = "workflow_event_transport_credential_freshness_claims"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_cred_fresh_claim_scope_idem",
        ),
        UniqueConstraint(
            "freshness_admission_id",
            name="uq_wf_cred_fresh_claim_admission",
        ),
        UniqueConstraint("canonical_digest", name="uq_wf_cred_fresh_claim_digest"),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    idempotency_scope_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    freshness_admission_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_transport_credential_freshness_admissions.freshness_admission_id"
        ),
        nullable=False,
        index=True,
    )
    credential_assignment_binding_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_physical_transport_credential_bindings.binding_id"),
        nullable=False,
        index=True,
    )
    credential_assignment_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("event_transport_credential_assignment_snapshots.snapshot_id"),
        nullable=False,
        index=True,
    )
    assignment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    assignment_revision: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    admitter_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventPhysicalTransportCredentialAccessAuthorizationLeaseModel(Base):
    __tablename__ = "workflow_event_transport_credential_access_authorization_leases"
    __table_args__ = (
        ForeignKeyConstraint(
            ["assignment_id", "assignment_revision"],
            [
                "deployment_event_transport_credential_assignments.assignment_id",
                "deployment_event_transport_credential_assignments.assignment_revision",
            ],
            name="fk_wf_cred_access_lease_assignment",
        ),
        UniqueConstraint("freshness_admission_id", name="uq_wf_cred_access_lease_freshness"),
        UniqueConstraint("canonical_digest", name="uq_wf_cred_access_lease_digest"),
        CheckConstraint(
            "credential_generation > 0 AND rotation_epoch > 0",
            name="ck_wf_cred_access_lease_rank",
        ),
        CheckConstraint("state = 'authorized_unconsumed'", name="ck_wf_cred_access_lease_state"),
        CheckConstraint(
            "assignment_activated_at <= issued_at "
            "AND issued_at < valid_until "
            "AND valid_until = issued_at + INTERVAL '15 seconds' "
            "AND valid_until <= assignment_expires_at",
            name="ck_wf_cred_access_lease_window",
        ),
        CheckConstraint(
            "assignment_active AND assignment_non_revoked",
            name="ck_wf_cred_access_lease_lifecycle",
        ),
        CheckConstraint(
            "NOT endpoint_resolution_authority_granted "
            "AND NOT protected_artifact_access_authority_granted "
            "AND NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT credential_selection_authority_granted "
            "AND NOT credential_assignment_binding_authority_granted "
            "AND credential_access_authority_granted "
            "AND NOT credential_brokerage_authority_granted "
            "AND NOT credential_resolution_authority_granted "
            "AND NOT credential_delivery_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted "
            "AND NOT infrastructure_mutation_authority_granted",
            name="ck_wf_cred_access_lease_authority",
        ),
    )

    authorization_lease_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    freshness_admission_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_transport_credential_freshness_admissions.freshness_admission_id"
        ),
        nullable=False,
        index=True,
    )
    freshness_admission_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    credential_assignment_binding_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_physical_transport_credential_bindings.binding_id"),
        nullable=False,
        index=True,
    )
    credential_assignment_binding_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    credential_assignment_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("event_transport_credential_assignment_snapshots.snapshot_id"),
        nullable=False,
        index=True,
    )
    credential_assignment_snapshot_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    assignment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    assignment_revision: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_assignment_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    credential_generation: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    rotation_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    assignment_activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    assignment_expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    assignment_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    assignment_non_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    accessor_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    endpoint_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    protected_artifact_access_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    route_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_binding_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_assignment_binding_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_brokerage_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    readiness_probe_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    infrastructure_mutation_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventPhysicalTransportCredentialAccessAuthorizationClaimModel(Base):
    __tablename__ = "workflow_event_transport_credential_access_authorization_claims"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_scope_id", "idempotency_key", name="uq_wf_cred_access_claim_idem"
        ),
        UniqueConstraint("authorization_lease_id", name="uq_wf_cred_access_claim_lease"),
        UniqueConstraint("canonical_digest", name="uq_wf_cred_access_claim_digest"),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    idempotency_scope_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    authorization_lease_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_transport_credential_access_authorization_leases.authorization_lease_id"
        ),
        nullable=False,
        index=True,
    )
    freshness_admission_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_transport_credential_freshness_admissions.freshness_admission_id"
        ),
        nullable=False,
        index=True,
    )
    assignment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    assignment_revision: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    accessor_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventPhysicalTransportCredentialAccessLeaseConsumptionClaimModel(Base):
    __tablename__ = "workflow_event_credential_access_lease_consumption_claims"
    __table_args__ = (
        UniqueConstraint("authorization_lease_id", name="uq_wf_credential_consume_claim_lease"),
        UniqueConstraint("attempt_id", name="uq_wf_credential_consume_claim_attempt"),
        UniqueConstraint(
            "materialization_id", name="uq_wf_credential_consume_claim_materialization"
        ),
        UniqueConstraint("idempotency_digest", name="uq_wf_credential_consume_claim_idempotency"),
        UniqueConstraint("canonical_digest", name="uq_wf_credential_consume_claim_digest"),
        CheckConstraint(
            "NOT endpoint_resolution_authority_granted "
            "AND NOT protected_artifact_access_authority_granted "
            "AND NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT credential_selection_authority_granted "
            "AND NOT credential_assignment_binding_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT credential_brokerage_authority_granted "
            "AND NOT credential_resolution_authority_granted "
            "AND NOT credential_delivery_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted "
            "AND NOT infrastructure_mutation_authority_granted",
            name="ck_wf_credential_consume_claim_zero_auth",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    authorization_lease_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_transport_credential_access_authorization_leases.authorization_lease_id"
        ),
        nullable=False,
        index=True,
    )
    authorization_lease_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    freshness_admission_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_transport_credential_freshness_admissions.freshness_admission_id"
        ),
        nullable=False,
        index=True,
    )
    freshness_admission_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    attempt_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    materialization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    accessor_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    endpoint_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    protected_artifact_access_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    route_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_binding_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_assignment_binding_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_brokerage_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    readiness_probe_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    infrastructure_mutation_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventPhysicalTransportCredentialMaterializationAttemptModel(Base):
    __tablename__ = "workflow_event_credential_materialization_attempts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["assignment_id", "assignment_revision"],
            [
                "deployment_event_transport_credential_assignments.assignment_id",
                "deployment_event_transport_credential_assignments.assignment_revision",
            ],
            name="fk_wf_credential_mat_attempt_assignment",
        ),
        UniqueConstraint("materialization_id", name="uq_wf_credential_mat_attempt_materialization"),
        UniqueConstraint("consumption_claim_id", name="uq_wf_credential_mat_attempt_claim"),
        UniqueConstraint("authorization_lease_id", name="uq_wf_credential_mat_attempt_lease"),
        UniqueConstraint("canonical_digest", name="uq_wf_credential_mat_attempt_digest"),
        CheckConstraint(
            "state = 'materialization_started'", name="ck_wf_credential_mat_attempt_state"
        ),
        CheckConstraint(
            "started_at < freshness_valid_until AND started_at < lease_valid_until",
            name="ck_wf_credential_mat_attempt_window",
        ),
        CheckConstraint(
            "credential_generation > 0 AND rotation_epoch > 0",
            name="ck_wf_credential_mat_attempt_rank",
        ),
        CheckConstraint(
            "NOT endpoint_resolution_authority_granted "
            "AND NOT protected_artifact_access_authority_granted "
            "AND NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT credential_selection_authority_granted "
            "AND NOT credential_assignment_binding_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT credential_brokerage_authority_granted "
            "AND NOT credential_resolution_authority_granted "
            "AND NOT credential_delivery_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted "
            "AND NOT infrastructure_mutation_authority_granted",
            name="ck_wf_credential_mat_attempt_zero_auth",
        ),
    )

    attempt_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    materialization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    consumption_claim_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_credential_access_lease_consumption_claims.claim_id"),
        nullable=False,
        index=True,
    )
    authorization_lease_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_transport_credential_access_authorization_leases.authorization_lease_id"
        ),
        nullable=False,
        index=True,
    )
    authorization_lease_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    freshness_admission_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_transport_credential_freshness_admissions.freshness_admission_id"
        ),
        nullable=False,
        index=True,
    )
    freshness_admission_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    physical_transport_credential_assignment_binding_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_physical_transport_credential_bindings.binding_id"),
        nullable=False,
        index=True,
    )
    physical_transport_credential_assignment_binding_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    credential_assignment_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("event_transport_credential_assignment_snapshots.snapshot_id"),
        nullable=False,
        index=True,
    )
    credential_assignment_snapshot_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    assignment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    assignment_revision: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_assignment_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    credential_generation: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    rotation_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    accessor_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    freshness_valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lease_valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    endpoint_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    protected_artifact_access_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    route_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_binding_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_assignment_binding_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_brokerage_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    readiness_probe_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    infrastructure_mutation_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventPhysicalTransportCredentialMaterializationResultModel(Base):
    __tablename__ = "workflow_event_credential_materialization_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["assignment_id", "assignment_revision"],
            [
                "deployment_event_transport_credential_assignments.assignment_id",
                "deployment_event_transport_credential_assignments.assignment_revision",
            ],
            name="fk_wf_credential_mat_result_assignment",
        ),
        UniqueConstraint("attempt_id", name="uq_wf_credential_mat_result_attempt"),
        UniqueConstraint("consumption_claim_id", name="uq_wf_credential_mat_result_claim"),
        UniqueConstraint("authorization_lease_id", name="uq_wf_credential_mat_result_lease"),
        UniqueConstraint("canonical_digest", name="uq_wf_credential_mat_result_digest"),
        CheckConstraint(
            "credential_generation > 0 AND rotation_epoch > 0",
            name="ck_wf_credential_mat_result_rank",
        ),
        CheckConstraint(
            "state IN ('materialized_protected', 'materialization_failed')",
            name="ck_wf_credential_mat_result_state",
        ),
        CheckConstraint(
            "(state = 'materialized_protected' "
            "AND protected_artifact_id IS NOT NULL "
            "AND protected_artifact_digest IS NOT NULL "
            "AND usable_until IS NOT NULL "
            "AND completed_at < usable_until "
            "AND NOT protected_artifact_revoked "
            "AND cleanup_confirmed "
            "AND failure_class IS NULL) "
            "OR (state = 'materialization_failed' "
            "AND protected_artifact_id IS NULL "
            "AND protected_artifact_digest IS NULL "
            "AND usable_until IS NULL "
            "AND protected_artifact_revoked "
            "AND cleanup_confirmed "
            "AND failure_class IS NOT NULL)",
            name="ck_wf_credential_mat_result_shape",
        ),
        CheckConstraint(
            "NOT endpoint_resolution_authority_granted "
            "AND NOT protected_artifact_access_authority_granted "
            "AND NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT credential_selection_authority_granted "
            "AND NOT credential_assignment_binding_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT credential_brokerage_authority_granted "
            "AND NOT credential_resolution_authority_granted "
            "AND NOT credential_delivery_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted "
            "AND NOT infrastructure_mutation_authority_granted",
            name="ck_wf_credential_mat_result_zero_auth",
        ),
    )

    materialization_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_credential_materialization_attempts.attempt_id"),
        nullable=False,
        index=True,
    )
    attempt_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    consumption_claim_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_credential_access_lease_consumption_claims.claim_id"),
        nullable=False,
        index=True,
    )
    consumption_claim_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    authorization_lease_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_transport_credential_access_authorization_leases.authorization_lease_id"
        ),
        nullable=False,
        index=True,
    )
    authorization_lease_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    freshness_admission_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_transport_credential_freshness_admissions.freshness_admission_id"
        ),
        nullable=False,
        index=True,
    )
    freshness_admission_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_assignment_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("event_transport_credential_assignment_snapshots.snapshot_id"),
        nullable=False,
        index=True,
    )
    credential_assignment_snapshot_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    assignment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    assignment_revision: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    credential_generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    rotation_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    accessor_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    materializer_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    materializer_version: Mapped[str] = mapped_column(String(64), nullable=False)
    materialization_receipt_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    failure_class: Mapped[str | None] = mapped_column(String(128), nullable=True)
    protected_artifact_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    protected_artifact_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    protected_artifact_schema_id: Mapped[str] = mapped_column(String(128), nullable=False)
    protected_artifact_schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    protected_artifact_profile_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    usable_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    protected_artifact_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    cleanup_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    endpoint_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    protected_artifact_access_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    route_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_binding_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_assignment_binding_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_brokerage_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    readiness_probe_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    infrastructure_mutation_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class DeploymentEventTransportRouteSelectionHeadModel(Base):
    __tablename__ = "deployment_event_transport_route_selection_heads"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "environment_id",
            "site_id",
            "route_set_id",
            name="uq_deploy_route_head_scope_set",
        ),
        CheckConstraint("generation > 0", name="ck_deploy_route_head_generation"),
        CheckConstraint("current", name="ck_deploy_route_head_current"),
    )

    head_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    route_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    route_set_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    selection_epoch_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    selection_epoch_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    selected_route_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    selected_route_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    selected_route_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    fencing_token_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    selection_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    selection_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    selection_suspended: Mapped[bool] = mapped_column(Boolean, nullable=False)
    selection_withdrawn: Mapped[bool] = mapped_column(Boolean, nullable=False)
    selection_superseded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    current: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class DeploymentEventTransportRouteSelectionHeadHistoryModel(Base):
    __tablename__ = "deployment_event_transport_route_selection_head_history"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "environment_id",
            "site_id",
            "route_set_id",
            "generation",
            name="uq_deploy_route_head_history_generation",
        ),
        UniqueConstraint(
            "canonical_digest",
            name="uq_deploy_route_head_history_digest",
        ),
        CheckConstraint("generation > 0", name="ck_deploy_route_head_hist_generation"),
        CheckConstraint("current", name="ck_deploy_route_head_hist_current"),
    )

    history_id: Mapped[str] = mapped_column(String(192), primary_key=True)
    head_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    route_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    route_set_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    selection_epoch_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    selection_epoch_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    selected_route_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    selected_route_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    selected_route_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    fencing_token_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    selection_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    selection_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    selection_suspended: Mapped[bool] = mapped_column(Boolean, nullable=False)
    selection_withdrawn: Mapped[bool] = mapped_column(Boolean, nullable=False)
    selection_superseded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    current: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventPhysicalTransportRouteFreshnessAdmissionModel(Base):
    __tablename__ = "workflow_event_physical_transport_route_freshness_admissions"
    __table_args__ = (
        UniqueConstraint(
            "physical_transport_route_binding_id",
            name="uq_wf_route_fresh_admission_binding",
        ),
        UniqueConstraint(
            "canonical_digest",
            name="uq_wf_route_fresh_admission_digest",
        ),
        CheckConstraint(
            "state = 'admitted_current'",
            name="ck_wf_route_fresh_admission_state",
        ),
        CheckConstraint(
            "selection_active AND selection_eligible "
            "AND NOT selection_suspended AND NOT selection_withdrawn "
            "AND NOT selection_superseded",
            name="ck_wf_route_fresh_admission_selection",
        ),
        CheckConstraint(
            "NOT endpoint_resolution_authority_granted "
            "AND NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted",
            name="ck_wf_route_fresh_admission_zero_auth",
        ),
        CheckConstraint(
            "current_selection_head_generation > 0",
            name="ck_wf_route_fresh_admission_generation",
        ),
        CheckConstraint(
            "valid_until > evaluated_at",
            name="ck_wf_route_fresh_admission_window",
        ),
    )

    freshness_admission_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    physical_transport_route_binding_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_physical_transport_route_bindings.binding_id"),
        nullable=False,
        index=True,
    )
    physical_transport_route_binding_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    transport_route_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("event_transport_route_snapshots.snapshot_id"), nullable=False, index=True
    )
    transport_route_snapshot_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    current_selection_head_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    current_selection_head_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    current_selection_head_generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    current_selection_head_fencing_token_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    route_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    route_set_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    selection_epoch_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    selection_epoch_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    selected_route_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    selected_route_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    selected_route_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    selection_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    selection_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    selection_suspended: Mapped[bool] = mapped_column(Boolean, nullable=False)
    selection_withdrawn: Mapped[bool] = mapped_column(Boolean, nullable=False)
    selection_superseded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    admitter_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    endpoint_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_binding_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    readiness_probe_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventPhysicalTransportRouteFreshnessAdmissionClaimModel(Base):
    __tablename__ = "workflow_event_route_freshness_admission_claims"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_route_fresh_claim_scope_idem",
        ),
        UniqueConstraint(
            "freshness_admission_id",
            name="uq_wf_route_fresh_claim_admission",
        ),
        UniqueConstraint(
            "canonical_digest",
            name="uq_wf_route_fresh_claim_digest",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    idempotency_scope_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    freshness_admission_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_physical_transport_route_freshness_admissions.freshness_admission_id"
        ),
        nullable=False,
        index=True,
    )
    physical_transport_route_binding_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_physical_transport_route_bindings.binding_id"),
        nullable=False,
        index=True,
    )
    transport_route_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("event_transport_route_snapshots.snapshot_id"), nullable=False, index=True
    )
    current_selection_head_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    current_selection_head_generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    current_selection_head_fencing_token_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    admitter_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseModel(Base):
    __tablename__ = "workflow_event_endpoint_resolution_authorization_leases"
    __table_args__ = (
        UniqueConstraint(
            "freshness_admission_id",
            name="uq_wf_endpoint_res_lease_freshness",
        ),
        UniqueConstraint(
            "canonical_digest",
            name="uq_wf_endpoint_res_lease_digest",
        ),
        CheckConstraint(
            "state = 'authorized_unconsumed'",
            name="ck_wf_endpoint_res_lease_state",
        ),
        CheckConstraint(
            "valid_until = issued_at + INTERVAL '15 seconds'",
            name="ck_wf_endpoint_res_lease_window",
        ),
        CheckConstraint(
            "endpoint_resolution_authority_granted "
            "AND NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted",
            name="ck_wf_endpoint_res_lease_authority",
        ),
        CheckConstraint(
            "current_selection_head_generation > 0",
            name="ck_wf_endpoint_res_lease_generation",
        ),
        CheckConstraint(
            "selection_active AND selection_eligible "
            "AND NOT selection_suspended AND NOT selection_withdrawn "
            "AND NOT selection_superseded",
            name="ck_wf_endpoint_res_lease_selection",
        ),
    )

    authorization_lease_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    freshness_admission_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_physical_transport_route_freshness_admissions.freshness_admission_id"
        ),
        nullable=False,
        index=True,
    )
    freshness_admission_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    physical_transport_route_binding_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_physical_transport_route_bindings.binding_id"),
        nullable=False,
        index=True,
    )
    physical_transport_route_binding_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    transport_route_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("event_transport_route_snapshots.snapshot_id"), nullable=False, index=True
    )
    transport_route_snapshot_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    current_selection_head_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    current_selection_head_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    current_selection_head_generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    current_selection_head_fencing_token_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    route_set_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    route_set_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    selection_epoch_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    selection_epoch_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    selected_route_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    selected_route_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    selected_route_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    selection_active: Mapped[bool] = mapped_column(Boolean, nullable=False)
    selection_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False)
    selection_suspended: Mapped[bool] = mapped_column(Boolean, nullable=False)
    selection_withdrawn: Mapped[bool] = mapped_column(Boolean, nullable=False)
    selection_superseded: Mapped[bool] = mapped_column(Boolean, nullable=False)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resolver_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    endpoint_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_binding_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    readiness_probe_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventPhysicalTransportEndpointResolutionAuthorizationLeaseClaimModel(Base):
    __tablename__ = "workflow_event_endpoint_resolution_authorization_lease_claims"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_endpoint_res_claim_scope_idem",
        ),
        UniqueConstraint(
            "authorization_lease_id",
            name="uq_wf_endpoint_res_claim_lease",
        ),
        UniqueConstraint(
            "canonical_digest",
            name="uq_wf_endpoint_res_claim_digest",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    idempotency_scope_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    authorization_lease_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_endpoint_resolution_authorization_leases.authorization_lease_id"
        ),
        nullable=False,
        index=True,
    )
    freshness_admission_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_physical_transport_route_freshness_admissions.freshness_admission_id"
        ),
        nullable=False,
        index=True,
    )
    physical_transport_route_binding_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_physical_transport_route_bindings.binding_id"),
        nullable=False,
        index=True,
    )
    transport_route_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("event_transport_route_snapshots.snapshot_id"), nullable=False, index=True
    )
    current_selection_head_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    current_selection_head_generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    current_selection_head_fencing_token_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resolver_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventPhysicalTransportEndpointResolutionLeaseConsumptionClaimModel(Base):
    __tablename__ = "workflow_event_endpoint_resolution_lease_consumption_claims"
    __table_args__ = (
        UniqueConstraint("authorization_lease_id", name="uq_wf_endpoint_consume_claim_lease"),
        UniqueConstraint("attempt_id", name="uq_wf_endpoint_consume_claim_attempt"),
        UniqueConstraint("materialization_id", name="uq_wf_endpoint_consume_claim_materialization"),
        UniqueConstraint("idempotency_digest", name="uq_wf_endpoint_consume_claim_idempotency"),
        UniqueConstraint("canonical_digest", name="uq_wf_endpoint_consume_claim_digest"),
        CheckConstraint(
            "NOT endpoint_resolution_authority_granted "
            "AND NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted",
            name="ck_wf_endpoint_consume_claim_zero_auth",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    authorization_lease_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_endpoint_resolution_authorization_leases.authorization_lease_id"
        ),
        nullable=False,
        index=True,
    )
    authorization_lease_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_endpoint_materialization_attempts.attempt_id",
            deferrable=True,
            initially="DEFERRED",
        ),
        nullable=False,
        index=True,
    )
    materialization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    freshness_admission_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_physical_transport_route_freshness_admissions.freshness_admission_id"
        ),
        nullable=False,
        index=True,
    )
    freshness_admission_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resolver_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    endpoint_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_binding_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    readiness_probe_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventPhysicalTransportEndpointMaterializationAttemptModel(Base):
    __tablename__ = "workflow_event_endpoint_materialization_attempts"
    __table_args__ = (
        UniqueConstraint("materialization_id", name="uq_wf_endpoint_mat_attempt_materialization"),
        UniqueConstraint("consumption_claim_id", name="uq_wf_endpoint_mat_attempt_claim"),
        UniqueConstraint("authorization_lease_id", name="uq_wf_endpoint_mat_attempt_lease"),
        UniqueConstraint("canonical_digest", name="uq_wf_endpoint_mat_attempt_digest"),
        CheckConstraint(
            "state = 'materialization_started'", name="ck_wf_endpoint_mat_attempt_state"
        ),
        CheckConstraint(
            "started_at < freshness_valid_until AND started_at < lease_valid_until",
            name="ck_wf_endpoint_mat_attempt_window",
        ),
        CheckConstraint(
            "current_selection_head_generation > 0",
            name="ck_wf_endpoint_mat_attempt_generation",
        ),
        CheckConstraint(
            "NOT endpoint_resolution_authority_granted "
            "AND NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted",
            name="ck_wf_endpoint_mat_attempt_zero_auth",
        ),
    )

    attempt_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    materialization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    consumption_claim_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_endpoint_resolution_lease_consumption_claims.claim_id"),
        nullable=False,
        index=True,
    )
    authorization_lease_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_endpoint_resolution_authorization_leases.authorization_lease_id"
        ),
        nullable=False,
        index=True,
    )
    authorization_lease_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    freshness_admission_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_physical_transport_route_freshness_admissions.freshness_admission_id"
        ),
        nullable=False,
        index=True,
    )
    freshness_admission_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    physical_transport_route_binding_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_physical_transport_route_bindings.binding_id"),
        nullable=False,
        index=True,
    )
    physical_transport_route_binding_digest: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    transport_route_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("event_transport_route_snapshots.snapshot_id"), nullable=False, index=True
    )
    transport_route_snapshot_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    current_selection_head_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    current_selection_head_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    current_selection_head_generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    current_selection_head_fencing_token_digest: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resolver_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    freshness_valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    lease_valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    endpoint_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_binding_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    readiness_probe_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventPhysicalTransportEndpointMaterializationResultModel(Base):
    __tablename__ = "workflow_event_endpoint_materialization_results"
    __table_args__ = (
        UniqueConstraint("attempt_id", name="uq_wf_endpoint_mat_result_attempt"),
        UniqueConstraint("consumption_claim_id", name="uq_wf_endpoint_mat_result_claim"),
        UniqueConstraint("authorization_lease_id", name="uq_wf_endpoint_mat_result_lease"),
        UniqueConstraint("canonical_digest", name="uq_wf_endpoint_mat_result_digest"),
        CheckConstraint(
            "state IN ('materialized_protected', 'materialization_failed')",
            name="ck_wf_endpoint_mat_result_state",
        ),
        CheckConstraint(
            "(state = 'materialized_protected' "
            "AND protected_artifact_id IS NOT NULL "
            "AND protected_artifact_digest IS NOT NULL "
            "AND normalized_endpoint_set_digest IS NOT NULL "
            "AND endpoint_count > 0 "
            "AND usable_until IS NOT NULL "
            "AND completed_at < usable_until "
            "AND NOT protected_artifact_revoked "
            "AND cleanup_confirmed "
            "AND failure_class IS NULL) "
            "OR (state = 'materialization_failed' "
            "AND protected_artifact_id IS NULL "
            "AND protected_artifact_digest IS NULL "
            "AND normalized_endpoint_set_digest IS NULL "
            "AND endpoint_count = 0 "
            "AND usable_until IS NULL "
            "AND protected_artifact_revoked "
            "AND cleanup_confirmed "
            "AND failure_class IS NOT NULL)",
            name="ck_wf_endpoint_mat_result_shape",
        ),
        CheckConstraint(
            "NOT endpoint_resolution_authority_granted "
            "AND NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted",
            name="ck_wf_endpoint_mat_result_zero_auth",
        ),
    )

    materialization_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_endpoint_materialization_attempts.attempt_id"),
        nullable=False,
        index=True,
    )
    attempt_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    consumption_claim_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_endpoint_resolution_lease_consumption_claims.claim_id"),
        nullable=False,
        index=True,
    )
    consumption_claim_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    authorization_lease_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_endpoint_resolution_authorization_leases.authorization_lease_id"
        ),
        nullable=False,
        index=True,
    )
    authorization_lease_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    freshness_admission_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_physical_transport_route_freshness_admissions.freshness_admission_id"
        ),
        nullable=False,
        index=True,
    )
    freshness_admission_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    transport_route_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("event_transport_route_snapshots.snapshot_id"), nullable=False, index=True
    )
    transport_route_snapshot_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    resolver_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    failure_class: Mapped[str | None] = mapped_column(String(128), nullable=True)
    protected_artifact_id: Mapped[str | None] = mapped_column(
        String(128), nullable=True, index=True
    )
    protected_artifact_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    normalized_endpoint_set_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    endpoint_count: Mapped[int] = mapped_column(Integer, nullable=False)
    materializer_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    materializer_version: Mapped[str] = mapped_column(String(64), nullable=False)
    materialization_receipt_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    protected_artifact_schema_id: Mapped[str] = mapped_column(String(128), nullable=False)
    protected_artifact_schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    protected_artifact_profile_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    usable_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    protected_artifact_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    cleanup_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    endpoint_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_binding_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    readiness_probe_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventPhysicalTransportTargetContextBindingModel(Base):
    __tablename__ = "workflow_event_transport_target_context_bindings"
    __table_args__ = (
        UniqueConstraint(
            "endpoint_materialization_id",
            name="uq_wf_tctx_bind_endpoint",
        ),
        UniqueConstraint(
            "credential_materialization_id",
            name="uq_wf_tctx_bind_credential",
        ),
        UniqueConstraint(
            "endpoint_materialization_id",
            "credential_materialization_id",
            name="uq_wf_tctx_bind_pair",
        ),
        UniqueConstraint("canonical_digest", name="uq_wf_tctx_bind_digest"),
        CheckConstraint("state = 'bound'", name="ck_wf_tctx_bind_state"),
        CheckConstraint(
            "bound_at < joint_usable_until",
            name="ck_wf_tctx_bind_window",
        ),
        CheckConstraint(
            "NOT endpoint_resolution_authority_granted "
            "AND NOT protected_artifact_access_authority_granted "
            "AND NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT credential_selection_authority_granted "
            "AND NOT credential_assignment_binding_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT credential_brokerage_authority_granted "
            "AND NOT credential_resolution_authority_granted "
            "AND NOT credential_delivery_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted "
            "AND NOT infrastructure_mutation_authority_granted",
            name="ck_wf_tctx_bind_zero_auth",
        ),
        Index("ix_wf_tctx_bind_route", "physical_transport_route_binding_id"),
        Index("ix_wf_tctx_bind_snapshot", "transport_route_snapshot_id"),
        Index("ix_wf_tctx_bind_endpoint", "endpoint_materialization_id"),
        Index(
            "ix_wf_tctx_bind_cred_binding",
            "physical_transport_credential_assignment_binding_id",
        ),
        Index("ix_wf_tctx_bind_cred_snapshot", "credential_assignment_snapshot_id"),
        Index("ix_wf_tctx_bind_cred_result", "credential_materialization_id"),
        Index("ix_wf_tctx_bind_policy", "policy_digest"),
        Index(
            "ix_wf_tctx_bind_scope",
            "organization_id",
            "environment_id",
            "site_id",
        ),
        Index("ix_wf_tctx_bind_binder", "binder_subject_id"),
        Index("ix_wf_tctx_bind_joint_until", "joint_usable_until"),
    )

    binding_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    physical_transport_route_binding_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_physical_transport_route_bindings.binding_id",
            name="fk_wf_tctx_bind_route_binding",
        ),
        nullable=False,
    )
    physical_transport_route_binding_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    transport_route_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey(
            "event_transport_route_snapshots.snapshot_id",
            name="fk_wf_tctx_bind_route_snapshot",
        ),
        nullable=False,
    )
    transport_route_snapshot_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    endpoint_materialization_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_endpoint_materialization_results.materialization_id",
            name="fk_wf_tctx_bind_endpoint_result",
        ),
        nullable=False,
    )
    endpoint_materialization_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    physical_transport_credential_assignment_binding_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_physical_transport_credential_bindings.binding_id",
            name="fk_wf_tctx_bind_cred_binding",
        ),
        nullable=False,
    )
    physical_transport_credential_assignment_binding_digest: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    credential_assignment_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey(
            "event_transport_credential_assignment_snapshots.snapshot_id",
            name="fk_wf_tctx_bind_cred_snapshot",
        ),
        nullable=False,
    )
    credential_assignment_snapshot_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_materialization_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_credential_materialization_results.materialization_id",
            name="fk_wf_tctx_bind_cred_result",
        ),
        nullable=False,
    )
    credential_materialization_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    resolver_subject_id: Mapped[str] = mapped_column(String(240), nullable=False)
    accessor_subject_id: Mapped[str] = mapped_column(String(240), nullable=False)
    target_context_schema_id: Mapped[str] = mapped_column(String(128), nullable=False)
    target_context_schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    target_context_commitment: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False)
    binder_subject_id: Mapped[str] = mapped_column(String(240), nullable=False)
    bound_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    joint_usable_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    endpoint_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    protected_artifact_access_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    route_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_binding_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_assignment_binding_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_brokerage_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    readiness_probe_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    infrastructure_mutation_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventPhysicalTransportTargetContextBindingClaimModel(Base):
    __tablename__ = "workflow_event_transport_target_context_binding_claims"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_tctx_claim_scope_idem",
        ),
        UniqueConstraint(
            "organization_id",
            "environment_id",
            "site_id",
            "binder_subject_id",
            "idempotency_key",
            name="uq_wf_tctx_claim_binder_idem",
        ),
        UniqueConstraint("binding_id", name="uq_wf_tctx_claim_binding"),
        UniqueConstraint("canonical_digest", name="uq_wf_tctx_claim_digest"),
        Index("ix_wf_tctx_claim_route", "physical_transport_route_binding_id"),
        Index("ix_wf_tctx_claim_snapshot", "transport_route_snapshot_id"),
        Index("ix_wf_tctx_claim_endpoint", "endpoint_materialization_id"),
        Index(
            "ix_wf_tctx_claim_cred_binding",
            "physical_transport_credential_assignment_binding_id",
        ),
        Index("ix_wf_tctx_claim_cred_snapshot", "credential_assignment_snapshot_id"),
        Index("ix_wf_tctx_claim_cred_result", "credential_materialization_id"),
        Index("ix_wf_tctx_claim_policy", "policy_digest"),
        Index("ix_wf_tctx_claim_created", "created_at"),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    idempotency_scope_id: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    binding_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_transport_target_context_bindings.binding_id",
            name="fk_wf_tctx_claim_binding",
        ),
        nullable=False,
    )
    physical_transport_route_binding_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_physical_transport_route_bindings.binding_id",
            name="fk_wf_tctx_claim_route_binding",
        ),
        nullable=False,
    )
    transport_route_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey(
            "event_transport_route_snapshots.snapshot_id",
            name="fk_wf_tctx_claim_route_snapshot",
        ),
        nullable=False,
    )
    endpoint_materialization_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_endpoint_materialization_results.materialization_id",
            name="fk_wf_tctx_claim_endpoint_result",
        ),
        nullable=False,
    )
    physical_transport_credential_assignment_binding_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_physical_transport_credential_bindings.binding_id",
            name="fk_wf_tctx_claim_cred_binding",
        ),
        nullable=False,
    )
    credential_assignment_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey(
            "event_transport_credential_assignment_snapshots.snapshot_id",
            name="fk_wf_tctx_claim_cred_snapshot",
        ),
        nullable=False,
    )
    credential_materialization_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_credential_materialization_results.materialization_id",
            name="fk_wf_tctx_claim_cred_result",
        ),
        nullable=False,
    )
    target_context_schema_id: Mapped[str] = mapped_column(String(128), nullable=False)
    target_context_schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False)
    binder_subject_id: Mapped[str] = mapped_column(String(240), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventPhysicalTransportTargetContextAccessAuthorizationLeaseModel(Base):
    __tablename__ = "workflow_event_tctx_access_authorization_leases"
    __table_args__ = (
        UniqueConstraint("target_context_binding_id", name="uq_wf_tctx_access_lease_binding"),
        UniqueConstraint("canonical_digest", name="uq_wf_tctx_access_lease_digest"),
        CheckConstraint("state = 'authorized_unconsumed'", name="ck_wf_tctx_access_lease_state"),
        CheckConstraint(
            "single_use AND NOT renewable AND NOT transferable",
            name="ck_wf_tctx_access_lease_lifecycle",
        ),
        CheckConstraint(
            "issued_at < valid_until "
            "AND valid_until = issued_at + INTERVAL '5 seconds' "
            "AND valid_until <= joint_usable_until "
            "AND valid_until <= endpoint_attestation_valid_until "
            "AND valid_until <= credential_attestation_valid_until",
            name="ck_wf_tctx_access_lease_window",
        ),
        CheckConstraint(
            "route_head_generation > 0 AND credential_generation > 0 AND rotation_epoch > 0",
            name="ck_wf_tctx_access_lease_ranks",
        ),
        CheckConstraint(
            "valid_until <= assignment_expires_at",
            name="ck_wf_tctx_access_lease_assignment_window",
        ),
        ForeignKeyConstraint(
            ["assignment_id", "assignment_revision"],
            [
                "deployment_event_transport_credential_assignments.assignment_id",
                "deployment_event_transport_credential_assignments.assignment_revision",
            ],
            name="fk_wf_tctx_access_lease_assignment",
        ),
        Index("ix_wf_tctx_access_lease_binding", "target_context_binding_id"),
        Index("ix_wf_tctx_access_lease_outbox", "outbox_entry_id"),
        Index("ix_wf_tctx_access_lease_route_head", "route_head_id"),
        Index("ix_wf_tctx_access_lease_route_generation", "route_head_generation"),
        Index("ix_wf_tctx_access_lease_assignment", "assignment_id"),
        Index("ix_wf_tctx_access_lease_credential_generation", "credential_generation"),
        Index("ix_wf_tctx_access_lease_rotation", "rotation_epoch"),
        Index("ix_wf_tctx_access_lease_evidence", "authorization_evidence_digest"),
        Index("ix_wf_tctx_access_lease_policy", "policy_digest"),
        Index("ix_wf_tctx_access_lease_org", "organization_id"),
        Index("ix_wf_tctx_access_lease_environment", "environment_id"),
        Index("ix_wf_tctx_access_lease_site", "site_id"),
        Index("ix_wf_tctx_access_lease_accessor", "accessor_subject_id"),
        Index("ix_wf_tctx_access_lease_valid_until", "valid_until"),
        Index("ix_wf_tctx_access_lease_state", "state"),
        CheckConstraint(
            "NOT endpoint_resolution_authority_granted "
            "AND protected_artifact_access_authority_granted "
            "AND NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT credential_selection_authority_granted "
            "AND NOT credential_assignment_binding_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT credential_brokerage_authority_granted "
            "AND NOT credential_resolution_authority_granted "
            "AND NOT credential_delivery_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted "
            "AND NOT infrastructure_mutation_authority_granted",
            name="ck_wf_tctx_access_lease_authority",
        ),
    )

    authorization_lease_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    target_context_binding_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_transport_target_context_bindings.binding_id",
            name="fk_wf_tctx_access_lease_binding",
        ),
        nullable=False,
    )
    target_context_binding_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    target_context_commitment: Mapped[str] = mapped_column(String(64), nullable=False)
    outbox_entry_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_dispatch_outbox_entries.outbox_entry_id",
            name="fk_wf_tctx_access_lease_outbox",
        ),
        nullable=False,
    )
    outbox_entry_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    route_head_id: Mapped[str] = mapped_column(String(128), nullable=False)
    route_head_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    route_head_generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    route_head_fencing_token_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    assignment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    assignment_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    assignment_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_generation: Mapped[int] = mapped_column(BigInteger, nullable=False)
    rotation_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False)
    assignment_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    authorization_evidence_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    endpoint_status_attestation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    endpoint_status_attestation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    endpoint_attestation_valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    endpoint_attestor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    endpoint_attestor_version: Mapped[str] = mapped_column(String(64), nullable=False)
    endpoint_signing_key_id: Mapped[str] = mapped_column(String(128), nullable=False)
    endpoint_signature_algorithm: Mapped[str] = mapped_column(String(64), nullable=False)
    endpoint_integrity_signature: Mapped[str] = mapped_column(String(2048), nullable=False)
    credential_status_attestation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    credential_status_attestation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_attestation_valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    credential_attestor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    credential_attestor_version: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_signing_key_id: Mapped[str] = mapped_column(String(128), nullable=False)
    credential_signature_algorithm: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_integrity_signature: Mapped[str] = mapped_column(String(2048), nullable=False)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False)
    accessor_subject_id: Mapped[str] = mapped_column(String(240), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    joint_usable_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    single_use: Mapped[bool] = mapped_column(Boolean, nullable=False)
    renewable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    transferable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    endpoint_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    protected_artifact_access_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    route_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_binding_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_assignment_binding_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_brokerage_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    readiness_probe_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    infrastructure_mutation_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    endpoint_attestation_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    credential_attestation_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    authorization_evidence_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventPhysicalTransportTargetContextAccessAuthorizationClaimModel(Base):
    __tablename__ = "workflow_event_tctx_access_authorization_claims"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_tctx_access_claim_idem",
        ),
        UniqueConstraint("authorization_lease_id", name="uq_wf_tctx_access_claim_lease"),
        UniqueConstraint("canonical_digest", name="uq_wf_tctx_access_claim_digest"),
        Index("ix_wf_tctx_access_claim_scope", "idempotency_scope_id"),
        Index("ix_wf_tctx_access_claim_lease", "authorization_lease_id"),
        Index("ix_wf_tctx_access_claim_binding", "target_context_binding_id"),
        Index("ix_wf_tctx_access_claim_policy", "policy_digest"),
        Index("ix_wf_tctx_access_claim_org", "organization_id"),
        Index("ix_wf_tctx_access_claim_environment", "environment_id"),
        Index("ix_wf_tctx_access_claim_site", "site_id"),
        Index("ix_wf_tctx_access_claim_accessor", "accessor_subject_id"),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    idempotency_scope_id: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    authorization_lease_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_tctx_access_authorization_leases.authorization_lease_id",
            name="fk_wf_tctx_access_claim_lease",
        ),
        nullable=False,
    )
    target_context_binding_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_transport_target_context_bindings.binding_id",
            name="fk_wf_tctx_access_claim_binding",
        ),
        nullable=False,
    )
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False)
    accessor_subject_id: Mapped[str] = mapped_column(String(240), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventPhysicalTransportTargetContextAccessConsumptionClaimModel(Base):
    __tablename__ = "workflow_event_tctx_access_consumption_claims"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_scope_id", "idempotency_key", name="uq_wf_tctx_open_claim_idem"
        ),
        UniqueConstraint("authorization_lease_id", name="uq_wf_tctx_open_claim_lease"),
        UniqueConstraint("attempt_id", name="uq_wf_tctx_open_claim_attempt"),
        UniqueConstraint("opening_id", name="uq_wf_tctx_open_claim_opening"),
        UniqueConstraint("canonical_digest", name="uq_wf_tctx_open_claim_digest"),
        UniqueConstraint(
            "claim_id",
            "authorization_lease_id",
            "attempt_id",
            "opening_id",
            "target_context_binding_id",
            "organization_id",
            "environment_id",
            "site_id",
            name="uq_wf_tctx_open_claim_lineage",
        ),
        CheckConstraint(
            "NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT endpoint_resolution_authority_granted "
            "AND NOT protected_artifact_access_authority_granted "
            "AND NOT credential_selection_authority_granted "
            "AND NOT credential_assignment_binding_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT credential_brokerage_authority_granted "
            "AND NOT credential_resolution_authority_granted "
            "AND NOT credential_delivery_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted "
            "AND NOT infrastructure_mutation_authority_granted",
            name="ck_wf_tctx_open_claim_authority",
        ),
        CheckConstraint(
            "char_length(consumption_authorization_audit_digest) = 64 "
            "AND consumption_authorization_audit_digest ~ '^[0-9a-f]{64}$' "
            "AND jsonb_typeof(consumption_authorization_audit_payload) = 'object' "
            "AND consumption_authorization_audit_payload <> '{}'::jsonb",
            name="ck_wf_tctx_open_claim_audit_digest",
        ),
        Index("ix_wf_tctx_open_claim_scope", "idempotency_scope_id"),
        Index("ix_wf_tctx_open_claim_lease", "authorization_lease_id"),
        Index("ix_wf_tctx_open_claim_binding", "target_context_binding_id"),
        Index("ix_wf_tctx_open_claim_subject", "accessor_subject_id"),
        Index("ix_wf_tctx_open_claim_time", "claimed_at"),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    idempotency_scope_id: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    authorization_lease_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_tctx_access_authorization_leases.authorization_lease_id",
            name="fk_wf_tctx_open_claim_lease",
        ),
        nullable=False,
    )
    authorization_lease_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    target_context_binding_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_transport_target_context_bindings.binding_id",
            name="fk_wf_tctx_open_claim_binding",
        ),
        nullable=False,
    )
    target_context_binding_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    target_context_commitment: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt_id: Mapped[str] = mapped_column(String(128), nullable=False)
    opening_id: Mapped[str] = mapped_column(String(128), nullable=False)
    authorization_evidence_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    consumption_authorization_audit_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False)
    accessor_subject_id: Mapped[str] = mapped_column(String(240), nullable=False)
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    route_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_binding_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    endpoint_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    protected_artifact_access_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_assignment_binding_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_brokerage_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    readiness_probe_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    infrastructure_mutation_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    authorization_evidence_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    consumption_authorization_audit_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False
    )


class WorkflowEventPhysicalTransportTargetContextArtifactOpeningAttemptModel(Base):
    __tablename__ = "workflow_event_tctx_artifact_opening_attempts"
    __table_args__ = (
        UniqueConstraint("opening_id", name="uq_wf_tctx_open_attempt_opening"),
        UniqueConstraint("consumption_claim_id", name="uq_wf_tctx_open_attempt_claim"),
        UniqueConstraint("authorization_lease_id", name="uq_wf_tctx_open_attempt_lease"),
        UniqueConstraint("canonical_digest", name="uq_wf_tctx_open_attempt_digest"),
        UniqueConstraint(
            "attempt_id",
            "consumption_claim_id",
            "authorization_lease_id",
            "opening_id",
            "target_context_binding_id",
            "organization_id",
            "environment_id",
            "site_id",
            name="uq_wf_tctx_open_attempt_lineage",
        ),
        ForeignKeyConstraint(
            [
                "consumption_claim_id",
                "authorization_lease_id",
                "attempt_id",
                "opening_id",
                "target_context_binding_id",
                "organization_id",
                "environment_id",
                "site_id",
            ],
            [
                "workflow_event_tctx_access_consumption_claims.claim_id",
                "workflow_event_tctx_access_consumption_claims.authorization_lease_id",
                "workflow_event_tctx_access_consumption_claims.attempt_id",
                "workflow_event_tctx_access_consumption_claims.opening_id",
                "workflow_event_tctx_access_consumption_claims.target_context_binding_id",
                "workflow_event_tctx_access_consumption_claims.organization_id",
                "workflow_event_tctx_access_consumption_claims.environment_id",
                "workflow_event_tctx_access_consumption_claims.site_id",
            ],
            name="fk_wf_tctx_open_attempt_claim_lineage",
        ),
        CheckConstraint("state = 'opening_started'", name="ck_wf_tctx_open_attempt_state"),
        CheckConstraint(
            "started_at < lease_valid_until "
            "AND started_at < joint_usable_until "
            "AND started_at < evidence_valid_until",
            name="ck_wf_tctx_open_attempt_window",
        ),
        CheckConstraint(
            "NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT endpoint_resolution_authority_granted "
            "AND NOT protected_artifact_access_authority_granted "
            "AND NOT credential_selection_authority_granted "
            "AND NOT credential_assignment_binding_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT credential_brokerage_authority_granted "
            "AND NOT credential_resolution_authority_granted "
            "AND NOT credential_delivery_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted "
            "AND NOT infrastructure_mutation_authority_granted",
            name="ck_wf_tctx_open_attempt_authority",
        ),
        Index("ix_wf_tctx_open_attempt_org", "organization_id"),
        Index("ix_wf_tctx_open_attempt_env", "environment_id"),
        Index("ix_wf_tctx_open_attempt_site", "site_id"),
        Index("ix_wf_tctx_open_attempt_binding", "target_context_binding_id"),
        Index("ix_wf_tctx_open_attempt_subject", "accessor_subject_id"),
        Index("ix_wf_tctx_open_attempt_started", "started_at"),
    )

    attempt_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    opening_id: Mapped[str] = mapped_column(String(128), nullable=False)
    consumption_claim_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_tctx_access_consumption_claims.claim_id",
            name="fk_wf_tctx_open_attempt_claim",
        ),
        nullable=False,
    )
    authorization_lease_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_tctx_access_authorization_leases.authorization_lease_id",
            name="fk_wf_tctx_open_attempt_lease",
        ),
        nullable=False,
    )
    authorization_lease_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    target_context_binding_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_transport_target_context_bindings.binding_id",
            name="fk_wf_tctx_open_attempt_binding",
        ),
        nullable=False,
    )
    target_context_binding_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    target_context_commitment: Mapped[str] = mapped_column(String(64), nullable=False)
    endpoint_materialization_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_endpoint_materialization_results.materialization_id",
            name="fk_wf_tctx_open_attempt_endpoint",
        ),
        nullable=False,
    )
    endpoint_materialization_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    endpoint_protected_artifact_id: Mapped[str] = mapped_column(String(128), nullable=False)
    endpoint_protected_artifact_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    endpoint_status_attestation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    endpoint_status_attestation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_materialization_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_credential_materialization_results.materialization_id",
            name="fk_wf_tctx_open_attempt_credential",
        ),
        nullable=False,
    )
    credential_materialization_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_protected_artifact_id: Mapped[str] = mapped_column(String(128), nullable=False)
    credential_protected_artifact_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    credential_status_attestation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    credential_status_attestation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_nonce_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    opener_contract_id: Mapped[str] = mapped_column(String(128), nullable=False)
    opener_attestor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False)
    accessor_subject_id: Mapped[str] = mapped_column(String(240), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lease_valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    joint_usable_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evidence_valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    route_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_binding_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    endpoint_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    protected_artifact_access_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_assignment_binding_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_brokerage_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    readiness_probe_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    infrastructure_mutation_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    endpoint_attestation_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    credential_attestation_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowEventPhysicalTransportTargetContextArtifactOpeningResultModel(Base):
    __tablename__ = "workflow_event_tctx_artifact_opening_results"
    __table_args__ = (
        UniqueConstraint("attempt_id", name="uq_wf_tctx_open_result_attempt"),
        UniqueConstraint("consumption_claim_id", name="uq_wf_tctx_open_result_claim"),
        UniqueConstraint("authorization_lease_id", name="uq_wf_tctx_open_result_lease"),
        UniqueConstraint("canonical_digest", name="uq_wf_tctx_open_result_digest"),
        ForeignKeyConstraint(
            [
                "attempt_id",
                "consumption_claim_id",
                "authorization_lease_id",
                "opening_id",
                "target_context_binding_id",
                "organization_id",
                "environment_id",
                "site_id",
            ],
            [
                "workflow_event_tctx_artifact_opening_attempts.attempt_id",
                "workflow_event_tctx_artifact_opening_attempts.consumption_claim_id",
                "workflow_event_tctx_artifact_opening_attempts.authorization_lease_id",
                "workflow_event_tctx_artifact_opening_attempts.opening_id",
                "workflow_event_tctx_artifact_opening_attempts.target_context_binding_id",
                "workflow_event_tctx_artifact_opening_attempts.organization_id",
                "workflow_event_tctx_artifact_opening_attempts.environment_id",
                "workflow_event_tctx_artifact_opening_attempts.site_id",
            ],
            name="fk_wf_tctx_open_result_attempt_lineage",
        ),
        CheckConstraint(
            "(state = 'opened_protected' AND failure_class IS NULL "
            "AND sealed_capsule_id IS NOT NULL AND sealed_capsule_digest IS NOT NULL "
            "AND usable_until IS NOT NULL AND completed_at < usable_until) OR "
            "(state = 'opening_failed' AND failure_class IS NOT NULL "
            "AND sealed_capsule_id IS NULL AND sealed_capsule_digest IS NULL "
            "AND usable_until IS NULL)",
            name="ck_wf_tctx_open_result_state",
        ),
        CheckConstraint(
            "NOT capsule_is_bearer_capability AND protected_sources_closed AND cleanup_confirmed",
            name="ck_wf_tctx_open_result_capsule",
        ),
        CheckConstraint(
            "NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT endpoint_resolution_authority_granted "
            "AND NOT protected_artifact_access_authority_granted "
            "AND NOT credential_selection_authority_granted "
            "AND NOT credential_assignment_binding_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT credential_brokerage_authority_granted "
            "AND NOT credential_resolution_authority_granted "
            "AND NOT credential_delivery_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted "
            "AND NOT infrastructure_mutation_authority_granted",
            name="ck_wf_tctx_open_result_authority",
        ),
        Index("ix_wf_tctx_open_result_org", "organization_id"),
        Index("ix_wf_tctx_open_result_env", "environment_id"),
        Index("ix_wf_tctx_open_result_site", "site_id"),
        Index("ix_wf_tctx_open_result_binding", "target_context_binding_id"),
        Index("ix_wf_tctx_open_result_subject", "accessor_subject_id"),
        Index("ix_wf_tctx_open_result_completed", "completed_at"),
        Index("ix_wf_tctx_open_result_state", "state"),
    )

    opening_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_tctx_artifact_opening_attempts.attempt_id",
            name="fk_wf_tctx_open_result_attempt",
        ),
        nullable=False,
    )
    attempt_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    consumption_claim_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_tctx_access_consumption_claims.claim_id",
            name="fk_wf_tctx_open_result_claim",
        ),
        nullable=False,
    )
    consumption_claim_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    authorization_lease_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_tctx_access_authorization_leases.authorization_lease_id",
            name="fk_wf_tctx_open_result_lease",
        ),
        nullable=False,
    )
    authorization_lease_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    target_context_binding_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_transport_target_context_bindings.binding_id",
            name="fk_wf_tctx_open_result_binding",
        ),
        nullable=False,
    )
    target_context_binding_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    target_context_commitment: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    opener_id: Mapped[str] = mapped_column(String(128), nullable=False)
    opener_version: Mapped[str] = mapped_column(String(64), nullable=False)
    opening_receipt_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    failure_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sealed_capsule_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sealed_capsule_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    capsule_is_bearer_capability: Mapped[bool] = mapped_column(Boolean, nullable=False)
    capsule_schema_id: Mapped[str] = mapped_column(String(128), nullable=False)
    capsule_schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False)
    accessor_subject_id: Mapped[str] = mapped_column(String(240), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    usable_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    protected_sources_closed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    cleanup_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_binding_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    endpoint_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    protected_artifact_access_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_assignment_binding_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_brokerage_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    readiness_probe_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    infrastructure_mutation_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowProtectedTransportTargetContextCapsuleConsumerBindingModel(Base):
    __tablename__ = "workflow_event_tctx_capsule_consumer_bindings"
    __table_args__ = (
        UniqueConstraint("opening_result_id", name="uq_wf_tctx_capsule_binding_opening"),
        UniqueConstraint("sealed_capsule_id", name="uq_wf_tctx_capsule_binding_capsule"),
        UniqueConstraint("canonical_digest", name="uq_wf_tctx_capsule_binding_digest"),
        UniqueConstraint(
            "outbox_entry_id",
            "event_id",
            "event_artifact_id",
            "consumer_subject_id",
            "consumer_contract_id",
            "consumer_contract_version",
            "purpose_id",
            name="uq_wf_tctx_capsule_binding_event_consumer",
        ),
        CheckConstraint("state = 'bound'", name="ck_wf_tctx_capsule_binding_state"),
        CheckConstraint(
            "bound_at < effective_until",
            name="ck_wf_tctx_capsule_binding_window",
        ),
        CheckConstraint(
            "NOT capsule_is_bearer_capability",
            name="ck_wf_tctx_capsule_binding_non_bearer",
        ),
        CheckConstraint(
            "consumer_subject_id = "
            "'service.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_audience = "
            "'audience.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_contract_id = "
            "'contract.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_contract_version = '1.0' "
            "AND purpose_id = "
            "'purpose.workflow-protected-transport-target-context-capsule-handoff-evaluation' "
            "AND policy_id = "
            "'policy.workflow-protected-transport-target-context-capsule-consumer-binding' "
            "AND policy_version = '1.0' "
            "AND policy_digest = "
            "'1f7d71594e9ffdc863626ef68e53e9cc0ff829a81511aaf52b7c2c7f82a85e8f' "
            "AND binder_subject_id = "
            "'service.workflow-protected-transport-target-context-capsule-binder' "
            "AND binder_audience = "
            "'audience.workflow-protected-transport-target-context-capsule-binder'",
            name="ck_wf_tctx_capsule_binding_contract",
        ),
        CheckConstraint(
            "NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT endpoint_resolution_authority_granted "
            "AND NOT protected_artifact_access_authority_granted "
            "AND NOT credential_selection_authority_granted "
            "AND NOT credential_assignment_binding_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT credential_brokerage_authority_granted "
            "AND NOT credential_resolution_authority_granted "
            "AND NOT credential_delivery_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted "
            "AND NOT infrastructure_mutation_authority_granted",
            name="ck_wf_tctx_capsule_binding_authority",
        ),
        Index("ix_wf_tctx_capsule_binding_scope", "organization_id", "environment_id", "site_id"),
        Index("ix_wf_tctx_capsule_binding_consumer", "consumer_subject_id"),
        Index("ix_wf_tctx_capsule_binding_outbox", "outbox_entry_id"),
        Index("ix_wf_tctx_capsule_binding_bound", "bound_at"),
    )

    binding_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    opening_result_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_tctx_artifact_opening_results.opening_id",
            name="fk_wf_tctx_capsule_binding_opening",
        ),
        nullable=False,
    )
    opening_result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    opening_attempt_id: Mapped[str] = mapped_column(String(128), nullable=False)
    opening_attempt_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    lease_consumption_claim_id: Mapped[str] = mapped_column(String(128), nullable=False)
    lease_consumption_claim_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    authorization_lease_id: Mapped[str] = mapped_column(String(128), nullable=False)
    authorization_lease_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    sealed_capsule_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sealed_capsule_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    capsule_schema_id: Mapped[str] = mapped_column(String(128), nullable=False)
    capsule_schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    capsule_is_bearer_capability: Mapped[bool] = mapped_column(Boolean, nullable=False)
    target_context_binding_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_transport_target_context_bindings.binding_id",
            name="fk_wf_tctx_capsule_binding_target_context",
        ),
        nullable=False,
    )
    target_context_binding_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    target_context_commitment: Mapped[str] = mapped_column(String(64), nullable=False)
    outbox_entry_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_dispatch_outbox_entries.outbox_entry_id",
            name="fk_wf_tctx_capsule_binding_outbox",
        ),
        nullable=False,
    )
    outbox_entry_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    event_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_dispatch_event_envelopes.event_id",
            name="fk_wf_tctx_capsule_binding_event",
        ),
        nullable=False,
    )
    event_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    event_artifact_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_byte_artifacts.artifact_id",
            name="fk_wf_tctx_capsule_binding_artifact",
        ),
        nullable=False,
    )
    event_artifact_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    logical_channel_binding_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_channel_bindings.binding_id",
            name="fk_wf_tctx_capsule_binding_logical",
        ),
        nullable=False,
    )
    logical_channel_binding_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    physical_transport_route_binding_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_physical_transport_route_bindings.binding_id",
            name="fk_wf_tctx_capsule_binding_route",
        ),
        nullable=False,
    )
    physical_transport_route_binding_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    transport_route_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey(
            "event_transport_route_snapshots.snapshot_id",
            name="fk_wf_tctx_capsule_binding_route_snapshot",
        ),
        nullable=False,
    )
    transport_route_snapshot_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    physical_transport_credential_assignment_binding_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_physical_transport_credential_bindings.binding_id",
            name="fk_wf_tctx_capsule_binding_credential",
        ),
        nullable=False,
    )
    physical_transport_credential_assignment_binding_digest: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
    credential_assignment_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey(
            "event_transport_credential_assignment_snapshots.snapshot_id",
            name="fk_wf_tctx_capsule_binding_credential_snapshot",
        ),
        nullable=False,
    )
    credential_assignment_snapshot_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    plan_id: Mapped[str] = mapped_column(String(128), nullable=False)
    plan_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    run_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    step_run_id: Mapped[str] = mapped_column(String(128), nullable=False)
    step_run_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    workflow_execution_attempt_id: Mapped[str] = mapped_column(String(128), nullable=False)
    workflow_execution_attempt_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    target_id: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False)
    consumer_subject_id: Mapped[str] = mapped_column(String(240), nullable=False)
    consumer_audience: Mapped[str] = mapped_column(String(240), nullable=False)
    consumer_contract_id: Mapped[str] = mapped_column(String(128), nullable=False)
    consumer_contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose_id: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False)
    binder_subject_id: Mapped[str] = mapped_column(String(240), nullable=False)
    binder_audience: Mapped[str] = mapped_column(String(240), nullable=False)
    bound_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    authorization_audit_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    route_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_binding_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    endpoint_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    protected_artifact_access_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_assignment_binding_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_brokerage_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    readiness_probe_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    infrastructure_mutation_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowProtectedTransportTargetContextCapsuleConsumerBindingClaimModel(Base):
    __tablename__ = "workflow_event_tctx_capsule_consumer_binding_claims"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_tctx_capsule_claim_scope_idem",
        ),
        UniqueConstraint("binding_id", name="uq_wf_tctx_capsule_claim_binding"),
        UniqueConstraint("canonical_digest", name="uq_wf_tctx_capsule_claim_digest"),
        CheckConstraint(
            "consumer_subject_id = "
            "'service.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_audience = "
            "'audience.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_contract_id = "
            "'contract.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_contract_version = '1.0' "
            "AND purpose_id = "
            "'purpose.workflow-protected-transport-target-context-capsule-handoff-evaluation' "
            "AND policy_id = "
            "'policy.workflow-protected-transport-target-context-capsule-consumer-binding' "
            "AND policy_version = '1.0' "
            "AND policy_digest = "
            "'1f7d71594e9ffdc863626ef68e53e9cc0ff829a81511aaf52b7c2c7f82a85e8f' "
            "AND binder_subject_id = "
            "'service.workflow-protected-transport-target-context-capsule-binder' "
            "AND binder_audience = "
            "'audience.workflow-protected-transport-target-context-capsule-binder'",
            name="ck_wf_tctx_capsule_claim_contract",
        ),
        CheckConstraint(
            "char_length(authorization_audit_digest) = 64 "
            "AND authorization_audit_digest ~ '^[0-9a-f]{64}$' "
            "AND jsonb_typeof(authorization_audit_payload) = 'object' "
            "AND authorization_audit_payload <> '{}'::jsonb",
            name="ck_wf_tctx_capsule_claim_audit",
        ),
        Index("ix_wf_tctx_capsule_claim_scope", "idempotency_scope_id"),
        Index("ix_wf_tctx_capsule_claim_opening", "opening_result_id"),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    idempotency_scope_id: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    binding_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_tctx_capsule_consumer_bindings.binding_id",
            name="fk_wf_tctx_capsule_claim_binding",
        ),
        nullable=False,
    )
    opening_result_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sealed_capsule_id: Mapped[str] = mapped_column(String(128), nullable=False)
    consumer_subject_id: Mapped[str] = mapped_column(String(240), nullable=False)
    consumer_audience: Mapped[str] = mapped_column(String(240), nullable=False)
    consumer_contract_id: Mapped[str] = mapped_column(String(128), nullable=False)
    consumer_contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose_id: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False)
    binder_subject_id: Mapped[str] = mapped_column(String(240), nullable=False)
    binder_audience: Mapped[str] = mapped_column(String(240), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    authorization_audit_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    authorization_audit_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationLeaseModel(Base):
    __tablename__ = "workflow_event_tctx_capsule_handoff_authorization_leases"
    __table_args__ = (
        UniqueConstraint("consumer_binding_id", name="uq_wf_tctx_handoff_lease_binding"),
        UniqueConstraint("sealed_capsule_id", name="uq_wf_tctx_handoff_lease_capsule"),
        UniqueConstraint("canonical_digest", name="uq_wf_tctx_handoff_lease_digest"),
        CheckConstraint(
            "state = 'authorized_unconsumed'",
            name="ck_wf_tctx_handoff_lease_state",
        ),
        CheckConstraint(
            "single_use AND NOT renewable AND NOT transferable "
            "AND NOT lease_is_bearer_capability AND NOT capsule_is_bearer_capability",
            name="ck_wf_tctx_handoff_lease_lifecycle",
        ),
        CheckConstraint(
            "issued_at < valid_until "
            "AND valid_until = issued_at + INTERVAL '1 second' "
            "AND valid_until <= effective_until "
            "AND valid_until <= lifecycle_attestation_valid_until",
            name="ck_wf_tctx_handoff_lease_window",
        ),
        CheckConstraint(
            "consumer_subject_id = "
            "'service.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_audience = "
            "'audience.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_contract_id = "
            "'contract.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_contract_version = '1.0' "
            "AND purpose_id = "
            "'purpose.workflow-protected-transport-target-context-capsule-handoff-evaluation' "
            "AND policy_id = "
            "'policy.workflow-protected-transport-target-context-capsule-handoff-authorization' "
            "AND policy_version = '1.0' "
            "AND policy_digest = "
            "'388fc176751bc5af37489bfea61c603106b3658aa60a6ca3459ee0bab9b51270' "
            "AND lifecycle_attestor_id = "
            "'attestor.workflow-protected-target-context-capsule-lifecycle' "
            "AND lifecycle_attestor_version = '1.0'",
            name="ck_wf_tctx_handoff_lease_contract",
        ),
        CheckConstraint(
            "target_context_capsule_handoff_authority_granted "
            "AND NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT endpoint_resolution_authority_granted "
            "AND NOT protected_artifact_access_authority_granted "
            "AND NOT credential_selection_authority_granted "
            "AND NOT credential_assignment_binding_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT credential_brokerage_authority_granted "
            "AND NOT credential_resolution_authority_granted "
            "AND NOT credential_delivery_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted "
            "AND NOT infrastructure_mutation_authority_granted",
            name="ck_wf_tctx_handoff_lease_authority",
        ),
        CheckConstraint(
            "char_length(authorization_audit_digest) = 64 "
            "AND authorization_audit_digest ~ '^[0-9a-f]{64}$' "
            "AND jsonb_typeof(authorization_audit_payload) = 'object' "
            "AND authorization_audit_payload <> '{}'::jsonb",
            name="ck_wf_tctx_handoff_lease_audit",
        ),
        Index(
            "ix_wf_tctx_handoff_lease_scope",
            "organization_id",
            "environment_id",
            "site_id",
        ),
        Index("ix_wf_tctx_handoff_lease_consumer", "consumer_subject_id"),
        Index("ix_wf_tctx_handoff_lease_valid", "valid_until"),
        Index("ix_wf_tctx_handoff_lease_state", "state"),
    )

    authorization_lease_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    consumer_binding_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_tctx_capsule_consumer_bindings.binding_id",
            name="fk_wf_tctx_handoff_lease_binding",
        ),
        nullable=False,
    )
    consumer_binding_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    opening_result_id: Mapped[str] = mapped_column(String(128), nullable=False)
    opening_result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    sealed_capsule_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sealed_capsule_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    capsule_schema_id: Mapped[str] = mapped_column(String(128), nullable=False)
    capsule_schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    capsule_is_bearer_capability: Mapped[bool] = mapped_column(Boolean, nullable=False)
    lifecycle_attestation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    lifecycle_attestation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    lifecycle_attestation_valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    lifecycle_attestor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    lifecycle_attestor_version: Mapped[str] = mapped_column(String(64), nullable=False)
    lifecycle_signing_key_id: Mapped[str] = mapped_column(String(128), nullable=False)
    lifecycle_signature_algorithm: Mapped[str] = mapped_column(String(64), nullable=False)
    lifecycle_integrity_signature: Mapped[str] = mapped_column(String(2048), nullable=False)
    consumer_subject_id: Mapped[str] = mapped_column(String(240), nullable=False)
    consumer_audience: Mapped[str] = mapped_column(String(240), nullable=False)
    consumer_contract_id: Mapped[str] = mapped_column(String(128), nullable=False)
    consumer_contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose_id: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    single_use: Mapped[bool] = mapped_column(Boolean, nullable=False)
    renewable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    transferable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    lease_is_bearer_capability: Mapped[bool] = mapped_column(Boolean, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    target_context_capsule_handoff_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    route_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_binding_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    endpoint_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    protected_artifact_access_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_assignment_binding_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_brokerage_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    readiness_probe_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    infrastructure_mutation_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    authorization_evidence_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    authorization_audit_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    lifecycle_attestation_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    authorization_evidence_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    authorization_audit_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowProtectedTransportTargetContextCapsuleHandoffAuthorizationClaimModel(Base):
    __tablename__ = "workflow_event_tctx_capsule_handoff_authorization_claims"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_tctx_handoff_claim_scope_idem",
        ),
        UniqueConstraint(
            "authorization_lease_id",
            name="uq_wf_tctx_handoff_claim_lease",
        ),
        UniqueConstraint("consumer_binding_id", name="uq_wf_tctx_handoff_claim_binding"),
        UniqueConstraint("sealed_capsule_id", name="uq_wf_tctx_handoff_claim_capsule"),
        UniqueConstraint("canonical_digest", name="uq_wf_tctx_handoff_claim_digest"),
        CheckConstraint(
            "consumer_subject_id = "
            "'service.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_audience = "
            "'audience.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_contract_id = "
            "'contract.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_contract_version = '1.0' "
            "AND purpose_id = "
            "'purpose.workflow-protected-transport-target-context-capsule-handoff-evaluation' "
            "AND policy_id = "
            "'policy.workflow-protected-transport-target-context-capsule-handoff-authorization' "
            "AND policy_version = '1.0' "
            "AND policy_digest = "
            "'388fc176751bc5af37489bfea61c603106b3658aa60a6ca3459ee0bab9b51270'",
            name="ck_wf_tctx_handoff_claim_contract",
        ),
        CheckConstraint(
            "char_length(authorization_audit_digest) = 64 "
            "AND authorization_audit_digest ~ '^[0-9a-f]{64}$' "
            "AND jsonb_typeof(authorization_audit_payload) = 'object' "
            "AND authorization_audit_payload <> '{}'::jsonb",
            name="ck_wf_tctx_handoff_claim_audit",
        ),
        Index("ix_wf_tctx_handoff_claim_scope", "idempotency_scope_id"),
        Index("ix_wf_tctx_handoff_claim_binding", "consumer_binding_id"),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    idempotency_scope_id: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    authorization_lease_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_tctx_capsule_handoff_authorization_leases.authorization_lease_id",
            name="fk_wf_tctx_handoff_claim_lease",
        ),
        nullable=False,
    )
    consumer_binding_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_tctx_capsule_consumer_bindings.binding_id",
            name="fk_wf_tctx_handoff_claim_binding",
        ),
        nullable=False,
    )
    sealed_capsule_id: Mapped[str] = mapped_column(String(128), nullable=False)
    consumer_subject_id: Mapped[str] = mapped_column(String(240), nullable=False)
    consumer_audience: Mapped[str] = mapped_column(String(240), nullable=False)
    consumer_contract_id: Mapped[str] = mapped_column(String(128), nullable=False)
    consumer_contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose_id: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    authorization_audit_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    authorization_audit_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowProtectedTransportTargetContextCapsuleHandoffConsumptionClaimModel(Base):
    __tablename__ = "workflow_event_tctx_capsule_handoff_consumption_claims"
    __table_args__ = (
        UniqueConstraint("authorization_lease_id", name="uq_wf_tctx_handoff_consume_lease"),
        UniqueConstraint("consumer_binding_id", name="uq_wf_tctx_handoff_consume_binding"),
        UniqueConstraint("sealed_capsule_id", name="uq_wf_tctx_handoff_consume_capsule"),
        UniqueConstraint("attempt_id", name="uq_wf_tctx_handoff_consume_attempt"),
        UniqueConstraint("handoff_id", name="uq_wf_tctx_handoff_consume_handoff"),
        UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_tctx_handoff_consume_scope_idem",
        ),
        CheckConstraint(
            "consumer_subject_id = "
            "'service.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_audience = "
            "'audience.workflow-protected-transport-target-context-capsule-consumer' "
            "AND policy_id = "
            "'policy.workflow-protected-transport-target-context-capsule-handoff-consumption' "
            "AND policy_version = '1.0'",
            name="ck_wf_tctx_handoff_consume_contract",
        ),
        CheckConstraint(
            "irreversible_consumption_acknowledged "
            "AND uncertain_outcome_requires_new_authorization_acknowledged",
            name="ck_wf_tctx_handoff_consume_ack",
        ),
        CheckConstraint(
            "NOT target_context_capsule_handoff_authority_granted "
            "AND NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT endpoint_resolution_authority_granted "
            "AND NOT protected_artifact_access_authority_granted "
            "AND NOT credential_selection_authority_granted "
            "AND NOT credential_assignment_binding_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT credential_brokerage_authority_granted "
            "AND NOT credential_resolution_authority_granted "
            "AND NOT credential_delivery_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted "
            "AND NOT infrastructure_mutation_authority_granted",
            name="ck_wf_tctx_handoff_consume_authority",
        ),
        Index(
            "ix_wf_tctx_handoff_consume_scope",
            "organization_id",
            "environment_id",
            "site_id",
        ),
        Index("ix_wf_tctx_handoff_consume_claimed", "claimed_at"),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    handoff_id: Mapped[str] = mapped_column(String(128), nullable=False)
    attempt_id: Mapped[str] = mapped_column(String(128), nullable=False)
    authorization_lease_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_tctx_capsule_handoff_authorization_leases.authorization_lease_id",
            name="fk_wf_tctx_handoff_consume_lease",
        ),
        nullable=False,
    )
    authorization_lease_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    consumer_binding_id: Mapped[str] = mapped_column(String(128), nullable=False)
    consumer_binding_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    sealed_capsule_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sealed_capsule_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False)
    consumer_subject_id: Mapped[str] = mapped_column(String(240), nullable=False)
    consumer_audience: Mapped[str] = mapped_column(String(240), nullable=False)
    consumer_contract_id: Mapped[str] = mapped_column(String(128), nullable=False)
    consumer_contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose_id: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_scope_id: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    irreversible_consumption_acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False)
    uncertain_outcome_requires_new_authorization_acknowledged: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    consumption_authorization_audit_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    target_context_capsule_handoff_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    route_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_binding_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    endpoint_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    protected_artifact_access_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_assignment_binding_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_brokerage_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    readiness_probe_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    infrastructure_mutation_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    consumption_authorization_audit_payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False
    )


class WorkflowProtectedTransportTargetContextCapsuleHandoffAttemptModel(Base):
    __tablename__ = "workflow_event_tctx_capsule_handoff_attempts"
    __table_args__ = (
        UniqueConstraint("consumption_claim_id", name="uq_wf_tctx_handoff_attempt_claim"),
        UniqueConstraint("authorization_lease_id", name="uq_wf_tctx_handoff_attempt_lease"),
        UniqueConstraint("handoff_id", name="uq_wf_tctx_handoff_attempt_handoff"),
        UniqueConstraint(
            "handoff_id",
            "attempt_id",
            "consumption_claim_id",
            name="uq_wf_tctx_handoff_attempt_lineage",
        ),
        CheckConstraint("state = 'started'", name="ck_wf_tctx_handoff_attempt_state"),
        CheckConstraint(
            "started_at < handoff_deadline AND handoff_deadline <= lease_valid_until "
            "AND handoff_deadline <= binding_effective_until "
            "AND handoff_deadline <= source_effective_until "
            "AND handoff_deadline <= lifecycle_attestation_valid_until "
            "AND handoff_deadline <= acceptance_attestation_valid_until",
            name="ck_wf_tctx_handoff_attempt_deadline",
        ),
        CheckConstraint(
            "destination_generation >= 1 "
            "AND adapter_contract_id = "
            "'contract.workflow-protected-target-context-capsule-sealed-handoff' "
            "AND adapter_contract_version = '1.0' "
            "AND approved_adapter_id = "
            "'adapter.workflow-protected-target-context-capsule-sealed-handoff' "
            "AND approved_adapter_version = '1.0'",
            name="ck_wf_tctx_handoff_attempt_profile",
        ),
        CheckConstraint(
            "NOT target_context_capsule_handoff_authority_granted "
            "AND NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT endpoint_resolution_authority_granted "
            "AND NOT protected_artifact_access_authority_granted "
            "AND NOT credential_selection_authority_granted "
            "AND NOT credential_assignment_binding_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT credential_brokerage_authority_granted "
            "AND NOT credential_resolution_authority_granted "
            "AND NOT credential_delivery_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted "
            "AND NOT infrastructure_mutation_authority_granted",
            name="ck_wf_tctx_handoff_attempt_authority",
        ),
        Index(
            "ix_wf_tctx_handoff_attempt_scope",
            "organization_id",
            "environment_id",
            "site_id",
        ),
        Index("ix_wf_tctx_handoff_attempt_started", "started_at"),
    )

    attempt_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    handoff_id: Mapped[str] = mapped_column(String(128), nullable=False)
    consumption_claim_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_tctx_capsule_handoff_consumption_claims.claim_id",
            name="fk_wf_tctx_handoff_attempt_claim",
        ),
        nullable=False,
    )
    authorization_lease_id: Mapped[str] = mapped_column(String(128), nullable=False)
    authorization_lease_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    consumer_binding_id: Mapped[str] = mapped_column(String(128), nullable=False)
    consumer_binding_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    sealed_capsule_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sealed_capsule_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    capsule_schema_id: Mapped[str] = mapped_column(String(128), nullable=False)
    capsule_schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False)
    consumer_subject_id: Mapped[str] = mapped_column(String(240), nullable=False)
    consumer_audience: Mapped[str] = mapped_column(String(240), nullable=False)
    consumer_contract_id: Mapped[str] = mapped_column(String(128), nullable=False)
    consumer_contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose_id: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    adapter_contract_id: Mapped[str] = mapped_column(String(128), nullable=False)
    adapter_contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_adapter_id: Mapped[str] = mapped_column(String(128), nullable=False)
    approved_adapter_version: Mapped[str] = mapped_column(String(64), nullable=False)
    destination_boundary_id: Mapped[str] = mapped_column(String(128), nullable=False)
    destination_deployment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    destination_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    destination_fencing_token_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    custody_contract_id: Mapped[str] = mapped_column(String(128), nullable=False)
    custody_contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    verification_signing_key_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trusted_profile_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    lifecycle_attestation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    lifecycle_attestation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    lifecycle_attestation_valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    acceptance_attestation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    acceptance_attestation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    acceptance_attestation_valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    request_nonce_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    handoff_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lease_valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    binding_effective_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source_effective_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    target_context_capsule_handoff_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    route_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_binding_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    endpoint_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    protected_artifact_access_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_assignment_binding_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_brokerage_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    readiness_probe_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    infrastructure_mutation_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    lifecycle_attestation_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    acceptance_attestation_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowProtectedTransportTargetContextCapsuleHandoffResultModel(Base):
    __tablename__ = "workflow_event_tctx_capsule_handoff_results"
    __table_args__ = (
        UniqueConstraint("attempt_id", name="uq_wf_tctx_handoff_result_attempt"),
        UniqueConstraint("consumption_claim_id", name="uq_wf_tctx_handoff_result_claim"),
        UniqueConstraint(
            "handoff_id",
            "attempt_id",
            "consumption_claim_id",
            name="uq_wf_tctx_handoff_result_lineage",
        ),
        ForeignKeyConstraint(
            ["handoff_id", "attempt_id", "consumption_claim_id"],
            [
                "workflow_event_tctx_capsule_handoff_attempts.handoff_id",
                "workflow_event_tctx_capsule_handoff_attempts.attempt_id",
                "workflow_event_tctx_capsule_handoff_attempts.consumption_claim_id",
            ],
            name="fk_wf_tctx_handoff_result_attempt_lineage",
        ),
        ForeignKeyConstraint(
            ["consumption_claim_id"],
            ["workflow_event_tctx_capsule_handoff_consumption_claims.claim_id"],
            name="fk_wf_tctx_handoff_result_claim",
        ),
        CheckConstraint(
            "(state = 'handed_off_sealed' AND failure_class IS NULL "
            "AND consumer_receipt_id IS NOT NULL AND sealed_capsule_handed_off "
            "AND usable_until IS NOT NULL AND completed_at < usable_until) OR "
            "(state = 'handoff_failed' AND failure_class IS NOT NULL "
            "AND consumer_receipt_id IS NULL AND NOT sealed_capsule_handed_off "
            "AND usable_until IS NULL AND source_cleanup_confirmed)",
            name="ck_wf_tctx_handoff_result_state",
        ),
        CheckConstraint(
            "NOT consumer_receipt_is_bearer_capability",
            name="ck_wf_tctx_handoff_result_non_bearer",
        ),
        CheckConstraint(
            "NOT target_context_capsule_handoff_authority_granted "
            "AND NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT endpoint_resolution_authority_granted "
            "AND NOT protected_artifact_access_authority_granted "
            "AND NOT credential_selection_authority_granted "
            "AND NOT credential_assignment_binding_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT credential_brokerage_authority_granted "
            "AND NOT credential_resolution_authority_granted "
            "AND NOT credential_delivery_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted "
            "AND NOT infrastructure_mutation_authority_granted",
            name="ck_wf_tctx_handoff_result_authority",
        ),
        Index(
            "ix_wf_tctx_handoff_result_scope",
            "organization_id",
            "environment_id",
            "site_id",
        ),
        Index("ix_wf_tctx_handoff_result_completed", "completed_at"),
    )

    handoff_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    attempt_id: Mapped[str] = mapped_column(String(128), nullable=False)
    attempt_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    consumption_claim_id: Mapped[str] = mapped_column(String(128), nullable=False)
    consumption_claim_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    authorization_lease_id: Mapped[str] = mapped_column(String(128), nullable=False)
    authorization_lease_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    consumer_binding_id: Mapped[str] = mapped_column(String(128), nullable=False)
    consumer_binding_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False)
    consumer_contract_id: Mapped[str] = mapped_column(String(128), nullable=False)
    consumer_contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose_id: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    adapter_contract_id: Mapped[str] = mapped_column(String(128), nullable=False)
    adapter_contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    receipt_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    failure_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    consumer_receipt_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    consumer_receipt_is_bearer_capability: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sealed_capsule_handed_off: Mapped[bool] = mapped_column(Boolean, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    usable_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_cleanup_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    target_context_capsule_handoff_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    route_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_binding_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    endpoint_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    protected_artifact_access_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_assignment_binding_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_brokerage_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    readiness_probe_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    infrastructure_mutation_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    receipt_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationLeaseModel(Base):
    __tablename__ = "workflow_event_tctx_capsule_opening_authorization_leases"
    __table_args__ = (
        UniqueConstraint("handoff_id", name="uq_wf_tctx_open_auth_result"),
        UniqueConstraint("consumer_receipt_id", name="uq_wf_tctx_open_auth_receipt"),
        UniqueConstraint("sealed_capsule_id", name="uq_wf_tctx_open_auth_capsule"),
        ForeignKeyConstraint(
            ["handoff_id", "attempt_id", "consumption_claim_id"],
            [
                "workflow_event_tctx_capsule_handoff_results.handoff_id",
                "workflow_event_tctx_capsule_handoff_results.attempt_id",
                "workflow_event_tctx_capsule_handoff_results.consumption_claim_id",
            ],
            name="fk_wf_tctx_open_auth_result_lineage",
        ),
        ForeignKeyConstraint(
            ["handoff_id", "attempt_id", "consumption_claim_id"],
            [
                "workflow_event_tctx_capsule_handoff_attempts.handoff_id",
                "workflow_event_tctx_capsule_handoff_attempts.attempt_id",
                "workflow_event_tctx_capsule_handoff_attempts.consumption_claim_id",
            ],
            name="fk_wf_tctx_open_auth_attempt_lineage",
        ),
        CheckConstraint(
            "valid_until = issued_at + interval '1 second' AND issued_at < valid_until "
            "AND valid_until <= effective_until AND valid_until <= custody_attestation_valid_until",
            name="ck_wf_tctx_capsule_open_auth_window",
        ),
        CheckConstraint(
            "single_use AND NOT renewable AND NOT transferable AND NOT lease_is_bearer_capability",
            name="ck_wf_tctx_capsule_open_auth_flags",
        ),
        CheckConstraint(
            "target_context_capsule_opening_authority_granted "
            "AND NOT target_context_capsule_handoff_authority_granted "
            "AND NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT endpoint_resolution_authority_granted "
            "AND NOT protected_artifact_access_authority_granted "
            "AND NOT credential_selection_authority_granted "
            "AND NOT credential_assignment_binding_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT credential_brokerage_authority_granted "
            "AND NOT credential_resolution_authority_granted "
            "AND NOT credential_delivery_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted "
            "AND NOT infrastructure_mutation_authority_granted",
            name="ck_wf_tctx_capsule_open_auth_authority",
        ),
        Index(
            "ix_wf_tctx_open_auth_scope",
            "organization_id",
            "environment_id",
            "site_id",
            "issued_at",
        ),
    )

    authorization_lease_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    handoff_id: Mapped[str] = mapped_column(String(128), nullable=False)
    handoff_result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt_id: Mapped[str] = mapped_column(String(128), nullable=False)
    attempt_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    consumption_claim_id: Mapped[str] = mapped_column(String(128), nullable=False)
    consumption_claim_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    upstream_authorization_lease_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_tctx_capsule_handoff_authorization_leases.authorization_lease_id"
        ),
        nullable=False,
    )
    upstream_authorization_lease_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    consumer_binding_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_event_tctx_capsule_consumer_bindings.binding_id"), nullable=False
    )
    consumer_binding_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    sealed_capsule_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sealed_capsule_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    consumer_receipt_id: Mapped[str] = mapped_column(String(128), nullable=False)
    receipt_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    destination_boundary_id: Mapped[str] = mapped_column(String(128), nullable=False)
    destination_deployment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    destination_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    destination_fencing_token_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    custody_contract_id: Mapped[str] = mapped_column(String(128), nullable=False)
    custody_contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_adapter_id: Mapped[str] = mapped_column(String(128), nullable=False)
    approved_adapter_version: Mapped[str] = mapped_column(String(64), nullable=False)
    verification_signing_key_id: Mapped[str] = mapped_column(String(128), nullable=False)
    trusted_profile_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    custody_attestation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    custody_attestation_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    custody_attestation_valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False)
    consumer_subject_id: Mapped[str] = mapped_column(String(240), nullable=False)
    consumer_audience: Mapped[str] = mapped_column(String(240), nullable=False)
    consumer_contract_id: Mapped[str] = mapped_column(String(128), nullable=False)
    consumer_contract_version: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose_id: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_id: Mapped[str] = mapped_column(String(128), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    single_use: Mapped[bool] = mapped_column(Boolean, nullable=False)
    renewable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    transferable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    lease_is_bearer_capability: Mapped[bool] = mapped_column(Boolean, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    target_context_capsule_opening_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    target_context_capsule_handoff_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    route_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    route_binding_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    endpoint_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    protected_artifact_access_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_selection_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_assignment_binding_authority_granted: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    credential_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_brokerage_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_resolution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    credential_delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    network_access_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    readiness_probe_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    publication_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delivery_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    dispatch_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    execution_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    infrastructure_mutation_authority_granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    custody_attestation_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowProtectedTransportTargetContextCapsuleOpeningAuthorizationClaimModel(Base):
    __tablename__ = "workflow_event_tctx_capsule_opening_authorization_claims"
    __table_args__ = (
        UniqueConstraint("authorization_lease_id", name="uq_wf_tctx_open_auth_claim_lease"),
        UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_tctx_open_auth_scope_idem",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    authorization_lease_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_event_tctx_capsule_opening_authorization_leases.authorization_lease_id"
        ),
        nullable=False,
    )
    handoff_id: Mapped[str] = mapped_column(String(128), nullable=False)
    consumer_receipt_id: Mapped[str] = mapped_column(String(128), nullable=False)
    sealed_capsule_id: Mapped[str] = mapped_column(String(128), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False)
    consumer_subject_id: Mapped[str] = mapped_column(String(240), nullable=False)
    consumer_audience: Mapped[str] = mapped_column(String(240), nullable=False)
    idempotency_scope_id: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    authorization_audit_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    claimed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    authorization_audit_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class WorkflowDispatchIntentStagingClaimModel(Base):
    __tablename__ = "workflow_dispatch_intent_staging_claims"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_workflow_dispatch_intent_staging_scope_idem",
        ),
        UniqueConstraint(
            "dispatch_intent_id",
            name="uq_workflow_dispatch_intent_staging_claim_intent",
        ),
        UniqueConstraint(
            "outbox_entry_id",
            name="uq_workflow_dispatch_intent_staging_claim_outbox",
        ),
        UniqueConstraint(
            "canonical_digest",
            name="uq_workflow_dispatch_intent_staging_claim_digest",
        ),
    )

    claim_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    idempotency_scope_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    result_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    result_outbox_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    dispatch_intent_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_dispatch_intents.dispatch_intent_id"),
        nullable=False,
        index=True,
    )
    outbox_entry_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_dispatch_outbox_entries.outbox_entry_id"),
        nullable=False,
        index=True,
    )
    attempt_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_attempts.attempt_id"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_execution_runs.run_id"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_run_plans.plan_id"),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    site_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    worker_subject_id: Mapped[str] = mapped_column(String(240), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canonical_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
