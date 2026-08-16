"""Add bounded target-context capsule opening authorization leases.

Revision ID: 20260816_0137
Revises: 20260816_0136
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260816_0137"
down_revision: str | None = "20260816_0136"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEASE_TABLE = "workflow_event_tctx_capsule_opening_authorization_leases"
CLAIM_TABLE = "workflow_event_tctx_capsule_opening_authorization_claims"
HANDOFF_RESULT_TABLE = "workflow_event_tctx_capsule_handoff_results"
HANDOFF_ATTEMPT_TABLE = "workflow_event_tctx_capsule_handoff_attempts"
HANDOFF_CLAIM_TABLE = "workflow_event_tctx_capsule_handoff_consumption_claims"
HANDOFF_LEASE_TABLE = "workflow_event_tctx_capsule_handoff_authorization_leases"
BINDING_TABLE = "workflow_event_tctx_capsule_consumer_bindings"
APPEND_ONLY_FUNCTION = "reject_wf_tctx_capsule_opening_auth_mutation"


def _scope_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("environment_id", sa.String(128), nullable=False),
        sa.Column("site_id", sa.String(128), nullable=False),
    )


def _authority_columns() -> tuple[sa.Column[object], ...]:
    return tuple(
        sa.Column(name, sa.Boolean(), nullable=False)
        for name in (
            "target_context_capsule_opening_authority_granted",
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


def _authority_check() -> str:
    return "target_context_capsule_opening_authority_granted AND " + " AND ".join(
        f"NOT {column.name}"
        for column in _authority_columns()
        if column.name != "target_context_capsule_opening_authority_granted"
    )


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_wf_tctx_handoff_result_lineage",
        HANDOFF_RESULT_TABLE,
        ["handoff_id", "attempt_id", "consumption_claim_id"],
    )
    op.create_unique_constraint(
        "uq_wf_tctx_handoff_result_open_auth_lineage",
        HANDOFF_RESULT_TABLE,
        [
            "handoff_id",
            "canonical_digest",
            "attempt_id",
            "attempt_digest",
            "consumption_claim_id",
            "consumption_claim_digest",
            "authorization_lease_id",
            "authorization_lease_digest",
            "consumer_binding_id",
            "consumer_binding_digest",
            "consumer_receipt_id",
            "receipt_digest",
        ],
    )
    op.create_unique_constraint(
        "uq_wf_tctx_handoff_attempt_open_auth_lineage",
        HANDOFF_ATTEMPT_TABLE,
        ["attempt_id", "canonical_digest", "sealed_capsule_id", "sealed_capsule_digest"],
    )
    op.create_table(
        LEASE_TABLE,
        sa.Column("authorization_lease_id", sa.String(128), primary_key=True),
        sa.Column("handoff_id", sa.String(128), nullable=False),
        sa.Column("handoff_result_digest", sa.String(64), nullable=False),
        sa.Column("attempt_id", sa.String(128), nullable=False),
        sa.Column("attempt_digest", sa.String(64), nullable=False),
        sa.Column("consumption_claim_id", sa.String(128), nullable=False),
        sa.Column("consumption_claim_digest", sa.String(64), nullable=False),
        sa.Column("upstream_authorization_lease_id", sa.String(128), nullable=False),
        sa.Column("upstream_authorization_lease_digest", sa.String(64), nullable=False),
        sa.Column("consumer_binding_id", sa.String(128), nullable=False),
        sa.Column("consumer_binding_digest", sa.String(64), nullable=False),
        sa.Column("sealed_capsule_id", sa.String(128), nullable=False),
        sa.Column("sealed_capsule_digest", sa.String(64), nullable=False),
        sa.Column("consumer_receipt_id", sa.String(128), nullable=False),
        sa.Column("receipt_digest", sa.String(64), nullable=False),
        sa.Column("destination_boundary_id", sa.String(128), nullable=False),
        sa.Column("destination_deployment_id", sa.String(128), nullable=False),
        sa.Column("destination_generation", sa.Integer(), nullable=False),
        sa.Column("destination_fencing_token_digest", sa.String(64), nullable=False),
        sa.Column("custody_contract_id", sa.String(128), nullable=False),
        sa.Column("custody_contract_version", sa.String(64), nullable=False),
        sa.Column("approved_adapter_id", sa.String(128), nullable=False),
        sa.Column("approved_adapter_version", sa.String(64), nullable=False),
        sa.Column("verification_signing_key_id", sa.String(128), nullable=False),
        sa.Column("trusted_profile_digest", sa.String(64), nullable=False),
        sa.Column("custody_attestation_id", sa.String(128), nullable=False),
        sa.Column("custody_attestation_digest", sa.String(64), nullable=False),
        sa.Column("custody_attestation_valid_until", sa.DateTime(timezone=True), nullable=False),
        *_scope_columns(),
        sa.Column("consumer_subject_id", sa.String(240), nullable=False),
        sa.Column("consumer_audience", sa.String(240), nullable=False),
        sa.Column("consumer_contract_id", sa.String(128), nullable=False),
        sa.Column("consumer_contract_version", sa.String(64), nullable=False),
        sa.Column("purpose_id", sa.String(128), nullable=False),
        sa.Column("policy_id", sa.String(128), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("policy_digest", sa.String(64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("single_use", sa.Boolean(), nullable=False),
        sa.Column("renewable", sa.Boolean(), nullable=False),
        sa.Column("transferable", sa.Boolean(), nullable=False),
        sa.Column("lease_is_bearer_capability", sa.Boolean(), nullable=False),
        sa.Column("state", sa.String(32), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("custody_attestation_payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "policy_id = 'policy.workflow-protected-transport-target-context-capsule-"
            "opening-authorization' "
            "AND policy_version = '1.0' "
            "AND consumer_subject_id = "
            "'service.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_audience = "
            "'audience.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_contract_id = "
            "'contract.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_contract_version = '1.0' "
            "AND purpose_id = "
            "'purpose.workflow-protected-transport-target-context-capsule-opening-evaluation' "
            "AND destination_boundary_id = "
            "'boundary.workflow-protected-target-context-capsule-consumer' "
            "AND destination_deployment_id = "
            "'deployment.workflow-protected-target-context-capsule-consumer' "
            "AND destination_generation = 1 "
            "AND destination_fencing_token_digest = "
            "'701153578261c45c3f1faa89f75b4a3f7003126683ddb895c0346aac0f9148e7' "
            "AND custody_contract_id = "
            "'contract.workflow-protected-target-context-capsule-custody' "
            "AND custody_contract_version = '1.0' "
            "AND approved_adapter_id = "
            "'adapter.workflow-protected-target-context-capsule-sealed-handoff' "
            "AND approved_adapter_version = '1.0' "
            "AND verification_signing_key_id = "
            "'key.workflow-protected-target-context-capsule-handoff-receipt.v1' "
            "AND trusted_profile_digest = "
            "'7f4c97bcac8852cb9bee577f15103a51dbbee4180ba9bff980d54bc6e691ff78' "
            "AND state = 'authorized_unconsumed'",
            name="ck_wf_tctx_capsule_open_auth_contract",
        ),
        sa.CheckConstraint(
            "valid_until = issued_at + interval '1 second' AND issued_at < valid_until "
            "AND valid_until <= effective_until AND valid_until <= custody_attestation_valid_until",
            name="ck_wf_tctx_capsule_open_auth_window",
        ),
        sa.CheckConstraint(
            "single_use AND NOT renewable AND NOT transferable AND NOT lease_is_bearer_capability",
            name="ck_wf_tctx_capsule_open_auth_flags",
        ),
        sa.CheckConstraint(_authority_check(), name="ck_wf_tctx_capsule_open_auth_authority"),
        sa.ForeignKeyConstraint(
            [
                "handoff_id",
                "handoff_result_digest",
                "attempt_id",
                "attempt_digest",
                "consumption_claim_id",
                "consumption_claim_digest",
                "upstream_authorization_lease_id",
                "upstream_authorization_lease_digest",
                "consumer_binding_id",
                "consumer_binding_digest",
                "consumer_receipt_id",
                "receipt_digest",
            ],
            [
                f"{HANDOFF_RESULT_TABLE}.handoff_id",
                f"{HANDOFF_RESULT_TABLE}.canonical_digest",
                f"{HANDOFF_RESULT_TABLE}.attempt_id",
                f"{HANDOFF_RESULT_TABLE}.attempt_digest",
                f"{HANDOFF_RESULT_TABLE}.consumption_claim_id",
                f"{HANDOFF_RESULT_TABLE}.consumption_claim_digest",
                f"{HANDOFF_RESULT_TABLE}.authorization_lease_id",
                f"{HANDOFF_RESULT_TABLE}.authorization_lease_digest",
                f"{HANDOFF_RESULT_TABLE}.consumer_binding_id",
                f"{HANDOFF_RESULT_TABLE}.consumer_binding_digest",
                f"{HANDOFF_RESULT_TABLE}.consumer_receipt_id",
                f"{HANDOFF_RESULT_TABLE}.receipt_digest",
            ],
            name="fk_wf_tctx_open_auth_result_lineage",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id", "attempt_digest", "sealed_capsule_id", "sealed_capsule_digest"],
            [
                f"{HANDOFF_ATTEMPT_TABLE}.attempt_id",
                f"{HANDOFF_ATTEMPT_TABLE}.canonical_digest",
                f"{HANDOFF_ATTEMPT_TABLE}.sealed_capsule_id",
                f"{HANDOFF_ATTEMPT_TABLE}.sealed_capsule_digest",
            ],
            name="fk_wf_tctx_open_auth_attempt_lineage",
        ),
        sa.ForeignKeyConstraint(
            ["consumption_claim_id"],
            [f"{HANDOFF_CLAIM_TABLE}.claim_id"],
            name="fk_wf_tctx_open_auth_claim",
        ),
        sa.ForeignKeyConstraint(
            ["upstream_authorization_lease_id"],
            [f"{HANDOFF_LEASE_TABLE}.authorization_lease_id"],
            name="fk_wf_tctx_open_auth_upstream_lease",
        ),
        sa.ForeignKeyConstraint(
            ["consumer_binding_id"],
            [f"{BINDING_TABLE}.binding_id"],
            name="fk_wf_tctx_open_auth_binding",
        ),
        sa.UniqueConstraint("handoff_id", name="uq_wf_tctx_open_auth_result"),
        sa.UniqueConstraint("consumer_receipt_id", name="uq_wf_tctx_open_auth_receipt"),
        sa.UniqueConstraint("sealed_capsule_id", name="uq_wf_tctx_open_auth_capsule"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_tctx_open_auth_digest"),
        sa.UniqueConstraint(
            "authorization_lease_id",
            "handoff_id",
            "consumer_receipt_id",
            "sealed_capsule_id",
            name="uq_wf_tctx_open_auth_claim_lineage",
        ),
    )
    op.create_index(
        "ix_wf_tctx_open_auth_scope",
        LEASE_TABLE,
        ["organization_id", "environment_id", "site_id", "issued_at"],
    )
    op.create_table(
        CLAIM_TABLE,
        sa.Column("claim_id", sa.String(128), primary_key=True),
        sa.Column("authorization_lease_id", sa.String(128), nullable=False),
        sa.Column("handoff_id", sa.String(128), nullable=False),
        sa.Column("consumer_receipt_id", sa.String(128), nullable=False),
        sa.Column("sealed_capsule_id", sa.String(128), nullable=False),
        *_scope_columns(),
        sa.Column("consumer_subject_id", sa.String(240), nullable=False),
        sa.Column("consumer_audience", sa.String(240), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("authorization_audit_digest", sa.String(64), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("authorization_audit_payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["authorization_lease_id", "handoff_id", "consumer_receipt_id", "sealed_capsule_id"],
            [
                f"{LEASE_TABLE}.authorization_lease_id",
                f"{LEASE_TABLE}.handoff_id",
                f"{LEASE_TABLE}.consumer_receipt_id",
                f"{LEASE_TABLE}.sealed_capsule_id",
            ],
            name="fk_wf_tctx_open_auth_claim_lease",
        ),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_tctx_open_auth_claim_lease"),
        sa.UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_tctx_open_auth_scope_idem",
        ),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_tctx_open_auth_claim_digest"),
    )
    op.execute(
        sa.text(
            f"""
            CREATE FUNCTION {APPEND_ONLY_FUNCTION}()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'capsule opening authorization evidence is append-only'
                    USING ERRCODE = '55000';
            END;
            $$
            """
        )
    )
    for table, trigger in (
        (LEASE_TABLE, "trg_wf_tctx_open_auth_lease_append_only"),
        (CLAIM_TABLE, "trg_wf_tctx_open_auth_claim_append_only"),
    ):
        op.execute(
            sa.text(
                f"CREATE TRIGGER {trigger} BEFORE UPDATE OR DELETE ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION {APPEND_ONLY_FUNCTION}()"
            )
        )


def downgrade() -> None:
    op.execute(
        sa.text(
            f"""
            DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM {LEASE_TABLE} LIMIT 1)
                   OR EXISTS (SELECT 1 FROM {CLAIM_TABLE} LIMIT 1) THEN
                    RAISE EXCEPTION
                        'refusing guarded downgrade: opening authorization evidence exists'
                        USING ERRCODE = '55000';
                END IF;
            END $$;
            """
        )
    )
    op.drop_table(CLAIM_TABLE)
    op.drop_table(LEASE_TABLE)
    op.drop_constraint(
        "uq_wf_tctx_handoff_attempt_open_auth_lineage", HANDOFF_ATTEMPT_TABLE, type_="unique"
    )
    op.drop_constraint(
        "uq_wf_tctx_handoff_result_open_auth_lineage", HANDOFF_RESULT_TABLE, type_="unique"
    )
    op.drop_constraint("uq_wf_tctx_handoff_result_lineage", HANDOFF_RESULT_TABLE, type_="unique")
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {APPEND_ONLY_FUNCTION}()"))
