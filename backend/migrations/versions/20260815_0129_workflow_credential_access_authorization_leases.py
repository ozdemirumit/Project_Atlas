"""Add immutable workflow credential-access authorization leases.

Revision ID: 20260815_0129
Revises: 20260815_0128
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260815_0129"
down_revision: str | None = "20260815_0128"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEASE_TABLE = "workflow_event_transport_credential_access_authorization_leases"
CLAIM_TABLE = "workflow_event_transport_credential_access_authorization_claims"


def upgrade() -> None:
    op.create_table(
        LEASE_TABLE,
        sa.Column("authorization_lease_id", sa.String(length=128), nullable=False),
        sa.Column("freshness_admission_id", sa.String(length=128), nullable=False),
        sa.Column("freshness_admission_digest", sa.String(length=64), nullable=False),
        sa.Column("credential_assignment_binding_id", sa.String(length=128), nullable=False),
        sa.Column("credential_assignment_binding_digest", sa.String(length=64), nullable=False),
        sa.Column("credential_assignment_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("credential_assignment_snapshot_digest", sa.String(length=64), nullable=False),
        sa.Column("assignment_id", sa.String(length=128), nullable=False),
        sa.Column("assignment_revision", sa.String(length=64), nullable=False),
        sa.Column("source_assignment_digest", sa.String(length=64), nullable=False),
        sa.Column("credential_generation", sa.BigInteger(), nullable=False),
        sa.Column("rotation_epoch", sa.BigInteger(), nullable=False),
        sa.Column("assignment_activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assignment_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assignment_active", sa.Boolean(), nullable=False),
        sa.Column("assignment_non_revoked", sa.Boolean(), nullable=False),
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("policy_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("accessor_subject_id", sa.String(length=240), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        *_authority_columns(),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "credential_generation > 0 AND rotation_epoch > 0",
            name="ck_wf_cred_access_lease_rank",
        ),
        sa.CheckConstraint("state = 'authorized_unconsumed'", name="ck_wf_cred_access_lease_state"),
        sa.CheckConstraint(
            "assignment_activated_at <= issued_at "
            "AND issued_at < valid_until "
            "AND valid_until = issued_at + INTERVAL '15 seconds' "
            "AND valid_until <= assignment_expires_at",
            name="ck_wf_cred_access_lease_window",
        ),
        sa.CheckConstraint(
            "assignment_active AND assignment_non_revoked",
            name="ck_wf_cred_access_lease_lifecycle",
        ),
        sa.CheckConstraint(_authority_check(), name="ck_wf_cred_access_lease_authority"),
        sa.ForeignKeyConstraint(
            ["freshness_admission_id"],
            ["workflow_event_transport_credential_freshness_admissions.freshness_admission_id"],
            name="fk_wf_cred_access_lease_freshness",
        ),
        sa.ForeignKeyConstraint(
            ["credential_assignment_binding_id"],
            ["workflow_event_physical_transport_credential_bindings.binding_id"],
            name="fk_wf_cred_access_lease_binding",
        ),
        sa.ForeignKeyConstraint(
            ["credential_assignment_snapshot_id"],
            ["event_transport_credential_assignment_snapshots.snapshot_id"],
            name="fk_wf_cred_access_lease_snapshot",
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id", "assignment_revision"],
            [
                "deployment_event_transport_credential_assignments.assignment_id",
                "deployment_event_transport_credential_assignments.assignment_revision",
            ],
            name="fk_wf_cred_access_lease_assignment",
        ),
        sa.PrimaryKeyConstraint("authorization_lease_id"),
        sa.UniqueConstraint("freshness_admission_id", name="uq_wf_cred_access_lease_freshness"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_cred_access_lease_digest"),
    )
    _create_indexes(
        LEASE_TABLE,
        "ix_wf_cred_access_lease",
        {
            "freshness_admission_id": "freshness",
            "credential_assignment_binding_id": "binding",
            "credential_assignment_snapshot_id": "snapshot",
            "assignment_id": "assignment",
            "assignment_revision": "revision",
            "credential_generation": "generation",
            "rotation_epoch": "rotation",
            "policy_id": "policy_id",
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
        sa.Column("freshness_admission_id", sa.String(length=128), nullable=False),
        sa.Column("assignment_id", sa.String(length=128), nullable=False),
        sa.Column("assignment_revision", sa.String(length=64), nullable=False),
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
            name="fk_wf_cred_access_claim_lease",
        ),
        sa.ForeignKeyConstraint(
            ["freshness_admission_id"],
            ["workflow_event_transport_credential_freshness_admissions.freshness_admission_id"],
            name="fk_wf_cred_access_claim_freshness",
        ),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "idempotency_scope_id", "idempotency_key", name="uq_wf_cred_access_claim_idem"
        ),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_cred_access_claim_lease"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_cred_access_claim_digest"),
    )
    _create_indexes(
        CLAIM_TABLE,
        "ix_wf_cred_access_claim",
        {
            "idempotency_scope_id": "scope",
            "authorization_lease_id": "lease",
            "freshness_admission_id": "freshness",
            "assignment_id": "assignment",
            "assignment_revision": "revision",
            "policy_digest": "policy",
            "organization_id": "org",
            "environment_id": "environment",
            "site_id": "site",
            "accessor_subject_id": "accessor",
        },
    )

    op.execute(
        """
        CREATE FUNCTION reject_wf_credential_access_authorization_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'workflow credential-access authorization evidence is append-only'
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
            EXECUTE FUNCTION reject_wf_credential_access_authorization_mutation()
            """
        )


def downgrade() -> None:
    for table_name, trigger_name in _triggers().items():
        op.execute(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name}")
    op.execute("DROP FUNCTION IF EXISTS reject_wf_credential_access_authorization_mutation()")
    for suffix in reversed(
        (
            "scope",
            "lease",
            "freshness",
            "assignment",
            "revision",
            "policy",
            "org",
            "environment",
            "site",
            "accessor",
        )
    ):
        op.drop_index(f"ix_wf_cred_access_claim_{suffix}", table_name=CLAIM_TABLE)
    op.drop_table(CLAIM_TABLE)
    for suffix in reversed(
        (
            "freshness",
            "binding",
            "snapshot",
            "assignment",
            "revision",
            "generation",
            "rotation",
            "policy_id",
            "policy",
            "org",
            "environment",
            "site",
            "accessor",
            "valid_until",
            "state",
        )
    ):
        op.drop_index(f"ix_wf_cred_access_lease_{suffix}", table_name=LEASE_TABLE)
    op.drop_table(LEASE_TABLE)


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
        if column.name == "credential_access_authority_granted"
        else f"NOT {column.name}"
        for column in _authority_columns()
    )


def _create_indexes(table_name: str, prefix: str, columns: dict[str, str]) -> None:
    for column, suffix in columns.items():
        op.create_index(f"{prefix}_{suffix}", table_name, [column])


def _triggers() -> dict[str, str]:
    return {
        LEASE_TABLE: "trg_wf_cred_access_leases_append_only",
        CLAIM_TABLE: "trg_wf_cred_access_claims_append_only",
    }
