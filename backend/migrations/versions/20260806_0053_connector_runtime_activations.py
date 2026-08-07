"""add connector runtime activations

Revision ID: 20260806_0053
Revises: 20260806_0052
Create Date: 2026-08-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260806_0053"
down_revision: str | None = "20260806_0052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connector_runtime_activations",
        sa.Column("activation_id", sa.String(length=128), nullable=False),
        sa.Column("source_brokerage_authorization_id", sa.String(length=128), nullable=False),
        sa.Column("instance_id", sa.String(length=128), nullable=False),
        sa.Column("activation_profile_id", sa.String(length=128), nullable=False),
        sa.Column("activated_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("activation_id"),
        sa.UniqueConstraint(
            "source_brokerage_authorization_id",
            name="uq_connector_runtime_activations_brokerage_authorization",
        ),
        sa.UniqueConstraint(
            "activated_by",
            "idempotency_key",
            name="uq_connector_runtime_activations_actor_idempotency",
        ),
    )
    for column in (
        "source_brokerage_authorization_id",
        "instance_id",
        "activation_profile_id",
        "activated_by",
        "organization_id",
        "environment_id",
    ):
        op.create_index(
            op.f(f"ix_connector_runtime_activations_{column}"),
            "connector_runtime_activations",
            [column],
            unique=False,
        )


def downgrade() -> None:
    op.drop_table("connector_runtime_activations")
