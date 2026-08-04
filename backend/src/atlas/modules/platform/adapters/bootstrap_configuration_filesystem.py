from __future__ import annotations

import os
import shutil
from hashlib import sha256
from pathlib import Path

from atlas.modules.platform.application.bootstrap_configuration_ports import (
    ConfigurationRenderingError,
)
from atlas.modules.platform.domain.bootstrap_configuration_rendering import (
    ConfigurationFileDisposition,
    ConfigurationRenderingReceipt,
    RenderedConfigurationEvidence,
)

CONFIGURATION_FILE_ID = "configuration.effective"
CONFIGURATION_FILE_NAME = "effective-configuration.json"


class FilesystemEffectiveConfigurationPublisher:
    def __init__(self, *, root: Path, max_bytes: int) -> None:
        self._root = root.resolve()
        self._max_bytes = max_bytes

    async def cleanup_attempt(self, execution_id: str) -> None:
        self._cleanup_owned_attempt(self._attempt_root(execution_id))

    async def publish(
        self,
        *,
        execution_id: str,
        organization_id: str,
        environment_id: str,
        site_id: str,
        release_id: str,
        configuration_digest: str,
        content: bytes,
    ) -> ConfigurationRenderingReceipt:
        if not content or len(content) > self._max_bytes:
            raise ConfigurationRenderingError("bootstrap_configuration_size_invalid")
        attempt_root = self._attempt_root(execution_id)
        destination_root = self._configuration_root(
            organization_id=organization_id,
            environment_id=environment_id,
            site_id=site_id,
            release_id=release_id,
            configuration_digest=configuration_digest,
        )
        self._prepare_attempt(attempt_root)
        try:
            output = attempt_root / CONFIGURATION_FILE_NAME
            with output.open("xb") as target:
                target.write(content)
                target.flush()
                os.fsync(target.fileno())
            output.chmod(0o640)
            disposition = (
                ConfigurationFileDisposition.PUBLISHED
                if self._publish_attempt(attempt_root, destination_root, content)
                else ConfigurationFileDisposition.REUSED
            )
            return self._receipt(content, disposition)
        except ConfigurationRenderingError:
            self._cleanup_owned_attempt(attempt_root)
            raise
        except (OSError, ValueError) as error:
            self._cleanup_owned_attempt(attempt_root)
            raise ConfigurationRenderingError("bootstrap_configuration_publish_failed") from error

    def _prepare_attempt(self, attempt_root: Path) -> None:
        self._mkdir_without_symlink(self._root)
        self._mkdir_without_symlink(self._root / ".staging")
        if attempt_root.exists() or attempt_root.is_symlink():
            raise ConfigurationRenderingError("bootstrap_configuration_attempt_conflict")
        attempt_root.mkdir()

    def _publish_attempt(self, attempt_root: Path, destination_root: Path, content: bytes) -> bool:
        self._mkdir_without_symlink(destination_root.parent)
        if destination_root.exists() or destination_root.is_symlink():
            if self._verify_existing(destination_root, content):
                self._cleanup_owned_attempt(attempt_root)
                return False
            raise ConfigurationRenderingError("bootstrap_configuration_existing_conflict")
        try:
            attempt_root.rename(destination_root)
            return True
        except FileExistsError:
            if self._verify_existing(destination_root, content):
                self._cleanup_owned_attempt(attempt_root)
                return False
            raise ConfigurationRenderingError("bootstrap_configuration_existing_conflict") from None

    def _verify_existing(self, destination_root: Path, content: bytes) -> bool:
        if destination_root.is_symlink() or not destination_root.is_dir():
            raise ConfigurationRenderingError("bootstrap_configuration_existing_conflict")
        files = tuple(destination_root.rglob("*"))
        if any(item.is_symlink() for item in files):
            raise ConfigurationRenderingError("bootstrap_configuration_path_unsafe")
        regular_files = tuple(item for item in files if item.is_file())
        expected = destination_root / CONFIGURATION_FILE_NAME
        if regular_files != (expected,):
            raise ConfigurationRenderingError("bootstrap_configuration_existing_conflict")
        if expected.read_bytes() != content:
            raise ConfigurationRenderingError("bootstrap_configuration_existing_conflict")
        return True

    def _cleanup_owned_attempt(self, attempt_root: Path) -> None:
        staging_root = self._root / ".staging"
        try:
            attempt_root.relative_to(staging_root)
        except ValueError as error:
            raise ConfigurationRenderingError("bootstrap_configuration_path_unsafe") from error
        if attempt_root.is_symlink():
            raise ConfigurationRenderingError("bootstrap_configuration_path_unsafe")
        if attempt_root.exists():
            shutil.rmtree(attempt_root)

    @staticmethod
    def _mkdir_without_symlink(path: Path) -> None:
        for candidate in (path, *path.parents):
            if candidate.is_symlink():
                raise ConfigurationRenderingError("bootstrap_configuration_path_unsafe")
        path.mkdir(parents=True, exist_ok=True)
        if path.is_symlink() or not path.is_dir():
            raise ConfigurationRenderingError("bootstrap_configuration_path_unsafe")

    def _attempt_root(self, execution_id: str) -> Path:
        return self._root / ".staging" / execution_id

    def _configuration_root(
        self,
        *,
        organization_id: str,
        environment_id: str,
        site_id: str,
        release_id: str,
        configuration_digest: str,
    ) -> Path:
        return (
            self._root
            / "deployments"
            / organization_id
            / environment_id
            / site_id
            / release_id
            / "configurations"
            / configuration_digest
        )

    @staticmethod
    def _receipt(
        content: bytes, disposition: ConfigurationFileDisposition
    ) -> ConfigurationRenderingReceipt:
        return ConfigurationRenderingReceipt(
            evidence=(
                RenderedConfigurationEvidence(
                    file_id=CONFIGURATION_FILE_ID,
                    sha256=sha256(content).hexdigest(),
                    size_bytes=len(content),
                    disposition=disposition,
                ),
            )
        )
