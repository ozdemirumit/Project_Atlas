from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.license_analysis_schemas import (
    ConnectorPackageLicenseAnalysisData,
    ConnectorPackageLicenseAnalysisInput,
    ConnectorPackageLicenseAnalysisResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_package_license_analysis_create,
    authorize_connector_package_license_analysis_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.license_analysis import (
    PackageLicenseAnalysisService,
)
from atlas.modules.connectors.application.license_analysis_ports import (
    PackageLicenseAnalysisError,
)
from atlas.modules.connectors.domain.license_analysis import (
    ConnectorPackageLicenseAnalysis,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/package-license-analyses", tags=["connectors"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: PackageLicenseAnalysisError) -> NoReturn:
    if error.code == "package_license_human_required":
        status = 403
    elif error.code.endswith("not_found"):
        status = 404
    elif error.code.endswith(("invalid", "unsupported", "required")):
        status = 422
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=error.code,
        title="Connector package license analysis unavailable",
        detail="The package could not be analyzed within the governed license policy boundary.",
    ) from error


def _response(
    analysis: ConnectorPackageLicenseAnalysis,
    request: Request,
    response: Response,
) -> ConnectorPackageLicenseAnalysisResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorPackageLicenseAnalysisResponse(
        data=ConnectorPackageLicenseAnalysisData.from_domain(analysis),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=ConnectorPackageLicenseAnalysisResponse, status_code=201)
async def create_package_license_analysis(
    payload: ConnectorPackageLicenseAnalysisInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_connector_package_license_analysis_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorPackageLicenseAnalysisResponse:
    service: PackageLicenseAnalysisService = request.app.state.package_license_analysis_service
    try:
        analysis = await service.create(
            actor=subject,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except PackageLicenseAnalysisError as error:
        _raise(error)
    return _response(analysis, request, response)


@router.get("/{analysis_id}", response_model=ConnectorPackageLicenseAnalysisResponse)
async def get_package_license_analysis(
    analysis_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_connector_package_license_analysis_read),
    ],
) -> ConnectorPackageLicenseAnalysisResponse:
    service: PackageLicenseAnalysisService = request.app.state.package_license_analysis_service
    try:
        analysis = await service.get(
            actor=subject,
            analysis_id=analysis_id,
            correlation_id=str(request.state.correlation_id),
        )
    except PackageLicenseAnalysisError as error:
        _raise(error)
    return _response(analysis, request, response)
