"""Add operational knowledge track review decisions.

Revision ID: 20260807_0065
Revises: 20260807_0064
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260807_0065"
down_revision: str | None = "20260807_0064"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_knowledge_track_review_decision_claims",
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("source_finding_presentation_id", sa.String(length=128), nullable=False),
        sa.Column("decision_id", sa.String(length=128), nullable=False),
        sa.Column("track_code", sa.String(length=128), nullable=False),
        sa.Column("disposition_code", sa.String(length=128), nullable=False),
        sa.Column("claimed_by_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("idempotency_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "source_finding_presentation_id",
            name="uq_ok_trd_claim_source_present",
        ),
        sa.UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_ok_trd_claim_actor_idem",
        ),
    )
    claim_indexes = {
        "ix_ok_trd_claim_source": "source_finding_presentation_id",
        "ix_ok_trd_claim_decision": "decision_id",
        "ix_ok_trd_claim_track": "track_code",
        "ix_ok_trd_claim_disposition": "disposition_code",
        "ix_ok_trd_claim_subject": "claimed_by_subject_digest",
        "ix_ok_trd_claim_org": "organization_id",
        "ix_ok_trd_claim_env": "environment_id",
    }
    for name, column in claim_indexes.items():
        op.create_index(name, "operational_knowledge_track_review_decision_claims", [column])

    op.create_table(
        "operational_knowledge_track_review_decisions",
        sa.Column("decision_id", sa.String(length=128), nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("source_finding_presentation_id", sa.String(length=128), nullable=False),
        sa.Column("source_lease_id", sa.String(length=128), nullable=False),
        sa.Column("source_assignment_set_id", sa.String(length=128), nullable=False),
        sa.Column("review_request_id", sa.String(length=128), nullable=False),
        sa.Column("track_code", sa.String(length=128), nullable=False),
        sa.Column("disposition_code", sa.String(length=128), nullable=False),
        sa.Column("knowledge_item_id", sa.String(length=128), nullable=False),
        sa.Column("decided_by_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("decision_id"),
        sa.UniqueConstraint(
            "source_finding_presentation_id",
            name="uq_ok_trd_source_present",
        ),
        sa.UniqueConstraint(
            "claim_id",
            name="uq_ok_trd_claim",
        ),
    )
    decision_indexes = {
        "ix_ok_trd_record_claim": "claim_id",
        "ix_ok_trd_record_source": "source_finding_presentation_id",
        "ix_ok_trd_record_lease": "source_lease_id",
        "ix_ok_trd_record_assignment": "source_assignment_set_id",
        "ix_ok_trd_record_request": "review_request_id",
        "ix_ok_trd_record_track": "track_code",
        "ix_ok_trd_record_disposition": "disposition_code",
        "ix_ok_trd_record_item": "knowledge_item_id",
        "ix_ok_trd_record_subject": "decided_by_subject_digest",
        "ix_ok_trd_record_org": "organization_id",
        "ix_ok_trd_record_env": "environment_id",
    }
    for name, column in decision_indexes.items():
        op.create_index(name, "operational_knowledge_track_review_decisions", [column])


def downgrade() -> None:
    op.drop_table("operational_knowledge_track_review_decisions")
    op.drop_table("operational_knowledge_track_review_decision_claims")
