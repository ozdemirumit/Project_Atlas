from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from atlas.modules.platform.domain.bootstrap_artifact_acquisition import (
    ArtifactAcquisitionReceipt,
)
from atlas.modules.platform.domain.release_preflight import (
    AcquisitionMode,
    ManifestArtifact,
    ReleaseManifest,
)


class ArtifactContentSource(Protocol):
    async def inventory(self, mode: AcquisitionMode) -> tuple[str, ...]: ...

    def stream(self, mode: AcquisitionMode, artifact: ManifestArtifact) -> AsyncIterator[bytes]: ...


class ReleaseArtifactPublisher(Protocol):
    async def acquire(
        self,
        *,
        manifest: ReleaseManifest,
        manifest_digest: str,
        mode: AcquisitionMode,
        execution_id: str,
    ) -> ArtifactAcquisitionReceipt: ...

    async def cleanup_attempt(self, execution_id: str) -> None: ...


class ArtifactAcquisitionError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code
