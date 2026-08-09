"""Add governed recommendation domain promotion metadata.

Revision ID: 20260809_0084
Revises: 20260809_0083
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260809_0084"
down_revision: str | None = "20260809_0083"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recommendation_promotion_claims",
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("promotion_id", sa.String(128), nullable=False),
        sa.Column("recommendation_id", sa.String(128), nullable=False),
        sa.Column("presentation_id", sa.String(128), nullable=False),
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
            name="uq_recommendation_promotion_claim_actor_idem",
        ),
        sa.UniqueConstraint(
            "presentation_id", name="uq_recommendation_promotion_claim_presentation"
        ),
    )
    for name, column in {
        "ix_recommendation_promotion_claim_promotion": "promotion_id",
        "ix_recommendation_promotion_claim_recommendation": "recommendation_id",
        "ix_recommendation_promotion_claim_presentation": "presentation_id",
        "ix_recommendation_promotion_claim_subject": "claimed_by_subject_digest",
        "ix_recommendation_promotion_claim_org": "organization_id",
        "ix_recommendation_promotion_claim_env": "environment_id",
    }.items():
        op.create_index(name, "recommendation_promotion_claims", [column])
    op.create_table(
        "promoted_recommendation_artifacts",
        sa.Column("recommendation_id", sa.String(128), nullable=False),
        sa.Column("promotion_id", sa.String(128), nullable=False),
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("presentation_id", sa.String(128), nullable=False),
        sa.Column("consumer_subject_digest", sa.String(64), nullable=False),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("environment_id", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("recommendation_id"),
        sa.UniqueConstraint("claim_id", name="uq_promoted_recommendation_artifact_claim"),
        sa.UniqueConstraint(
            "presentation_id", name="uq_promoted_recommendation_artifact_presentation"
        ),
        sa.UniqueConstraint("promotion_id", name="uq_promoted_recommendation_artifact_promotion"),
    )
    for name, column in {
        "ix_promoted_recommendation_artifact_promotion": "promotion_id",
        "ix_promoted_recommendation_artifact_claim": "claim_id",
        "ix_promoted_recommendation_artifact_presentation": "presentation_id",
        "ix_promoted_recommendation_artifact_subject": "consumer_subject_digest",
        "ix_promoted_recommendation_artifact_org": "organization_id",
        "ix_promoted_recommendation_artifact_env": "environment_id",
        "ix_promoted_recommendation_artifact_expires": "expires_at",
    }.items():
        op.create_index(name, "promoted_recommendation_artifacts", [column])


def downgrade() -> None:
    op.drop_table("promoted_recommendation_artifacts")
    op.drop_table("recommendation_promotion_claims")
