from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from atlas.modules.connectors.vendors.hitachi_ops_center.client import HitachiOpsCenterClient
from atlas.modules.connectors.vendors.hitachi_ops_center.synthetic import (
    SyntheticHitachiFault,
    SyntheticHitachiResponse,
    SyntheticHitachiTransport,
)
from atlas.modules.health_checks.adapters.hitachi import (
    HitachiCapacityHealthExecutor,
    HitachiControllerHealthExecutor,
)
from atlas.modules.health_checks.adapters.synthetic import (
    CAPACITY_DEFINITION_ID,
    build_synthetic_health_check_definitions,
)
from atlas.modules.health_checks.domain.models import (
    HealthCheckDefinition,
    HealthCheckLimits,
    HealthCheckRunState,
    ObservationState,
)

NOW = datetime(2026, 8, 25, 10, 0, tzinfo=UTC)
STORAGE_A = "836000123456"
STORAGE_B = "A34000800556"
INVENTORY_PATH = "/v1/objects/storages"
HEALTH_A_PATH = f"/v1/objects/storages/{STORAGE_A}/components/instance"
HEALTH_B_PATH = f"/v1/objects/storages/{STORAGE_B}/components/instance"
CAPACITY_A_PATH = f"/v1/objects/storages/{STORAGE_A}/pools"
ALLOWED_STORAGE_IDS = frozenset({STORAGE_A, STORAGE_B})


def definition(*, limits: HealthCheckLimits | None = None) -> HealthCheckDefinition:
    controller = build_synthetic_health_check_definitions(
        organization_id="organization.test", environment="lab", anchor_at=NOW
    )[0]
    return replace(
        controller,
        connector_id="connector.hitachi.opscenter.configuration-manager",
        limits=limits
        or HealthCheckLimits(
            timeout_seconds=5.0,
            max_steps=3,
            max_evidence_records=3,
            max_targets=2,
        ),
    )


def executor(
    routes: dict[str, SyntheticHitachiResponse],
    *,
    allowed_ids: frozenset[str] = ALLOWED_STORAGE_IDS,
) -> tuple[HitachiControllerHealthExecutor, SyntheticHitachiTransport]:
    transport = SyntheticHitachiTransport(routes)
    client = HitachiOpsCenterClient(
        transport=transport,
        allowed_storage_device_ids=allowed_ids,
        clock=lambda: NOW,
    )
    return HitachiControllerHealthExecutor(client=client, clock=lambda: NOW), transport


@pytest.mark.asyncio
async def test_all_normal_component_health_completes() -> None:
    health_executor, transport = executor(
        {
            INVENTORY_PATH: SyntheticHitachiResponse(
                payload={
                    "data": [
                        {
                            "storageDeviceId": STORAGE_A,
                            "model": "VSP G400",
                            "serialNumber": 123456,
                        }
                    ]
                }
            ),
            HEALTH_A_PATH: SyntheticHitachiResponse(
                payload={"ctls": [{"location": "CTL1", "status": "Normal"}]}
            ),
        },
        allowed_ids=frozenset({STORAGE_A}),
    )

    result = await health_executor.execute(definition(), started_at=NOW)

    assert transport.requests == [INVENTORY_PATH, HEALTH_A_PATH]
    assert result.state is HealthCheckRunState.COMPLETED
    assert result.partial_reasons == ()
    assert result.unknowns == ()
    assert len(result.observations) == 1
    assert result.observations[0].state is ObservationState.NORMAL
    assert result.findings == ()


@pytest.mark.asyncio
async def test_executes_inventory_then_component_health_and_maps_severity_safely() -> None:
    health_executor, transport = executor(
        {
            INVENTORY_PATH: SyntheticHitachiResponse(
                payload={
                    "data": [
                        {
                            "storageDeviceId": STORAGE_A,
                            "model": "VSP G400",
                            "serialNumber": 123456,
                            "password": "must-not-escape",
                        }
                    ]
                }
            ),
            HEALTH_A_PATH: SyntheticHitachiResponse(
                payload={
                    "ctls": [
                        {"location": "CTL1", "status": "Normal"},
                        {"location": "CTL2", "status": "Warning"},
                        {"location": "CTL3", "status": "Moderate"},
                        {"location": "CTL4", "status": "Failed"},
                    ],
                    "authorization": "must-not-escape",
                }
            ),
        },
        allowed_ids=frozenset({STORAGE_A}),
    )

    result = await health_executor.execute(definition(), started_at=NOW)

    assert transport.requests == [INVENTORY_PATH, HEALTH_A_PATH]
    assert result.state is HealthCheckRunState.PARTIAL
    assert result.step_count == 2
    assert [item.state for item in result.observations] == [
        ObservationState.NORMAL,
        ObservationState.WARNING,
        ObservationState.WARNING,
        ObservationState.CRITICAL,
    ]
    assert {item.severity for item in result.findings} == {
        ObservationState.WARNING,
        ObservationState.CRITICAL,
    }
    assert len(result.evidence) == 2
    disclosed = repr(result)
    assert "must-not-escape" not in disclosed
    assert "authorization" not in disclosed
    assert "password" not in disclosed
    assert all("sha256:" in item.reference for item in result.evidence)


@pytest.mark.asyncio
async def test_enforces_target_step_and_evidence_limits_without_extra_reads() -> None:
    health_executor, transport = executor(
        {
            INVENTORY_PATH: SyntheticHitachiResponse(
                payload={
                    "data": [
                        {"storageDeviceId": STORAGE_A, "model": "VSP G400", "serialNumber": 1},
                        {"storageDeviceId": STORAGE_B, "model": "VSP B28", "serialNumber": 2},
                    ]
                }
            ),
            HEALTH_A_PATH: SyntheticHitachiResponse(
                payload={"ctls": [{"location": "CTL1", "status": "Normal"}]}
            ),
            HEALTH_B_PATH: SyntheticHitachiResponse(
                payload={"ctls": [{"location": "CTL1", "status": "Normal"}]}
            ),
        }
    )
    bounded_definition = definition(
        limits=HealthCheckLimits(
            timeout_seconds=5.0,
            max_steps=2,
            max_evidence_records=2,
            max_targets=1,
        )
    )

    result = await health_executor.execute(bounded_definition, started_at=NOW)

    assert transport.requests == [INVENTORY_PATH, HEALTH_A_PATH]
    assert result.state is HealthCheckRunState.PARTIAL
    assert result.step_count <= bounded_definition.limits.max_steps
    assert len(result.evidence) <= bounded_definition.limits.max_evidence_records
    assert len({item.target_id for item in result.observations}) <= 1
    assert "bounded execution set" in " ".join(result.unknowns)


@pytest.mark.asyncio
async def test_inventory_connector_failure_returns_safe_failed_result() -> None:
    health_executor, transport = executor(
        {INVENTORY_PATH: SyntheticHitachiResponse(fault=SyntheticHitachiFault.DENIED)}
    )

    result = await health_executor.execute(definition(), started_at=NOW)

    assert transport.requests == [INVENTORY_PATH]
    assert result.state is HealthCheckRunState.FAILED
    assert result.step_count == 1
    assert result.observations == ()
    assert result.findings == ()
    assert result.evidence == ()
    assert result.partial_reasons == ("The Hitachi read failed safely (vendor_permission_denied).",)


@pytest.mark.asyncio
async def test_component_failure_after_successful_array_returns_partial_result() -> None:
    health_executor, transport = executor(
        {
            INVENTORY_PATH: SyntheticHitachiResponse(
                payload={
                    "data": [
                        {"storageDeviceId": STORAGE_A, "model": "VSP G400", "serialNumber": 1},
                        {"storageDeviceId": STORAGE_B, "model": "VSP B28", "serialNumber": 2},
                    ]
                }
            ),
            HEALTH_A_PATH: SyntheticHitachiResponse(
                payload={"ctls": [{"location": "CTL1", "status": "Normal"}]}
            ),
            HEALTH_B_PATH: SyntheticHitachiResponse(fault=SyntheticHitachiFault.TIMEOUT),
        }
    )

    result = await health_executor.execute(definition(), started_at=NOW)

    assert transport.requests == [INVENTORY_PATH, HEALTH_A_PATH, HEALTH_B_PATH]
    assert result.state is HealthCheckRunState.PARTIAL
    assert len(result.observations) == 1
    assert result.partial_reasons == ("The Hitachi read failed safely (target_timeout).",)
    assert all("detail" not in reason.lower() for reason in result.partial_reasons)


@pytest.mark.asyncio
async def test_insufficient_definition_budget_fails_without_contacting_target() -> None:
    health_executor, transport = executor({})
    insufficient = definition(
        limits=HealthCheckLimits(
            timeout_seconds=5.0,
            max_steps=1,
            max_evidence_records=1,
            max_targets=1,
        )
    )

    result = await health_executor.execute(insufficient, started_at=NOW)

    assert result.state is HealthCheckRunState.FAILED
    assert result.step_count == 0
    assert transport.requests == []


@pytest.mark.asyncio
async def test_rejects_capacity_definition_without_contacting_target() -> None:
    health_executor, transport = executor({})
    capacity = build_synthetic_health_check_definitions(
        organization_id="organization.test", environment="lab", anchor_at=NOW
    )[1]
    assert capacity.definition_id == CAPACITY_DEFINITION_ID

    with pytest.raises(ValueError, match="unsupported Hitachi health-check definition"):
        await health_executor.execute(capacity, started_at=NOW)

    assert transport.requests == []


@pytest.mark.asyncio
async def test_capacity_executor_maps_vendor_pool_thresholds() -> None:
    transport = SyntheticHitachiTransport(
        {
            INVENTORY_PATH: SyntheticHitachiResponse(
                payload={
                    "data": [{"storageDeviceId": STORAGE_A, "model": "VSP G400", "serialNumber": 1}]
                }
            ),
            CAPACITY_A_PATH: SyntheticHitachiResponse(
                payload={
                    "data": [
                        {
                            "poolId": 5,
                            "poolName": "Production",
                            "usedCapacityRate": 78,
                            "warningThreshold": 75,
                            "depletionThreshold": 90,
                        },
                        {
                            "poolId": 6,
                            "poolName": "Critical",
                            "usedCapacityRate": 94,
                            "warningThreshold": 75,
                            "depletionThreshold": 90,
                        },
                    ]
                }
            ),
        }
    )
    client = HitachiOpsCenterClient(
        transport=transport,
        allowed_storage_device_ids=frozenset({STORAGE_A}),
        clock=lambda: NOW,
    )
    capacity = replace(
        build_synthetic_health_check_definitions(
            organization_id="organization.test", environment="lab", anchor_at=NOW
        )[1],
        connector_id="connector.hitachi.opscenter.configuration-manager",
    )

    result = await HitachiCapacityHealthExecutor(client=client, clock=lambda: NOW).execute(
        capacity, started_at=NOW
    )

    assert transport.requests == [INVENTORY_PATH, CAPACITY_A_PATH]
    assert result.state is HealthCheckRunState.COMPLETED
    assert [item.state for item in result.observations] == [
        ObservationState.WARNING,
        ObservationState.CRITICAL,
    ]
    assert len(result.findings) == 2
