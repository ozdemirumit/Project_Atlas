"""Add governed recommendation corrections.

Revision ID: 20260810_0093
Revises: 20260810_0092
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260810_0093"
down_revision: str | None = "20260810_0092"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recommendation_correction_claims",
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("source_review_request_id", sa.String(length=128), nullable=False),
        sa.Column("correction_id", sa.String(length=128), nullable=False),
        sa.Column("claimed_by_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("idempotency_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint("source_review_request_id", name="uq_rec_corr_claim_source"),
        sa.UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_rec_corr_claim_actor_idem",
        ),
    )
    for name, column in {
        "ix_rec_corr_claim_source": "source_review_request_id",
        "ix_rec_corr_claim_correction": "correction_id",
        "ix_rec_corr_claim_subject": "claimed_by_subject_digest",
        "ix_rec_corr_claim_org": "organization_id",
        "ix_rec_corr_claim_env": "environment_id",
    }.items():
        op.create_index(name, "recommendation_correction_claims", [column])

    op.create_table(
        "recommendation_corrections",
        sa.Column("correction_id", sa.String(length=128), nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("source_review_request_id", sa.String(length=128), nullable=False),
        sa.Column("source_recommendation_id", sa.String(length=128), nullable=False),
        sa.Column("new_recommendation_id", sa.String(length=128), nullable=False),
        sa.Column("new_promotion_id", sa.String(length=128), nullable=False),
        sa.Column("corrected_by_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("correction_id"),
        sa.UniqueConstraint("source_review_request_id", name="uq_rec_corr_source"),
        sa.UniqueConstraint("claim_id", name="uq_rec_corr_claim"),
        sa.UniqueConstraint("new_recommendation_id", name="uq_rec_corr_new_rec"),
    )
    for name, column in {
        "ix_rec_corr_record_claim": "claim_id",
        "ix_rec_corr_record_source": "source_review_request_id",
        "ix_rec_corr_record_source_rec": "source_recommendation_id",
        "ix_rec_corr_record_new_rec": "new_recommendation_id",
        "ix_rec_corr_record_new_promotion": "new_promotion_id",
        "ix_rec_corr_record_subject": "corrected_by_subject_digest",
        "ix_rec_corr_record_org": "organization_id",
        "ix_rec_corr_record_env": "environment_id",
    }.items():
        op.create_index(name, "recommendation_corrections", [column])


def downgrade() -> None:
    op.drop_table("recommendation_corrections")
    op.drop_table("recommendation_correction_claims")
