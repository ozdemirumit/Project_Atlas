from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime

from atlas.modules.connectors.vendors.hitachi_ops_center.client import (
    HitachiConnectorError,
    HitachiOpsCenterClient,
)
from atlas.modules.connectors.vendors.hitachi_ops_center.domain import (
    HealthSeverity,
    HitachiCapacityResult,
    HitachiComponentHealth,
    HitachiHealthResult,
    HitachiPoolCapacity,
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

CONTROLLER_DEFINITION_ID = "health-check.storage.controller-status"
CONTROLLER_CAPABILITY_ID = "hitachi.opscenter.storage.hardware.read"
CAPACITY_DEFINITION_ID = "health-check.storage.capacity-utilization"
CAPACITY_CAPABILITY_ID = "hitachi.opscenter.storage.capacity.read"

_SAFE_CONNECTOR_ERROR_CODES = frozenset(
    {
        "invalid_storage_device_id",
        "malformed_vendor_response",
        "target_not_bound",
        "target_timeout",
        "target_unavailable",
        "unsupported_vendor_version",
        "vendor_permission_denied",
        "vendor_rate_limited",
        "vendor_response_limit_exceeded",
    }
)
_OBSERVATION_STATE = {
    HealthSeverity.NORMAL: ObservationState.NORMAL,
    HealthSeverity.WARNING: ObservationState.WARNING,
    HealthSeverity.DEGRADED: ObservationState.WARNING,
    HealthSeverity.CRITICAL: ObservationState.CRITICAL,
    HealthSeverity.UNKNOWN: ObservationState.UNKNOWN,
}


class HitachiControllerHealthExecutor:
    """Executes the bounded, read-only Hitachi controller health definition."""

    def __init__(
        self,
        *,
        client: HitachiOpsCenterClient,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._clock = clock or (lambda: datetime.now(UTC))

    async def execute(
        self, definition: HealthCheckDefinition, *, started_at: datetime
    ) -> HealthCheckExecutionResult:
        self._validate_definition(definition)
        if definition.limits.max_steps < 2 or definition.limits.max_evidence_records < 2:
            return self._failed_result(
                started_at=started_at,
                step_count=0,
                partial_reason="The definition budget cannot contain inventory and health reads.",
                unknown="Target health is unknown because the definition budget is insufficient.",
            )

        step_count = 1
        try:
            inventory = await self._client.read_inventory()
        except HitachiConnectorError as exc:
            return self._failed_result(
                started_at=started_at,
                step_count=step_count,
                partial_reason=self._connector_failure_reason(exc),
                unknown="Target health is unknown because storage inventory could not be read.",
            )

        if len(inventory.evidence_references) > definition.limits.max_evidence_records:
            return self._failed_result(
                started_at=started_at,
                step_count=step_count,
                partial_reason="The inventory evidence exceeded the definition budget.",
                unknown="Target health is unknown because the bounded result was rejected.",
            )

        evidence = [
            self._evidence(
                reference=reference,
                observed_at=inventory.observed_at,
                definition=definition,
                kind="inventory",
            )
            for reference in inventory.evidence_references
        ]
        observations: list[HealthObservation] = []
        findings: list[HealthCheckFinding] = []
        partial_reasons: list[str] = []
        unknowns: list[str] = []
        successful_health_reads = 0

        remaining_step_budget = definition.limits.max_steps - step_count
        remaining_evidence_budget = definition.limits.max_evidence_records - len(evidence)
        target_budget = min(
            definition.limits.max_targets,
            remaining_step_budget,
            remaining_evidence_budget,
        )
        selected_arrays = inventory.arrays[:target_budget]
        if len(inventory.arrays) > target_budget:
            partial_reasons.append(
                "Additional allowlisted arrays were omitted by the definition target "
                "or read budget."
            )
            unknowns.append("Health is unknown for arrays outside the bounded execution set.")
        if not inventory.arrays:
            partial_reasons.append("No allowlisted storage arrays were returned by inventory.")
            unknowns.append("No component health could be evaluated.")

        for array in selected_arrays:
            step_count += 1
            try:
                health = await self._client.read_hardware_health(array.storage_device_id)
            except HitachiConnectorError as exc:
                partial_reasons.append(self._connector_failure_reason(exc))
                unknowns.append("Component health is unknown for an allowlisted storage array.")
                continue

            if len(evidence) + len(health.evidence_references) > (
                definition.limits.max_evidence_records
            ):
                partial_reasons.append(
                    "A component-health evidence set exceeded the remaining definition budget."
                )
                unknowns.append("Component health was omitted because its evidence was incomplete.")
                continue

            health_evidence = tuple(
                self._evidence(
                    reference=reference,
                    observed_at=health.observed_at,
                    definition=definition,
                    kind="component-health",
                )
                for reference in health.evidence_references
            )
            evidence.extend(health_evidence)
            successful_health_reads += 1
            mapped_observations, mapped_findings = self._map_health(
                definition=definition,
                health=health,
                evidence_references=tuple(item.reference for item in health_evidence),
            )
            observations.extend(mapped_observations)
            findings.extend(mapped_findings)

            if health.warnings:
                partial_reasons.append(
                    "The vendor returned component health that could not be fully normalized."
                )
                unknowns.append("At least one component state remains unknown.")
            if mapped_findings:
                partial_reasons.append(
                    "Corroborating event evidence is not available from this bounded executor."
                )
                unknowns.append(
                    "No root cause or service interruption is established by this read-only check."
                )

        if successful_health_reads == 0:
            state = HealthCheckRunState.FAILED if inventory.arrays else HealthCheckRunState.PARTIAL
        elif partial_reasons:
            state = HealthCheckRunState.PARTIAL
        else:
            state = HealthCheckRunState.COMPLETED

        return HealthCheckExecutionResult(
            state=state,
            completed_at=self._completed_at(started_at),
            step_count=step_count,
            observations=tuple(observations),
            findings=tuple(findings),
            evidence=tuple(evidence),
            partial_reasons=tuple(dict.fromkeys(partial_reasons)),
            unknowns=tuple(dict.fromkeys(unknowns)),
        )

    @staticmethod
    def _validate_definition(definition: HealthCheckDefinition) -> None:
        if (
            definition.definition_id != CONTROLLER_DEFINITION_ID
            or definition.capability_id != CONTROLLER_CAPABILITY_ID
        ):
            raise ValueError("unsupported Hitachi health-check definition")

    @staticmethod
    def _evidence(
        *,
        reference: str,
        observed_at: datetime,
        definition: HealthCheckDefinition,
        kind: str,
    ) -> HealthCheckEvidence:
        return HealthCheckEvidence(
            reference=reference,
            source=f"Hitachi Ops Center {kind} read",
            source_version=definition.connector_version,
            observed_at=observed_at,
            freshness=FreshnessState.CURRENT,
            trust_basis="Digest-only evidence from an allowlisted C1 HTTPS GET response",
        )

    @classmethod
    def _map_health(
        cls,
        *,
        definition: HealthCheckDefinition,
        health: HitachiHealthResult,
        evidence_references: tuple[str, ...],
    ) -> tuple[list[HealthObservation], list[HealthCheckFinding]]:
        components = health.components or (
            HitachiComponentHealth(
                category="hardware",
                location="storage-array",
                vendor_status="unknown",
                severity=HealthSeverity.UNKNOWN,
            ),
        )
        observations: list[HealthObservation] = []
        findings: list[HealthCheckFinding] = []
        for index, component in enumerate(components):
            state = _OBSERVATION_STATE[component.severity]
            identity = cls._identity(
                health.storage_device_id,
                component.category,
                component.location,
                str(index),
            )
            observation_id = f"observation.hitachi.controller.{identity}"
            observation = HealthObservation(
                observation_id=observation_id,
                target_id=f"{definition.target_id}/{health.storage_device_id}",
                component=f"{component.category}:{component.location}",
                metric="controller.status",
                value=state.value,
                unit=None,
                state=state,
                observed_at=health.observed_at,
                freshness=FreshnessState.CURRENT,
                evidence_references=evidence_references,
            )
            observations.append(observation)
            if state is ObservationState.NORMAL:
                continue
            findings.append(
                HealthCheckFinding(
                    finding_id=f"finding.hitachi.controller.{identity}",
                    severity=state,
                    title="Hitachi component status requires attention",
                    summary=(
                        "An allowlisted component was classified as "
                        f"{state.value} by the read-only health check."
                    ),
                    observation_ids=(observation_id,),
                    evidence_references=evidence_references,
                )
            )
        return observations, findings

    @staticmethod
    def _identity(*parts: str) -> str:
        normalized = "\x1f".join(parts).encode("utf-8")
        return hashlib.sha256(normalized).hexdigest()[:20]

    @staticmethod
    def _connector_failure_reason(exc: HitachiConnectorError) -> str:
        code = exc.code if exc.code in _SAFE_CONNECTOR_ERROR_CODES else "connector_error"
        return f"The Hitachi read failed safely ({code})."

    def _failed_result(
        self,
        *,
        started_at: datetime,
        step_count: int,
        partial_reason: str,
        unknown: str,
    ) -> HealthCheckExecutionResult:
        return HealthCheckExecutionResult(
            state=HealthCheckRunState.FAILED,
            completed_at=self._completed_at(started_at),
            step_count=step_count,
            observations=(),
            findings=(),
            evidence=(),
            partial_reasons=(partial_reason,),
            unknowns=(unknown,),
        )

    def _completed_at(self, started_at: datetime) -> datetime:
        return max(self._clock(), started_at)


class HitachiCapacityHealthExecutor:
    """Executes bounded, read-only pool-capacity reads for allowlisted arrays."""

    def __init__(
        self,
        *,
        client: HitachiOpsCenterClient,
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
            raise ValueError("unsupported Hitachi capacity-check definition")
        if definition.limits.max_steps < 2 or definition.limits.max_evidence_records < 2:
            return self._failed(
                definition,
                started_at,
                "The definition budget cannot contain inventory and capacity reads.",
                "Pool capacity is unknown because the definition budget is insufficient.",
            )

        try:
            inventory = await self._client.read_inventory()
        except HitachiConnectorError as exc:
            return self._failed(
                definition,
                started_at,
                HitachiControllerHealthExecutor._connector_failure_reason(exc),
                "Pool capacity is unknown because storage inventory could not be read.",
                step_count=1,
            )

        evidence = [
            HitachiControllerHealthExecutor._evidence(
                reference=reference,
                observed_at=inventory.observed_at,
                definition=definition,
                kind="inventory",
            )
            for reference in inventory.evidence_references
        ]
        if len(evidence) > definition.limits.max_evidence_records:
            return self._failed(
                definition,
                started_at,
                "The inventory evidence exceeded the definition budget.",
                "Pool capacity is unknown because the bounded result was rejected.",
                step_count=1,
            )

        step_count = 1
        observations: list[HealthObservation] = []
        findings: list[HealthCheckFinding] = []
        partial_reasons: list[str] = []
        unknowns: list[str] = []
        successful_reads = 0
        target_budget = min(
            definition.limits.max_targets,
            definition.limits.max_steps - step_count,
            definition.limits.max_evidence_records - len(evidence),
        )
        selected_arrays = inventory.arrays[:target_budget]
        if len(inventory.arrays) > target_budget:
            partial_reasons.append(
                "Additional allowlisted arrays were omitted by the definition target "
                "or read budget."
            )
            unknowns.append("Capacity is unknown for arrays outside the bounded execution set.")
        if not inventory.arrays:
            partial_reasons.append("No allowlisted storage arrays were returned by inventory.")
            unknowns.append("No pool capacity could be evaluated.")

        for array in selected_arrays:
            step_count += 1
            try:
                capacity = await self._client.read_pool_capacity(array.storage_device_id)
            except HitachiConnectorError as exc:
                partial_reasons.append(
                    HitachiControllerHealthExecutor._connector_failure_reason(exc)
                )
                unknowns.append("Pool capacity is unknown for an allowlisted storage array.")
                continue
            if len(evidence) + len(capacity.evidence_references) > (
                definition.limits.max_evidence_records
            ):
                partial_reasons.append(
                    "A capacity evidence set exceeded the remaining definition budget."
                )
                unknowns.append("Pool capacity was omitted because its evidence was incomplete.")
                continue

            capacity_evidence = tuple(
                HitachiControllerHealthExecutor._evidence(
                    reference=reference,
                    observed_at=capacity.observed_at,
                    definition=definition,
                    kind="pool-capacity",
                )
                for reference in capacity.evidence_references
            )
            evidence.extend(capacity_evidence)
            successful_reads += 1
            mapped_observations, mapped_findings = self._map_capacity(
                definition=definition,
                capacity=capacity,
                evidence_references=tuple(item.reference for item in capacity_evidence),
            )
            observations.extend(mapped_observations)
            findings.extend(mapped_findings)
            if not capacity.pools:
                partial_reasons.append("The allowlisted storage array returned no pools.")
                unknowns.append("No pool utilization could be evaluated for one storage array.")

        if successful_reads == 0:
            state = HealthCheckRunState.FAILED if inventory.arrays else HealthCheckRunState.PARTIAL
        elif partial_reasons:
            state = HealthCheckRunState.PARTIAL
        else:
            state = HealthCheckRunState.COMPLETED
        return HealthCheckExecutionResult(
            state=state,
            completed_at=max(self._clock(), started_at),
            step_count=step_count,
            observations=tuple(observations),
            findings=tuple(findings),
            evidence=tuple(evidence),
            partial_reasons=tuple(dict.fromkeys(partial_reasons)),
            unknowns=tuple(dict.fromkeys(unknowns)),
        )

    @classmethod
    def _map_capacity(
        cls,
        *,
        definition: HealthCheckDefinition,
        capacity: HitachiCapacityResult,
        evidence_references: tuple[str, ...],
    ) -> tuple[list[HealthObservation], list[HealthCheckFinding]]:
        observations: list[HealthObservation] = []
        findings: list[HealthCheckFinding] = []
        for pool in capacity.pools:
            state = cls._pool_state(pool)
            identity = HitachiControllerHealthExecutor._identity(
                capacity.storage_device_id, str(pool.pool_id)
            )
            observation_id = f"observation.hitachi.capacity.{identity}"
            observations.append(
                HealthObservation(
                    observation_id=observation_id,
                    target_id=f"{definition.target_id}/{capacity.storage_device_id}",
                    component=f"pool:{pool.pool_id}:{pool.pool_name}",
                    metric="pool.utilization",
                    value=str(pool.used_capacity_rate),
                    unit="percent",
                    state=state,
                    observed_at=capacity.observed_at,
                    freshness=FreshnessState.CURRENT,
                    evidence_references=evidence_references,
                )
            )
            if state is ObservationState.NORMAL:
                continue
            findings.append(
                HealthCheckFinding(
                    finding_id=f"finding.hitachi.capacity.{identity}",
                    severity=state,
                    title="Hitachi pool capacity requires attention",
                    summary=(
                        f"Pool utilization is {pool.used_capacity_rate} percent; the configured "
                        f"warning and depletion thresholds are {pool.warning_threshold} and "
                        f"{pool.depletion_threshold} percent."
                    ),
                    observation_ids=(observation_id,),
                    evidence_references=evidence_references,
                )
            )
        return observations, findings

    @staticmethod
    def _pool_state(pool: HitachiPoolCapacity) -> ObservationState:
        if pool.used_capacity_rate >= pool.depletion_threshold:
            return ObservationState.CRITICAL
        if pool.used_capacity_rate >= pool.warning_threshold:
            return ObservationState.WARNING
        return ObservationState.NORMAL

    def _failed(
        self,
        definition: HealthCheckDefinition,
        started_at: datetime,
        reason: str,
        unknown: str,
        *,
        step_count: int = 0,
    ) -> HealthCheckExecutionResult:
        del definition
        return HealthCheckExecutionResult(
            state=HealthCheckRunState.FAILED,
            completed_at=max(self._clock(), started_at),
            step_count=step_count,
            observations=(),
            findings=(),
            evidence=(),
            partial_reasons=(reason,),
            unknowns=(unknown,),
        )
