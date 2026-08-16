"""Add atomic protected resident-context access consumption evidence.

Revision ID: 20260816_0140
Revises: 20260816_0139
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260816_0140"
down_revision: str | None = "20260816_0139"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEASE_TABLE = "workflow_event_resident_context_access_auth_leases"
CLAIM_TABLE = "workflow_event_resident_context_access_consumption_claims"
ATTEMPT_TABLE = "workflow_event_resident_context_access_attempts"
RESULT_TABLE = "workflow_event_resident_context_access_results"
APPEND_ONLY_FUNCTION = "reject_wf_rc_access_consumption_mutation"


def _scope_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("environment_id", sa.String(128), nullable=False),
        sa.Column("site_id", sa.String(128), nullable=False),
    )


def _authority_names() -> tuple[str, ...]:
    return (
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


def _authority_columns() -> tuple[sa.Column[object], ...]:
    return tuple(sa.Column(name, sa.Boolean(), nullable=False) for name in _authority_names())


def _zero_authority_check() -> str:
    return " AND ".join(f"NOT {name}" for name in _authority_names())


def _lineage_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("access_id", sa.String(128), nullable=False),
        sa.Column("authorization_lease_id", sa.String(128), nullable=False),
        sa.Column("authorization_lease_digest", sa.String(64), nullable=False),
        sa.Column("protected_resident_context_id", sa.String(128), nullable=False),
        sa.Column("protected_resident_context_digest", sa.String(64), nullable=False),
    )


def _identity_policy_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("consumer_subject_id", sa.String(240), nullable=False),
        sa.Column("consumer_audience", sa.String(240), nullable=False),
        sa.Column("policy_id", sa.String(128), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("policy_digest", sa.String(64), nullable=False),
    )


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_wf_rc_access_auth_consume_lineage",
        LEASE_TABLE,
        [
            "access_authorization_lease_id",
            "canonical_digest",
            "claim_id",
            "claim_digest",
            "opening_id",
            "protected_resident_context_id",
            "protected_resident_context_digest",
        ],
    )
    op.create_table(
        CLAIM_TABLE,
        sa.Column("claim_id", sa.String(128), primary_key=True),
        sa.Column("access_id", sa.String(128), nullable=False),
        sa.Column("attempt_id", sa.String(128), nullable=False),
        sa.Column("authorization_lease_id", sa.String(128), nullable=False),
        sa.Column("authorization_lease_digest", sa.String(64), nullable=False),
        sa.Column("authorization_claim_id", sa.String(128), nullable=False),
        sa.Column("authorization_claim_digest", sa.String(64), nullable=False),
        sa.Column("opening_id", sa.String(128), nullable=False),
        sa.Column("opening_result_digest", sa.String(64), nullable=False),
        sa.Column("protected_resident_context_id", sa.String(128), nullable=False),
        sa.Column("protected_resident_context_digest", sa.String(64), nullable=False),
        *_scope_columns(),
        sa.Column("consumer_subject_id", sa.String(240), nullable=False),
        sa.Column("consumer_audience", sa.String(240), nullable=False),
        sa.Column("consumer_contract_id", sa.String(128), nullable=False),
        sa.Column("consumer_contract_version", sa.String(64), nullable=False),
        sa.Column("purpose_id", sa.String(128), nullable=False),
        sa.Column("policy_id", sa.String(128), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("policy_digest", sa.String(64), nullable=False),
        sa.Column("irreversible_consumption_acknowledged", sa.Boolean(), nullable=False),
        sa.Column(
            "uncertain_outcome_requires_new_authorization_acknowledged",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("idempotency_digest", sa.String(64), nullable=False),
        sa.Column("consumption_authorization_audit_digest", sa.String(64), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("consumption_authorization_audit_payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            [
                "authorization_lease_id",
                "authorization_lease_digest",
                "authorization_claim_id",
                "authorization_claim_digest",
                "opening_id",
                "protected_resident_context_id",
                "protected_resident_context_digest",
            ],
            [
                f"{LEASE_TABLE}.access_authorization_lease_id",
                f"{LEASE_TABLE}.canonical_digest",
                f"{LEASE_TABLE}.claim_id",
                f"{LEASE_TABLE}.claim_digest",
                f"{LEASE_TABLE}.opening_id",
                f"{LEASE_TABLE}.protected_resident_context_id",
                f"{LEASE_TABLE}.protected_resident_context_digest",
            ],
            name="fk_wf_rc_access_consume_lease_lineage",
        ),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_rc_access_consume_lease"),
        sa.UniqueConstraint(
            "protected_resident_context_id", name="uq_wf_rc_access_consume_context"
        ),
        sa.UniqueConstraint("access_id", name="uq_wf_rc_access_consume_operation"),
        sa.UniqueConstraint("attempt_id", name="uq_wf_rc_access_consume_attempt"),
        sa.UniqueConstraint(
            "idempotency_scope_id", "idempotency_key", name="uq_wf_rc_access_consume_scope_idem"
        ),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rc_access_consume_digest"),
        sa.UniqueConstraint(
            "claim_id",
            "canonical_digest",
            "access_id",
            "attempt_id",
            "authorization_lease_id",
            "authorization_lease_digest",
            "protected_resident_context_id",
            "protected_resident_context_digest",
            name="uq_wf_rc_access_consume_claim_lineage",
        ),
        sa.CheckConstraint(
            "consumer_subject_id = 'service.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_audience = 'audience.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_contract_id = 'contract.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_contract_version = '1.0' "
            "AND purpose_id = 'purpose.workflow-protected-resident-context-access-consumption' "
            "AND policy_id = 'policy.workflow-protected-resident-context-access-consumption' "
            "AND policy_version = '1.0' AND policy_digest = "
            "'9efc5c1bf8cb09789de6b9373fb72d09c7397df723f9184ff80b454ce10ede9a'",
            name="ck_wf_rc_access_consume_contract",
        ),
        sa.CheckConstraint(
            "irreversible_consumption_acknowledged "
            "AND uncertain_outcome_requires_new_authorization_acknowledged",
            name="ck_wf_rc_access_consume_ack",
        ),
        sa.CheckConstraint(_zero_authority_check(), name="ck_wf_rc_access_consume_authority"),
    )
    op.create_index(
        "ix_wf_rc_access_consume_scope",
        CLAIM_TABLE,
        ["organization_id", "environment_id", "site_id", "claimed_at"],
    )

    op.create_table(
        ATTEMPT_TABLE,
        sa.Column("attempt_id", sa.String(128), primary_key=True),
        *_lineage_columns(),
        sa.Column("consumption_claim_id", sa.String(128), nullable=False),
        sa.Column("consumption_claim_digest", sa.String(64), nullable=False),
        *_scope_columns(),
        *_identity_policy_columns(),
        sa.Column("consumer_contract_id", sa.String(128), nullable=False),
        sa.Column("consumer_contract_version", sa.String(64), nullable=False),
        sa.Column("purpose_id", sa.String(128), nullable=False),
        sa.Column("required_accessor_contract_id", sa.String(128), nullable=False),
        sa.Column("required_accessor_contract_version", sa.String(64), nullable=False),
        sa.Column("approved_accessor_id", sa.String(128), nullable=False),
        sa.Column("approved_accessor_version", sa.String(64), nullable=False),
        sa.Column("destination_boundary_id", sa.String(128), nullable=False),
        sa.Column("destination_deployment_id", sa.String(128), nullable=False),
        sa.Column("destination_generation", sa.Integer(), nullable=False),
        sa.Column("destination_fencing_token_digest", sa.String(64), nullable=False),
        sa.Column("runtime_handle_profile_id", sa.String(128), nullable=False),
        sa.Column("runtime_handle_profile_version", sa.String(64), nullable=False),
        sa.Column("runtime_handle_profile_digest", sa.String(64), nullable=False),
        sa.Column("verification_signing_key_id", sa.String(128), nullable=False),
        sa.Column("lifecycle_attestation_id", sa.String(128), nullable=False),
        sa.Column("lifecycle_attestation_digest", sa.String(64), nullable=False),
        sa.Column("readiness_attestation_id", sa.String(128), nullable=False),
        sa.Column("readiness_attestation_digest", sa.String(64), nullable=False),
        sa.Column("request_nonce_digest", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("access_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("authorization_lease_valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "protected_resident_context_usable_until", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("lifecycle_attestation_valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("readiness_attestation_valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(64), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("lifecycle_attestation_payload", postgresql.JSONB(), nullable=False),
        sa.Column("readiness_attestation_payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            [
                "consumption_claim_id",
                "consumption_claim_digest",
                "access_id",
                "attempt_id",
                "authorization_lease_id",
                "authorization_lease_digest",
                "protected_resident_context_id",
                "protected_resident_context_digest",
            ],
            [
                f"{CLAIM_TABLE}.claim_id",
                f"{CLAIM_TABLE}.canonical_digest",
                f"{CLAIM_TABLE}.access_id",
                f"{CLAIM_TABLE}.attempt_id",
                f"{CLAIM_TABLE}.authorization_lease_id",
                f"{CLAIM_TABLE}.authorization_lease_digest",
                f"{CLAIM_TABLE}.protected_resident_context_id",
                f"{CLAIM_TABLE}.protected_resident_context_digest",
            ],
            name="fk_wf_rc_access_attempt_claim_lineage",
        ),
        sa.UniqueConstraint("consumption_claim_id", name="uq_wf_rc_access_attempt_claim"),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_rc_access_attempt_lease"),
        sa.UniqueConstraint(
            "protected_resident_context_id", name="uq_wf_rc_access_attempt_context"
        ),
        sa.UniqueConstraint("access_id", name="uq_wf_rc_access_attempt_operation"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rc_access_attempt_digest"),
        sa.UniqueConstraint(
            "attempt_id",
            "canonical_digest",
            "access_id",
            "consumption_claim_id",
            "consumption_claim_digest",
            "authorization_lease_id",
            "authorization_lease_digest",
            "protected_resident_context_id",
            "protected_resident_context_digest",
            name="uq_wf_rc_access_attempt_result_lineage",
        ),
        sa.CheckConstraint("state = 'started'", name="ck_wf_rc_access_attempt_state"),
        sa.CheckConstraint(
            "consumer_subject_id = 'service.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_audience = 'audience.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_contract_id = 'contract.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_contract_version = '1.0' "
            "AND purpose_id = 'purpose.workflow-protected-resident-context-access-consumption' "
            "AND policy_id = 'policy.workflow-protected-resident-context-access-consumption' "
            "AND policy_version = '1.0' AND policy_digest = "
            "'9efc5c1bf8cb09789de6b9373fb72d09c7397df723f9184ff80b454ce10ede9a'",
            name="ck_wf_rc_access_attempt_contract",
        ),
        sa.CheckConstraint(
            "started_at < access_deadline AND access_deadline <= authorization_lease_valid_until "
            "AND access_deadline <= protected_resident_context_usable_until "
            "AND access_deadline <= lifecycle_attestation_valid_until "
            "AND access_deadline <= readiness_attestation_valid_until",
            name="ck_wf_rc_access_attempt_window",
        ),
        sa.CheckConstraint(
            "required_accessor_contract_id = 'contract.workflow-protected-resident-context-accessor' "
            "AND required_accessor_contract_version = '1.0' "
            "AND approved_accessor_id = 'accessor.workflow-protected-resident-context' "
            "AND approved_accessor_version = '1.0' "
            "AND runtime_handle_profile_id = 'profile.workflow-protected-resident-context-runtime-handle' "
            "AND runtime_handle_profile_version = '1.0' "
            "AND runtime_handle_profile_digest = "
            "'1a318541a6303a5caf48131a737b1e79f458c7442498fa8dcc83f7f137e63e8a' "
            "AND verification_signing_key_id = "
            "'key.workflow-protected-resident-context-access-receipt.v1'",
            name="ck_wf_rc_access_attempt_profile",
        ),
        sa.CheckConstraint(_zero_authority_check(), name="ck_wf_rc_access_attempt_authority"),
    )
    op.create_index(
        "ix_wf_rc_access_attempt_scope",
        ATTEMPT_TABLE,
        ["organization_id", "environment_id", "site_id", "started_at"],
    )

    op.create_table(
        RESULT_TABLE,
        sa.Column("access_id", sa.String(128), primary_key=True),
        sa.Column("attempt_id", sa.String(128), nullable=False),
        sa.Column("attempt_digest", sa.String(64), nullable=False),
        sa.Column("consumption_claim_id", sa.String(128), nullable=False),
        sa.Column("consumption_claim_digest", sa.String(64), nullable=False),
        sa.Column("authorization_lease_id", sa.String(128), nullable=False),
        sa.Column("authorization_lease_digest", sa.String(64), nullable=False),
        sa.Column("protected_resident_context_id", sa.String(128), nullable=False),
        sa.Column("protected_resident_context_digest", sa.String(64), nullable=False),
        *_scope_columns(),
        *_identity_policy_columns(),
        sa.Column("consumer_contract_id", sa.String(128), nullable=False),
        sa.Column("consumer_contract_version", sa.String(64), nullable=False),
        sa.Column("purpose_id", sa.String(128), nullable=False),
        sa.Column("accessor_id", sa.String(128), nullable=False),
        sa.Column("accessor_version", sa.String(64), nullable=False),
        sa.Column("runtime_handle_profile_id", sa.String(128), nullable=False),
        sa.Column("runtime_handle_profile_version", sa.String(64), nullable=False),
        sa.Column("runtime_handle_profile_digest", sa.String(64), nullable=False),
        sa.Column("protected_runtime_handle_id", sa.String(128), nullable=True),
        sa.Column("protected_runtime_handle_digest", sa.String(64), nullable=True),
        sa.Column("protected_runtime_handle_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "protected_runtime_handle_usable_until", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("protected_runtime_handle_is_bearer_capability", sa.Boolean(), nullable=False),
        sa.Column("runtime_handle_established_in_protected_boundary", sa.Boolean(), nullable=False),
        sa.Column("protected_resident_context_consumed", sa.Boolean(), nullable=False),
        sa.Column("runtime_handle_absence_confirmed", sa.Boolean(), nullable=False),
        sa.Column("outcome_known", sa.Boolean(), nullable=False),
        sa.Column("accessor_receipt_digest", sa.String(64), nullable=True),
        sa.Column("access_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "protected_resident_context_usable_until", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("state", sa.String(64), nullable=False),
        sa.Column("failure_class", sa.String(64), nullable=True),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("accessor_receipt_payload", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(
            [
                "attempt_id",
                "attempt_digest",
                "access_id",
                "consumption_claim_id",
                "consumption_claim_digest",
                "authorization_lease_id",
                "authorization_lease_digest",
                "protected_resident_context_id",
                "protected_resident_context_digest",
            ],
            [
                f"{ATTEMPT_TABLE}.attempt_id",
                f"{ATTEMPT_TABLE}.canonical_digest",
                f"{ATTEMPT_TABLE}.access_id",
                f"{ATTEMPT_TABLE}.consumption_claim_id",
                f"{ATTEMPT_TABLE}.consumption_claim_digest",
                f"{ATTEMPT_TABLE}.authorization_lease_id",
                f"{ATTEMPT_TABLE}.authorization_lease_digest",
                f"{ATTEMPT_TABLE}.protected_resident_context_id",
                f"{ATTEMPT_TABLE}.protected_resident_context_digest",
            ],
            name="fk_wf_rc_access_result_attempt_lineage",
        ),
        sa.UniqueConstraint("attempt_id", name="uq_wf_rc_access_result_attempt"),
        sa.UniqueConstraint("consumption_claim_id", name="uq_wf_rc_access_result_claim"),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_rc_access_result_lease"),
        sa.UniqueConstraint("protected_resident_context_id", name="uq_wf_rc_access_result_context"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rc_access_result_digest"),
        sa.CheckConstraint(
            "access_deadline <= protected_resident_context_usable_until AND "
            "((state = 'access_outcome_uncertain' AND recorded_at >= access_deadline) OR "
            "completed_at < access_deadline)",
            name="ck_wf_rc_access_result_window",
        ),
        sa.CheckConstraint(
            "consumer_subject_id = 'service.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_audience = 'audience.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_contract_id = 'contract.workflow-protected-transport-target-context-capsule-consumer' "
            "AND consumer_contract_version = '1.0' "
            "AND purpose_id = 'purpose.workflow-protected-resident-context-access-consumption' "
            "AND policy_id = 'policy.workflow-protected-resident-context-access-consumption' "
            "AND policy_version = '1.0' AND policy_digest = "
            "'9efc5c1bf8cb09789de6b9373fb72d09c7397df723f9184ff80b454ce10ede9a'",
            name="ck_wf_rc_access_result_contract",
        ),
        sa.CheckConstraint(
            "(state = 'handle_established_in_protected_boundary' AND failure_class IS NULL "
            "AND completed_at IS NOT NULL AND accessor_receipt_digest IS NOT NULL "
            "AND protected_runtime_handle_id IS NOT NULL AND protected_runtime_handle_digest IS NOT NULL "
            "AND protected_runtime_handle_created_at = completed_at "
            "AND protected_runtime_handle_usable_until IS NOT NULL "
            "AND runtime_handle_established_in_protected_boundary "
            "AND protected_resident_context_consumed AND NOT runtime_handle_absence_confirmed "
            "AND outcome_known "
            "AND NOT protected_runtime_handle_is_bearer_capability) OR "
            "(state = 'resident_context_access_failed' AND failure_class IS NOT NULL "
            "AND completed_at IS NOT NULL AND accessor_receipt_digest IS NOT NULL "
            "AND protected_runtime_handle_id IS NULL AND protected_runtime_handle_digest IS NULL "
            "AND protected_runtime_handle_created_at IS NULL "
            "AND protected_runtime_handle_usable_until IS NULL "
            "AND NOT runtime_handle_established_in_protected_boundary "
            "AND protected_resident_context_consumed AND runtime_handle_absence_confirmed "
            "AND outcome_known) OR "
            "(state = 'access_outcome_uncertain' AND failure_class = 'access_outcome_uncertain' "
            "AND completed_at IS NULL AND accessor_receipt_digest IS NULL "
            "AND protected_runtime_handle_id IS NULL AND protected_runtime_handle_digest IS NULL "
            "AND protected_runtime_handle_created_at IS NULL "
            "AND protected_runtime_handle_usable_until IS NULL "
            "AND NOT runtime_handle_established_in_protected_boundary "
            "AND NOT protected_resident_context_consumed "
            "AND NOT runtime_handle_absence_confirmed AND NOT outcome_known)",
            name="ck_wf_rc_access_result_outcome",
        ),
        sa.CheckConstraint(
            "NOT protected_runtime_handle_is_bearer_capability",
            name="ck_wf_rc_access_result_non_bearer",
        ),
        sa.CheckConstraint(_zero_authority_check(), name="ck_wf_rc_access_result_authority"),
    )
    op.create_index(
        "ix_wf_rc_access_result_scope",
        RESULT_TABLE,
        ["organization_id", "environment_id", "site_id", "recorded_at"],
    )

    op.execute(
        sa.text(f"""
        CREATE FUNCTION {APPEND_ONLY_FUNCTION}() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'resident-context access consumption evidence is append-only'
                USING ERRCODE = '55000';
        END;
        $$
    """)
    )
    for table, trigger in (
        (CLAIM_TABLE, "trg_wf_rc_access_consume_append_only"),
        (ATTEMPT_TABLE, "trg_wf_rc_access_attempt_append_only"),
        (RESULT_TABLE, "trg_wf_rc_access_result_append_only"),
    ):
        op.execute(
            sa.text(
                f"CREATE TRIGGER {trigger} BEFORE UPDATE OR DELETE ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION {APPEND_ONLY_FUNCTION}()"
            )
        )


def downgrade() -> None:
    op.execute(
        sa.text(f"""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM {CLAIM_TABLE} LIMIT 1)
               OR EXISTS (SELECT 1 FROM {ATTEMPT_TABLE} LIMIT 1)
               OR EXISTS (SELECT 1 FROM {RESULT_TABLE} LIMIT 1) THEN
                RAISE EXCEPTION
                    'refusing guarded downgrade: resident-context access consumption evidence exists'
                    USING ERRCODE = '55000';
            END IF;
        END $$;
    """)
    )
    op.drop_table(RESULT_TABLE)
    op.drop_table(ATTEMPT_TABLE)
    op.drop_table(CLAIM_TABLE)
    op.drop_constraint("uq_wf_rc_access_auth_consume_lineage", LEASE_TABLE, type_="unique")
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {APPEND_ONLY_FUNCTION}()"))
