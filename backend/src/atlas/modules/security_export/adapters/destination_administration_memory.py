from __future__ import annotations

import asyncio

from atlas.modules.security_export.domain.destination_administration import (
    DestinationDisablement,
    DestinationValidationRecord,
    SyslogDestinationProfile,
)


class InMemorySyslogDestinationAdministrationRepository:
    def __init__(self) -> None:
        self._profiles: dict[str, SyslogDestinationProfile] = {}
        self._validations: dict[str, DestinationValidationRecord] = {}
        self._disablements: list[DestinationDisablement] = []
        self._lock = asyncio.Lock()

    async def save_profile(self, profile: SyslogDestinationProfile) -> None:
        async with self._lock:
            self._profiles[profile.destination_id] = profile

    async def get_profile(self, destination_id: str) -> SyslogDestinationProfile | None:
        async with self._lock:
            return self._profiles.get(destination_id)

    async def save_validation(self, record: DestinationValidationRecord) -> None:
        async with self._lock:
            self._validations[record.destination_id] = record

    async def get_validation(self, destination_id: str) -> DestinationValidationRecord | None:
        async with self._lock:
            return self._validations.get(destination_id)

    async def save_disablement(self, disablement: DestinationDisablement) -> None:
        async with self._lock:
            self._disablements.append(disablement)
