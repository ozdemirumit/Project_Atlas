from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime

from atlas.modules.connectors.vendors.huawei_pacific.client import (
    HuaweiPacificClient,
    HuaweiPacificConnectorError,
)
from atlas.modules.connectors.vendors.huawei_pacific.domain import (
    HuaweiPacificNodeRunningStatus,
    HuaweiPacificPoolCapacity,
    HuaweiPacificPoolStatus,
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

CLUSTER_NODE_DEFINITION_ID = "health-check.storage.huawei-pacific.node-status"
CLUSTER_NODE_CAPABILITY_ID = "huawei.pacific.storage.cluster.read"
CAPACITY_DEFINITION_ID = "health-check.storage.huawei-pacific.capacity-utilization"
CAPACITY_CAPABILITY_ID = "huawei.pacific.storage.pool.read"
# Pacific's storagepool object exposes no configured warning/depletion threshold field (same
# confirmed gap as Dorado's /storagepool) -- this connector's own fixed policy, not a value read
# from the cluster.
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
_NODE_OBSERVATION_STATE: dict[HuaweiPacificNodeRunningStatus, ObservationState] = {
    HuaweiPacificNodeRunningStatus.ONLINE: ObservationState.NORMAL,
    HuaweiPacificNodeRunningStatus.OFFLINE: ObservationState.CRITICAL,
    HuaweiPacificNodeRunningStatus.UNKNOWN: ObservationState.UNKNOWN,
}
_POOL_OBSERVATION_STATE: dict[HuaweiPacificPoolStatus, ObservationState] = {
    HuaweiPacificPoolStatus.NORMAL: ObservationState.NORMAL,
    HuaweiPacificPoolStatus.DEGRADED: ObservationState.WARNING,
    HuaweiPacificPoolStatus.MIGRATING: ObservationState.WARNING,
    HuaweiPacificPoolStatus.REBUILDING: ObservationState.WARNING,
    HuaweiPacificPoolStatus.WRITE_PROTECTED: ObservationState.CRITICAL,
    HuaweiPacificPoolStatus.FAULTY: ObservationState.CRITICAL,
    HuaweiPacificPoolStatus.STOPPED: ObservationState.CRITICAL,
    HuaweiPacificPoolStatus.FAULTY_AND_WRITE_PROTECTED: ObservationState.CRITICAL,
    HuaweiPacificPoolStatus.UNKNOWN: ObservationState.UNKNOWN,
}


def _connector_failure_reason(exc: HuaweiPacificConnectorError) -> str:
    code = exc.code if exc.code in _SAFE_CONNECTOR_ERROR_CODES else "connector_error"
    return f"The Huawei Pacific read failed safely ({code})."


def _identity(*parts: str) -> str:
    normalized = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()[:20]


def _evidence(
    *, reference: str, observed_at: datetime, definition: HealthCheckDefinition, kind: str
) -> HealthCheckEvidence:
    return HealthCheckEvidence(
        reference=reference,
        source=f"Huawei Pacific {kind} read",
        source_version=definition.connector_version,
        observed_at=observed_at,
        freshness=FreshnessState.CURRENT,
        trust_basis="Digest-only evidence from an allowlisted C1 cluster-manager response",
    )


class HuaweiPacificNodeHealthExecutor:
    """Executes the bounded, read-only Huawei Pacific cluster-node running-status check.

    Single-step, like Huawei Dorado's controller check: the cluster is already exactly identified
    by the configured connector's management endpoint, so there is no separate list-then-read
    step required.
    """

    def __init__(
        self,
        *,
        client: HuaweiPacificClient,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._clock = clock or (lambda: datetime.now(UTC))

    async def execute(
        self, definition: HealthCheckDefinition, *, started_at: datetime
    ) -> HealthCheckExecutionResult:
        if (
            definition.definition_id != CLUSTER_NODE_DEFINITION_ID
            or definition.capability_id != CLUSTER_NODE_CAPABILITY_ID
        ):
            raise ValueError("unsupported Huawei Pacific node-status definition")
        if definition.limits.max_steps < 1 or definition.limits.max_evidence_records < 1:
            return self._failed(
                started_at, 0, "The definition budget cannot contain a cluster-node read."
            )

        try:
            inventory = await self._client.read_cluster_inventory()
        except HuaweiPacificConnectorError as exc:
            return self._failed(
                started_at,
                1,
                _connector_failure_reason(exc),
                "Node status is unknown because the read failed.",
            )
        if not inventory.nodes:
            return self._failed(
                started_at,
                1,
                "No cluster nodes were returned by the configured Huawei Pacific MCP.",
            )

        evidence = tuple(
            _evidence(
                reference=reference,
                observed_at=inventory.observed_at,
                definition=definition,
                kind="cluster-node",
            )
            for reference in inventory.evidence_references
        )
        if len(evidence) > definition.limits.max_evidence_records:
            return self._failed(
                started_at, 1, "The cluster-node evidence exceeded the definition budget."
            )

        observations: list[HealthObservation] = []
        findings: list[HealthCheckFinding] = []
        selected = inventory.nodes[: definition.limits.max_targets]
        partial_reasons: list[str] = []
        unknowns: list[str] = []
        if len(inventory.nodes) > len(selected):
            partial_reasons.append("Additional nodes were omitted by the definition target budget.")
            unknowns.append("Status is unknown for nodes outside the bounded execution set.")

        for node in selected:
            state = _NODE_OBSERVATION_STATE.get(node.running_status, ObservationState.UNKNOWN)
            identity = _identity(node.node_id)
            observation_id = f"observation.huawei-pacific.node.{identity}"
            observations.append(
                HealthObservation(
                    observation_id=observation_id,
                    target_id=f"{definition.target_id}/{node.node_id}",
                    component=f"node:{node.node_id}:{node.name}",
                    metric="node.running_status",
                    value=state.value,
                    unit=None,
                    state=state,
                    observed_at=inventory.observed_at,
                    freshness=FreshnessState.CURRENT,
                    evidence_references=tuple(item.reference for item in evidence),
                )
            )
            if node.oam_agent_status is not None:
                observations.append(
                    HealthObservation(
                        observation_id=f"observation.huawei-pacific.node.{identity}.oam-agent",
                        target_id=f"{definition.target_id}/{node.node_id}",
                        component=f"node:{node.node_id}:{node.name}",
                        metric="node.oam_agent_status",
                        value=node.oam_agent_status,
                        unit=None,
                        # Value vocabulary is not confirmed (see domain.py) -- reported as
                        # informational only, never used to derive severity or a finding.
                        state=ObservationState.UNKNOWN,
                        observed_at=inventory.observed_at,
                        freshness=FreshnessState.CURRENT,
                        evidence_references=tuple(item.reference for item in evidence),
                    )
                )
            if node.warranty_status is not None:
                observations.append(
                    HealthObservation(
                        observation_id=f"observation.huawei-pacific.node.{identity}.warranty",
                        target_id=f"{definition.target_id}/{node.node_id}",
                        component=f"node:{node.node_id}:{node.name}",
                        metric="node.warranty_status",
                        value=node.warranty_status,
                        unit=None,
                        state=ObservationState.UNKNOWN,
                        observed_at=inventory.observed_at,
                        freshness=FreshnessState.CURRENT,
                        evidence_references=tuple(item.reference for item in evidence),
                    )
                )
            if node.error_code is not None:
                # error_code's own vocabulary is unconfirmed, but treating a present, non-zero
                # code as a signal worth surfacing (rather than silently dropping it) matches this
                # same connector's own established convention for interpreting vendor "code"
                # fields (see client.py's _bounded(), which treats a non-zero/non-"0" result.code
                # as a logical error) -- WARNING rather than CRITICAL because the exact severity
                # behind an unrecognized code is still unknown.
                error_present = node.error_code not in ("0", "")
                error_state = ObservationState.WARNING if error_present else ObservationState.NORMAL
                error_observation_id = f"observation.huawei-pacific.node.{identity}.error-code"
                observations.append(
                    HealthObservation(
                        observation_id=error_observation_id,
                        target_id=f"{definition.target_id}/{node.node_id}",
                        component=f"node:{node.node_id}:{node.name}",
                        metric="node.error_code",
                        value=node.error_code,
                        unit=None,
                        state=error_state,
                        observed_at=inventory.observed_at,
                        freshness=FreshnessState.CURRENT,
                        evidence_references=tuple(item.reference for item in evidence),
                    )
                )
                if error_present:
                    findings.append(
                        HealthCheckFinding(
                            finding_id=f"finding.huawei-pacific.node.{identity}.error-code",
                            severity=error_state,
                            title="Huawei Pacific cluster node reports a non-zero error code",
                            summary=(
                                f"Node {node.node_id} ({node.name}) reports error code "
                                f"'{node.error_code}'; this connector does not have a confirmed "
                                "mapping from vendor error codes to specific causes."
                            ),
                            observation_ids=(error_observation_id,),
                            evidence_references=tuple(item.reference for item in evidence),
                        )
                    )

            if state is ObservationState.NORMAL:
                continue
            findings.append(
                HealthCheckFinding(
                    finding_id=f"finding.huawei-pacific.node.{identity}",
                    severity=state,
                    title="Huawei Pacific cluster node status requires attention",
                    summary=(
                        f"Node {node.node_id} ({node.name}) reports running status "
                        f"'{node.running_status.value}'."
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
            unknowns=(unknown or "Cluster node status remains unknown.",),
        )


class HuaweiPacificCapacityHealthExecutor:
    """Executes the bounded, read-only Huawei Pacific storage-pool capacity read."""

    def __init__(
        self,
        *,
        client: HuaweiPacificClient,
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
            raise ValueError("unsupported Huawei Pacific capacity-check definition")
        if definition.limits.max_steps < 1 or definition.limits.max_evidence_records < 1:
            return self._failed(started_at, 0, "The definition budget cannot contain a read.")

        try:
            pools = await self._client.read_pool_capacity()
        except HuaweiPacificConnectorError as exc:
            return self._failed(
                started_at,
                1,
                _connector_failure_reason(exc),
                "Pool capacity is unknown because the read failed.",
            )
        if not pools:
            return self._failed(
                started_at,
                1,
                "No storage pools were returned by the configured Huawei Pacific MCP.",
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
            identity = _identity(pool.pool_id)
            observation_id = f"observation.huawei-pacific.capacity.{identity}"
            observations.append(
                HealthObservation(
                    observation_id=observation_id,
                    target_id=f"{definition.target_id}/{pool.pool_id}",
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
                    finding_id=f"finding.huawei-pacific.capacity.{identity}",
                    severity=state,
                    title="Huawei Pacific pool capacity or status requires attention",
                    summary=(
                        f"Pool {pool.pool_name} reports status '{pool.status.value}' at "
                        f"{pool.used_capacity_percent} percent utilization; this connector's "
                        f"fixed warning and critical thresholds are {_CAPACITY_WARNING_PERCENT} "
                        f"and {_CAPACITY_CRITICAL_PERCENT} percent."
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
    def _pool_state(pool: HuaweiPacificPoolCapacity) -> ObservationState:
        status_state = _POOL_OBSERVATION_STATE.get(pool.status, ObservationState.UNKNOWN)
        if status_state is not ObservationState.NORMAL:
            return status_state
        if pool.used_capacity_percent >= _CAPACITY_CRITICAL_PERCENT:
            return ObservationState.CRITICAL
        if pool.used_capacity_percent >= _CAPACITY_WARNING_PERCENT:
            return ObservationState.WARNING
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
