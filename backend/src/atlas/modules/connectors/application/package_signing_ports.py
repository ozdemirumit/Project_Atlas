from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.package_signing import (
    ConnectorPackageSignatureResult,
    ConnectorPackageSigningEnvelope,
    ConnectorPackageSigningPolicySnapshot,
    ConnectorPackageSigningReceipt,
)
from atlas.modules.connectors.domain.publisher_attestation import (
    ConnectorPublisherAttestationReport,
)


class PackageSigningError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class PackageSigningAttestationSource(Protocol):
    async def package_signing_source(
        self, *, report_id: str
    ) -> tuple[ConnectorPublisherAttestationReport, frozenset[str]]: ...


class PackageSigningPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorPackageSigningPolicySnapshot | None: ...


class PackageSigner(Protocol):
    async def sign(
        self,
        *,
        envelope: ConnectorPackageSigningEnvelope,
        policy: ConnectorPackageSigningPolicySnapshot,
        idempotency_key: str,
    ) -> ConnectorPackageSignatureResult: ...


class PackageSigningRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get(self, *, receipt_id: str) -> ConnectorPackageSigningReceipt | None: ...

    async def get_by_attestation(
        self, *, source_attestation_report_id: str
    ) -> ConnectorPackageSigningReceipt | None: ...

    async def get_by_create_key(
        self, *, requested_by: str, idempotency_key: str
    ) -> ConnectorPackageSigningReceipt | None: ...

    async def add(self, receipt: ConnectorPackageSigningReceipt) -> bool: ...

    async def close(self) -> None: ...
