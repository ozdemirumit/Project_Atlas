from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import Annotated, NoReturn

from fastapi import APIRouter, Depends, Path, Request, Response

from atlas.api.errors import AtlasError
from atlas.api.itsm_attachment_schemas import (
    ItsmAttachmentData,
    ItsmAttachmentDownloadData,
    ItsmAttachmentDownloadLinkCreatePayload,
    ItsmAttachmentDownloadLinkData,
    ItsmAttachmentDownloadLinkResponse,
    ItsmAttachmentDownloadResponse,
    ItsmAttachmentReplacePayload,
    ItsmAttachmentResponse,
    ItsmAttachmentUploadPayload,
    ItsmEvidencePackageCreatePayload,
    ItsmEvidencePackageData,
    ItsmEvidencePackageResponse,
)
from atlas.api.schemas import ResponseMeta
from atlas.api.security import (
    authenticated_subject,
    authorize_itsm_attachment_create,
    authorize_itsm_attachment_delete,
    authorize_itsm_attachment_download,
    authorize_itsm_attachment_read,
)
from atlas.modules.authorization.domain.models import AuthorizationDecision
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.itsm.application.attachments import ItsmAttachmentError, ItsmAttachmentService
from atlas.modules.itsm.domain.attachments import ItsmAttachment, ItsmEvidencePackage

router = APIRouter(prefix="/itsm", tags=["itsm"])
SAFE_ID = Path(pattern=r"^[a-z][a-z0-9_.:-]{2,127}$")


def _raise(error: ItsmAttachmentError) -> NoReturn:
    code = str(error)
    if code.endswith("not_found"):
        status = 404
    elif code.endswith(
        (
            "human_required",
            "permission_denied",
            "scope_mismatch",
            "subject_mismatch",
            "ceiling_exceeded",
            "expired_or_consumed",
        )
    ):
        status = 403
    elif code.endswith(("conflict", "integrity_failed")):
        status = 409
    else:
        status = 422
    raise AtlasError(
        status=status,
        code=code,
        title="ITSM attachment operation unavailable",
        detail=(
            "Attachment upload, evidence packaging, and download grant no infrastructure or "
            "execution authority; every download re-authorizes access at the moment it happens."
        ),
    ) from error


def _meta(request: Request) -> ResponseMeta:
    return ResponseMeta(
        correlation_id=str(request.state.correlation_id), generated_at=datetime.now(UTC)
    )


def _attachment_data(attachment: ItsmAttachment) -> ItsmAttachmentData:
    return ItsmAttachmentData(
        attachment_id=attachment.attachment_id,
        external_ticket_id=attachment.external_ticket_id,
        filename=attachment.filename,
        media_type=attachment.media_type,
        size_bytes=attachment.size_bytes,
        content_digest=attachment.content_digest,
        classification=attachment.classification,
        uploaded_by=attachment.uploaded_by,
        uploaded_at=attachment.uploaded_at.isoformat(),
        scan_state=attachment.scan_state.value,
        transferable=attachment.transferable,
        allowlist_check_completed=attachment.allowlist_check_completed,
        size_check_completed=attachment.size_check_completed,
        active_content_policy_scan_completed=attachment.active_content_policy_scan_completed,
        secret_pattern_scan_completed=attachment.secret_pattern_scan_completed,
        malware_signature_scan_completed=attachment.malware_signature_scan_completed,
    )


def _evidence_package_data(package: ItsmEvidencePackage) -> ItsmEvidencePackageData:
    return ItsmEvidencePackageData(
        package_id=package.package_id,
        external_ticket_id=package.external_ticket_id,
        attachment_ids=list(package.attachment_ids),
        manifest_digest=package.manifest_digest,
        artifact_versions=list(package.artifact_versions),
        classification=package.classification,
        custodied_by=package.custodied_by,
        created_by=package.created_by,
        created_at=package.created_at.isoformat(),
        expires_at=package.expires_at.isoformat() if package.expires_at is not None else None,
    )


@router.post("/attachments", response_model=ItsmAttachmentResponse, status_code=201)
async def upload_attachment(
    payload: ItsmAttachmentUploadPayload,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_itsm_attachment_create)],
) -> ItsmAttachmentResponse:
    service: ItsmAttachmentService = request.app.state.itsm_attachment_service
    try:
        attachment = await service.upload(
            actor=subject,
            organization_id=subject.organization_id,
            environment_id=f"environment.{request.app.state.settings.environment}",
            external_ticket_id=payload.external_ticket_id,
            filename=payload.filename,
            media_type=payload.media_type,
            content=payload.content_bytes(),
            classification=payload.classification,
            correlation_id=str(request.state.correlation_id),
        )
    except ItsmAttachmentError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ItsmAttachmentResponse(data=_attachment_data(attachment), meta=_meta(request))


@router.get("/attachments/{attachment_id}", response_model=ItsmAttachmentResponse)
async def get_attachment(
    attachment_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_itsm_attachment_read)],
) -> ItsmAttachmentResponse:
    service: ItsmAttachmentService = request.app.state.itsm_attachment_service
    try:
        attachment = await service.get(
            actor=subject,
            organization_id=subject.organization_id,
            environment_id=f"environment.{request.app.state.settings.environment}",
            attachment_id=attachment_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ItsmAttachmentError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ItsmAttachmentResponse(data=_attachment_data(attachment), meta=_meta(request))


@router.delete("/attachments/{attachment_id}", status_code=204)
async def delete_attachment(
    attachment_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_itsm_attachment_delete)],
) -> None:
    service: ItsmAttachmentService = request.app.state.itsm_attachment_service
    try:
        await service.delete(
            actor=subject,
            organization_id=subject.organization_id,
            environment_id=f"environment.{request.app.state.settings.environment}",
            attachment_id=attachment_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ItsmAttachmentError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"


@router.post(
    "/attachments/{attachment_id}/replace", response_model=ItsmAttachmentResponse, status_code=200
)
async def replace_attachment(
    attachment_id: Annotated[str, SAFE_ID],
    payload: ItsmAttachmentReplacePayload,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_itsm_attachment_create)],
) -> ItsmAttachmentResponse:
    service: ItsmAttachmentService = request.app.state.itsm_attachment_service
    try:
        attachment = await service.replace(
            actor=subject,
            organization_id=subject.organization_id,
            environment_id=f"environment.{request.app.state.settings.environment}",
            attachment_id=attachment_id,
            filename=payload.filename,
            media_type=payload.media_type,
            content=payload.content_bytes(),
            classification=payload.classification,
            correlation_id=str(request.state.correlation_id),
        )
    except ItsmAttachmentError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ItsmAttachmentResponse(data=_attachment_data(attachment), meta=_meta(request))


@router.post("/evidence-packages", response_model=ItsmEvidencePackageResponse, status_code=201)
async def create_evidence_package(
    payload: ItsmEvidencePackageCreatePayload,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_itsm_attachment_create)],
) -> ItsmEvidencePackageResponse:
    service: ItsmAttachmentService = request.app.state.itsm_attachment_service
    try:
        package = await service.create_evidence_package(
            actor=subject,
            organization_id=subject.organization_id,
            environment_id=f"environment.{request.app.state.settings.environment}",
            external_ticket_id=payload.external_ticket_id,
            attachment_ids=tuple(payload.attachment_ids),
            artifact_versions=tuple(payload.artifact_versions),
            classification=payload.classification,
            expires_at=payload.expires_at,
            correlation_id=str(request.state.correlation_id),
        )
    except ItsmAttachmentError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ItsmEvidencePackageResponse(data=_evidence_package_data(package), meta=_meta(request))


@router.get("/evidence-packages/{package_id}", response_model=ItsmEvidencePackageResponse)
async def get_evidence_package(
    package_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_itsm_attachment_read)],
) -> ItsmEvidencePackageResponse:
    service: ItsmAttachmentService = request.app.state.itsm_attachment_service
    try:
        package = await service.get_evidence_package(
            actor=subject,
            organization_id=subject.organization_id,
            environment_id=f"environment.{request.app.state.settings.environment}",
            package_id=package_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ItsmAttachmentError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ItsmEvidencePackageResponse(data=_evidence_package_data(package), meta=_meta(request))


@router.post(
    "/evidence-packages/{package_id}/download-links",
    response_model=ItsmAttachmentDownloadLinkResponse,
    status_code=201,
)
async def issue_download_link(
    package_id: Annotated[str, SAFE_ID],
    payload: ItsmAttachmentDownloadLinkCreatePayload,
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_itsm_attachment_download)],
) -> ItsmAttachmentDownloadLinkResponse:
    service: ItsmAttachmentService = request.app.state.itsm_attachment_service
    try:
        link = await service.issue_download_link(
            actor=subject,
            organization_id=subject.organization_id,
            environment_id=f"environment.{request.app.state.settings.environment}",
            package_id=package_id,
            attachment_id=payload.attachment_id,
            ttl_seconds=payload.ttl_seconds,
            correlation_id=str(request.state.correlation_id),
        )
    except ItsmAttachmentError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ItsmAttachmentDownloadLinkResponse(
        data=ItsmAttachmentDownloadLinkData(
            link_id=link.link_id,
            attachment_id=link.attachment_id,
            issued_to_subject_id=link.issued_to_subject_id,
            issued_at=link.issued_at.isoformat(),
            expires_at=link.expires_at.isoformat(),
            consumed_at=link.consumed_at.isoformat() if link.consumed_at is not None else None,
        ),
        meta=_meta(request),
    )


@router.get(
    "/evidence-packages/{package_id}/download-links/{link_id}",
    response_model=ItsmAttachmentDownloadResponse,
)
async def download_attachment(
    package_id: Annotated[str, SAFE_ID],
    link_id: Annotated[str, SAFE_ID],
    request: Request,
    response: Response,
    subject: Annotated[AuthenticatedSubject, Depends(authenticated_subject)],
    _decision: Annotated[AuthorizationDecision, Depends(authorize_itsm_attachment_download)],
) -> ItsmAttachmentDownloadResponse:
    service: ItsmAttachmentService = request.app.state.itsm_attachment_service
    try:
        attachment, content = await service.consume_download_link(
            actor=subject,
            organization_id=subject.organization_id,
            environment_id=f"environment.{request.app.state.settings.environment}",
            package_id=package_id,
            link_id=link_id,
            correlation_id=str(request.state.correlation_id),
        )
    except ItsmAttachmentError as error:
        _raise(error)
    response.headers["Cache-Control"] = "no-store"
    return ItsmAttachmentDownloadResponse(
        data=ItsmAttachmentDownloadData(
            attachment=_attachment_data(attachment),
            content_base64=base64.b64encode(content).decode("ascii"),
        ),
        meta=_meta(request),
    )
