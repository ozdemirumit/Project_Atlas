"""Add immutable deployment event transport route snapshots.

Revision ID: 20260814_0121
Revises: 20260814_0120
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0121"
down_revision: str | None = "20260814_0120"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    snapshot_table = "event_transport_route_snapshots"
    op.create_table(
        snapshot_table,
        sa.Column("snapshot_id", sa.String(length=128), nullable=False),
        # Preserve deployment-owned source identity as immutable evidence. It
        # deliberately has no foreign key to mutable deployment configuration.
        sa.Column("route_id", sa.String(length=128), nullable=False),
        sa.Column("route_revision", sa.String(length=64), nullable=False),
        sa.Column("route_set_id", sa.String(length=128), nullable=False),
        sa.Column("route_set_revision", sa.String(length=64), nullable=False),
        sa.Column("selection_epoch_id", sa.String(length=128), nullable=False),
        sa.Column("selection_epoch_revision", sa.String(length=64), nullable=False),
        sa.Column("source_route_digest", sa.String(length=64), nullable=False),
        sa.Column("deployment_release_id", sa.String(length=128), nullable=False),
        sa.Column("deployment_profile", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("transport_profile_id", sa.String(length=128), nullable=False),
        sa.Column("transport_profile_revision", sa.String(length=64), nullable=False),
        sa.Column("transport_resource_id", sa.String(length=128), nullable=False),
        sa.Column("transport_resource_digest", sa.String(length=64), nullable=False),
        sa.Column("transport_implementation_id", sa.String(length=128), nullable=False),
        sa.Column("transport_implementation_version", sa.String(length=64), nullable=False),
        sa.Column("adapter_contract_id", sa.String(length=128), nullable=False),
        sa.Column("adapter_contract_version", sa.String(length=64), nullable=False),
        sa.Column("adapter_contract_digest", sa.String(length=64), nullable=False),
        sa.Column("route_kind", sa.String(length=64), nullable=False),
        sa.Column("endpoint_set_id", sa.String(length=128), nullable=False),
        sa.Column("endpoint_set_revision", sa.String(length=64), nullable=False),
        sa.Column("destination_id", sa.String(length=128), nullable=False),
        sa.Column("destination_revision", sa.String(length=64), nullable=False),
        sa.Column("routing_contract_id", sa.String(length=128), nullable=False),
        sa.Column("routing_contract_revision", sa.String(length=64), nullable=False),
        sa.Column("private_route_descriptor_commitment", sa.String(length=64), nullable=False),
        sa.Column("transport_security_policy_id", sa.String(length=128), nullable=False),
        sa.Column("transport_security_policy_version", sa.String(length=64), nullable=False),
        sa.Column("transport_security_policy_digest", sa.String(length=64), nullable=False),
        sa.Column("minimum_tls_version", sa.String(length=32), nullable=False),
        sa.Column("server_authentication_required", sa.Boolean(), nullable=False),
        sa.Column("client_authentication_required", sa.Boolean(), nullable=False),
        sa.Column("plaintext_fallback_prohibited", sa.Boolean(), nullable=False),
        sa.Column("network_policy_id", sa.String(length=128), nullable=False),
        sa.Column("network_policy_version", sa.String(length=64), nullable=False),
        sa.Column("network_policy_digest", sa.String(length=64), nullable=False),
        sa.Column("source_zone_class", sa.String(length=64), nullable=False),
        sa.Column("destination_zone_class", sa.String(length=64), nullable=False),
        sa.Column("restricted_network_enforced", sa.Boolean(), nullable=False),
        sa.Column("public_egress_prohibited", sa.Boolean(), nullable=False),
        sa.Column("proxy_mode", sa.String(length=32), nullable=False),
        sa.Column("credential_requirement_profile_id", sa.String(length=128), nullable=False),
        sa.Column("credential_requirement_profile_version", sa.String(length=64), nullable=False),
        sa.Column("credential_requirement_profile_digest", sa.String(length=64), nullable=False),
        sa.Column("authentication_mechanism_class", sa.String(length=64), nullable=False),
        sa.Column("principal_class", sa.String(length=64), nullable=False),
        sa.Column("snapshotter_subject_id", sa.String(length=240), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("route_selection_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("route_binding_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("endpoint_resolution_authority_granted", sa.Boolean(), nullable=False),
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
            "state = 'snapshotted'",
            name="ck_event_transport_route_snapshot_state",
        ),
        sa.CheckConstraint(
            "NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT endpoint_resolution_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT network_access_authority_granted "
            "AND NOT readiness_probe_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted",
            name="ck_event_transport_route_snapshot_zero_auth",
        ),
        sa.PrimaryKeyConstraint("snapshot_id"),
        sa.UniqueConstraint(
            "route_id",
            "route_revision",
            name="uq_event_transport_route_snapshot_revision",
        ),
        sa.UniqueConstraint(
            "source_route_digest",
            name="uq_event_transport_route_snapshot_source_digest",
        ),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_event_transport_route_snapshot_digest",
        ),
    )
    snapshot_indexes = {
        "route_id": "route",
        "route_set_id": "route_set",
        "selection_epoch_id": "selection_epoch",
        "source_route_digest": "source_digest",
        "deployment_release_id": "release",
        "deployment_profile": "deployment_profile",
        "organization_id": "org",
        "environment_id": "environment",
        "site_id": "site",
        "transport_profile_id": "profile",
        "transport_resource_id": "resource",
        "transport_implementation_id": "implementation",
        "adapter_contract_id": "adapter",
        "snapshotter_subject_id": "snapshotter",
        "state": "state",
    }
    for column, suffix in snapshot_indexes.items():
        op.create_index(f"ix_event_transport_route_snapshot_{suffix}", snapshot_table, [column])

    claim_table = "event_transport_route_snapshot_claims"
    op.create_table(
        claim_table,
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("result_digest", sa.String(length=64), nullable=False),
        sa.Column("snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("route_id", sa.String(length=128), nullable=False),
        sa.Column("route_revision", sa.String(length=64), nullable=False),
        sa.Column("source_route_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("snapshotter_subject_id", sa.String(length=240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["event_transport_route_snapshots.snapshot_id"],
            name="fk_event_transport_route_claim_snapshot",
        ),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_event_transport_route_claim_scope_idem",
        ),
        sa.UniqueConstraint(
            "snapshot_id",
            name="uq_event_transport_route_claim_snapshot",
        ),
        sa.UniqueConstraint(
            "route_id",
            "route_revision",
            name="uq_event_transport_route_claim_revision",
        ),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_event_transport_route_claim_digest",
        ),
    )
    claim_indexes = {
        "idempotency_scope_id": "scope",
        "snapshot_id": "snapshot",
        "route_id": "route",
        "source_route_digest": "source_digest",
        "organization_id": "org",
        "environment_id": "environment",
        "site_id": "site",
        "snapshotter_subject_id": "snapshotter",
    }
    for column, suffix in claim_indexes.items():
        op.create_index(f"ix_event_transport_route_claim_{suffix}", claim_table, [column])

    op.execute(
        """
        CREATE FUNCTION reject_event_transport_route_snapshot_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'event transport route snapshots are append-only'
                USING ERRCODE = '55000';
        END;
        $$
        """
    )
    for table_name in (snapshot_table, claim_table):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table_name}_append_only
            BEFORE UPDATE OR DELETE ON {table_name}
            FOR EACH ROW
            EXECUTE FUNCTION reject_event_transport_route_snapshot_mutation()
            """
        )


def downgrade() -> None:
    snapshot_table = "event_transport_route_snapshots"
    claim_table = "event_transport_route_snapshot_claims"
    for table_name in (claim_table, snapshot_table):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_append_only ON {table_name}")
    op.execute("DROP FUNCTION IF EXISTS reject_event_transport_route_snapshot_mutation()")

    for suffix in reversed(
        (
            "scope",
            "snapshot",
            "route",
            "source_digest",
            "org",
            "environment",
            "site",
            "snapshotter",
        )
    ):
        op.drop_index(f"ix_event_transport_route_claim_{suffix}", table_name=claim_table)
    op.drop_table(claim_table)

    for suffix in reversed(
        (
            "route",
            "route_set",
            "selection_epoch",
            "source_digest",
            "release",
            "deployment_profile",
            "org",
            "environment",
            "site",
            "profile",
            "resource",
            "implementation",
            "adapter",
            "snapshotter",
            "state",
        )
    ):
        op.drop_index(f"ix_event_transport_route_snapshot_{suffix}", table_name=snapshot_table)
    op.drop_table(snapshot_table)
