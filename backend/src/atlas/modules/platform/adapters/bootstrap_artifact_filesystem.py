from __future__ import annotations

import asyncio
import os
import shutil
from collections.abc import AsyncIterator
from hashlib import sha256
from pathlib import Path, PurePosixPath

from atlas.modules.platform.application.bootstrap_artifact_ports import (
    ArtifactAcquisitionError,
    ArtifactContentSource,
)
from atlas.modules.platform.domain.bootstrap_artifact_acquisition import (
    ArtifactAcquisitionReceipt,
    ArtifactDisposition,
    VerifiedArtifactEvidence,
)
from atlas.modules.platform.domain.release_preflight import (
    AcquisitionMode,
    ManifestArtifact,
    ReleaseManifest,
)


class FileSystemReleaseArtifactPublisher:
    def __init__(
        self,
        *,
        root: Path,
        source: ArtifactContentSource,
        max_total_bytes: int,
    ) -> None:
        if max_total_bytes < 1:
            raise ValueError("artifact acquisition byte limit must be positive")
        self._root = root.absolute()
        self._source = source
        self._max_total_bytes = max_total_bytes
        self._lock = asyncio.Lock()

    async def acquire(
        self,
        *,
        manifest: ReleaseManifest,
        manifest_digest: str,
        mode: AcquisitionMode,
        execution_id: str,
    ) -> ArtifactAcquisitionReceipt:
        if len(manifest.artifacts) > 128:
            raise ArtifactAcquisitionError("bootstrap_artifact_count_exceeded")
        expected_bytes = sum(item.size_bytes for item in manifest.artifacts)
        if expected_bytes > self._max_total_bytes:
            raise ArtifactAcquisitionError("bootstrap_artifact_size_exceeded")
        inventory = await self._source.inventory(mode)
        expected_paths = tuple(item.relative_path for item in manifest.artifacts)
        if len(inventory) != len(set(inventory)):
            raise ArtifactAcquisitionError("bootstrap_artifact_inventory_duplicate")
        if set(inventory) != set(expected_paths):
            raise ArtifactAcquisitionError("bootstrap_artifact_inventory_mismatch")

        async with self._lock:
            await asyncio.to_thread(self._ensure_root)
            release_root = self._release_root(manifest.release_id, manifest_digest)
            if await asyncio.to_thread(self._verify_existing_release, release_root, manifest):
                return self._receipt(manifest, ArtifactDisposition.REUSED)

            attempt_root = self._attempt_root(execution_id)
            await asyncio.to_thread(self._prepare_attempt, attempt_root)
            try:
                for artifact in manifest.artifacts:
                    await self._stage_artifact(attempt_root, mode, artifact)
                published = await asyncio.to_thread(
                    self._publish_attempt,
                    attempt_root,
                    release_root,
                    manifest,
                )
            except ArtifactAcquisitionError:
                await asyncio.to_thread(self._cleanup_owned_attempt, attempt_root)
                raise
            except Exception as error:
                await asyncio.to_thread(self._cleanup_owned_attempt, attempt_root)
                raise ArtifactAcquisitionError("bootstrap_artifact_source_unavailable") from error
            return self._receipt(
                manifest,
                ArtifactDisposition.PUBLISHED if published else ArtifactDisposition.REUSED,
            )

    async def cleanup_attempt(self, execution_id: str) -> None:
        await asyncio.to_thread(self._cleanup_owned_attempt, self._attempt_root(execution_id))

    async def _stage_artifact(
        self,
        attempt_root: Path,
        mode: AcquisitionMode,
        artifact: ManifestArtifact,
    ) -> None:
        destination = attempt_root.joinpath(*PurePosixPath(artifact.relative_path).parts)
        await asyncio.to_thread(self._prepare_destination, attempt_root, destination)
        digest = sha256()
        size = 0
        try:
            with destination.open("xb") as output:
                async for chunk in self._source.stream(mode, artifact):
                    if not isinstance(chunk, bytes) or not chunk:
                        raise ArtifactAcquisitionError("bootstrap_artifact_stream_invalid")
                    size += len(chunk)
                    if size > artifact.size_bytes or size > self._max_total_bytes:
                        raise ArtifactAcquisitionError("bootstrap_artifact_size_mismatch")
                    digest.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
        except ArtifactAcquisitionError:
            raise
        except Exception as error:
            raise ArtifactAcquisitionError("bootstrap_artifact_source_unavailable") from error
        if size != artifact.size_bytes:
            raise ArtifactAcquisitionError("bootstrap_artifact_size_mismatch")
        if digest.hexdigest() != artifact.sha256:
            raise ArtifactAcquisitionError("bootstrap_artifact_digest_mismatch")

    def _ensure_root(self) -> None:
        self._mkdir_without_symlink(self._root)
        self._mkdir_without_symlink(self._root / ".staging")
        self._mkdir_without_symlink(self._root / "releases")

    def _prepare_attempt(self, attempt_root: Path) -> None:
        if attempt_root.exists() or attempt_root.is_symlink():
            self._cleanup_owned_attempt(attempt_root)
        attempt_root.mkdir(mode=0o700)
        if attempt_root.is_symlink():
            raise ArtifactAcquisitionError("bootstrap_artifact_path_unsafe")

    def _prepare_destination(self, attempt_root: Path, destination: Path) -> None:
        try:
            destination.relative_to(attempt_root)
        except ValueError as error:
            raise ArtifactAcquisitionError("bootstrap_artifact_path_unsafe") from error
        current = attempt_root
        for part in destination.relative_to(attempt_root).parts[:-1]:
            current /= part
            self._mkdir_without_symlink(current)
        if destination.exists() or destination.is_symlink():
            raise ArtifactAcquisitionError("bootstrap_artifact_path_conflict")

    def _publish_attempt(
        self,
        attempt_root: Path,
        release_root: Path,
        manifest: ReleaseManifest,
    ) -> bool:
        self._mkdir_without_symlink(release_root.parent)
        if release_root.exists() or release_root.is_symlink():
            if self._verify_existing_release(release_root, manifest):
                self._cleanup_owned_attempt(attempt_root)
                return False
            raise ArtifactAcquisitionError("bootstrap_artifact_existing_conflict")
        try:
            attempt_root.rename(release_root)
            return True
        except FileExistsError:
            if self._verify_existing_release(release_root, manifest):
                self._cleanup_owned_attempt(attempt_root)
                return False
            raise ArtifactAcquisitionError("bootstrap_artifact_existing_conflict") from None

    def _verify_existing_release(self, release_root: Path, manifest: ReleaseManifest) -> bool:
        if not release_root.exists() and not release_root.is_symlink():
            return False
        if release_root.is_symlink() or not release_root.is_dir():
            raise ArtifactAcquisitionError("bootstrap_artifact_existing_conflict")
        expected = {item.relative_path: item for item in manifest.artifacts}
        observed: set[str] = set()
        for item in release_root.rglob("*"):
            if item.is_symlink():
                raise ArtifactAcquisitionError("bootstrap_artifact_path_unsafe")
            if not item.is_file():
                continue
            relative = item.relative_to(release_root).as_posix()
            observed.add(relative)
            artifact = expected.get(relative)
            if artifact is None or item.stat().st_size != artifact.size_bytes:
                raise ArtifactAcquisitionError("bootstrap_artifact_existing_conflict")
            digest = sha256()
            with item.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != artifact.sha256:
                raise ArtifactAcquisitionError("bootstrap_artifact_existing_conflict")
        if observed != set(expected):
            raise ArtifactAcquisitionError("bootstrap_artifact_existing_conflict")
        return True

    def _cleanup_owned_attempt(self, attempt_root: Path) -> None:
        staging_root = self._root / ".staging"
        try:
            attempt_root.relative_to(staging_root)
        except ValueError as error:
            raise ArtifactAcquisitionError("bootstrap_artifact_path_unsafe") from error
        if attempt_root.is_symlink():
            raise ArtifactAcquisitionError("bootstrap_artifact_path_unsafe")
        if attempt_root.exists():
            shutil.rmtree(attempt_root)

    @staticmethod
    def _mkdir_without_symlink(path: Path) -> None:
        for candidate in (path, *path.parents):
            if candidate.is_symlink():
                raise ArtifactAcquisitionError("bootstrap_artifact_path_unsafe")
        path.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or not path.is_dir():
            raise ArtifactAcquisitionError("bootstrap_artifact_path_unsafe")

    def _attempt_root(self, execution_id: str) -> Path:
        return self._root / ".staging" / execution_id

    def _release_root(self, release_id: str, manifest_digest: str) -> Path:
        return self._root / "releases" / release_id / manifest_digest

    @staticmethod
    def _receipt(
        manifest: ReleaseManifest, disposition: ArtifactDisposition
    ) -> ArtifactAcquisitionReceipt:
        return ArtifactAcquisitionReceipt(
            evidence=tuple(
                VerifiedArtifactEvidence(
                    artifact_id=item.artifact_id,
                    sha256=item.sha256,
                    size_bytes=item.size_bytes,
                    disposition=disposition,
                )
                for item in manifest.artifacts
            )
        )


class MemoryArtifactContentSource:
    def __init__(self, content: dict[str, bytes]) -> None:
        self._content = dict(content)

    async def inventory(self, mode: AcquisitionMode) -> tuple[str, ...]:
        del mode
        return tuple(self._content)

    async def stream(
        self, mode: AcquisitionMode, artifact: ManifestArtifact
    ) -> AsyncIterator[bytes]:
        del mode
        content = self._content.get(artifact.relative_path)
        if content is None:
            raise ArtifactAcquisitionError("bootstrap_artifact_source_missing")
        for offset in range(0, len(content), 1024 * 1024):
            yield content[offset : offset + 1024 * 1024]
