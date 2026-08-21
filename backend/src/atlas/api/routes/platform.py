from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response

from atlas.api.schemas import PlatformStatusData, PlatformStatusResponse, ResponseMeta
from atlas.modules.platform.application.service import PlatformStatusService

router = APIRouter(prefix="/platform", tags=["platform"])


@router.get("/status", response_model=PlatformStatusResponse)
async def platform_status(request: Request, response: Response) -> PlatformStatusResponse:
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "no-referrer"
    service: PlatformStatusService = request.app.state.platform_status_service
    status = await service.get_status()
    return PlatformStatusResponse(
        data=PlatformStatusData.from_domain(status),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id),
            generated_at=datetime.now(UTC),
        ),
    )
