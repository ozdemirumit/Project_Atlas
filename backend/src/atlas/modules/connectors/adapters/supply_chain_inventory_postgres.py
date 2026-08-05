from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorPackageSupplyChainInventoryModel
from atlas.modules.connectors.domain.supply_chain_inventory import (
    ConnectorPackageSupplyChainInventory,
    DependencyKind,
    InventoryCheckState,
    InventoryLifecycle,
    InventoryOutcome,
    InventorySeverity,
    PackageContentClass,
    PackageDependencyEvidence,
    PackageFileEvidence,
    PackageInventoryCheck,
)


class PostgreSQLPackageSupplyChainInventoryRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLPackageSupplyChainInventoryRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get_by_id(self, *, inventory_id: str) -> ConnectorPackageSupplyChainInventory | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorPackageSupplyChainInventoryModel, inventory_id)
            return self._to_domain(row) if row is not None else None

    async def get_by_validation(
        self, *, source_validation_id: str
    ) -> ConnectorPackageSupplyChainInventory | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageSupplyChainInventoryModel).where(
                    ConnectorPackageSupplyChainInventoryModel.source_validation_id
                    == source_validation_id
                )
            )
            return self._to_domain(row) if row is not None else None

    async def get_by_create_key(
        self, *, inventoried_by: str, idempotency_key: str
    ) -> ConnectorPackageSupplyChainInventory | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageSupplyChainInventoryModel).where(
                    ConnectorPackageSupplyChainInventoryModel.inventoried_by == inventoried_by,
                    ConnectorPackageSupplyChainInventoryModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row) if row is not None else None

    async def add(self, inventory: ConnectorPackageSupplyChainInventory) -> bool:
        try:
            async with self._sessions.begin() as session:
                session.add(ConnectorPackageSupplyChainInventoryModel(**self._values(inventory)))
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _values(inventory: ConnectorPackageSupplyChainInventory) -> dict[str, object]:
        excluded = {"lifecycle", "outcome", "files", "dependencies", "checks", "limitations"}
        scalar_fields = (
            column.name
            for column in ConnectorPackageSupplyChainInventoryModel.__table__.columns
            if column.name not in excluded
        )
        return {
            **{field: getattr(inventory, field) for field in scalar_fields},
            "lifecycle": inventory.lifecycle.value,
            "outcome": inventory.outcome.value,
            "files": [
                {
                    "relative_path": item.relative_path,
                    "digest": item.digest,
                    "size_bytes": item.size_bytes,
                    "content_class": item.content_class.value,
                }
                for item in inventory.files
            ],
            "dependencies": [
                {
                    "name": item.name,
                    "version_constraint": item.version_constraint,
                    "kind": item.kind.value,
                    "source_path": item.source_path,
                }
                for item in inventory.dependencies
            ],
            "checks": [
                {
                    "code": item.code,
                    "state": item.state.value,
                    "severity": item.severity.value,
                    "summary": item.summary,
                    "evidence_paths": list(item.evidence_paths),
                    "remediation": item.remediation,
                }
                for item in inventory.checks
            ],
            "limitations": list(inventory.limitations),
        }

    @staticmethod
    def _to_domain(
        row: ConnectorPackageSupplyChainInventoryModel,
    ) -> ConnectorPackageSupplyChainInventory:
        excluded = {"lifecycle", "outcome", "files", "dependencies", "checks", "limitations"}
        values = {
            column.name: getattr(row, column.name)
            for column in ConnectorPackageSupplyChainInventoryModel.__table__.columns
            if column.name not in excluded
        }
        return ConnectorPackageSupplyChainInventory(
            **values,
            lifecycle=InventoryLifecycle(row.lifecycle),
            outcome=InventoryOutcome(row.outcome),
            files=tuple(
                PackageFileEvidence(
                    relative_path=item["relative_path"],
                    digest=item["digest"],
                    size_bytes=item["size_bytes"],
                    content_class=PackageContentClass(item["content_class"]),
                )
                for item in row.files
            ),
            dependencies=tuple(
                PackageDependencyEvidence(
                    name=item["name"],
                    version_constraint=item["version_constraint"],
                    kind=DependencyKind(item["kind"]),
                    source_path=item["source_path"],
                )
                for item in row.dependencies
            ),
            checks=tuple(
                PackageInventoryCheck(
                    code=item["code"],
                    state=InventoryCheckState(item["state"]),
                    severity=InventorySeverity(item["severity"]),
                    summary=item["summary"],
                    evidence_paths=tuple(item["evidence_paths"]),
                    remediation=item["remediation"],
                )
                for item in row.checks
            ),
            limitations=tuple(row.limitations),
        )
