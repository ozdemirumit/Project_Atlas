"""Add operational knowledge source materialization records.

Revision ID: 20260807_0069
Revises: 20260807_0068
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260807_0069"
down_revision: str | None = "20260807_0068"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_knowledge_source_materialization_claims",
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("preparation_id", sa.String(length=128), nullable=False),
        sa.Column("materialization_id", sa.String(length=128), nullable=False),
        sa.Column("claimed_by_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("idempotency_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint("preparation_id", name="uq_ok_source_mat_claim_preparation"),
        sa.UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_ok_source_mat_claim_actor_idem",
        ),
    )
    for name, column in {
        "ix_ok_source_mat_claim_preparation": "preparation_id",
        "ix_ok_source_mat_claim_materialization": "materialization_id",
        "ix_ok_source_mat_claim_subject": "claimed_by_subject_digest",
        "ix_ok_source_mat_claim_org": "organization_id",
        "ix_ok_source_mat_claim_env": "environment_id",
    }.items():
        op.create_index(name, "operational_knowledge_source_materialization_claims", [column])

    op.create_table(
        "operational_knowledge_source_materializations",
        sa.Column("materialization_id", sa.String(length=128), nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("preparation_id", sa.String(length=128), nullable=False),
        sa.Column("resolution_id", sa.String(length=128), nullable=False),
        sa.Column("source_draft_id", sa.String(length=128), nullable=False),
        sa.Column("knowledge_item_id", sa.String(length=128), nullable=False),
        sa.Column("materialized_by_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("materialization_id"),
        sa.UniqueConstraint("claim_id", name="uq_ok_source_mat_claim"),
        sa.UniqueConstraint("preparation_id", name="uq_ok_source_mat_preparation"),
    )
    for name, column in {
        "ix_ok_source_mat_record_claim": "claim_id",
        "ix_ok_source_mat_record_preparation": "preparation_id",
        "ix_ok_source_mat_record_resolution": "resolution_id",
        "ix_ok_source_mat_record_draft": "source_draft_id",
        "ix_ok_source_mat_record_item": "knowledge_item_id",
        "ix_ok_source_mat_record_subject": "materialized_by_subject_digest",
        "ix_ok_source_mat_record_org": "organization_id",
        "ix_ok_source_mat_record_env": "environment_id",
    }.items():
        op.create_index(name, "operational_knowledge_source_materializations", [column])


def downgrade() -> None:
    op.drop_table("operational_knowledge_source_materializations")
    op.drop_table("operational_knowledge_source_materialization_claims")
