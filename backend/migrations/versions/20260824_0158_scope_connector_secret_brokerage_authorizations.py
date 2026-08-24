"""Scope connector secret brokerage authorization uniqueness.

Revision ID: 20260824_0158
Revises: 20260824_0157
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260824_0158"
down_revision: str | None = "20260824_0157"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "connector_secret_brokerage_authorizations"
    op.drop_constraint(
        "uq_connector_secret_brokerage_authorizations_runtime_trust",
        table,
        type_="unique",
    )
    op.drop_constraint(
        "uq_connector_secret_brokerage_authorizations_actor_idempotency",
        table,
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_connector_secret_brokerage_authorizations_runtime_trust",
        table,
        ["organization_id", "environment_id", "source_runtime_trust_grant_id"],
    )
    op.create_unique_constraint(
        "uq_connector_secret_brokerage_authorizations_actor_idempotency",
        table,
        ["organization_id", "environment_id", "authorized_by", "idempotency_key"],
    )


def downgrade() -> None:
    table = "connector_secret_brokerage_authorizations"
    connection = op.get_bind()
    duplicate_runtime_trust = connection.execute(
        sa.text(
            "SELECT source_runtime_trust_grant_id "
            "FROM connector_secret_brokerage_authorizations "
            "GROUP BY source_runtime_trust_grant_id HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    duplicate_create_key = connection.execute(
        sa.text(
            "SELECT authorized_by, idempotency_key "
            "FROM connector_secret_brokerage_authorizations "
            "GROUP BY authorized_by, idempotency_key HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate_runtime_trust is not None or duplicate_create_key is not None:
        raise RuntimeError(
            "Cannot downgrade connector secret brokerage authorizations: tenant-scoped records "
            "would violate the legacy global uniqueness constraints."
        )
    op.drop_constraint(
        "uq_connector_secret_brokerage_authorizations_actor_idempotency",
        table,
        type_="unique",
    )
    op.drop_constraint(
        "uq_connector_secret_brokerage_authorizations_runtime_trust",
        table,
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_connector_secret_brokerage_authorizations_actor_idempotency",
        table,
        ["authorized_by", "idempotency_key"],
    )
    op.create_unique_constraint(
        "uq_connector_secret_brokerage_authorizations_runtime_trust",
        table,
        ["source_runtime_trust_grant_id"],
    )
