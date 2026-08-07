"""Add operational knowledge index staging.

Revision ID: 20260807_0072
Revises: 20260807_0071
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260807_0072"
down_revision: str | None = "20260807_0071"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_knowledge_index_claims",
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("embedding_set_id", sa.String(length=128), nullable=False),
        sa.Column("index_staging_id", sa.String(length=128), nullable=False),
        sa.Column("claimed_by_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("idempotency_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint("embedding_set_id", name="uq_ok_index_claim_embedding"),
        sa.UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_ok_index_claim_actor_idem",
        ),
    )
    for name, column in {
        "ix_ok_index_claim_embedding": "embedding_set_id",
        "ix_ok_index_claim_staging": "index_staging_id",
        "ix_ok_index_claim_subject": "claimed_by_subject_digest",
        "ix_ok_index_claim_org": "organization_id",
        "ix_ok_index_claim_env": "environment_id",
    }.items():
        op.create_index(name, "operational_knowledge_index_claims", [column])

    op.create_table(
        "operational_knowledge_index_stagings",
        sa.Column("index_staging_id", sa.String(length=128), nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("embedding_set_id", sa.String(length=128), nullable=False),
        sa.Column("chunk_set_id", sa.String(length=128), nullable=False),
        sa.Column("knowledge_item_id", sa.String(length=128), nullable=False),
        sa.Column("index_steward_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("index_staging_id"),
        sa.UniqueConstraint("embedding_set_id", name="uq_ok_index_staging_embedding"),
        sa.UniqueConstraint("claim_id", name="uq_ok_index_staging_claim"),
    )
    for name, column in {
        "ix_ok_index_staging_claim": "claim_id",
        "ix_ok_index_staging_embedding": "embedding_set_id",
        "ix_ok_index_staging_chunk": "chunk_set_id",
        "ix_ok_index_staging_item": "knowledge_item_id",
        "ix_ok_index_staging_subject": "index_steward_subject_digest",
        "ix_ok_index_staging_org": "organization_id",
        "ix_ok_index_staging_env": "environment_id",
    }.items():
        op.create_index(name, "operational_knowledge_index_stagings", [column])


def downgrade() -> None:
    op.drop_table("operational_knowledge_index_stagings")
    op.drop_table("operational_knowledge_index_claims")
