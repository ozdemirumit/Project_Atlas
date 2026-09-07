from __future__ import annotations

from typing import Protocol

from atlas.modules.identity.domain.local_credentials import (
    LocalCredentialRecord,
    LocalRecoveryActivation,
)


class LocalCredentialRepository(Protocol):
    async def get(self, subject_id: str) -> LocalCredentialRecord | None: ...

    async def create(self, record: LocalCredentialRecord) -> bool:
        """Returns False if a record already exists for `record.subject_id`."""
        ...

    async def update(self, record: LocalCredentialRecord, *, expected_version: int) -> bool: ...

    async def get_recovery_activation(self, subject_id: str) -> LocalRecoveryActivation | None: ...

    async def save_recovery_activation(self, activation: LocalRecoveryActivation) -> None: ...
