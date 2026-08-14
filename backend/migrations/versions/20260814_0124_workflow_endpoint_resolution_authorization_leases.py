"""Add bounded workflow endpoint-resolution authorization leases.

Revision ID: 20260814_0124
Revises: 20260814_0123
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0124"
down_revision: str | None = "20260814_0123"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    lease_table = "workflow_event_endpoint_resolution_authorization_leases"
    claim_table = "workflow_event_endpoint_resolution_authorization_lease_claims"

    op.create_table(
        lease_table,
        sa.Column(
            "authorization_lease_id",
            sa.String(length=128),
            nullable=False,
        ),
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
        sa.Column("route_set_id", sa.String(length=128), nullable=False),
        sa.Column("route_set_revision", sa.String(length=64), nullable=False),
        sa.Column("selection_epoch_id", sa.String(length=128), nullable=False),
        sa.Column("selection_epoch_revision", sa.String(length=64), nullable=False),
        sa.Column("selected_route_id", sa.String(length=128), nullable=False),
        sa.Column("selected_route_revision", sa.String(length=64), nullable=False),
        sa.Column("selected_route_digest", sa.String(length=64), nullable=False),
        sa.Column("selection_active", sa.Boolean(), nullable=False),
        sa.Column("selection_eligible", sa.Boolean(), nullable=False),
        sa.Column("selection_suspended", sa.Boolean(), nullable=False),
        sa.Column("selection_withdrawn", sa.Boolean(), nullable=False),
        sa.Column("selection_superseded", sa.Boolean(), nullable=False),
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("policy_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("resolver_subject_id", sa.String(length=240), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("endpoint_resolution_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("route_selection_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("route_binding_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("credential_access_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("network_access_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("readiness_probe_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("publication_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("delivery_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("dispatch_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("execution_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "state = 'authorized_unconsumed'",
            name="ck_wf_endpoint_res_lease_state",
        ),
        sa.CheckConstraint(
            "valid_until = issued_at + INTERVAL '15 seconds'",
            name="ck_wf_endpoint_res_lease_window",
        ),
        sa.CheckConstraint(
            "endpoint_resolution_authority_granted "
            "AND NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted",
            name="ck_wf_endpoint_res_lease_authority",
        ),
        sa.CheckConstraint(
            "current_selection_head_generation > 0",
            name="ck_wf_endpoint_res_lease_generation",
        ),
        sa.CheckConstraint(
            "selection_active AND selection_eligible "
            "AND NOT selection_suspended AND NOT selection_withdrawn "
            "AND NOT selection_superseded",
            name="ck_wf_endpoint_res_lease_selection",
        ),
        sa.ForeignKeyConstraint(
            ["freshness_admission_id"],
            ["workflow_event_physical_transport_route_freshness_admissions.freshness_admission_id"],
            name="fk_wf_endpoint_res_lease_freshness",
        ),
        sa.ForeignKeyConstraint(
            ["physical_transport_route_binding_id"],
            ["workflow_event_physical_transport_route_bindings.binding_id"],
            name="fk_wf_endpoint_res_lease_binding",
        ),
        sa.ForeignKeyConstraint(
            ["transport_route_snapshot_id"],
            ["event_transport_route_snapshots.snapshot_id"],
            name="fk_wf_endpoint_res_lease_snapshot",
        ),
        sa.PrimaryKeyConstraint("authorization_lease_id"),
        sa.UniqueConstraint(
            "freshness_admission_id",
            name="uq_wf_endpoint_res_lease_freshness",
        ),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_wf_endpoint_res_lease_digest",
        ),
    )
    lease_indexes = {
        "freshness_admission_id": "freshness",
        "freshness_admission_digest": "fresh_digest",
        "physical_transport_route_binding_id": "binding",
        "physical_transport_route_binding_digest": "binding_digest",
        "transport_route_snapshot_id": "snapshot",
        "transport_route_snapshot_digest": "snapshot_digest",
        "current_selection_head_id": "head",
        "current_selection_head_digest": "head_digest",
        "current_selection_head_fencing_token_digest": "fence",
        "route_set_id": "route_set",
        "selection_epoch_id": "epoch",
        "selected_route_id": "route",
        "selected_route_digest": "route_digest",
        "policy_id": "policy",
        "policy_digest": "policy_digest",
        "organization_id": "org",
        "environment_id": "environment",
        "site_id": "site",
        "resolver_subject_id": "resolver",
        "valid_until": "valid_until",
        "state": "state",
    }
    for column, suffix in lease_indexes.items():
        op.create_index(f"ix_wf_endpoint_res_lease_{suffix}", lease_table, [column])

    op.create_table(
        claim_table,
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("result_digest", sa.String(length=64), nullable=False),
        sa.Column(
            "authorization_lease_id",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column("freshness_admission_id", sa.String(length=128), nullable=False),
        sa.Column("physical_transport_route_binding_id", sa.String(length=128), nullable=False),
        sa.Column("transport_route_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("current_selection_head_id", sa.String(length=128), nullable=False),
        sa.Column("current_selection_head_generation", sa.BigInteger(), nullable=False),
        sa.Column(
            "current_selection_head_fencing_token_digest",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("policy_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("resolver_subject_id", sa.String(length=240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["authorization_lease_id"],
            [f"{lease_table}.authorization_lease_id"],
            name="fk_wf_endpoint_res_claim_lease",
        ),
        sa.ForeignKeyConstraint(
            ["freshness_admission_id"],
            ["workflow_event_physical_transport_route_freshness_admissions.freshness_admission_id"],
            name="fk_wf_endpoint_res_claim_freshness",
        ),
        sa.ForeignKeyConstraint(
            ["physical_transport_route_binding_id"],
            ["workflow_event_physical_transport_route_bindings.binding_id"],
            name="fk_wf_endpoint_res_claim_binding",
        ),
        sa.ForeignKeyConstraint(
            ["transport_route_snapshot_id"],
            ["event_transport_route_snapshots.snapshot_id"],
            name="fk_wf_endpoint_res_claim_snapshot",
        ),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_endpoint_res_claim_scope_idem",
        ),
        sa.UniqueConstraint(
            "authorization_lease_id",
            name="uq_wf_endpoint_res_claim_lease",
        ),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_wf_endpoint_res_claim_digest",
        ),
    )
    claim_indexes = {
        "idempotency_scope_id": "scope",
        "authorization_lease_id": "lease",
        "freshness_admission_id": "freshness",
        "physical_transport_route_binding_id": "binding",
        "transport_route_snapshot_id": "snapshot",
        "current_selection_head_id": "head",
        "current_selection_head_fencing_token_digest": "fence",
        "policy_digest": "policy",
        "organization_id": "org",
        "environment_id": "environment",
        "site_id": "site",
        "resolver_subject_id": "resolver",
    }
    for column, suffix in claim_indexes.items():
        op.create_index(f"ix_wf_endpoint_res_claim_{suffix}", claim_table, [column])

    op.execute(
        """
        CREATE FUNCTION reject_endpoint_resolution_authorization_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'endpoint-resolution authorization evidence is append-only'
                USING ERRCODE = '55000';
        END;
        $$
        """
    )
    for table, trigger in (
        (lease_table, "trg_wf_endpoint_res_lease_append_only"),
        (claim_table, "trg_wf_endpoint_res_claim_append_only"),
    ):
        op.execute(
            f"""
            CREATE TRIGGER {trigger}
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION reject_endpoint_resolution_authorization_mutation()
            """
        )


def downgrade() -> None:
    lease_table = "workflow_event_endpoint_resolution_authorization_leases"
    claim_table = "workflow_event_endpoint_resolution_authorization_lease_claims"

    for table, trigger in (
        (claim_table, "trg_wf_endpoint_res_claim_append_only"),
        (lease_table, "trg_wf_endpoint_res_lease_append_only"),
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
    op.execute("DROP FUNCTION IF EXISTS reject_endpoint_resolution_authorization_mutation()")

    op.drop_table(claim_table)
    op.drop_table(lease_table)
