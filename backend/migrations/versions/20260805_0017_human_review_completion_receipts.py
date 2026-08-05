"""Add non-executable human review completion receipts.

Revision ID: 20260805_0017
Revises: 20260805_0016
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260805_0017"
down_revision: str | None = "20260805_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platform_human_review_completion_receipts",
        sa.Column("receipt_id", sa.String(length=128), nullable=False),
        sa.Column("schema_version", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("review_id", sa.String(length=128), nullable=False),
        sa.Column("review_version", sa.Integer(), nullable=False),
        sa.Column("review_digest", sa.String(length=64), nullable=False),
        sa.Column("review_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("packet_id", sa.String(length=128), nullable=False),
        sa.Column("packet_digest", sa.String(length=64), nullable=False),
        sa.Column("requester_id", sa.String(length=128), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("risk_class", sa.String(length=128), nullable=False),
        sa.Column("change_class", sa.String(length=128), nullable=False),
        sa.Column("impacted_service_ids", postgresql.JSONB(), nullable=False),
        sa.Column("evidence_digests", postgresql.JSONB(), nullable=False),
        sa.Column("proposed_window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("proposed_window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stages", postgresql.JSONB(), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version = 1", name="ck_platform_review_receipts_version"),
        sa.PrimaryKeyConstraint("receipt_id"),
        sa.UniqueConstraint("review_id", name="uq_platform_review_receipts_review"),
        sa.UniqueConstraint(
            "created_by",
            "idempotency_key",
            name="uq_platform_review_receipts_creator_idempotency",
        ),
    )
    op.create_index(
        op.f("ix_platform_human_review_completion_receipts_review_id"),
        "platform_human_review_completion_receipts",
        ["review_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_platform_human_review_completion_receipts_review_id"),
        table_name="platform_human_review_completion_receipts",
    )
    op.drop_table("platform_human_review_completion_receipts")
