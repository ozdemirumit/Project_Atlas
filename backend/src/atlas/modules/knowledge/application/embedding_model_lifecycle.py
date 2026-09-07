"""ATLAS-054 SS10: Embedding Model Lifecycle application service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.knowledge.application.embedding_model_lifecycle_ports import (
    EmbeddingModelLifecycleRepository,
)
from atlas.modules.knowledge.domain.embedding_model_lifecycle import (
    EmbeddingModelLifecycleStage,
    is_valid_embedding_model_transition,
    validate_embedding_model_id,
)


class EmbeddingModelLifecycleError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class EmbeddingModelLifecycleService:
    def __init__(
        self,
        *,
        repository: EmbeddingModelLifecycleRepository,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))

    async def register(self, *, model_id: str, correlation_id: str) -> EmbeddingModelLifecycleStage:
        validate_embedding_model_id(model_id)
        if await self._repository.get_stage(model_id) is not None:
            raise EmbeddingModelLifecycleError("embedding_model_already_registered")
        await self._repository.save_stage(model_id, EmbeddingModelLifecycleStage.CANDIDATE)
        await self._audit(
            correlation_id=correlation_id,
            model_id=model_id,
            outcome=EmbeddingModelLifecycleStage.CANDIDATE.value,
        )
        return EmbeddingModelLifecycleStage.CANDIDATE

    async def transition(
        self,
        *,
        model_id: str,
        target: EmbeddingModelLifecycleStage,
        correlation_id: str,
    ) -> EmbeddingModelLifecycleStage:
        current = await self._repository.get_stage(model_id)
        if current is None:
            raise EmbeddingModelLifecycleError("embedding_model_unregistered")
        if not is_valid_embedding_model_transition(current, target):
            raise EmbeddingModelLifecycleError("embedding_model_transition_invalid")
        await self._repository.save_stage(model_id, target)
        await self._audit(correlation_id=correlation_id, model_id=model_id, outcome=target.value)
        return target

    async def _audit(self, *, correlation_id: str, model_id: str, outcome: str) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.knowledge.embedding-model-lifecycle",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=None,
                actor_type=None,
                authentication_method=None,
                assurance_level=None,
                permission_id=None,
                resource_type="resource.knowledge.embedding-model",
                scope_reference=model_id,
                decision_id=None,
                outcome="succeeded",
                result_code=f"embedding_model_lifecycle.{outcome}",
            )
        )
