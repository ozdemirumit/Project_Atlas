from __future__ import annotations

import asyncio

from atlas.modules.connectors.application.package_registration_ports import PackageRegistrationError
from atlas.modules.connectors.domain.package_registration import (
    ConnectorPackageRegistrationPolicySnapshot,
    ConnectorPackageRegistrationRecord,
)
from atlas.modules.connectors.domain.registry_publication import (
    ConnectorInternalRegistryPublicationResult,
)


class InMemoryPackageRegistrationRepository:
    def __init__(self) -> None:
        self._records: dict[str, ConnectorPackageRegistrationRecord] = {}
        self._lock = asyncio.Lock()

    @property
    def durable(self) -> bool:
        return False

    async def get(self, *, record_id: str) -> ConnectorPackageRegistrationRecord | None:
        return self._records.get(record_id)

    async def get_by_publication_receipt(
        self, *, source_publication_receipt_id: str
    ) -> ConnectorPackageRegistrationRecord | None:
        return next(
            (
                item
                for item in self._records.values()
                if item.source_publication_receipt_id == source_publication_receipt_id
            ),
            None,
        )

    async def get_by_package_release(
        self, *, connector_id: str, release_version: str
    ) -> ConnectorPackageRegistrationRecord | None:
        return next(
            (
                item
                for item in self._records.values()
                if item.connector_id == connector_id and item.release_version == release_version
            ),
            None,
        )

    async def get_by_create_key(
        self, *, registered_by: str, idempotency_key: str
    ) -> ConnectorPackageRegistrationRecord | None:
        return next(
            (
                item
                for item in self._records.values()
                if item.registered_by == registered_by and item.idempotency_key == idempotency_key
            ),
            None,
        )

    async def add(self, record: ConnectorPackageRegistrationRecord) -> bool:
        async with self._lock:
            if record.record_id in self._records:
                return False
            if any(
                item.source_publication_receipt_id == record.source_publication_receipt_id
                or (
                    item.connector_id == record.connector_id
                    and item.release_version == record.release_version
                )
                or (
                    item.registered_by == record.registered_by
                    and item.idempotency_key == record.idempotency_key
                )
                for item in self._records.values()
            ):
                return False
            self._records[record.record_id] = record
            return True

    async def close(self) -> None:
        return None


class InMemoryPackageRegistrationPolicySource:
    def __init__(self, policies: tuple[ConnectorPackageRegistrationPolicySnapshot, ...]) -> None:
        self._policies = {item.policy_id: item for item in policies}

    async def get_by_id(
        self, *, policy_id: str
    ) -> ConnectorPackageRegistrationPolicySnapshot | None:
        return self._policies.get(policy_id)


class UnavailableInternalRegistryArtifactReader:
    async def read(
        self,
        *,
        publication: ConnectorInternalRegistryPublicationResult,
        policy: ConnectorPackageRegistrationPolicySnapshot,
    ) -> bytes:
        del publication, policy
        raise PackageRegistrationError("package_registration_registry_reader_unavailable")
