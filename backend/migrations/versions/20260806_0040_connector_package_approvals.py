"""Add immutable connector package approval requests and decisions.

Revision ID: 20260806_0040
Revises: 20260806_0039
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260806_0040"
down_revision: str | None = "20260806_0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    requests = "connector_package_approval_requests"
    op.create_table(
        requests,
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("source_final_validation_id", sa.String(length=128), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("request_id"),
        sa.UniqueConstraint(
            "source_final_validation_id",
            name="uq_connector_package_approval_requests_source",
        ),
        sa.UniqueConstraint(
            "requested_by",
            "idempotency_key",
            name="uq_connector_package_approval_requests_actor_idempotency",
        ),
    )
    for column in (
        "source_final_validation_id",
        "requested_by",
        "organization_id",
        "environment_id",
    ):
        op.create_index(op.f(f"ix_{requests}_{column}"), requests, [column], unique=False)

    decisions = "connector_package_approval_decisions"
    op.create_table(
        decisions,
        sa.Column("decision_id", sa.String(length=128), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=False),
        sa.Column("decided_by", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("decision_id"),
        sa.UniqueConstraint(
            "request_id",
            name="uq_connector_package_approval_decisions_request",
        ),
        sa.UniqueConstraint(
            "decided_by",
            "idempotency_key",
            name="uq_connector_package_approval_decisions_actor_idempotency",
        ),
    )
    for column in ("request_id", "decided_by", "organization_id", "environment_id"):
        op.create_index(op.f(f"ix_{decisions}_{column}"), decisions, [column], unique=False)


def downgrade() -> None:
    for table, columns in (
        (
            "connector_package_approval_decisions",
            ("request_id", "decided_by", "organization_id", "environment_id"),
        ),
        (
            "connector_package_approval_requests",
            (
                "source_final_validation_id",
                "requested_by",
                "organization_id",
                "environment_id",
            ),
        ),
    ):
        for column in reversed(columns):
            op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
        op.drop_table(table)
