"""Scope and minimize connector invocation authorizations.

Revision ID: 20260824_0161
Revises: 20260824_0160
"""

import json
from collections.abc import Sequence
from hashlib import sha256

import sqlalchemy as sa
from alembic import op

revision: str = "20260824_0161"
down_revision: str | None = "20260824_0160"
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
    table = "connector_invocation_authorizations"
    connection = op.get_bind()
    connection.execute(sa.text(f"LOCK TABLE {table} IN ACCESS EXCLUSIVE MODE"))
    op.add_column(table, sa.Column("replay_digest", sa.String(length=64), nullable=True))
    op.drop_constraint(
        "uq_connector_invocation_authorizations_target_session", table, type_="unique"
    )
    op.drop_constraint(
        "uq_connector_invocation_authorizations_actor_idempotency", table, type_="unique"
    )
    op.alter_column(table, "idempotency_key", new_column_name="idempotency_digest")

    rows = tuple(
        connection.execute(
            sa.text(
                "SELECT authorization_id, organization_id, environment_id, authorized_by, "
                "idempotency_digest, payload ->> 'request_fingerprint' AS request_fingerprint "
                f"FROM {table}"
            )
        ).mappings()
    )
    updates: list[dict[str, str]] = []
    for row in rows:
        request_fingerprint = row["request_fingerprint"]
        if not isinstance(request_fingerprint, str) or len(request_fingerprint) != 64:
            raise RuntimeError(
                "Cannot migrate invocation authorization without its request fingerprint."
            )
        idempotency_digest = _json_digest(
            [
                row["organization_id"],
                row["environment_id"],
                row["authorized_by"],
                row["idempotency_digest"],
            ]
        )
        replay_digest = _json_digest(
            [
                row["organization_id"],
                row["environment_id"],
                row["authorized_by"],
                idempotency_digest,
                request_fingerprint,
            ]
        )
        updates.append(
            {
                "authorization_id": row["authorization_id"],
                "idempotency_digest": idempotency_digest,
                "replay_digest": replay_digest,
            }
        )
    if updates:
        connection.execute(
            sa.text(
                f"UPDATE {table} AS target SET "
                "idempotency_digest = replacement.idempotency_digest, "
                "replay_digest = replacement.replay_digest FROM unnest("
                "CAST(:authorization_ids AS text[]), "
                "CAST(:idempotency_digests AS text[]), "
                "CAST(:replay_digests AS text[])"
                ") AS replacement(authorization_id, idempotency_digest, replay_digest) "
                "WHERE target.authorization_id = replacement.authorization_id"
            ),
            {
                "authorization_ids": [item["authorization_id"] for item in updates],
                "idempotency_digests": [item["idempotency_digest"] for item in updates],
                "replay_digests": [item["replay_digest"] for item in updates],
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
    op.alter_column(table, "replay_digest", existing_type=sa.String(64), nullable=False)
    op.create_unique_constraint(
        "uq_connector_invocation_authorizations_target_session",
        table,
        ["organization_id", "environment_id", "source_target_session_verification_id"],
    )
    op.create_unique_constraint(
        "uq_connector_invocation_authorizations_actor_idempotency",
        table,
        ["organization_id", "environment_id", "authorized_by", "idempotency_digest"],
    )


def downgrade() -> None:
    table = "connector_invocation_authorizations"
    connection = op.get_bind()
    connection.execute(sa.text(f"LOCK TABLE {table} IN ACCESS EXCLUSIVE MODE"))
    count = connection.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
    if count:
        raise RuntimeError(
            "Cannot downgrade invocation authorizations with existing records: minimized "
            "idempotency and request fields cannot be reconstructed."
        )
    op.drop_constraint(
        "uq_connector_invocation_authorizations_actor_idempotency", table, type_="unique"
    )
    op.drop_constraint(
        "uq_connector_invocation_authorizations_target_session", table, type_="unique"
    )
    op.create_unique_constraint(
        "uq_connector_invocation_authorizations_target_session",
        table,
        ["source_target_session_verification_id"],
    )
    op.create_unique_constraint(
        "uq_connector_invocation_authorizations_actor_idempotency",
        table,
        ["authorized_by", "idempotency_digest"],
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
