from __future__ import annotations

from datetime import datetime
from typing import Protocol

from atlas.modules.rca.domain.models import RcaCase, RcaCreateRequest


class RcaAssembler(Protocol):
    async def build(
        self,
        request: RcaCreateRequest,
        *,
        requested_by: str,
        organization_id: str,
        environment_id: str,
        site_id: str,
        created_at: datetime,
        version: int,
        prior_version_id: str | None,
    ) -> RcaCase: ...
