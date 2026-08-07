"""add operational knowledge finding presentation metadata

Revision ID: 20260807_0064
Revises: 20260807_0063
Create Date: 2026-08-07 08:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260807_0064"
down_revision: str | None = "20260807_0063"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_knowledge_finding_presentation_claims",
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
            "source_finding_packet_id",
            name="uq_ok_finding_present_claim_source",
        ),
        sa.UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_ok_finding_present_claim_actor_idem",
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
            op.f(f"ix_operational_knowledge_finding_presentation_claims_{column}"),
            "operational_knowledge_finding_presentation_claims",
            [column],
        )
    op.create_table(
        "operational_knowledge_finding_presentations",
        sa.Column("finding_presentation_id", sa.String(length=128), nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("source_finding_packet_id", sa.String(length=128), nullable=False),
        sa.Column("source_lease_id", sa.String(length=128), nullable=False),
        sa.Column("source_content_presentation_id", sa.String(length=128), nullable=False),
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
        sa.PrimaryKeyConstraint("finding_presentation_id"),
        sa.UniqueConstraint(
            "source_finding_packet_id",
            name="uq_operational_knowledge_finding_presentations_source_finding",
        ),
        sa.UniqueConstraint(
            "claim_id",
            name="uq_operational_knowledge_finding_presentations_claim",
        ),
    )
    for column in (
        "claim_id",
        "source_finding_packet_id",
        "source_lease_id",
        "source_content_presentation_id",
        "source_assignment_set_id",
        "track_code",
        "knowledge_item_id",
        "lease_holder_subject_digest",
        "organization_id",
        "environment_id",
    ):
        op.create_index(
            op.f(f"ix_operational_knowledge_finding_presentations_{column}"),
            "operational_knowledge_finding_presentations",
            [column],
        )


def downgrade() -> None:
    op.drop_table("operational_knowledge_finding_presentations")
    op.drop_table("operational_knowledge_finding_presentation_claims")
