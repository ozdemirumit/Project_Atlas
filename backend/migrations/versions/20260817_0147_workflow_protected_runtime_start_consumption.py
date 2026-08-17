"""Add atomic protected runtime-start consumption evidence.

Revision ID: 20260817_0147
Revises: 20260817_0146
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260817_0147"
down_revision: str | None = "20260817_0146"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEASE_TABLE = "workflow_event_runtime_start_auth_leases"
AUTH_CLAIM_TABLE = "workflow_event_runtime_start_auth_claims"
COORDINATION_TABLE = "workflow_event_runtime_start_coordination_heads"
CLAIM_TABLE = "workflow_event_runtime_start_consumption_claims"
ATTEMPT_TABLE = "workflow_event_runtime_start_consumption_attempts"
RESULT_TABLE = "workflow_event_runtime_start_consumption_results"
APPEND_ONLY_FUNCTION = "reject_wf_rtstart_cons_mutation"
COORDINATION_GUARD_FUNCTION = "guard_wf_rtstart_coord_mutation"

POLICY_DIGEST = "75ed8efd455acee45b3df68e65890de39f705ff1849c2eed02818fb8ab39be80"
SOURCE_POLICY_DIGEST = "8d5db5d3fcfd4ce75a1f4440ec5e543419c6aa95ba96089e315c6367731443e7"
RUNTIME_START_PROFILE_DIGEST = "233c49d3d7cb7d80655d2d2456431f38efecec49ad4c79d2100323754e829995"


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
        "AND purpose_id = 'purpose.workflow-protected-runtime-start' "
        "AND policy_id = 'policy.workflow-protected-runtime-start' "
        f"AND policy_version = '1.0' AND policy_digest = '{POLICY_DIGEST}' "
        "AND source_policy_id = 'policy.workflow-protected-runtime-start-authorization' "
        f"AND source_policy_version = '1.0' AND source_policy_digest = '{SOURCE_POLICY_DIGEST}'"
    )


def _lease_constraint(*, prefix: str) -> sa.ForeignKeyConstraint:
    local = [column.name for column in _source_columns()]
    remote = [
        "authorization_lease_id",
        "canonical_digest",
        "claim_id",
        "claim_digest",
        "use_result_id",
        "use_result_digest",
        "destination_deployment_id",
        "destination_generation",
        "destination_fencing_token_digest",
        "runtime_slot_commitment",
        "runtime_slot_post_generation",
        "runtime_envelope_id",
        "runtime_envelope_commitment",
        "runtime_envelope_generation",
        "runtime_start_profile_id",
        "runtime_start_profile_version",
        "runtime_start_profile_digest",
    ]
    return sa.ForeignKeyConstraint(
        local,
        [f"{LEASE_TABLE}.{name}" for name in remote],
        name=f"fk_wf_rtstart_cons_{prefix}_lease",
    )


def _coordination_constraint(*, prefix: str) -> sa.ForeignKeyConstraint:
    local = [
        "runtime_envelope_id",
        "runtime_envelope_commitment",
        "runtime_envelope_generation",
        "use_result_id",
        "use_result_digest",
        "destination_deployment_id",
        "destination_generation",
        "destination_fencing_token_digest",
        "runtime_slot_commitment",
        "runtime_slot_generation",
    ]
    remote = [*local[:-1], "runtime_slot_post_generation"]
    return sa.ForeignKeyConstraint(
        local,
        [f"{COORDINATION_TABLE}.{name}" for name in remote],
        name=f"fk_wf_rtstart_cons_{prefix}_coord",
    )


def _replace_coordination_guard() -> None:
    op.execute(
        sa.text(f"""
        CREATE OR REPLACE FUNCTION {COORDINATION_GUARD_FUNCTION}()
        RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE
            terminal_result_state text;
            terminal_result_runtime_started boolean;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'runtime-start coordination heads cannot be deleted'
                    USING ERRCODE = '55000';
            END IF;
            IF NEW.runtime_envelope_id IS DISTINCT FROM OLD.runtime_envelope_id
               OR NEW.runtime_envelope_commitment IS DISTINCT FROM OLD.runtime_envelope_commitment
               OR NEW.runtime_envelope_generation IS DISTINCT FROM OLD.runtime_envelope_generation
               OR NEW.use_result_id IS DISTINCT FROM OLD.use_result_id
               OR NEW.use_result_digest IS DISTINCT FROM OLD.use_result_digest
               OR NEW.destination_deployment_id IS DISTINCT FROM OLD.destination_deployment_id
               OR NEW.destination_generation IS DISTINCT FROM OLD.destination_generation
               OR NEW.destination_fencing_token_digest IS DISTINCT FROM OLD.destination_fencing_token_digest
               OR NEW.runtime_slot_commitment IS DISTINCT FROM OLD.runtime_slot_commitment
               OR NEW.runtime_slot_post_generation IS DISTINCT FROM OLD.runtime_slot_post_generation
               OR NEW.version <> OLD.version + 1 THEN
                RAISE EXCEPTION 'runtime-start coordination lineage is immutable'
                    USING ERRCODE = '55000';
            END IF;
            IF NOT (
                (OLD.state = 'inactive_unstarted' AND NEW.state = 'authorized_unconsumed'
                 AND OLD.active_authorization_lease_id IS NULL
                 AND NEW.active_authorization_lease_id IS NOT NULL
                 AND NEW.consumption_claim_id IS NULL
                 AND NEW.runtime_start_attempt_id IS NULL
                 AND NEW.runtime_start_result_id IS NULL
                 AND NEW.runtime_start_result_digest IS NULL
                 AND NOT NEW.runtime_start_attempt_pending
                 AND NOT NEW.runtime_start_attempt_terminal
                 AND NOT NEW.runtime_started AND NOT NEW.runtime_resumed
                 AND NOT NEW.process_created AND NOT NEW.process_scheduled)
                OR
                (OLD.state = 'authorized_unconsumed' AND NEW.state = 'start_attempt_pending'
                 AND NEW.active_authorization_lease_id = OLD.active_authorization_lease_id
                 AND NEW.consumption_claim_id IS NOT NULL
                 AND NEW.runtime_start_attempt_id IS NOT NULL
                 AND NEW.runtime_start_result_id IS NULL
                 AND NEW.runtime_start_result_digest IS NULL
                 AND NEW.runtime_start_attempt_pending
                 AND NOT NEW.runtime_start_attempt_terminal
                 AND NOT NEW.runtime_started AND NOT NEW.runtime_resumed
                 AND NOT NEW.process_created AND NOT NEW.process_scheduled)
                OR
                (OLD.state = 'start_attempt_pending' AND NEW.state = 'start_attempt_terminal'
                 AND NEW.active_authorization_lease_id = OLD.active_authorization_lease_id
                 AND NEW.consumption_claim_id = OLD.consumption_claim_id
                 AND NEW.runtime_start_attempt_id = OLD.runtime_start_attempt_id
                 AND NEW.runtime_start_result_id IS NOT NULL
                 AND length(NEW.runtime_start_result_digest) = 64
                 AND NOT NEW.runtime_start_attempt_pending
                 AND NEW.runtime_start_attempt_terminal
                 AND NOT NEW.runtime_resumed
                 AND NOT NEW.process_created AND NOT NEW.process_scheduled)
            ) THEN
                RAISE EXCEPTION 'illegal runtime-start coordination transition'
                    USING ERRCODE = '55000';
            END IF;
            IF OLD.state = 'start_attempt_pending'
               AND NEW.state = 'start_attempt_terminal' THEN
                SELECT state, runtime_started
                  INTO terminal_result_state, terminal_result_runtime_started
                  FROM {RESULT_TABLE}
                 WHERE result_id = NEW.runtime_start_result_id
                   AND canonical_digest = NEW.runtime_start_result_digest
                   AND claim_id = NEW.consumption_claim_id
                   AND attempt_id = NEW.runtime_start_attempt_id
                   AND authorization_lease_id = NEW.active_authorization_lease_id;
                IF NOT FOUND
                   OR NEW.runtime_started IS DISTINCT FROM (
                       terminal_result_state = 'runtime_started_in_protected_boundary'
                       AND terminal_result_runtime_started IS TRUE
                   ) THEN
                    RAISE EXCEPTION 'runtime-start terminal outcome does not match result evidence'
                        USING ERRCODE = '55000';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    )


def _restore_adr173_coordination_guard() -> None:
    op.execute(
        sa.text(f"""
        CREATE OR REPLACE FUNCTION {COORDINATION_GUARD_FUNCTION}()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'runtime-start coordination heads cannot be deleted'
                    USING ERRCODE = '55000';
            END IF;
            IF NEW.runtime_envelope_id IS DISTINCT FROM OLD.runtime_envelope_id
               OR NEW.runtime_envelope_commitment IS DISTINCT FROM OLD.runtime_envelope_commitment
               OR NEW.runtime_envelope_generation IS DISTINCT FROM OLD.runtime_envelope_generation
               OR NEW.use_result_id IS DISTINCT FROM OLD.use_result_id
               OR NEW.use_result_digest IS DISTINCT FROM OLD.use_result_digest
               OR NEW.destination_deployment_id IS DISTINCT FROM OLD.destination_deployment_id
               OR NEW.destination_generation IS DISTINCT FROM OLD.destination_generation
               OR NEW.destination_fencing_token_digest IS DISTINCT FROM OLD.destination_fencing_token_digest
               OR NEW.runtime_slot_commitment IS DISTINCT FROM OLD.runtime_slot_commitment
               OR NEW.runtime_slot_post_generation IS DISTINCT FROM OLD.runtime_slot_post_generation
               OR NEW.version <> OLD.version + 1 THEN
                RAISE EXCEPTION 'runtime-start coordination lineage is immutable'
                    USING ERRCODE = '55000';
            END IF;
            IF NOT (
                (OLD.state = 'inactive_unstarted' AND NEW.state = 'authorized_unconsumed'
                 AND OLD.active_authorization_lease_id IS NULL
                 AND NEW.active_authorization_lease_id IS NOT NULL
                 AND NEW.consumption_claim_id IS NULL
                 AND NEW.runtime_start_attempt_id IS NULL
                 AND NOT NEW.runtime_start_attempt_pending
                 AND NOT NEW.runtime_start_attempt_terminal
                 AND NOT NEW.runtime_started AND NOT NEW.runtime_resumed
                 AND NOT NEW.process_created AND NOT NEW.process_scheduled)
                OR
                (OLD.state = 'authorized_unconsumed'
                 AND NEW.state = 'start_attempt_pending'
                 AND NEW.active_authorization_lease_id = OLD.active_authorization_lease_id
                 AND NEW.consumption_claim_id IS NOT NULL
                 AND NEW.runtime_start_attempt_id IS NOT NULL
                 AND NEW.runtime_start_attempt_pending AND NOT NEW.runtime_start_attempt_terminal
                 AND NOT NEW.runtime_started AND NOT NEW.runtime_resumed
                 AND NOT NEW.process_created AND NOT NEW.process_scheduled)
                OR
                (OLD.state = 'authorized_unconsumed'
                 AND NEW.state = 'start_attempt_terminal'
                 AND NEW.active_authorization_lease_id = OLD.active_authorization_lease_id
                 AND NEW.consumption_claim_id IS NOT NULL
                 AND NEW.runtime_start_attempt_id IS NOT NULL
                 AND NOT NEW.runtime_start_attempt_pending AND NEW.runtime_start_attempt_terminal
                 AND NOT NEW.runtime_resumed)
            ) THEN
                RAISE EXCEPTION 'illegal runtime-start coordination transition'
                    USING ERRCODE = '55000';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    )


def _guard_upgrade_without_legacy_runtime_start_attempts() -> None:
    op.execute(
        sa.text(f"""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1
                  FROM {COORDINATION_TABLE}
                 WHERE state IN ('start_attempt_pending', 'start_attempt_terminal')
                    OR runtime_start_attempt_pending
                    OR runtime_start_attempt_terminal
                    OR consumption_claim_id IS NOT NULL
                    OR runtime_start_attempt_id IS NOT NULL
                 LIMIT 1
            ) THEN
                RAISE EXCEPTION
                    'refusing guarded upgrade: legacy protected runtime-start attempts lack atomic consumption evidence'
                    USING ERRCODE = '55000';
            END IF;
        END $$;
    """)
    )


def upgrade() -> None:
    _guard_upgrade_without_legacy_runtime_start_attempts()
    op.add_column(COORDINATION_TABLE, sa.Column("runtime_start_result_id", sa.String(128)))
    op.add_column(COORDINATION_TABLE, sa.Column("runtime_start_result_digest", sa.String(64)))
    op.drop_constraint("ck_wf_rtstart_coord_state", COORDINATION_TABLE, type_="check")
    op.create_check_constraint(
        "ck_wf_rtstart_coord_state",
        COORDINATION_TABLE,
        "(state = 'inactive_unstarted' AND active_authorization_lease_id IS NULL "
        "AND consumption_claim_id IS NULL AND runtime_start_attempt_id IS NULL "
        "AND runtime_start_result_id IS NULL AND runtime_start_result_digest IS NULL "
        "AND NOT runtime_start_attempt_pending AND NOT runtime_start_attempt_terminal "
        "AND NOT runtime_started AND NOT runtime_resumed AND NOT process_created "
        "AND NOT process_scheduled AND version = 1) OR "
        "(state = 'authorized_unconsumed' AND active_authorization_lease_id IS NOT NULL "
        "AND consumption_claim_id IS NULL AND runtime_start_attempt_id IS NULL "
        "AND runtime_start_result_id IS NULL AND runtime_start_result_digest IS NULL "
        "AND NOT runtime_start_attempt_pending AND NOT runtime_start_attempt_terminal "
        "AND NOT runtime_started AND NOT runtime_resumed AND NOT process_created "
        "AND NOT process_scheduled AND version = 2) OR "
        "(state = 'start_attempt_pending' AND active_authorization_lease_id IS NOT NULL "
        "AND consumption_claim_id IS NOT NULL AND runtime_start_attempt_id IS NOT NULL "
        "AND runtime_start_result_id IS NULL AND runtime_start_result_digest IS NULL "
        "AND runtime_start_attempt_pending AND NOT runtime_start_attempt_terminal "
        "AND NOT runtime_started AND NOT runtime_resumed AND NOT process_created "
        "AND NOT process_scheduled) OR "
        "(state = 'start_attempt_terminal' AND active_authorization_lease_id IS NOT NULL "
        "AND consumption_claim_id IS NOT NULL AND runtime_start_attempt_id IS NOT NULL "
        "AND runtime_start_result_id IS NOT NULL "
        "AND length(runtime_start_result_digest) = 64 "
        "AND NOT runtime_start_attempt_pending AND runtime_start_attempt_terminal "
        "AND NOT runtime_resumed AND NOT process_created AND NOT process_scheduled)",
    )
    op.create_unique_constraint(
        "uq_wf_rtstart_auth_lease_identity",
        LEASE_TABLE,
        ["authorization_lease_id", "canonical_digest"],
    )
    lease_lineage = [
        "authorization_lease_id",
        "canonical_digest",
        "claim_id",
        "claim_digest",
        "use_result_id",
        "use_result_digest",
        "destination_deployment_id",
        "destination_generation",
        "destination_fencing_token_digest",
        "runtime_slot_commitment",
        "runtime_slot_post_generation",
        "runtime_envelope_id",
        "runtime_envelope_commitment",
        "runtime_envelope_generation",
        "runtime_start_profile_id",
        "runtime_start_profile_version",
        "runtime_start_profile_digest",
    ]
    op.create_unique_constraint("uq_wf_rtstart_auth_lease_consume", LEASE_TABLE, lease_lineage)

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
        _lease_constraint(prefix="claim"),
        _coordination_constraint(prefix="claim"),
        sa.ForeignKeyConstraint(
            ["authorization_claim_id", "authorization_claim_digest", "authorization_lease_id"],
            [
                f"{AUTH_CLAIM_TABLE}.claim_id",
                f"{AUTH_CLAIM_TABLE}.canonical_digest",
                f"{AUTH_CLAIM_TABLE}.authorization_lease_id",
            ],
            name="fk_wf_rtstart_cons_claim_auth_claim",
        ),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_rtstart_cons_claim_lease"),
        sa.UniqueConstraint("consumption_id", name="uq_wf_rtstart_cons_claim_consumption"),
        sa.UniqueConstraint("attempt_id", name="uq_wf_rtstart_cons_claim_attempt"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rtstart_cons_claim_digest"),
        sa.UniqueConstraint(
            "organization_id",
            "environment_id",
            "site_id",
            "consumer_subject_id",
            "consumer_audience",
            "idempotency_digest",
            name="uq_wf_rtstart_cons_claim_tenant_idem",
        ),
        sa.UniqueConstraint(
            "claim_id",
            "canonical_digest",
            "consumption_id",
            "attempt_id",
            "authorization_lease_id",
            name="uq_wf_rtstart_cons_claim_lineage",
        ),
        sa.CheckConstraint(_contract_check(), name="ck_wf_rtstart_cons_claim_contract"),
        sa.CheckConstraint(
            "irreversible_consumption_acknowledged "
            "AND uncertainty_no_retry_acknowledged "
            "AND runtime_slot_generation = runtime_envelope_generation "
            "AND runtime_slot_generation >= 1 "
            "AND length(idempotency_scope_id) = 64 "
            "AND length(idempotency_digest) = 64 "
            "AND length(request_fingerprint) = 64 AND " + _zero_authority(),
            name="ck_wf_rtstart_cons_claim_semantics",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object'", name="ck_wf_rtstart_cons_claim_payload"
        ),
    )
    op.create_index(
        "ix_wf_rtstart_cons_claim_scope",
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
        sa.Column("protected_operation_reference", sa.String(128), nullable=False),
        sa.Column("expected_start_count_pre", sa.Integer(), nullable=False),
        sa.Column("expected_start_count_post", sa.Integer(), nullable=False),
        sa.Column("starter_contract_id", sa.String(128), nullable=False),
        sa.Column("starter_contract_version", sa.String(64), nullable=False),
        sa.Column("starter_id", sa.String(128), nullable=False),
        sa.Column("starter_version", sa.String(64), nullable=False),
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
        _lease_constraint(prefix="attempt"),
        _coordination_constraint(prefix="attempt"),
        sa.ForeignKeyConstraint(
            ["claim_id", "claim_digest", "consumption_id", "attempt_id", "authorization_lease_id"],
            [
                f"{CLAIM_TABLE}.claim_id",
                f"{CLAIM_TABLE}.canonical_digest",
                f"{CLAIM_TABLE}.consumption_id",
                f"{CLAIM_TABLE}.attempt_id",
                f"{CLAIM_TABLE}.authorization_lease_id",
            ],
            name="fk_wf_rtstart_cons_attempt_claim",
        ),
        sa.UniqueConstraint("claim_id", name="uq_wf_rtstart_cons_attempt_claim"),
        sa.UniqueConstraint("consumption_id", name="uq_wf_rtstart_cons_attempt_consumption"),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_rtstart_cons_attempt_lease"),
        sa.UniqueConstraint("instruction_digest", name="uq_wf_rtstart_cons_attempt_instruction"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rtstart_cons_attempt_digest"),
        sa.UniqueConstraint(
            "claim_id",
            "attempt_id",
            "authorization_lease_id",
            name="uq_wf_rtstart_cons_attempt_coord",
        ),
        sa.UniqueConstraint(
            "attempt_id",
            "canonical_digest",
            "claim_id",
            "claim_digest",
            "consumption_id",
            "authorization_lease_id",
            name="uq_wf_rtstart_cons_attempt_lineage",
        ),
        sa.UniqueConstraint(
            "attempt_id",
            "canonical_digest",
            "claim_id",
            "claim_digest",
            "consumption_id",
            "authorization_lease_id",
            "authorization_lease_digest",
            "destination_deployment_id",
            "destination_generation",
            "runtime_envelope_commitment",
            "runtime_envelope_generation",
            "runtime_start_profile_id",
            "runtime_start_profile_version",
            "runtime_start_profile_digest",
            "protected_operation_reference",
            "instruction_digest",
            "started_at",
            "invocation_deadline",
            name="uq_wf_rtstart_cons_attempt_result_line",
        ),
        sa.CheckConstraint(_contract_check(), name="ck_wf_rtstart_cons_attempt_contract"),
        sa.CheckConstraint(
            "state = 'runtime_start_attempt_started' "
            "AND claimed_at <= started_at AND started_at < invocation_deadline "
            "AND expected_start_count_pre = 0 AND expected_start_count_post = 1 "
            "AND runtime_slot_generation = runtime_envelope_generation",
            name="ck_wf_rtstart_cons_attempt_state",
        ),
        sa.CheckConstraint(
            "starter_contract_id = 'contract.workflow-protected-runtime-start-executor' "
            "AND starter_contract_version = '1.0' "
            "AND starter_id = 'executor.workflow-protected-runtime-start' "
            "AND starter_version = '1.0' "
            "AND receipt_verification_signing_key_id = 'key.workflow-protected-runtime-start-receipt.v1' "
            "AND instruction_signing_key_id = 'key.workflow-protected-runtime-start-instruction.v1' "
            "AND instruction_signature_algorithm = 'hmac-sha256' "
            "AND length(instruction_digest) = 64 "
            "AND length(signed_instruction_envelope_digest) = 64 "
            "AND length(request_nonce_digest) = 64 AND " + _zero_authority(),
            name="ck_wf_rtstart_cons_attempt_instruction",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object' "
            "AND jsonb_typeof(signed_instruction_envelope_payload) = 'object' "
            "AND signed_instruction_envelope_payload <> '{}'::jsonb",
            name="ck_wf_rtstart_cons_attempt_payload",
        ),
    )
    op.create_index(
        "ix_wf_rtstart_cons_attempt_scope",
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
        sa.Column("authorization_lease_id", sa.String(128), nullable=False),
        sa.Column("authorization_lease_digest", sa.String(64), nullable=False),
        sa.Column("runtime_start_profile_id", sa.String(128), nullable=False),
        sa.Column("runtime_start_profile_version", sa.String(64), nullable=False),
        sa.Column("runtime_start_profile_digest", sa.String(64), nullable=False),
        sa.Column("destination_deployment_id", sa.String(128), nullable=False),
        sa.Column("destination_generation", sa.Integer(), nullable=False),
        sa.Column("runtime_envelope_commitment", sa.String(64), nullable=False),
        sa.Column("runtime_envelope_generation", sa.Integer(), nullable=False),
        *_identity_columns(),
        sa.Column("protected_operation_reference", sa.String(128), nullable=False),
        sa.Column("instruction_digest", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("invocation_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(64), nullable=False),
        sa.Column("failure_class", sa.String(64), nullable=True),
        sa.Column("outcome_known", sa.Boolean(), nullable=False),
        sa.Column("runtime_started", sa.Boolean(), nullable=True),
        sa.Column("starter_receipt_digest", sa.String(64), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("starter_receipt_payload", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(
            [
                "attempt_id",
                "attempt_digest",
                "claim_id",
                "claim_digest",
                "consumption_id",
                "authorization_lease_id",
                "authorization_lease_digest",
                "destination_deployment_id",
                "destination_generation",
                "runtime_envelope_commitment",
                "runtime_envelope_generation",
                "runtime_start_profile_id",
                "runtime_start_profile_version",
                "runtime_start_profile_digest",
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
                f"{ATTEMPT_TABLE}.destination_deployment_id",
                f"{ATTEMPT_TABLE}.destination_generation",
                f"{ATTEMPT_TABLE}.runtime_envelope_commitment",
                f"{ATTEMPT_TABLE}.runtime_envelope_generation",
                f"{ATTEMPT_TABLE}.runtime_start_profile_id",
                f"{ATTEMPT_TABLE}.runtime_start_profile_version",
                f"{ATTEMPT_TABLE}.runtime_start_profile_digest",
                f"{ATTEMPT_TABLE}.protected_operation_reference",
                f"{ATTEMPT_TABLE}.instruction_digest",
                f"{ATTEMPT_TABLE}.started_at",
                f"{ATTEMPT_TABLE}.invocation_deadline",
            ],
            name="fk_wf_rtstart_cons_result_attempt",
        ),
        sa.ForeignKeyConstraint(
            ["authorization_lease_id", "authorization_lease_digest"],
            [f"{LEASE_TABLE}.authorization_lease_id", f"{LEASE_TABLE}.canonical_digest"],
            name="fk_wf_rtstart_cons_result_lease",
        ),
        sa.UniqueConstraint("attempt_id", name="uq_wf_rtstart_cons_result_attempt"),
        sa.UniqueConstraint("claim_id", name="uq_wf_rtstart_cons_result_claim"),
        sa.UniqueConstraint("consumption_id", name="uq_wf_rtstart_cons_result_consumption"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rtstart_cons_result_digest"),
        sa.UniqueConstraint(
            "result_id",
            "canonical_digest",
            "claim_id",
            "attempt_id",
            "authorization_lease_id",
            name="uq_wf_rtstart_cons_result_coord",
        ),
        sa.CheckConstraint(_contract_check(), name="ck_wf_rtstart_cons_result_contract"),
        sa.CheckConstraint(
            "recorded_at >= started_at AND "
            "((state = 'runtime_start_outcome_uncertain' "
            "AND failure_class = 'runtime_start_outcome_uncertain' "
            "AND NOT outcome_known AND runtime_started IS NULL "
            "AND starter_receipt_digest IS NULL AND starter_receipt_payload IS NULL "
            "AND completed_at IS NULL) OR "
            "(state = 'runtime_started_in_protected_boundary' "
            "AND failure_class IS NULL AND outcome_known AND runtime_started "
            "AND starter_receipt_digest IS NOT NULL AND starter_receipt_payload IS NOT NULL "
            "AND completed_at IS NOT NULL AND started_at <= completed_at "
            "AND completed_at <= recorded_at AND completed_at < invocation_deadline) OR "
            "(state = 'runtime_start_failed_without_start' "
            "AND failure_class IN ('protected_starter_rejected_without_start', "
            "'protected_compare_and_swap_rejected') "
            "AND outcome_known AND NOT runtime_started "
            "AND starter_receipt_digest IS NOT NULL AND starter_receipt_payload IS NOT NULL "
            "AND completed_at IS NOT NULL AND started_at <= completed_at "
            "AND completed_at <= recorded_at AND completed_at < invocation_deadline))",
            name="ck_wf_rtstart_cons_result_outcome",
        ),
        sa.CheckConstraint(
            "runtime_envelope_generation >= 1 "
            "AND runtime_start_profile_id = 'profile.workflow-protected-runtime-start' "
            "AND runtime_start_profile_version = '1.0' "
            f"AND runtime_start_profile_digest = '{RUNTIME_START_PROFILE_DIGEST}' AND "
            + _zero_authority(),
            name="ck_wf_rtstart_cons_result_semantics",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object' "
            "AND (starter_receipt_payload IS NULL OR jsonb_typeof(starter_receipt_payload) = 'object')",
            name="ck_wf_rtstart_cons_result_payload",
        ),
    )
    op.create_index(
        "ix_wf_rtstart_cons_result_scope",
        RESULT_TABLE,
        ["organization_id", "environment_id", "site_id", "recorded_at"],
    )

    op.create_foreign_key(
        "fk_wf_rtstart_coord_attempt",
        COORDINATION_TABLE,
        ATTEMPT_TABLE,
        ["consumption_claim_id", "runtime_start_attempt_id", "active_authorization_lease_id"],
        ["claim_id", "attempt_id", "authorization_lease_id"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_foreign_key(
        "fk_wf_rtstart_coord_terminal_result",
        COORDINATION_TABLE,
        RESULT_TABLE,
        [
            "runtime_start_result_id",
            "runtime_start_result_digest",
            "consumption_claim_id",
            "runtime_start_attempt_id",
            "active_authorization_lease_id",
        ],
        ["result_id", "canonical_digest", "claim_id", "attempt_id", "authorization_lease_id"],
        deferrable=True,
        initially="DEFERRED",
    )
    _replace_coordination_guard()

    op.execute(
        sa.text(f"""
        CREATE FUNCTION {APPEND_ONLY_FUNCTION}() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'protected runtime-start consumption evidence is append-only'
                USING ERRCODE = '55000';
        END;
        $$
    """)
    )
    for table, trigger in (
        (CLAIM_TABLE, "trg_wf_rtstart_cons_claim_append_only"),
        (ATTEMPT_TABLE, "trg_wf_rtstart_cons_attempt_append_only"),
        (RESULT_TABLE, "trg_wf_rtstart_cons_result_append_only"),
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
                    'refusing guarded downgrade: protected runtime-start consumption evidence exists'
                    USING ERRCODE = '55000';
            END IF;
        END $$;
    """)
    )
    op.drop_constraint(
        "fk_wf_rtstart_coord_terminal_result", COORDINATION_TABLE, type_="foreignkey"
    )
    op.drop_constraint("fk_wf_rtstart_coord_attempt", COORDINATION_TABLE, type_="foreignkey")
    op.drop_table(RESULT_TABLE)
    op.drop_table(ATTEMPT_TABLE)
    op.drop_table(CLAIM_TABLE)
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {APPEND_ONLY_FUNCTION}()"))
    op.drop_constraint("uq_wf_rtstart_auth_lease_consume", LEASE_TABLE, type_="unique")
    op.drop_constraint("uq_wf_rtstart_auth_lease_identity", LEASE_TABLE, type_="unique")
    op.drop_constraint("ck_wf_rtstart_coord_state", COORDINATION_TABLE, type_="check")
    _restore_adr173_coordination_guard()
    op.drop_column(COORDINATION_TABLE, "runtime_start_result_digest")
    op.drop_column(COORDINATION_TABLE, "runtime_start_result_id")
    op.create_check_constraint(
        "ck_wf_rtstart_coord_state",
        COORDINATION_TABLE,
        "(state = 'inactive_unstarted' AND active_authorization_lease_id IS NULL "
        "AND consumption_claim_id IS NULL AND runtime_start_attempt_id IS NULL "
        "AND NOT runtime_start_attempt_pending AND NOT runtime_start_attempt_terminal "
        "AND NOT runtime_started AND NOT runtime_resumed AND NOT process_created "
        "AND NOT process_scheduled AND version = 1) OR "
        "(state = 'authorized_unconsumed' AND active_authorization_lease_id IS NOT NULL "
        "AND consumption_claim_id IS NULL AND runtime_start_attempt_id IS NULL "
        "AND NOT runtime_start_attempt_pending AND NOT runtime_start_attempt_terminal "
        "AND NOT runtime_started AND NOT runtime_resumed AND NOT process_created "
        "AND NOT process_scheduled AND version = 2) OR "
        "(state = 'start_attempt_pending' AND active_authorization_lease_id IS NOT NULL "
        "AND consumption_claim_id IS NOT NULL AND runtime_start_attempt_id IS NOT NULL "
        "AND runtime_start_attempt_pending AND NOT runtime_start_attempt_terminal "
        "AND NOT runtime_started AND NOT runtime_resumed AND NOT process_created "
        "AND NOT process_scheduled) OR "
        "(state = 'start_attempt_terminal' AND active_authorization_lease_id IS NOT NULL "
        "AND consumption_claim_id IS NOT NULL AND runtime_start_attempt_id IS NOT NULL "
        "AND NOT runtime_start_attempt_pending AND runtime_start_attempt_terminal "
        "AND NOT runtime_resumed)",
    )
