from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from atlas.core.protected_content import ProtectedContentStore
from atlas.modules.connectors.application.connection_test_ports import (
    ConnectorAuthorizationHeaderLease,
    ConnectorConnectionTestError,
)
from atlas.modules.connectors.application.vault_secret import ConnectorVaultSecretRepository


@dataclass(slots=True)
class _VaultAuthorizationHeaderLease(ConnectorAuthorizationHeaderLease):
    _value: str | None = field(repr=False)

    def authorization_header(self) -> str:
        if self._value is None:
            raise ConnectorConnectionTestError("connection_test_credential_lease_closed")
        return self._value

    def close(self) -> None:
        self._value = None


class LocalVaultConnectorCredentialMaterializer:
    """Production-capable `ConnectorCredentialMaterializer` reading from the self-built
    connector-credential vault (see `atlas.modules.connectors.application.vault_secret`), unlike
    `DevelopmentEnvironmentCredentialMaterializer`, which is hard-gated to development and reads
    raw OS environment variables. No vendor transport code changes: every vendor already calls
    only `.authorization_header()`, so the string's meaning (a literal header vs. a
    "username:password" pair a session-based vendor logs in with) is unchanged."""

    def __init__(
        self,
        *,
        repository: ConnectorVaultSecretRepository,
        protected_content: ProtectedContentStore,
        organization_id: str,
        environment_id: str,
    ) -> None:
        self._repository = repository
        self._protected_content = protected_content
        self._organization_id = organization_id
        self._environment_id = environment_id

    @asynccontextmanager
    async def lease_authorization_header(
        self,
        *,
        secret_reference_id: str,
        maximum_lease_seconds: int,
    ) -> AsyncIterator[ConnectorAuthorizationHeaderLease]:
        del maximum_lease_seconds
        digest = await self._repository.get_digest(
            organization_id=self._organization_id,
            environment_id=self._environment_id,
            secret_reference_id=secret_reference_id,
        )
        content = (
            await self._protected_content.retrieve(
                organization_id=self._organization_id,
                environment_id=self._environment_id,
                digest=digest,
            )
            if digest is not None
            else None
        )
        if content is None:
            raise ConnectorConnectionTestError("connection_test_credentials_unavailable")
        lease = _VaultAuthorizationHeaderLease(content.decode("utf-8"))
        try:
            yield lease
        finally:
            lease.close()
