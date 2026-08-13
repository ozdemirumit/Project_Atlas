from __future__ import annotations

import asyncio

from atlas.modules.itsm.domain.models import ItsmIntegrationProfile, ItsmProfileLifecycle


class InMemoryItsmIntegrationProfileRepository:
    durable = False

    def __init__(self) -> None:
        self._profiles: dict[str, ItsmIntegrationProfile] = {}
        self._lock = asyncio.Lock()

    async def get(self, *, profile_id: str) -> ItsmIntegrationProfile | None:
        return self._profiles.get(profile_id)

    async def get_by_scope_key(
        self, *, organization_id: str, environment_id: str, profile_key: str
    ) -> ItsmIntegrationProfile | None:
        return next(
            (
                item
                for item in self._profiles.values()
                if item.organization_id == organization_id
                and item.environment_id == environment_id
                and item.profile_key == profile_key
            ),
            None,
        )

    async def get_by_create_key(
        self, *, created_by: str, idempotency_key: str
    ) -> ItsmIntegrationProfile | None:
        return next(
            (
                item
                for item in self._profiles.values()
                if item.created_by == created_by and item.create_idempotency_key == idempotency_key
            ),
            None,
        )

    async def get_by_retirement_key(
        self, *, retired_by: str, idempotency_key: str
    ) -> ItsmIntegrationProfile | None:
        return next(
            (
                item
                for item in self._profiles.values()
                if item.retired_by == retired_by
                and item.retirement_idempotency_key == idempotency_key
            ),
            None,
        )

    async def list_scope(
        self,
        *,
        organization_id: str,
        environment_id: str,
        lifecycle: ItsmProfileLifecycle | None,
        limit: int,
    ) -> tuple[ItsmIntegrationProfile, ...]:
        records = (
            item
            for item in self._profiles.values()
            if item.organization_id == organization_id
            and item.environment_id == environment_id
            and (lifecycle is None or item.lifecycle is lifecycle)
        )
        return tuple(sorted(records, key=lambda item: item.profile_key)[:limit])

    async def add(self, profile: ItsmIntegrationProfile) -> bool:
        async with self._lock:
            if profile.profile_id in self._profiles or any(
                item.organization_id == profile.organization_id
                and item.environment_id == profile.environment_id
                and (
                    item.profile_key == profile.profile_key
                    or (
                        item.created_by == profile.created_by
                        and item.create_idempotency_key == profile.create_idempotency_key
                    )
                )
                for item in self._profiles.values()
            ):
                return False
            self._profiles[profile.profile_id] = profile
            return True

    async def update(self, profile: ItsmIntegrationProfile, *, expected_version: int) -> bool:
        async with self._lock:
            current = self._profiles.get(profile.profile_id)
            if current is None or current.version != expected_version:
                return False
            self._profiles[profile.profile_id] = profile
            return True

    async def close(self) -> None:
        return None
