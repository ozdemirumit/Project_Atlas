from __future__ import annotations

from datetime import datetime
from typing import Protocol

from atlas.modules.identity.domain.identity_status import IdentityStatusRecord
from atlas.modules.identity.domain.models import AuthenticatedSubject


class IdentityStatusRepository(Protocol):
    async def observe(
        self, subject: AuthenticatedSubject, *, observed_at: datetime
    ) -> IdentityStatusRecord: ...

    async def get(self, subject_id: str) -> IdentityStatusRecord | None: ...

    async def update(self, record: IdentityStatusRecord, *, expected_version: int) -> bool: ...

    async def all_records(self) -> tuple[IdentityStatusRecord, ...]: ...
