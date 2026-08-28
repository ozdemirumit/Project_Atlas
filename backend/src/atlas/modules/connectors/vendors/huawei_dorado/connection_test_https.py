from __future__ import annotations

import asyncio
import os
import ssl
from collections.abc import Callable, Mapping
from typing import Protocol

from atlas.modules.connectors.application.connection_test_ports import (
    ConnectionProbeOutcome,
    HuaweiConnectionTestTransportFactory,
)
from atlas.modules.connectors.vendors.huawei_dorado.https import HuaweiDoradoHttpsTransport
from atlas.modules.connectors.vendors.huawei_dorado.manifest import PACKAGE_ID
from atlas.modules.connectors.vendors.huawei_dorado.ports import HuaweiTransportError

_SYSTEM_PATH = "/system/"


class HuaweiTlsTrustSource(Protocol):
    def ca_file(self, *, trust_profile_id: str) -> str | os.PathLike[str]: ...


class HuaweiDoradoConnectionTestHttpsFactory:
    def __init__(self, *, trust_source: HuaweiTlsTrustSource | None = None) -> None:
        self._trust_source = trust_source

    def create(
        self,
        *,
        hostname: str,
        port: int,
        system_id: str,
        trust_profile_id: str,
        credential_provider: Callable[[], str],
        timeout_seconds: float,
        maximum_response_bytes: int,
    ) -> HuaweiDoradoHttpsTransport:
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
        return HuaweiDoradoHttpsTransport(
            hostname=hostname,
            port=port,
            system_id=system_id,
            ssl_context=ssl.create_default_context() if use_system_ca else None,
            ca_file=ca_file,
            credential_provider=credential_provider,
            timeout_seconds=timeout_seconds,
            maximum_response_bytes=maximum_response_bytes,
        )


class HuaweiConnectionTestProbe:
    """This vendor's whole connectivity check. Like Brocade SANnav, OceanStor has no confirmed
    dedicated version/compatibility endpoint, so this probe reuses the system-identity read
    itself. Requires `system_id` (see ConnectionTestProbe.probe()'s docstring) since every
    OceanStor request, including this one, is scoped to one exact system."""

    connector_id = PACKAGE_ID

    def __init__(self, *, transport_factory: HuaweiConnectionTestTransportFactory) -> None:
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
        if not system_id:
            return ConnectionProbeOutcome(
                outcome="failed",
                result_code="connection_test_configuration_invalid",
                retryable=False,
                request_performed=False,
                target_contacted=False,
            )
        transport = self._transport_factory.create(
            hostname=hostname,
            port=port,
            system_id=system_id,
            trust_profile_id=trust_profile_id,
            credential_provider=authorization_header_provider,
            timeout_seconds=timeout_seconds,
            maximum_response_bytes=maximum_response_bytes,
        )
        try:
            # Login + read + logout, so the full timeout budget must cover all three.
            async with asyncio.timeout((timeout_seconds * 3) + 1):
                payload = await transport.get(_SYSTEM_PATH)
            data = payload.get("data")
            compatible = isinstance(data, Mapping) and isinstance(data.get("MODEL"), str)
            return ConnectionProbeOutcome(
                outcome="passed" if compatible else "failed",
                result_code="huawei_dorado_api_compatible" if compatible else "product_mismatch",
                retryable=False,
                request_performed=True,
                target_contacted=True,
            )
        except HuaweiTransportError as error:
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
