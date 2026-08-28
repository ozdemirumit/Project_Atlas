from __future__ import annotations

import asyncio
import os
import ssl
from collections.abc import Callable
from typing import Protocol

from atlas.modules.connectors.application.connection_test_ports import (
    ConnectionProbeOutcome,
    VCenterConnectionTestTransportFactory,
)
from atlas.modules.connectors.vendors.vcenter.https import VCenterHttpsTransport
from atlas.modules.connectors.vendors.vcenter.manifest import PACKAGE_ID
from atlas.modules.connectors.vendors.vcenter.ports import VCenterTransportError

_HOST_PATH = "/api/vcenter/host"


class VCenterTlsTrustSource(Protocol):
    def ca_file(self, *, trust_profile_id: str) -> str | os.PathLike[str]: ...


class VCenterConnectionTestHttpsFactory:
    def __init__(self, *, trust_source: VCenterTlsTrustSource | None = None) -> None:
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
    ) -> VCenterHttpsTransport:
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
        return VCenterHttpsTransport(
            hostname=hostname,
            port=port,
            ssl_context=ssl.create_default_context() if use_system_ca else None,
            ca_file=ca_file,
            credential_provider=credential_provider,
            timeout_seconds=timeout_seconds,
            maximum_response_bytes=maximum_response_bytes,
        )


class VCenterConnectionTestProbe:
    """This vendor's whole connectivity check. Reuses the host inventory read itself as the
    self-test, the same pattern used for both Huawei connectors -- vCenter has no confirmed
    lighter-weight version/compatibility endpoint independent of the inventory reads this
    connector already performs."""

    connector_id = PACKAGE_ID

    def __init__(self, *, transport_factory: VCenterConnectionTestTransportFactory) -> None:
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
        del system_id  # vCenter's endpoints carry no per-instance path segment.
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
                payload = await transport.get(_HOST_PATH)
            compatible = isinstance(payload, list)
            return ConnectionProbeOutcome(
                outcome="passed" if compatible else "failed",
                result_code="vcenter_api_compatible" if compatible else "product_mismatch",
                retryable=False,
                request_performed=True,
                target_contacted=True,
            )
        except VCenterTransportError as error:
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
