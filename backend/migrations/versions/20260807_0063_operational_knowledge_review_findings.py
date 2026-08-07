"""add operational knowledge review finding metadata

Revision ID: 20260807_0063
Revises: 20260806_0062
Create Date: 2026-08-07 05:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260807_0063"
down_revision: str | None = "20260806_0062"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_knowledge_review_finding_claims",
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
            "source_presentation_id",
            name="uq_ok_finding_claim_source_present",
        ),
        sa.UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_ok_finding_claim_actor_idem",
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
            op.f(f"ix_operational_knowledge_review_finding_claims_{column}"),
            "operational_knowledge_review_finding_claims",
            [column],
        )
    op.create_table(
        "operational_knowledge_review_findings",
        sa.Column("finding_packet_id", sa.String(length=128), nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("source_lease_id", sa.String(length=128), nullable=False),
        sa.Column("source_presentation_id", sa.String(length=128), nullable=False),
        sa.Column("source_assignment_set_id", sa.String(length=128), nullable=False),
        sa.Column("track_code", sa.String(length=128), nullable=False),
        sa.Column("knowledge_item_id", sa.String(length=128), nullable=False),
        sa.Column("lease_holder_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("finding_content_digest", sa.String(length=64), nullable=False),
        sa.Column("finding_count", sa.Integer(), nullable=False),
        sa.Column("finding_bytes", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("finding_packet_id"),
        sa.UniqueConstraint(
            "source_presentation_id",
            name="uq_operational_knowledge_review_findings_source_presentation",
        ),
        sa.UniqueConstraint(
            "claim_id",
            name="uq_operational_knowledge_review_findings_claim",
        ),
    )
    for column in (
        "claim_id",
        "source_lease_id",
        "source_presentation_id",
        "source_assignment_set_id",
        "track_code",
        "knowledge_item_id",
        "lease_holder_subject_digest",
        "organization_id",
        "environment_id",
    ):
        op.create_index(
            op.f(f"ix_operational_knowledge_review_findings_{column}"),
            "operational_knowledge_review_findings",
            [column],
        )


def downgrade() -> None:
    op.drop_table("operational_knowledge_review_findings")
    op.drop_table("operational_knowledge_review_finding_claims")
