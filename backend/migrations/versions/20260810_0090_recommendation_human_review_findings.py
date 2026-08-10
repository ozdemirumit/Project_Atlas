"""Add governed recommendation human review findings.

Revision ID: 20260810_0090
Revises: 20260810_0089
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260810_0090"
down_revision: str | None = "20260810_0089"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recommendation_human_review_finding_claims",
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("source_presentation_id", sa.String(length=128), nullable=False),
        sa.Column("finding_packet_id", sa.String(length=128), nullable=False),
        sa.Column("track_code", sa.String(length=128), nullable=False),
        sa.Column("claimed_by_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("idempotency_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "source_presentation_id", name="uq_recommendation_finding_claim_source_present"
        ),
        sa.UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_recommendation_finding_claim_actor_idem",
        ),
    )
    for column in (
        "source_presentation_id",
        "finding_packet_id",
        "track_code",
        "claimed_by_subject_digest",
        "organization_id",
        "environment_id",
    ):
        op.create_index(
            f"ix_recommendation_finding_claim_{column}",
            "recommendation_human_review_finding_claims",
            [column],
        )

    op.create_table(
        "recommendation_human_review_findings",
        sa.Column("finding_packet_id", sa.String(length=128), nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
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
        sa.PrimaryKeyConstraint("finding_packet_id"),
        sa.UniqueConstraint("claim_id", name="uq_recommendation_findings_claim"),
        sa.UniqueConstraint(
            "source_presentation_id", name="uq_recommendation_findings_source_presentation"
        ),
    )
    for column in (
        "claim_id",
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
            f"ix_recommendation_findings_{column}",
            "recommendation_human_review_findings",
            [column],
        )


def downgrade() -> None:
    op.drop_table("recommendation_human_review_findings")
    op.drop_table("recommendation_human_review_finding_claims")
