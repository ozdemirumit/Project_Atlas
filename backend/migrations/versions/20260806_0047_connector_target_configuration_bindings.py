"""Add immutable connector target configuration bindings.

Revision ID: 20260806_0047
Revises: 20260806_0046
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260806_0047"
down_revision: str | None = "20260806_0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "connector_target_configuration_bindings"
    op.create_table(
        table,
        sa.Column("binding_id", sa.String(length=128), nullable=False),
        sa.Column("source_instance_record_id", sa.String(length=128), nullable=False),
        sa.Column("instance_id", sa.String(length=128), nullable=False),
        sa.Column("target_profile_id", sa.String(length=128), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("bound_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("binding_id"),
        sa.UniqueConstraint(
            "source_instance_record_id",
            name="uq_connector_target_configuration_bindings_instance",
        ),
        sa.UniqueConstraint(
            "bound_by",
            "idempotency_key",
            name="uq_connector_target_configuration_bindings_actor_idempotency",
        ),
    )
    for column in (
        "source_instance_record_id",
        "instance_id",
        "target_profile_id",
        "target_id",
        "bound_by",
        "organization_id",
        "environment_id",
    ):
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def downgrade() -> None:
    table = "connector_target_configuration_bindings"
    for column in reversed(
        (
            "source_instance_record_id",
            "instance_id",
            "target_profile_id",
            "target_id",
            "bound_by",
            "organization_id",
            "environment_id",
        )
    ):
        op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
    op.drop_table(table)
