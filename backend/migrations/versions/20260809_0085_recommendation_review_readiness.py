"""Add governed recommendation review-readiness metadata.

Revision ID: 20260809_0085
Revises: 20260809_0084
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260809_0085"
down_revision: str | None = "20260809_0084"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recommendation_readiness_claims",
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("assessment_id", sa.String(128), nullable=False),
        sa.Column("recommendation_id", sa.String(128), nullable=False),
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
            name="uq_recommendation_readiness_claim_actor_idem",
        ),
        sa.UniqueConstraint(
            "recommendation_id", name="uq_recommendation_readiness_claim_recommendation"
        ),
    )
    for name, column in {
        "ix_recommendation_readiness_claim_assessment": "assessment_id",
        "ix_recommendation_readiness_claim_recommendation": "recommendation_id",
        "ix_recommendation_readiness_claim_subject": "claimed_by_subject_digest",
        "ix_recommendation_readiness_claim_org": "organization_id",
        "ix_recommendation_readiness_claim_env": "environment_id",
    }.items():
        op.create_index(name, "recommendation_readiness_claims", [column])
    op.create_table(
        "recommendation_readiness_assessments",
        sa.Column("assessment_id", sa.String(128), nullable=False),
        sa.Column("recommendation_id", sa.String(128), nullable=False),
        sa.Column("promotion_id", sa.String(128), nullable=False),
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("consumer_subject_digest", sa.String(64), nullable=False),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("environment_id", sa.String(128), nullable=False),
        sa.Column("evaluation_outcome", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("assessment_id"),
        sa.UniqueConstraint("claim_id", name="uq_recommendation_readiness_assessment_claim"),
        sa.UniqueConstraint(
            "recommendation_id",
            name="uq_recommendation_readiness_assessment_recommendation",
        ),
    )
    for name, column in {
        "ix_recommendation_readiness_assessment_recommendation": "recommendation_id",
        "ix_recommendation_readiness_assessment_promotion": "promotion_id",
        "ix_recommendation_readiness_assessment_claim": "claim_id",
        "ix_recommendation_readiness_assessment_subject": "consumer_subject_digest",
        "ix_recommendation_readiness_assessment_org": "organization_id",
        "ix_recommendation_readiness_assessment_env": "environment_id",
        "ix_recommendation_readiness_assessment_outcome": "evaluation_outcome",
        "ix_recommendation_readiness_assessment_expires": "expires_at",
    }.items():
        op.create_index(name, "recommendation_readiness_assessments", [column])


def downgrade() -> None:
    op.drop_table("recommendation_readiness_assessments")
    op.drop_table("recommendation_readiness_claims")
