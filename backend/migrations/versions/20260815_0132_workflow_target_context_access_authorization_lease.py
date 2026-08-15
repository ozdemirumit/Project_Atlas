"""Add immutable target-context access authorization leases.

Revision ID: 20260815_0132
Revises: 20260815_0131
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260815_0132"
down_revision: str | None = "20260815_0131"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEASE_TABLE = "workflow_event_tctx_access_authorization_leases"
CLAIM_TABLE = "workflow_event_tctx_access_authorization_claims"


def upgrade() -> None:
    op.create_table(
        LEASE_TABLE,
        sa.Column("authorization_lease_id", sa.String(length=128), nullable=False),
        sa.Column("target_context_binding_id", sa.String(length=128), nullable=False),
        sa.Column("target_context_binding_digest", sa.String(length=64), nullable=False),
        sa.Column("target_context_commitment", sa.String(length=64), nullable=False),
        sa.Column("outbox_entry_id", sa.String(length=128), nullable=False),
        sa.Column("outbox_entry_digest", sa.String(length=64), nullable=False),
        sa.Column("route_head_id", sa.String(length=128), nullable=False),
        sa.Column("route_head_digest", sa.String(length=64), nullable=False),
        sa.Column("route_head_generation", sa.BigInteger(), nullable=False),
        sa.Column("route_head_fencing_token_digest", sa.String(length=64), nullable=False),
        sa.Column("assignment_id", sa.String(length=128), nullable=False),
        sa.Column("assignment_revision", sa.String(length=64), nullable=False),
        sa.Column("assignment_digest", sa.String(length=64), nullable=False),
        sa.Column("credential_generation", sa.BigInteger(), nullable=False),
        sa.Column("rotation_epoch", sa.BigInteger(), nullable=False),
        sa.Column("assignment_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("authorization_evidence_digest", sa.String(length=64), nullable=False),
        *_attestation_columns("endpoint"),
        *_attestation_columns("credential"),
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("policy_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("accessor_subject_id", sa.String(length=240), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("joint_usable_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("single_use", sa.Boolean(), nullable=False),
        sa.Column("renewable", sa.Boolean(), nullable=False),
        sa.Column("transferable", sa.Boolean(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("endpoint_attestation_payload", postgresql.JSONB(), nullable=False),
        sa.Column("credential_attestation_payload", postgresql.JSONB(), nullable=False),
        sa.Column("authorization_evidence_payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "route_head_generation > 0 AND credential_generation > 0 AND rotation_epoch > 0",
            name="ck_wf_tctx_access_lease_ranks",
        ),
        sa.CheckConstraint(
            "state = 'authorized_unconsumed'",
            name="ck_wf_tctx_access_lease_state",
        ),
        sa.CheckConstraint(
            "single_use AND NOT renewable AND NOT transferable",
            name="ck_wf_tctx_access_lease_lifecycle",
        ),
        sa.CheckConstraint(
            "issued_at < valid_until "
            "AND valid_until = issued_at + INTERVAL '5 seconds' "
            "AND valid_until <= joint_usable_until "
            "AND valid_until <= endpoint_attestation_valid_until "
            "AND valid_until <= credential_attestation_valid_until",
            name="ck_wf_tctx_access_lease_window",
        ),
        sa.CheckConstraint(
            "valid_until <= assignment_expires_at",
            name="ck_wf_tctx_access_lease_assignment_window",
        ),
        sa.CheckConstraint(_authority_check(), name="ck_wf_tctx_access_lease_authority"),
        sa.ForeignKeyConstraint(
            ["target_context_binding_id"],
            ["workflow_event_transport_target_context_bindings.binding_id"],
            name="fk_wf_tctx_access_lease_binding",
        ),
        sa.ForeignKeyConstraint(
            ["outbox_entry_id"],
            ["workflow_dispatch_outbox_entries.outbox_entry_id"],
            name="fk_wf_tctx_access_lease_outbox",
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id", "assignment_revision"],
            [
                "deployment_event_transport_credential_assignments.assignment_id",
                "deployment_event_transport_credential_assignments.assignment_revision",
            ],
            name="fk_wf_tctx_access_lease_assignment",
        ),
        sa.PrimaryKeyConstraint("authorization_lease_id"),
        sa.UniqueConstraint("target_context_binding_id", name="uq_wf_tctx_access_lease_binding"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_tctx_access_lease_digest"),
    )
    _create_indexes(
        LEASE_TABLE,
        "ix_wf_tctx_access_lease",
        {
            "target_context_binding_id": "binding",
            "outbox_entry_id": "outbox",
            "route_head_id": "route_head",
            "route_head_generation": "route_generation",
            "assignment_id": "assignment",
            "credential_generation": "credential_generation",
            "rotation_epoch": "rotation",
            "authorization_evidence_digest": "evidence",
            "policy_digest": "policy",
            "organization_id": "org",
            "environment_id": "environment",
            "site_id": "site",
            "accessor_subject_id": "accessor",
            "valid_until": "valid_until",
            "state": "state",
        },
    )

    op.create_table(
        CLAIM_TABLE,
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("result_digest", sa.String(length=64), nullable=False),
        sa.Column("authorization_lease_id", sa.String(length=128), nullable=False),
        sa.Column("target_context_binding_id", sa.String(length=128), nullable=False),
        sa.Column("policy_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("accessor_subject_id", sa.String(length=240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["authorization_lease_id"],
            [f"{LEASE_TABLE}.authorization_lease_id"],
            name="fk_wf_tctx_access_claim_lease",
        ),
        sa.ForeignKeyConstraint(
            ["target_context_binding_id"],
            ["workflow_event_transport_target_context_bindings.binding_id"],
            name="fk_wf_tctx_access_claim_binding",
        ),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_tctx_access_claim_idem",
        ),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_tctx_access_claim_lease"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_tctx_access_claim_digest"),
    )
    _create_indexes(
        CLAIM_TABLE,
        "ix_wf_tctx_access_claim",
        {
            "idempotency_scope_id": "scope",
            "authorization_lease_id": "lease",
            "target_context_binding_id": "binding",
            "policy_digest": "policy",
            "organization_id": "org",
            "environment_id": "environment",
            "site_id": "site",
            "accessor_subject_id": "accessor",
        },
    )

    op.execute(
        """
        CREATE FUNCTION reject_wf_tctx_access_authorization_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'workflow target-context access authorization evidence is append-only'
                USING ERRCODE = '55000';
        END;
        $$
        """
    )
    for table_name, trigger_name in _triggers().items():
        op.execute(
            f"""
            CREATE TRIGGER {trigger_name}
            BEFORE UPDATE OR DELETE ON {table_name}
            FOR EACH ROW
            EXECUTE FUNCTION reject_wf_tctx_access_authorization_mutation()
            """
        )


def downgrade() -> None:
    for table_name, trigger_name in _triggers().items():
        op.execute(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name}")
    op.execute("DROP FUNCTION IF EXISTS reject_wf_tctx_access_authorization_mutation()")
    op.drop_table(CLAIM_TABLE)
    op.drop_table(LEASE_TABLE)


def _attestation_columns(prefix: str) -> tuple[sa.Column[object], ...]:
    return (
        sa.Column(f"{prefix}_status_attestation_id", sa.String(length=128), nullable=False),
        sa.Column(f"{prefix}_status_attestation_digest", sa.String(length=64), nullable=False),
        sa.Column(f"{prefix}_attestation_valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column(f"{prefix}_attestor_id", sa.String(length=128), nullable=False),
        sa.Column(f"{prefix}_attestor_version", sa.String(length=64), nullable=False),
        sa.Column(f"{prefix}_signing_key_id", sa.String(length=128), nullable=False),
        sa.Column(f"{prefix}_signature_algorithm", sa.String(length=64), nullable=False),
        sa.Column(f"{prefix}_integrity_signature", sa.String(length=2048), nullable=False),
    )


def _authority_columns() -> tuple[sa.Column[object], ...]:
    return tuple(
        sa.Column(name, sa.Boolean(), nullable=False)
        for name in (
            "endpoint_resolution_authority_granted",
            "protected_artifact_access_authority_granted",
            "route_selection_authority_granted",
            "route_binding_authority_granted",
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


def _authority_check() -> str:
    return " AND ".join(
        column.name
        if column.name == "protected_artifact_access_authority_granted"
        else f"NOT {column.name}"
        for column in _authority_columns()
    )


def _create_indexes(table_name: str, prefix: str, columns: dict[str, str]) -> None:
    for column, suffix in columns.items():
        op.create_index(f"{prefix}_{suffix}", table_name, [column])


def _triggers() -> dict[str, str]:
    return {
        LEASE_TABLE: "trg_wf_tctx_access_leases_append_only",
        CLAIM_TABLE: "trg_wf_tctx_access_claims_append_only",
    }
