from __future__ import annotations

from typing import Protocol

from atlas.modules.security_export.domain.detection_deployment import SiemDetectionDeployment
from atlas.modules.security_export.domain.handoff_metrics import SiemIncidentHandoffSummary


class SiemDetectionDeploymentRepository(Protocol):
    async def get(self, deployment_id: str) -> SiemDetectionDeployment | None: ...

    async def save(self, deployment: SiemDetectionDeployment) -> None: ...

    async def add_handoff(
        self, deployment_id: str, handoff: SiemIncidentHandoffSummary
    ) -> None: ...

    async def list_handoffs(self, deployment_id: str) -> tuple[SiemIncidentHandoffSummary, ...]: ...

    async def close(self) -> None: ...
