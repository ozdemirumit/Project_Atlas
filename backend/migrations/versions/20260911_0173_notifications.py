"""Add real, durable, pull-based in-app notifications (docs/037_Approval_Workflow.md Sec.20,
Sec.22; pass 38 audit finding).

One new table:

* ``notifications`` -- one real, recipient-addressed notification per row. Created by a real
  event-bus subscriber reacting to an already-committed approval domain event
  (``ApprovalRequestCreated`` / ``ApprovalGranted``), never written directly from an HTTP request.
  ``created_at``/``read_at`` are real, indexed columns (not only fields inside ``payload``) so the
  recipient inbox's unread filter and ordering never need to parse JSON.

See atlas.modules.notifications.domain.models for the real domain model and why this module is a
dedicated cross-cutting module rather than living inside ``approvals`` -- and
atlas.modules.notifications.application.service / atlas.api.routes.notifications for the service
and routes that make this table reachable.

Revision ID: 20260911_0173
Revises: 20260911_0172
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260911_0173"
down_revision: str | None = "20260911_0172"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("notification_id", sa.String(128), primary_key=True),
        sa.Column("recipient_subject_id", sa.String(128), nullable=False),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("environment_id", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", JSONB(), nullable=False),
    )
    op.create_index(
        "ix_notifications_recipient",
        "notifications",
        ["recipient_subject_id", "organization_id", "environment_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_recipient", table_name="notifications")
    op.drop_table("notifications")
