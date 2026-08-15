"""Add immutable deployment transport credential-assignment snapshots.

Revision ID: 20260815_0126
Revises: 20260814_0125
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260815_0126"
down_revision: str | None = "20260814_0125"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    source_table = "deployment_event_transport_credential_assignments"
    snapshot_table = "event_transport_credential_assignment_snapshots"
    claim_table = "event_transport_credential_assignment_snapshot_claims"

    op.create_table(
        source_table,
        *_assignment_columns(),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "credential_generation > 0 AND rotation_epoch > 0",
            name="ck_deploy_transport_credential_assignment_generations",
        ),
        sa.CheckConstraint(
            "activated_at < expires_at",
            name="ck_deploy_transport_credential_assignment_window",
        ),
        sa.CheckConstraint(
            "NOT (active AND revoked)",
            name="ck_deploy_transport_credential_assignment_lifecycle",
        ),
        sa.PrimaryKeyConstraint("assignment_id", "assignment_revision"),
        sa.UniqueConstraint(
            "source_assignment_digest",
            name="uq_deploy_transport_credential_assignment_source_digest",
        ),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_deploy_transport_credential_assignment_digest",
        ),
        sa.UniqueConstraint(
            "assignment_id",
            "rotation_epoch",
            "credential_generation",
            name="uq_deploy_transport_credential_assignment_head_rank",
        ),
    )
    _create_indexes(
        source_table,
        "ix_deploy_transport_credential_assignment",
        {
            "assignment_id": "assignment",
            "route_id": "route",
            "organization_id": "org",
            "environment_id": "environment",
            "site_id": "site",
            "credential_generation": "generation",
            "rotation_epoch": "rotation",
            "expires_at": "expires",
            "active": "active",
        },
    )

    op.create_table(
        snapshot_table,
        sa.Column("snapshot_id", sa.String(length=128), nullable=False),
        *_assignment_columns(snapshot=True),
        sa.Column("route_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("snapshotter_subject_id", sa.String(length=240), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        *_zero_authority_columns(),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "credential_generation > 0 AND rotation_epoch > 0",
            name="ck_event_transport_credential_snapshot_generations",
        ),
        sa.CheckConstraint(
            "activated_at <= captured_at AND captured_at < expires_at",
            name="ck_event_transport_credential_snapshot_window",
        ),
        sa.CheckConstraint(
            "state = 'snapshotted' AND source_non_revoked",
            name="ck_event_transport_credential_snapshot_state",
        ),
        sa.CheckConstraint(
            _zero_authority_check(),
            name="ck_event_transport_credential_snapshot_zero_auth",
        ),
        sa.ForeignKeyConstraint(
            ["route_snapshot_id"],
            ["event_transport_route_snapshots.snapshot_id"],
            name="fk_event_transport_credential_snapshot_route",
        ),
        sa.PrimaryKeyConstraint("snapshot_id"),
        sa.UniqueConstraint(
            "assignment_id",
            "assignment_revision",
            name="uq_event_transport_credential_snapshot_revision",
        ),
        sa.UniqueConstraint(
            "source_assignment_digest",
            name="uq_event_transport_credential_snapshot_source_digest",
        ),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_event_transport_credential_snapshot_digest",
        ),
    )
    _create_indexes(
        snapshot_table,
        "ix_event_transport_credential_snapshot",
        {
            "assignment_id": "assignment",
            "route_id": "route",
            "route_snapshot_id": "route_snapshot",
            "organization_id": "org",
            "environment_id": "environment",
            "site_id": "site",
            "credential_generation": "generation",
            "rotation_epoch": "rotation",
            "expires_at": "expires",
            "snapshotter_subject_id": "snapshotter",
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
        sa.Column("snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("assignment_id", sa.String(length=128), nullable=False),
        sa.Column("assignment_revision", sa.String(length=64), nullable=False),
        sa.Column("source_assignment_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("snapshotter_subject_id", sa.String(length=240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            [f"{snapshot_table}.snapshot_id"],
            name="fk_event_transport_credential_claim_snapshot",
        ),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_event_transport_credential_claim_scope_idem",
        ),
        sa.UniqueConstraint(
            "snapshot_id",
            name="uq_event_transport_credential_claim_snapshot",
        ),
        sa.UniqueConstraint(
            "assignment_id",
            "assignment_revision",
            name="uq_event_transport_credential_claim_revision",
        ),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_event_transport_credential_claim_digest",
        ),
    )
    _create_indexes(
        claim_table,
        "ix_event_transport_credential_claim",
        {
            "idempotency_scope_id": "scope",
            "snapshot_id": "snapshot",
            "assignment_id": "assignment",
            "source_assignment_digest": "source_digest",
            "organization_id": "org",
            "environment_id": "environment",
            "site_id": "site",
            "snapshotter_subject_id": "snapshotter",
        },
    )

    op.execute(
        """
        CREATE FUNCTION reject_event_transport_credential_assignment_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'event transport credential-assignment evidence is append-only'
                USING ERRCODE = '55000';
        END;
        $$
        """
    )
    for table_name in (source_table, snapshot_table, claim_table):
        op.execute(
            f"""
            CREATE TRIGGER trg_{table_name}_append_only
            BEFORE UPDATE OR DELETE ON {table_name}
            FOR EACH ROW
            EXECUTE FUNCTION reject_event_transport_credential_assignment_mutation()
            """
        )


def downgrade() -> None:
    source_table = "deployment_event_transport_credential_assignments"
    snapshot_table = "event_transport_credential_assignment_snapshots"
    claim_table = "event_transport_credential_assignment_snapshot_claims"
    for table_name in (claim_table, snapshot_table, source_table):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table_name}_append_only ON {table_name}")
    op.execute("DROP FUNCTION IF EXISTS reject_event_transport_credential_assignment_mutation()")

    for suffix in reversed(
        (
            "scope",
            "snapshot",
            "assignment",
            "source_digest",
            "org",
            "environment",
            "site",
            "snapshotter",
        )
    ):
        op.drop_index(f"ix_event_transport_credential_claim_{suffix}", table_name=claim_table)
    op.drop_table(claim_table)

    for suffix in reversed(
        (
            "assignment",
            "route",
            "route_snapshot",
            "org",
            "environment",
            "site",
            "generation",
            "rotation",
            "expires",
            "snapshotter",
            "state",
        )
    ):
        op.drop_index(f"ix_event_transport_credential_snapshot_{suffix}", table_name=snapshot_table)
    op.drop_table(snapshot_table)

    for suffix in reversed(
        (
            "assignment",
            "route",
            "org",
            "environment",
            "site",
            "generation",
            "rotation",
            "expires",
            "active",
        )
    ):
        op.drop_index(
            f"ix_deploy_transport_credential_assignment_{suffix}", table_name=source_table
        )
    op.drop_table(source_table)


def _assignment_columns(*, snapshot: bool = False) -> tuple[sa.Column[object], ...]:
    return (
        sa.Column("assignment_id", sa.String(length=128), nullable=False),
        sa.Column("assignment_revision", sa.String(length=64), nullable=False),
        sa.Column("source_assignment_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("route_id", sa.String(length=128), nullable=False),
        sa.Column("route_revision", sa.String(length=64), nullable=False),
        sa.Column("source_route_digest", sa.String(length=64), nullable=False),
        sa.Column("credential_requirement_profile_id", sa.String(length=128), nullable=False),
        sa.Column("credential_requirement_profile_version", sa.String(length=64), nullable=False),
        sa.Column("credential_requirement_profile_digest", sa.String(length=64), nullable=False),
        sa.Column("credential_profile_id", sa.String(length=128), nullable=False),
        sa.Column("credential_profile_version", sa.String(length=64), nullable=False),
        sa.Column("credential_profile_digest", sa.String(length=64), nullable=False),
        sa.Column("authentication_mechanism_class", sa.String(length=64), nullable=False),
        sa.Column("principal_class", sa.String(length=64), nullable=False),
        sa.Column("privilege_class", sa.String(length=64), nullable=False),
        sa.Column("target_scope_commitment", sa.String(length=64), nullable=False),
        sa.Column("credential_generation", sa.BigInteger(), nullable=False),
        sa.Column("rotation_epoch", sa.BigInteger(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "source_non_revoked" if snapshot else "revoked",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column("broker_policy_id", sa.String(length=128), nullable=False),
        sa.Column("broker_policy_version", sa.String(length=64), nullable=False),
        sa.Column("broker_policy_digest", sa.String(length=64), nullable=False),
    )


def _zero_authority_columns() -> tuple[sa.Column[object], ...]:
    return tuple(
        sa.Column(name, sa.Boolean(), nullable=False)
        for name in (
            "endpoint_resolution_authority_granted",
            "protected_artifact_access_authority_granted",
            "credential_selection_authority_granted",
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
    return " AND ".join(
        f"NOT {name}"
        for name in (
            "endpoint_resolution_authority_granted",
            "protected_artifact_access_authority_granted",
            "credential_selection_authority_granted",
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


def _create_indexes(table_name: str, prefix: str, columns: dict[str, str]) -> None:
    for column, suffix in columns.items():
        op.create_index(f"{prefix}_{suffix}", table_name, [column])
