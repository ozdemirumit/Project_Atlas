"""Add bounded target-context capsule handoff authorization leases.

Revision ID: 20260816_0135
Revises: 20260816_0134
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260816_0135"
down_revision: str | None = "20260816_0134"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEASE_TABLE = "workflow_event_tctx_capsule_handoff_authorization_leases"
CLAIM_TABLE = "workflow_event_tctx_capsule_handoff_authorization_claims"
APPEND_ONLY_FUNCTION = "reject_wf_tctx_capsule_handoff_auth_mutation"


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
        "'purpose.workflow-protected-transport-target-context-capsule-handoff-evaluation' "
        "AND policy_id = "
        "'policy.workflow-protected-transport-target-context-capsule-handoff-authorization' "
        "AND policy_version = '1.0' "
        "AND policy_digest = "
        "'388fc176751bc5af37489bfea61c603106b3658aa60a6ca3459ee0bab9b51270'"
    )


def _authority_check() -> str:
    return (
        "target_context_capsule_handoff_authority_granted "
        "AND NOT route_selection_authority_granted "
        "AND NOT route_binding_authority_granted "
        "AND NOT endpoint_resolution_authority_granted "
        "AND NOT protected_artifact_access_authority_granted "
        "AND NOT credential_selection_authority_granted "
        "AND NOT credential_assignment_binding_authority_granted "
        "AND NOT credential_access_authority_granted "
        "AND NOT credential_brokerage_authority_granted "
        "AND NOT credential_resolution_authority_granted "
        "AND NOT credential_delivery_authority_granted "
        "AND NOT network_access_authority_granted "
        "AND NOT readiness_probe_authority_granted "
        "AND NOT publication_authority_granted "
        "AND NOT delivery_authority_granted "
        "AND NOT dispatch_authority_granted "
        "AND NOT execution_authority_granted "
        "AND NOT infrastructure_mutation_authority_granted"
    )


def _audit_check() -> str:
    return (
        "char_length(authorization_audit_digest) = 64 "
        "AND authorization_audit_digest ~ '^[0-9a-f]{64}$' "
        "AND jsonb_typeof(authorization_audit_payload) = 'object' "
        "AND authorization_audit_payload <> '{}'::jsonb"
    )


def _authority_columns() -> tuple[sa.Column[bool], ...]:
    return tuple(
        sa.Column(name, sa.Boolean(), nullable=False)
        for name in (
            "target_context_capsule_handoff_authority_granted",
            "route_selection_authority_granted",
            "route_binding_authority_granted",
            "endpoint_resolution_authority_granted",
            "protected_artifact_access_authority_granted",
            "credential_selection_authority_granted",
            "credential_assignment_binding_authority_granted",
            "credential_access_authority_granted",
            "credential_brokerage_authority_granted",
            "credential_resolution_authority_granted",
            "credential_delivery_authority_granted",
            "network_access_authority_granted",
            "readiness_probe_authority_granted",
            "publication_authority_granted",
            "delivery_authority_granted",
            "dispatch_authority_granted",
            "execution_authority_granted",
            "infrastructure_mutation_authority_granted",
        )
    )


def _consumer_columns() -> tuple[sa.Column[str], ...]:
    return (
        sa.Column("consumer_subject_id", sa.String(length=240), nullable=False),
        sa.Column("consumer_audience", sa.String(length=240), nullable=False),
        sa.Column("consumer_contract_id", sa.String(length=128), nullable=False),
        sa.Column("consumer_contract_version", sa.String(length=64), nullable=False),
        sa.Column("purpose_id", sa.String(length=128), nullable=False),
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("policy_digest", sa.String(length=64), nullable=False),
    )


def _scope_columns() -> tuple[sa.Column[str], ...]:
    return (
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
    )


def upgrade() -> None:
    op.create_table(
        LEASE_TABLE,
        sa.Column("authorization_lease_id", sa.String(length=128), nullable=False),
        sa.Column("consumer_binding_id", sa.String(length=128), nullable=False),
        sa.Column("consumer_binding_digest", sa.String(length=64), nullable=False),
        sa.Column("opening_result_id", sa.String(length=128), nullable=False),
        sa.Column("opening_result_digest", sa.String(length=64), nullable=False),
        sa.Column("sealed_capsule_id", sa.String(length=128), nullable=False),
        sa.Column("sealed_capsule_digest", sa.String(length=64), nullable=False),
        sa.Column("capsule_schema_id", sa.String(length=128), nullable=False),
        sa.Column("capsule_schema_version", sa.String(length=64), nullable=False),
        sa.Column("capsule_is_bearer_capability", sa.Boolean(), nullable=False),
        sa.Column("lifecycle_attestation_id", sa.String(length=128), nullable=False),
        sa.Column("lifecycle_attestation_digest", sa.String(length=64), nullable=False),
        sa.Column(
            "lifecycle_attestation_valid_until",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("lifecycle_attestor_id", sa.String(length=128), nullable=False),
        sa.Column("lifecycle_attestor_version", sa.String(length=64), nullable=False),
        sa.Column("lifecycle_signing_key_id", sa.String(length=128), nullable=False),
        sa.Column("lifecycle_signature_algorithm", sa.String(length=64), nullable=False),
        sa.Column("lifecycle_integrity_signature", sa.String(length=2048), nullable=False),
        *_consumer_columns(),
        *_scope_columns(),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("single_use", sa.Boolean(), nullable=False),
        sa.Column("renewable", sa.Boolean(), nullable=False),
        sa.Column("transferable", sa.Boolean(), nullable=False),
        sa.Column("lease_is_bearer_capability", sa.Boolean(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        *_authority_columns(),
        sa.Column("authorization_evidence_digest", sa.String(length=64), nullable=False),
        sa.Column("authorization_audit_digest", sa.String(length=64), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("lifecycle_attestation_payload", postgresql.JSONB(), nullable=False),
        sa.Column("authorization_evidence_payload", postgresql.JSONB(), nullable=False),
        sa.Column("authorization_audit_payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "state = 'authorized_unconsumed'",
            name="ck_wf_tctx_handoff_lease_state",
        ),
        sa.CheckConstraint(
            "single_use AND NOT renewable AND NOT transferable "
            "AND NOT lease_is_bearer_capability AND NOT capsule_is_bearer_capability",
            name="ck_wf_tctx_handoff_lease_lifecycle",
        ),
        sa.CheckConstraint(
            "issued_at < valid_until "
            "AND valid_until = issued_at + INTERVAL '1 second' "
            "AND valid_until <= effective_until "
            "AND valid_until <= lifecycle_attestation_valid_until",
            name="ck_wf_tctx_handoff_lease_window",
        ),
        sa.CheckConstraint(
            _contract_check() + " AND lifecycle_attestor_id = "
            "'attestor.workflow-protected-target-context-capsule-lifecycle' "
            "AND lifecycle_attestor_version = '1.0'",
            name="ck_wf_tctx_handoff_lease_contract",
        ),
        sa.CheckConstraint(_authority_check(), name="ck_wf_tctx_handoff_lease_authority"),
        sa.CheckConstraint(_audit_check(), name="ck_wf_tctx_handoff_lease_audit"),
        sa.ForeignKeyConstraint(
            ["consumer_binding_id"],
            ["workflow_event_tctx_capsule_consumer_bindings.binding_id"],
            name="fk_wf_tctx_handoff_lease_binding",
        ),
        sa.PrimaryKeyConstraint("authorization_lease_id"),
        sa.UniqueConstraint("consumer_binding_id", name="uq_wf_tctx_handoff_lease_binding"),
        sa.UniqueConstraint("sealed_capsule_id", name="uq_wf_tctx_handoff_lease_capsule"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_tctx_handoff_lease_digest"),
    )
    for name, columns in (
        ("ix_wf_tctx_handoff_lease_scope", ("organization_id", "environment_id", "site_id")),
        ("ix_wf_tctx_handoff_lease_consumer", ("consumer_subject_id",)),
        ("ix_wf_tctx_handoff_lease_valid", ("valid_until",)),
        ("ix_wf_tctx_handoff_lease_state", ("state",)),
    ):
        op.create_index(name, LEASE_TABLE, list(columns))

    op.create_table(
        CLAIM_TABLE,
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("idempotency_digest", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("result_digest", sa.String(length=64), nullable=False),
        sa.Column("authorization_lease_id", sa.String(length=128), nullable=False),
        sa.Column("consumer_binding_id", sa.String(length=128), nullable=False),
        sa.Column("sealed_capsule_id", sa.String(length=128), nullable=False),
        *_consumer_columns(),
        *_scope_columns(),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("authorization_audit_digest", sa.String(length=64), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("authorization_audit_payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(_contract_check(), name="ck_wf_tctx_handoff_claim_contract"),
        sa.CheckConstraint(_audit_check(), name="ck_wf_tctx_handoff_claim_audit"),
        sa.ForeignKeyConstraint(
            ["authorization_lease_id"],
            [f"{LEASE_TABLE}.authorization_lease_id"],
            name="fk_wf_tctx_handoff_claim_lease",
        ),
        sa.ForeignKeyConstraint(
            ["consumer_binding_id"],
            ["workflow_event_tctx_capsule_consumer_bindings.binding_id"],
            name="fk_wf_tctx_handoff_claim_binding",
        ),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_tctx_handoff_claim_scope_idem",
        ),
        sa.UniqueConstraint(
            "authorization_lease_id",
            name="uq_wf_tctx_handoff_claim_lease",
        ),
        sa.UniqueConstraint("consumer_binding_id", name="uq_wf_tctx_handoff_claim_binding"),
        sa.UniqueConstraint("sealed_capsule_id", name="uq_wf_tctx_handoff_claim_capsule"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_tctx_handoff_claim_digest"),
    )
    op.create_index("ix_wf_tctx_handoff_claim_scope", CLAIM_TABLE, ["idempotency_scope_id"])
    op.create_index("ix_wf_tctx_handoff_claim_binding", CLAIM_TABLE, ["consumer_binding_id"])

    op.execute(
        sa.text(
            f"""
            CREATE FUNCTION {APPEND_ONLY_FUNCTION}()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION
                    'workflow target-context capsule handoff authorization records are append-only'
                    USING ERRCODE = '55000';
            END;
            $$
            """
        )
    )
    for table, trigger in (
        (LEASE_TABLE, "trg_wf_tctx_handoff_leases_append_only"),
        (CLAIM_TABLE, "trg_wf_tctx_handoff_claims_append_only"),
    ):
        op.execute(
            sa.text(
                f"CREATE TRIGGER {trigger} BEFORE UPDATE OR DELETE ON {table} "
                f"FOR EACH ROW EXECUTE FUNCTION {APPEND_ONLY_FUNCTION}()"
            )
        )


DOWNGRADE_EMPTY_GUARD_SQL = f"""
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM {CLAIM_TABLE} LIMIT 1)
       OR EXISTS (SELECT 1 FROM {LEASE_TABLE} LIMIT 1) THEN
        RAISE EXCEPTION
            'refusing to downgrade target-context capsule handoff authorization schema: '
            'append-only tables contain evidence'
            USING ERRCODE = '55000';
    END IF;
END
$$;
"""


def downgrade() -> None:
    op.execute(DOWNGRADE_EMPTY_GUARD_SQL)
    op.drop_table(CLAIM_TABLE)
    op.drop_table(LEASE_TABLE)
    op.execute(sa.text(f"DROP FUNCTION IF EXISTS {APPEND_ONLY_FUNCTION}()"))
