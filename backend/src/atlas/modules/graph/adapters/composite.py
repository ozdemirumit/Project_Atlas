from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from atlas.modules.graph.application.ports import GraphSnapshotProvider
from atlas.modules.graph.domain.models import FreshnessState, GraphSnapshot

_DATA_PROFILE = "composite_configured_read_only"


def _identity(*parts: str) -> str:
    normalized = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()[:20]


class CompositeGraphSnapshotProvider:
    """Merges the independent snapshots of multiple configured, single-vendor providers into one
    graph. Each underlying provider already self-checks whether its own vendor is actually
    configured and enabled, degrading to an empty, "unavailable" snapshot if not -- so this
    composite never needs to know which vendors, if any, are really configured. It just presents
    whatever real data each contributed, side by side, without fabricating any relationship
    between entities read from different connectors.
    """

    def __init__(
        self,
        *,
        providers: tuple[GraphSnapshotProvider, ...],
        organization_id: str,
        environment_id: str,
        site_id: str = "site.local",
    ) -> None:
        if not providers:
            raise ValueError("a composite graph snapshot provider requires at least one provider")
        self._providers = providers
        self._organization_id = organization_id
        self._environment_id = environment_id
        self._site_id = site_id

    async def get_snapshot(self) -> GraphSnapshot:
        snapshots = tuple([await provider.get_snapshot() for provider in self._providers])

        entities = tuple(entity for snapshot in snapshots for entity in snapshot.entities)
        relationships = tuple(
            relationship for snapshot in snapshots for relationship in snapshot.relationships
        )
        evidence = tuple(record for snapshot in snapshots for record in snapshot.evidence)
        known_gaps = tuple(
            dict.fromkeys(gap for snapshot in snapshots for gap in snapshot.known_gaps)
        )
        has_entities = bool(entities)
        generated_at = max(
            (snapshot.generated_at for snapshot in snapshots), default=datetime.now(UTC)
        )

        return GraphSnapshot(
            snapshot_id=(
                "snapshot.graph.composite."
                f"{_identity(*(snapshot.snapshot_id for snapshot in snapshots))}"
            ),
            schema_version="1.0",
            organization_id=self._organization_id,
            environment_id=self._environment_id,
            site_id=self._site_id,
            generated_at=generated_at,
            freshness=FreshnessState.FRESH if has_entities else FreshnessState.UNKNOWN,
            completeness="partial" if has_entities else "unavailable",
            entities=entities,
            relationships=relationships,
            observations=(),
            evidence=evidence,
            known_gaps=known_gaps,
            data_profile=_DATA_PROFILE,
        )
