"""Add operational knowledge publication preparation records.

Revision ID: 20260807_0068
Revises: 20260807_0067
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260807_0068"
down_revision: str | None = "20260807_0067"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_knowledge_publication_preparation_claims",
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("resolution_id", sa.String(length=128), nullable=False),
        sa.Column("preparation_id", sa.String(length=128), nullable=False),
        sa.Column("claimed_by_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("idempotency_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint("resolution_id", name="uq_ok_pub_prep_claim_resolution"),
        sa.UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_ok_pub_prep_claim_actor_idem",
        ),
    )
    for name, column in {
        "ix_ok_pub_prep_claim_resolution": "resolution_id",
        "ix_ok_pub_prep_claim_preparation": "preparation_id",
        "ix_ok_pub_prep_claim_subject": "claimed_by_subject_digest",
        "ix_ok_pub_prep_claim_org": "organization_id",
        "ix_ok_pub_prep_claim_env": "environment_id",
    }.items():
        op.create_index(name, "operational_knowledge_publication_preparation_claims", [column])

    op.create_table(
        "operational_knowledge_publication_preparations",
        sa.Column("preparation_id", sa.String(length=128), nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("resolution_id", sa.String(length=128), nullable=False),
        sa.Column("review_request_id", sa.String(length=128), nullable=False),
        sa.Column("source_draft_id", sa.String(length=128), nullable=False),
        sa.Column("knowledge_item_id", sa.String(length=128), nullable=False),
        sa.Column("prepared_by_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("preparation_id"),
        sa.UniqueConstraint("claim_id", name="uq_ok_pub_prep_claim"),
        sa.UniqueConstraint("resolution_id", name="uq_ok_pub_prep_resolution"),
    )
    for name, column in {
        "ix_ok_pub_prep_record_claim": "claim_id",
        "ix_ok_pub_prep_record_resolution": "resolution_id",
        "ix_ok_pub_prep_record_request": "review_request_id",
        "ix_ok_pub_prep_record_draft": "source_draft_id",
        "ix_ok_pub_prep_record_item": "knowledge_item_id",
        "ix_ok_pub_prep_record_subject": "prepared_by_subject_digest",
        "ix_ok_pub_prep_record_org": "organization_id",
        "ix_ok_pub_prep_record_env": "environment_id",
    }.items():
        op.create_index(name, "operational_knowledge_publication_preparations", [column])


def downgrade() -> None:
    op.drop_table("operational_knowledge_publication_preparations")
    op.drop_table("operational_knowledge_publication_preparation_claims")
