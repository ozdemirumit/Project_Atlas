"""ATLAS-059 SS37: audit, completing Release Process.

SS37 names seventeen distinct release-lifecycle events (plan, scope, candidate creation, evidence,
review, approval, signature, publication, promotion, rollout, rollback, patch, exception,
suspension, recall, deprecation, support-state change) that all share the same audit shape -- a
release reference, an actor, an outcome, and detail references -- so one generic function
parameterized by event kind covers all seventeen, rather than seventeen near-identical functions.
This mirrors `atlas.core.audit.AuditRecord`/`AuditSink` exactly, the eighth subsystem this session
to record through that primitive.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from atlas.core.audit import AuditRecord, AuditSink


class ReleaseAuditEventKind(StrEnum):
    """SS37's seventeen recorded event kinds."""

    RELEASE_PLAN = "release_plan"
    SCOPE = "scope"
    CANDIDATE_CREATION = "candidate_creation"
    EVIDENCE = "evidence"
    REVIEW = "review"
    APPROVAL = "approval"
    SIGNATURE = "signature"
    PUBLICATION = "publication"
    PROMOTION = "promotion"
    ROLLOUT = "rollout"
    ROLLBACK = "rollback"
    PATCH = "patch"
    EXCEPTION = "exception"
    SUSPENSION = "suspension"
    RECALL = "recall"
    DEPRECATION = "deprecation"
    SUPPORT_STATE_CHANGE = "support_state_change"


def release_evidence_preserves_secret_material() -> bool:
    """SS37: "release evidence preserves human and automation identities without secret
    material.\""""
    return False


async def record_release_lifecycle_event(
    sink: AuditSink,
    *,
    event_kind: ReleaseAuditEventKind,
    release_reference: str,
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
            event_type=f"atlas.release.{event_kind.value}",
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
            resource_type="release.lifecycle_event",
            scope_reference=release_reference,
            decision_id=None,
            outcome=outcome,
            result_code=f"release.{event_kind.value}.{outcome}",
            target_metadata=tuple(("detail_reference", ref) for ref in detail_references),
        )
    )
