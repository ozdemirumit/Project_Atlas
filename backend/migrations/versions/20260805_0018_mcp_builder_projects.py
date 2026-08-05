"""Add governed MCP Builder source-analysis projects.

Revision ID: 20260805_0018
Revises: 20260805_0017
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260805_0018"
down_revision: str | None = "20260805_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_builder_projects",
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("schema_version", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("owner_id", sa.String(length=128), nullable=False),
        sa.Column("vendor", sa.String(length=200), nullable=False),
        sa.Column("product", sa.String(length=200), nullable=False),
        sa.Column("intended_product_versions", postgresql.JSONB(), nullable=False),
        sa.Column("target_environment", sa.String(length=200), nullable=False),
        sa.Column("sdk_profile", sa.String(length=128), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("source_authority", sa.String(length=200), nullable=False),
        sa.Column("source_owner", sa.String(length=200), nullable=False),
        sa.Column("documentation_version", sa.String(length=200), nullable=False),
        sa.Column("publication_date", sa.Date(), nullable=False),
        sa.Column("license_id", sa.String(length=200), nullable=False),
        sa.Column("redistribution_allowed", sa.Boolean(), nullable=False),
        sa.Column("classification", sa.String(length=32), nullable=False),
        sa.Column("openapi_version", sa.String(length=32), nullable=False),
        sa.Column("api_title", sa.String(length=160), nullable=False),
        sa.Column("api_version", sa.String(length=80), nullable=False),
        sa.Column("source_digest", sa.String(length=64), nullable=False),
        sa.Column("source_size_bytes", sa.Integer(), nullable=False),
        sa.Column("canonical_source_json", sa.Text(), nullable=False),
        sa.Column("declared_servers", postgresql.JSONB(), nullable=False),
        sa.Column("authentication_schemes", postgresql.JSONB(), nullable=False),
        sa.Column("capability_candidates", postgresql.JSONB(), nullable=False),
        sa.Column("findings", postgresql.JSONB(), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version = 1", name="ck_mcp_builder_projects_version"),
        sa.PrimaryKeyConstraint("project_id"),
        sa.UniqueConstraint(
            "owner_id", "idempotency_key", name="uq_mcp_builder_projects_owner_idempotency"
        ),
    )
    op.create_index(
        op.f("ix_mcp_builder_projects_owner_id"),
        "mcp_builder_projects",
        ["owner_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_mcp_builder_projects_owner_id"), table_name="mcp_builder_projects")
    op.drop_table("mcp_builder_projects")
