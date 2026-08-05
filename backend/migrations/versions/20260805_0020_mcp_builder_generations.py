"""Add quarantined MCP Builder generation metadata.

Revision ID: 20260805_0020
Revises: 20260805_0019
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260805_0020"
down_revision: str | None = "20260805_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_builder_generations",
        sa.Column("generation_id", sa.String(length=128), nullable=False),
        sa.Column("schema_version", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("project_version", sa.Integer(), nullable=False),
        sa.Column("project_digest", sa.String(length=64), nullable=False),
        sa.Column("source_digest", sa.String(length=64), nullable=False),
        sa.Column("checkpoint_id", sa.String(length=128), nullable=False),
        sa.Column("checkpoint_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("language_profile", sa.String(length=128), nullable=False),
        sa.Column("template_version", sa.String(length=128), nullable=False),
        sa.Column("artifact_digest", sa.String(length=64), nullable=False),
        sa.Column("artifact_size_bytes", sa.Integer(), nullable=False),
        sa.Column("files", postgresql.JSONB(), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version = 1", name="ck_mcp_builder_generations_version"),
        sa.PrimaryKeyConstraint("generation_id"),
        sa.UniqueConstraint("project_id", name="uq_mcp_builder_generations_project"),
        sa.UniqueConstraint(
            "requested_by",
            "idempotency_key",
            name="uq_mcp_builder_generations_requester_idempotency",
        ),
    )
    op.create_index(
        op.f("ix_mcp_builder_generations_project_id"),
        "mcp_builder_generations",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mcp_builder_generations_checkpoint_id"),
        "mcp_builder_generations",
        ["checkpoint_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_mcp_builder_generations_requested_by"),
        "mcp_builder_generations",
        ["requested_by"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_mcp_builder_generations_requested_by"),
        table_name="mcp_builder_generations",
    )
    op.drop_index(
        op.f("ix_mcp_builder_generations_checkpoint_id"),
        table_name="mcp_builder_generations",
    )
    op.drop_index(
        op.f("ix_mcp_builder_generations_project_id"),
        table_name="mcp_builder_generations",
    )
    op.drop_table("mcp_builder_generations")
