"""Add governed ITSM handoff human reviews.

Revision ID: 20260813_0102
Revises: 20260812_0101
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260813_0102"
down_revision: str | None = "20260812_0101"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "report_itsm_handoff_human_reviews"
    op.create_table(
        table,
        sa.Column("review_id", sa.String(length=128), nullable=False),
        sa.Column("schema_version", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("report_id", sa.String(length=128), nullable=False),
        sa.Column("report_version", sa.Integer(), nullable=False),
        sa.Column("report_digest", sa.String(length=64), nullable=False),
        sa.Column("handoff_draft_id", sa.String(length=128), nullable=False),
        sa.Column("handoff_digest", sa.String(length=64), nullable=False),
        sa.Column("handoff_idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("incident_reference", sa.String(length=80), nullable=False),
        sa.Column("operation", sa.String(length=128), nullable=False),
        sa.Column("requester_id", sa.String(length=128), nullable=False),
        sa.Column("reviewer_id", sa.String(length=128), nullable=False),
        sa.Column("reviewer_role_id", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("rationale", sa.String(length=1000), nullable=False),
        sa.Column("acknowledged_review_only", sa.Boolean(), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version = 1", name="ck_report_itsm_handoff_reviews_version"),
        sa.PrimaryKeyConstraint("review_id"),
        sa.UniqueConstraint("handoff_draft_id", name="uq_report_itsm_handoff_reviews_handoff"),
        sa.UniqueConstraint(
            "reviewer_id",
            "idempotency_key",
            name="uq_report_itsm_handoff_reviews_reviewer_idempotency",
        ),
    )
    for column in ("report_id", "reviewer_id", "organization_id", "environment_id"):
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def downgrade() -> None:
    table = "report_itsm_handoff_human_reviews"
    for column in reversed(("report_id", "reviewer_id", "organization_id", "environment_id")):
        op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
    op.drop_table(table)
