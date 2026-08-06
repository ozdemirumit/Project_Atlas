"""Add immutable connector package installation receipts.

Revision ID: 20260806_0045
Revises: 20260806_0044
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260806_0045"
down_revision: str | None = "20260806_0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "connector_package_installation_receipts"
    op.create_table(
        table,
        sa.Column("receipt_id", sa.String(length=128), nullable=False),
        sa.Column("source_registration_record_id", sa.String(length=128), nullable=False),
        sa.Column("connector_id", sa.String(length=128), nullable=False),
        sa.Column("release_version", sa.String(length=128), nullable=False),
        sa.Column("installation_store_profile_id", sa.String(length=128), nullable=False),
        sa.Column("installed_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("receipt_id"),
        sa.UniqueConstraint(
            "source_registration_record_id",
            name="uq_connector_package_installation_receipts_registration",
        ),
        sa.UniqueConstraint(
            "connector_id",
            "release_version",
            name="uq_connector_package_installation_receipts_release",
        ),
        sa.UniqueConstraint(
            "installed_by",
            "idempotency_key",
            name="uq_connector_package_installation_receipts_actor_idempotency",
        ),
    )
    for column in (
        "source_registration_record_id",
        "connector_id",
        "installation_store_profile_id",
        "installed_by",
        "organization_id",
        "environment_id",
    ):
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def downgrade() -> None:
    table = "connector_package_installation_receipts"
    for column in reversed(
        (
            "source_registration_record_id",
            "connector_id",
            "installation_store_profile_id",
            "installed_by",
            "organization_id",
            "environment_id",
        )
    ):
        op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
    op.drop_table(table)
