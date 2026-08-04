from __future__ import annotations

from datetime import datetime
from typing import Protocol

from atlas.modules.rca.domain.models import RcaCase
from atlas.modules.recommendations.domain.models import (
    RecommendationArtifact,
    RecommendationRequest,
)


class RcaCaseProvider(Protocol):
    async def get_case(self, case_id: str, version: int, target_id: str) -> RcaCase: ...


class RecommendationAssembler(Protocol):
    def build(
        self,
        request: RecommendationRequest,
        source_case: RcaCase,
        *,
        requested_by: str,
        organization_id: str,
        environment_id: str,
        site_id: str,
        created_at: datetime,
        version: int,
        prior_version_id: str | None,
    ) -> RecommendationArtifact: ...
