"""Add bounded protected runtime-context injection authorization leases.

Revision ID: 20260816_0141
Revises: 20260816_0140
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260816_0141"
down_revision: str | None = "20260816_0140"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SOURCE_RESULT_TABLE = "workflow_event_resident_context_access_results"
DESTINATION_HEAD_TABLE = "workflow_protected_runtime_context_injection_destination_heads"
LEASE_TABLE = "workflow_event_runtime_context_injection_auth_leases"
CLAIM_TABLE = "workflow_event_runtime_context_injection_auth_claims"
APPEND_ONLY_FUNCTION = "reject_wf_rtctx_inj_auth_mutation"

POLICY_DIGEST = "cf8b08ca5eef652623d69dd4521f8e25a7d537dc80a06de40fa7cc4cdc34fbcb"
RUNTIME_HANDLE_PROFILE_DIGEST = "1a318541a6303a5caf48131a737b1e79f458c7442498fa8dcc83f7f137e63e8a"
RUNTIME_SLOT_PROFILE_DIGEST = "7c429ec36bd39f5d02add24b7622e55e32eb0cfca9345ebf272fd231385e3e6b"
DESTINATION_HEAD_DIGEST = "05a2d559de8e9017bbd542f632f75c1de1371b938351038ee720f4cb5f2f0e1f"


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
        "protected_runtime_context_injection_authority_granted",
    )


def _authority_columns() -> tuple[sa.Column[object], ...]:
    return tuple(sa.Column(name, sa.Boolean(), nullable=False) for name in _authority_names())


def _claim_authority_check() -> str:
    return " AND ".join(f"NOT {name}" for name in _authority_names())


def _lease_authority_check() -> str:
    return "protected_runtime_context_injection_authority_granted AND " + " AND ".join(
        f"NOT {name}"
        for name in _authority_names()
        if name != "protected_runtime_context_injection_authority_granted"
    )


def _source_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("access_result_id", sa.String(128), nullable=False),
        sa.Column("access_result_digest", sa.String(64), nullable=False),
        sa.Column("access_attempt_id", sa.String(128), nullable=False),
        sa.Column("access_attempt_digest", sa.String(64), nullable=False),
        sa.Column("access_consumption_claim_id", sa.String(128), nullable=False),
        sa.Column("access_consumption_claim_digest", sa.String(64), nullable=False),
        sa.Column("access_authorization_lease_id", sa.String(128), nullable=False),
        sa.Column("access_authorization_lease_digest", sa.String(64), nullable=False),
        sa.Column("accessor_receipt_digest", sa.String(64), nullable=False),
        sa.Column("access_result_state", sa.String(64), nullable=False),
        sa.Column("access_completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("access_result_recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("access_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("protected_runtime_handle_id", sa.String(128), nullable=False),
        sa.Column("protected_runtime_handle_digest", sa.String(64), nullable=False),
        sa.Column(
            "protected_runtime_handle_created_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "protected_runtime_handle_usable_until", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("protected_runtime_handle_is_bearer_capability", sa.Boolean(), nullable=False),
        sa.Column(
            "protected_resident_context_usable_until", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("protected_resident_context_consumed", sa.Boolean(), nullable=False),
        sa.Column("runtime_handle_established_in_protected_boundary", sa.Boolean(), nullable=False),
        sa.Column("access_outcome_known", sa.Boolean(), nullable=False),
        sa.Column("destination_boundary_id", sa.String(128), nullable=False),
        sa.Column("destination_deployment_id", sa.String(128), nullable=False),
        sa.Column("destination_generation", sa.Integer(), nullable=False),
        sa.Column("destination_fencing_token_digest", sa.String(64), nullable=False),
        sa.Column("runtime_handle_profile_id", sa.String(128), nullable=False),
        sa.Column("runtime_handle_profile_version", sa.String(64), nullable=False),
        sa.Column("runtime_handle_profile_digest", sa.String(64), nullable=False),
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


def _source_fk(name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [
            "access_result_id",
            "access_result_digest",
            "access_attempt_id",
            "access_attempt_digest",
            "access_consumption_claim_id",
            "access_consumption_claim_digest",
            "access_authorization_lease_id",
            "access_authorization_lease_digest",
            "accessor_receipt_digest",
            "protected_runtime_handle_id",
            "protected_runtime_handle_digest",
            "runtime_handle_profile_id",
            "runtime_handle_profile_version",
            "runtime_handle_profile_digest",
            "access_result_state",
            "access_completed_at",
            "access_result_recorded_at",
            "access_deadline",
            "protected_runtime_handle_created_at",
            "protected_runtime_handle_usable_until",
            "protected_runtime_handle_is_bearer_capability",
            "protected_resident_context_usable_until",
            "protected_resident_context_consumed",
            "runtime_handle_established_in_protected_boundary",
            "access_outcome_known",
        ],
        [
            f"{SOURCE_RESULT_TABLE}.access_id",
            f"{SOURCE_RESULT_TABLE}.canonical_digest",
            f"{SOURCE_RESULT_TABLE}.attempt_id",
            f"{SOURCE_RESULT_TABLE}.attempt_digest",
            f"{SOURCE_RESULT_TABLE}.consumption_claim_id",
            f"{SOURCE_RESULT_TABLE}.consumption_claim_digest",
            f"{SOURCE_RESULT_TABLE}.authorization_lease_id",
            f"{SOURCE_RESULT_TABLE}.authorization_lease_digest",
            f"{SOURCE_RESULT_TABLE}.accessor_receipt_digest",
            f"{SOURCE_RESULT_TABLE}.protected_runtime_handle_id",
            f"{SOURCE_RESULT_TABLE}.protected_runtime_handle_digest",
            f"{SOURCE_RESULT_TABLE}.runtime_handle_profile_id",
            f"{SOURCE_RESULT_TABLE}.runtime_handle_profile_version",
            f"{SOURCE_RESULT_TABLE}.runtime_handle_profile_digest",
            f"{SOURCE_RESULT_TABLE}.state",
            f"{SOURCE_RESULT_TABLE}.completed_at",
            f"{SOURCE_RESULT_TABLE}.recorded_at",
            f"{SOURCE_RESULT_TABLE}.access_deadline",
            f"{SOURCE_RESULT_TABLE}.protected_runtime_handle_created_at",
            f"{SOURCE_RESULT_TABLE}.protected_runtime_handle_usable_until",
            f"{SOURCE_RESULT_TABLE}.protected_runtime_handle_is_bearer_capability",
            f"{SOURCE_RESULT_TABLE}.protected_resident_context_usable_until",
            f"{SOURCE_RESULT_TABLE}.protected_resident_context_consumed",
            f"{SOURCE_RESULT_TABLE}.runtime_handle_established_in_protected_boundary",
            f"{SOURCE_RESULT_TABLE}.outcome_known",
        ],
        name=name,
    )


def _contract_check() -> str:
    return (
        "consumer_subject_id = 'service.workflow-protected-transport-target-context-capsule-consumer' "
        "AND consumer_audience = 'audience.workflow-protected-transport-target-context-capsule-consumer' "
        "AND consumer_contract_id = 'contract.workflow-protected-transport-target-context-capsule-consumer' "
        "AND consumer_contract_version = '1.0' "
        "AND purpose_id = 'purpose.workflow-protected-runtime-context-injection-evaluation' "
        "AND policy_id = 'policy.workflow-protected-runtime-context-injection-authorization' "
        f"AND policy_version = '1.0' AND policy_digest = '{POLICY_DIGEST}'"
    )


def _source_check() -> str:
    return (
        "access_result_state = 'handle_established_in_protected_boundary' "
        "AND access_completed_at < access_deadline "
        "AND access_completed_at <= access_result_recorded_at "
        "AND protected_runtime_handle_created_at = access_completed_at "
        "AND protected_runtime_handle_created_at < protected_runtime_handle_usable_until "
        "AND protected_runtime_handle_usable_until <= protected_resident_context_usable_until "
        "AND NOT protected_runtime_handle_is_bearer_capability "
        "AND protected_resident_context_consumed "
        "AND runtime_handle_established_in_protected_boundary "
        "AND access_outcome_known "
        "AND destination_boundary_id = 'boundary.workflow-protected-target-context-capsule-consumer' "
        "AND destination_deployment_id = 'deployment.workflow-protected-target-context-capsule-consumer' "
        "AND destination_generation = 1 "
        "AND destination_fencing_token_digest = "
        "'701153578261c45c3f1faa89f75b4a3f7003126683ddb895c0346aac0f9148e7' "
        "AND runtime_handle_profile_id = "
        "'profile.workflow-protected-resident-context-runtime-handle' "
        "AND runtime_handle_profile_version = '1.0' "
        f"AND runtime_handle_profile_digest = '{RUNTIME_HANDLE_PROFILE_DIGEST}'"
    )


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_wf_rc_access_result_injection_auth_lineage",
        SOURCE_RESULT_TABLE,
        [
            "access_id",
            "canonical_digest",
            "attempt_id",
            "attempt_digest",
            "consumption_claim_id",
            "consumption_claim_digest",
            "authorization_lease_id",
            "authorization_lease_digest",
            "accessor_receipt_digest",
            "protected_runtime_handle_id",
            "protected_runtime_handle_digest",
            "runtime_handle_profile_id",
            "runtime_handle_profile_version",
            "runtime_handle_profile_digest",
            "state",
            "completed_at",
            "recorded_at",
            "access_deadline",
            "protected_runtime_handle_created_at",
            "protected_runtime_handle_usable_until",
            "protected_runtime_handle_is_bearer_capability",
            "protected_resident_context_usable_until",
            "protected_resident_context_consumed",
            "runtime_handle_established_in_protected_boundary",
            "outcome_known",
        ],
    )

    destination_head_payload = {
        "destination_boundary_id": ("boundary.workflow-protected-target-context-capsule-consumer"),
        "destination_deployment_id": (
            "deployment.workflow-protected-target-context-capsule-consumer"
        ),
        "destination_generation": 1,
        "destination_fencing_token_digest": (
            "701153578261c45c3f1faa89f75b4a3f7003126683ddb895c0346aac0f9148e7"
        ),
        "policy_digest": POLICY_DIGEST,
    }
    destination_head = op.create_table(
        DESTINATION_HEAD_TABLE,
        sa.Column("destination_deployment_id", sa.String(128), primary_key=True),
        sa.Column("destination_boundary_id", sa.String(128), nullable=False),
        sa.Column("destination_generation", sa.Integer(), nullable=False),
        sa.Column("destination_fencing_token_digest", sa.String(64), nullable=False),
        sa.Column("policy_digest", sa.String(64), nullable=False),
        sa.Column("current", sa.Boolean(), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint(
            "destination_boundary_id",
            "destination_deployment_id",
            "destination_generation",
            "destination_fencing_token_digest",
            "policy_digest",
            name="uq_wf_rtctx_inj_dest_head_lineage",
        ),
        sa.CheckConstraint(
            "destination_boundary_id = "
            "'boundary.workflow-protected-target-context-capsule-consumer' "
            "AND destination_deployment_id = "
            "'deployment.workflow-protected-target-context-capsule-consumer' "
            "AND destination_generation >= 1 "
            "AND length(destination_fencing_token_digest) = 64 "
            f"AND policy_digest = '{POLICY_DIGEST}' AND current",
            name="ck_wf_rtctx_inj_dest_head_contract",
        ),
        sa.CheckConstraint(
            "length(canonical_digest) = 64 AND payload = jsonb_build_object("
            "'destination_boundary_id', destination_boundary_id, "
            "'destination_deployment_id', destination_deployment_id, "
            "'destination_generation', destination_generation, "
            "'destination_fencing_token_digest', destination_fencing_token_digest, "
            "'policy_digest', policy_digest)",
            name="ck_wf_rtctx_inj_dest_head_digest",
        ),
    )
    op.bulk_insert(
        destination_head,
        [
            {
                **destination_head_payload,
                "current": True,
                "canonical_digest": DESTINATION_HEAD_DIGEST,
                "payload": destination_head_payload,
            }
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
        sa.Column("lifecycle_attestor_id", sa.String(128), nullable=False),
        sa.Column("lifecycle_attestor_version", sa.String(64), nullable=False),
        sa.Column("lifecycle_signing_key_id", sa.String(128), nullable=False),
        sa.Column("lifecycle_profile_digest", sa.String(64), nullable=False),
        sa.Column("request_nonce_digest", sa.String(64), nullable=False),
        sa.Column("injector_contract_id", sa.String(128), nullable=False),
        sa.Column("injector_contract_version", sa.String(64), nullable=False),
        sa.Column("injector_id", sa.String(128), nullable=False),
        sa.Column("injector_version", sa.String(64), nullable=False),
        sa.Column("runtime_slot_profile_id", sa.String(128), nullable=False),
        sa.Column("runtime_slot_profile_version", sa.String(64), nullable=False),
        sa.Column("runtime_slot_profile_digest", sa.String(64), nullable=False),
        sa.Column("pre_attestation_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("runtime_handle_present", sa.Boolean(), nullable=False),
        sa.Column("runtime_handle_is_bearer_capability", sa.Boolean(), nullable=False),
        sa.Column("runtime_handle_unexpired", sa.Boolean(), nullable=False),
        sa.Column("runtime_handle_unrevoked", sa.Boolean(), nullable=False),
        sa.Column("runtime_handle_undestroyed", sa.Boolean(), nullable=False),
        sa.Column("runtime_handle_uninjected", sa.Boolean(), nullable=False),
        sa.Column("runtime_handle_unused", sa.Boolean(), nullable=False),
        sa.Column("injection_consumption_outstanding", sa.Boolean(), nullable=False),
        sa.Column("destination_generation_current", sa.Boolean(), nullable=False),
        sa.Column("destination_fence_current", sa.Boolean(), nullable=False),
        sa.Column("injector_profile_eligible", sa.Boolean(), nullable=False),
        sa.Column("runtime_slot_profile_eligible", sa.Boolean(), nullable=False),
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
        _source_fk("fk_wf_rtctx_inj_auth_lease_result"),
        sa.UniqueConstraint("access_result_id", name="uq_wf_rtctx_inj_auth_lease_result"),
        sa.UniqueConstraint(
            "protected_runtime_handle_id", name="uq_wf_rtctx_inj_auth_lease_handle"
        ),
        sa.UniqueConstraint("claim_id", name="uq_wf_rtctx_inj_auth_lease_claim"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rtctx_inj_auth_lease_digest"),
        sa.UniqueConstraint(
            "authorization_lease_id",
            "access_result_id",
            "protected_runtime_handle_id",
            name="uq_wf_rtctx_inj_auth_lease_claim_lineage",
        ),
        sa.CheckConstraint(_contract_check(), name="ck_wf_rtctx_inj_auth_lease_contract"),
        sa.CheckConstraint(_source_check(), name="ck_wf_rtctx_inj_auth_lease_source"),
        sa.CheckConstraint(
            "state = 'authorized_unconsumed' AND single_use "
            "AND NOT renewable AND NOT transferable AND NOT lease_is_bearer_capability",
            name="ck_wf_rtctx_inj_auth_lease_state",
        ),
        sa.CheckConstraint(
            "issued_at < valid_until "
            "AND valid_until <= issued_at + INTERVAL '1 second' "
            "AND access_result_recorded_at <= pre_attestation_observed_at "
            "AND pre_attestation_observed_at <= lifecycle_attestation_observed_at "
            "AND lifecycle_attestation_observed_at <= issued_at "
            "AND valid_until <= effective_until "
            "AND effective_until <= protected_runtime_handle_usable_until "
            "AND effective_until <= lifecycle_attestation_valid_until",
            name="ck_wf_rtctx_inj_auth_lease_window",
        ),
        sa.CheckConstraint(
            "lifecycle_attestor_id = 'attestor.workflow-protected-runtime-handle-lifecycle' "
            "AND lifecycle_attestor_version = '1.0' "
            "AND lifecycle_signing_key_id = "
            "'key.workflow-protected-runtime-handle-lifecycle.v1' "
            "AND injector_contract_id = 'contract.workflow-protected-runtime-context-injector' "
            "AND injector_contract_version = '1.0' "
            "AND injector_id = 'injector.workflow-protected-runtime-context' "
            "AND injector_version = '1.0' "
            "AND runtime_slot_profile_id = 'profile.workflow-protected-runtime-context-slot' "
            "AND runtime_slot_profile_version = '1.0' "
            f"AND runtime_slot_profile_digest = '{RUNTIME_SLOT_PROFILE_DIGEST}' "
            "AND lifecycle_profile_digest = "
            "'24795b23ee48081fb91bcc09e40c281fa9ccd676db965cca291bdee4c3422a9d'",
            name="ck_wf_rtctx_inj_auth_lease_profile",
        ),
        sa.CheckConstraint(
            "runtime_handle_present AND NOT runtime_handle_is_bearer_capability "
            "AND runtime_handle_unexpired AND runtime_handle_unrevoked "
            "AND runtime_handle_undestroyed AND runtime_handle_uninjected "
            "AND runtime_handle_unused AND NOT injection_consumption_outstanding "
            "AND destination_generation_current AND destination_fence_current "
            "AND injector_profile_eligible "
            "AND runtime_slot_profile_eligible",
            name="ck_wf_rtctx_inj_auth_lease_lifecycle",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(lifecycle_attestation_payload) = 'object' "
            "AND lifecycle_attestation_payload <> '{}'::jsonb",
            name="ck_wf_rtctx_inj_auth_lease_attestation",
        ),
        sa.CheckConstraint(_lease_authority_check(), name="ck_wf_rtctx_inj_auth_lease_authority"),
    )
    op.create_index(
        "ix_wf_rtctx_inj_auth_lease_scope",
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
        sa.Column("pre_attestation_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("authorization_audit_payload", postgresql.JSONB(), nullable=False),
        _source_fk("fk_wf_rtctx_inj_auth_claim_result"),
        sa.ForeignKeyConstraint(
            ["authorization_lease_id", "access_result_id", "protected_runtime_handle_id"],
            [
                f"{LEASE_TABLE}.authorization_lease_id",
                f"{LEASE_TABLE}.access_result_id",
                f"{LEASE_TABLE}.protected_runtime_handle_id",
            ],
            name="fk_wf_rtctx_inj_auth_claim_lease",
        ),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_rtctx_inj_auth_claim_lease"),
        sa.UniqueConstraint("access_result_id", name="uq_wf_rtctx_inj_auth_claim_result"),
        sa.UniqueConstraint(
            "protected_runtime_handle_id", name="uq_wf_rtctx_inj_auth_claim_handle"
        ),
        sa.UniqueConstraint(
            "idempotency_scope_id", "idempotency_key", name="uq_wf_rtctx_inj_auth_scope_idem"
        ),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rtctx_inj_auth_claim_digest"),
        sa.UniqueConstraint(
            "claim_id",
            "canonical_digest",
            "authorization_lease_id",
            name="uq_wf_rtctx_inj_auth_claim_lease_lineage",
        ),
        sa.CheckConstraint(_contract_check(), name="ck_wf_rtctx_inj_auth_claim_contract"),
        sa.CheckConstraint(_source_check(), name="ck_wf_rtctx_inj_auth_claim_source"),
        sa.CheckConstraint(
            "access_result_recorded_at <= claimed_at "
            "AND access_result_recorded_at <= pre_attestation_observed_at "
            "AND pre_attestation_observed_at <= claimed_at "
            "AND claimed_at < protected_runtime_handle_usable_until",
            name="ck_wf_rtctx_inj_auth_claim_window",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(authorization_audit_payload) = 'object' "
            "AND authorization_audit_payload <> '{}'::jsonb",
            name="ck_wf_rtctx_inj_auth_claim_audit",
        ),
        sa.CheckConstraint(_claim_authority_check(), name="ck_wf_rtctx_inj_auth_claim_authority"),
    )
    op.create_index(
        "ix_wf_rtctx_inj_auth_claim_scope",
        CLAIM_TABLE,
        ["organization_id", "environment_id", "site_id", "claimed_at"],
    )
    op.create_foreign_key(
        "fk_wf_rtctx_inj_auth_lease_claim",
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
            RAISE EXCEPTION 'runtime-context injection authorization evidence is append-only'
                USING ERRCODE = '55000';
        END;
        $$
    """)
    )
    for table, trigger in (
        (LEASE_TABLE, "trg_wf_rtctx_inj_auth_lease_append_only"),
        (CLAIM_TABLE, "trg_wf_rtctx_inj_auth_claim_append_only"),
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
                    'refusing guarded downgrade: runtime-context injection authorization evidence exists'
                    USING ERRCODE = '55000';
            END IF;
        END $$;
    """)
    )
    op.drop_constraint(
        "fk_wf_rtctx_inj_auth_lease_claim",
        LEASE_TABLE,
        type_="foreignkey",
    )
    op.drop_table(CLAIM_TABLE)
    op.drop_table(LEASE_TABLE)
    op.drop_table(DESTINATION_HEAD_TABLE)
    op.drop_constraint(
        "uq_wf_rc_access_result_injection_auth_lineage",
        SOURCE_RESULT_TABLE,
        type_="unique",
    )
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {APPEND_ONLY_FUNCTION}()"))
