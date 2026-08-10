"""Add governed recommendation protected inspection leases.

Revision ID: 20260810_0088
Revises: 20260810_0087
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260810_0088"
down_revision: str | None = "20260810_0087"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recommendation_protected_inspection_claims",
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("source_assignment_set_id", sa.String(128), nullable=False),
        sa.Column("track_code", sa.String(128), nullable=False),
        sa.Column("lease_id", sa.String(128), nullable=False),
        sa.Column("claimed_by_subject_digest", sa.String(64), nullable=False),
        sa.Column("idempotency_digest", sa.String(64), nullable=False),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("environment_id", sa.String(128), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "source_assignment_set_id",
            "track_code",
            name="uq_recommendation_inspection_claim_source_track",
        ),
        sa.UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_recommendation_inspection_claim_actor_idem",
        ),
    )
    for name, column in {
        "ix_recommendation_inspection_claim_set": "source_assignment_set_id",
        "ix_recommendation_inspection_claim_track": "track_code",
        "ix_recommendation_inspection_claim_lease": "lease_id",
        "ix_recommendation_inspection_claim_subject": "claimed_by_subject_digest",
        "ix_recommendation_inspection_claim_org": "organization_id",
        "ix_recommendation_inspection_claim_env": "environment_id",
    }.items():
        op.create_index(name, "recommendation_protected_inspection_claims", [column])

    op.create_table(
        "recommendation_protected_inspection_leases",
        sa.Column("lease_id", sa.String(128), nullable=False),
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("source_assignment_set_id", sa.String(128), nullable=False),
        sa.Column("recommendation_id", sa.String(128), nullable=False),
        sa.Column("track_code", sa.String(128), nullable=False),
        sa.Column("lease_holder_subject_digest", sa.String(64), nullable=False),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("environment_id", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("lease_id"),
        sa.UniqueConstraint(
            "source_assignment_set_id",
            "track_code",
            name="uq_recommendation_inspection_lease_source_track",
        ),
        sa.UniqueConstraint("claim_id", name="uq_recommendation_inspection_lease_claim"),
    )
    for name, column in {
        "ix_recommendation_inspection_lease_claim": "claim_id",
        "ix_recommendation_inspection_lease_set": "source_assignment_set_id",
        "ix_recommendation_inspection_lease_recommendation": "recommendation_id",
        "ix_recommendation_inspection_lease_track": "track_code",
        "ix_recommendation_inspection_lease_holder": "lease_holder_subject_digest",
        "ix_recommendation_inspection_lease_org": "organization_id",
        "ix_recommendation_inspection_lease_env": "environment_id",
        "ix_recommendation_inspection_lease_expires": "expires_at",
    }.items():
        op.create_index(name, "recommendation_protected_inspection_leases", [column])


def downgrade() -> None:
    op.drop_table("recommendation_protected_inspection_leases")
    op.drop_table("recommendation_protected_inspection_claims")
