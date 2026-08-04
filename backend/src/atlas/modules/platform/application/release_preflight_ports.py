from __future__ import annotations

from typing import Protocol

from atlas.modules.platform.domain.release_preflight import (
    AcquisitionMode,
    ArtifactObservation,
    HostSnapshot,
    ReleaseManifest,
)


class ReleaseSignatureVerifier(Protocol):
    def verify(self, payload: bytes, manifest: ReleaseManifest) -> bool: ...


class ReleaseArtifactInventory(Protocol):
    async def observations(self, mode: AcquisitionMode) -> tuple[ArtifactObservation, ...]: ...


class PreflightHostProbe(Protocol):
    async def snapshot(self) -> HostSnapshot: ...
