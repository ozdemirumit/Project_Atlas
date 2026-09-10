from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime

from atlas.modules.itsm.application.attachments_ports import StoredItsmAttachmentDownloadLink
from atlas.modules.itsm.domain.attachments import ItsmAttachment, ItsmEvidencePackage

_AttachmentKey = tuple[str, str, str]


class InMemoryItsmAttachmentRepository:
    durable = False

    def __init__(self) -> None:
        self._attachments: dict[_AttachmentKey, ItsmAttachment] = {}
        self._content: dict[_AttachmentKey, bytes] = {}
        self._packages: dict[_AttachmentKey, ItsmEvidencePackage] = {}
        self._links: dict[str, StoredItsmAttachmentDownloadLink] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _key(identifier: str, organization_id: str, environment_id: str) -> _AttachmentKey:
        return (identifier, organization_id, environment_id)

    async def get_attachment(
        self, *, attachment_id: str, organization_id: str, environment_id: str
    ) -> ItsmAttachment | None:
        return self._attachments.get(self._key(attachment_id, organization_id, environment_id))

    async def add_attachment(self, attachment: ItsmAttachment, *, content: bytes) -> bool:
        async with self._lock:
            key = self._key(
                attachment.attachment_id, attachment.organization_id, attachment.environment_id
            )
            if key in self._attachments:
                return False
            self._attachments[key] = attachment
            self._content[key] = content
            return True

    async def replace_attachment(
        self, *, expected: ItsmAttachment, replacement: ItsmAttachment, content: bytes
    ) -> bool:
        async with self._lock:
            key = self._key(
                expected.attachment_id, expected.organization_id, expected.environment_id
            )
            if self._attachments.get(key) != expected:
                return False
            self._attachments[key] = replacement
            self._content[key] = content
            return True

    async def get_attachment_content(
        self, *, attachment_id: str, organization_id: str, environment_id: str
    ) -> bytes | None:
        return self._content.get(self._key(attachment_id, organization_id, environment_id))

    async def delete_attachment(
        self, *, attachment_id: str, organization_id: str, environment_id: str
    ) -> bool:
        async with self._lock:
            key = self._key(attachment_id, organization_id, environment_id)
            if key not in self._attachments:
                return False
            del self._attachments[key]
            self._content.pop(key, None)
            return True

    async def get_evidence_package(
        self, *, package_id: str, organization_id: str, environment_id: str
    ) -> ItsmEvidencePackage | None:
        return self._packages.get(self._key(package_id, organization_id, environment_id))

    async def add_evidence_package(self, package: ItsmEvidencePackage) -> bool:
        async with self._lock:
            key = self._key(package.package_id, package.organization_id, package.environment_id)
            if key in self._packages:
                return False
            self._packages[key] = package
            return True

    async def get_download_link(self, *, link_id: str) -> StoredItsmAttachmentDownloadLink | None:
        return self._links.get(link_id)

    async def add_download_link(self, record: StoredItsmAttachmentDownloadLink) -> bool:
        async with self._lock:
            if record.link.link_id in self._links:
                return False
            self._links[record.link.link_id] = record
            return True

    async def consume_download_link(
        self, *, link_id: str, consumed_at: datetime
    ) -> StoredItsmAttachmentDownloadLink | None:
        async with self._lock:
            record = self._links.get(link_id)
            if record is None or record.link.consumed_at is not None:
                return None
            updated = replace(record, link=replace(record.link, consumed_at=consumed_at))
            self._links[link_id] = updated
            return updated

    async def close(self) -> None:
        return None
