"""Scope connector capability enablement uniqueness.

Revision ID: 20260824_0156
Revises: 20260824_0155
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260824_0156"
down_revision: str | None = "20260824_0155"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "connector_capability_enablements"
    op.drop_constraint(
        "uq_connector_capability_enablements_validation",
        table,
        type_="unique",
    )
    op.drop_constraint(
        "uq_connector_capability_enablements_actor_idempotency",
        table,
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_connector_capability_enablements_validation",
        table,
        ["organization_id", "environment_id", "source_validation_id"],
    )
    op.create_unique_constraint(
        "uq_connector_capability_enablements_actor_idempotency",
        table,
        ["organization_id", "environment_id", "enabled_by", "idempotency_key"],
    )


def downgrade() -> None:
    table = "connector_capability_enablements"
    connection = op.get_bind()
    duplicate_validation = connection.execute(
        sa.text(
            "SELECT source_validation_id FROM connector_capability_enablements "
            "GROUP BY source_validation_id HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    duplicate_create_key = connection.execute(
        sa.text(
            "SELECT enabled_by, idempotency_key FROM connector_capability_enablements "
            "GROUP BY enabled_by, idempotency_key HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate_validation is not None or duplicate_create_key is not None:
        raise RuntimeError(
            "Cannot downgrade connector capability enablements: tenant-scoped records "
            "would violate the legacy global uniqueness constraints."
        )
    op.drop_constraint(
        "uq_connector_capability_enablements_actor_idempotency",
        table,
        type_="unique",
    )
    op.drop_constraint(
        "uq_connector_capability_enablements_validation",
        table,
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_connector_capability_enablements_actor_idempotency",
        table,
        ["enabled_by", "idempotency_key"],
    )
    op.create_unique_constraint(
        "uq_connector_capability_enablements_validation",
        table,
        ["source_validation_id"],
    )
