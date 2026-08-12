from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.instance_creation_schemas import (
    ConnectorInstanceCreationInput,
    ConnectorInstanceCreationPolicyData,
    ConnectorInstanceCreationPolicyListResponse,
    ConnectorInstanceCreationResponse,
    ConnectorInstanceListResponse,
    ConnectorInstanceRecordData,
    ConnectorInstanceRetirementInput,
    ConnectorUpgradeApprovalCreateInput,
    ConnectorUpgradeApprovalDecisionInput,
    ConnectorUpgradeApprovalRecordData,
    ConnectorUpgradeApprovalRecordResponse,
    ConnectorUpgradeApprovalRequestData,
    ConnectorUpgradeApprovalResponse,
    ConnectorUpgradeApprovalRevalidationData,
    ConnectorUpgradeApprovalRevalidationInput,
    ConnectorUpgradeApprovalRevalidationResponse,
    ConnectorUpgradeChangeContextDraftData,
    ConnectorUpgradeChangeContextDraftInput,
    ConnectorUpgradeChangeContextDraftResponse,
    ConnectorUpgradeEvidenceReceiptData,
    ConnectorUpgradeEvidenceReceiptInput,
    ConnectorUpgradeEvidenceReceiptResponse,
    ConnectorUpgradeEvidenceReceiptVerificationData,
    ConnectorUpgradeEvidenceReceiptVerificationInput,
    ConnectorUpgradeEvidenceReceiptVerificationResponse,
    ConnectorUpgradeEvidenceSigningKeyTrustInventoryData,
    ConnectorUpgradeEvidenceSigningKeyTrustInventoryResponse,
    ConnectorUpgradeHandoffReadinessData,
    ConnectorUpgradeHandoffReadinessResponse,
    ConnectorUpgradePlanData,
    ConnectorUpgradePlanResponse,
    ConnectorUpgradeReadinessData,
    ConnectorUpgradeReadinessResponse,
    ConnectorUpgradeSignedEvidenceReceiptData,
    ConnectorUpgradeSignedEvidenceReceiptInput,
    ConnectorUpgradeSignedEvidenceReceiptResponse,
    ConnectorUpgradeSignedEvidenceReceiptVerificationData,
    ConnectorUpgradeSignedEvidenceReceiptVerificationInput,
    ConnectorUpgradeSignedEvidenceReceiptVerificationResponse,
    ConnectorUpgradeSigningProviderConformanceData,
    ConnectorUpgradeSigningProviderConformanceInput,
    ConnectorUpgradeSigningProviderConformanceResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authorize_connector_instance_create,
    authorize_connector_instance_read,
    authorize_connector_instance_retire,
    authorize_connector_upgrade_approval_create,
    authorize_connector_upgrade_approval_decide,
    authorize_connector_upgrade_approval_read,
    authorize_connector_upgrade_approval_revalidation_create,
    authorize_connector_upgrade_approval_revalidation_read,
    authorize_connector_upgrade_change_context_create,
    authorize_connector_upgrade_change_context_read,
    authorize_connector_upgrade_evidence_receipt_create,
    authorize_connector_upgrade_evidence_receipt_verify,
    authorize_connector_upgrade_handoff_readiness_read,
    authorize_connector_upgrade_signed_evidence_receipt_create,
    authorize_connector_upgrade_signed_evidence_receipt_verify,
    authorize_connector_upgrade_signing_key_trust_inventory_read,
    authorize_connector_upgrade_signing_provider_conformance_create,
    authorize_connector_upgrade_signing_provider_conformance_read,
    browser_session_subject,
    connector_signing_conformance_subject,
    connector_signing_trust_read_subject,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.connectors.application.instance_creation import (
    ConnectorInstanceCreationService,
)
from atlas.modules.connectors.application.instance_creation_ports import (
    ConnectorInstanceCreationError,
)
from atlas.modules.connectors.application.instance_lifecycle import (
    ConnectorInstanceLifecycleService,
)
from atlas.modules.connectors.application.upgrade_approval import (
    ConnectorUpgradeApprovalService,
)
from atlas.modules.connectors.application.upgrade_approval_ports import (
    ConnectorUpgradeApprovalError,
)
from atlas.modules.connectors.application.upgrade_readiness import (
    ConnectorUpgradeReadinessService,
)
from atlas.modules.connectors.domain.instance_creation import ConnectorInstanceRecord
from atlas.modules.connectors.domain.upgrade_approval import ConnectorUpgradeApprovalOutcome
from atlas.modules.identity.domain.models import AuthenticatedSubject

router = APIRouter(prefix="/connectors/instances", tags=["connectors"])
IDEMPOTENCY = Header(
    alias="Idempotency-Key", min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"
)


def _raise(error: ConnectorInstanceCreationError) -> NoReturn:
    code = str(error)
    if code.endswith(("mfa_required", "separation_required")):
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
        title="Connector instance creation unavailable",
        detail="The governed connector instance operation could not be completed.",
    ) from error


def _response(
    record: ConnectorInstanceRecord, request: Request, response: Response
) -> ConnectorInstanceCreationResponse:
    response.headers["Cache-Control"] = "no-store"
    return ConnectorInstanceCreationResponse(
        data=ConnectorInstanceRecordData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


def _raise_upgrade_approval(error: ConnectorUpgradeApprovalError) -> NoReturn:
    code = error.code
    if code.endswith(
        ("mfa_required", "assurance_insufficient", "separation_required", "verifier_required")
    ):
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
        title="Connector upgrade approval unavailable",
        detail="The governed connector upgrade approval request could not be completed.",
    ) from error


@router.get("", response_model=ConnectorInstanceListResponse)
async def list_connector_instances(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_instance_read)],
    lifecycle: Annotated[str, Query(pattern=r"^(active|retired|all)$")] = "active",
    query: Annotated[str, Query(max_length=200)] = "",
) -> ConnectorInstanceListResponse:
    service: ConnectorInstanceLifecycleService = (
        request.app.state.connector_instance_lifecycle_service
    )
    try:
        records = await service.list(
            actor=subject,
            lifecycle=lifecycle,
            query=query,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorInstanceCreationError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorInstanceListResponse(
        data=tuple(ConnectorInstanceRecordData.from_domain(item) for item in records),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post("", response_model=ConnectorInstanceCreationResponse, status_code=201)
async def create_connector_instance(
    payload: ConnectorInstanceCreationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_instance_create)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorInstanceCreationResponse:
    service: ConnectorInstanceCreationService = (
        request.app.state.connector_instance_creation_service
    )
    try:
        record = await service.create(
            actor=subject,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except ConnectorInstanceCreationError as error:
        _raise(error)
    return _response(record, request, response)


@router.get("/creation-policies", response_model=ConnectorInstanceCreationPolicyListResponse)
async def list_connector_instance_creation_policies(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_instance_read)],
) -> ConnectorInstanceCreationPolicyListResponse:
    service: ConnectorInstanceCreationService = (
        request.app.state.connector_instance_creation_service
    )
    try:
        policies = await service.list_policies(
            actor=subject,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorInstanceCreationError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorInstanceCreationPolicyListResponse(
        data=tuple(ConnectorInstanceCreationPolicyData.from_domain(item) for item in policies),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get(
    "/upgrade-evidence-signing-key-trust",
    response_model=ConnectorUpgradeEvidenceSigningKeyTrustInventoryResponse,
)
async def get_connector_upgrade_signing_key_trust_inventory(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(connector_signing_trust_read_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_connector_upgrade_signing_key_trust_inventory_read),
    ],
) -> ConnectorUpgradeEvidenceSigningKeyTrustInventoryResponse:
    service: ConnectorUpgradeApprovalService = request.app.state.connector_upgrade_approval_service
    try:
        inventory = await service.signing_key_trust_inventory(
            actor=subject,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorUpgradeApprovalError as error:
        _raise_upgrade_approval(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorUpgradeEvidenceSigningKeyTrustInventoryResponse(
        data=ConnectorUpgradeEvidenceSigningKeyTrustInventoryData.from_domain(inventory),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/upgrade-evidence-signing-provider-conformance-assessments",
    response_model=ConnectorUpgradeSigningProviderConformanceResponse,
    status_code=201,
)
async def assess_connector_upgrade_signing_provider_conformance(
    payload: ConnectorUpgradeSigningProviderConformanceInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(connector_signing_conformance_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_connector_upgrade_signing_provider_conformance_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorUpgradeSigningProviderConformanceResponse:
    service: ConnectorUpgradeApprovalService = request.app.state.connector_upgrade_approval_service
    try:
        assessment = await service.assess_signing_provider_conformance(
            actor=subject,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except ConnectorUpgradeApprovalError as error:
        _raise_upgrade_approval(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorUpgradeSigningProviderConformanceResponse(
        data=ConnectorUpgradeSigningProviderConformanceData.from_domain(assessment),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get(
    "/upgrade-evidence-signing-provider-conformance-assessments/latest",
    response_model=ConnectorUpgradeSigningProviderConformanceResponse,
)
async def get_latest_connector_upgrade_signing_provider_conformance(
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(connector_signing_conformance_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_connector_upgrade_signing_provider_conformance_read),
    ],
) -> ConnectorUpgradeSigningProviderConformanceResponse:
    service: ConnectorUpgradeApprovalService = request.app.state.connector_upgrade_approval_service
    try:
        assessment = await service.latest_signing_provider_conformance(
            actor=subject,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorUpgradeApprovalError as error:
        _raise_upgrade_approval(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorUpgradeSigningProviderConformanceResponse(
        data=ConnectorUpgradeSigningProviderConformanceData.from_domain(assessment),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get("/{record_id}", response_model=ConnectorInstanceCreationResponse)
async def get_connector_instance(
    record_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_instance_read)],
) -> ConnectorInstanceCreationResponse:
    service: ConnectorInstanceCreationService = (
        request.app.state.connector_instance_creation_service
    )
    try:
        record = await service.get(
            actor=subject,
            record_id=record_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorInstanceCreationError as error:
        _raise(error)
    return _response(record, request, response)


@router.post(
    "/{record_id}/retirements",
    response_model=ConnectorInstanceCreationResponse,
)
async def retire_connector_instance(
    record_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: ConnectorInstanceRetirementInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_instance_retire)],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorInstanceCreationResponse:
    service: ConnectorInstanceLifecycleService = (
        request.app.state.connector_instance_lifecycle_service
    )
    try:
        record = await service.retire(
            actor=subject,
            record_id=record_id,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except ConnectorInstanceCreationError as error:
        _raise(error)
    return _response(record, request, response)


@router.get(
    "/{record_id}/upgrade-readiness",
    response_model=ConnectorUpgradeReadinessResponse,
)
async def get_connector_upgrade_readiness(
    record_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_instance_read)],
) -> ConnectorUpgradeReadinessResponse:
    service: ConnectorUpgradeReadinessService = (
        request.app.state.connector_upgrade_readiness_service
    )
    try:
        readiness = await service.evaluate(
            actor=subject,
            record_id=record_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorInstanceCreationError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorUpgradeReadinessResponse(
        data=ConnectorUpgradeReadinessData.from_domain(readiness),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get(
    "/{record_id}/upgrade-plans/{candidate_receipt_id}",
    response_model=ConnectorUpgradePlanResponse,
)
async def get_connector_upgrade_plan(
    record_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    candidate_receipt_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_instance_read)],
) -> ConnectorUpgradePlanResponse:
    service: ConnectorUpgradeReadinessService = (
        request.app.state.connector_upgrade_readiness_service
    )
    try:
        plan = await service.plan(
            actor=subject,
            record_id=record_id,
            candidate_receipt_id=candidate_receipt_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorInstanceCreationError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorUpgradePlanResponse(
        data=ConnectorUpgradePlanData.from_domain(plan),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{record_id}/upgrade-plans/{candidate_receipt_id}/approval-requests",
    response_model=ConnectorUpgradeApprovalResponse,
    status_code=201,
)
async def create_connector_upgrade_approval_request(
    record_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    candidate_receipt_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: ConnectorUpgradeApprovalCreateInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_upgrade_approval_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorUpgradeApprovalResponse:
    service: ConnectorUpgradeApprovalService = request.app.state.connector_upgrade_approval_service
    try:
        approval_request = await service.create(
            actor=subject,
            record_id=record_id,
            candidate_receipt_id=candidate_receipt_id,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except ConnectorUpgradeApprovalError as error:
        _raise_upgrade_approval(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorUpgradeApprovalResponse(
        data=ConnectorUpgradeApprovalRequestData.from_domain(approval_request),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get(
    "/{record_id}/upgrade-plans/{candidate_receipt_id}/approval-record",
    response_model=ConnectorUpgradeApprovalRecordResponse,
)
async def get_connector_upgrade_approval_record_for_plan(
    record_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    candidate_receipt_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_upgrade_approval_read)],
) -> ConnectorUpgradeApprovalRecordResponse:
    service: ConnectorUpgradeApprovalService = request.app.state.connector_upgrade_approval_service
    try:
        record = await service.get_record_for_plan(
            actor=subject,
            record_id=record_id,
            candidate_receipt_id=candidate_receipt_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorUpgradeApprovalError as error:
        _raise_upgrade_approval(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorUpgradeApprovalRecordResponse(
        data=ConnectorUpgradeApprovalRecordData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{record_id}/upgrade-approval-requests/{request_id}/decisions",
    response_model=ConnectorUpgradeApprovalRecordResponse,
)
async def decide_connector_upgrade_approval_request(
    record_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: ConnectorUpgradeApprovalDecisionInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_upgrade_approval_decide)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorUpgradeApprovalRecordResponse:
    service: ConnectorUpgradeApprovalService = request.app.state.connector_upgrade_approval_service
    try:
        data = payload.model_dump(exclude={"schema_version"})
        data["outcome"] = ConnectorUpgradeApprovalOutcome(str(data["outcome"]))
        record = await service.decide(
            actor=subject,
            record_id=record_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **data,
        )
    except ConnectorUpgradeApprovalError as error:
        _raise_upgrade_approval(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorUpgradeApprovalRecordResponse(
        data=ConnectorUpgradeApprovalRecordData.from_domain(record),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{record_id}/upgrade-approval-requests/{request_id}/revalidations",
    response_model=ConnectorUpgradeApprovalRevalidationResponse,
    status_code=201,
)
async def revalidate_connector_upgrade_approval(
    record_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: ConnectorUpgradeApprovalRevalidationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_connector_upgrade_approval_revalidation_create),
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorUpgradeApprovalRevalidationResponse:
    service: ConnectorUpgradeApprovalService = request.app.state.connector_upgrade_approval_service
    try:
        revalidation = await service.revalidate(
            actor=subject,
            record_id=record_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except ConnectorUpgradeApprovalError as error:
        _raise_upgrade_approval(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorUpgradeApprovalRevalidationResponse(
        data=ConnectorUpgradeApprovalRevalidationData.from_domain(revalidation),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get(
    "/{record_id}/upgrade-approval-requests/{request_id}/revalidations/latest",
    response_model=ConnectorUpgradeApprovalRevalidationResponse,
)
async def get_latest_connector_upgrade_approval_revalidation(
    record_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_connector_upgrade_approval_revalidation_read),
    ],
) -> ConnectorUpgradeApprovalRevalidationResponse:
    service: ConnectorUpgradeApprovalService = request.app.state.connector_upgrade_approval_service
    try:
        revalidation = await service.get_latest_revalidation(
            actor=subject,
            record_id=record_id,
            request_id=request_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorUpgradeApprovalError as error:
        _raise_upgrade_approval(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorUpgradeApprovalRevalidationResponse(
        data=ConnectorUpgradeApprovalRevalidationData.from_domain(revalidation),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get(
    "/{record_id}/upgrade-approval-requests/{request_id}/handoff-readiness",
    response_model=ConnectorUpgradeHandoffReadinessResponse,
)
async def assess_connector_upgrade_handoff_readiness(
    record_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_connector_upgrade_handoff_readiness_read),
    ],
) -> ConnectorUpgradeHandoffReadinessResponse:
    service: ConnectorUpgradeApprovalService = request.app.state.connector_upgrade_approval_service
    try:
        assessment = await service.assess_handoff_readiness(
            actor=subject,
            record_id=record_id,
            request_id=request_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorUpgradeApprovalError as error:
        _raise_upgrade_approval(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorUpgradeHandoffReadinessResponse(
        data=ConnectorUpgradeHandoffReadinessData.from_domain(assessment),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{record_id}/upgrade-approval-requests/{request_id}/evidence-receipts",
    response_model=ConnectorUpgradeEvidenceReceiptResponse,
    status_code=201,
)
async def create_connector_upgrade_evidence_receipt(
    record_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: ConnectorUpgradeEvidenceReceiptInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_connector_upgrade_evidence_receipt_create),
    ],
) -> ConnectorUpgradeEvidenceReceiptResponse:
    service: ConnectorUpgradeApprovalService = request.app.state.connector_upgrade_approval_service
    try:
        receipt = await service.create_evidence_receipt(
            actor=subject,
            record_id=record_id,
            request_id=request_id,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except ConnectorUpgradeApprovalError as error:
        _raise_upgrade_approval(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorUpgradeEvidenceReceiptResponse(
        data=ConnectorUpgradeEvidenceReceiptData.from_domain(receipt),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{record_id}/upgrade-approval-requests/{request_id}/evidence-receipts/verify",
    response_model=ConnectorUpgradeEvidenceReceiptVerificationResponse,
)
async def verify_connector_upgrade_evidence_receipt(
    record_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: ConnectorUpgradeEvidenceReceiptVerificationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_connector_upgrade_evidence_receipt_verify),
    ],
) -> ConnectorUpgradeEvidenceReceiptVerificationResponse:
    service: ConnectorUpgradeApprovalService = request.app.state.connector_upgrade_approval_service
    try:
        verification = await service.verify_evidence_receipt(
            actor=subject,
            record_id=record_id,
            request_id=request_id,
            receipt=payload.receipt.to_domain(),
            correlation_id=str(request.state.correlation_id),
            acknowledged_digest_integrity_is_not_authenticity_or_execution_authority=(
                payload.acknowledged_digest_integrity_is_not_authenticity_or_execution_authority
            ),
        )
    except (ConnectorUpgradeApprovalError, ValueError) as error:
        approval_error = (
            error
            if isinstance(error, ConnectorUpgradeApprovalError)
            else ConnectorUpgradeApprovalError(
                "connector_upgrade_evidence_receipt_verification_invalid"
            )
        )
        _raise_upgrade_approval(approval_error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorUpgradeEvidenceReceiptVerificationResponse(
        data=ConnectorUpgradeEvidenceReceiptVerificationData.from_domain(verification),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{record_id}/upgrade-approval-requests/{request_id}/signed-evidence-receipts",
    response_model=ConnectorUpgradeSignedEvidenceReceiptResponse,
    status_code=201,
)
async def create_connector_upgrade_signed_evidence_receipt(
    record_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: ConnectorUpgradeSignedEvidenceReceiptInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_connector_upgrade_signed_evidence_receipt_create),
    ],
) -> ConnectorUpgradeSignedEvidenceReceiptResponse:
    service: ConnectorUpgradeApprovalService = request.app.state.connector_upgrade_approval_service
    try:
        signed = await service.sign_evidence_receipt(
            actor=subject,
            record_id=record_id,
            request_id=request_id,
            receipt=payload.receipt.to_domain(),
            correlation_id=str(request.state.correlation_id),
            acknowledged_signature_authenticates_origin_but_grants_no_authority=(
                payload.acknowledged_signature_authenticates_origin_but_grants_no_authority
            ),
        )
    except (ConnectorUpgradeApprovalError, ValueError) as error:
        approval_error = (
            error
            if isinstance(error, ConnectorUpgradeApprovalError)
            else ConnectorUpgradeApprovalError("connector_upgrade_signed_evidence_receipt_invalid")
        )
        _raise_upgrade_approval(approval_error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorUpgradeSignedEvidenceReceiptResponse(
        data=ConnectorUpgradeSignedEvidenceReceiptData.from_domain(signed),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{record_id}/upgrade-approval-requests/{request_id}/signed-evidence-receipts/verify",
    response_model=ConnectorUpgradeSignedEvidenceReceiptVerificationResponse,
)
async def verify_connector_upgrade_signed_evidence_receipt(
    record_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: ConnectorUpgradeSignedEvidenceReceiptVerificationInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision,
        Depends(authorize_connector_upgrade_signed_evidence_receipt_verify),
    ],
) -> ConnectorUpgradeSignedEvidenceReceiptVerificationResponse:
    service: ConnectorUpgradeApprovalService = request.app.state.connector_upgrade_approval_service
    try:
        verification = await service.verify_signed_evidence_receipt(
            actor=subject,
            record_id=record_id,
            request_id=request_id,
            signed_receipt=payload.signed_receipt.to_domain(),
            correlation_id=str(request.state.correlation_id),
            acknowledged_signature_is_not_approval_or_execution_authority=(
                payload.acknowledged_signature_is_not_approval_or_execution_authority
            ),
        )
    except (ConnectorUpgradeApprovalError, ValueError) as error:
        approval_error = (
            error
            if isinstance(error, ConnectorUpgradeApprovalError)
            else ConnectorUpgradeApprovalError(
                "connector_upgrade_signed_evidence_receipt_verification_invalid"
            )
        )
        _raise_upgrade_approval(approval_error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorUpgradeSignedEvidenceReceiptVerificationResponse(
        data=ConnectorUpgradeSignedEvidenceReceiptVerificationData.from_domain(verification),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.post(
    "/{record_id}/upgrade-approval-requests/{request_id}/change-context-drafts",
    response_model=ConnectorUpgradeChangeContextDraftResponse,
    status_code=201,
)
async def create_connector_upgrade_change_context_draft(
    record_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    payload: ConnectorUpgradeChangeContextDraftInput,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_upgrade_change_context_create)
    ],
    idempotency_key: Annotated[str, IDEMPOTENCY],
) -> ConnectorUpgradeChangeContextDraftResponse:
    service: ConnectorUpgradeApprovalService = request.app.state.connector_upgrade_approval_service
    try:
        draft = await service.create_change_context_draft(
            actor=subject,
            record_id=record_id,
            request_id=request_id,
            idempotency_key=idempotency_key,
            correlation_id=str(request.state.correlation_id),
            **payload.model_dump(exclude={"schema_version"}),
        )
    except ConnectorUpgradeApprovalError as error:
        _raise_upgrade_approval(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorUpgradeChangeContextDraftResponse(
        data=ConnectorUpgradeChangeContextDraftData.from_domain(draft),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get(
    "/{record_id}/upgrade-approval-requests/{request_id}/change-context-drafts/latest",
    response_model=ConnectorUpgradeChangeContextDraftResponse,
)
async def get_latest_connector_upgrade_change_context_draft(
    record_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[
        AuthorizationDecision, Depends(authorize_connector_upgrade_change_context_read)
    ],
) -> ConnectorUpgradeChangeContextDraftResponse:
    service: ConnectorUpgradeApprovalService = request.app.state.connector_upgrade_approval_service
    try:
        draft = await service.get_latest_change_context_draft(
            actor=subject,
            record_id=record_id,
            request_id=request_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorUpgradeApprovalError as error:
        _raise_upgrade_approval(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorUpgradeChangeContextDraftResponse(
        data=ConnectorUpgradeChangeContextDraftData.from_domain(draft),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )


@router.get(
    "/{record_id}/upgrade-approval-requests/{request_id}",
    response_model=ConnectorUpgradeApprovalResponse,
)
async def get_connector_upgrade_approval_request(
    record_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request_id: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(browser_session_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_connector_upgrade_approval_read)],
) -> ConnectorUpgradeApprovalResponse:
    service: ConnectorUpgradeApprovalService = request.app.state.connector_upgrade_approval_service
    try:
        approval_request = await service.get(
            actor=subject,
            record_id=record_id,
            request_id=request_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ConnectorUpgradeApprovalError as error:
        _raise_upgrade_approval(error)
    response.headers["Cache-Control"] = "no-store"
    return ConnectorUpgradeApprovalResponse(
        data=ConnectorUpgradeApprovalRequestData.from_domain(approval_request),
        meta=ResponseMeta(
            correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
        ),
    )
