from __future__ import annotations

import asyncio
import os
import re
import shutil
from hashlib import sha256
from pathlib import Path, PurePosixPath
from uuid import uuid4

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.mcp_builder.application.generator import BuilderGeneratedContent
from atlas.modules.mcp_builder.application.ports import McpBuilderArtifactError
from atlas.modules.mcp_builder.domain.generation import (
    BuilderGeneratedFile,
    validate_generated_path,
)


class FileSystemMcpBuilderArtifactPublisher:
    def __init__(self, *, root: Path) -> None:
        self._root = root.absolute()
        self._lock = asyncio.Lock()

    async def publish(
        self,
        *,
        generation_id: str,
        artifact_digest: str,
        files: tuple[BuilderGeneratedContent, ...],
    ) -> bool:
        self._validate_identity(generation_id, artifact_digest)
        inventory = tuple(item.metadata for item in files)
        async with self._lock:
            await asyncio.to_thread(self._ensure_root)
            destination = self._generation_root(generation_id, artifact_digest)
            if await asyncio.to_thread(self._verify_existing, destination, inventory):
                return False
            attempt = self._root / ".staging" / f"{generation_id}-{uuid4().hex}"
            await asyncio.to_thread(self._prepare_attempt, attempt)
            try:
                for item in files:
                    await asyncio.to_thread(self._write_file, attempt, item)
                published = await asyncio.to_thread(
                    self._publish_attempt, attempt, destination, inventory
                )
            except McpBuilderArtifactError:
                await asyncio.to_thread(self._cleanup_attempt, attempt)
                raise
            except Exception as error:
                await asyncio.to_thread(self._cleanup_attempt, attempt)
                raise McpBuilderArtifactError(
                    "builder_generation_artifact_publish_failed"
                ) from error
            return published

    async def read(
        self,
        *,
        generation_id: str,
        artifact_digest: str,
        inventory: tuple[BuilderGeneratedFile, ...],
        relative_path: str,
    ) -> str:
        self._validate_identity(generation_id, artifact_digest)
        validate_generated_path(relative_path)
        destination = self._generation_root(generation_id, artifact_digest)
        await asyncio.to_thread(self._verify_required, destination, inventory)
        expected = next((item for item in inventory if item.relative_path == relative_path), None)
        if expected is None:
            raise McpBuilderArtifactError("builder_generation_file_not_found")
        path = destination.joinpath(*PurePosixPath(relative_path).parts)
        try:
            content = await asyncio.to_thread(path.read_text, encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise McpBuilderArtifactError("builder_generation_artifact_integrity_failed") from error
        encoded = content.encode("utf-8")
        if len(encoded) != expected.size_bytes or sha256(encoded).hexdigest() != expected.sha256:
            raise McpBuilderArtifactError("builder_generation_artifact_integrity_failed")
        return content

    def _ensure_root(self) -> None:
        self._mkdir_safe(self._root)
        self._mkdir_safe(self._root / ".staging")
        self._mkdir_safe(self._root / "generations")

    def _prepare_attempt(self, attempt: Path) -> None:
        if attempt.exists() or attempt.is_symlink():
            raise McpBuilderArtifactError("builder_generation_staging_conflict")
        attempt.mkdir(mode=0o700)
        if attempt.is_symlink():
            raise McpBuilderArtifactError("builder_generation_artifact_path_unsafe")

    def _write_file(self, attempt: Path, item: BuilderGeneratedContent) -> None:
        destination = attempt.joinpath(*PurePosixPath(item.relative_path).parts)
        try:
            destination.relative_to(attempt)
        except ValueError as error:
            raise McpBuilderArtifactError("builder_generation_artifact_path_unsafe") from error
        current = attempt
        for part in destination.relative_to(attempt).parts[:-1]:
            current /= part
            self._mkdir_safe(current)
        if destination.exists() or destination.is_symlink():
            raise McpBuilderArtifactError("builder_generation_artifact_path_conflict")
        encoded = item.content.encode("utf-8")
        try:
            with destination.open("xb") as output:
                output.write(encoded)
                output.flush()
                os.fsync(output.fileno())
            destination.chmod(0o600)
        except OSError as error:
            raise McpBuilderArtifactError("builder_generation_artifact_publish_failed") from error
        metadata = item.metadata
        if destination.stat().st_size != metadata.size_bytes:
            raise McpBuilderArtifactError("builder_generation_artifact_integrity_failed")

    def _publish_attempt(
        self,
        attempt: Path,
        destination: Path,
        inventory: tuple[BuilderGeneratedFile, ...],
    ) -> bool:
        self._mkdir_safe(destination.parent)
        if destination.exists() or destination.is_symlink():
            if self._verify_existing(destination, inventory):
                self._cleanup_attempt(attempt)
                return False
            raise McpBuilderArtifactError("builder_generation_artifact_conflict")
        try:
            attempt.rename(destination)
        except FileExistsError:
            if self._verify_existing(destination, inventory):
                self._cleanup_attempt(attempt)
                return False
            raise McpBuilderArtifactError("builder_generation_artifact_conflict") from None
        return True

    def _verify_required(
        self, destination: Path, inventory: tuple[BuilderGeneratedFile, ...]
    ) -> None:
        if not self._verify_existing(destination, inventory):
            raise McpBuilderArtifactError("builder_generation_artifact_not_found")

    def _verify_existing(
        self, destination: Path, inventory: tuple[BuilderGeneratedFile, ...]
    ) -> bool:
        if not destination.exists() and not destination.is_symlink():
            return False
        if destination.is_symlink() or not destination.is_dir():
            raise McpBuilderArtifactError("builder_generation_artifact_path_unsafe")
        expected = {item.relative_path: item for item in inventory}
        observed: set[str] = set()
        for path in destination.rglob("*"):
            if path.is_symlink():
                raise McpBuilderArtifactError("builder_generation_artifact_path_unsafe")
            if not path.is_file():
                continue
            relative = path.relative_to(destination).as_posix()
            observed.add(relative)
            item = expected.get(relative)
            if item is None or path.stat().st_size != item.size_bytes:
                raise McpBuilderArtifactError("builder_generation_artifact_integrity_failed")
            digest = sha256()
            try:
                with path.open("rb") as source:
                    for chunk in iter(lambda: source.read(65_536), b""):
                        digest.update(chunk)
            except OSError as error:
                raise McpBuilderArtifactError(
                    "builder_generation_artifact_integrity_failed"
                ) from error
            if digest.hexdigest() != item.sha256:
                raise McpBuilderArtifactError("builder_generation_artifact_integrity_failed")
        if observed != set(expected):
            raise McpBuilderArtifactError("builder_generation_artifact_integrity_failed")
        return True

    def _cleanup_attempt(self, attempt: Path) -> None:
        staging = self._root / ".staging"
        try:
            attempt.relative_to(staging)
        except ValueError as error:
            raise McpBuilderArtifactError("builder_generation_artifact_path_unsafe") from error
        if attempt.is_symlink():
            raise McpBuilderArtifactError("builder_generation_artifact_path_unsafe")
        if attempt.exists():
            shutil.rmtree(attempt)

    @staticmethod
    def _mkdir_safe(path: Path) -> None:
        for candidate in (path, *path.parents):
            if candidate.is_symlink():
                raise McpBuilderArtifactError("builder_generation_artifact_path_unsafe")
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.is_symlink() or not path.is_dir():
            raise McpBuilderArtifactError("builder_generation_artifact_path_unsafe")

    def _generation_root(self, generation_id: str, artifact_digest: str) -> Path:
        return self._root / "generations" / generation_id / artifact_digest

    @staticmethod
    def _validate_identity(generation_id: str, artifact_digest: str) -> None:
        try:
            validate_stable_identifier(generation_id, "generation id")
        except ValueError as error:
            raise McpBuilderArtifactError("builder_generation_artifact_path_unsafe") from error
        if re.fullmatch(r"[a-f0-9]{64}", artifact_digest) is None:
            raise McpBuilderArtifactError("builder_generation_artifact_path_unsafe")
