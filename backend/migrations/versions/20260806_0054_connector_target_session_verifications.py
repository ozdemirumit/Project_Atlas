"""add connector target session verifications

Revision ID: 20260806_0054
Revises: 20260806_0053
Create Date: 2026-08-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260806_0054"
down_revision: str | None = "20260806_0053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connector_target_session_verifications",
        sa.Column("verification_id", sa.String(length=128), nullable=False),
        sa.Column("source_runtime_activation_id", sa.String(length=128), nullable=False),
        sa.Column("instance_id", sa.String(length=128), nullable=False),
        sa.Column("session_profile_id", sa.String(length=128), nullable=False),
        sa.Column("verified_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("verification_id"),
        sa.UniqueConstraint(
            "source_runtime_activation_id",
            name="uq_connector_target_sessions_runtime_activation",
        ),
        sa.UniqueConstraint(
            "verified_by",
            "idempotency_key",
            name="uq_connector_target_sessions_actor_idempotency",
        ),
    )
    for column in (
        "source_runtime_activation_id",
        "instance_id",
        "session_profile_id",
        "verified_by",
        "organization_id",
        "environment_id",
    ):
        op.create_index(
            f"ix_connector_target_session_verifications_{column}",
            "connector_target_session_verifications",
            [column],
            unique=False,
        )


def downgrade() -> None:
    op.drop_table("connector_target_session_verifications")
