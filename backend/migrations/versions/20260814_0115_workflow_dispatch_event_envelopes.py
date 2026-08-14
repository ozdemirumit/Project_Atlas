"""Add immutable canonical workflow dispatch event envelopes.

Revision ID: 20260814_0115
Revises: 20260814_0114
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0115"
down_revision: str | None = "20260814_0114"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    envelope_table = "workflow_dispatch_event_envelopes"
    op.create_table(
        envelope_table,
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("event_version", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("producer", sa.String(length=128), nullable=False),
        sa.Column("producer_version", sa.String(length=64), nullable=False),
        sa.Column("subject_type", sa.String(length=64), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("causation_id", sa.String(length=128), nullable=False),
        sa.Column("workflow_id", sa.String(length=128), nullable=False),
        sa.Column("data_classification", sa.String(length=64), nullable=False),
        sa.Column("schema_uri", sa.String(length=512), nullable=False),
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
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        # Exact historical lease evidence intentionally has no FK to either
        # replaceable current lease row.
        sa.Column("orchestration_lease_id", sa.String(length=128), nullable=False),
        sa.Column("orchestration_lease_digest", sa.String(length=64), nullable=False),
        sa.Column("orchestration_fencing_token", sa.Integer(), nullable=False),
        sa.Column("publication_lease_id", sa.String(length=128), nullable=False),
        sa.Column("publication_lease_digest", sa.String(length=64), nullable=False),
        sa.Column("publication_fencing_token", sa.Integer(), nullable=False),
        sa.Column("publisher_subject_id", sa.String(length=240), nullable=False),
        sa.Column("prepared_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("publication_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("delivery_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("dispatch_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("execution_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "attempt_number = 1",
            name="ck_workflow_dispatch_event_envelope_attempt_number",
        ),
        sa.CheckConstraint(
            "orchestration_fencing_token >= 1",
            name="ck_workflow_dispatch_event_envelope_orchestration_fence",
        ),
        sa.CheckConstraint(
            "publication_fencing_token >= 1",
            name="ck_workflow_dispatch_event_envelope_publication_fence",
        ),
        sa.CheckConstraint(
            "state = 'prepared'",
            name="ck_workflow_dispatch_event_envelope_state",
        ),
        sa.CheckConstraint(
            "NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted",
            name="ck_workflow_dispatch_event_envelope_zero_authority",
        ),
        sa.ForeignKeyConstraint(
            ["outbox_entry_id"],
            ["workflow_dispatch_outbox_entries.outbox_entry_id"],
            name="fk_workflow_dispatch_event_envelope_outbox",
        ),
        sa.ForeignKeyConstraint(
            ["dispatch_intent_id"],
            ["workflow_dispatch_intents.dispatch_intent_id"],
            name="fk_workflow_dispatch_event_envelope_intent",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["workflow_run_plans.plan_id"],
            name="fk_workflow_dispatch_event_envelope_plan",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["workflow_execution_runs.run_id"],
            name="fk_workflow_dispatch_event_envelope_run",
        ),
        sa.ForeignKeyConstraint(
            ["step_run_id"],
            ["workflow_execution_step_runs.step_run_id"],
            name="fk_workflow_dispatch_event_envelope_step",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["workflow_execution_attempts.attempt_id"],
            name="fk_workflow_dispatch_event_envelope_attempt",
        ),
        sa.PrimaryKeyConstraint("event_id"),
        sa.UniqueConstraint(
            "outbox_entry_id",
            name="uq_workflow_dispatch_event_envelope_outbox",
        ),
        sa.UniqueConstraint(
            "event_id",
            name="uq_workflow_dispatch_event_envelope_event",
        ),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_workflow_dispatch_event_envelope_digest",
        ),
    )
    for column in (
        "event_type",
        "producer",
        "subject_type",
        "subject_id",
        "organization_id",
        "environment_id",
        "site_id",
        "correlation_id",
        "causation_id",
        "workflow_id",
        "data_classification",
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
        "target_type",
        "target_id",
        "orchestration_lease_id",
        "orchestration_lease_digest",
        "publication_lease_id",
        "publication_lease_digest",
        "publisher_subject_id",
        "state",
    ):
        op.create_index(op.f(f"ix_{envelope_table}_{column}"), envelope_table, [column])

    claim_table = "workflow_dispatch_event_envelope_preparation_claims"
    op.create_table(
        claim_table,
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("result_digest", sa.String(length=64), nullable=False),
        # No FK to the immutable envelope is needed: the claim preserves an exact
        # canonical result independently and can be checked without row coupling.
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
        sa.ForeignKeyConstraint(
            ["outbox_entry_id"],
            ["workflow_dispatch_outbox_entries.outbox_entry_id"],
            name="fk_workflow_dispatch_event_envelope_claim_outbox",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["workflow_run_plans.plan_id"],
            name="fk_workflow_dispatch_event_envelope_claim_plan",
        ),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_workflow_dispatch_event_envelope_scope_idem",
        ),
        sa.UniqueConstraint(
            "event_id",
            name="uq_workflow_dispatch_event_envelope_claim_event",
        ),
        sa.UniqueConstraint(
            "outbox_entry_id",
            name="uq_workflow_dispatch_event_envelope_claim_outbox",
        ),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_workflow_dispatch_event_envelope_claim_digest",
        ),
    )
    for column in (
        "idempotency_scope_id",
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
    claim_table = "workflow_dispatch_event_envelope_preparation_claims"
    for column in reversed(
        (
            "idempotency_scope_id",
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

    envelope_table = "workflow_dispatch_event_envelopes"
    for column in reversed(
        (
            "event_type",
            "producer",
            "subject_type",
            "subject_id",
            "organization_id",
            "environment_id",
            "site_id",
            "correlation_id",
            "causation_id",
            "workflow_id",
            "data_classification",
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
            "target_type",
            "target_id",
            "orchestration_lease_id",
            "orchestration_lease_digest",
            "publication_lease_id",
            "publication_lease_digest",
            "publisher_subject_id",
            "state",
        )
    ):
        op.drop_index(op.f(f"ix_{envelope_table}_{column}"), table_name=envelope_table)
    op.drop_table(envelope_table)
