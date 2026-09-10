"""ATLAS-036 SS17: attachments and evidence.

Pass 32 of this session's standing audit loop found SS17 had zero implementation anywhere in
`atlas.modules.itsm` -- no attachment upload/download, no active-content check, no
classification/permission validation, no evidence manifest/checksum packaging, no
secret-exclusion default, no expiring re-authorized links, and no audit coverage. This file
covers, mirroring `test_package_content_policy_scan.py`'s split: domain-level invariants, then
service-level business rules against a fake (but Protocol-real) permission authorizer with a
controllable clock, then HTTP-level reachability and the two-stage authentication/authorization
denial pattern this session has applied to every other route file.
"""

from __future__ import annotations

import base64
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from atlas.api.app import create_app
from atlas.core.audit import AuditRecord
from atlas.core.classification import DataClassification
from atlas.core.config import Settings
from atlas.modules.identity.domain.models import (
    AssuranceLevel,
    AuthenticatedSubject,
    AuthenticationMethod,
    SubjectKind,
)
from atlas.modules.itsm.adapters.attachments_memory import InMemoryItsmAttachmentRepository
from atlas.modules.itsm.application.attachments import ItsmAttachmentError, ItsmAttachmentService
from atlas.modules.itsm.domain.attachments import (
    ItsmAttachment,
    ItsmAttachmentDownloadLink,
    ItsmAttachmentScanState,
    ItsmEvidencePackage,
    active_content_signature_detected,
    embedded_script_markup_detected,
)

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)
ORG = "organization.development"
ENV = "environment.test"


def _subject(
    subject_id: str = "subject.itsm.attachment-operator",
    *,
    organization_id: str = ORG,
    kind: SubjectKind = SubjectKind.HUMAN,
) -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id=subject_id,
        display_name="ITSM Attachment Operator",
        kind=kind,
        provider_id="provider.ldap.test",
        authentication_method=AuthenticationMethod.LDAP,
        assurance_level=AssuranceLevel.MULTI_FACTOR,
        authenticated_at=NOW,
        organization_id=organization_id,
        role_ids=("role.itsm-attachment-operator",),
    )


class CollectingAuditSink:
    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    async def record(self, event: AuditRecord) -> None:
        self.records.append(event)


class _Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now


class _FakeAttachmentAuthorizer:
    """Satisfies `ItsmAttachmentPermissionAuthorizer` without any real RBAC wiring -- the
    service-level tests below exercise the attachment business rules, not the authorization
    stack (that is exercised separately by the real, RBAC-backed HTTP tests at the bottom of this
    file)."""

    def __init__(self, *, ceiling: DataClassification = DataClassification.RESTRICTED) -> None:
        self.ceiling = ceiling
        self.denied = False

    async def authorize(self, **_: object) -> None:
        if self.denied:
            raise ItsmAttachmentError("itsm_attachment_permission_denied")

    async def classification_ceiling(self, **_: object) -> DataClassification:
        return self.ceiling


def _service(
    *,
    authorizer: _FakeAttachmentAuthorizer | None = None,
    clock: Callable[[], datetime] | None = None,
) -> tuple[
    ItsmAttachmentService,
    InMemoryItsmAttachmentRepository,
    _FakeAttachmentAuthorizer,
    CollectingAuditSink,
]:
    repository = InMemoryItsmAttachmentRepository()
    resolved_authorizer = authorizer or _FakeAttachmentAuthorizer()
    audit = CollectingAuditSink()
    service = ItsmAttachmentService(
        repository=repository,
        permission_authorizer=resolved_authorizer,
        audit_sink=audit,
        clock=clock or (lambda: NOW),
    )
    return service, repository, resolved_authorizer, audit


async def _upload(
    service: ItsmAttachmentService,
    *,
    actor: AuthenticatedSubject | None = None,
    external_ticket_id: str = "INC0010001",
    filename: str = "notes.txt",
    media_type: str = "text/plain",
    content: bytes = b"clean diagnostic notes with no secrets in them",
    classification: str = "classification.internal",
) -> ItsmAttachment:
    return await service.upload(
        actor=actor or _subject(),
        organization_id=ORG,
        environment_id=ENV,
        external_ticket_id=external_ticket_id,
        filename=filename,
        media_type=media_type,
        content=content,
        classification=classification,
        correlation_id="cor_itsm_attachment_test",
    )


async def _evidence_package(
    service: ItsmAttachmentService,
    *,
    attachment_ids: tuple[str, ...],
    actor: AuthenticatedSubject | None = None,
    external_ticket_id: str = "INC0010001",
    classification: str = "classification.internal",
    expires_at: datetime | None = None,
) -> ItsmEvidencePackage:
    return await service.create_evidence_package(
        actor=actor or _subject(),
        organization_id=ORG,
        environment_id=ENV,
        external_ticket_id=external_ticket_id,
        attachment_ids=attachment_ids,
        artifact_versions=("report.itsm-attachment-test:v1",),
        classification=classification,
        expires_at=expires_at,
        correlation_id="cor_itsm_attachment_test",
    )


# ---------------------------------------------------------------------------
# Domain-level invariants
# ---------------------------------------------------------------------------


def _attachment(**overrides: object) -> ItsmAttachment:
    defaults: dict[str, object] = {
        "attachment_id": "itsm-attachment.example0000000000000001",
        "external_ticket_id": "INC0010001",
        "organization_id": ORG,
        "environment_id": ENV,
        "filename": "notes.txt",
        "media_type": "text/plain",
        "size_bytes": 10,
        "content_digest": "a" * 64,
        "classification": "classification.internal",
        "uploaded_by": "subject.itsm.attachment-operator",
        "uploaded_at": NOW,
        "allowlist_check_completed": True,
        "size_check_completed": True,
        "active_content_policy_scan_completed": True,
        "secret_pattern_scan_completed": True,
        "scan_state": ItsmAttachmentScanState.PASSED,
        "rejection_reason": None,
    }
    defaults.update(overrides)
    return ItsmAttachment(**defaults)  # type: ignore[arg-type]


def test_attachment_builds_when_passed_checks_are_honest() -> None:
    attachment = _attachment()
    assert attachment.transferable is True


def test_attachment_cannot_claim_a_real_malware_signature_scan() -> None:
    with pytest.raises(ValueError, match="no real scanner engine"):
        _attachment(malware_signature_scan_completed=True)


def test_attachment_cannot_be_passed_without_every_real_check_completed() -> None:
    with pytest.raises(ValueError, match="every real check"):
        _attachment(secret_pattern_scan_completed=False)


def test_attachment_passed_cannot_carry_a_rejection_reason() -> None:
    with pytest.raises(ValueError, match="cannot carry a rejection reason"):
        _attachment(rejection_reason="should not be here")


def test_attachment_rejected_requires_a_rejection_reason() -> None:
    with pytest.raises(ValueError, match="requires a rejection reason"):
        _attachment(scan_state=ItsmAttachmentScanState.REJECTED, rejection_reason=None)


def test_attachment_rejected_is_never_transferable() -> None:
    attachment = _attachment(
        scan_state=ItsmAttachmentScanState.REJECTED,
        rejection_reason="disallowed media type",
        allowlist_check_completed=False,
    )
    assert attachment.transferable is False


def test_attachment_pending_cannot_carry_a_rejection_reason() -> None:
    with pytest.raises(ValueError, match="pending ITSM attachment"):
        _attachment(
            scan_state=ItsmAttachmentScanState.PENDING,
            rejection_reason="premature",
            allowlist_check_completed=False,
            size_check_completed=False,
            active_content_policy_scan_completed=False,
            secret_pattern_scan_completed=False,
        )


def test_attachment_media_type_must_be_allowlisted() -> None:
    with pytest.raises(ValueError, match="not allowlisted"):
        _attachment(media_type="application/zip")


def test_attachment_size_must_be_within_bounds() -> None:
    with pytest.raises(ValueError, match="bounded allowance"):
        _attachment(size_bytes=0)


def test_active_content_signature_detected_for_a_disguised_executable() -> None:
    assert active_content_signature_detected(b"MZ\x90\x00\x03\x00\x00\x00") is True
    assert active_content_signature_detected(b"%PDF-1.4 a normal pdf body") is False


def test_embedded_script_markup_detected() -> None:
    assert embedded_script_markup_detected("hello <script>alert(1)</script>") is True
    assert embedded_script_markup_detected("just plain notes") is False


def _evidence_package_domain(**overrides: object) -> ItsmEvidencePackage:
    defaults: dict[str, object] = {
        "package_id": "itsm-evidence-package.example000000000001",
        "organization_id": ORG,
        "environment_id": ENV,
        "external_ticket_id": "INC0010001",
        "attachment_ids": ("itsm-attachment.example0000000000000001",),
        "manifest_digest": "b" * 64,
        "artifact_versions": ("report.itsm-attachment-test:v1",),
        "classification": "classification.internal",
        "custodied_by": "subject.itsm.attachment-operator",
        "created_by": "subject.itsm.attachment-operator",
        "created_at": NOW,
        "expires_at": None,
    }
    defaults.update(overrides)
    return ItsmEvidencePackage(**defaults)  # type: ignore[arg-type]


def test_evidence_package_requires_distinct_attachments() -> None:
    with pytest.raises(ValueError, match="1-50 distinct attachments"):
        _evidence_package_domain(attachment_ids=())


def test_evidence_package_cannot_expire_before_it_is_created() -> None:
    with pytest.raises(ValueError, match="cannot expire before it is created"):
        _evidence_package_domain(expires_at=NOW - timedelta(hours=1))


def test_evidence_package_accepts_an_appropriate_expiry() -> None:
    package = _evidence_package_domain(expires_at=NOW + timedelta(days=7))
    assert package.expires_at is not None


def _download_link(**overrides: object) -> ItsmAttachmentDownloadLink:
    defaults: dict[str, object] = {
        "link_id": "itsm-attachment-download-link.example00001",
        "attachment_id": "itsm-attachment.example0000000000000001",
        "issued_to_subject_id": "subject.itsm.attachment-operator",
        "issued_at": NOW,
        "expires_at": NOW + timedelta(minutes=5),
        "consumed_at": None,
    }
    defaults.update(overrides)
    return ItsmAttachmentDownloadLink(**defaults)  # type: ignore[arg-type]


def test_download_link_must_expire_after_it_is_issued() -> None:
    with pytest.raises(ValueError, match="must expire after it is issued"):
        _download_link(expires_at=NOW)


def test_download_link_active_at_reflects_expiry_and_consumption() -> None:
    link = _download_link()
    assert link.active_at(NOW + timedelta(minutes=1)) is True
    assert link.active_at(NOW + timedelta(minutes=10)) is False
    consumed = _download_link(consumed_at=NOW + timedelta(minutes=1))
    assert consumed.active_at(NOW + timedelta(seconds=30)) is False


def test_download_link_cannot_be_consumed_outside_its_validity_window() -> None:
    with pytest.raises(ValueError, match="outside its validity window"):
        _download_link(consumed_at=NOW + timedelta(minutes=10))


# ---------------------------------------------------------------------------
# Service-level business rules
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_persists_a_passed_attachment_and_audits_it() -> None:
    service, repository, _, audit = _service()

    attachment = await _upload(service)

    assert attachment.scan_state is ItsmAttachmentScanState.PASSED
    assert attachment.transferable is True
    assert (
        await repository.get_attachment(
            attachment_id=attachment.attachment_id, organization_id=ORG, environment_id=ENV
        )
        == attachment
    )
    assert [record.result_code for record in audit.records] == ["itsm_integration.attach.uploaded"]


@pytest.mark.asyncio
async def test_upload_requires_a_human_actor() -> None:
    service, _, _, _ = _service()
    with pytest.raises(ItsmAttachmentError, match="itsm_attachment_human_required"):
        await _upload(service, actor=_subject(kind=SubjectKind.SERVICE))


@pytest.mark.asyncio
async def test_upload_rejects_a_disallowed_media_type() -> None:
    service, _, _, _ = _service()
    with pytest.raises(ItsmAttachmentError, match="not_allowlisted"):
        await _upload(service, media_type="application/zip", filename="bundle.zip")


@pytest.mark.asyncio
async def test_upload_rejects_oversized_content() -> None:
    service, _, _, _ = _service()
    with pytest.raises(ItsmAttachmentError, match="size_out_of_bounds"):
        await _upload(service, content=b"a" * 10_000_001)


@pytest.mark.asyncio
async def test_upload_rejects_active_content_disguised_as_an_allowlisted_type() -> None:
    service, _, _, _ = _service()
    with pytest.raises(ItsmAttachmentError, match="active_content_detected"):
        await _upload(
            service,
            media_type="application/pdf",
            filename="report.pdf",
            content=b"MZ\x90\x00\x03\x00\x00\x00 disguised executable",
        )


@pytest.mark.asyncio
async def test_upload_rejects_embedded_script_markup() -> None:
    service, _, _, _ = _service()
    with pytest.raises(ItsmAttachmentError, match="active_content_detected"):
        await _upload(service, content=b"notes <script>alert(1)</script>")


@pytest.mark.asyncio
async def test_upload_rejects_a_secret_pattern() -> None:
    service, _, _, _ = _service()
    matched_value = "Sup3r" + "SyntheticValue"
    with pytest.raises(ItsmAttachmentError, match="secret_pattern_detected"):
        await _upload(service, content=f"password = {matched_value}".encode())


@pytest.mark.asyncio
async def test_upload_rejects_an_unrecognized_classification() -> None:
    service, _, _, _ = _service()
    with pytest.raises(ItsmAttachmentError, match="classification_unrecognized"):
        await _upload(service, classification="classification.not-a-real-level")


@pytest.mark.asyncio
async def test_get_returns_the_uploaded_attachment() -> None:
    service, _, _, _ = _service()
    uploaded = await _upload(service)
    fetched = await service.get(
        actor=_subject(),
        organization_id=ORG,
        environment_id=ENV,
        attachment_id=uploaded.attachment_id,
        correlation_id="cor_itsm_attachment_test",
    )
    assert fetched == uploaded


@pytest.mark.asyncio
async def test_get_unknown_attachment_is_not_found() -> None:
    service, _, _, _ = _service()
    with pytest.raises(ItsmAttachmentError, match="itsm_attachment_not_found"):
        await service.get(
            actor=_subject(),
            organization_id=ORG,
            environment_id=ENV,
            attachment_id="itsm-attachment.does-not-exist",
            correlation_id="cor_itsm_attachment_test",
        )


@pytest.mark.asyncio
async def test_delete_removes_the_attachment() -> None:
    service, _, _, _ = _service()
    uploaded = await _upload(service)
    await service.delete(
        actor=_subject(),
        organization_id=ORG,
        environment_id=ENV,
        attachment_id=uploaded.attachment_id,
        correlation_id="cor_itsm_attachment_test",
    )
    with pytest.raises(ItsmAttachmentError, match="itsm_attachment_not_found"):
        await service.get(
            actor=_subject(),
            organization_id=ORG,
            environment_id=ENV,
            attachment_id=uploaded.attachment_id,
            correlation_id="cor_itsm_attachment_test",
        )


@pytest.mark.asyncio
async def test_replace_updates_content_and_digest_in_place() -> None:
    service, _, _, _ = _service()
    uploaded = await _upload(service, content=b"original clean content")
    replaced = await service.replace(
        actor=_subject(),
        organization_id=ORG,
        environment_id=ENV,
        attachment_id=uploaded.attachment_id,
        filename="notes-v2.txt",
        media_type="text/plain",
        content=b"replacement clean content",
        classification="classification.internal",
        correlation_id="cor_itsm_attachment_test",
    )
    assert replaced.attachment_id == uploaded.attachment_id
    assert replaced.content_digest != uploaded.content_digest
    assert replaced.filename == "notes-v2.txt"


@pytest.mark.asyncio
async def test_create_evidence_package_requires_transferable_attachments() -> None:
    service, _, _, _ = _service()
    with pytest.raises(ItsmAttachmentError, match="itsm_attachment_not_found"):
        await _evidence_package(service, attachment_ids=("itsm-attachment.does-not-exist",))


@pytest.mark.asyncio
async def test_create_evidence_package_requires_a_sufficient_classification() -> None:
    service, _, _, _ = _service()
    attachment = await _upload(service, classification="classification.confidential")
    with pytest.raises(ItsmAttachmentError, match="classification_too_low"):
        await _evidence_package(
            service,
            attachment_ids=(attachment.attachment_id,),
            classification="classification.internal",
        )


@pytest.mark.asyncio
async def test_create_evidence_package_builds_a_real_manifest() -> None:
    service, _, _, _ = _service()
    attachment = await _upload(service)
    package = await _evidence_package(
        service,
        attachment_ids=(attachment.attachment_id,),
        classification="classification.internal",
    )
    assert package.attachment_ids == (attachment.attachment_id,)
    assert len(package.manifest_digest) == 64


@pytest.mark.asyncio
async def test_issue_and_consume_download_link_returns_the_original_content() -> None:
    content = b"clean diagnostic notes with no secrets in them"
    service, _, _, _ = _service()
    attachment = await _upload(service, content=content)
    package = await _evidence_package(service, attachment_ids=(attachment.attachment_id,))
    link = await service.issue_download_link(
        actor=_subject(),
        organization_id=ORG,
        environment_id=ENV,
        package_id=package.package_id,
        attachment_id=attachment.attachment_id,
        ttl_seconds=300,
        correlation_id="cor_itsm_attachment_test",
    )
    downloaded_attachment, downloaded_content = await service.consume_download_link(
        actor=_subject(),
        organization_id=ORG,
        environment_id=ENV,
        package_id=package.package_id,
        link_id=link.link_id,
        correlation_id="cor_itsm_attachment_test",
    )
    assert downloaded_attachment == attachment
    assert downloaded_content == content


@pytest.mark.asyncio
async def test_consume_download_link_rejects_a_second_consumption() -> None:
    service, _, _, _ = _service()
    attachment = await _upload(service)
    package = await _evidence_package(service, attachment_ids=(attachment.attachment_id,))
    link = await service.issue_download_link(
        actor=_subject(),
        organization_id=ORG,
        environment_id=ENV,
        package_id=package.package_id,
        attachment_id=attachment.attachment_id,
        ttl_seconds=300,
        correlation_id="cor_itsm_attachment_test",
    )
    await service.consume_download_link(
        actor=_subject(),
        organization_id=ORG,
        environment_id=ENV,
        package_id=package.package_id,
        link_id=link.link_id,
        correlation_id="cor_itsm_attachment_test",
    )
    with pytest.raises(ItsmAttachmentError, match="expired_or_consumed"):
        await service.consume_download_link(
            actor=_subject(),
            organization_id=ORG,
            environment_id=ENV,
            package_id=package.package_id,
            link_id=link.link_id,
            correlation_id="cor_itsm_attachment_test",
        )


@pytest.mark.asyncio
async def test_consume_download_link_rejects_a_different_subject() -> None:
    service, _, _, _ = _service()
    attachment = await _upload(service)
    package = await _evidence_package(service, attachment_ids=(attachment.attachment_id,))
    link = await service.issue_download_link(
        actor=_subject("subject.itsm.issuer"),
        organization_id=ORG,
        environment_id=ENV,
        package_id=package.package_id,
        attachment_id=attachment.attachment_id,
        ttl_seconds=300,
        correlation_id="cor_itsm_attachment_test",
    )
    with pytest.raises(ItsmAttachmentError, match="subject_mismatch"):
        await service.consume_download_link(
            actor=_subject("subject.itsm.someone-else"),
            organization_id=ORG,
            environment_id=ENV,
            package_id=package.package_id,
            link_id=link.link_id,
            correlation_id="cor_itsm_attachment_test",
        )


@pytest.mark.asyncio
async def test_consume_download_link_rejects_after_expiry() -> None:
    clock = _Clock(NOW)
    service, _, _, _ = _service(clock=clock)
    attachment = await _upload(service)
    package = await _evidence_package(service, attachment_ids=(attachment.attachment_id,))
    link = await service.issue_download_link(
        actor=_subject(),
        organization_id=ORG,
        environment_id=ENV,
        package_id=package.package_id,
        attachment_id=attachment.attachment_id,
        ttl_seconds=60,
        correlation_id="cor_itsm_attachment_test",
    )
    clock.now = NOW + timedelta(seconds=61)
    with pytest.raises(ItsmAttachmentError, match="expired_or_consumed"):
        await service.consume_download_link(
            actor=_subject(),
            organization_id=ORG,
            environment_id=ENV,
            package_id=package.package_id,
            link_id=link.link_id,
            correlation_id="cor_itsm_attachment_test",
        )


@pytest.mark.asyncio
async def test_issue_download_link_re_checks_classification_ceiling_at_issuance() -> None:
    authorizer = _FakeAttachmentAuthorizer(ceiling=DataClassification.INTERNAL)
    service, _, _, _ = _service(authorizer=authorizer)
    attachment = await _upload(service, classification="classification.confidential")
    package = await _evidence_package(
        service,
        attachment_ids=(attachment.attachment_id,),
        classification="classification.confidential",
    )
    with pytest.raises(ItsmAttachmentError, match="ceiling_exceeded"):
        await service.issue_download_link(
            actor=_subject(),
            organization_id=ORG,
            environment_id=ENV,
            package_id=package.package_id,
            attachment_id=attachment.attachment_id,
            ttl_seconds=300,
            correlation_id="cor_itsm_attachment_test",
        )


@pytest.mark.asyncio
async def test_consume_download_link_re_checks_classification_ceiling_not_just_at_issuance() -> (
    None
):
    """SS17: 'Links re-authorize access in Atlas.' The permission and classification-ceiling
    check must happen again at consumption -- a ceiling that was sufficient at issuance and is
    lowered before the link is used must still be honored, not bypassed by the earlier check."""
    authorizer = _FakeAttachmentAuthorizer(ceiling=DataClassification.RESTRICTED)
    service, _, _, _ = _service(authorizer=authorizer)
    attachment = await _upload(service, classification="classification.confidential")
    package = await _evidence_package(
        service,
        attachment_ids=(attachment.attachment_id,),
        classification="classification.confidential",
    )
    link = await service.issue_download_link(
        actor=_subject(),
        organization_id=ORG,
        environment_id=ENV,
        package_id=package.package_id,
        attachment_id=attachment.attachment_id,
        ttl_seconds=300,
        correlation_id="cor_itsm_attachment_test",
    )
    authorizer.ceiling = DataClassification.INTERNAL
    with pytest.raises(ItsmAttachmentError, match="ceiling_exceeded"):
        await service.consume_download_link(
            actor=_subject(),
            organization_id=ORG,
            environment_id=ENV,
            package_id=package.package_id,
            link_id=link.link_id,
            correlation_id="cor_itsm_attachment_test",
        )


# ---------------------------------------------------------------------------
# HTTP-level reachability and denial
# ---------------------------------------------------------------------------


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "development_identity_enabled": True,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/v1/authentication/sessions",
        json={"username": "atlas-demo", "password": "local-demo"},
    )
    assert response.status_code == 201
    return str(response.headers["X-CSRF-Token"])


def test_itsm_attachments_require_authentication() -> None:
    """No session cookie and no development identity: every route must fail closed at
    authentication, not merely at authorization."""
    with TestClient(create_app(Settings(environment="test"))) as client:
        upload = client.post(
            "/api/v1/itsm/attachments",
            json={
                "external_ticket_id": "INC0010001",
                "filename": "notes.txt",
                "media_type": "text/plain",
                "classification": "classification.internal",
                "content_base64": "Y2xlYW4=",
            },
        )
        read = client.get("/api/v1/itsm/attachments/itsm-attachment.wiring-test-auth")
        download = client.get(
            "/api/v1/itsm/evidence-packages/itsm-evidence-package.wiring-test-auth/"
            "download-links/itsm-attachment-download-link.wiring-test-auth"
        )
    for response in (upload, read, download):
        assert response.status_code == 401, response.text
        assert response.json()["code"] == "authentication_required"


def test_itsm_attachments_require_permission() -> None:
    """A real, logged-in human subject with zero granted role permissions must still be denied
    by the real `AuthorizationService`, not by a faked dependency override."""
    with TestClient(create_app(_settings(development_role_ids=()))) as client:
        csrf = _login(client)
        upload_denied = client.post(
            "/api/v1/itsm/attachments",
            json={
                "external_ticket_id": "INC0010001",
                "filename": "notes.txt",
                "media_type": "text/plain",
                "classification": "classification.internal",
                "content_base64": "Y2xlYW4=",
            },
            headers={"X-CSRF-Token": csrf},
        )
        read_denied = client.get(
            "/api/v1/itsm/attachments/itsm-attachment.wiring-test-denied",
        )
        delete_denied = client.delete(
            "/api/v1/itsm/attachments/itsm-attachment.wiring-test-denied",
            headers={"X-CSRF-Token": csrf},
        )
        link_denied = client.post(
            "/api/v1/itsm/evidence-packages/itsm-evidence-package.wiring-test-denied/"
            "download-links",
            json={
                "attachment_id": "itsm-attachment.wiring-test-denied",
                "ttl_seconds": 300,
            },
            headers={"X-CSRF-Token": csrf},
        )
    for response in (upload_denied, read_denied, delete_denied, link_denied):
        assert response.status_code == 403, response.text
        assert response.json()["code"] == "authorization_denied"


def test_itsm_attachment_full_lifecycle_is_reachable_through_the_api() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        uploaded = client.post(
            "/api/v1/itsm/attachments",
            json={
                "external_ticket_id": "INC0010001",
                "filename": "notes.txt",
                "media_type": "text/plain",
                "classification": "classification.internal",
                "content_base64": "Y2xlYW4gZGlhZ25vc3RpYyBub3Rlcw==",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert uploaded.status_code == 201, uploaded.text
        attachment_id = uploaded.json()["data"]["attachment_id"]
        assert uploaded.json()["data"]["transferable"] is True
        assert uploaded.json()["data"]["malware_signature_scan_completed"] is False

        fetched = client.get(f"/api/v1/itsm/attachments/{attachment_id}")
        assert fetched.status_code == 200, fetched.text
        assert fetched.json()["data"]["content_digest"] == uploaded.json()["data"]["content_digest"]

        package = client.post(
            "/api/v1/itsm/evidence-packages",
            json={
                "external_ticket_id": "INC0010001",
                "attachment_ids": [attachment_id],
                "artifact_versions": ["report.itsm-attachment-wiring-test:v1"],
                "classification": "classification.internal",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert package.status_code == 201, package.text
        package_id = package.json()["data"]["package_id"]

        link = client.post(
            f"/api/v1/itsm/evidence-packages/{package_id}/download-links",
            json={"attachment_id": attachment_id, "ttl_seconds": 300},
            headers={"X-CSRF-Token": csrf},
        )
        assert link.status_code == 201, link.text
        link_id = link.json()["data"]["link_id"]

        downloaded = client.get(
            f"/api/v1/itsm/evidence-packages/{package_id}/download-links/{link_id}"
        )
        assert downloaded.status_code == 200, downloaded.text
        assert downloaded.json()["data"]["content_base64"] == "Y2xlYW4gZGlhZ25vc3RpYyBub3Rlcw=="

        replaced = client.post(
            f"/api/v1/itsm/attachments/{attachment_id}/replace",
            json={
                "filename": "notes-v2.txt",
                "media_type": "text/plain",
                "classification": "classification.internal",
                "content_base64": "cmVwbGFjZW1lbnQgY29udGVudA==",
            },
            headers={"X-CSRF-Token": csrf},
        )
        assert replaced.status_code == 200, replaced.text
        assert replaced.json()["data"]["filename"] == "notes-v2.txt"

        deleted = client.delete(
            f"/api/v1/itsm/attachments/{attachment_id}",
            headers={"X-CSRF-Token": csrf},
        )
        assert deleted.status_code == 204, deleted.text

        gone = client.get(f"/api/v1/itsm/attachments/{attachment_id}")
        assert gone.status_code == 404
        assert gone.json()["code"] == "itsm_attachment_not_found"


def test_itsm_attachment_upload_rejects_disallowed_media_type_through_the_api() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        response = client.post(
            "/api/v1/itsm/attachments",
            json={
                "external_ticket_id": "INC0010002",
                "filename": "bundle.zip",
                "media_type": "application/zip",
                "classification": "classification.internal",
                "content_base64": "Y2xlYW4=",
            },
            headers={"X-CSRF-Token": csrf},
        )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "itsm_attachment_media_type_not_allowlisted"


def test_itsm_attachment_upload_rejects_a_secret_pattern_through_the_api() -> None:
    matched_value = "Sup3r" + "SyntheticValue"
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        response = client.post(
            "/api/v1/itsm/attachments",
            json={
                "external_ticket_id": "INC0010003",
                "filename": "notes.txt",
                "media_type": "text/plain",
                "classification": "classification.internal",
                "content_base64": base64.b64encode(f"password = {matched_value}".encode()).decode(
                    "ascii"
                ),
            },
            headers={"X-CSRF-Token": csrf},
        )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "itsm_attachment_secret_pattern_detected"
    assert matched_value not in response.text


def test_itsm_attachment_download_link_rejects_after_expiry_through_the_api() -> None:
    with TestClient(create_app(_settings())) as client:
        csrf = _login(client)
        uploaded = client.post(
            "/api/v1/itsm/attachments",
            json={
                "external_ticket_id": "INC0010004",
                "filename": "notes.txt",
                "media_type": "text/plain",
                "classification": "classification.internal",
                "content_base64": "Y2xlYW4=",
            },
            headers={"X-CSRF-Token": csrf},
        )
        attachment_id = uploaded.json()["data"]["attachment_id"]
        package = client.post(
            "/api/v1/itsm/evidence-packages",
            json={
                "external_ticket_id": "INC0010004",
                "attachment_ids": [attachment_id],
                "artifact_versions": ["report.itsm-attachment-wiring-test:v1"],
                "classification": "classification.internal",
            },
            headers={"X-CSRF-Token": csrf},
        )
        package_id = package.json()["data"]["package_id"]

        response = client.get(
            f"/api/v1/itsm/evidence-packages/{package_id}/download-links/"
            "itsm-attachment-download-link.does-not-exist"
        )
    assert response.status_code == 404, response.text
    assert response.json()["code"] == "itsm_attachment_download_link_not_found"
