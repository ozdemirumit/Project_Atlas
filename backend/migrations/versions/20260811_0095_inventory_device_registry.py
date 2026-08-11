"""Add governed inventory device records.

Revision ID: 20260811_0095
Revises: 20260810_0094
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260811_0095"
down_revision: str | None = "20260810_0094"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "inventory_device_records"
    op.create_table(
        table,
        sa.Column("device_id", sa.String(length=128), nullable=False),
        sa.Column("device_key", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("device_type", sa.String(length=32), nullable=False),
        sa.Column("vendor", sa.String(length=120), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("serial_number", sa.String(length=160), nullable=True),
        sa.Column("management_address", sa.String(length=253), nullable=True),
        sa.Column("lifecycle", sa.String(length=32), nullable=False),
        sa.Column("created_by", sa.String(length=128), nullable=False),
        sa.Column("create_idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retired_by", sa.String(length=128), nullable=True),
        sa.Column("retirement_idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("device_id"),
        sa.UniqueConstraint(
            "organization_id",
            "environment_id",
            "device_key",
            name="uq_inventory_device_records_scope_key",
        ),
        sa.UniqueConstraint(
            "created_by",
            "create_idempotency_key",
            name="uq_inventory_device_records_actor_create_idem",
        ),
        sa.UniqueConstraint(
            "retired_by",
            "retirement_idempotency_key",
            name="uq_inventory_device_records_actor_retire_idem",
        ),
    )
    for column in (
        "device_key",
        "device_type",
        "vendor",
        "lifecycle",
        "created_by",
        "retired_by",
        "organization_id",
        "environment_id",
        "site_id",
    ):
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def downgrade() -> None:
    table = "inventory_device_records"
    for column in reversed(
        (
            "device_key",
            "device_type",
            "vendor",
            "lifecycle",
            "created_by",
            "retired_by",
            "organization_id",
            "environment_id",
            "site_id",
        )
    ):
        op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
    op.drop_table(table)
