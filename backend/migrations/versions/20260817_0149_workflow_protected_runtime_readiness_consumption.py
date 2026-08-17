"""Add atomic protected runtime-readiness consumption evidence.

Revision ID: 20260817_0149
Revises: 20260817_0148
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260817_0149"
down_revision: str | None = "20260817_0148"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEASE_TABLE = "workflow_event_runtime_readiness_auth_leases"
AUTH_CLAIM_TABLE = "workflow_event_runtime_readiness_auth_claims"
CLAIM_TABLE = "workflow_event_runtime_readiness_consumption_claims"
ATTEMPT_TABLE = "workflow_event_runtime_readiness_consumption_attempts"
RESULT_TABLE = "workflow_event_runtime_readiness_consumption_results"
APPEND_ONLY_FUNCTION = "reject_wf_rtready_cons_mutation"
FINAL_VALIDATION_FUNCTION = "validate_wf_rtready_cons_commit"

POLICY_DIGEST = "986fdb339467c04ab227dbbb28d73ca566a2888a3234fc1d82a729e104cb2c55"
SOURCE_POLICY_DIGEST = "4d797b56dd215b9ab74974fb841e50c554c7ecf7aa76380e697fe1a2ebd360c5"
RUNTIME_START_PROFILE_DIGEST = "233c49d3d7cb7d80655d2d2456431f38efecec49ad4c79d2100323754e829995"
READINESS_PROFILE_DIGEST = "830c47f035804b954d29813b226fe9ed2199d2b3b25f2a5694e5ca2d0fe219a3"
SCOPE_COLUMNS = ("organization_id", "environment_id", "site_id")


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
        sa.Column("authorization_lease_id", sa.String(128), nullable=False),
        sa.Column("authorization_lease_digest", sa.String(64), nullable=False),
        sa.Column("authorization_claim_id", sa.String(128), nullable=False),
        sa.Column("authorization_claim_digest", sa.String(64), nullable=False),
        sa.Column("start_result_id", sa.String(128), nullable=False),
        sa.Column("start_result_digest", sa.String(64), nullable=False),
        sa.Column("start_consumption_id", sa.String(128), nullable=False),
        sa.Column("start_attempt_id", sa.String(128), nullable=False),
        sa.Column("start_attempt_digest", sa.String(64), nullable=False),
        sa.Column("start_consumption_claim_id", sa.String(128), nullable=False),
        sa.Column("start_consumption_claim_digest", sa.String(64), nullable=False),
        sa.Column("runtime_start_authorization_lease_id", sa.String(128), nullable=False),
        sa.Column("runtime_start_authorization_lease_digest", sa.String(64), nullable=False),
        sa.Column("runtime_start_authorization_claim_id", sa.String(128), nullable=False),
        sa.Column("runtime_start_authorization_claim_digest", sa.String(64), nullable=False),
        sa.Column("use_result_id", sa.String(128), nullable=False),
        sa.Column("use_result_digest", sa.String(64), nullable=False),
        sa.Column("destination_deployment_id", sa.String(128), nullable=False),
        sa.Column("destination_generation", sa.Integer(), nullable=False),
        sa.Column("destination_fencing_token_digest", sa.String(64), nullable=False),
        sa.Column("runtime_slot_commitment", sa.String(64), nullable=False),
        sa.Column("runtime_slot_generation", sa.Integer(), nullable=False),
        sa.Column("runtime_envelope_id", sa.String(128), nullable=False),
        sa.Column("runtime_envelope_commitment", sa.String(64), nullable=False),
        sa.Column("runtime_envelope_generation", sa.Integer(), nullable=False),
        sa.Column("runtime_start_profile_id", sa.String(128), nullable=False),
        sa.Column("runtime_start_profile_version", sa.String(64), nullable=False),
        sa.Column("runtime_start_profile_digest", sa.String(64), nullable=False),
        sa.Column("readiness_profile_id", sa.String(128), nullable=False),
        sa.Column("readiness_profile_version", sa.String(64), nullable=False),
        sa.Column("readiness_profile_digest", sa.String(64), nullable=False),
        sa.Column("protected_operation_reference", sa.String(128), nullable=False),
        sa.Column("start_instruction_digest", sa.String(64), nullable=False),
        sa.Column("start_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("start_invocation_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("start_completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("start_result_recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("starter_receipt_digest", sa.String(64), nullable=False),
        sa.Column("start_result_state", sa.String(64), nullable=False),
        sa.Column("start_outcome_known", sa.Boolean(), nullable=False),
        sa.Column("runtime_started", sa.Boolean(), nullable=False),
        sa.Column("coordination_state", sa.String(64), nullable=False),
        sa.Column("runtime_start_attempt_pending", sa.Boolean(), nullable=False),
        sa.Column("runtime_start_attempt_terminal", sa.Boolean(), nullable=False),
        sa.Column("runtime_resumed", sa.Boolean(), nullable=False),
        sa.Column("process_created", sa.Boolean(), nullable=False),
        sa.Column("process_scheduled", sa.Boolean(), nullable=False),
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
        "protected_runtime_readiness_authority_granted",
    )


def _authority_columns() -> tuple[sa.Column[object], ...]:
    return tuple(sa.Column(name, sa.Boolean(), nullable=False) for name in _authority_names())


def _zero_authority() -> str:
    return " AND ".join(f"NOT {name}" for name in _authority_names())


def _contract_check() -> str:
    return (
        "consumer_subject_id = "
        "'service.workflow-protected-transport-target-context-capsule-consumer' "
        "AND consumer_audience = "
        "'audience.workflow-protected-transport-target-context-capsule-consumer' "
        "AND consumer_contract_id = "
        "'contract.workflow-protected-transport-target-context-capsule-consumer' "
        "AND consumer_contract_version = '1.0' "
        "AND purpose_id = 'purpose.workflow-protected-runtime-readiness-evaluation' "
        "AND policy_id = 'policy.workflow-protected-runtime-readiness-consumption' "
        f"AND policy_version = '1.0' AND policy_digest = '{POLICY_DIGEST}' "
        "AND source_policy_id = 'policy.workflow-protected-runtime-readiness-authorization' "
        f"AND source_policy_version = '1.0' AND source_policy_digest = '{SOURCE_POLICY_DIGEST}'"
    )


def _source_check() -> str:
    return (
        "start_result_state = 'runtime_started_in_protected_boundary' "
        "AND start_outcome_known AND runtime_started "
        "AND start_started_at <= start_completed_at "
        "AND start_completed_at <= start_result_recorded_at "
        "AND start_completed_at < start_invocation_deadline "
        "AND coordination_state = 'start_attempt_terminal' "
        "AND NOT runtime_start_attempt_pending AND runtime_start_attempt_terminal "
        "AND NOT runtime_resumed AND NOT process_created AND NOT process_scheduled "
        "AND runtime_slot_generation = runtime_envelope_generation "
        "AND runtime_slot_generation >= 2 AND destination_generation >= 1 "
        "AND length(start_result_digest) = 64 "
        "AND length(start_attempt_digest) = 64 "
        "AND length(start_consumption_claim_digest) = 64 "
        "AND length(runtime_start_authorization_lease_digest) = 64 "
        "AND length(runtime_start_authorization_claim_digest) = 64 "
        "AND length(use_result_digest) = 64 "
        "AND length(destination_fencing_token_digest) = 64 "
        "AND length(runtime_slot_commitment) = 64 "
        "AND length(runtime_envelope_commitment) = 64 "
        "AND length(start_instruction_digest) = 64 "
        "AND length(starter_receipt_digest) = 64 "
        "AND runtime_start_profile_id = 'profile.workflow-protected-runtime-start' "
        "AND runtime_start_profile_version = '1.0' "
        f"AND runtime_start_profile_digest = '{RUNTIME_START_PROFILE_DIGEST}' "
        "AND readiness_profile_id = 'profile.workflow-protected-runtime-readiness' "
        "AND readiness_profile_version = '1.0' "
        f"AND readiness_profile_digest = '{READINESS_PROFILE_DIGEST}'"
    )


def _lease_lineage_columns() -> tuple[str, ...]:
    return (
        "authorization_lease_id",
        "authorization_lease_digest",
        "authorization_claim_id",
        "authorization_claim_digest",
        "start_result_id",
        "start_result_digest",
        "start_consumption_id",
        "start_attempt_id",
        "start_attempt_digest",
        "start_consumption_claim_id",
        "start_consumption_claim_digest",
        "runtime_start_authorization_lease_id",
        "runtime_start_authorization_lease_digest",
        "runtime_start_authorization_claim_id",
        "runtime_start_authorization_claim_digest",
        "use_result_id",
        "use_result_digest",
        "destination_deployment_id",
        "destination_generation",
        "destination_fencing_token_digest",
        "runtime_slot_commitment",
        "runtime_slot_generation",
        "runtime_envelope_id",
        "runtime_envelope_commitment",
        "runtime_envelope_generation",
        "runtime_start_profile_id",
        "runtime_start_profile_version",
        "runtime_start_profile_digest",
        "readiness_profile_id",
        "readiness_profile_version",
        "readiness_profile_digest",
    )


def _lease_outcome_columns(*, include_operation_reference: bool = True) -> tuple[str, ...]:
    columns = (
        "authorization_lease_id",
        "authorization_lease_digest",
        "start_instruction_digest",
        "start_started_at",
        "start_invocation_deadline",
        "start_completed_at",
        "start_result_recorded_at",
        "starter_receipt_digest",
        "start_result_state",
        "start_outcome_known",
        "runtime_started",
        "coordination_state",
        "runtime_start_attempt_pending",
        "runtime_start_attempt_terminal",
        "runtime_resumed",
        "process_created",
        "process_scheduled",
    )
    if include_operation_reference:
        return (*columns[:2], "protected_operation_reference", *columns[2:])
    return columns


def _lease_constraints(*, prefix: str) -> tuple[sa.ForeignKeyConstraint, ...]:
    lineage = _lease_lineage_columns()
    lineage_remote = (
        "authorization_lease_id",
        "canonical_digest",
        "claim_id",
        "claim_digest",
        *lineage[4:],
    )
    outcome = _lease_outcome_columns(include_operation_reference=prefix == "claim")
    outcome_remote = ("authorization_lease_id", "canonical_digest", *outcome[2:])
    return (
        sa.ForeignKeyConstraint(
            lineage,
            [f"{LEASE_TABLE}.{name}" for name in lineage_remote],
            name=f"fk_wf_rtready_cons_{prefix}_lease",
        ),
        sa.ForeignKeyConstraint(
            outcome,
            [f"{LEASE_TABLE}.{name}" for name in outcome_remote],
            name=f"fk_wf_rtready_cons_{prefix}_outcome",
        ),
        sa.ForeignKeyConstraint(
            [
                *SCOPE_COLUMNS,
                "authorization_claim_id",
                "authorization_claim_digest",
                "authorization_lease_id",
            ],
            [
                *(f"{AUTH_CLAIM_TABLE}.{name}" for name in SCOPE_COLUMNS),
                f"{AUTH_CLAIM_TABLE}.claim_id",
                f"{AUTH_CLAIM_TABLE}.canonical_digest",
                f"{AUTH_CLAIM_TABLE}.authorization_lease_id",
            ],
            name=f"fk_wf_rtready_cons_{prefix}_auth_claim",
        ),
    )


def _common_constraints(*, prefix: str) -> tuple[sa.Constraint, ...]:
    return (
        *_lease_constraints(prefix=prefix),
        sa.CheckConstraint(_contract_check(), name=f"ck_wf_rtready_cons_{prefix}_contract"),
        sa.CheckConstraint(_source_check(), name=f"ck_wf_rtready_cons_{prefix}_source"),
    )


def upgrade() -> None:
    lease_lineage = _lease_lineage_columns()
    op.create_unique_constraint(
        "uq_wf_rtready_auth_lease_identity",
        LEASE_TABLE,
        ["authorization_lease_id", "canonical_digest"],
    )
    op.create_unique_constraint(
        "uq_wf_rtready_auth_lease_consume",
        LEASE_TABLE,
        [
            "authorization_lease_id",
            "canonical_digest",
            "claim_id",
            "claim_digest",
            *lease_lineage[4:],
        ],
    )
    lease_outcome = _lease_outcome_columns()
    op.create_unique_constraint(
        "uq_wf_rtready_auth_lease_consume_outcome",
        LEASE_TABLE,
        ["authorization_lease_id", "canonical_digest", *lease_outcome[2:]],
    )
    projected_lease_outcome = _lease_outcome_columns(include_operation_reference=False)
    op.create_unique_constraint(
        "uq_wf_rtready_auth_lease_consume_outcome_projection",
        LEASE_TABLE,
        ["authorization_lease_id", "canonical_digest", *projected_lease_outcome[2:]],
    )

    op.create_table(
        CLAIM_TABLE,
        sa.Column("claim_id", sa.String(128), primary_key=True),
        sa.Column("consumption_id", sa.String(128), nullable=False),
        sa.Column("attempt_id", sa.String(128), nullable=False),
        *_source_columns(),
        *_identity_columns(),
        sa.Column("idempotency_scope_id", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("idempotency_digest", sa.String(64), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("irreversible_consumption_acknowledged", sa.Boolean(), nullable=False),
        sa.Column("uncertainty_no_retry_acknowledged", sa.Boolean(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        *_common_constraints(prefix="claim"),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_rtready_cons_claim_lease"),
        sa.UniqueConstraint("consumption_id", name="uq_wf_rtready_cons_claim_consumption"),
        sa.UniqueConstraint("attempt_id", name="uq_wf_rtready_cons_claim_attempt"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rtready_cons_claim_digest"),
        sa.UniqueConstraint(
            "organization_id",
            "environment_id",
            "site_id",
            "consumer_subject_id",
            "consumer_audience",
            "idempotency_digest",
            name="uq_wf_rtready_cons_claim_tenant_idem",
        ),
        sa.UniqueConstraint(
            "claim_id",
            "canonical_digest",
            "consumption_id",
            "attempt_id",
            "authorization_lease_id",
            name="uq_wf_rtready_cons_claim_lineage",
        ),
        sa.CheckConstraint(
            "irreversible_consumption_acknowledged "
            "AND uncertainty_no_retry_acknowledged "
            "AND runtime_slot_generation = runtime_envelope_generation "
            "AND runtime_slot_generation >= 2 "
            "AND length(idempotency_scope_id) = 64 "
            "AND length(idempotency_digest) = 64 "
            "AND length(request_fingerprint) = 64 AND " + _zero_authority(),
            name="ck_wf_rtready_cons_claim_semantics",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object'",
            name="ck_wf_rtready_cons_claim_payload",
        ),
    )
    op.create_index(
        "ix_wf_rtready_cons_claim_scope",
        CLAIM_TABLE,
        ["organization_id", "environment_id", "site_id", "claimed_at"],
    )

    op.create_table(
        ATTEMPT_TABLE,
        sa.Column("attempt_id", sa.String(128), primary_key=True),
        sa.Column("consumption_id", sa.String(128), nullable=False),
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("claim_digest", sa.String(64), nullable=False),
        *_source_columns(),
        *_identity_columns(),
        sa.Column("expected_assessment_count_pre", sa.Integer(), nullable=False),
        sa.Column("expected_assessment_count_post", sa.Integer(), nullable=False),
        sa.Column("assessor_contract_id", sa.String(128), nullable=False),
        sa.Column("assessor_contract_version", sa.String(64), nullable=False),
        sa.Column("assessor_id", sa.String(128), nullable=False),
        sa.Column("assessor_version", sa.String(64), nullable=False),
        sa.Column("receipt_verification_signing_key_id", sa.String(128), nullable=False),
        sa.Column("request_nonce_digest", sa.String(64), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invocation_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(64), nullable=False),
        sa.Column("instruction_digest", sa.String(64), nullable=False),
        sa.Column("instruction_signing_key_id", sa.String(128), nullable=False),
        sa.Column("instruction_signature_algorithm", sa.String(64), nullable=False),
        sa.Column("signed_instruction_envelope_digest", sa.String(64), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("signed_instruction_envelope_payload", postgresql.JSONB(), nullable=False),
        *_common_constraints(prefix="attempt"),
        sa.ForeignKeyConstraint(
            ["claim_id", "claim_digest", "consumption_id", "attempt_id", "authorization_lease_id"],
            [
                f"{CLAIM_TABLE}.claim_id",
                f"{CLAIM_TABLE}.canonical_digest",
                f"{CLAIM_TABLE}.consumption_id",
                f"{CLAIM_TABLE}.attempt_id",
                f"{CLAIM_TABLE}.authorization_lease_id",
            ],
            name="fk_wf_rtready_cons_attempt_claim",
        ),
        sa.UniqueConstraint("claim_id", name="uq_wf_rtready_cons_attempt_claim"),
        sa.UniqueConstraint("consumption_id", name="uq_wf_rtready_cons_attempt_consumption"),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_rtready_cons_attempt_lease"),
        sa.UniqueConstraint("instruction_digest", name="uq_wf_rtready_cons_attempt_instruction"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rtready_cons_attempt_digest"),
        sa.UniqueConstraint(
            "attempt_id",
            "canonical_digest",
            "claim_id",
            "claim_digest",
            "consumption_id",
            "authorization_lease_id",
            "authorization_lease_digest",
            "start_result_id",
            "start_result_digest",
            "destination_deployment_id",
            "destination_generation",
            "destination_fencing_token_digest",
            "runtime_slot_commitment",
            "runtime_slot_generation",
            "runtime_envelope_id",
            "runtime_envelope_commitment",
            "runtime_envelope_generation",
            "readiness_profile_id",
            "readiness_profile_version",
            "readiness_profile_digest",
            "protected_operation_reference",
            "instruction_digest",
            "started_at",
            "invocation_deadline",
            name="uq_wf_rtready_cons_attempt_result",
        ),
        sa.CheckConstraint(
            "state = 'runtime_readiness_attempt_started' "
            "AND claimed_at <= started_at AND started_at < invocation_deadline "
            "AND expected_assessment_count_pre = 0 "
            "AND expected_assessment_count_post = 1 "
            "AND runtime_slot_generation = runtime_envelope_generation",
            name="ck_wf_rtready_cons_attempt_state",
        ),
        sa.CheckConstraint(
            "assessor_contract_id = 'contract.workflow-protected-runtime-readiness-assessor' "
            "AND assessor_contract_version = '1.0' "
            "AND assessor_id = 'assessor.workflow-protected-runtime-readiness' "
            "AND assessor_version = '1.0' "
            "AND receipt_verification_signing_key_id = 'key.workflow-protected-runtime-readiness-receipt.v1' "
            "AND instruction_signing_key_id = 'key.workflow-protected-runtime-readiness-instruction.v1' "
            "AND instruction_signature_algorithm = 'hmac-sha256' "
            "AND length(instruction_digest) = 64 "
            "AND length(signed_instruction_envelope_digest) = 64 "
            "AND length(request_nonce_digest) = 64 AND " + _zero_authority(),
            name="ck_wf_rtready_cons_attempt_instruction",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object' "
            "AND jsonb_typeof(signed_instruction_envelope_payload) = 'object' "
            "AND signed_instruction_envelope_payload <> '{}'::jsonb",
            name="ck_wf_rtready_cons_attempt_payload",
        ),
    )
    op.create_index(
        "ix_wf_rtready_cons_attempt_scope",
        ATTEMPT_TABLE,
        ["organization_id", "environment_id", "site_id", "started_at"],
    )

    op.create_table(
        RESULT_TABLE,
        sa.Column("result_id", sa.String(128), primary_key=True),
        sa.Column("consumption_id", sa.String(128), nullable=False),
        sa.Column("attempt_id", sa.String(128), nullable=False),
        sa.Column("attempt_digest", sa.String(64), nullable=False),
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("claim_digest", sa.String(64), nullable=False),
        *_source_columns(),
        *_identity_columns(),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invocation_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("instruction_digest", sa.String(64), nullable=False),
        sa.Column("state", sa.String(64), nullable=False),
        sa.Column("failure_class", sa.String(64), nullable=True),
        sa.Column("outcome_known", sa.Boolean(), nullable=False),
        sa.Column("assessment_performed", sa.Boolean(), nullable=True),
        sa.Column("runtime_ready", sa.Boolean(), nullable=True),
        sa.Column("assessor_receipt_digest", sa.String(64), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("assessor_receipt_payload", postgresql.JSONB(), nullable=True),
        *_common_constraints(prefix="result"),
        sa.ForeignKeyConstraint(
            [
                "attempt_id",
                "attempt_digest",
                "claim_id",
                "claim_digest",
                "consumption_id",
                "authorization_lease_id",
                "authorization_lease_digest",
                "start_result_id",
                "start_result_digest",
                "destination_deployment_id",
                "destination_generation",
                "destination_fencing_token_digest",
                "runtime_slot_commitment",
                "runtime_slot_generation",
                "runtime_envelope_id",
                "runtime_envelope_commitment",
                "runtime_envelope_generation",
                "readiness_profile_id",
                "readiness_profile_version",
                "readiness_profile_digest",
                "protected_operation_reference",
                "instruction_digest",
                "started_at",
                "invocation_deadline",
            ],
            [
                f"{ATTEMPT_TABLE}.attempt_id",
                f"{ATTEMPT_TABLE}.canonical_digest",
                f"{ATTEMPT_TABLE}.claim_id",
                f"{ATTEMPT_TABLE}.claim_digest",
                f"{ATTEMPT_TABLE}.consumption_id",
                f"{ATTEMPT_TABLE}.authorization_lease_id",
                f"{ATTEMPT_TABLE}.authorization_lease_digest",
                f"{ATTEMPT_TABLE}.start_result_id",
                f"{ATTEMPT_TABLE}.start_result_digest",
                f"{ATTEMPT_TABLE}.destination_deployment_id",
                f"{ATTEMPT_TABLE}.destination_generation",
                f"{ATTEMPT_TABLE}.destination_fencing_token_digest",
                f"{ATTEMPT_TABLE}.runtime_slot_commitment",
                f"{ATTEMPT_TABLE}.runtime_slot_generation",
                f"{ATTEMPT_TABLE}.runtime_envelope_id",
                f"{ATTEMPT_TABLE}.runtime_envelope_commitment",
                f"{ATTEMPT_TABLE}.runtime_envelope_generation",
                f"{ATTEMPT_TABLE}.readiness_profile_id",
                f"{ATTEMPT_TABLE}.readiness_profile_version",
                f"{ATTEMPT_TABLE}.readiness_profile_digest",
                f"{ATTEMPT_TABLE}.protected_operation_reference",
                f"{ATTEMPT_TABLE}.instruction_digest",
                f"{ATTEMPT_TABLE}.started_at",
                f"{ATTEMPT_TABLE}.invocation_deadline",
            ],
            name="fk_wf_rtready_cons_result_attempt",
        ),
        sa.UniqueConstraint("attempt_id", name="uq_wf_rtready_cons_result_attempt"),
        sa.UniqueConstraint("claim_id", name="uq_wf_rtready_cons_result_claim"),
        sa.UniqueConstraint("consumption_id", name="uq_wf_rtready_cons_result_consumption"),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_rtready_cons_result_lease"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rtready_cons_result_digest"),
        sa.CheckConstraint(
            "recorded_at >= started_at AND "
            "((state = 'runtime_readiness_outcome_uncertain' "
            "AND failure_class = 'runtime_readiness_outcome_uncertain' "
            "AND NOT outcome_known AND assessment_performed IS NULL "
            "AND runtime_ready IS NULL AND assessor_receipt_digest IS NULL "
            "AND assessor_receipt_payload IS NULL AND completed_at IS NULL) OR "
            "(state = 'runtime_ready_in_protected_boundary' "
            "AND failure_class IS NULL AND outcome_known AND assessment_performed "
            "AND runtime_ready AND assessor_receipt_digest IS NOT NULL "
            "AND assessor_receipt_payload IS NOT NULL AND completed_at IS NOT NULL "
            "AND started_at <= completed_at AND completed_at <= recorded_at "
            "AND completed_at < invocation_deadline) OR "
            "(state = 'runtime_not_ready_in_protected_boundary' "
            "AND failure_class IS NULL AND outcome_known AND assessment_performed "
            "AND NOT runtime_ready AND assessor_receipt_digest IS NOT NULL "
            "AND assessor_receipt_payload IS NOT NULL AND completed_at IS NOT NULL "
            "AND started_at <= completed_at AND completed_at <= recorded_at "
            "AND completed_at < invocation_deadline) OR "
            "(state = 'runtime_readiness_failed_without_assessment' "
            "AND failure_class IN ('protected_assessor_rejected_without_assessment', "
            "'protected_assessment_failed_without_assessment') "
            "AND outcome_known AND NOT assessment_performed AND runtime_ready IS NULL "
            "AND assessor_receipt_digest IS NOT NULL "
            "AND assessor_receipt_payload IS NOT NULL AND completed_at IS NOT NULL "
            "AND started_at <= completed_at AND completed_at <= recorded_at "
            "AND completed_at < invocation_deadline))",
            name="ck_wf_rtready_cons_result_outcome",
        ),
        sa.CheckConstraint(
            "runtime_slot_generation = runtime_envelope_generation "
            "AND runtime_slot_generation >= 2 AND " + _zero_authority(),
            name="ck_wf_rtready_cons_result_semantics",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object' "
            "AND (assessor_receipt_payload IS NULL "
            "OR jsonb_typeof(assessor_receipt_payload) = 'object')",
            name="ck_wf_rtready_cons_result_payload",
        ),
    )
    op.create_index(
        "ix_wf_rtready_cons_result_scope",
        RESULT_TABLE,
        ["organization_id", "environment_id", "site_id", "recorded_at"],
    )

    op.execute(
        sa.text(f"""
        CREATE FUNCTION {FINAL_VALIDATION_FUNCTION}() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            lease_issued_at timestamptz;
            lease_valid_until timestamptz;
            lease_effective_until timestamptz;
            attempt_started_at timestamptz;
            attempt_deadline timestamptz;
        BEGIN
            SELECT issued_at, valid_until, effective_until
              INTO lease_issued_at, lease_valid_until, lease_effective_until
              FROM {LEASE_TABLE}
             WHERE authorization_lease_id = NEW.authorization_lease_id
               AND canonical_digest = NEW.authorization_lease_digest;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'protected runtime-readiness authorization lineage is missing'
                    USING ERRCODE = '23503';
            END IF;
            SELECT started_at, invocation_deadline
              INTO attempt_started_at, attempt_deadline
              FROM {ATTEMPT_TABLE}
             WHERE claim_id = NEW.claim_id
               AND attempt_id = NEW.attempt_id
               AND authorization_lease_id = NEW.authorization_lease_id;
            IF NOT FOUND THEN
                RAISE EXCEPTION 'readiness claim and attempt must commit atomically'
                    USING ERRCODE = '23514';
            END IF;
            IF NEW.claimed_at < lease_issued_at
               OR attempt_started_at < NEW.claimed_at
               OR attempt_deadline > lease_valid_until
               OR attempt_deadline > lease_effective_until
               OR clock_timestamp() >= lease_valid_until
               OR clock_timestamp() >= lease_effective_until
               OR clock_timestamp() + INTERVAL '100 milliseconds' > attempt_deadline THEN
                RAISE EXCEPTION 'protected runtime-readiness lease window is no longer valid'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    )
    op.execute(
        sa.text(
            f"CREATE CONSTRAINT TRIGGER trg_wf_rtready_cons_final_window "
            f"AFTER INSERT ON {CLAIM_TABLE} DEFERRABLE INITIALLY DEFERRED "
            f"FOR EACH ROW EXECUTE FUNCTION {FINAL_VALIDATION_FUNCTION}()"
        )
    )

    op.execute(
        sa.text(f"""
        CREATE FUNCTION {APPEND_ONLY_FUNCTION}() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'protected runtime-readiness consumption evidence is append-only'
                USING ERRCODE = '55000';
        END;
        $$
    """)
    )
    for table, trigger in (
        (CLAIM_TABLE, "trg_wf_rtready_cons_claim_append_only"),
        (ATTEMPT_TABLE, "trg_wf_rtready_cons_attempt_append_only"),
        (RESULT_TABLE, "trg_wf_rtready_cons_result_append_only"),
    ):
        op.execute(
            sa.text(
                f"CREATE TRIGGER {trigger} BEFORE UPDATE OR DELETE ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION {APPEND_ONLY_FUNCTION}()"
            )
        )
    for table, trigger in (
        (CLAIM_TABLE, "trg_wf_rtready_cons_claim_no_truncate"),
        (ATTEMPT_TABLE, "trg_wf_rtready_cons_attempt_no_truncate"),
        (RESULT_TABLE, "trg_wf_rtready_cons_result_no_truncate"),
    ):
        op.execute(
            sa.text(
                f"CREATE TRIGGER {trigger} BEFORE TRUNCATE ON {table} "
                f"FOR EACH STATEMENT EXECUTE FUNCTION {APPEND_ONLY_FUNCTION}()"
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
                    'refusing guarded downgrade: protected runtime-readiness consumption evidence exists'
                    USING ERRCODE = '55000';
            END IF;
        END $$;
    """)
    )
    op.drop_table(RESULT_TABLE)
    op.drop_table(ATTEMPT_TABLE)
    op.drop_table(CLAIM_TABLE)
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {FINAL_VALIDATION_FUNCTION}()"))
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {APPEND_ONLY_FUNCTION}()"))
    op.drop_constraint("uq_wf_rtready_auth_lease_consume_outcome", LEASE_TABLE, type_="unique")
    op.drop_constraint(
        "uq_wf_rtready_auth_lease_consume_outcome_projection",
        LEASE_TABLE,
        type_="unique",
    )
    op.drop_constraint("uq_wf_rtready_auth_lease_consume", LEASE_TABLE, type_="unique")
    op.drop_constraint("uq_wf_rtready_auth_lease_identity", LEASE_TABLE, type_="unique")
