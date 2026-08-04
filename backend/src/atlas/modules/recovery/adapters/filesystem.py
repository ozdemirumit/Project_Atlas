from __future__ import annotations

import os
from hashlib import sha256
from pathlib import Path

from atlas.modules.recovery.application.ports import RecoveryError


class FilesystemBackupArchiveStore:
    def __init__(self, *, root: Path, max_archive_bytes: int) -> None:
        self._root = root.resolve()
        self._max_archive_bytes = max_archive_bytes

    async def inspect(self, *, target_id: str, expected: bytes) -> str:
        self._validate_expected(expected)
        target = self._target(target_id)
        if not target.exists() and not target.is_symlink():
            return "empty"
        if target.is_symlink() or not target.is_file():
            raise RecoveryError("backup_target_unsafe")
        if target.read_bytes() != expected:
            raise RecoveryError("backup_target_conflict")
        return "reusable"

    async def publish(
        self, *, backup_id: str, target_id: str, expected: bytes
    ) -> tuple[str, int, str, bool]:
        self._validate_expected(expected)
        self._mkdir(self._root)
        staging = self._root / ".staging"
        self._mkdir(staging)
        attempt = staging / f"{backup_id}.tmp"
        target = self._target(target_id)
        if attempt.exists() or attempt.is_symlink():
            raise RecoveryError("backup_attempt_conflict")
        try:
            with attempt.open("xb") as output:
                output.write(expected)
                output.flush()
                os.fsync(output.fileno())
            attempt.chmod(0o640)
            self._mkdir(target.parent)
            reused = False
            if target.exists() or target.is_symlink():
                if target.is_symlink() or not target.is_file() or target.read_bytes() != expected:
                    raise RecoveryError("backup_target_conflict")
                reused = True
            else:
                attempt.replace(target)
            if attempt.exists():
                attempt.unlink()
            return sha256(expected).hexdigest(), len(expected), target.name, reused
        except RecoveryError:
            self._cleanup(attempt)
            raise
        except OSError as error:
            self._cleanup(attempt)
            raise RecoveryError("backup_publish_failed") from error

    async def read(self, *, target_id: str, max_bytes: int) -> bytes:
        target = self._target(target_id)
        if target.is_symlink() or not target.is_file():
            raise RecoveryError("backup_archive_unavailable")
        if target.stat().st_size > min(max_bytes, self._max_archive_bytes):
            raise RecoveryError("backup_archive_budget_exceeded")
        try:
            content = target.read_bytes()
        except OSError as error:
            raise RecoveryError("backup_archive_unavailable") from error
        self._validate_expected(content)
        return content

    def _target(self, target_id: str) -> Path:
        if not target_id.startswith("target.logical-backup."):
            raise RecoveryError("backup_target_unsafe")
        return self._root / "archives" / f"{target_id}.zip"

    def _validate_expected(self, expected: bytes) -> None:
        if not expected or len(expected) > self._max_archive_bytes:
            raise RecoveryError("backup_archive_budget_exceeded")

    @staticmethod
    def _cleanup(path: Path) -> None:
        if path.exists() and not path.is_symlink() and path.is_file():
            path.unlink()

    @staticmethod
    def _mkdir(path: Path) -> None:
        for candidate in (path, *path.parents):
            if candidate.is_symlink():
                raise RecoveryError("backup_target_unsafe")
        path.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or not path.is_dir():
            raise RecoveryError("backup_target_unsafe")
