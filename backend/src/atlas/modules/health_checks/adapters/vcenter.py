from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime

from atlas.modules.connectors.vendors.vcenter.client import VCenterClient, VCenterConnectorError
from atlas.modules.connectors.vendors.vcenter.domain import (
    VCenterHost,
    VCenterHostConnectionState,
    VCenterHostPowerState,
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

HOST_HEALTH_DEFINITION_ID = "health-check.hypervisor.vcenter-host-status"

_SAFE_CONNECTOR_ERROR_CODES = frozenset(
    {
        "malformed_vendor_response",
        "target_timeout",
        "target_unavailable",
        "vendor_permission_denied",
        "vendor_rate_limited",
        "vendor_response_limit_exceeded",
    }
)


def _observation_state(host: VCenterHost) -> ObservationState:
    # connection_state is the primary availability signal; power_state only refines it once a
    # host is confirmed reachable. A host vCenter cannot reach is always CRITICAL regardless of
    # its last-known power state.
    if host.connection_state in (
        VCenterHostConnectionState.DISCONNECTED,
        VCenterHostConnectionState.NOT_RESPONDING,
    ):
        return ObservationState.CRITICAL
    if host.connection_state is VCenterHostConnectionState.UNKNOWN:
        return ObservationState.WARNING
    if host.power_state is VCenterHostPowerState.POWERED_ON:
        return ObservationState.NORMAL
    if host.power_state is VCenterHostPowerState.STANDBY:
        return ObservationState.WARNING
    return ObservationState.CRITICAL


class VCenterHostHealthExecutor:
    """Executes the bounded, read-only vCenter host connection/power status check."""

    def __init__(
        self,
        *,
        client: VCenterClient,
        capability_id: str,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._client = client
        self._capability_id = capability_id
        self._clock = clock or (lambda: datetime.now(UTC))

    async def execute(
        self, definition: HealthCheckDefinition, *, started_at: datetime
    ) -> HealthCheckExecutionResult:
        self._validate_definition(definition)
        if definition.limits.max_steps < 1 or definition.limits.max_evidence_records < 1:
            return self._failed_result(
                started_at=started_at,
                step_count=0,
                partial_reason="The definition budget cannot contain a host-inventory read.",
                unknown="Host health is unknown because the definition budget is insufficient.",
            )

        try:
            inventory = await self._client.read_host_inventory()
        except VCenterConnectorError as exc:
            return self._failed_result(
                started_at=started_at,
                step_count=1,
                partial_reason=self._connector_failure_reason(exc),
                unknown="Host health is unknown because host inventory could not be read.",
            )

        if len(inventory.evidence_references) > definition.limits.max_evidence_records:
            return self._failed_result(
                started_at=started_at,
                step_count=1,
                partial_reason="The inventory evidence exceeded the definition budget.",
                unknown="Host health is unknown because the bounded result was rejected.",
            )

        evidence = [
            HealthCheckEvidence(
                reference=reference,
                source="vCenter host-inventory read",
                source_version=definition.connector_version,
                observed_at=inventory.observed_at,
                freshness=FreshnessState.CURRENT,
                trust_basis="Digest-only evidence from an allowlisted C1 vSphere Automation API "
                "response",
            )
            for reference in inventory.evidence_references
        ]
        evidence_refs = tuple(item.reference for item in evidence)
        partial_reasons: list[str] = []
        unknowns: list[str] = []

        host_budget = min(definition.limits.max_targets, len(inventory.hosts))
        selected_hosts = inventory.hosts[:host_budget]
        if len(inventory.hosts) > host_budget:
            partial_reasons.append("Additional hosts were omitted by the definition target budget.")
            unknowns.append("Health is unknown for hosts outside the bounded execution set.")
        if not inventory.hosts:
            partial_reasons.append("No hosts were returned by inventory.")
            unknowns.append("No host status could be evaluated.")

        observations: list[HealthObservation] = []
        findings: list[HealthCheckFinding] = []
        for host in selected_hosts:
            state = _observation_state(host)
            identity = self._identity(host.host_id)
            observation_id = f"observation.vcenter.host.{identity}"
            observation = HealthObservation(
                observation_id=observation_id,
                target_id=f"{definition.target_id}/{host.host_id}",
                component=f"host:{host.host_id}",
                metric="host.connection_and_power_state",
                value=f"{host.connection_state.value}/{host.power_state.value}",
                unit="state",
                state=state,
                observed_at=inventory.observed_at,
                freshness=FreshnessState.CURRENT,
                evidence_references=evidence_refs,
            )
            observations.append(observation)
            if state is ObservationState.NORMAL:
                continue
            findings.append(
                HealthCheckFinding(
                    finding_id=f"finding.vcenter.host.{identity}",
                    severity=state,
                    title=f"vCenter host {host.name} reported a non-normal state",
                    summary=(
                        f"Host {host.name} reports connection state "
                        f"'{host.connection_state.value}' and power state "
                        f"'{host.power_state.value}'."
                    ),
                    observation_ids=(observation_id,),
                    evidence_references=evidence_refs,
                )
            )

        run_state = (
            HealthCheckRunState.FAILED
            if not inventory.hosts
            else HealthCheckRunState.PARTIAL
            if partial_reasons
            else HealthCheckRunState.COMPLETED
        )

        return HealthCheckExecutionResult(
            state=run_state,
            completed_at=self._completed_at(started_at),
            step_count=1,
            observations=tuple(observations),
            findings=tuple(findings),
            evidence=tuple(evidence),
            partial_reasons=tuple(dict.fromkeys(partial_reasons)),
            unknowns=tuple(dict.fromkeys(unknowns)),
        )

    def _validate_definition(self, definition: HealthCheckDefinition) -> None:
        if (
            definition.definition_id != HOST_HEALTH_DEFINITION_ID
            or definition.capability_id != self._capability_id
        ):
            raise ValueError("unsupported vCenter health-check definition")

    @staticmethod
    def _identity(*parts: str) -> str:
        normalized = "\x1f".join(parts).encode("utf-8")
        return hashlib.sha256(normalized).hexdigest()[:20]

    @staticmethod
    def _connector_failure_reason(exc: VCenterConnectorError) -> str:
        code = exc.code if exc.code in _SAFE_CONNECTOR_ERROR_CODES else "connector_error"
        return f"The vCenter read failed safely ({code})."

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
