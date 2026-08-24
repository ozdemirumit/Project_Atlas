"""Scope connector runtime activation uniqueness.

Revision ID: 20260824_0159
Revises: 20260824_0158
"""

import json
from collections.abc import Sequence
from hashlib import sha256

import sqlalchemy as sa
from alembic import op

revision: str = "20260824_0159"
down_revision: str | None = "20260824_0158"
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


def _legacy_digests(
    *,
    organization_id: str,
    environment_id: str,
    activated_by: str,
    idempotency_key: str,
    request_fingerprint: str,
) -> tuple[str, str, str]:
    activated_by_digest = sha256(activated_by.encode("ascii")).hexdigest()
    idempotency_digest = _json_digest(
        [organization_id, environment_id, activated_by, idempotency_key]
    )
    replay_digest = _json_digest(
        [
            organization_id,
            environment_id,
            activated_by_digest,
            idempotency_digest,
            request_fingerprint,
        ]
    )
    return activated_by_digest, idempotency_digest, replay_digest


def upgrade() -> None:
    table = "connector_runtime_activations"
    op.execute(sa.text("LOCK TABLE connector_runtime_activations IN ACCESS EXCLUSIVE MODE"))
    op.add_column(
        table,
        sa.Column("activation_attempt_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        table,
        sa.Column("replay_digest", sa.String(length=64), nullable=True),
    )
    op.add_column(
        table,
        sa.Column("activated_by_digest", sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_connector_runtime_activations_activation_attempt",
        table,
        ["activation_attempt_id"],
    )
    op.drop_constraint(
        "uq_connector_runtime_activations_brokerage_authorization",
        table,
        type_="unique",
    )
    op.drop_constraint(
        "uq_connector_runtime_activations_actor_idempotency",
        table,
        type_="unique",
    )
    op.alter_column(
        table,
        "idempotency_key",
        new_column_name="idempotency_digest",
    )
    connection = op.get_bind()
    legacy_rows = connection.execute(
        sa.text(
            "SELECT activation_id, organization_id, environment_id, activated_by, "
            "idempotency_digest, payload ->> 'request_fingerprint' AS request_fingerprint "
            "FROM connector_runtime_activations"
        )
    ).mappings()
    for row in legacy_rows:
        request_fingerprint = row["request_fingerprint"]
        if not isinstance(request_fingerprint, str) or len(request_fingerprint) != 64:
            raise RuntimeError(
                "Cannot migrate connector runtime activation without its request fingerprint."
            )
        activated_by_digest, idempotency_digest, replay_digest = _legacy_digests(
            organization_id=row["organization_id"],
            environment_id=row["environment_id"],
            activated_by=row["activated_by"],
            idempotency_key=row["idempotency_digest"],
            request_fingerprint=request_fingerprint,
        )
        connection.execute(
            sa.text(
                "UPDATE connector_runtime_activations SET "
                "activated_by_digest = :activated_by_digest, "
                "idempotency_digest = :idempotency_digest, replay_digest = :replay_digest "
                "WHERE activation_id = :activation_id"
            ),
            {
                "activation_id": row["activation_id"],
                "activated_by_digest": activated_by_digest,
                "idempotency_digest": idempotency_digest,
                "replay_digest": replay_digest,
            },
        )
    op.execute(
        sa.text(
            "UPDATE connector_runtime_activations SET "
            "payload = payload - 'request_fingerprint' - 'idempotency_key'"
        )
    )
    op.alter_column(
        table,
        "idempotency_digest",
        type_=sa.String(length=64),
        existing_type=sa.String(length=128),
        existing_nullable=False,
    )
    op.alter_column(
        table,
        "replay_digest",
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.alter_column(
        table,
        "activated_by_digest",
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.create_unique_constraint(
        "uq_connector_runtime_activations_brokerage_authorization",
        table,
        ["organization_id", "environment_id", "source_brokerage_authorization_id"],
    )
    op.create_unique_constraint(
        "uq_connector_runtime_activations_actor_idempotency",
        table,
        ["organization_id", "environment_id", "activated_by_digest", "idempotency_digest"],
    )
    op.create_table(
        "connector_runtime_activation_claims",
        sa.Column("activation_attempt_id", sa.String(length=128), nullable=False),
        sa.Column("activation_id", sa.String(length=128), nullable=False),
        sa.Column("source_brokerage_authorization_id", sa.String(length=128), nullable=False),
        sa.Column("organization_id", sa.String(length=128), nullable=False),
        sa.Column("environment_id", sa.String(length=128), nullable=False),
        sa.Column("activated_by_digest", sa.String(length=64), nullable=False),
        sa.Column("idempotency_digest", sa.String(length=64), nullable=False),
        sa.Column("replay_digest", sa.String(length=64), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("recovery_owner_attempt_id", sa.String(length=128), nullable=True),
        sa.Column("recovery_lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canonical_digest", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("activation_attempt_id"),
        sa.UniqueConstraint(
            "organization_id",
            "environment_id",
            "source_brokerage_authorization_id",
            name="uq_connector_runtime_activation_claims_source",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "environment_id",
            "activated_by_digest",
            "idempotency_digest",
            name="uq_connector_runtime_activation_claims_actor_idempotency",
        ),
        sa.CheckConstraint(
            "(state = 'active' AND recovery_owner_attempt_id IS NULL AND "
            "recovery_lease_expires_at IS NULL) OR "
            "(state = 'recovering' AND recovery_owner_attempt_id IS NOT NULL AND "
            "recovery_lease_expires_at IS NOT NULL)",
            name="ck_connector_runtime_activation_claims_recovery_state",
        ),
    )
    op.create_index(
        "ix_connector_runtime_activation_claims_activation_id",
        "connector_runtime_activation_claims",
        ["activation_id"],
    )
    op.create_index(
        "ix_connector_rt_activation_claims_source",
        "connector_runtime_activation_claims",
        ["source_brokerage_authorization_id"],
    )
    op.create_index(
        "ix_connector_runtime_activation_claims_organization_id",
        "connector_runtime_activation_claims",
        ["organization_id"],
    )
    op.create_index(
        "ix_connector_runtime_activation_claims_environment_id",
        "connector_runtime_activation_claims",
        ["environment_id"],
    )


def downgrade() -> None:
    table = "connector_runtime_activations"
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "LOCK TABLE connector_runtime_activations, "
            "connector_runtime_activation_claims IN ACCESS EXCLUSIVE MODE"
        )
    )
    activation_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM connector_runtime_activations")
    ).scalar_one()
    claim_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM connector_runtime_activation_claims")
    ).scalar_one()
    if activation_count or claim_count:
        raise RuntimeError(
            "Cannot downgrade connector runtime activations with existing records: "
            "the minimized legacy idempotency and request fields cannot be reconstructed."
        )
    op.drop_table("connector_runtime_activation_claims")
    duplicate_source = connection.execute(
        sa.text(
            "SELECT source_brokerage_authorization_id FROM connector_runtime_activations "
            "GROUP BY source_brokerage_authorization_id HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    duplicate_create_key = connection.execute(
        sa.text(
            "SELECT activated_by, idempotency_digest FROM connector_runtime_activations "
            "GROUP BY activated_by, idempotency_digest HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate_source is not None or duplicate_create_key is not None:
        raise RuntimeError(
            "Cannot downgrade connector runtime activations: tenant-scoped records would "
            "violate the legacy global uniqueness constraints."
        )
    op.drop_constraint(
        "uq_connector_runtime_activations_actor_idempotency",
        table,
        type_="unique",
    )
    op.drop_constraint(
        "uq_connector_runtime_activations_brokerage_authorization",
        table,
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_connector_runtime_activations_actor_idempotency",
        table,
        ["activated_by", "idempotency_digest"],
    )
    op.create_unique_constraint(
        "uq_connector_runtime_activations_brokerage_authorization",
        table,
        ["source_brokerage_authorization_id"],
    )
    op.drop_constraint(
        "uq_connector_runtime_activations_activation_attempt",
        table,
        type_="unique",
    )
    op.drop_column(table, "activation_attempt_id")
    op.drop_column(table, "replay_digest")
    op.drop_column(table, "activated_by_digest")
    op.alter_column(
        table,
        "idempotency_digest",
        type_=sa.String(length=128),
        existing_type=sa.String(length=64),
        existing_nullable=False,
    )
    op.alter_column(
        table,
        "idempotency_digest",
        new_column_name="idempotency_key",
    )
