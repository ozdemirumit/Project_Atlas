"""Scope bounded invocations and downstream evidence ingestion.

Revision ID: 20260825_0162
Revises: 20260824_0161
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260825_0162"
down_revision: str | None = "20260824_0161"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCOPE = ("organization_id", "environment_id")
PRIMARY_KEYS = (
    (
        "connector_invocation_consumption_claims",
        "connector_invocation_consumption_claims_pkey",
        "claim_id",
    ),
    (
        "connector_bounded_invocations",
        "connector_bounded_invocations_pkey",
        "invocation_id",
    ),
    (
        "connector_invocation_evidence_claims",
        "connector_invocation_evidence_claims_pkey",
        "claim_id",
    ),
    (
        "connector_invocation_evidence_ingestions",
        "connector_invocation_evidence_ingestions_pkey",
        "ingestion_id",
    ),
)
UNIQUE_CONSTRAINTS = (
    (
        "connector_invocation_consumption_claims",
        "uq_connector_invocation_claims_authorization",
        ("source_authorization_id",),
    ),
    (
        "connector_invocation_consumption_claims",
        "uq_connector_invocation_claims_actor_idempotency",
        ("claimed_by", "idempotency_digest"),
    ),
    (
        "connector_bounded_invocations",
        "uq_connector_bounded_invocations_authorization",
        ("source_authorization_id",),
    ),
    (
        "connector_bounded_invocations",
        "uq_connector_bounded_invocations_claim",
        ("consumption_claim_id",),
    ),
    (
        "connector_invocation_evidence_claims",
        "uq_connector_invocation_evidence_claims_source",
        ("source_invocation_id",),
    ),
    (
        "connector_invocation_evidence_claims",
        "uq_connector_invocation_evidence_claims_actor_idempotency",
        ("claimed_by", "idempotency_digest"),
    ),
    (
        "connector_invocation_evidence_ingestions",
        "uq_connector_invocation_evidence_source",
        ("source_invocation_id",),
    ),
    (
        "connector_invocation_evidence_ingestions",
        "uq_connector_invocation_evidence_claim",
        ("claim_id",),
    ),
)


def _lock_tables() -> None:
    op.get_bind().execute(
        sa.text(
            "LOCK TABLE connector_invocation_consumption_claims, "
            "connector_bounded_invocations, connector_invocation_evidence_claims, "
            "connector_invocation_evidence_ingestions IN ACCESS EXCLUSIVE MODE"
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
            "Cannot downgrade tenant-scoped invocation records while identifiers overlap "
            "between tenants."
        )
    for table, name, _ in UNIQUE_CONSTRAINTS:
        op.drop_constraint(name, table, type_="unique")
    for table, name, identifier in PRIMARY_KEYS:
        op.drop_constraint(name, table, type_="primary")
        op.create_primary_key(name, table, [identifier])
    for table, name, columns in UNIQUE_CONSTRAINTS:
        op.create_unique_constraint(name, table, [*columns])
