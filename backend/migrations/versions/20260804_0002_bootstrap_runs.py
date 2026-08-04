"""Create persistent bootstrap run coordination table.

Revision ID: 20260804_0002
Revises: 20260803_0001
Create Date: 2026-08-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260804_0002"
down_revision: str | None = "20260803_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platform_bootstrap_runs",
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("release_id", sa.String(length=128), nullable=False),
        sa.Column("profile", sa.String(length=32), nullable=False),
        sa.Column("plan_digest", sa.String(length=64), nullable=False),
        sa.Column("resume_key", sa.String(length=128), nullable=False),
        sa.Column("configuration_digest", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("phase_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("checkpoints", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("idempotency_records", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("lease_holder_id", sa.String(length=128), nullable=True),
        sa.Column("lease_acquired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_platform_bootstrap_runs_version_positive"),
        sa.PrimaryKeyConstraint("run_id", name="pk_platform_bootstrap_runs"),
        sa.UniqueConstraint(
            "organization_id",
            "environment_id",
            "site_id",
            name="uq_platform_bootstrap_runs_deployment",
        ),
    )


def downgrade() -> None:
    op.drop_table("platform_bootstrap_runs")
