"""ATLAS-024 SS25: audit, completing Decision Engine.

Maps `DecisionRecord` (slice 8) onto the platform's own `atlas.core.audit.AuditRecord`/
`AuditSink` -- the fifth subsystem this session to record through that primitive rather than a
sixth audit path. `DecisionRecord` already aggregates nearly everything SS25 asks to be
recorded (request, evidence package version, findings/hypotheses/candidate counts, policy
handoffs, review/supersession state, component versions), so one function covers most of SS25; a
second covers sensitive export separately since that is a distinct event in time from decision
creation, not a field on the record itself.
"""

from __future__ import annotations

from datetime import datetime

from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.decision_engine.domain.record import DecisionRecord


async def record_decision(
    sink: AuditSink,
    record: DecisionRecord,
    *,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type=f"atlas.decision_engine.decision.{record.supersession_state.value}",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=record.created_at,
            correlation_id=correlation_id,
            subject_id=record.request.requesting_identity,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="decision_engine.decision",
            scope_reference=record.decision_id,
            decision_id=None,
            outcome=record.supersession_state.value,
            result_code=f"decision.version_{record.version}",
            target_metadata=(
                ("decision_request_id", record.request.request_id),
                ("evidence_package_version", record.evidence_package_version),
                ("finding_count", str(len(record.findings))),
                ("hypothesis_count", str(len(record.hypotheses))),
                ("candidate_count", str(len(record.recommendation_candidates))),
                ("policy_handoff_count", str(len(record.policy_handoffs))),
                ("review_state", record.review_state.value),
                ("model_version", record.component_versions.model_version or ""),
                ("agent_version", record.component_versions.agent_version or ""),
            ),
        )
    )


async def record_sensitive_export(
    sink: AuditSink,
    *,
    decision_id: str,
    exported_by: str,
    export_reference: str,
    occurred_at: datetime,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    """SS25: "sensitive export" -- audited as its own event, separate from decision creation."""
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type="atlas.decision_engine.sensitive_export",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=occurred_at,
            correlation_id=correlation_id,
            subject_id=exported_by,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="decision_engine.decision",
            scope_reference=decision_id,
            decision_id=None,
            outcome="exported",
            result_code="sensitive_export.completed",
            target_metadata=(("export_reference", export_reference),),
        )
    )
