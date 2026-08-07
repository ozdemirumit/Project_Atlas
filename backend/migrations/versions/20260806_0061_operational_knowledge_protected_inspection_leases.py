"""add operational knowledge protected inspection lease claims and records

Revision ID: 20260806_0061
Revises: 20260806_0060
Create Date: 2026-08-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260806_0061"
down_revision: str | None = "20260806_0060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operational_knowledge_protected_inspection_claims",
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("source_assignment_set_id", sa.String(length=128), nullable=False),
        sa.Column("track_code", sa.String(length=128), nullable=False),
        sa.Column("lease_id", sa.String(length=128), nullable=False),
        sa.Column("claimed_by_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("idempotency_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "source_assignment_set_id",
            "track_code",
            name="uq_ok_inspect_claim_source_track",
        ),
        sa.UniqueConstraint(
            "claimed_by_subject_digest",
            "idempotency_digest",
            name="uq_ok_inspect_claim_actor_idem",
        ),
    )
    for column in (
        "source_assignment_set_id",
        "track_code",
        "lease_id",
        "claimed_by_subject_digest",
        "organization_id",
        "environment_id",
    ):
        op.create_index(
            op.f(f"ix_operational_knowledge_protected_inspection_claims_{column}"),
            "operational_knowledge_protected_inspection_claims",
            [column],
            unique=False,
        )

    op.create_table(
        "operational_knowledge_protected_inspection_leases",
        sa.Column("lease_id", sa.String(length=128), nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("source_assignment_set_id", sa.String(length=128), nullable=False),
        sa.Column("track_code", sa.String(length=128), nullable=False),
        sa.Column("knowledge_item_id", sa.String(length=128), nullable=False),
        sa.Column("lease_holder_subject_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("lease_id"),
        sa.UniqueConstraint(
            "source_assignment_set_id",
            "track_code",
            name="uq_ok_inspect_lease_source_track",
        ),
        sa.UniqueConstraint(
            "claim_id",
            name="uq_operational_knowledge_protected_inspection_leases_claim",
        ),
    )
    for column in (
        "claim_id",
        "source_assignment_set_id",
        "track_code",
        "knowledge_item_id",
        "lease_holder_subject_digest",
        "organization_id",
        "environment_id",
    ):
        op.create_index(
            op.f(f"ix_operational_knowledge_protected_inspection_leases_{column}"),
            "operational_knowledge_protected_inspection_leases",
            [column],
            unique=False,
        )


def downgrade() -> None:
    op.drop_table("operational_knowledge_protected_inspection_leases")
    op.drop_table("operational_knowledge_protected_inspection_claims")
