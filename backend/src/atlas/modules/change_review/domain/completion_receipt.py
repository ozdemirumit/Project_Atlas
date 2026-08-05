from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from atlas.modules.change_review.domain.human_review import HumanReviewOutcome

STABLE_ID = re.compile(r"^[a-z][a-z0-9_.:-]{2,127}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")


@dataclass(frozen=True, slots=True)
class CompletionStageEvidence:
    stage_id: str
    sequence: int
    required_role_id: str
    reviewer_id: str
    decision_id: str
    request_version: int
    outcome: HumanReviewOutcome
    rationale_digest: str
    acknowledged_no_authority: bool
    decided_at: datetime

    def __post_init__(self) -> None:
        identifiers = (
            self.stage_id,
            self.required_role_id,
            self.reviewer_id,
            self.decision_id,
        )
        if any(STABLE_ID.fullmatch(value) is None for value in identifiers):
            raise ValueError("completion stage evidence identifier is invalid")
        if (
            self.sequence < 1
            or self.request_version < 1
            or self.outcome is not HumanReviewOutcome.APPROVE
            or SHA256.fullmatch(self.rationale_digest) is None
            or not self.acknowledged_no_authority
            or self.decided_at.tzinfo is None
        ):
            raise ValueError("completion stage evidence is invalid")


@dataclass(frozen=True, slots=True)
class HumanReviewCompletionReceipt:
    receipt_id: str
    schema_version: str
    version: int
    review_id: str
    review_version: int
    review_digest: str
    review_expires_at: datetime
    packet_id: str
    packet_digest: str
    requester_id: str
    created_by: str
    organization_id: str
    environment_id: str
    site_id: str
    risk_class: str
    change_class: str
    impacted_service_ids: tuple[str, ...]
    evidence_digests: tuple[str, ...]
    proposed_window_start: datetime
    proposed_window_end: datetime
    stages: tuple[CompletionStageEvidence, ...]
    canonical_digest: str
    request_fingerprint: str
    idempotency_key: str
    created_at: datetime
    reused: bool = False
    human_review_completed: bool = True
    completion_evidence_only: bool = True
    approval_granted: bool = False
    itsm_dispatched: bool = False
    notification_sent: bool = False
    handoff_issued: bool = False
    workflow_executed: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_performed: bool = False

    def __post_init__(self) -> None:
        identifiers = (
            self.receipt_id,
            self.schema_version,
            self.review_id,
            self.packet_id,
            self.requester_id,
            self.created_by,
            self.organization_id,
            self.environment_id,
            self.site_id,
            self.risk_class,
            self.change_class,
        )
        if any(STABLE_ID.fullmatch(value) is None for value in identifiers):
            raise ValueError("completion receipt identifier is invalid")
        if any(
            SHA256.fullmatch(value) is None
            for value in (
                self.review_digest,
                self.packet_digest,
                *self.evidence_digests,
                self.canonical_digest,
                self.request_fingerprint,
            )
        ):
            raise ValueError("completion receipt digest is invalid")
        timestamps = (
            self.review_expires_at,
            self.proposed_window_start,
            self.proposed_window_end,
            self.created_at,
        )
        if any(value.tzinfo is None for value in timestamps):
            raise ValueError("completion receipt timestamps must be timezone-aware")
        if (
            self.version != 1
            or self.review_version < 1
            or self.created_at >= self.review_expires_at
            or self.proposed_window_start >= self.proposed_window_end
            or len(self.impacted_service_ids) != 2
            or len(self.evidence_digests) != 4
            or len(self.stages) != 4
            or tuple(stage.sequence for stage in self.stages) != (1, 2, 3, 4)
            or len({stage.reviewer_id for stage in self.stages}) != 4
            or not 8 <= len(self.idempotency_key) <= 128
            or not self.human_review_completed
            or not self.completion_evidence_only
        ):
            raise ValueError("completion receipt contract is invalid")
        if any(
            (
                self.approval_granted,
                self.itsm_dispatched,
                self.notification_sent,
                self.handoff_issued,
                self.workflow_executed,
                self.execution_authorized,
                self.infrastructure_mutation_performed,
            )
        ):
            raise ValueError("completion receipt violates the no-execution boundary")
