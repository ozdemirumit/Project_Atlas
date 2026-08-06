from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.package_installation import (
    ConnectorPackageInstallationPolicySnapshot,
    ConnectorPackageInstallationReceipt,
    ConnectorPackageInstallationResult,
)
from atlas.modules.connectors.domain.package_registration import (
    ConnectorPackageRegistrationRecord,
    ConnectorRegisteredManifestSnapshot,
)
from atlas.modules.connectors.domain.registry_publication import (
    ConnectorInternalRegistryPublicationReceipt,
    ConnectorInternalRegistryPublicationResult,
)
from atlas.modules.mcp_builder.domain.candidate_handoff import McpBuilderCandidateHandoff


class PackageInstallationError(RuntimeError):
    pass


class PackageInstallationRegistrationSource(Protocol):
    async def package_installation_source(
        self, *, record_id: str
    ) -> tuple[
        ConnectorPackageRegistrationRecord,
        ConnectorInternalRegistryPublicationReceipt,
        McpBuilderCandidateHandoff,
        frozenset[str],
    ]: ...


class PackageInstallationArtifactReader(Protocol):
    async def read(
        self,
        *,
        publication: ConnectorInternalRegistryPublicationResult,
        policy: ConnectorPackageInstallationPolicySnapshot,
    ) -> bytes: ...


class PackageInstallationManifestInspector(Protocol):
    def inspect(
        self, *, content: bytes, policy: ConnectorPackageInstallationPolicySnapshot
    ) -> ConnectorRegisteredManifestSnapshot: ...


class ConnectorPackageInstaller(Protocol):
    async def install(
        self,
        *,
        content: bytes,
        registration: ConnectorPackageRegistrationRecord,
        policy: ConnectorPackageInstallationPolicySnapshot,
        idempotency_key: str,
    ) -> ConnectorPackageInstallationResult: ...


class PackageInstallationPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorPackageInstallationPolicySnapshot | None: ...


class PackageInstallationRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get(self, *, receipt_id: str) -> ConnectorPackageInstallationReceipt | None: ...

    async def get_by_registration_record(
        self, *, source_registration_record_id: str
    ) -> ConnectorPackageInstallationReceipt | None: ...

    async def get_by_package_release(
        self, *, connector_id: str, release_version: str
    ) -> ConnectorPackageInstallationReceipt | None: ...

    async def get_by_create_key(
        self, *, installed_by: str, idempotency_key: str
    ) -> ConnectorPackageInstallationReceipt | None: ...

    async def add(self, receipt: ConnectorPackageInstallationReceipt) -> bool: ...

    async def close(self) -> None: ...
