"""ATLAS-014 SS19: Model Lifecycle application service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditRecord, AuditSink
from atlas.modules.ai.application.model_lifecycle_ports import ModelLifecycleRepository
from atlas.modules.ai.domain.model_lifecycle import (
    ModelLifecycleStage,
    ModelVersionChangeRecord,
    is_valid_model_lifecycle_transition,
)


class ModelLifecycleError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ModelLifecycleService:
    def __init__(
        self,
        *,
        repository: ModelLifecycleRepository,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))

    async def register(self, *, model_id: str, correlation_id: str) -> ModelLifecycleStage:
        if await self._repository.get_stage(model_id) is not None:
            raise ModelLifecycleError("model_lifecycle_already_registered")
        await self._repository.save_stage(model_id, ModelLifecycleStage.REGISTERED)
        await self._audit(
            correlation_id=correlation_id,
            model_id=model_id,
            outcome=ModelLifecycleStage.REGISTERED.value,
        )
        return ModelLifecycleStage.REGISTERED

    async def transition(
        self, *, model_id: str, target: ModelLifecycleStage, correlation_id: str
    ) -> ModelLifecycleStage:
        current = await self._repository.get_stage(model_id)
        if current is None:
            raise ModelLifecycleError("model_lifecycle_unregistered")
        if not is_valid_model_lifecycle_transition(current, target):
            raise ModelLifecycleError("model_lifecycle_transition_invalid")
        await self._repository.save_stage(model_id, target)
        await self._audit(correlation_id=correlation_id, model_id=model_id, outcome=target.value)
        return target

    async def record_version_change(
        self, record: ModelVersionChangeRecord, *, correlation_id: str
    ) -> ModelVersionChangeRecord:
        await self._repository.save_change_record(record)
        await self._audit(
            correlation_id=correlation_id,
            model_id=record.model_id,
            outcome="version_change_recorded",
            actor=record.recorded_by,
        )
        return record

    async def _audit(
        self, *, correlation_id: str, model_id: str, outcome: str, actor: str | None = None
    ) -> None:
        await self._audit_sink.record(
            AuditRecord(
                event_id=f"evt_{uuid4().hex}",
                event_type="atlas.ai.model-lifecycle",
                schema_version="1.0",
                producer="project-atlas-api",
                producer_version=__version__,
                occurred_at=self._clock(),
                correlation_id=correlation_id,
                subject_id=actor,
                actor_type=None,
                authentication_method=None,
                assurance_level=None,
                permission_id=None,
                resource_type="resource.ai.model",
                scope_reference=model_id,
                decision_id=None,
                outcome=outcome,
                result_code=f"model_lifecycle.{outcome}",
            )
        )
