"""Durable role assignments, closing the gap where AuthorizationService could only authorize
subjects hand-written into a static, code-level list at startup (docs/031_RBAC.md Sec.11/26).

One new table:

* ``role_assignments`` -- one row per `(subject_id, role_id, scope)` grant. Additive to the
  existing static assignment list, never replacing it: `AuthorizationService.evaluate()` checks
  this table only when no static assignment already matches. See
  atlas.modules.authorization.adapters.role_assignment_postgres and
  atlas.modules.authorization.application.role_assignment_grant for what makes this reachable.

Revision ID: 20260917_0175
Revises: 20260916_0174
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260917_0175"
down_revision: str | None = "20260916_0174"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "role_assignments",
        sa.Column("assignment_id", sa.String(128), primary_key=True),
        sa.Column("subject_id", sa.String(128), nullable=False),
        sa.Column("role_id", sa.String(128), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
    )
    op.create_index("ix_role_assignments_subject_id", "role_assignments", ["subject_id"])
    op.create_index("ix_role_assignments_role_id", "role_assignments", ["role_id"])


def downgrade() -> None:
    op.drop_index("ix_role_assignments_role_id", table_name="role_assignments")
    op.drop_index("ix_role_assignments_subject_id", table_name="role_assignments")
    op.drop_table("role_assignments")
