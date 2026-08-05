from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorPackageAcquisitionModel
from atlas.modules.connectors.domain.acquisition import (
    AcquiredCapabilityEvidence,
    ConnectorPackageAcquisition,
    PackageAcquisitionSource,
    PackageAcquisitionState,
    PackageSignatureState,
    PublisherAttestationState,
)


class PostgreSQLPackageAcquisitionRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLPackageAcquisitionRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get_by_id(self, *, acquisition_id: str) -> ConnectorPackageAcquisition | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorPackageAcquisitionModel, acquisition_id)
            return self._to_domain(row) if row is not None else None

    async def get_by_handoff(self, *, source_handoff_id: str) -> ConnectorPackageAcquisition | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageAcquisitionModel).where(
                    ConnectorPackageAcquisitionModel.source_handoff_id == source_handoff_id
                )
            )
            return self._to_domain(row) if row is not None else None

    async def get_by_create_key(
        self, *, acquired_by: str, idempotency_key: str
    ) -> ConnectorPackageAcquisition | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageAcquisitionModel).where(
                    ConnectorPackageAcquisitionModel.acquired_by == acquired_by,
                    ConnectorPackageAcquisitionModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row) if row is not None else None

    async def add(self, acquisition: ConnectorPackageAcquisition) -> bool:
        values = self._values(acquisition)
        try:
            async with self._sessions.begin() as session:
                session.add(ConnectorPackageAcquisitionModel(**values))
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _values(acquisition: ConnectorPackageAcquisition) -> dict[str, object]:
        scalar_fields = (
            "acquisition_id",
            "schema_version",
            "version",
            "source_handoff_id",
            "source_handoff_digest",
            "source_project_id",
            "source_custodied_by",
            "source_domain_reviewed_by",
            "source_security_reviewed_by",
            "source_lab_operated_by",
            "organization_id",
            "environment_id",
            "acquired_by",
            "acquisition_profile",
            "archive_contract_version",
            "package_filename",
            "package_digest",
            "package_size_bytes",
            "publisher_identity",
            "canonical_digest",
            "request_fingerprint",
            "idempotency_key",
            "acquired_at",
        )
        return {
            **{field: getattr(acquisition, field) for field in scalar_fields},
            "state": acquisition.state.value,
            "source_type": acquisition.source_type.value,
            "signature_state": acquisition.signature_state.value,
            "attestation_state": acquisition.attestation_state.value,
            "capabilities": [
                {
                    "capability_id": item.capability_id,
                    "capability_class": item.capability_class,
                    "required_permission": item.required_permission,
                    "supported_product_versions": list(item.supported_product_versions),
                }
                for item in acquisition.capabilities
            ],
            "limitations": list(acquisition.limitations),
        }

    @staticmethod
    def _to_domain(row: ConnectorPackageAcquisitionModel) -> ConnectorPackageAcquisition:
        excluded = {
            "state",
            "source_type",
            "signature_state",
            "attestation_state",
            "capabilities",
            "limitations",
        }
        values = {
            column.name: getattr(row, column.name)
            for column in ConnectorPackageAcquisitionModel.__table__.columns
            if column.name not in excluded
        }
        return ConnectorPackageAcquisition(
            **values,
            state=PackageAcquisitionState(row.state),
            source_type=PackageAcquisitionSource(row.source_type),
            signature_state=PackageSignatureState(row.signature_state),
            attestation_state=PublisherAttestationState(row.attestation_state),
            capabilities=tuple(
                AcquiredCapabilityEvidence(
                    capability_id=item["capability_id"],
                    capability_class=item["capability_class"],
                    required_permission=item["required_permission"],
                    supported_product_versions=tuple(item["supported_product_versions"]),
                )
                for item in row.capabilities
            ),
            limitations=tuple(row.limitations),
        )
