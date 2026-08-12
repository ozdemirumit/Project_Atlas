from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256

from atlas.modules.reports.domain.models import ItsmHandoffDraft

STABLE_ID = re.compile(r"^[a-z][a-z0-9_.:-]{2,127}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")


class ItsmHandoffReviewOutcome(StrEnum):
    ACCEPT = "accept"
    NEEDS_EVIDENCE = "needs_evidence"
    REJECT = "reject"


def canonical_handoff_digest(handoff: ItsmHandoffDraft) -> str:
    payload = {
        "draft_id": handoff.draft_id,
        "idempotency_key": handoff.idempotency_key,
        "state": handoff.state.value,
        "external_system": handoff.external_system,
        "operation": handoff.operation,
        "incident_reference": handoff.incident_reference,
        "report_id": handoff.report_id,
        "report_version": handoff.report_version,
        "generated_content_label": handoff.generated_content_label,
        "field_mappings": [
            {
                "field": item.field,
                "value": item.value,
                "source_reference": item.source_reference,
            }
            for item in handoff.field_mappings
        ],
        "artifact_references": list(handoff.artifact_references),
        "classification": handoff.classification.value,
        "redaction_state": handoff.redaction_state.value,
        "human_review_required": handoff.human_review_required,
        "dispatch_authorized": handoff.dispatch_authorized,
        "external_record_mutated": handoff.external_record_mutated,
    }
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class ItsmHandoffHumanReview:
    review_id: str
    schema_version: str
    version: int
    outcome: ItsmHandoffReviewOutcome
    report_id: str
    report_version: int
    report_digest: str
    handoff_draft_id: str
    handoff_digest: str
    handoff_idempotency_key: str
    incident_reference: str
    operation: str
    requester_id: str
    reviewer_id: str
    reviewer_role_id: str
    organization_id: str
    environment_id: str
    site_id: str
    rationale: str
    acknowledged_review_only: bool
    request_fingerprint: str
    idempotency_key: str
    canonical_digest: str
    decided_at: datetime
    expires_at: datetime
    review_complete: bool
    dispatch_authorized: bool = False
    external_record_mutated: bool = False
    itsm_approval_satisfied: bool = False
    workflow_approved: bool = False
    execution_authorized: bool = False
    infrastructure_mutation_performed: bool = False
    reused: bool = False

    def __post_init__(self) -> None:
        identifiers = (
            self.review_id,
            self.schema_version,
            self.report_id,
            self.handoff_draft_id,
            self.requester_id,
            self.reviewer_id,
            self.reviewer_role_id,
            self.organization_id,
            self.environment_id,
            self.site_id,
        )
        if any(STABLE_ID.fullmatch(value) is None for value in identifiers):
            raise ValueError("ITSM handoff review identifier is invalid")
        if (
            self.version != 1
            or self.report_version < 1
            or any(
                SHA256.fullmatch(value) is None
                for value in (
                    self.report_digest,
                    self.handoff_digest,
                    self.handoff_idempotency_key,
                    self.request_fingerprint,
                    self.canonical_digest,
                )
            )
            or not 5 <= len(self.rationale.strip()) <= 1000
            or not 8 <= len(self.idempotency_key) <= 128
            or not self.incident_reference.startswith("INC-")
            or not self.operation.strip()
            or self.decided_at.tzinfo is None
            or self.expires_at.tzinfo is None
            or self.expires_at <= self.decided_at
            or not self.acknowledged_review_only
        ):
            raise ValueError("ITSM handoff review is invalid")
        if self.requester_id == self.reviewer_id:
            raise ValueError("ITSM handoff review requires reviewer separation")
        if self.review_complete != (self.outcome is ItsmHandoffReviewOutcome.ACCEPT):
            raise ValueError("ITSM handoff review completion is inconsistent")
        if any(
            (
                self.dispatch_authorized,
                self.external_record_mutated,
                self.itsm_approval_satisfied,
                self.workflow_approved,
                self.execution_authorized,
                self.infrastructure_mutation_performed,
            )
        ):
            raise ValueError("ITSM handoff review cannot grant operational authority")
