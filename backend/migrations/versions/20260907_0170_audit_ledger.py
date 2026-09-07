"""Add the durable, append-only audit ledger.

Revision ID: 20260907_0170
Revises: 20260827_0169
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260907_0170"
down_revision: str | None = "20260827_0169"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_ledger_heads",
        sa.Column("ledger_name", sa.String(length=128), nullable=False),
        sa.Column("last_sequence", sa.BigInteger(), nullable=False),
        sa.Column("last_digest", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("ledger_name"),
    )
    op.create_table(
        "audit_ledger_records",
        sa.Column("ledger_name", sa.String(length=128), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("previous_record_digest", sa.String(length=64), nullable=False),
        sa.Column("record_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("ledger_name", "sequence"),
        sa.UniqueConstraint("ledger_name", "event_id", name="uq_audit_ledger_records_event"),
    )


def downgrade() -> None:
    op.drop_table("audit_ledger_records")
    op.drop_table("audit_ledger_heads")
