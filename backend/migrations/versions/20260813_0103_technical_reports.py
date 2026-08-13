"""Add durable governed technical reports.

Revision ID: 20260813_0103
Revises: 20260813_0102
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260813_0103"
down_revision: str | None = "20260813_0102"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "technical_reports"
    op.create_table(
        table,
        sa.Column("report_id", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("lineage_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("prior_version_id", sa.String(length=128), nullable=True),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("report_id"),
        sa.UniqueConstraint("request_fingerprint", name="uq_technical_reports_request"),
        sa.UniqueConstraint(
            "lineage_fingerprint",
            "version",
            name="uq_technical_reports_lineage_version",
        ),
    )
    for column in (
        "lineage_fingerprint",
        "organization_id",
        "environment_id",
        "target_id",
        "requested_by",
    ):
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def downgrade() -> None:
    table = "technical_reports"
    for column in reversed(
        (
            "lineage_fingerprint",
            "organization_id",
            "environment_id",
            "target_id",
            "requested_by",
        )
    ):
        op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
    op.drop_table(table)
