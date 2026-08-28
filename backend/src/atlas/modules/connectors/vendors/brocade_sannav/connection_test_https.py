from __future__ import annotations

import asyncio
import os
import ssl
from collections.abc import Callable
from typing import Protocol

from atlas.modules.connectors.application.connection_test_ports import (
    BrocadeConnectionTestTransportFactory,
    ConnectionProbeOutcome,
)
from atlas.modules.connectors.vendors.brocade_sannav.https import BrocadeSanNavHttpsTransport
from atlas.modules.connectors.vendors.brocade_sannav.manifest import PACKAGE_ID
from atlas.modules.connectors.vendors.brocade_sannav.ports import BrocadeTransportError

_FABRIC_DISCOVERY_PATH = "/external-api/v1/discovery/fabrics/"


class BrocadeTlsTrustSource(Protocol):
    def ca_file(self, *, trust_profile_id: str) -> str | os.PathLike[str]: ...


class BrocadeSanNavConnectionTestHttpsFactory:
    def __init__(self, *, trust_source: BrocadeTlsTrustSource | None = None) -> None:
        self._trust_source = trust_source

    def create(
        self,
        *,
        hostname: str,
        port: int,
        trust_profile_id: str,
        authorization_header_provider: Callable[[], str],
        timeout_seconds: float,
        maximum_response_bytes: int,
    ) -> BrocadeSanNavHttpsTransport:
        if not callable(authorization_header_provider):
            raise ValueError("authorization header provider is invalid")
        use_system_ca = trust_profile_id == "trust.system-ca"
        if not use_system_ca and self._trust_source is None:
            raise ValueError("fixed CA trust profile is unavailable")
        ca_file = None
        if not use_system_ca:
            if self._trust_source is None:
                raise ValueError("fixed CA trust profile is unavailable")
            ca_file = self._trust_source.ca_file(trust_profile_id=trust_profile_id)
        return BrocadeSanNavHttpsTransport(
            hostname=hostname,
            port=port,
            ssl_context=ssl.create_default_context() if use_system_ca else None,
            ca_file=ca_file,
            authorization_header_provider=authorization_header_provider,
            timeout_seconds=timeout_seconds,
            maximum_response_bytes=maximum_response_bytes,
        )


class BrocadeConnectionTestProbe:
    """This vendor's whole connectivity check. SANnav has no confirmed dedicated
    version/compatibility endpoint (see source-provenance.json), so this probe reuses the
    fabric-discovery read itself, exactly as BrocadeSanNavClient.self_test() does, and confirms
    the response is a well-formed fabric-discovery envelope. Never raises -- always returns a
    ConnectionProbeOutcome, matching every other connector's probe."""

    connector_id = PACKAGE_ID

    def __init__(self, *, transport_factory: BrocadeConnectionTestTransportFactory) -> None:
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
    ) -> ConnectionProbeOutcome:
        transport = self._transport_factory.create(
            hostname=hostname,
            port=port,
            trust_profile_id=trust_profile_id,
            authorization_header_provider=authorization_header_provider,
            timeout_seconds=timeout_seconds,
            maximum_response_bytes=maximum_response_bytes,
        )
        try:
            async with asyncio.timeout(timeout_seconds + 1):
                payload = await transport.get(_FABRIC_DISCOVERY_PATH)
            result_code = (
                "sannav_api_compatible"
                if isinstance(payload.get("Fabrics"), list)
                else ("product_mismatch")
            )
            return ConnectionProbeOutcome(
                outcome="passed" if result_code == "sannav_api_compatible" else "failed",
                result_code=result_code,
                retryable=False,
                request_performed=True,
                target_contacted=True,
            )
        except BrocadeTransportError as error:
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
