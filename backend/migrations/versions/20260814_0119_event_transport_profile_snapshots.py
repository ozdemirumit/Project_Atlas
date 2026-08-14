"""Add immutable deployment transport capability profile snapshots.

Revision ID: 20260814_0119
Revises: 20260814_0118
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0119"
down_revision: str | None = "20260814_0118"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    snapshot_table = "event_transport_profile_snapshots"
    op.create_table(
        snapshot_table,
        sa.Column("snapshot_id", sa.String(length=128), nullable=False),
        # Mutable deployment source identity is retained as exact historical
        # evidence. It deliberately has no foreign key to the current profile.
        sa.Column("transport_profile_id", sa.String(length=128), nullable=False),
        sa.Column("transport_profile_revision", sa.String(length=64), nullable=False),
        sa.Column("source_profile_digest", sa.String(length=64), nullable=False),
        sa.Column("deployment_release_id", sa.String(length=128), nullable=False),
        sa.Column("deployment_profile", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("transport_resource_id", sa.String(length=128), nullable=False),
        sa.Column("transport_resource_digest", sa.String(length=64), nullable=False),
        sa.Column("transport_implementation_id", sa.String(length=128), nullable=False),
        sa.Column("transport_implementation_version", sa.String(length=64), nullable=False),
        sa.Column("adapter_contract_id", sa.String(length=128), nullable=False),
        sa.Column("adapter_contract_version", sa.String(length=64), nullable=False),
        sa.Column("adapter_contract_digest", sa.String(length=64), nullable=False),
        sa.Column("supported_event_contracts", postgresql.JSONB(), nullable=False),
        sa.Column("supported_classifications", postgresql.JSONB(), nullable=False),
        sa.Column("supported_representations", postgresql.JSONB(), nullable=False),
        sa.Column("supported_encodings", postgresql.JSONB(), nullable=False),
        sa.Column("supported_delivery_semantics", postgresql.JSONB(), nullable=False),
        sa.Column("durable_delivery_supported", sa.Boolean(), nullable=False),
        sa.Column("supported_ordering_key_kinds", postgresql.JSONB(), nullable=False),
        sa.Column("supported_retention_classes", postgresql.JSONB(), nullable=False),
        sa.Column("maximum_message_byte_count", sa.Integer(), nullable=False),
        sa.Column("transport_encryption_required", sa.Boolean(), nullable=False),
        sa.Column("restricted_network_supported", sa.Boolean(), nullable=False),
        sa.Column("snapshotter_subject_id", sa.String(length=240), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("route_selection_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("publication_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("delivery_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("dispatch_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("execution_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "maximum_message_byte_count >= 1",
            name="ck_event_transport_profile_snapshot_max_bytes",
        ),
        sa.CheckConstraint(
            "state = 'snapshotted'",
            name="ck_event_transport_profile_snapshot_state",
        ),
        sa.CheckConstraint(
            "NOT route_selection_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted",
            name="ck_event_transport_profile_snapshot_zero_auth",
        ),
        sa.PrimaryKeyConstraint("snapshot_id"),
        sa.UniqueConstraint(
            "transport_profile_id",
            "transport_profile_revision",
            name="uq_event_transport_profile_snapshot_revision",
        ),
        sa.UniqueConstraint(
            "source_profile_digest",
            name="uq_event_transport_profile_snapshot_source_digest",
        ),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_event_transport_profile_snapshot_digest",
        ),
    )
    snapshot_indexes = {
        "transport_profile_id": "profile",
        "source_profile_digest": "source_digest",
        "deployment_release_id": "release",
        "deployment_profile": "deployment_profile",
        "organization_id": "org",
        "environment_id": "environment",
        "site_id": "site",
        "transport_resource_id": "resource",
        "transport_resource_digest": "resource_digest",
        "transport_implementation_id": "implementation",
        "adapter_contract_id": "adapter",
        "adapter_contract_digest": "adapter_digest",
        "snapshotter_subject_id": "snapshotter",
        "state": "state",
    }
    for column, suffix in snapshot_indexes.items():
        op.create_index(f"ix_event_transport_profile_snapshot_{suffix}", snapshot_table, [column])

    claim_table = "event_transport_profile_snapshot_claims"
    op.create_table(
        claim_table,
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("result_digest", sa.String(length=64), nullable=False),
        sa.Column("snapshot_id", sa.String(length=128), nullable=False),
        # The claim repeats the exact source identity without linking to a
        # replaceable deployment configuration row.
        sa.Column("transport_profile_id", sa.String(length=128), nullable=False),
        sa.Column("transport_profile_revision", sa.String(length=64), nullable=False),
        sa.Column("source_profile_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("snapshotter_subject_id", sa.String(length=240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["event_transport_profile_snapshots.snapshot_id"],
            name="fk_event_transport_profile_claim_snapshot",
        ),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_event_transport_profile_claim_scope_idem",
        ),
        sa.UniqueConstraint(
            "snapshot_id",
            name="uq_event_transport_profile_claim_snapshot",
        ),
        sa.UniqueConstraint(
            "transport_profile_id",
            "transport_profile_revision",
            name="uq_event_transport_profile_claim_revision",
        ),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_event_transport_profile_claim_digest",
        ),
    )
    claim_indexes = {
        "idempotency_scope_id": "scope",
        "snapshot_id": "snapshot",
        "transport_profile_id": "profile",
        "source_profile_digest": "source_digest",
        "organization_id": "org",
        "environment_id": "environment",
        "site_id": "site",
        "snapshotter_subject_id": "snapshotter",
    }
    for column, suffix in claim_indexes.items():
        op.create_index(f"ix_event_transport_profile_claim_{suffix}", claim_table, [column])


def downgrade() -> None:
    claim_table = "event_transport_profile_snapshot_claims"
    for suffix in reversed(
        (
            "scope",
            "snapshot",
            "profile",
            "source_digest",
            "org",
            "environment",
            "site",
            "snapshotter",
        )
    ):
        op.drop_index(f"ix_event_transport_profile_claim_{suffix}", table_name=claim_table)
    op.drop_table(claim_table)

    snapshot_table = "event_transport_profile_snapshots"
    for suffix in reversed(
        (
            "profile",
            "source_digest",
            "release",
            "deployment_profile",
            "org",
            "environment",
            "site",
            "resource",
            "resource_digest",
            "implementation",
            "adapter",
            "adapter_digest",
            "snapshotter",
            "state",
        )
    ):
        op.drop_index(f"ix_event_transport_profile_snapshot_{suffix}", table_name=snapshot_table)
    op.drop_table(snapshot_table)
