"""Add immutable workflow transport target-context bindings.

Revision ID: 20260815_0131
Revises: 20260815_0130
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260815_0131"
down_revision: str | None = "20260815_0130"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


BINDING_TABLE = "workflow_event_transport_target_context_bindings"
CLAIM_TABLE = "workflow_event_transport_target_context_binding_claims"


def upgrade() -> None:
    op.create_table(
        BINDING_TABLE,
        sa.Column("binding_id", sa.String(length=128), nullable=False),
        sa.Column("physical_transport_route_binding_id", sa.String(length=128), nullable=False),
        sa.Column("physical_transport_route_binding_digest", sa.String(length=64), nullable=False),
        sa.Column("transport_route_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("transport_route_snapshot_digest", sa.String(length=64), nullable=False),
        sa.Column("endpoint_materialization_id", sa.String(length=128), nullable=False),
        sa.Column("endpoint_materialization_digest", sa.String(length=64), nullable=False),
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
        sa.Column("credential_materialization_id", sa.String(length=128), nullable=False),
        sa.Column("credential_materialization_digest", sa.String(length=64), nullable=False),
        sa.Column("resolver_subject_id", sa.String(length=240), nullable=False),
        sa.Column("accessor_subject_id", sa.String(length=240), nullable=False),
        sa.Column("target_context_schema_id", sa.String(length=128), nullable=False),
        sa.Column("target_context_schema_version", sa.String(length=64), nullable=False),
        sa.Column("target_context_commitment", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("binder_subject_id", sa.String(length=240), nullable=False),
        sa.Column("bound_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("joint_usable_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("policy_digest", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        *_zero_authority_columns(),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("state = 'bound'", name="ck_wf_tctx_bind_state"),
        sa.CheckConstraint(
            "bound_at < joint_usable_until",
            name="ck_wf_tctx_bind_window",
        ),
        sa.CheckConstraint(
            _zero_authority_check(),
            name="ck_wf_tctx_bind_zero_auth",
        ),
        sa.ForeignKeyConstraint(
            ["physical_transport_route_binding_id"],
            ["workflow_event_physical_transport_route_bindings.binding_id"],
            name="fk_wf_tctx_bind_route_binding",
        ),
        sa.ForeignKeyConstraint(
            ["transport_route_snapshot_id"],
            ["event_transport_route_snapshots.snapshot_id"],
            name="fk_wf_tctx_bind_route_snapshot",
        ),
        sa.ForeignKeyConstraint(
            ["endpoint_materialization_id"],
            ["workflow_event_endpoint_materialization_results.materialization_id"],
            name="fk_wf_tctx_bind_endpoint_result",
        ),
        sa.ForeignKeyConstraint(
            ["physical_transport_credential_assignment_binding_id"],
            ["workflow_event_physical_transport_credential_bindings.binding_id"],
            name="fk_wf_tctx_bind_cred_binding",
        ),
        sa.ForeignKeyConstraint(
            ["credential_assignment_snapshot_id"],
            ["event_transport_credential_assignment_snapshots.snapshot_id"],
            name="fk_wf_tctx_bind_cred_snapshot",
        ),
        sa.ForeignKeyConstraint(
            ["credential_materialization_id"],
            ["workflow_event_credential_materialization_results.materialization_id"],
            name="fk_wf_tctx_bind_cred_result",
        ),
        sa.PrimaryKeyConstraint("binding_id", name="pk_wf_tctx_bind"),
        sa.UniqueConstraint(
            "endpoint_materialization_id",
            name="uq_wf_tctx_bind_endpoint",
        ),
        sa.UniqueConstraint(
            "credential_materialization_id",
            name="uq_wf_tctx_bind_credential",
        ),
        sa.UniqueConstraint(
            "endpoint_materialization_id",
            "credential_materialization_id",
            name="uq_wf_tctx_bind_pair",
        ),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_tctx_bind_digest"),
    )
    _create_binding_indexes()

    op.create_table(
        CLAIM_TABLE,
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("result_digest", sa.String(length=64), nullable=False),
        sa.Column("binding_id", sa.String(length=128), nullable=False),
        sa.Column("physical_transport_route_binding_id", sa.String(length=128), nullable=False),
        sa.Column("transport_route_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("endpoint_materialization_id", sa.String(length=128), nullable=False),
        sa.Column(
            "physical_transport_credential_assignment_binding_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column("credential_assignment_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("credential_materialization_id", sa.String(length=128), nullable=False),
        sa.Column("target_context_schema_id", sa.String(length=128), nullable=False),
        sa.Column("target_context_schema_version", sa.String(length=64), nullable=False),
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("policy_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("binder_subject_id", sa.String(length=240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["binding_id"],
            [f"{BINDING_TABLE}.binding_id"],
            name="fk_wf_tctx_claim_binding",
        ),
        sa.ForeignKeyConstraint(
            ["physical_transport_route_binding_id"],
            ["workflow_event_physical_transport_route_bindings.binding_id"],
            name="fk_wf_tctx_claim_route_binding",
        ),
        sa.ForeignKeyConstraint(
            ["transport_route_snapshot_id"],
            ["event_transport_route_snapshots.snapshot_id"],
            name="fk_wf_tctx_claim_route_snapshot",
        ),
        sa.ForeignKeyConstraint(
            ["endpoint_materialization_id"],
            ["workflow_event_endpoint_materialization_results.materialization_id"],
            name="fk_wf_tctx_claim_endpoint_result",
        ),
        sa.ForeignKeyConstraint(
            ["physical_transport_credential_assignment_binding_id"],
            ["workflow_event_physical_transport_credential_bindings.binding_id"],
            name="fk_wf_tctx_claim_cred_binding",
        ),
        sa.ForeignKeyConstraint(
            ["credential_assignment_snapshot_id"],
            ["event_transport_credential_assignment_snapshots.snapshot_id"],
            name="fk_wf_tctx_claim_cred_snapshot",
        ),
        sa.ForeignKeyConstraint(
            ["credential_materialization_id"],
            ["workflow_event_credential_materialization_results.materialization_id"],
            name="fk_wf_tctx_claim_cred_result",
        ),
        sa.PrimaryKeyConstraint("claim_id", name="pk_wf_tctx_claim"),
        sa.UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_tctx_claim_scope_idem",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "environment_id",
            "site_id",
            "binder_subject_id",
            "idempotency_key",
            name="uq_wf_tctx_claim_binder_idem",
        ),
        sa.UniqueConstraint("binding_id", name="uq_wf_tctx_claim_binding"),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_tctx_claim_digest"),
    )
    _create_claim_indexes()

    op.execute(
        """
        CREATE FUNCTION reject_wf_target_context_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'workflow target-context evidence is append-only'
                USING ERRCODE = '55000';
        END;
        $$
        """
    )
    for table_name, trigger_name in (
        (BINDING_TABLE, "trg_wf_tctx_bind_append_only"),
        (CLAIM_TABLE, "trg_wf_tctx_claim_append_only"),
    ):
        op.execute(
            f"""
            CREATE TRIGGER {trigger_name}
            BEFORE UPDATE OR DELETE ON {table_name}
            FOR EACH ROW
            EXECUTE FUNCTION reject_wf_target_context_mutation()
            """
        )


def downgrade() -> None:
    for table_name, trigger_name in (
        (CLAIM_TABLE, "trg_wf_tctx_claim_append_only"),
        (BINDING_TABLE, "trg_wf_tctx_bind_append_only"),
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name}")
    op.execute("DROP FUNCTION IF EXISTS reject_wf_target_context_mutation()")
    op.drop_table(CLAIM_TABLE)
    op.drop_table(BINDING_TABLE)


def _zero_authority_columns() -> tuple[sa.Column[object], ...]:
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


def _create_binding_indexes() -> None:
    indexes: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("ix_wf_tctx_bind_route", ("physical_transport_route_binding_id",)),
        ("ix_wf_tctx_bind_snapshot", ("transport_route_snapshot_id",)),
        ("ix_wf_tctx_bind_endpoint", ("endpoint_materialization_id",)),
        (
            "ix_wf_tctx_bind_cred_binding",
            ("physical_transport_credential_assignment_binding_id",),
        ),
        ("ix_wf_tctx_bind_cred_snapshot", ("credential_assignment_snapshot_id",)),
        ("ix_wf_tctx_bind_cred_result", ("credential_materialization_id",)),
        ("ix_wf_tctx_bind_policy", ("policy_digest",)),
        ("ix_wf_tctx_bind_scope", ("organization_id", "environment_id", "site_id")),
        ("ix_wf_tctx_bind_binder", ("binder_subject_id",)),
        ("ix_wf_tctx_bind_joint_until", ("joint_usable_until",)),
    )
    for name, columns in indexes:
        op.create_index(name, BINDING_TABLE, list(columns))


def _create_claim_indexes() -> None:
    indexes: tuple[tuple[str, str], ...] = (
        ("ix_wf_tctx_claim_route", "physical_transport_route_binding_id"),
        ("ix_wf_tctx_claim_snapshot", "transport_route_snapshot_id"),
        ("ix_wf_tctx_claim_endpoint", "endpoint_materialization_id"),
        (
            "ix_wf_tctx_claim_cred_binding",
            "physical_transport_credential_assignment_binding_id",
        ),
        ("ix_wf_tctx_claim_cred_snapshot", "credential_assignment_snapshot_id"),
        ("ix_wf_tctx_claim_cred_result", "credential_materialization_id"),
        ("ix_wf_tctx_claim_policy", "policy_digest"),
        ("ix_wf_tctx_claim_created", "created_at"),
    )
    for name, column in indexes:
        op.create_index(name, CLAIM_TABLE, [column])
