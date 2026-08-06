from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.package_approval import ConnectorPackageApprovalRecord
from atlas.modules.connectors.domain.publisher_attestation import (
    ConnectorPublisherAttestationPolicySnapshot,
    ConnectorPublisherAttestationReport,
    ConnectorPublisherClaimSnapshot,
)


class PublisherAttestationError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class PublisherAttestationApprovalSource(Protocol):
    async def publisher_attestation_source(
        self, *, request_id: str
    ) -> tuple[ConnectorPackageApprovalRecord, frozenset[str]]: ...


class PublisherClaimSource(Protocol):
    async def get_by_id(self, *, claim_id: str) -> ConnectorPublisherClaimSnapshot | None: ...


class PublisherAttestationPolicySource(Protocol):
    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorPublisherAttestationPolicySnapshot | None: ...


class PublisherAttestationRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get(self, *, report_id: str) -> ConnectorPublisherAttestationReport | None: ...

    async def get_by_approval(
        self, *, source_approval_request_id: str
    ) -> ConnectorPublisherAttestationReport | None: ...

    async def get_by_create_key(
        self, *, verified_by: str, idempotency_key: str
    ) -> ConnectorPublisherAttestationReport | None: ...

    async def add(self, report: ConnectorPublisherAttestationReport) -> bool: ...

    async def close(self) -> None: ...
