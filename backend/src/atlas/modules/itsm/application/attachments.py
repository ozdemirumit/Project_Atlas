"""ATLAS-036 SS17: the application service that makes `itsm.domain.attachments` reachable.

Upload runs the allowlist, size, active-content-signature, and secret-pattern checks
synchronously and *before* anything is persisted -- a rejected upload never becomes a stored
`ItsmAttachment` in a `REJECTED` scan_state; it raises. The `PENDING`/`REJECTED` scan states are
real, constructible domain states (exercised directly at the domain layer), but this
synchronous service only ever persists a `PASSED` attachment, matching SS17's "before transfer or
ingestion" ordering literally.

`issue_download_link` and `consume_download_link` each independently call the injected
`ItsmAttachmentPermissionAuthorizer.authorize()` *and* `.classification_ceiling()` -- the
re-authorization SS17 requires happens at consumption, not merely at issuance, mirroring
`document_retrieval.DocumentKnowledgeRetrievalService.retrieve()`'s read-time-only use of
`classification_ceiling()`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from atlas import __version__
from atlas.core.audit import AuditSink
from atlas.core.classification import DataClassification
from atlas.modules.guardrails.domain.input_guardrails import detect_secret_patterns
from atlas.modules.identity.domain.models import AuthenticatedSubject, SubjectKind
from atlas.modules.itsm.application.attachments_ports import (
    ItsmAttachmentPermissionAuthorizer,
    ItsmAttachmentRepository,
    StoredItsmAttachmentDownloadLink,
)
from atlas.modules.itsm.application.dispatch_audit import (
    ItsmAuditEventKind,
    record_itsm_integration_event,
)
from atlas.modules.itsm.application.service import ItsmIntegrationError
from atlas.modules.itsm.domain.attachments import (
    ALLOWED_ATTACHMENT_MEDIA_TYPES,
    MAX_ATTACHMENT_SIZE_BYTES,
    ItsmAttachment,
    ItsmAttachmentDownloadLink,
    ItsmAttachmentScanState,
    ItsmEvidencePackage,
    active_content_signature_detected,
    attachment_content_is_text_decodable,
    embedded_script_markup_detected,
)

_ITSM_ATTACHMENT_READ = "itsm.attachments.read"
_ITSM_ATTACHMENT_CREATE = "itsm.attachments.create"
_ITSM_ATTACHMENT_DELETE = "itsm.attachments.delete"
_ITSM_ATTACHMENT_DOWNLOAD = "itsm.attachments.download"

_MIN_LINK_TTL_SECONDS = 60
_MAX_LINK_TTL_SECONDS = 86_400


class ItsmAttachmentError(ItsmIntegrationError):
    """Deliberately a subtype of `ItsmIntegrationError` so the existing itsm route error-code
    mapping convention (`code = str(error)`) handles it without a parallel mapper -- see
    `ItsmDispatchAuthorizationError` for the precedent."""


class ItsmAttachmentService:
    def __init__(
        self,
        *,
        repository: ItsmAttachmentRepository,
        permission_authorizer: ItsmAttachmentPermissionAuthorizer,
        audit_sink: AuditSink,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._repository = repository
        self._permission_authorizer = permission_authorizer
        self._audit_sink = audit_sink
        self._clock = clock or (lambda: datetime.now(UTC))

    @property
    def repository(self) -> ItsmAttachmentRepository:
        return self._repository

    async def upload(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        external_ticket_id: str,
        filename: str,
        media_type: str,
        content: bytes,
        classification: str,
        correlation_id: str,
    ) -> ItsmAttachment:
        self._require_human(actor)
        if actor.organization_id != organization_id:
            raise ItsmAttachmentError("itsm_attachment_scope_mismatch")
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            permission_id=_ITSM_ATTACHMENT_CREATE,
            correlation_id=correlation_id,
        )
        self._require_classification(classification)
        if media_type not in ALLOWED_ATTACHMENT_MEDIA_TYPES:
            raise ItsmAttachmentError("itsm_attachment_media_type_not_allowlisted")
        if not 1 <= len(content) <= MAX_ATTACHMENT_SIZE_BYTES:
            raise ItsmAttachmentError("itsm_attachment_size_out_of_bounds")
        if active_content_signature_detected(content):
            raise ItsmAttachmentError("itsm_attachment_active_content_detected")
        if attachment_content_is_text_decodable(media_type):
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError as error:
                raise ItsmAttachmentError("itsm_attachment_content_not_decodable") from error
            if embedded_script_markup_detected(text):
                raise ItsmAttachmentError("itsm_attachment_active_content_detected")
            if detect_secret_patterns(text):
                raise ItsmAttachmentError("itsm_attachment_secret_pattern_detected")

        now = self._clock()
        digest = sha256(content).hexdigest()
        seed = self._digest(
            [
                organization_id,
                environment_id,
                external_ticket_id,
                digest,
                actor.subject_id,
                now.isoformat(),
                uuid4().hex,
            ]
        )
        attachment_id = f"itsm-attachment.{seed[:24]}"
        try:
            attachment = ItsmAttachment(
                attachment_id=attachment_id,
                external_ticket_id=external_ticket_id,
                organization_id=organization_id,
                environment_id=environment_id,
                filename=filename,
                media_type=media_type,
                size_bytes=len(content),
                content_digest=digest,
                classification=classification,
                uploaded_by=actor.subject_id,
                uploaded_at=now,
                allowlist_check_completed=True,
                size_check_completed=True,
                active_content_policy_scan_completed=True,
                secret_pattern_scan_completed=True,
                scan_state=ItsmAttachmentScanState.PASSED,
                rejection_reason=None,
            )
        except ValueError as error:
            raise ItsmAttachmentError("itsm_attachment_invalid") from error
        if not await self._repository.add_attachment(attachment, content=content):
            raise ItsmAttachmentError("itsm_attachment_persistence_conflict")
        await self._audit(
            reference=attachment.attachment_id,
            actor=actor,
            correlation_id=correlation_id,
            event_kind=ItsmAuditEventKind.ATTACH,
            outcome="uploaded",
        )
        return attachment

    async def get(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        attachment_id: str,
        correlation_id: str,
    ) -> ItsmAttachment:
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            permission_id=_ITSM_ATTACHMENT_READ,
            correlation_id=correlation_id,
        )
        attachment = await self._repository.get_attachment(
            attachment_id=attachment_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if attachment is None:
            raise ItsmAttachmentError("itsm_attachment_not_found")
        await self._audit(
            reference=attachment.attachment_id,
            actor=actor,
            correlation_id=correlation_id,
            event_kind=ItsmAuditEventKind.RECORD_RETRIEVAL_OF_SENSITIVE_CONTENT,
            outcome="read",
        )
        return attachment

    async def delete(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        attachment_id: str,
        correlation_id: str,
    ) -> None:
        self._require_human(actor)
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            permission_id=_ITSM_ATTACHMENT_DELETE,
            correlation_id=correlation_id,
        )
        attachment = await self._repository.get_attachment(
            attachment_id=attachment_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if attachment is None:
            raise ItsmAttachmentError("itsm_attachment_not_found")
        if not await self._repository.delete_attachment(
            attachment_id=attachment_id,
            organization_id=organization_id,
            environment_id=environment_id,
        ):
            raise ItsmAttachmentError("itsm_attachment_delete_conflict")
        await self._audit(
            reference=attachment_id,
            actor=actor,
            correlation_id=correlation_id,
            event_kind=ItsmAuditEventKind.STATE_TRANSITION,
            outcome="deleted",
        )

    async def replace(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        attachment_id: str,
        filename: str,
        media_type: str,
        content: bytes,
        classification: str,
        correlation_id: str,
    ) -> ItsmAttachment:
        self._require_human(actor)
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            permission_id=_ITSM_ATTACHMENT_CREATE,
            correlation_id=correlation_id,
        )
        existing = await self._repository.get_attachment(
            attachment_id=attachment_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if existing is None:
            raise ItsmAttachmentError("itsm_attachment_not_found")
        self._require_classification(classification)
        if media_type not in ALLOWED_ATTACHMENT_MEDIA_TYPES:
            raise ItsmAttachmentError("itsm_attachment_media_type_not_allowlisted")
        if not 1 <= len(content) <= MAX_ATTACHMENT_SIZE_BYTES:
            raise ItsmAttachmentError("itsm_attachment_size_out_of_bounds")
        if active_content_signature_detected(content):
            raise ItsmAttachmentError("itsm_attachment_active_content_detected")
        if attachment_content_is_text_decodable(media_type):
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError as error:
                raise ItsmAttachmentError("itsm_attachment_content_not_decodable") from error
            if embedded_script_markup_detected(text):
                raise ItsmAttachmentError("itsm_attachment_active_content_detected")
            if detect_secret_patterns(text):
                raise ItsmAttachmentError("itsm_attachment_secret_pattern_detected")

        now = self._clock()
        digest = sha256(content).hexdigest()
        try:
            replacement = ItsmAttachment(
                attachment_id=existing.attachment_id,
                external_ticket_id=existing.external_ticket_id,
                organization_id=organization_id,
                environment_id=environment_id,
                filename=filename,
                media_type=media_type,
                size_bytes=len(content),
                content_digest=digest,
                classification=classification,
                uploaded_by=actor.subject_id,
                uploaded_at=now,
                allowlist_check_completed=True,
                size_check_completed=True,
                active_content_policy_scan_completed=True,
                secret_pattern_scan_completed=True,
                scan_state=ItsmAttachmentScanState.PASSED,
                rejection_reason=None,
            )
        except ValueError as error:
            raise ItsmAttachmentError("itsm_attachment_invalid") from error
        if not await self._repository.replace_attachment(
            expected=existing, replacement=replacement, content=content
        ):
            raise ItsmAttachmentError("itsm_attachment_replace_conflict")
        await self._audit(
            reference=replacement.attachment_id,
            actor=actor,
            correlation_id=correlation_id,
            event_kind=ItsmAuditEventKind.UPDATE,
            outcome="replaced",
        )
        return replacement

    async def create_evidence_package(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        external_ticket_id: str,
        attachment_ids: tuple[str, ...],
        artifact_versions: tuple[str, ...],
        classification: str,
        expires_at: datetime | None,
        correlation_id: str,
    ) -> ItsmEvidencePackage:
        self._require_human(actor)
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            permission_id=_ITSM_ATTACHMENT_CREATE,
            correlation_id=correlation_id,
        )
        requested = self._require_classification(classification)
        if not attachment_ids:
            raise ItsmAttachmentError("itsm_evidence_package_attachments_required")
        attachments: list[ItsmAttachment] = []
        for attachment_id in attachment_ids:
            attachment = await self._repository.get_attachment(
                attachment_id=attachment_id,
                organization_id=organization_id,
                environment_id=environment_id,
            )
            if attachment is None:
                raise ItsmAttachmentError("itsm_attachment_not_found")
            if attachment.external_ticket_id != external_ticket_id:
                raise ItsmAttachmentError("itsm_evidence_package_ticket_mismatch")
            if not attachment.transferable:
                raise ItsmAttachmentError("itsm_evidence_package_attachment_not_transferable")
            attachments.append(attachment)
        highest = max(
            DataClassification(item.classification.removeprefix("classification."))
            for item in attachments
        )
        if not requested.permits(highest):
            raise ItsmAttachmentError("itsm_evidence_package_classification_too_low")

        ordered = sorted(attachments, key=lambda item: item.attachment_id)
        manifest_payload = tuple(
            {
                "attachment_id": item.attachment_id,
                "content_digest": item.content_digest,
                "filename": item.filename,
                "size_bytes": item.size_bytes,
            }
            for item in ordered
        )
        manifest_digest = self._digest(manifest_payload)
        now = self._clock()
        seed = self._digest(
            [
                organization_id,
                environment_id,
                external_ticket_id,
                manifest_digest,
                actor.subject_id,
                now.isoformat(),
                uuid4().hex,
            ]
        )
        try:
            package = ItsmEvidencePackage(
                package_id=f"itsm-evidence-package.{seed[:24]}",
                organization_id=organization_id,
                environment_id=environment_id,
                external_ticket_id=external_ticket_id,
                attachment_ids=tuple(item.attachment_id for item in ordered),
                manifest_digest=manifest_digest,
                artifact_versions=artifact_versions,
                classification=classification,
                custodied_by=actor.subject_id,
                created_by=actor.subject_id,
                created_at=now,
                expires_at=expires_at,
            )
        except ValueError as error:
            raise ItsmAttachmentError("itsm_evidence_package_invalid") from error
        if not await self._repository.add_evidence_package(package):
            raise ItsmAttachmentError("itsm_evidence_package_persistence_conflict")
        await self._audit(
            reference=package.package_id,
            actor=actor,
            correlation_id=correlation_id,
            event_kind=ItsmAuditEventKind.ATTACH,
            outcome="evidence_package_created",
        )
        return package

    async def get_evidence_package(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        package_id: str,
        correlation_id: str,
    ) -> ItsmEvidencePackage:
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            permission_id=_ITSM_ATTACHMENT_READ,
            correlation_id=correlation_id,
        )
        package = await self._repository.get_evidence_package(
            package_id=package_id, organization_id=organization_id, environment_id=environment_id
        )
        if package is None:
            raise ItsmAttachmentError("itsm_evidence_package_not_found")
        await self._audit(
            reference=package.package_id,
            actor=actor,
            correlation_id=correlation_id,
            event_kind=ItsmAuditEventKind.RECORD_RETRIEVAL_OF_SENSITIVE_CONTENT,
            outcome="read",
        )
        return package

    async def issue_download_link(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        package_id: str,
        attachment_id: str,
        ttl_seconds: int,
        correlation_id: str,
    ) -> ItsmAttachmentDownloadLink:
        self._require_human(actor)
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            permission_id=_ITSM_ATTACHMENT_DOWNLOAD,
            correlation_id=correlation_id,
        )
        ceiling = await self._permission_authorizer.classification_ceiling(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            correlation_id=correlation_id,
        )
        if not _MIN_LINK_TTL_SECONDS <= ttl_seconds <= _MAX_LINK_TTL_SECONDS:
            raise ItsmAttachmentError("itsm_attachment_download_link_ttl_invalid")
        package = await self._repository.get_evidence_package(
            package_id=package_id, organization_id=organization_id, environment_id=environment_id
        )
        if package is None:
            raise ItsmAttachmentError("itsm_evidence_package_not_found")
        if attachment_id not in package.attachment_ids:
            raise ItsmAttachmentError("itsm_evidence_package_attachment_not_member")
        attachment = await self._repository.get_attachment(
            attachment_id=attachment_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if attachment is None or not attachment.transferable:
            raise ItsmAttachmentError("itsm_attachment_not_found")
        requested = DataClassification(attachment.classification.removeprefix("classification."))
        if not ceiling.permits(requested):
            raise ItsmAttachmentError("itsm_attachment_classification_ceiling_exceeded")

        now = self._clock()
        seed = self._digest(
            [package_id, attachment_id, actor.subject_id, now.isoformat(), uuid4().hex]
        )
        try:
            link = ItsmAttachmentDownloadLink(
                link_id=f"itsm-attachment-download-link.{seed[:24]}",
                attachment_id=attachment_id,
                issued_to_subject_id=actor.subject_id,
                issued_at=now,
                expires_at=now + timedelta(seconds=ttl_seconds),
                consumed_at=None,
            )
        except ValueError as error:
            raise ItsmAttachmentError("itsm_attachment_download_link_invalid") from error
        stored = StoredItsmAttachmentDownloadLink(
            link=link,
            package_id=package_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if not await self._repository.add_download_link(stored):
            raise ItsmAttachmentError("itsm_attachment_download_link_persistence_conflict")
        await self._audit(
            reference=link.link_id,
            actor=actor,
            correlation_id=correlation_id,
            event_kind=ItsmAuditEventKind.LINK,
            outcome="download_link_issued",
        )
        return link

    async def consume_download_link(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        package_id: str,
        link_id: str,
        correlation_id: str,
    ) -> tuple[ItsmAttachment, bytes]:
        self._require_human(actor)
        await self._permission_authorizer.authorize(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            permission_id=_ITSM_ATTACHMENT_DOWNLOAD,
            correlation_id=correlation_id,
        )
        ceiling = await self._permission_authorizer.classification_ceiling(
            actor=actor,
            organization_id=organization_id,
            environment_id=environment_id,
            correlation_id=correlation_id,
        )
        stored = await self._repository.get_download_link(link_id=link_id)
        if (
            stored is None
            or stored.package_id != package_id
            or stored.organization_id != organization_id
            or stored.environment_id != environment_id
        ):
            await self._audit_denied(
                reference=link_id,
                actor=actor,
                correlation_id=correlation_id,
                result_code="itsm_attachment_download_link_not_found",
            )
            raise ItsmAttachmentError("itsm_attachment_download_link_not_found")
        link = stored.link
        if link.issued_to_subject_id != actor.subject_id:
            await self._audit_denied(
                reference=link_id,
                actor=actor,
                correlation_id=correlation_id,
                result_code="itsm_attachment_download_link_subject_mismatch",
            )
            raise ItsmAttachmentError("itsm_attachment_download_link_subject_mismatch")
        now = self._clock()
        if not link.active_at(now):
            await self._audit_denied(
                reference=link_id,
                actor=actor,
                correlation_id=correlation_id,
                result_code="itsm_attachment_download_link_expired_or_consumed",
            )
            raise ItsmAttachmentError("itsm_attachment_download_link_expired_or_consumed")
        attachment = await self._repository.get_attachment(
            attachment_id=link.attachment_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if attachment is None or not attachment.transferable:
            raise ItsmAttachmentError("itsm_attachment_not_found")
        requested = DataClassification(attachment.classification.removeprefix("classification."))
        if not ceiling.permits(requested):
            await self._audit_denied(
                reference=link_id,
                actor=actor,
                correlation_id=correlation_id,
                result_code="itsm_attachment_classification_ceiling_exceeded",
            )
            raise ItsmAttachmentError("itsm_attachment_classification_ceiling_exceeded")
        content = await self._repository.get_attachment_content(
            attachment_id=attachment.attachment_id,
            organization_id=organization_id,
            environment_id=environment_id,
        )
        if content is None or sha256(content).hexdigest() != attachment.content_digest:
            raise ItsmAttachmentError("itsm_attachment_content_integrity_failed")
        consumed = await self._repository.consume_download_link(link_id=link_id, consumed_at=now)
        if consumed is None:
            raise ItsmAttachmentError("itsm_attachment_download_link_expired_or_consumed")
        await self._audit(
            reference=link_id,
            actor=actor,
            correlation_id=correlation_id,
            event_kind=ItsmAuditEventKind.RESTRICTED_EXPORT,
            outcome="downloaded",
        )
        return attachment, content

    async def close(self) -> None:
        await self._repository.close()

    @staticmethod
    def _require_classification(classification: str) -> DataClassification:
        try:
            return DataClassification(classification.removeprefix("classification."))
        except ValueError as error:
            raise ItsmAttachmentError("itsm_attachment_classification_unrecognized") from error

    @staticmethod
    def _require_human(actor: AuthenticatedSubject) -> None:
        if actor.kind is not SubjectKind.HUMAN:
            raise ItsmAttachmentError("itsm_attachment_human_required")

    async def _audit(
        self,
        *,
        reference: str,
        actor: AuthenticatedSubject,
        correlation_id: str,
        event_kind: ItsmAuditEventKind,
        outcome: str,
    ) -> None:
        await record_itsm_integration_event(
            self._audit_sink,
            event_kind=event_kind,
            profile_reference=reference,
            actor_identity=actor.subject_id,
            is_automation=actor.kind is not SubjectKind.HUMAN,
            outcome=outcome,
            external_record_id=None,
            external_source_version=None,
            idempotency_key=None,
            detail_references=(reference,),
            occurred_at=self._clock(),
            correlation_id=correlation_id,
            event_id=f"evt_{uuid4().hex}",
            producer="project-atlas-api",
            producer_version=__version__,
        )

    async def _audit_denied(
        self,
        *,
        reference: str,
        actor: AuthenticatedSubject,
        correlation_id: str,
        result_code: str,
    ) -> None:
        await record_itsm_integration_event(
            self._audit_sink,
            event_kind=ItsmAuditEventKind.RESTRICTED_EXPORT,
            profile_reference=reference,
            actor_identity=actor.subject_id,
            is_automation=actor.kind is not SubjectKind.HUMAN,
            outcome="denied",
            external_record_id=None,
            external_source_version=None,
            idempotency_key=None,
            detail_references=(result_code,),
            occurred_at=self._clock(),
            correlation_id=correlation_id,
            event_id=f"evt_{uuid4().hex}",
            producer="project-atlas-api",
            producer_version=__version__,
        )

    @staticmethod
    def _digest(payload: object) -> str:
        return sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        ).hexdigest()
