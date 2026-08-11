"""Add governed connector instance lifecycle fields.

Revision ID: 20260811_0096
Revises: 20260811_0095
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0096"
down_revision: str | None = "20260811_0095"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "connector_instance_records"
    op.add_column(table, sa.Column("display_name", sa.String(length=200), nullable=True))
    op.add_column(
        table,
        sa.Column(
            "instance_state",
            sa.String(length=32),
            nullable=False,
            server_default="disabled_unconfigured",
        ),
    )
    op.add_column(table, sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column(table, sa.Column("retired_by", sa.String(length=128), nullable=True))
    op.add_column(
        table, sa.Column("retirement_idempotency_key", sa.String(length=128), nullable=True)
    )
    op.execute(
        "UPDATE connector_instance_records "
        "SET display_name = payload ->> 'display_name' "
        "WHERE display_name IS NULL"
    )
    op.alter_column(table, "display_name", existing_type=sa.String(length=200), nullable=False)
    op.create_unique_constraint(
        "uq_connector_instance_records_actor_retire_idem",
        table,
        ["retired_by", "retirement_idempotency_key"],
    )
    for column in ("display_name", "instance_state", "retired_by"):
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def downgrade() -> None:
    table = "connector_instance_records"
    for column in reversed(("display_name", "instance_state", "retired_by")):
        op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
    op.drop_constraint("uq_connector_instance_records_actor_retire_idem", table, type_="unique")
    for column in (
        "retirement_idempotency_key",
        "retired_by",
        "version",
        "instance_state",
        "display_name",
    ):
        op.drop_column(table, column)
