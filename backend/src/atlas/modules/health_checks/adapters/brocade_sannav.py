from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime

from atlas.modules.connectors.vendors.brocade_sannav.client import (
    BrocadeConnectorError,
    BrocadeSanNavClient,
)
from atlas.modules.connectors.vendors.brocade_sannav.domain import BrocadeFaultSummary
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

FABRIC_HEALTH_DEFINITION_ID = "health-check.san.fabric-status"

_SAFE_CONNECTOR_ERROR_CODES = frozenset(
    {
        "invalid_fabric_identifier",
        "malformed_vendor_response",
        "target_not_bound",
        "target_timeout",
        "target_unavailable",
        "vendor_permission_denied",
        "vendor_rate_limited",
        "vendor_response_limit_exceeded",
    }
)


class BrocadeFabricHealthExecutor:
    """Executes the bounded, read-only Brocade SANnav fabric fault-count check.

    The fault/events response schema was not independently confirmed during connector
    construction (see brocade_sannav/domain.py and mcp/connectors/brocade_sannav/README.md), so
    this executor only ever reports NORMAL or WARNING, never CRITICAL -- a nonzero event count is
    a real, honest signal that something happened on the fabric, but claiming a specific severity
    tier from an unconfirmed per-event schema would not be.
    """

    def __init__(
        self,
        *,
        client: BrocadeSanNavClient,
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
        if definition.limits.max_steps < 2 or definition.limits.max_evidence_records < 2:
            return self._failed_result(
                started_at=started_at,
                step_count=0,
                partial_reason="The definition budget cannot contain inventory and fault reads.",
                unknown="Fabric health is unknown because the definition budget is insufficient.",
            )

        step_count = 1
        try:
            inventory = await self._client.read_inventory()
        except BrocadeConnectorError as exc:
            return self._failed_result(
                started_at=started_at,
                step_count=step_count,
                partial_reason=self._connector_failure_reason(exc),
                unknown="Fabric health is unknown because fabric inventory could not be read.",
            )

        if len(inventory.evidence_references) > definition.limits.max_evidence_records:
            return self._failed_result(
                started_at=started_at,
                step_count=step_count,
                partial_reason="The inventory evidence exceeded the definition budget.",
                unknown="Fabric health is unknown because the bounded result was rejected.",
            )

        evidence = [
            self._evidence(
                reference=reference,
                observed_at=inventory.observed_at,
                definition=definition,
                kind="fabric-inventory",
            )
            for reference in inventory.evidence_references
        ]
        observations: list[HealthObservation] = []
        findings: list[HealthCheckFinding] = []
        partial_reasons: list[str] = []
        unknowns: list[str] = []
        successful_fault_reads = 0

        remaining_step_budget = definition.limits.max_steps - step_count
        remaining_evidence_budget = definition.limits.max_evidence_records - len(evidence)
        target_budget = min(
            definition.limits.max_targets,
            remaining_step_budget,
            remaining_evidence_budget,
        )
        selected_fabrics = inventory.fabrics[:target_budget]
        if len(inventory.fabrics) > target_budget:
            partial_reasons.append(
                "Additional allowlisted fabrics were omitted by the definition target or read "
                "budget."
            )
            unknowns.append("Health is unknown for fabrics outside the bounded execution set.")
        if not inventory.fabrics:
            partial_reasons.append("No allowlisted SAN fabrics were returned by inventory.")
            unknowns.append("No fabric fault status could be evaluated.")

        for fabric in selected_fabrics:
            step_count += 1
            try:
                summary = await self._client.read_fabric_fault_summary(fabric.principal_switch_wwn)
            except BrocadeConnectorError as exc:
                partial_reasons.append(self._connector_failure_reason(exc))
                unknowns.append("Fault status is unknown for an allowlisted fabric.")
                continue

            if len(evidence) + len(summary.evidence_references) > (
                definition.limits.max_evidence_records
            ):
                partial_reasons.append(
                    "A fault-summary evidence set exceeded the remaining definition budget."
                )
                unknowns.append("Fault status was omitted because its evidence was incomplete.")
                continue

            fault_evidence = tuple(
                self._evidence(
                    reference=reference,
                    observed_at=summary.observed_at,
                    definition=definition,
                    kind="fault-events",
                )
                for reference in summary.evidence_references
            )
            evidence.extend(fault_evidence)
            successful_fault_reads += 1
            observation, finding = self._map_summary(
                definition=definition,
                summary=summary,
                evidence_references=tuple(item.reference for item in fault_evidence),
            )
            observations.append(observation)
            if finding is not None:
                findings.append(finding)
                partial_reasons.append(
                    "Per-event severity and affected-component detail are not available from "
                    "this bounded executor."
                )
                unknowns.append(
                    "No root cause or affected component is established by this read-only "
                    "fault-count check."
                )

        if successful_fault_reads == 0:
            state = HealthCheckRunState.FAILED if inventory.fabrics else HealthCheckRunState.PARTIAL
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

    def _validate_definition(self, definition: HealthCheckDefinition) -> None:
        if (
            definition.definition_id != FABRIC_HEALTH_DEFINITION_ID
            or definition.capability_id != self._capability_id
        ):
            raise ValueError("unsupported Brocade SANnav health-check definition")

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
            source=f"Brocade SANnav {kind} read",
            source_version=definition.connector_version,
            observed_at=observed_at,
            freshness=FreshnessState.CURRENT,
            trust_basis="Digest-only evidence from an allowlisted C1 HTTPS response",
        )

    @classmethod
    def _map_summary(
        cls,
        *,
        definition: HealthCheckDefinition,
        summary: BrocadeFaultSummary,
        evidence_references: tuple[str, ...],
    ) -> tuple[HealthObservation, HealthCheckFinding | None]:
        state = ObservationState.NORMAL if summary.event_count == 0 else ObservationState.WARNING
        identity = cls._identity(summary.fabric_principal_switch_wwn)
        observation_id = f"observation.brocade.fabric.{identity}"
        observation = HealthObservation(
            observation_id=observation_id,
            target_id=f"{definition.target_id}/{summary.fabric_principal_switch_wwn}",
            component=f"fabric:{summary.fabric_principal_switch_wwn}",
            metric="fabric.fault_event_count",
            value=str(summary.event_count),
            unit="events",
            state=state,
            observed_at=summary.observed_at,
            freshness=FreshnessState.CURRENT,
            evidence_references=evidence_references,
        )
        if state is ObservationState.NORMAL:
            return observation, None
        finding = HealthCheckFinding(
            finding_id=f"finding.brocade.fabric.{identity}",
            severity=state,
            title="Brocade fabric reported recent fault events",
            summary=(
                f"{summary.event_count} fault event(s) were reported for this fabric in the "
                "read window. Per-event severity is not available from this connector, so this "
                "is reported as a WARNING pending manual review."
            ),
            observation_ids=(observation_id,),
            evidence_references=evidence_references,
        )
        return observation, finding

    @staticmethod
    def _identity(*parts: str) -> str:
        normalized = "\x1f".join(parts).encode("utf-8")
        return hashlib.sha256(normalized).hexdigest()[:20]

    @staticmethod
    def _connector_failure_reason(exc: BrocadeConnectorError) -> str:
        code = exc.code if exc.code in _SAFE_CONNECTOR_ERROR_CODES else "connector_error"
        return f"The Brocade SANnav read failed safely ({code})."

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
