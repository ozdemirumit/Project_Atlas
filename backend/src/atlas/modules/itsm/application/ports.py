from __future__ import annotations

from typing import Protocol

from atlas.modules.itsm.domain.models import ItsmIntegrationProfile, ItsmProfileLifecycle


class ItsmIntegrationProfileRepository(Protocol):
    durable: bool

    async def get(self, *, profile_id: str) -> ItsmIntegrationProfile | None: ...

    async def get_by_scope_key(
        self, *, organization_id: str, environment_id: str, profile_key: str
    ) -> ItsmIntegrationProfile | None: ...

    async def get_by_create_key(
        self, *, created_by: str, idempotency_key: str
    ) -> ItsmIntegrationProfile | None: ...

    async def get_by_retirement_key(
        self, *, retired_by: str, idempotency_key: str
    ) -> ItsmIntegrationProfile | None: ...

    async def list_scope(
        self,
        *,
        organization_id: str,
        environment_id: str,
        lifecycle: ItsmProfileLifecycle | None,
        limit: int,
    ) -> tuple[ItsmIntegrationProfile, ...]: ...

    async def add(self, profile: ItsmIntegrationProfile) -> bool: ...

    async def update(self, profile: ItsmIntegrationProfile, *, expected_version: int) -> bool: ...

    async def close(self) -> None: ...
