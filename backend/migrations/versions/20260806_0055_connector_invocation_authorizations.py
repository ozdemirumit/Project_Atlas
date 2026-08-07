"""add connector invocation authorizations

Revision ID: 20260806_0055
Revises: 20260806_0054
Create Date: 2026-08-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260806_0055"
down_revision: str | None = "20260806_0054"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connector_invocation_authorizations",
        sa.Column("authorization_id", sa.String(length=128), nullable=False),
        sa.Column("source_target_session_verification_id", sa.String(length=128), nullable=False),
        sa.Column("instance_id", sa.String(length=128), nullable=False),
        sa.Column("capability_id", sa.String(length=128), nullable=False),
        sa.Column("authorized_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("authorization_id"),
        sa.UniqueConstraint(
            "source_target_session_verification_id",
            name="uq_connector_invocation_authorizations_target_session",
        ),
        sa.UniqueConstraint(
            "authorized_by",
            "idempotency_key",
            name="uq_connector_invocation_authorizations_actor_idempotency",
        ),
    )
    for column in (
        "source_target_session_verification_id",
        "instance_id",
        "capability_id",
        "authorized_by",
        "organization_id",
        "environment_id",
    ):
        op.create_index(
            op.f(f"ix_connector_invocation_authorizations_{column}"),
            "connector_invocation_authorizations",
            [column],
            unique=False,
        )


def downgrade() -> None:
    op.drop_table("connector_invocation_authorizations")
