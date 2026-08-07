"""Add operational knowledge embedding sets.

Revision ID: 20260807_0071
Revises: 20260807_0070
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260807_0071"
down_revision: str | None = "20260807_0070"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_knowledge_embedding_claims",
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("chunk_set_id", sa.String(length=128), nullable=False),
        sa.Column("embedding_set_id", sa.String(length=128), nullable=False),
        sa.Column("claimed_by_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("idempotency_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint("chunk_set_id", name="uq_ok_embed_claim_chunk_set"),
        sa.UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_ok_embed_claim_actor_idem",
        ),
    )
    for name, column in {
        "ix_ok_embed_claim_chunk": "chunk_set_id",
        "ix_ok_embed_claim_set": "embedding_set_id",
        "ix_ok_embed_claim_subject": "claimed_by_subject_digest",
        "ix_ok_embed_claim_org": "organization_id",
        "ix_ok_embed_claim_env": "environment_id",
    }.items():
        op.create_index(name, "operational_knowledge_embedding_claims", [column])

    op.create_table(
        "operational_knowledge_embedding_sets",
        sa.Column("embedding_set_id", sa.String(length=128), nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("chunk_set_id", sa.String(length=128), nullable=False),
        sa.Column("materialization_id", sa.String(length=128), nullable=False),
        sa.Column("preparation_id", sa.String(length=128), nullable=False),
        sa.Column("knowledge_item_id", sa.String(length=128), nullable=False),
        sa.Column("embedded_by_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("embedding_set_id"),
        sa.UniqueConstraint("claim_id", name="uq_ok_embed_set_claim"),
        sa.UniqueConstraint("chunk_set_id", name="uq_ok_embed_set_chunk_set"),
    )
    for name, column in {
        "ix_ok_embed_set_claim": "claim_id",
        "ix_ok_embed_set_chunk": "chunk_set_id",
        "ix_ok_embed_set_materialization": "materialization_id",
        "ix_ok_embed_set_preparation": "preparation_id",
        "ix_ok_embed_set_item": "knowledge_item_id",
        "ix_ok_embed_set_subject": "embedded_by_subject_digest",
        "ix_ok_embed_set_org": "organization_id",
        "ix_ok_embed_set_env": "environment_id",
    }.items():
        op.create_index(name, "operational_knowledge_embedding_sets", [column])


def downgrade() -> None:
    op.drop_table("operational_knowledge_embedding_sets")
    op.drop_table("operational_knowledge_embedding_claims")
