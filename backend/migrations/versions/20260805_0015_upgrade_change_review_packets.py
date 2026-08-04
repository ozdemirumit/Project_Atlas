"""Add governed upgrade change review packets.

Revision ID: 20260805_0015
Revises: 20260805_0014
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260805_0015"
down_revision: str | None = "20260805_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platform_upgrade_change_review_packets",
        sa.Column("packet_id", sa.String(length=128), nullable=False),
        sa.Column("schema_version", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("source_run_id", sa.String(length=128), nullable=False),
        sa.Column("source_run_version", sa.Integer(), nullable=False),
        sa.Column("preview_id", sa.String(length=128), nullable=False),
        sa.Column("preview_digest", sa.String(length=64), nullable=False),
        sa.Column("plan_id", sa.String(length=128), nullable=False),
        sa.Column("plan_digest", sa.String(length=64), nullable=False),
        sa.Column("simulation_id", sa.String(length=128), nullable=False),
        sa.Column("simulation_digest", sa.String(length=64), nullable=False),
        sa.Column("backup_id", sa.String(length=128), nullable=False),
        sa.Column("restore_validation_id", sa.String(length=128), nullable=False),
        sa.Column("risk_class", sa.String(length=128), nullable=False),
        sa.Column("change_class", sa.String(length=128), nullable=False),
        sa.Column("impacted_service_ids", postgresql.JSONB(), nullable=False),
        sa.Column("migration_step_ids", postgresql.JSONB(), nullable=False),
        sa.Column("abort_criterion_ids", postgresql.JSONB(), nullable=False),
        sa.Column("rollback_step_ids", postgresql.JSONB(), nullable=False),
        sa.Column("post_verification_check_ids", postgresql.JSONB(), nullable=False),
        sa.Column("assumption_ids", postgresql.JSONB(), nullable=False),
        sa.Column("unknown_ids", postgresql.JSONB(), nullable=False),
        sa.Column("residual_risk_ids", postgresql.JSONB(), nullable=False),
        sa.Column("owner_role_ids", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_digests", postgresql.JSONB(), nullable=False),
        sa.Column("proposed_window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("proposed_window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("estimated_downtime_min_minutes", sa.Integer(), nullable=False),
        sa.Column("estimated_downtime_max_minutes", sa.Integer(), nullable=False),
        sa.Column("rollback_window_minutes", sa.Integer(), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("itsm_draft_id", sa.String(length=128), nullable=False),
        sa.Column("itsm_draft_title", sa.String(length=160), nullable=False),
        sa.Column("itsm_draft_digest", sa.String(length=64), nullable=False),
        sa.Column("packet_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_run_version > 0",
            name="ck_platform_upgrade_change_review_packets_source",
        ),
        sa.PrimaryKeyConstraint("packet_id"),
        sa.UniqueConstraint(
            "actor_id",
            "idempotency_key",
            name="uq_platform_upgrade_change_review_packets_actor_idempotency",
        ),
    )


def downgrade() -> None:
    op.drop_table("platform_upgrade_change_review_packets")
