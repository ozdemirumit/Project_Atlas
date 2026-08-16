"""Add atomic protected runtime-context injection consumption evidence.

Revision ID: 20260816_0142
Revises: 20260816_0141
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260816_0142"
down_revision: str | None = "20260816_0141"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUTH_LEASE_TABLE = "workflow_event_runtime_context_injection_auth_leases"
SLOT_HEAD_TABLE = "workflow_protected_runtime_context_injection_slot_heads"
CLAIM_TABLE = "workflow_event_runtime_context_injection_consumption_claims"
ATTEMPT_TABLE = "workflow_event_runtime_context_injection_attempts"
RESULT_TABLE = "workflow_event_runtime_context_injection_results"
APPEND_ONLY_FUNCTION = "reject_wf_rtctx_inj_consume_mutation"

POLICY_DIGEST = "1a8e963fcb95a15bdc2dcfcc0bd613bbfab3f12a23faedcebff777d65bcc24d4"
RUNTIME_HANDLE_PROFILE_DIGEST = "1a318541a6303a5caf48131a737b1e79f458c7442498fa8dcc83f7f137e63e8a"
RUNTIME_SLOT_PROFILE_DIGEST = "7c429ec36bd39f5d02add24b7622e55e32eb0cfca9345ebf272fd231385e3e6b"
INITIAL_SLOT_COMMITMENT = "24ef9e4c15509cd067e74c8e95c5cf0aeb94788b418cb94651f5c852a5b51c0a"
INITIAL_SLOT_HEAD_DIGEST = "f12434a400f6ca68b10c939c69ea4c4ea6ffdb5b3fb70cb068a439c4cf9c5349"


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
        "runtime_use_authorized",
    )


def _authority_columns() -> tuple[sa.Column[object], ...]:
    return tuple(sa.Column(name, sa.Boolean(), nullable=False) for name in _authority_names())


def _zero_authority_check() -> str:
    return " AND ".join(f"NOT {name}" for name in _authority_names())


def _authorization_lineage_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("authorization_lease_id", sa.String(128), nullable=False),
        sa.Column("authorization_lease_digest", sa.String(64), nullable=False),
        sa.Column("authorization_claim_id", sa.String(128), nullable=False),
        sa.Column("authorization_claim_digest", sa.String(64), nullable=False),
        sa.Column("access_result_id", sa.String(128), nullable=False),
        sa.Column("access_result_digest", sa.String(64), nullable=False),
        sa.Column("protected_runtime_handle_digest", sa.String(64), nullable=False),
        sa.Column("destination_boundary_id", sa.String(128), nullable=False),
        sa.Column("destination_deployment_id", sa.String(128), nullable=False),
        sa.Column("destination_generation", sa.Integer(), nullable=False),
        sa.Column("destination_fencing_token_digest", sa.String(64), nullable=False),
        sa.Column("runtime_handle_profile_digest", sa.String(64), nullable=False),
        sa.Column("runtime_slot_profile_digest", sa.String(64), nullable=False),
        sa.Column("authorization_lease_valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "authorization_lease_effective_until", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "protected_runtime_handle_usable_until", sa.DateTime(timezone=True), nullable=False
        ),
    )


def _slot_snapshot_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("runtime_slot_commitment", sa.String(64), nullable=False),
        sa.Column("runtime_slot_pre_generation", sa.Integer(), nullable=False),
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


def _contract_check() -> str:
    return (
        "consumer_subject_id = 'service.workflow-protected-transport-target-context-capsule-consumer' "
        "AND consumer_audience = 'audience.workflow-protected-transport-target-context-capsule-consumer' "
        "AND consumer_contract_id = 'contract.workflow-protected-transport-target-context-capsule-consumer' "
        "AND consumer_contract_version = '1.0' "
        "AND purpose_id = 'purpose.workflow-protected-runtime-context-injection-consumption' "
        "AND policy_id = 'policy.workflow-protected-runtime-context-injection-consumption' "
        f"AND policy_version = '1.0' AND policy_digest = '{POLICY_DIGEST}'"
    )


def _authorization_fk(name: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [
            "authorization_lease_id",
            "authorization_lease_digest",
            "authorization_claim_id",
            "authorization_claim_digest",
            "access_result_id",
            "access_result_digest",
            "protected_runtime_handle_digest",
            "destination_boundary_id",
            "destination_deployment_id",
            "destination_generation",
            "destination_fencing_token_digest",
            "runtime_handle_profile_digest",
            "runtime_slot_profile_digest",
            "authorization_lease_valid_until",
            "authorization_lease_effective_until",
            "protected_runtime_handle_usable_until",
        ],
        [
            f"{AUTH_LEASE_TABLE}.authorization_lease_id",
            f"{AUTH_LEASE_TABLE}.canonical_digest",
            f"{AUTH_LEASE_TABLE}.claim_id",
            f"{AUTH_LEASE_TABLE}.claim_digest",
            f"{AUTH_LEASE_TABLE}.access_result_id",
            f"{AUTH_LEASE_TABLE}.access_result_digest",
            f"{AUTH_LEASE_TABLE}.protected_runtime_handle_digest",
            f"{AUTH_LEASE_TABLE}.destination_boundary_id",
            f"{AUTH_LEASE_TABLE}.destination_deployment_id",
            f"{AUTH_LEASE_TABLE}.destination_generation",
            f"{AUTH_LEASE_TABLE}.destination_fencing_token_digest",
            f"{AUTH_LEASE_TABLE}.runtime_handle_profile_digest",
            f"{AUTH_LEASE_TABLE}.runtime_slot_profile_digest",
            f"{AUTH_LEASE_TABLE}.valid_until",
            f"{AUTH_LEASE_TABLE}.effective_until",
            f"{AUTH_LEASE_TABLE}.protected_runtime_handle_usable_until",
        ],
        name=name,
        deferrable=True,
        initially="DEFERRED",
    )


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_wf_rtctx_inj_auth_consume_lineage",
        AUTH_LEASE_TABLE,
        [
            "authorization_lease_id",
            "canonical_digest",
            "claim_id",
            "claim_digest",
            "access_result_id",
            "access_result_digest",
            "protected_runtime_handle_digest",
            "destination_boundary_id",
            "destination_deployment_id",
            "destination_generation",
            "destination_fencing_token_digest",
            "runtime_handle_profile_digest",
            "runtime_slot_profile_digest",
            "valid_until",
            "effective_until",
            "protected_runtime_handle_usable_until",
        ],
    )

    slot_payload = {
        "destination_boundary_id": "boundary.workflow-protected-target-context-capsule-consumer",
        "destination_deployment_id": "deployment.workflow-protected-target-context-capsule-consumer",
        "destination_generation": 1,
        "destination_fencing_token_digest": (
            "701153578261c45c3f1faa89f75b4a3f7003126683ddb895c0346aac0f9148e7"
        ),
        "runtime_slot_commitment": INITIAL_SLOT_COMMITMENT,
        "runtime_slot_profile_digest": RUNTIME_SLOT_PROFILE_DIGEST,
        "slot_generation": 0,
        "slot_state": "empty_inert",
    }
    slot_head = op.create_table(
        SLOT_HEAD_TABLE,
        sa.Column("destination_deployment_id", sa.String(128), primary_key=True),
        sa.Column("runtime_slot_commitment", sa.String(64), primary_key=True),
        sa.Column("destination_boundary_id", sa.String(128), nullable=False),
        sa.Column("destination_generation", sa.Integer(), nullable=False),
        sa.Column("destination_fencing_token_digest", sa.String(64), nullable=False),
        sa.Column("runtime_slot_profile_digest", sa.String(64), nullable=False),
        sa.Column("slot_generation", sa.Integer(), nullable=False),
        sa.Column("slot_state", sa.String(64), nullable=False),
        sa.Column("current", sa.Boolean(), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.UniqueConstraint(
            "destination_deployment_id",
            "runtime_slot_commitment",
            name="uq_wf_rtctx_inj_slot_head_commitment",
        ),
        sa.CheckConstraint(
            "destination_boundary_id = 'boundary.workflow-protected-target-context-capsule-consumer' "
            "AND destination_deployment_id = 'deployment.workflow-protected-target-context-capsule-consumer' "
            "AND destination_generation >= 1 "
            "AND length(destination_fencing_token_digest) = 64 "
            "AND length(runtime_slot_commitment) = 64 "
            f"AND runtime_slot_profile_digest = '{RUNTIME_SLOT_PROFILE_DIGEST}' "
            "AND slot_generation >= 0 "
            "AND slot_state IN ('empty_inert', 'inert_context_present', 'outcome_uncertain') "
            "AND current",
            name="ck_wf_rtctx_inj_slot_head_contract",
        ),
        sa.CheckConstraint(
            "length(canonical_digest) = 64 AND payload = jsonb_build_object("
            "'destination_boundary_id', destination_boundary_id, "
            "'destination_deployment_id', destination_deployment_id, "
            "'destination_generation', destination_generation, "
            "'destination_fencing_token_digest', destination_fencing_token_digest, "
            "'runtime_slot_commitment', runtime_slot_commitment, "
            "'runtime_slot_profile_digest', runtime_slot_profile_digest, "
            "'slot_generation', slot_generation, 'slot_state', slot_state)",
            name="ck_wf_rtctx_inj_slot_head_payload",
        ),
    )
    op.create_index(
        "ix_wf_rtctx_inj_slot_head_lock",
        SLOT_HEAD_TABLE,
        [
            "destination_boundary_id",
            "destination_deployment_id",
            "runtime_slot_commitment",
            "slot_generation",
        ],
        unique=True,
    )
    op.bulk_insert(
        slot_head,
        [
            {
                **slot_payload,
                "current": True,
                "canonical_digest": INITIAL_SLOT_HEAD_DIGEST,
                "payload": slot_payload,
            }
        ],
    )

    op.create_table(
        CLAIM_TABLE,
        sa.Column("claim_id", sa.String(128), primary_key=True),
        sa.Column("injection_id", sa.String(128), nullable=False),
        sa.Column("attempt_id", sa.String(128), nullable=False),
        *_authorization_lineage_columns(),
        *_slot_snapshot_columns(),
        *_scope_columns(),
        *_identity_policy_columns(),
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
        _authorization_fk("fk_wf_rtctx_inj_consume_auth_lease"),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_rtctx_inj_consume_lease"),
        sa.UniqueConstraint(
            "protected_runtime_handle_digest", name="uq_wf_rtctx_inj_consume_handle"
        ),
        sa.UniqueConstraint(
            "destination_deployment_id",
            "runtime_slot_commitment",
            "runtime_slot_pre_generation",
            name="uq_wf_rtctx_inj_consume_slot_generation",
        ),
        sa.UniqueConstraint("injection_id", name="uq_wf_rtctx_inj_consume_operation"),
        sa.UniqueConstraint("attempt_id", name="uq_wf_rtctx_inj_consume_attempt"),
        sa.UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_rtctx_inj_consume_scope_idem",
        ),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rtctx_inj_consume_digest"),
        sa.UniqueConstraint(
            "claim_id",
            "canonical_digest",
            "injection_id",
            "attempt_id",
            "authorization_lease_id",
            "authorization_lease_digest",
            "protected_runtime_handle_digest",
            "destination_deployment_id",
            "runtime_slot_commitment",
            "runtime_slot_pre_generation",
            "claimed_at",
            name="uq_wf_rtctx_inj_consume_claim_lineage",
        ),
        sa.CheckConstraint(_contract_check(), name="ck_wf_rtctx_inj_consume_contract"),
        sa.CheckConstraint(
            "irreversible_consumption_acknowledged "
            "AND uncertain_outcome_requires_new_authorization_acknowledged",
            name="ck_wf_rtctx_inj_consume_ack",
        ),
        sa.CheckConstraint(
            "claimed_at < authorization_lease_valid_until "
            "AND claimed_at < authorization_lease_effective_until "
            "AND claimed_at < protected_runtime_handle_usable_until "
            "AND runtime_slot_pre_generation >= 0 "
            "AND length(runtime_slot_commitment) = 64",
            name="ck_wf_rtctx_inj_consume_window_slot",
        ),
        sa.CheckConstraint(
            "runtime_handle_profile_digest = "
            f"'{RUNTIME_HANDLE_PROFILE_DIGEST}' "
            f"AND runtime_slot_profile_digest = '{RUNTIME_SLOT_PROFILE_DIGEST}'",
            name="ck_wf_rtctx_inj_consume_profiles",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(consumption_authorization_audit_payload) = 'object' "
            "AND consumption_authorization_audit_payload <> '{}'::jsonb",
            name="ck_wf_rtctx_inj_consume_audit",
        ),
        sa.CheckConstraint(_zero_authority_check(), name="ck_wf_rtctx_inj_consume_authority"),
    )
    op.create_index(
        "ix_wf_rtctx_inj_consume_scope",
        CLAIM_TABLE,
        ["organization_id", "environment_id", "site_id", "claimed_at"],
    )

    op.create_table(
        ATTEMPT_TABLE,
        sa.Column("attempt_id", sa.String(128), primary_key=True),
        sa.Column("injection_id", sa.String(128), nullable=False),
        sa.Column("consumption_claim_id", sa.String(128), nullable=False),
        sa.Column("consumption_claim_digest", sa.String(64), nullable=False),
        *_authorization_lineage_columns(),
        *_slot_snapshot_columns(),
        *_scope_columns(),
        *_identity_policy_columns(),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("protected_operation_reference", sa.String(128), nullable=False),
        sa.Column("instruction_digest", sa.String(64), nullable=False),
        sa.Column("lifecycle_attestation_id", sa.String(128), nullable=False),
        sa.Column("lifecycle_attestation_digest", sa.String(64), nullable=False),
        sa.Column("lifecycle_signing_key_id", sa.String(128), nullable=False),
        sa.Column("lifecycle_attestation_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lifecycle_attestation_valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("slot_readiness_attestation_id", sa.String(128), nullable=False),
        sa.Column("slot_readiness_attestation_digest", sa.String(64), nullable=False),
        sa.Column("slot_readiness_signing_key_id", sa.String(128), nullable=False),
        sa.Column(
            "slot_readiness_attestation_observed_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "slot_readiness_attestation_valid_until", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("runtime_slot_profile_id", sa.String(128), nullable=False),
        sa.Column("runtime_slot_profile_version", sa.String(64), nullable=False),
        sa.Column("expected_runtime_slot_post_generation", sa.Integer(), nullable=False),
        sa.Column("required_injector_contract_id", sa.String(128), nullable=False),
        sa.Column("required_injector_contract_version", sa.String(64), nullable=False),
        sa.Column("approved_injector_id", sa.String(128), nullable=False),
        sa.Column("approved_injector_version", sa.String(64), nullable=False),
        sa.Column("receipt_verification_signing_key_id", sa.String(128), nullable=False),
        sa.Column("request_nonce_digest", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("injection_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(64), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("lifecycle_attestation_payload", postgresql.JSONB(), nullable=False),
        sa.Column("slot_readiness_attestation_payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            [
                "consumption_claim_id",
                "consumption_claim_digest",
                "injection_id",
                "attempt_id",
                "authorization_lease_id",
                "authorization_lease_digest",
                "protected_runtime_handle_digest",
                "destination_deployment_id",
                "runtime_slot_commitment",
                "runtime_slot_pre_generation",
                "claimed_at",
            ],
            [
                f"{CLAIM_TABLE}.claim_id",
                f"{CLAIM_TABLE}.canonical_digest",
                f"{CLAIM_TABLE}.injection_id",
                f"{CLAIM_TABLE}.attempt_id",
                f"{CLAIM_TABLE}.authorization_lease_id",
                f"{CLAIM_TABLE}.authorization_lease_digest",
                f"{CLAIM_TABLE}.protected_runtime_handle_digest",
                f"{CLAIM_TABLE}.destination_deployment_id",
                f"{CLAIM_TABLE}.runtime_slot_commitment",
                f"{CLAIM_TABLE}.runtime_slot_pre_generation",
                f"{CLAIM_TABLE}.claimed_at",
            ],
            name="fk_wf_rtctx_inj_attempt_claim_lineage",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.UniqueConstraint("consumption_claim_id", name="uq_wf_rtctx_inj_attempt_claim"),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_rtctx_inj_attempt_lease"),
        sa.UniqueConstraint(
            "protected_runtime_handle_digest", name="uq_wf_rtctx_inj_attempt_handle"
        ),
        sa.UniqueConstraint(
            "destination_deployment_id",
            "runtime_slot_commitment",
            "runtime_slot_pre_generation",
            name="uq_wf_rtctx_inj_attempt_slot_generation",
        ),
        sa.UniqueConstraint("injection_id", name="uq_wf_rtctx_inj_attempt_operation"),
        sa.UniqueConstraint("instruction_digest", name="uq_wf_rtctx_inj_attempt_instruction"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rtctx_inj_attempt_digest"),
        sa.UniqueConstraint(
            "attempt_id",
            "canonical_digest",
            "injection_id",
            "consumption_claim_id",
            "consumption_claim_digest",
            "authorization_lease_id",
            "authorization_lease_digest",
            "protected_runtime_handle_digest",
            "destination_boundary_id",
            "destination_deployment_id",
            "destination_generation",
            "destination_fencing_token_digest",
            "runtime_slot_commitment",
            "runtime_slot_pre_generation",
            "runtime_slot_profile_digest",
            "started_at",
            "injection_deadline",
            name="uq_wf_rtctx_inj_attempt_result_lineage",
        ),
        sa.CheckConstraint(_contract_check(), name="ck_wf_rtctx_inj_attempt_contract"),
        sa.CheckConstraint("state = 'started'", name="ck_wf_rtctx_inj_attempt_state"),
        sa.CheckConstraint(
            "claimed_at <= lifecycle_attestation_observed_at "
            "AND claimed_at <= slot_readiness_attestation_observed_at "
            "AND lifecycle_attestation_observed_at <= started_at "
            "AND slot_readiness_attestation_observed_at <= started_at "
            "AND started_at < injection_deadline "
            "AND injection_deadline <= authorization_lease_valid_until "
            "AND injection_deadline <= authorization_lease_effective_until "
            "AND injection_deadline <= protected_runtime_handle_usable_until "
            "AND injection_deadline <= lifecycle_attestation_valid_until "
            "AND injection_deadline <= slot_readiness_attestation_valid_until",
            name="ck_wf_rtctx_inj_attempt_window",
        ),
        sa.CheckConstraint(
            "required_injector_contract_id = 'contract.workflow-protected-runtime-context-injector' "
            "AND required_injector_contract_version = '1.0' "
            "AND approved_injector_id = 'injector.workflow-protected-runtime-context' "
            "AND approved_injector_version = '1.0' "
            "AND lifecycle_signing_key_id = 'key.workflow-protected-runtime-handle-lifecycle.v1' "
            "AND slot_readiness_signing_key_id = 'key.workflow-protected-runtime-context-slot-readiness.v1' "
            "AND receipt_verification_signing_key_id = 'key.workflow-protected-runtime-context-injection-receipt.v1' "
            "AND runtime_slot_profile_id = 'profile.workflow-protected-runtime-context-slot' "
            "AND runtime_slot_profile_version = '1.0' "
            "AND expected_runtime_slot_post_generation = runtime_slot_pre_generation + 1",
            name="ck_wf_rtctx_inj_attempt_injector",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(lifecycle_attestation_payload) = 'object' "
            "AND lifecycle_attestation_payload <> '{}'::jsonb "
            "AND jsonb_typeof(slot_readiness_attestation_payload) = 'object' "
            "AND slot_readiness_attestation_payload <> '{}'::jsonb",
            name="ck_wf_rtctx_inj_attempt_attestations",
        ),
        sa.CheckConstraint(_zero_authority_check(), name="ck_wf_rtctx_inj_attempt_authority"),
    )
    op.create_index(
        "ix_wf_rtctx_inj_attempt_scope",
        ATTEMPT_TABLE,
        ["organization_id", "environment_id", "site_id", "started_at"],
    )

    op.create_table(
        RESULT_TABLE,
        sa.Column("result_id", sa.String(128), primary_key=True),
        sa.Column("injection_id", sa.String(128), nullable=False),
        sa.Column("attempt_id", sa.String(128), nullable=False),
        sa.Column("attempt_digest", sa.String(64), nullable=False),
        sa.Column("consumption_claim_id", sa.String(128), nullable=False),
        sa.Column("consumption_claim_digest", sa.String(64), nullable=False),
        sa.Column("authorization_lease_id", sa.String(128), nullable=False),
        sa.Column("authorization_lease_digest", sa.String(64), nullable=False),
        sa.Column("protected_runtime_handle_digest", sa.String(64), nullable=False),
        sa.Column("destination_boundary_id", sa.String(128), nullable=False),
        sa.Column("destination_deployment_id", sa.String(128), nullable=False),
        sa.Column("destination_generation", sa.Integer(), nullable=False),
        sa.Column("destination_fencing_token_digest", sa.String(64), nullable=False),
        sa.Column("runtime_slot_profile_id", sa.String(128), nullable=False),
        sa.Column("runtime_slot_profile_version", sa.String(64), nullable=False),
        sa.Column("runtime_slot_commitment", sa.String(64), nullable=False),
        sa.Column("runtime_slot_pre_generation", sa.Integer(), nullable=False),
        sa.Column("runtime_slot_profile_digest", sa.String(64), nullable=False),
        sa.Column("runtime_slot_post_generation", sa.Integer(), nullable=True),
        *_scope_columns(),
        *_identity_policy_columns(),
        sa.Column("protected_operation_reference", sa.String(128), nullable=False),
        sa.Column("instruction_digest", sa.String(64), nullable=False),
        sa.Column("injector_contract_id", sa.String(128), nullable=False),
        sa.Column("injector_contract_version", sa.String(64), nullable=False),
        sa.Column("approved_injector_id", sa.String(128), nullable=False),
        sa.Column("approved_injector_version", sa.String(64), nullable=False),
        sa.Column("receipt_verification_signing_key_id", sa.String(128), nullable=False),
        sa.Column("injector_receipt_digest", sa.String(64), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("injection_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("authorization_lease_consumed", sa.Boolean(), nullable=False),
        sa.Column("protected_runtime_handle_consumed", sa.Boolean(), nullable=True),
        sa.Column("inert_context_injected", sa.Boolean(), nullable=False),
        sa.Column("runtime_slot_mutation_performed", sa.Boolean(), nullable=False),
        sa.Column("outcome_known", sa.Boolean(), nullable=False),
        sa.Column("state", sa.String(64), nullable=False),
        sa.Column("failure_class", sa.String(64), nullable=True),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("injector_receipt_payload", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(
            [
                "attempt_id",
                "attempt_digest",
                "injection_id",
                "consumption_claim_id",
                "consumption_claim_digest",
                "authorization_lease_id",
                "authorization_lease_digest",
                "protected_runtime_handle_digest",
                "destination_boundary_id",
                "destination_deployment_id",
                "destination_generation",
                "destination_fencing_token_digest",
                "runtime_slot_commitment",
                "runtime_slot_pre_generation",
                "runtime_slot_profile_digest",
                "started_at",
                "injection_deadline",
            ],
            [
                f"{ATTEMPT_TABLE}.attempt_id",
                f"{ATTEMPT_TABLE}.canonical_digest",
                f"{ATTEMPT_TABLE}.injection_id",
                f"{ATTEMPT_TABLE}.consumption_claim_id",
                f"{ATTEMPT_TABLE}.consumption_claim_digest",
                f"{ATTEMPT_TABLE}.authorization_lease_id",
                f"{ATTEMPT_TABLE}.authorization_lease_digest",
                f"{ATTEMPT_TABLE}.protected_runtime_handle_digest",
                f"{ATTEMPT_TABLE}.destination_boundary_id",
                f"{ATTEMPT_TABLE}.destination_deployment_id",
                f"{ATTEMPT_TABLE}.destination_generation",
                f"{ATTEMPT_TABLE}.destination_fencing_token_digest",
                f"{ATTEMPT_TABLE}.runtime_slot_commitment",
                f"{ATTEMPT_TABLE}.runtime_slot_pre_generation",
                f"{ATTEMPT_TABLE}.runtime_slot_profile_digest",
                f"{ATTEMPT_TABLE}.started_at",
                f"{ATTEMPT_TABLE}.injection_deadline",
            ],
            name="fk_wf_rtctx_inj_result_attempt_lineage",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.UniqueConstraint("attempt_id", name="uq_wf_rtctx_inj_result_attempt"),
        sa.UniqueConstraint("consumption_claim_id", name="uq_wf_rtctx_inj_result_claim"),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_rtctx_inj_result_lease"),
        sa.UniqueConstraint("injection_id", name="uq_wf_rtctx_inj_result_operation"),
        sa.UniqueConstraint(
            "protected_runtime_handle_digest", name="uq_wf_rtctx_inj_result_handle"
        ),
        sa.UniqueConstraint(
            "destination_deployment_id",
            "runtime_slot_commitment",
            "runtime_slot_pre_generation",
            name="uq_wf_rtctx_inj_result_slot_generation",
        ),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rtctx_inj_result_digest"),
        sa.CheckConstraint(_contract_check(), name="ck_wf_rtctx_inj_result_contract"),
        sa.CheckConstraint(
            "claimed_at <= started_at "
            "AND ((state = 'injection_outcome_uncertain' "
            "AND completed_at IS NULL AND recorded_at >= injection_deadline) "
            "OR (completed_at IS NOT NULL AND started_at <= completed_at "
            "AND completed_at <= recorded_at AND completed_at < injection_deadline))",
            name="ck_wf_rtctx_inj_result_chronology",
        ),
        sa.CheckConstraint(
            "authorization_lease_consumed",
            name="ck_wf_rtctx_inj_result_consumed",
        ),
        sa.CheckConstraint(
            "runtime_slot_profile_digest = "
            f"'{RUNTIME_SLOT_PROFILE_DIGEST}' "
            "AND runtime_slot_profile_id = 'profile.workflow-protected-runtime-context-slot' "
            "AND runtime_slot_profile_version = '1.0' "
            "AND length(destination_fencing_token_digest) = 64 "
            "AND length(runtime_slot_commitment) = 64",
            name="ck_wf_rtctx_inj_result_profile_fence",
        ),
        sa.CheckConstraint(
            "(state = 'injected_into_protected_runtime_slot' "
            "AND failure_class IS NULL AND outcome_known "
            "AND injector_receipt_digest IS NOT NULL "
            "AND injector_receipt_payload IS NOT NULL "
            "AND COALESCE((injector_receipt_payload ->> 'canonical_digest') = injector_receipt_digest, FALSE) "
            "AND COALESCE((injector_receipt_payload ->> 'signing_key_id') = receipt_verification_signing_key_id, FALSE) "
            "AND length(COALESCE(injector_receipt_payload ->> 'integrity_signature', '')) > 0 "
            "AND COALESCE((injector_receipt_payload ->> 'instruction_digest') = instruction_digest, FALSE) "
            "AND COALESCE((injector_receipt_payload ->> 'protected_operation_reference') = protected_operation_reference, FALSE) "
            "AND runtime_slot_post_generation = runtime_slot_pre_generation + 1 "
            "AND protected_runtime_handle_consumed "
            "AND runtime_slot_mutation_performed AND inert_context_injected "
            "AND COALESCE((injector_receipt_payload ->> 'temporary_material_zeroized')::boolean, FALSE) "
            'AND injector_receipt_payload @> \'{"runtime_started": false, "runtime_resumed": false, "filesystem_activity_performed": false, "provider_activity_performed": false, "connector_activity_performed": false, "network_activity_performed": false, "readiness_probe_performed": false, "publication_performed": false, "delivery_performed": false, "dispatch_performed": false, "execution_performed": false, "infrastructure_mutation_performed": false}\'::jsonb) OR '
            "(state = 'injection_failed' "
            "AND failure_class IS NOT NULL AND outcome_known "
            "AND injector_receipt_digest IS NOT NULL "
            "AND injector_receipt_payload IS NOT NULL "
            "AND COALESCE((injector_receipt_payload ->> 'canonical_digest') = injector_receipt_digest, FALSE) "
            "AND COALESCE((injector_receipt_payload ->> 'signing_key_id') = receipt_verification_signing_key_id, FALSE) "
            "AND length(COALESCE(injector_receipt_payload ->> 'integrity_signature', '')) > 0 "
            "AND COALESCE((injector_receipt_payload ->> 'instruction_digest') = instruction_digest, FALSE) "
            "AND COALESCE((injector_receipt_payload ->> 'protected_operation_reference') = protected_operation_reference, FALSE) "
            "AND runtime_slot_post_generation = runtime_slot_pre_generation "
            "AND NOT protected_runtime_handle_consumed "
            "AND NOT runtime_slot_mutation_performed AND NOT inert_context_injected "
            "AND COALESCE((injector_receipt_payload ->> 'temporary_material_zeroized')::boolean, FALSE) "
            'AND injector_receipt_payload @> \'{"runtime_started": false, "runtime_resumed": false, "filesystem_activity_performed": false, "provider_activity_performed": false, "connector_activity_performed": false, "network_activity_performed": false, "readiness_probe_performed": false, "publication_performed": false, "delivery_performed": false, "dispatch_performed": false, "execution_performed": false, "infrastructure_mutation_performed": false}\'::jsonb) OR '
            "(state = 'injection_outcome_uncertain' "
            "AND failure_class = 'injection_outcome_uncertain' AND NOT outcome_known "
            "AND injector_receipt_digest IS NULL AND injector_receipt_payload IS NULL "
            "AND runtime_slot_post_generation IS NULL "
            "AND protected_runtime_handle_consumed IS NULL "
            "AND NOT runtime_slot_mutation_performed AND NOT inert_context_injected)",
            name="ck_wf_rtctx_inj_result_outcome",
        ),
        sa.CheckConstraint(
            "injector_contract_id = 'contract.workflow-protected-runtime-context-injector' "
            "AND injector_contract_version = '1.0' "
            "AND approved_injector_id = 'injector.workflow-protected-runtime-context' "
            "AND approved_injector_version = '1.0' "
            "AND receipt_verification_signing_key_id = 'key.workflow-protected-runtime-context-injection-receipt.v1'",
            name="ck_wf_rtctx_inj_result_injector",
        ),
        sa.CheckConstraint(_zero_authority_check(), name="ck_wf_rtctx_inj_result_authority"),
    )
    op.create_index(
        "ix_wf_rtctx_inj_result_scope",
        RESULT_TABLE,
        ["organization_id", "environment_id", "site_id", "recorded_at"],
    )

    op.execute(
        sa.text(f"""
        CREATE FUNCTION {APPEND_ONLY_FUNCTION}() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'runtime-context injection consumption evidence is append-only'
                USING ERRCODE = '55000';
        END;
        $$
    """)
    )
    for table, trigger in (
        (CLAIM_TABLE, "trg_wf_rtctx_inj_consume_append_only"),
        (ATTEMPT_TABLE, "trg_wf_rtctx_inj_attempt_append_only"),
        (RESULT_TABLE, "trg_wf_rtctx_inj_result_append_only"),
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
               OR EXISTS (SELECT 1 FROM {RESULT_TABLE} LIMIT 1)
               OR EXISTS (
                   SELECT 1 FROM {SLOT_HEAD_TABLE}
                   WHERE slot_generation <> 0 OR slot_state <> 'empty_inert'
               ) THEN
                RAISE EXCEPTION
                    'refusing guarded downgrade: runtime-context injection consumption evidence exists'
                    USING ERRCODE = '55000';
            END IF;
        END $$;
    """)
    )
    op.drop_table(RESULT_TABLE)
    op.drop_table(ATTEMPT_TABLE)
    op.drop_table(CLAIM_TABLE)
    op.drop_table(SLOT_HEAD_TABLE)
    op.drop_constraint(
        "uq_wf_rtctx_inj_auth_consume_lineage",
        AUTH_LEASE_TABLE,
        type_="unique",
    )
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {APPEND_ONLY_FUNCTION}()"))
