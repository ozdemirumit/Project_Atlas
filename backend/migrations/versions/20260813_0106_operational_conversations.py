"""Add durable operational conversations and ordered turns.

Revision ID: 20260813_0106
Revises: 20260813_0105
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260813_0106"
down_revision: str | None = "20260813_0105"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conversation_table = "operational_conversations"
    op.create_table(
        conversation_table,
        sa.Column("conversation_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("lifecycle", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("owner_subject_id", sa.String(length=240), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("version >= 1", name="ck_operational_conversation_version"),
        sa.PrimaryKeyConstraint("conversation_id"),
    )
    for column in (
        "lifecycle",
        "target_type",
        "target_id",
        "owner_subject_id",
        "organization_id",
        "environment_id",
        "site_id",
    ):
        op.create_index(
            op.f(f"ix_{conversation_table}_{column}"),
            conversation_table,
            [column],
            unique=False,
        )
    op.create_index(
        "ix_operational_conversations_scope_owner_updated",
        conversation_table,
        [
            "organization_id",
            "environment_id",
            "site_id",
            "owner_subject_id",
            "updated_at",
        ],
        unique=False,
    )

    turn_table = "operational_conversation_turns"
    op.create_table(
        turn_table,
        sa.Column("turn_id", sa.String(length=128), nullable=False),
        sa.Column("conversation_id", sa.String(length=128), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("ordinal >= 1", name="ck_operational_conversation_turn_ordinal"),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["operational_conversations.conversation_id"],
            name="fk_operational_conversation_turn_parent",
        ),
        sa.PrimaryKeyConstraint("turn_id"),
        sa.UniqueConstraint(
            "conversation_id",
            "ordinal",
            name="uq_operational_conversation_turn_ordinal",
        ),
    )
    for column in ("conversation_id", "role", "status"):
        op.create_index(op.f(f"ix_{turn_table}_{column}"), turn_table, [column], unique=False)

    idempotency_table = "operational_conversation_idempotency_records"
    op.create_table(
        idempotency_table,
        sa.Column("record_id", sa.String(length=128), nullable=False),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("idempotency_scope_id", sa.String(length=240), nullable=False),
        sa.Column("owner_subject_id", sa.String(length=240), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("result_digest", sa.String(length=64), nullable=False),
        sa.Column("conversation_id", sa.String(length=128), nullable=False),
        sa.Column("result_version", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("result_version >= 1", name="ck_operational_conversation_idem_version"),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["operational_conversations.conversation_id"],
            name="fk_operational_conversation_idem_parent",
        ),
        sa.PrimaryKeyConstraint("record_id"),
        sa.UniqueConstraint(
            "operation",
            "idempotency_scope_id",
            "idempotency_key",
            name="uq_operational_conversation_operation_scope_idem",
        ),
    )
    for column in (
        "operation",
        "idempotency_scope_id",
        "owner_subject_id",
        "conversation_id",
        "organization_id",
        "environment_id",
        "site_id",
    ):
        op.create_index(
            op.f(f"ix_{idempotency_table}_{column}"),
            idempotency_table,
            [column],
            unique=False,
        )


def downgrade() -> None:
    idempotency_table = "operational_conversation_idempotency_records"
    for column in reversed(
        (
            "operation",
            "idempotency_scope_id",
            "owner_subject_id",
            "conversation_id",
            "organization_id",
            "environment_id",
            "site_id",
        )
    ):
        op.drop_index(op.f(f"ix_{idempotency_table}_{column}"), table_name=idempotency_table)
    op.drop_table(idempotency_table)

    turn_table = "operational_conversation_turns"
    for column in reversed(("conversation_id", "role", "status")):
        op.drop_index(op.f(f"ix_{turn_table}_{column}"), table_name=turn_table)
    op.drop_table(turn_table)

    conversation_table = "operational_conversations"
    op.drop_index("ix_operational_conversations_scope_owner_updated", table_name=conversation_table)
    for column in reversed(
        (
            "lifecycle",
            "target_type",
            "target_id",
            "owner_subject_id",
            "organization_id",
            "environment_id",
            "site_id",
        )
    ):
        op.drop_index(op.f(f"ix_{conversation_table}_{column}"), table_name=conversation_table)
    op.drop_table(conversation_table)
