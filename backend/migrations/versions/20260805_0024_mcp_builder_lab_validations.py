"""Add immutable MCP Builder isolated lab validations.

Revision ID: 20260805_0024
Revises: 20260805_0023
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260805_0024"
down_revision: str | None = "20260805_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_builder_lab_validations",
        sa.Column("lab_validation_id", sa.String(length=128), nullable=False),
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
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("operated_by", sa.String(length=128), nullable=False),
        sa.Column("lab_profile", sa.String(length=128), nullable=False),
        sa.Column("runner_contract_version", sa.String(length=128), nullable=False),
        sa.Column("runtime_version", sa.String(length=128), nullable=False),
        sa.Column("checks", postgresql.JSONB(), nullable=False),
        sa.Column("passed_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("child_started", sa.Boolean(), nullable=False),
        sa.Column("child_exit_code", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("output_digest", sa.String(length=64), nullable=False),
        sa.Column("output_size_bytes", sa.Integer(), nullable=False),
        sa.Column("artifact_file_count", sa.Integer(), nullable=False),
        sa.Column("artifact_size_bytes", sa.Integer(), nullable=False),
        sa.Column("workspace_removed", sa.Boolean(), nullable=False),
        sa.Column("limitations", postgresql.JSONB(), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version = 1", name="ck_mcp_builder_lab_validations_version"),
        sa.PrimaryKeyConstraint("lab_validation_id"),
        sa.UniqueConstraint("project_id", name="uq_mcp_builder_lab_validations_project"),
        sa.UniqueConstraint(
            "security_review_id", name="uq_mcp_builder_lab_validations_security_review"
        ),
        sa.UniqueConstraint(
            "operated_by",
            "idempotency_key",
            name="uq_mcp_builder_lab_validations_operator_idempotency",
        ),
    )
    for column in (
        "project_id",
        "checkpoint_id",
        "generation_id",
        "validation_id",
        "domain_review_id",
        "security_review_id",
        "operated_by",
    ):
        op.create_index(
            op.f(f"ix_mcp_builder_lab_validations_{column}"),
            "mcp_builder_lab_validations",
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
            "operated_by",
        )
    ):
        op.drop_index(
            op.f(f"ix_mcp_builder_lab_validations_{column}"),
            table_name="mcp_builder_lab_validations",
        )
    op.drop_table("mcp_builder_lab_validations")
