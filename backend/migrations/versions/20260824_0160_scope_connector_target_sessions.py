"""Scope and minimize connector target-session verifications.

Revision ID: 20260824_0160
Revises: 20260824_0159
"""

import json
from collections.abc import Sequence
from hashlib import sha256

import sqlalchemy as sa
from alembic import op

revision: str = "20260824_0160"
down_revision: str | None = "20260824_0159"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json_digest(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return sha256(encoded).hexdigest()


def upgrade() -> None:
    table = "connector_target_session_verifications"
    connection = op.get_bind()
    connection.execute(sa.text(f"LOCK TABLE {table} IN ACCESS EXCLUSIVE MODE"))
    op.add_column(
        table,
        sa.Column("verification_attempt_id", sa.String(length=128), nullable=True),
    )
    op.add_column(table, sa.Column("verified_by_digest", sa.String(length=64), nullable=True))
    op.add_column(table, sa.Column("replay_digest", sa.String(length=64), nullable=True))
    op.drop_constraint("uq_connector_target_sessions_runtime_activation", table, type_="unique")
    op.drop_constraint("uq_connector_target_sessions_actor_idempotency", table, type_="unique")
    op.alter_column(table, "idempotency_key", new_column_name="idempotency_digest")

    rows = connection.execute(
        sa.text(
            "SELECT verification_id, organization_id, environment_id, verified_by, "
            "idempotency_digest, payload ->> 'request_fingerprint' AS request_fingerprint "
            f"FROM {table}"
        )
    ).mappings()
    for row in rows:
        request_fingerprint = row["request_fingerprint"]
        if not isinstance(request_fingerprint, str) or len(request_fingerprint) != 64:
            raise RuntimeError(
                "Cannot migrate connector target session without its request fingerprint."
            )
        verified_by_digest = sha256(row["verified_by"].encode("ascii")).hexdigest()
        idempotency_digest = _json_digest(
            [
                row["organization_id"],
                row["environment_id"],
                row["verified_by"],
                row["idempotency_digest"],
            ]
        )
        replay_digest = _json_digest(
            [
                row["organization_id"],
                row["environment_id"],
                verified_by_digest,
                idempotency_digest,
                request_fingerprint,
            ]
        )
        verification_attempt_id = (
            "connector-target-session-attempt.legacy-"
            f"{sha256(row['verification_id'].encode('ascii')).hexdigest()[:24]}"
        )
        connection.execute(
            sa.text(
                f"UPDATE {table} SET verified_by_digest = :verified_by_digest, "
                "idempotency_digest = :idempotency_digest, replay_digest = :replay_digest, "
                "verification_attempt_id = :verification_attempt_id, "
                "payload = jsonb_set(payload, '{verification_attempt_id}', "
                "to_jsonb(CAST(:verification_attempt_id AS text)), true) "
                "WHERE verification_id = :verification_id"
            ),
            {
                "verification_id": row["verification_id"],
                "verified_by_digest": verified_by_digest,
                "idempotency_digest": idempotency_digest,
                "replay_digest": replay_digest,
                "verification_attempt_id": verification_attempt_id,
            },
        )
    connection.execute(
        sa.text(
            f"UPDATE {table} SET payload = payload - 'request_fingerprint' - "
            "'idempotency_key' - 'replay_digest' - 'idempotency_digest' - 'reused'"
        )
    )
    op.alter_column(
        table,
        "idempotency_digest",
        type_=sa.String(length=64),
        existing_type=sa.String(length=128),
        existing_nullable=False,
    )
    op.alter_column(table, "verified_by_digest", existing_type=sa.String(64), nullable=False)
    op.alter_column(table, "replay_digest", existing_type=sa.String(64), nullable=False)
    op.alter_column(
        table,
        "verification_attempt_id",
        existing_type=sa.String(128),
        nullable=False,
    )
    op.create_unique_constraint(
        "uq_connector_target_sessions_runtime_activation",
        table,
        ["organization_id", "environment_id", "source_runtime_activation_id"],
    )
    op.create_unique_constraint(
        "uq_connector_target_sessions_actor_idempotency",
        table,
        ["organization_id", "environment_id", "verified_by_digest", "idempotency_digest"],
    )
    op.create_unique_constraint(
        "uq_connector_target_sessions_attempt",
        table,
        ["organization_id", "environment_id", "verification_attempt_id"],
    )
    op.create_table(
        "connector_target_session_claims",
        sa.Column("verification_attempt_id", sa.String(length=128), nullable=False),
        sa.Column("verification_id", sa.String(length=128), nullable=False),
        sa.Column("source_runtime_activation_id", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("verified_by_digest", sa.String(length=64), nullable=False),
        sa.Column("idempotency_digest", sa.String(length=64), nullable=False),
        sa.Column("replay_digest", sa.String(length=64), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("recovery_owner_attempt_id", sa.String(length=128), nullable=True),
        sa.Column("recovery_lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "(state = 'active' AND recovery_owner_attempt_id IS NULL AND "
            "recovery_lease_expires_at IS NULL) OR "
            "(state = 'recovering' AND recovery_owner_attempt_id IS NOT NULL AND "
            "recovery_lease_expires_at IS NOT NULL)",
            name="ck_connector_target_session_claims_state",
        ),
        sa.PrimaryKeyConstraint("verification_attempt_id"),
        sa.UniqueConstraint(
            "organization_id",
            "environment_id",
            "source_runtime_activation_id",
            name="uq_connector_target_session_claims_source",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "environment_id",
            "verified_by_digest",
            "idempotency_digest",
            name="uq_connector_target_session_claims_actor_key",
        ),
    )


def downgrade() -> None:
    table = "connector_target_session_verifications"
    claim_table = "connector_target_session_claims"
    connection = op.get_bind()
    connection.execute(sa.text(f"LOCK TABLE {table} IN ACCESS EXCLUSIVE MODE"))
    connection.execute(sa.text(f"LOCK TABLE {claim_table} IN ACCESS EXCLUSIVE MODE"))
    count = connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
    claim_count = connection.execute(sa.text(f"SELECT COUNT(*) FROM {claim_table}")).scalar_one()
    if count or claim_count:
        raise RuntimeError(
            "Cannot downgrade connector target sessions with existing records: the minimized "
            "legacy idempotency and request fields cannot be reconstructed."
        )
    op.drop_table(claim_table)
    op.drop_constraint("uq_connector_target_sessions_attempt", table, type_="unique")
    op.drop_constraint("uq_connector_target_sessions_actor_idempotency", table, type_="unique")
    op.drop_constraint("uq_connector_target_sessions_runtime_activation", table, type_="unique")
    op.create_unique_constraint(
        "uq_connector_target_sessions_actor_idempotency",
        table,
        ["verified_by", "idempotency_digest"],
    )
    op.create_unique_constraint(
        "uq_connector_target_sessions_runtime_activation",
        table,
        ["source_runtime_activation_id"],
    )
    op.alter_column(
        table,
        "idempotency_digest",
        type_=sa.String(length=128),
        existing_type=sa.String(length=64),
        existing_nullable=False,
    )
    op.alter_column(table, "idempotency_digest", new_column_name="idempotency_key")
    op.drop_column(table, "replay_digest")
    op.drop_column(table, "verified_by_digest")
    op.drop_column(table, "verification_attempt_id")
