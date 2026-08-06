"""Add immutable connector package signing receipts.

Revision ID: 20260806_0042
Revises: 20260806_0041
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260806_0042"
down_revision: str | None = "20260806_0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "connector_package_signing_receipts"
    op.create_table(
        table,
        sa.Column("receipt_id", sa.String(length=128), nullable=False),
        sa.Column("source_attestation_report_id", sa.String(length=128), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("receipt_id"),
        sa.UniqueConstraint(
            "source_attestation_report_id",
            name="uq_connector_package_signing_receipts_attestation",
        ),
        sa.UniqueConstraint(
            "requested_by",
            "idempotency_key",
            name="uq_connector_package_signing_receipts_actor_idempotency",
        ),
    )
    for column in (
        "source_attestation_report_id",
        "requested_by",
        "organization_id",
        "environment_id",
    ):
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def downgrade() -> None:
    table = "connector_package_signing_receipts"
    for column in reversed(
        (
            "source_attestation_report_id",
            "requested_by",
            "organization_id",
            "environment_id",
        )
    ):
        op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
    op.drop_table(table)
