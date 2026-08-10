"""Add governed recommendation finding presentations.

Revision ID: 20260810_0091
Revises: 20260810_0090
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260810_0091"
down_revision: str | None = "20260810_0090"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recommendation_finding_presentation_claims",
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("source_finding_packet_id", sa.String(length=128), nullable=False),
        sa.Column("finding_presentation_id", sa.String(length=128), nullable=False),
        sa.Column("track_code", sa.String(length=128), nullable=False),
        sa.Column("claimed_by_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("idempotency_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "source_finding_packet_id", name="uq_recommendation_finding_present_claim_source"
        ),
        sa.UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_recommendation_finding_present_claim_actor_idem",
        ),
    )
    for column in (
        "source_finding_packet_id",
        "finding_presentation_id",
        "track_code",
        "claimed_by_subject_digest",
        "organization_id",
        "environment_id",
    ):
        op.create_index(
            f"ix_rec_finding_present_claim_{column}",
            "recommendation_finding_presentation_claims",
            [column],
        )

    op.create_table(
        "recommendation_finding_presentations",
        sa.Column("finding_presentation_id", sa.String(length=128), nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("source_finding_packet_id", sa.String(length=128), nullable=False),
        sa.Column("source_lease_id", sa.String(length=128), nullable=False),
        sa.Column("source_presentation_id", sa.String(length=128), nullable=False),
        sa.Column("source_assignment_set_id", sa.String(length=128), nullable=False),
        sa.Column("recommendation_id", sa.String(length=128), nullable=False),
        sa.Column("track_code", sa.String(length=128), nullable=False),
        sa.Column("lease_holder_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("finding_content_digest", sa.String(length=64), nullable=False),
        sa.Column("finding_count", sa.Integer(), nullable=False),
        sa.Column("finding_bytes", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("finding_presentation_id"),
        sa.UniqueConstraint(
            "source_finding_packet_id", name="uq_recommendation_finding_present_source"
        ),
        sa.UniqueConstraint("claim_id", name="uq_recommendation_finding_present_claim"),
    )
    for column in (
        "claim_id",
        "source_finding_packet_id",
        "source_lease_id",
        "source_presentation_id",
        "source_assignment_set_id",
        "recommendation_id",
        "track_code",
        "lease_holder_subject_digest",
        "organization_id",
        "environment_id",
    ):
        op.create_index(
            f"ix_rec_finding_present_{column}",
            "recommendation_finding_presentations",
            [column],
        )


def downgrade() -> None:
    op.drop_table("recommendation_finding_presentations")
    op.drop_table("recommendation_finding_presentation_claims")
