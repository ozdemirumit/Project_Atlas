from __future__ import annotations

import asyncio

from atlas.modules.connectors.domain.publisher_attestation import (
    ConnectorPublisherAttestationPolicySnapshot,
    ConnectorPublisherAttestationReport,
    ConnectorPublisherClaimSnapshot,
)


class InMemoryPublisherAttestationRepository:
    def __init__(self) -> None:
        self._reports: dict[str, ConnectorPublisherAttestationReport] = {}
        self._approval_index: dict[str, str] = {}
        self._create_index: dict[tuple[str, str], str] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get(self, *, report_id: str) -> ConnectorPublisherAttestationReport | None:
        return self._reports.get(report_id)

    async def get_by_approval(
        self, *, source_approval_request_id: str
    ) -> ConnectorPublisherAttestationReport | None:
        report_id = self._approval_index.get(source_approval_request_id)
        return self._reports.get(report_id) if report_id else None

    async def get_by_create_key(
        self, *, verified_by: str, idempotency_key: str
    ) -> ConnectorPublisherAttestationReport | None:
        report_id = self._create_index.get((verified_by, idempotency_key))
        return self._reports.get(report_id) if report_id else None

    async def add(self, report: ConnectorPublisherAttestationReport) -> bool:
        async with self._lock:
            key = (report.verified_by, report.idempotency_key)
            if (
                report.report_id in self._reports
                or report.source_approval_request_id in self._approval_index
                or key in self._create_index
            ):
                return False
            self._reports[report.report_id] = report
            self._approval_index[report.source_approval_request_id] = report.report_id
            self._create_index[key] = report.report_id
            return True

    async def close(self) -> None:
        return None


class InMemoryPublisherClaimSource:
    def __init__(self, claims: tuple[ConnectorPublisherClaimSnapshot, ...] = ()) -> None:
        self._records = {item.claim_id: item for item in claims}

    async def get_by_id(self, *, claim_id: str) -> ConnectorPublisherClaimSnapshot | None:
        return self._records.get(claim_id)


class InMemoryPublisherAttestationPolicySource:
    def __init__(
        self, policies: tuple[ConnectorPublisherAttestationPolicySnapshot, ...] = ()
    ) -> None:
        self._records = {item.policy_id: item for item in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorPublisherAttestationPolicySnapshot | None:
        return self._records.get(policy_id)
