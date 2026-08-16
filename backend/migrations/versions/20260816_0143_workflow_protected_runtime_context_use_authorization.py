"""Add bounded protected runtime-context use authorization leases.

Revision ID: 20260816_0143
Revises: 20260816_0142
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260816_0143"
down_revision: str | None = "20260816_0142"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE_TABLE = "workflow_event_runtime_context_injection_results"
ATTEMPT_TABLE = "workflow_event_runtime_context_injection_attempts"
CONSUMPTION_CLAIM_TABLE = "workflow_event_runtime_context_injection_consumption_claims"
INJECTION_AUTH_LEASE_TABLE = "workflow_event_runtime_context_injection_auth_leases"
LEASE_TABLE = "workflow_event_runtime_context_use_auth_leases"
CLAIM_TABLE = "workflow_event_runtime_context_use_auth_claims"
APPEND_ONLY_FUNCTION = "reject_wf_rtctx_use_auth_mutation"

POLICY_DIGEST = "4287e205f26c138d7bab29faf92bd1a1d1c222378633fb7c28ddefadc8a9e5bd"
RUNTIME_SLOT_PROFILE_DIGEST = "7c429ec36bd39f5d02add24b7622e55e32eb0cfca9345ebf272fd231385e3e6b"
USE_PROFILE_DIGEST = "833b75839dd35cb6d4f84e64b1d414aef380a081f4a066e391485a047edddd84"


def _scope_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("environment_id", sa.String(128), nullable=False),
        sa.Column("site_id", sa.String(128), nullable=False),
    )


def _identity_policy_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("consumer_subject_id", sa.String(240), nullable=False),
        sa.Column("consumer_audience", sa.String(240), nullable=False),
        sa.Column("consumer_contract_id", sa.String(128), nullable=False),
        sa.Column("consumer_contract_version", sa.String(64), nullable=False),
        sa.Column("purpose_id", sa.String(128), nullable=False),
        sa.Column("policy_id", sa.String(128), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("policy_digest", sa.String(64), nullable=False),
    )


def _source_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("injection_result_id", sa.String(128), nullable=False),
        sa.Column("injection_result_digest", sa.String(64), nullable=False),
        sa.Column("injection_id", sa.String(128), nullable=False),
        sa.Column("injection_attempt_id", sa.String(128), nullable=False),
        sa.Column("injection_attempt_digest", sa.String(64), nullable=False),
        sa.Column("injection_consumption_claim_id", sa.String(128), nullable=False),
        sa.Column("injection_consumption_claim_digest", sa.String(64), nullable=False),
        sa.Column("injection_authorization_lease_id", sa.String(128), nullable=False),
        sa.Column("injection_authorization_lease_digest", sa.String(64), nullable=False),
        sa.Column("injector_receipt_digest", sa.String(64), nullable=False),
        sa.Column("injection_result_state", sa.String(64), nullable=False),
        sa.Column("injection_completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("injection_result_recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("injection_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("injection_outcome_known", sa.Boolean(), nullable=False),
        sa.Column("protected_runtime_handle_consumed", sa.Boolean(), nullable=False),
        sa.Column("inert_context_injected", sa.Boolean(), nullable=False),
        sa.Column("runtime_slot_mutation_performed", sa.Boolean(), nullable=False),
        sa.Column("destination_boundary_id", sa.String(128), nullable=False),
        sa.Column("destination_deployment_id", sa.String(128), nullable=False),
        sa.Column("destination_generation", sa.Integer(), nullable=False),
        sa.Column("destination_fencing_token_digest", sa.String(64), nullable=False),
        sa.Column("runtime_slot_profile_id", sa.String(128), nullable=False),
        sa.Column("runtime_slot_profile_version", sa.String(64), nullable=False),
        sa.Column("runtime_slot_profile_digest", sa.String(64), nullable=False),
        sa.Column("runtime_slot_commitment", sa.String(64), nullable=False),
        sa.Column("runtime_slot_post_generation", sa.Integer(), nullable=False),
        sa.Column("injected_context_usable_until", sa.DateTime(timezone=True), nullable=False),
    )


def _upstream_foreign_keys(*, prefix: str) -> tuple[sa.ForeignKeyConstraint, ...]:
    return (
        sa.ForeignKeyConstraint(
            ["injection_result_id", "injection_result_digest"],
            [f"{SOURCE_TABLE}.result_id", f"{SOURCE_TABLE}.canonical_digest"],
            name=f"fk_wf_rtctx_use_{prefix}_result",
        ),
        sa.ForeignKeyConstraint(
            ["injection_attempt_id", "injection_attempt_digest"],
            [f"{ATTEMPT_TABLE}.attempt_id", f"{ATTEMPT_TABLE}.canonical_digest"],
            name=f"fk_wf_rtctx_use_{prefix}_attempt",
        ),
        sa.ForeignKeyConstraint(
            ["injection_consumption_claim_id", "injection_consumption_claim_digest"],
            [
                f"{CONSUMPTION_CLAIM_TABLE}.claim_id",
                f"{CONSUMPTION_CLAIM_TABLE}.canonical_digest",
            ],
            name=f"fk_wf_rtctx_use_{prefix}_consume_claim",
        ),
        sa.ForeignKeyConstraint(
            ["injection_authorization_lease_id", "injection_authorization_lease_digest"],
            [
                f"{INJECTION_AUTH_LEASE_TABLE}.authorization_lease_id",
                f"{INJECTION_AUTH_LEASE_TABLE}.canonical_digest",
            ],
            name=f"fk_wf_rtctx_use_{prefix}_inj_auth_lease",
        ),
    )


def _authority_names() -> tuple[str, ...]:
    return (
        "endpoint_resolution_authorized",
        "route_selection_authorized",
        "route_binding_authorized",
        "credential_selection_authorized",
        "credential_assignment_binding_authorized",
        "credential_access_authorized",
        "credential_brokerage_authorized",
        "credential_resolution_authorized",
        "protected_artifact_access_authorized",
        "credential_delivery_authorized",
        "network_access_authorized",
        "readiness_probe_authorized",
        "publication_authorized",
        "delivery_authorized",
        "dispatch_authorized",
        "execution_authorized",
        "infrastructure_mutation_authorized",
        "target_context_capsule_handoff_authorized",
        "target_context_capsule_opening_authorized",
        "protected_resident_context_access_authority_granted",
        "protected_runtime_context_injection_authority_granted",
        "runtime_use_authorized",
        "runtime_start_authorized",
        "runtime_resume_authorized",
        "connector_activity_authorized",
        "protected_runtime_context_use_authority_granted",
    )


def _authority_columns() -> tuple[sa.Column[object], ...]:
    return tuple(sa.Column(name, sa.Boolean(), nullable=False) for name in _authority_names())


def _zero_prior_authority() -> str:
    return " AND ".join(
        f"NOT {name}"
        for name in _authority_names()
        if name != "protected_runtime_context_use_authority_granted"
    )


def _contract_check() -> str:
    return (
        "consumer_subject_id = "
        "'service.workflow-protected-transport-target-context-capsule-consumer' "
        "AND consumer_audience = "
        "'audience.workflow-protected-transport-target-context-capsule-consumer' "
        "AND consumer_contract_id = "
        "'contract.workflow-protected-transport-target-context-capsule-consumer' "
        "AND consumer_contract_version = '1.0' "
        "AND purpose_id = 'purpose.workflow-protected-runtime-context-use-evaluation' "
        "AND policy_id = 'policy.workflow-protected-runtime-context-use-authorization' "
        f"AND policy_version = '1.0' AND policy_digest = '{POLICY_DIGEST}'"
    )


def _source_check() -> str:
    return (
        "injection_result_state = 'injected_into_protected_runtime_slot' "
        "AND injection_outcome_known "
        "AND protected_runtime_handle_consumed "
        "AND inert_context_injected "
        "AND runtime_slot_mutation_performed "
        "AND injection_completed_at < injection_deadline "
        "AND injection_completed_at <= injection_result_recorded_at "
        "AND injection_completed_at < injected_context_usable_until "
        "AND runtime_slot_post_generation >= 1 "
        "AND length(runtime_slot_commitment) = 64 "
        "AND length(destination_fencing_token_digest) = 64 "
        "AND runtime_slot_profile_id = 'profile.workflow-protected-runtime-context-slot' "
        "AND runtime_slot_profile_version = '1.0' "
        f"AND runtime_slot_profile_digest = '{RUNTIME_SLOT_PROFILE_DIGEST}'"
    )


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_wf_rtctx_inj_result_id_digest",
        SOURCE_TABLE,
        ["result_id", "canonical_digest"],
    )
    op.create_unique_constraint(
        "uq_wf_rtctx_inj_attempt_id_digest",
        ATTEMPT_TABLE,
        ["attempt_id", "canonical_digest"],
    )
    op.create_unique_constraint(
        "uq_wf_rtctx_inj_consume_claim_id_digest",
        CONSUMPTION_CLAIM_TABLE,
        ["claim_id", "canonical_digest"],
    )
    op.create_unique_constraint(
        "uq_wf_rtctx_inj_auth_lease_id_digest",
        INJECTION_AUTH_LEASE_TABLE,
        ["authorization_lease_id", "canonical_digest"],
    )
    op.create_table(
        LEASE_TABLE,
        sa.Column("authorization_lease_id", sa.String(128), primary_key=True),
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("claim_digest", sa.String(64), nullable=False),
        *_source_columns(),
        *_scope_columns(),
        *_identity_policy_columns(),
        sa.Column("lifecycle_attestation_id", sa.String(128), nullable=False),
        sa.Column("lifecycle_attestation_digest", sa.String(64), nullable=False),
        sa.Column("lifecycle_attestation_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lifecycle_attestation_valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("use_profile_id", sa.String(128), nullable=False),
        sa.Column("use_profile_version", sa.String(64), nullable=False),
        sa.Column("use_profile_digest", sa.String(64), nullable=False),
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
        *_upstream_foreign_keys(prefix="lease"),
        sa.UniqueConstraint("claim_id", name="uq_wf_rtctx_use_auth_lease_claim"),
        sa.UniqueConstraint("injection_result_id", name="uq_wf_rtctx_use_auth_lease_result"),
        sa.UniqueConstraint(
            "destination_deployment_id",
            "runtime_slot_commitment",
            "runtime_slot_post_generation",
            name="uq_wf_rtctx_use_auth_lease_slot_generation",
        ),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rtctx_use_auth_lease_digest"),
        sa.UniqueConstraint(
            "authorization_lease_id",
            "injection_result_id",
            "runtime_slot_commitment",
            "runtime_slot_post_generation",
            name="uq_wf_rtctx_use_auth_lease_lineage",
        ),
        sa.CheckConstraint(_contract_check(), name="ck_wf_rtctx_use_auth_lease_contract"),
        sa.CheckConstraint(_source_check(), name="ck_wf_rtctx_use_auth_lease_source"),
        sa.CheckConstraint(
            "injection_result_recorded_at <= lifecycle_attestation_observed_at "
            "AND lifecycle_attestation_observed_at <= issued_at "
            "AND issued_at < valid_until "
            "AND valid_until <= effective_until "
            "AND effective_until <= lifecycle_attestation_valid_until "
            "AND effective_until <= injected_context_usable_until "
            "AND valid_until <= issued_at + INTERVAL '1 second'",
            name="ck_wf_rtctx_use_auth_lease_window",
        ),
        sa.CheckConstraint(
            "single_use AND NOT renewable AND NOT transferable "
            "AND NOT lease_is_bearer_capability AND state = 'authorized_unconsumed'",
            name="ck_wf_rtctx_use_auth_lease_semantics",
        ),
        sa.CheckConstraint(
            "use_profile_id = 'profile.workflow-protected-runtime-context-use' "
            "AND use_profile_version = '1.0' "
            f"AND use_profile_digest = '{USE_PROFILE_DIGEST}'",
            name="ck_wf_rtctx_use_auth_lease_profile",
        ),
        sa.CheckConstraint(
            _zero_prior_authority() + " AND protected_runtime_context_use_authority_granted",
            name="ck_wf_rtctx_use_auth_lease_authority",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object' "
            "AND jsonb_typeof(lifecycle_attestation_payload) = 'object' "
            "AND lifecycle_attestation_payload <> '{}'::jsonb",
            name="ck_wf_rtctx_use_auth_lease_evidence",
        ),
    )
    op.create_index(
        "ix_wf_rtctx_use_auth_lease_scope",
        LEASE_TABLE,
        ["organization_id", "environment_id", "site_id", "issued_at"],
    )

    op.create_table(
        CLAIM_TABLE,
        sa.Column("claim_id", sa.String(128), primary_key=True),
        sa.Column("authorization_lease_id", sa.String(128), nullable=False),
        *_source_columns(),
        *_scope_columns(),
        *_identity_policy_columns(),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("idempotency_digest", sa.String(64), nullable=False),
        sa.Column("authorization_audit_digest", sa.String(64), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("authorization_audit_payload", postgresql.JSONB(), nullable=False),
        *_upstream_foreign_keys(prefix="claim"),
        sa.ForeignKeyConstraint(
            [
                "authorization_lease_id",
                "injection_result_id",
                "runtime_slot_commitment",
                "runtime_slot_post_generation",
            ],
            [
                f"{LEASE_TABLE}.authorization_lease_id",
                f"{LEASE_TABLE}.injection_result_id",
                f"{LEASE_TABLE}.runtime_slot_commitment",
                f"{LEASE_TABLE}.runtime_slot_post_generation",
            ],
            name="fk_wf_rtctx_use_auth_claim_lease",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_rtctx_use_auth_claim_lease"),
        sa.UniqueConstraint("injection_result_id", name="uq_wf_rtctx_use_auth_claim_result"),
        sa.UniqueConstraint(
            "destination_deployment_id",
            "runtime_slot_commitment",
            "runtime_slot_post_generation",
            name="uq_wf_rtctx_use_auth_claim_slot_generation",
        ),
        sa.UniqueConstraint(
            "idempotency_scope_id", "idempotency_key", name="uq_wf_rtctx_use_auth_scope_idem"
        ),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rtctx_use_auth_claim_digest"),
        sa.UniqueConstraint(
            "claim_id",
            "canonical_digest",
            "authorization_lease_id",
            name="uq_wf_rtctx_use_auth_claim_lease_lineage",
        ),
        sa.CheckConstraint(_contract_check(), name="ck_wf_rtctx_use_auth_claim_contract"),
        sa.CheckConstraint(_source_check(), name="ck_wf_rtctx_use_auth_claim_source"),
        sa.CheckConstraint(
            "injection_result_recorded_at <= claimed_at "
            "AND claimed_at < injected_context_usable_until",
            name="ck_wf_rtctx_use_auth_claim_window",
        ),
        sa.CheckConstraint(
            _zero_prior_authority() + " AND NOT protected_runtime_context_use_authority_granted",
            name="ck_wf_rtctx_use_auth_claim_authority",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object' "
            "AND jsonb_typeof(authorization_audit_payload) = 'object' "
            "AND authorization_audit_payload <> '{}'::jsonb",
            name="ck_wf_rtctx_use_auth_claim_audit",
        ),
    )
    op.create_index(
        "ix_wf_rtctx_use_auth_claim_scope",
        CLAIM_TABLE,
        ["organization_id", "environment_id", "site_id", "claimed_at"],
    )
    op.create_foreign_key(
        "fk_wf_rtctx_use_auth_lease_claim",
        LEASE_TABLE,
        CLAIM_TABLE,
        ["claim_id", "claim_digest", "authorization_lease_id"],
        ["claim_id", "canonical_digest", "authorization_lease_id"],
        deferrable=True,
        initially="DEFERRED",
    )

    op.execute(
        sa.text(f"""
        CREATE FUNCTION {APPEND_ONLY_FUNCTION}() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'runtime-context use authorization evidence is append-only'
                USING ERRCODE = '55000';
        END;
        $$
    """)
    )
    for table, trigger in (
        (LEASE_TABLE, "trg_wf_rtctx_use_auth_lease_append_only"),
        (CLAIM_TABLE, "trg_wf_rtctx_use_auth_claim_append_only"),
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
            IF EXISTS (SELECT 1 FROM {LEASE_TABLE} LIMIT 1)
               OR EXISTS (SELECT 1 FROM {CLAIM_TABLE} LIMIT 1) THEN
                RAISE EXCEPTION
                    'refusing guarded downgrade: runtime-context use authorization evidence exists'
                    USING ERRCODE = '55000';
            END IF;
        END $$;
    """)
    )
    op.drop_constraint(
        "fk_wf_rtctx_use_auth_lease_claim",
        LEASE_TABLE,
        type_="foreignkey",
    )
    op.drop_table(CLAIM_TABLE)
    op.drop_table(LEASE_TABLE)
    op.drop_constraint(
        "uq_wf_rtctx_inj_auth_lease_id_digest",
        INJECTION_AUTH_LEASE_TABLE,
        type_="unique",
    )
    op.drop_constraint(
        "uq_wf_rtctx_inj_consume_claim_id_digest",
        CONSUMPTION_CLAIM_TABLE,
        type_="unique",
    )
    op.drop_constraint(
        "uq_wf_rtctx_inj_attempt_id_digest",
        ATTEMPT_TABLE,
        type_="unique",
    )
    op.drop_constraint(
        "uq_wf_rtctx_inj_result_id_digest",
        SOURCE_TABLE,
        type_="unique",
    )
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {APPEND_ONLY_FUNCTION}()"))
