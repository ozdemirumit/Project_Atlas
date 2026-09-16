"""Production cutover plan: durable local admin login (Part A) and self-built
connector-credential vault (Part B), both built on real Postgres persistence.

Proves: `PostgreSQLLocalCredentialRepository` and `PostgreSQLConnectorVaultSecretRepository`
round-trip through a live database (unlike their `InMemory*` counterparts, which only prove
in-process correctness), and that `LocalVaultConnectorCredentialMaterializer` resolves a real
vault-stored secret through the real `PostgreSQLProtectedContentStore` encryption boundary.
"""

from __future__ import annotations

import base64
import os
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import create_async_engine

from atlas.core.persistence.models import (
    ConnectorVaultSecretModel,
    LocalCredentialModel,
    LocalRecoveryActivationModel,
    ProtectedContentBlobModel,
)
from atlas.core.protected_content import PostgreSQLProtectedContentStore
from atlas.modules.connectors.adapters.connection_test_credential_local_vault import (
    LocalVaultConnectorCredentialMaterializer,
)
from atlas.modules.connectors.adapters.vault_secret_postgres import (
    PostgreSQLConnectorVaultSecretRepository,
)
from atlas.modules.connectors.application.connection_test_ports import ConnectorConnectionTestError
from atlas.modules.identity.adapters.local_credentials_postgres import (
    PostgreSQLLocalCredentialRepository,
)
from atlas.modules.identity.domain.local_credentials import (
    LocalCredentialKind,
    LocalCredentialRecord,
    LocalCredentialState,
    LocalRecoveryActivation,
    hash_local_password,
)


@pytest.mark.asyncio
async def test_live_postgres_restores_local_credential_and_recovery_activation() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")

    suffix = uuid4().hex
    subject_id = f"subject.persistence.{suffix}"
    now = datetime.now(UTC)
    engine = create_async_engine(database_url, pool_pre_ping=True)
    repository = PostgreSQLLocalCredentialRepository(engine)
    try:
        record = LocalCredentialRecord(
            subject_id=subject_id,
            kind=LocalCredentialKind.BOOTSTRAP_ADMINISTRATOR,
            organization_id="organization.persistence",
            display_name="Persistence Test Administrator",
            role_ids=("role.platform.bootstrap-setup",),
            password_hash=hash_local_password("a-strong-bootstrap-password"),
            state=LocalCredentialState.MUST_REPLACE,
            version=1,
            created_at=now,
            updated_at=now,
        )
        assert await repository.create(record) is True
        assert await repository.create(record) is False
        assert await repository.get(subject_id) == record

        updated = LocalCredentialRecord(
            subject_id=subject_id,
            kind=record.kind,
            organization_id=record.organization_id,
            display_name=record.display_name,
            role_ids=record.role_ids,
            password_hash=hash_local_password("a-different-strong-password"),
            state=LocalCredentialState.ACTIVE,
            version=2,
            created_at=record.created_at,
            updated_at=now,
        )
        assert await repository.update(updated, expected_version=1) is True
        assert await repository.update(updated, expected_version=1) is False
        assert await repository.get(subject_id) == updated

        assert await repository.get_recovery_activation(subject_id) is None
        activation = LocalRecoveryActivation(
            activation_id=f"activation.{suffix}",
            subject_id=subject_id,
            justification="Persistence round-trip verification.",
            activated_by="subject.persistence.operator",
            activated_at=now,
            expires_at=now + timedelta(hours=1),
        )
        await repository.save_recovery_activation(activation)
        assert await repository.get_recovery_activation(subject_id) == activation

        reviewed = LocalRecoveryActivation(
            activation_id=activation.activation_id,
            subject_id=subject_id,
            justification=activation.justification,
            activated_by=activation.activated_by,
            activated_at=activation.activated_at,
            expires_at=activation.expires_at,
            used_at=now,
            reviewed_at=now,
            reviewed_by="subject.persistence.reviewer",
            review_notes="Reviewed as part of a persistence round-trip test.",
        )
        await repository.save_recovery_activation(reviewed)
        assert await repository.get_recovery_activation(subject_id) == reviewed
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                delete(LocalRecoveryActivationModel).where(
                    LocalRecoveryActivationModel.subject_id == subject_id
                )
            )
            await connection.execute(
                delete(LocalCredentialModel).where(LocalCredentialModel.subject_id == subject_id)
            )
        await engine.dispose()


@pytest.mark.asyncio
async def test_live_postgres_connector_vault_round_trips_through_local_vault_materializer() -> None:
    database_url = os.getenv("ATLAS_TEST_POSTGRES_DSN")
    if not database_url:
        pytest.skip("ATLAS_TEST_POSTGRES_DSN is not configured")

    suffix = uuid4().hex
    organization_id = f"organization.vault-persistence.{suffix}"
    environment_id = "environment.test"
    secret_reference_id = "secret.hitachi.readonly"
    key_b64 = base64.b64encode(secrets.token_bytes(32)).decode("ascii")
    engine = create_async_engine(database_url, pool_pre_ping=True)
    protected_content = PostgreSQLProtectedContentStore(
        engine=engine, key=base64.b64decode(key_b64)
    )
    vault_repository = PostgreSQLConnectorVaultSecretRepository(engine)
    try:
        digest = await protected_content.store(
            organization_id=organization_id,
            environment_id=environment_id,
            content=b"Basic dGVzdDp0ZXN0",
        )
        await vault_repository.upsert(
            organization_id=organization_id,
            environment_id=environment_id,
            secret_reference_id=secret_reference_id,
            protected_content_digest=digest,
            set_by_subject_digest="digest.persistence.operator",
            updated_at=datetime.now(UTC),
        )
        references = await vault_repository.list_references(
            organization_id=organization_id, environment_id=environment_id
        )
        assert [item.secret_reference_id for item in references] == [secret_reference_id]

        materializer = LocalVaultConnectorCredentialMaterializer(
            repository=vault_repository,
            protected_content=protected_content,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        async with materializer.lease_authorization_header(
            secret_reference_id=secret_reference_id, maximum_lease_seconds=30
        ) as lease:
            assert lease.authorization_header() == "Basic dGVzdDp0ZXN0"

        with pytest.raises(ConnectorConnectionTestError):
            async with materializer.lease_authorization_header(
                secret_reference_id="secret.unconfigured.readonly", maximum_lease_seconds=30
            ):
                pass
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                delete(ConnectorVaultSecretModel).where(
                    ConnectorVaultSecretModel.organization_id == organization_id
                )
            )
            await connection.execute(
                delete(ProtectedContentBlobModel).where(
                    ProtectedContentBlobModel.organization_id == organization_id
                )
            )
        await engine.dispose()
