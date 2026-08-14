"""Add fenced workflow dispatch outbox publication leases.

Revision ID: 20260814_0114
Revises: 20260814_0113
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0114"
down_revision: str | None = "20260814_0113"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    lease_table = "workflow_dispatch_outbox_publication_leases"
    op.create_table(
        lease_table,
        sa.Column("publication_lease_id", sa.String(length=128), nullable=False),
        sa.Column("outbox_entry_id", sa.String(length=128), nullable=False),
        sa.Column("outbox_entry_digest", sa.String(length=64), nullable=False),
        sa.Column("dispatch_intent_id", sa.String(length=128), nullable=False),
        sa.Column("dispatch_intent_digest", sa.String(length=64), nullable=False),
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
        # Historical lineage deliberately has no FK to the replaceable current
        # workflow_orchestration_leases row.
        sa.Column("orchestration_lease_id", sa.String(length=128), nullable=False),
        sa.Column("orchestration_lease_digest", sa.String(length=64), nullable=False),
        sa.Column("orchestration_fencing_token", sa.Integer(), nullable=False),
        sa.Column("publisher_subject_id", sa.String(length=240), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("publication_fencing_token", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "publication_fencing_token >= 1",
            name="ck_workflow_dispatch_outbox_publication_lease_fence",
        ),
        sa.CheckConstraint(
            "orchestration_fencing_token >= 1",
            name="ck_workflow_dispatch_outbox_publication_orchestration_fence",
        ),
        sa.CheckConstraint(
            "attempt_number = 1",
            name="ck_workflow_dispatch_outbox_publication_attempt_number",
        ),
        sa.CheckConstraint(
            "state IN ('active', 'released')",
            name="ck_workflow_dispatch_outbox_publication_lease_state",
        ),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_workflow_dispatch_outbox_publication_lease_version",
        ),
        sa.CheckConstraint(
            "last_heartbeat_at >= acquired_at",
            name="ck_workflow_dispatch_outbox_publication_lease_heartbeat_time",
        ),
        sa.CheckConstraint(
            "expires_at > last_heartbeat_at",
            name="ck_workflow_dispatch_outbox_publication_lease_expiry_time",
        ),
        sa.ForeignKeyConstraint(
            ["outbox_entry_id"],
            ["workflow_dispatch_outbox_entries.outbox_entry_id"],
            name="fk_workflow_dispatch_outbox_publication_lease_entry",
        ),
        sa.ForeignKeyConstraint(
            ["dispatch_intent_id"],
            ["workflow_dispatch_intents.dispatch_intent_id"],
            name="fk_workflow_dispatch_outbox_publication_lease_intent",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["workflow_run_plans.plan_id"],
            name="fk_workflow_dispatch_outbox_publication_lease_plan",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["workflow_execution_runs.run_id"],
            name="fk_workflow_dispatch_outbox_publication_lease_run",
        ),
        sa.ForeignKeyConstraint(
            ["step_run_id"],
            ["workflow_execution_step_runs.step_run_id"],
            name="fk_workflow_dispatch_outbox_publication_lease_step",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["workflow_execution_attempts.attempt_id"],
            name="fk_workflow_dispatch_outbox_publication_lease_attempt",
        ),
        sa.PrimaryKeyConstraint("publication_lease_id"),
        sa.UniqueConstraint(
            "outbox_entry_id",
            name="uq_workflow_dispatch_outbox_publication_lease_entry",
        ),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_workflow_dispatch_outbox_publication_lease_digest",
        ),
    )
    for column in (
        "outbox_entry_id",
        "outbox_entry_digest",
        "dispatch_intent_id",
        "dispatch_intent_digest",
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
        "orchestration_lease_id",
        "orchestration_lease_digest",
        "publisher_subject_id",
        "expires_at",
        "state",
    ):
        op.create_index(op.f(f"ix_{lease_table}_{column}"), lease_table, [column])
    op.create_index(
        "ix_workflow_dispatch_outbox_publication_lease_state_expiry",
        lease_table,
        ["outbox_entry_id", "state", "expires_at"],
    )

    claim_table = "workflow_dispatch_outbox_publication_lease_acquire_claims"
    op.create_table(
        claim_table,
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("result_digest", sa.String(length=64), nullable=False),
        # No FK to the current publication lease; the claim remains immutable
        # after an expired/released current lease is replaced by a takeover.
        sa.Column("publication_lease_id", sa.String(length=128), nullable=False),
        sa.Column("outbox_entry_id", sa.String(length=128), nullable=False),
        sa.Column("plan_id", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("publisher_subject_id", sa.String(length=240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["outbox_entry_id"],
            ["workflow_dispatch_outbox_entries.outbox_entry_id"],
            name="fk_workflow_dispatch_outbox_publication_claim_entry",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["workflow_run_plans.plan_id"],
            name="fk_workflow_dispatch_outbox_publication_claim_plan",
        ),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_workflow_dispatch_outbox_publication_lease_scope_idem",
        ),
        sa.UniqueConstraint(
            "publication_lease_id",
            name="uq_workflow_dispatch_outbox_publication_lease_claim_lease",
        ),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_workflow_dispatch_outbox_publication_lease_claim_digest",
        ),
    )
    for column in (
        "idempotency_scope_id",
        "publication_lease_id",
        "outbox_entry_id",
        "plan_id",
        "organization_id",
        "environment_id",
        "site_id",
        "publisher_subject_id",
    ):
        op.create_index(op.f(f"ix_{claim_table}_{column}"), claim_table, [column])


def downgrade() -> None:
    claim_table = "workflow_dispatch_outbox_publication_lease_acquire_claims"
    for column in reversed(
        (
            "idempotency_scope_id",
            "publication_lease_id",
            "outbox_entry_id",
            "plan_id",
            "organization_id",
            "environment_id",
            "site_id",
            "publisher_subject_id",
        )
    ):
        op.drop_index(op.f(f"ix_{claim_table}_{column}"), table_name=claim_table)
    op.drop_table(claim_table)

    lease_table = "workflow_dispatch_outbox_publication_leases"
    op.drop_index(
        "ix_workflow_dispatch_outbox_publication_lease_state_expiry",
        table_name=lease_table,
    )
    for column in reversed(
        (
            "outbox_entry_id",
            "outbox_entry_digest",
            "dispatch_intent_id",
            "dispatch_intent_digest",
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
            "orchestration_lease_id",
            "orchestration_lease_digest",
            "publisher_subject_id",
            "expires_at",
            "state",
        )
    ):
        op.drop_index(op.f(f"ix_{lease_table}_{column}"), table_name=lease_table)
    op.drop_table(lease_table)
