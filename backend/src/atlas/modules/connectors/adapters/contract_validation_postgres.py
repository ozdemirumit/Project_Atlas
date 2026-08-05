from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorPackageContractValidationModel
from atlas.modules.connectors.application.contract_validation import (
    PackageContractValidationService,
)
from atlas.modules.connectors.domain.contract_validation import (
    ConnectorPackageContractValidation,
    ContractArtifactScope,
    ContractCheck,
    ContractCheckSeverity,
    ContractCheckState,
    ContractCoverageSummary,
    ContractFinding,
    ContractLifecycle,
    ContractOutcome,
    ContractSeverity,
)


class PostgreSQLPackageContractValidationRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLPackageContractValidationRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get_by_id(self, *, validation_id: str) -> ConnectorPackageContractValidation | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorPackageContractValidationModel, validation_id)
            return self._to_domain(row.payload) if row is not None else None

    async def get_by_source_analysis(
        self, *, source_license_analysis_id: str
    ) -> ConnectorPackageContractValidation | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageContractValidationModel).where(
                    ConnectorPackageContractValidationModel.source_license_analysis_id
                    == source_license_analysis_id
                )
            )
            return self._to_domain(row.payload) if row is not None else None

    async def get_by_create_key(
        self, *, validated_by: str, idempotency_key: str
    ) -> ConnectorPackageContractValidation | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageContractValidationModel).where(
                    ConnectorPackageContractValidationModel.validated_by == validated_by,
                    ConnectorPackageContractValidationModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row.payload) if row is not None else None

    async def add(self, validation: ConnectorPackageContractValidation) -> bool:
        payload = PackageContractValidationService._normalize(
            PackageContractValidationService._canonical_payload_with_internal_fields(validation)
        )
        assert isinstance(payload, dict)
        try:
            async with self._sessions.begin() as session:
                session.add(
                    ConnectorPackageContractValidationModel(
                        validation_id=validation.validation_id,
                        source_license_analysis_id=validation.source_license_analysis_id,
                        validated_by=validation.validated_by,
                        idempotency_key=validation.idempotency_key,
                        organization_id=validation.organization_id,
                        environment_id=validation.environment_id,
                        canonical_digest=validation.canonical_digest,
                        payload=payload,
                    )
                )
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _to_domain(raw: dict[str, object]) -> ConnectorPackageContractValidation:
        payload = dict(raw)
        payload["validated_at"] = datetime.fromisoformat(str(payload["validated_at"]))
        payload["lifecycle"] = ContractLifecycle(str(payload["lifecycle"]))
        payload["outcome"] = ContractOutcome(str(payload["outcome"]))
        coverage = payload.pop("coverage")
        findings = payload.pop("findings")
        checks = payload.pop("checks")
        limitations = payload.pop("limitations")
        assert isinstance(coverage, dict)
        assert isinstance(findings, list)
        assert isinstance(checks, list)
        assert isinstance(limitations, list)
        return ConnectorPackageContractValidation(
            **cast(Any, payload),
            coverage=ContractCoverageSummary(**coverage),
            findings=tuple(
                ContractFinding(
                    rule_id=str(item["rule_id"]),
                    category=str(item["category"]),
                    severity=ContractSeverity(str(item["severity"])),
                    artifact_scope=ContractArtifactScope(str(item["artifact_scope"])),
                    subject_fingerprint=str(item["subject_fingerprint"]),
                    summary=str(item["summary"]),
                    remediation=str(item["remediation"]),
                )
                for item in findings
                if isinstance(item, dict)
            ),
            checks=tuple(
                ContractCheck(
                    code=str(item["code"]),
                    state=ContractCheckState(str(item["state"])),
                    severity=ContractCheckSeverity(str(item["severity"])),
                    summary=str(item["summary"]),
                    remediation=str(item["remediation"]),
                )
                for item in checks
                if isinstance(item, dict)
            ),
            limitations=tuple(str(item) for item in limitations),
        )
