"""Add immutable workflow credential-assignment freshness admissions.

Revision ID: 20260815_0128
Revises: 20260815_0127
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260815_0128"
down_revision: str | None = "20260815_0127"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    admission_table = "workflow_event_transport_credential_freshness_admissions"
    claim_table = "workflow_event_transport_credential_freshness_claims"

    op.create_table(
        admission_table,
        sa.Column("freshness_admission_id", sa.String(length=128), nullable=False),
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
        sa.Column("admitter_subject_id", sa.String(length=240), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        *_zero_authority_columns(),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "credential_generation > 0 AND rotation_epoch > 0",
            name="ck_wf_cred_fresh_rank",
        ),
        sa.CheckConstraint("state = 'admitted_current'", name="ck_wf_cred_fresh_state"),
        sa.CheckConstraint(
            "assignment_activated_at <= evaluated_at "
            "AND evaluated_at < valid_until "
            "AND valid_until <= assignment_expires_at "
            "AND valid_until <= evaluated_at + INTERVAL '60 seconds'",
            name="ck_wf_cred_fresh_window",
        ),
        sa.CheckConstraint(
            "assignment_active AND assignment_non_revoked",
            name="ck_wf_cred_fresh_lifecycle",
        ),
        sa.CheckConstraint(_zero_authority_check(), name="ck_wf_cred_fresh_zero_auth"),
        sa.ForeignKeyConstraint(
            ["credential_assignment_binding_id"],
            ["workflow_event_physical_transport_credential_bindings.binding_id"],
            name="fk_wf_cred_fresh_binding",
        ),
        sa.ForeignKeyConstraint(
            ["credential_assignment_snapshot_id"],
            ["event_transport_credential_assignment_snapshots.snapshot_id"],
            name="fk_wf_cred_fresh_snapshot",
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id", "assignment_revision"],
            [
                "deployment_event_transport_credential_assignments.assignment_id",
                "deployment_event_transport_credential_assignments.assignment_revision",
            ],
            name="fk_wf_cred_fresh_assignment",
        ),
        sa.PrimaryKeyConstraint("freshness_admission_id"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_cred_fresh_digest"),
    )
    _create_indexes(
        admission_table,
        "ix_wf_cred_fresh_admission",
        {
            "credential_assignment_binding_id": "binding",
            "credential_assignment_binding_digest": "binding_digest",
            "credential_assignment_snapshot_id": "snapshot",
            "credential_assignment_snapshot_digest": "snapshot_digest",
            "assignment_id": "assignment",
            "assignment_revision": "revision",
            "source_assignment_digest": "source_digest",
            "credential_generation": "generation",
            "rotation_epoch": "rotation",
            "assignment_expires_at": "expires",
            "policy_id": "policy_id",
            "policy_digest": "policy",
            "organization_id": "org",
            "environment_id": "environment",
            "site_id": "site",
            "admitter_subject_id": "admitter",
            "valid_until": "valid_until",
            "state": "state",
        },
    )

    op.create_table(
        claim_table,
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("result_digest", sa.String(length=64), nullable=False),
        sa.Column("freshness_admission_id", sa.String(length=128), nullable=False),
        sa.Column("credential_assignment_binding_id", sa.String(length=128), nullable=False),
        sa.Column("credential_assignment_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("assignment_id", sa.String(length=128), nullable=False),
        sa.Column("assignment_revision", sa.String(length=64), nullable=False),
        sa.Column("policy_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("admitter_subject_id", sa.String(length=240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["freshness_admission_id"],
            [f"{admission_table}.freshness_admission_id"],
            name="fk_wf_cred_fresh_claim_admission",
        ),
        sa.ForeignKeyConstraint(
            ["credential_assignment_binding_id"],
            ["workflow_event_physical_transport_credential_bindings.binding_id"],
            name="fk_wf_cred_fresh_claim_binding",
        ),
        sa.ForeignKeyConstraint(
            ["credential_assignment_snapshot_id"],
            ["event_transport_credential_assignment_snapshots.snapshot_id"],
            name="fk_wf_cred_fresh_claim_snapshot",
        ),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_cred_fresh_claim_scope_idem",
        ),
        sa.UniqueConstraint(
            "freshness_admission_id",
            name="uq_wf_cred_fresh_claim_admission",
        ),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_cred_fresh_claim_digest"),
    )
    _create_indexes(
        claim_table,
        "ix_wf_cred_fresh_claim",
        {
            "idempotency_scope_id": "scope",
            "freshness_admission_id": "admission",
            "credential_assignment_binding_id": "binding",
            "credential_assignment_snapshot_id": "snapshot",
            "assignment_id": "assignment",
            "assignment_revision": "revision",
            "policy_digest": "policy",
            "organization_id": "org",
            "environment_id": "environment",
            "site_id": "site",
            "admitter_subject_id": "admitter",
        },
    )

    op.execute(
        """
        CREATE FUNCTION reject_wf_credential_freshness_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'workflow credential freshness evidence is append-only'
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
            EXECUTE FUNCTION reject_wf_credential_freshness_mutation()
            """
        )


def downgrade() -> None:
    admission_table = "workflow_event_transport_credential_freshness_admissions"
    claim_table = "workflow_event_transport_credential_freshness_claims"
    for table_name, trigger_name in _triggers().items():
        op.execute(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name}")
    op.execute("DROP FUNCTION IF EXISTS reject_wf_credential_freshness_mutation()")

    for suffix in reversed(
        (
            "scope",
            "admission",
            "binding",
            "snapshot",
            "assignment",
            "revision",
            "policy",
            "org",
            "environment",
            "site",
            "admitter",
        )
    ):
        op.drop_index(f"ix_wf_cred_fresh_claim_{suffix}", table_name=claim_table)
    op.drop_table(claim_table)

    for suffix in reversed(
        (
            "binding",
            "binding_digest",
            "snapshot",
            "snapshot_digest",
            "assignment",
            "revision",
            "source_digest",
            "generation",
            "rotation",
            "expires",
            "policy_id",
            "policy",
            "org",
            "environment",
            "site",
            "admitter",
            "valid_until",
            "state",
        )
    ):
        op.drop_index(f"ix_wf_cred_fresh_admission_{suffix}", table_name=admission_table)
    op.drop_table(admission_table)


def _zero_authority_columns() -> tuple[sa.Column[object], ...]:
    return tuple(
        sa.Column(name, sa.Boolean(), nullable=False)
        for name in (
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


def _zero_authority_check() -> str:
    return " AND ".join(f"NOT {column.name}" for column in _zero_authority_columns())


def _create_indexes(table_name: str, prefix: str, columns: dict[str, str]) -> None:
    for column, suffix in columns.items():
        op.create_index(f"{prefix}_{suffix}", table_name, [column])


def _triggers() -> dict[str, str]:
    return {
        "workflow_event_transport_credential_freshness_admissions": (
            "trg_wf_cred_fresh_admissions_append_only"
        ),
        "workflow_event_transport_credential_freshness_claims": (
            "trg_wf_cred_fresh_claims_append_only"
        ),
    }
