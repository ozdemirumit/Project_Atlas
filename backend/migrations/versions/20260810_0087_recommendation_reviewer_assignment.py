"""Add governed recommendation reviewer assignment metadata.

Revision ID: 20260810_0087
Revises: 20260809_0086
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260810_0087"
down_revision: str | None = "20260809_0086"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recommendation_reviewer_assignment_claims",
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("assignment_set_id", sa.String(128), nullable=False),
        sa.Column("review_request_id", sa.String(128), nullable=False),
        sa.Column("claimed_by_subject_digest", sa.String(64), nullable=False),
        sa.Column("idempotency_digest", sa.String(64), nullable=False),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("environment_id", sa.String(128), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_recommendation_reviewer_assignment_claim_actor_idem",
        ),
        sa.UniqueConstraint(
            "review_request_id",
            name="uq_recommendation_reviewer_assignment_claim_request",
        ),
    )
    for name, column in {
        "ix_recommendation_reviewer_assignment_claim_set": "assignment_set_id",
        "ix_recommendation_reviewer_assignment_claim_request": "review_request_id",
        "ix_recommendation_reviewer_assignment_claim_subject": "claimed_by_subject_digest",
        "ix_recommendation_reviewer_assignment_claim_org": "organization_id",
        "ix_recommendation_reviewer_assignment_claim_env": "environment_id",
    }.items():
        op.create_index(name, "recommendation_reviewer_assignment_claims", [column])

    op.create_table(
        "recommendation_reviewer_assignments",
        sa.Column("assignment_set_id", sa.String(128), nullable=False),
        sa.Column("review_request_id", sa.String(128), nullable=False),
        sa.Column("recommendation_id", sa.String(128), nullable=False),
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("environment_id", sa.String(128), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("assignment_set_id"),
        sa.UniqueConstraint("claim_id", name="uq_recommendation_reviewer_assignment_record_claim"),
        sa.UniqueConstraint(
            "review_request_id", name="uq_recommendation_reviewer_assignment_record_request"
        ),
    )
    for name, column in {
        "ix_recommendation_reviewer_assignment_request": "review_request_id",
        "ix_recommendation_reviewer_assignment_recommendation": "recommendation_id",
        "ix_recommendation_reviewer_assignment_claim": "claim_id",
        "ix_recommendation_reviewer_assignment_org": "organization_id",
        "ix_recommendation_reviewer_assignment_env": "environment_id",
        "ix_recommendation_reviewer_assignment_state": "state",
        "ix_recommendation_reviewer_assignment_expires": "expires_at",
    }.items():
        op.create_index(name, "recommendation_reviewer_assignments", [column])


def downgrade() -> None:
    op.drop_table("recommendation_reviewer_assignments")
    op.drop_table("recommendation_reviewer_assignment_claims")
