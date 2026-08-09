from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Integer,
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
