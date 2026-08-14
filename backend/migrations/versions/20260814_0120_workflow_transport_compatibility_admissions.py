"""Add immutable workflow transport compatibility admissions.

Revision ID: 20260814_0120
Revises: 20260814_0119
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0120"
down_revision: str | None = "20260814_0119"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    admission_table = "workflow_event_transport_compatibility_admissions"
    op.create_table(
        admission_table,
        sa.Column("compatibility_admission_id", sa.String(length=128), nullable=False),
        sa.Column("logical_channel_binding_id", sa.String(length=128), nullable=False),
        sa.Column("logical_channel_binding_digest", sa.String(length=64), nullable=False),
        sa.Column("transport_profile_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("transport_profile_snapshot_digest", sa.String(length=64), nullable=False),
        sa.Column("transport_profile_id", sa.String(length=128), nullable=False),
        sa.Column("transport_profile_revision", sa.String(length=64), nullable=False),
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("policy_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("event_version", sa.String(length=32), nullable=False),
        sa.Column("schema_uri", sa.String(length=512), nullable=False),
        sa.Column("data_classification", sa.String(length=64), nullable=False),
        sa.Column("representation_name", sa.String(length=64), nullable=False),
        sa.Column("encoding", sa.String(length=32), nullable=False),
        sa.Column("delivery_semantics", sa.String(length=64), nullable=False),
        sa.Column("durability_required", sa.Boolean(), nullable=False),
        sa.Column("ordering_key_kind", sa.String(length=64), nullable=False),
        sa.Column("retention_class", sa.String(length=64), nullable=False),
        sa.Column("logical_maximum_byte_count", sa.Integer(), nullable=False),
        sa.Column("artifact_byte_count", sa.Integer(), nullable=False),
        sa.Column("profile_maximum_message_byte_count", sa.Integer(), nullable=False),
        sa.Column("admitter_subject_id", sa.String(length=240), nullable=False),
        sa.Column("admitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("route_selection_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("route_binding_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("credential_access_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("publication_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("delivery_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("dispatch_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("execution_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "state = 'admitted'",
            name="ck_wf_transport_compat_admission_state",
        ),
        sa.CheckConstraint(
            "logical_maximum_byte_count >= 1 "
            "AND artifact_byte_count >= 1 "
            "AND artifact_byte_count <= logical_maximum_byte_count "
            "AND logical_maximum_byte_count <= profile_maximum_message_byte_count",
            name="ck_wf_transport_compat_admission_bytes",
        ),
        sa.CheckConstraint(
            "NOT route_selection_authority_granted "
            "AND NOT route_binding_authority_granted "
            "AND NOT credential_access_authority_granted "
            "AND NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted",
            name="ck_wf_transport_compat_admission_zero_auth",
        ),
        sa.ForeignKeyConstraint(
            ["logical_channel_binding_id"],
            ["workflow_event_channel_bindings.binding_id"],
            name="fk_wf_transport_compat_admission_binding",
        ),
        sa.ForeignKeyConstraint(
            ["transport_profile_snapshot_id"],
            ["event_transport_profile_snapshots.snapshot_id"],
            name="fk_wf_transport_compat_admission_profile",
        ),
        sa.PrimaryKeyConstraint("compatibility_admission_id"),
        sa.UniqueConstraint(
            "logical_channel_binding_id",
            "transport_profile_snapshot_id",
            "policy_digest",
            name="uq_wf_transport_compat_binding_profile_policy",
        ),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_wf_transport_compat_admission_digest",
        ),
    )
    admission_indexes = {
        "logical_channel_binding_id": "binding",
        "logical_channel_binding_digest": "binding_digest",
        "transport_profile_snapshot_id": "profile",
        "transport_profile_snapshot_digest": "profile_digest",
        "transport_profile_id": "profile_identity",
        "policy_id": "policy",
        "policy_digest": "policy_digest",
        "organization_id": "org",
        "environment_id": "environment",
        "site_id": "site",
        "admitter_subject_id": "admitter",
        "state": "state",
    }
    for column, suffix in admission_indexes.items():
        op.create_index(f"ix_wf_transport_compat_admission_{suffix}", admission_table, [column])

    claim_table = "workflow_event_transport_compatibility_admission_claims"
    op.create_table(
        claim_table,
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("result_digest", sa.String(length=64), nullable=False),
        sa.Column("compatibility_admission_id", sa.String(length=128), nullable=False),
        sa.Column("logical_channel_binding_id", sa.String(length=128), nullable=False),
        sa.Column("transport_profile_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("policy_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("admitter_subject_id", sa.String(length=240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["compatibility_admission_id"],
            ["workflow_event_transport_compatibility_admissions.compatibility_admission_id"],
            name="fk_wf_transport_compat_claim_admission",
        ),
        sa.ForeignKeyConstraint(
            ["logical_channel_binding_id"],
            ["workflow_event_channel_bindings.binding_id"],
            name="fk_wf_transport_compat_claim_binding",
        ),
        sa.ForeignKeyConstraint(
            ["transport_profile_snapshot_id"],
            ["event_transport_profile_snapshots.snapshot_id"],
            name="fk_wf_transport_compat_claim_profile",
        ),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_transport_compat_claim_scope_idem",
        ),
        sa.UniqueConstraint(
            "compatibility_admission_id",
            name="uq_wf_transport_compat_claim_admission",
        ),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_wf_transport_compat_claim_digest",
        ),
    )
    claim_indexes = {
        "idempotency_scope_id": "scope",
        "compatibility_admission_id": "admission",
        "logical_channel_binding_id": "binding",
        "transport_profile_snapshot_id": "profile",
        "policy_digest": "policy_digest",
        "organization_id": "org",
        "environment_id": "environment",
        "site_id": "site",
        "admitter_subject_id": "admitter",
    }
    for column, suffix in claim_indexes.items():
        op.create_index(f"ix_wf_transport_compat_claim_{suffix}", claim_table, [column])


def downgrade() -> None:
    claim_table = "workflow_event_transport_compatibility_admission_claims"
    for suffix in reversed(
        (
            "scope",
            "admission",
            "binding",
            "profile",
            "policy_digest",
            "org",
            "environment",
            "site",
            "admitter",
        )
    ):
        op.drop_index(f"ix_wf_transport_compat_claim_{suffix}", table_name=claim_table)
    op.drop_table(claim_table)

    admission_table = "workflow_event_transport_compatibility_admissions"
    for suffix in reversed(
        (
            "binding",
            "binding_digest",
            "profile",
            "profile_digest",
            "profile_identity",
            "policy",
            "policy_digest",
            "org",
            "environment",
            "site",
            "admitter",
            "state",
        )
    ):
        op.drop_index(f"ix_wf_transport_compat_admission_{suffix}", table_name=admission_table)
    op.drop_table(admission_table)
