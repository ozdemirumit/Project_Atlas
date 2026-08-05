"""Add immutable MCP Builder human domain reviews.

Revision ID: 20260805_0022
Revises: 20260805_0021
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260805_0022"
down_revision: str | None = "20260805_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_builder_domain_reviews",
        sa.Column("review_id", sa.String(length=128), nullable=False),
        sa.Column("schema_version", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("project_version", sa.Integer(), nullable=False),
        sa.Column("project_digest", sa.String(length=64), nullable=False),
        sa.Column("source_digest", sa.String(length=64), nullable=False),
        sa.Column("checkpoint_id", sa.String(length=128), nullable=False),
        sa.Column("checkpoint_digest", sa.String(length=64), nullable=False),
        sa.Column("generation_id", sa.String(length=128), nullable=False),
        sa.Column("generation_digest", sa.String(length=64), nullable=False),
        sa.Column("artifact_digest", sa.String(length=64), nullable=False),
        sa.Column("validation_id", sa.String(length=128), nullable=False),
        sa.Column("validation_digest", sa.String(length=64), nullable=False),
        sa.Column("validation_profile", sa.String(length=128), nullable=False),
        sa.Column("validator_version", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("reviewed_by", sa.String(length=128), nullable=False),
        sa.Column("review_profile", sa.String(length=128), nullable=False),
        sa.Column("reviewer_contract_version", sa.String(length=128), nullable=False),
        sa.Column("capability_decisions", postgresql.JSONB(), nullable=False),
        sa.Column("accepted_count", sa.Integer(), nullable=False),
        sa.Column("needs_evidence_count", sa.Integer(), nullable=False),
        sa.Column("rejected_count", sa.Integer(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("limitations", postgresql.JSONB(), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version = 1", name="ck_mcp_builder_domain_reviews_version"),
        sa.PrimaryKeyConstraint("review_id"),
        sa.UniqueConstraint("project_id", name="uq_mcp_builder_domain_reviews_project"),
        sa.UniqueConstraint("validation_id", name="uq_mcp_builder_domain_reviews_validation"),
        sa.UniqueConstraint(
            "reviewed_by",
            "idempotency_key",
            name="uq_mcp_builder_domain_reviews_reviewer_idempotency",
        ),
    )
    for column in (
        "project_id",
        "checkpoint_id",
        "generation_id",
        "validation_id",
        "reviewed_by",
    ):
        op.create_index(
            op.f(f"ix_mcp_builder_domain_reviews_{column}"),
            "mcp_builder_domain_reviews",
            [column],
            unique=False,
        )


def downgrade() -> None:
    for column in reversed(
        (
            "project_id",
            "checkpoint_id",
            "generation_id",
            "validation_id",
            "reviewed_by",
        )
    ):
        op.drop_index(
            op.f(f"ix_mcp_builder_domain_reviews_{column}"),
            table_name="mcp_builder_domain_reviews",
        )
    op.drop_table("mcp_builder_domain_reviews")
