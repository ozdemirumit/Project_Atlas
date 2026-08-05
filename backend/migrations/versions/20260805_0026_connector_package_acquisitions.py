"""Add immutable connector package acquisitions.

Revision ID: 20260805_0026
Revises: 20260805_0025
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260805_0026"
down_revision: str | None = "20260805_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connector_package_acquisitions",
        sa.Column("acquisition_id", sa.String(length=128), nullable=False),
        sa.Column("schema_version", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("source_handoff_id", sa.String(length=128), nullable=False),
        sa.Column("source_handoff_digest", sa.String(length=64), nullable=False),
        sa.Column("source_project_id", sa.String(length=128), nullable=False),
        sa.Column("source_custodied_by", sa.String(length=128), nullable=False),
        sa.Column("source_domain_reviewed_by", sa.String(length=128), nullable=False),
        sa.Column("source_security_reviewed_by", sa.String(length=128), nullable=False),
        sa.Column("source_lab_operated_by", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("acquired_by", sa.String(length=128), nullable=False),
        sa.Column("acquisition_profile", sa.String(length=128), nullable=False),
        sa.Column("archive_contract_version", sa.String(length=128), nullable=False),
        sa.Column("package_filename", sa.String(length=132), nullable=False),
        sa.Column("package_digest", sa.String(length=64), nullable=False),
        sa.Column("package_size_bytes", sa.Integer(), nullable=False),
        sa.Column("publisher_identity", sa.String(length=128), nullable=False),
        sa.Column("signature_state", sa.String(length=32), nullable=False),
        sa.Column("attestation_state", sa.String(length=32), nullable=False),
        sa.Column("capabilities", postgresql.JSONB(), nullable=False),
        sa.Column("limitations", postgresql.JSONB(), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version = 1", name="ck_connector_package_acquisitions_version"),
        sa.PrimaryKeyConstraint("acquisition_id"),
        sa.UniqueConstraint(
            "source_handoff_id", name="uq_connector_package_acquisitions_source_handoff"
        ),
        sa.UniqueConstraint(
            "package_digest", name="uq_connector_package_acquisitions_package_digest"
        ),
        sa.UniqueConstraint(
            "acquired_by",
            "idempotency_key",
            name="uq_connector_package_acquisitions_actor_idempotency",
        ),
    )
    for column in ("source_handoff_id", "source_project_id", "acquired_by"):
        op.create_index(
            op.f(f"ix_connector_package_acquisitions_{column}"),
            "connector_package_acquisitions",
            [column],
            unique=False,
        )


def downgrade() -> None:
    for column in reversed(("source_handoff_id", "source_project_id", "acquired_by")):
        op.drop_index(
            op.f(f"ix_connector_package_acquisitions_{column}"),
            table_name="connector_package_acquisitions",
        )
    op.drop_table("connector_package_acquisitions")
