from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.package_registration import (
    ConnectorPackageRegistrationPolicySnapshot,
    ConnectorPackageRegistrationRecord,
    ConnectorRegisteredManifestSnapshot,
)
from atlas.modules.connectors.domain.registry_publication import (
    ConnectorInternalRegistryPublicationReceipt,
    ConnectorInternalRegistryPublicationResult,
)
from atlas.modules.mcp_builder.domain.candidate_handoff import McpBuilderCandidateHandoff


class PackageRegistrationError(RuntimeError):
    pass


class PackageRegistrationPublicationSource(Protocol):
    async def package_registration_source(
        self, *, receipt_id: str
    ) -> tuple[
        ConnectorInternalRegistryPublicationReceipt,
        McpBuilderCandidateHandoff,
        frozenset[str],
    ]: ...


class InternalRegistryArtifactReader(Protocol):
    async def read(
        self,
        *,
        publication: ConnectorInternalRegistryPublicationResult,
        policy: ConnectorPackageRegistrationPolicySnapshot,
    ) -> bytes: ...


class ConnectorPackageManifestInspector(Protocol):
    def inspect(
        self, *, content: bytes, policy: ConnectorPackageRegistrationPolicySnapshot
    ) -> ConnectorRegisteredManifestSnapshot: ...


class PackageRegistrationPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorPackageRegistrationPolicySnapshot | None: ...


class PackageRegistrationRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get(self, *, record_id: str) -> ConnectorPackageRegistrationRecord | None: ...

    async def get_by_publication_receipt(
        self, *, source_publication_receipt_id: str
    ) -> ConnectorPackageRegistrationRecord | None: ...

    async def get_by_package_release(
        self, *, connector_id: str, release_version: str
    ) -> ConnectorPackageRegistrationRecord | None: ...

    async def get_by_create_key(
        self, *, registered_by: str, idempotency_key: str
    ) -> ConnectorPackageRegistrationRecord | None: ...

    async def add(self, record: ConnectorPackageRegistrationRecord) -> bool: ...

    async def close(self) -> None: ...
