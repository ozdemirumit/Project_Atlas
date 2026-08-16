"""Add immutable target-context capsule consumer bindings.

Revision ID: 20260816_0134
Revises: 20260815_0133
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260816_0134"
down_revision: str | None = "20260815_0133"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BINDING_TABLE = "workflow_event_tctx_capsule_consumer_bindings"
CLAIM_TABLE = "workflow_event_tctx_capsule_consumer_binding_claims"
OPENING_RESULT_TABLE = "workflow_event_tctx_artifact_opening_results"
TARGET_CONTEXT_TABLE = "workflow_event_transport_target_context_bindings"
OUTBOX_TABLE = "workflow_dispatch_outbox_entries"
EVENT_TABLE = "workflow_dispatch_event_envelopes"
ARTIFACT_TABLE = "workflow_event_byte_artifacts"
ROUTE_BINDING_TABLE = "workflow_event_physical_transport_route_bindings"
ROUTE_SNAPSHOT_TABLE = "event_transport_route_snapshots"
CREDENTIAL_BINDING_TABLE = "workflow_event_physical_transport_credential_bindings"
CREDENTIAL_SNAPSHOT_TABLE = "event_transport_credential_assignment_snapshots"

DOWNGRADE_EMPTY_GUARD_SQL = f"""
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM {CLAIM_TABLE} LIMIT 1)
       OR EXISTS (SELECT 1 FROM {BINDING_TABLE} LIMIT 1) THEN
        RAISE EXCEPTION
            'refusing to downgrade target-context capsule consumer binding schema: '
            'append-only tables contain evidence'
            USING ERRCODE = '55000';
    END IF;
END;
$$
"""


def upgrade() -> None:
    op.create_table(
        BINDING_TABLE,
        sa.Column("binding_id", sa.String(length=128), nullable=False),
        sa.Column("opening_result_id", sa.String(length=128), nullable=False),
        sa.Column("opening_result_digest", sa.String(length=64), nullable=False),
        sa.Column("opening_attempt_id", sa.String(length=128), nullable=False),
        sa.Column("opening_attempt_digest", sa.String(length=64), nullable=False),
        sa.Column("lease_consumption_claim_id", sa.String(length=128), nullable=False),
        sa.Column("lease_consumption_claim_digest", sa.String(length=64), nullable=False),
        sa.Column("authorization_lease_id", sa.String(length=128), nullable=False),
        sa.Column("authorization_lease_digest", sa.String(length=64), nullable=False),
        sa.Column("sealed_capsule_id", sa.String(length=128), nullable=False),
        sa.Column("sealed_capsule_digest", sa.String(length=64), nullable=False),
        sa.Column("capsule_schema_id", sa.String(length=128), nullable=False),
        sa.Column("capsule_schema_version", sa.String(length=64), nullable=False),
        sa.Column("capsule_is_bearer_capability", sa.Boolean(), nullable=False),
        sa.Column("target_context_binding_id", sa.String(length=128), nullable=False),
        sa.Column("target_context_binding_digest", sa.String(length=64), nullable=False),
        sa.Column("target_context_commitment", sa.String(length=64), nullable=False),
        sa.Column("outbox_entry_id", sa.String(length=128), nullable=False),
        sa.Column("outbox_entry_digest", sa.String(length=64), nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("event_digest", sa.String(length=64), nullable=False),
        sa.Column("event_artifact_id", sa.String(length=128), nullable=False),
        sa.Column("event_artifact_digest", sa.String(length=64), nullable=False),
        sa.Column("logical_channel_binding_id", sa.String(length=128), nullable=False),
        sa.Column("logical_channel_binding_digest", sa.String(length=64), nullable=False),
        sa.Column("physical_transport_route_binding_id", sa.String(length=128), nullable=False),
        sa.Column("physical_transport_route_binding_digest", sa.String(length=64), nullable=False),
        sa.Column("transport_route_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("transport_route_snapshot_digest", sa.String(length=64), nullable=False),
        sa.Column(
            "physical_transport_credential_assignment_binding_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "physical_transport_credential_assignment_binding_digest",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("credential_assignment_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("credential_assignment_snapshot_digest", sa.String(length=64), nullable=False),
        sa.Column("plan_id", sa.String(length=128), nullable=False),
        sa.Column("plan_digest", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("run_digest", sa.String(length=64), nullable=False),
        sa.Column("step_run_id", sa.String(length=128), nullable=False),
        sa.Column("step_run_digest", sa.String(length=64), nullable=False),
        sa.Column("workflow_execution_attempt_id", sa.String(length=128), nullable=False),
        sa.Column("workflow_execution_attempt_digest", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("consumer_subject_id", sa.String(length=240), nullable=False),
        sa.Column("consumer_audience", sa.String(length=240), nullable=False),
        sa.Column("consumer_contract_id", sa.String(length=128), nullable=False),
        sa.Column("consumer_contract_version", sa.String(length=64), nullable=False),
        sa.Column("purpose_id", sa.String(length=128), nullable=False),
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("policy_digest", sa.String(length=64), nullable=False),
        *_scope_columns(),
        sa.Column("binder_subject_id", sa.String(length=240), nullable=False),
        sa.Column("binder_audience", sa.String(length=240), nullable=False),
        sa.Column("bound_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_digest", sa.String(length=64), nullable=False),
        sa.Column("authorization_audit_digest", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("state = 'bound'", name="ck_wf_tctx_capsule_binding_state"),
        sa.CheckConstraint(
            "bound_at < effective_until",
            name="ck_wf_tctx_capsule_binding_window",
        ),
        sa.CheckConstraint(
            "NOT capsule_is_bearer_capability",
            name="ck_wf_tctx_capsule_binding_non_bearer",
        ),
        sa.CheckConstraint(
            _code_owned_contract_check(),
            name="ck_wf_tctx_capsule_binding_contract",
        ),
        sa.CheckConstraint(_zero_authority_check(), name="ck_wf_tctx_capsule_binding_authority"),
        sa.ForeignKeyConstraint(
            ["opening_result_id"],
            [f"{OPENING_RESULT_TABLE}.opening_id"],
            name="fk_wf_tctx_capsule_binding_opening",
        ),
        sa.ForeignKeyConstraint(
            ["target_context_binding_id"],
            [f"{TARGET_CONTEXT_TABLE}.binding_id"],
            name="fk_wf_tctx_capsule_binding_target_context",
        ),
        sa.ForeignKeyConstraint(
            ["outbox_entry_id"],
            [f"{OUTBOX_TABLE}.outbox_entry_id"],
            name="fk_wf_tctx_capsule_binding_outbox",
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            [f"{EVENT_TABLE}.event_id"],
            name="fk_wf_tctx_capsule_binding_event",
        ),
        sa.ForeignKeyConstraint(
            ["event_artifact_id"],
            [f"{ARTIFACT_TABLE}.artifact_id"],
            name="fk_wf_tctx_capsule_binding_artifact",
        ),
        sa.ForeignKeyConstraint(
            ["logical_channel_binding_id"],
            ["workflow_event_channel_bindings.binding_id"],
            name="fk_wf_tctx_capsule_binding_logical",
        ),
        sa.ForeignKeyConstraint(
            ["physical_transport_route_binding_id"],
            [f"{ROUTE_BINDING_TABLE}.binding_id"],
            name="fk_wf_tctx_capsule_binding_route",
        ),
        sa.ForeignKeyConstraint(
            ["transport_route_snapshot_id"],
            [f"{ROUTE_SNAPSHOT_TABLE}.snapshot_id"],
            name="fk_wf_tctx_capsule_binding_route_snapshot",
        ),
        sa.ForeignKeyConstraint(
            ["physical_transport_credential_assignment_binding_id"],
            [f"{CREDENTIAL_BINDING_TABLE}.binding_id"],
            name="fk_wf_tctx_capsule_binding_credential",
        ),
        sa.ForeignKeyConstraint(
            ["credential_assignment_snapshot_id"],
            [f"{CREDENTIAL_SNAPSHOT_TABLE}.snapshot_id"],
            name="fk_wf_tctx_capsule_binding_credential_snapshot",
        ),
        sa.PrimaryKeyConstraint("binding_id"),
        sa.UniqueConstraint("opening_result_id", name="uq_wf_tctx_capsule_binding_opening"),
        sa.UniqueConstraint("sealed_capsule_id", name="uq_wf_tctx_capsule_binding_capsule"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_tctx_capsule_binding_digest"),
        sa.UniqueConstraint(
            "outbox_entry_id",
            "event_id",
            "event_artifact_id",
            "consumer_subject_id",
            "consumer_contract_id",
            "consumer_contract_version",
            "purpose_id",
            name="uq_wf_tctx_capsule_binding_event_consumer",
        ),
    )
    _create_indexes(
        BINDING_TABLE,
        {
            "consumer_subject_id": "ix_wf_tctx_capsule_binding_consumer",
            "outbox_entry_id": "ix_wf_tctx_capsule_binding_outbox",
            "bound_at": "ix_wf_tctx_capsule_binding_bound",
        },
    )
    op.create_index(
        "ix_wf_tctx_capsule_binding_scope",
        BINDING_TABLE,
        ["organization_id", "environment_id", "site_id"],
    )

    op.create_table(
        CLAIM_TABLE,
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("idempotency_digest", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("result_digest", sa.String(length=64), nullable=False),
        sa.Column("binding_id", sa.String(length=128), nullable=False),
        sa.Column("opening_result_id", sa.String(length=128), nullable=False),
        sa.Column("sealed_capsule_id", sa.String(length=128), nullable=False),
        sa.Column("consumer_subject_id", sa.String(length=240), nullable=False),
        sa.Column("consumer_audience", sa.String(length=240), nullable=False),
        sa.Column("consumer_contract_id", sa.String(length=128), nullable=False),
        sa.Column("consumer_contract_version", sa.String(length=64), nullable=False),
        sa.Column("purpose_id", sa.String(length=128), nullable=False),
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("policy_digest", sa.String(length=64), nullable=False),
        *_scope_columns(),
        sa.Column("binder_subject_id", sa.String(length=240), nullable=False),
        sa.Column("binder_audience", sa.String(length=240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("authorization_audit_digest", sa.String(length=64), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("authorization_audit_payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            _code_owned_contract_check(),
            name="ck_wf_tctx_capsule_claim_contract",
        ),
        sa.CheckConstraint(
            "char_length(authorization_audit_digest) = 64 "
            "AND authorization_audit_digest ~ '^[0-9a-f]{64}$' "
            "AND jsonb_typeof(authorization_audit_payload) = 'object' "
            "AND authorization_audit_payload <> '{}'::jsonb",
            name="ck_wf_tctx_capsule_claim_audit",
        ),
        sa.ForeignKeyConstraint(
            ["binding_id"],
            [f"{BINDING_TABLE}.binding_id"],
            name="fk_wf_tctx_capsule_claim_binding",
        ),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_tctx_capsule_claim_scope_idem",
        ),
        sa.UniqueConstraint("binding_id", name="uq_wf_tctx_capsule_claim_binding"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_tctx_capsule_claim_digest"),
    )
    _create_indexes(
        CLAIM_TABLE,
        {
            "idempotency_scope_id": "ix_wf_tctx_capsule_claim_scope",
            "opening_result_id": "ix_wf_tctx_capsule_claim_opening",
        },
    )

    op.execute(
        """
        CREATE FUNCTION reject_wf_tctx_capsule_consumer_binding_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'workflow target-context capsule consumer bindings are append-only'
                USING ERRCODE = '55000';
        END;
        $$
        """
    )
    for table_name, trigger_name in _triggers().items():
        op.execute(
            f"""
            CREATE TRIGGER {trigger_name}
            BEFORE UPDATE OR DELETE ON {table_name}
            FOR EACH ROW
            EXECUTE FUNCTION reject_wf_tctx_capsule_consumer_binding_mutation()
            """
        )


def downgrade() -> None:
    op.execute(DOWNGRADE_EMPTY_GUARD_SQL)
    for table_name, trigger_name in _triggers().items():
        op.execute(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name}")
    op.execute("DROP FUNCTION IF EXISTS reject_wf_tctx_capsule_consumer_binding_mutation()")
    op.drop_table(CLAIM_TABLE)
    op.drop_table(BINDING_TABLE)


def _scope_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
    )


def _authority_columns() -> tuple[sa.Column[object], ...]:
    return tuple(
        sa.Column(name, sa.Boolean(), nullable=False)
        for name in (
            "route_selection_authority_granted",
            "route_binding_authority_granted",
            "endpoint_resolution_authority_granted",
            "protected_artifact_access_authority_granted",
            "credential_selection_authority_granted",
            "credential_assignment_binding_authority_granted",
            "credential_access_authority_granted",
            "credential_brokerage_authority_granted",
            "credential_resolution_authority_granted",
            "credential_delivery_authority_granted",
            "network_access_authority_granted",
            "readiness_probe_authority_granted",
            "publication_authority_granted",
            "delivery_authority_granted",
            "dispatch_authority_granted",
            "execution_authority_granted",
            "infrastructure_mutation_authority_granted",
        )
    )


def _zero_authority_check() -> str:
    return " AND ".join(f"NOT {column.name}" for column in _authority_columns())


def _code_owned_contract_check() -> str:
    return (
        "consumer_subject_id = "
        "'service.workflow-protected-transport-target-context-capsule-consumer' "
        "AND consumer_audience = "
        "'audience.workflow-protected-transport-target-context-capsule-consumer' "
        "AND consumer_contract_id = "
        "'contract.workflow-protected-transport-target-context-capsule-consumer' "
        "AND consumer_contract_version = '1.0' "
        "AND purpose_id = "
        "'purpose.workflow-protected-transport-target-context-capsule-handoff-evaluation' "
        "AND policy_id = "
        "'policy.workflow-protected-transport-target-context-capsule-consumer-binding' "
        "AND policy_version = '1.0' "
        "AND policy_digest = "
        "'1f7d71594e9ffdc863626ef68e53e9cc0ff829a81511aaf52b7c2c7f82a85e8f' "
        "AND binder_subject_id = "
        "'service.workflow-protected-transport-target-context-capsule-binder' "
        "AND binder_audience = "
        "'audience.workflow-protected-transport-target-context-capsule-binder'"
    )


def _create_indexes(table_name: str, indexes: dict[str, str]) -> None:
    for column, name in indexes.items():
        op.create_index(name, table_name, [column])


def _triggers() -> dict[str, str]:
    return {
        BINDING_TABLE: "trg_wf_tctx_capsule_bindings_append_only",
        CLAIM_TABLE: "trg_wf_tctx_capsule_claims_append_only",
    }
