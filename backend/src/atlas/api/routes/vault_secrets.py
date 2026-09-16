from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_vault_secret_create,
    authorize_connector_vault_secret_read,
    browser_session_subject,
)
from atlas.api.vault_secret_schemas import (
    ConnectorVaultSecretInput,
    ConnectorVaultSecretListResponse,
    ConnectorVaultSecretReferenceData,
    ConnectorVaultSecretWriteResponse,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.vault_secret import (
    ConnectorVaultError,
    ConnectorVaultService,
)
from atlas.modules.connectors.domain.vault_secret import SECRET_REFERENCE_ID_PATTERN
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/vault-secrets", tags=["connectors"])


def _raise(error: ConnectorVaultError) -> NoReturn:
    code = error.code
    status = 403 if code.endswith("required") else 422
    raise AtlasError(
        status=status,
        code=code,
        title="Connector vault secret operation unavailable",
        detail="The connector-credential vault operation could not be completed.",
    ) from error


def _meta(request: Request) -> ResponseMeta:
    return ResponseMeta(
        correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
    )


@router.put(
    "/{secret_reference_id}",
    response_model=ConnectorVaultSecretWriteResponse,
)
async def set_connector_vault_secret(
    secret_reference_id: Annotated[str, Path(pattern=SECRET_REFERENCE_ID_PATTERN.pattern)],
    payload: ConnectorVaultSecretInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_vault_secret_create)],
) -> ConnectorVaultSecretWriteResponse:
    service: ConnectorVaultService = request.app.state.connector_vault_service
    try:
        reference = await service.set_secret(
            actor=subject,
            secret_reference_id=secret_reference_id,
            value=payload.value.get_secret_value(),
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorVaultError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorVaultSecretWriteResponse(
        data=ConnectorVaultSecretReferenceData.from_domain(reference), meta=_meta(request)
    )


@router.get("", response_model=ConnectorVaultSecretListResponse)
async def list_connector_vault_secrets(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_vault_secret_read)],
) -> ConnectorVaultSecretListResponse:
    service: ConnectorVaultService = request.app.state.connector_vault_service
    references = await service.list_references(
        actor=subject, correlation_id=str(request.state.correlation_id)
    )
    response.headers["Cache-Control"] = "no-store"
    return ConnectorVaultSecretListResponse(
        data=tuple(ConnectorVaultSecretReferenceData.from_domain(item) for item in references),
        meta=_meta(request),
    )
