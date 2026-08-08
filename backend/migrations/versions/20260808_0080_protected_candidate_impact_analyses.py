"""Add protected candidate-impact metadata.

Revision ID: 20260808_0080
Revises: 20260808_0079
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260808_0080"
down_revision: str | None = "20260808_0079"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "protected_candidate_impact_claims",
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("impact_analysis_id", sa.String(128), nullable=False),
        sa.Column("candidate_set_id", sa.String(128), nullable=False),
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
            name="uq_protected_candidate_impact_claim_actor_idem",
        ),
        sa.UniqueConstraint(
            "candidate_set_id", name="uq_protected_candidate_impact_claim_candidate_set"
        ),
    )
    for name, column in {
        "ix_protected_candidate_impact_claim_analysis": "impact_analysis_id",
        "ix_protected_candidate_impact_claim_candidate": "candidate_set_id",
        "ix_protected_candidate_impact_claim_subject": "claimed_by_subject_digest",
        "ix_protected_candidate_impact_claim_org": "organization_id",
        "ix_protected_candidate_impact_claim_env": "environment_id",
    }.items():
        op.create_index(name, "protected_candidate_impact_claims", [column])
    op.create_table(
        "protected_candidate_impact_analyses",
        sa.Column("impact_analysis_id", sa.String(128), nullable=False),
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("candidate_set_id", sa.String(128), nullable=False),
        sa.Column("consumer_subject_digest", sa.String(64), nullable=False),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("environment_id", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("impact_analysis_id"),
        sa.UniqueConstraint("claim_id", name="uq_protected_candidate_impact_claim"),
        sa.UniqueConstraint(
            "candidate_set_id", name="uq_protected_candidate_impact_candidate_set"
        ),
    )
    for name, column in {
        "ix_protected_candidate_impact_claim": "claim_id",
        "ix_protected_candidate_impact_candidate": "candidate_set_id",
        "ix_protected_candidate_impact_subject": "consumer_subject_digest",
        "ix_protected_candidate_impact_org": "organization_id",
        "ix_protected_candidate_impact_env": "environment_id",
        "ix_protected_candidate_impact_expires": "expires_at",
    }.items():
        op.create_index(name, "protected_candidate_impact_analyses", [column])


def downgrade() -> None:
    op.drop_table("protected_candidate_impact_analyses")
    op.drop_table("protected_candidate_impact_claims")
