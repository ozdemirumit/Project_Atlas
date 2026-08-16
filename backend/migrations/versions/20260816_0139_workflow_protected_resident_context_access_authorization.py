"""Add bounded protected resident-context access authorization leases.

Revision ID: 20260816_0139
Revises: 20260816_0138
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260816_0139"
down_revision: str | None = "20260816_0138"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEASE_TABLE = "workflow_event_resident_context_access_auth_leases"
CLAIM_TABLE = "workflow_event_resident_context_access_auth_claims"
OPENING_RESULT_TABLE = "workflow_event_tctx_capsule_opening_results"
OPENING_ATTEMPT_TABLE = "workflow_event_tctx_capsule_opening_attempts"
OPENING_CLAIM_TABLE = "workflow_event_tctx_capsule_opening_consumption_claims"
APPEND_ONLY_FUNCTION = "reject_wf_rc_access_auth_mutation"


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
            "protected_resident_context_access_authority_granted",
            "target_context_capsule_handoff_authority_granted",
            "target_context_capsule_opening_authority_granted",
            "endpoint_resolution_authority_granted",
            "route_selection_authority_granted",
            "route_binding_authority_granted",
            "credential_selection_authority_granted",
            "credential_assignment_binding_authority_granted",
            "credential_access_authority_granted",
            "credential_brokerage_authority_granted",
            "credential_resolution_authority_granted",
            "protected_artifact_access_authority_granted",
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


def _lease_authority_check() -> str:
    return "protected_resident_context_access_authority_granted AND " + " AND ".join(
        f"NOT {column.name}"
        for column in _authority_columns()
        if column.name != "protected_resident_context_access_authority_granted"
    )


def _claim_authority_check() -> str:
    return " AND ".join(f"NOT {column.name}" for column in _authority_columns())


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_wf_tctx_caps_open_claim_access_auth_lineage",
        OPENING_CLAIM_TABLE,
        ["claim_id", "canonical_digest", "opening_id", "attempt_id"],
    )
    op.create_unique_constraint(
        "uq_wf_tctx_caps_open_attempt_access_auth_lineage",
        OPENING_ATTEMPT_TABLE,
        [
            "attempt_id",
            "canonical_digest",
            "opening_id",
            "consumption_claim_id",
            "consumption_claim_digest",
        ],
    )
    op.create_unique_constraint(
        "uq_wf_tctx_caps_open_result_access_auth_lineage",
        OPENING_RESULT_TABLE,
        [
            "opening_id",
            "canonical_digest",
            "attempt_id",
            "attempt_digest",
            "consumption_claim_id",
            "consumption_claim_digest",
            "authorization_lease_id",
            "authorization_lease_digest",
            "protected_resident_context_id",
            "protected_resident_context_digest",
            "opening_receipt_digest",
        ],
    )

    op.create_table(
        LEASE_TABLE,
        sa.Column("access_authorization_lease_id", sa.String(128), primary_key=True),
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("claim_digest", sa.String(64), nullable=False),
        sa.Column("opening_id", sa.String(128), nullable=False),
        sa.Column("opening_result_digest", sa.String(64), nullable=False),
        sa.Column("opening_attempt_id", sa.String(128), nullable=False),
        sa.Column("opening_attempt_digest", sa.String(64), nullable=False),
        sa.Column("opening_consumption_claim_id", sa.String(128), nullable=False),
        sa.Column("opening_consumption_claim_digest", sa.String(64), nullable=False),
        sa.Column("opening_authorization_lease_id", sa.String(128), nullable=False),
        sa.Column("opening_authorization_lease_digest", sa.String(64), nullable=False),
        sa.Column("opening_receipt_digest", sa.String(64), nullable=False),
        sa.Column("opening_result_state", sa.String(64), nullable=False),
        sa.Column("opening_completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("opening_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("protected_resident_context_id", sa.String(128), nullable=False),
        sa.Column("protected_resident_context_digest", sa.String(64), nullable=False),
        sa.Column(
            "protected_resident_context_created_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "protected_resident_context_usable_until", sa.DateTime(timezone=True), nullable=False
        ),
        *_scope_columns(),
        sa.Column("consumer_subject_id", sa.String(240), nullable=False),
        sa.Column("consumer_audience", sa.String(240), nullable=False),
        sa.Column("consumer_contract_id", sa.String(128), nullable=False),
        sa.Column("consumer_contract_version", sa.String(64), nullable=False),
        sa.Column("purpose_id", sa.String(128), nullable=False),
        sa.Column("policy_id", sa.String(128), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("policy_digest", sa.String(64), nullable=False),
        sa.Column("destination_boundary_id", sa.String(128), nullable=False),
        sa.Column("destination_deployment_id", sa.String(128), nullable=False),
        sa.Column("destination_generation", sa.Integer(), nullable=False),
        sa.Column("destination_fencing_token_digest", sa.String(64), nullable=False),
        sa.Column("lifecycle_attestation_id", sa.String(128), nullable=False),
        sa.Column("lifecycle_attestation_digest", sa.String(64), nullable=False),
        sa.Column("lifecycle_attestor_id", sa.String(128), nullable=False),
        sa.Column("lifecycle_attestor_version", sa.String(64), nullable=False),
        sa.Column("lifecycle_signing_key_id", sa.String(128), nullable=False),
        sa.Column("lifecycle_profile_digest", sa.String(64), nullable=False),
        sa.Column("request_nonce_digest", sa.String(64), nullable=False),
        sa.Column("lifecycle_attestation_valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resident_context_present", sa.Boolean(), nullable=False),
        sa.Column("resident_context_unexpired", sa.Boolean(), nullable=False),
        sa.Column("resident_context_unrevoked", sa.Boolean(), nullable=False),
        sa.Column("resident_context_undestroyed", sa.Boolean(), nullable=False),
        sa.Column("resident_context_unconsumed", sa.Boolean(), nullable=False),
        sa.Column("resident_context_handle_outstanding", sa.Boolean(), nullable=False),
        sa.Column("protected_resident_context_is_bearer_capability", sa.Boolean(), nullable=False),
        sa.Column("capsule_opened_in_protected_boundary", sa.Boolean(), nullable=False),
        sa.Column("target_context_pair_verified", sa.Boolean(), nullable=False),
        sa.Column("opening_outcome_known", sa.Boolean(), nullable=False),
        sa.Column("protected_source_closed", sa.Boolean(), nullable=False),
        sa.Column("source_capsule_zeroized", sa.Boolean(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("single_use", sa.Boolean(), nullable=False),
        sa.Column("renewable", sa.Boolean(), nullable=False),
        sa.Column("transferable", sa.Boolean(), nullable=False),
        sa.Column("lease_is_bearer_capability", sa.Boolean(), nullable=False),
        sa.Column("state", sa.String(64), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("lifecycle_attestation_payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "consumer_subject_id = "
            "'service.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_audience = "
            "'audience.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_contract_id = "
            "'contract.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_contract_version = '1.0' "
            "AND purpose_id = "
            "'purpose.workflow-protected-resident-context-access-evaluation' "
            "AND policy_id = "
            "'policy.workflow-protected-resident-context-access-authorization' "
            "AND policy_version = '1.0' "
            "AND policy_digest = "
            "'51141a6f2a3bbc6e61a3d95f76088325ec5f04e7246a05d334365dc941a83555'",
            name="ck_wf_rc_access_auth_lease_contract",
        ),
        sa.CheckConstraint(
            "state = 'authorized_unconsumed' AND single_use "
            "AND NOT renewable AND NOT transferable AND NOT lease_is_bearer_capability",
            name="ck_wf_rc_access_auth_lease_state",
        ),
        sa.CheckConstraint(
            "destination_boundary_id = "
            "'boundary.workflow-protected-target-context-capsule-consumer' "
            "AND destination_deployment_id = "
            "'deployment.workflow-protected-target-context-capsule-consumer' "
            "AND destination_generation = 1 "
            "AND destination_fencing_token_digest = "
            "'701153578261c45c3f1faa89f75b4a3f7003126683ddb895c0346aac0f9148e7' "
            "AND lifecycle_attestor_id = "
            "'attestor.workflow-protected-resident-context-lifecycle' "
            "AND lifecycle_attestor_version = '1.0' "
            "AND lifecycle_signing_key_id = "
            "'key.workflow-protected-target-context-capsule-opening-receipt.v1'",
            name="ck_wf_rc_access_auth_lease_profile",
        ),
        sa.CheckConstraint(
            "issued_at < valid_until "
            "AND valid_until <= issued_at + INTERVAL '1 second' "
            "AND valid_until <= effective_until "
            "AND effective_until <= protected_resident_context_usable_until "
            "AND effective_until <= lifecycle_attestation_valid_until",
            name="ck_wf_rc_access_auth_lease_window",
        ),
        sa.CheckConstraint(
            "resident_context_present AND resident_context_unexpired "
            "AND resident_context_unrevoked AND resident_context_undestroyed "
            "AND resident_context_unconsumed AND NOT resident_context_handle_outstanding "
            "AND NOT protected_resident_context_is_bearer_capability",
            name="ck_wf_rc_access_auth_lease_lifecycle",
        ),
        sa.CheckConstraint(
            "opening_result_state = 'opened_in_protected_consumer_boundary' "
            "AND opening_completed_at < opening_deadline "
            "AND protected_resident_context_created_at = opening_completed_at "
            "AND protected_resident_context_created_at < protected_resident_context_usable_until "
            "AND protected_resident_context_usable_until <= "
            "protected_resident_context_created_at + INTERVAL '30 seconds' "
            "AND NOT protected_resident_context_is_bearer_capability "
            "AND capsule_opened_in_protected_boundary AND target_context_pair_verified "
            "AND opening_outcome_known AND protected_source_closed AND source_capsule_zeroized",
            name="ck_wf_rc_access_auth_lease_source",
        ),
        sa.CheckConstraint(_lease_authority_check(), name="ck_wf_rc_access_auth_lease_authority"),
        sa.ForeignKeyConstraint(
            [
                "opening_id",
                "opening_result_digest",
                "opening_attempt_id",
                "opening_attempt_digest",
                "opening_consumption_claim_id",
                "opening_consumption_claim_digest",
                "opening_authorization_lease_id",
                "opening_authorization_lease_digest",
                "protected_resident_context_id",
                "protected_resident_context_digest",
                "opening_receipt_digest",
            ],
            [
                f"{OPENING_RESULT_TABLE}.opening_id",
                f"{OPENING_RESULT_TABLE}.canonical_digest",
                f"{OPENING_RESULT_TABLE}.attempt_id",
                f"{OPENING_RESULT_TABLE}.attempt_digest",
                f"{OPENING_RESULT_TABLE}.consumption_claim_id",
                f"{OPENING_RESULT_TABLE}.consumption_claim_digest",
                f"{OPENING_RESULT_TABLE}.authorization_lease_id",
                f"{OPENING_RESULT_TABLE}.authorization_lease_digest",
                f"{OPENING_RESULT_TABLE}.protected_resident_context_id",
                f"{OPENING_RESULT_TABLE}.protected_resident_context_digest",
                f"{OPENING_RESULT_TABLE}.opening_receipt_digest",
            ],
            name="fk_wf_rc_access_auth_result_lineage",
        ),
        sa.ForeignKeyConstraint(
            [
                "opening_attempt_id",
                "opening_attempt_digest",
                "opening_id",
                "opening_consumption_claim_id",
                "opening_consumption_claim_digest",
            ],
            [
                f"{OPENING_ATTEMPT_TABLE}.attempt_id",
                f"{OPENING_ATTEMPT_TABLE}.canonical_digest",
                f"{OPENING_ATTEMPT_TABLE}.opening_id",
                f"{OPENING_ATTEMPT_TABLE}.consumption_claim_id",
                f"{OPENING_ATTEMPT_TABLE}.consumption_claim_digest",
            ],
            name="fk_wf_rc_access_auth_attempt_lineage",
        ),
        sa.ForeignKeyConstraint(
            [
                "opening_consumption_claim_id",
                "opening_consumption_claim_digest",
                "opening_id",
                "opening_attempt_id",
            ],
            [
                f"{OPENING_CLAIM_TABLE}.claim_id",
                f"{OPENING_CLAIM_TABLE}.canonical_digest",
                f"{OPENING_CLAIM_TABLE}.opening_id",
                f"{OPENING_CLAIM_TABLE}.attempt_id",
            ],
            name="fk_wf_rc_access_auth_claim_lineage",
        ),
        sa.UniqueConstraint("opening_id", name="uq_wf_rc_access_auth_lease_result"),
        sa.UniqueConstraint(
            "protected_resident_context_id", name="uq_wf_rc_access_auth_lease_context"
        ),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rc_access_auth_lease_digest"),
        sa.UniqueConstraint(
            "access_authorization_lease_id",
            "opening_id",
            "protected_resident_context_id",
            name="uq_wf_rc_access_auth_lease_claim_lineage",
        ),
    )
    op.create_index(
        "ix_wf_rc_access_auth_lease_scope",
        LEASE_TABLE,
        ["organization_id", "environment_id", "site_id", "issued_at"],
    )

    op.create_table(
        CLAIM_TABLE,
        sa.Column("claim_id", sa.String(128), primary_key=True),
        sa.Column("access_authorization_lease_id", sa.String(128), nullable=False),
        sa.Column("opening_id", sa.String(128), nullable=False),
        sa.Column("opening_result_digest", sa.String(64), nullable=False),
        sa.Column("opening_attempt_id", sa.String(128), nullable=False),
        sa.Column("opening_attempt_digest", sa.String(64), nullable=False),
        sa.Column("opening_consumption_claim_id", sa.String(128), nullable=False),
        sa.Column("opening_consumption_claim_digest", sa.String(64), nullable=False),
        sa.Column("opening_authorization_lease_id", sa.String(128), nullable=False),
        sa.Column("opening_authorization_lease_digest", sa.String(64), nullable=False),
        sa.Column("opening_receipt_digest", sa.String(64), nullable=False),
        sa.Column("opening_result_state", sa.String(64), nullable=False),
        sa.Column("opening_completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("opening_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("protected_resident_context_id", sa.String(128), nullable=False),
        sa.Column("protected_resident_context_digest", sa.String(64), nullable=False),
        sa.Column(
            "protected_resident_context_created_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "protected_resident_context_usable_until", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("protected_resident_context_is_bearer_capability", sa.Boolean(), nullable=False),
        sa.Column("capsule_opened_in_protected_boundary", sa.Boolean(), nullable=False),
        sa.Column("target_context_pair_verified", sa.Boolean(), nullable=False),
        sa.Column("opening_outcome_known", sa.Boolean(), nullable=False),
        sa.Column("protected_source_closed", sa.Boolean(), nullable=False),
        sa.Column("source_capsule_zeroized", sa.Boolean(), nullable=False),
        *_scope_columns(),
        sa.Column("consumer_subject_id", sa.String(240), nullable=False),
        sa.Column("consumer_audience", sa.String(240), nullable=False),
        sa.Column("consumer_contract_id", sa.String(128), nullable=False),
        sa.Column("consumer_contract_version", sa.String(64), nullable=False),
        sa.Column("purpose_id", sa.String(128), nullable=False),
        sa.Column("policy_id", sa.String(128), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("policy_digest", sa.String(64), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("idempotency_digest", sa.String(64), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("authorization_audit_digest", sa.String(64), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("authorization_audit_payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(_claim_authority_check(), name="ck_wf_rc_access_auth_claim_authority"),
        sa.CheckConstraint(
            "consumer_subject_id = "
            "'service.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_audience = "
            "'audience.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_contract_id = "
            "'contract.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_contract_version = '1.0' "
            "AND purpose_id = "
            "'purpose.workflow-protected-resident-context-access-evaluation' "
            "AND policy_id = "
            "'policy.workflow-protected-resident-context-access-authorization' "
            "AND policy_version = '1.0' "
            "AND policy_digest = "
            "'51141a6f2a3bbc6e61a3d95f76088325ec5f04e7246a05d334365dc941a83555'",
            name="ck_wf_rc_access_auth_claim_contract",
        ),
        sa.CheckConstraint(
            "opening_result_state = 'opened_in_protected_consumer_boundary' "
            "AND opening_completed_at < opening_deadline "
            "AND protected_resident_context_created_at = opening_completed_at "
            "AND protected_resident_context_created_at < protected_resident_context_usable_until "
            "AND protected_resident_context_usable_until <= "
            "protected_resident_context_created_at + INTERVAL '30 seconds' "
            "AND NOT protected_resident_context_is_bearer_capability "
            "AND capsule_opened_in_protected_boundary AND target_context_pair_verified "
            "AND opening_outcome_known AND protected_source_closed AND source_capsule_zeroized",
            name="ck_wf_rc_access_auth_claim_source",
        ),
        sa.ForeignKeyConstraint(
            [
                "access_authorization_lease_id",
                "opening_id",
                "protected_resident_context_id",
            ],
            [
                f"{LEASE_TABLE}.access_authorization_lease_id",
                f"{LEASE_TABLE}.opening_id",
                f"{LEASE_TABLE}.protected_resident_context_id",
            ],
            name="fk_wf_rc_access_auth_claim_lease",
        ),
        sa.UniqueConstraint(
            "access_authorization_lease_id", name="uq_wf_rc_access_auth_claim_lease"
        ),
        sa.UniqueConstraint("opening_id", name="uq_wf_rc_access_auth_claim_result"),
        sa.UniqueConstraint(
            "protected_resident_context_id", name="uq_wf_rc_access_auth_claim_context"
        ),
        sa.UniqueConstraint(
            "idempotency_scope_id", "idempotency_key", name="uq_wf_rc_access_auth_scope_idem"
        ),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rc_access_auth_claim_digest"),
    )

    op.execute(
        sa.text(
            f"""
            CREATE FUNCTION {APPEND_ONLY_FUNCTION}()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'resident-context access authorization evidence is append-only'
                    USING ERRCODE = '55000';
            END;
            $$
            """
        )
    )
    for table, trigger in (
        (LEASE_TABLE, "trg_wf_rc_access_auth_lease_append_only"),
        (CLAIM_TABLE, "trg_wf_rc_access_auth_claim_append_only"),
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
                        'refusing guarded downgrade: resident-context access evidence exists'
                        USING ERRCODE = '55000';
                END IF;
            END $$;
            """
        )
    )
    op.drop_table(CLAIM_TABLE)
    op.drop_table(LEASE_TABLE)
    op.drop_constraint(
        "uq_wf_tctx_caps_open_result_access_auth_lineage",
        OPENING_RESULT_TABLE,
        type_="unique",
    )
    op.drop_constraint(
        "uq_wf_tctx_caps_open_attempt_access_auth_lineage",
        OPENING_ATTEMPT_TABLE,
        type_="unique",
    )
    op.drop_constraint(
        "uq_wf_tctx_caps_open_claim_access_auth_lineage",
        OPENING_CLAIM_TABLE,
        type_="unique",
    )
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {APPEND_ONLY_FUNCTION}()"))
