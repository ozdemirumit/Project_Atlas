"""add operational knowledge reviewer assignment claims and records

Revision ID: 20260806_0060
Revises: 20260806_0059
Create Date: 2026-08-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260806_0060"
down_revision: str | None = "20260806_0059"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_knowledge_reviewer_assignment_claims",
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("source_review_request_id", sa.String(length=128), nullable=False),
        sa.Column("assignment_set_id", sa.String(length=128), nullable=False),
        sa.Column("claimed_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "source_review_request_id",
            name="uq_operational_knowledge_reviewer_assignment_claims_source",
        ),
        sa.UniqueConstraint(
            "claimed_by",
            "idempotency_digest",
            name="uq_operational_knowledge_reviewer_assignment_claims_actor_idempotency",
        ),
    )
    for column in (
        "source_review_request_id",
        "assignment_set_id",
        "claimed_by",
        "organization_id",
        "environment_id",
    ):
        op.create_index(
            f"ix_operational_knowledge_reviewer_assignment_claims_{column}",
            "operational_knowledge_reviewer_assignment_claims",
            [column],
            unique=False,
        )

    op.create_table(
        "operational_knowledge_reviewer_assignments",
        sa.Column("assignment_set_id", sa.String(length=128), nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("source_review_request_id", sa.String(length=128), nullable=False),
        sa.Column("knowledge_item_id", sa.String(length=128), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("assignment_set_id"),
        sa.UniqueConstraint(
            "source_review_request_id",
            name="uq_operational_knowledge_reviewer_assignments_source",
        ),
        sa.UniqueConstraint(
            "claim_id",
            name="uq_operational_knowledge_reviewer_assignments_claim",
        ),
    )
    for column in (
        "claim_id",
        "source_review_request_id",
        "knowledge_item_id",
        "requested_by",
        "organization_id",
        "environment_id",
    ):
        op.create_index(
            f"ix_operational_knowledge_reviewer_assignments_{column}",
            "operational_knowledge_reviewer_assignments",
            [column],
            unique=False,
        )


def downgrade() -> None:
    op.drop_table("operational_knowledge_reviewer_assignments")
    op.drop_table("operational_knowledge_reviewer_assignment_claims")
