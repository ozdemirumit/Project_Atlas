from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Protocol

from atlas.modules.connectors.domain.connection_test import ConnectorConnectionTestResult
from atlas.modules.connectors.vendors.hitachi_ops_center.ports import HitachiOpsCenterTransport


class ConnectorConnectionTestError(RuntimeError):
    pass


class ConnectorAuthorizationHeaderLease(Protocol):
    def authorization_header(self) -> str: ...


class ConnectorCredentialMaterializer(Protocol):
    def lease_authorization_header(
        self,
        *,
        secret_reference_id: str,
        maximum_lease_seconds: int,
    ) -> AbstractAsyncContextManager[ConnectorAuthorizationHeaderLease]: ...


class ConnectorConnectionTestResultRepository(Protocol):
    async def put(
        self,
        *,
        organization_id: str,
        environment_id: str,
        result: ConnectorConnectionTestResult,
    ) -> None: ...

    async def get_latest(
        self,
        *,
        organization_id: str,
        environment_id: str,
        instance_id: str,
    ) -> ConnectorConnectionTestResult | None: ...


class HitachiConnectionTestTransportFactory(Protocol):
    def create(
        self,
        *,
        hostname: str,
        port: int,
        trust_profile_id: str,
        authorization_header_provider: Callable[[], str],
        timeout_seconds: float,
        maximum_response_bytes: int,
    ) -> HitachiOpsCenterTransport: ...
