"""Add governed MCP Builder human design checkpoints.

Revision ID: 20260805_0019
Revises: 20260805_0018
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260805_0019"
down_revision: str | None = "20260805_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_builder_design_checkpoints",
        sa.Column("checkpoint_id", sa.String(length=128), nullable=False),
        sa.Column("schema_version", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("project_version", sa.Integer(), nullable=False),
        sa.Column("project_digest", sa.String(length=64), nullable=False),
        sa.Column("source_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("reviewer_id", sa.String(length=128), nullable=False),
        sa.Column("connector_boundary", sa.Text(), nullable=False),
        sa.Column("target_products", postgresql.JSONB(), nullable=False),
        sa.Column("network_destinations", postgresql.JSONB(), nullable=False),
        sa.Column("configuration_keys", postgresql.JSONB(), nullable=False),
        sa.Column("secret_reference_ids", postgresql.JSONB(), nullable=False),
        sa.Column("entity_mappings", postgresql.JSONB(), nullable=False),
        sa.Column("capability_decisions", postgresql.JSONB(), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version = 1", name="ck_mcp_builder_design_checkpoints_version"),
        sa.PrimaryKeyConstraint("checkpoint_id"),
        sa.UniqueConstraint("project_id", name="uq_mcp_builder_design_checkpoints_project"),
        sa.UniqueConstraint(
            "reviewer_id",
            "idempotency_key",
            name="uq_mcp_builder_design_checkpoints_reviewer_idempotency",
        ),
    )
    op.create_index(
        op.f("ix_mcp_builder_design_checkpoints_project_id"),
        "mcp_builder_design_checkpoints",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mcp_builder_design_checkpoints_reviewer_id"),
        "mcp_builder_design_checkpoints",
        ["reviewer_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_mcp_builder_design_checkpoints_reviewer_id"),
        table_name="mcp_builder_design_checkpoints",
    )
    op.drop_index(
        op.f("ix_mcp_builder_design_checkpoints_project_id"),
        table_name="mcp_builder_design_checkpoints",
    )
    op.drop_table("mcp_builder_design_checkpoints")
