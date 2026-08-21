from __future__ import annotations

import asyncio
from collections.abc import Sequence

from atlas.modules.platform.domain.advisory_posture import (
    AdvisoryOnlyPosture,
    build_advisory_only_posture,
)
from atlas.modules.platform.domain.status import (
    ComponentHealth,
    ComponentState,
    HealthProbe,
    PlatformHealth,
)


class PlatformStatusService:
    def __init__(
        self,
        *,
        service_name: str,
        service_version: str,
        environment: str,
        probes: Sequence[HealthProbe],
        operational_posture: AdvisoryOnlyPosture | None = None,
    ) -> None:
        self.service_name = service_name
        self.service_version = service_version
        self.environment = environment
        self._probes = tuple(probes)
        self._operational_posture = operational_posture or build_advisory_only_posture()

    async def get_status(self) -> PlatformHealth:
        components: tuple[ComponentHealth, ...] = tuple(
            await asyncio.gather(*(probe.check() for probe in self._probes))
        )
        required_failure = any(
            component.required and component.status is not ComponentState.HEALTHY
            for component in components
        )
        optional_failure = any(
            not component.required and component.status is ComponentState.UNAVAILABLE
            for component in components
        )
        warnings = tuple(
            component.code
            for component in components
            if component.status in {ComponentState.UNAVAILABLE, ComponentState.DEGRADED}
        )

        if required_failure:
            overall = ComponentState.UNAVAILABLE
        elif optional_failure:
            overall = ComponentState.DEGRADED
        else:
            overall = ComponentState.HEALTHY

        return PlatformHealth(
            service_name=self.service_name,
            service_version=self.service_version,
            environment=self.environment,
            status=overall,
            ready=not required_failure,
            components=components,
            warnings=warnings,
            operational_posture=self._operational_posture,
        )
