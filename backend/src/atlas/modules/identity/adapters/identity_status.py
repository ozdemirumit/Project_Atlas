from __future__ import annotations

import asyncio
from datetime import datetime

from atlas.modules.identity.domain.identity_status import (
    IdentityLifecycleState,
    IdentityStatusRecord,
)
from atlas.modules.identity.domain.models import AuthenticatedSubject


class InMemoryIdentityStatusRepository:
    def __init__(self) -> None:
        self._records: dict[str, IdentityStatusRecord] = {}
        self._lock = asyncio.Lock()

    async def observe(
        self, subject: AuthenticatedSubject, *, observed_at: datetime
    ) -> IdentityStatusRecord:
        async with self._lock:
            existing = self._records.get(subject.subject_id)
            if existing is not None:
                if (
                    existing.subject.organization_id != subject.organization_id
                    or existing.subject.provider_id != subject.provider_id
                    or existing.subject.kind is not subject.kind
                ):
                    raise ValueError("identity status subject boundary changed")
                return existing
            record = IdentityStatusRecord(
                subject=subject,
                version=1,
                state=IdentityLifecycleState.ACTIVE,
                observed_at=observed_at,
            )
            self._records[subject.subject_id] = record
            return record

    async def get(self, subject_id: str) -> IdentityStatusRecord | None:
        async with self._lock:
            return self._records.get(subject_id)

    async def update(self, record: IdentityStatusRecord, *, expected_version: int) -> bool:
        async with self._lock:
            current = self._records.get(record.subject.subject_id)
            if current is None or current.version != expected_version:
                return False
            if (
                current.subject.organization_id != record.subject.organization_id
                or current.subject.provider_id != record.subject.provider_id
                or current.subject.kind is not record.subject.kind
            ):
                raise ValueError("identity status subject boundary is immutable")
            self._records[record.subject.subject_id] = record
            return True

    async def all_records(self) -> tuple[IdentityStatusRecord, ...]:
        async with self._lock:
            return tuple(self._records.values())
