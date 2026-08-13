from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from typing import Any

NO_EXECUTION_SAFETY_NOTICE = (
    "Decision support only. Atlas cannot invoke connectors, create approvals, mutate ITSM, "
    "dispatch workflows, execute runbooks, or change infrastructure from this conversation."
)


class ConversationLifecycle(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class ConversationTurnRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ConversationTurnStatus(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


def canonical_digest(payload: object) -> str:
    return sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


def _require_text(value: str, *, name: str, maximum: int) -> None:
    if value != value.strip() or not value or len(value) > maximum:
        raise ValueError(f"{name} must contain 1 to {maximum} normalized characters")


def _require_identifier(value: str, *, name: str) -> None:
    _require_text(value, name=name, maximum=240)
    if any(character.isspace() for character in value):
        raise ValueError(f"{name} must not contain whitespace")


def _require_bounded_unique(values: tuple[str, ...], *, name: str, limit: int) -> None:
    if len(values) > limit or len(values) != len(set(values)):
        raise ValueError(f"{name} must be unique and contain at most {limit} values")
    for value in values:
        _require_text(value, name=name, maximum=500)


@dataclass(frozen=True, slots=True)
class ConversationScope:
    organization_id: str
    environment_id: str
    site_id: str

    def __post_init__(self) -> None:
        _require_identifier(self.organization_id, name="organization_id")
        _require_identifier(self.environment_id, name="environment_id")
        _require_identifier(self.site_id, name="site_id")

    def canonical_value(self) -> dict[str, str]:
        return {
            "environment_id": self.environment_id,
            "organization_id": self.organization_id,
            "site_id": self.site_id,
        }


@dataclass(frozen=True, slots=True)
class AuthorizedConversationTarget:
    target_id: str
    display_name: str
    description: str

    def __post_init__(self) -> None:
        _require_identifier(self.target_id, name="target_id")
        _require_text(self.display_name, name="display_name", maximum=120)
        _require_text(self.description, name="description", maximum=500)


@dataclass(frozen=True, slots=True)
class ConversationEvidenceReference:
    evidence_id: str
    citation: str
    artifact_id: str
    artifact_version: str
    source_type: str
    source_reference: str
    observed_at: datetime

    def __post_init__(self) -> None:
        _require_identifier(self.evidence_id, name="evidence_id")
        _require_text(self.citation, name="citation", maximum=1000)
        _require_identifier(self.artifact_id, name="artifact_id")
        _require_identifier(self.artifact_version, name="artifact_version")
        _require_identifier(self.source_type, name="source_type")
        _require_text(self.source_reference, name="source_reference", maximum=1000)
        if self.observed_at.tzinfo is None:
            raise ValueError("evidence observed_at must be timezone-aware")

    def canonical_value(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_version": self.artifact_version,
            "citation": self.citation,
            "evidence_id": self.evidence_id,
            "observed_at": self.observed_at.isoformat(),
            "source_reference": self.source_reference,
            "source_type": self.source_type,
        }


@dataclass(frozen=True, slots=True)
class ConversationArtifactReference:
    artifact_id: str
    artifact_version: int
    artifact_type: str

    def __post_init__(self) -> None:
        _require_identifier(self.artifact_id, name="artifact_id")
        _require_identifier(self.artifact_type, name="artifact_type")
        if self.artifact_version < 1:
            raise ValueError("artifact_version must be positive")

    def canonical_value(self) -> dict[str, object]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "artifact_version": self.artifact_version,
        }


@dataclass(frozen=True, slots=True)
class ConversationAuthority:
    connector_invocation_authorized: bool = False
    approval_creation_authorized: bool = False
    itsm_mutation_authorized: bool = False
    workflow_dispatch_authorized: bool = False
    runbook_execution_authorized: bool = False
    infrastructure_execution_authorized: bool = False

    def __post_init__(self) -> None:
        if any(self.canonical_value().values()):
            raise ValueError("operational conversations cannot grant execution authority")

    def canonical_value(self) -> dict[str, bool]:
        return {
            "approval_creation_authorized": self.approval_creation_authorized,
            "connector_invocation_authorized": self.connector_invocation_authorized,
            "infrastructure_execution_authorized": self.infrastructure_execution_authorized,
            "itsm_mutation_authorized": self.itsm_mutation_authorized,
            "runbook_execution_authorized": self.runbook_execution_authorized,
            "workflow_dispatch_authorized": self.workflow_dispatch_authorized,
        }


@dataclass(frozen=True, slots=True)
class ConversationTurn:
    turn_id: str
    ordinal: int
    role: ConversationTurnRole
    status: ConversationTurnStatus
    text: str
    observed_at: datetime
    evidence_references: tuple[ConversationEvidenceReference, ...]
    artifact_references: tuple[ConversationArtifactReference, ...]
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]
    confidence_basis: tuple[str, ...]
    failure_code: str | None
    safety_notice: str
    authority: ConversationAuthority
    canonical_digest: str

    def __post_init__(self) -> None:
        _require_identifier(self.turn_id, name="turn_id")
        if self.ordinal < 1:
            raise ValueError("turn ordinal must be positive")
        _require_text(self.text, name="turn text", maximum=8000)
        if self.observed_at.tzinfo is None:
            raise ValueError("turn observed_at must be timezone-aware")
        if len(self.evidence_references) > 20:
            raise ValueError("a turn may reference at most 20 evidence records")
        if len({item.evidence_id for item in self.evidence_references}) != len(
            self.evidence_references
        ):
            raise ValueError("turn evidence identifiers must be unique")
        if len(self.artifact_references) > 20:
            raise ValueError("a turn may reference at most 20 artifacts")
        artifact_keys = {
            (item.artifact_id, item.artifact_version) for item in self.artifact_references
        }
        if len(artifact_keys) != len(self.artifact_references):
            raise ValueError("turn artifact references must be unique")
        _require_bounded_unique(self.assumptions, name="assumptions", limit=20)
        _require_bounded_unique(self.unknowns, name="unknowns", limit=20)
        _require_bounded_unique(self.confidence_basis, name="confidence_basis", limit=20)
        if self.safety_notice != NO_EXECUTION_SAFETY_NOTICE:
            raise ValueError("turn safety notice must preserve the no-execution boundary")
        if self.role is ConversationTurnRole.USER:
            if self.status is not ConversationTurnStatus.COMPLETED:
                raise ValueError("user turns must be completed")
            if (
                any(
                    (
                        self.evidence_references,
                        self.artifact_references,
                        self.assumptions,
                        self.unknowns,
                        self.confidence_basis,
                    )
                )
                or self.failure_code is not None
            ):
                raise ValueError("user turns cannot contain generated assertions")
        elif self.status is ConversationTurnStatus.COMPLETED:
            if not self.evidence_references or not self.confidence_basis:
                raise ValueError("completed assistant turns require evidence and confidence basis")
            if self.failure_code is not None:
                raise ValueError("completed assistant turns cannot contain a failure code")
        elif self.status is ConversationTurnStatus.PARTIAL:
            if not self.unknowns or not self.confidence_basis or self.failure_code is not None:
                raise ValueError("partial assistant turns require unknowns and confidence basis")
        elif (
            not self.failure_code
            or not self.unknowns
            or self.evidence_references
            or self.artifact_references
            or self.assumptions
        ):
            raise ValueError("failed assistant turns require a bounded failure without claims")
        if self.failure_code is not None:
            _require_identifier(self.failure_code, name="failure_code")
        expected = canonical_digest(self.digest_payload())
        if self.canonical_digest != expected:
            raise ValueError("turn canonical digest mismatch")

    def digest_payload(self) -> dict[str, Any]:
        return {
            "artifact_references": [item.canonical_value() for item in self.artifact_references],
            "assumptions": self.assumptions,
            "authority": self.authority.canonical_value(),
            "confidence_basis": self.confidence_basis,
            "evidence_references": [item.canonical_value() for item in self.evidence_references],
            "failure_code": self.failure_code,
            "observed_at": self.observed_at.isoformat(),
            "ordinal": self.ordinal,
            "role": self.role.value,
            "safety_notice": self.safety_notice,
            "status": self.status.value,
            "text": self.text,
            "turn_id": self.turn_id,
            "unknowns": self.unknowns,
        }


@dataclass(frozen=True, slots=True)
class OperationalConversation:
    conversation_id: str
    version: int
    lifecycle: ConversationLifecycle
    title: str
    scope: ConversationScope
    owner_subject_id: str
    target_id: str
    target_type: str
    created_by: str
    updated_by: str
    created_at: datetime
    updated_at: datetime
    durable: bool
    turns: tuple[ConversationTurn, ...]
    canonical_digest: str

    def __post_init__(self) -> None:
        _require_identifier(self.conversation_id, name="conversation_id")
        if self.version < 1:
            raise ValueError("conversation version must be positive")
        _require_text(self.title, name="title", maximum=120)
        _require_identifier(self.owner_subject_id, name="owner_subject_id")
        _require_identifier(self.target_id, name="target_id")
        if self.target_type != "storage":
            raise ValueError("this conversation slice is limited to storage targets")
        _require_identifier(self.created_by, name="created_by")
        _require_identifier(self.updated_by, name="updated_by")
        if self.created_by != self.owner_subject_id or self.updated_by != self.owner_subject_id:
            raise ValueError("conversation mutation identities must match the owner")
        if self.created_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("conversation timestamps must be timezone-aware")
        if self.updated_at < self.created_at:
            raise ValueError("conversation updated_at cannot precede created_at")
        if len(self.turns) > 200:
            raise ValueError("a conversation may contain at most 200 turns")
        if tuple(turn.ordinal for turn in self.turns) != tuple(range(1, len(self.turns) + 1)):
            raise ValueError("conversation turn ordinals must be contiguous")
        if len(self.turns) % 2 or any(
            self.turns[index].role is not ConversationTurnRole.USER
            or self.turns[index + 1].role is not ConversationTurnRole.ASSISTANT
            for index in range(0, len(self.turns), 2)
        ):
            raise ValueError("conversation turns must be ordered user and assistant pairs")
        if self.version != 1 + len(self.turns) // 2:
            raise ValueError("conversation version must advance once per turn pair")
        expected = canonical_digest(self.digest_payload())
        if self.canonical_digest != expected:
            raise ValueError("conversation canonical digest mismatch")

    def digest_payload(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "durable": self.durable,
            "lifecycle": self.lifecycle.value,
            "owner_subject_id": self.owner_subject_id,
            "scope": self.scope.canonical_value(),
            "target_id": self.target_id,
            "target_type": self.target_type,
            "title": self.title,
            "turn_digests": [turn.canonical_digest for turn in self.turns],
            "updated_at": self.updated_at.isoformat(),
            "updated_by": self.updated_by,
            "version": self.version,
        }


@dataclass(frozen=True, slots=True)
class ConversationGenerationRequest:
    request_digest: str
    conversation_id: str
    conversation_version: int
    scope: ConversationScope
    owner_subject_id: str
    role_ids: frozenset[str]
    decision_id: str
    target_id: str
    question: str
    prior_turns: tuple[ConversationTurn, ...]
    requested_at: datetime
    correlation_id: str

    def __post_init__(self) -> None:
        _require_identifier(self.request_digest, name="request_digest")
        _require_identifier(self.conversation_id, name="conversation_id")
        if self.conversation_version < 1:
            raise ValueError("conversation_version must be positive")
        _require_identifier(self.owner_subject_id, name="owner_subject_id")
        if not self.role_ids:
            raise ValueError("generation role_ids must not be empty")
        for role_id in self.role_ids:
            _require_identifier(role_id, name="role_id")
        _require_identifier(self.decision_id, name="decision_id")
        _require_identifier(self.target_id, name="target_id")
        _require_text(self.question, name="question", maximum=700)
        if self.requested_at.tzinfo is None:
            raise ValueError("generation requested_at must be timezone-aware")
        _require_identifier(self.correlation_id, name="correlation_id")


@dataclass(frozen=True, slots=True)
class ConversationGenerationResult:
    request_digest: str
    conversation_id: str
    scope: ConversationScope
    owner_subject_id: str
    target_id: str
    status: ConversationTurnStatus
    text: str
    observed_at: datetime
    evidence_references: tuple[ConversationEvidenceReference, ...]
    artifact_references: tuple[ConversationArtifactReference, ...]
    assumptions: tuple[str, ...]
    unknowns: tuple[str, ...]
    confidence_basis: tuple[str, ...]
    failure_code: str | None
    safety_notice: str
    authority: ConversationAuthority
    result_digest: str

    def __post_init__(self) -> None:
        if self.status not in {
            ConversationTurnStatus.COMPLETED,
            ConversationTurnStatus.PARTIAL,
            ConversationTurnStatus.FAILED,
        }:
            raise ValueError("invalid generated turn status")
        _require_identifier(self.request_digest, name="request_digest")
        _require_identifier(self.conversation_id, name="conversation_id")
        _require_identifier(self.owner_subject_id, name="owner_subject_id")
        _require_identifier(self.target_id, name="target_id")
        if self.observed_at.tzinfo is None:
            raise ValueError("generation observed_at must be timezone-aware")
        expected = canonical_digest(self.digest_payload())
        if self.result_digest != expected:
            raise ValueError("generation result digest mismatch")

    def digest_payload(self) -> dict[str, Any]:
        return {
            "artifact_references": [item.canonical_value() for item in self.artifact_references],
            "assumptions": self.assumptions,
            "authority": self.authority.canonical_value(),
            "confidence_basis": self.confidence_basis,
            "conversation_id": self.conversation_id,
            "evidence_references": [item.canonical_value() for item in self.evidence_references],
            "failure_code": self.failure_code,
            "observed_at": self.observed_at.isoformat(),
            "owner_subject_id": self.owner_subject_id,
            "request_digest": self.request_digest,
            "safety_notice": self.safety_notice,
            "scope": self.scope.canonical_value(),
            "status": self.status.value,
            "target_id": self.target_id,
            "text": self.text,
            "unknowns": self.unknowns,
        }
