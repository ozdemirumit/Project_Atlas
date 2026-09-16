from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorVaultSecretModel
from atlas.modules.connectors.domain.vault_secret import ConnectorVaultSecretReference


class PostgreSQLConnectorVaultSecretRepository:
    """Pointer-row repository for the self-built connector-credential vault (see
    `atlas.core.protected_content` for the actual AES-256-GCM encrypted-content-at-rest boundary
    this points into). Never sees the plaintext secret or the encryption key -- only a digest."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLConnectorVaultSecretRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    async def get_digest(
        self, *, organization_id: str, environment_id: str, secret_reference_id: str
    ) -> str | None:
        async with self._sessions() as session:
            row = await session.get(
                ConnectorVaultSecretModel,
                (organization_id, environment_id, secret_reference_id),
            )
            return row.protected_content_digest if row is not None else None

    async def upsert(
        self,
        *,
        organization_id: str,
        environment_id: str,
        secret_reference_id: str,
        protected_content_digest: str,
        set_by_subject_digest: str,
        updated_at: datetime,
    ) -> None:
        statement = pg_insert(ConnectorVaultSecretModel).values(
            organization_id=organization_id,
            environment_id=environment_id,
            secret_reference_id=secret_reference_id,
            protected_content_digest=protected_content_digest,
            set_by_subject_digest=set_by_subject_digest,
            updated_at=updated_at,
        )
        statement = statement.on_conflict_do_update(
            index_elements=["organization_id", "environment_id", "secret_reference_id"],
            set_={
                "protected_content_digest": statement.excluded.protected_content_digest,
                "set_by_subject_digest": statement.excluded.set_by_subject_digest,
                "updated_at": statement.excluded.updated_at,
            },
        )
        async with self._sessions.begin() as session:
            await session.execute(statement)

    async def list_references(
        self, *, organization_id: str, environment_id: str
    ) -> list[ConnectorVaultSecretReference]:
        async with self._sessions() as session:
            rows = await session.scalars(
                select(ConnectorVaultSecretModel).where(
                    ConnectorVaultSecretModel.organization_id == organization_id,
                    ConnectorVaultSecretModel.environment_id == environment_id,
                )
            )
            return [
                ConnectorVaultSecretReference(
                    secret_reference_id=row.secret_reference_id,
                    updated_at=row.updated_at,
                    set_by_subject_digest=row.set_by_subject_digest,
                )
                for row in rows
            ]

    async def close(self) -> None:
        await self._engine.dispose()
