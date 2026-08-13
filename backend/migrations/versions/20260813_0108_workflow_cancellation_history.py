"""Add workflow cancellation state and immutable transition history.

Revision ID: 20260813_0108
Revises: 20260813_0107
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260813_0108"
down_revision: str | None = "20260813_0107"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    plan_table = "workflow_run_plans"
    op.drop_constraint("ck_workflow_run_plan_state", plan_table, type_="check")
    op.create_check_constraint(
        "ck_workflow_run_plan_state",
        plan_table,
        "state IN ('planned', 'cancelled')",
    )
    op.add_column(
        plan_table,
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        plan_table,
        sa.Column("state_version", sa.Integer(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE workflow_run_plans "
            "SET updated_at = created_at, state_version = 1 "
            "WHERE updated_at IS NULL OR state_version IS NULL"
        )
    )
    op.alter_column(plan_table, "updated_at", nullable=False)
    op.alter_column(plan_table, "state_version", nullable=False)
    op.create_check_constraint(
        "ck_workflow_run_plan_state_version",
        plan_table,
        "state_version >= 1",
    )

    transition_table = "workflow_plan_transitions"
    op.create_table(
        transition_table,
        sa.Column("transition_id", sa.String(length=128), nullable=False),
        sa.Column("plan_id", sa.String(length=128), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("from_state", sa.String(length=32), nullable=False),
        sa.Column("to_state", sa.String(length=32), nullable=False),
        sa.Column("actor_subject_id", sa.String(length=240), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("reason_digest", sa.String(length=64), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("sequence >= 1", name="ck_workflow_plan_transition_sequence"),
        sa.CheckConstraint(
            "from_state = 'planned' AND to_state = 'cancelled'",
            name="ck_workflow_plan_transition_states",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["workflow_run_plans.plan_id"],
            name="fk_workflow_plan_transition_run_plan",
        ),
        sa.PrimaryKeyConstraint("transition_id"),
        sa.UniqueConstraint(
            "plan_id",
            "sequence",
            name="uq_workflow_plan_transition_sequence",
        ),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_workflow_plan_transition_digest",
        ),
    )
    for column in (
        "plan_id",
        "from_state",
        "to_state",
        "actor_subject_id",
        "organization_id",
        "environment_id",
        "site_id",
        "target_type",
        "target_id",
        "correlation_id",
    ):
        op.create_index(op.f(f"ix_{transition_table}_{column}"), transition_table, [column])
    op.create_index(
        "ix_workflow_plan_transitions_plan_sequence",
        transition_table,
        ["plan_id", "sequence"],
    )


def downgrade() -> None:
    transition_table = "workflow_plan_transitions"
    op.drop_index(
        "ix_workflow_plan_transitions_plan_sequence",
        table_name=transition_table,
    )
    for column in reversed(
        (
            "plan_id",
            "from_state",
            "to_state",
            "actor_subject_id",
            "organization_id",
            "environment_id",
            "site_id",
            "target_type",
            "target_id",
            "correlation_id",
        )
    ):
        op.drop_index(op.f(f"ix_{transition_table}_{column}"), table_name=transition_table)
    op.drop_table(transition_table)

    plan_table = "workflow_run_plans"
    op.drop_constraint("ck_workflow_run_plan_state_version", plan_table, type_="check")
    op.drop_column(plan_table, "state_version")
    op.drop_column(plan_table, "updated_at")
    op.drop_constraint("ck_workflow_run_plan_state", plan_table, type_="check")
    op.create_check_constraint(
        "ck_workflow_run_plan_state",
        plan_table,
        "state = 'planned'",
    )
