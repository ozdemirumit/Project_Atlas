from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from atlas.core.capabilities import CapabilityClass
from atlas.modules.connectors.adapters.simulator import (
    ConnectorSimulatorRunner,
    ResultState,
    SimulatorFixture,
    SimulatorInvocationContext,
    SimulatorIsolationPolicy,
    SimulatorScenario,
)
from atlas.modules.connectors.domain.models import (
    CapabilityManifest,
    ConnectorHealth,
    ConnectorInstance,
    IdempotencyClass,
    InstanceLifecycle,
    SideEffect,
)

NOW = datetime(2026, 8, 3, 15, 0, tzinfo=UTC)


def capability() -> CapabilityManifest:
    return CapabilityManifest(
        capability_id="storage.health.read",
        version="1.0.0",
        description="Read synthetic storage health.",
        capability_class=CapabilityClass.C1_READ_ONLY,
        side_effects=frozenset({SideEffect.READ}),
        target_types=("target.storage.array",),
        timeout_seconds=30,
        idempotency=IdempotencyClass.SAFE,
    )


def instance() -> ConnectorInstance:
    return ConnectorInstance(
        instance_id="instance.storage.lab",
        package_id="connector.simulator.storage",
        package_version="1.0.0",
        organization_id="organization.test",
        environment_id="environment.test",
        site_id="site.lab",
        target_id="target.storage.lab",
        enabled_capability_ids=frozenset({"storage.health.read"}),
        secret_reference_ids=(),
        lifecycle=InstanceLifecycle.ENABLED,
        health=ConnectorHealth.HEALTHY,
        configuration_revision=2,
        created_at=NOW,
        created_by="subject.test.operator",
    )


def context(**overrides: object) -> SimulatorInvocationContext:
    values: dict[str, object] = {
        "invocation_id": "invocation.simulator.test",
        "correlation_id": "cor_simulator_test",
        "organization_id": "organization.test",
        "environment_id": "environment.test",
        "site_id": "site.lab",
        "target_id": "target.storage.lab",
        "instance_id": "instance.storage.lab",
        "capability_id": "storage.health.read",
        "capability_version": "1.0.0",
        "deadline": NOW + timedelta(minutes=1),
    }
    values.update(overrides)
    return SimulatorInvocationContext(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("scenario", "expected_state", "expected_error", "retryable"),
    [
        (SimulatorScenario.SUCCESS, ResultState.SUCCEEDED, None, False),
        (SimulatorScenario.EMPTY, ResultState.SUCCEEDED, None, False),
        (SimulatorScenario.DENIED, ResultState.FAILED, "vendor_permission_denied", False),
        (SimulatorScenario.TIMEOUT, ResultState.TIMED_OUT, "target_timeout", True),
        (SimulatorScenario.THROTTLED, ResultState.FAILED, "vendor_rate_limited", True),
        (
            SimulatorScenario.MALFORMED,
            ResultState.FAILED,
            "malformed_vendor_response",
            False,
        ),
        (SimulatorScenario.PARTIAL, ResultState.PARTIAL, "partial_result", False),
        (SimulatorScenario.UNKNOWN, ResultState.UNCERTAIN, "outcome_uncertain", False),
        (SimulatorScenario.VENDOR_ERROR, ResultState.FAILED, "vendor_internal_error", False),
    ],
)
@pytest.mark.asyncio
async def test_simulator_produces_deterministic_scenarios(
    scenario: SimulatorScenario,
    expected_state: ResultState,
    expected_error: str | None,
    retryable: bool,
) -> None:
    runner = ConnectorSimulatorRunner(clock=lambda: NOW)

    result = await runner.invoke(
        instance=instance(),
        capability=capability(),
        context=context(),
        parameters={"include_components": True},
        fixture=SimulatorFixture(
            scenario=scenario,
            output={"status": "healthy"},
            evidence_references=("simulator://fixture/storage-health",),
        ),
    )

    assert result.state is expected_state
    assert result.error_code == expected_error
    assert result.retryable is retryable
    if expected_state is ResultState.SUCCEEDED:
        assert result.evidence_references


@pytest.mark.asyncio
async def test_simulator_rejects_scope_and_capability_binding_mismatch() -> None:
    runner = ConnectorSimulatorRunner(clock=lambda: NOW)

    result = await runner.invoke(
        instance=instance(),
        capability=capability(),
        context=context(target_id="target.storage.other"),
        parameters={},
        fixture=SimulatorFixture(scenario=SimulatorScenario.SUCCESS, output={}),
    )

    assert result.state is ResultState.FAILED
    assert result.error_code == "invocation_scope_mismatch"


@pytest.mark.asyncio
async def test_simulator_enforces_deadline_and_output_bound() -> None:
    runner = ConnectorSimulatorRunner(
        policy=SimulatorIsolationPolicy(maximum_output_bytes=16), clock=lambda: NOW
    )
    expired = await runner.invoke(
        instance=instance(),
        capability=capability(),
        context=context(deadline=NOW),
        parameters={},
        fixture=SimulatorFixture(scenario=SimulatorScenario.SUCCESS, output={}),
    )
    oversized = await runner.invoke(
        instance=instance(),
        capability=capability(),
        context=context(),
        parameters={},
        fixture=SimulatorFixture(scenario=SimulatorScenario.SUCCESS, output={"payload": "x" * 128}),
    )

    assert expired.state is ResultState.TIMED_OUT
    assert expired.error_code == "deadline_expired"
    assert oversized.state is ResultState.FAILED
    assert oversized.error_code == "output_limit_exceeded"


@pytest.mark.asyncio
async def test_simulator_isolation_cannot_enable_external_access() -> None:
    with pytest.raises(ValueError, match="cannot receive external access"):
        SimulatorIsolationPolicy(network_access=True)

    result = await ConnectorSimulatorRunner(clock=lambda: NOW).self_test(instance())
    assert result.health is ConnectorHealth.HEALTHY
    assert result.code == "simulator_isolation_verified"
