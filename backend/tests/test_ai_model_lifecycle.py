from __future__ import annotations

from datetime import UTC, datetime

import pytest

from atlas.core.audit import AuditRecord
from atlas.modules.ai.adapters.model_lifecycle_memory import InMemoryModelLifecycleRepository
from atlas.modules.ai.application.model_lifecycle import (
    ModelLifecycleError,
    ModelLifecycleService,
)
from atlas.modules.ai.domain.model_lifecycle import (
    ModelLifecycleStage,
    ModelVersionChangeRecord,
    a_non_immutable_model_alias_is_recorded_as_a_production_model_identity,
    is_valid_model_lifecycle_transition,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)


def _change_record(**overrides: object) -> ModelVersionChangeRecord:
    values: dict[str, object] = {
        "change_id": "change.model-local-llama.v2",
        "model_id": "model.local-llama-70b",
        "prior_version": "2026-08-01",
        "new_version": "2026-09-01",
        "identity_and_capability_comparison": "New version adds structured-output mode parity.",
        "evaluation_suite_reference": "evaluation.suite.grounded-answer.v3",
        "hosting_or_behavior_changed": False,
        "security_privacy_review_reference": None,
        "compatibility_validation_reference": "validation.structured-output.v3",
        "performance_capacity_validation_reference": "validation.performance.v3",
        "rollback_readiness_reference": "rollback.plan.model-local-llama.v2",
        "release_note": "Improved grounded-answer citation fidelity.",
        "affected_agent_ids": ("agent.root-cause",),
        "recorded_by": "subject.ai-platform-owner.primary",
        "recorded_at": NOW,
    }
    values.update(overrides)
    return ModelVersionChangeRecord(**values)  # type: ignore[arg-type]


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


def _service() -> tuple[ModelLifecycleService, CollectingAuditSink]:
    audit_sink = CollectingAuditSink()
    service = ModelLifecycleService(
        repository=InMemoryModelLifecycleRepository(),
        audit_sink=audit_sink,
        clock=lambda: NOW,
    )
    return service, audit_sink


def test_absolute_rule_is_false() -> None:
    assert a_non_immutable_model_alias_is_recorded_as_a_production_model_identity() is False


def test_diagram_transitions_are_valid() -> None:
    assert (
        is_valid_model_lifecycle_transition(
            ModelLifecycleStage.REGISTERED, ModelLifecycleStage.UNDER_EVALUATION
        )
        is True
    )
    assert (
        is_valid_model_lifecycle_transition(
            ModelLifecycleStage.UNDER_EVALUATION,
            ModelLifecycleStage.APPROVED_FOR_PRODUCTION_TASKS,
        )
        is True
    )


def test_undiagrammed_transitions_are_rejected() -> None:
    assert (
        is_valid_model_lifecycle_transition(
            ModelLifecycleStage.REGISTERED, ModelLifecycleStage.APPROVED_FOR_PRODUCTION_TASKS
        )
        is False
    )
    assert (
        is_valid_model_lifecycle_transition(
            ModelLifecycleStage.RETIRED, ModelLifecycleStage.REGISTERED
        )
        is False
    )


def test_change_record_rejects_a_mutable_alias() -> None:
    with pytest.raises(ValueError, match="not sufficient production model identities"):
        _change_record(new_version="latest")


def test_change_record_requires_security_review_when_hosting_changes() -> None:
    with pytest.raises(ValueError, match="security and privacy review is required"):
        _change_record(hosting_or_behavior_changed=True, security_privacy_review_reference=None)
    record = _change_record(
        hosting_or_behavior_changed=True,
        security_privacy_review_reference="review.security.model-local-llama.v2",
    )
    assert record.hosting_or_behavior_changed is True


def test_change_record_forbids_a_review_reference_when_nothing_changed() -> None:
    with pytest.raises(ValueError, match="only recorded when hosting or"):
        _change_record(
            hosting_or_behavior_changed=False,
            security_privacy_review_reference="review.security.unnecessary",
        )


@pytest.mark.asyncio
async def test_register_then_transition_through_the_lifecycle() -> None:
    service, audit_sink = _service()
    stage = await service.register(
        model_id="model.local-llama-70b", correlation_id="correlation.test"
    )
    assert stage is ModelLifecycleStage.REGISTERED
    await service.transition(
        model_id="model.local-llama-70b",
        target=ModelLifecycleStage.UNDER_EVALUATION,
        correlation_id="correlation.test",
    )
    approved = await service.transition(
        model_id="model.local-llama-70b",
        target=ModelLifecycleStage.APPROVED_FOR_PRODUCTION_TASKS,
        correlation_id="correlation.test",
    )
    assert approved is ModelLifecycleStage.APPROVED_FOR_PRODUCTION_TASKS
    assert any(
        item.result_code == "model_lifecycle.approved_for_production_tasks"
        for item in audit_sink.records
    )


@pytest.mark.asyncio
async def test_register_twice_is_refused() -> None:
    service, _audit = _service()
    await service.register(model_id="model.local-llama-70b", correlation_id="correlation.test")
    with pytest.raises(ModelLifecycleError, match="model_lifecycle_already_registered"):
        await service.register(model_id="model.local-llama-70b", correlation_id="correlation.test")


@pytest.mark.asyncio
async def test_transition_requires_prior_registration() -> None:
    service, _audit = _service()
    with pytest.raises(ModelLifecycleError, match="model_lifecycle_unregistered"):
        await service.transition(
            model_id="model.unregistered",
            target=ModelLifecycleStage.UNDER_EVALUATION,
            correlation_id="correlation.test",
        )


@pytest.mark.asyncio
async def test_transition_rejects_an_undiagrammed_target() -> None:
    service, _audit = _service()
    await service.register(model_id="model.local-llama-70b", correlation_id="correlation.test")
    with pytest.raises(ModelLifecycleError, match="model_lifecycle_transition_invalid"):
        await service.transition(
            model_id="model.local-llama-70b",
            target=ModelLifecycleStage.APPROVED_FOR_PRODUCTION_TASKS,
            correlation_id="correlation.test",
        )


@pytest.mark.asyncio
async def test_record_version_change() -> None:
    service, audit_sink = _service()
    record = await service.record_version_change(
        _change_record(), correlation_id="correlation.test"
    )
    assert record.new_version == "2026-09-01"
    assert any(
        item.result_code == "model_lifecycle.version_change_recorded" for item in audit_sink.records
    )
