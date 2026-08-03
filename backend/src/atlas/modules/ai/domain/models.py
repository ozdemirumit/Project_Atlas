from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from urllib.parse import urlparse

from atlas.core.classification import DataClassification
from atlas.modules.knowledge.domain.models import Citation, RetrievalHit


class TaskClass(StrEnum):
    GROUNDED_ANSWER = "grounded_answer"


class EndpointLifecycle(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class EvaluationStatus(StrEnum):
    APPROVED = "approved"
    EVALUATING = "evaluating"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ModelEndpointProfile:
    endpoint_id: str
    owner: str
    provider_type: str
    base_url: str
    secret_reference_id: str
    approved_model_ids: frozenset[str]
    approved_task_classes: frozenset[TaskClass]
    classification_ceiling: DataClassification
    network_boundary: str
    max_context_characters: int
    max_output_tokens: int
    timeout_seconds: float
    lifecycle: EndpointLifecycle
    evaluation_status: EvaluationStatus

    def __post_init__(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("model endpoint must use an absolute HTTP(S) URL")
        if parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError("unencrypted model endpoints are limited to loopback hosts")
        if not self.endpoint_id or not self.owner or not self.secret_reference_id:
            raise ValueError("model endpoint identity, owner, and secret reference are required")
        if self.provider_type != "openai_compatible":
            raise ValueError("only the approved OpenAI-compatible provider contract is supported")
        if not self.approved_model_ids or not self.approved_task_classes:
            raise ValueError("model and task allowlists must not be empty")
        if not 1000 <= self.max_context_characters <= 1_000_000:
            raise ValueError("model context limit is outside the supported range")
        if not 1 <= self.max_output_tokens <= 8192:
            raise ValueError("model output limit is outside the supported range")
        if not 0.1 <= self.timeout_seconds <= 120:
            raise ValueError("model timeout is outside the supported range")


@dataclass(frozen=True, slots=True)
class GroundedModelRequest:
    task_class: TaskClass
    query: str
    evidence: tuple[RetrievalHit, ...]
    classification: DataClassification
    requested_model_id: str
    max_output_tokens: int
    response_schema_version: str
    correlation_id: str


@dataclass(frozen=True, slots=True)
class ModelInvocation:
    endpoint_id: str
    base_url: str
    model_id: str
    task_class: TaskClass
    query: str
    evidence: tuple[RetrievalHit, ...]
    max_output_tokens: int
    response_schema_version: str
    timeout_seconds: float
    correlation_id: str


@dataclass(frozen=True, slots=True)
class ProviderCompletion:
    summary: str
    citation_references: tuple[str, ...]
    unknowns: tuple[str, ...]
    finish_reason: str
    model_id: str
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True, slots=True)
class GroundedAnswerDraft:
    summary: str
    citations: tuple[Citation, ...]
    unknowns: tuple[str, ...]
    endpoint_id: str
    model_id: str
    finish_reason: str
    response_schema_version: str


@dataclass(frozen=True, slots=True)
class GroundedAnswer:
    answer_id: str
    query_id: str
    summary: str
    citations: tuple[Citation, ...]
    unknowns: tuple[str, ...]
    model_invoked: bool
    endpoint_id: str | None
    model_id: str | None
    response_schema_version: str
    data_profile: str
    generated_at: datetime

    def __post_init__(self) -> None:
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        if not self.summary.strip() or not self.unknowns:
            raise ValueError("grounded answers require a summary and explicit unknowns")
        if self.model_invoked and (not self.endpoint_id or not self.model_id):
            raise ValueError("model identity is required when a model was invoked")
