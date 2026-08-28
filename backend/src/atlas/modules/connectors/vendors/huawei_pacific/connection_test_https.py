from __future__ import annotations

import asyncio
import os
import ssl
from collections.abc import Callable
from typing import Protocol

from atlas.modules.connectors.application.connection_test_ports import (
    ConnectionProbeOutcome,
    HuaweiPacificConnectionTestTransportFactory,
)
from atlas.modules.connectors.vendors.huawei_pacific.https import HuaweiPacificHttpsTransport
from atlas.modules.connectors.vendors.huawei_pacific.manifest import PACKAGE_ID
from atlas.modules.connectors.vendors.huawei_pacific.ports import HuaweiPacificTransportError

_CLUSTER_SERVERS_PATH = "/api/v2/cluster/servers"


class HuaweiPacificTlsTrustSource(Protocol):
    def ca_file(self, *, trust_profile_id: str) -> str | os.PathLike[str]: ...


class HuaweiPacificConnectionTestHttpsFactory:
    def __init__(self, *, trust_source: HuaweiPacificTlsTrustSource | None = None) -> None:
        self._trust_source = trust_source

    def create(
        self,
        *,
        hostname: str,
        port: int,
        trust_profile_id: str,
        credential_provider: Callable[[], str],
        timeout_seconds: float,
        maximum_response_bytes: int,
    ) -> HuaweiPacificHttpsTransport:
        if not callable(credential_provider):
            raise ValueError("credential provider is invalid")
        use_system_ca = trust_profile_id == "trust.system-ca"
        if not use_system_ca and self._trust_source is None:
            raise ValueError("fixed CA trust profile is unavailable")
        ca_file = None
        if not use_system_ca:
            if self._trust_source is None:
                raise ValueError("fixed CA trust profile is unavailable")
            ca_file = self._trust_source.ca_file(trust_profile_id=trust_profile_id)
        return HuaweiPacificHttpsTransport(
            hostname=hostname,
            port=port,
            ssl_context=ssl.create_default_context() if use_system_ca else None,
            ca_file=ca_file,
            credential_provider=credential_provider,
            timeout_seconds=timeout_seconds,
            maximum_response_bytes=maximum_response_bytes,
        )


class HuaweiPacificConnectionTestProbe:
    """This vendor's whole connectivity check. Like Dorado, Pacific has no confirmed dedicated
    version/compatibility endpoint, so this probe reuses the cluster-node discovery read itself."""

    connector_id = PACKAGE_ID

    def __init__(self, *, transport_factory: HuaweiPacificConnectionTestTransportFactory) -> None:
        self._transport_factory = transport_factory

    async def probe(
        self,
        *,
        hostname: str,
        port: int,
        trust_profile_id: str,
        authorization_header_provider: Callable[[], str],
        timeout_seconds: float,
        maximum_response_bytes: int,
        system_id: str | None = None,
    ) -> ConnectionProbeOutcome:
        del system_id  # Pacific's endpoints carry no per-cluster path segment.
        transport = self._transport_factory.create(
            hostname=hostname,
            port=port,
            trust_profile_id=trust_profile_id,
            credential_provider=authorization_header_provider,
            timeout_seconds=timeout_seconds,
            maximum_response_bytes=maximum_response_bytes,
        )
        try:
            # Login + read + logout, so the full timeout budget must cover all three.
            async with asyncio.timeout((timeout_seconds * 3) + 1):
                payload = await transport.get(_CLUSTER_SERVERS_PATH)
            compatible = isinstance(payload.get("data"), list)
            return ConnectionProbeOutcome(
                outcome="passed" if compatible else "failed",
                result_code="huawei_pacific_api_compatible" if compatible else "product_mismatch",
                retryable=False,
                request_performed=True,
                target_contacted=True,
            )
        except HuaweiPacificTransportError as error:
            return ConnectionProbeOutcome(
                outcome="failed",
                result_code=error.code,
                retryable=error.retryable,
                request_performed=True,
                target_contacted=True,
            )
        except TimeoutError:
            return ConnectionProbeOutcome(
                outcome="failed",
                result_code="target_timeout",
                retryable=True,
                request_performed=True,
                target_contacted=True,
            )
