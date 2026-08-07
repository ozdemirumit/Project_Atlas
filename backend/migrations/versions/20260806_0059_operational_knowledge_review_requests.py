"""add operational knowledge review request claims and records

Revision ID: 20260806_0059
Revises: 20260806_0058
Create Date: 2026-08-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260806_0059"
down_revision: str | None = "20260806_0058"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_knowledge_review_request_claims",
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("source_draft_id", sa.String(length=128), nullable=False),
        sa.Column("review_request_id", sa.String(length=128), nullable=False),
        sa.Column("claimed_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "source_draft_id",
            name="uq_operational_knowledge_review_request_claims_source",
        ),
        sa.UniqueConstraint(
            "claimed_by",
            "idempotency_digest",
            name="uq_ok_review_req_claim_actor_idem",
        ),
    )
    for column in (
        "source_draft_id",
        "review_request_id",
        "claimed_by",
        "organization_id",
        "environment_id",
    ):
        op.create_index(
            op.f(f"ix_operational_knowledge_review_request_claims_{column}"),
            "operational_knowledge_review_request_claims",
            [column],
            unique=False,
        )

    op.create_table(
        "operational_knowledge_review_requests",
        sa.Column("review_request_id", sa.String(length=128), nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("source_draft_id", sa.String(length=128), nullable=False),
        sa.Column("knowledge_item_id", sa.String(length=128), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("review_request_id"),
        sa.UniqueConstraint(
            "source_draft_id",
            name="uq_operational_knowledge_review_requests_source",
        ),
        sa.UniqueConstraint(
            "claim_id",
            name="uq_operational_knowledge_review_requests_claim",
        ),
    )
    for column in (
        "claim_id",
        "source_draft_id",
        "knowledge_item_id",
        "requested_by",
        "organization_id",
        "environment_id",
    ):
        op.create_index(
            op.f(f"ix_operational_knowledge_review_requests_{column}"),
            "operational_knowledge_review_requests",
            [column],
            unique=False,
        )


def downgrade() -> None:
    op.drop_table("operational_knowledge_review_requests")
    op.drop_table("operational_knowledge_review_request_claims")
