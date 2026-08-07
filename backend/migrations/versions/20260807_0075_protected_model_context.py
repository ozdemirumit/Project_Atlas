"""Add protected model-context assembly metadata.

Revision ID: 20260807_0075
Revises: 20260807_0074
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260807_0075"
down_revision: str | None = "20260807_0074"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "protected_model_context_claims",
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("context_id", sa.String(length=128), nullable=False),
        sa.Column("retrieval_id", sa.String(length=128), nullable=False),
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
            name="uq_protected_model_context_claim_actor_idem",
        ),
    )
    for name, column in {
        "ix_protected_model_context_claim_context": "context_id",
        "ix_protected_model_context_claim_retrieval": "retrieval_id",
        "ix_protected_model_context_claim_subject": "claimed_by_subject_digest",
        "ix_protected_model_context_claim_org": "organization_id",
        "ix_protected_model_context_claim_env": "environment_id",
    }.items():
        op.create_index(name, "protected_model_context_claims", [column])

    op.create_table(
        "protected_model_contexts",
        sa.Column("context_id", sa.String(length=128), nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("retrieval_id", sa.String(length=128), nullable=False),
        sa.Column("publication_id", sa.String(length=128), nullable=False),
        sa.Column("consumer_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("protected_artifact_reference", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("context_id"),
        sa.UniqueConstraint("claim_id", name="uq_protected_model_context_claim"),
        sa.UniqueConstraint(
            "protected_artifact_reference", name="uq_protected_model_context_artifact"
        ),
    )
    for name, column in {
        "ix_protected_model_context_claim": "claim_id",
        "ix_protected_model_context_retrieval": "retrieval_id",
        "ix_protected_model_context_publication": "publication_id",
        "ix_protected_model_context_subject": "consumer_subject_digest",
        "ix_protected_model_context_artifact": "protected_artifact_reference",
        "ix_protected_model_context_org": "organization_id",
        "ix_protected_model_context_env": "environment_id",
        "ix_protected_model_context_expires": "expires_at",
    }.items():
        op.create_index(name, "protected_model_contexts", [column])


def downgrade() -> None:
    op.drop_table("protected_model_contexts")
    op.drop_table("protected_model_context_claims")
