from __future__ import annotations

import os
import ssl
from collections.abc import Callable
from typing import Protocol

from atlas.modules.connectors.vendors.hitachi_ops_center.https import (
    HitachiOpsCenterHttpsTransport,
)


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
