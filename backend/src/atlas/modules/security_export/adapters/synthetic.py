from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from atlas.core.classification import DataClassification
from atlas.modules.security_export.domain.models import (
    DestinationState,
    SecurityCategory,
    SyslogDestination,
    SyslogMessage,
    TransportProfile,
    TransportReceipt,
)


def build_synthetic_syslog_destinations() -> tuple[SyslogDestination, ...]:
    return (
        SyslogDestination(
            destination_id="destination.syslog.synthetic-siem",
            version=1,
            name="Enterprise SIEM synthetic TLS collector",
            state=DestinationState.ACTIVE,
            transport=TransportProfile.TLS,
            host="siem-collector.synthetic.local",
            port=6514,
            tls_server_authentication=True,
            tls_hostname_validation=True,
            certificate_not_after=datetime.now(UTC) + timedelta(days=90),
            facility=16,
            selected_categories=(
                SecurityCategory.AUDIT,
                SecurityCategory.SECURITY,
                SecurityCategory.PLATFORM,
            ),
            classification_ceiling=DataClassification.INTERNAL,
            max_queue_records=100,
            max_attempts=3,
        ),
    )


class SyntheticTlsSyslogTransport:
    def __init__(self, *, fail_attempts: int = 0) -> None:
        self._remaining_failures = fail_attempts
        self.messages: list[SyslogMessage] = []

    async def send(
        self,
        destination: SyslogDestination,
        message: SyslogMessage,
    ) -> TransportReceipt:
        now = datetime.now(UTC)
        if (
            destination.transport is not TransportProfile.TLS
            or not destination.tls_server_authentication
            or not destination.tls_hostname_validation
            or destination.certificate_not_after <= now
        ):
            raise RuntimeError("tls_destination_validation_failed")
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise RuntimeError("synthetic_transport_unavailable")
        self.messages.append(message)
        return TransportReceipt(
            receipt_id=f"receipt_{uuid4().hex}",
            destination_id=destination.destination_id,
            event_id=message.event_id,
            accepted_at=now,
            transport=TransportProfile.TLS,
            collector_acknowledged=True,
            siem_ingestion_confirmed=False,
        )
