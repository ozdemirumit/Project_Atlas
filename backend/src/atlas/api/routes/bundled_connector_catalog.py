from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.bundled_connector_catalog_schemas import (
    BundledConnectorCatalogResponse,
    BundledConnectorDescriptorData,
    BundledConnectorInstanceData,
    BundledConnectorInstanceInput,
    BundledConnectorInstanceResponse,
)
from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_instance_create,
    authorize_connector_instance_read,
    browser_session_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.bundled_catalog import (
    BundledConnectorCatalogError,
    BundledConnectorCatalogService,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/catalog", tags=["connectors"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)
CATALOG_ITEM_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: BundledConnectorCatalogError) -> NoReturn:
    code = str(error)
    if code.endswith("human_required"):
        status = 403
    elif code.endswith("not_found"):
        status = 404
    elif code.endswith(("invalid", "required")):
        status = 422
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=code,
        title="Bundled connector catalog operation unavailable",
        detail="The bounded bundled connector catalog operation could not be completed.",
    ) from error


@router.get("", response_model=BundledConnectorCatalogResponse)
async def list_bundled_connector_catalog(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_instance_read)],
) -> BundledConnectorCatalogResponse:
    service: BundledConnectorCatalogService = request.app.state.bundled_connector_catalog_service
    try:
        descriptors = await service.list(
            actor=subject, correlation_id=str(request.state.correlation_id)
        )
    except BundledConnectorCatalogError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return BundledConnectorCatalogResponse(
        data=tuple(BundledConnectorDescriptorData.from_domain(item) for item in descriptors),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{catalog_item_id}/instances",
    response_model=BundledConnectorInstanceResponse,
    status_code=201,
)
async def create_bundled_connector_instance(
    payload: BundledConnectorInstanceInput,
    request: Request,
    response: Response,
    catalog_item_id: Annotated[str, CATALOG_ITEM_ID],
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_instance_create)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> BundledConnectorInstanceResponse:
    service: BundledConnectorCatalogService = request.app.state.bundled_connector_catalog_service
    try:
        record = await service.create_instance(
            actor=subject,
            catalog_item_id=catalog_item_id,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except BundledConnectorCatalogError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return BundledConnectorInstanceResponse(
        data=BundledConnectorInstanceData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )
