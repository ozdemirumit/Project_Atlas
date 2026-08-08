"""Add protected recommendation adjudication metadata.

Revision ID: 20260808_0082
Revises: 20260808_0081
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260808_0082"
down_revision: str | None = "20260808_0081"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "protected_recommendation_adjudication_claims",
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("adjudication_id", sa.String(128), nullable=False),
        sa.Column("completion_id", sa.String(128), nullable=False),
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
            name="uq_protected_recommendation_adjudication_claim_actor_idem",
        ),
        sa.UniqueConstraint(
            "completion_id",
            name="uq_protected_recommendation_adjudication_claim_completion",
        ),
    )
    for name, column in {
        "ix_protected_recommendation_adjudication_claim_adjudication": "adjudication_id",
        "ix_protected_recommendation_adjudication_claim_completion": "completion_id",
        "ix_protected_recommendation_adjudication_claim_subject": "claimed_by_subject_digest",
        "ix_protected_recommendation_adjudication_claim_org": "organization_id",
        "ix_protected_recommendation_adjudication_claim_env": "environment_id",
    }.items():
        op.create_index(name, "protected_recommendation_adjudication_claims", [column])
    op.create_table(
        "protected_recommendation_adjudications",
        sa.Column("adjudication_id", sa.String(128), nullable=False),
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("completion_id", sa.String(128), nullable=False),
        sa.Column("candidate_set_id", sa.String(128), nullable=False),
        sa.Column("consumer_subject_digest", sa.String(64), nullable=False),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("environment_id", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("adjudication_id"),
        sa.UniqueConstraint("claim_id", name="uq_protected_recommendation_adjudication_claim"),
        sa.UniqueConstraint(
            "completion_id", name="uq_protected_recommendation_adjudication_completion"
        ),
    )
    for name, column in {
        "ix_protected_recommendation_adjudication_claim": "claim_id",
        "ix_protected_recommendation_adjudication_completion": "completion_id",
        "ix_protected_recommendation_adjudication_candidate": "candidate_set_id",
        "ix_protected_recommendation_adjudication_subject": "consumer_subject_digest",
        "ix_protected_recommendation_adjudication_org": "organization_id",
        "ix_protected_recommendation_adjudication_env": "environment_id",
        "ix_protected_recommendation_adjudication_expires": "expires_at",
    }.items():
        op.create_index(name, "protected_recommendation_adjudications", [column])


def downgrade() -> None:
    op.drop_table("protected_recommendation_adjudications")
    op.drop_table("protected_recommendation_adjudication_claims")
