"""Add atomic protected runtime-context use-authorization consumption evidence.

Revision ID: 20260817_0144
Revises: 20260816_0143
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260817_0144"
down_revision: str | None = "20260816_0143"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEASE_TABLE = "workflow_event_runtime_context_use_auth_leases"
AUTH_CLAIM_TABLE = "workflow_event_runtime_context_use_auth_claims"
CLAIM_TABLE = "workflow_event_runtime_context_use_auth_consumption_claims"
RESULT_TABLE = "workflow_event_runtime_context_use_auth_consumption_results"
APPEND_ONLY_FUNCTION = "reject_wf_rtctx_use_auth_consume_mutation"

POLICY_DIGEST = "7dd60d9cae7725c6c41175945c391cedf17d6fbadf2e1735119c037bdd3063fd"
SOURCE_POLICY_DIGEST = "4287e205f26c138d7bab29faf92bd1a1d1c222378633fb7c28ddefadc8a9e5bd"


def _scope_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("environment_id", sa.String(128), nullable=False),
        sa.Column("site_id", sa.String(128), nullable=False),
    )


def _identity_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("consumer_subject_id", sa.String(240), nullable=False),
        sa.Column("consumer_audience", sa.String(240), nullable=False),
        sa.Column("consumer_contract_id", sa.String(128), nullable=False),
        sa.Column("consumer_contract_version", sa.String(64), nullable=False),
        sa.Column("purpose_id", sa.String(128), nullable=False),
    )


def _policy_columns() -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("policy_id", sa.String(128), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("policy_digest", sa.String(64), nullable=False),
        sa.Column("source_policy_id", sa.String(128), nullable=False),
        sa.Column("source_policy_version", sa.String(64), nullable=False),
        sa.Column("source_policy_digest", sa.String(64), nullable=False),
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
        "AND purpose_id = "
        "'purpose.workflow-protected-runtime-context-use-authorization-consumption' "
        "AND policy_id = "
        "'policy.workflow-protected-runtime-context-use-authorization-consumption' "
        f"AND policy_version = '1.0' AND policy_digest = '{POLICY_DIGEST}' "
        "AND source_policy_id = 'policy.workflow-protected-runtime-context-use-authorization' "
        f"AND source_policy_version = '1.0' AND source_policy_digest = '{SOURCE_POLICY_DIGEST}'"
    )


def _lease_lineage_constraints() -> tuple[sa.ForeignKeyConstraint, ...]:
    return (
        sa.ForeignKeyConstraint(
            ["authorization_lease_id", "authorization_lease_digest"],
            [f"{LEASE_TABLE}.authorization_lease_id", f"{LEASE_TABLE}.canonical_digest"],
            name="fk_wf_rtctx_use_consume_claim_lease_digest",
        ),
        sa.ForeignKeyConstraint(
            ["authorization_lease_id", "authorization_claim_id", "authorization_claim_digest"],
            [
                f"{LEASE_TABLE}.authorization_lease_id",
                f"{LEASE_TABLE}.claim_id",
                f"{LEASE_TABLE}.claim_digest",
            ],
            name="fk_wf_rtctx_use_consume_claim_lease_claim",
        ),
        sa.ForeignKeyConstraint(
            ["authorization_claim_id", "authorization_claim_digest", "authorization_lease_id"],
            [
                f"{AUTH_CLAIM_TABLE}.claim_id",
                f"{AUTH_CLAIM_TABLE}.canonical_digest",
                f"{AUTH_CLAIM_TABLE}.authorization_lease_id",
            ],
            name="fk_wf_rtctx_use_consume_claim_auth_claim",
        ),
        sa.ForeignKeyConstraint(
            ["authorization_lease_id", "injection_result_id", "injection_result_digest"],
            [
                f"{LEASE_TABLE}.authorization_lease_id",
                f"{LEASE_TABLE}.injection_result_id",
                f"{LEASE_TABLE}.injection_result_digest",
            ],
            name="fk_wf_rtctx_use_consume_claim_result",
        ),
        sa.ForeignKeyConstraint(
            [
                "authorization_lease_id",
                "destination_deployment_id",
                "destination_generation",
                "destination_fencing_token_digest",
                "runtime_slot_commitment",
                "runtime_slot_post_generation",
            ],
            [
                f"{LEASE_TABLE}.authorization_lease_id",
                f"{LEASE_TABLE}.destination_deployment_id",
                f"{LEASE_TABLE}.destination_generation",
                f"{LEASE_TABLE}.destination_fencing_token_digest",
                f"{LEASE_TABLE}.runtime_slot_commitment",
                f"{LEASE_TABLE}.runtime_slot_post_generation",
            ],
            name="fk_wf_rtctx_use_consume_claim_slot",
        ),
        sa.ForeignKeyConstraint(
            [
                "authorization_lease_id",
                "injected_context_usable_until",
                "use_profile_id",
                "use_profile_version",
                "use_profile_digest",
                "source_lease_state",
                "source_lease_issued_at",
                "source_lease_valid_until",
                "source_lease_effective_until",
            ],
            [
                f"{LEASE_TABLE}.authorization_lease_id",
                f"{LEASE_TABLE}.injected_context_usable_until",
                f"{LEASE_TABLE}.use_profile_id",
                f"{LEASE_TABLE}.use_profile_version",
                f"{LEASE_TABLE}.use_profile_digest",
                f"{LEASE_TABLE}.state",
                f"{LEASE_TABLE}.issued_at",
                f"{LEASE_TABLE}.valid_until",
                f"{LEASE_TABLE}.effective_until",
            ],
            name="fk_wf_rtctx_use_consume_claim_window",
        ),
        sa.ForeignKeyConstraint(
            [
                "authorization_lease_id",
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
                f"{LEASE_TABLE}.authorization_lease_id",
                f"{LEASE_TABLE}.organization_id",
                f"{LEASE_TABLE}.environment_id",
                f"{LEASE_TABLE}.site_id",
                f"{LEASE_TABLE}.consumer_subject_id",
                f"{LEASE_TABLE}.consumer_audience",
                f"{LEASE_TABLE}.consumer_contract_id",
                f"{LEASE_TABLE}.consumer_contract_version",
                f"{LEASE_TABLE}.policy_id",
                f"{LEASE_TABLE}.policy_version",
                f"{LEASE_TABLE}.policy_digest",
            ],
            name="fk_wf_rtctx_use_consume_claim_scope_policy",
        ),
    )


def upgrade() -> None:
    for name, columns in (
        ("uq_wf_rtctx_use_auth_lease_id_digest", ["authorization_lease_id", "canonical_digest"]),
        (
            "uq_wf_rtctx_use_auth_lease_claim_line",
            ["authorization_lease_id", "claim_id", "claim_digest"],
        ),
        (
            "uq_wf_rtctx_use_auth_lease_result_line",
            ["authorization_lease_id", "injection_result_id", "injection_result_digest"],
        ),
        (
            "uq_wf_rtctx_use_auth_lease_slot_line",
            [
                "authorization_lease_id",
                "destination_deployment_id",
                "destination_generation",
                "destination_fencing_token_digest",
                "runtime_slot_commitment",
                "runtime_slot_post_generation",
            ],
        ),
        (
            "uq_wf_rtctx_use_auth_lease_window_line",
            [
                "authorization_lease_id",
                "injected_context_usable_until",
                "use_profile_id",
                "use_profile_version",
                "use_profile_digest",
                "state",
                "issued_at",
                "valid_until",
                "effective_until",
            ],
        ),
        (
            "uq_wf_rtctx_use_auth_lease_scope_policy",
            [
                "authorization_lease_id",
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
        ),
    ):
        op.create_unique_constraint(name, LEASE_TABLE, columns)

    op.create_table(
        CLAIM_TABLE,
        sa.Column("consumption_claim_id", sa.String(128), primary_key=True),
        sa.Column("consumption_id", sa.String(128), nullable=False),
        sa.Column("authorization_lease_id", sa.String(128), nullable=False),
        sa.Column("authorization_lease_digest", sa.String(64), nullable=False),
        sa.Column("authorization_claim_id", sa.String(128), nullable=False),
        sa.Column("authorization_claim_digest", sa.String(64), nullable=False),
        sa.Column("injection_result_id", sa.String(128), nullable=False),
        sa.Column("injection_result_digest", sa.String(64), nullable=False),
        sa.Column("destination_deployment_id", sa.String(128), nullable=False),
        sa.Column("destination_generation", sa.Integer(), nullable=False),
        sa.Column("destination_fencing_token_digest", sa.String(64), nullable=False),
        sa.Column("runtime_slot_commitment", sa.String(64), nullable=False),
        sa.Column("runtime_slot_post_generation", sa.Integer(), nullable=False),
        sa.Column("injected_context_usable_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("use_profile_id", sa.String(128), nullable=False),
        sa.Column("use_profile_version", sa.String(64), nullable=False),
        sa.Column("use_profile_digest", sa.String(64), nullable=False),
        sa.Column("source_lease_state", sa.String(64), nullable=False),
        sa.Column("source_lease_issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_lease_valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_lease_effective_until", sa.DateTime(timezone=True), nullable=False),
        *_scope_columns(),
        *_identity_columns(),
        *_policy_columns(),
        sa.Column("idempotency_digest", sa.String(64), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("irreversible_consumption_acknowledged", sa.Boolean(), nullable=False),
        sa.Column("consumption_audit_digest", sa.String(64), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("consumption_audit_payload", postgresql.JSONB(), nullable=False),
        *_lease_lineage_constraints(),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_rtctx_use_consume_claim_lease"),
        sa.UniqueConstraint("consumption_id", name="uq_wf_rtctx_use_consume_claim_use"),
        sa.UniqueConstraint("idempotency_digest", name="uq_wf_rtctx_use_consume_claim_idem"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rtctx_use_consume_claim_digest"),
        sa.UniqueConstraint(
            "consumption_claim_id",
            "canonical_digest",
            "consumption_id",
            "authorization_lease_id",
            "authorization_lease_digest",
            "claimed_at",
            name="uq_wf_rtctx_use_consume_claim_result_line",
        ),
        sa.UniqueConstraint(
            "consumption_claim_id",
            "organization_id",
            "environment_id",
            "site_id",
            "consumer_subject_id",
            "consumer_audience",
            "consumer_contract_id",
            "consumer_contract_version",
            name="uq_wf_rtctx_use_consume_claim_identity",
        ),
        sa.UniqueConstraint(
            "consumption_claim_id",
            "purpose_id",
            "policy_id",
            "policy_version",
            "policy_digest",
            "source_policy_id",
            "source_policy_version",
            "source_policy_digest",
            name="uq_wf_rtctx_use_consume_claim_policy",
        ),
        sa.CheckConstraint(_contract_check(), name="ck_wf_rtctx_use_consume_claim_contract"),
        sa.CheckConstraint(
            "source_lease_state = 'authorized_unconsumed' "
            "AND source_lease_issued_at < source_lease_valid_until "
            "AND source_lease_valid_until <= source_lease_effective_until "
            "AND source_lease_effective_until <= injected_context_usable_until "
            "AND source_lease_issued_at <= claimed_at "
            "AND claimed_at < source_lease_valid_until "
            "AND claimed_at < source_lease_effective_until "
            "AND claimed_at < injected_context_usable_until",
            name="ck_wf_rtctx_use_consume_claim_window",
        ),
        sa.CheckConstraint(
            "irreversible_consumption_acknowledged AND " + _zero_authority(),
            name="ck_wf_rtctx_use_consume_claim_semantics",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object' "
            "AND jsonb_typeof(consumption_audit_payload) = 'object' "
            "AND consumption_audit_payload <> '{}'::jsonb",
            name="ck_wf_rtctx_use_consume_claim_evidence",
        ),
    )
    op.create_index(
        "ix_wf_rtctx_use_consume_claim_scope",
        CLAIM_TABLE,
        ["organization_id", "environment_id", "site_id", "claimed_at"],
    )

    op.create_table(
        RESULT_TABLE,
        sa.Column("result_id", sa.String(128), primary_key=True),
        sa.Column("consumption_id", sa.String(128), nullable=False),
        sa.Column("consumption_claim_id", sa.String(128), nullable=False),
        sa.Column("consumption_claim_digest", sa.String(64), nullable=False),
        sa.Column("authorization_lease_id", sa.String(128), nullable=False),
        sa.Column("authorization_lease_digest", sa.String(64), nullable=False),
        *_scope_columns(),
        *_identity_columns(),
        *_policy_columns(),
        sa.Column("state", sa.String(64), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("authorization_lease_consumed", sa.Boolean(), nullable=False),
        sa.Column("historical_result_only", sa.Boolean(), nullable=False),
        sa.Column("context_accessed", sa.Boolean(), nullable=False),
        sa.Column("context_used", sa.Boolean(), nullable=False),
        sa.Column("runtime_started", sa.Boolean(), nullable=False),
        sa.Column("runtime_resumed", sa.Boolean(), nullable=False),
        sa.Column("network_activity_performed", sa.Boolean(), nullable=False),
        sa.Column("connector_activity_performed", sa.Boolean(), nullable=False),
        sa.Column("readiness_probe_performed", sa.Boolean(), nullable=False),
        sa.Column("publication_performed", sa.Boolean(), nullable=False),
        sa.Column("delivery_performed", sa.Boolean(), nullable=False),
        sa.Column("dispatch_performed", sa.Boolean(), nullable=False),
        sa.Column("execution_performed", sa.Boolean(), nullable=False),
        sa.Column("infrastructure_mutation_performed", sa.Boolean(), nullable=False),
        sa.Column("renewal_created", sa.Boolean(), nullable=False),
        sa.Column("transfer_created", sa.Boolean(), nullable=False),
        sa.Column("replacement_created", sa.Boolean(), nullable=False),
        sa.Column("retry_created", sa.Boolean(), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            [
                "consumption_claim_id",
                "consumption_claim_digest",
                "consumption_id",
                "authorization_lease_id",
                "authorization_lease_digest",
                "consumed_at",
            ],
            [
                f"{CLAIM_TABLE}.consumption_claim_id",
                f"{CLAIM_TABLE}.canonical_digest",
                f"{CLAIM_TABLE}.consumption_id",
                f"{CLAIM_TABLE}.authorization_lease_id",
                f"{CLAIM_TABLE}.authorization_lease_digest",
                f"{CLAIM_TABLE}.claimed_at",
            ],
            name="fk_wf_rtctx_use_consume_result_claim",
        ),
        sa.ForeignKeyConstraint(
            [
                "consumption_claim_id",
                "organization_id",
                "environment_id",
                "site_id",
                "consumer_subject_id",
                "consumer_audience",
                "consumer_contract_id",
                "consumer_contract_version",
            ],
            [
                f"{CLAIM_TABLE}.consumption_claim_id",
                f"{CLAIM_TABLE}.organization_id",
                f"{CLAIM_TABLE}.environment_id",
                f"{CLAIM_TABLE}.site_id",
                f"{CLAIM_TABLE}.consumer_subject_id",
                f"{CLAIM_TABLE}.consumer_audience",
                f"{CLAIM_TABLE}.consumer_contract_id",
                f"{CLAIM_TABLE}.consumer_contract_version",
            ],
            name="fk_wf_rtctx_use_consume_result_identity",
        ),
        sa.ForeignKeyConstraint(
            [
                "consumption_claim_id",
                "purpose_id",
                "policy_id",
                "policy_version",
                "policy_digest",
                "source_policy_id",
                "source_policy_version",
                "source_policy_digest",
            ],
            [
                f"{CLAIM_TABLE}.consumption_claim_id",
                f"{CLAIM_TABLE}.purpose_id",
                f"{CLAIM_TABLE}.policy_id",
                f"{CLAIM_TABLE}.policy_version",
                f"{CLAIM_TABLE}.policy_digest",
                f"{CLAIM_TABLE}.source_policy_id",
                f"{CLAIM_TABLE}.source_policy_version",
                f"{CLAIM_TABLE}.source_policy_digest",
            ],
            name="fk_wf_rtctx_use_consume_result_policy",
        ),
        sa.UniqueConstraint("consumption_claim_id", name="uq_wf_rtctx_use_consume_result_claim"),
        sa.UniqueConstraint("consumption_id", name="uq_wf_rtctx_use_consume_result_use"),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_rtctx_use_consume_result_lease"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_rtctx_use_consume_result_digest"),
        sa.CheckConstraint(_contract_check(), name="ck_wf_rtctx_use_consume_result_contract"),
        sa.CheckConstraint(
            "state = 'authorization_consumed_without_runtime_use' "
            "AND consumed_at <= recorded_at "
            "AND authorization_lease_consumed AND historical_result_only "
            "AND NOT context_accessed AND NOT context_used "
            "AND NOT runtime_started AND NOT runtime_resumed "
            "AND NOT network_activity_performed AND NOT connector_activity_performed "
            "AND NOT readiness_probe_performed AND NOT publication_performed "
            "AND NOT delivery_performed AND NOT dispatch_performed "
            "AND NOT execution_performed AND NOT infrastructure_mutation_performed "
            "AND NOT renewal_created AND NOT transfer_created "
            "AND NOT replacement_created AND NOT retry_created AND " + _zero_authority(),
            name="ck_wf_rtctx_use_consume_result_semantics",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object'", name="ck_wf_rtctx_use_consume_result_payload"
        ),
    )
    op.create_index(
        "ix_wf_rtctx_use_consume_result_scope",
        RESULT_TABLE,
        ["organization_id", "environment_id", "site_id", "recorded_at"],
    )

    op.execute(
        sa.text(f"""
        CREATE FUNCTION {APPEND_ONLY_FUNCTION}() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'runtime-context use-authorization consumption evidence is append-only'
                USING ERRCODE = '55000';
        END;
        $$
    """)
    )
    for table, trigger in (
        (CLAIM_TABLE, "trg_wf_rtctx_use_consume_claim_append_only"),
        (RESULT_TABLE, "trg_wf_rtctx_use_consume_result_append_only"),
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
               OR EXISTS (SELECT 1 FROM {RESULT_TABLE} LIMIT 1) THEN
                RAISE EXCEPTION
                    'refusing guarded downgrade: runtime-context use-authorization '
                    'consumption evidence exists'
                    USING ERRCODE = '55000';
            END IF;
        END $$;
    """)
    )
    op.drop_table(RESULT_TABLE)
    op.drop_table(CLAIM_TABLE)
    for name in (
        "uq_wf_rtctx_use_auth_lease_scope_policy",
        "uq_wf_rtctx_use_auth_lease_window_line",
        "uq_wf_rtctx_use_auth_lease_slot_line",
        "uq_wf_rtctx_use_auth_lease_result_line",
        "uq_wf_rtctx_use_auth_lease_claim_line",
        "uq_wf_rtctx_use_auth_lease_id_digest",
    ):
        op.drop_constraint(name, LEASE_TABLE, type_="unique")
    op.execute(sa.text(f"DROP FUNCTION {APPEND_ONLY_FUNCTION}()"))
