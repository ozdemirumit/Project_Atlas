"""Add governed upgrade change human reviews.

Revision ID: 20260805_0016
Revises: 20260805_0015
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260805_0016"
down_revision: str | None = "20260805_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platform_upgrade_change_human_reviews",
        sa.Column("review_id", sa.String(length=128), nullable=False),
        sa.Column("schema_version", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("packet_id", sa.String(length=128), nullable=False),
        sa.Column("packet_digest", sa.String(length=64), nullable=False),
        sa.Column("requester_id", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("risk_class", sa.String(length=128), nullable=False),
        sa.Column("change_class", sa.String(length=128), nullable=False),
        sa.Column("impacted_service_ids", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_digests", postgresql.JSONB(), nullable=False),
        sa.Column("proposed_window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("proposed_window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("justification", sa.String(length=500), nullable=False),
        sa.Column("required_role_ids", postgresql.JSONB(), nullable=False),
        sa.Column("stages", postgresql.JSONB(), nullable=False),
        sa.Column("decisions", postgresql.JSONB(), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_platform_upgrade_human_reviews_version"),
        sa.PrimaryKeyConstraint("review_id"),
        sa.UniqueConstraint(
            "requester_id",
            "idempotency_key",
            name="uq_platform_upgrade_human_reviews_requester_idempotency",
        ),
    )
    op.create_index(
        op.f("ix_platform_upgrade_change_human_reviews_packet_id"),
        "platform_upgrade_change_human_reviews",
        ["packet_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_platform_upgrade_change_human_reviews_packet_id"),
        table_name="platform_upgrade_change_human_reviews",
    )
    op.drop_table("platform_upgrade_change_human_reviews")
