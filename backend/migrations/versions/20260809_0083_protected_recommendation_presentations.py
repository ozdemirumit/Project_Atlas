"""Add protected recommendation presentation metadata.

Revision ID: 20260809_0083
Revises: 20260808_0082
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260809_0083"
down_revision: str | None = "20260808_0082"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "protected_recommendation_presentation_claims",
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("presentation_id", sa.String(128), nullable=False),
        sa.Column("adjudication_id", sa.String(128), nullable=False),
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
            name="uq_protected_recommendation_presentation_claim_actor_idem",
        ),
        sa.UniqueConstraint(
            "adjudication_id",
            name="uq_protected_recommendation_presentation_claim_adjudication",
        ),
    )
    for name, column in {
        "ix_protected_recommendation_presentation_claim_presentation": "presentation_id",
        "ix_protected_recommendation_presentation_claim_adjudication": "adjudication_id",
        "ix_protected_recommendation_presentation_claim_subject": "claimed_by_subject_digest",
        "ix_protected_recommendation_presentation_claim_org": "organization_id",
        "ix_protected_recommendation_presentation_claim_env": "environment_id",
    }.items():
        op.create_index(name, "protected_recommendation_presentation_claims", [column])
    op.create_table(
        "protected_recommendation_presentations",
        sa.Column("presentation_id", sa.String(128), nullable=False),
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("adjudication_id", sa.String(128), nullable=False),
        sa.Column("consumer_subject_digest", sa.String(64), nullable=False),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("environment_id", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("presentation_id"),
        sa.UniqueConstraint("claim_id", name="uq_protected_recommendation_presentation_claim"),
        sa.UniqueConstraint(
            "adjudication_id", name="uq_protected_recommendation_presentation_adjudication"
        ),
    )
    for name, column in {
        "ix_protected_recommendation_presentation_claim": "claim_id",
        "ix_protected_recommendation_presentation_adjudication": "adjudication_id",
        "ix_protected_recommendation_presentation_subject": "consumer_subject_digest",
        "ix_protected_recommendation_presentation_org": "organization_id",
        "ix_protected_recommendation_presentation_env": "environment_id",
        "ix_protected_recommendation_presentation_expires": "expires_at",
    }.items():
        op.create_index(name, "protected_recommendation_presentations", [column])


def downgrade() -> None:
    op.drop_table("protected_recommendation_presentations")
    op.drop_table("protected_recommendation_presentation_claims")
