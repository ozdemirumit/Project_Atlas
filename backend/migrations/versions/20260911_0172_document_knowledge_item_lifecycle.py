"""Add document-sourced knowledge item lifecycle and conflict tracking (docs/027_Knowledge_Engine.md
Sec.8, Sec.21).

Two new tables:

* ``document_knowledge_item_lifecycle`` -- one *current-state* row per document-sourced knowledge
  item, composite primary key ``(knowledge_item_id, organization_id, environment_id)``. Mutable,
  unlike the append-only ``document_knowledge_{drafts,reviews,approvals,preparations}`` tables
  from migration 20260827_0168 -- this table tracks an already-published item's ongoing lifecycle
  (Sec.8's "Published -> Suspended -> Published" and "Published -> Superseded -> Retired"
  transitions), not a one-way approval chain, so there is exactly one row of current truth per
  item. An item with no row here is implicitly ACTIVE ("Published") -- the overwhelming majority
  case, matching the doc's own default.
* ``document_knowledge_conflicts`` -- append-only detected conflicts between two items (Sec.21,
  "Conflict and Supersession" -- MVP-included). Resolution is recorded in place via payload
  fields, never a new row.

See atlas.modules.knowledge.domain.document_knowledge_lifecycle for the real domain models and
atlas.modules.knowledge.application.document_knowledge_lifecycle for the service that makes these
tables reachable, including the real retrieval-time enforcement in
DocumentKnowledgeRetrievalService.retrieve() that excludes non-ACTIVE items from search results.

Revision ID: 20260911_0172
Revises: 20260911_0171
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260911_0172"
down_revision: str | None = "20260911_0171"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_knowledge_item_lifecycle",
        sa.Column("knowledge_item_id", sa.String(128), primary_key=True),
        sa.Column("organization_id", sa.String(128), primary_key=True),
        sa.Column("environment_id", sa.String(128), primary_key=True),
        sa.Column("state", sa.String(32), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
    )
    op.create_index(
        "ix_document_knowledge_item_lifecycle_scope",
        "document_knowledge_item_lifecycle",
        ["organization_id", "environment_id"],
    )

    op.create_table(
        "document_knowledge_conflicts",
        sa.Column("conflict_id", sa.String(128), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("environment_id", sa.String(128), nullable=False),
        sa.Column("knowledge_item_id_a", sa.String(128), nullable=False),
        sa.Column("knowledge_item_id_b", sa.String(128), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
    )
    op.create_index(
        "ix_document_knowledge_conflicts_scope",
        "document_knowledge_conflicts",
        ["organization_id", "environment_id"],
    )
    op.create_index(
        "ix_document_knowledge_conflicts_item_a",
        "document_knowledge_conflicts",
        ["knowledge_item_id_a"],
    )
    op.create_index(
        "ix_document_knowledge_conflicts_item_b",
        "document_knowledge_conflicts",
        ["knowledge_item_id_b"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_knowledge_conflicts_item_b", table_name="document_knowledge_conflicts"
    )
    op.drop_index(
        "ix_document_knowledge_conflicts_item_a", table_name="document_knowledge_conflicts"
    )
    op.drop_index(
        "ix_document_knowledge_conflicts_scope", table_name="document_knowledge_conflicts"
    )
    op.drop_table("document_knowledge_conflicts")

    op.drop_index(
        "ix_document_knowledge_item_lifecycle_scope",
        table_name="document_knowledge_item_lifecycle",
    )
    op.drop_table("document_knowledge_item_lifecycle")
