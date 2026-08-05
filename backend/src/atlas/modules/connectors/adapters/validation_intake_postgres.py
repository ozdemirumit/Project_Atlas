from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorPackageValidationModel
from atlas.modules.connectors.domain.validation_intake import (
    ConnectorPackageValidation,
    PackageValidationCheck,
    PackageValidationCheckState,
    PackageValidationLifecycle,
    PackageValidationOutcome,
    PackageValidationSeverity,
    ValidatedSchemaEvidence,
    ValidatedSchemaPurpose,
)


class PostgreSQLPackageValidationRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLPackageValidationRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get_by_id(self, *, validation_id: str) -> ConnectorPackageValidation | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorPackageValidationModel, validation_id)
            return self._to_domain(row) if row is not None else None

    async def get_by_acquisition(
        self, *, source_acquisition_id: str
    ) -> ConnectorPackageValidation | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageValidationModel).where(
                    ConnectorPackageValidationModel.source_acquisition_id == source_acquisition_id
                )
            )
            return self._to_domain(row) if row is not None else None

    async def get_by_create_key(
        self, *, validated_by: str, idempotency_key: str
    ) -> ConnectorPackageValidation | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageValidationModel).where(
                    ConnectorPackageValidationModel.validated_by == validated_by,
                    ConnectorPackageValidationModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row) if row is not None else None

    async def add(self, validation: ConnectorPackageValidation) -> bool:
        try:
            async with self._sessions.begin() as session:
                session.add(ConnectorPackageValidationModel(**self._values(validation)))
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _values(validation: ConnectorPackageValidation) -> dict[str, object]:
        scalar_fields = (
            "validation_id",
            "schema_version",
            "version",
            "source_acquisition_id",
            "source_acquisition_digest",
            "source_handoff_id",
            "source_handoff_digest",
            "source_project_id",
            "source_acquired_by",
            "source_custodied_by",
            "source_domain_reviewed_by",
            "source_security_reviewed_by",
            "source_lab_operated_by",
            "organization_id",
            "environment_id",
            "validated_by",
            "validation_profile",
            "validator_version",
            "package_digest",
            "package_size_bytes",
            "manifest_path",
            "manifest_digest",
            "canonical_digest",
            "request_fingerprint",
            "idempotency_key",
            "validated_at",
        )
        return {
            **{field: getattr(validation, field) for field in scalar_fields},
            "lifecycle": validation.lifecycle.value,
            "outcome": validation.outcome.value,
            "capability_ids": list(validation.capability_ids),
            "schema_evidence": [
                {
                    "relative_path": item.relative_path,
                    "digest": item.digest,
                    "schema_id": item.schema_id,
                    "purpose": item.purpose.value,
                    "capability_id": item.capability_id,
                }
                for item in validation.schema_evidence
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
                for item in validation.checks
            ],
            "limitations": list(validation.limitations),
        }

    @staticmethod
    def _to_domain(row: ConnectorPackageValidationModel) -> ConnectorPackageValidation:
        excluded = {
            "lifecycle",
            "outcome",
            "capability_ids",
            "schema_evidence",
            "checks",
            "limitations",
        }
        values = {
            column.name: getattr(row, column.name)
            for column in ConnectorPackageValidationModel.__table__.columns
            if column.name not in excluded
        }
        return ConnectorPackageValidation(
            **values,
            lifecycle=PackageValidationLifecycle(row.lifecycle),
            outcome=PackageValidationOutcome(row.outcome),
            capability_ids=tuple(row.capability_ids),
            schema_evidence=tuple(
                ValidatedSchemaEvidence(
                    relative_path=item["relative_path"],
                    digest=item["digest"],
                    schema_id=item["schema_id"],
                    purpose=ValidatedSchemaPurpose(item["purpose"]),
                    capability_id=item["capability_id"],
                )
                for item in row.schema_evidence
            ),
            checks=tuple(
                PackageValidationCheck(
                    code=item["code"],
                    state=PackageValidationCheckState(item["state"]),
                    severity=PackageValidationSeverity(item["severity"]),
                    summary=item["summary"],
                    evidence_paths=tuple(item["evidence_paths"]),
                    remediation=item["remediation"],
                )
                for item in row.checks
            ),
            limitations=tuple(row.limitations),
        )
