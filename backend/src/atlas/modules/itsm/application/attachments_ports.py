from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from atlas.core.classification import DataClassification
from atlas.modules.identity.domain.models import AuthenticatedSubject
from atlas.modules.itsm.domain.attachments import (
    ItsmAttachment,
    ItsmAttachmentDownloadLink,
    ItsmEvidencePackage,
)


@dataclass(frozen=True, slots=True)
class StoredItsmAttachmentDownloadLink:
    """`ItsmAttachmentDownloadLink` deliberately carries no `package_id` -- SS17 re-authorizes
    access to one attachment at a time at consumption, not to an evidence package as a bulk unit.
    This wrapper keeps the evidence-package scoping a link was issued under, and its
    organization/environment scope, as persistence bookkeeping -- the same way
    `StoredItsmDispatchAuthorization` keeps request bookkeeping out of its own minimal domain
    type (see `dispatch_authorization_ports.py`)."""

    link: ItsmAttachmentDownloadLink
    package_id: str
    organization_id: str
    environment_id: str


class ItsmAttachmentRepository(Protocol):
    durable: bool

    async def get_attachment(
        self, *, attachment_id: str, organization_id: str, environment_id: str
    ) -> ItsmAttachment | None: ...

    async def add_attachment(self, attachment: ItsmAttachment, *, content: bytes) -> bool: ...

    async def replace_attachment(
        self, *, expected: ItsmAttachment, replacement: ItsmAttachment, content: bytes
    ) -> bool: ...

    async def get_attachment_content(
        self, *, attachment_id: str, organization_id: str, environment_id: str
    ) -> bytes | None: ...

    async def delete_attachment(
        self, *, attachment_id: str, organization_id: str, environment_id: str
    ) -> bool: ...

    async def get_evidence_package(
        self, *, package_id: str, organization_id: str, environment_id: str
    ) -> ItsmEvidencePackage | None: ...

    async def add_evidence_package(self, package: ItsmEvidencePackage) -> bool: ...

    async def get_download_link(
        self, *, link_id: str
    ) -> StoredItsmAttachmentDownloadLink | None: ...

    async def add_download_link(self, record: StoredItsmAttachmentDownloadLink) -> bool: ...

    async def consume_download_link(
        self, *, link_id: str, consumed_at: datetime
    ) -> StoredItsmAttachmentDownloadLink | None: ...

    async def close(self) -> None: ...


class ItsmAttachmentPermissionAuthorizer(Protocol):
    """Matches `DocumentKnowledgePermissionAuthorizer`'s shape exactly (see
    `knowledge/application/document_knowledge_ports.py`): one reusable authorize() for every
    operation's own permission, plus a dedicated classification_ceiling() used only at the
    moment of download -- see `document_retrieval.py`'s `retrieve()` for the read-time-only
    precedent this mirrors.
    """

    async def authorize(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        permission_id: str,
        correlation_id: str,
    ) -> None: ...

    async def classification_ceiling(
        self,
        *,
        actor: AuthenticatedSubject,
        organization_id: str,
        environment_id: str,
        correlation_id: str,
    ) -> DataClassification: ...


__all__ = [
    "ItsmAttachmentPermissionAuthorizer",
    "ItsmAttachmentRepository",
    "StoredItsmAttachmentDownloadLink",
]
