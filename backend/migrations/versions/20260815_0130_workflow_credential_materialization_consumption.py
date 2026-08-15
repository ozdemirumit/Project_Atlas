"""Add single-use credential materialization consumption evidence.

Revision ID: 20260815_0130
Revises: 20260815_0129
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260815_0130"
down_revision: str | None = "20260815_0129"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    claim_table = "workflow_event_credential_access_lease_consumption_claims"
    attempt_table = "workflow_event_credential_materialization_attempts"
    result_table = "workflow_event_credential_materialization_results"
    lease_table = "workflow_event_transport_credential_access_authorization_leases"
    freshness_table = "workflow_event_transport_credential_freshness_admissions"
    binding_table = "workflow_event_physical_transport_credential_bindings"
    snapshot_table = "event_transport_credential_assignment_snapshots"
    assignment_table = "deployment_event_transport_credential_assignments"

    op.create_table(
        claim_table,
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("authorization_lease_id", sa.String(length=128), nullable=False),
        sa.Column("authorization_lease_digest", sa.String(length=64), nullable=False),
        sa.Column("freshness_admission_id", sa.String(length=128), nullable=False),
        sa.Column("freshness_admission_digest", sa.String(length=64), nullable=False),
        sa.Column("attempt_id", sa.String(length=128), nullable=False),
        sa.Column("materialization_id", sa.String(length=128), nullable=False),
        *_scope_columns(),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_digest", sa.String(length=64), nullable=False),
        *_zero_authority_columns(),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            _zero_authority_check(), name="ck_wf_credential_consume_claim_zero_auth"
        ),
        sa.ForeignKeyConstraint(
            ["authorization_lease_id"],
            [f"{lease_table}.authorization_lease_id"],
            name="fk_wf_credential_consume_claim_lease",
        ),
        sa.ForeignKeyConstraint(
            ["freshness_admission_id"],
            [f"{freshness_table}.freshness_admission_id"],
            name="fk_wf_credential_consume_claim_freshness",
        ),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_credential_consume_claim_lease"),
        sa.UniqueConstraint("attempt_id", name="uq_wf_credential_consume_claim_attempt"),
        sa.UniqueConstraint(
            "materialization_id", name="uq_wf_credential_consume_claim_materialization"
        ),
        sa.UniqueConstraint(
            "idempotency_digest", name="uq_wf_credential_consume_claim_idempotency"
        ),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_credential_consume_claim_digest"),
    )

    op.create_table(
        attempt_table,
        sa.Column("attempt_id", sa.String(length=128), nullable=False),
        sa.Column("materialization_id", sa.String(length=128), nullable=False),
        sa.Column("consumption_claim_id", sa.String(length=128), nullable=False),
        sa.Column("authorization_lease_id", sa.String(length=128), nullable=False),
        sa.Column("authorization_lease_digest", sa.String(length=64), nullable=False),
        sa.Column("freshness_admission_id", sa.String(length=128), nullable=False),
        sa.Column("freshness_admission_digest", sa.String(length=64), nullable=False),
        sa.Column(
            "physical_transport_credential_assignment_binding_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "physical_transport_credential_assignment_binding_digest",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("credential_assignment_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("credential_assignment_snapshot_digest", sa.String(length=64), nullable=False),
        sa.Column("assignment_id", sa.String(length=128), nullable=False),
        sa.Column("assignment_revision", sa.String(length=64), nullable=False),
        sa.Column("source_assignment_digest", sa.String(length=64), nullable=False),
        sa.Column("credential_generation", sa.BigInteger(), nullable=False),
        sa.Column("rotation_epoch", sa.BigInteger(), nullable=False),
        *_scope_columns(),
        *_policy_columns(),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("freshness_valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        *_zero_authority_columns(),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "state = 'materialization_started'", name="ck_wf_credential_mat_attempt_state"
        ),
        sa.CheckConstraint(
            "started_at < freshness_valid_until AND started_at < lease_valid_until",
            name="ck_wf_credential_mat_attempt_window",
        ),
        sa.CheckConstraint(
            "credential_generation > 0 AND rotation_epoch > 0",
            name="ck_wf_credential_mat_attempt_rank",
        ),
        sa.CheckConstraint(_zero_authority_check(), name="ck_wf_credential_mat_attempt_zero_auth"),
        sa.ForeignKeyConstraint(
            ["consumption_claim_id"],
            [f"{claim_table}.claim_id"],
            name="fk_wf_credential_mat_attempt_claim",
        ),
        sa.ForeignKeyConstraint(
            ["authorization_lease_id"],
            [f"{lease_table}.authorization_lease_id"],
            name="fk_wf_credential_mat_attempt_lease",
        ),
        sa.ForeignKeyConstraint(
            ["freshness_admission_id"],
            [f"{freshness_table}.freshness_admission_id"],
            name="fk_wf_credential_mat_attempt_freshness",
        ),
        sa.ForeignKeyConstraint(
            ["physical_transport_credential_assignment_binding_id"],
            [f"{binding_table}.binding_id"],
            name="fk_wf_credential_mat_attempt_binding",
        ),
        sa.ForeignKeyConstraint(
            ["credential_assignment_snapshot_id"],
            [f"{snapshot_table}.snapshot_id"],
            name="fk_wf_credential_mat_attempt_snapshot",
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id", "assignment_revision"],
            [f"{assignment_table}.assignment_id", f"{assignment_table}.assignment_revision"],
            name="fk_wf_credential_mat_attempt_assignment",
        ),
        sa.PrimaryKeyConstraint("attempt_id"),
        sa.UniqueConstraint(
            "materialization_id", name="uq_wf_credential_mat_attempt_materialization"
        ),
        sa.UniqueConstraint("consumption_claim_id", name="uq_wf_credential_mat_attempt_claim"),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_credential_mat_attempt_lease"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_credential_mat_attempt_digest"),
    )
    op.create_foreign_key(
        "fk_wf_credential_consume_claim_attempt",
        claim_table,
        attempt_table,
        ["attempt_id"],
        ["attempt_id"],
        deferrable=True,
        initially="DEFERRED",
    )

    op.create_table(
        result_table,
        sa.Column("materialization_id", sa.String(length=128), nullable=False),
        sa.Column("attempt_id", sa.String(length=128), nullable=False),
        sa.Column("attempt_digest", sa.String(length=64), nullable=False),
        sa.Column("consumption_claim_id", sa.String(length=128), nullable=False),
        sa.Column("consumption_claim_digest", sa.String(length=64), nullable=False),
        sa.Column("authorization_lease_id", sa.String(length=128), nullable=False),
        sa.Column("authorization_lease_digest", sa.String(length=64), nullable=False),
        sa.Column("freshness_admission_id", sa.String(length=128), nullable=False),
        sa.Column("freshness_admission_digest", sa.String(length=64), nullable=False),
        sa.Column("credential_assignment_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("credential_assignment_snapshot_digest", sa.String(length=64), nullable=False),
        sa.Column("assignment_id", sa.String(length=128), nullable=False),
        sa.Column("assignment_revision", sa.String(length=64), nullable=False),
        sa.Column("credential_generation", sa.BigInteger(), nullable=False),
        sa.Column("rotation_epoch", sa.BigInteger(), nullable=False),
        *_scope_columns(),
        *_policy_columns(),
        sa.Column("materializer_id", sa.String(length=128), nullable=False),
        sa.Column("materializer_version", sa.String(length=64), nullable=False),
        sa.Column("materialization_receipt_digest", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column("failure_class", sa.String(length=128), nullable=True),
        sa.Column("protected_artifact_id", sa.String(length=128), nullable=True),
        sa.Column("protected_artifact_digest", sa.String(length=64), nullable=True),
        sa.Column("protected_artifact_schema_id", sa.String(length=128), nullable=False),
        sa.Column("protected_artifact_schema_version", sa.String(length=64), nullable=False),
        sa.Column("protected_artifact_profile_digest", sa.String(length=64), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usable_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("protected_artifact_revoked", sa.Boolean(), nullable=False),
        sa.Column("cleanup_confirmed", sa.Boolean(), nullable=False),
        *_zero_authority_columns(),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "credential_generation > 0 AND rotation_epoch > 0",
            name="ck_wf_credential_mat_result_rank",
        ),
        sa.CheckConstraint(
            "state IN ('materialized_protected', 'materialization_failed')",
            name="ck_wf_credential_mat_result_state",
        ),
        sa.CheckConstraint(
            "(state = 'materialized_protected' "
            "AND protected_artifact_id IS NOT NULL "
            "AND protected_artifact_digest IS NOT NULL "
            "AND usable_until IS NOT NULL "
            "AND completed_at < usable_until "
            "AND NOT protected_artifact_revoked "
            "AND cleanup_confirmed "
            "AND failure_class IS NULL) "
            "OR (state = 'materialization_failed' "
            "AND protected_artifact_id IS NULL "
            "AND protected_artifact_digest IS NULL "
            "AND usable_until IS NULL "
            "AND protected_artifact_revoked "
            "AND cleanup_confirmed "
            "AND failure_class IS NOT NULL)",
            name="ck_wf_credential_mat_result_shape",
        ),
        sa.CheckConstraint(_zero_authority_check(), name="ck_wf_credential_mat_result_zero_auth"),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            [f"{attempt_table}.attempt_id"],
            name="fk_wf_credential_mat_result_attempt",
        ),
        sa.ForeignKeyConstraint(
            ["consumption_claim_id"],
            [f"{claim_table}.claim_id"],
            name="fk_wf_credential_mat_result_claim",
        ),
        sa.ForeignKeyConstraint(
            ["authorization_lease_id"],
            [f"{lease_table}.authorization_lease_id"],
            name="fk_wf_credential_mat_result_lease",
        ),
        sa.ForeignKeyConstraint(
            ["freshness_admission_id"],
            [f"{freshness_table}.freshness_admission_id"],
            name="fk_wf_credential_mat_result_freshness",
        ),
        sa.ForeignKeyConstraint(
            ["credential_assignment_snapshot_id"],
            [f"{snapshot_table}.snapshot_id"],
            name="fk_wf_credential_mat_result_snapshot",
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id", "assignment_revision"],
            [f"{assignment_table}.assignment_id", f"{assignment_table}.assignment_revision"],
            name="fk_wf_credential_mat_result_assignment",
        ),
        sa.PrimaryKeyConstraint("materialization_id"),
        sa.UniqueConstraint("attempt_id", name="uq_wf_credential_mat_result_attempt"),
        sa.UniqueConstraint("consumption_claim_id", name="uq_wf_credential_mat_result_claim"),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_credential_mat_result_lease"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_credential_mat_result_digest"),
    )

    _create_indexes(
        claim_table,
        "ix_wf_credential_consume_claim",
        (
            "authorization_lease_id",
            "freshness_admission_id",
            "attempt_id",
            "materialization_id",
            "organization_id",
            "environment_id",
            "site_id",
            "accessor_subject_id",
            "idempotency_digest",
        ),
    )
    _create_indexes(
        attempt_table,
        "ix_wf_credential_mat_attempt",
        (
            "authorization_lease_id",
            "freshness_admission_id",
            "credential_assignment_snapshot_id",
            "assignment_id",
            "policy_digest",
            "organization_id",
            "environment_id",
            "site_id",
            "accessor_subject_id",
        ),
    )
    op.create_index(
        "ix_wf_credential_mat_attempt_assignment_binding",
        attempt_table,
        ["physical_transport_credential_assignment_binding_id"],
    )
    _create_indexes(
        result_table,
        "ix_wf_credential_mat_result",
        (
            "authorization_lease_id",
            "freshness_admission_id",
            "credential_assignment_snapshot_id",
            "assignment_id",
            "policy_digest",
            "organization_id",
            "environment_id",
            "site_id",
            "accessor_subject_id",
            "state",
            "protected_artifact_id",
        ),
    )

    op.execute(
        """
        CREATE FUNCTION reject_workflow_credential_materialization_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'workflow credential materialization evidence is append-only'
                USING ERRCODE = '55000';
        END;
        $$
        """
    )
    for table, trigger in (
        (claim_table, "trg_wf_credential_consume_claim_append_only"),
        (attempt_table, "trg_wf_credential_mat_attempt_append_only"),
        (result_table, "trg_wf_credential_mat_result_append_only"),
    ):
        op.execute(
            f"""
            CREATE TRIGGER {trigger}
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION reject_workflow_credential_materialization_mutation()
            """
        )


def downgrade() -> None:
    result_table = "workflow_event_credential_materialization_results"
    attempt_table = "workflow_event_credential_materialization_attempts"
    claim_table = "workflow_event_credential_access_lease_consumption_claims"
    for table, trigger in (
        (result_table, "trg_wf_credential_mat_result_append_only"),
        (attempt_table, "trg_wf_credential_mat_attempt_append_only"),
        (claim_table, "trg_wf_credential_consume_claim_append_only"),
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
    op.drop_table(result_table)
    op.drop_constraint("fk_wf_credential_consume_claim_attempt", claim_table, type_="foreignkey")
    op.drop_table(attempt_table)
    op.drop_table(claim_table)
    op.execute("DROP FUNCTION IF EXISTS reject_workflow_credential_materialization_mutation()")


def _scope_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("accessor_subject_id", sa.String(length=240), nullable=False),
    )


def _policy_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("policy_digest", sa.String(length=64), nullable=False),
    )


def _zero_authority_columns() -> tuple[sa.Column, ...]:
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


def _zero_authority_check() -> str:
    return " AND ".join(f"NOT {column.name}" for column in _zero_authority_columns())


def _create_indexes(table: str, prefix: str, columns: tuple[str, ...]) -> None:
    for column in columns:
        op.create_index(f"{prefix}_{column}", table, [column])
