"""Add bounded protected runtime process-creation request authorization.

Revision ID: 20260818_0150
Revises: 20260817_0149
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260818_0150"
down_revision: str | None = "20260817_0149"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RESULT_TABLE = "workflow_event_runtime_readiness_consumption_results"
ATTEMPT_TABLE = "workflow_event_runtime_readiness_consumption_attempts"
CONSUMPTION_CLAIM_TABLE = "workflow_event_runtime_readiness_consumption_claims"
READINESS_LEASE_TABLE = "workflow_event_runtime_readiness_auth_leases"
READINESS_CLAIM_TABLE = "workflow_event_runtime_readiness_auth_claims"
START_HEAD_TABLE = "workflow_event_runtime_start_coordination_heads"
LEASE_TABLE = "workflow_event_runtime_process_creation_auth_leases"
CLAIM_TABLE = "workflow_event_runtime_process_creation_auth_claims"
APPEND_ONLY_FUNCTION = "reject_wf_rtproc_auth_mutation"
POLICY_DIGEST = "864620a2296233207d3ff1bde932725f65df1c102bddbdca304f9bcfe7e0cc96"
PROFILE_DIGEST = "b08432f01dd864b34157e2522fc591606487a6d0968d2f39dd88a5672aa0ba1b"
SOURCE_POLICY_DIGEST = "986fdb339467c04ab227dbbb28d73ca566a2888a3234fc1d82a729e104cb2c55"
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
        "readiness_result_id",
        "readiness_consumption_id",
        "readiness_attempt_id",
        "readiness_claim_id",
        "readiness_authorization_lease_id",
        "readiness_authorization_claim_id",
        "start_result_id",
        "start_consumption_id",
        "start_attempt_id",
        "start_consumption_claim_id",
        "runtime_start_authorization_lease_id",
        "runtime_start_authorization_claim_id",
        "use_result_id",
        "destination_deployment_id",
        "runtime_envelope_id",
        "runtime_start_profile_id",
        "readiness_profile_id",
        "protected_operation_reference",
    )
    strings_64 = (
        "readiness_result_digest",
        "readiness_attempt_digest",
        "readiness_claim_digest",
        "readiness_authorization_lease_digest",
        "readiness_authorization_claim_digest",
        "start_result_digest",
        "start_attempt_digest",
        "start_consumption_claim_digest",
        "runtime_start_authorization_lease_digest",
        "runtime_start_authorization_claim_digest",
        "use_result_digest",
        "destination_fencing_token_digest",
        "runtime_slot_commitment",
        "runtime_envelope_commitment",
        "runtime_start_profile_version",
        "runtime_start_profile_digest",
        "readiness_profile_version",
        "readiness_profile_digest",
        "start_instruction_digest",
        "starter_receipt_digest",
        "assessor_receipt_digest",
    )
    return (
        *(sa.Column(name, sa.String(128), nullable=False) for name in strings_128),
        *(sa.Column(name, sa.String(64), nullable=False) for name in strings_64),
        sa.Column("destination_generation", sa.Integer(), nullable=False),
        sa.Column("runtime_slot_generation", sa.Integer(), nullable=False),
        sa.Column("runtime_envelope_generation", sa.Integer(), nullable=False),
        sa.Column("start_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("start_invocation_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("start_completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("start_result_recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("start_result_state", sa.String(64), nullable=False),
        sa.Column("start_outcome_known", sa.Boolean(), nullable=False),
        sa.Column("runtime_started", sa.Boolean(), nullable=False),
        sa.Column("coordination_state", sa.String(64), nullable=False),
        sa.Column("runtime_start_attempt_pending", sa.Boolean(), nullable=False),
        sa.Column("runtime_start_attempt_terminal", sa.Boolean(), nullable=False),
        sa.Column("runtime_resumed", sa.Boolean(), nullable=False),
        sa.Column("process_created", sa.Boolean(), nullable=False),
        sa.Column("process_scheduled", sa.Boolean(), nullable=False),
        sa.Column("readiness_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("readiness_invocation_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("readiness_result_state", sa.String(64), nullable=False),
        sa.Column("readiness_failure_class", sa.String(64), nullable=True),
        sa.Column("readiness_outcome_known", sa.Boolean(), nullable=False),
        sa.Column("readiness_assessment_performed", sa.Boolean(), nullable=False),
        sa.Column("runtime_ready", sa.Boolean(), nullable=False),
        sa.Column("readiness_completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("readiness_result_recorded_at", sa.DateTime(timezone=True), nullable=False),
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
    )


def _authority_columns() -> tuple[sa.Column[object], ...]:
    return tuple(sa.Column(name, sa.Boolean(), nullable=False) for name in _authority_names())


def _zero_authority(*, lease: bool) -> str:
    return " AND ".join(
        ("" if lease and name == "protected_runtime_process_creation_authority_granted" else "NOT ")
        + name
        for name in _authority_names()
    )


def _contract_check() -> str:
    return (
        "consumer_subject_id = 'service.workflow-protected-transport-target-context-capsule-consumer' "
        "AND consumer_audience = 'audience.workflow-protected-transport-target-context-capsule-consumer' "
        "AND consumer_contract_id = 'contract.workflow-protected-transport-target-context-capsule-consumer' "
        "AND consumer_contract_version = '1.0' "
        "AND purpose_id = 'purpose.workflow-protected-runtime-process-creation-request' "
        "AND policy_id = 'policy.workflow-protected-runtime-process-creation-authorization' "
        f"AND policy_version = '1.0' AND policy_digest = '{POLICY_DIGEST}' "
        "AND source_policy_id = 'policy.workflow-protected-runtime-readiness-consumption' "
        f"AND source_policy_version = '1.0' AND source_policy_digest = '{SOURCE_POLICY_DIGEST}'"
    )


def _source_check() -> str:
    return (
        "readiness_result_state = 'runtime_ready_in_protected_boundary' "
        "AND readiness_outcome_known AND readiness_assessment_performed AND runtime_ready "
        "AND readiness_failure_class IS NULL "
        "AND readiness_started_at <= readiness_completed_at "
        "AND readiness_completed_at <= readiness_result_recorded_at "
        "AND readiness_completed_at < readiness_invocation_deadline "
        "AND coordination_state = 'start_attempt_terminal' "
        "AND NOT runtime_start_attempt_pending AND runtime_start_attempt_terminal "
        "AND runtime_started AND NOT runtime_resumed AND NOT process_created AND NOT process_scheduled "
        "AND runtime_slot_generation = runtime_envelope_generation AND runtime_slot_generation >= 2"
    )


def _source_constraints(prefix: str) -> tuple[sa.ForeignKeyConstraint, ...]:
    result_local = (
        *SCOPE,
        "readiness_result_id",
        "readiness_result_digest",
        "readiness_consumption_id",
        "readiness_attempt_id",
        "readiness_attempt_digest",
        "readiness_claim_id",
        "readiness_claim_digest",
        "readiness_authorization_lease_id",
        "readiness_authorization_lease_digest",
    )
    result_remote = (
        *SCOPE,
        "result_id",
        "canonical_digest",
        "consumption_id",
        "attempt_id",
        "attempt_digest",
        "claim_id",
        "claim_digest",
        "authorization_lease_id",
        "authorization_lease_digest",
    )
    outcome_local = (
        *SCOPE,
        "readiness_result_id",
        "readiness_result_digest",
        "readiness_result_state",
        "readiness_outcome_known",
        "readiness_assessment_performed",
        "runtime_ready",
        "assessor_receipt_digest",
        "readiness_started_at",
        "readiness_invocation_deadline",
        "readiness_completed_at",
        "readiness_result_recorded_at",
    )
    outcome_remote = (
        *SCOPE,
        "result_id",
        "canonical_digest",
        "state",
        "outcome_known",
        "assessment_performed",
        "runtime_ready",
        "assessor_receipt_digest",
        "started_at",
        "invocation_deadline",
        "completed_at",
        "recorded_at",
    )
    return (
        sa.ForeignKeyConstraint(
            result_local,
            [f"{RESULT_TABLE}.{name}" for name in result_remote],
            name=f"fk_wf_rtproc_{prefix}_ready_result",
        ),
        sa.ForeignKeyConstraint(
            outcome_local,
            [f"{RESULT_TABLE}.{name}" for name in outcome_remote],
            name=f"fk_wf_rtproc_{prefix}_ready_outcome",
        ),
        sa.ForeignKeyConstraint(
            (
                "readiness_attempt_id",
                "readiness_attempt_digest",
                "readiness_claim_id",
                "readiness_claim_digest",
                "readiness_consumption_id",
                "readiness_authorization_lease_id",
                "readiness_authorization_lease_digest",
            ),
            tuple(
                f"{ATTEMPT_TABLE}.{name}"
                for name in (
                    "attempt_id",
                    "canonical_digest",
                    "claim_id",
                    "claim_digest",
                    "consumption_id",
                    "authorization_lease_id",
                    "authorization_lease_digest",
                )
            ),
            name=f"fk_wf_rtproc_{prefix}_ready_attempt",
        ),
        sa.ForeignKeyConstraint(
            (
                "readiness_claim_id",
                "readiness_claim_digest",
                "readiness_consumption_id",
                "readiness_attempt_id",
                "readiness_authorization_lease_id",
            ),
            tuple(
                f"{CONSUMPTION_CLAIM_TABLE}.{name}"
                for name in (
                    "claim_id",
                    "canonical_digest",
                    "consumption_id",
                    "attempt_id",
                    "authorization_lease_id",
                )
            ),
            name=f"fk_wf_rtproc_{prefix}_ready_claim",
        ),
        sa.ForeignKeyConstraint(
            (
                "readiness_authorization_lease_id",
                "readiness_authorization_lease_digest",
                "readiness_authorization_claim_id",
                "readiness_authorization_claim_digest",
            ),
            tuple(
                f"{READINESS_LEASE_TABLE}.{name}"
                for name in (
                    "authorization_lease_id",
                    "canonical_digest",
                    "claim_id",
                    "claim_digest",
                )
            ),
            name=f"fk_wf_rtproc_{prefix}_ready_lease",
        ),
        sa.ForeignKeyConstraint(
            (
                *SCOPE,
                "readiness_authorization_claim_id",
                "readiness_authorization_claim_digest",
                "readiness_authorization_lease_id",
            ),
            tuple(
                f"{READINESS_CLAIM_TABLE}.{name}"
                for name in (*SCOPE, "claim_id", "canonical_digest", "authorization_lease_id")
            ),
            name=f"fk_wf_rtproc_{prefix}_ready_auth_claim",
        ),
        sa.ForeignKeyConstraint(
            (
                *SCOPE,
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
                "coordination_state",
                "runtime_start_authorization_lease_id",
                "start_consumption_claim_id",
                "start_attempt_id",
                "start_result_id",
                "start_result_digest",
                "runtime_start_attempt_pending",
                "runtime_start_attempt_terminal",
                "runtime_started",
                "runtime_resumed",
                "process_created",
                "process_scheduled",
            ),
            tuple(
                f"{START_HEAD_TABLE}.{name}"
                for name in (
                    *SCOPE,
                    "runtime_envelope_id",
                    "runtime_envelope_commitment",
                    "runtime_envelope_generation",
                    "use_result_id",
                    "use_result_digest",
                    "destination_deployment_id",
                    "destination_generation",
                    "destination_fencing_token_digest",
                    "runtime_slot_commitment",
                    "runtime_slot_post_generation",
                    "state",
                    "active_authorization_lease_id",
                    "consumption_claim_id",
                    "runtime_start_attempt_id",
                    "runtime_start_result_id",
                    "runtime_start_result_digest",
                    "runtime_start_attempt_pending",
                    "runtime_start_attempt_terminal",
                    "runtime_started",
                    "runtime_resumed",
                    "process_created",
                    "process_scheduled",
                )
            ),
            name=f"fk_wf_rtproc_{prefix}_started_head",
        ),
    )


def _add_result_projection_uniques() -> None:
    op.create_unique_constraint(
        "uq_wf_rtproc_src_ready_lease",
        READINESS_LEASE_TABLE,
        ["authorization_lease_id", "canonical_digest", "claim_id", "claim_digest"],
    )
    op.create_unique_constraint(
        "uq_wf_rtproc_src_ready_attempt",
        ATTEMPT_TABLE,
        [
            "attempt_id",
            "canonical_digest",
            "claim_id",
            "claim_digest",
            "consumption_id",
            "authorization_lease_id",
            "authorization_lease_digest",
        ],
    )
    op.create_unique_constraint(
        "uq_wf_rtproc_src_ready_result_lineage",
        RESULT_TABLE,
        [
            *SCOPE,
            "result_id",
            "canonical_digest",
            "consumption_id",
            "attempt_id",
            "attempt_digest",
            "claim_id",
            "claim_digest",
            "authorization_lease_id",
            "authorization_lease_digest",
        ],
    )
    op.create_unique_constraint(
        "uq_wf_rtproc_src_ready_result_outcome",
        RESULT_TABLE,
        [
            *SCOPE,
            "result_id",
            "canonical_digest",
            "state",
            "outcome_known",
            "assessment_performed",
            "runtime_ready",
            "assessor_receipt_digest",
            "started_at",
            "invocation_deadline",
            "completed_at",
            "recorded_at",
        ],
    )


def _create_lease() -> None:
    op.create_table(
        LEASE_TABLE,
        sa.Column("authorization_lease_id", sa.String(128), primary_key=True),
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("claim_digest", sa.String(64), nullable=False),
        *_identity_columns(),
        *_source_columns(),
        *_authority_columns(),
        sa.Column("source_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("single_use", sa.Boolean(), nullable=False),
        sa.Column("renewable", sa.Boolean(), nullable=False),
        sa.Column("transferable", sa.Boolean(), nullable=False),
        sa.Column("lease_is_bearer_capability", sa.Boolean(), nullable=False),
        sa.Column("state", sa.String(64), nullable=False),
        sa.Column("lifecycle_attestation_id", sa.String(128), nullable=False),
        sa.Column("lifecycle_attestation_digest", sa.String(64), nullable=False),
        sa.Column("lifecycle_attestation_valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("runtime_envelope_eligible_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attestation_metadata_only", sa.Boolean(), nullable=False),
        sa.Column("process_creation_profile_id", sa.String(128), nullable=False),
        sa.Column("process_creation_profile_version", sa.String(64), nullable=False),
        sa.Column("process_creation_profile_digest", sa.String(64), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "lifecycle_attestation_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        *_source_constraints("lease"),
        sa.UniqueConstraint("readiness_result_id", name="uq_wf_rtproc_auth_lease_ready_result"),
        sa.UniqueConstraint("claim_id", name="uq_wf_rtproc_auth_lease_claim"),
        sa.UniqueConstraint(
            "authorization_lease_id", "claim_digest", name="uq_wf_rtproc_auth_lease_claim_digest"
        ),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rtproc_auth_lease_digest"),
        sa.CheckConstraint(_contract_check(), name="ck_wf_rtproc_auth_lease_contract"),
        sa.CheckConstraint(_source_check(), name="ck_wf_rtproc_auth_lease_source"),
        sa.CheckConstraint(
            "claimed_at <= issued_at AND issued_at < valid_until AND valid_until = effective_until "
            "AND valid_until <= issued_at + INTERVAL '1 second' "
            "AND source_observed_at <= authorized_at AND source_observed_at = claimed_at "
            "AND authorized_at = issued_at "
            "AND effective_until <= lifecycle_attestation_valid_until "
            "AND effective_until <= runtime_envelope_eligible_until "
            "AND attestation_metadata_only "
            "AND process_creation_profile_id = 'profile.workflow-protected-runtime-process-creation-request' "
            f"AND process_creation_profile_version = '1.0' AND process_creation_profile_digest = '{PROFILE_DIGEST}' "
            "AND single_use AND NOT renewable AND NOT transferable "
            "AND NOT lease_is_bearer_capability AND state = 'authorized_unconsumed' AND "
            + _zero_authority(lease=True),
            name="ck_wf_rtproc_auth_lease_semantics",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object' AND jsonb_typeof(lifecycle_attestation_payload) = 'object' AND lifecycle_attestation_payload <> '{}'::jsonb",
            name="ck_wf_rtproc_auth_lease_payload",
        ),
    )
    op.create_index("ix_wf_rtproc_auth_lease_scope", LEASE_TABLE, [*SCOPE, "issued_at"])


def _create_claim() -> None:
    op.create_table(
        CLAIM_TABLE,
        sa.Column("claim_id", sa.String(128), primary_key=True),
        sa.Column("authorization_lease_id", sa.String(128), nullable=False),
        *_identity_columns(),
        *_source_columns(),
        *_authority_columns(),
        sa.Column("idempotency_scope_id", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("idempotency_digest", sa.String(64), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("authorization_audit_digest", sa.String(64), nullable=False),
        sa.Column("source_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "authorization_audit_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        *_source_constraints("claim"),
        sa.ForeignKeyConstraint(
            ("authorization_lease_id", "canonical_digest"),
            (f"{LEASE_TABLE}.authorization_lease_id", f"{LEASE_TABLE}.claim_digest"),
            name="fk_wf_rtproc_auth_claim_lease",
        ),
        sa.UniqueConstraint("readiness_result_id", name="uq_wf_rtproc_auth_claim_ready_result"),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_rtproc_auth_claim_lease"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rtproc_auth_claim_digest"),
        sa.UniqueConstraint(
            *SCOPE,
            "consumer_subject_id",
            "consumer_audience",
            "idempotency_key",
            name="uq_wf_rtproc_auth_scope_idem",
        ),
        sa.CheckConstraint(_contract_check(), name="ck_wf_rtproc_auth_claim_contract"),
        sa.CheckConstraint(_source_check(), name="ck_wf_rtproc_auth_claim_source"),
        sa.CheckConstraint(
            "source_observed_at = claimed_at AND readiness_result_recorded_at <= claimed_at "
            "AND length(idempotency_scope_id) = 64 AND length(idempotency_digest) = 64 "
            "AND length(request_fingerprint) = 64 AND length(authorization_audit_digest) = 64 AND "
            + _zero_authority(lease=False),
            name="ck_wf_rtproc_auth_claim_semantics",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object' AND jsonb_typeof(authorization_audit_payload) = 'object'",
            name="ck_wf_rtproc_auth_claim_payload",
        ),
    )
    op.create_index("ix_wf_rtproc_auth_claim_scope", CLAIM_TABLE, [*SCOPE, "claimed_at"])


def upgrade() -> None:
    _add_result_projection_uniques()
    _create_lease()
    _create_claim()
    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION {APPEND_ONLY_FUNCTION}()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'protected process-creation authorization evidence is append-only';
            END;
            $$
            """
        )
    )
    op.execute(
        sa.text(
            f"CREATE TRIGGER trg_wf_rtproc_auth_lease_append_only BEFORE UPDATE OR DELETE ON {LEASE_TABLE} FOR EACH ROW EXECUTE FUNCTION {APPEND_ONLY_FUNCTION}()"
        )
    )
    op.execute(
        sa.text(
            f"CREATE TRIGGER trg_wf_rtproc_auth_lease_no_truncate BEFORE TRUNCATE ON {LEASE_TABLE} FOR EACH STATEMENT EXECUTE FUNCTION {APPEND_ONLY_FUNCTION}()"
        )
    )
    op.execute(
        sa.text(
            f"CREATE TRIGGER trg_wf_rtproc_auth_claim_append_only BEFORE UPDATE OR DELETE ON {CLAIM_TABLE} FOR EACH ROW EXECUTE FUNCTION {APPEND_ONLY_FUNCTION}()"
        )
    )
    op.execute(
        sa.text(
            f"CREATE TRIGGER trg_wf_rtproc_auth_claim_no_truncate BEFORE TRUNCATE ON {CLAIM_TABLE} FOR EACH STATEMENT EXECUTE FUNCTION {APPEND_ONLY_FUNCTION}()"
        )
    )


def downgrade() -> None:
    connection = op.get_bind()
    lease_count = int(
        connection.execute(sa.text(f"SELECT count(*) FROM {LEASE_TABLE}")).scalar_one()
    )
    claim_count = int(
        connection.execute(sa.text(f"SELECT count(*) FROM {CLAIM_TABLE}")).scalar_one()
    )
    if lease_count or claim_count:
        raise RuntimeError(
            "refusing guarded downgrade: protected runtime process-creation authorization evidence exists"
        )
    op.drop_table(CLAIM_TABLE)
    op.drop_table(LEASE_TABLE)
    op.drop_constraint("uq_wf_rtproc_src_ready_result_outcome", RESULT_TABLE, type_="unique")
    op.drop_constraint("uq_wf_rtproc_src_ready_result_lineage", RESULT_TABLE, type_="unique")
    op.drop_constraint("uq_wf_rtproc_src_ready_attempt", ATTEMPT_TABLE, type_="unique")
    op.drop_constraint("uq_wf_rtproc_src_ready_lease", READINESS_LEASE_TABLE, type_="unique")
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {APPEND_ONLY_FUNCTION}()"))
