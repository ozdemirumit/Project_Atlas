"""Add operational knowledge deterministic chunk sets.

Revision ID: 20260807_0070
Revises: 20260807_0069
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260807_0070"
down_revision: str | None = "20260807_0069"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_knowledge_chunking_claims",
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("materialization_id", sa.String(length=128), nullable=False),
        sa.Column("chunk_set_id", sa.String(length=128), nullable=False),
        sa.Column("claimed_by_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("idempotency_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint("materialization_id", name="uq_ok_chunk_claim_materialization"),
        sa.UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_ok_chunk_claim_actor_idem",
        ),
    )
    for name, column in {
        "ix_ok_chunk_claim_materialization": "materialization_id",
        "ix_ok_chunk_claim_set": "chunk_set_id",
        "ix_ok_chunk_claim_subject": "claimed_by_subject_digest",
        "ix_ok_chunk_claim_org": "organization_id",
        "ix_ok_chunk_claim_env": "environment_id",
    }.items():
        op.create_index(name, "operational_knowledge_chunking_claims", [column])

    op.create_table(
        "operational_knowledge_chunk_sets",
        sa.Column("chunk_set_id", sa.String(length=128), nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("materialization_id", sa.String(length=128), nullable=False),
        sa.Column("preparation_id", sa.String(length=128), nullable=False),
        sa.Column("resolution_id", sa.String(length=128), nullable=False),
        sa.Column("source_draft_id", sa.String(length=128), nullable=False),
        sa.Column("knowledge_item_id", sa.String(length=128), nullable=False),
        sa.Column("chunked_by_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("chunk_set_id"),
        sa.UniqueConstraint("claim_id", name="uq_ok_chunk_set_claim"),
        sa.UniqueConstraint("materialization_id", name="uq_ok_chunk_set_materialization"),
    )
    for name, column in {
        "ix_ok_chunk_set_claim": "claim_id",
        "ix_ok_chunk_set_materialization": "materialization_id",
        "ix_ok_chunk_set_preparation": "preparation_id",
        "ix_ok_chunk_set_resolution": "resolution_id",
        "ix_ok_chunk_set_draft": "source_draft_id",
        "ix_ok_chunk_set_item": "knowledge_item_id",
        "ix_ok_chunk_set_subject": "chunked_by_subject_digest",
        "ix_ok_chunk_set_org": "organization_id",
        "ix_ok_chunk_set_env": "environment_id",
    }.items():
        op.create_index(name, "operational_knowledge_chunk_sets", [column])


def downgrade() -> None:
    op.drop_table("operational_knowledge_chunk_sets")
    op.drop_table("operational_knowledge_chunking_claims")
