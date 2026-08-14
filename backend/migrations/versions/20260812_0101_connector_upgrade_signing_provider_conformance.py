"""Add connector upgrade signing-provider conformance assessments.

Revision ID: 20260812_0101
Revises: 20260812_0100
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260812_0101"
down_revision: str | None = "20260812_0100"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "connector_upgrade_signing_provider_conformance_assessments"
    op.create_table(
        table,
        sa.Column("assessment_id", sa.String(length=128), nullable=False),
        sa.Column("assessed_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("provider_class", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("assessment_id"),
        sa.UniqueConstraint(
            "assessed_by",
            "idempotency_key",
            name="uq_connector_upgrade_signing_conformance_actor_idem",
        ),
    )
    for column in (
        "assessed_by",
        "organization_id",
        "environment_id",
        "provider_class",
        "state",
        "observed_at",
        "valid_until",
    ):
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def downgrade() -> None:
    table = "connector_upgrade_signing_provider_conformance_assessments"
    for column in reversed(
        (
            "assessed_by",
            "organization_id",
            "environment_id",
            "provider_class",
            "state",
            "observed_at",
            "valid_until",
        )
    ):
        op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
    op.drop_table(table)
