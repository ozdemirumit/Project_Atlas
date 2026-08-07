"""Add operational knowledge retrieval metadata.

Revision ID: 20260807_0074
Revises: 20260807_0073
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260807_0074"
down_revision: str | None = "20260807_0073"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_knowledge_retrieval_claims",
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("retrieval_id", sa.String(length=128), nullable=False),
        sa.Column("publication_id", sa.String(length=128), nullable=False),
        sa.Column("claimed_by_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("idempotency_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_ok_retrieval_claim_actor_idem",
        ),
    )
    for name, column in {
        "ix_ok_retrieval_claim_retrieval": "retrieval_id",
        "ix_ok_retrieval_claim_publication": "publication_id",
        "ix_ok_retrieval_claim_subject": "claimed_by_subject_digest",
        "ix_ok_retrieval_claim_org": "organization_id",
        "ix_ok_retrieval_claim_env": "environment_id",
    }.items():
        op.create_index(name, "operational_knowledge_retrieval_claims", [column])

    op.create_table(
        "operational_knowledge_retrievals",
        sa.Column("retrieval_id", sa.String(length=128), nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("publication_id", sa.String(length=128), nullable=False),
        sa.Column("knowledge_item_id", sa.String(length=128), nullable=False),
        sa.Column("consumer_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("protected_artifact_reference", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("retrieval_id"),
        sa.UniqueConstraint("claim_id", name="uq_ok_retrieval_claim"),
        sa.UniqueConstraint("protected_artifact_reference", name="uq_ok_retrieval_artifact"),
    )
    for name, column in {
        "ix_ok_retrieval_claim": "claim_id",
        "ix_ok_retrieval_publication": "publication_id",
        "ix_ok_retrieval_item": "knowledge_item_id",
        "ix_ok_retrieval_subject": "consumer_subject_digest",
        "ix_ok_retrieval_artifact": "protected_artifact_reference",
        "ix_ok_retrieval_org": "organization_id",
        "ix_ok_retrieval_env": "environment_id",
        "ix_ok_retrieval_expires": "expires_at",
    }.items():
        op.create_index(name, "operational_knowledge_retrievals", [column])


def downgrade() -> None:
    op.drop_table("operational_knowledge_retrievals")
    op.drop_table("operational_knowledge_retrieval_claims")
