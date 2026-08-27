"""Add real vector storage for document-sourced knowledge (ADR-183, ADR-184 amendment).

Revision ID: 20260827_0169
Revises: 20260827_0168
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "20260827_0169"
down_revision: str | None = "20260827_0168"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "document_knowledge_vectors",
        sa.Column("chunk_id", sa.String(length=128), nullable=False),
        sa.Column("knowledge_item_id", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("classification", sa.String(length=128), nullable=False),
        sa.Column("content_digest", sa.String(length=64), nullable=False),
        sa.Column("model_profile_id", sa.String(length=128), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("chunk_id"),
    )
    op.create_index(
        "ix_document_knowledge_vectors_knowledge_item_id",
        "document_knowledge_vectors",
        ["knowledge_item_id"],
    )
    op.create_index(
        "ix_document_knowledge_vectors_scope",
        "document_knowledge_vectors",
        ["organization_id", "environment_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_document_knowledge_vectors_scope", table_name="document_knowledge_vectors")
    op.drop_index(
        "ix_document_knowledge_vectors_knowledge_item_id",
        table_name="document_knowledge_vectors",
    )
    op.drop_table("document_knowledge_vectors")
    op.execute("DROP EXTENSION IF EXISTS vector")
