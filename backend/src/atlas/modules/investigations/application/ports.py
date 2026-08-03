from __future__ import annotations

from datetime import datetime
from typing import Protocol

from atlas.modules.investigations.domain.models import InvestigationRequest, ReasoningArtifact


class InvestigationAssembler(Protocol):
    def build(
        self,
        request: InvestigationRequest,
        *,
        requested_by: str,
        organization_id: str,
        environment_id: str,
        site_id: str,
        created_at: datetime,
        version: int,
        prior_version_id: str | None,
    ) -> ReasoningArtifact: ...
