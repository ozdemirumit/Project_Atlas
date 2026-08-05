"""Add immutable MCP Builder static validation reports.

Revision ID: 20260805_0021
Revises: 20260805_0020
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260805_0021"
down_revision: str | None = "20260805_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_builder_validations",
        sa.Column("validation_id", sa.String(length=128), nullable=False),
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
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("validated_by", sa.String(length=128), nullable=False),
        sa.Column("language_profile", sa.String(length=128), nullable=False),
        sa.Column("template_version", sa.String(length=128), nullable=False),
        sa.Column("validation_profile", sa.String(length=128), nullable=False),
        sa.Column("validator_version", sa.String(length=128), nullable=False),
        sa.Column("checks", postgresql.JSONB(), nullable=False),
        sa.Column("passed_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("limitations", postgresql.JSONB(), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version = 1", name="ck_mcp_builder_validations_version"),
        sa.PrimaryKeyConstraint("validation_id"),
        sa.UniqueConstraint("project_id", name="uq_mcp_builder_validations_project"),
        sa.UniqueConstraint("generation_id", name="uq_mcp_builder_validations_generation"),
        sa.UniqueConstraint(
            "validated_by",
            "idempotency_key",
            name="uq_mcp_builder_validations_validator_idempotency",
        ),
    )
    op.create_index(
        op.f("ix_mcp_builder_validations_project_id"),
        "mcp_builder_validations",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mcp_builder_validations_checkpoint_id"),
        "mcp_builder_validations",
        ["checkpoint_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mcp_builder_validations_generation_id"),
        "mcp_builder_validations",
        ["generation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mcp_builder_validations_validated_by"),
        "mcp_builder_validations",
        ["validated_by"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_mcp_builder_validations_validated_by"),
        table_name="mcp_builder_validations",
    )
    op.drop_index(
        op.f("ix_mcp_builder_validations_generation_id"),
        table_name="mcp_builder_validations",
    )
    op.drop_index(
        op.f("ix_mcp_builder_validations_checkpoint_id"),
        table_name="mcp_builder_validations",
    )
    op.drop_index(
        op.f("ix_mcp_builder_validations_project_id"),
        table_name="mcp_builder_validations",
    )
    op.drop_table("mcp_builder_validations")
