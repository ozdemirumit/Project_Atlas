"""add connector bounded invocation claims and completions

Revision ID: 20260806_0056
Revises: 20260806_0055
Create Date: 2026-08-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260806_0056"
down_revision: str | None = "20260806_0055"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connector_invocation_consumption_claims",
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("source_authorization_id", sa.String(length=128), nullable=False),
        sa.Column("invocation_id", sa.String(length=128), nullable=False),
        sa.Column("claimed_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "source_authorization_id",
            name="uq_connector_invocation_claims_authorization",
        ),
        sa.UniqueConstraint(
            "claimed_by",
            "idempotency_digest",
            name="uq_connector_invocation_claims_actor_idempotency",
        ),
    )
    for column in (
        "source_authorization_id",
        "invocation_id",
        "claimed_by",
        "organization_id",
        "environment_id",
    ):
        op.create_index(
            f"ix_connector_invocation_consumption_claims_{column}",
            "connector_invocation_consumption_claims",
            [column],
            unique=False,
        )

    op.create_table(
        "connector_bounded_invocations",
        sa.Column("invocation_id", sa.String(length=128), nullable=False),
        sa.Column("consumption_claim_id", sa.String(length=128), nullable=False),
        sa.Column("source_authorization_id", sa.String(length=128), nullable=False),
        sa.Column("instance_id", sa.String(length=128), nullable=False),
        sa.Column("capability_id", sa.String(length=128), nullable=False),
        sa.Column("invoked_by", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("invocation_id"),
        sa.UniqueConstraint(
            "source_authorization_id",
            name="uq_connector_bounded_invocations_authorization",
        ),
        sa.UniqueConstraint(
            "consumption_claim_id",
            name="uq_connector_bounded_invocations_claim",
        ),
    )
    for column in (
        "consumption_claim_id",
        "source_authorization_id",
        "instance_id",
        "capability_id",
        "invoked_by",
        "organization_id",
        "environment_id",
    ):
        op.create_index(
            f"ix_connector_bounded_invocations_{column}",
            "connector_bounded_invocations",
            [column],
            unique=False,
        )


def downgrade() -> None:
    op.drop_table("connector_bounded_invocations")
    op.drop_table("connector_invocation_consumption_claims")
