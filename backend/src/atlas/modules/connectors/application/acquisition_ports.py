from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.acquisition import ConnectorPackageAcquisition
from atlas.modules.mcp_builder.domain.candidate_handoff import McpBuilderCandidateHandoff


class PackageAcquisitionError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class PackageAcquisitionRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get_by_id(self, *, acquisition_id: str) -> ConnectorPackageAcquisition | None: ...

    async def get_by_handoff(
        self, *, source_handoff_id: str
    ) -> ConnectorPackageAcquisition | None: ...

    async def get_by_create_key(
        self, *, acquired_by: str, idempotency_key: str
    ) -> ConnectorPackageAcquisition | None: ...

    async def add(self, acquisition: ConnectorPackageAcquisition) -> bool: ...

    async def close(self) -> None: ...


class CandidateHandoffSource(Protocol):
    async def get_by_id(self, *, handoff_id: str) -> McpBuilderCandidateHandoff | None: ...


class CandidateArchiveSource(Protocol):
    async def read(self, *, package_digest: str, size_bytes: int) -> bytes: ...


class AcquiredPackagePublisher(Protocol):
    async def publish(self, *, package_digest: str, content: bytes) -> bool: ...

    async def read(self, *, package_digest: str, size_bytes: int) -> bytes: ...
