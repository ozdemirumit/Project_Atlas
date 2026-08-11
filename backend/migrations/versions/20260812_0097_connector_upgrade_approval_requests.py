"""Add governed connector upgrade approval requests.

Revision ID: 20260812_0097
Revises: 20260811_0096
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260812_0097"
down_revision: str | None = "20260811_0096"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "connector_upgrade_approval_requests"
    op.create_table(
        table,
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("source_record_id", sa.String(length=128), nullable=False),
        sa.Column("instance_id", sa.String(length=128), nullable=False),
        sa.Column("connector_id", sa.String(length=128), nullable=False),
        sa.Column("plan_digest", sa.String(length=64), nullable=False),
        sa.Column("candidate_receipt_id", sa.String(length=128), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("request_id"),
        sa.UniqueConstraint("plan_digest", name="uq_connector_upgrade_approval_requests_plan"),
        sa.UniqueConstraint(
            "requested_by",
            "idempotency_key",
            name="uq_connector_upgrade_approval_requests_actor_idempotency",
        ),
    )
    for column in (
        "source_record_id",
        "instance_id",
        "connector_id",
        "candidate_receipt_id",
        "requested_by",
        "organization_id",
        "environment_id",
        "state",
        "expires_at",
    ):
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def downgrade() -> None:
    table = "connector_upgrade_approval_requests"
    for column in reversed(
        (
            "source_record_id",
            "instance_id",
            "connector_id",
            "candidate_receipt_id",
            "requested_by",
            "organization_id",
            "environment_id",
            "state",
            "expires_at",
        )
    ):
        op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
    op.drop_table(table)
