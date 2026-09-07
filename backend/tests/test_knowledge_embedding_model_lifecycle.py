from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.knowledge.adapters.embedding_model_lifecycle_memory import (
    InMemoryEmbeddingModelLifecycleRepository,
)
from atlas.modules.knowledge.application.embedding_model_lifecycle import (
    EmbeddingModelLifecycleError,
    EmbeddingModelLifecycleService,
)
from atlas.modules.knowledge.domain.embedding_model_lifecycle import (
    EmbeddingModelLifecycleStage,
    an_embedding_model_becomes_active_without_passing_through_approval_or_revalidation,
    is_valid_embedding_model_transition,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


def _service() -> tuple[EmbeddingModelLifecycleService, CollectingAuditSink]:
    audit_sink = CollectingAuditSink()
    service = EmbeddingModelLifecycleService(
        repository=InMemoryEmbeddingModelLifecycleRepository(),
        audit_sink=audit_sink,
        clock=lambda: NOW,
    )
    return service, audit_sink


def test_absolute_rule_is_false() -> None:
    assert (
        an_embedding_model_becomes_active_without_passing_through_approval_or_revalidation()
        is False
    )


def test_active_is_reachable_only_from_approved_or_suspended() -> None:
    assert (
        is_valid_embedding_model_transition(
            EmbeddingModelLifecycleStage.APPROVED, EmbeddingModelLifecycleStage.ACTIVE
        )
        is True
    )
    assert (
        is_valid_embedding_model_transition(
            EmbeddingModelLifecycleStage.SUSPENDED, EmbeddingModelLifecycleStage.ACTIVE
        )
        is True
    )
    assert (
        is_valid_embedding_model_transition(
            EmbeddingModelLifecycleStage.CANDIDATE, EmbeddingModelLifecycleStage.ACTIVE
        )
        is False
    )


def test_retired_is_terminal() -> None:
    for target in EmbeddingModelLifecycleStage:
        assert (
            is_valid_embedding_model_transition(EmbeddingModelLifecycleStage.RETIRED, target)
            is False
        )


@pytest.mark.asyncio
async def test_full_lifecycle() -> None:
    service, audit_sink = _service()
    stage = await service.register(
        model_id="model.embedding.bge-large-v2", correlation_id="correlation.test"
    )
    assert stage is EmbeddingModelLifecycleStage.CANDIDATE
    await service.transition(
        model_id="model.embedding.bge-large-v2",
        target=EmbeddingModelLifecycleStage.EVALUATING,
        correlation_id="correlation.test",
    )
    await service.transition(
        model_id="model.embedding.bge-large-v2",
        target=EmbeddingModelLifecycleStage.APPROVED,
        correlation_id="correlation.test",
    )
    active = await service.transition(
        model_id="model.embedding.bge-large-v2",
        target=EmbeddingModelLifecycleStage.ACTIVE,
        correlation_id="correlation.test",
    )
    assert active is EmbeddingModelLifecycleStage.ACTIVE
    assert any(
        item.result_code == "embedding_model_lifecycle.active" for item in audit_sink.records
    )


@pytest.mark.asyncio
async def test_register_twice_is_refused() -> None:
    service, _audit = _service()
    await service.register(
        model_id="model.embedding.bge-large-v2", correlation_id="correlation.test"
    )
    with pytest.raises(EmbeddingModelLifecycleError) as exc_info:
        await service.register(
            model_id="model.embedding.bge-large-v2", correlation_id="correlation.test"
        )
    assert exc_info.value.code == "embedding_model_already_registered"


@pytest.mark.asyncio
async def test_transition_rejects_an_undiagrammed_target() -> None:
    service, _audit = _service()
    await service.register(
        model_id="model.embedding.bge-large-v2", correlation_id="correlation.test"
    )
    with pytest.raises(EmbeddingModelLifecycleError) as exc_info:
        await service.transition(
            model_id="model.embedding.bge-large-v2",
            target=EmbeddingModelLifecycleStage.ACTIVE,
            correlation_id="correlation.test",
        )
    assert exc_info.value.code == "embedding_model_transition_invalid"


@pytest.mark.asyncio
async def test_transition_requires_prior_registration() -> None:
    service, _audit = _service()
    with pytest.raises(EmbeddingModelLifecycleError) as exc_info:
        await service.transition(
            model_id="model.unregistered",
            target=EmbeddingModelLifecycleStage.EVALUATING,
            correlation_id="correlation.test",
        )
    assert exc_info.value.code == "embedding_model_unregistered"
