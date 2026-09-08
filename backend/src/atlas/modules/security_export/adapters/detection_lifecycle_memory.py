from __future__ import annotations

from atlas.modules.security_export.domain.detection_deployment import SiemDetectionDeployment
from atlas.modules.security_export.domain.handoff_metrics import SiemIncidentHandoffSummary


class InMemorySiemDetectionDeploymentRepository:
    def __init__(self) -> None:
        self._deployments: dict[str, SiemDetectionDeployment] = {}
        self._handoffs: dict[str, list[SiemIncidentHandoffSummary]] = {}

    async def get(self, deployment_id: str) -> SiemDetectionDeployment | None:
        return self._deployments.get(deployment_id)

    async def save(self, deployment: SiemDetectionDeployment) -> None:
        self._deployments[deployment.deployment_id] = deployment

    async def add_handoff(self, deployment_id: str, handoff: SiemIncidentHandoffSummary) -> None:
        self._handoffs.setdefault(deployment_id, []).append(handoff)

    async def list_handoffs(self, deployment_id: str) -> tuple[SiemIncidentHandoffSummary, ...]:
        return tuple(self._handoffs.get(deployment_id, ()))

    async def close(self) -> None:
        return None
