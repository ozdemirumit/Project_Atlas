"""Scope connector configuration validation uniqueness.

Revision ID: 20260824_0155
Revises: 20260821_0154
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260824_0155"
down_revision: str | None = "20260821_0154"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "connector_configuration_validations"
    op.drop_constraint(
        "uq_connector_configuration_validations_assignment",
        table,
        type_="unique",
    )
    op.drop_constraint(
        "uq_connector_configuration_validations_actor_idempotency",
        table,
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_connector_configuration_validations_assignment",
        table,
        ["organization_id", "environment_id", "source_assignment_id"],
    )
    op.create_unique_constraint(
        "uq_connector_configuration_validations_actor_idempotency",
        table,
        ["organization_id", "environment_id", "validated_by", "idempotency_key"],
    )


def downgrade() -> None:
    table = "connector_configuration_validations"
    op.drop_constraint(
        "uq_connector_configuration_validations_actor_idempotency",
        table,
        type_="unique",
    )
    op.drop_constraint(
        "uq_connector_configuration_validations_assignment",
        table,
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_connector_configuration_validations_actor_idempotency",
        table,
        ["validated_by", "idempotency_key"],
    )
    op.create_unique_constraint(
        "uq_connector_configuration_validations_assignment",
        table,
        ["source_assignment_id"],
    )
