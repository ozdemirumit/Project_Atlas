"""Add operational knowledge final resolution records.

Revision ID: 20260807_0067
Revises: 20260807_0066
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260807_0067"
down_revision: str | None = "20260807_0066"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_knowledge_final_resolution_claims",
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("review_request_id", sa.String(length=128), nullable=False),
        sa.Column("resolution_id", sa.String(length=128), nullable=False),
        sa.Column("claimed_by_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("idempotency_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint("review_request_id", name="uq_ok_final_claim_request"),
        sa.UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_ok_final_claim_actor_idem",
        ),
    )
    for name, column in {
        "ix_ok_final_claim_request": "review_request_id",
        "ix_ok_final_claim_resolution": "resolution_id",
        "ix_ok_final_claim_subject": "claimed_by_subject_digest",
        "ix_ok_final_claim_org": "organization_id",
        "ix_ok_final_claim_env": "environment_id",
    }.items():
        op.create_index(name, "operational_knowledge_final_resolution_claims", [column])

    op.create_table(
        "operational_knowledge_final_resolutions",
        sa.Column("resolution_id", sa.String(length=128), nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("review_request_id", sa.String(length=128), nullable=False),
        sa.Column("source_draft_id", sa.String(length=128), nullable=False),
        sa.Column("knowledge_item_id", sa.String(length=128), nullable=False),
        sa.Column("disposition_code", sa.String(length=128), nullable=False),
        sa.Column("approved_by_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("resolution_id"),
        sa.UniqueConstraint("claim_id", name="uq_ok_final_claim"),
        sa.UniqueConstraint("review_request_id", name="uq_ok_final_request"),
    )
    for name, column in {
        "ix_ok_final_record_claim": "claim_id",
        "ix_ok_final_record_request": "review_request_id",
        "ix_ok_final_record_draft": "source_draft_id",
        "ix_ok_final_record_item": "knowledge_item_id",
        "ix_ok_final_record_disposition": "disposition_code",
        "ix_ok_final_record_subject": "approved_by_subject_digest",
        "ix_ok_final_record_org": "organization_id",
        "ix_ok_final_record_env": "environment_id",
    }.items():
        op.create_index(name, "operational_knowledge_final_resolutions", [column])


def downgrade() -> None:
    op.drop_table("operational_knowledge_final_resolutions")
    op.drop_table("operational_knowledge_final_resolution_claims")
