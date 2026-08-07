"""Add protected draft-adjudication metadata.

Revision ID: 20260807_0077
Revises: 20260807_0076
Create Date: 2026-08-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260807_0077"
down_revision: str | None = "20260807_0076"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "protected_draft_adjudication_claims",
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("adjudication_id", sa.String(128), nullable=False),
        sa.Column("invocation_id", sa.String(128), nullable=False),
        sa.Column("claimed_by_subject_digest", sa.String(64), nullable=False),
        sa.Column("idempotency_digest", sa.String(64), nullable=False),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("environment_id", sa.String(128), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_protected_draft_adjudication_claim_actor_idem",
        ),
    )
    for name, column in {
        "ix_protected_draft_adj_claim_adjudication": "adjudication_id",
        "ix_protected_draft_adj_claim_invocation": "invocation_id",
        "ix_protected_draft_adj_claim_subject": "claimed_by_subject_digest",
        "ix_protected_draft_adj_claim_org": "organization_id",
        "ix_protected_draft_adj_claim_env": "environment_id",
    }.items():
        op.create_index(name, "protected_draft_adjudication_claims", [column])
    op.create_table(
        "protected_draft_adjudications",
        sa.Column("adjudication_id", sa.String(128), nullable=False),
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("invocation_id", sa.String(128), nullable=False),
        sa.Column("consumer_subject_digest", sa.String(64), nullable=False),
        sa.Column("protected_report_reference", sa.String(128), nullable=False),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("environment_id", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("adjudication_id"),
        sa.UniqueConstraint("claim_id", name="uq_protected_draft_adjudication_claim"),
        sa.UniqueConstraint(
            "protected_report_reference", name="uq_protected_draft_adjudication_report"
        ),
    )
    for name, column in {
        "ix_protected_draft_adj_claim": "claim_id",
        "ix_protected_draft_adj_invocation": "invocation_id",
        "ix_protected_draft_adj_subject": "consumer_subject_digest",
        "ix_protected_draft_adj_report": "protected_report_reference",
        "ix_protected_draft_adj_org": "organization_id",
        "ix_protected_draft_adj_env": "environment_id",
        "ix_protected_draft_adj_expires": "expires_at",
    }.items():
        op.create_index(name, "protected_draft_adjudications", [column])


def downgrade() -> None:
    op.drop_table("protected_draft_adjudications")
    op.drop_table("protected_draft_adjudication_claims")
