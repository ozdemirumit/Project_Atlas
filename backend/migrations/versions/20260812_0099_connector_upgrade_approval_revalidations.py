"""Add governed connector upgrade approval revalidations.

Revision ID: 20260812_0099
Revises: 20260812_0098
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260812_0099"
down_revision: str | None = "20260812_0098"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "connector_upgrade_approval_revalidations"
    op.create_table(
        table,
        sa.Column("revalidation_id", sa.String(length=128), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("decision_id", sa.String(length=128), nullable=False),
        sa.Column("revalidated_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("revalidated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("revalidation_id"),
        sa.UniqueConstraint(
            "revalidated_by",
            "idempotency_key",
            name="uq_connector_upgrade_approval_revalidations_actor_idempotency",
        ),
    )
    for column in (
        "request_id",
        "decision_id",
        "revalidated_by",
        "organization_id",
        "environment_id",
        "revalidated_at",
        "valid_until",
    ):
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def downgrade() -> None:
    table = "connector_upgrade_approval_revalidations"
    for column in reversed(
        (
            "request_id",
            "decision_id",
            "revalidated_by",
            "organization_id",
            "environment_id",
            "revalidated_at",
            "valid_until",
        )
    ):
        op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
    op.drop_table(table)
