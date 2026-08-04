from __future__ import annotations

import asyncio

from atlas.modules.identity.domain.api_credentials import (
    ApiCredentialRecord,
    ApiCredentialState,
)


class InMemoryApiCredentialRepository:
    def __init__(self) -> None:
        self._records: dict[str, ApiCredentialRecord] = {}
        self._digest_index: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def get_by_digest(self, token_digest: str) -> ApiCredentialRecord | None:
        credential_id = self._digest_index.get(token_digest)
        return self._records.get(credential_id) if credential_id is not None else None

    async def get_by_id(self, credential_id: str) -> ApiCredentialRecord | None:
        return self._records.get(credential_id)

    async def add(self, record: ApiCredentialRecord) -> None:
        async with self._lock:
            if record.credential_id in self._records or record.token_digest in self._digest_index:
                raise ValueError("API credential identifiers must be unique")
            self._records[record.credential_id] = record
            self._digest_index[record.token_digest] = record.credential_id

    async def update(self, record: ApiCredentialRecord, *, expected_version: int) -> bool:
        async with self._lock:
            current = self._records.get(record.credential_id)
            if current is None or current.version != expected_version:
                return False
            if current.token_digest != record.token_digest:
                raise ValueError("API credential digest is immutable")
            self._records[record.credential_id] = record
            return True

    async def for_subject(self, subject_id: str) -> tuple[ApiCredentialRecord, ...]:
        return tuple(
            record for record in self._records.values() if record.subject.subject_id == subject_id
        )

    async def active_for_subject(self, subject_id: str) -> tuple[ApiCredentialRecord, ...]:
        return tuple(
            record
            for record in self._records.values()
            if record.subject.subject_id == subject_id and record.state is ApiCredentialState.ACTIVE
        )
