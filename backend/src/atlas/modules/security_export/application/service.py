from __future__ import annotations

import asyncio
import base64
import binascii
import hmac
import re
import secrets
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.core.classification import DataClassification
from atlas.modules.security_export.application.ports import SyslogTransport
from atlas.modules.security_export.domain.models import (
    AuditEventPage,
    AuditEventProjection,
    AuditExportOverview,
    AuditRetryResult,
    DeliveryRecord,
    DeliveryState,
    DestinationHealth,
    DestinationState,
    NormalizedSecurityEvent,
    SecurityCategory,
    SecurityExportOverview,
    SecuritySeverity,
    SyslogDestination,
    SyslogMessage,
)

MAPPING_VERSION = "atlas-siem-mapping.v1"
NORMALIZED_SCHEMA_VERSION = "atlas-security-event.v1"
SAFETY_NOTICE = (
    "Transport delivery confirms only Syslog handoff. SIEM ingestion, parsing, correlation, "
    "alerting, ticket creation, and infrastructure action remain unconfirmed and unauthorized."
)
SECRET_VALUE_PATTERN = re.compile(
    r"(?i)(?:password|passwd|secret|token|credential|api[-_]?key)\s*[:=]\s*\S+|bearer\s+\S+"
)
MAX_AUDIT_PAGE_SIZE = 50
MAX_AUDIT_QUERY_LENGTH = 80


@dataclass(frozen=True, slots=True)
class SecurityExportAccessContext:
    subject_id: str
    actor_type: str
    authentication_method: str
    assurance_level: str
    organization_id: str
    environment_id: str
    site_id: str
    resource_id: str
    correlation_id: str
    decision_id: str
    requested_at: datetime


class SecurityExportOperationsError(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class SecurityExportService(AuditSink):
    def __init__(
        self,
        *,
        delegate: AuditSink,
        destinations: tuple[SyslogDestination, ...],
        transport: SyslogTransport,
        environment_id: str,
        site_id: str,
        hostname: str = "atlas-local",
    ) -> None:
        self._delegate = delegate
        self._destinations = {item.destination_id: item for item in destinations}
        self._transport = transport
        self._environment_id = environment_id
        self._site_id = site_id
        self._hostname = hostname
        self._queues: dict[str, list[str]] = {item.destination_id: [] for item in destinations}
        self._deliveries: dict[str, DeliveryRecord] = {}
        self._events: dict[str, NormalizedSecurityEvent] = {}
        self._messages: dict[str, SyslogMessage] = {}
        self._audit_events: list[AuditEventProjection] = []
        self._audit_records: dict[str, AuditRecord] = {}
        self._cursor_key = secrets.token_bytes(32)
        self._delivered_counts: dict[str, int] = {item.destination_id: 0 for item in destinations}
        self._last_handoff: dict[str, datetime | None] = {
            item.destination_id: None for item in destinations
        }
        self._lock = asyncio.Lock()

    async def record(self, event: AuditRecord) -> None:
        async with self._lock:
            existing = self._audit_records.get(event.event_id)
            if existing is not None:
                if existing != event:
                    raise RuntimeError("audit_event_identity_conflict")
                return
            await self._delegate.record(event)
            projection = self._project_audit_event(event, sequence=len(self._audit_events) + 1)
            self._audit_records[event.event_id] = event
            self._audit_events.append(projection)
            try:
                normalized = self._normalize(event)
            except RuntimeError:
                return
            for destination in self._destinations.values():
                if (
                    destination.state is DestinationState.ACTIVE
                    and normalized.category in destination.selected_categories
                    and destination.classification_ceiling.permits(normalized.classification)
                ):
                    try:
                        await self._enqueue_and_deliver(destination, normalized)
                    except RuntimeError:
                        continue

    async def get_overview(
        self,
        *,
        context: SecurityExportAccessContext,
    ) -> SecurityExportOverview:
        self._validate_scope(context)
        await self._record_operation_audit(
            context,
            event_type="atlas.security_export.overview.read",
            result_code="security_export_overview_returned",
        )
        preview_record = self._preview_audit_record(context)
        preview_event = self._normalize(preview_record)
        destination = next(iter(self._destinations.values()))
        preview_message = self._format_syslog(preview_event, destination)
        return SecurityExportOverview(
            generated_at=context.requested_at,
            mapping_version=MAPPING_VERSION,
            normalized_schema_version=NORMALIZED_SCHEMA_VERSION,
            destinations=tuple(self._destinations.values()),
            health=self._health(context.requested_at),
            recent_deliveries=tuple(list(self._deliveries.values())[-20:][::-1]),
            preview_event=preview_event,
            preview_message=preview_message,
            safety_notice=SAFETY_NOTICE,
        )

    async def get_audit_overview(
        self,
        *,
        context: SecurityExportAccessContext,
        limit: int,
        cursor: str | None,
        query: str | None,
        outcome: str | None,
    ) -> AuditExportOverview:
        self._validate_audit_scope(context)
        self._validate_audit_query(limit=limit, query=query, outcome=outcome)
        await self._record_operation_audit(
            context,
            event_type="atlas.audit.inventory.read",
            result_code="bounded_audit_inventory_returned",
            permission_id="audit.read",
            resource_type="resource.audit.events",
        )
        async with self._lock:
            return AuditExportOverview(
                generated_at=context.requested_at,
                page=self._audit_page(
                    context=context,
                    limit=limit,
                    cursor=cursor,
                    query=query,
                    outcome=outcome,
                ),
                health=self._health(context.requested_at),
                recent_deliveries=tuple(list(self._deliveries.values())[-20:][::-1]),
                safety_notice=SAFETY_NOTICE,
            )

    async def retry_audit_deliveries(
        self,
        *,
        context: SecurityExportAccessContext,
    ) -> AuditRetryResult:
        self._validate_audit_scope(context)
        await self._record_operation_audit(
            context,
            event_type="atlas.audit.export.retry",
            result_code="bounded_delivery_retry_requested",
            permission_id="audit.export",
            resource_type="resource.audit.export",
        )
        attempted = 0
        delivered = 0
        retrying = 0
        dead_letter = 0
        async with self._lock:
            for destination_id, queue in self._queues.items():
                destination = self._destinations[destination_id]
                for delivery_id in tuple(queue):
                    attempted += 1
                    await self._deliver(destination, delivery_id, at=context.requested_at)
                    state = self._deliveries[delivery_id].state
                    delivered += state is DeliveryState.TRANSPORT_DELIVERED
                    retrying += state is DeliveryState.RETRYING
                    dead_letter += state is DeliveryState.DEAD_LETTER
                    if state is DeliveryState.RETRYING:
                        break
        return AuditRetryResult(
            attempted=attempted,
            delivered=delivered,
            retrying=retrying,
            dead_letter=dead_letter,
            generated_at=context.requested_at,
        )

    async def emit_test_event(
        self,
        *,
        context: SecurityExportAccessContext,
    ) -> DeliveryRecord:
        self._validate_scope(context)
        event_id = f"evt_{uuid4().hex}"
        await self.record(
            AuditRecord(
                event_id=event_id,
                event_type="atlas.security_export.test_event",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level=context.assurance_level,
                permission_id="security-export.test.create",
                resource_type="resource.security-export",
                scope_reference="/".join(
                    (
                        context.organization_id,
                        context.environment_id,
                        context.site_id,
                        context.resource_id,
                    )
                ),
                decision_id=context.decision_id,
                outcome="succeeded",
                result_code="synthetic_test_event",
            )
        )
        delivery = next(
            (
                item
                for item in reversed(tuple(self._deliveries.values()))
                if item.event_id == event_id
            ),
            None,
        )
        if delivery is None:
            raise SecurityExportOperationsError(
                "security_export_delivery_unavailable",
                "The test event did not enter an authorized destination queue.",
            )
        return delivery

    async def retry_all(self, *, at: datetime) -> None:
        async with self._lock:
            for destination_id, queue in self._queues.items():
                destination = self._destinations[destination_id]
                for delivery_id in tuple(queue):
                    delivery = self._deliveries[delivery_id]
                    if delivery.next_attempt_at is None or delivery.next_attempt_at <= at:
                        await self._deliver(destination, delivery_id, at=at)
                        if self._deliveries[delivery_id].state is DeliveryState.RETRYING:
                            break
                    else:
                        break

    def _audit_page(
        self,
        *,
        context: SecurityExportAccessContext,
        limit: int,
        cursor: str | None,
        query: str | None,
        outcome: str | None,
    ) -> AuditEventPage:
        before_sequence = self._decode_cursor(cursor) if cursor is not None else None
        scope_prefix = (
            "/".join((context.organization_id, context.environment_id, context.site_id)) + "/"
        )
        normalized_query = query.strip().lower() if query else None
        normalized_outcome = outcome.strip().lower() if outcome else None
        matching = []
        for event in reversed(self._audit_events):
            if before_sequence is not None and event.sequence >= before_sequence:
                continue
            if not event.scope_reference.startswith(scope_prefix):
                continue
            if normalized_outcome is not None and event.outcome.lower() != normalized_outcome:
                continue
            if normalized_query is not None and normalized_query not in " ".join(
                value.lower()
                for value in (
                    event.event_id,
                    event.event_type,
                    event.result_code,
                    event.correlation_id,
                    event.subject_id or "",
                    event.target_subject_id or "",
                )
            ):
                continue
            matching.append(event)
            if len(matching) > limit:
                break
        has_more = len(matching) > limit
        events = tuple(matching[:limit])
        next_cursor = self._encode_cursor(events[-1].sequence) if has_more and events else None
        return AuditEventPage(
            events=events,
            limit=limit,
            next_cursor=next_cursor,
            has_more=has_more,
        )

    def _project_audit_event(
        self,
        event: AuditRecord,
        *,
        sequence: int,
    ) -> AuditEventProjection:
        return AuditEventProjection(
            sequence=sequence,
            event_id=self._sanitize(event.event_id, limit=120),
            event_type=self._sanitize(event.event_type, limit=120),
            schema_version=self._sanitize(event.schema_version, limit=20),
            occurred_at=event.occurred_at.astimezone(UTC),
            accepted_at=datetime.now(UTC),
            correlation_id=self._sanitize(event.correlation_id, limit=120),
            subject_id=self._optional(event.subject_id, 120),
            actor_type=self._optional(event.actor_type, 32),
            authentication_method=self._optional(event.authentication_method, 32),
            assurance_level=self._optional(event.assurance_level, 32),
            permission_id=self._optional(event.permission_id, 120),
            resource_type=self._optional(event.resource_type, 120),
            scope_reference=self._optional(event.scope_reference, 512) or "scope.unspecified",
            decision_id=self._optional(event.decision_id, 120),
            outcome=self._sanitize(event.outcome, limit=32),
            result_code=self._sanitize(event.result_code, limit=120),
            target_subject_id=self._optional(event.target_subject_id, 120),
        )

    def _encode_cursor(self, sequence: int) -> str:
        value = f"v1:{sequence}".encode()
        signature = hmac.digest(self._cursor_key, value, "sha256")
        encoded_value = base64.urlsafe_b64encode(value).decode().rstrip("=")
        encoded_signature = base64.urlsafe_b64encode(signature).decode().rstrip("=")
        return f"{encoded_value}.{encoded_signature}"

    def _decode_cursor(self, cursor: str) -> int:
        try:
            encoded_value, encoded_signature = cursor.split(".", maxsplit=1)
            value = base64.urlsafe_b64decode(encoded_value + "=" * (-len(encoded_value) % 4))
            signature = base64.urlsafe_b64decode(
                encoded_signature + "=" * (-len(encoded_signature) % 4)
            )
            if (
                base64.urlsafe_b64encode(value).decode().rstrip("=") != encoded_value
                or base64.urlsafe_b64encode(signature).decode().rstrip("=") != encoded_signature
            ):
                raise ValueError
            if not hmac.compare_digest(signature, hmac.digest(self._cursor_key, value, "sha256")):
                raise ValueError
            version, sequence = value.decode().split(":", maxsplit=1)
            if version != "v1" or int(sequence) < 1:
                raise ValueError
            return int(sequence)
        except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
            raise SecurityExportOperationsError(
                "audit_export_request_invalid",
                "The bounded audit request could not be processed.",
            ) from exc

    async def _enqueue_and_deliver(
        self,
        destination: SyslogDestination,
        event: NormalizedSecurityEvent,
    ) -> None:
        queue = self._queues[destination.destination_id]
        if len(queue) >= destination.max_queue_records:
            raise RuntimeError("security_export_queue_capacity_exceeded")
        message = self._format_syslog(event, destination)
        delivery_id = f"delivery_{uuid4().hex}"
        delivery = DeliveryRecord(
            delivery_id=delivery_id,
            destination_id=destination.destination_id,
            event_id=event.event_id,
            state=DeliveryState.QUEUED,
            attempts=0,
            queued_at=event.occurred_at,
            updated_at=event.occurred_at,
            next_attempt_at=event.occurred_at,
            last_error_code=None,
            receipt=None,
        )
        self._deliveries[delivery_id] = delivery
        self._events[delivery_id] = event
        self._messages[delivery_id] = message
        queue.append(delivery_id)
        if queue[0] == delivery_id:
            await self._deliver(destination, delivery_id, at=event.occurred_at)

    async def _deliver(
        self,
        destination: SyslogDestination,
        delivery_id: str,
        *,
        at: datetime,
    ) -> None:
        delivery = self._deliveries[delivery_id]
        message = self._messages[delivery_id]
        attempts = delivery.attempts + 1
        try:
            receipt = await self._transport.send(destination, message)
        except RuntimeError as exc:
            if attempts >= destination.max_attempts:
                state = DeliveryState.DEAD_LETTER
                next_attempt = None
                self._queues[destination.destination_id].remove(delivery_id)
            else:
                state = DeliveryState.RETRYING
                next_attempt = at + timedelta(seconds=2 ** (attempts - 1))
            self._deliveries[delivery_id] = replace(
                delivery,
                state=state,
                attempts=attempts,
                updated_at=at,
                next_attempt_at=next_attempt,
                last_error_code=self._sanitize(str(exc), limit=80),
            )
            return
        self._queues[destination.destination_id].remove(delivery_id)
        self._deliveries[delivery_id] = replace(
            delivery,
            state=DeliveryState.TRANSPORT_DELIVERED,
            attempts=attempts,
            updated_at=receipt.accepted_at,
            next_attempt_at=None,
            receipt=receipt,
        )
        self._delivered_counts[destination.destination_id] += 1
        self._last_handoff[destination.destination_id] = receipt.accepted_at
        del self._events[delivery_id]
        del self._messages[delivery_id]

    def _normalize(self, event: AuditRecord) -> NormalizedSecurityEvent:
        event_type = self._sanitize(event.event_type, limit=120)
        category = self._category(event_type)
        severity, reason = self._severity(event)
        return NormalizedSecurityEvent(
            event_id=self._sanitize(event.event_id, limit=120),
            event_type=event_type,
            source_schema_version=self._sanitize(event.schema_version, limit=20),
            normalized_schema_version=NORMALIZED_SCHEMA_VERSION,
            occurred_at=event.occurred_at.astimezone(UTC),
            correlation_id=self._sanitize(event.correlation_id, limit=120),
            category=category,
            severity=severity,
            severity_reason=reason,
            producer=self._sanitize(event.producer, limit=48),
            producer_version=self._sanitize(event.producer_version, limit=32),
            environment_id=self._environment_id,
            site_id=self._site_id,
            subject_id=self._optional(event.subject_id, 120),
            actor_type=self._optional(event.actor_type, 32),
            permission_id=self._optional(event.permission_id, 120),
            resource_type=self._optional(event.resource_type, 120),
            sanitized_scope_reference=self._optional(event.scope_reference, 240),
            outcome=self._sanitize(event.outcome, limit=32),
            result_code=self._sanitize(event.result_code, limit=120),
            classification=DataClassification.INTERNAL,
            redaction_state="complete",
            mapping_version=MAPPING_VERSION,
        )

    def _format_syslog(
        self,
        event: NormalizedSecurityEvent,
        destination: SyslogDestination,
    ) -> SyslogMessage:
        severity_code = {
            SecuritySeverity.INFORMATIONAL: 6,
            SecuritySeverity.LOW: 5,
            SecuritySeverity.MEDIUM: 4,
            SecuritySeverity.HIGH: 3,
            SecuritySeverity.CRITICAL: 2,
        }[event.severity]
        priority = destination.facility * 8 + severity_code
        message_id = self._sanitize(event.event_type.upper().replace(".", "_"), limit=32)
        fields = {
            "eventId": event.event_id,
            "eventType": event.event_type,
            "schema": event.normalized_schema_version,
            "correlationId": event.correlation_id,
            "category": event.category.value,
            "severity": event.severity.value,
            "outcome": event.outcome,
            "resultCode": event.result_code,
            "environment": event.environment_id,
            "site": event.site_id,
            "classification": event.classification.value,
            "redaction": event.redaction_state,
            "mapping": event.mapping_version,
        }
        structured = (
            "[atlas@32473 "
            + " ".join(f'{key}="{self._escape_structured(value)}"' for key, value in fields.items())
            + "]"
        )
        summary = self._sanitize(
            f"{event.event_type} completed with {event.outcome} ({event.result_code})",
            limit=240,
        )
        timestamp = event.occurred_at.astimezone(UTC)
        payload = (
            f"<{priority}>1 {timestamp.isoformat().replace('+00:00', 'Z')} "
            f"{self._hostname} atlas - {message_id} {structured} {summary}"
        )
        payload_bytes = len(payload.encode("utf-8"))
        if payload_bytes > 4096:
            raise RuntimeError("security_export_message_size_exceeded")
        return SyslogMessage(
            event_id=event.event_id,
            priority=priority,
            facility=destination.facility,
            severity_code=severity_code,
            timestamp=timestamp,
            hostname=self._hostname,
            app_name="atlas",
            message_id=message_id,
            structured_data=structured,
            summary=summary,
            payload=payload,
            payload_bytes=payload_bytes,
            content_digest=sha256(payload.encode("utf-8")).hexdigest(),
        )

    def _health(self, now: datetime) -> tuple[DestinationHealth, ...]:
        result = []
        for destination in self._destinations.values():
            deliveries = tuple(
                item
                for item in self._deliveries.values()
                if item.destination_id == destination.destination_id
            )
            retrying = sum(item.state is DeliveryState.RETRYING for item in deliveries)
            dead = sum(item.state is DeliveryState.DEAD_LETTER for item in deliveries)
            days = (destination.certificate_not_after - now).days
            state = (
                DestinationState.DEGRADED if retrying or dead or days < 30 else destination.state
            )
            result.append(
                DestinationHealth(
                    destination_id=destination.destination_id,
                    state=state,
                    queue_depth=len(self._queues[destination.destination_id]),
                    delivered_count=self._delivered_counts[destination.destination_id],
                    retrying_count=retrying,
                    dead_letter_count=dead,
                    certificate_days_remaining=max(days, 0),
                    last_transport_handoff_at=self._last_handoff[destination.destination_id],
                    collector_acknowledgement_available=True,
                    siem_ingestion_confirmed=False,
                    limitations=(
                        "Transport handoff does not prove SIEM ingestion or parsing.",
                        "The synthetic collector does not provide correlation acknowledgement.",
                    ),
                )
            )
        return tuple(result)

    @staticmethod
    def _category(event_type: str) -> SecurityCategory:
        if any(token in event_type for token in ("auth", "security", "guardrail")):
            return SecurityCategory.SECURITY
        if any(token in event_type for token in ("platform", "health", "deployment")):
            return SecurityCategory.PLATFORM
        return SecurityCategory.AUDIT

    @staticmethod
    def _severity(event: AuditRecord) -> tuple[SecuritySeverity, str]:
        combined = f"{event.event_type} {event.result_code}".lower()
        if "integrity" in combined or "control_bypass" in combined:
            return SecuritySeverity.CRITICAL, "audit or security-control integrity condition"
        if event.outcome.lower() in {"denied", "failed", "error"}:
            return SecuritySeverity.HIGH, "protected operation did not succeed"
        return SecuritySeverity.INFORMATIONAL, "expected governed lifecycle activity"

    @staticmethod
    def _escape_structured(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"').replace("]", "\\]")

    @staticmethod
    def _sanitize(value: str, *, limit: int) -> str:
        cleaned = "".join(character if 32 <= ord(character) < 127 else " " for character in value)
        cleaned = " ".join(cleaned.split())
        if SECRET_VALUE_PATTERN.search(cleaned):
            return "redacted"
        return cleaned[:limit] or "unknown"

    def _optional(self, value: str | None, limit: int) -> str | None:
        return None if value is None else self._sanitize(value, limit=limit)

    @staticmethod
    def _validate_scope(context: SecurityExportAccessContext) -> None:
        if context.resource_id != "resource.security-export.synthetic":
            raise SecurityExportOperationsError(
                "security_export_scope_mismatch",
                "The security-export destination is outside the authorized scope.",
            )

    @staticmethod
    def _validate_audit_scope(context: SecurityExportAccessContext) -> None:
        if context.resource_id != "resource.audit.enterprise-events":
            raise SecurityExportOperationsError(
                "audit_export_scope_mismatch",
                "The audit inventory is outside the authorized scope.",
            )

    @staticmethod
    def _validate_audit_query(
        *,
        limit: int,
        query: str | None,
        outcome: str | None,
    ) -> None:
        if not 1 <= limit <= MAX_AUDIT_PAGE_SIZE:
            raise SecurityExportOperationsError(
                "audit_export_request_invalid",
                "The bounded audit request could not be processed.",
            )
        for value in (query, outcome):
            if value is not None and (
                not value.strip()
                or len(value) > MAX_AUDIT_QUERY_LENGTH
                or any(ord(character) < 32 for character in value)
            ):
                raise SecurityExportOperationsError(
                    "audit_export_request_invalid",
                    "The bounded audit request could not be processed.",
                )

    async def _record_operation_audit(
        self,
        context: SecurityExportAccessContext,
        *,
        event_type: str,
        result_code: str,
        permission_id: str = "security-export.overview.read",
        resource_type: str = "resource.security-export",
    ) -> None:
        await self.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type=event_type,
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=context.requested_at,
                correlation_id=context.correlation_id,
                subject_id=context.subject_id,
                actor_type=context.actor_type,
                authentication_method=context.authentication_method,
                assurance_level=context.assurance_level,
                permission_id=permission_id,
                resource_type=resource_type,
                scope_reference="/".join(
                    (
                        context.organization_id,
                        context.environment_id,
                        context.site_id,
                        context.resource_id,
                    )
                ),
                decision_id=context.decision_id,
                outcome="succeeded",
                result_code=result_code,
            )
        )

    @staticmethod
    def _preview_audit_record(context: SecurityExportAccessContext) -> AuditRecord:
        return AuditRecord(
            event_id="evt_preview_security_export",
            event_type="atlas.authorization.decision",
            schema_version="1.0",
            producer="project-atlas-api",
            producer_version=__version__,
            occurred_at=context.requested_at,
            correlation_id=context.correlation_id,
            subject_id=context.subject_id,
            actor_type=context.actor_type,
            authentication_method=context.authentication_method,
            assurance_level=context.assurance_level,
            permission_id="security-export.overview.read",
            resource_type="resource.security-export",
            scope_reference=context.resource_id,
            decision_id=context.decision_id,
            outcome="succeeded",
            result_code="preview_only_not_dispatched",
        )
