"""Add versioned definitions and non-executable workflow run plans.

Revision ID: 20260813_0107
Revises: 20260813_0106
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260813_0107"
down_revision: str | None = "20260813_0106"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    definition_table = "workflow_definitions"
    op.create_table(
        definition_table,
        sa.Column("record_id", sa.String(length=128), nullable=False),
        sa.Column("definition_id", sa.String(length=128), nullable=False),
        sa.Column("definition_version", sa.Integer(), nullable=False),
        sa.Column("definition_digest", sa.String(length=64), nullable=False),
        sa.Column("capability_class", sa.String(length=16), nullable=False),
        sa.Column("input_schema_version", sa.String(length=128), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("definition_version >= 1", name="ck_workflow_definition_version"),
        sa.PrimaryKeyConstraint("record_id"),
        sa.UniqueConstraint(
            "definition_id",
            "definition_version",
            name="uq_workflow_definition_identity_version",
        ),
    )
    for column in ("definition_id", "capability_class", "active"):
        op.create_index(op.f(f"ix_{definition_table}_{column}"), definition_table, [column])

    plan_table = "workflow_run_plans"
    op.create_table(
        plan_table,
        sa.Column("plan_id", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("definition_id", sa.String(length=128), nullable=False),
        sa.Column("definition_version", sa.Integer(), nullable=False),
        sa.Column("definition_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("creator_subject_id", sa.String(length=240), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("canonical_input_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "definition_version >= 1",
            name="ck_workflow_run_plan_definition_version",
        ),
        sa.CheckConstraint("state = 'planned'", name="ck_workflow_run_plan_state"),
        sa.PrimaryKeyConstraint("plan_id"),
        sa.UniqueConstraint("canonical_digest", name="uq_workflow_run_plan_digest"),
    )
    for column in (
        "state",
        "definition_id",
        "organization_id",
        "environment_id",
        "site_id",
        "creator_subject_id",
        "target_type",
        "target_id",
    ):
        op.create_index(op.f(f"ix_{plan_table}_{column}"), plan_table, [column])
    op.create_index(
        "ix_workflow_run_plans_scope_created",
        plan_table,
        ["organization_id", "environment_id", "site_id", "created_at"],
    )

    idempotency_table = "workflow_idempotency_records"
    op.create_table(
        idempotency_table,
        sa.Column("record_id", sa.String(length=128), nullable=False),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(length=240), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("result_digest", sa.String(length=64), nullable=False),
        sa.Column("plan_id", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("creator_subject_id", sa.String(length=240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["workflow_run_plans.plan_id"],
            name="fk_workflow_idempotency_run_plan",
        ),
        sa.PrimaryKeyConstraint("record_id"),
        sa.UniqueConstraint(
            "operation",
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_workflow_operation_scope_idem",
        ),
    )
    for column in (
        "operation",
        "idempotency_scope_id",
        "plan_id",
        "organization_id",
        "environment_id",
        "site_id",
        "creator_subject_id",
    ):
        op.create_index(op.f(f"ix_{idempotency_table}_{column}"), idempotency_table, [column])


def downgrade() -> None:
    idempotency_table = "workflow_idempotency_records"
    for column in reversed(
        (
            "operation",
            "idempotency_scope_id",
            "plan_id",
            "organization_id",
            "environment_id",
            "site_id",
            "creator_subject_id",
        )
    ):
        op.drop_index(op.f(f"ix_{idempotency_table}_{column}"), table_name=idempotency_table)
    op.drop_table(idempotency_table)

    plan_table = "workflow_run_plans"
    op.drop_index("ix_workflow_run_plans_scope_created", table_name=plan_table)
    for column in reversed(
        (
            "state",
            "definition_id",
            "organization_id",
            "environment_id",
            "site_id",
            "creator_subject_id",
            "target_type",
            "target_id",
        )
    ):
        op.drop_index(op.f(f"ix_{plan_table}_{column}"), table_name=plan_table)
    op.drop_table(plan_table)

    definition_table = "workflow_definitions"
    for column in reversed(("definition_id", "capability_class", "active")):
        op.drop_index(op.f(f"ix_{definition_table}_{column}"), table_name=definition_table)
    op.drop_table(definition_table)
