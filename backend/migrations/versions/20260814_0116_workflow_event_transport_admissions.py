"""Add immutable policy-governed workflow event transport admissions.

Revision ID: 20260814_0116
Revises: 20260814_0115
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0116"
down_revision: str | None = "20260814_0115"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    admission_table = "workflow_event_transport_admissions"
    op.create_table(
        admission_table,
        sa.Column("admission_id", sa.String(length=128), nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("event_digest", sa.String(length=64), nullable=False),
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
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("policy_digest", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("event_version", sa.String(length=32), nullable=False),
        sa.Column("schema_uri", sa.String(length=512), nullable=False),
        sa.Column("data_classification", sa.String(length=64), nullable=False),
        sa.Column("representation_name", sa.String(length=64), nullable=False),
        sa.Column("encoding", sa.String(length=32), nullable=False),
        sa.Column("maximum_canonical_byte_count", sa.Integer(), nullable=False),
        sa.Column("canonical_byte_count", sa.Integer(), nullable=False),
        # Exact historical lease evidence intentionally has no FK to either
        # replaceable current lease row.
        sa.Column("orchestration_lease_id", sa.String(length=128), nullable=False),
        sa.Column("orchestration_lease_digest", sa.String(length=64), nullable=False),
        sa.Column("orchestration_fencing_token", sa.Integer(), nullable=False),
        sa.Column("publication_lease_id", sa.String(length=128), nullable=False),
        sa.Column("publication_lease_digest", sa.String(length=64), nullable=False),
        sa.Column("publication_fencing_token", sa.Integer(), nullable=False),
        sa.Column("publisher_subject_id", sa.String(length=240), nullable=False),
        sa.Column("admitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("publication_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("delivery_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("dispatch_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("execution_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "attempt_number = 1",
            name="ck_workflow_event_transport_admission_attempt_number",
        ),
        sa.CheckConstraint(
            "canonical_byte_count >= 1 AND canonical_byte_count <= maximum_canonical_byte_count",
            name="ck_workflow_event_transport_admission_byte_count",
        ),
        sa.CheckConstraint(
            "orchestration_fencing_token >= 1",
            name="ck_workflow_event_transport_admission_orchestration_fence",
        ),
        sa.CheckConstraint(
            "publication_fencing_token >= 1",
            name="ck_workflow_event_transport_admission_publication_fence",
        ),
        sa.CheckConstraint(
            "state = 'admitted'",
            name="ck_workflow_event_transport_admission_state",
        ),
        sa.CheckConstraint(
            "NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted",
            name="ck_workflow_event_transport_admission_zero_authority",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["workflow_dispatch_event_envelopes.event_id"],
            name="fk_workflow_event_transport_admission_event",
        ),
        sa.ForeignKeyConstraint(
            ["outbox_entry_id"],
            ["workflow_dispatch_outbox_entries.outbox_entry_id"],
            name="fk_workflow_event_transport_admission_outbox",
        ),
        sa.ForeignKeyConstraint(
            ["dispatch_intent_id"],
            ["workflow_dispatch_intents.dispatch_intent_id"],
            name="fk_workflow_event_transport_admission_intent",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["workflow_run_plans.plan_id"],
            name="fk_workflow_event_transport_admission_plan",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["workflow_execution_runs.run_id"],
            name="fk_workflow_event_transport_admission_run",
        ),
        sa.ForeignKeyConstraint(
            ["step_run_id"],
            ["workflow_execution_step_runs.step_run_id"],
            name="fk_workflow_event_transport_admission_step",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["workflow_execution_attempts.attempt_id"],
            name="fk_workflow_event_transport_admission_attempt",
        ),
        sa.PrimaryKeyConstraint("admission_id"),
        sa.UniqueConstraint(
            "event_id",
            name="uq_workflow_event_transport_admission_event",
        ),
        sa.UniqueConstraint(
            "outbox_entry_id",
            name="uq_workflow_event_transport_admission_outbox",
        ),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_workflow_event_transport_admission_digest",
        ),
    )
    for column in (
        "event_id",
        "event_digest",
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
        "policy_id",
        "policy_digest",
        "orchestration_lease_id",
        "orchestration_lease_digest",
        "publication_lease_id",
        "publication_lease_digest",
        "publisher_subject_id",
        "state",
    ):
        op.create_index(op.f(f"ix_{admission_table}_{column}"), admission_table, [column])

    claim_table = "workflow_event_transport_admission_claims"
    op.create_table(
        claim_table,
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("result_digest", sa.String(length=64), nullable=False),
        sa.Column("admission_id", sa.String(length=128), nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("outbox_entry_id", sa.String(length=128), nullable=False),
        sa.Column("plan_id", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("publisher_subject_id", sa.String(length=240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        # The claim independently preserves the exact immutable result. It is not
        # coupled to replaceable lease rows or to a mutable execution lifecycle.
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["workflow_dispatch_event_envelopes.event_id"],
            name="fk_workflow_event_transport_admission_claim_event",
        ),
        sa.ForeignKeyConstraint(
            ["outbox_entry_id"],
            ["workflow_dispatch_outbox_entries.outbox_entry_id"],
            name="fk_workflow_event_transport_admission_claim_outbox",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["workflow_run_plans.plan_id"],
            name="fk_workflow_event_transport_admission_claim_plan",
        ),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_workflow_event_transport_admission_scope_idem",
        ),
        sa.UniqueConstraint(
            "admission_id",
            name="uq_workflow_event_transport_admission_claim_admission",
        ),
        sa.UniqueConstraint(
            "event_id",
            name="uq_workflow_event_transport_admission_claim_event",
        ),
        sa.UniqueConstraint(
            "outbox_entry_id",
            name="uq_workflow_event_transport_admission_claim_outbox",
        ),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_workflow_event_transport_admission_claim_digest",
        ),
    )
    for column in (
        "idempotency_scope_id",
        "admission_id",
        "event_id",
        "outbox_entry_id",
        "plan_id",
        "organization_id",
        "environment_id",
        "site_id",
        "publisher_subject_id",
    ):
        op.create_index(op.f(f"ix_{claim_table}_{column}"), claim_table, [column])


def downgrade() -> None:
    claim_table = "workflow_event_transport_admission_claims"
    for column in reversed(
        (
            "idempotency_scope_id",
            "admission_id",
            "event_id",
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

    admission_table = "workflow_event_transport_admissions"
    for column in reversed(
        (
            "event_id",
            "event_digest",
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
            "policy_id",
            "policy_digest",
            "orchestration_lease_id",
            "orchestration_lease_digest",
            "publication_lease_id",
            "publication_lease_digest",
            "publisher_subject_id",
            "state",
        )
    ):
        op.drop_index(op.f(f"ix_{admission_table}_{column}"), table_name=admission_table)
    op.drop_table(admission_table)
