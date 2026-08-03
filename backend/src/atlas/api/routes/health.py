from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from atlas.api.schemas import ComponentStatusSchema, HealthResponse
from atlas.modules.platform.application.service import PlatformStatusService

router = APIRouter(tags=["platform-health"])


def _status_service(request: Request) -> PlatformStatusService:
    service: PlatformStatusService = request.app.state.platform_status_service
    return service


@router.get("/health/live", response_model=HealthResponse)
async def liveness(request: Request) -> HealthResponse:
    service = _status_service(request)
    return HealthResponse(
        status="alive", service=service.service_name, version=service.service_version
    )


@router.get("/health/ready", response_model=HealthResponse)
async def readiness(request: Request) -> HealthResponse | JSONResponse:
    status = await _status_service(request).get_status()
    response = HealthResponse(
        status="ready" if status.ready else "not_ready",
        service=status.service_name,
        version=status.service_version,
        components=[ComponentStatusSchema.from_domain(item) for item in status.components],
    )
    if status.ready:
        return response
    return JSONResponse(status_code=503, content=response.model_dump(mode="json"))
