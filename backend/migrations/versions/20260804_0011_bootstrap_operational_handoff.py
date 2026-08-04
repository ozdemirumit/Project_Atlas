"""Add operational bootstrap handoff state.

Revision ID: 20260804_0011
Revises: 20260804_0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260804_0011"
down_revision: str | None = "20260804_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "platform_bootstrap_runs",
        sa.Column(
            "operational_handoff",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("platform_bootstrap_runs", "operational_handoff")
