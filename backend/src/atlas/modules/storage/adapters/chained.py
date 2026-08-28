from __future__ import annotations

from datetime import datetime

from atlas.modules.storage.application.ports import StorageOverviewProvider
from atlas.modules.storage.domain.models import StorageOverview


class ChainedStorageOverviewProvider:
    """Tries each configured, single-vendor provider in order and returns the first one that
    actually produced assets. Each underlying provider already self-checks whether its own vendor
    is really configured, degrading to an empty, "unavailable" overview if not -- so this chain
    never needs to know which vendor, if any, is configured. Unlike the graph snapshot's
    CompositeGraphSnapshotProvider, storage overviews are not merged across vendors: a
    StorageOverview carries one narrative investigation and report, and combining two vendors'
    narratives into one coherent story is editorial work this project has not designed, so only
    one vendor's real overview is ever shown at a time. If none produced assets, the last
    provider's unavailable overview (with its own honest reason) is returned as-is.
    """

    def __init__(self, *, providers: tuple[StorageOverviewProvider, ...]) -> None:
        if not providers:
            raise ValueError("a chained storage overview provider requires at least one provider")
        self._providers = providers

    async def get_overview(self, *, requested_at: datetime) -> StorageOverview:
        result: StorageOverview | None = None
        for provider in self._providers:
            result = await provider.get_overview(requested_at=requested_at)
            if result.assets:
                return result
        assert result is not None
        return result
