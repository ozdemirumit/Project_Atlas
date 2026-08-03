from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from atlas.modules.health_checks.domain.models import (
    HealthCheckDefinition,
    HealthCheckEvidence,
    HealthCheckFinding,
    HealthCheckRunState,
    HealthObservation,
)


@dataclass(frozen=True, slots=True)
class HealthCheckExecutionResult:
    state: HealthCheckRunState
    completed_at: datetime
    step_count: int
    observations: tuple[HealthObservation, ...]
    findings: tuple[HealthCheckFinding, ...]
    evidence: tuple[HealthCheckEvidence, ...]
    partial_reasons: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()


class HealthCheckExecutor(Protocol):
    async def execute(
        self, definition: HealthCheckDefinition, *, started_at: datetime
    ) -> HealthCheckExecutionResult: ...
