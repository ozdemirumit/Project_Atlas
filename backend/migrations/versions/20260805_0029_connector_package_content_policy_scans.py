"""Add immutable connector package content-policy scans.

Revision ID: 20260805_0029
Revises: 20260805_0028
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260805_0029"
down_revision: str | None = "20260805_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connector_package_content_policy_scans",
        sa.Column("scan_id", sa.String(length=128), nullable=False),
        sa.Column("schema_version", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("lifecycle", sa.String(length=32), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("source_inventory_id", sa.String(length=128), nullable=False),
        sa.Column("source_inventory_digest", sa.String(length=64), nullable=False),
        sa.Column("source_validation_id", sa.String(length=128), nullable=False),
        sa.Column("source_validation_digest", sa.String(length=64), nullable=False),
        sa.Column("source_acquisition_id", sa.String(length=128), nullable=False),
        sa.Column("source_acquisition_digest", sa.String(length=64), nullable=False),
        sa.Column("source_handoff_id", sa.String(length=128), nullable=False),
        sa.Column("source_project_id", sa.String(length=128), nullable=False),
        sa.Column("source_acquired_by", sa.String(length=128), nullable=False),
        sa.Column("source_validated_by", sa.String(length=128), nullable=False),
        sa.Column("source_inventoried_by", sa.String(length=128), nullable=False),
        sa.Column("source_custodied_by", sa.String(length=128), nullable=False),
        sa.Column("source_domain_reviewed_by", sa.String(length=128), nullable=False),
        sa.Column("source_security_reviewed_by", sa.String(length=128), nullable=False),
        sa.Column("source_lab_operated_by", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("scanned_by", sa.String(length=128), nullable=False),
        sa.Column("scan_profile", sa.String(length=128), nullable=False),
        sa.Column("scanner_version", sa.String(length=128), nullable=False),
        sa.Column("package_digest", sa.String(length=64), nullable=False),
        sa.Column("package_size_bytes", sa.Integer(), nullable=False),
        sa.Column("inventory_digest", sa.String(length=64), nullable=False),
        sa.Column("dependency_set_digest", sa.String(length=64), nullable=False),
        sa.Column("scanned_file_count", sa.Integer(), nullable=False),
        sa.Column("findings", postgresql.JSONB(), nullable=False),
        sa.Column("finding_set_digest", sa.String(length=64), nullable=False),
        sa.Column("content_scan_digest", sa.String(length=64), nullable=False),
        sa.Column("checks", postgresql.JSONB(), nullable=False),
        sa.Column("limitations", postgresql.JSONB(), nullable=False),
        sa.Column("promotion_blocked", sa.Boolean(), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version = 1", name="ck_connector_package_content_policy_scans_version"),
        sa.PrimaryKeyConstraint("scan_id"),
        sa.UniqueConstraint(
            "source_inventory_id",
            name="uq_connector_package_content_policy_scans_source_inventory",
        ),
        sa.UniqueConstraint(
            "scanned_by",
            "idempotency_key",
            name="uq_connector_package_content_policy_scans_actor_idempotency",
        ),
    )
    for column in (
        "source_inventory_id",
        "source_validation_id",
        "source_acquisition_id",
        "source_handoff_id",
        "source_project_id",
        "scanned_by",
    ):
        op.create_index(
            op.f(f"ix_connector_package_content_policy_scans_{column}"),
            "connector_package_content_policy_scans",
            [column],
            unique=False,
        )


def downgrade() -> None:
    for column in reversed(
        (
            "source_inventory_id",
            "source_validation_id",
            "source_acquisition_id",
            "source_handoff_id",
            "source_project_id",
            "scanned_by",
        )
    ):
        op.drop_index(
            op.f(f"ix_connector_package_content_policy_scans_{column}"),
            table_name="connector_package_content_policy_scans",
        )
    op.drop_table("connector_package_content_policy_scans")
