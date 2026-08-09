"""Add governed recommendation human-review request metadata.

Revision ID: 20260809_0086
Revises: 20260809_0085
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260809_0086"
down_revision: str | None = "20260809_0085"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recommendation_review_request_claims",
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("review_request_id", sa.String(128), nullable=False),
        sa.Column("recommendation_id", sa.String(128), nullable=False),
        sa.Column("readiness_assessment_id", sa.String(128), nullable=False),
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
            name="uq_recommendation_review_request_claim_actor_idem",
        ),
        sa.UniqueConstraint(
            "readiness_assessment_id",
            name="uq_recommendation_review_request_claim_assessment",
        ),
    )
    for name, column in {
        "ix_recommendation_review_request_claim_request": "review_request_id",
        "ix_recommendation_review_request_claim_recommendation": "recommendation_id",
        "ix_recommendation_review_request_claim_assessment": "readiness_assessment_id",
        "ix_recommendation_review_request_claim_subject": "claimed_by_subject_digest",
        "ix_recommendation_review_request_claim_org": "organization_id",
        "ix_recommendation_review_request_claim_env": "environment_id",
    }.items():
        op.create_index(name, "recommendation_review_request_claims", [column])

    op.create_table(
        "recommendation_review_requests",
        sa.Column("review_request_id", sa.String(128), nullable=False),
        sa.Column("recommendation_id", sa.String(128), nullable=False),
        sa.Column("readiness_assessment_id", sa.String(128), nullable=False),
        sa.Column("promotion_id", sa.String(128), nullable=False),
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("requester_subject_digest", sa.String(64), nullable=False),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("environment_id", sa.String(128), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("review_request_id"),
        sa.UniqueConstraint("claim_id", name="uq_recommendation_review_request_record_claim"),
        sa.UniqueConstraint(
            "readiness_assessment_id",
            name="uq_recommendation_review_request_record_assessment",
        ),
    )
    for name, column in {
        "ix_recommendation_review_request_recommendation": "recommendation_id",
        "ix_recommendation_review_request_assessment": "readiness_assessment_id",
        "ix_recommendation_review_request_promotion": "promotion_id",
        "ix_recommendation_review_request_claim": "claim_id",
        "ix_recommendation_review_request_subject": "requester_subject_digest",
        "ix_recommendation_review_request_org": "organization_id",
        "ix_recommendation_review_request_env": "environment_id",
        "ix_recommendation_review_request_state": "state",
        "ix_recommendation_review_request_expires": "expires_at",
    }.items():
        op.create_index(name, "recommendation_review_requests", [column])


def downgrade() -> None:
    op.drop_table("recommendation_review_requests")
    op.drop_table("recommendation_review_request_claims")
