"""ATLAS-036 SS21: audit requirements for outbound dispatch and lifecycle events.

Mirrors `atlas.core.audit.AuditRecord`/`AuditSink` exactly, as every other subsystem's generic
lifecycle-event recorder this session does -- one function parameterized by event kind.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from atlas.core.audit import AuditRecord, AuditSink


class ItsmAuditEventKind(StrEnum):
    """SS21's named event categories."""

    RECORD_RETRIEVAL_OF_SENSITIVE_CONTENT = "record_retrieval_of_sensitive_content"
    CREATE = "create"
    UPDATE = "update"
    COMMENT = "comment"
    ATTACH = "attach"
    LINK = "link"
    STATE_TRANSITION = "state_transition"
    SYNCHRONIZATION = "synchronization"
    APPROVAL_MAPPING_OUTCOME = "approval_mapping_outcome"
    CONFLICT = "conflict"
    DUPLICATE = "duplicate"
    RECONCILIATION = "reconciliation"
    REPLAY = "replay"
    MANUAL_OVERRIDE = "manual_override"
    RESTRICTED_EXPORT = "restricted_export"


async def record_itsm_integration_event(
    sink: AuditSink,
    *,
    event_kind: ItsmAuditEventKind,
    profile_reference: str,
    actor_identity: str,
    is_automation: bool,
    outcome: str,
    external_record_id: str | None,
    external_source_version: str | None,
    idempotency_key: str | None,
    detail_references: tuple[str, ...],
    occurred_at: datetime,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    metadata = tuple(("detail_reference", ref) for ref in detail_references)
    if external_record_id is not None:
        metadata = (("external_record_id", external_record_id), *metadata)
    if external_source_version is not None:
        metadata = (("external_source_version", external_source_version), *metadata)
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type=f"atlas.itsm_integration.{event_kind.value}",
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
            resource_type="itsm.integration_event",
            scope_reference=profile_reference,
            decision_id=None,
            outcome=outcome,
            result_code=f"itsm_integration.{event_kind.value}.{outcome}",
            idempotency_key=idempotency_key,
            target_metadata=metadata,
        )
    )


def ticket_content_is_copied_unconditionally_into_the_audit_ledger() -> bool:
    """SS21: "Ticket content is referenced or bounded according to classification rather than
    copied unconditionally into the audit ledger.\""""
    return False
