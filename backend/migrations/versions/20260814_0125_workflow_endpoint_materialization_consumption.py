"""Add single-use endpoint materialization consumption evidence.

Revision ID: 20260814_0125
Revises: 20260814_0124
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0125"
down_revision: str | None = "20260814_0124"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    claim_table = "workflow_event_endpoint_resolution_lease_consumption_claims"
    attempt_table = "workflow_event_endpoint_materialization_attempts"
    result_table = "workflow_event_endpoint_materialization_results"
    lease_table = "workflow_event_endpoint_resolution_authorization_leases"

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
        sa.CheckConstraint(_zero_authority_check(), name="ck_wf_endpoint_consume_claim_zero_auth"),
        sa.ForeignKeyConstraint(
            ["authorization_lease_id"],
            [f"{lease_table}.authorization_lease_id"],
            name="fk_wf_endpoint_consume_claim_lease",
        ),
        sa.ForeignKeyConstraint(
            ["freshness_admission_id"],
            ["workflow_event_physical_transport_route_freshness_admissions.freshness_admission_id"],
            name="fk_wf_endpoint_consume_claim_freshness",
        ),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_endpoint_consume_claim_lease"),
        sa.UniqueConstraint("attempt_id", name="uq_wf_endpoint_consume_claim_attempt"),
        sa.UniqueConstraint(
            "materialization_id", name="uq_wf_endpoint_consume_claim_materialization"
        ),
        sa.UniqueConstraint("idempotency_digest", name="uq_wf_endpoint_consume_claim_idempotency"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_endpoint_consume_claim_digest"),
    )
    _create_indexes(
        claim_table,
        "ix_wf_endpoint_consume_claim",
        {
            "authorization_lease_id": "lease",
            "authorization_lease_digest": "lease_digest",
            "freshness_admission_id": "freshness",
            "freshness_admission_digest": "fresh_digest",
            "attempt_id": "attempt",
            "materialization_id": "materialization",
            "organization_id": "org",
            "environment_id": "environment",
            "site_id": "site",
            "resolver_subject_id": "resolver",
            "idempotency_digest": "idempotency",
        },
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
        sa.Column("physical_transport_route_binding_id", sa.String(length=128), nullable=False),
        sa.Column("physical_transport_route_binding_digest", sa.String(length=64), nullable=False),
        sa.Column("transport_route_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("transport_route_snapshot_digest", sa.String(length=64), nullable=False),
        sa.Column("current_selection_head_id", sa.String(length=128), nullable=False),
        sa.Column("current_selection_head_digest", sa.String(length=64), nullable=False),
        sa.Column("current_selection_head_generation", sa.BigInteger(), nullable=False),
        sa.Column(
            "current_selection_head_fencing_token_digest",
            sa.String(length=64),
            nullable=False,
        ),
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
            "state = 'materialization_started'", name="ck_wf_endpoint_mat_attempt_state"
        ),
        sa.CheckConstraint(
            "started_at < freshness_valid_until AND started_at < lease_valid_until",
            name="ck_wf_endpoint_mat_attempt_window",
        ),
        sa.CheckConstraint(
            "current_selection_head_generation > 0",
            name="ck_wf_endpoint_mat_attempt_generation",
        ),
        sa.CheckConstraint(_zero_authority_check(), name="ck_wf_endpoint_mat_attempt_zero_auth"),
        sa.ForeignKeyConstraint(
            ["consumption_claim_id"],
            [f"{claim_table}.claim_id"],
            name="fk_wf_endpoint_mat_attempt_claim",
        ),
        sa.ForeignKeyConstraint(
            ["authorization_lease_id"],
            [f"{lease_table}.authorization_lease_id"],
            name="fk_wf_endpoint_mat_attempt_lease",
        ),
        sa.ForeignKeyConstraint(
            ["freshness_admission_id"],
            ["workflow_event_physical_transport_route_freshness_admissions.freshness_admission_id"],
            name="fk_wf_endpoint_mat_attempt_freshness",
        ),
        sa.ForeignKeyConstraint(
            ["physical_transport_route_binding_id"],
            ["workflow_event_physical_transport_route_bindings.binding_id"],
            name="fk_wf_endpoint_mat_attempt_binding",
        ),
        sa.ForeignKeyConstraint(
            ["transport_route_snapshot_id"],
            ["event_transport_route_snapshots.snapshot_id"],
            name="fk_wf_endpoint_mat_attempt_snapshot",
        ),
        sa.PrimaryKeyConstraint("attempt_id"),
        sa.UniqueConstraint(
            "materialization_id", name="uq_wf_endpoint_mat_attempt_materialization"
        ),
        sa.UniqueConstraint("consumption_claim_id", name="uq_wf_endpoint_mat_attempt_claim"),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_endpoint_mat_attempt_lease"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_endpoint_mat_attempt_digest"),
    )
    _create_indexes(
        attempt_table,
        "ix_wf_endpoint_mat_attempt",
        {
            "materialization_id": "materialization",
            "consumption_claim_id": "claim",
            "authorization_lease_id": "lease",
            "authorization_lease_digest": "lease_digest",
            "freshness_admission_id": "freshness",
            "freshness_admission_digest": "fresh_digest",
            "physical_transport_route_binding_id": "binding",
            "physical_transport_route_binding_digest": "binding_digest",
            "transport_route_snapshot_id": "snapshot",
            "current_selection_head_id": "head",
            "policy_id": "policy",
            "policy_digest": "policy_digest",
            "organization_id": "org",
            "environment_id": "environment",
            "site_id": "site",
            "resolver_subject_id": "resolver",
            "freshness_valid_until": "fresh_valid_until",
            "lease_valid_until": "lease_valid_until",
            "state": "state",
        },
    )
    op.create_foreign_key(
        "fk_wf_endpoint_consume_claim_attempt",
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
        sa.Column("transport_route_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("transport_route_snapshot_digest", sa.String(length=64), nullable=False),
        *_scope_columns(),
        *_policy_columns(),
        sa.Column("materializer_id", sa.String(length=128), nullable=False),
        sa.Column("materializer_version", sa.String(length=64), nullable=False),
        sa.Column("materialization_receipt_digest", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column("failure_class", sa.String(length=128), nullable=True),
        sa.Column("protected_artifact_id", sa.String(length=128), nullable=True),
        sa.Column("protected_artifact_digest", sa.String(length=64), nullable=True),
        sa.Column("normalized_endpoint_set_digest", sa.String(length=64), nullable=True),
        sa.Column("endpoint_count", sa.Integer(), nullable=False),
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
            "state IN ('materialized_protected', 'materialization_failed')",
            name="ck_wf_endpoint_mat_result_state",
        ),
        sa.CheckConstraint(
            "(state = 'materialized_protected' "
            "AND protected_artifact_id IS NOT NULL "
            "AND protected_artifact_digest IS NOT NULL "
            "AND normalized_endpoint_set_digest IS NOT NULL "
            "AND endpoint_count > 0 "
            "AND usable_until IS NOT NULL "
            "AND completed_at < usable_until "
            "AND NOT protected_artifact_revoked "
            "AND cleanup_confirmed "
            "AND failure_class IS NULL) "
            "OR (state = 'materialization_failed' "
            "AND protected_artifact_id IS NULL "
            "AND protected_artifact_digest IS NULL "
            "AND normalized_endpoint_set_digest IS NULL "
            "AND endpoint_count = 0 "
            "AND usable_until IS NULL "
            "AND protected_artifact_revoked "
            "AND cleanup_confirmed "
            "AND failure_class IS NOT NULL)",
            name="ck_wf_endpoint_mat_result_shape",
        ),
        sa.CheckConstraint(_zero_authority_check(), name="ck_wf_endpoint_mat_result_zero_auth"),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            [f"{attempt_table}.attempt_id"],
            name="fk_wf_endpoint_mat_result_attempt",
        ),
        sa.ForeignKeyConstraint(
            ["consumption_claim_id"],
            [f"{claim_table}.claim_id"],
            name="fk_wf_endpoint_mat_result_claim",
        ),
        sa.ForeignKeyConstraint(
            ["authorization_lease_id"],
            [f"{lease_table}.authorization_lease_id"],
            name="fk_wf_endpoint_mat_result_lease",
        ),
        sa.ForeignKeyConstraint(
            ["freshness_admission_id"],
            ["workflow_event_physical_transport_route_freshness_admissions.freshness_admission_id"],
            name="fk_wf_endpoint_mat_result_freshness",
        ),
        sa.ForeignKeyConstraint(
            ["transport_route_snapshot_id"],
            ["event_transport_route_snapshots.snapshot_id"],
            name="fk_wf_endpoint_mat_result_snapshot",
        ),
        sa.PrimaryKeyConstraint("materialization_id"),
        sa.UniqueConstraint("attempt_id", name="uq_wf_endpoint_mat_result_attempt"),
        sa.UniqueConstraint("consumption_claim_id", name="uq_wf_endpoint_mat_result_claim"),
        sa.UniqueConstraint("authorization_lease_id", name="uq_wf_endpoint_mat_result_lease"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_endpoint_mat_result_digest"),
    )
    _create_indexes(
        result_table,
        "ix_wf_endpoint_mat_result",
        {
            "attempt_id": "attempt",
            "consumption_claim_id": "claim",
            "authorization_lease_id": "lease",
            "authorization_lease_digest": "lease_digest",
            "freshness_admission_id": "freshness",
            "transport_route_snapshot_id": "snapshot",
            "organization_id": "org",
            "environment_id": "environment",
            "site_id": "site",
            "resolver_subject_id": "resolver",
            "policy_id": "policy",
            "policy_digest": "policy_digest",
            "materializer_id": "materializer",
            "state": "state",
            "protected_artifact_id": "artifact",
        },
    )

    op.execute(
        """
        CREATE FUNCTION reject_workflow_endpoint_materialization_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'workflow endpoint materialization evidence is append-only'
                USING ERRCODE = '55000';
        END;
        $$
        """
    )
    for table, trigger in (
        (claim_table, "trg_wf_endpoint_consume_claim_append_only"),
        (attempt_table, "trg_wf_endpoint_mat_attempt_append_only"),
        (result_table, "trg_wf_endpoint_mat_result_append_only"),
    ):
        op.execute(
            f"""
            CREATE TRIGGER {trigger}
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION reject_workflow_endpoint_materialization_mutation()
            """
        )


def downgrade() -> None:
    result_table = "workflow_event_endpoint_materialization_results"
    attempt_table = "workflow_event_endpoint_materialization_attempts"
    claim_table = "workflow_event_endpoint_resolution_lease_consumption_claims"
    for table, trigger in (
        (result_table, "trg_wf_endpoint_mat_result_append_only"),
        (attempt_table, "trg_wf_endpoint_mat_attempt_append_only"),
        (claim_table, "trg_wf_endpoint_consume_claim_append_only"),
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
    op.drop_table(result_table)
    op.drop_constraint(
        "fk_wf_endpoint_consume_claim_attempt",
        claim_table,
        type_="foreignkey",
    )
    op.drop_table(attempt_table)
    op.drop_table(claim_table)
    op.execute("DROP FUNCTION IF EXISTS reject_workflow_endpoint_materialization_mutation()")


def _scope_columns() -> tuple[sa.Column, ...]:
    return (
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("resolver_subject_id", sa.String(length=240), nullable=False),
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
            "route_selection_authority_granted",
            "route_binding_authority_granted",
            "credential_access_authority_granted",
            "network_access_authority_granted",
            "readiness_probe_authority_granted",
            "publication_authority_granted",
            "delivery_authority_granted",
            "dispatch_authority_granted",
            "execution_authority_granted",
        )
    )


def _zero_authority_check() -> str:
    return (
        "NOT endpoint_resolution_authority_granted "
        "AND NOT route_selection_authority_granted "
        "AND NOT route_binding_authority_granted "
        "AND NOT credential_access_authority_granted "
        "AND NOT network_access_authority_granted "
        "AND NOT readiness_probe_authority_granted "
        "AND NOT publication_authority_granted "
        "AND NOT delivery_authority_granted "
        "AND NOT dispatch_authority_granted "
        "AND NOT execution_authority_granted"
    )


def _create_indexes(table: str, prefix: str, columns: dict[str, str]) -> None:
    for column, suffix in columns.items():
        op.create_index(f"{prefix}_{suffix}", table, [column])
