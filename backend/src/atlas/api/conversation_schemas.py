from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from atlas.api.schemas import ResponseMeta
from atlas.modules.conversations.domain.models import (
    AuthorizedConversationTarget,
    ConversationArtifactReference,
    ConversationEvidenceReference,
    ConversationTurn,
    OperationalConversation,
)

STABLE_ID = r"^[a-z][a-z0-9_.:-]{2,127}$"


class CreateOperationalConversationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.operational-conversation-create.v1"]
    target_id: str = Field(min_length=3, max_length=128, pattern=STABLE_ID)
    target_type: Literal["storage"]
    title: str = Field(min_length=1, max_length=120)
    acknowledged_decision_support_only: Literal[True]


class AppendOperationalConversationTurnInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.operational-conversation-turn-append.v1"]
    expected_version: int = Field(ge=1)
    question: str = Field(min_length=1, max_length=700)
    acknowledged_decision_support_only: Literal[True]


class ConversationEvidenceReferenceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str
    artifact_id: str
    artifact_version: str
    source_type: str
    source_reference: str
    observed_at: datetime
    citation: str

    @classmethod
    def from_domain(
        cls,
        reference: ConversationEvidenceReference,
    ) -> ConversationEvidenceReferenceData:
        return cls(
            evidence_id=reference.evidence_id,
            artifact_id=reference.artifact_id,
            artifact_version=reference.artifact_version,
            source_type=reference.source_type,
            source_reference=reference.source_reference,
            observed_at=reference.observed_at,
            citation=reference.citation,
        )


class ConversationArtifactReferenceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    artifact_type: str
    version: int

    @classmethod
    def from_domain(
        cls, reference: ConversationArtifactReference
    ) -> ConversationArtifactReferenceData:
        return cls(
            artifact_id=reference.artifact_id,
            artifact_type=reference.artifact_type,
            version=reference.artifact_version,
        )


class OperationalConversationTurnData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.operational-conversation-turn.v1"] = (
        "atlas.operational-conversation-turn.v1"
    )
    turn_id: str
    ordinal: int
    role: Literal["user", "assistant"]
    status: Literal["completed", "partial", "failed"]
    text: str
    observed_at: datetime
    evidence_references: list[ConversationEvidenceReferenceData]
    artifact_references: list[ConversationArtifactReferenceData]
    assumptions: list[str]
    unknowns: list[str]
    confidence_basis: str
    failure_code: str | None
    safety_notice: str
    canonical_digest: str

    @classmethod
    def from_domain(cls, turn: ConversationTurn) -> OperationalConversationTurnData:
        return cls(
            turn_id=turn.turn_id,
            ordinal=turn.ordinal,
            role=turn.role.value,
            status=turn.status.value,
            text=turn.text,
            observed_at=turn.observed_at,
            evidence_references=[
                ConversationEvidenceReferenceData.from_domain(item)
                for item in turn.evidence_references
            ],
            artifact_references=[
                ConversationArtifactReferenceData.from_domain(item)
                for item in turn.artifact_references
            ],
            assumptions=list(turn.assumptions),
            unknowns=list(turn.unknowns),
            confidence_basis="\n".join(turn.confidence_basis),
            failure_code=turn.failure_code,
            safety_notice=turn.safety_notice,
            canonical_digest=turn.canonical_digest,
        )


class OperationalConversationSummaryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["atlas.operational-conversation.v1"] = (
        "atlas.operational-conversation.v1"
    )
    conversation_id: str
    version: int
    organization_id: str
    environment_id: str
    site_id: str
    owner_subject_id: str
    target_id: str
    target_type: Literal["storage"]
    title: str
    lifecycle: Literal["open", "closed"]
    turn_count: int
    created_by: str
    created_at: datetime
    updated_by: str
    updated_at: datetime
    durable: bool
    canonical_digest: str

    @classmethod
    def from_domain(
        cls, conversation: OperationalConversation
    ) -> OperationalConversationSummaryData:
        return cls(
            conversation_id=conversation.conversation_id,
            version=conversation.version,
            organization_id=conversation.scope.organization_id,
            environment_id=conversation.scope.environment_id,
            site_id=conversation.scope.site_id,
            owner_subject_id=conversation.owner_subject_id,
            target_id=conversation.target_id,
            target_type="storage",
            title=conversation.title,
            lifecycle=conversation.lifecycle.value,
            turn_count=len(conversation.turns),
            created_by=conversation.created_by,
            created_at=conversation.created_at,
            updated_by=conversation.updated_by,
            updated_at=conversation.updated_at,
            durable=conversation.durable,
            canonical_digest=conversation.canonical_digest,
        )


class OperationalConversationData(OperationalConversationSummaryData):
    turns: list[OperationalConversationTurnData]

    @classmethod
    def from_domain(cls, conversation: OperationalConversation) -> OperationalConversationData:
        summary = OperationalConversationSummaryData.from_domain(conversation)
        return cls(
            **summary.model_dump(),
            turns=[
                OperationalConversationTurnData.from_domain(item) for item in conversation.turns
            ],
        )


class AuthorizedConversationTargetData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_id: str
    display_name: str
    description: str

    @classmethod
    def from_domain(cls, target: AuthorizedConversationTarget) -> AuthorizedConversationTargetData:
        return cls(
            target_id=target.target_id,
            display_name=target.display_name,
            description=target.description,
        )


class OperationalConversationInventoryData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversations: list[OperationalConversationSummaryData]
    authorized_targets: list[AuthorizedConversationTargetData]
    durable: bool
    truncated: bool


class OperationalConversationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: OperationalConversationData
    meta: ResponseMeta


class OperationalConversationInventoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: OperationalConversationInventoryData
    meta: ResponseMeta
