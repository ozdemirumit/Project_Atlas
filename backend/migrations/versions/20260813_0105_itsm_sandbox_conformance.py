"""Add governed ITSM sandbox conformance assessments.

Revision ID: 20260813_0105
Revises: 20260813_0104
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260813_0105"
down_revision: str | None = "20260813_0104"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "itsm_sandbox_conformance_assessments"
    op.create_table(
        table,
        sa.Column("assessment_id", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("profile_id", sa.String(length=128), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("assessed_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("assessment_id"),
        sa.UniqueConstraint(
            "assessed_by",
            "idempotency_key",
            name="uq_itsm_sandbox_conformance_actor_idem",
        ),
    )
    for column in (
        "organization_id",
        "environment_id",
        "site_id",
        "profile_id",
        "state",
        "assessed_by",
    ):
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def downgrade() -> None:
    table = "itsm_sandbox_conformance_assessments"
    for column in reversed(
        (
            "organization_id",
            "environment_id",
            "site_id",
            "profile_id",
            "state",
            "assessed_by",
        )
    ):
        op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
    op.drop_table(table)
