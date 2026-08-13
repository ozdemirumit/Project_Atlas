"""Add governed ITSM integration profiles.

Revision ID: 20260813_0104
Revises: 20260813_0103
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260813_0104"
down_revision: str | None = "20260813_0103"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "itsm_integration_profiles"
    op.create_table(
        table,
        sa.Column("profile_id", sa.String(length=128), nullable=False),
        sa.Column("profile_key", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("provider_family", sa.String(length=64), nullable=False),
        sa.Column("lifecycle", sa.String(length=32), nullable=False),
        sa.Column("readiness_state", sa.String(length=32), nullable=False),
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
        sa.PrimaryKeyConstraint("profile_id"),
        sa.UniqueConstraint(
            "organization_id",
            "environment_id",
            "profile_key",
            name="uq_itsm_integration_profiles_scope_key",
        ),
        sa.UniqueConstraint(
            "created_by",
            "create_idempotency_key",
            name="uq_itsm_integration_profiles_actor_create_idem",
        ),
        sa.UniqueConstraint(
            "retired_by",
            "retirement_idempotency_key",
            name="uq_itsm_integration_profiles_actor_retire_idem",
        ),
    )
    for column in (
        "profile_key",
        "provider_family",
        "lifecycle",
        "readiness_state",
        "created_by",
        "retired_by",
        "organization_id",
        "environment_id",
        "site_id",
    ):
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def downgrade() -> None:
    table = "itsm_integration_profiles"
    for column in reversed(
        (
            "profile_key",
            "provider_family",
            "lifecycle",
            "readiness_state",
            "created_by",
            "retired_by",
            "organization_id",
            "environment_id",
            "site_id",
        )
    ):
        op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
    op.drop_table(table)
