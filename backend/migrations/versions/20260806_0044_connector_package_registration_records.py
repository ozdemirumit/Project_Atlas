"""Add immutable connector package registration records.

Revision ID: 20260806_0044
Revises: 20260806_0043
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260806_0044"
down_revision: str | None = "20260806_0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "connector_package_registration_records"
    op.create_table(
        table,
        sa.Column("record_id", sa.String(length=128), nullable=False),
        sa.Column("source_publication_receipt_id", sa.String(length=128), nullable=False),
        sa.Column("connector_id", sa.String(length=128), nullable=False),
        sa.Column("release_version", sa.String(length=128), nullable=False),
        sa.Column("registered_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("record_id"),
        sa.UniqueConstraint(
            "source_publication_receipt_id",
            name="uq_connector_package_registration_records_publication",
        ),
        sa.UniqueConstraint(
            "connector_id",
            "release_version",
            name="uq_connector_package_registration_records_release",
        ),
        sa.UniqueConstraint(
            "registered_by",
            "idempotency_key",
            name="uq_connector_package_registration_records_actor_idempotency",
        ),
    )
    for column in (
        "source_publication_receipt_id",
        "connector_id",
        "registered_by",
        "organization_id",
        "environment_id",
    ):
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def downgrade() -> None:
    table = "connector_package_registration_records"
    for column in reversed(
        (
            "source_publication_receipt_id",
            "connector_id",
            "registered_by",
            "organization_id",
            "environment_id",
        )
    ):
        op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
    op.drop_table(table)
