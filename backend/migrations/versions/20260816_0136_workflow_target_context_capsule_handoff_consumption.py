"""Add atomic sealed target-context capsule handoff evidence.

Revision ID: 20260816_0136
Revises: 20260816_0135
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260816_0136"
down_revision: str | None = "20260816_0135"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEASE_TABLE = "workflow_event_tctx_capsule_handoff_authorization_leases"
CLAIM_TABLE = "workflow_event_tctx_capsule_handoff_consumption_claims"
ATTEMPT_TABLE = "workflow_event_tctx_capsule_handoff_attempts"
RESULT_TABLE = "workflow_event_tctx_capsule_handoff_results"
APPEND_ONLY_FUNCTION = "reject_wf_tctx_capsule_handoff_mutation"


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
            "target_context_capsule_handoff_authority_granted",
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


def upgrade() -> None:
    op.create_table(
        CLAIM_TABLE,
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("handoff_id", sa.String(length=128), nullable=False),
        sa.Column("attempt_id", sa.String(length=128), nullable=False),
        sa.Column("authorization_lease_id", sa.String(length=128), nullable=False),
        sa.Column("authorization_lease_digest", sa.String(length=64), nullable=False),
        sa.Column("consumer_binding_id", sa.String(length=128), nullable=False),
        sa.Column("consumer_binding_digest", sa.String(length=64), nullable=False),
        sa.Column("sealed_capsule_id", sa.String(length=128), nullable=False),
        sa.Column("sealed_capsule_digest", sa.String(length=64), nullable=False),
        *_scope_columns(),
        sa.Column("consumer_subject_id", sa.String(length=240), nullable=False),
        sa.Column("consumer_audience", sa.String(length=240), nullable=False),
        sa.Column("consumer_contract_id", sa.String(length=128), nullable=False),
        sa.Column("consumer_contract_version", sa.String(length=64), nullable=False),
        sa.Column("purpose_id", sa.String(length=128), nullable=False),
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("policy_digest", sa.String(length=64), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("idempotency_digest", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("irreversible_consumption_acknowledged", sa.Boolean(), nullable=False),
        sa.Column(
            "uncertain_outcome_requires_new_authorization_acknowledged",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column("consumption_authorization_audit_digest", sa.String(64), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("consumption_authorization_audit_payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "consumer_subject_id = "
            "'service.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_audience = "
            "'audience.workflow-protected-transport-target-context-capsule-consumer' "
            "AND policy_id = "
            "'policy.workflow-protected-transport-target-context-capsule-handoff-consumption' "
            "AND policy_version = '1.0'",
            name="ck_wf_tctx_handoff_consume_contract",
        ),
        sa.CheckConstraint(
            "irreversible_consumption_acknowledged "
            "AND uncertain_outcome_requires_new_authorization_acknowledged",
            name="ck_wf_tctx_handoff_consume_ack",
        ),
        sa.CheckConstraint(_zero_authority_check(), name="ck_wf_tctx_handoff_consume_authority"),
        sa.ForeignKeyConstraint(
            ["authorization_lease_id"],
            [f"{LEASE_TABLE}.authorization_lease_id"],
            name="fk_wf_tctx_handoff_consume_lease",
        ),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_tctx_handoff_consume_lease"),
        sa.UniqueConstraint("consumer_binding_id", name="uq_wf_tctx_handoff_consume_binding"),
        sa.UniqueConstraint("sealed_capsule_id", name="uq_wf_tctx_handoff_consume_capsule"),
        sa.UniqueConstraint("attempt_id", name="uq_wf_tctx_handoff_consume_attempt"),
        sa.UniqueConstraint("handoff_id", name="uq_wf_tctx_handoff_consume_handoff"),
        sa.UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_tctx_handoff_consume_scope_idem",
        ),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_tctx_handoff_consume_digest"),
    )
    op.create_index(
        "ix_wf_tctx_handoff_consume_scope",
        CLAIM_TABLE,
        ["organization_id", "environment_id", "site_id"],
    )
    op.create_index("ix_wf_tctx_handoff_consume_claimed", CLAIM_TABLE, ["claimed_at"])

    op.create_table(
        ATTEMPT_TABLE,
        sa.Column("attempt_id", sa.String(length=128), nullable=False),
        sa.Column("handoff_id", sa.String(length=128), nullable=False),
        sa.Column("consumption_claim_id", sa.String(length=128), nullable=False),
        sa.Column("authorization_lease_id", sa.String(length=128), nullable=False),
        sa.Column("authorization_lease_digest", sa.String(length=64), nullable=False),
        sa.Column("consumer_binding_id", sa.String(length=128), nullable=False),
        sa.Column("consumer_binding_digest", sa.String(length=64), nullable=False),
        sa.Column("sealed_capsule_id", sa.String(length=128), nullable=False),
        sa.Column("sealed_capsule_digest", sa.String(length=64), nullable=False),
        sa.Column("capsule_schema_id", sa.String(length=128), nullable=False),
        sa.Column("capsule_schema_version", sa.String(length=64), nullable=False),
        *_scope_columns(),
        sa.Column("consumer_subject_id", sa.String(length=240), nullable=False),
        sa.Column("consumer_audience", sa.String(length=240), nullable=False),
        sa.Column("consumer_contract_id", sa.String(length=128), nullable=False),
        sa.Column("consumer_contract_version", sa.String(length=64), nullable=False),
        sa.Column("purpose_id", sa.String(length=128), nullable=False),
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("policy_digest", sa.String(length=64), nullable=False),
        sa.Column("adapter_contract_id", sa.String(length=128), nullable=False),
        sa.Column("adapter_contract_version", sa.String(length=64), nullable=False),
        sa.Column("approved_adapter_id", sa.String(length=128), nullable=False),
        sa.Column("approved_adapter_version", sa.String(length=64), nullable=False),
        sa.Column("destination_boundary_id", sa.String(length=128), nullable=False),
        sa.Column("destination_deployment_id", sa.String(length=128), nullable=False),
        sa.Column("destination_generation", sa.Integer(), nullable=False),
        sa.Column("destination_fencing_token_digest", sa.String(length=64), nullable=False),
        sa.Column("custody_contract_id", sa.String(length=128), nullable=False),
        sa.Column("custody_contract_version", sa.String(length=64), nullable=False),
        sa.Column("verification_signing_key_id", sa.String(length=128), nullable=False),
        sa.Column("trusted_profile_digest", sa.String(length=64), nullable=False),
        sa.Column("lifecycle_attestation_id", sa.String(length=128), nullable=False),
        sa.Column("lifecycle_attestation_digest", sa.String(length=64), nullable=False),
        sa.Column("lifecycle_attestation_valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acceptance_attestation_id", sa.String(length=128), nullable=False),
        sa.Column("acceptance_attestation_digest", sa.String(length=64), nullable=False),
        sa.Column("acceptance_attestation_valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_nonce_digest", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("handoff_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("binding_effective_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_effective_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("lifecycle_attestation_payload", postgresql.JSONB(), nullable=False),
        sa.Column("acceptance_attestation_payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("state = 'started'", name="ck_wf_tctx_handoff_attempt_state"),
        sa.CheckConstraint(
            "started_at < handoff_deadline AND handoff_deadline <= lease_valid_until "
            "AND handoff_deadline <= binding_effective_until "
            "AND handoff_deadline <= source_effective_until "
            "AND handoff_deadline <= lifecycle_attestation_valid_until "
            "AND handoff_deadline <= acceptance_attestation_valid_until",
            name="ck_wf_tctx_handoff_attempt_deadline",
        ),
        sa.CheckConstraint(
            "destination_generation >= 1 "
            "AND adapter_contract_id = "
            "'contract.workflow-protected-target-context-capsule-sealed-handoff' "
            "AND adapter_contract_version = '1.0' "
            "AND approved_adapter_id = "
            "'adapter.workflow-protected-target-context-capsule-sealed-handoff' "
            "AND approved_adapter_version = '1.0'",
            name="ck_wf_tctx_handoff_attempt_profile",
        ),
        sa.CheckConstraint(_zero_authority_check(), name="ck_wf_tctx_handoff_attempt_authority"),
        sa.ForeignKeyConstraint(
            ["consumption_claim_id"],
            [f"{CLAIM_TABLE}.claim_id"],
            name="fk_wf_tctx_handoff_attempt_claim",
        ),
        sa.PrimaryKeyConstraint("attempt_id"),
        sa.UniqueConstraint("consumption_claim_id", name="uq_wf_tctx_handoff_attempt_claim"),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_tctx_handoff_attempt_lease"),
        sa.UniqueConstraint("handoff_id", name="uq_wf_tctx_handoff_attempt_handoff"),
        sa.UniqueConstraint(
            "handoff_id",
            "attempt_id",
            "consumption_claim_id",
            name="uq_wf_tctx_handoff_attempt_lineage",
        ),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_tctx_handoff_attempt_digest"),
    )
    op.create_index(
        "ix_wf_tctx_handoff_attempt_scope",
        ATTEMPT_TABLE,
        ["organization_id", "environment_id", "site_id"],
    )
    op.create_index("ix_wf_tctx_handoff_attempt_started", ATTEMPT_TABLE, ["started_at"])

    op.create_table(
        RESULT_TABLE,
        sa.Column("handoff_id", sa.String(length=128), nullable=False),
        sa.Column("attempt_id", sa.String(length=128), nullable=False),
        sa.Column("attempt_digest", sa.String(length=64), nullable=False),
        sa.Column("consumption_claim_id", sa.String(length=128), nullable=False),
        sa.Column("consumption_claim_digest", sa.String(length=64), nullable=False),
        sa.Column("authorization_lease_id", sa.String(length=128), nullable=False),
        sa.Column("authorization_lease_digest", sa.String(length=64), nullable=False),
        sa.Column("consumer_binding_id", sa.String(length=128), nullable=False),
        sa.Column("consumer_binding_digest", sa.String(length=64), nullable=False),
        *_scope_columns(),
        sa.Column("consumer_contract_id", sa.String(length=128), nullable=False),
        sa.Column("consumer_contract_version", sa.String(length=64), nullable=False),
        sa.Column("purpose_id", sa.String(length=128), nullable=False),
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("policy_digest", sa.String(length=64), nullable=False),
        sa.Column("adapter_contract_id", sa.String(length=128), nullable=False),
        sa.Column("adapter_contract_version", sa.String(length=64), nullable=False),
        sa.Column("receipt_digest", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("failure_class", sa.String(length=64), nullable=True),
        sa.Column("consumer_receipt_id", sa.String(length=128), nullable=True),
        sa.Column("consumer_receipt_is_bearer_capability", sa.Boolean(), nullable=False),
        sa.Column("sealed_capsule_handed_off", sa.Boolean(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usable_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_cleanup_confirmed", sa.Boolean(), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("receipt_payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "(state = 'handed_off_sealed' AND failure_class IS NULL "
            "AND consumer_receipt_id IS NOT NULL AND sealed_capsule_handed_off "
            "AND usable_until IS NOT NULL AND completed_at < usable_until) OR "
            "(state = 'handoff_failed' AND failure_class IS NOT NULL "
            "AND consumer_receipt_id IS NULL AND NOT sealed_capsule_handed_off "
            "AND usable_until IS NULL AND source_cleanup_confirmed)",
            name="ck_wf_tctx_handoff_result_state",
        ),
        sa.CheckConstraint(
            "NOT consumer_receipt_is_bearer_capability",
            name="ck_wf_tctx_handoff_result_non_bearer",
        ),
        sa.CheckConstraint(_zero_authority_check(), name="ck_wf_tctx_handoff_result_authority"),
        sa.ForeignKeyConstraint(
            ["handoff_id", "attempt_id", "consumption_claim_id"],
            [
                f"{ATTEMPT_TABLE}.handoff_id",
                f"{ATTEMPT_TABLE}.attempt_id",
                f"{ATTEMPT_TABLE}.consumption_claim_id",
            ],
            name="fk_wf_tctx_handoff_result_attempt_lineage",
        ),
        sa.ForeignKeyConstraint(
            ["consumption_claim_id"],
            [f"{CLAIM_TABLE}.claim_id"],
            name="fk_wf_tctx_handoff_result_claim",
        ),
        sa.PrimaryKeyConstraint("handoff_id"),
        sa.UniqueConstraint("attempt_id", name="uq_wf_tctx_handoff_result_attempt"),
        sa.UniqueConstraint("consumption_claim_id", name="uq_wf_tctx_handoff_result_claim"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_tctx_handoff_result_digest"),
    )
    op.create_index(
        "ix_wf_tctx_handoff_result_scope",
        RESULT_TABLE,
        ["organization_id", "environment_id", "site_id"],
    )
    op.create_index("ix_wf_tctx_handoff_result_completed", RESULT_TABLE, ["completed_at"])

    op.execute(
        sa.text(
            f"""
            CREATE FUNCTION {APPEND_ONLY_FUNCTION}()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION
                    'workflow target-context capsule handoff evidence is append-only'
                    USING ERRCODE = '55000';
            END;
            $$
            """
        )
    )
    for table, trigger in (
        (CLAIM_TABLE, "trg_wf_tctx_handoff_consume_append_only"),
        (ATTEMPT_TABLE, "trg_wf_tctx_handoff_attempt_append_only"),
        (RESULT_TABLE, "trg_wf_tctx_handoff_result_append_only"),
    ):
        op.execute(
            sa.text(
                f"CREATE TRIGGER {trigger} BEFORE UPDATE OR DELETE ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION {APPEND_ONLY_FUNCTION}()"
            )
        )


DOWNGRADE_EMPTY_GUARD_SQL = f"""
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM {RESULT_TABLE} LIMIT 1)
       OR EXISTS (SELECT 1 FROM {ATTEMPT_TABLE} LIMIT 1)
       OR EXISTS (SELECT 1 FROM {CLAIM_TABLE} LIMIT 1) THEN
        RAISE EXCEPTION
            'refusing to downgrade target-context capsule handoff schema: '
            'append-only tables contain evidence'
            USING ERRCODE = '55000';
    END IF;
END
$$;
"""


def downgrade() -> None:
    op.execute(DOWNGRADE_EMPTY_GUARD_SQL)
    op.drop_table(RESULT_TABLE)
    op.drop_table(ATTEMPT_TABLE)
    op.drop_table(CLAIM_TABLE)
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {APPEND_ONLY_FUNCTION}()"))
