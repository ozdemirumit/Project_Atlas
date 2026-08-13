"""Add fenced workflow orchestration leases.

Revision ID: 20260813_0109
Revises: 20260813_0108
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260813_0109"
down_revision: str | None = "20260813_0108"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    lease_table = "workflow_orchestration_leases"
    op.create_table(
        lease_table,
        sa.Column("lease_id", sa.String(length=128), nullable=False),
        sa.Column("plan_id", sa.String(length=128), nullable=False),
        sa.Column("plan_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("worker_subject_id", sa.String(length=240), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fencing_token", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "state IN ('active', 'released')",
            name="ck_workflow_orchestration_lease_state",
        ),
        sa.CheckConstraint(
            "fencing_token >= 1",
            name="ck_workflow_orchestration_lease_fencing_token",
        ),
        sa.CheckConstraint(
            "version >= 1",
            name="ck_workflow_orchestration_lease_version",
        ),
        sa.CheckConstraint(
            "last_heartbeat_at >= acquired_at",
            name="ck_workflow_orchestration_lease_heartbeat_time",
        ),
        sa.CheckConstraint(
            "expires_at > last_heartbeat_at",
            name="ck_workflow_orchestration_lease_expiry_time",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["workflow_run_plans.plan_id"],
            name="fk_workflow_orchestration_lease_run_plan",
        ),
        sa.PrimaryKeyConstraint("lease_id"),
        sa.UniqueConstraint("plan_id", name="uq_workflow_orchestration_lease_plan"),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_workflow_orchestration_lease_digest",
        ),
    )
    for column in (
        "plan_id",
        "plan_digest",
        "organization_id",
        "environment_id",
        "site_id",
        "target_type",
        "target_id",
        "worker_subject_id",
        "expires_at",
        "state",
    ):
        op.create_index(op.f(f"ix_{lease_table}_{column}"), lease_table, [column])
    op.create_index(
        "ix_workflow_orchestration_leases_plan_state_expiry",
        lease_table,
        ["plan_id", "state", "expires_at"],
    )

    idempotency_table = "workflow_lease_idempotency_records"
    op.create_table(
        idempotency_table,
        sa.Column("record_id", sa.String(length=128), nullable=False),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(length=240), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("result_digest", sa.String(length=64), nullable=False),
        sa.Column("lease_id", sa.String(length=128), nullable=False),
        sa.Column("plan_id", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("worker_subject_id", sa.String(length=240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "operation IN ('acquire', 'heartbeat', 'release')",
            name="ck_workflow_lease_idempotency_operation",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["workflow_run_plans.plan_id"],
            name="fk_workflow_lease_idempotency_plan",
        ),
        sa.PrimaryKeyConstraint("record_id"),
        sa.UniqueConstraint(
            "operation",
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_workflow_lease_operation_scope_idem",
        ),
    )
    for column in (
        "operation",
        "idempotency_scope_id",
        "lease_id",
        "plan_id",
        "organization_id",
        "environment_id",
        "site_id",
        "worker_subject_id",
    ):
        op.create_index(op.f(f"ix_{idempotency_table}_{column}"), idempotency_table, [column])


def downgrade() -> None:
    idempotency_table = "workflow_lease_idempotency_records"
    for column in reversed(
        (
            "operation",
            "idempotency_scope_id",
            "lease_id",
            "plan_id",
            "organization_id",
            "environment_id",
            "site_id",
            "worker_subject_id",
        )
    ):
        op.drop_index(op.f(f"ix_{idempotency_table}_{column}"), table_name=idempotency_table)
    op.drop_table(idempotency_table)

    lease_table = "workflow_orchestration_leases"
    op.drop_index(
        "ix_workflow_orchestration_leases_plan_state_expiry",
        table_name=lease_table,
    )
    for column in reversed(
        (
            "plan_id",
            "plan_digest",
            "organization_id",
            "environment_id",
            "site_id",
            "target_type",
            "target_id",
            "worker_subject_id",
            "expires_at",
            "state",
        )
    ):
        op.drop_index(op.f(f"ix_{lease_table}_{column}"), table_name=lease_table)
    op.drop_table(lease_table)
