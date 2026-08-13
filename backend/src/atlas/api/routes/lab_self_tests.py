from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.lab_self_test_schemas import (
    ConnectorPackageLabSelfTestData,
    ConnectorPackageLabSelfTestInput,
    ConnectorPackageLabSelfTestResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_package_lab_self_test_create,
    authorize_connector_package_lab_self_test_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.lab_self_test import PackageLabSelfTestService
from atlas.modules.connectors.application.lab_self_test_ports import PackageLabSelfTestError
from atlas.modules.connectors.domain.lab_self_test import ConnectorPackageLabSelfTest
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/package-lab-self-tests", tags=["connectors"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: PackageLabSelfTestError) -> NoReturn:
    if error.code == "package_lab_human_required":
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
        title="Connector package lab self-test unavailable",
        detail="The package could not be tested within the governed read-only lab boundary.",
    ) from error


def _response(
    self_test: ConnectorPackageLabSelfTest, request: Request, response: Response
) -> ConnectorPackageLabSelfTestResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorPackageLabSelfTestResponse(
        data=ConnectorPackageLabSelfTestData.from_domain(self_test),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=ConnectorPackageLabSelfTestResponse, status_code=201)
async def create_package_lab_self_test(
    payload: ConnectorPackageLabSelfTestInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_package_lab_self_test_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorPackageLabSelfTestResponse:
    service: PackageLabSelfTestService = request.app.state.package_lab_self_test_service
    try:
        self_test = await service.create(
            actor=subject,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except PackageLabSelfTestError as error:
        _raise(error)
    return _response(self_test, request, response)


@router.get("/{self_test_id}", response_model=ConnectorPackageLabSelfTestResponse)
async def get_package_lab_self_test(
    self_test_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_package_lab_self_test_read)
    ],
) -> ConnectorPackageLabSelfTestResponse:
    service: PackageLabSelfTestService = request.app.state.package_lab_self_test_service
    try:
        self_test = await service.get(
            actor=subject,
            self_test_id=self_test_id,
            correlation_id=str(request.state.correlation_id),
        )
    except PackageLabSelfTestError as error:
        _raise(error)
    return _response(self_test, request, response)
