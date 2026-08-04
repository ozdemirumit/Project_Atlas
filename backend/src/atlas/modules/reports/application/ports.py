from __future__ import annotations

from datetime import datetime
from typing import Protocol

from atlas.modules.recommendations.domain.models import RecommendationArtifact
from atlas.modules.reports.domain.models import ReportRequest, TechnicalReport


class RecommendationProvider(Protocol):
    async def get_recommendation(
        self,
        recommendation_id: str,
        version: int,
        target_id: str,
    ) -> RecommendationArtifact: ...


class ReportAssembler(Protocol):
    def build(
        self,
        request: ReportRequest,
        source: RecommendationArtifact,
        *,
        requested_by: str,
        organization_id: str,
        environment_id: str,
        site_id: str,
        created_at: datetime,
        version: int,
        prior_version_id: str | None,
    ) -> TechnicalReport: ...
