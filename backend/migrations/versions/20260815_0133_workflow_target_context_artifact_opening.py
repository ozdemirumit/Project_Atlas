"""Add immutable target-context artifact opening evidence.

Revision ID: 20260815_0133
Revises: 20260815_0132
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260815_0133"
down_revision: str | None = "20260815_0132"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEASE_TABLE = "workflow_event_tctx_access_authorization_leases"
BINDING_TABLE = "workflow_event_transport_target_context_bindings"
ENDPOINT_TABLE = "workflow_event_endpoint_materialization_results"
CREDENTIAL_TABLE = "workflow_event_credential_materialization_results"
CLAIM_TABLE = "workflow_event_tctx_access_consumption_claims"
ATTEMPT_TABLE = "workflow_event_tctx_artifact_opening_attempts"
RESULT_TABLE = "workflow_event_tctx_artifact_opening_results"
DOWNGRADE_EMPTY_GUARD_SQL = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM workflow_event_tctx_artifact_opening_results LIMIT 1
    ) OR EXISTS (
        SELECT 1 FROM workflow_event_tctx_artifact_opening_attempts LIMIT 1
    ) OR EXISTS (
        SELECT 1 FROM workflow_event_tctx_access_consumption_claims LIMIT 1
    ) THEN
        RAISE EXCEPTION
            'refusing to downgrade target-context artifact opening audit schema: '
            'append-only tables contain evidence'
            USING ERRCODE = '55000';
    END IF;
END;
$$
"""


def upgrade() -> None:
    op.create_table(
        CLAIM_TABLE,
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("idempotency_digest", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("authorization_lease_id", sa.String(length=128), nullable=False),
        sa.Column("authorization_lease_digest", sa.String(length=64), nullable=False),
        sa.Column("target_context_binding_id", sa.String(length=128), nullable=False),
        sa.Column("target_context_binding_digest", sa.String(length=64), nullable=False),
        sa.Column("target_context_commitment", sa.String(length=64), nullable=False),
        sa.Column("attempt_id", sa.String(length=128), nullable=False),
        sa.Column("opening_id", sa.String(length=128), nullable=False),
        sa.Column("authorization_evidence_digest", sa.String(length=64), nullable=False),
        sa.Column("consumption_authorization_audit_digest", sa.String(length=64), nullable=False),
        *_scope_columns(),
        sa.Column("accessor_subject_id", sa.String(length=240), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("authorization_evidence_payload", postgresql.JSONB(), nullable=False),
        sa.Column("consumption_authorization_audit_payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(_zero_authority_check(), name="ck_wf_tctx_open_claim_authority"),
        sa.CheckConstraint(
            "char_length(consumption_authorization_audit_digest) = 64 "
            "AND consumption_authorization_audit_digest ~ '^[0-9a-f]{64}$' "
            "AND jsonb_typeof(consumption_authorization_audit_payload) = 'object' "
            "AND consumption_authorization_audit_payload <> '{}'::jsonb",
            name="ck_wf_tctx_open_claim_audit_digest",
        ),
        sa.ForeignKeyConstraint(
            ["authorization_lease_id"],
            [f"{LEASE_TABLE}.authorization_lease_id"],
            name="fk_wf_tctx_open_claim_lease",
        ),
        sa.ForeignKeyConstraint(
            ["target_context_binding_id"],
            [f"{BINDING_TABLE}.binding_id"],
            name="fk_wf_tctx_open_claim_binding",
        ),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "idempotency_scope_id", "idempotency_key", name="uq_wf_tctx_open_claim_idem"
        ),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_tctx_open_claim_lease"),
        sa.UniqueConstraint("attempt_id", name="uq_wf_tctx_open_claim_attempt"),
        sa.UniqueConstraint("opening_id", name="uq_wf_tctx_open_claim_opening"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_tctx_open_claim_digest"),
        sa.UniqueConstraint(
            "claim_id",
            "authorization_lease_id",
            "attempt_id",
            "opening_id",
            "target_context_binding_id",
            "organization_id",
            "environment_id",
            "site_id",
            name="uq_wf_tctx_open_claim_lineage",
        ),
    )
    _create_indexes(
        CLAIM_TABLE,
        {
            "idempotency_scope_id": "ix_wf_tctx_open_claim_scope",
            "authorization_lease_id": "ix_wf_tctx_open_claim_lease",
            "target_context_binding_id": "ix_wf_tctx_open_claim_binding",
            "accessor_subject_id": "ix_wf_tctx_open_claim_subject",
            "claimed_at": "ix_wf_tctx_open_claim_time",
        },
    )

    op.create_table(
        ATTEMPT_TABLE,
        sa.Column("attempt_id", sa.String(length=128), nullable=False),
        sa.Column("opening_id", sa.String(length=128), nullable=False),
        sa.Column("consumption_claim_id", sa.String(length=128), nullable=False),
        sa.Column("authorization_lease_id", sa.String(length=128), nullable=False),
        sa.Column("authorization_lease_digest", sa.String(length=64), nullable=False),
        sa.Column("target_context_binding_id", sa.String(length=128), nullable=False),
        sa.Column("target_context_binding_digest", sa.String(length=64), nullable=False),
        sa.Column("target_context_commitment", sa.String(length=64), nullable=False),
        sa.Column("endpoint_materialization_id", sa.String(length=128), nullable=False),
        sa.Column("endpoint_materialization_digest", sa.String(length=64), nullable=False),
        sa.Column("endpoint_protected_artifact_id", sa.String(length=128), nullable=False),
        sa.Column("endpoint_protected_artifact_digest", sa.String(length=64), nullable=False),
        sa.Column("endpoint_status_attestation_id", sa.String(length=128), nullable=False),
        sa.Column("endpoint_status_attestation_digest", sa.String(length=64), nullable=False),
        sa.Column("credential_materialization_id", sa.String(length=128), nullable=False),
        sa.Column("credential_materialization_digest", sa.String(length=64), nullable=False),
        sa.Column("credential_protected_artifact_id", sa.String(length=128), nullable=False),
        sa.Column("credential_protected_artifact_digest", sa.String(length=64), nullable=False),
        sa.Column("credential_status_attestation_id", sa.String(length=128), nullable=False),
        sa.Column("credential_status_attestation_digest", sa.String(length=64), nullable=False),
        sa.Column("request_nonce_digest", sa.String(length=64), nullable=False),
        sa.Column("opener_contract_id", sa.String(length=128), nullable=False),
        sa.Column("opener_attestor_id", sa.String(length=128), nullable=False),
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("policy_digest", sa.String(length=64), nullable=False),
        *_scope_columns(),
        sa.Column("accessor_subject_id", sa.String(length=240), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("joint_usable_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("endpoint_attestation_payload", postgresql.JSONB(), nullable=False),
        sa.Column("credential_attestation_payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("state = 'opening_started'", name="ck_wf_tctx_open_attempt_state"),
        sa.CheckConstraint(
            "started_at < lease_valid_until "
            "AND started_at < joint_usable_until "
            "AND started_at < evidence_valid_until",
            name="ck_wf_tctx_open_attempt_window",
        ),
        sa.CheckConstraint(_zero_authority_check(), name="ck_wf_tctx_open_attempt_authority"),
        sa.ForeignKeyConstraint(
            ["consumption_claim_id"],
            [f"{CLAIM_TABLE}.claim_id"],
            name="fk_wf_tctx_open_attempt_claim",
        ),
        sa.ForeignKeyConstraint(
            ["authorization_lease_id"],
            [f"{LEASE_TABLE}.authorization_lease_id"],
            name="fk_wf_tctx_open_attempt_lease",
        ),
        sa.ForeignKeyConstraint(
            ["target_context_binding_id"],
            [f"{BINDING_TABLE}.binding_id"],
            name="fk_wf_tctx_open_attempt_binding",
        ),
        sa.ForeignKeyConstraint(
            ["endpoint_materialization_id"],
            [f"{ENDPOINT_TABLE}.materialization_id"],
            name="fk_wf_tctx_open_attempt_endpoint",
        ),
        sa.ForeignKeyConstraint(
            ["credential_materialization_id"],
            [f"{CREDENTIAL_TABLE}.materialization_id"],
            name="fk_wf_tctx_open_attempt_credential",
        ),
        sa.ForeignKeyConstraint(
            [
                "consumption_claim_id",
                "authorization_lease_id",
                "attempt_id",
                "opening_id",
                "target_context_binding_id",
                "organization_id",
                "environment_id",
                "site_id",
            ],
            [
                f"{CLAIM_TABLE}.claim_id",
                f"{CLAIM_TABLE}.authorization_lease_id",
                f"{CLAIM_TABLE}.attempt_id",
                f"{CLAIM_TABLE}.opening_id",
                f"{CLAIM_TABLE}.target_context_binding_id",
                f"{CLAIM_TABLE}.organization_id",
                f"{CLAIM_TABLE}.environment_id",
                f"{CLAIM_TABLE}.site_id",
            ],
            name="fk_wf_tctx_open_attempt_claim_lineage",
        ),
        sa.PrimaryKeyConstraint("attempt_id"),
        sa.UniqueConstraint("opening_id", name="uq_wf_tctx_open_attempt_opening"),
        sa.UniqueConstraint("consumption_claim_id", name="uq_wf_tctx_open_attempt_claim"),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_tctx_open_attempt_lease"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_tctx_open_attempt_digest"),
        sa.UniqueConstraint(
            "attempt_id",
            "consumption_claim_id",
            "authorization_lease_id",
            "opening_id",
            "target_context_binding_id",
            "organization_id",
            "environment_id",
            "site_id",
            name="uq_wf_tctx_open_attempt_lineage",
        ),
    )
    _create_indexes(
        ATTEMPT_TABLE,
        {
            "organization_id": "ix_wf_tctx_open_attempt_org",
            "environment_id": "ix_wf_tctx_open_attempt_env",
            "site_id": "ix_wf_tctx_open_attempt_site",
            "target_context_binding_id": "ix_wf_tctx_open_attempt_binding",
            "accessor_subject_id": "ix_wf_tctx_open_attempt_subject",
            "started_at": "ix_wf_tctx_open_attempt_started",
        },
    )

    op.create_table(
        RESULT_TABLE,
        sa.Column("opening_id", sa.String(length=128), nullable=False),
        sa.Column("attempt_id", sa.String(length=128), nullable=False),
        sa.Column("attempt_digest", sa.String(length=64), nullable=False),
        sa.Column("consumption_claim_id", sa.String(length=128), nullable=False),
        sa.Column("consumption_claim_digest", sa.String(length=64), nullable=False),
        sa.Column("authorization_lease_id", sa.String(length=128), nullable=False),
        sa.Column("authorization_lease_digest", sa.String(length=64), nullable=False),
        sa.Column("target_context_binding_id", sa.String(length=128), nullable=False),
        sa.Column("target_context_binding_digest", sa.String(length=64), nullable=False),
        sa.Column("target_context_commitment", sa.String(length=64), nullable=False),
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("policy_digest", sa.String(length=64), nullable=False),
        sa.Column("opener_id", sa.String(length=128), nullable=False),
        sa.Column("opener_version", sa.String(length=64), nullable=False),
        sa.Column("opening_receipt_digest", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("failure_class", sa.String(length=64), nullable=True),
        sa.Column("sealed_capsule_id", sa.String(length=128), nullable=True),
        sa.Column("sealed_capsule_digest", sa.String(length=64), nullable=True),
        sa.Column("capsule_is_bearer_capability", sa.Boolean(), nullable=False),
        sa.Column("capsule_schema_id", sa.String(length=128), nullable=False),
        sa.Column("capsule_schema_version", sa.String(length=64), nullable=False),
        *_scope_columns(),
        sa.Column("accessor_subject_id", sa.String(length=240), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usable_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("protected_sources_closed", sa.Boolean(), nullable=False),
        sa.Column("cleanup_confirmed", sa.Boolean(), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "(state = 'opened_protected' AND failure_class IS NULL "
            "AND sealed_capsule_id IS NOT NULL AND sealed_capsule_digest IS NOT NULL "
            "AND usable_until IS NOT NULL AND completed_at < usable_until) OR "
            "(state = 'opening_failed' AND failure_class IS NOT NULL "
            "AND sealed_capsule_id IS NULL AND sealed_capsule_digest IS NULL "
            "AND usable_until IS NULL)",
            name="ck_wf_tctx_open_result_state",
        ),
        sa.CheckConstraint(
            "NOT capsule_is_bearer_capability AND protected_sources_closed AND cleanup_confirmed",
            name="ck_wf_tctx_open_result_capsule",
        ),
        sa.CheckConstraint(_zero_authority_check(), name="ck_wf_tctx_open_result_authority"),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            [f"{ATTEMPT_TABLE}.attempt_id"],
            name="fk_wf_tctx_open_result_attempt",
        ),
        sa.ForeignKeyConstraint(
            ["consumption_claim_id"],
            [f"{CLAIM_TABLE}.claim_id"],
            name="fk_wf_tctx_open_result_claim",
        ),
        sa.ForeignKeyConstraint(
            ["authorization_lease_id"],
            [f"{LEASE_TABLE}.authorization_lease_id"],
            name="fk_wf_tctx_open_result_lease",
        ),
        sa.ForeignKeyConstraint(
            ["target_context_binding_id"],
            [f"{BINDING_TABLE}.binding_id"],
            name="fk_wf_tctx_open_result_binding",
        ),
        sa.ForeignKeyConstraint(
            [
                "attempt_id",
                "consumption_claim_id",
                "authorization_lease_id",
                "opening_id",
                "target_context_binding_id",
                "organization_id",
                "environment_id",
                "site_id",
            ],
            [
                f"{ATTEMPT_TABLE}.attempt_id",
                f"{ATTEMPT_TABLE}.consumption_claim_id",
                f"{ATTEMPT_TABLE}.authorization_lease_id",
                f"{ATTEMPT_TABLE}.opening_id",
                f"{ATTEMPT_TABLE}.target_context_binding_id",
                f"{ATTEMPT_TABLE}.organization_id",
                f"{ATTEMPT_TABLE}.environment_id",
                f"{ATTEMPT_TABLE}.site_id",
            ],
            name="fk_wf_tctx_open_result_attempt_lineage",
        ),
        sa.PrimaryKeyConstraint("opening_id"),
        sa.UniqueConstraint("attempt_id", name="uq_wf_tctx_open_result_attempt"),
        sa.UniqueConstraint("consumption_claim_id", name="uq_wf_tctx_open_result_claim"),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_tctx_open_result_lease"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_tctx_open_result_digest"),
    )
    _create_indexes(
        RESULT_TABLE,
        {
            "organization_id": "ix_wf_tctx_open_result_org",
            "environment_id": "ix_wf_tctx_open_result_env",
            "site_id": "ix_wf_tctx_open_result_site",
            "target_context_binding_id": "ix_wf_tctx_open_result_binding",
            "accessor_subject_id": "ix_wf_tctx_open_result_subject",
            "completed_at": "ix_wf_tctx_open_result_completed",
            "state": "ix_wf_tctx_open_result_state",
        },
    )

    op.execute(
        """
        CREATE FUNCTION reject_wf_tctx_artifact_opening_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'workflow target-context artifact opening evidence is append-only'
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
            EXECUTE FUNCTION reject_wf_tctx_artifact_opening_mutation()
            """
        )


def downgrade() -> None:
    op.execute(DOWNGRADE_EMPTY_GUARD_SQL)
    for table_name, trigger_name in _triggers().items():
        op.execute(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name}")
    op.execute("DROP FUNCTION IF EXISTS reject_wf_tctx_artifact_opening_mutation()")
    op.drop_table(RESULT_TABLE)
    op.drop_table(ATTEMPT_TABLE)
    op.drop_table(CLAIM_TABLE)


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


def _create_indexes(table_name: str, indexes: dict[str, str]) -> None:
    for column, name in indexes.items():
        op.create_index(name, table_name, [column])


def _triggers() -> dict[str, str]:
    return {
        CLAIM_TABLE: "trg_wf_tctx_open_claims_append_only",
        ATTEMPT_TABLE: "trg_wf_tctx_open_attempts_append_only",
        RESULT_TABLE: "trg_wf_tctx_open_results_append_only",
    }
