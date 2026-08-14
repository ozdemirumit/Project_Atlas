"""Add authoritative route heads and immutable freshness admissions.

Revision ID: 20260814_0123
Revises: 20260814_0122
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0123"
down_revision: str | None = "20260814_0122"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _head_columns(*, history: bool = False) -> list[sa.Column[object]]:
    columns: list[sa.Column[object]] = []
    if history:
        columns.append(sa.Column("history_id", sa.String(length=192), nullable=False))
    columns.extend(
        (
            sa.Column("head_id", sa.String(length=128), nullable=False),
            sa.Column("generation", sa.BigInteger(), nullable=False),
            sa.Column("route_set_id", sa.String(length=128), nullable=False),
            sa.Column("route_set_revision", sa.String(length=64), nullable=False),
            sa.Column("selection_epoch_id", sa.String(length=128), nullable=False),
            sa.Column("selection_epoch_revision", sa.String(length=64), nullable=False),
            sa.Column("selected_route_id", sa.String(length=128), nullable=False),
            sa.Column("selected_route_revision", sa.String(length=64), nullable=False),
            sa.Column("selected_route_digest", sa.String(length=64), nullable=False),
            sa.Column("fencing_token_digest", sa.String(length=64), nullable=False),
            sa.Column("selection_active", sa.Boolean(), nullable=False),
            sa.Column("selection_eligible", sa.Boolean(), nullable=False),
            sa.Column("selection_suspended", sa.Boolean(), nullable=False),
            sa.Column("selection_withdrawn", sa.Boolean(), nullable=False),
            sa.Column("selection_superseded", sa.Boolean(), nullable=False),
            sa.Column("organization_id", sa.String(length=128), nullable=False),
            sa.Column("environment_id", sa.String(length=128), nullable=False),
            sa.Column("site_id", sa.String(length=128), nullable=False),
            sa.Column("current", sa.Boolean(), nullable=False),
            sa.Column("canonical_digest", sa.String(length=64), nullable=False),
            sa.Column("payload", postgresql.JSONB(), nullable=False),
        )
    )
    return columns


def upgrade() -> None:
    head_table = "deployment_event_transport_route_selection_heads"
    history_table = "deployment_event_transport_route_selection_head_history"
    admission_table = "workflow_event_physical_transport_route_freshness_admissions"
    claim_table = "workflow_event_route_freshness_admission_claims"

    op.create_table(
        head_table,
        *_head_columns(),
        sa.CheckConstraint("generation > 0", name="ck_deploy_route_head_generation"),
        sa.CheckConstraint("current", name="ck_deploy_route_head_current"),
        sa.PrimaryKeyConstraint("head_id"),
        sa.UniqueConstraint(
            "organization_id",
            "environment_id",
            "site_id",
            "route_set_id",
            name="uq_deploy_route_head_scope_set",
        ),
    )
    op.create_table(
        history_table,
        *_head_columns(history=True),
        sa.CheckConstraint("generation > 0", name="ck_deploy_route_head_hist_generation"),
        sa.CheckConstraint("current", name="ck_deploy_route_head_hist_current"),
        sa.PrimaryKeyConstraint("history_id"),
        sa.UniqueConstraint(
            "organization_id",
            "environment_id",
            "site_id",
            "route_set_id",
            "generation",
            name="uq_deploy_route_head_history_generation",
        ),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_deploy_route_head_history_digest",
        ),
    )
    for table, prefix in (
        (head_table, "ix_deploy_route_head"),
        (history_table, "ix_route_head_hist"),
    ):
        for column, suffix in (
            ("route_set_id", "route_set"),
            ("selection_epoch_id", "epoch"),
            ("selected_route_id", "route"),
            ("selected_route_digest", "route_digest"),
            ("fencing_token_digest", "fence"),
            ("organization_id", "org"),
            ("environment_id", "environment"),
            ("site_id", "site"),
            ("canonical_digest", "digest"),
        ):
            op.create_index(f"{prefix}_{suffix}", table, [column])
    op.create_index("ix_route_head_hist_head", history_table, ["head_id"])

    op.create_table(
        admission_table,
        sa.Column("freshness_admission_id", sa.String(length=128), nullable=False),
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
        sa.Column("admitter_subject_id", sa.String(length=240), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.CheckConstraint("state = 'admitted_current'", name="ck_wf_route_fresh_admission_state"),
        sa.CheckConstraint(
            "selection_active AND selection_eligible "
            "AND NOT selection_suspended AND NOT selection_withdrawn "
            "AND NOT selection_superseded",
            name="ck_wf_route_fresh_admission_selection",
        ),
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
            name="ck_wf_route_fresh_admission_zero_auth",
        ),
        sa.CheckConstraint(
            "current_selection_head_generation > 0",
            name="ck_wf_route_fresh_admission_generation",
        ),
        sa.CheckConstraint(
            "valid_until > evaluated_at",
            name="ck_wf_route_fresh_admission_window",
        ),
        sa.ForeignKeyConstraint(
            ["physical_transport_route_binding_id"],
            ["workflow_event_physical_transport_route_bindings.binding_id"],
            name="fk_wf_route_fresh_admission_binding",
        ),
        sa.ForeignKeyConstraint(
            ["transport_route_snapshot_id"],
            ["event_transport_route_snapshots.snapshot_id"],
            name="fk_wf_route_fresh_admission_snapshot",
        ),
        sa.PrimaryKeyConstraint("freshness_admission_id"),
        sa.UniqueConstraint(
            "physical_transport_route_binding_id",
            name="uq_wf_route_fresh_admission_binding",
        ),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_route_fresh_admission_digest"),
    )
    admission_indexes = {
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
        "admitter_subject_id": "admitter",
        "state": "state",
    }
    for column, suffix in admission_indexes.items():
        op.create_index(f"ix_wf_route_fresh_admission_{suffix}", admission_table, [column])

    op.create_table(
        claim_table,
        sa.Column("claim_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("result_digest", sa.String(length=64), nullable=False),
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
        sa.Column("admitter_subject_id", sa.String(length=240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.ForeignKeyConstraint(
            ["freshness_admission_id"],
            [f"{admission_table}.freshness_admission_id"],
            name="fk_wf_route_fresh_claim_admission",
        ),
        sa.ForeignKeyConstraint(
            ["physical_transport_route_binding_id"],
            ["workflow_event_physical_transport_route_bindings.binding_id"],
            name="fk_wf_route_fresh_claim_binding",
        ),
        sa.ForeignKeyConstraint(
            ["transport_route_snapshot_id"],
            ["event_transport_route_snapshots.snapshot_id"],
            name="fk_wf_route_fresh_claim_snapshot",
        ),
        sa.PrimaryKeyConstraint("claim_id"),
        sa.UniqueConstraint(
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_wf_route_fresh_claim_scope_idem",
        ),
        sa.UniqueConstraint(
            "freshness_admission_id",
            name="uq_wf_route_fresh_claim_admission",
        ),
        sa.UniqueConstraint("canonical_digest", name="uq_wf_route_fresh_claim_digest"),
    )
    claim_indexes = {
        "idempotency_scope_id": "scope",
        "freshness_admission_id": "admission",
        "physical_transport_route_binding_id": "binding",
        "transport_route_snapshot_id": "snapshot",
        "current_selection_head_id": "head",
        "current_selection_head_fencing_token_digest": "fence",
        "policy_digest": "policy_digest",
        "organization_id": "org",
        "environment_id": "environment",
        "site_id": "site",
        "admitter_subject_id": "admitter",
    }
    for column, suffix in claim_indexes.items():
        op.create_index(f"ix_wf_route_fresh_claim_{suffix}", claim_table, [column])

    op.execute(
        """
        CREATE FUNCTION enforce_deployment_route_head_sync()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF current_setting('atlas.route_head_sync', true) IS DISTINCT FROM 'enabled' THEN
                RAISE EXCEPTION 'route selection head synchronization required'
                    USING ERRCODE = '55000';
            END IF;
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'route selection heads cannot be deleted'
                    USING ERRCODE = '55000';
            END IF;
            IF TG_OP = 'UPDATE' THEN
                IF NEW.organization_id IS DISTINCT FROM OLD.organization_id
                   OR NEW.environment_id IS DISTINCT FROM OLD.environment_id
                   OR NEW.site_id IS DISTINCT FROM OLD.site_id
                   OR NEW.route_set_id IS DISTINCT FROM OLD.route_set_id THEN
                    RAISE EXCEPTION 'route selection head identity cannot change'
                        USING ERRCODE = '55000';
                END IF;
                IF NEW.generation <= OLD.generation THEN
                    RAISE EXCEPTION 'route selection head generation must increase'
                        USING ERRCODE = '55000';
                END IF;
                IF NEW.fencing_token_digest = OLD.fencing_token_digest THEN
                    RAISE EXCEPTION 'route selection head fencing token must change'
                        USING ERRCODE = '55000';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER trg_deployment_route_head_sync
        BEFORE INSERT OR UPDATE OR DELETE ON {head_table}
        FOR EACH ROW EXECUTE FUNCTION enforce_deployment_route_head_sync()
        """
    )
    op.execute(
        f"""
        CREATE FUNCTION record_deployment_route_head_history()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            INSERT INTO {history_table} (
                history_id, head_id, generation, route_set_id, route_set_revision,
                selection_epoch_id, selection_epoch_revision, selected_route_id,
                selected_route_revision, selected_route_digest, fencing_token_digest,
                selection_active, selection_eligible, selection_suspended,
                selection_withdrawn, selection_superseded, organization_id,
                environment_id, site_id, current, canonical_digest, payload
            ) VALUES (
                NEW.head_id || ':' || NEW.generation::text,
                NEW.head_id, NEW.generation, NEW.route_set_id, NEW.route_set_revision,
                NEW.selection_epoch_id, NEW.selection_epoch_revision, NEW.selected_route_id,
                NEW.selected_route_revision, NEW.selected_route_digest, NEW.fencing_token_digest,
                NEW.selection_active, NEW.selection_eligible, NEW.selection_suspended,
                NEW.selection_withdrawn, NEW.selection_superseded, NEW.organization_id,
                NEW.environment_id, NEW.site_id, NEW.current, NEW.canonical_digest, NEW.payload
            );
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER trg_deployment_route_head_history
        AFTER INSERT OR UPDATE ON {head_table}
        FOR EACH ROW EXECUTE FUNCTION record_deployment_route_head_history()
        """
    )
    op.execute(
        """
        CREATE FUNCTION reject_route_freshness_evidence_mutation()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'route freshness evidence is append-only'
                USING ERRCODE = '55000';
        END;
        $$
        """
    )
    for table, trigger in (
        (history_table, "trg_route_head_history_append_only"),
        (admission_table, "trg_route_fresh_admission_append_only"),
        (claim_table, "trg_route_fresh_claim_append_only"),
    ):
        op.execute(
            f"""
            CREATE TRIGGER {trigger}
            BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION reject_route_freshness_evidence_mutation()
            """
        )


def downgrade() -> None:
    head_table = "deployment_event_transport_route_selection_heads"
    history_table = "deployment_event_transport_route_selection_head_history"
    admission_table = "workflow_event_physical_transport_route_freshness_admissions"
    claim_table = "workflow_event_route_freshness_admission_claims"

    for table, trigger in (
        (claim_table, "trg_route_fresh_claim_append_only"),
        (admission_table, "trg_route_fresh_admission_append_only"),
        (history_table, "trg_route_head_history_append_only"),
    ):
        op.execute(f"DROP TRIGGER IF EXISTS {trigger} ON {table}")
    op.execute("DROP FUNCTION IF EXISTS reject_route_freshness_evidence_mutation()")
    op.execute(f"DROP TRIGGER IF EXISTS trg_deployment_route_head_history ON {head_table}")
    op.execute("DROP FUNCTION IF EXISTS record_deployment_route_head_history()")
    op.execute(f"DROP TRIGGER IF EXISTS trg_deployment_route_head_sync ON {head_table}")
    op.execute("DROP FUNCTION IF EXISTS enforce_deployment_route_head_sync()")

    op.drop_table(claim_table)
    op.drop_table(admission_table)
    op.drop_table(history_table)
    op.drop_table(head_table)
