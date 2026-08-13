"""Add immutable workflow step-attempt materialization records.

Revision ID: 20260814_0111
Revises: 20260814_0110
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0111"
down_revision: str | None = "20260814_0110"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    attempt_table = "workflow_execution_attempts"
    op.create_table(
        attempt_table,
        sa.Column("attempt_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("run_digest", sa.String(length=64), nullable=False),
        sa.Column("step_run_id", sa.String(length=128), nullable=False),
        sa.Column("step_run_digest", sa.String(length=64), nullable=False),
        sa.Column("step_id", sa.String(length=128), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
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
            "attempt_number = 1",
            name="ck_workflow_execution_attempt_number",
        ),
        sa.CheckConstraint(
            "definition_version >= 1",
            name="ck_workflow_execution_attempt_definition_version",
        ),
        sa.CheckConstraint(
            "lease_fencing_token >= 1",
            name="ck_workflow_execution_attempt_fencing_token",
        ),
        sa.CheckConstraint("state = 'created'", name="ck_workflow_execution_attempt_state"),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["workflow_execution_runs.run_id"],
            name="fk_workflow_execution_attempt_run",
        ),
        sa.ForeignKeyConstraint(
            ["step_run_id"],
            ["workflow_execution_step_runs.step_run_id"],
            name="fk_workflow_execution_attempt_step_run",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["workflow_run_plans.plan_id"],
            name="fk_workflow_execution_attempt_plan",
        ),
        # Lease identity is an immutable historical snapshot. The current lease row is
        # replaceable during fencing takeover, so these fields intentionally have no FK.
        sa.PrimaryKeyConstraint("attempt_id"),
        sa.UniqueConstraint(
            "step_run_id",
            name="uq_workflow_execution_attempt_step_run",
        ),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_workflow_execution_attempt_digest",
        ),
    )
    attempt_indexes = (
        "run_id",
        "run_digest",
        "step_run_id",
        "step_run_digest",
        "step_id",
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
    )
    for column in attempt_indexes:
        op.create_index(op.f(f"ix_{attempt_table}_{column}"), attempt_table, [column])
    op.create_index(
        "ix_workflow_execution_attempts_run_created",
        attempt_table,
        ["run_id", "created_at", "attempt_id"],
    )

    claim_table = "workflow_attempt_materialization_claims"
    op.create_table(
        claim_table,
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("result_digest", sa.String(length=64), nullable=False),
        sa.Column("attempt_id", sa.String(length=128), nullable=False),
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
            ["attempt_id"],
            ["workflow_execution_attempts.attempt_id"],
            name="fk_workflow_attempt_materialization_claim_attempt",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["workflow_execution_runs.run_id"],
            name="fk_workflow_attempt_materialization_claim_run",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["workflow_run_plans.plan_id"],
            name="fk_workflow_attempt_materialization_claim_plan",
        ),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_workflow_attempt_materialization_scope_idem",
        ),
        sa.UniqueConstraint(
            "attempt_id",
            name="uq_workflow_attempt_materialization_claim_attempt",
        ),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_workflow_attempt_materialization_claim_digest",
        ),
    )
    for column in (
        "idempotency_scope_id",
        "attempt_id",
        "run_id",
        "plan_id",
        "organization_id",
        "environment_id",
        "site_id",
        "worker_subject_id",
    ):
        op.create_index(op.f(f"ix_{claim_table}_{column}"), claim_table, [column])


def downgrade() -> None:
    claim_table = "workflow_attempt_materialization_claims"
    for column in reversed(
        (
            "idempotency_scope_id",
            "attempt_id",
            "run_id",
            "plan_id",
            "organization_id",
            "environment_id",
            "site_id",
            "worker_subject_id",
        )
    ):
        op.drop_index(op.f(f"ix_{claim_table}_{column}"), table_name=claim_table)
    op.drop_table(claim_table)

    attempt_table = "workflow_execution_attempts"
    op.drop_index("ix_workflow_execution_attempts_run_created", table_name=attempt_table)
    for column in reversed(
        (
            "run_id",
            "run_digest",
            "step_run_id",
            "step_run_digest",
            "step_id",
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
        )
    ):
        op.drop_index(op.f(f"ix_{attempt_table}_{column}"), table_name=attempt_table)
    op.drop_table(attempt_table)
