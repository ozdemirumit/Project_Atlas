from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.workload_identities import (
    WorkloadCredentialRecord,
    WorkloadIdentityRecord,
)


class WorkloadIdentityRepository(Protocol):
    async def get_identity(self, identity_id: str) -> WorkloadIdentityRecord | None: ...

    async def get_credential(self, credential_id: str) -> WorkloadCredentialRecord | None: ...

    async def all_identities(self) -> tuple[WorkloadIdentityRecord, ...]: ...

    async def all_credentials(self) -> tuple[WorkloadCredentialRecord, ...]: ...

    async def add_identity(self, record: WorkloadIdentityRecord) -> bool: ...

    async def update_identity(
        self, record: WorkloadIdentityRecord, *, expected_version: int
    ) -> bool: ...

    async def delete_identity(self, identity_id: str, *, expected_version: int) -> bool: ...

    async def add_credential(self, record: WorkloadCredentialRecord) -> bool: ...

    async def update_credential(
        self, record: WorkloadCredentialRecord, *, expected_version: int
    ) -> bool: ...

    async def delete_credential(self, credential_id: str, *, expected_version: int) -> bool: ...
