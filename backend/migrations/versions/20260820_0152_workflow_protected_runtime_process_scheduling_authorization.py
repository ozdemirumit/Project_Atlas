"""Add bounded protected runtime process-scheduling request authorization.

Revision ID: 20260820_0152
Revises: 20260820_0151
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260820_0152"
down_revision: str | None = "20260820_0151"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RESULT_TABLE = "workflow_event_runtime_process_creation_results"
ATTEMPT_TABLE = "workflow_event_runtime_process_creation_attempts"
CONSUMPTION_CLAIM_TABLE = "workflow_event_runtime_process_creation_consumption_claims"
PROCESS_AUTH_LEASE_TABLE = "workflow_event_runtime_process_creation_auth_leases"
PROCESS_AUTH_CLAIM_TABLE = "workflow_event_runtime_process_creation_auth_claims"
LEASE_TABLE = "workflow_event_runtime_process_scheduling_auth_leases"
CLAIM_TABLE = "workflow_event_runtime_process_scheduling_auth_claims"
APPEND_ONLY_FUNCTION = "reject_wf_rtpsched_auth_mutation"
SOURCE_POLICY_DIGEST = "4e9692080e0236eb64a69708499e382bcf3a373aa49b1b42ece990e6c5d6b572"
SCOPE = ("organization_id", "environment_id", "site_id")

RESULT_LOCAL = (
    *SCOPE,
    "process_creation_result_id",
    "process_creation_result_digest",
    "process_creation_consumption_id",
    "process_creation_attempt_id",
    "process_creation_attempt_digest",
    "process_creation_claim_id",
    "process_creation_claim_digest",
    "process_creation_authorization_lease_id",
    "process_creation_authorization_lease_digest",
    "process_creation_result_state",
    "process_creation_outcome_known",
    "process_created",
    "process_sealed",
    "process_suspended",
    "process_scheduled",
    "process_resumed",
    "process_dispatched",
    "process_executed",
    "process_creation_receipt_digest",
    "process_creation_completed_at",
    "process_creation_result_recorded_at",
)
RESULT_REMOTE = (
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
    "state",
    "outcome_known",
    "result_process_created",
    "process_sealed",
    "process_suspended",
    "result_process_scheduled",
    "result_process_resumed",
    "result_process_dispatched",
    "result_process_executed",
    "receipt_digest",
    "completed_at",
    "recorded_at",
)


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
    )
    return (
        *(sa.Column(name, sa.String(128), nullable=False) for name in strings_128),
        *(
            sa.Column(
                name,
                sa.String(64),
                nullable=name
                not in ("process_creation_failure_class", "process_creation_receipt_digest"),
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


def _zero_authority(*, lease: bool) -> str:
    return " AND ".join(
        (
            ""
            if lease and name == "protected_runtime_process_scheduling_authority_granted"
            else "NOT "
        )
        + name
        for name in _authority_names()
    )


def _contract_check() -> str:
    return (
        "consumer_subject_id = 'service.workflow-protected-transport-target-context-capsule-consumer' "
        "AND consumer_audience = 'audience.workflow-protected-transport-target-context-capsule-consumer' "
        "AND consumer_contract_id = 'contract.workflow-protected-transport-target-context-capsule-consumer' "
        "AND consumer_contract_version = '1.0' "
        "AND purpose_id = 'purpose.workflow-protected-runtime-process-scheduling-request' "
        "AND policy_id = 'policy.workflow-protected-runtime-process-scheduling-authorization' "
        "AND policy_version = '1.0' AND length(policy_digest) = 64 "
        "AND source_policy_id = 'policy.workflow-protected-runtime-process-creation-consumption' "
        f"AND source_policy_version = '1.0' AND source_policy_digest = '{SOURCE_POLICY_DIGEST}'"
    )


def _source_check() -> str:
    return (
        "process_creation_result_state = 'process_created_suspended_in_protected_boundary' "
        "AND process_creation_outcome_known AND process_created AND process_sealed "
        "AND process_suspended AND NOT process_scheduled AND NOT process_resumed "
        "AND NOT process_dispatched AND NOT process_executed "
        "AND process_creation_failure_class IS NULL "
        "AND process_creation_receipt_digest IS NOT NULL "
        "AND process_creation_completed_at <= process_creation_result_recorded_at "
        "AND runtime_slot_generation = runtime_envelope_generation "
        "AND runtime_slot_generation >= 2"
    )


def _source_constraints(prefix: str) -> tuple[sa.ForeignKeyConstraint, ...]:
    return (
        sa.ForeignKeyConstraint(
            RESULT_LOCAL,
            [f"{RESULT_TABLE}.{name}" for name in RESULT_REMOTE],
            name=f"fk_wf_rtpsched_{prefix}_result",
        ),
        sa.ForeignKeyConstraint(
            (
                *SCOPE,
                "process_creation_attempt_id",
                "process_creation_attempt_digest",
                "process_creation_claim_id",
                "process_creation_claim_digest",
                "process_creation_consumption_id",
                "process_creation_authorization_lease_id",
                "process_creation_authorization_lease_digest",
                "runtime_envelope_id",
                "runtime_envelope_commitment",
                "runtime_envelope_generation",
                "process_creation_profile_id",
                "process_creation_profile_version",
                "process_creation_profile_digest",
                "primitive_id",
                "primitive_version",
                "primitive_digest",
            ),
            tuple(
                f"{ATTEMPT_TABLE}.{name}"
                for name in (
                    *SCOPE,
                    "attempt_id",
                    "canonical_digest",
                    "claim_id",
                    "claim_digest",
                    "consumption_id",
                    "authorization_lease_id",
                    "authorization_lease_digest",
                    "runtime_envelope_id",
                    "runtime_envelope_commitment",
                    "runtime_envelope_generation",
                    "process_creation_profile_id",
                    "process_creation_profile_version",
                    "process_creation_profile_digest",
                    "primitive_id",
                    "primitive_version",
                    "primitive_digest",
                )
            ),
            name=f"fk_wf_rtpsched_{prefix}_attempt",
        ),
        sa.ForeignKeyConstraint(
            (
                *SCOPE,
                "process_creation_claim_id",
                "process_creation_claim_digest",
                "process_creation_consumption_id",
                "process_creation_attempt_id",
                "process_creation_authorization_lease_id",
                "process_creation_authorization_lease_digest",
                "process_creation_authorization_claim_id",
                "process_creation_authorization_claim_digest",
            ),
            tuple(
                f"{CONSUMPTION_CLAIM_TABLE}.{name}"
                for name in (
                    *SCOPE,
                    "claim_id",
                    "canonical_digest",
                    "consumption_id",
                    "attempt_id",
                    "authorization_lease_id",
                    "authorization_lease_digest",
                    "authorization_claim_id",
                    "authorization_claim_digest",
                )
            ),
            name=f"fk_wf_rtpsched_{prefix}_claim",
        ),
        sa.ForeignKeyConstraint(
            (
                *SCOPE,
                "process_creation_authorization_lease_id",
                "process_creation_authorization_lease_digest",
                "process_creation_authorization_claim_id",
                "process_creation_authorization_claim_digest",
            ),
            tuple(
                f"{PROCESS_AUTH_LEASE_TABLE}.{name}"
                for name in (
                    *SCOPE,
                    "authorization_lease_id",
                    "canonical_digest",
                    "claim_id",
                    "claim_digest",
                )
            ),
            name=f"fk_wf_rtpsched_{prefix}_src_lease",
        ),
        sa.ForeignKeyConstraint(
            (
                *SCOPE,
                "process_creation_authorization_claim_id",
                "process_creation_authorization_claim_digest",
                "process_creation_authorization_lease_id",
            ),
            tuple(
                f"{PROCESS_AUTH_CLAIM_TABLE}.{name}"
                for name in (*SCOPE, "claim_id", "canonical_digest", "authorization_lease_id")
            ),
            name=f"fk_wf_rtpsched_{prefix}_src_auth_claim",
        ),
    )


def _create_lease() -> None:
    op.create_table(
        LEASE_TABLE,
        sa.Column("authorization_lease_id", sa.String(128), primary_key=True),
        sa.Column("claim_id", sa.String(128), nullable=False),
        sa.Column("claim_digest", sa.String(64), nullable=False),
        sa.Column("state", sa.String(64), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("single_use", sa.Boolean(), nullable=False),
        sa.Column("renewable", sa.Boolean(), nullable=False),
        sa.Column("transferable", sa.Boolean(), nullable=False),
        sa.Column("replaceable", sa.Boolean(), nullable=False),
        sa.Column("reissuable", sa.Boolean(), nullable=False),
        sa.Column("lease_is_bearer_capability", sa.Boolean(), nullable=False),
        sa.Column("process_state_attestation_id", sa.String(128), nullable=False),
        sa.Column("process_state_attestation_digest", sa.String(64), nullable=False),
        sa.Column(
            "process_state_attestation_observed_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column(
            "process_state_attestation_valid_until", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("process_state_attestation_payload", postgresql.JSONB(), nullable=False),
        *_source_columns(),
        *_identity_columns(),
        *_authority_columns(),
        *_source_constraints("lease"),
        sa.UniqueConstraint("process_creation_result_id", name="uq_wf_rtpsched_lease_result"),
        sa.UniqueConstraint("claim_id", name="uq_wf_rtpsched_lease_claim"),
        sa.UniqueConstraint(
            *SCOPE,
            "authorization_lease_id",
            "claim_digest",
            "claim_id",
            name="uq_wf_rtpsched_lease_lineage",
        ),
        sa.CheckConstraint(_contract_check(), name="ck_wf_rtpsched_lease_contract"),
        sa.CheckConstraint(_source_check(), name="ck_wf_rtpsched_lease_source"),
        sa.CheckConstraint(
            "state = 'authorized_unconsumed' AND issued_at = effective_from "
            "AND effective_from < effective_until "
            "AND effective_until <= issued_at + INTERVAL '1 second' "
            "AND valid_until = effective_until AND source_observed_at <= issued_at "
            "AND process_creation_result_recorded_at <= source_observed_at "
            "AND process_state_attestation_observed_at <= issued_at "
            "AND issued_at < process_state_attestation_valid_until "
            "AND effective_until <= process_state_attestation_valid_until "
            "AND single_use AND NOT renewable AND NOT transferable "
            "AND NOT replaceable AND NOT reissuable AND NOT lease_is_bearer_capability AND "
            + _zero_authority(lease=True),
            name="ck_wf_rtpsched_lease_semantics",
        ),
        sa.CheckConstraint(
            "length(process_state_attestation_digest) = 64 "
            "AND jsonb_typeof(payload) = 'object' "
            "AND jsonb_typeof(process_state_attestation_payload) = 'object' "
            "AND process_state_attestation_payload <> '{}'::jsonb",
            name="ck_wf_rtpsched_lease_payload",
        ),
    )
    op.create_index("ix_wf_rtpsched_lease_scope", LEASE_TABLE, [*SCOPE, "issued_at"])


def _create_claim() -> None:
    op.create_table(
        CLAIM_TABLE,
        sa.Column("claim_id", sa.String(128), primary_key=True),
        sa.Column("authorization_lease_id", sa.String(128), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("idempotency_digest", sa.String(64), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("authorization_audit_digest", sa.String(64), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("authorization_audit_payload", postgresql.JSONB(), nullable=False),
        *_source_columns(),
        *_identity_columns(),
        *_authority_columns(),
        *_source_constraints("claim"),
        sa.ForeignKeyConstraint(
            [*SCOPE, "authorization_lease_id", "canonical_digest", "claim_id"],
            [
                f"{LEASE_TABLE}.{name}"
                for name in (*SCOPE, "authorization_lease_id", "claim_digest", "claim_id")
            ],
            name="fk_wf_rtpsched_claim_auth_lease",
            deferrable=True,
            initially="DEFERRED",
        ),
        sa.UniqueConstraint(
            *SCOPE,
            "consumer_subject_id",
            "consumer_audience",
            "idempotency_key",
            name="uq_wf_rtpsched_scope_idem",
        ),
        sa.UniqueConstraint("process_creation_result_id", name="uq_wf_rtpsched_claim_result"),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_rtpsched_claim_lease"),
        sa.UniqueConstraint(
            *SCOPE,
            "claim_id",
            "canonical_digest",
            "authorization_lease_id",
            name="uq_wf_rtpsched_claim_lineage",
        ),
        sa.CheckConstraint(_contract_check(), name="ck_wf_rtpsched_claim_contract"),
        sa.CheckConstraint(_source_check(), name="ck_wf_rtpsched_claim_source"),
        sa.CheckConstraint(
            "source_observed_at = claimed_at "
            "AND process_creation_result_recorded_at <= claimed_at "
            "AND length(idempotency_scope_id) = 64 AND length(idempotency_digest) = 64 "
            "AND length(request_fingerprint) = 64 AND length(authorization_audit_digest) = 64 AND "
            + _zero_authority(lease=False),
            name="ck_wf_rtpsched_claim_semantics",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object' AND jsonb_typeof(authorization_audit_payload) = 'object'",
            name="ck_wf_rtpsched_claim_payload",
        ),
    )
    op.create_index("ix_wf_rtpsched_claim_scope", CLAIM_TABLE, [*SCOPE, "claimed_at"])


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_wf_rtpsched_src_result_lineage", RESULT_TABLE, list(RESULT_REMOTE)
    )
    op.create_unique_constraint(
        "uq_wf_rtpsched_src_attempt_lineage",
        ATTEMPT_TABLE,
        [
            *SCOPE,
            "attempt_id",
            "canonical_digest",
            "claim_id",
            "claim_digest",
            "consumption_id",
            "authorization_lease_id",
            "authorization_lease_digest",
            "runtime_envelope_id",
            "runtime_envelope_commitment",
            "runtime_envelope_generation",
            "process_creation_profile_id",
            "process_creation_profile_version",
            "process_creation_profile_digest",
            "primitive_id",
            "primitive_version",
            "primitive_digest",
        ],
    )
    op.create_unique_constraint(
        "uq_wf_rtpsched_src_claim_lineage",
        CONSUMPTION_CLAIM_TABLE,
        [
            *SCOPE,
            "claim_id",
            "canonical_digest",
            "consumption_id",
            "attempt_id",
            "authorization_lease_id",
            "authorization_lease_digest",
            "authorization_claim_id",
            "authorization_claim_digest",
        ],
    )
    op.create_unique_constraint(
        "uq_wf_rtpsched_src_auth_lease",
        PROCESS_AUTH_LEASE_TABLE,
        [*SCOPE, "authorization_lease_id", "canonical_digest", "claim_id", "claim_digest"],
    )
    _create_lease()
    _create_claim()
    op.create_foreign_key(
        "fk_wf_rtpsched_lease_auth_claim",
        LEASE_TABLE,
        CLAIM_TABLE,
        [*SCOPE, "claim_id", "claim_digest", "authorization_lease_id"],
        [*SCOPE, "claim_id", "canonical_digest", "authorization_lease_id"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION {APPEND_ONLY_FUNCTION}()
            RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                RAISE EXCEPTION 'protected process-scheduling authorization evidence is append-only';
            END;
            $$
            """
        )
    )
    for table, stem in ((LEASE_TABLE, "lease"), (CLAIM_TABLE, "claim")):
        op.execute(
            sa.text(
                f"CREATE TRIGGER trg_wf_rtpsched_{stem}_append_only BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION {APPEND_ONLY_FUNCTION}()"
            )
        )
        op.execute(
            sa.text(
                f"CREATE TRIGGER trg_wf_rtpsched_{stem}_no_truncate BEFORE TRUNCATE ON {table} FOR EACH STATEMENT EXECUTE FUNCTION {APPEND_ONLY_FUNCTION}()"
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
            "refusing guarded downgrade: protected runtime process-scheduling authorization evidence exists"
        )
    op.drop_constraint("fk_wf_rtpsched_lease_auth_claim", LEASE_TABLE, type_="foreignkey")
    op.drop_table(CLAIM_TABLE)
    op.drop_table(LEASE_TABLE)
    op.drop_constraint("uq_wf_rtpsched_src_auth_lease", PROCESS_AUTH_LEASE_TABLE, type_="unique")
    op.drop_constraint("uq_wf_rtpsched_src_claim_lineage", CONSUMPTION_CLAIM_TABLE, type_="unique")
    op.drop_constraint("uq_wf_rtpsched_src_attempt_lineage", ATTEMPT_TABLE, type_="unique")
    op.drop_constraint("uq_wf_rtpsched_src_result_lineage", RESULT_TABLE, type_="unique")
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {APPEND_ONLY_FUNCTION}()"))
