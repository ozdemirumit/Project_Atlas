from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response

from atlas.api.release_preflight_schemas import (
    ReleasePreflightData,
    ReleasePreflightResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import authenticated_subject, authorize_release_preflight_read
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.platform.application.release_preflight import ReleasePreflightService
from atlas.modules.platform.domain.release_preflight import AcquisitionMode, DeploymentProfile

router = APIRouter(prefix="/platform/release-preflight", tags=["release-preflight"])


@router.get("", response_model=ReleasePreflightResponse)
async def get_release_preflight(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_release_preflight_read)],
    mode: Annotated[AcquisitionMode, Query()] = AcquisitionMode.OFFLINE,
    profile: Annotated[DeploymentProfile, Query()] = DeploymentProfile.LINUX_LAB,
) -> ReleasePreflightResponse:
    service: ReleasePreflightService = request.app.state.release_preflight_service
    report = await service.run(
        actor=subject,
        mode=mode,
        profile=profile,
        correlation_id=str(request.state.correlation_id),
    )
    response.headers["Cache-Control"] = "no-store"
    return ReleasePreflightResponse(
        data=ReleasePreflightData.from_domain(report),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )
