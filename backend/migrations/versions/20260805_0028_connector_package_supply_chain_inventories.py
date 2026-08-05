"""Add immutable connector package supply-chain inventories.

Revision ID: 20260805_0028
Revises: 20260805_0027
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260805_0028"
down_revision: str | None = "20260805_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connector_package_supply_chain_inventories",
        sa.Column("inventory_id", sa.String(length=128), nullable=False),
        sa.Column("schema_version", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("lifecycle", sa.String(length=32), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("source_validation_id", sa.String(length=128), nullable=False),
        sa.Column("source_validation_digest", sa.String(length=64), nullable=False),
        sa.Column("source_acquisition_id", sa.String(length=128), nullable=False),
        sa.Column("source_acquisition_digest", sa.String(length=64), nullable=False),
        sa.Column("source_handoff_id", sa.String(length=128), nullable=False),
        sa.Column("source_project_id", sa.String(length=128), nullable=False),
        sa.Column("source_acquired_by", sa.String(length=128), nullable=False),
        sa.Column("source_validated_by", sa.String(length=128), nullable=False),
        sa.Column("source_custodied_by", sa.String(length=128), nullable=False),
        sa.Column("source_domain_reviewed_by", sa.String(length=128), nullable=False),
        sa.Column("source_security_reviewed_by", sa.String(length=128), nullable=False),
        sa.Column("source_lab_operated_by", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("inventoried_by", sa.String(length=128), nullable=False),
        sa.Column("inventory_profile", sa.String(length=128), nullable=False),
        sa.Column("inspector_version", sa.String(length=128), nullable=False),
        sa.Column("package_digest", sa.String(length=64), nullable=False),
        sa.Column("package_size_bytes", sa.Integer(), nullable=False),
        sa.Column("files", postgresql.JSONB(), nullable=False),
        sa.Column("dependencies", postgresql.JSONB(), nullable=False),
        sa.Column("inventory_digest", sa.String(length=64), nullable=False),
        sa.Column("dependency_set_digest", sa.String(length=64), nullable=False),
        sa.Column("runtime_dependency_count", sa.Integer(), nullable=False),
        sa.Column("build_dependency_count", sa.Integer(), nullable=False),
        sa.Column("dependency_lock_present", sa.Boolean(), nullable=False),
        sa.Column("checks", postgresql.JSONB(), nullable=False),
        sa.Column("limitations", postgresql.JSONB(), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("inventoried_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "version = 1", name="ck_connector_package_supply_chain_inventories_version"
        ),
        sa.PrimaryKeyConstraint("inventory_id"),
        sa.UniqueConstraint(
            "source_validation_id",
            name="uq_connector_package_supply_chain_inventories_source_validation",
        ),
        sa.UniqueConstraint(
            "inventoried_by",
            "idempotency_key",
            name="uq_connector_package_supply_chain_inventories_actor_idempotency",
        ),
    )
    for column in (
        "source_validation_id",
        "source_acquisition_id",
        "source_handoff_id",
        "source_project_id",
        "inventoried_by",
    ):
        op.create_index(
            op.f(f"ix_connector_package_supply_chain_inventories_{column}"),
            "connector_package_supply_chain_inventories",
            [column],
            unique=False,
        )


def downgrade() -> None:
    for column in reversed(
        (
            "source_validation_id",
            "source_acquisition_id",
            "source_handoff_id",
            "source_project_id",
            "inventoried_by",
        )
    ):
        op.drop_index(
            op.f(f"ix_connector_package_supply_chain_inventories_{column}"),
            table_name="connector_package_supply_chain_inventories",
        )
    op.drop_table("connector_package_supply_chain_inventories")
