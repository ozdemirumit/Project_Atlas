from __future__ import annotations

import os
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from atlas.modules.connectors.application.connection_test_ports import (
    ConnectorAuthorizationHeaderLease,
    ConnectorConnectionTestError,
)


@dataclass(slots=True)
class _EnvironmentAuthorizationHeaderLease(ConnectorAuthorizationHeaderLease):
    _value: str | None = field(repr=False)

    def authorization_header(self) -> str:
        if self._value is None:
            raise ConnectorConnectionTestError("connection_test_credential_lease_closed")
        return self._value

    def close(self) -> None:
        self._value = None


class DevelopmentEnvironmentCredentialMaterializer:
    def __init__(
        self,
        *,
        deployment_environment: str,
        reference_environment_variables: Mapping[str, str],
    ) -> None:
        self._enabled = deployment_environment == "development"
        self._references = dict(reference_environment_variables)

    @asynccontextmanager
    async def lease_authorization_header(
        self,
        *,
        secret_reference_id: str,
        maximum_lease_seconds: int,
    ) -> AsyncIterator[ConnectorAuthorizationHeaderLease]:
        del maximum_lease_seconds
        if not self._enabled:
            raise ConnectorConnectionTestError("connection_test_credentials_unavailable")
        variable_name = self._references.get(secret_reference_id)
        value = os.environ.get(variable_name, "") if variable_name is not None else ""
        if (
            not value
            or value != value.strip()
            or len(value) > 8_192
            or any(ord(character) < 32 or ord(character) == 127 for character in value)
        ):
            raise ConnectorConnectionTestError("connection_test_credentials_unavailable")
        lease = _EnvironmentAuthorizationHeaderLease(value)
        try:
            yield lease
        finally:
            lease.close()
