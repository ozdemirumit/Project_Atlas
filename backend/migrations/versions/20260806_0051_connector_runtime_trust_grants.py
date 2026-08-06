"""Add immutable connector runtime trust grants.

Revision ID: 20260806_0051
Revises: 20260806_0050
Create Date: 2026-08-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260806_0051"
down_revision: str | None = "20260806_0050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connector_runtime_trust_grants",
        sa.Column("grant_id", sa.String(length=128), nullable=False),
        sa.Column("source_enablement_id", sa.String(length=128), nullable=False),
        sa.Column("instance_id", sa.String(length=128), nullable=False),
        sa.Column("runtime_profile_id", sa.String(length=128), nullable=False),
        sa.Column("granted_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("grant_id"),
        sa.UniqueConstraint(
            "granted_by",
            "idempotency_key",
            name="uq_connector_runtime_trust_grants_actor_idempotency",
        ),
        sa.UniqueConstraint(
            "source_enablement_id",
            name="uq_connector_runtime_trust_grants_enablement",
        ),
    )
    op.create_index(
        op.f("ix_connector_runtime_trust_grants_environment_id"),
        "connector_runtime_trust_grants",
        ["environment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_connector_runtime_trust_grants_granted_by"),
        "connector_runtime_trust_grants",
        ["granted_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_connector_runtime_trust_grants_instance_id"),
        "connector_runtime_trust_grants",
        ["instance_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_connector_runtime_trust_grants_organization_id"),
        "connector_runtime_trust_grants",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_connector_runtime_trust_grants_runtime_profile_id"),
        "connector_runtime_trust_grants",
        ["runtime_profile_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_connector_runtime_trust_grants_source_enablement_id"),
        "connector_runtime_trust_grants",
        ["source_enablement_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_connector_runtime_trust_grants_source_enablement_id"),
        table_name="connector_runtime_trust_grants",
    )
    op.drop_index(
        op.f("ix_connector_runtime_trust_grants_runtime_profile_id"),
        table_name="connector_runtime_trust_grants",
    )
    op.drop_index(
        op.f("ix_connector_runtime_trust_grants_organization_id"),
        table_name="connector_runtime_trust_grants",
    )
    op.drop_index(
        op.f("ix_connector_runtime_trust_grants_instance_id"),
        table_name="connector_runtime_trust_grants",
    )
    op.drop_index(
        op.f("ix_connector_runtime_trust_grants_granted_by"),
        table_name="connector_runtime_trust_grants",
    )
    op.drop_index(
        op.f("ix_connector_runtime_trust_grants_environment_id"),
        table_name="connector_runtime_trust_grants",
    )
    op.drop_table("connector_runtime_trust_grants")
