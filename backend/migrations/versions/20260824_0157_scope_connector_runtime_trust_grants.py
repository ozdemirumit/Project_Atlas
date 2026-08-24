"""Scope connector runtime trust grant uniqueness.

Revision ID: 20260824_0157
Revises: 20260824_0156
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260824_0157"
down_revision: str | None = "20260824_0156"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "connector_runtime_trust_grants"
    op.drop_constraint(
        "uq_connector_runtime_trust_grants_enablement",
        table,
        type_="unique",
    )
    op.drop_constraint(
        "uq_connector_runtime_trust_grants_actor_idempotency",
        table,
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_connector_runtime_trust_grants_enablement",
        table,
        ["organization_id", "environment_id", "source_enablement_id"],
    )
    op.create_unique_constraint(
        "uq_connector_runtime_trust_grants_actor_idempotency",
        table,
        ["organization_id", "environment_id", "granted_by", "idempotency_key"],
    )


def downgrade() -> None:
    table = "connector_runtime_trust_grants"
    connection = op.get_bind()
    duplicate_enablement = connection.execute(
        sa.text(
            "SELECT source_enablement_id FROM connector_runtime_trust_grants "
            "GROUP BY source_enablement_id HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    duplicate_create_key = connection.execute(
        sa.text(
            "SELECT granted_by, idempotency_key FROM connector_runtime_trust_grants "
            "GROUP BY granted_by, idempotency_key HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate_enablement is not None or duplicate_create_key is not None:
        raise RuntimeError(
            "Cannot downgrade connector runtime trust grants: tenant-scoped records "
            "would violate the legacy global uniqueness constraints."
        )
    op.drop_constraint(
        "uq_connector_runtime_trust_grants_actor_idempotency",
        table,
        type_="unique",
    )
    op.drop_constraint(
        "uq_connector_runtime_trust_grants_enablement",
        table,
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_connector_runtime_trust_grants_actor_idempotency",
        table,
        ["granted_by", "idempotency_key"],
    )
    op.create_unique_constraint(
        "uq_connector_runtime_trust_grants_enablement",
        table,
        ["source_enablement_id"],
    )
