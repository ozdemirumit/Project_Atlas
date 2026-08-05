from __future__ import annotations

import asyncio
from hashlib import sha256

from atlas.modules.mcp_builder.application.ports import McpBuilderArtifactError


class InMemoryMcpBuilderCandidateArchivePublisher:
    def __init__(self) -> None:
        self._archives: dict[str, bytes] = {}
        self._lock = asyncio.Lock()

    async def publish(self, *, package_digest: str, content: bytes) -> bool:
        if sha256(content).hexdigest() != package_digest:
            raise McpBuilderArtifactError("builder_candidate_archive_integrity_failed")
        async with self._lock:
            existing = self._archives.get(package_digest)
            if existing is not None:
                if existing != content:
                    raise McpBuilderArtifactError("builder_candidate_archive_conflict")
                return False
            self._archives[package_digest] = content
            return True

    async def read(self, *, package_digest: str, size_bytes: int) -> bytes:
        content = self._archives.get(package_digest)
        if content is None:
            raise McpBuilderArtifactError("builder_candidate_archive_not_found")
        if len(content) != size_bytes or sha256(content).hexdigest() != package_digest:
            raise McpBuilderArtifactError("builder_candidate_archive_integrity_failed")
        return content
