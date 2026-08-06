"""Add immutable connector publisher attestation reports.

Revision ID: 20260806_0041
Revises: 20260806_0040
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260806_0041"
down_revision: str | None = "20260806_0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "connector_publisher_attestations"
    op.create_table(
        table,
        sa.Column("report_id", sa.String(length=128), nullable=False),
        sa.Column("source_approval_request_id", sa.String(length=128), nullable=False),
        sa.Column("verified_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("report_id"),
        sa.UniqueConstraint(
            "source_approval_request_id",
            name="uq_connector_publisher_attestations_approval",
        ),
        sa.UniqueConstraint(
            "verified_by",
            "idempotency_key",
            name="uq_connector_publisher_attestations_actor_idempotency",
        ),
    )
    for column in (
        "source_approval_request_id",
        "verified_by",
        "organization_id",
        "environment_id",
    ):
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def downgrade() -> None:
    table = "connector_publisher_attestations"
    for column in reversed(
        (
            "source_approval_request_id",
            "verified_by",
            "organization_id",
            "environment_id",
        )
    ):
        op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
    op.drop_table(table)
