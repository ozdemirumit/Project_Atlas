"""add connector invocation evidence claims and ingestions

Revision ID: 20260806_0057
Revises: 20260806_0056
Create Date: 2026-08-06
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260806_0057"
down_revision: str | None = "20260806_0056"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connector_invocation_evidence_claims",
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("source_invocation_id", sa.String(length=128), nullable=False),
        sa.Column("ingestion_id", sa.String(length=128), nullable=False),
        sa.Column("claimed_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "source_invocation_id",
            name="uq_connector_invocation_evidence_claims_source",
        ),
        sa.UniqueConstraint(
            "claimed_by",
            "idempotency_digest",
            name="uq_connector_invocation_evidence_claims_actor_idempotency",
        ),
    )
    for column in (
        "source_invocation_id",
        "ingestion_id",
        "claimed_by",
        "organization_id",
        "environment_id",
    ):
        op.create_index(
            op.f(f"ix_connector_invocation_evidence_claims_{column}"),
            "connector_invocation_evidence_claims",
            [column],
            unique=False,
        )

    op.create_table(
        "connector_invocation_evidence_ingestions",
        sa.Column("ingestion_id", sa.String(length=128), nullable=False),
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("source_invocation_id", sa.String(length=128), nullable=False),
        sa.Column("instance_id", sa.String(length=128), nullable=False),
        sa.Column("capability_id", sa.String(length=128), nullable=False),
        sa.Column("evidence_package_id", sa.String(length=128), nullable=False),
        sa.Column("ingested_by", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("ingestion_id"),
        sa.UniqueConstraint(
            "source_invocation_id",
            name="uq_connector_invocation_evidence_source",
        ),
        sa.UniqueConstraint("claim_id", name="uq_connector_invocation_evidence_claim"),
    )
    for column in (
        "claim_id",
        "source_invocation_id",
        "instance_id",
        "capability_id",
        "evidence_package_id",
        "ingested_by",
        "organization_id",
        "environment_id",
    ):
        op.create_index(
            op.f(f"ix_connector_invocation_evidence_ingestions_{column}"),
            "connector_invocation_evidence_ingestions",
            [column],
            unique=False,
        )


def downgrade() -> None:
    op.drop_table("connector_invocation_evidence_ingestions")
    op.drop_table("connector_invocation_evidence_claims")
