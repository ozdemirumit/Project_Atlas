from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.core.classification import DataClassification


class SecurityCategory(StrEnum):
    AUDIT = "audit"
    SECURITY = "security"
    PLATFORM = "platform"


class SecuritySeverity(StrEnum):
    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TransportProfile(StrEnum):
    TLS = "tls"


class DestinationState(StrEnum):
    ACTIVE = "active"
    DEGRADED = "degraded"
    DISABLED = "disabled"


class DeliveryState(StrEnum):
    QUEUED = "queued"
    RETRYING = "retrying"
    TRANSPORT_DELIVERED = "transport_delivered"
    DEAD_LETTER = "dead_letter"


@dataclass(frozen=True, slots=True)
class NormalizedSecurityEvent:
    event_id: str
    event_type: str
    source_schema_version: str
    normalized_schema_version: str
    occurred_at: datetime
    correlation_id: str
    category: SecurityCategory
    severity: SecuritySeverity
    severity_reason: str
    producer: str
    producer_version: str
    environment_id: str
    site_id: str
    subject_id: str | None
    actor_type: str | None
    permission_id: str | None
    resource_type: str | None
    sanitized_scope_reference: str | None
    outcome: str
    result_code: str
    classification: DataClassification
    redaction_state: str
    mapping_version: str

    def __post_init__(self) -> None:
        if self.occurred_at.tzinfo is None:
            raise ValueError("security-event time must be timezone-aware")
        if self.redaction_state != "complete":
            raise ValueError("security events must be redacted before export")
        if not all(
            value.strip()
            for value in (
                self.event_id,
                self.event_type,
                self.normalized_schema_version,
                self.correlation_id,
                self.mapping_version,
            )
        ):
            raise ValueError("security-event identity fields are required")


@dataclass(frozen=True, slots=True)
class SyslogMessage:
    event_id: str
    priority: int
    facility: int
    severity_code: int
    timestamp: datetime
    hostname: str
    app_name: str
    message_id: str
    structured_data: str
    summary: str
    payload: str
    payload_bytes: int
    content_digest: str

    def __post_init__(self) -> None:
        if self.timestamp.tzinfo is None or not 0 <= self.priority <= 191:
            raise ValueError("invalid Syslog header")
        if self.payload_bytes != len(self.payload.encode("utf-8")) or self.payload_bytes > 4096:
            raise ValueError("invalid Syslog payload size")
        if "\n" in self.payload or "\r" in self.payload:
            raise ValueError("Syslog payload must be one framed record")
        if len(self.content_digest) != 64:
            raise ValueError("Syslog payload requires a SHA-256 digest")


@dataclass(frozen=True, slots=True)
class SyslogDestination:
    destination_id: str
    version: int
    name: str
    state: DestinationState
    transport: TransportProfile
    host: str
    port: int
    tls_server_authentication: bool
    tls_hostname_validation: bool
    trust_reference_id: str
    client_identity_secret_reference_id: str | None
    certificate_not_after: datetime
    facility: int
    selected_categories: tuple[SecurityCategory, ...]
    classification_ceiling: DataClassification
    max_queue_records: int
    max_attempts: int

    def __post_init__(self) -> None:
        if self.version < 1 or self.transport is not TransportProfile.TLS:
            raise ValueError("the MVP destination must be versioned and TLS-only")
        if not self.tls_server_authentication or not self.tls_hostname_validation:
            raise ValueError("TLS server and hostname validation are mandatory")
        if not self.trust_reference_id.startswith("trust."):
            raise ValueError("a non-secret trust reference is required")
        if (
            self.client_identity_secret_reference_id is not None
            and not self.client_identity_secret_reference_id.startswith("secret.")
        ):
            raise ValueError("client identity must be an opaque secret reference")
        if self.certificate_not_after.tzinfo is None:
            raise ValueError("certificate expiry must be timezone-aware")
        if not 1 <= self.port <= 65535 or not 1 <= self.max_queue_records <= 1000:
            raise ValueError("invalid destination bounds")
        if not 1 <= self.max_attempts <= 10:
            raise ValueError("invalid delivery attempt bound")


@dataclass(frozen=True, slots=True)
class TransportReceipt:
    receipt_id: str
    destination_id: str
    event_id: str
    accepted_at: datetime
    transport: TransportProfile
    collector_acknowledged: bool
    siem_ingestion_confirmed: bool

    def __post_init__(self) -> None:
        if self.accepted_at.tzinfo is None or self.siem_ingestion_confirmed:
            raise ValueError("transport receipt cannot confirm SIEM ingestion")


@dataclass(frozen=True, slots=True)
class DeliveryRecord:
    delivery_id: str
    destination_id: str
    event_id: str
    state: DeliveryState
    attempts: int
    queued_at: datetime
    updated_at: datetime
    next_attempt_at: datetime | None
    last_error_code: str | None
    receipt: TransportReceipt | None


@dataclass(frozen=True, slots=True)
class DestinationHealth:
    destination_id: str
    state: DestinationState
    queue_depth: int
    delivered_count: int
    retrying_count: int
    dead_letter_count: int
    certificate_days_remaining: int
    last_transport_handoff_at: datetime | None
    collector_acknowledgement_available: bool
    siem_ingestion_confirmed: bool
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SecurityExportOverview:
    generated_at: datetime
    mapping_version: str
    normalized_schema_version: str
    destinations: tuple[SyslogDestination, ...]
    health: tuple[DestinationHealth, ...]
    recent_deliveries: tuple[DeliveryRecord, ...]
    preview_event: NormalizedSecurityEvent
    preview_message: SyslogMessage
    safety_notice: str


@dataclass(frozen=True, slots=True)
class AuditEventProjection:
    sequence: int
    event_id: str
    event_type: str
    schema_version: str
    occurred_at: datetime
    accepted_at: datetime
    correlation_id: str
    subject_id: str | None
    actor_type: str | None
    authentication_method: str | None
    assurance_level: str | None
    permission_id: str | None
    resource_type: str | None
    scope_reference: str
    decision_id: str | None
    outcome: str
    result_code: str
    target_subject_id: str | None

    def __post_init__(self) -> None:
        if self.sequence < 1:
            raise ValueError("audit sequence must be positive")
        if self.occurred_at.tzinfo is None or self.accepted_at.tzinfo is None:
            raise ValueError("audit event times must be timezone-aware")


@dataclass(frozen=True, slots=True)
class AuditEventPage:
    events: tuple[AuditEventProjection, ...]
    limit: int
    next_cursor: str | None
    has_more: bool


@dataclass(frozen=True, slots=True)
class AuditExportOverview:
    generated_at: datetime
    page: AuditEventPage
    health: tuple[DestinationHealth, ...]
    recent_deliveries: tuple[DeliveryRecord, ...]
    safety_notice: str


@dataclass(frozen=True, slots=True)
class AuditRetryResult:
    attempted: int
    delivered: int
    retrying: int
    dead_letter: int
    generated_at: datetime
