from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol

from atlas.modules.connectors.domain.connection_test import ConnectorConnectionTestResult
from atlas.modules.connectors.vendors.brocade_sannav.ports import BrocadeSanNavTransport
from atlas.modules.connectors.vendors.hitachi_ops_center.ports import HitachiOpsCenterTransport
from atlas.modules.connectors.vendors.huawei_dorado.ports import HuaweiDoradoTransport
from atlas.modules.connectors.vendors.huawei_pacific.ports import HuaweiPacificTransport


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
        # Only meaningful for a vendor whose real API is scoped to one exact target per
        # configured instance (e.g. Huawei OceanStor's system_id); every other probe ignores it.
        system_id: str | None = None,
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


class BrocadeConnectionTestTransportFactory(Protocol):
    def create(
        self,
        *,
        hostname: str,
        port: int,
        trust_profile_id: str,
        authorization_header_provider: Callable[[], str],
        timeout_seconds: float,
        maximum_response_bytes: int,
    ) -> BrocadeSanNavTransport: ...


class HuaweiDoradoConnectionTestTransportFactory(Protocol):
    def create(
        self,
        *,
        hostname: str,
        port: int,
        system_id: str,
        trust_profile_id: str,
        # Returns "username:password", not a pre-built header -- OceanStor's real REST API is
        # session-based (see huawei_dorado/ports.py). The same lease/materializer plumbing used
        # for every other vendor is reused; only the returned string's meaning differs.
        credential_provider: Callable[[], str],
        timeout_seconds: float,
        maximum_response_bytes: int,
    ) -> HuaweiDoradoTransport: ...


class HuaweiPacificConnectionTestTransportFactory(Protocol):
    def create(
        self,
        *,
        hostname: str,
        port: int,
        trust_profile_id: str,
        # Returns "username:password", not a pre-built header -- Pacific's real cluster-manager
        # REST API is session-based (see huawei_pacific/ports.py), same rationale as Dorado. No
        # system_id is needed: Pacific's confirmed endpoints carry no per-cluster path segment.
        credential_provider: Callable[[], str],
        timeout_seconds: float,
        maximum_response_bytes: int,
    ) -> HuaweiPacificTransport: ...
