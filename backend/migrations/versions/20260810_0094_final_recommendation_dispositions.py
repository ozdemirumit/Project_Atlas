"""Add governed final recommendation dispositions.

Revision ID: 20260810_0094
Revises: 20260810_0093
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260810_0094"
down_revision: str | None = "20260810_0093"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "final_recommendation_disposition_claims",
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("review_request_id", sa.String(length=128), nullable=False),
        sa.Column("disposition_id", sa.String(length=128), nullable=False),
        sa.Column("claimed_by_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("idempotency_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint("review_request_id", name="uq_rec_final_claim_request"),
        sa.UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_rec_final_claim_actor_idem",
        ),
    )
    for name, column in {
        "ix_rec_final_claim_request": "review_request_id",
        "ix_rec_final_claim_disposition": "disposition_id",
        "ix_rec_final_claim_subject": "claimed_by_subject_digest",
        "ix_rec_final_claim_org": "organization_id",
        "ix_rec_final_claim_env": "environment_id",
    }.items():
        op.create_index(name, "final_recommendation_disposition_claims", [column])

    op.create_table(
        "final_recommendation_dispositions",
        sa.Column("disposition_id", sa.String(length=128), nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("review_request_id", sa.String(length=128), nullable=False),
        sa.Column("recommendation_id", sa.String(length=128), nullable=False),
        sa.Column("disposition_code", sa.String(length=128), nullable=False),
        sa.Column("approved_by_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("disposition_id"),
        sa.UniqueConstraint("review_request_id", name="uq_rec_final_request"),
        sa.UniqueConstraint("claim_id", name="uq_rec_final_claim"),
    )
    for name, column in {
        "ix_rec_final_record_claim": "claim_id",
        "ix_rec_final_record_request": "review_request_id",
        "ix_rec_final_record_recommendation": "recommendation_id",
        "ix_rec_final_record_disposition": "disposition_code",
        "ix_rec_final_record_subject": "approved_by_subject_digest",
        "ix_rec_final_record_org": "organization_id",
        "ix_rec_final_record_env": "environment_id",
    }.items():
        op.create_index(name, "final_recommendation_dispositions", [column])


def downgrade() -> None:
    op.drop_table("final_recommendation_dispositions")
    op.drop_table("final_recommendation_disposition_claims")
