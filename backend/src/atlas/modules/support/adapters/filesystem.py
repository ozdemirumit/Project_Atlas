from __future__ import annotations

import os
from hashlib import sha256
from pathlib import Path

from atlas.modules.support.application.ports import SupportBundleError


class FilesystemSupportBundlePublisher:
    def __init__(self, *, root: Path, max_archive_bytes: int) -> None:
        self._root = root.resolve()
        self._max_archive_bytes = max_archive_bytes

    async def inspect(self, *, target_id: str, expected: bytes) -> str:
        self._validate_expected(expected)
        target = self._target(target_id)
        if not target.exists() and not target.is_symlink():
            return "empty"
        if target.is_symlink() or not target.is_file():
            raise SupportBundleError("support_bundle_target_unsafe")
        if target.read_bytes() != expected:
            raise SupportBundleError("support_bundle_target_conflict")
        return "reusable"

    async def publish(
        self, *, export_id: str, target_id: str, expected: bytes
    ) -> tuple[str, int, str, bool]:
        self._validate_expected(expected)
        self._mkdir(self._root)
        staging = self._root / ".staging"
        self._mkdir(staging)
        attempt = staging / f"{export_id}.tmp"
        target = self._target(target_id)
        if attempt.exists() or attempt.is_symlink():
            raise SupportBundleError("support_bundle_attempt_conflict")
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
                    raise SupportBundleError("support_bundle_target_conflict")
                reused = True
            else:
                attempt.replace(target)
            if attempt.exists():
                attempt.unlink()
            return sha256(expected).hexdigest(), len(expected), target.name, reused
        except SupportBundleError:
            self._cleanup(attempt)
            raise
        except OSError as error:
            self._cleanup(attempt)
            raise SupportBundleError("support_bundle_publish_failed") from error

    def _target(self, target_id: str) -> Path:
        if not target_id.startswith("target.support-bundle."):
            raise SupportBundleError("support_bundle_target_unsafe")
        return self._root / "exports" / f"{target_id}.zip"

    def _validate_expected(self, expected: bytes) -> None:
        if not expected or len(expected) > self._max_archive_bytes:
            raise SupportBundleError("support_bundle_archive_budget_exceeded")

    @staticmethod
    def _cleanup(path: Path) -> None:
        if path.exists() and not path.is_symlink() and path.is_file():
            path.unlink()

    @staticmethod
    def _mkdir(path: Path) -> None:
        for candidate in (path, *path.parents):
            if candidate.is_symlink():
                raise SupportBundleError("support_bundle_target_unsafe")
        path.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or not path.is_dir():
            raise SupportBundleError("support_bundle_target_unsafe")
