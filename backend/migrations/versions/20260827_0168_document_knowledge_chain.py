"""Add the compact document-sourced knowledge governance chain (ADR-184).

Revision ID: 20260827_0168
Revises: 20260827_0167
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260827_0168"
down_revision: str | None = "20260827_0167"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_knowledge_drafts",
        sa.Column("draft_id", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("protected_material_digest", sa.String(length=64), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("draft_id"),
    )
    op.create_index(
        "ix_document_knowledge_drafts_organization_id",
        "document_knowledge_drafts",
        ["organization_id"],
    )
    op.create_index(
        "ix_document_knowledge_drafts_environment_id",
        "document_knowledge_drafts",
        ["environment_id"],
    )

    op.create_table(
        "document_knowledge_reviews",
        sa.Column("review_id", sa.String(length=128), nullable=False),
        sa.Column("draft_id", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("review_id"),
        sa.UniqueConstraint("draft_id", name="uq_document_knowledge_review_draft"),
    )
    op.create_index(
        "ix_document_knowledge_reviews_draft_id", "document_knowledge_reviews", ["draft_id"]
    )
    op.create_index(
        "ix_document_knowledge_reviews_organization_id",
        "document_knowledge_reviews",
        ["organization_id"],
    )
    op.create_index(
        "ix_document_knowledge_reviews_environment_id",
        "document_knowledge_reviews",
        ["environment_id"],
    )

    op.create_table(
        "document_knowledge_approvals",
        sa.Column("approval_id", sa.String(length=128), nullable=False),
        sa.Column("review_id", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("approval_id"),
        sa.UniqueConstraint("review_id", name="uq_document_knowledge_approval_review"),
    )
    op.create_index(
        "ix_document_knowledge_approvals_review_id",
        "document_knowledge_approvals",
        ["review_id"],
    )
    op.create_index(
        "ix_document_knowledge_approvals_organization_id",
        "document_knowledge_approvals",
        ["organization_id"],
    )
    op.create_index(
        "ix_document_knowledge_approvals_environment_id",
        "document_knowledge_approvals",
        ["environment_id"],
    )

    op.create_table(
        "document_knowledge_preparations",
        sa.Column("preparation_id", sa.String(length=128), nullable=False),
        sa.Column("approval_id", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("preparation_id"),
        sa.UniqueConstraint("approval_id", name="uq_document_knowledge_preparation_approval"),
    )
    op.create_index(
        "ix_document_knowledge_preparations_approval_id",
        "document_knowledge_preparations",
        ["approval_id"],
    )
    op.create_index(
        "ix_document_knowledge_preparations_organization_id",
        "document_knowledge_preparations",
        ["organization_id"],
    )
    op.create_index(
        "ix_document_knowledge_preparations_environment_id",
        "document_knowledge_preparations",
        ["environment_id"],
    )


def downgrade() -> None:
    for table in (
        "document_knowledge_preparations",
        "document_knowledge_approvals",
        "document_knowledge_reviews",
        "document_knowledge_drafts",
    ):
        for column in ("organization_id", "environment_id"):
            op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
    op.drop_index("ix_document_knowledge_reviews_draft_id", table_name="document_knowledge_reviews")
    op.drop_index(
        "ix_document_knowledge_approvals_review_id", table_name="document_knowledge_approvals"
    )
    op.drop_index(
        "ix_document_knowledge_preparations_approval_id",
        table_name="document_knowledge_preparations",
    )
    op.drop_table("document_knowledge_preparations")
    op.drop_table("document_knowledge_approvals")
    op.drop_table("document_knowledge_reviews")
    op.drop_table("document_knowledge_drafts")
