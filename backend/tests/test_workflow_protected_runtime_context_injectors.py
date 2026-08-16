from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime, timedelta

import pytest

from atlas.modules.workflows.adapters.protected_runtime_context_injectors import (
    DeterministicDevelopmentWorkflowProtectedRuntimeContextTrustedInjector,
    UnavailableWorkflowProtectedRuntimeContextTrustedInjector,
)
from atlas.modules.workflows.application.protected_runtime_context_injection_consumption_ports import (  # noqa: E501
    WorkflowProtectedRuntimeContextInjectionConsumptionError,
)
from atlas.modules.workflows.domain import (
    WorkflowProtectedRuntimeContextTrustedInjectorInvocation,
)

NOW = datetime(2026, 8, 16, 12, 0, tzinfo=UTC)


def _invocation() -> WorkflowProtectedRuntimeContextTrustedInjectorInvocation:
    return WorkflowProtectedRuntimeContextTrustedInjectorInvocation(
        protected_operation_reference="protected-operation.test",
        instruction_digest="1" * 64,
        injection_deadline=NOW + timedelta(seconds=1),
    )


@pytest.mark.asyncio
async def test_unavailable_production_default_fails_closed() -> None:
    injector = UnavailableWorkflowProtectedRuntimeContextTrustedInjector()

    assert injector.available is False
    with pytest.raises(WorkflowProtectedRuntimeContextInjectionConsumptionError):
        await injector.inject_context(_invocation())


@pytest.mark.asyncio
async def test_development_injector_receives_only_opaque_metadata_and_emits_inert_receipt() -> None:
    injector = DeterministicDevelopmentWorkflowProtectedRuntimeContextTrustedInjector(
        development_enabled=True,
        clock=lambda: NOW,
        runtime_slot_pre_generation=4,
    )

    receipt = await injector.inject_context(_invocation())

    assert [field.name for field in fields(injector.calls[0])] == [
        "protected_operation_reference",
        "instruction_digest",
        "injection_deadline",
    ]
    assert injector.verify_receipt(receipt) is True
    assert receipt.runtime_slot_pre_generation == 4
    assert receipt.runtime_slot_post_generation == 5
    assert receipt.inert_context_injected is True
    assert receipt.runtime_started is False
    assert receipt.connector_activity_performed is False
    assert receipt.network_activity_performed is False
    assert receipt.execution_performed is False
    assert receipt.infrastructure_mutation_performed is False
    assert not hasattr(receipt, "protected_runtime_handle_digest")


@pytest.mark.asyncio
async def test_development_injector_models_irreversible_single_cas_without_retry() -> None:
    injector = DeterministicDevelopmentWorkflowProtectedRuntimeContextTrustedInjector(
        development_enabled=True,
        clock=lambda: NOW,
    )
    invocation = _invocation()

    await injector.inject_context(invocation)
    with pytest.raises(WorkflowProtectedRuntimeContextInjectionConsumptionError):
        await injector.inject_context(invocation)

    assert injector.calls == [invocation]
