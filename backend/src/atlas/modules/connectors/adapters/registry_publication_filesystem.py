from __future__ import annotations

import asyncio
import os
import re
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from atlas.modules.connectors.application.registry_publication_ports import (
    RegistryPublicationError,
)
from atlas.modules.connectors.domain.package_installation import (
    ConnectorPackageInstallationPolicySnapshot,
)
from atlas.modules.connectors.domain.package_registration import (
    ConnectorPackageRegistrationPolicySnapshot,
)
from atlas.modules.connectors.domain.registry_publication import (
    ConnectorInternalRegistryPublicationResult,
    ConnectorRegistryPublicationPolicySnapshot,
)

_DIGEST = re.compile(r"^[a-f0-9]{64}$")


class FileSystemNonProductionInternalRegistryPublisher:
    def __init__(
        self,
        *,
        root: Path,
        registry_profile_id: str,
        publisher_workload_id: str,
        reader_workload_id: str = "workload.connector-registry-reader",
    ) -> None:
        self._root = root.absolute()
        self._registry_profile_id = registry_profile_id
        self._publisher_workload_id = publisher_workload_id
        self._reader_workload_id = reader_workload_id
        self._lock = asyncio.Lock()

    async def publish(
        self,
        *,
        content: bytes,
        source_signing_receipt_digest: str,
        policy: ConnectorRegistryPublicationPolicySnapshot,
        published_at: datetime,
        idempotency_key: str,
    ) -> ConnectorInternalRegistryPublicationResult:
        del idempotency_key
        if (
            policy.registry_profile_id != self._registry_profile_id
            or policy.publisher_workload_id != self._publisher_workload_id
        ):
            raise RegistryPublicationError("registry_publication_publisher_profile_invalid")
        package_digest = sha256(content).hexdigest()
        if _DIGEST.fullmatch(package_digest) is None or not content:
            raise RegistryPublicationError("registry_publication_archive_integrity_failed")
        async with self._lock:
            reused = await asyncio.to_thread(self._publish, package_digest, content)
        artifact_reference = f"registry-artifact.sha256-{package_digest}"
        publication_digest = sha256(
            (
                f"{policy.registry_profile_id}:{artifact_reference}:{package_digest}:"
                f"{len(content)}:{source_signing_receipt_digest}"
            ).encode("ascii")
        ).hexdigest()
        return ConnectorInternalRegistryPublicationResult(
            registry_profile_id=policy.registry_profile_id,
            publisher_workload_id=policy.publisher_workload_id,
            artifact_reference_schema=policy.artifact_reference_schema,
            artifact_reference=artifact_reference,
            package_digest=package_digest,
            package_size_bytes=len(content),
            source_signing_receipt_digest=source_signing_receipt_digest,
            publication_digest=publication_digest,
            published_at=published_at,
            integrity_verified=True,
            reused=reused,
        )

    async def read(
        self,
        *,
        publication: ConnectorInternalRegistryPublicationResult,
        policy: (
            ConnectorPackageRegistrationPolicySnapshot | ConnectorPackageInstallationPolicySnapshot
        ),
    ) -> bytes:
        if (
            policy.required_registry_profile_id != self._registry_profile_id
            or policy.reader_workload_id != self._reader_workload_id
            or publication.registry_profile_id != self._registry_profile_id
            or publication.artifact_reference_schema != policy.required_artifact_reference_schema
        ):
            raise RegistryPublicationError("package_registration_registry_binding_invalid")
        path = self._root / publication.package_digest[:2] / f"{publication.package_digest}.zip"
        try:
            content = await asyncio.to_thread(self._read, path, publication.package_digest)
        except OSError as error:
            raise RegistryPublicationError(
                "package_registration_registry_artifact_unavailable"
            ) from error
        return content

    def _publish(self, package_digest: str, content: bytes) -> bool:
        self._mkdir_safe(self._root)
        destination = self._root / package_digest[:2] / f"{package_digest}.zip"
        self._mkdir_safe(destination.parent)
        if destination.exists() or destination.is_symlink():
            if self._read(destination, package_digest) == content:
                return True
            raise RegistryPublicationError("registry_publication_artifact_conflict")
        attempt = self._root / f".{package_digest}.{uuid4().hex}.tmp"
        try:
            with attempt.open("xb") as output:
                output.write(content)
                output.flush()
                os.fsync(output.fileno())
            attempt.chmod(0o600)
            if sha256(attempt.read_bytes()).hexdigest() != package_digest:
                raise RegistryPublicationError("registry_publication_archive_integrity_failed")
            os.link(attempt, destination, follow_symlinks=False)
        except FileExistsError:
            if destination.exists() and self._read(destination, package_digest) == content:
                return True
            raise RegistryPublicationError("registry_publication_artifact_conflict") from None
        except RegistryPublicationError:
            raise
        except OSError as error:
            raise RegistryPublicationError("registry_publication_publish_failed") from error
        finally:
            if attempt.exists() and not attempt.is_symlink():
                attempt.unlink()
        return False

    @staticmethod
    def _read(path: Path, package_digest: str) -> bytes:
        if path.is_symlink() or not path.is_file():
            raise RegistryPublicationError("registry_publication_artifact_conflict")
        content = path.read_bytes()
        if sha256(content).hexdigest() != package_digest:
            raise RegistryPublicationError("registry_publication_artifact_conflict")
        return content

    @staticmethod
    def _mkdir_safe(path: Path) -> None:
        for candidate in (path, *path.parents):
            if candidate.is_symlink():
                raise RegistryPublicationError("registry_publication_path_unsafe")
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        if path.is_symlink() or not path.is_dir():
            raise RegistryPublicationError("registry_publication_path_unsafe")
