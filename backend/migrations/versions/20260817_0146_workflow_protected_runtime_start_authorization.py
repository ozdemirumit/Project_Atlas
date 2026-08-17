"""Add bounded protected runtime-start authorization leases.

Revision ID: 20260817_0146
Revises: 20260817_0145
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260817_0146"
down_revision: str | None = "20260817_0145"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

USE_RESULT_TABLE = "workflow_protected_runtime_context_use_results"
USE_ATTEMPT_TABLE = "workflow_protected_runtime_context_use_attempts"
USE_CLAIM_TABLE = "workflow_protected_runtime_context_use_claims"
LEASE_TABLE = "workflow_event_runtime_start_auth_leases"
CLAIM_TABLE = "workflow_event_runtime_start_auth_claims"
APPEND_ONLY_FUNCTION = "reject_wf_rtstart_auth_mutation"

POLICY_DIGEST = "8d5db5d3fcfd4ce75a1f4440ec5e543419c6aa95ba96089e315c6367731443e7"
SOURCE_POLICY_DIGEST = "3be4b37122db97ca4288fdc5cc88af15224069e5257e46a8c198d9e0069f298a"
USE_PROFILE_DIGEST = "833b75839dd35cb6d4f84e64b1d414aef380a081f4a066e391485a047edddd84"
RUNTIME_START_PROFILE_DIGEST = "233c49d3d7cb7d80655d2d2456431f38efecec49ad4c79d2100323754e829995"


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
        sa.Column("source_policy_id", sa.String(128), nullable=False),
        sa.Column("source_policy_version", sa.String(64), nullable=False),
        sa.Column("source_policy_digest", sa.String(64), nullable=False),
    )


def _source_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("use_result_id", sa.String(128), nullable=False),
        sa.Column("use_result_digest", sa.String(64), nullable=False),
        sa.Column("use_id", sa.String(128), nullable=False),
        sa.Column("use_attempt_id", sa.String(128), nullable=False),
        sa.Column("use_attempt_digest", sa.String(64), nullable=False),
        sa.Column("use_claim_id", sa.String(128), nullable=False),
        sa.Column("use_claim_digest", sa.String(64), nullable=False),
        sa.Column("use_receipt_digest", sa.String(64), nullable=False),
        sa.Column("authorization_consumption_result_id", sa.String(128), nullable=False),
        sa.Column("authorization_consumption_result_digest", sa.String(64), nullable=False),
        sa.Column("use_result_state", sa.String(64), nullable=False),
        sa.Column("use_completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("use_result_recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("use_outcome_known", sa.Boolean(), nullable=False),
        sa.Column("context_adopted", sa.Boolean(), nullable=False),
        sa.Column("protected_runtime_context_use_performed", sa.Boolean(), nullable=False),
        sa.Column("context_terminal_non_reusable", sa.Boolean(), nullable=False),
        sa.Column("transient_material_zeroized", sa.Boolean(), nullable=False),
        sa.Column("destination_deployment_id", sa.String(128), nullable=False),
        sa.Column("destination_generation", sa.Integer(), nullable=False),
        sa.Column("destination_fencing_token_digest", sa.String(64), nullable=False),
        sa.Column("runtime_slot_commitment", sa.String(64), nullable=False),
        sa.Column("runtime_slot_pre_generation", sa.Integer(), nullable=False),
        sa.Column("runtime_slot_post_generation", sa.Integer(), nullable=False),
        sa.Column("use_count_pre", sa.Integer(), nullable=False),
        sa.Column("use_count_post", sa.Integer(), nullable=False),
        sa.Column("use_profile_id", sa.String(128), nullable=False),
        sa.Column("use_profile_version", sa.String(64), nullable=False),
        sa.Column("use_profile_digest", sa.String(64), nullable=False),
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
        "protected_runtime_start_authority_granted",
    )


def _authority_columns() -> tuple[sa.Column[object], ...]:
    return tuple(sa.Column(name, sa.Boolean(), nullable=False) for name in _authority_names())


def _zero_existing_authority() -> str:
    return " AND ".join(
        f"NOT {name}"
        for name in _authority_names()
        if name != "protected_runtime_start_authority_granted"
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
        "AND purpose_id = 'purpose.workflow-protected-runtime-start-evaluation' "
        "AND policy_id = 'policy.workflow-protected-runtime-start-authorization' "
        f"AND policy_version = '1.0' AND policy_digest = '{POLICY_DIGEST}' "
        "AND source_policy_id = 'policy.workflow-protected-runtime-context-use' "
        f"AND source_policy_version = '1.0' AND source_policy_digest = '{SOURCE_POLICY_DIGEST}'"
    )


def _source_check() -> str:
    return (
        "use_result_state = 'context_used_once_in_protected_boundary' "
        "AND use_outcome_known AND context_adopted "
        "AND protected_runtime_context_use_performed "
        "AND context_terminal_non_reusable AND transient_material_zeroized "
        "AND use_completed_at <= use_result_recorded_at "
        "AND runtime_slot_pre_generation >= 1 "
        "AND runtime_slot_post_generation = runtime_slot_pre_generation + 1 "
        "AND use_count_pre = 0 AND use_count_post = 1 "
        "AND destination_generation >= 1 "
        "AND length(use_receipt_digest) = 64 "
        "AND length(destination_fencing_token_digest) = 64 "
        "AND length(runtime_slot_commitment) = 64 "
        "AND use_profile_id = 'profile.workflow-protected-runtime-context-use' "
        f"AND use_profile_version = '1.0' AND use_profile_digest = '{USE_PROFILE_DIGEST}'"
    )


def _upstream_constraints(*, prefix: str) -> tuple[sa.ForeignKeyConstraint, ...]:
    return (
        sa.ForeignKeyConstraint(
            [
                "use_result_id",
                "use_result_digest",
                "use_id",
                "use_attempt_id",
                "use_attempt_digest",
                "use_claim_id",
                "use_claim_digest",
                "authorization_consumption_result_id",
                "authorization_consumption_result_digest",
            ],
            [
                f"{USE_RESULT_TABLE}.result_id",
                f"{USE_RESULT_TABLE}.canonical_digest",
                f"{USE_RESULT_TABLE}.use_id",
                f"{USE_RESULT_TABLE}.attempt_id",
                f"{USE_RESULT_TABLE}.attempt_digest",
                f"{USE_RESULT_TABLE}.claim_id",
                f"{USE_RESULT_TABLE}.claim_digest",
                f"{USE_RESULT_TABLE}.authorization_consumption_result_id",
                f"{USE_RESULT_TABLE}.authorization_consumption_result_digest",
            ],
            name=f"fk_wf_rtstart_{prefix}_use_result",
        ),
        sa.ForeignKeyConstraint(
            [
                "use_attempt_id",
                "use_attempt_digest",
                "use_id",
                "use_claim_id",
                "use_claim_digest",
                "authorization_consumption_result_id",
                "authorization_consumption_result_digest",
            ],
            [
                f"{USE_ATTEMPT_TABLE}.attempt_id",
                f"{USE_ATTEMPT_TABLE}.canonical_digest",
                f"{USE_ATTEMPT_TABLE}.use_id",
                f"{USE_ATTEMPT_TABLE}.claim_id",
                f"{USE_ATTEMPT_TABLE}.claim_digest",
                f"{USE_ATTEMPT_TABLE}.authorization_consumption_result_id",
                f"{USE_ATTEMPT_TABLE}.authorization_consumption_result_digest",
            ],
            name=f"fk_wf_rtstart_{prefix}_use_attempt",
        ),
        sa.ForeignKeyConstraint(
            [
                "use_claim_id",
                "use_claim_digest",
                "use_id",
                "authorization_consumption_result_id",
                "authorization_consumption_result_digest",
            ],
            [
                f"{USE_CLAIM_TABLE}.claim_id",
                f"{USE_CLAIM_TABLE}.canonical_digest",
                f"{USE_CLAIM_TABLE}.use_id",
                f"{USE_CLAIM_TABLE}.authorization_consumption_result_id",
                f"{USE_CLAIM_TABLE}.authorization_consumption_result_digest",
            ],
            name=f"fk_wf_rtstart_{prefix}_use_claim",
        ),
    )


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_wf_rtctx_use_result_start_source",
        USE_RESULT_TABLE,
        [
            "result_id",
            "canonical_digest",
            "use_id",
            "attempt_id",
            "attempt_digest",
            "claim_id",
            "claim_digest",
            "authorization_consumption_result_id",
            "authorization_consumption_result_digest",
        ],
    )
    op.create_unique_constraint(
        "uq_wf_rtctx_use_attempt_start_source",
        USE_ATTEMPT_TABLE,
        [
            "attempt_id",
            "canonical_digest",
            "use_id",
            "claim_id",
            "claim_digest",
            "authorization_consumption_result_id",
            "authorization_consumption_result_digest",
        ],
    )
    op.create_unique_constraint(
        "uq_wf_rtctx_use_claim_start_source",
        USE_CLAIM_TABLE,
        [
            "claim_id",
            "canonical_digest",
            "use_id",
            "authorization_consumption_result_id",
            "authorization_consumption_result_digest",
        ],
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
        sa.Column("runtime_start_profile_id", sa.String(128), nullable=False),
        sa.Column("runtime_start_profile_version", sa.String(64), nullable=False),
        sa.Column("runtime_start_profile_digest", sa.String(64), nullable=False),
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
        *_upstream_constraints(prefix="lease"),
        sa.UniqueConstraint("claim_id", name="uq_wf_rtstart_auth_lease_claim"),
        sa.UniqueConstraint("use_result_id", name="uq_wf_rtstart_auth_lease_use_result"),
        sa.UniqueConstraint(
            "destination_deployment_id",
            "runtime_slot_commitment",
            "runtime_slot_post_generation",
            name="uq_wf_rtstart_auth_lease_slot",
        ),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rtstart_auth_lease_digest"),
        sa.UniqueConstraint(
            "authorization_lease_id",
            "use_result_id",
            "runtime_slot_commitment",
            "runtime_slot_post_generation",
            name="uq_wf_rtstart_auth_lease_lineage",
        ),
        sa.CheckConstraint(_contract_check(), name="ck_wf_rtstart_auth_lease_contract"),
        sa.CheckConstraint(_source_check(), name="ck_wf_rtstart_auth_lease_source"),
        sa.CheckConstraint(
            "use_result_recorded_at <= lifecycle_attestation_observed_at "
            "AND lifecycle_attestation_observed_at <= issued_at "
            "AND issued_at < valid_until AND valid_until <= effective_until "
            "AND effective_until <= lifecycle_attestation_valid_until "
            "AND valid_until <= issued_at + INTERVAL '1 second'",
            name="ck_wf_rtstart_auth_lease_window",
        ),
        sa.CheckConstraint(
            "single_use AND NOT renewable AND NOT transferable "
            "AND NOT lease_is_bearer_capability AND state = 'authorized_unconsumed'",
            name="ck_wf_rtstart_auth_lease_semantics",
        ),
        sa.CheckConstraint(
            "runtime_start_profile_id = 'profile.workflow-protected-runtime-start' "
            "AND runtime_start_profile_version = '1.0' "
            f"AND runtime_start_profile_digest = '{RUNTIME_START_PROFILE_DIGEST}'",
            name="ck_wf_rtstart_auth_lease_profile",
        ),
        sa.CheckConstraint(
            _zero_existing_authority() + " AND protected_runtime_start_authority_granted",
            name="ck_wf_rtstart_auth_lease_authority",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object' "
            "AND jsonb_typeof(lifecycle_attestation_payload) = 'object' "
            "AND lifecycle_attestation_payload <> '{}'::jsonb",
            name="ck_wf_rtstart_auth_lease_evidence",
        ),
    )
    op.create_index(
        "ix_wf_rtstart_auth_lease_scope",
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
        *_upstream_constraints(prefix="claim"),
        sa.ForeignKeyConstraint(
            [
                "authorization_lease_id",
                "use_result_id",
                "runtime_slot_commitment",
                "runtime_slot_post_generation",
            ],
            [
                f"{LEASE_TABLE}.authorization_lease_id",
                f"{LEASE_TABLE}.use_result_id",
                f"{LEASE_TABLE}.runtime_slot_commitment",
                f"{LEASE_TABLE}.runtime_slot_post_generation",
            ],
            name="fk_wf_rtstart_auth_claim_lease",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_rtstart_auth_claim_lease"),
        sa.UniqueConstraint("use_result_id", name="uq_wf_rtstart_auth_claim_use_result"),
        sa.UniqueConstraint(
            "destination_deployment_id",
            "runtime_slot_commitment",
            "runtime_slot_post_generation",
            name="uq_wf_rtstart_auth_claim_slot",
        ),
        sa.UniqueConstraint(
            "idempotency_scope_id", "idempotency_key", name="uq_wf_rtstart_auth_scope_idem"
        ),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rtstart_auth_claim_digest"),
        sa.UniqueConstraint(
            "claim_id",
            "canonical_digest",
            "authorization_lease_id",
            name="uq_wf_rtstart_auth_claim_lineage",
        ),
        sa.CheckConstraint(_contract_check(), name="ck_wf_rtstart_auth_claim_contract"),
        sa.CheckConstraint(_source_check(), name="ck_wf_rtstart_auth_claim_source"),
        sa.CheckConstraint(
            "use_result_recorded_at <= claimed_at",
            name="ck_wf_rtstart_auth_claim_window",
        ),
        sa.CheckConstraint(
            _zero_existing_authority() + " AND NOT protected_runtime_start_authority_granted",
            name="ck_wf_rtstart_auth_claim_authority",
        ),
        sa.CheckConstraint(
            "length(request_fingerprint) = 64 AND length(idempotency_scope_id) = 64 "
            "AND length(idempotency_digest) = 64 "
            "AND jsonb_typeof(payload) = 'object' "
            "AND jsonb_typeof(authorization_audit_payload) = 'object' "
            "AND authorization_audit_payload <> '{}'::jsonb",
            name="ck_wf_rtstart_auth_claim_audit",
        ),
    )
    op.create_index(
        "ix_wf_rtstart_auth_claim_scope",
        CLAIM_TABLE,
        ["organization_id", "environment_id", "site_id", "claimed_at"],
    )
    op.create_foreign_key(
        "fk_wf_rtstart_auth_lease_claim",
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
            RAISE EXCEPTION 'protected runtime-start authorization evidence is append-only'
                USING ERRCODE = '55000';
        END;
        $$
    """)
    )
    for table, trigger in (
        (LEASE_TABLE, "trg_wf_rtstart_auth_lease_append_only"),
        (CLAIM_TABLE, "trg_wf_rtstart_auth_claim_append_only"),
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
                    'refusing guarded downgrade: protected runtime-start authorization evidence exists'
                    USING ERRCODE = '55000';
            END IF;
        END $$;
    """)
    )
    op.drop_constraint("fk_wf_rtstart_auth_lease_claim", LEASE_TABLE, type_="foreignkey")
    op.drop_table(CLAIM_TABLE)
    op.drop_table(LEASE_TABLE)
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {APPEND_ONLY_FUNCTION}()"))
    op.drop_constraint("uq_wf_rtctx_use_claim_start_source", USE_CLAIM_TABLE, type_="unique")
    op.drop_constraint("uq_wf_rtctx_use_attempt_start_source", USE_ATTEMPT_TABLE, type_="unique")
    op.drop_constraint("uq_wf_rtctx_use_result_start_source", USE_RESULT_TABLE, type_="unique")
