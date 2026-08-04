"""Add governed logical backup and restore-validation records.

Revision ID: 20260804_0013
Revises: 20260804_0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260804_0013"
down_revision: str | None = "20260804_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platform_logical_backups",
        sa.Column("backup_id", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("source_run_id", sa.String(length=128), nullable=False),
        sa.Column("source_run_version", sa.Integer(), nullable=False),
        sa.Column("preview_digest", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("archive_sha256", sa.String(length=64), nullable=False),
        sa.Column("archive_size_bytes", sa.Integer(), nullable=False),
        sa.Column("archive_name", sa.String(length=180), nullable=False),
        sa.Column("entry_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_run_version > 0", name="ck_platform_logical_backups_source_version"
        ),
        sa.CheckConstraint(
            "archive_size_bytes > 0", name="ck_platform_logical_backups_archive_size"
        ),
        sa.PrimaryKeyConstraint("backup_id"),
        sa.UniqueConstraint(
            "actor_id", "idempotency_key", name="uq_platform_logical_backups_actor_idempotency"
        ),
    )
    op.create_table(
        "platform_restore_validations",
        sa.Column("validation_id", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("backup_id", sa.String(length=128), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("archive_sha256", sa.String(length=64), nullable=False),
        sa.Column("validation_digest", sa.String(length=64), nullable=False),
        sa.Column("check_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("entry_count", sa.Integer(), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("entry_count > 0", name="ck_platform_restore_validations_entry_count"),
        sa.PrimaryKeyConstraint("validation_id"),
        sa.UniqueConstraint(
            "actor_id", "idempotency_key", name="uq_platform_restore_validations_actor_idempotency"
        ),
    )


def downgrade() -> None:
    op.drop_table("platform_restore_validations")
    op.drop_table("platform_logical_backups")
