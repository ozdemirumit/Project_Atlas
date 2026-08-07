"""Add operational knowledge correction and resubmission records.

Revision ID: 20260807_0066
Revises: 20260807_0065
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260807_0066"
down_revision: str | None = "20260807_0065"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_knowledge_correction_claims",
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("source_review_request_id", sa.String(length=128), nullable=False),
        sa.Column("correction_id", sa.String(length=128), nullable=False),
        sa.Column("claimed_by_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("idempotency_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "source_review_request_id", name="uq_ok_correction_claim_source_request"
        ),
        sa.UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_ok_correction_claim_actor_idem",
        ),
    )
    for name, column in {
        "ix_ok_correction_claim_source": "source_review_request_id",
        "ix_ok_correction_claim_record": "correction_id",
        "ix_ok_correction_claim_subject": "claimed_by_subject_digest",
        "ix_ok_correction_claim_org": "organization_id",
        "ix_ok_correction_claim_env": "environment_id",
    }.items():
        op.create_index(name, "operational_knowledge_correction_claims", [column])

    op.create_table(
        "operational_knowledge_corrections",
        sa.Column("correction_id", sa.String(length=128), nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("source_review_request_id", sa.String(length=128), nullable=False),
        sa.Column("source_draft_id", sa.String(length=128), nullable=False),
        sa.Column("knowledge_item_id", sa.String(length=128), nullable=False),
        sa.Column("new_draft_id", sa.String(length=128), nullable=False),
        sa.Column("new_review_request_id", sa.String(length=128), nullable=False),
        sa.Column("corrected_by_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("correction_id"),
        sa.UniqueConstraint("claim_id", name="uq_ok_correction_claim"),
        sa.UniqueConstraint("source_review_request_id", name="uq_ok_correction_source_request"),
        sa.UniqueConstraint("new_draft_id", name="uq_ok_correction_new_draft"),
        sa.UniqueConstraint("new_review_request_id", name="uq_ok_correction_new_request"),
    )
    for name, column in {
        "ix_ok_correction_record_claim": "claim_id",
        "ix_ok_correction_record_source": "source_review_request_id",
        "ix_ok_correction_record_source_draft": "source_draft_id",
        "ix_ok_correction_record_item": "knowledge_item_id",
        "ix_ok_correction_record_new_draft": "new_draft_id",
        "ix_ok_correction_record_new_request": "new_review_request_id",
        "ix_ok_correction_record_subject": "corrected_by_subject_digest",
        "ix_ok_correction_record_org": "organization_id",
        "ix_ok_correction_record_env": "environment_id",
    }.items():
        op.create_index(name, "operational_knowledge_corrections", [column])


def downgrade() -> None:
    op.drop_table("operational_knowledge_corrections")
    op.drop_table("operational_knowledge_correction_claims")
