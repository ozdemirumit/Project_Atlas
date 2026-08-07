"""Add immutable connector package schema semantics validations.

Revision ID: 20260805_0030
Revises: 20260805_0029
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260805_0030"
down_revision: str | None = "20260805_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = "connector_package_schema_semantics_validations"
    op.create_table(
        table,
        sa.Column("validation_id", sa.String(length=128), nullable=False),
        sa.Column("schema_version", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("lifecycle", sa.String(length=32), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("source_content_policy_scan_id", sa.String(length=128), nullable=False),
        sa.Column("source_content_policy_scan_digest", sa.String(length=64), nullable=False),
        sa.Column("source_inventory_id", sa.String(length=128), nullable=False),
        sa.Column("source_inventory_digest", sa.String(length=64), nullable=False),
        sa.Column("source_validation_id", sa.String(length=128), nullable=False),
        sa.Column("source_validation_digest", sa.String(length=64), nullable=False),
        sa.Column("source_acquisition_id", sa.String(length=128), nullable=False),
        sa.Column("source_acquisition_digest", sa.String(length=64), nullable=False),
        sa.Column("source_handoff_id", sa.String(length=128), nullable=False),
        sa.Column("source_project_id", sa.String(length=128), nullable=False),
        sa.Column("source_acquired_by", sa.String(length=128), nullable=False),
        sa.Column("source_manifest_validated_by", sa.String(length=128), nullable=False),
        sa.Column("source_inventoried_by", sa.String(length=128), nullable=False),
        sa.Column("source_content_scanned_by", sa.String(length=128), nullable=False),
        sa.Column("source_custodied_by", sa.String(length=128), nullable=False),
        sa.Column("source_domain_reviewed_by", sa.String(length=128), nullable=False),
        sa.Column("source_security_reviewed_by", sa.String(length=128), nullable=False),
        sa.Column("source_lab_operated_by", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("validated_by", sa.String(length=128), nullable=False),
        sa.Column("validation_profile", sa.String(length=128), nullable=False),
        sa.Column("validator_version", sa.String(length=128), nullable=False),
        sa.Column("package_digest", sa.String(length=64), nullable=False),
        sa.Column("package_size_bytes", sa.Integer(), nullable=False),
        sa.Column("inventory_digest", sa.String(length=64), nullable=False),
        sa.Column("content_scan_digest", sa.String(length=64), nullable=False),
        sa.Column("schemas", postgresql.JSONB(), nullable=False),
        sa.Column("schema_set_digest", sa.String(length=64), nullable=False),
        sa.Column("findings", postgresql.JSONB(), nullable=False),
        sa.Column("finding_set_digest", sa.String(length=64), nullable=False),
        sa.Column("semantic_validation_digest", sa.String(length=64), nullable=False),
        sa.Column("checks", postgresql.JSONB(), nullable=False),
        sa.Column("limitations", postgresql.JSONB(), nullable=False),
        sa.Column("promotion_blocked", sa.Boolean(), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "version = 1", name="ck_connector_package_schema_semantics_validations_version"
        ),
        sa.PrimaryKeyConstraint("validation_id"),
        sa.UniqueConstraint(
            "source_content_policy_scan_id",
            name="uq_connector_package_schema_semantics_validations_source_scan",
        ),
        sa.UniqueConstraint(
            "validated_by",
            "idempotency_key",
            name="uq_pkg_schema_sem_actor_idem",
        ),
    )
    for column in (
        "source_content_policy_scan_id",
        "source_inventory_id",
        "source_validation_id",
        "source_acquisition_id",
        "source_handoff_id",
        "source_project_id",
        "validated_by",
    ):
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)


def downgrade() -> None:
    table = "connector_package_schema_semantics_validations"
    for column in reversed(
        (
            "source_content_policy_scan_id",
            "source_inventory_id",
            "source_validation_id",
            "source_acquisition_id",
            "source_handoff_id",
            "source_project_id",
            "validated_by",
        )
    ):
        op.drop_index(op.f(f"ix_{table}_{column}"), table_name=table)
    op.drop_table(table)
