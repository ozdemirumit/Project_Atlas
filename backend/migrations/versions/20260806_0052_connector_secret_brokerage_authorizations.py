"""add connector secret brokerage authorizations

Revision ID: 20260806_0052
Revises: 20260806_0051
Create Date: 2026-08-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260806_0052"
down_revision: str | None = "20260806_0051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connector_secret_brokerage_authorizations",
        sa.Column("authorization_id", sa.String(length=128), nullable=False),
        sa.Column("source_runtime_trust_grant_id", sa.String(length=128), nullable=False),
        sa.Column("instance_id", sa.String(length=128), nullable=False),
        sa.Column("brokerage_profile_id", sa.String(length=128), nullable=False),
        sa.Column("authorized_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("authorization_id"),
        sa.UniqueConstraint(
            "source_runtime_trust_grant_id",
            name="uq_connector_secret_brokerage_authorizations_runtime_trust",
        ),
        sa.UniqueConstraint(
            "authorized_by",
            "idempotency_key",
            name="uq_connector_secret_brokerage_authorizations_actor_idempotency",
        ),
    )
    for column in (
        "source_runtime_trust_grant_id",
        "instance_id",
        "brokerage_profile_id",
        "authorized_by",
        "organization_id",
        "environment_id",
    ):
        op.create_index(
            op.f(f"ix_connector_secret_brokerage_authorizations_{column}"),
            "connector_secret_brokerage_authorizations",
            [column],
            unique=False,
        )


def downgrade() -> None:
    op.drop_table("connector_secret_brokerage_authorizations")
