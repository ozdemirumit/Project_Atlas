"""Add immutable MCP Builder candidate package handoffs.

Revision ID: 20260805_0025
Revises: 20260805_0024
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260805_0025"
down_revision: str | None = "20260805_0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_builder_candidate_handoffs",
        sa.Column("handoff_id", sa.String(length=128), nullable=False),
        sa.Column("schema_version", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("project_version", sa.Integer(), nullable=False),
        sa.Column("project_digest", sa.String(length=64), nullable=False),
        sa.Column("source_digest", sa.String(length=64), nullable=False),
        sa.Column("checkpoint_id", sa.String(length=128), nullable=False),
        sa.Column("checkpoint_digest", sa.String(length=64), nullable=False),
        sa.Column("generation_id", sa.String(length=128), nullable=False),
        sa.Column("generation_digest", sa.String(length=64), nullable=False),
        sa.Column("artifact_digest", sa.String(length=64), nullable=False),
        sa.Column("validation_id", sa.String(length=128), nullable=False),
        sa.Column("validation_digest", sa.String(length=64), nullable=False),
        sa.Column("domain_review_id", sa.String(length=128), nullable=False),
        sa.Column("domain_review_digest", sa.String(length=64), nullable=False),
        sa.Column("domain_reviewed_by", sa.String(length=128), nullable=False),
        sa.Column("security_review_id", sa.String(length=128), nullable=False),
        sa.Column("security_review_digest", sa.String(length=64), nullable=False),
        sa.Column("security_reviewed_by", sa.String(length=128), nullable=False),
        sa.Column("lab_validation_id", sa.String(length=128), nullable=False),
        sa.Column("lab_validation_digest", sa.String(length=64), nullable=False),
        sa.Column("lab_operated_by", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("custodied_by", sa.String(length=128), nullable=False),
        sa.Column("handoff_profile", sa.String(length=128), nullable=False),
        sa.Column("archive_contract_version", sa.String(length=128), nullable=False),
        sa.Column("package_filename", sa.String(length=132), nullable=False),
        sa.Column("package_digest", sa.String(length=64), nullable=False),
        sa.Column("package_size_bytes", sa.Integer(), nullable=False),
        sa.Column("package_entry_count", sa.Integer(), nullable=False),
        sa.Column("generated_file_count", sa.Integer(), nullable=False),
        sa.Column("generated_size_bytes", sa.Integer(), nullable=False),
        sa.Column("envelope_digest", sa.String(length=64), nullable=False),
        sa.Column("signature_state", sa.String(length=32), nullable=False),
        sa.Column("capabilities", postgresql.JSONB(), nullable=False),
        sa.Column("network_destinations", postgresql.JSONB(), nullable=False),
        sa.Column("limitations", postgresql.JSONB(), nullable=False),
        sa.Column("unsupported_behavior", postgresql.JSONB(), nullable=False),
        sa.Column("manual_change_count", sa.Integer(), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version = 1", name="ck_mcp_builder_candidate_handoffs_version"),
        sa.PrimaryKeyConstraint("handoff_id"),
        sa.UniqueConstraint("project_id", name="uq_mcp_builder_candidate_handoffs_project"),
        sa.UniqueConstraint(
            "lab_validation_id", name="uq_mcp_builder_candidate_handoffs_lab_validation"
        ),
        sa.UniqueConstraint(
            "package_digest", name="uq_mcp_builder_candidate_handoffs_package_digest"
        ),
        sa.UniqueConstraint(
            "custodied_by",
            "idempotency_key",
            name="uq_mcp_builder_candidate_handoffs_custodian_idempotency",
        ),
    )
    for column in (
        "project_id",
        "checkpoint_id",
        "generation_id",
        "validation_id",
        "domain_review_id",
        "security_review_id",
        "lab_validation_id",
        "custodied_by",
    ):
        op.create_index(
            op.f(f"ix_mcp_builder_candidate_handoffs_{column}"),
            "mcp_builder_candidate_handoffs",
            [column],
            unique=False,
        )


def downgrade() -> None:
    for column in reversed(
        (
            "project_id",
            "checkpoint_id",
            "generation_id",
            "validation_id",
            "domain_review_id",
            "security_review_id",
            "lab_validation_id",
            "custodied_by",
        )
    ):
        op.drop_index(
            op.f(f"ix_mcp_builder_candidate_handoffs_{column}"),
            table_name="mcp_builder_candidate_handoffs",
        )
    op.drop_table("mcp_builder_candidate_handoffs")
