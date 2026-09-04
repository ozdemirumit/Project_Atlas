"""ATLAS-041 SS26: audit, completing Reasoning.

Maps `ReasoningArtifact` (slice 12) onto the platform's own `atlas.core.audit.AuditRecord`/
`AuditSink` -- the same primitive Policy Engine, Explainability, and Runbook Engine already
record through -- rather than a fifth audit path. `ReasoningArtifact` already aggregates nearly
everything SS26 asks to be recorded (identity, task scope via `frame`, agent/model/prompt
versions via `component_versions`, evidence references, claim/hypothesis counts, stop reason), so
one function covers most of SS26; a second covers human correction separately since that is a
distinct event in time from artifact creation, not a field on the artifact itself.
"""

from __future__ import annotations

from datetime import datetime

from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.reasoning.domain.artifact import ReasoningArtifact


def exact_model_output_reproduction_is_promised() -> bool:
    """SS26: "exact token-for-token model output is not required and must not be falsely
    promised." Always `False`."""
    return False


async def record_reasoning_artifact(
    sink: AuditSink,
    artifact: ReasoningArtifact,
    *,
    tool_call_count: int,
    resulting_decision_references: tuple[str, ...],
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    outcome = artifact.stop_reason.value if artifact.stop_reason is not None else "in_progress"
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type=f"atlas.reasoning.artifact.{outcome}",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=artifact.created_at,
            correlation_id=correlation_id,
            subject_id=None,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="reasoning.artifact",
            scope_reference=artifact.frame.frame_id,
            decision_id=None,
            outcome=outcome,
            result_code=f"reasoning_artifact.version_{artifact.version}",
            reason=artifact.current_conclusion,
            target_metadata=(
                ("evidence_count", str(len(artifact.evidence_inventory))),
                ("claim_count", str(len(artifact.claims))),
                ("hypothesis_count", str(len(artifact.hypotheses))),
                ("tool_call_count", str(tool_call_count)),
                ("agent_version", artifact.component_versions.agent_version or ""),
                ("model_version", artifact.component_versions.model_version or ""),
                ("prompt_version", artifact.component_versions.prompt_version or ""),
                ("resulting_decision_references", ",".join(resulting_decision_references)),
            ),
        )
    )


async def record_human_correction(
    sink: AuditSink,
    *,
    artifact_id: str,
    new_version_id: str,
    corrected_by: str,
    correction_note: str,
    occurred_at: datetime,
    correlation_id: str,
    event_id: str,
    producer: str,
    producer_version: str,
) -> None:
    """SS19/SS26: "human correction creates a new reasoning version" -- audited as its own event
    separate from artifact creation."""
    await sink.record(
        AuditRecord(
            event_id=event_id,
            event_type="atlas.reasoning.human_correction",
            schema_version="1.0",
            producer=producer,
            producer_version=producer_version,
            occurred_at=occurred_at,
            correlation_id=correlation_id,
            subject_id=corrected_by,
            actor_type=None,
            authentication_method=None,
            assurance_level=None,
            permission_id=None,
            resource_type="reasoning.artifact",
            scope_reference=artifact_id,
            decision_id=None,
            outcome="corrected",
            result_code="human_correction.new_version",
            reason=correction_note,
            target_metadata=(("new_version_id", new_version_id),),
        )
    )
