from __future__ import annotations

import asyncio
import os
import re
import ssl
from collections.abc import Callable, Mapping
from typing import Protocol

from atlas.modules.connectors.application.connection_test_ports import (
    ConnectionProbeOutcome,
    HitachiConnectionTestTransportFactory,
)
from atlas.modules.connectors.vendors.hitachi_ops_center.https import (
    HitachiOpsCenterHttpsTransport,
)
from atlas.modules.connectors.vendors.hitachi_ops_center.manifest import PACKAGE_ID
from atlas.modules.connectors.vendors.hitachi_ops_center.ports import HitachiTransportError

_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


class HitachiTlsTrustSource(Protocol):
    def ca_file(self, *, trust_profile_id: str) -> str | os.PathLike[str]: ...


class HitachiOpsCenterConnectionTestHttpsFactory:
    def __init__(self, *, trust_source: HitachiTlsTrustSource | None = None) -> None:
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
    ) -> HitachiOpsCenterHttpsTransport:
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
        return HitachiOpsCenterHttpsTransport(
            hostname=hostname,
            port=port,
            ssl_context=ssl.create_default_context() if use_system_ca else None,
            ca_file=ca_file,
            authorization_header_provider=authorization_header_provider,
            timeout_seconds=timeout_seconds,
            maximum_response_bytes=maximum_response_bytes,
        )


class HitachiConnectionTestProbe:
    """This vendor's whole connectivity check: create a transport, GET the version endpoint, and
    confirm the response identifies a compatible Configuration Manager REST API instance. Never
    raises -- always returns a ConnectionProbeOutcome, matching every other connector's probe."""

    connector_id = PACKAGE_ID

    def __init__(self, *, transport_factory: HitachiConnectionTestTransportFactory) -> None:
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
        del system_id  # Hitachi's Configuration Manager is not scoped to one target per instance.
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
                payload = await transport.get("/configuration/version")
            result_code = self._version_result(payload)
            outcome = "passed" if result_code == "hitachi_api_compatible" else "failed"
            return ConnectionProbeOutcome(
                outcome=outcome,
                result_code=result_code,
                retryable=False,
                request_performed=True,
                target_contacted=True,
            )
        except HitachiTransportError as error:
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

    @staticmethod
    def _version_result(payload: Mapping[str, object]) -> str:
        if payload.get("productName") != "Configuration Manager REST API":
            return "product_mismatch"
        version = payload.get("apiVersion")
        if not isinstance(version, str) or _VERSION.fullmatch(version) is None:
            return "unsupported_vendor_version"
        return "hitachi_api_compatible"
