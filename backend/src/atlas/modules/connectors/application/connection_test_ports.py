from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol

from atlas.modules.connectors.domain.connection_test import ConnectorConnectionTestResult
from atlas.modules.connectors.vendors.hitachi_ops_center.ports import HitachiOpsCenterTransport


class ConnectorConnectionTestError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ConnectionProbeOutcome:
    """What a single vendor's connectivity probe found. Never raised -- a probe reports failure
    through this outcome rather than propagating a vendor-specific exception, so the generic
    ConnectorConnectionTestService never needs to know any vendor's exception types."""

    outcome: str
    result_code: str
    retryable: bool
    request_performed: bool
    target_contacted: bool


class ConnectionTestProbe(Protocol):
    """One vendor's whole "is this a compatible, reachable target" check: creates its own
    transport and interprets its own vendor-specific response shape. `connector_id` is the
    package id this probe applies to; `ConnectorConnectionTestService` selects a probe by matching
    it against the configuration being tested, so it stays vendor-agnostic itself."""

    connector_id: str

    async def probe(
        self,
        *,
        hostname: str,
        port: int,
        trust_profile_id: str,
        authorization_header_provider: Callable[[], str],
        timeout_seconds: float,
        maximum_response_bytes: int,
    ) -> ConnectionProbeOutcome: ...


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
