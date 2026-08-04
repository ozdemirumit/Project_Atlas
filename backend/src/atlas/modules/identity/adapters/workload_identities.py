from __future__ import annotations

import asyncio

from atlas.modules.identity.domain.workload_identities import (
    WorkloadCredentialRecord,
    WorkloadIdentityRecord,
)


class InMemoryWorkloadIdentityRepository:
    def __init__(self) -> None:
        self._identities: dict[str, WorkloadIdentityRecord] = {}
        self._credentials: dict[str, WorkloadCredentialRecord] = {}
        self._lock = asyncio.Lock()

    async def get_identity(self, identity_id: str) -> WorkloadIdentityRecord | None:
        return self._identities.get(identity_id)

    async def get_credential(self, credential_id: str) -> WorkloadCredentialRecord | None:
        return self._credentials.get(credential_id)

    async def all_identities(self) -> tuple[WorkloadIdentityRecord, ...]:
        return tuple(self._identities.values())

    async def all_credentials(self) -> tuple[WorkloadCredentialRecord, ...]:
        return tuple(self._credentials.values())

    async def add_identity(self, record: WorkloadIdentityRecord) -> bool:
        async with self._lock:
            if record.identity_id in self._identities:
                return False
            self._identities[record.identity_id] = record
            return True

    async def update_identity(
        self, record: WorkloadIdentityRecord, *, expected_version: int
    ) -> bool:
        async with self._lock:
            current = self._identities.get(record.identity_id)
            if current is None or current.version != expected_version:
                return False
            self._identities[record.identity_id] = record
            return True

    async def delete_identity(self, identity_id: str, *, expected_version: int) -> bool:
        async with self._lock:
            current = self._identities.get(identity_id)
            if current is None or current.version != expected_version:
                return False
            del self._identities[identity_id]
            return True

    async def add_credential(self, record: WorkloadCredentialRecord) -> bool:
        async with self._lock:
            if record.credential_id in self._credentials:
                return False
            self._credentials[record.credential_id] = record
            return True

    async def update_credential(
        self, record: WorkloadCredentialRecord, *, expected_version: int
    ) -> bool:
        async with self._lock:
            current = self._credentials.get(record.credential_id)
            if current is None or current.version != expected_version:
                return False
            self._credentials[record.credential_id] = record
            return True

    async def delete_credential(self, credential_id: str, *, expected_version: int) -> bool:
        async with self._lock:
            current = self._credentials.get(credential_id)
            if current is None or current.version != expected_version:
                return False
            del self._credentials[credential_id]
            return True
