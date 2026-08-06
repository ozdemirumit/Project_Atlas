"""Add immutable connector credential assignments.

Revision ID: 20260806_0048
Revises: 20260806_0047
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260806_0048"
down_revision: str | None = "20260806_0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "connector_credential_assignments"
    op.create_table(
        table,
        sa.Column("assignment_id", sa.String(length=128), nullable=False),
        sa.Column("source_target_binding_id", sa.String(length=128), nullable=False),
        sa.Column("instance_id", sa.String(length=128), nullable=False),
        sa.Column("credential_profile_id", sa.String(length=128), nullable=False),
        sa.Column("assigned_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("assignment_id"),
        sa.UniqueConstraint(
            "source_target_binding_id",
            name="uq_connector_credential_assignments_target_binding",
        ),
        sa.UniqueConstraint(
            "assigned_by",
            "idempotency_key",
            name="uq_connector_credential_assignments_actor_idempotency",
        ),
    )
    for column in (
        "source_target_binding_id",
        "instance_id",
        "credential_profile_id",
        "assigned_by",
        "organization_id",
        "environment_id",
    ):
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def downgrade() -> None:
    table = "connector_credential_assignments"
    for column in reversed(
        (
            "source_target_binding_id",
            "instance_id",
            "credential_profile_id",
            "assigned_by",
            "organization_id",
            "environment_id",
        )
    ):
        op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
    op.drop_table(table)
