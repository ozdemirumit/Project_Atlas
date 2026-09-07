"""ATLAS-035 SS19/SS20: detection content and integration lifecycle audit.

Mirrors `atlas.core.audit.AuditRecord`/`AuditSink` exactly, as every other subsystem's generic
lifecycle-event recorder this session does: one function parameterized by event kind rather than
nine near-identical functions for SS19's nine lifecycle stages.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from atlas.core.audit import AuditRecord, AuditSink


class SiemDetectionAuditEventKind(StrEnum):
    DESTINATION_REGISTERED = "destination_registered"
    DESTINATION_CONFIGURED = "destination_configured"
    DESTINATION_VALIDATED = "destination_validated"
    FIXTURES_REPLAYED = "fixtures_replayed"
    DETECTION_VERIFIED = "detection_verified"
    DETECTION_DEPLOYED_TEST_MODE = "detection_deployed_test_mode"
    DETECTION_ACTIVATED_PRODUCTION = "detection_activated_production"
    DETECTION_TUNED = "detection_tuned"
    DETECTION_RETIRED = "detection_retired"
    INCIDENT_HANDOFF = "incident_handoff"


async def record_siem_detection_lifecycle_event(
    sink: AuditSink,
    *,
    event_kind: SiemDetectionAuditEventKind,
    detection_reference: str,
    actor_identity: str,
    is_automation: bool,
    outcome: str,
    detail_references: tuple[str, ...],
    occurred_at: datetime,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type=f"atlas.siem_detection.{event_kind.value}",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=occurred_at,
            correlation_id=correlation_id,
            subject_id=actor_identity,
            actor_type="automation" if is_automation else "human",
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="siem.detection_lifecycle_event",
            scope_reference=detection_reference,
            decision_id=None,
            outcome=outcome,
            result_code=f"siem_detection.{event_kind.value}.{outcome}",
            target_metadata=tuple(("detail_reference", ref) for ref in detail_references),
        )
    )
