from __future__ import annotations

from datetime import datetime
from typing import Protocol

from atlas.modules.connectors.domain.acquisition import ConnectorPackageAcquisition
from atlas.modules.connectors.domain.final_validation import ConnectorPackageFinalValidation
from atlas.modules.connectors.domain.package_approval import ConnectorPackageApprovalRecord
from atlas.modules.connectors.domain.package_signing import (
    ConnectorPackageSigningPolicySnapshot,
    ConnectorPackageSigningReceipt,
)
from atlas.modules.connectors.domain.registry_publication import (
    ConnectorInternalRegistryPublicationReceipt,
    ConnectorInternalRegistryPublicationResult,
    ConnectorPackageSignatureVerification,
    ConnectorRegistryPublicationPolicySnapshot,
)


class RegistryPublicationError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class RegistryPublicationSigningSource(Protocol):
    async def registry_publication_source(
        self, *, receipt_id: str
    ) -> tuple[
        ConnectorPackageSigningReceipt,
        ConnectorPackageSigningPolicySnapshot,
        frozenset[str],
    ]: ...


class RegistryPublicationApprovalSource(Protocol):
    async def publisher_attestation_source(
        self, *, request_id: str
    ) -> tuple[ConnectorPackageApprovalRecord, frozenset[str]]: ...


class RegistryPublicationFinalSource(Protocol):
    async def registry_publication_source(
        self, *, validation_id: str
    ) -> tuple[
        ConnectorPackageFinalValidation,
        ConnectorPackageAcquisition,
        bytes,
        frozenset[str],
    ]: ...


class RegistryPublicationPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorRegistryPublicationPolicySnapshot | None: ...


class PackageSignatureVerifier(Protocol):
    async def verify(
        self,
        *,
        receipt: ConnectorPackageSigningReceipt,
        signing_policy: ConnectorPackageSigningPolicySnapshot,
        publication_policy: ConnectorRegistryPublicationPolicySnapshot,
        verified_at: datetime,
    ) -> ConnectorPackageSignatureVerification: ...


class InternalRegistryPublisher(Protocol):
    async def publish(
        self,
        *,
        content: bytes,
        source_signing_receipt_digest: str,
        policy: ConnectorRegistryPublicationPolicySnapshot,
        published_at: datetime,
        idempotency_key: str,
    ) -> ConnectorInternalRegistryPublicationResult: ...


class RegistryPublicationRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get(
        self, *, receipt_id: str
    ) -> ConnectorInternalRegistryPublicationReceipt | None: ...

    async def get_by_signing_receipt(
        self, *, source_signing_receipt_id: str
    ) -> ConnectorInternalRegistryPublicationReceipt | None: ...

    async def get_by_create_key(
        self, *, requested_by: str, idempotency_key: str
    ) -> ConnectorInternalRegistryPublicationReceipt | None: ...

    async def add(self, receipt: ConnectorInternalRegistryPublicationReceipt) -> bool: ...

    async def close(self) -> None: ...
