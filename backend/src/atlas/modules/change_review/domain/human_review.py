from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

STABLE_ID = re.compile(r"^[a-z][a-z0-9_.:-]{2,127}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")


class HumanReviewState(StrEnum):
    PENDING = "pending"
    NEEDS_EVIDENCE = "needs_evidence"
    DEFERRED = "deferred"
    REJECTED = "rejected"
    COMPLETED = "completed"
    EXPIRED = "expired"


class HumanReviewStageState(StrEnum):
    WAITING = "waiting"
    PENDING = "pending"
    APPROVED = "approved"
    NEEDS_EVIDENCE = "needs_evidence"
    DEFERRED = "deferred"
    REJECTED = "rejected"


class HumanReviewOutcome(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    NEEDS_EVIDENCE = "needs_evidence"
    DEFER = "defer"


@dataclass(frozen=True, slots=True)
class HumanReviewStage:
    stage_id: str
    sequence: int
    required_role_id: str
    quorum: int
    state: HumanReviewStageState
    packet_digest: str
    reviewer_id: str | None = None
    decision_id: str | None = None
    decided_at: datetime | None = None
    rationale: str | None = None

    def __post_init__(self) -> None:
        if (
            STABLE_ID.fullmatch(self.stage_id) is None
            or STABLE_ID.fullmatch(self.required_role_id) is None
            or SHA256.fullmatch(self.packet_digest) is None
            or self.sequence < 1
            or self.quorum != 1
        ):
            raise ValueError("human review stage is invalid")
        decision_values = (self.reviewer_id, self.decision_id, self.decided_at, self.rationale)
        if self.state in {HumanReviewStageState.WAITING, HumanReviewStageState.PENDING}:
            if any(value is not None for value in decision_values):
                raise ValueError("undecided human review stage contains a decision")
        elif any(value is None for value in decision_values):
            raise ValueError("decided human review stage is incomplete")


@dataclass(frozen=True, slots=True)
class HumanReviewDecision:
    decision_id: str
    stage_id: str
    request_version: int
    outcome: HumanReviewOutcome
    reviewer_id: str
    reviewer_role_id: str
    rationale: str
    acknowledged_no_authority: bool
    idempotency_key: str
    request_fingerprint: str
    decided_at: datetime

    def __post_init__(self) -> None:
        identifiers = (self.decision_id, self.stage_id, self.reviewer_id, self.reviewer_role_id)
        if any(STABLE_ID.fullmatch(value) is None for value in identifiers):
            raise ValueError("human review decision identifier is invalid")
        if (
            self.request_version < 1
            or not 5 <= len(self.rationale.strip()) <= 1000
            or not 8 <= len(self.idempotency_key) <= 128
            or SHA256.fullmatch(self.request_fingerprint) is None
            or self.decided_at.tzinfo is None
        ):
            raise ValueError("human review decision is invalid")


@dataclass(frozen=True, slots=True)
class UpgradeChangeHumanReview:
    review_id: str
    schema_version: str
    version: int
    state: HumanReviewState
    packet_id: str
    packet_digest: str
    requester_id: str
    organization_id: str
    environment_id: str
    site_id: str
    risk_class: str
    change_class: str
    impacted_service_ids: tuple[str, ...]
    evidence_digests: tuple[str, ...]
    proposed_window_start: datetime
    proposed_window_end: datetime
    justification: str
    required_role_ids: tuple[str, ...]
    stages: tuple[HumanReviewStage, ...]
    decisions: tuple[HumanReviewDecision, ...]
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    reused: bool = False
    human_review_completed: bool = False
    approval_granted: bool = False
    itsm_dispatched: bool = False
    handoff_issued: bool = False
    workflow_executed: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_performed: bool = False

    def __post_init__(self) -> None:
        identifiers = (
            self.review_id,
            self.schema_version,
            self.packet_id,
            self.requester_id,
            self.organization_id,
            self.environment_id,
            self.site_id,
            self.risk_class,
            self.change_class,
        )
        if any(STABLE_ID.fullmatch(value) is None for value in identifiers):
            raise ValueError("human review identifier is invalid")
        if any(
            SHA256.fullmatch(value) is None
            for value in (
                *self.evidence_digests,
                self.packet_digest,
                self.canonical_digest,
                self.request_fingerprint,
            )
        ):
            raise ValueError("human review digest is invalid")
        timestamps = (
            self.proposed_window_start,
            self.proposed_window_end,
            self.created_at,
            self.updated_at,
            self.expires_at,
        )
        if any(value.tzinfo is None for value in timestamps):
            raise ValueError("human review timestamps must be timezone-aware")
        if (
            self.version < 1
            or self.created_at > self.updated_at
            or self.created_at >= self.expires_at
            or self.proposed_window_start >= self.proposed_window_end
            or not 12 <= len(self.justification.strip()) <= 500
            or len(self.required_role_ids) != 4
            or len(set(self.required_role_ids)) != 4
            or len(self.stages) != 4
            or len(self.impacted_service_ids) != 2
            or len(self.evidence_digests) != 4
        ):
            raise ValueError("human review contract is invalid")
        if tuple(stage.sequence for stage in self.stages) != (1, 2, 3, 4):
            raise ValueError("human review stages are out of order")
        if tuple(stage.required_role_id for stage in self.stages) != self.required_role_ids:
            raise ValueError("human review roles do not match stages")
        if any(stage.packet_digest != self.packet_digest for stage in self.stages):
            raise ValueError("human review stage binding is invalid")
        completed = self.state is HumanReviewState.COMPLETED
        if self.human_review_completed != completed:
            raise ValueError("human review completion state is invalid")
        if completed and any(
            stage.state is not HumanReviewStageState.APPROVED for stage in self.stages
        ):
            raise ValueError("human review completed without every stage")
        if any(
            (
                self.approval_granted,
                self.itsm_dispatched,
                self.handoff_issued,
                self.workflow_executed,
                self.execution_authorized,
                self.infrastructure_mutation_performed,
            )
        ):
            raise ValueError("human review violates the no-execution boundary")
