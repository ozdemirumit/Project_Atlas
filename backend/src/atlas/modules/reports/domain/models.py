from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.core.classification import DataClassification


class ReportType(StrEnum):
    TECHNICAL_DECISION = "technical_decision"


class ReportAudience(StrEnum):
    TECHNICAL_OPERATIONS = "technical_operations"
    MANAGEMENT = "management"


class ReportState(StrEnum):
    READY_FOR_REVIEW = "ready_for_review"


class SectionState(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


class RedactionState(StrEnum):
    COMPLETE = "complete"


class HandoffState(StrEnum):
    REVIEW_REQUIRED = "review_required"


class ReviewStatus(StrEnum):
    PENDING = "pending"


@dataclass(frozen=True, slots=True)
class ReportRequest:
    source_recommendation_id: str
    source_recommendation_version: int
    target_id: str
    report_type: ReportType
    audience: ReportAudience
    classification: DataClassification
    include_itsm_handoff: bool
    incident_reference: str | None

    def __post_init__(self) -> None:
        if self.source_recommendation_version < 1:
            raise ValueError("source recommendation version must be positive")
        if not self.source_recommendation_id.strip() or not self.target_id.strip():
            raise ValueError("report source and target are required")
        if self.include_itsm_handoff and self.incident_reference is None:
            raise ValueError("ITSM handoff requires an incident reference")
        if self.incident_reference is not None and (
            not self.incident_reference.startswith("INC-") or len(self.incident_reference) > 80
        ):
            raise ValueError("invalid incident reference")


@dataclass(frozen=True, slots=True)
class ReportSourceLineage:
    recommendation_id: str
    recommendation_version: int
    recommendation_state: str
    recommendation_created_at: datetime
    recommendation_expires_at: datetime
    rca_case_id: str
    rca_case_version: int
    target_id: str
    evidence_ids: tuple[str, ...]
    component_versions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReportSection:
    section_id: str
    title: str
    state: SectionState
    statements: tuple[str, ...]
    evidence_references: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.section_id.strip() or not self.title.strip():
            raise ValueError("report sections require identity and title")
        if self.state is SectionState.FAILED and not self.limitations:
            raise ValueError("failed report sections require limitations")
        if self.state is SectionState.COMPLETE and self.limitations:
            raise ValueError("complete report sections cannot contain limitations")


@dataclass(frozen=True, slots=True)
class ReportReview:
    status: ReviewStatus
    reviewer_id: str | None
    reviewed_at: datetime | None
    rationale: str | None

    def __post_init__(self) -> None:
        if any(value is not None for value in (self.reviewer_id, self.reviewed_at, self.rationale)):
            raise ValueError("pending report review cannot contain a decision")


@dataclass(frozen=True, slots=True)
class ItsmFieldMapping:
    field: str
    value: str
    source_reference: str


@dataclass(frozen=True, slots=True)
class ItsmHandoffDraft:
    draft_id: str
    idempotency_key: str
    state: HandoffState
    external_system: str
    operation: str
    incident_reference: str
    report_id: str
    report_version: int
    generated_content_label: str
    field_mappings: tuple[ItsmFieldMapping, ...]
    artifact_references: tuple[str, ...]
    classification: DataClassification
    redaction_state: RedactionState
    human_review_required: bool
    dispatch_authorized: bool
    external_record_mutated: bool

    def __post_init__(self) -> None:
        if not self.idempotency_key.strip() or not self.incident_reference.strip():
            raise ValueError("ITSM handoff identity is required")
        if not self.human_review_required:
            raise ValueError("ITSM handoff requires human review")
        if self.dispatch_authorized or self.external_record_mutated:
            raise ValueError("report handoff drafts cannot mutate external records")


@dataclass(frozen=True, slots=True)
class TechnicalReport:
    report_id: str
    version: int
    prior_version_id: str | None
    owner: str
    state: ReportState
    requested_by: str
    created_at: datetime
    expires_at: datetime
    organization_id: str
    environment_id: str
    site_id: str
    target_id: str
    report_type: ReportType
    audience: ReportAudience
    classification: DataClassification
    redaction_state: RedactionState
    source: ReportSourceLineage
    sections: tuple[ReportSection, ...]
    review: ReportReview
    itsm_handoff: ItsmHandoffDraft | None
    rendered_markdown: str
    content_digest: str
    component_versions: tuple[str, ...]
    data_profile: str
    execution_authorized: bool
    external_mutation_authorized: bool
    safety_notice: str

    def __post_init__(self) -> None:
        if self.version < 1 or not self.sections:
            raise ValueError("reports require a positive version and sections")
        if any(value.tzinfo is None for value in (self.created_at, self.expires_at)):
            raise ValueError("report timestamps must be timezone-aware")
        if self.expires_at <= self.created_at:
            raise ValueError("report expiry must follow creation")
        if len(self.content_digest) != 64 or any(
            character not in "0123456789abcdef" for character in self.content_digest
        ):
            raise ValueError("report content digest must be SHA-256")
        if self.execution_authorized or self.external_mutation_authorized:
            raise ValueError("reports cannot authorize execution or external mutation")
        section_ids = {section.section_id for section in self.sections}
        if len(section_ids) != len(self.sections):
            raise ValueError("report section IDs must be unique")
        evidence_ids = set(self.source.evidence_ids)
        references = {
            reference for section in self.sections for reference in section.evidence_references
        }
        if not references <= evidence_ids:
            raise ValueError("report contains unresolved evidence references")
        if self.itsm_handoff is not None and (
            self.itsm_handoff.report_id != self.report_id
            or self.itsm_handoff.report_version != self.version
        ):
            raise ValueError("ITSM handoff must bind to the exact report")
