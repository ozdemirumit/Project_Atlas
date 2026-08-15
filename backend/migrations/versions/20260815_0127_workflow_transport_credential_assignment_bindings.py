"""Add immutable workflow transport credential-assignment bindings.

Revision ID: 20260815_0127
Revises: 20260815_0126
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260815_0127"
down_revision: str | None = "20260815_0126"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    binding_table = "workflow_event_physical_transport_credential_bindings"
    claim_table = "workflow_event_physical_transport_credential_binding_claims"

    op.create_table(
        binding_table,
        sa.Column("binding_id", sa.String(length=128), nullable=False),
        sa.Column("physical_transport_route_binding_id", sa.String(length=128), nullable=False),
        sa.Column("physical_transport_route_binding_digest", sa.String(length=64), nullable=False),
        sa.Column("transport_route_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("transport_route_snapshot_digest", sa.String(length=64), nullable=False),
        sa.Column("credential_assignment_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("credential_assignment_snapshot_digest", sa.String(length=64), nullable=False),
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("policy_version", sa.String(length=64), nullable=False),
        sa.Column("policy_digest", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("binder_subject_id", sa.String(length=240), nullable=False),
        sa.Column("bound_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        *_zero_authority_columns(),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "state = 'bound'",
            name="ck_wf_transport_credential_binding_state",
        ),
        sa.CheckConstraint(
            _zero_authority_check(),
            name="ck_wf_transport_credential_binding_zero_auth",
        ),
        sa.ForeignKeyConstraint(
            ["physical_transport_route_binding_id"],
            ["workflow_event_physical_transport_route_bindings.binding_id"],
            name="fk_wf_transport_credential_binding_route_binding",
        ),
        sa.ForeignKeyConstraint(
            ["transport_route_snapshot_id"],
            ["event_transport_route_snapshots.snapshot_id"],
            name="fk_wf_transport_credential_binding_route_snapshot",
        ),
        sa.ForeignKeyConstraint(
            ["credential_assignment_snapshot_id"],
            ["event_transport_credential_assignment_snapshots.snapshot_id"],
            name="fk_wf_transport_credential_binding_assignment_snapshot",
        ),
        sa.PrimaryKeyConstraint("binding_id"),
        sa.UniqueConstraint(
            "physical_transport_route_binding_id",
            "credential_assignment_snapshot_id",
            name="uq_wf_transport_credential_binding_pair",
        ),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_wf_transport_credential_binding_digest",
        ),
    )
    _create_indexes(
        binding_table,
        "ix_wf_transport_credential_binding",
        {
            "physical_transport_route_binding_id": "route_binding",
            "physical_transport_route_binding_digest": "route_binding_digest",
            "transport_route_snapshot_id": "route_snapshot",
            "transport_route_snapshot_digest": "route_snapshot_digest",
            "credential_assignment_snapshot_id": "assignment_snapshot",
            "credential_assignment_snapshot_digest": "assignment_snapshot_digest",
            "policy_id": "policy_id",
            "policy_digest": "policy",
            "organization_id": "org",
            "environment_id": "environment",
            "site_id": "site",
            "binder_subject_id": "binder",
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
        sa.Column("binding_id", sa.String(length=128), nullable=False),
        sa.Column("physical_transport_route_binding_id", sa.String(length=128), nullable=False),
        sa.Column("transport_route_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("credential_assignment_snapshot_id", sa.String(length=128), nullable=False),
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
            [f"{binding_table}.binding_id"],
            name="fk_wf_transport_credential_claim_binding",
        ),
        sa.ForeignKeyConstraint(
            ["physical_transport_route_binding_id"],
            ["workflow_event_physical_transport_route_bindings.binding_id"],
            name="fk_wf_transport_credential_claim_route_binding",
        ),
        sa.ForeignKeyConstraint(
            ["transport_route_snapshot_id"],
            ["event_transport_route_snapshots.snapshot_id"],
            name="fk_wf_transport_credential_claim_route_snapshot",
        ),
        sa.ForeignKeyConstraint(
            ["credential_assignment_snapshot_id"],
            ["event_transport_credential_assignment_snapshots.snapshot_id"],
            name="fk_wf_transport_credential_claim_assignment_snapshot",
        ),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_transport_credential_claim_scope_idem",
        ),
        sa.UniqueConstraint(
            "binding_id",
            name="uq_wf_transport_credential_claim_binding",
        ),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_wf_transport_credential_claim_digest",
        ),
    )
    _create_indexes(
        claim_table,
        "ix_wf_transport_credential_claim",
        {
            "idempotency_scope_id": "scope",
            "binding_id": "binding",
            "physical_transport_route_binding_id": "route_binding",
            "transport_route_snapshot_id": "route_snapshot",
            "credential_assignment_snapshot_id": "assignment_snapshot",
            "policy_digest": "policy",
            "organization_id": "org",
            "environment_id": "environment",
            "site_id": "site",
            "binder_subject_id": "binder",
        },
    )

    op.execute(
        """
        CREATE FUNCTION reject_wf_transport_credential_binding_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'workflow transport credential bindings are append-only'
                USING ERRCODE = '55000';
        END;
        $$
        """
    )
    triggers = {
        binding_table: "trg_wf_transport_credential_bindings_append_only",
        claim_table: "trg_wf_transport_credential_binding_claims_append_only",
    }
    for table_name, trigger_name in triggers.items():
        op.execute(
            f"""
            CREATE TRIGGER {trigger_name}
            BEFORE UPDATE OR DELETE ON {table_name}
            FOR EACH ROW
            EXECUTE FUNCTION reject_wf_transport_credential_binding_mutation()
            """
        )


def downgrade() -> None:
    binding_table = "workflow_event_physical_transport_credential_bindings"
    claim_table = "workflow_event_physical_transport_credential_binding_claims"
    triggers = {
        binding_table: "trg_wf_transport_credential_bindings_append_only",
        claim_table: "trg_wf_transport_credential_binding_claims_append_only",
    }
    for table_name, trigger_name in triggers.items():
        op.execute(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name}")
    op.execute("DROP FUNCTION IF EXISTS reject_wf_transport_credential_binding_mutation()")

    for suffix in reversed(
        (
            "scope",
            "binding",
            "route_binding",
            "route_snapshot",
            "assignment_snapshot",
            "policy",
            "org",
            "environment",
            "site",
            "binder",
        )
    ):
        op.drop_index(f"ix_wf_transport_credential_claim_{suffix}", table_name=claim_table)
    op.drop_table(claim_table)

    for suffix in reversed(
        (
            "route_binding",
            "route_binding_digest",
            "route_snapshot",
            "route_snapshot_digest",
            "assignment_snapshot",
            "assignment_snapshot_digest",
            "policy_id",
            "policy",
            "org",
            "environment",
            "site",
            "binder",
            "state",
        )
    ):
        op.drop_index(f"ix_wf_transport_credential_binding_{suffix}", table_name=binding_table)
    op.drop_table(binding_table)


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
