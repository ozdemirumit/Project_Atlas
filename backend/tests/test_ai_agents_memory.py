from __future__ import annotations

import pytest

from atlas.modules.ai_agents.domain.memory import (
    ConversationMemoryScope,
    DurableMemorySystem,
    MemoryScope,
    MemoryWrite,
    UserCorrectionOutcome,
    UserCorrectionRecord,
    agents_can_create_invisible_facts_in_model_state,
    conversation_becomes_authoritative_knowledge_automatically,
    cross_user_or_cross_organization_memory_access_is_permitted,
)


def test_conversation_memory_scope_accepts_task_or_session() -> None:
    assert ConversationMemoryScope(
        scope=MemoryScope.TASK, scope_reference="task.example"
    ).scope is (MemoryScope.TASK)


def memory_write(**overrides: object) -> MemoryWrite:
    defaults: dict[str, object] = {
        "write_id": "memory-write.example",
        "target_system": DurableMemorySystem.KNOWLEDGE,
        "schema_version": "knowledge-candidate.v1",
        "owner": "knowledge-team",
        "retention_class": "governed",
        "provenance": "user_correction.example",
        "reviewed": False,
    }
    defaults.update(overrides)
    return MemoryWrite(**defaults)  # type: ignore[arg-type]


def test_memory_write_requires_provenance() -> None:
    with pytest.raises(ValueError, match="requires provenance"):
        memory_write(provenance="")


def test_memory_write_requires_owner() -> None:
    with pytest.raises(ValueError, match="requires an owner"):
        memory_write(owner="")


def test_agents_never_create_invisible_facts() -> None:
    assert agents_can_create_invisible_facts_in_model_state() is False


def test_conversation_never_becomes_authoritative_automatically() -> None:
    assert conversation_becomes_authoritative_knowledge_automatically() is False


def test_user_correction_record_requires_rationale() -> None:
    with pytest.raises(ValueError, match="requires a rationale"):
        UserCorrectionRecord(
            correction_id="correction.example",
            corrected_by="subject.reviewer",
            outcome=UserCorrectionOutcome.TRACEABLE_UPDATE,
            target_reference="knowledge-item.example",
            rationale="",
        )


def test_cross_organization_memory_access_requires_explicit_policy() -> None:
    assert (
        cross_user_or_cross_organization_memory_access_is_permitted(explicit_policy_grant=False)
        is False
    )
    assert (
        cross_user_or_cross_organization_memory_access_is_permitted(explicit_policy_grant=True)
        is True
    )
