"""Add immutable workflow logical publication channel bindings.

Revision ID: 20260814_0118
Revises: 20260814_0117
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0118"
down_revision: str | None = "20260814_0117"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    binding_table = "workflow_event_channel_bindings"
    op.create_table(
        binding_table,
        sa.Column("binding_id", sa.String(length=128), nullable=False),
        sa.Column("artifact_id", sa.String(length=128), nullable=False),
        sa.Column("artifact_digest", sa.String(length=64), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column("canonical_byte_count", sa.Integer(), nullable=False),
        sa.Column("admission_id", sa.String(length=128), nullable=False),
        sa.Column("admission_digest", sa.String(length=64), nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("event_digest", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("event_version", sa.String(length=32), nullable=False),
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
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("policy_digest", sa.String(length=64), nullable=False),
        sa.Column("logical_channel_id", sa.String(length=128), nullable=False),
        sa.Column("logical_channel_version", sa.String(length=64), nullable=False),
        sa.Column("data_classification", sa.String(length=64), nullable=False),
        sa.Column("representation_name", sa.String(length=64), nullable=False),
        sa.Column("encoding", sa.String(length=32), nullable=False),
        sa.Column("delivery_semantics", sa.String(length=64), nullable=False),
        sa.Column("durability_required", sa.Boolean(), nullable=False),
        sa.Column("ordering_key_kind", sa.String(length=64), nullable=False),
        sa.Column("ordering_key_value", sa.String(length=128), nullable=False),
        sa.Column("retention_class", sa.String(length=64), nullable=False),
        sa.Column("maximum_canonical_byte_count", sa.Integer(), nullable=False),
        # Current lease ownership rows are replaceable. Preserve the exact
        # historical lease evidence without foreign keys to those rows.
        sa.Column("orchestration_lease_id", sa.String(length=128), nullable=False),
        sa.Column("orchestration_lease_digest", sa.String(length=64), nullable=False),
        sa.Column("orchestration_fencing_token", sa.Integer(), nullable=False),
        sa.Column("publication_lease_id", sa.String(length=128), nullable=False),
        sa.Column("publication_lease_digest", sa.String(length=64), nullable=False),
        sa.Column("publication_fencing_token", sa.Integer(), nullable=False),
        sa.Column("publisher_subject_id", sa.String(length=240), nullable=False),
        sa.Column("bound_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("publication_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("delivery_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("dispatch_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("execution_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("attempt_number = 1", name="ck_wf_event_channel_binding_attempt"),
        sa.CheckConstraint(
            "canonical_byte_count >= 1 AND canonical_byte_count <= maximum_canonical_byte_count",
            name="ck_wf_event_channel_binding_byte_count",
        ),
        sa.CheckConstraint(
            "orchestration_fencing_token >= 1",
            name="ck_wf_event_channel_binding_orch_fence",
        ),
        sa.CheckConstraint(
            "publication_fencing_token >= 1",
            name="ck_wf_event_channel_binding_pub_fence",
        ),
        sa.CheckConstraint("state = 'bound'", name="ck_wf_event_channel_binding_state"),
        sa.CheckConstraint(
            "NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted",
            name="ck_wf_event_channel_binding_zero_auth",
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["workflow_event_byte_artifacts.artifact_id"],
            name="fk_wf_event_channel_binding_artifact",
        ),
        sa.ForeignKeyConstraint(
            ["admission_id"],
            ["workflow_event_transport_admissions.admission_id"],
            name="fk_wf_event_channel_binding_admission",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["workflow_dispatch_event_envelopes.event_id"],
            name="fk_wf_event_channel_binding_event",
        ),
        sa.ForeignKeyConstraint(
            ["outbox_entry_id"],
            ["workflow_dispatch_outbox_entries.outbox_entry_id"],
            name="fk_wf_event_channel_binding_outbox",
        ),
        sa.ForeignKeyConstraint(
            ["dispatch_intent_id"],
            ["workflow_dispatch_intents.dispatch_intent_id"],
            name="fk_wf_event_channel_binding_intent",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["workflow_run_plans.plan_id"],
            name="fk_wf_event_channel_binding_plan",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["workflow_execution_runs.run_id"],
            name="fk_wf_event_channel_binding_run",
        ),
        sa.ForeignKeyConstraint(
            ["step_run_id"],
            ["workflow_execution_step_runs.step_run_id"],
            name="fk_wf_event_channel_binding_step_run",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["workflow_execution_attempts.attempt_id"],
            name="fk_wf_event_channel_binding_attempt",
        ),
        sa.PrimaryKeyConstraint("binding_id"),
        sa.UniqueConstraint("artifact_id", name="uq_wf_event_channel_binding_artifact"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_event_channel_binding_digest"),
    )
    binding_indexes = {
        "artifact_id": "artifact",
        "artifact_digest": "artifact_digest",
        "content_sha256": "content_sha",
        "admission_id": "admission",
        "admission_digest": "admission_digest",
        "event_id": "event",
        "event_digest": "event_digest",
        "outbox_entry_id": "outbox",
        "outbox_entry_digest": "outbox_digest",
        "dispatch_intent_id": "intent",
        "dispatch_intent_digest": "intent_digest",
        "plan_id": "plan",
        "plan_digest": "plan_digest",
        "run_id": "run",
        "run_digest": "run_digest",
        "step_run_id": "step_run",
        "step_run_digest": "step_run_digest",
        "step_id": "step",
        "attempt_id": "attempt",
        "attempt_digest": "attempt_digest",
        "organization_id": "org",
        "environment_id": "environment",
        "site_id": "site",
        "target_type": "target_type",
        "target_id": "target",
        "policy_id": "policy",
        "policy_digest": "policy_digest",
        "logical_channel_id": "channel",
        "ordering_key_value": "ordering_value",
        "orchestration_lease_id": "orch_lease",
        "orchestration_lease_digest": "orch_lease_digest",
        "publication_lease_id": "pub_lease",
        "publication_lease_digest": "pub_lease_digest",
        "publisher_subject_id": "publisher",
        "state": "state",
    }
    for column, suffix in binding_indexes.items():
        op.create_index(f"ix_wf_event_channel_binding_{suffix}", binding_table, [column])

    claim_table = "workflow_event_channel_binding_claims"
    op.create_table(
        claim_table,
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("result_digest", sa.String(length=64), nullable=False),
        sa.Column("binding_id", sa.String(length=128), nullable=False),
        sa.Column("artifact_id", sa.String(length=128), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["binding_id"],
            ["workflow_event_channel_bindings.binding_id"],
            name="fk_wf_event_channel_claim_binding",
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["workflow_event_byte_artifacts.artifact_id"],
            name="fk_wf_event_channel_claim_artifact",
        ),
        sa.ForeignKeyConstraint(
            ["admission_id"],
            ["workflow_event_transport_admissions.admission_id"],
            name="fk_wf_event_channel_claim_admission",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["workflow_dispatch_event_envelopes.event_id"],
            name="fk_wf_event_channel_claim_event",
        ),
        sa.ForeignKeyConstraint(
            ["outbox_entry_id"],
            ["workflow_dispatch_outbox_entries.outbox_entry_id"],
            name="fk_wf_event_channel_claim_outbox",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["workflow_run_plans.plan_id"],
            name="fk_wf_event_channel_claim_plan",
        ),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_event_channel_claim_scope_idem",
        ),
        sa.UniqueConstraint("binding_id", name="uq_wf_event_channel_claim_binding"),
        sa.UniqueConstraint("artifact_id", name="uq_wf_event_channel_claim_artifact"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_event_channel_claim_digest"),
    )
    claim_indexes = {
        "idempotency_scope_id": "scope",
        "binding_id": "binding",
        "artifact_id": "artifact",
        "admission_id": "admission",
        "event_id": "event",
        "outbox_entry_id": "outbox",
        "plan_id": "plan",
        "organization_id": "org",
        "environment_id": "environment",
        "site_id": "site",
        "publisher_subject_id": "publisher",
    }
    for column, suffix in claim_indexes.items():
        op.create_index(f"ix_wf_event_channel_claim_{suffix}", claim_table, [column])


def downgrade() -> None:
    claim_table = "workflow_event_channel_binding_claims"
    for suffix in reversed(
        (
            "scope",
            "binding",
            "artifact",
            "admission",
            "event",
            "outbox",
            "plan",
            "org",
            "environment",
            "site",
            "publisher",
        )
    ):
        op.drop_index(f"ix_wf_event_channel_claim_{suffix}", table_name=claim_table)
    op.drop_table(claim_table)

    binding_table = "workflow_event_channel_bindings"
    for suffix in reversed(
        (
            "artifact",
            "artifact_digest",
            "content_sha",
            "admission",
            "admission_digest",
            "event",
            "event_digest",
            "outbox",
            "outbox_digest",
            "intent",
            "intent_digest",
            "plan",
            "plan_digest",
            "run",
            "run_digest",
            "step_run",
            "step_run_digest",
            "step",
            "attempt",
            "attempt_digest",
            "org",
            "environment",
            "site",
            "target_type",
            "target",
            "policy",
            "policy_digest",
            "channel",
            "ordering_value",
            "orch_lease",
            "orch_lease_digest",
            "pub_lease",
            "pub_lease_digest",
            "publisher",
            "state",
        )
    ):
        op.drop_index(f"ix_wf_event_channel_binding_{suffix}", table_name=binding_table)
    op.drop_table(binding_table)
