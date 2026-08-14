"""Add immutable workflow dispatch-intent staging records.

Revision ID: 20260814_0112
Revises: 20260814_0111
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0112"
down_revision: str | None = "20260814_0111"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    intent_table = "workflow_dispatch_intents"
    op.create_table(
        intent_table,
        sa.Column("dispatch_intent_id", sa.String(length=128), nullable=False),
        sa.Column("plan_id", sa.String(length=128), nullable=False),
        sa.Column("plan_digest", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("run_digest", sa.String(length=64), nullable=False),
        sa.Column("step_run_id", sa.String(length=128), nullable=False),
        sa.Column("step_run_digest", sa.String(length=64), nullable=False),
        sa.Column("step_id", sa.String(length=128), nullable=False),
        sa.Column("attempt_id", sa.String(length=128), nullable=False),
        sa.Column("attempt_digest", sa.String(length=64), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("lease_id", sa.String(length=128), nullable=False),
        sa.Column("lease_digest", sa.String(length=64), nullable=False),
        sa.Column("lease_fencing_token", sa.Integer(), nullable=False),
        sa.Column("worker_subject_id", sa.String(length=240), nullable=False),
        sa.Column("staged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "attempt_number = 1",
            name="ck_workflow_dispatch_intent_attempt_number",
        ),
        sa.CheckConstraint(
            "lease_fencing_token >= 1",
            name="ck_workflow_dispatch_intent_fencing_token",
        ),
        sa.CheckConstraint("state = 'staged'", name="ck_workflow_dispatch_intent_state"),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["workflow_run_plans.plan_id"],
            name="fk_workflow_dispatch_intent_plan",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["workflow_execution_runs.run_id"],
            name="fk_workflow_dispatch_intent_run",
        ),
        sa.ForeignKeyConstraint(
            ["step_run_id"],
            ["workflow_execution_step_runs.step_run_id"],
            name="fk_workflow_dispatch_intent_step_run",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["workflow_execution_attempts.attempt_id"],
            name="fk_workflow_dispatch_intent_attempt",
        ),
        # Lease identity is an immutable historical snapshot. The current lease row is
        # replaceable during fencing takeover, so these fields intentionally have no FK.
        sa.PrimaryKeyConstraint("dispatch_intent_id"),
        sa.UniqueConstraint("attempt_id", name="uq_workflow_dispatch_intent_attempt"),
        sa.UniqueConstraint("canonical_digest", name="uq_workflow_dispatch_intent_digest"),
    )
    intent_indexes = (
        "plan_id",
        "plan_digest",
        "run_id",
        "run_digest",
        "step_run_id",
        "step_run_digest",
        "step_id",
        "attempt_id",
        "attempt_digest",
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
    for column in intent_indexes:
        op.create_index(op.f(f"ix_{intent_table}_{column}"), intent_table, [column])
    op.create_index(
        "ix_workflow_dispatch_intents_run_staged",
        intent_table,
        ["run_id", "staged_at", "dispatch_intent_id"],
    )

    claim_table = "workflow_dispatch_intent_staging_claims"
    op.create_table(
        claim_table,
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("result_digest", sa.String(length=64), nullable=False),
        sa.Column("dispatch_intent_id", sa.String(length=128), nullable=False),
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
            ["dispatch_intent_id"],
            ["workflow_dispatch_intents.dispatch_intent_id"],
            name="fk_workflow_dispatch_intent_staging_claim_intent",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["workflow_execution_attempts.attempt_id"],
            name="fk_workflow_dispatch_intent_staging_claim_attempt",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["workflow_execution_runs.run_id"],
            name="fk_workflow_dispatch_intent_staging_claim_run",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["workflow_run_plans.plan_id"],
            name="fk_workflow_dispatch_intent_staging_claim_plan",
        ),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_workflow_dispatch_intent_staging_scope_idem",
        ),
        sa.UniqueConstraint(
            "dispatch_intent_id",
            name="uq_workflow_dispatch_intent_staging_claim_intent",
        ),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_workflow_dispatch_intent_staging_claim_digest",
        ),
    )
    for column in (
        "idempotency_scope_id",
        "dispatch_intent_id",
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
    claim_table = "workflow_dispatch_intent_staging_claims"
    for column in reversed(
        (
            "idempotency_scope_id",
            "dispatch_intent_id",
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

    intent_table = "workflow_dispatch_intents"
    op.drop_index("ix_workflow_dispatch_intents_run_staged", table_name=intent_table)
    for column in reversed(
        (
            "plan_id",
            "plan_digest",
            "run_id",
            "run_digest",
            "step_run_id",
            "step_run_digest",
            "step_id",
            "attempt_id",
            "attempt_digest",
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
        op.drop_index(op.f(f"ix_{intent_table}_{column}"), table_name=intent_table)
    op.drop_table(intent_table)
