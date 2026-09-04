"""ATLAS-040 SS14: memory."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier


class MemoryScope(StrEnum):
    """SS14: "conversation memory is scoped to the task or configured session.\""""

    TASK = "task"
    SESSION = "session"


@dataclass(frozen=True, slots=True)
class ConversationMemoryScope:
    scope: MemoryScope
    scope_reference: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.scope_reference, "scope_reference")


class DurableMemorySystem(StrEnum):
    """SS14: "durable organizational memory is stored in governed graph, knowledge, workflow,
    decision, and audit systems.\""""

    GRAPH = "graph"
    KNOWLEDGE = "knowledge"
    WORKFLOW = "workflow"
    DECISION = "decision"
    AUDIT = "audit"


@dataclass(frozen=True, slots=True)
class MemoryWrite:
    """SS14: "memory writes use explicit schemas, owners, retention, provenance, and review.\""""

    write_id: str
    target_system: DurableMemorySystem
    schema_version: str
    owner: str
    retention_class: str
    provenance: str
    reviewed: bool

    def __post_init__(self) -> None:
        validate_stable_identifier(self.write_id, "write_id")
        if not self.schema_version.strip():
            raise ValueError("a memory write requires a schema version")
        if not self.owner.strip():
            raise ValueError("a memory write requires an owner")
        if not self.retention_class.strip():
            raise ValueError("a memory write requires a retention class")
        if not self.provenance.strip():
            raise ValueError("a memory write requires provenance")


def agents_can_create_invisible_facts_in_model_state() -> bool:
    """SS14: "agents cannot create invisible facts in model state.\""""
    return False


def conversation_becomes_authoritative_knowledge_automatically() -> bool:
    """SS14: "a conversation does not become authoritative knowledge automatically.\""""
    return False


class UserCorrectionOutcome(StrEnum):
    """SS14: "user correction creates a traceable update or candidate knowledge item.\""""

    TRACEABLE_UPDATE = "traceable_update"
    CANDIDATE_KNOWLEDGE_ITEM = "candidate_knowledge_item"


@dataclass(frozen=True, slots=True)
class UserCorrectionRecord:
    correction_id: str
    corrected_by: str
    outcome: UserCorrectionOutcome
    target_reference: str
    rationale: str

    def __post_init__(self) -> None:
        validate_stable_identifier(self.correction_id, "correction_id")
        validate_stable_identifier(self.target_reference, "target_reference")
        if not self.corrected_by.strip():
            raise ValueError("a user correction record requires an identity")
        if not self.rationale.strip():
            raise ValueError("a user correction record requires a rationale")


def cross_user_or_cross_organization_memory_access_is_permitted(
    *, explicit_policy_grant: bool
) -> bool:
    """SS14: "cross-user or cross-organization memory access is prohibited without explicit
    policy.\""""
    return explicit_policy_grant
