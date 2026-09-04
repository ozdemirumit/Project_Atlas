"""ATLAS-044 SS29: audit and reproducibility, completing Change Impact.

`record_impact_result` maps `ImpactResult` (SS22) onto the platform's own `atlas.core.audit.
AuditRecord`/`AuditSink` -- the sixth subsystem this session to record through that primitive.
`ImpactResult` already aggregates nearly everything SS29 asks to be recorded (request/change/plan
versions via `change_request`, snapshot, evidence/method/scenario/estimate/assumption/unknown
counts, validation via the caller's own `ValidationReport`, component versions), so one function
covers most of SS29; `record_human_correction` and `record_recalculation` audit SS27's corrections
and SS25's recalculations as their own events, separate from result creation, matching this
session's established pattern (Reasoning's `record_human_correction`, Decision Engine's
`record_sensitive_export`) of auditing a distinct-in-time event separately from the artifact it
acts on.
"""

from __future__ import annotations

from datetime import datetime

from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.change_impact.domain.itsm_review import HumanCorrection
from atlas.modules.change_impact.domain.result import ImpactResult
from atlas.modules.change_impact.domain.validation_freshness import RecalculationEvent


def exact_reproduction_of_a_live_rerun_is_promised() -> bool:
    """SS29: "reproduction uses immutable snapshot and version references. A live rerun may
    differ and is recorded as a new result." Mirrors Reasoning's and Decision Engine's identically
    purposed function for the same rule, applied to Change Impact's own artifact."""
    return False


async def record_impact_result(
    sink: AuditSink,
    result: ImpactResult,
    *,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type=f"atlas.change_impact.result.{result.supersession_state.value}",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=result.created_at,
            correlation_id=correlation_id,
            subject_id=result.change_request.audience,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="change_impact.impact_result",
            scope_reference=result.result_id,
            decision_id=None,
            outcome=result.supersession_state.value,
            result_code=f"impact_result.version_{result.version}",
            target_metadata=(
                ("change_request_id", result.change_request.request_id),
                ("proposed_change_version", str(result.change_request.proposed_change_version)),
                ("graph_snapshot_id", result.component_versions.graph_snapshot_id),
                ("scenario_count", str(len(result.scenarios))),
                ("unknown_count", str(len(result.unknowns))),
                ("risk_level", result.risk_classification.risk_level.value),
                ("model_version", result.component_versions.model_version or ""),
                ("classification", result.classification.value),
            ),
        )
    )


async def record_human_correction(
    sink: AuditSink,
    correction: HumanCorrection,
    *,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type="atlas.change_impact.human_correction",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=correction.corrected_at,
            correlation_id=correlation_id,
            subject_id=correction.corrected_by,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="change_impact.impact_result",
            scope_reference=correction.impact_result_id,
            decision_id=None,
            outcome="corrected",
            result_code=f"human_correction.{correction.kind.value}",
            target_metadata=(
                ("resulting_impact_result_id", correction.resulting_impact_result_id),
                (
                    "resulting_impact_result_version",
                    str(correction.resulting_impact_result_version),
                ),
            ),
        )
    )


async def record_recalculation(
    sink: AuditSink,
    event: RecalculationEvent,
    *,
    occurred_at: datetime,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type="atlas.change_impact.recalculation",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=occurred_at,
            correlation_id=correlation_id,
            subject_id=None,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="change_impact.impact_result",
            scope_reference=event.impact_result_id,
            decision_id=None,
            outcome="invalidated" if event.is_invalidation else "recalculated",
            result_code=f"recalculation.{event.trigger.value}",
            target_metadata=(("changed_section_count", str(len(event.changed_section_notes))),),
        )
    )
