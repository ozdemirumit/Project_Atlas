"""Durable local admin login + self-built connector-credential vault (production cutover plan).

Three new tables:

* ``local_credentials`` -- durable storage for
  ``atlas.modules.identity.domain.local_credentials.LocalCredentialRecord`` (ATLAS-030 SS6.3/SS11
  bootstrap-administrator and recovery credentials). Previously only
  ``InMemoryLocalCredentialRepository`` existed, so the admin account did not survive a restart.
* ``local_recovery_activations`` -- durable storage for ``LocalRecoveryActivation``, one row per
  recovery-kind subject.
* ``connector_vault_secrets`` -- pointer rows for a self-built connector-credential vault. Stores
  only which ``protected_content_blobs`` digest (see ``atlas.core.protected_content``, ADR-184) a
  ``secret_reference_id`` currently resolves to -- never the plaintext secret or the encryption
  key. Superseded an earlier plan to use an external HashiCorp Vault; the user chose to build this
  on the already-real ``PostgreSQLProtectedContentStore`` encryption-at-rest primitive instead.

See atlas.modules.identity.adapters.local_credentials_postgres and
atlas.modules.connectors.adapters.vault_secret_postgres for the repositories that make these
tables reachable.

Revision ID: 20260916_0174
Revises: 20260911_0173
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260916_0174"
down_revision: str | None = "20260911_0173"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "local_credentials",
        sa.Column("subject_id", sa.String(128), primary_key=True),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
    )
    op.create_index("ix_local_credentials_organization", "local_credentials", ["organization_id"])
    op.create_table(
        "local_recovery_activations",
        sa.Column("subject_id", sa.String(128), primary_key=True),
        sa.Column("payload", JSONB(), nullable=False),
    )
    op.create_table(
        "connector_vault_secrets",
        sa.Column("organization_id", sa.String(128), primary_key=True),
        sa.Column("environment_id", sa.String(128), primary_key=True),
        sa.Column("secret_reference_id", sa.String(128), primary_key=True),
        sa.Column("protected_content_digest", sa.String(64), nullable=False),
        sa.Column("set_by_subject_digest", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("connector_vault_secrets")
    op.drop_table("local_recovery_activations")
    op.drop_index("ix_local_credentials_organization", table_name="local_credentials")
    op.drop_table("local_credentials")
