"""Add immutable workflow physical transport route bindings.

Revision ID: 20260814_0122
Revises: 20260814_0121
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0122"
down_revision: str | None = "20260814_0121"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    binding_table = "workflow_event_physical_transport_route_bindings"
    op.create_table(
        binding_table,
        sa.Column("binding_id", sa.String(length=128), nullable=False),
        sa.Column("logical_channel_binding_id", sa.String(length=128), nullable=False),
        sa.Column("logical_channel_binding_digest", sa.String(length=64), nullable=False),
        sa.Column("transport_compatibility_admission_id", sa.String(length=128), nullable=False),
        sa.Column("transport_compatibility_admission_digest", sa.String(length=64), nullable=False),
        sa.Column("transport_profile_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("transport_profile_snapshot_digest", sa.String(length=64), nullable=False),
        sa.Column("transport_route_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("transport_route_snapshot_digest", sa.String(length=64), nullable=False),
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("policy_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("binder_subject_id", sa.String(length=240), nullable=False),
        sa.Column("bound_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.CheckConstraint("state = 'bound'", name="ck_wf_physical_route_binding_state"),
        sa.CheckConstraint(
            "NOT endpoint_resolution_authority_granted "
            "AND NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted",
            name="ck_wf_physical_route_binding_zero_auth",
        ),
        sa.ForeignKeyConstraint(
            ["logical_channel_binding_id"],
            ["workflow_event_channel_bindings.binding_id"],
            name="fk_wf_physical_route_binding_logical",
        ),
        sa.ForeignKeyConstraint(
            ["transport_compatibility_admission_id"],
            ["workflow_event_transport_compatibility_admissions.compatibility_admission_id"],
            name="fk_wf_physical_route_binding_compat",
        ),
        sa.ForeignKeyConstraint(
            ["transport_profile_snapshot_id"],
            ["event_transport_profile_snapshots.snapshot_id"],
            name="fk_wf_physical_route_binding_profile",
        ),
        sa.ForeignKeyConstraint(
            ["transport_route_snapshot_id"],
            ["event_transport_route_snapshots.snapshot_id"],
            name="fk_wf_physical_route_binding_route",
        ),
        sa.PrimaryKeyConstraint("binding_id"),
        sa.UniqueConstraint(
            "logical_channel_binding_id",
            name="uq_wf_physical_route_binding_logical_binding",
        ),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_wf_physical_route_binding_digest",
        ),
    )
    binding_indexes = {
        "logical_channel_binding_id": "logical",
        "logical_channel_binding_digest": "logical_digest",
        "transport_compatibility_admission_id": "compat",
        "transport_compatibility_admission_digest": "compat_digest",
        "transport_profile_snapshot_id": "profile",
        "transport_profile_snapshot_digest": "profile_digest",
        "transport_route_snapshot_id": "route",
        "transport_route_snapshot_digest": "route_digest",
        "policy_id": "policy",
        "policy_digest": "policy_digest",
        "organization_id": "org",
        "environment_id": "environment",
        "site_id": "site",
        "binder_subject_id": "binder",
        "state": "state",
    }
    for column, suffix in binding_indexes.items():
        op.create_index(f"ix_wf_physical_route_binding_{suffix}", binding_table, [column])

    claim_table = "workflow_event_physical_transport_route_binding_claims"
    op.create_table(
        claim_table,
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("result_digest", sa.String(length=64), nullable=False),
        sa.Column("binding_id", sa.String(length=128), nullable=False),
        sa.Column("logical_channel_binding_id", sa.String(length=128), nullable=False),
        sa.Column("transport_compatibility_admission_id", sa.String(length=128), nullable=False),
        sa.Column("transport_profile_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("transport_route_snapshot_id", sa.String(length=128), nullable=False),
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
            ["workflow_event_physical_transport_route_bindings.binding_id"],
            name="fk_wf_physical_route_binding_claim_binding",
        ),
        sa.ForeignKeyConstraint(
            ["logical_channel_binding_id"],
            ["workflow_event_channel_bindings.binding_id"],
            name="fk_wf_physical_route_binding_claim_logical",
        ),
        sa.ForeignKeyConstraint(
            ["transport_compatibility_admission_id"],
            ["workflow_event_transport_compatibility_admissions.compatibility_admission_id"],
            name="fk_wf_physical_route_binding_claim_compat",
        ),
        sa.ForeignKeyConstraint(
            ["transport_profile_snapshot_id"],
            ["event_transport_profile_snapshots.snapshot_id"],
            name="fk_wf_physical_route_binding_claim_profile",
        ),
        sa.ForeignKeyConstraint(
            ["transport_route_snapshot_id"],
            ["event_transport_route_snapshots.snapshot_id"],
            name="fk_wf_physical_route_binding_claim_route",
        ),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_physical_route_binding_claim_scope_idem",
        ),
        sa.UniqueConstraint(
            "binding_id",
            name="uq_wf_physical_route_binding_claim_binding",
        ),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_wf_physical_route_binding_claim_digest",
        ),
    )
    claim_indexes = {
        "idempotency_scope_id": "scope",
        "binding_id": "binding",
        "logical_channel_binding_id": "logical",
        "transport_compatibility_admission_id": "compat",
        "transport_profile_snapshot_id": "profile",
        "transport_route_snapshot_id": "route",
        "policy_digest": "policy_digest",
        "organization_id": "org",
        "environment_id": "environment",
        "site_id": "site",
        "binder_subject_id": "binder",
    }
    for column, suffix in claim_indexes.items():
        op.create_index(f"ix_wf_physical_route_claim_{suffix}", claim_table, [column])

    op.execute(
        """
        CREATE FUNCTION reject_wf_physical_route_binding_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'workflow physical transport route bindings are append-only'
                USING ERRCODE = '55000';
        END;
        $$
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER trg_wf_physical_route_bindings_append_only
        BEFORE UPDATE OR DELETE ON {binding_table}
        FOR EACH ROW
        EXECUTE FUNCTION reject_wf_physical_route_binding_mutation()
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER trg_wf_physical_route_binding_claims_append_only
        BEFORE UPDATE OR DELETE ON {claim_table}
        FOR EACH ROW
        EXECUTE FUNCTION reject_wf_physical_route_binding_mutation()
        """
    )


def downgrade() -> None:
    binding_table = "workflow_event_physical_transport_route_bindings"
    claim_table = "workflow_event_physical_transport_route_binding_claims"
    op.execute(
        f"DROP TRIGGER IF EXISTS trg_wf_physical_route_binding_claims_append_only ON {claim_table}"
    )
    op.execute(
        f"DROP TRIGGER IF EXISTS trg_wf_physical_route_bindings_append_only ON {binding_table}"
    )
    op.execute("DROP FUNCTION IF EXISTS reject_wf_physical_route_binding_mutation()")

    for suffix in reversed(
        (
            "scope",
            "binding",
            "logical",
            "compat",
            "profile",
            "route",
            "policy_digest",
            "org",
            "environment",
            "site",
            "binder",
        )
    ):
        op.drop_index(f"ix_wf_physical_route_claim_{suffix}", table_name=claim_table)
    op.drop_table(claim_table)

    for suffix in reversed(
        (
            "logical",
            "logical_digest",
            "compat",
            "compat_digest",
            "profile",
            "profile_digest",
            "route",
            "route_digest",
            "policy",
            "policy_digest",
            "org",
            "environment",
            "site",
            "binder",
            "state",
        )
    ):
        op.drop_index(f"ix_wf_physical_route_binding_{suffix}", table_name=binding_table)
    op.drop_table(binding_table)
