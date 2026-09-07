"""ATLAS-047 SS30: audit.

SS30 names fifteen distinct guardrail event kinds that all share the same audit shape -- a rule
or incident reference, an actor, an outcome, and detail references -- so one generic function
parameterized by event kind covers all fifteen, mirroring `atlas.core.audit.AuditRecord`/
`AuditSink` exactly, following the same pattern `release.application.audit.record_release_
lifecycle_event` already established for this codebase's other seventeen-event, one-function
audit surface.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from atlas.core.audit import AuditRecord, AuditSink


class GuardrailAuditEventKind(StrEnum):
    """SS30's fifteen recorded event kinds."""

    RULE_VERSION = "rule_version"
    EVALUATION = "evaluation"
    BLOCK = "block"
    WARNING = "warning"
    QUARANTINE = "quarantine"
    REDACTION = "redaction"
    HUMAN_REVIEW = "human_review"
    EXCEPTION = "exception"
    TOOL_DENIAL = "tool_denial"
    MODEL_ENDPOINT_CHOICE = "model_endpoint_choice"
    INJECTION_OR_DLP_SIGNAL = "injection_or_dlp_signal"
    GENERATED_ARTIFACT_CONTROL = "generated_artifact_control"
    CONFIGURATION_CHANGE = "configuration_change"
    FAILURE = "failure"
    INCIDENT = "incident"


def guardrail_audit_data_stores_a_raw_secret_value_or_unsafe_payload() -> bool:
    """SS30: "Audit data does not store detected secret values or unsafe payloads unnecessarily;
    it stores safe references and classifications." `record_guardrail_event` accepts only
    `detail_references` (stable string references) -- there is no field for raw payload content
    to flow through in the first place."""
    return False


async def record_guardrail_event(
    sink: AuditSink,
    *,
    event_kind: GuardrailAuditEventKind,
    rule_or_incident_reference: str,
    actor_identity: str | None,
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
            event_type=f"atlas.guardrails.{event_kind.value}",
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
            resource_type="guardrails.event",
            scope_reference=rule_or_incident_reference,
            decision_id=None,
            outcome=outcome,
            result_code=f"guardrails.{event_kind.value}.{outcome}",
            target_metadata=tuple(("detail_reference", ref) for ref in detail_references),
        )
    )
