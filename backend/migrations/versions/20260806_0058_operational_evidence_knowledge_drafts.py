"""add operational evidence knowledge draft claims and records

Revision ID: 20260806_0058
Revises: 20260806_0057
Create Date: 2026-08-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260806_0058"
down_revision: str | None = "20260806_0057"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_evidence_knowledge_draft_claims",
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("source_ingestion_id", sa.String(length=128), nullable=False),
        sa.Column("draft_id", sa.String(length=128), nullable=False),
        sa.Column("claimed_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "source_ingestion_id",
            name="uq_operational_evidence_knowledge_draft_claims_source",
        ),
        sa.UniqueConstraint(
            "claimed_by",
            "idempotency_digest",
            name="uq_operational_evidence_knowledge_draft_claims_actor_idempotency",
        ),
    )
    for column in (
        "source_ingestion_id",
        "draft_id",
        "claimed_by",
        "organization_id",
        "environment_id",
    ):
        op.create_index(
            f"ix_operational_evidence_knowledge_draft_claims_{column}",
            "operational_evidence_knowledge_draft_claims",
            [column],
            unique=False,
        )

    op.create_table(
        "operational_evidence_knowledge_drafts",
        sa.Column("draft_id", sa.String(length=128), nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("source_ingestion_id", sa.String(length=128), nullable=False),
        sa.Column("instance_id", sa.String(length=128), nullable=False),
        sa.Column("capability_id", sa.String(length=128), nullable=False),
        sa.Column("evidence_package_id", sa.String(length=128), nullable=False),
        sa.Column("curated_by", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("draft_id"),
        sa.UniqueConstraint(
            "source_ingestion_id",
            name="uq_operational_evidence_knowledge_drafts_source",
        ),
        sa.UniqueConstraint("claim_id", name="uq_operational_evidence_knowledge_drafts_claim"),
    )
    for column in (
        "claim_id",
        "source_ingestion_id",
        "instance_id",
        "capability_id",
        "evidence_package_id",
        "curated_by",
        "organization_id",
        "environment_id",
    ):
        op.create_index(
            f"ix_operational_evidence_knowledge_drafts_{column}",
            "operational_evidence_knowledge_drafts",
            [column],
            unique=False,
        )


def downgrade() -> None:
    op.drop_table("operational_evidence_knowledge_drafts")
    op.drop_table("operational_evidence_knowledge_draft_claims")
