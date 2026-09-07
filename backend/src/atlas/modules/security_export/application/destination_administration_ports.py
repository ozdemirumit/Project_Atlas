from __future__ import annotations

from typing import Protocol

from atlas.modules.security_export.domain.destination_administration import (
    DestinationDisablement,
    DestinationValidationRecord,
    SyslogDestinationProfile,
)


class SyslogDestinationAdministrationRepository(Protocol):
    async def save_profile(self, profile: SyslogDestinationProfile) -> None: ...

    async def get_profile(self, destination_id: str) -> SyslogDestinationProfile | None: ...

    async def save_validation(self, record: DestinationValidationRecord) -> None: ...

    async def get_validation(self, destination_id: str) -> DestinationValidationRecord | None: ...

    async def save_disablement(self, disablement: DestinationDisablement) -> None: ...
