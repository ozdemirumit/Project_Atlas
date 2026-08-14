"""Add immutable workflow dispatch outbox admissions.

Revision ID: 20260814_0113
Revises: 20260814_0112
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from hashlib import sha256
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260814_0113"
down_revision: str | None = "20260814_0112"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _canonical_digest(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode()
    return sha256(encoded).hexdigest()


def _outbox_entry_id(dispatch_intent_id: str) -> str:
    suffix = sha256(f"{dispatch_intent_id}:admitted".encode()).hexdigest()[:24]
    return f"workflow-dispatch-outbox.{suffix}"


def _outbox_payload(intent: Mapping[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "admitted_at": intent["staged_at"],
        "attempt_digest": intent["attempt_digest"],
        "attempt_id": intent["attempt_id"],
        "attempt_number": intent["attempt_number"],
        "authority": intent["authority"],
        "dispatch_intent_digest": intent["canonical_digest"],
        "dispatch_intent_id": intent["dispatch_intent_id"],
        "fencing_token": intent["fencing_token"],
        "lease_digest": intent["lease_digest"],
        "lease_id": intent["lease_id"],
        "outbox_entry_id": _outbox_entry_id(str(intent["dispatch_intent_id"])),
        "plan_digest": intent["plan_digest"],
        "plan_id": intent["plan_id"],
        "run_digest": intent["run_digest"],
        "run_id": intent["run_id"],
        "scope": intent["scope"],
        "state": "pending_publication",
        "step_id": intent["step_id"],
        "step_run_digest": intent["step_run_digest"],
        "step_run_id": intent["step_run_id"],
        "target_id": intent["target_id"],
        "target_type": intent["target_type"],
        "worker_subject_id": intent["worker_subject_id"],
    }
    return payload | {"canonical_digest": _canonical_digest(payload)}


def _outbox_table() -> sa.TableClause:
    return sa.table(
        "workflow_dispatch_outbox_entries",
        sa.column("outbox_entry_id", sa.String()),
        sa.column("dispatch_intent_id", sa.String()),
        sa.column("dispatch_intent_digest", sa.String()),
        sa.column("plan_id", sa.String()),
        sa.column("plan_digest", sa.String()),
        sa.column("run_id", sa.String()),
        sa.column("run_digest", sa.String()),
        sa.column("step_run_id", sa.String()),
        sa.column("step_run_digest", sa.String()),
        sa.column("step_id", sa.String()),
        sa.column("attempt_id", sa.String()),
        sa.column("attempt_digest", sa.String()),
        sa.column("attempt_number", sa.Integer()),
        sa.column("organization_id", sa.String()),
        sa.column("environment_id", sa.String()),
        sa.column("site_id", sa.String()),
        sa.column("target_type", sa.String()),
        sa.column("target_id", sa.String()),
        sa.column("lease_id", sa.String()),
        sa.column("lease_digest", sa.String()),
        sa.column("lease_fencing_token", sa.Integer()),
        sa.column("worker_subject_id", sa.String()),
        sa.column("admitted_at", sa.DateTime(timezone=True)),
        sa.column("state", sa.String()),
        sa.column("publication_authority_granted", sa.Boolean()),
        sa.column("delivery_authority_granted", sa.Boolean()),
        sa.column("dispatch_authority_granted", sa.Boolean()),
        sa.column("execution_authority_granted", sa.Boolean()),
        sa.column("canonical_digest", sa.String()),
        sa.column("payload", postgresql.JSONB()),
    )


def _claim_table() -> sa.TableClause:
    return sa.table(
        "workflow_dispatch_intent_staging_claims",
        sa.column("claim_id", sa.String()),
        sa.column("dispatch_intent_id", sa.String()),
        sa.column("outbox_entry_id", sa.String()),
        sa.column("result_outbox_digest", sa.String()),
        sa.column("canonical_digest", sa.String()),
        sa.column("payload", postgresql.JSONB()),
    )


def upgrade() -> None:
    table_name = "workflow_dispatch_outbox_entries"
    op.create_table(
        table_name,
        sa.Column("outbox_entry_id", sa.String(length=128), nullable=False),
        sa.Column("dispatch_intent_id", sa.String(length=128), nullable=False),
        sa.Column("dispatch_intent_digest", sa.String(length=64), nullable=False),
        sa.Column("plan_id", sa.String(length=128), nullable=False),
        sa.Column("plan_digest", sa.String(length=64), nullable=False),
        sa.Column("run_id", sa.String(length=128), nullable=False),
        sa.Column("run_digest", sa.String(length=64), nullable=False),
        sa.Column("step_run_id", sa.String(length=128), nullable=False),
        sa.Column("step_run_digest", sa.String(length=64), nullable=False),
        sa.Column("step_id", sa.String(length=128), nullable=False),
        sa.Column("attempt_id", sa.String(length=128), nullable=False),
        sa.Column("attempt_digest", sa.String(length=64), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("site_id", sa.String(length=128), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        # The current lease row can be replaced by a fencing takeover. This table
        # keeps the exact historical lease snapshot and intentionally has no lease FK.
        sa.Column("lease_id", sa.String(length=128), nullable=False),
        sa.Column("lease_digest", sa.String(length=64), nullable=False),
        sa.Column("lease_fencing_token", sa.Integer(), nullable=False),
        sa.Column("worker_subject_id", sa.String(length=240), nullable=False),
        sa.Column("admitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("publication_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("delivery_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("dispatch_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("execution_authority_granted", sa.Boolean(), nullable=False),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "attempt_number = 1",
            name="ck_workflow_dispatch_outbox_attempt_number",
        ),
        sa.CheckConstraint(
            "lease_fencing_token >= 1",
            name="ck_workflow_dispatch_outbox_fencing_token",
        ),
        sa.CheckConstraint(
            "state = 'pending_publication'",
            name="ck_workflow_dispatch_outbox_state",
        ),
        sa.CheckConstraint(
            "NOT publication_authority_granted "
            "AND NOT delivery_authority_granted "
            "AND NOT dispatch_authority_granted "
            "AND NOT execution_authority_granted",
            name="ck_workflow_dispatch_outbox_zero_authority",
        ),
        sa.ForeignKeyConstraint(
            ["dispatch_intent_id"],
            ["workflow_dispatch_intents.dispatch_intent_id"],
            name="fk_workflow_dispatch_outbox_source_intent",
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"],
            ["workflow_run_plans.plan_id"],
            name="fk_workflow_dispatch_outbox_plan",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["workflow_execution_runs.run_id"],
            name="fk_workflow_dispatch_outbox_run",
        ),
        sa.ForeignKeyConstraint(
            ["step_run_id"],
            ["workflow_execution_step_runs.step_run_id"],
            name="fk_workflow_dispatch_outbox_step_run",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["workflow_execution_attempts.attempt_id"],
            name="fk_workflow_dispatch_outbox_attempt",
        ),
        sa.PrimaryKeyConstraint("outbox_entry_id"),
        sa.UniqueConstraint(
            "dispatch_intent_id",
            name="uq_workflow_dispatch_outbox_source_intent",
        ),
        sa.UniqueConstraint(
            "canonical_digest",
            name="uq_workflow_dispatch_outbox_digest",
        ),
    )
    index_columns = (
        "dispatch_intent_id",
        "dispatch_intent_digest",
        "plan_id",
        "plan_digest",
        "run_id",
        "run_digest",
        "step_run_id",
        "step_run_digest",
        "step_id",
        "attempt_id",
        "attempt_digest",
        "organization_id",
        "environment_id",
        "site_id",
        "target_type",
        "target_id",
        "lease_id",
        "lease_digest",
        "worker_subject_id",
        "state",
    )
    for column in index_columns:
        op.create_index(op.f(f"ix_{table_name}_{column}"), table_name, [column])
    op.create_index(
        "ix_workflow_dispatch_outbox_run_admitted",
        table_name,
        ["run_id", "admitted_at", "outbox_entry_id"],
    )

    bind = op.get_bind()
    intent_rows = bind.execute(
        sa.text(
            "SELECT dispatch_intent_id, staged_at, payload "
            "FROM workflow_dispatch_intents ORDER BY dispatch_intent_id"
        )
    ).mappings()
    outbox_table = _outbox_table()
    for intent_row in intent_rows:
        intent = dict(intent_row["payload"])
        outbox = _outbox_payload(intent)
        authority = outbox["authority"]
        if not isinstance(authority, dict) or any(authority.values()):
            raise ValueError("existing dispatch intent grants operational authority")
        scope = outbox["scope"]
        if not isinstance(scope, dict):
            raise ValueError("existing dispatch intent has an invalid scope")
        bind.execute(
            outbox_table.insert().values(
                outbox_entry_id=outbox["outbox_entry_id"],
                dispatch_intent_id=outbox["dispatch_intent_id"],
                dispatch_intent_digest=outbox["dispatch_intent_digest"],
                plan_id=outbox["plan_id"],
                plan_digest=outbox["plan_digest"],
                run_id=outbox["run_id"],
                run_digest=outbox["run_digest"],
                step_run_id=outbox["step_run_id"],
                step_run_digest=outbox["step_run_digest"],
                step_id=outbox["step_id"],
                attempt_id=outbox["attempt_id"],
                attempt_digest=outbox["attempt_digest"],
                attempt_number=outbox["attempt_number"],
                organization_id=scope["organization_id"],
                environment_id=scope["environment_id"],
                site_id=scope["site_id"],
                target_type=outbox["target_type"],
                target_id=outbox["target_id"],
                lease_id=outbox["lease_id"],
                lease_digest=outbox["lease_digest"],
                lease_fencing_token=outbox["fencing_token"],
                worker_subject_id=outbox["worker_subject_id"],
                admitted_at=intent_row["staged_at"],
                state="pending_publication",
                publication_authority_granted=False,
                delivery_authority_granted=False,
                dispatch_authority_granted=False,
                execution_authority_granted=False,
                canonical_digest=outbox["canonical_digest"],
                payload=outbox,
            )
        )

    claim_table_name = "workflow_dispatch_intent_staging_claims"
    op.add_column(
        claim_table_name,
        sa.Column("result_outbox_digest", sa.String(length=64), nullable=True),
    )
    op.add_column(
        claim_table_name,
        sa.Column("outbox_entry_id", sa.String(length=128), nullable=True),
    )
    claim_rows = bind.execute(
        sa.text(
            "SELECT c.claim_id, c.payload AS claim_payload, o.outbox_entry_id, "
            "o.canonical_digest AS outbox_digest, o.payload AS outbox_payload "
            "FROM workflow_dispatch_intent_staging_claims AS c "
            "JOIN workflow_dispatch_outbox_entries AS o "
            "ON o.dispatch_intent_id = c.dispatch_intent_id "
            "ORDER BY c.claim_id"
        )
    ).mappings()
    claim_table = _claim_table()
    for claim_row in claim_rows:
        payload = dict(claim_row["claim_payload"])
        payload["result_outbox_digest"] = claim_row["outbox_digest"]
        payload["result_outbox_entry"] = dict(claim_row["outbox_payload"])
        bind.execute(
            claim_table.update()
            .where(claim_table.c.claim_id == claim_row["claim_id"])
            .values(
                outbox_entry_id=claim_row["outbox_entry_id"],
                result_outbox_digest=claim_row["outbox_digest"],
                canonical_digest=_canonical_digest(payload),
                payload=payload,
            )
        )
    op.alter_column(claim_table_name, "result_outbox_digest", nullable=False)
    op.alter_column(claim_table_name, "outbox_entry_id", nullable=False)
    op.create_foreign_key(
        "fk_workflow_dispatch_intent_staging_claim_outbox",
        claim_table_name,
        table_name,
        ["outbox_entry_id"],
        ["outbox_entry_id"],
    )
    op.create_unique_constraint(
        "uq_workflow_dispatch_intent_staging_claim_outbox",
        claim_table_name,
        ["outbox_entry_id"],
    )
    op.create_index(
        op.f(f"ix_{claim_table_name}_outbox_entry_id"),
        claim_table_name,
        ["outbox_entry_id"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    claim_table_name = "workflow_dispatch_intent_staging_claims"
    claim_table = _claim_table()
    claim_rows = bind.execute(
        sa.text(
            "SELECT claim_id, payload FROM workflow_dispatch_intent_staging_claims "
            "ORDER BY claim_id"
        )
    ).mappings()
    for claim_row in claim_rows:
        payload = dict(claim_row["payload"])
        payload.pop("result_outbox_digest", None)
        payload.pop("result_outbox_entry", None)
        bind.execute(
            claim_table.update()
            .where(claim_table.c.claim_id == claim_row["claim_id"])
            .values(canonical_digest=_canonical_digest(payload), payload=payload)
        )
    op.drop_index(
        op.f(f"ix_{claim_table_name}_outbox_entry_id"),
        table_name=claim_table_name,
    )
    op.drop_constraint(
        "uq_workflow_dispatch_intent_staging_claim_outbox",
        claim_table_name,
        type_="unique",
    )
    op.drop_constraint(
        "fk_workflow_dispatch_intent_staging_claim_outbox",
        claim_table_name,
        type_="foreignkey",
    )
    op.drop_column(claim_table_name, "outbox_entry_id")
    op.drop_column(claim_table_name, "result_outbox_digest")

    table_name = "workflow_dispatch_outbox_entries"
    op.drop_index("ix_workflow_dispatch_outbox_run_admitted", table_name=table_name)
    for column in reversed(
        (
            "dispatch_intent_id",
            "dispatch_intent_digest",
            "plan_id",
            "plan_digest",
            "run_id",
            "run_digest",
            "step_run_id",
            "step_run_digest",
            "step_id",
            "attempt_id",
            "attempt_digest",
            "organization_id",
            "environment_id",
            "site_id",
            "target_type",
            "target_id",
            "lease_id",
            "lease_digest",
            "worker_subject_id",
            "state",
        )
    ):
        op.drop_index(op.f(f"ix_{table_name}_{column}"), table_name=table_name)
    op.drop_table(table_name)
