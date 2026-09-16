from __future__ import annotations

import asyncio
from datetime import datetime

from atlas.modules.connectors.domain.vault_secret import ConnectorVaultSecretReference


class InMemoryConnectorVaultSecretRepository:
    """Process-local development/test vault pointer store. Never used in production -- see
    `PostgreSQLConnectorVaultSecretRepository`."""

    def __init__(self) -> None:
        self._digests: dict[tuple[str, str, str], str] = {}
        self._set_by: dict[tuple[str, str, str], str] = {}
        self._updated_at: dict[tuple[str, str, str], datetime] = {}
        self._lock = asyncio.Lock()

    async def get_digest(
        self, *, organization_id: str, environment_id: str, secret_reference_id: str
    ) -> str | None:
        async with self._lock:
            return self._digests.get((organization_id, environment_id, secret_reference_id))

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
        key = (organization_id, environment_id, secret_reference_id)
        async with self._lock:
            self._digests[key] = protected_content_digest
            self._set_by[key] = set_by_subject_digest
            self._updated_at[key] = updated_at

    async def list_references(
        self, *, organization_id: str, environment_id: str
    ) -> list[ConnectorVaultSecretReference]:
        async with self._lock:
            return [
                ConnectorVaultSecretReference(
                    secret_reference_id=key[2],
                    updated_at=self._updated_at[key],
                    set_by_subject_digest=self._set_by[key],
                )
                for key in self._digests
                if key[0] == organization_id and key[1] == environment_id
            ]
