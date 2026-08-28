from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime

from atlas.modules.connectors.vendors.huawei_dorado.client import (
    HuaweiConnectorError,
    HuaweiDoradoClient,
)
from atlas.modules.connectors.vendors.huawei_dorado.domain import (
    HuaweiHealthStatus,
    HuaweiPoolCapacity,
)
from atlas.modules.health_checks.application.ports import HealthCheckExecutionResult
from atlas.modules.health_checks.domain.models import (
    FreshnessState,
    HealthCheckDefinition,
    HealthCheckEvidence,
    HealthCheckFinding,
    HealthCheckRunState,
    HealthObservation,
    ObservationState,
)

CONTROLLER_DEFINITION_ID = "health-check.storage.huawei-dorado.controller-status"
CONTROLLER_CAPABILITY_ID = "huawei.dorado.storage.controller.read"
CAPACITY_DEFINITION_ID = "health-check.storage.huawei-dorado.capacity-utilization"
CAPACITY_CAPABILITY_ID = "huawei.dorado.storage.pool.read"
# OceanStor's storagepool object exposes no configured warning/depletion threshold field (unlike
# Hitachi's /pools) -- see HuaweiPoolCapacity.used_capacity_percent's docstring. These are this
# connector's own fixed policy, matching Hitachi's typical defaults, not a value read from the
# array.
_CAPACITY_WARNING_PERCENT = 75.0
_CAPACITY_CRITICAL_PERCENT = 90.0

_SAFE_CONNECTOR_ERROR_CODES = frozenset(
    {
        "malformed_vendor_response",
        "target_timeout",
        "target_unavailable",
        "vendor_error_response",
        "vendor_permission_denied",
        "vendor_rate_limited",
        "vendor_response_limit_exceeded",
    }
)
_OBSERVATION_STATE: dict[HuaweiHealthStatus, ObservationState] = {
    HuaweiHealthStatus.NORMAL: ObservationState.NORMAL,
    HuaweiHealthStatus.FAULTY: ObservationState.CRITICAL,
    HuaweiHealthStatus.UNKNOWN: ObservationState.UNKNOWN,
}


def _connector_failure_reason(exc: HuaweiConnectorError) -> str:
    code = exc.code if exc.code in _SAFE_CONNECTOR_ERROR_CODES else "connector_error"
    return f"The Huawei Dorado read failed safely ({code})."


def _identity(*parts: str) -> str:
    normalized = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()[:20]


def _evidence(
    *, reference: str, observed_at: datetime, definition: HealthCheckDefinition, kind: str
) -> HealthCheckEvidence:
    return HealthCheckEvidence(
        reference=reference,
        source=f"Huawei Dorado {kind} read",
        source_version=definition.connector_version,
        observed_at=observed_at,
        freshness=FreshnessState.CURRENT,
        trust_basis="Digest-only evidence from an allowlisted C1 DeviceManager response",
    )


class HuaweiControllerHealthExecutor:
    """Executes the bounded, read-only Huawei Dorado controller health definition.

    Unlike Hitachi's two-step (inventory, then per-array health) executor, this is a single-step
    read: the system is already exactly identified by the configured connector's system_id, so
    there is no array list to enumerate first.
    """

    def __init__(
        self,
        *,
        client: HuaweiDoradoClient,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._clock = clock or (lambda: datetime.now(UTC))

    async def execute(
        self, definition: HealthCheckDefinition, *, started_at: datetime
    ) -> HealthCheckExecutionResult:
        if (
            definition.definition_id != CONTROLLER_DEFINITION_ID
            or definition.capability_id != CONTROLLER_CAPABILITY_ID
        ):
            raise ValueError("unsupported Huawei Dorado controller-check definition")
        if definition.limits.max_steps < 1 or definition.limits.max_evidence_records < 1:
            return self._failed(
                started_at, 0, "The definition budget cannot contain a controller-health read."
            )

        try:
            controllers = await self._client.read_controller_health()
        except HuaweiConnectorError as exc:
            return self._failed(
                started_at,
                1,
                _connector_failure_reason(exc),
                "Controller health is unknown because the read failed.",
            )
        if not controllers:
            return self._failed(
                started_at, 1, "No controllers were returned by the configured Huawei Dorado MCP."
            )

        observed_at = controllers[0].observed_at
        evidence = tuple(
            _evidence(
                reference=reference,
                observed_at=observed_at,
                definition=definition,
                kind="controller-health",
            )
            for reference in controllers[0].evidence_references
        )
        if len(evidence) > definition.limits.max_evidence_records:
            return self._failed(
                started_at, 1, "The controller-health evidence exceeded the definition budget."
            )

        observations: list[HealthObservation] = []
        findings: list[HealthCheckFinding] = []
        selected = controllers[: definition.limits.max_targets]
        partial_reasons: list[str] = []
        unknowns: list[str] = []
        if len(controllers) > len(selected):
            partial_reasons.append(
                "Additional controllers were omitted by the definition target budget."
            )
            unknowns.append("Health is unknown for controllers outside the bounded execution set.")

        for controller in selected:
            state = _OBSERVATION_STATE.get(controller.health_status, ObservationState.UNKNOWN)
            identity = _identity(controller.system_id, controller.controller_id)
            observation_id = f"observation.huawei.controller.{identity}"
            observations.append(
                HealthObservation(
                    observation_id=observation_id,
                    target_id=f"{definition.target_id}/{controller.system_id}",
                    component=f"controller:{controller.controller_id}",
                    metric="controller.status",
                    value=state.value,
                    unit=None,
                    state=state,
                    observed_at=controller.observed_at,
                    freshness=FreshnessState.CURRENT,
                    evidence_references=tuple(item.reference for item in evidence),
                )
            )
            if state is ObservationState.NORMAL:
                continue
            findings.append(
                HealthCheckFinding(
                    finding_id=f"finding.huawei.controller.{identity}",
                    severity=state,
                    title="Huawei controller status requires attention",
                    summary=(
                        f"Controller {controller.controller_id} ({controller.role}) was "
                        f"classified as {state.value} by the read-only health check."
                    ),
                    observation_ids=(observation_id,),
                    evidence_references=tuple(item.reference for item in evidence),
                )
            )
        if findings:
            partial_reasons.append(
                "Corroborating event evidence is not available from this bounded executor."
            )
            unknowns.append(
                "No root cause or service interruption is established by this read-only check."
            )

        run_state = (
            HealthCheckRunState.PARTIAL if partial_reasons else HealthCheckRunState.COMPLETED
        )
        return HealthCheckExecutionResult(
            state=run_state,
            completed_at=self._completed_at(started_at),
            step_count=1,
            observations=tuple(observations),
            findings=tuple(findings),
            evidence=evidence,
            partial_reasons=tuple(dict.fromkeys(partial_reasons)),
            unknowns=tuple(dict.fromkeys(unknowns)),
        )

    def _completed_at(self, started_at: datetime) -> datetime:
        return max(self._clock(), started_at)

    def _failed(
        self, started_at: datetime, step_count: int, partial_reason: str, unknown: str | None = None
    ) -> HealthCheckExecutionResult:
        return HealthCheckExecutionResult(
            state=HealthCheckRunState.FAILED,
            completed_at=self._completed_at(started_at),
            step_count=step_count,
            observations=(),
            findings=(),
            evidence=(),
            partial_reasons=(partial_reason,),
            unknowns=(unknown or "Controller health remains unknown.",),
        )


class HuaweiCapacityHealthExecutor:
    """Executes the bounded, read-only Huawei Dorado pool-capacity read."""

    def __init__(
        self,
        *,
        client: HuaweiDoradoClient,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._clock = clock or (lambda: datetime.now(UTC))

    async def execute(
        self, definition: HealthCheckDefinition, *, started_at: datetime
    ) -> HealthCheckExecutionResult:
        if (
            definition.definition_id != CAPACITY_DEFINITION_ID
            or definition.capability_id != CAPACITY_CAPABILITY_ID
        ):
            raise ValueError("unsupported Huawei Dorado capacity-check definition")
        if definition.limits.max_steps < 1 or definition.limits.max_evidence_records < 1:
            return self._failed(started_at, 0, "The definition budget cannot contain a read.")

        try:
            pools = await self._client.read_pool_capacity()
        except HuaweiConnectorError as exc:
            return self._failed(
                started_at,
                1,
                _connector_failure_reason(exc),
                "Pool capacity is unknown because the read failed.",
            )
        if not pools:
            return self._failed(
                started_at, 1, "No storage pools were returned by the configured Huawei Dorado MCP."
            )

        observed_at = pools[0].observed_at
        evidence = tuple(
            _evidence(
                reference=reference, observed_at=observed_at, definition=definition, kind="pool"
            )
            for reference in pools[0].evidence_references
        )
        if len(evidence) > definition.limits.max_evidence_records:
            return self._failed(
                started_at, 1, "The pool-capacity evidence exceeded the definition budget."
            )

        observations: list[HealthObservation] = []
        findings: list[HealthCheckFinding] = []
        selected = pools[: definition.limits.max_targets]
        partial_reasons: list[str] = []
        unknowns: list[str] = []
        if len(pools) > len(selected):
            partial_reasons.append("Additional pools were omitted by the definition target budget.")
            unknowns.append("Capacity is unknown for pools outside the bounded execution set.")

        for pool in selected:
            state = self._pool_state(pool)
            identity = _identity(pool.system_id, pool.pool_id)
            observation_id = f"observation.huawei.capacity.{identity}"
            observations.append(
                HealthObservation(
                    observation_id=observation_id,
                    target_id=f"{definition.target_id}/{pool.system_id}",
                    component=f"pool:{pool.pool_id}:{pool.pool_name}",
                    metric="pool.utilization",
                    value=str(pool.used_capacity_percent),
                    unit="percent",
                    state=state,
                    observed_at=pool.observed_at,
                    freshness=FreshnessState.CURRENT,
                    evidence_references=tuple(item.reference for item in evidence),
                )
            )
            if state is ObservationState.NORMAL:
                continue
            findings.append(
                HealthCheckFinding(
                    finding_id=f"finding.huawei.capacity.{identity}",
                    severity=state,
                    title="Huawei pool capacity requires attention",
                    summary=(
                        f"Pool {pool.pool_name} utilization is {pool.used_capacity_percent} "
                        f"percent; this connector's fixed warning and critical thresholds are "
                        f"{_CAPACITY_WARNING_PERCENT} and {_CAPACITY_CRITICAL_PERCENT} percent."
                    ),
                    observation_ids=(observation_id,),
                    evidence_references=tuple(item.reference for item in evidence),
                )
            )

        run_state = (
            HealthCheckRunState.PARTIAL if partial_reasons else HealthCheckRunState.COMPLETED
        )
        return HealthCheckExecutionResult(
            state=run_state,
            completed_at=self._completed_at(started_at),
            step_count=1,
            observations=tuple(observations),
            findings=tuple(findings),
            evidence=evidence,
            partial_reasons=tuple(dict.fromkeys(partial_reasons)),
            unknowns=tuple(dict.fromkeys(unknowns)),
        )

    @staticmethod
    def _pool_state(pool: HuaweiPoolCapacity) -> ObservationState:
        if pool.health_status is HuaweiHealthStatus.FAULTY:
            return ObservationState.CRITICAL
        if pool.used_capacity_percent >= _CAPACITY_CRITICAL_PERCENT:
            return ObservationState.CRITICAL
        if pool.used_capacity_percent >= _CAPACITY_WARNING_PERCENT:
            return ObservationState.WARNING
        if pool.health_status is HuaweiHealthStatus.UNKNOWN:
            return ObservationState.UNKNOWN
        return ObservationState.NORMAL

    def _completed_at(self, started_at: datetime) -> datetime:
        return max(self._clock(), started_at)

    def _failed(
        self, started_at: datetime, step_count: int, partial_reason: str, unknown: str | None = None
    ) -> HealthCheckExecutionResult:
        return HealthCheckExecutionResult(
            state=HealthCheckRunState.FAILED,
            completed_at=self._completed_at(started_at),
            step_count=step_count,
            observations=(),
            findings=(),
            evidence=(),
            partial_reasons=(partial_reason,),
            unknowns=(unknown or "Pool capacity remains unknown.",),
        )
