"""Add immutable connector capability enablements.

Revision ID: 20260806_0050
Revises: 20260806_0049
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260806_0050"
down_revision: str | None = "20260806_0049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "connector_capability_enablements"
    op.create_table(
        table,
        sa.Column("enablement_id", sa.String(length=128), nullable=False),
        sa.Column("source_validation_id", sa.String(length=128), nullable=False),
        sa.Column("instance_id", sa.String(length=128), nullable=False),
        sa.Column("capability_profile_id", sa.String(length=128), nullable=False),
        sa.Column("enabled_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("enablement_id"),
        sa.UniqueConstraint(
            "source_validation_id", name="uq_connector_capability_enablements_validation"
        ),
        sa.UniqueConstraint(
            "enabled_by",
            "idempotency_key",
            name="uq_connector_capability_enablements_actor_idempotency",
        ),
    )
    for column in (
        "source_validation_id",
        "instance_id",
        "capability_profile_id",
        "enabled_by",
        "organization_id",
        "environment_id",
    ):
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def downgrade() -> None:
    table = "connector_capability_enablements"
    for column in reversed(
        (
            "source_validation_id",
            "instance_id",
            "capability_profile_id",
            "enabled_by",
            "organization_id",
            "environment_id",
        )
    ):
        op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
    op.drop_table(table)
