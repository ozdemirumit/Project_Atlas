"""Add governed recommendation protected content presentations.

Revision ID: 20260810_0089
Revises: 20260810_0088
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260810_0089"
down_revision: str | None = "20260810_0088"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recommendation_protected_content_claims",
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("source_lease_id", sa.String(128), nullable=False),
        sa.Column("presentation_id", sa.String(128), nullable=False),
        sa.Column("claimed_by_subject_digest", sa.String(64), nullable=False),
        sa.Column("idempotency_digest", sa.String(64), nullable=False),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("environment_id", sa.String(128), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "source_lease_id", name="uq_recommendation_protected_content_claim_source_lease"
        ),
        sa.UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_recommendation_content_claim_actor_idem",
        ),
    )
    for name, column in {
        "ix_recommendation_content_claim_lease": "source_lease_id",
        "ix_recommendation_content_claim_presentation": "presentation_id",
        "ix_recommendation_content_claim_subject": "claimed_by_subject_digest",
        "ix_recommendation_content_claim_org": "organization_id",
        "ix_recommendation_content_claim_env": "environment_id",
    }.items():
        op.create_index(name, "recommendation_protected_content_claims", [column])

    op.create_table(
        "recommendation_protected_content_presentations",
        sa.Column("presentation_id", sa.String(128), nullable=False),
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("source_lease_id", sa.String(128), nullable=False),
        sa.Column("source_assignment_set_id", sa.String(128), nullable=False),
        sa.Column("recommendation_id", sa.String(128), nullable=False),
        sa.Column("track_code", sa.String(128), nullable=False),
        sa.Column("lease_holder_subject_digest", sa.String(64), nullable=False),
        sa.Column("presented_content_digest", sa.String(64), nullable=False),
        sa.Column("content_bytes", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("environment_id", sa.String(128), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("presentation_id"),
        sa.UniqueConstraint(
            "source_lease_id", name="uq_recommendation_content_present_source_lease"
        ),
        sa.UniqueConstraint("claim_id", name="uq_recommendation_content_present_claim"),
    )
    for name, column in {
        "ix_recommendation_content_present_claim": "claim_id",
        "ix_recommendation_content_present_lease": "source_lease_id",
        "ix_recommendation_content_present_set": "source_assignment_set_id",
        "ix_recommendation_content_present_recommendation": "recommendation_id",
        "ix_recommendation_content_present_track": "track_code",
        "ix_recommendation_content_present_holder": "lease_holder_subject_digest",
        "ix_recommendation_content_present_org": "organization_id",
        "ix_recommendation_content_present_env": "environment_id",
    }.items():
        op.create_index(name, "recommendation_protected_content_presentations", [column])


def downgrade() -> None:
    op.drop_table("recommendation_protected_content_presentations")
    op.drop_table("recommendation_protected_content_claims")
