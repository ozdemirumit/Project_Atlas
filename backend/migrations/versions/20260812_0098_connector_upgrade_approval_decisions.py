"""Add governed connector upgrade approval decisions.

Revision ID: 20260812_0098
Revises: 20260812_0097
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260812_0098"
down_revision: str | None = "20260812_0097"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "connector_upgrade_approval_decisions"
    op.create_table(
        table,
        sa.Column("decision_id", sa.String(length=128), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("decided_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("decision_id"),
        sa.UniqueConstraint("request_id", name="uq_connector_upgrade_approval_decisions_request"),
        sa.UniqueConstraint(
            "decided_by",
            "idempotency_key",
            name="uq_connector_upgrade_approval_decisions_actor_idempotency",
        ),
    )
    for column in ("request_id", "decided_by", "organization_id", "environment_id"):
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def downgrade() -> None:
    table = "connector_upgrade_approval_decisions"
    for column in reversed(("request_id", "decided_by", "organization_id", "environment_id")):
        op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
    op.drop_table(table)
