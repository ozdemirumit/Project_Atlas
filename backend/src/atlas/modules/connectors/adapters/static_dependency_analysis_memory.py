from __future__ import annotations

import asyncio

from atlas.modules.connectors.domain.static_dependency_analysis import (
    ConnectorPackageStaticDependencyAnalysis,
)


class InMemoryPackageStaticDependencyAnalysisRepository:
    durable = False

    def __init__(self) -> None:
        self._records: dict[str, ConnectorPackageStaticDependencyAnalysis] = {}
        self._lock = asyncio.Lock()

    async def get_by_id(
        self, *, analysis_id: str
    ) -> ConnectorPackageStaticDependencyAnalysis | None:
        return self._records.get(analysis_id)

    async def get_by_source_validation(
        self, *, source_authority_behavior_validation_id: str
    ) -> ConnectorPackageStaticDependencyAnalysis | None:
        return next(
            (
                item
                for item in self._records.values()
                if item.source_authority_behavior_validation_id
                == source_authority_behavior_validation_id
            ),
            None,
        )

    async def get_by_create_key(
        self, *, analyzed_by: str, idempotency_key: str
    ) -> ConnectorPackageStaticDependencyAnalysis | None:
        return next(
            (
                item
                for item in self._records.values()
                if item.analyzed_by == analyzed_by and item.idempotency_key == idempotency_key
            ),
            None,
        )

    async def add(self, analysis: ConnectorPackageStaticDependencyAnalysis) -> bool:
        async with self._lock:
            if analysis.analysis_id in self._records:
                return False
            if any(
                item.source_authority_behavior_validation_id
                == analysis.source_authority_behavior_validation_id
                or (
                    item.analyzed_by == analysis.analyzed_by
                    and item.idempotency_key == analysis.idempotency_key
                )
                for item in self._records.values()
            ):
                return False
            self._records[analysis.analysis_id] = analysis
            return True

    async def close(self) -> None:
        return None
