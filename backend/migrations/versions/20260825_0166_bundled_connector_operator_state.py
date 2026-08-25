"""Add bundled connector operator-state persistence.

Revision ID: 20260825_0166
Revises: 20260825_0165
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260825_0166"
down_revision: str | None = "20260825_0165"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    configuration_table = "bundled_connection_configurations"
    op.create_table(
        configuration_table,
        sa.Column("configuration_id", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("connector_id", sa.String(length=128), nullable=False),
        sa.Column("instance_id", sa.String(length=128), nullable=False),
        sa.Column("configured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.PrimaryKeyConstraint("configuration_id"),
        sa.UniqueConstraint(
            "organization_id",
            "environment_id",
            "instance_id",
            name="uq_bundled_connection_configurations_scope_instance",
        ),
    )
    for column in (
        "organization_id",
        "environment_id",
        "connector_id",
        "instance_id",
        "configured_at",
    ):
        op.create_index(
            op.f(f"ix_{configuration_table}_{column}"),
            configuration_table,
            [column],
            unique=False,
        )

    test_result_table = "connector_connection_test_results"
    op.create_table(
        test_result_table,
        sa.Column("test_id", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("connector_id", sa.String(length=128), nullable=False),
        sa.Column("instance_id", sa.String(length=128), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('passed', 'failed')",
            name="ck_connector_connection_test_results_outcome",
        ),
        sa.PrimaryKeyConstraint("test_id"),
    )
    for column in (
        "organization_id",
        "environment_id",
        "connector_id",
        "instance_id",
        "outcome",
    ):
        op.create_index(
            op.f(f"ix_{test_result_table}_{column}"),
            test_result_table,
            [column],
            unique=False,
        )
    op.create_index(
        "ix_connector_connection_test_results_scope_latest",
        test_result_table,
        ["organization_id", "environment_id", "instance_id", "checked_at"],
        unique=False,
    )

    runtime_state_table = "bundled_connector_runtime_states"
    op.create_table(
        runtime_state_table,
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("instance_id", sa.String(length=128), nullable=False),
        sa.Column("connector_id", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "state IN ('disabled', 'enabled_read_only')",
            name="ck_bundled_connector_runtime_states_state",
        ),
        sa.CheckConstraint(
            "version >= 0",
            name="ck_bundled_connector_runtime_states_version",
        ),
        sa.PrimaryKeyConstraint("organization_id", "environment_id", "instance_id"),
    )
    for column in (
        "organization_id",
        "environment_id",
        "instance_id",
        "connector_id",
        "state",
        "changed_at",
    ):
        op.create_index(
            op.f(f"ix_{runtime_state_table}_{column}"),
            runtime_state_table,
            [column],
            unique=False,
        )


def downgrade() -> None:
    runtime_state_table = "bundled_connector_runtime_states"
    for column in reversed(
        (
            "organization_id",
            "environment_id",
            "instance_id",
            "connector_id",
            "state",
            "changed_at",
        )
    ):
        op.drop_index(op.f(f"ix_{runtime_state_table}_{column}"), table_name=runtime_state_table)
    op.drop_table(runtime_state_table)

    test_result_table = "connector_connection_test_results"
    op.drop_index(
        "ix_connector_connection_test_results_scope_latest",
        table_name=test_result_table,
    )
    for column in reversed(
        (
            "organization_id",
            "environment_id",
            "connector_id",
            "instance_id",
            "outcome",
        )
    ):
        op.drop_index(op.f(f"ix_{test_result_table}_{column}"), table_name=test_result_table)
    op.drop_table(test_result_table)

    configuration_table = "bundled_connection_configurations"
    for column in reversed(
        (
            "organization_id",
            "environment_id",
            "connector_id",
            "instance_id",
            "configured_at",
        )
    ):
        op.drop_index(
            op.f(f"ix_{configuration_table}_{column}"),
            table_name=configuration_table,
        )
    op.drop_table(configuration_table)
