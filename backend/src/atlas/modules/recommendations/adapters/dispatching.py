from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from atlas.modules.rca.domain.models import RcaCase
from atlas.modules.recommendations.application.ports import RecommendationAssembler
from atlas.modules.recommendations.domain.models import (
    RecommendationArtifact,
    RecommendationRequest,
)


class DispatchingRecommendationAssembler:
    """Selects the vendor-specific assembler that matches the source RCA case's own
    `data_profile` (e.g. "configured_hitachi_read_only", "configured_huawei_dorado_read_only") --
    unlike RCA target resolution, a recommendation assembler cannot simply be tried in order and
    fall through on failure: every real assembler successfully builds from any real RcaCase's
    generic evidence (source_type tags like "storage_hardware_health" carry no vendor identity),
    so picking the wrong one would silently attach the wrong vendor's capability ids to the plan
    steps instead of failing loudly. `data_profile` is the one field every Configured<Vendor>*
    assembler already stamps with its own real identity, so it is the correct dispatch key.
    """

    def __init__(
        self,
        *,
        assemblers_by_data_profile: Mapping[str, RecommendationAssembler],
        default: RecommendationAssembler,
    ) -> None:
        self._assemblers_by_data_profile = assemblers_by_data_profile
        self._default = default

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
    ) -> RecommendationArtifact:
        assembler = self._assemblers_by_data_profile.get(source_case.data_profile, self._default)
        return assembler.build(
            request,
            source_case,
            requested_by=requested_by,
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
            created_at=created_at,
            version=version,
            prior_version_id=prior_version_id,
        )
