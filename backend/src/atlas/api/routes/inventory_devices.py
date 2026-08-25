from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.inventory_schemas import (
    CreateInventoryDeviceInput,
    InventoryDeviceData,
    InventoryDeviceInventoryData,
    InventoryDeviceInventoryResponse,
    InventoryDeviceResponse,
    ReactivateInventoryDeviceInput,
    RetireInventoryDeviceInput,
    UpdateInventoryDeviceInput,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_inventory_device_create,
    authorize_inventory_device_read,
    authorize_inventory_device_retire,
    inventory_device_mutation_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.inventory.application.service import InventoryDeviceError, InventoryDeviceService
from atlas.modules.inventory.domain.devices import InventoryDeviceLifecycle, InventoryDeviceRecord

router = APIRouter(prefix="/inventory/devices", tags=["inventory"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _meta(request: Request) -> ResponseMeta:
    return ResponseMeta(
        correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
    )


def _raise(error: InventoryDeviceError) -> NoReturn:
    code = str(error)
    if code.endswith("not_found"):
        status = 404
    elif code.endswith(("required", "request_invalid")):
        status = 422
    elif code.endswith("human_required"):
        status = 403
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=code,
        title="Inventory device operation unavailable",
        detail="The governed inventory device operation could not be completed.",
    ) from error


def _response(
    record: InventoryDeviceRecord, request: Request, response: Response
) -> InventoryDeviceResponse:
    response.headers["Cache-Control"] = "no-store"
    return InventoryDeviceResponse(
        data=InventoryDeviceData.from_domain(record), meta=_meta(request)
    )


@router.get("", response_model=InventoryDeviceInventoryResponse)
async def list_inventory_devices(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_inventory_device_read)],
    lifecycle: Annotated[InventoryDeviceLifecycle | None, Query()] = None,
    query: Annotated[str | None, Query(max_length=160)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> InventoryDeviceInventoryResponse:
    service: InventoryDeviceService = request.app.state.inventory_device_service
    try:
        devices = await service.list_devices(
            actor=subject,
            lifecycle=lifecycle,
            query=query,
            limit=limit,
            correlation_id=str(request.state.correlation_id),
        )
    except InventoryDeviceError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return InventoryDeviceInventoryResponse(
        data=InventoryDeviceInventoryData(
            devices=[InventoryDeviceData.from_domain(item) for item in devices],
            durable=service.repository.durable,
            truncated=len(devices) == limit,
        ),
        meta=_meta(request),
    )


@router.post("", response_model=InventoryDeviceResponse, status_code=201)
async def create_inventory_device(
    payload: CreateInventoryDeviceInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(inventory_device_mutation_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_inventory_device_create)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> InventoryDeviceResponse:
    service: InventoryDeviceService = request.app.state.inventory_device_service
    try:
        record = await service.create(
            actor=subject,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except InventoryDeviceError as error:
        _raise(error)
    return _response(record, request, response)


@router.get("/{device_id}", response_model=InventoryDeviceResponse)
async def get_inventory_device(
    device_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_inventory_device_read)],
) -> InventoryDeviceResponse:
    service: InventoryDeviceService = request.app.state.inventory_device_service
    try:
        record = await service.get(
            actor=subject,
            device_id=device_id,
            correlation_id=str(request.state.correlation_id),
        )
    except InventoryDeviceError as error:
        _raise(error)
    return _response(record, request, response)


@router.patch("/{device_id}", response_model=InventoryDeviceResponse)
async def update_inventory_device(
    device_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: UpdateInventoryDeviceInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(inventory_device_mutation_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_inventory_device_create)],
) -> InventoryDeviceResponse:
    service: InventoryDeviceService = request.app.state.inventory_device_service
    changes = payload.model_dump(exclude={"schema_version", "expected_version"}, exclude_unset=True)
    try:
        record = await service.update_device(
            actor=subject,
            device_id=device_id,
            expected_version=payload.expected_version,
            changes=changes,
            correlation_id=str(request.state.correlation_id),
        )
    except InventoryDeviceError as error:
        _raise(error)
    return _response(record, request, response)


@router.post("/{device_id}/retirements", response_model=InventoryDeviceResponse)
async def retire_inventory_device(
    device_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: RetireInventoryDeviceInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(inventory_device_mutation_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_inventory_device_retire)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> InventoryDeviceResponse:
    service: InventoryDeviceService = request.app.state.inventory_device_service
    try:
        record = await service.retire(
            actor=subject,
            device_id=device_id,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except InventoryDeviceError as error:
        _raise(error)
    return _response(record, request, response)


@router.post("/{device_id}/reactivations", response_model=InventoryDeviceResponse)
async def reactivate_inventory_device(
    device_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: ReactivateInventoryDeviceInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(inventory_device_mutation_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_inventory_device_create)],
) -> InventoryDeviceResponse:
    service: InventoryDeviceService = request.app.state.inventory_device_service
    try:
        record = await service.reactivate(
            actor=subject,
            device_id=device_id,
            expected_version=payload.expected_version,
            correlation_id=str(request.state.correlation_id),
        )
    except InventoryDeviceError as error:
        _raise(error)
    return _response(record, request, response)
