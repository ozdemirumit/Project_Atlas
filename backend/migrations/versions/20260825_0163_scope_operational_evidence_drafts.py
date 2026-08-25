"""Scope operational evidence draft claims and records.

Revision ID: 20260825_0163
Revises: 20260825_0162
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260825_0163"
down_revision: str | None = "20260825_0162"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCOPE = ("organization_id", "environment_id")
PRIMARY_KEYS = (
    (
        "operational_evidence_knowledge_draft_claims",
        "operational_evidence_knowledge_draft_claims_pkey",
        "claim_id",
    ),
    (
        "operational_evidence_knowledge_drafts",
        "operational_evidence_knowledge_drafts_pkey",
        "draft_id",
    ),
)
UNIQUE_CONSTRAINTS = (
    (
        "operational_evidence_knowledge_draft_claims",
        "uq_operational_evidence_knowledge_draft_claims_source",
        ("source_ingestion_id",),
    ),
    (
        "operational_evidence_knowledge_draft_claims",
        "uq_ok_draft_claim_actor_idem",
        ("claimed_by", "idempotency_digest"),
    ),
    (
        "operational_evidence_knowledge_drafts",
        "uq_operational_evidence_knowledge_drafts_source",
        ("source_ingestion_id",),
    ),
    (
        "operational_evidence_knowledge_drafts",
        "uq_operational_evidence_knowledge_drafts_claim",
        ("claim_id",),
    ),
)


def _lock_tables() -> None:
    op.get_bind().execute(
        sa.text(
            "LOCK TABLE operational_evidence_knowledge_draft_claims, "
            "operational_evidence_knowledge_drafts IN ACCESS EXCLUSIVE MODE"
        )
    )


def upgrade() -> None:
    _lock_tables()
    for table, name, _ in UNIQUE_CONSTRAINTS:
        op.drop_constraint(name, table, type_="unique")
    for table, name, identifier in PRIMARY_KEYS:
        op.drop_constraint(name, table, type_="primary")
        op.create_primary_key(name, table, [identifier, *SCOPE])
    for table, name, columns in UNIQUE_CONSTRAINTS:
        op.create_unique_constraint(name, table, [*SCOPE, *columns])


def _has_global_duplicates(table: str, columns: tuple[str, ...]) -> bool:
    grouping = ", ".join(columns)
    result = op.get_bind().execute(
        sa.text(f"SELECT EXISTS (SELECT 1 FROM {table} GROUP BY {grouping} HAVING COUNT(*) > 1)")
    )
    return bool(result.scalar_one())


def downgrade() -> None:
    _lock_tables()
    duplicate_contracts = tuple(
        (table, (identifier,)) for table, _, identifier in PRIMARY_KEYS
    ) + tuple((table, columns) for table, _, columns in UNIQUE_CONSTRAINTS)
    if any(_has_global_duplicates(table, columns) for table, columns in duplicate_contracts):
        raise RuntimeError(
            "Cannot downgrade tenant-scoped operational evidence drafts while identifiers "
            "overlap between tenants."
        )
    for table, name, _ in UNIQUE_CONSTRAINTS:
        op.drop_constraint(name, table, type_="unique")
    for table, name, identifier in PRIMARY_KEYS:
        op.drop_constraint(name, table, type_="primary")
        op.create_primary_key(name, table, [identifier])
    for table, name, columns in UNIQUE_CONSTRAINTS:
        op.create_unique_constraint(name, table, [*columns])
