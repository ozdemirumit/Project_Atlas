from __future__ import annotations

import asyncio
import os
import re
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from atlas.modules.mcp_builder.application.ports import McpBuilderArtifactError

_DIGEST = re.compile(r"^[a-f0-9]{64}$")


class FileSystemMcpBuilderCandidateArchivePublisher:
    def __init__(self, *, root: Path) -> None:
        self._root = root.absolute()
        self._lock = asyncio.Lock()

    async def publish(self, *, package_digest: str, content: bytes) -> bool:
        self._validate_digest(package_digest)
        if sha256(content).hexdigest() != package_digest or not content:
            raise McpBuilderArtifactError("builder_candidate_archive_integrity_failed")
        async with self._lock:
            return await asyncio.to_thread(self._publish, package_digest, content)

    async def read(self, *, package_digest: str, size_bytes: int) -> bytes:
        self._validate_digest(package_digest)
        return await asyncio.to_thread(self._read, package_digest, size_bytes)

    def _publish(self, package_digest: str, content: bytes) -> bool:
        self._mkdir_safe(self._root)
        destination = self._path(package_digest)
        self._mkdir_safe(destination.parent)
        if destination.exists() or destination.is_symlink():
            existing = self._read(package_digest, len(content))
            if existing == content:
                return False
            raise McpBuilderArtifactError("builder_candidate_archive_conflict")
        attempt = self._root / f".{package_digest}.{uuid4().hex}.tmp"
        try:
            with attempt.open("xb") as output:
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            attempt.chmod(0o600)
            if sha256(attempt.read_bytes()).hexdigest() != package_digest:
                raise McpBuilderArtifactError("builder_candidate_archive_integrity_failed")
            # A hard link publishes the verified inode atomically without replacing an
            # archive that another process may have published concurrently.
            os.link(attempt, destination, follow_symlinks=False)
        except FileExistsError:
            if destination.exists() and self._read(package_digest, len(content)) == content:
                return False
            raise McpBuilderArtifactError("builder_candidate_archive_conflict") from None
        except McpBuilderArtifactError:
            raise
        except OSError as error:
            raise McpBuilderArtifactError("builder_candidate_archive_publish_failed") from error
        finally:
            if attempt.exists() and not attempt.is_symlink():
                attempt.unlink()
        return True

    def _read(self, package_digest: str, size_bytes: int) -> bytes:
        path = self._path(package_digest)
        if path.is_symlink() or not path.is_file():
            raise McpBuilderArtifactError("builder_candidate_archive_not_found")
        try:
            content = path.read_bytes()
        except OSError as error:
            raise McpBuilderArtifactError("builder_candidate_archive_not_found") from error
        if (
            len(content) != size_bytes
            or len(content) > 25_000_000
            or sha256(content).hexdigest() != package_digest
        ):
            raise McpBuilderArtifactError("builder_candidate_archive_integrity_failed")
        return content

    def _path(self, package_digest: str) -> Path:
        return self._root / package_digest[:2] / f"{package_digest}.zip"

    @staticmethod
    def _mkdir_safe(path: Path) -> None:
        for candidate in (path, *path.parents):
            if candidate.is_symlink():
                raise McpBuilderArtifactError("builder_candidate_archive_path_unsafe")
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.is_symlink() or not path.is_dir():
            raise McpBuilderArtifactError("builder_candidate_archive_path_unsafe")

    @staticmethod
    def _validate_digest(package_digest: str) -> None:
        if _DIGEST.fullmatch(package_digest) is None:
            raise McpBuilderArtifactError("builder_candidate_archive_path_unsafe")
