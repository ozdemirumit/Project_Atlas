"""Add immutable workflow run materialization records.

Revision ID: 20260814_0110
Revises: 20260813_0109
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0110"
down_revision: str | None = "20260813_0109"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    run_table = "workflow_execution_runs"
    op.create_table(
        run_table,
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("plan_id", sa.String(length=128), nullable=False),
        sa.Column("plan_digest", sa.String(length=64), nullable=False),
        sa.Column("definition_id", sa.String(length=128), nullable=False),
        sa.Column("definition_version", sa.Integer(), nullable=False),
        sa.Column("definition_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("lease_id", sa.String(length=128), nullable=False),
        sa.Column("lease_digest", sa.String(length=64), nullable=False),
        sa.Column("lease_fencing_token", sa.Integer(), nullable=False),
        sa.Column("materialized_by_subject_id", sa.String(length=240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "definition_version >= 1",
            name="ck_workflow_execution_run_definition_version",
        ),
        sa.CheckConstraint(
            "lease_fencing_token >= 1",
            name="ck_workflow_execution_run_fencing_token",
        ),
        sa.CheckConstraint("state = 'created'", name="ck_workflow_execution_run_state"),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["workflow_run_plans.plan_id"],
            name="fk_workflow_execution_run_plan",
        ),
        # Lease identity is an immutable historical snapshot. The current lease row is
        # replaceable during fencing takeover, so this field intentionally has no FK.
        sa.PrimaryKeyConstraint("run_id"),
        sa.UniqueConstraint("plan_id", name="uq_workflow_execution_run_plan"),
        sa.UniqueConstraint("canonical_digest", name="uq_workflow_execution_run_digest"),
    )
    for column in (
        "plan_id",
        "plan_digest",
        "definition_id",
        "organization_id",
        "environment_id",
        "site_id",
        "target_type",
        "target_id",
        "lease_id",
        "lease_digest",
        "materialized_by_subject_id",
        "state",
    ):
        op.create_index(op.f(f"ix_{run_table}_{column}"), run_table, [column])
    op.create_index(
        "ix_workflow_execution_runs_scope_target_created",
        run_table,
        ["organization_id", "environment_id", "site_id", "target_id", "created_at"],
    )

    step_table = "workflow_execution_step_runs"
    op.create_table(
        step_table,
        sa.Column("step_run_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("step_id", sa.String(length=128), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("capability_class", sa.String(length=8), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("depends_on", postgresql.JSONB(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("ordinal >= 1", name="ck_workflow_step_run_ordinal"),
        sa.CheckConstraint(
            "capability_class IN ('C0', 'C1', 'C2')",
            name="ck_workflow_step_run_capability_class",
        ),
        sa.CheckConstraint(
            "timeout_seconds BETWEEN 1 AND 3600",
            name="ck_workflow_step_run_timeout",
        ),
        sa.CheckConstraint("state = 'not_started'", name="ck_workflow_step_run_state"),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["workflow_execution_runs.run_id"],
            name="fk_workflow_step_run_run",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("step_run_id"),
        sa.UniqueConstraint("run_id", "step_id", name="uq_workflow_step_run_step"),
        sa.UniqueConstraint("run_id", "ordinal", name="uq_workflow_step_run_ordinal"),
        sa.UniqueConstraint("canonical_digest", name="uq_workflow_step_run_digest"),
    )
    for column in ("run_id", "step_id", "kind", "capability_class", "state"):
        op.create_index(op.f(f"ix_{step_table}_{column}"), step_table, [column])
    op.create_index(
        "ix_workflow_execution_step_runs_run_ordinal",
        step_table,
        ["run_id", "ordinal"],
    )

    claim_table = "workflow_run_materialization_claims"
    op.create_table(
        claim_table,
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("result_digest", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("plan_id", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("worker_subject_id", sa.String(length=240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["workflow_execution_runs.run_id"],
            name="fk_workflow_run_materialization_claim_run",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["workflow_run_plans.plan_id"],
            name="fk_workflow_run_materialization_claim_plan",
        ),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_workflow_run_materialization_scope_idem",
        ),
        sa.UniqueConstraint("run_id", name="uq_workflow_run_materialization_claim_run"),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_workflow_run_materialization_claim_digest",
        ),
    )
    for column in (
        "idempotency_scope_id",
        "run_id",
        "plan_id",
        "organization_id",
        "environment_id",
        "site_id",
        "worker_subject_id",
    ):
        op.create_index(op.f(f"ix_{claim_table}_{column}"), claim_table, [column])


def downgrade() -> None:
    claim_table = "workflow_run_materialization_claims"
    for column in reversed(
        (
            "idempotency_scope_id",
            "run_id",
            "plan_id",
            "organization_id",
            "environment_id",
            "site_id",
            "materialized_by_subject_id",
        )
    ):
        op.drop_index(op.f(f"ix_{claim_table}_{column}"), table_name=claim_table)
    op.drop_table(claim_table)

    step_table = "workflow_execution_step_runs"
    op.drop_index("ix_workflow_execution_step_runs_run_ordinal", table_name=step_table)
    for column in reversed(("run_id", "step_id", "kind", "capability_class", "state")):
        op.drop_index(op.f(f"ix_{step_table}_{column}"), table_name=step_table)
    op.drop_table(step_table)

    run_table = "workflow_execution_runs"
    op.drop_index("ix_workflow_execution_runs_scope_target_created", table_name=run_table)
    for column in reversed(
        (
            "plan_id",
            "plan_digest",
            "definition_id",
            "organization_id",
            "environment_id",
            "site_id",
            "target_type",
            "target_id",
            "lease_id",
            "lease_digest",
            "worker_subject_id",
            "state",
        )
    ):
        op.drop_index(op.f(f"ix_{run_table}_{column}"), table_name=run_table)
    op.drop_table(run_table)
