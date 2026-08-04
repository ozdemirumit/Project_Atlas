from __future__ import annotations

from typing import Protocol

from atlas.modules.security_export.domain.models import (
    SyslogDestination,
    SyslogMessage,
    TransportReceipt,
)


class SyslogTransport(Protocol):
    async def send(
        self,
        destination: SyslogDestination,
        message: SyslogMessage,
    ) -> TransportReceipt: ...
