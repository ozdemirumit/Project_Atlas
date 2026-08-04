"""Add governed upgrade simulation records.

Revision ID: 20260805_0014
Revises: 20260804_0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260805_0014"
down_revision: str | None = "20260804_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platform_upgrade_simulations",
        sa.Column("simulation_id", sa.String(length=128), nullable=False),
        sa.Column("schema_version", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("source_run_id", sa.String(length=128), nullable=False),
        sa.Column("source_run_version", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.String(length=128), nullable=False),
        sa.Column("plan_digest", sa.String(length=64), nullable=False),
        sa.Column("backup_id", sa.String(length=128), nullable=False),
        sa.Column("restore_validation_id", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("steps", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("impacted_service_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "post_verification_check_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("abort_injected_at_step_id", sa.String(length=128), nullable=False),
        sa.Column("rollback_decision", sa.String(length=128), nullable=False),
        sa.Column("estimated_downtime_minutes", sa.Integer(), nullable=False),
        sa.Column("simulation_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("source_run_version > 0", name="ck_platform_upgrade_simulations_source"),
        sa.CheckConstraint(
            "estimated_downtime_minutes > 0",
            name="ck_platform_upgrade_simulations_downtime",
        ),
        sa.PrimaryKeyConstraint("simulation_id"),
        sa.UniqueConstraint(
            "actor_id",
            "idempotency_key",
            name="uq_platform_upgrade_simulations_actor_idempotency",
        ),
    )


def downgrade() -> None:
    op.drop_table("platform_upgrade_simulations")
