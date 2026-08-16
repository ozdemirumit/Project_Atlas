"""Add atomic target-context capsule opening consumption evidence.

Revision ID: 20260816_0138
Revises: 20260816_0137
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260816_0138"
down_revision: str | None = "20260816_0137"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEASE_TABLE = "workflow_event_tctx_capsule_opening_authorization_leases"
CLAIM_TABLE = "workflow_event_tctx_capsule_opening_consumption_claims"
ATTEMPT_TABLE = "workflow_event_tctx_capsule_opening_attempts"
RESULT_TABLE = "workflow_event_tctx_capsule_opening_results"
APPEND_ONLY_FUNCTION = "reject_wf_tctx_capsule_opening_mutation"

POLICY_ID = "policy.workflow-protected-transport-target-context-capsule-opening-consumption"
POLICY_DIGEST = "8f430062de218e4dbcba9f505d27082a1b6ffb700111bea67882113f4551bce2"
SUBJECT_ID = "service.workflow-protected-transport-target-context-capsule-consumer"
AUDIENCE = "audience.workflow-protected-transport-target-context-capsule-consumer"
CONTRACT_ID = "contract.workflow-protected-transport-target-context-capsule-consumer"
PURPOSE_ID = "purpose.workflow-protected-transport-target-context-capsule-opening-evaluation"
OPENER_CONTRACT_ID = "contract.workflow-protected-target-context-capsule-consumer-boundary-opener"
OPENER_ID = "opener.workflow-protected-target-context-capsule-consumer-boundary"
BOUNDARY_ID = "boundary.workflow-protected-target-context-capsule-consumer"
DEPLOYMENT_ID = "deployment.workflow-protected-target-context-capsule-consumer"
FENCING_DIGEST = "701153578261c45c3f1faa89f75b4a3f7003126683ddb895c0346aac0f9148e7"
CUSTODY_CONTRACT_ID = "contract.workflow-protected-target-context-capsule-custody"
SIGNING_KEY_ID = "key.workflow-protected-target-context-capsule-opening-receipt.v1"
OPENER_PROFILE_DIGEST = "1e7a8403d5ebe4e4b1816bd10afe64998f31846095ebe648327ee719913df987"


def _scope_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("environment_id", sa.String(128), nullable=False),
        sa.Column("site_id", sa.String(128), nullable=False),
    )


def _authority_names() -> tuple[str, ...]:
    return (
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
        "target_context_capsule_handoff_authority_granted",
        "target_context_capsule_opening_authority_granted",
    )


def _authority_columns() -> tuple[sa.Column[object], ...]:
    return tuple(sa.Column(name, sa.Boolean(), nullable=False) for name in _authority_names())


def _zero_authority_check() -> str:
    return " AND ".join(f"NOT {name}" for name in _authority_names())


def _code_owned_contract_check() -> str:
    return (
        f"consumer_subject_id = '{SUBJECT_ID}' "
        f"AND consumer_audience = '{AUDIENCE}' "
        f"AND consumer_contract_id = '{CONTRACT_ID}' "
        "AND consumer_contract_version = '1.0' "
        f"AND purpose_id = '{PURPOSE_ID}' "
        f"AND policy_id = '{POLICY_ID}' "
        "AND policy_version = '1.0' "
        f"AND policy_digest = '{POLICY_DIGEST}'"
    )


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_wf_tctx_open_auth_consume_lineage",
        LEASE_TABLE,
        [
            "authorization_lease_id",
            "canonical_digest",
            "handoff_id",
            "handoff_result_digest",
            "attempt_id",
            "attempt_digest",
            "consumption_claim_id",
            "consumption_claim_digest",
            "consumer_binding_id",
            "consumer_binding_digest",
            "sealed_capsule_id",
            "sealed_capsule_digest",
            "consumer_receipt_id",
            "receipt_digest",
        ],
    )
    op.create_table(
        CLAIM_TABLE,
        sa.Column("claim_id", sa.String(128), primary_key=True),
        sa.Column("opening_id", sa.String(128), nullable=False),
        sa.Column("attempt_id", sa.String(128), nullable=False),
        sa.Column("authorization_lease_id", sa.String(128), nullable=False),
        sa.Column("authorization_lease_digest", sa.String(64), nullable=False),
        sa.Column("handoff_id", sa.String(128), nullable=False),
        sa.Column("handoff_result_digest", sa.String(64), nullable=False),
        sa.Column("handoff_attempt_id", sa.String(128), nullable=False),
        sa.Column("handoff_attempt_digest", sa.String(64), nullable=False),
        sa.Column("handoff_consumption_claim_id", sa.String(128), nullable=False),
        sa.Column("handoff_consumption_claim_digest", sa.String(64), nullable=False),
        sa.Column("consumer_binding_id", sa.String(128), nullable=False),
        sa.Column("consumer_binding_digest", sa.String(64), nullable=False),
        sa.Column("sealed_capsule_id", sa.String(128), nullable=False),
        sa.Column("sealed_capsule_digest", sa.String(64), nullable=False),
        sa.Column("consumer_receipt_id", sa.String(128), nullable=False),
        sa.Column("consumer_receipt_digest", sa.String(64), nullable=False),
        sa.Column("sealed_capsule_is_bearer_capability", sa.Boolean(), nullable=False),
        sa.Column("consumer_receipt_is_bearer_capability", sa.Boolean(), nullable=False),
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
        sa.CheckConstraint(_code_owned_contract_check(), name="ck_wf_tctx_open_consume_contract"),
        sa.CheckConstraint(
            "irreversible_consumption_acknowledged "
            "AND uncertain_outcome_requires_new_authorization_acknowledged",
            name="ck_wf_tctx_open_consume_ack",
        ),
        sa.CheckConstraint(
            "NOT sealed_capsule_is_bearer_capability AND NOT consumer_receipt_is_bearer_capability",
            name="ck_wf_tctx_open_consume_non_bearer",
        ),
        sa.CheckConstraint(_zero_authority_check(), name="ck_wf_tctx_open_consume_authority"),
        sa.ForeignKeyConstraint(
            [
                "authorization_lease_id",
                "authorization_lease_digest",
                "handoff_id",
                "handoff_result_digest",
                "handoff_attempt_id",
                "handoff_attempt_digest",
                "handoff_consumption_claim_id",
                "handoff_consumption_claim_digest",
                "consumer_binding_id",
                "consumer_binding_digest",
                "sealed_capsule_id",
                "sealed_capsule_digest",
                "consumer_receipt_id",
                "consumer_receipt_digest",
            ],
            [
                f"{LEASE_TABLE}.authorization_lease_id",
                f"{LEASE_TABLE}.canonical_digest",
                f"{LEASE_TABLE}.handoff_id",
                f"{LEASE_TABLE}.handoff_result_digest",
                f"{LEASE_TABLE}.attempt_id",
                f"{LEASE_TABLE}.attempt_digest",
                f"{LEASE_TABLE}.consumption_claim_id",
                f"{LEASE_TABLE}.consumption_claim_digest",
                f"{LEASE_TABLE}.consumer_binding_id",
                f"{LEASE_TABLE}.consumer_binding_digest",
                f"{LEASE_TABLE}.sealed_capsule_id",
                f"{LEASE_TABLE}.sealed_capsule_digest",
                f"{LEASE_TABLE}.consumer_receipt_id",
                f"{LEASE_TABLE}.receipt_digest",
            ],
            name="fk_wf_tctx_open_consume_lease_lineage",
        ),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_tctx_open_consume_lease"),
        sa.UniqueConstraint("handoff_id", name="uq_wf_tctx_open_consume_handoff"),
        sa.UniqueConstraint("consumer_receipt_id", name="uq_wf_tctx_open_consume_receipt"),
        sa.UniqueConstraint("sealed_capsule_id", name="uq_wf_tctx_open_consume_capsule"),
        sa.UniqueConstraint("opening_id", name="uq_wf_tctx_open_consume_opening"),
        sa.UniqueConstraint("attempt_id", name="uq_wf_tctx_open_consume_attempt"),
        sa.UniqueConstraint(
            "idempotency_scope_id", "idempotency_key", name="uq_wf_tctx_open_consume_scope_idem"
        ),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_tctx_open_consume_digest"),
        sa.UniqueConstraint(
            "claim_id",
            "canonical_digest",
            "opening_id",
            "attempt_id",
            "authorization_lease_id",
            "authorization_lease_digest",
            "consumer_binding_id",
            "consumer_binding_digest",
            "sealed_capsule_id",
            "sealed_capsule_digest",
            "consumer_receipt_id",
            "consumer_receipt_digest",
            name="uq_wf_tctx_open_consume_claim_lineage",
        ),
    )
    op.create_index(
        "ix_wf_tctx_open_consume_scope",
        CLAIM_TABLE,
        ["organization_id", "environment_id", "site_id", "claimed_at"],
    )

    op.create_table(
        ATTEMPT_TABLE,
        sa.Column("attempt_id", sa.String(128), primary_key=True),
        sa.Column("opening_id", sa.String(128), nullable=False),
        sa.Column("consumption_claim_id", sa.String(128), nullable=False),
        sa.Column("consumption_claim_digest", sa.String(64), nullable=False),
        sa.Column("authorization_lease_id", sa.String(128), nullable=False),
        sa.Column("authorization_lease_digest", sa.String(64), nullable=False),
        sa.Column("consumer_binding_id", sa.String(128), nullable=False),
        sa.Column("consumer_binding_digest", sa.String(64), nullable=False),
        sa.Column("sealed_capsule_id", sa.String(128), nullable=False),
        sa.Column("sealed_capsule_digest", sa.String(64), nullable=False),
        sa.Column("consumer_receipt_id", sa.String(128), nullable=False),
        sa.Column("consumer_receipt_digest", sa.String(64), nullable=False),
        sa.Column("sealed_capsule_is_bearer_capability", sa.Boolean(), nullable=False),
        sa.Column("consumer_receipt_is_bearer_capability", sa.Boolean(), nullable=False),
        *_scope_columns(),
        sa.Column("consumer_subject_id", sa.String(240), nullable=False),
        sa.Column("consumer_audience", sa.String(240), nullable=False),
        sa.Column("consumer_contract_id", sa.String(128), nullable=False),
        sa.Column("consumer_contract_version", sa.String(64), nullable=False),
        sa.Column("purpose_id", sa.String(128), nullable=False),
        sa.Column("policy_id", sa.String(128), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("policy_digest", sa.String(64), nullable=False),
        sa.Column("required_opener_contract_id", sa.String(128), nullable=False),
        sa.Column("required_opener_contract_version", sa.String(64), nullable=False),
        sa.Column("approved_opener_id", sa.String(128), nullable=False),
        sa.Column("approved_opener_version", sa.String(64), nullable=False),
        sa.Column("destination_boundary_id", sa.String(128), nullable=False),
        sa.Column("destination_deployment_id", sa.String(128), nullable=False),
        sa.Column("destination_generation", sa.Integer(), nullable=False),
        sa.Column("destination_fencing_token_digest", sa.String(64), nullable=False),
        sa.Column("custody_contract_id", sa.String(128), nullable=False),
        sa.Column("custody_contract_version", sa.String(64), nullable=False),
        sa.Column("verification_signing_key_id", sa.String(128), nullable=False),
        sa.Column("trusted_opener_profile_digest", sa.String(64), nullable=False),
        sa.Column("custody_attestation_id", sa.String(128), nullable=False),
        sa.Column("custody_attestation_digest", sa.String(64), nullable=False),
        sa.Column("openability_attestation_id", sa.String(128), nullable=False),
        sa.Column("openability_attestation_digest", sa.String(64), nullable=False),
        sa.Column("request_nonce_digest", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("opening_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("custody_attestation_valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "openability_attestation_valid_until", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "resident_context_usable_until_limit", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("state", sa.String(64), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("custody_attestation_payload", postgresql.JSONB(), nullable=False),
        sa.Column("openability_attestation_payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(_code_owned_contract_check(), name="ck_wf_tctx_open_attempt_contract"),
        sa.CheckConstraint("state = 'started'", name="ck_wf_tctx_open_attempt_state"),
        sa.CheckConstraint(
            "started_at < opening_deadline "
            "AND opening_deadline <= lease_valid_until "
            "AND opening_deadline <= custody_attestation_valid_until "
            "AND opening_deadline <= openability_attestation_valid_until "
            "AND opening_deadline <= resident_context_usable_until_limit",
            name="ck_wf_tctx_open_attempt_window",
        ),
        sa.CheckConstraint(
            f"required_opener_contract_id = '{OPENER_CONTRACT_ID}' "
            "AND required_opener_contract_version = '1.0' "
            f"AND approved_opener_id = '{OPENER_ID}' "
            "AND approved_opener_version = '1.0' "
            f"AND destination_boundary_id = '{BOUNDARY_ID}' "
            f"AND destination_deployment_id = '{DEPLOYMENT_ID}' "
            "AND destination_generation = 1 "
            f"AND destination_fencing_token_digest = '{FENCING_DIGEST}' "
            f"AND custody_contract_id = '{CUSTODY_CONTRACT_ID}' "
            "AND custody_contract_version = '1.0' "
            f"AND verification_signing_key_id = '{SIGNING_KEY_ID}' "
            f"AND trusted_opener_profile_digest = '{OPENER_PROFILE_DIGEST}'",
            name="ck_wf_tctx_open_attempt_profile",
        ),
        sa.CheckConstraint(
            "NOT sealed_capsule_is_bearer_capability AND NOT consumer_receipt_is_bearer_capability",
            name="ck_wf_tctx_open_attempt_non_bearer",
        ),
        sa.CheckConstraint(_zero_authority_check(), name="ck_wf_tctx_open_attempt_authority"),
        sa.ForeignKeyConstraint(
            [
                "consumption_claim_id",
                "consumption_claim_digest",
                "opening_id",
                "attempt_id",
                "authorization_lease_id",
                "authorization_lease_digest",
                "consumer_binding_id",
                "consumer_binding_digest",
                "sealed_capsule_id",
                "sealed_capsule_digest",
                "consumer_receipt_id",
                "consumer_receipt_digest",
            ],
            [
                f"{CLAIM_TABLE}.claim_id",
                f"{CLAIM_TABLE}.canonical_digest",
                f"{CLAIM_TABLE}.opening_id",
                f"{CLAIM_TABLE}.attempt_id",
                f"{CLAIM_TABLE}.authorization_lease_id",
                f"{CLAIM_TABLE}.authorization_lease_digest",
                f"{CLAIM_TABLE}.consumer_binding_id",
                f"{CLAIM_TABLE}.consumer_binding_digest",
                f"{CLAIM_TABLE}.sealed_capsule_id",
                f"{CLAIM_TABLE}.sealed_capsule_digest",
                f"{CLAIM_TABLE}.consumer_receipt_id",
                f"{CLAIM_TABLE}.consumer_receipt_digest",
            ],
            name="fk_wf_tctx_open_attempt_claim_lineage",
        ),
        sa.UniqueConstraint("consumption_claim_id", name="uq_wf_tctx_open_attempt_claim"),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_tctx_open_attempt_lease"),
        sa.UniqueConstraint("opening_id", name="uq_wf_tctx_open_attempt_opening"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_tctx_open_attempt_digest"),
        sa.UniqueConstraint(
            "attempt_id",
            "canonical_digest",
            "opening_id",
            "consumption_claim_id",
            "consumption_claim_digest",
            "authorization_lease_id",
            "authorization_lease_digest",
            "consumer_binding_id",
            "consumer_binding_digest",
            "sealed_capsule_id",
            "sealed_capsule_digest",
            "consumer_receipt_id",
            "consumer_receipt_digest",
            name="uq_wf_tctx_open_attempt_result_lineage",
        ),
    )
    op.create_index(
        "ix_wf_tctx_open_attempt_scope",
        ATTEMPT_TABLE,
        ["organization_id", "environment_id", "site_id", "started_at"],
    )

    op.create_table(
        RESULT_TABLE,
        sa.Column("opening_id", sa.String(128), primary_key=True),
        sa.Column("attempt_id", sa.String(128), nullable=False),
        sa.Column("attempt_digest", sa.String(64), nullable=False),
        sa.Column("consumption_claim_id", sa.String(128), nullable=False),
        sa.Column("consumption_claim_digest", sa.String(64), nullable=False),
        sa.Column("authorization_lease_id", sa.String(128), nullable=False),
        sa.Column("authorization_lease_digest", sa.String(64), nullable=False),
        sa.Column("consumer_binding_id", sa.String(128), nullable=False),
        sa.Column("consumer_binding_digest", sa.String(64), nullable=False),
        sa.Column("sealed_capsule_id", sa.String(128), nullable=False),
        sa.Column("sealed_capsule_digest", sa.String(64), nullable=False),
        sa.Column("consumer_receipt_id", sa.String(128), nullable=False),
        sa.Column("consumer_receipt_digest", sa.String(64), nullable=False),
        *_scope_columns(),
        sa.Column("consumer_subject_id", sa.String(240), nullable=False),
        sa.Column("consumer_audience", sa.String(240), nullable=False),
        sa.Column("consumer_contract_id", sa.String(128), nullable=False),
        sa.Column("consumer_contract_version", sa.String(64), nullable=False),
        sa.Column("purpose_id", sa.String(128), nullable=False),
        sa.Column("policy_id", sa.String(128), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("policy_digest", sa.String(64), nullable=False),
        sa.Column("opener_id", sa.String(128), nullable=False),
        sa.Column("opener_version", sa.String(64), nullable=False),
        sa.Column("opening_receipt_digest", sa.String(64), nullable=True),
        sa.Column("state", sa.String(64), nullable=False),
        sa.Column("failure_class", sa.String(64), nullable=True),
        sa.Column("protected_resident_context_id", sa.String(128), nullable=True),
        sa.Column("protected_resident_context_digest", sa.String(64), nullable=True),
        sa.Column(
            "protected_resident_context_created_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "protected_resident_context_usable_until", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("protected_resident_context_is_bearer_capability", sa.Boolean(), nullable=False),
        sa.Column("capsule_opened_in_protected_boundary", sa.Boolean(), nullable=False),
        sa.Column("target_context_pair_verified", sa.Boolean(), nullable=False),
        sa.Column("outcome_known", sa.Boolean(), nullable=False),
        sa.Column("protected_source_closed", sa.Boolean(), nullable=False),
        sa.Column("source_capsule_zeroized", sa.Boolean(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("opening_deadline", sa.DateTime(timezone=True), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("opening_receipt_payload", postgresql.JSONB(), nullable=True),
        sa.CheckConstraint(_code_owned_contract_check(), name="ck_wf_tctx_open_result_contract"),
        sa.CheckConstraint(
            f"opener_id = '{OPENER_ID}' AND opener_version = '1.0' "
            "AND NOT protected_resident_context_is_bearer_capability",
            name="ck_wf_tctx_open_result_profile",
        ),
        sa.CheckConstraint(
            "(state = 'opened_in_protected_consumer_boundary' "
            "AND failure_class IS NULL AND opening_receipt_digest IS NOT NULL "
            "AND opening_receipt_payload IS NOT NULL "
            "AND protected_resident_context_id IS NOT NULL "
            "AND protected_resident_context_digest IS NOT NULL "
            "AND protected_resident_context_created_at IS NOT NULL "
            "AND protected_resident_context_usable_until IS NOT NULL "
            "AND protected_resident_context_created_at = completed_at "
            "AND protected_resident_context_usable_until > protected_resident_context_created_at "
            "AND protected_resident_context_usable_until <= "
            "protected_resident_context_created_at + INTERVAL '30 seconds' "
            "AND capsule_opened_in_protected_boundary AND target_context_pair_verified "
            "AND outcome_known AND protected_source_closed AND source_capsule_zeroized "
            "AND completed_at IS NOT NULL AND completed_at < opening_deadline "
            "AND recorded_at >= completed_at) OR "
            "(state = 'opening_failed' AND failure_class IS NOT NULL "
            "AND failure_class <> 'opening_outcome_uncertain' "
            "AND opening_receipt_digest IS NOT NULL AND opening_receipt_payload IS NOT NULL "
            "AND protected_resident_context_id IS NULL "
            "AND protected_resident_context_digest IS NULL "
            "AND protected_resident_context_created_at IS NULL "
            "AND protected_resident_context_usable_until IS NULL "
            "AND NOT capsule_opened_in_protected_boundary AND NOT target_context_pair_verified "
            "AND outcome_known AND protected_source_closed AND source_capsule_zeroized "
            "AND completed_at IS NOT NULL AND completed_at < opening_deadline "
            "AND recorded_at >= completed_at) OR "
            "(state = 'opening_outcome_uncertain' "
            "AND failure_class = 'opening_outcome_uncertain' "
            "AND opening_receipt_digest IS NULL AND opening_receipt_payload IS NULL "
            "AND protected_resident_context_id IS NULL "
            "AND protected_resident_context_digest IS NULL "
            "AND protected_resident_context_created_at IS NULL "
            "AND protected_resident_context_usable_until IS NULL "
            "AND NOT capsule_opened_in_protected_boundary AND NOT target_context_pair_verified "
            "AND NOT outcome_known AND NOT protected_source_closed AND NOT source_capsule_zeroized "
            "AND completed_at IS NULL AND recorded_at >= opening_deadline)",
            name="ck_wf_tctx_open_result_state",
        ),
        sa.CheckConstraint(_zero_authority_check(), name="ck_wf_tctx_open_result_authority"),
        sa.ForeignKeyConstraint(
            [
                "attempt_id",
                "attempt_digest",
                "opening_id",
                "consumption_claim_id",
                "consumption_claim_digest",
                "authorization_lease_id",
                "authorization_lease_digest",
                "consumer_binding_id",
                "consumer_binding_digest",
                "sealed_capsule_id",
                "sealed_capsule_digest",
                "consumer_receipt_id",
                "consumer_receipt_digest",
            ],
            [
                f"{ATTEMPT_TABLE}.attempt_id",
                f"{ATTEMPT_TABLE}.canonical_digest",
                f"{ATTEMPT_TABLE}.opening_id",
                f"{ATTEMPT_TABLE}.consumption_claim_id",
                f"{ATTEMPT_TABLE}.consumption_claim_digest",
                f"{ATTEMPT_TABLE}.authorization_lease_id",
                f"{ATTEMPT_TABLE}.authorization_lease_digest",
                f"{ATTEMPT_TABLE}.consumer_binding_id",
                f"{ATTEMPT_TABLE}.consumer_binding_digest",
                f"{ATTEMPT_TABLE}.sealed_capsule_id",
                f"{ATTEMPT_TABLE}.sealed_capsule_digest",
                f"{ATTEMPT_TABLE}.consumer_receipt_id",
                f"{ATTEMPT_TABLE}.consumer_receipt_digest",
            ],
            name="fk_wf_tctx_open_result_attempt_lineage",
        ),
        sa.UniqueConstraint("attempt_id", name="uq_wf_tctx_open_result_attempt"),
        sa.UniqueConstraint("consumption_claim_id", name="uq_wf_tctx_open_result_claim"),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_tctx_open_result_lease"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_tctx_open_result_digest"),
    )
    op.create_index(
        "ix_wf_tctx_open_result_scope",
        RESULT_TABLE,
        ["organization_id", "environment_id", "site_id", "recorded_at"],
    )

    op.execute(
        sa.text(
            f"""
            CREATE FUNCTION {APPEND_ONLY_FUNCTION}()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'capsule opening evidence is append-only'
                    USING ERRCODE = '55000';
            END;
            $$
            """
        )
    )
    for table, trigger in (
        (CLAIM_TABLE, "trg_wf_tctx_open_consume_append_only"),
        (ATTEMPT_TABLE, "trg_wf_tctx_open_attempt_append_only"),
        (RESULT_TABLE, "trg_wf_tctx_open_result_append_only"),
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
                IF EXISTS (SELECT 1 FROM {CLAIM_TABLE} LIMIT 1)
                   OR EXISTS (SELECT 1 FROM {ATTEMPT_TABLE} LIMIT 1)
                   OR EXISTS (SELECT 1 FROM {RESULT_TABLE} LIMIT 1) THEN
                    RAISE EXCEPTION
                        'refusing guarded downgrade: capsule opening evidence exists'
                        USING ERRCODE = '55000';
                END IF;
            END $$;
            """
        )
    )
    op.drop_table(RESULT_TABLE)
    op.drop_table(ATTEMPT_TABLE)
    op.drop_table(CLAIM_TABLE)
    op.drop_constraint("uq_wf_tctx_open_auth_consume_lineage", LEASE_TABLE, type_="unique")
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {APPEND_ONLY_FUNCTION}()"))
