"""Add single-use protected runtime-context adoption evidence.

Revision ID: 20260817_0145
Revises: 20260817_0144
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260817_0145"
down_revision: str | None = "20260817_0144"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUTH_CLAIM_TABLE = "workflow_event_runtime_context_use_auth_consumption_claims"
AUTH_RESULT_TABLE = "workflow_event_runtime_context_use_auth_consumption_results"
SLOT_HEAD_TABLE = "workflow_protected_runtime_context_injection_slot_heads"
CLAIM_TABLE = "workflow_protected_runtime_context_use_claims"
ATTEMPT_TABLE = "workflow_protected_runtime_context_use_attempts"
RESULT_TABLE = "workflow_protected_runtime_context_use_results"
APPEND_ONLY_FUNCTION = "reject_wf_rtctx_use_mutation"

POLICY_DIGEST = "3be4b37122db97ca4288fdc5cc88af15224069e5257e46a8c198d9e0069f298a"
USE_PROFILE_DIGEST = "833b75839dd35cb6d4f84e64b1d414aef380a081f4a066e391485a047edddd84"
SOURCE_NAMES = (
    "authorization_consumption_result_id",
    "authorization_consumption_result_digest",
    "authorization_consumption_id",
    "authorization_consumption_claim_id",
    "authorization_consumption_claim_digest",
    "authorization_lease_id",
    "authorization_lease_digest",
    "injection_result_id",
    "injection_result_digest",
    "destination_deployment_id",
    "destination_generation",
    "destination_fencing_token_digest",
    "runtime_slot_commitment",
    "runtime_slot_pre_generation",
    "injected_context_usable_until",
    "use_profile_id",
    "use_profile_version",
    "use_profile_digest",
    "authorization_consumed_at",
)
IDENTITY_NAMES = (
    "organization_id",
    "environment_id",
    "site_id",
    "consumer_subject_id",
    "consumer_audience",
    "consumer_contract_id",
    "consumer_contract_version",
    "purpose_id",
    "policy_id",
    "policy_version",
    "policy_digest",
    "source_policy_id",
    "source_policy_version",
    "source_policy_digest",
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


def _zero_authority_check() -> str:
    return " AND ".join(f"NOT {name}" for name in _authority_names())


def _identity_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("environment_id", sa.String(128), nullable=False),
        sa.Column("site_id", sa.String(128), nullable=False),
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
        sa.Column("authorization_consumption_result_id", sa.String(128), nullable=False),
        sa.Column("authorization_consumption_result_digest", sa.String(64), nullable=False),
        sa.Column("authorization_consumption_id", sa.String(128), nullable=False),
        sa.Column("authorization_consumption_claim_id", sa.String(128), nullable=False),
        sa.Column("authorization_consumption_claim_digest", sa.String(64), nullable=False),
        sa.Column("authorization_lease_id", sa.String(128), nullable=False),
        sa.Column("authorization_lease_digest", sa.String(64), nullable=False),
        sa.Column("injection_result_id", sa.String(128), nullable=False),
        sa.Column("injection_result_digest", sa.String(64), nullable=False),
        sa.Column("destination_deployment_id", sa.String(128), nullable=False),
        sa.Column("destination_generation", sa.Integer(), nullable=False),
        sa.Column("destination_fencing_token_digest", sa.String(64), nullable=False),
        sa.Column("runtime_slot_commitment", sa.String(64), nullable=False),
        sa.Column("runtime_slot_pre_generation", sa.Integer(), nullable=False),
        sa.Column("injected_context_usable_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("use_profile_id", sa.String(128), nullable=False),
        sa.Column("use_profile_version", sa.String(64), nullable=False),
        sa.Column("use_profile_digest", sa.String(64), nullable=False),
        sa.Column("authorization_consumed_at", sa.DateTime(timezone=True), nullable=False),
    )


def _contract_check() -> str:
    return (
        "consumer_subject_id = 'service.workflow-protected-transport-target-context-capsule-consumer' "
        "AND consumer_audience = 'audience.workflow-protected-transport-target-context-capsule-consumer' "
        "AND consumer_contract_id = 'contract.workflow-protected-transport-target-context-capsule-consumer' "
        "AND consumer_contract_version = '1.0' "
        "AND purpose_id = 'purpose.workflow-protected-runtime-context-use' "
        "AND policy_id = 'policy.workflow-protected-runtime-context-use' "
        f"AND policy_version = '1.0' AND policy_digest = '{POLICY_DIGEST}' "
        "AND source_policy_id = 'policy.workflow-protected-runtime-context-use-authorization-consumption' "
        "AND source_policy_version = '1.0' "
        "AND source_policy_digest = '7dd60d9cae7725c6c41175945c391cedf17d6fbadf2e1735119c037bdd3063fd'"
    )


def _source_foreign_keys() -> tuple[sa.ForeignKeyConstraint, ...]:
    return (
        sa.ForeignKeyConstraint(
            [
                "authorization_consumption_result_id",
                "authorization_consumption_result_digest",
                "authorization_consumption_id",
                "authorization_consumption_claim_id",
                "authorization_consumption_claim_digest",
                "authorization_lease_id",
                "authorization_lease_digest",
                "authorization_consumed_at",
            ],
            [
                f"{AUTH_RESULT_TABLE}.result_id",
                f"{AUTH_RESULT_TABLE}.canonical_digest",
                f"{AUTH_RESULT_TABLE}.consumption_id",
                f"{AUTH_RESULT_TABLE}.consumption_claim_id",
                f"{AUTH_RESULT_TABLE}.consumption_claim_digest",
                f"{AUTH_RESULT_TABLE}.authorization_lease_id",
                f"{AUTH_RESULT_TABLE}.authorization_lease_digest",
                f"{AUTH_RESULT_TABLE}.consumed_at",
            ],
            name="fk_wf_rtctx_use_claim_auth_result",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "authorization_consumption_claim_id",
                "authorization_consumption_claim_digest",
                "authorization_consumption_id",
                "authorization_lease_id",
                "authorization_lease_digest",
                "authorization_consumed_at",
            ],
            [
                f"{AUTH_CLAIM_TABLE}.consumption_claim_id",
                f"{AUTH_CLAIM_TABLE}.canonical_digest",
                f"{AUTH_CLAIM_TABLE}.consumption_id",
                f"{AUTH_CLAIM_TABLE}.authorization_lease_id",
                f"{AUTH_CLAIM_TABLE}.authorization_lease_digest",
                f"{AUTH_CLAIM_TABLE}.claimed_at",
            ],
            name="fk_wf_rtctx_use_claim_auth_claim",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "authorization_consumption_claim_id",
                "injection_result_id",
                "injection_result_digest",
                "destination_deployment_id",
                "destination_generation",
                "destination_fencing_token_digest",
                "runtime_slot_commitment",
                "runtime_slot_pre_generation",
                "injected_context_usable_until",
                "use_profile_id",
                "use_profile_version",
                "use_profile_digest",
            ],
            [
                f"{AUTH_CLAIM_TABLE}.consumption_claim_id",
                f"{AUTH_CLAIM_TABLE}.injection_result_id",
                f"{AUTH_CLAIM_TABLE}.injection_result_digest",
                f"{AUTH_CLAIM_TABLE}.destination_deployment_id",
                f"{AUTH_CLAIM_TABLE}.destination_generation",
                f"{AUTH_CLAIM_TABLE}.destination_fencing_token_digest",
                f"{AUTH_CLAIM_TABLE}.runtime_slot_commitment",
                f"{AUTH_CLAIM_TABLE}.runtime_slot_post_generation",
                f"{AUTH_CLAIM_TABLE}.injected_context_usable_until",
                f"{AUTH_CLAIM_TABLE}.use_profile_id",
                f"{AUTH_CLAIM_TABLE}.use_profile_version",
                f"{AUTH_CLAIM_TABLE}.use_profile_digest",
            ],
            name="fk_wf_rtctx_use_claim_source",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            [
                "authorization_consumption_claim_id",
                "organization_id",
                "environment_id",
                "site_id",
                "consumer_subject_id",
                "consumer_audience",
                "consumer_contract_id",
                "consumer_contract_version",
                "source_policy_id",
                "source_policy_version",
                "source_policy_digest",
            ],
            [
                f"{AUTH_CLAIM_TABLE}.consumption_claim_id",
                f"{AUTH_CLAIM_TABLE}.organization_id",
                f"{AUTH_CLAIM_TABLE}.environment_id",
                f"{AUTH_CLAIM_TABLE}.site_id",
                f"{AUTH_CLAIM_TABLE}.consumer_subject_id",
                f"{AUTH_CLAIM_TABLE}.consumer_audience",
                f"{AUTH_CLAIM_TABLE}.consumer_contract_id",
                f"{AUTH_CLAIM_TABLE}.consumer_contract_version",
                f"{AUTH_CLAIM_TABLE}.policy_id",
                f"{AUTH_CLAIM_TABLE}.policy_version",
                f"{AUTH_CLAIM_TABLE}.policy_digest",
            ],
            name="fk_wf_rtctx_use_claim_source_scope",
            deferrable=True,
            initially="DEFERRED",
        ),
    )


def _result_effect_columns() -> tuple[sa.Column[object], ...]:
    names = (
        "protected_runtime_context_use_performed",
        "context_adopted",
        "context_terminal_non_reusable",
        "transient_material_zeroized",
        "context_disclosed",
        "runtime_handle_disclosed",
        "runtime_slot_locator_disclosed",
        "derived_capability_created",
        "runtime_started",
        "runtime_resumed",
        "process_created",
        "prompt_constructed",
        "model_inference_performed",
        "model_output_created",
        "filesystem_activity_performed",
        "provider_activity_performed",
        "connector_activity_performed",
        "network_activity_performed",
        "readiness_probe_performed",
        "publication_performed",
        "delivery_performed",
        "dispatch_performed",
        "execution_performed",
        "infrastructure_mutation_performed",
    )
    return tuple(sa.Column(name, sa.Boolean(), nullable=False) for name in names)


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_wf_rtctx_use_consume_claim_source",
        AUTH_CLAIM_TABLE,
        [
            "consumption_claim_id",
            "injection_result_id",
            "injection_result_digest",
            "destination_deployment_id",
            "destination_generation",
            "destination_fencing_token_digest",
            "runtime_slot_commitment",
            "runtime_slot_post_generation",
            "injected_context_usable_until",
            "use_profile_id",
            "use_profile_version",
            "use_profile_digest",
        ],
    )
    op.create_unique_constraint(
        "uq_wf_rtctx_use_consume_claim_source_scope",
        AUTH_CLAIM_TABLE,
        [
            "consumption_claim_id",
            "organization_id",
            "environment_id",
            "site_id",
            "consumer_subject_id",
            "consumer_audience",
            "consumer_contract_id",
            "consumer_contract_version",
            "policy_id",
            "policy_version",
            "policy_digest",
        ],
    )
    op.create_unique_constraint(
        "uq_wf_rtctx_use_consume_result_lineage",
        AUTH_RESULT_TABLE,
        [
            "result_id",
            "canonical_digest",
            "consumption_id",
            "consumption_claim_id",
            "consumption_claim_digest",
            "authorization_lease_id",
            "authorization_lease_digest",
            "consumed_at",
        ],
    )

    op.drop_constraint("ck_wf_rtctx_inj_slot_head_contract", SLOT_HEAD_TABLE, type_="check")
    op.create_check_constraint(
        "ck_wf_rtctx_inj_slot_head_contract",
        SLOT_HEAD_TABLE,
        "destination_boundary_id = 'boundary.workflow-protected-target-context-capsule-consumer' "
        "AND destination_deployment_id = 'deployment.workflow-protected-target-context-capsule-consumer' "
        "AND destination_generation >= 1 "
        "AND length(destination_fencing_token_digest) = 64 "
        "AND length(runtime_slot_commitment) = 64 "
        "AND runtime_slot_profile_digest = '7c429ec36bd39f5d02add24b7622e55e32eb0cfca9345ebf272fd231385e3e6b' "
        "AND slot_generation >= 0 "
        "AND slot_state IN ('empty_inert', 'inert_context_present', 'outcome_uncertain', "
        "'use_outcome_uncertain', 'context_used_terminal') AND current",
    )

    op.create_table(
        CLAIM_TABLE,
        sa.Column("claim_id", sa.String(128), primary_key=True),
        sa.Column("use_id", sa.String(128), nullable=False),
        sa.Column("attempt_id", sa.String(128), nullable=False),
        *_source_columns(),
        *_identity_columns(),
        sa.Column("irreversible_use_acknowledged", sa.Boolean(), nullable=False),
        sa.Column("uncertainty_no_retry_acknowledged", sa.Boolean(), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("idempotency_digest", sa.String(64), nullable=False),
        sa.Column("use_authorization_audit_digest", sa.String(64), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("use_authorization_audit_payload", postgresql.JSONB(), nullable=False),
        *_source_foreign_keys(),
        sa.UniqueConstraint(
            "authorization_consumption_result_id", name="uq_wf_rtctx_use_claim_auth_result"
        ),
        sa.UniqueConstraint("injection_result_id", name="uq_wf_rtctx_use_claim_injection_result"),
        sa.UniqueConstraint(
            "destination_deployment_id",
            "runtime_slot_commitment",
            "runtime_slot_pre_generation",
            name="uq_wf_rtctx_use_claim_slot_generation",
        ),
        sa.UniqueConstraint("use_id", name="uq_wf_rtctx_use_claim_use"),
        sa.UniqueConstraint("attempt_id", name="uq_wf_rtctx_use_claim_attempt"),
        sa.UniqueConstraint(
            "organization_id",
            "environment_id",
            "site_id",
            "consumer_subject_id",
            "consumer_audience",
            "idempotency_digest",
            name="uq_wf_rtctx_use_claim_tenant_idem",
        ),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rtctx_use_claim_digest"),
        sa.UniqueConstraint(
            "claim_id",
            "canonical_digest",
            "use_id",
            "attempt_id",
            "authorization_consumption_result_id",
            "destination_deployment_id",
            "runtime_slot_commitment",
            "runtime_slot_pre_generation",
            "claimed_at",
            name="uq_wf_rtctx_use_claim_attempt_line",
        ),
        sa.UniqueConstraint("claim_id", *SOURCE_NAMES, name="uq_wf_rtctx_use_claim_source_line"),
        sa.UniqueConstraint(
            "claim_id", *IDENTITY_NAMES, name="uq_wf_rtctx_use_claim_identity_line"
        ),
        sa.CheckConstraint(_contract_check(), name="ck_wf_rtctx_use_claim_contract"),
        sa.CheckConstraint(
            "authorization_consumed_at <= claimed_at "
            "AND claimed_at < injected_context_usable_until "
            "AND runtime_slot_pre_generation >= 1",
            name="ck_wf_rtctx_use_claim_chronology",
        ),
        sa.CheckConstraint(
            "use_profile_id = 'profile.workflow-protected-runtime-context-use' "
            f"AND use_profile_version = '1.0' AND use_profile_digest = '{USE_PROFILE_DIGEST}'",
            name="ck_wf_rtctx_use_claim_profile",
        ),
        sa.CheckConstraint(
            "irreversible_use_acknowledged AND uncertainty_no_retry_acknowledged "
            "AND length(idempotency_digest) = 64 AND length(request_fingerprint) = 64 AND "
            + _zero_authority_check(),
            name="ck_wf_rtctx_use_claim_semantics",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object' "
            "AND jsonb_typeof(use_authorization_audit_payload) = 'object' "
            "AND use_authorization_audit_payload <> '{}'::jsonb",
            name="ck_wf_rtctx_use_claim_evidence",
        ),
    )
    op.create_index(
        "ix_wf_rtctx_use_claim_scope",
        CLAIM_TABLE,
        ["organization_id", "environment_id", "site_id", "claimed_at"],
    )

    op.create_table(
        ATTEMPT_TABLE,
        sa.Column("attempt_id", sa.String(128), primary_key=True),
        sa.Column("use_id", sa.String(128), nullable=False),
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("claim_digest", sa.String(64), nullable=False),
        *_source_columns(),
        *_identity_columns(),
        sa.Column("protected_operation_reference", sa.String(128), nullable=False),
        sa.Column("instruction_digest", sa.String(64), nullable=False),
        sa.Column("expected_runtime_slot_post_generation", sa.Integer(), nullable=False),
        sa.Column("expected_use_count_pre", sa.Integer(), nullable=False),
        sa.Column("expected_use_count_post", sa.Integer(), nullable=False),
        sa.Column("eligibility_attestor_id", sa.String(128), nullable=False),
        sa.Column("eligibility_attestor_version", sa.String(64), nullable=False),
        sa.Column("eligibility_attestation_signing_key_id", sa.String(128), nullable=False),
        sa.Column("eligibility_attestation_id", sa.String(128), nullable=False),
        sa.Column("eligibility_attestation_digest", sa.String(64), nullable=False),
        sa.Column(
            "eligibility_attestation_observed_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("attestation_valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("required_executor_contract_id", sa.String(128), nullable=False),
        sa.Column("required_executor_contract_version", sa.String(64), nullable=False),
        sa.Column("approved_executor_id", sa.String(128), nullable=False),
        sa.Column("approved_executor_version", sa.String(64), nullable=False),
        sa.Column("receipt_verification_signing_key_id", sa.String(128), nullable=False),
        sa.Column("request_nonce_digest", sa.String(64), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("use_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(64), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("eligibility_attestation_payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            [
                "claim_id",
                "claim_digest",
                "use_id",
                "attempt_id",
                "authorization_consumption_result_id",
                "destination_deployment_id",
                "runtime_slot_commitment",
                "runtime_slot_pre_generation",
                "claimed_at",
            ],
            [
                f"{CLAIM_TABLE}.claim_id",
                f"{CLAIM_TABLE}.canonical_digest",
                f"{CLAIM_TABLE}.use_id",
                f"{CLAIM_TABLE}.attempt_id",
                f"{CLAIM_TABLE}.authorization_consumption_result_id",
                f"{CLAIM_TABLE}.destination_deployment_id",
                f"{CLAIM_TABLE}.runtime_slot_commitment",
                f"{CLAIM_TABLE}.runtime_slot_pre_generation",
                f"{CLAIM_TABLE}.claimed_at",
            ],
            name="fk_wf_rtctx_use_attempt_claim",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["claim_id", *SOURCE_NAMES],
            [f"{CLAIM_TABLE}.claim_id", *(f"{CLAIM_TABLE}.{name}" for name in SOURCE_NAMES)],
            name="fk_wf_rtctx_use_attempt_source",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["claim_id", *IDENTITY_NAMES],
            [f"{CLAIM_TABLE}.claim_id", *(f"{CLAIM_TABLE}.{name}" for name in IDENTITY_NAMES)],
            name="fk_wf_rtctx_use_attempt_identity",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.UniqueConstraint("claim_id", name="uq_wf_rtctx_use_attempt_claim"),
        sa.UniqueConstraint(
            "authorization_consumption_result_id", name="uq_wf_rtctx_use_attempt_auth_result"
        ),
        sa.UniqueConstraint("use_id", name="uq_wf_rtctx_use_attempt_use"),
        sa.UniqueConstraint("instruction_digest", name="uq_wf_rtctx_use_attempt_instruction"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rtctx_use_attempt_digest"),
        sa.UniqueConstraint(
            "attempt_id",
            "canonical_digest",
            "use_id",
            "claim_id",
            "claim_digest",
            "authorization_consumption_result_id",
            "destination_deployment_id",
            "runtime_slot_commitment",
            "runtime_slot_pre_generation",
            "started_at",
            "use_deadline",
            name="uq_wf_rtctx_use_attempt_result_line",
        ),
        sa.UniqueConstraint(
            "attempt_id", *SOURCE_NAMES, name="uq_wf_rtctx_use_attempt_source_line"
        ),
        sa.UniqueConstraint(
            "attempt_id", *IDENTITY_NAMES, name="uq_wf_rtctx_use_attempt_identity_line"
        ),
        sa.CheckConstraint(_contract_check(), name="ck_wf_rtctx_use_attempt_contract"),
        sa.CheckConstraint("state = 'use_started'", name="ck_wf_rtctx_use_attempt_state"),
        sa.CheckConstraint(
            "claimed_at <= eligibility_attestation_observed_at "
            "AND eligibility_attestation_observed_at <= started_at "
            "AND started_at < use_deadline "
            "AND use_deadline <= attestation_valid_until "
            "AND use_deadline <= injected_context_usable_until",
            name="ck_wf_rtctx_use_attempt_window",
        ),
        sa.CheckConstraint(
            "required_executor_contract_id = 'contract.workflow-protected-runtime-context-use-executor' "
            "AND required_executor_contract_version = '1.0' "
            "AND approved_executor_id = 'executor.workflow-protected-runtime-context-use' "
            "AND approved_executor_version = '1.0' "
            "AND eligibility_attestor_id = 'attestor.workflow-protected-runtime-context-use-eligibility' "
            "AND eligibility_attestor_version = '1.0' "
            "AND eligibility_attestation_signing_key_id = 'key.workflow-protected-runtime-context-use-eligibility.v1' "
            "AND receipt_verification_signing_key_id = 'key.workflow-protected-runtime-context-use-receipt.v1' "
            "AND expected_runtime_slot_post_generation = runtime_slot_pre_generation + 1 "
            "AND expected_use_count_pre = 0 AND expected_use_count_post = 1",
            name="ck_wf_rtctx_use_attempt_executor",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object' "
            "AND jsonb_typeof(eligibility_attestation_payload) = 'object' "
            "AND eligibility_attestation_payload <> '{}'::jsonb "
            "AND length(instruction_digest) = 64 AND length(request_nonce_digest) = 64 AND "
            + _zero_authority_check(),
            name="ck_wf_rtctx_use_attempt_evidence",
        ),
    )
    op.create_index(
        "ix_wf_rtctx_use_attempt_scope",
        ATTEMPT_TABLE,
        ["organization_id", "environment_id", "site_id", "started_at"],
    )

    op.create_table(
        RESULT_TABLE,
        sa.Column("result_id", sa.String(128), primary_key=True),
        sa.Column("use_id", sa.String(128), nullable=False),
        sa.Column("attempt_id", sa.String(128), nullable=False),
        sa.Column("attempt_digest", sa.String(64), nullable=False),
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("claim_digest", sa.String(64), nullable=False),
        *_source_columns(),
        *_identity_columns(),
        sa.Column("protected_operation_reference", sa.String(128), nullable=False),
        sa.Column("instruction_digest", sa.String(64), nullable=False),
        sa.Column("executor_contract_id", sa.String(128), nullable=False),
        sa.Column("executor_contract_version", sa.String(64), nullable=False),
        sa.Column("executor_id", sa.String(128), nullable=False),
        sa.Column("executor_version", sa.String(64), nullable=False),
        sa.Column("receipt_verification_signing_key_id", sa.String(128), nullable=False),
        sa.Column("executor_receipt_digest", sa.String(64), nullable=True),
        sa.Column("runtime_slot_post_generation", sa.Integer(), nullable=True),
        sa.Column("use_count_pre", sa.Integer(), nullable=False),
        sa.Column("use_count_post", sa.Integer(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("use_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome_known", sa.Boolean(), nullable=False),
        sa.Column("state", sa.String(64), nullable=False),
        sa.Column("failure_class", sa.String(64), nullable=True),
        *_result_effect_columns(),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("executor_receipt_payload", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(
            [
                "attempt_id",
                "attempt_digest",
                "use_id",
                "claim_id",
                "claim_digest",
                "authorization_consumption_result_id",
                "destination_deployment_id",
                "runtime_slot_commitment",
                "runtime_slot_pre_generation",
                "started_at",
                "use_deadline",
            ],
            [
                f"{ATTEMPT_TABLE}.attempt_id",
                f"{ATTEMPT_TABLE}.canonical_digest",
                f"{ATTEMPT_TABLE}.use_id",
                f"{ATTEMPT_TABLE}.claim_id",
                f"{ATTEMPT_TABLE}.claim_digest",
                f"{ATTEMPT_TABLE}.authorization_consumption_result_id",
                f"{ATTEMPT_TABLE}.destination_deployment_id",
                f"{ATTEMPT_TABLE}.runtime_slot_commitment",
                f"{ATTEMPT_TABLE}.runtime_slot_pre_generation",
                f"{ATTEMPT_TABLE}.started_at",
                f"{ATTEMPT_TABLE}.use_deadline",
            ],
            name="fk_wf_rtctx_use_result_attempt",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id", *SOURCE_NAMES],
            [
                f"{ATTEMPT_TABLE}.attempt_id",
                *(f"{ATTEMPT_TABLE}.{name}" for name in SOURCE_NAMES),
            ],
            name="fk_wf_rtctx_use_result_source",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id", *IDENTITY_NAMES],
            [
                f"{ATTEMPT_TABLE}.attempt_id",
                *(f"{ATTEMPT_TABLE}.{name}" for name in IDENTITY_NAMES),
            ],
            name="fk_wf_rtctx_use_result_identity",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.UniqueConstraint("attempt_id", name="uq_wf_rtctx_use_result_attempt"),
        sa.UniqueConstraint("claim_id", name="uq_wf_rtctx_use_result_claim"),
        sa.UniqueConstraint(
            "authorization_consumption_result_id", name="uq_wf_rtctx_use_result_auth_result"
        ),
        sa.UniqueConstraint("use_id", name="uq_wf_rtctx_use_result_use"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rtctx_use_result_digest"),
        sa.CheckConstraint(_contract_check(), name="ck_wf_rtctx_use_result_contract"),
        sa.CheckConstraint(
            "claimed_at <= started_at AND "
            "((state = 'context_use_outcome_uncertain' AND completed_at IS NULL "
            "AND recorded_at >= started_at) OR (completed_at IS NOT NULL "
            "AND started_at <= completed_at AND completed_at <= recorded_at "
            "AND completed_at < use_deadline))",
            name="ck_wf_rtctx_use_result_chronology",
        ),
        sa.CheckConstraint(
            "(state = 'context_used_once_in_protected_boundary' "
            "AND failure_class IS NULL AND outcome_known "
            "AND executor_receipt_digest IS NOT NULL AND executor_receipt_payload IS NOT NULL "
            "AND runtime_slot_post_generation = runtime_slot_pre_generation + 1 "
            "AND use_count_pre = 0 AND use_count_post = 1 "
            "AND protected_runtime_context_use_performed AND context_adopted "
            "AND context_terminal_non_reusable AND transient_material_zeroized) OR "
            "(state = 'context_use_failed_without_use' "
            "AND failure_class IS NOT NULL AND outcome_known "
            "AND executor_receipt_digest IS NOT NULL AND executor_receipt_payload IS NOT NULL "
            "AND runtime_slot_post_generation = runtime_slot_pre_generation "
            "AND use_count_pre = 0 AND use_count_post = 0 "
            "AND NOT protected_runtime_context_use_performed AND NOT context_adopted "
            "AND NOT context_terminal_non_reusable AND transient_material_zeroized) OR "
            "(state = 'context_use_outcome_uncertain' "
            "AND failure_class = 'context_use_outcome_uncertain' AND NOT outcome_known "
            "AND executor_receipt_digest IS NULL AND executor_receipt_payload IS NULL "
            "AND runtime_slot_post_generation IS NULL "
            "AND use_count_pre = 0 AND use_count_post IS NULL "
            "AND NOT protected_runtime_context_use_performed AND NOT context_adopted "
            "AND NOT context_terminal_non_reusable AND NOT transient_material_zeroized)",
            name="ck_wf_rtctx_use_result_outcome",
        ),
        sa.CheckConstraint(
            "(NOT outcome_known) OR ("
            "COALESCE((executor_receipt_payload ->> 'canonical_digest') = executor_receipt_digest, FALSE) "
            "AND COALESCE((executor_receipt_payload ->> 'signing_key_id') = receipt_verification_signing_key_id, FALSE) "
            "AND COALESCE((executor_receipt_payload ->> 'instruction_digest') = instruction_digest, FALSE) "
            "AND COALESCE((executor_receipt_payload ->> 'protected_operation_reference') = protected_operation_reference, FALSE) "
            "AND length(COALESCE(executor_receipt_payload ->> 'integrity_signature', '')) > 0 "
            "AND length(COALESCE(executor_receipt_payload ->> 'attested_by', '')) > 0 "
            "AND length(COALESCE(executor_receipt_payload ->> 'signature_algorithm', '')) > 0 "
            "AND executor_receipt_payload @> jsonb_build_object("
            "'authorization_consumption_result_id', authorization_consumption_result_id, "
            "'authorization_consumption_result_digest', authorization_consumption_result_digest, "
            "'destination_deployment_id', destination_deployment_id, "
            "'destination_generation', destination_generation, "
            "'destination_fencing_token_digest', destination_fencing_token_digest, "
            "'runtime_slot_commitment', runtime_slot_commitment, "
            "'runtime_slot_pre_generation', runtime_slot_pre_generation, "
            "'runtime_slot_post_generation', runtime_slot_post_generation, "
            "'use_count_pre', use_count_pre, 'use_count_post', use_count_post, "
            "'use_profile_id', use_profile_id, 'use_profile_version', use_profile_version, "
            "'use_profile_digest', use_profile_digest, "
            "'executor_contract_id', executor_contract_id, "
            "'executor_contract_version', executor_contract_version, "
            "'executor_id', executor_id, 'executor_version', executor_version, "
            "'state', state, 'failure_class', failure_class, "
            "'protected_runtime_context_use_performed', protected_runtime_context_use_performed, "
            "'context_adopted', context_adopted, "
            "'context_terminal_non_reusable', context_terminal_non_reusable, "
            "'transient_material_zeroized', transient_material_zeroized, "
            "'context_disclosed', context_disclosed, "
            "'runtime_started', runtime_started, 'runtime_resumed', runtime_resumed, "
            "'process_created', process_created, "
            "'prompt_constructed', prompt_constructed, "
            "'model_inference_performed', model_inference_performed, "
            "'model_output_created', model_output_created, "
            "'filesystem_activity_performed', filesystem_activity_performed, "
            "'provider_activity_performed', provider_activity_performed, "
            "'connector_activity_performed', connector_activity_performed, "
            "'network_activity_performed', network_activity_performed, "
            "'readiness_probe_performed', readiness_probe_performed, "
            "'publication_performed', publication_performed, "
            "'delivery_performed', delivery_performed, "
            "'dispatch_performed', dispatch_performed, "
            "'execution_performed', execution_performed, "
            "'infrastructure_mutation_performed', infrastructure_mutation_performed))",
            name="ck_wf_rtctx_use_result_receipt",
        ),
        sa.CheckConstraint(
            "executor_contract_id = 'contract.workflow-protected-runtime-context-use-executor' "
            "AND executor_contract_version = '1.0' "
            "AND executor_id = 'executor.workflow-protected-runtime-context-use' "
            "AND executor_version = '1.0' "
            "AND receipt_verification_signing_key_id = 'key.workflow-protected-runtime-context-use-receipt.v1'",
            name="ck_wf_rtctx_use_result_executor",
        ),
        sa.CheckConstraint(
            "NOT context_disclosed AND NOT runtime_handle_disclosed "
            "AND NOT runtime_slot_locator_disclosed AND NOT derived_capability_created "
            "AND NOT runtime_started AND NOT runtime_resumed AND NOT process_created "
            "AND NOT prompt_constructed AND NOT model_inference_performed "
            "AND NOT model_output_created "
            "AND NOT filesystem_activity_performed AND NOT provider_activity_performed "
            "AND NOT connector_activity_performed AND NOT network_activity_performed "
            "AND NOT readiness_probe_performed AND NOT publication_performed "
            "AND NOT delivery_performed AND NOT dispatch_performed "
            "AND NOT execution_performed AND NOT infrastructure_mutation_performed AND "
            + _zero_authority_check(),
            name="ck_wf_rtctx_use_result_effects",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object' "
            "AND (executor_receipt_payload IS NULL "
            "OR jsonb_typeof(executor_receipt_payload) = 'object')",
            name="ck_wf_rtctx_use_result_payload",
        ),
    )
    op.create_index(
        "ix_wf_rtctx_use_result_scope",
        RESULT_TABLE,
        ["organization_id", "environment_id", "site_id", "recorded_at"],
    )

    op.execute(
        sa.text(f"""
        CREATE FUNCTION {APPEND_ONLY_FUNCTION}() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'protected runtime-context use evidence is append-only'
                USING ERRCODE = '55000';
        END;
        $$
    """)
    )
    for table, trigger in (
        (CLAIM_TABLE, "trg_wf_rtctx_use_claim_append_only"),
        (ATTEMPT_TABLE, "trg_wf_rtctx_use_attempt_append_only"),
        (RESULT_TABLE, "trg_wf_rtctx_use_result_append_only"),
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
                   WHERE slot_state IN ('use_outcome_uncertain', 'context_used_terminal')
               ) THEN
                RAISE EXCEPTION
                    'refusing guarded downgrade: protected runtime-context use evidence exists'
                    USING ERRCODE = '55000';
            END IF;
        END $$;
    """)
    )
    op.drop_table(RESULT_TABLE)
    op.drop_table(ATTEMPT_TABLE)
    op.drop_table(CLAIM_TABLE)
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {APPEND_ONLY_FUNCTION}()"))

    op.drop_constraint("ck_wf_rtctx_inj_slot_head_contract", SLOT_HEAD_TABLE, type_="check")
    op.create_check_constraint(
        "ck_wf_rtctx_inj_slot_head_contract",
        SLOT_HEAD_TABLE,
        "destination_boundary_id = 'boundary.workflow-protected-target-context-capsule-consumer' "
        "AND destination_deployment_id = 'deployment.workflow-protected-target-context-capsule-consumer' "
        "AND destination_generation >= 1 "
        "AND length(destination_fencing_token_digest) = 64 "
        "AND length(runtime_slot_commitment) = 64 "
        "AND runtime_slot_profile_digest = '7c429ec36bd39f5d02add24b7622e55e32eb0cfca9345ebf272fd231385e3e6b' "
        "AND slot_generation >= 0 "
        "AND slot_state IN ('empty_inert', 'inert_context_present', 'outcome_uncertain') AND current",
    )
    op.drop_constraint("uq_wf_rtctx_use_consume_result_lineage", AUTH_RESULT_TABLE, type_="unique")
    op.drop_constraint(
        "uq_wf_rtctx_use_consume_claim_source_scope", AUTH_CLAIM_TABLE, type_="unique"
    )
    op.drop_constraint("uq_wf_rtctx_use_consume_claim_source", AUTH_CLAIM_TABLE, type_="unique")
