"""Add atomic protected runtime process-scheduling consumption evidence.

Revision ID: 20260821_0153
Revises: 20260820_0152
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260821_0153"
down_revision: str | None = "20260820_0152"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUTH_LEASE_TABLE = "workflow_event_runtime_process_scheduling_auth_leases"
AUTH_CLAIM_TABLE = "workflow_event_runtime_process_scheduling_auth_claims"
CLAIM_TABLE = "workflow_event_runtime_process_scheduling_consumption_claims"
ATTEMPT_TABLE = "workflow_event_runtime_process_scheduling_attempts"
RESULT_TABLE = "workflow_event_runtime_process_scheduling_results"
APPEND_ONLY_FUNCTION = "reject_wf_rtpsched_cons_mutation"
SOURCE_POLICY_DIGEST = "45b55d2fa3eabacde7659d2bf5d447c4f72d9290a7cdb515eb8ac0534b4d4760"
POLICY_DIGEST = "138e8bbdf1472df0a9adfde7271b177d0d133f865d6e2548597a0b33143a6464"
PRIMITIVE_DIGEST = "f7a15804784b14745672b8902a771897e6971e2311120021bf819c387d1303e3"
SCOPE = ("organization_id", "environment_id", "site_id")


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
    strings_128 = (
        "process_creation_result_id",
        "process_creation_consumption_id",
        "process_creation_attempt_id",
        "process_creation_claim_id",
        "process_creation_authorization_lease_id",
        "process_creation_authorization_claim_id",
        "runtime_envelope_id",
        "destination_deployment_id",
        "process_creation_profile_id",
        "primitive_id",
        "scheduling_authorization_lease_id",
        "scheduling_authorization_claim_id",
        "process_state_attestation_id",
        "scheduling_profile_id",
    )
    strings_64 = (
        "process_creation_result_digest",
        "process_creation_attempt_digest",
        "process_creation_claim_digest",
        "process_creation_authorization_lease_digest",
        "process_creation_authorization_claim_digest",
        "runtime_envelope_commitment",
        "destination_fencing_token_digest",
        "runtime_slot_commitment",
        "process_creation_profile_version",
        "process_creation_profile_digest",
        "primitive_version",
        "primitive_digest",
        "process_creation_result_state",
        "process_creation_failure_class",
        "process_creation_receipt_digest",
        "scheduling_authorization_lease_digest",
        "scheduling_authorization_claim_digest",
        "scheduling_authorization_state",
        "process_state_attestation_digest",
        "scheduling_profile_version",
        "scheduling_profile_digest",
    )
    return (
        *(sa.Column(name, sa.String(128), nullable=False) for name in strings_128),
        *(
            sa.Column(
                name,
                sa.String(64),
                nullable=name == "process_creation_failure_class",
            )
            for name in strings_64
        ),
        sa.Column("runtime_envelope_generation", sa.Integer(), nullable=False),
        sa.Column("destination_generation", sa.Integer(), nullable=False),
        sa.Column("runtime_slot_generation", sa.Integer(), nullable=False),
        sa.Column("process_creation_outcome_known", sa.Boolean(), nullable=False),
        sa.Column("process_created", sa.Boolean(), nullable=False),
        sa.Column("process_sealed", sa.Boolean(), nullable=False),
        sa.Column("process_suspended", sa.Boolean(), nullable=False),
        sa.Column("process_scheduled", sa.Boolean(), nullable=False),
        sa.Column("process_resumed", sa.Boolean(), nullable=False),
        sa.Column("process_dispatched", sa.Boolean(), nullable=False),
        sa.Column("process_executed", sa.Boolean(), nullable=False),
        sa.Column("process_creation_completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "process_creation_result_recorded_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("source_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "scheduling_authorization_issued_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "scheduling_authorization_valid_until", sa.DateTime(timezone=True), nullable=False
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
        "protected_runtime_start_authority_granted",
        "protected_runtime_readiness_authority_granted",
        "protected_runtime_process_creation_authority_granted",
        "protected_runtime_process_scheduling_authority_granted",
    )


def _authority_columns() -> tuple[sa.Column[object], ...]:
    return tuple(sa.Column(name, sa.Boolean(), nullable=False) for name in _authority_names())


def _zero_authority() -> str:
    return " AND ".join(f"NOT {name}" for name in _authority_names())


def _contract_check() -> str:
    return (
        "policy_id = 'policy.workflow-protected-runtime-process-scheduling-consumption' "
        f"AND policy_version = '1.0' AND policy_digest = '{POLICY_DIGEST}' "
        "AND source_policy_id = 'policy.workflow-protected-runtime-process-scheduling-authorization' "
        f"AND source_policy_version = '1.0' AND source_policy_digest = '{SOURCE_POLICY_DIGEST}'"
    )


def _source_check() -> str:
    return (
        "scheduling_authorization_state = 'authorized_unconsumed' "
        "AND scheduling_authorization_issued_at < scheduling_authorization_valid_until "
        "AND process_creation_result_state = 'process_created_suspended_in_protected_boundary' "
        "AND process_creation_outcome_known AND process_created AND process_sealed "
        "AND process_suspended AND NOT process_scheduled AND NOT process_resumed "
        "AND NOT process_dispatched AND NOT process_executed "
        "AND process_creation_failure_class IS NULL "
        "AND runtime_slot_generation = runtime_envelope_generation "
        "AND runtime_slot_generation >= 2"
    )


def _source_constraints(prefix: str) -> tuple[sa.ForeignKeyConstraint, ...]:
    return (
        sa.ForeignKeyConstraint(
            (
                *SCOPE,
                "scheduling_authorization_lease_id",
                "scheduling_authorization_lease_digest",
                "scheduling_authorization_claim_id",
                "scheduling_authorization_claim_digest",
            ),
            tuple(
                f"{AUTH_LEASE_TABLE}.{name}"
                for name in (
                    *SCOPE,
                    "authorization_lease_id",
                    "canonical_digest",
                    "claim_id",
                    "claim_digest",
                )
            ),
            name=f"fk_wf_rtpsched_cons_{prefix}_lease",
        ),
        sa.ForeignKeyConstraint(
            (
                *SCOPE,
                "scheduling_authorization_claim_id",
                "scheduling_authorization_claim_digest",
                "scheduling_authorization_lease_id",
            ),
            tuple(
                f"{AUTH_CLAIM_TABLE}.{name}"
                for name in (*SCOPE, "claim_id", "canonical_digest", "authorization_lease_id")
            ),
            name=f"fk_wf_rtpsched_cons_{prefix}_claim",
        ),
    )


def _common_constraints(prefix: str) -> tuple[sa.Constraint, ...]:
    return (
        *_source_constraints(prefix),
        sa.CheckConstraint(_contract_check(), name=f"ck_wf_rtpsched_cons_{prefix}_contract"),
        sa.CheckConstraint(_source_check(), name=f"ck_wf_rtpsched_cons_{prefix}_source"),
    )


def _create_claim() -> None:
    op.create_table(
        CLAIM_TABLE,
        sa.Column("claim_id", sa.String(128), primary_key=True),
        sa.Column("consumption_id", sa.String(128), nullable=False),
        sa.Column("attempt_id", sa.String(128), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("idempotency_digest", sa.String(64), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("irreversible_consumption_acknowledged", sa.Boolean(), nullable=False),
        sa.Column("uncertainty_no_retry_acknowledged", sa.Boolean(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        *_source_columns(),
        *_identity_columns(),
        *_authority_columns(),
        *_common_constraints("claim"),
        sa.UniqueConstraint(
            "scheduling_authorization_lease_id", name="uq_wf_rtpsched_cons_claim_lease"
        ),
        sa.UniqueConstraint("consumption_id", name="uq_wf_rtpsched_cons_claim_consumption"),
        sa.UniqueConstraint("attempt_id", name="uq_wf_rtpsched_cons_claim_attempt"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rtpsched_cons_claim_digest"),
        sa.UniqueConstraint(
            *SCOPE,
            "consumer_subject_id",
            "consumer_audience",
            "idempotency_digest",
            name="uq_wf_rtpsched_cons_claim_idem",
        ),
        sa.UniqueConstraint(
            "claim_id",
            "canonical_digest",
            "consumption_id",
            "attempt_id",
            "scheduling_authorization_lease_id",
            name="uq_wf_rtpsched_cons_claim_lineage",
        ),
        sa.CheckConstraint(
            "irreversible_consumption_acknowledged "
            "AND uncertainty_no_retry_acknowledged "
            "AND scheduling_authorization_issued_at <= claimed_at "
            "AND claimed_at < scheduling_authorization_valid_until "
            "AND length(idempotency_scope_id) = 64 "
            "AND length(idempotency_digest) = 64 "
            "AND length(request_fingerprint) = 64 AND "
            + _zero_authority(),
            name="ck_wf_rtpsched_cons_claim_semantics",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object'", name="ck_wf_rtpsched_cons_claim_payload"
        ),
    )
    op.create_index(
        "ix_wf_rtpsched_cons_claim_scope", CLAIM_TABLE, [*SCOPE, "claimed_at"]
    )


def _create_attempt() -> None:
    op.create_table(
        ATTEMPT_TABLE,
        sa.Column("attempt_id", sa.String(128), primary_key=True),
        sa.Column("consumption_id", sa.String(128), nullable=False),
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("claim_digest", sa.String(64), nullable=False),
        sa.Column("expected_scheduled_count_pre", sa.Integer(), nullable=False),
        sa.Column("expected_scheduled_count_post", sa.Integer(), nullable=False),
        sa.Column("scheduler_primitive_id", sa.String(128), nullable=False),
        sa.Column("scheduler_primitive_version", sa.String(64), nullable=False),
        sa.Column("scheduler_primitive_digest", sa.String(64), nullable=False),
        sa.Column("scheduler_contract_id", sa.String(128), nullable=False),
        sa.Column("scheduler_contract_version", sa.String(64), nullable=False),
        sa.Column("scheduler_id", sa.String(128), nullable=False),
        sa.Column("scheduler_version", sa.String(64), nullable=False),
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
        sa.Column("protected_operation_reference", sa.String(128), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("signed_instruction_envelope_payload", postgresql.JSONB(), nullable=False),
        *_source_columns(),
        *_identity_columns(),
        *_authority_columns(),
        *_common_constraints("attempt"),
        sa.ForeignKeyConstraint(
            (
                "claim_id",
                "claim_digest",
                "consumption_id",
                "attempt_id",
                "scheduling_authorization_lease_id",
            ),
            tuple(
                f"{CLAIM_TABLE}.{name}"
                for name in (
                    "claim_id",
                    "canonical_digest",
                    "consumption_id",
                    "attempt_id",
                    "scheduling_authorization_lease_id",
                )
            ),
            name="fk_wf_rtpsched_cons_attempt_cons_claim",
        ),
        sa.UniqueConstraint("claim_id", name="uq_wf_rtpsched_cons_attempt_cons_claim"),
        sa.UniqueConstraint("consumption_id", name="uq_wf_rtpsched_cons_attempt_consumption"),
        sa.UniqueConstraint(
            "scheduling_authorization_lease_id", name="uq_wf_rtpsched_cons_attempt_lease"
        ),
        sa.UniqueConstraint("instruction_digest", name="uq_wf_rtpsched_cons_attempt_instruction"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rtpsched_cons_attempt_digest"),
        sa.UniqueConstraint(
            "attempt_id",
            "canonical_digest",
            "claim_id",
            "claim_digest",
            "consumption_id",
            "scheduling_authorization_lease_id",
            "scheduling_authorization_lease_digest",
            "runtime_envelope_id",
            "runtime_envelope_commitment",
            "runtime_envelope_generation",
            "scheduling_profile_id",
            "scheduling_profile_version",
            "scheduling_profile_digest",
            "scheduler_primitive_id",
            "scheduler_primitive_version",
            "scheduler_primitive_digest",
            "protected_operation_reference",
            "instruction_digest",
            "started_at",
            "invocation_deadline",
            name="uq_wf_rtpsched_cons_attempt_result",
        ),
        sa.CheckConstraint(
            "state = 'process_scheduling_attempt_started' "
            "AND claimed_at <= started_at AND started_at < invocation_deadline "
            "AND expected_scheduled_count_pre = 0 AND expected_scheduled_count_post = 1",
            name="ck_wf_rtpsched_cons_attempt_state",
        ),
        sa.CheckConstraint(
            "scheduler_primitive_id = 'primitive.workflow-protected-runtime-schedule-sealed-suspended-process' "
            "AND scheduler_primitive_version = '1.0' "
            f"AND scheduler_primitive_digest = '{PRIMITIVE_DIGEST}' "
            "AND scheduler_contract_id = 'contract.workflow-protected-runtime-suspended-process-scheduler' "
            "AND scheduler_contract_version = '1.0' "
            "AND scheduler_id = 'scheduler.workflow-protected-runtime-suspended-process' "
            "AND scheduler_version = '1.0' "
            "AND instruction_signature_algorithm = 'hmac-sha256' "
            "AND length(instruction_digest) = 64 "
            "AND length(signed_instruction_envelope_digest) = 64 "
            "AND length(request_nonce_digest) = 64 AND "
            + _zero_authority(),
            name="ck_wf_rtpsched_cons_attempt_instruction",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object' "
            "AND jsonb_typeof(signed_instruction_envelope_payload) = 'object' "
            "AND signed_instruction_envelope_payload <> '{}'::jsonb",
            name="ck_wf_rtpsched_cons_attempt_payload",
        ),
    )
    op.create_index(
        "ix_wf_rtpsched_cons_attempt_scope", ATTEMPT_TABLE, [*SCOPE, "started_at"]
    )


def _create_result() -> None:
    op.create_table(
        RESULT_TABLE,
        sa.Column("result_id", sa.String(128), primary_key=True),
        sa.Column("consumption_id", sa.String(128), nullable=False),
        sa.Column("attempt_id", sa.String(128), nullable=False),
        sa.Column("attempt_digest", sa.String(64), nullable=False),
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("claim_digest", sa.String(64), nullable=False),
        sa.Column("scheduler_primitive_id", sa.String(128), nullable=False),
        sa.Column("scheduler_primitive_version", sa.String(64), nullable=False),
        sa.Column("scheduler_primitive_digest", sa.String(64), nullable=False),
        sa.Column("protected_operation_reference", sa.String(128), nullable=False),
        sa.Column("instruction_digest", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invocation_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(64), nullable=False),
        sa.Column("failure_class", sa.String(64), nullable=True),
        sa.Column("outcome_known", sa.Boolean(), nullable=False),
        sa.Column("result_process_scheduled", sa.Boolean(), nullable=True),
        sa.Column("result_process_suspended", sa.Boolean(), nullable=True),
        sa.Column("result_process_runnable", sa.Boolean(), nullable=True),
        sa.Column("result_process_resumed", sa.Boolean(), nullable=False),
        sa.Column("result_process_dispatched", sa.Boolean(), nullable=False),
        sa.Column("result_process_executed", sa.Boolean(), nullable=False),
        sa.Column("receipt_digest", sa.String(64), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("receipt_payload", postgresql.JSONB(), nullable=True),
        *_source_columns(),
        *_identity_columns(),
        *_authority_columns(),
        *_common_constraints("result"),
        sa.ForeignKeyConstraint(
            (
                "attempt_id",
                "attempt_digest",
                "claim_id",
                "claim_digest",
                "consumption_id",
                "scheduling_authorization_lease_id",
                "scheduling_authorization_lease_digest",
                "runtime_envelope_id",
                "runtime_envelope_commitment",
                "runtime_envelope_generation",
                "scheduling_profile_id",
                "scheduling_profile_version",
                "scheduling_profile_digest",
                "scheduler_primitive_id",
                "scheduler_primitive_version",
                "scheduler_primitive_digest",
                "protected_operation_reference",
                "instruction_digest",
                "started_at",
                "invocation_deadline",
            ),
            tuple(
                f"{ATTEMPT_TABLE}.{name}"
                for name in (
                    "attempt_id",
                    "canonical_digest",
                    "claim_id",
                    "claim_digest",
                    "consumption_id",
                    "scheduling_authorization_lease_id",
                    "scheduling_authorization_lease_digest",
                    "runtime_envelope_id",
                    "runtime_envelope_commitment",
                    "runtime_envelope_generation",
                    "scheduling_profile_id",
                    "scheduling_profile_version",
                    "scheduling_profile_digest",
                    "scheduler_primitive_id",
                    "scheduler_primitive_version",
                    "scheduler_primitive_digest",
                    "protected_operation_reference",
                    "instruction_digest",
                    "started_at",
                    "invocation_deadline",
                )
            ),
            name="fk_wf_rtpsched_cons_result_attempt",
        ),
        sa.UniqueConstraint("attempt_id", name="uq_wf_rtpsched_cons_result_attempt"),
        sa.UniqueConstraint("claim_id", name="uq_wf_rtpsched_cons_result_claim"),
        sa.UniqueConstraint("consumption_id", name="uq_wf_rtpsched_cons_result_consumption"),
        sa.UniqueConstraint(
            "scheduling_authorization_lease_id", name="uq_wf_rtpsched_cons_result_lease"
        ),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rtpsched_cons_result_digest"),
        sa.CheckConstraint(
            "recorded_at >= completed_at AND completed_at >= started_at AND "
            "((state = 'process_scheduled_suspended_in_protected_boundary' "
            "AND failure_class IS NULL AND outcome_known AND result_process_scheduled "
            "AND result_process_suspended AND NOT result_process_runnable "
            "AND receipt_digest IS NOT NULL AND completed_at < invocation_deadline) OR "
            "(state = 'process_scheduling_rejected_without_scheduling' "
            "AND failure_class = 'protected_scheduler_rejected_without_scheduling' "
            "AND outcome_known AND NOT result_process_scheduled "
            "AND result_process_suspended AND NOT result_process_runnable "
            "AND receipt_digest IS NOT NULL AND completed_at < invocation_deadline) OR "
            "(state = 'process_scheduling_failed_without_scheduling' "
            "AND failure_class = 'protected_scheduler_failed_without_scheduling' "
            "AND outcome_known AND NOT result_process_scheduled "
            "AND result_process_suspended AND NOT result_process_runnable "
            "AND receipt_digest IS NOT NULL AND completed_at < invocation_deadline) OR "
            "(state = 'process_scheduling_outcome_uncertain' "
            "AND failure_class = 'process_scheduling_outcome_uncertain' "
            "AND NOT outcome_known AND result_process_scheduled IS NULL "
            "AND result_process_suspended IS NULL AND result_process_runnable IS NULL "
            "AND receipt_digest IS NULL)) "
            "AND NOT result_process_resumed AND NOT result_process_dispatched "
            "AND NOT result_process_executed",
            name="ck_wf_rtpsched_cons_result_outcome",
        ),
        sa.CheckConstraint(_zero_authority(), name="ck_wf_rtpsched_cons_result_semantics"),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object' "
            "AND (receipt_payload IS NULL OR jsonb_typeof(receipt_payload) = 'object')",
            name="ck_wf_rtpsched_cons_result_payload",
        ),
    )
    op.create_index(
        "ix_wf_rtpsched_cons_result_scope", RESULT_TABLE, [*SCOPE, "recorded_at"]
    )


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_wf_rtpsched_lease_cons_source",
        AUTH_LEASE_TABLE,
        [
            *SCOPE,
            "authorization_lease_id",
            "canonical_digest",
            "claim_id",
            "claim_digest",
        ],
    )
    _create_claim()
    _create_attempt()
    _create_result()
    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION {APPEND_ONLY_FUNCTION}()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'protected process-scheduling consumption evidence is append-only';
            END;
            $$
            """
        )
    )
    for table, stem in (
        (CLAIM_TABLE, "claim"),
        (ATTEMPT_TABLE, "attempt"),
        (RESULT_TABLE, "result"),
    ):
        op.execute(
            sa.text(
                f"CREATE TRIGGER trg_wf_rtpsched_cons_{stem}_append_only "
                f"BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW "
                f"EXECUTE FUNCTION {APPEND_ONLY_FUNCTION}()"
            )
        )
        op.execute(
            sa.text(
                f"CREATE TRIGGER trg_wf_rtpsched_cons_{stem}_no_truncate "
                f"BEFORE TRUNCATE ON {table} FOR EACH STATEMENT "
                f"EXECUTE FUNCTION {APPEND_ONLY_FUNCTION}()"
            )
        )


def downgrade() -> None:
    connection = op.get_bind()
    counts = {
        table: int(connection.execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one())
        for table in (CLAIM_TABLE, ATTEMPT_TABLE, RESULT_TABLE)
    }
    if any(counts.values()):
        raise RuntimeError(
            "refusing guarded downgrade: protected runtime process-scheduling consumption evidence exists"
        )
    op.drop_table(RESULT_TABLE)
    op.drop_table(ATTEMPT_TABLE)
    op.drop_table(CLAIM_TABLE)
    op.drop_constraint(
        "uq_wf_rtpsched_lease_cons_source", AUTH_LEASE_TABLE, type_="unique"
    )
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {APPEND_ONLY_FUNCTION}()"))
