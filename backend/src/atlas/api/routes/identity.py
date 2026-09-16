from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Request

from atlas.api.errors import AtlasError
from atlas.api.schemas import (
    CurrentIdentityData,
    CurrentIdentityResponse,
    LocalCredentialReplaceData,
    LocalCredentialReplaceInput,
    LocalCredentialReplaceResponse,
    ResponseMeta,
)
from atlas.api.security import (
    authenticated_subject,
    authorize_identity_self_read,
    authorize_local_credential_self_replace,
)
from atlas.modules.authorization.application.bootstrap import current_identity_scope
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.application.local_credentials import (
    LocalCredentialError,
    LocalCredentialService,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/identity", tags=["identity"])


def _raise_local_credential_error(error: LocalCredentialError) -> NoReturn:
    code = error.code
    status = 403 if code.endswith(("invalid", "locked", "unavailable")) else 422
    raise AtlasError(
        status=status,
        code=code,
        title="Local credential replacement unavailable",
        detail="The local credential could not be replaced.",
    ) from error


@router.get("/me", response_model=CurrentIdentityResponse)
async def current_identity(
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    decision: Annotated[AuthorizationDecision, Depends(authorize_identity_self_read)],
) -> CurrentIdentityResponse:
    scope = current_identity_scope(subject.organization_id, request.app.state.settings.environment)
    return CurrentIdentityResponse(
        data=CurrentIdentityData.from_domain(
            subject,
            scope,
            decision,
            credential_kind=getattr(
                request.state,
                "authenticated_credential_kind",
                "identity_provider",
            ),
        ),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id),
            generated_at=datetime.now(UTC),
        ),
    )


@router.post("/local-credential/replace", response_model=LocalCredentialReplaceResponse)
async def replace_local_credential(
    payload: LocalCredentialReplaceInput,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_local_credential_self_replace)],
) -> LocalCredentialReplaceResponse:
    """ATLAS-030 SS11: the escape hatch from `MUST_REPLACE` -- the only two permissions
    `BOOTSTRAP_SETUP_ROLE_ID` carries are this and reading one's own identity, so a freshly
    bootstrapped administrator can always reach this route regardless of which real tier they
    were also granted for after replacing the temporary password."""
    service: LocalCredentialService = request.app.state.local_credential_service
    try:
        updated = await service.replace_credential(
            subject_id=subject.subject_id,
            current_password=payload.current_password,
            new_password=payload.new_password,
            correlation_id=str(request.state.correlation_id),
        )
    except LocalCredentialError as error:
        _raise_local_credential_error(error)
    return LocalCredentialReplaceResponse(
        data=LocalCredentialReplaceData(subject_id=updated.subject_id, state=updated.state.value),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id),
            generated_at=datetime.now(UTC),
        ),
    )
