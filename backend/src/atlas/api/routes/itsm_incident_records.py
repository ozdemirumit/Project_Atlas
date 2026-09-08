from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Path, Request

from atlas.api.errors import AtlasError
from atlas.api.itsm_incident_record_schemas import (
    ItsmIncidentRecordData,
    ItsmIncidentRecordResponse,
    UpsertItsmIncidentRecordPayload,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_itsm_incident_record_cache_manage,
)
from atlas.core.classification import DataClassification
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.itsm.application.record_cache import (
    ItsmIncidentRecordCacheService,
    ItsmRecordCacheError,
)
from atlas.modules.itsm.domain.records import (
    IncidentRecord,
    ItsmRecordCommonFields,
    ItsmRecordType,
)

router = APIRouter(prefix="/itsm/incident-records", tags=["itsm"])
INTEGRATION_REFERENCE = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: ItsmRecordCacheError) -> NoReturn:
    status = 404 if error.code.endswith("not_found") else 422
    raise AtlasError(
        status=status,
        code=error.code,
        title="ITSM incident record cache operation unavailable",
        detail="The requested incident record cache operation could not be completed.",
    ) from error


def _record_data(record: IncidentRecord) -> ItsmIncidentRecordData:
    common = record.common
    return ItsmIncidentRecordData(
        integration_reference=common.integration_reference,
        profile_id=common.profile_id,
        external_system=common.external_system,
        external_instance=common.external_instance,
        external_record_id=common.external_record_id,
        display_number=common.display_number,
        title=common.title,
        state=common.state,
        priority=common.priority,
        severity=common.severity,
        environment_id=common.environment_id,
        site_id=common.site_id,
        classification=common.classification.value,
        external_version=common.external_version,
        last_synchronized_at=common.last_synchronized_at.isoformat(),
        detection_source=record.detection_source,
        symptoms=record.symptoms,
        current_status_summary=record.current_status_summary,
        resolution_summary=record.resolution_summary,
    )


@router.post("/{integration_reference}", response_model=ItsmIncidentRecordResponse, status_code=201)
async def upsert_incident_record(
    integration_reference: Annotated[str, INTEGRATION_REFERENCE],
    payload: UpsertItsmIncidentRecordPayload,
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_itsm_incident_record_cache_manage)
    ],
) -> ItsmIncidentRecordResponse:
    now = datetime.now(UTC)
    try:
        classification = DataClassification(payload.classification)
    except ValueError as error:
        raise AtlasError(
            status=422,
            code="itsm_incident_record_classification_unrecognized",
            title="ITSM incident record cache operation unavailable",
            detail="The classification is not recognized.",
        ) from error
    try:
        common = ItsmRecordCommonFields(
            integration_reference=integration_reference,
            profile_id=payload.profile_id,
            external_system=payload.external_system,
            external_instance=payload.external_instance,
            record_type=ItsmRecordType.INCIDENT,
            external_record_id=payload.external_record_id,
            display_number=payload.display_number,
            title=payload.title,
            sanitized_summary=payload.sanitized_summary,
            state=payload.state,
            priority=payload.priority,
            impact=payload.impact,
            urgency=payload.urgency,
            severity=payload.severity,
            assignment_group=payload.assignment_group,
            owner_reference=payload.owner_reference,
            requester_reference=payload.requester_reference,
            approver_reference=payload.approver_reference,
            service_reference=payload.service_reference,
            configuration_item_reference=payload.configuration_item_reference,
            environment_id=payload.environment_id,
            site_id=payload.site_id,
            organizational_scope=payload.organizational_scope,
            created_at=payload.created_at,
            updated_at=payload.updated_at,
            resolved_at=payload.resolved_at,
            closed_at=payload.closed_at,
            planned_start_at=payload.planned_start_at,
            planned_end_at=payload.planned_end_at,
            classification=classification,
            access_policy_reference=payload.access_policy_reference,
            retention_reference=payload.retention_reference,
            external_version=payload.external_version,
            last_synchronized_at=payload.last_synchronized_at,
            last_synchronization_status=payload.last_synchronization_status,
        )
        record = IncidentRecord(
            common=common,
            detection_source=payload.detection_source,
            first_observed_at=payload.first_observed_at,
            symptoms=payload.symptoms,
            affected_services=tuple(payload.affected_services),
            current_impact_summary=payload.current_impact_summary,
            evidence_references=tuple(payload.evidence_references),
            investigation_references=tuple(payload.investigation_references),
            probable_causes=tuple(payload.probable_causes),
            probable_cause_confidence=payload.probable_cause_confidence,
            workaround_summary=payload.workaround_summary,
            remediation_recommendation_reference=payload.remediation_recommendation_reference,
            current_status_summary=payload.current_status_summary,
            resolution_summary=payload.resolution_summary,
            confirmed_cause=payload.confirmed_cause,
            validation_outcome=payload.validation_outcome,
        )
    except ValueError as error:
        raise AtlasError(
            status=422,
            code="itsm_incident_record_invalid",
            title="ITSM incident record cache operation unavailable",
            detail="The incident record does not satisfy the SS6 normalized record contract.",
        ) from error
    service: ItsmIncidentRecordCacheService = request.app.state.itsm_incident_record_cache_service
    try:
        upserted = await service.upsert(
            record, actor=subject, correlation_id=str(request.state.correlation_id)
        )
    except ItsmRecordCacheError as error:
        _raise(error)
    return ItsmIncidentRecordResponse(
        data=_record_data(upserted),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )


@router.get("/{integration_reference}", response_model=ItsmIncidentRecordResponse)
async def get_incident_record(
    integration_reference: Annotated[str, INTEGRATION_REFERENCE],
    request: Request,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_itsm_incident_record_cache_manage)
    ],
) -> ItsmIncidentRecordResponse:
    now = datetime.now(UTC)
    service: ItsmIncidentRecordCacheService = request.app.state.itsm_incident_record_cache_service
    try:
        record = await service.get(
            integration_reference, actor=subject, correlation_id=str(request.state.correlation_id)
        )
    except ItsmRecordCacheError as error:
        _raise(error)
    return ItsmIncidentRecordResponse(
        data=_record_data(record),
        meta=ResponseMeta(correlation_id=str(request.state.correlation_id), generated_at=now),
    )
