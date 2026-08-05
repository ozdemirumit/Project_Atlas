"""Add immutable connector package final validations.

Revision ID: 20260806_0039
Revises: 20260806_0038
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260806_0039"
down_revision: str | None = "20260806_0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "connector_package_final_validations"
    op.create_table(
        table,
        sa.Column("validation_id", sa.String(length=128), nullable=False),
        sa.Column("source_lab_self_test_id", sa.String(length=128), nullable=False),
        sa.Column("validated_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("validation_id"),
        sa.UniqueConstraint(
            "source_lab_self_test_id",
            name="uq_connector_package_final_validations_source",
        ),
        sa.UniqueConstraint(
            "validated_by",
            "idempotency_key",
            name="uq_connector_package_final_validations_actor_idempotency",
        ),
    )
    for column in (
        "source_lab_self_test_id",
        "validated_by",
        "organization_id",
        "environment_id",
    ):
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def downgrade() -> None:
    table = "connector_package_final_validations"
    for column in reversed(
        (
            "source_lab_self_test_id",
            "validated_by",
            "organization_id",
            "environment_id",
        )
    ):
        op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
    op.drop_table(table)
