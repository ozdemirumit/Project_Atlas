from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_package_supply_chain_inventory_create,
    authorize_connector_package_supply_chain_inventory_read,
    browser_session_subject,
)
from atlas.api.supply_chain_inventory_schemas import (
    ConnectorPackageSupplyChainInventoryData,
    ConnectorPackageSupplyChainInventoryInput,
    ConnectorPackageSupplyChainInventoryResponse,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.supply_chain_inventory import (
    PackageSupplyChainInventoryService,
)
from atlas.modules.connectors.application.supply_chain_inventory_ports import (
    PackageSupplyChainInventoryError,
)
from atlas.modules.connectors.domain.supply_chain_inventory import (
    ConnectorPackageSupplyChainInventory,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/package-supply-chain-inventories", tags=["connectors"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key",
    min_length=8,
    max_length=128,
    pattern=r"^[A-Za-z0-9._:-]+$",
)


def _raise(error: PackageSupplyChainInventoryError) -> NoReturn:
    if error.code == "package_inventory_human_required":
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
        title="Connector package inventory unavailable",
        detail="The package could not be inventoried within the governed supply-chain boundary.",
    ) from error


def _response(
    inventory: ConnectorPackageSupplyChainInventory, request: Request, response: Response
) -> ConnectorPackageSupplyChainInventoryResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorPackageSupplyChainInventoryResponse(
        data=ConnectorPackageSupplyChainInventoryData.from_domain(inventory),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=ConnectorPackageSupplyChainInventoryResponse, status_code=201)
async def create_package_supply_chain_inventory(
    payload: ConnectorPackageSupplyChainInventoryInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_connector_package_supply_chain_inventory_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorPackageSupplyChainInventoryResponse:
    service: PackageSupplyChainInventoryService = (
        request.app.state.package_supply_chain_inventory_service
    )
    try:
        inventory = await service.create(
            actor=subject,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except PackageSupplyChainInventoryError as error:
        _raise(error)
    return _response(inventory, request, response)


@router.get("/{inventory_id}", response_model=ConnectorPackageSupplyChainInventoryResponse)
async def get_package_supply_chain_inventory(
    inventory_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_connector_package_supply_chain_inventory_read),
    ],
) -> ConnectorPackageSupplyChainInventoryResponse:
    service: PackageSupplyChainInventoryService = (
        request.app.state.package_supply_chain_inventory_service
    )
    try:
        inventory = await service.get(
            actor=subject,
            inventory_id=inventory_id,
            correlation_id=str(request.state.correlation_id),
        )
    except PackageSupplyChainInventoryError as error:
        _raise(error)
    return _response(inventory, request, response)
