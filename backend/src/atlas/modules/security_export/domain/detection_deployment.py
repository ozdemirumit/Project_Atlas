"""ATLAS-035 SS19: the deployment record that makes the detection content contract and lifecycle
stage machinery (`detection_content.py`, `detection_lifecycle.py`) into something with real,
per-destination state -- which specific baseline detection is at which of the nine lifecycle
stages, against which SIEM destination, and who owns it."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.security_export.domain.detection_content import DetectionUseCaseId
from atlas.modules.security_export.domain.detection_lifecycle import DetectionLifecycleStage


@dataclass(frozen=True, slots=True)
class SiemDetectionDeployment:
    deployment_id: str
    detection_id: DetectionUseCaseId
    detection_version: str
    destination_id: str
    stage: DetectionLifecycleStage
    owner: str
    registered_by: str
    registered_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        validate_stable_identifier(self.deployment_id, "deployment_id")
        validate_stable_identifier(self.destination_id, "destination_id")
        validate_stable_identifier(self.registered_by, "registered_by")
        if not self.detection_version.strip() or not self.owner.strip():
            raise ValueError("a SIEM detection deployment requires a version and an owner")
        if self.registered_at.tzinfo is None or self.updated_at.tzinfo is None:
            raise ValueError("SIEM detection deployment timestamps must be timezone-aware")
        if self.updated_at < self.registered_at:
            raise ValueError("a SIEM detection deployment cannot be updated before registration")
