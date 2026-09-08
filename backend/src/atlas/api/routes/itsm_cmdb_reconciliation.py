from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Path, Request

from atlas.api.errors import AtlasError
from atlas.api.itsm_cmdb_reconciliation_schemas import (
    ItsmCiMappingRuleData,
    ItsmCiMappingRuleResponse,
    ItsmCiReconciliationConflictData,
    ItsmCiReconciliationConflictResponse,
    RecordItsmCiReconciliationConflictPayload,
    RegisterItsmCiMappingRulePayload,
    UpdateItsmCiReconciliationMatchStatePayload,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_itsm_cmdb_reconciliation_manage,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.itsm.application.cmdb_reconciliation import (
    ItsmCmdbReconciliationError,
    ItsmCmdbReconciliationService,
)
from atlas.modules.itsm.domain.cmdb_reconciliation import (
    ItsmCiConflictAuthority,
    ItsmCiConflictField,
    ItsmCiMappingRule,
    ItsmCiMatchState,
    ItsmCiReconciliationConflict,
)

router = APIRouter(prefix="/itsm/cmdb-reconciliation", tags=["itsm"])
RULE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")
CONFLICT_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: ItsmCmdbReconciliationError) -> NoReturn:
    if error.code.endswith("not_found"):
        status = 404
    elif error.code.endswith("invalid"):
        status = 422
    else:
        status = 409
    raise AtlasError(
        status=status,
        code=error.code,
        title="ITSM CMDB reconciliation operation unavailable",
        detail="The requested CI mapping rule or reconciliation conflict operation failed.",
    ) from error


def _rule_data(rule: ItsmCiMappingRule) -> ItsmCiMappingRuleData:
    return ItsmCiMappingRuleData(
        rule_id=rule.rule_id,
        version=rule.version,
        external_ci_class=rule.external_ci_class,
        atlas_entity_type=rule.atlas_entity_type,
        profile_id=rule.profile_id,
    )


def _conflict_data(conflict: ItsmCiReconciliationConflict) -> ItsmCiReconciliationConflictData:
    return ItsmCiReconciliationConflictData(
        conflict_id=conflict.conflict_id,
        external_ci_id=conflict.external_ci_id,
        mapped_atlas_entity_id=conflict.mapped_atlas_entity_id,
        field=conflict.field.value,
        cmdb_value=conflict.cmdb_value,
        cmdb_observed_at=conflict.cmdb_observed_at.isoformat(),
        live_value=conflict.live_value,
        live_observed_at=conflict.live_observed_at.isoformat(),
        proposed_authority=conflict.proposed_authority.value,
        confidence=conflict.confidence,
        match_state=conflict.match_state.value,
    )


@router.post("/mapping-rules/{rule_id}", response_model=ItsmCiMappingRuleResponse, status_code=201)
async def register_mapping_rule(
    rule_id: Annotated[str, RULE_ID],
    payload: RegisterItsmCiMappingRulePayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_itsm_cmdb_reconciliation_manage)],
) -> ItsmCiMappingRuleResponse:
    now = datetime.now(UTC)
    service: ItsmCmdbReconciliationService = request.app.state.itsm_cmdb_reconciliation_service
    try:
        rule = await service.register_mapping_rule(
            rule_id=rule_id,
            version=payload.version,
            external_ci_class=payload.external_ci_class,
            atlas_entity_type=payload.atlas_entity_type,
            profile_id=payload.profile_id,
            actor=subject,
            correlation_id=str(request.state.correlation_id),
        )
    except ItsmCmdbReconciliationError as error:
        _raise(error)
    return ItsmCiMappingRuleResponse(
        data=_rule_data(rule),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post(
    "/conflicts/{conflict_id}",
    response_model=ItsmCiReconciliationConflictResponse,
    status_code=201,
)
async def record_conflict(
    conflict_id: Annotated[str, CONFLICT_ID],
    payload: RecordItsmCiReconciliationConflictPayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_itsm_cmdb_reconciliation_manage)],
) -> ItsmCiReconciliationConflictResponse:
    now = datetime.now(UTC)
    try:
        field = ItsmCiConflictField(payload.field)
        proposed_authority = ItsmCiConflictAuthority(payload.proposed_authority)
    except ValueError as error:
        raise AtlasError(
            status=422,
            code="itsm_ci_reconciliation_conflict_field_or_authority_unrecognized",
            title="ITSM CMDB reconciliation operation unavailable",
            detail="The conflict field or proposed authority is not recognized.",
        ) from error
    service: ItsmCmdbReconciliationService = request.app.state.itsm_cmdb_reconciliation_service
    try:
        conflict = await service.record_conflict(
            conflict_id=conflict_id,
            external_ci_id=payload.external_ci_id,
            mapped_atlas_entity_id=payload.mapped_atlas_entity_id,
            field=field,
            cmdb_value=payload.cmdb_value,
            cmdb_observed_at=payload.cmdb_observed_at,
            live_value=payload.live_value,
            live_observed_at=payload.live_observed_at,
            proposed_authority=proposed_authority,
            confidence=payload.confidence,
            actor=subject,
            correlation_id=str(request.state.correlation_id),
        )
    except ItsmCmdbReconciliationError as error:
        _raise(error)
    return ItsmCiReconciliationConflictResponse(
        data=_conflict_data(conflict),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.post(
    "/conflicts/{conflict_id}/match-state",
    response_model=ItsmCiReconciliationConflictResponse,
)
async def update_match_state(
    conflict_id: Annotated[str, CONFLICT_ID],
    payload: UpdateItsmCiReconciliationMatchStatePayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_itsm_cmdb_reconciliation_manage)],
) -> ItsmCiReconciliationConflictResponse:
    now = datetime.now(UTC)
    try:
        match_state = ItsmCiMatchState(payload.match_state)
    except ValueError as error:
        raise AtlasError(
            status=422,
            code="itsm_ci_match_state_unrecognized",
            title="ITSM CMDB reconciliation operation unavailable",
            detail="The match state is not recognized.",
        ) from error
    service: ItsmCmdbReconciliationService = request.app.state.itsm_cmdb_reconciliation_service
    try:
        conflict = await service.update_match_state(
            conflict_id=conflict_id,
            match_state=match_state,
            actor=subject,
            correlation_id=str(request.state.correlation_id),
        )
    except ItsmCmdbReconciliationError as error:
        _raise(error)
    return ItsmCiReconciliationConflictResponse(
        data=_conflict_data(conflict),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )
