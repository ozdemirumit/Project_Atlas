from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.guardrails.domain.human_review import (
    DetectedElement,
    HumanReviewQueueEntry,
    HumanReviewResolution,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"


class DetectedElementInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    redacted: bool


class GuardrailHumanReviewEnqueueInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    triggered_rule_id: str = Field(pattern=STABLE_ID)
    safe_rationale: str = Field(min_length=1, max_length=2000)
    request_reference: str = Field(min_length=1, max_length=200)
    bounded_context_reference: str = Field(min_length=1, max_length=200)
    detected_elements: list[DetectedElementInput] = Field(default_factory=list, max_length=50)
    proposed_disposition: str = Field(min_length=1, max_length=2000)
    proposed_impact: str = Field(min_length=1, max_length=2000)
    related_policy_reference: str | None = None
    related_approval_reference: str | None = None
    related_connector_reference: str | None = None
    related_audit_reference: str = Field(min_length=1, max_length=200)
    allowed_decisions: list[str] = Field(min_length=1, max_length=4)


class GuardrailHumanReviewResolveInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: str = Field(min_length=1, max_length=32)
    rationale: str = Field(min_length=1, max_length=2000)
    triggering_guardrail_class: str = Field(min_length=1, max_length=32)


class DetectedElementData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    description: str
    redacted: bool

    @classmethod
    def from_domain(cls, element: DetectedElement) -> DetectedElementData:
        return cls(kind=element.kind, description=element.description, redacted=element.redacted)


class GuardrailHumanReviewEntryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: str
    triggered_rule_id: str
    safe_rationale: str
    request_reference: str
    bounded_context_reference: str
    detected_elements: list[DetectedElementData]
    proposed_disposition: str
    proposed_impact: str
    related_policy_reference: str | None
    related_approval_reference: str | None
    related_connector_reference: str | None
    related_audit_reference: str
    allowed_decisions: list[str]
    created_at: datetime

    @classmethod
    def from_domain(cls, entry: HumanReviewQueueEntry) -> GuardrailHumanReviewEntryData:
        return cls(
            entry_id=entry.entry_id,
            triggered_rule_id=entry.triggered_rule_id,
            safe_rationale=entry.safe_rationale,
            request_reference=entry.request_reference,
            bounded_context_reference=entry.bounded_context_reference,
            detected_elements=[
                DetectedElementData.from_domain(item) for item in entry.detected_elements
            ],
            proposed_disposition=entry.proposed_disposition,
            proposed_impact=entry.proposed_impact,
            related_policy_reference=entry.related_policy_reference,
            related_approval_reference=entry.related_approval_reference,
            related_connector_reference=entry.related_connector_reference,
            related_audit_reference=entry.related_audit_reference,
            allowed_decisions=[decision.value for decision in entry.allowed_decisions],
            created_at=entry.created_at,
        )


class GuardrailHumanReviewEntryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: GuardrailHumanReviewEntryData
    meta: ResponseMeta


class GuardrailHumanReviewResolutionData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: str
    decision: str
    reviewed_by: str
    reviewed_at: datetime
    rationale: str

    @classmethod
    def from_domain(cls, resolution: HumanReviewResolution) -> GuardrailHumanReviewResolutionData:
        return cls(
            entry_id=resolution.entry_id,
            decision=resolution.decision.value,
            reviewed_by=resolution.reviewed_by,
            reviewed_at=resolution.reviewed_at,
            rationale=resolution.rationale,
        )


class GuardrailHumanReviewResolutionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: GuardrailHumanReviewResolutionData
    meta: ResponseMeta
