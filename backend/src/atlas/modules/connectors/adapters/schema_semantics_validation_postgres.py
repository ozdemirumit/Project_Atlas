from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorPackageSchemaSemanticsValidationModel
from atlas.modules.connectors.domain.schema_semantics_validation import (
    ConnectorPackageSchemaSemanticsValidation,
    SchemaPurpose,
    SchemaSemanticsCheck,
    SchemaSemanticsCheckState,
    SchemaSemanticsFinding,
    SchemaSemanticsFindingKind,
    SchemaSemanticsLifecycle,
    SchemaSemanticsOutcome,
    SchemaSemanticsSeverity,
    SchemaSemanticsSummary,
)


class PostgreSQLPackageSchemaSemanticsValidationRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLPackageSchemaSemanticsValidationRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get_by_id(
        self, *, validation_id: str
    ) -> ConnectorPackageSchemaSemanticsValidation | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorPackageSchemaSemanticsValidationModel, validation_id)
            return self._to_domain(row) if row is not None else None

    async def get_by_source_scan(
        self, *, source_content_policy_scan_id: str
    ) -> ConnectorPackageSchemaSemanticsValidation | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageSchemaSemanticsValidationModel).where(
                    ConnectorPackageSchemaSemanticsValidationModel.source_content_policy_scan_id
                    == source_content_policy_scan_id
                )
            )
            return self._to_domain(row) if row is not None else None

    async def get_by_create_key(
        self, *, validated_by: str, idempotency_key: str
    ) -> ConnectorPackageSchemaSemanticsValidation | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageSchemaSemanticsValidationModel).where(
                    ConnectorPackageSchemaSemanticsValidationModel.validated_by == validated_by,
                    ConnectorPackageSchemaSemanticsValidationModel.idempotency_key
                    == idempotency_key,
                )
            )
            return self._to_domain(row) if row is not None else None

    async def add(self, validation: ConnectorPackageSchemaSemanticsValidation) -> bool:
        try:
            async with self._sessions.begin() as session:
                session.add(
                    ConnectorPackageSchemaSemanticsValidationModel(**self._values(validation))
                )
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _values(validation: ConnectorPackageSchemaSemanticsValidation) -> dict[str, object]:
        excluded = {"lifecycle", "outcome", "schemas", "findings", "checks", "limitations"}
        scalar_fields = (
            column.name
            for column in ConnectorPackageSchemaSemanticsValidationModel.__table__.columns
            if column.name not in excluded
        )
        return {
            **{field: getattr(validation, field) for field in scalar_fields},
            "lifecycle": validation.lifecycle.value,
            "outcome": validation.outcome.value,
            "schemas": PackageSchemaSemanticsValidationServicePayload.schemas(validation.schemas),
            "findings": PackageSchemaSemanticsValidationServicePayload.findings(
                validation.findings
            ),
            "checks": PackageSchemaSemanticsValidationServicePayload.checks(validation.checks),
            "limitations": list(validation.limitations),
        }

    @staticmethod
    def _to_domain(
        row: ConnectorPackageSchemaSemanticsValidationModel,
    ) -> ConnectorPackageSchemaSemanticsValidation:
        excluded = {"lifecycle", "outcome", "schemas", "findings", "checks", "limitations"}
        values = {
            column.name: getattr(row, column.name)
            for column in ConnectorPackageSchemaSemanticsValidationModel.__table__.columns
            if column.name not in excluded
        }
        return ConnectorPackageSchemaSemanticsValidation(
            **values,
            lifecycle=SchemaSemanticsLifecycle(row.lifecycle),
            outcome=SchemaSemanticsOutcome(row.outcome),
            schemas=tuple(
                SchemaSemanticsSummary(
                    relative_path=item["relative_path"],
                    digest=item["digest"],
                    purpose=SchemaPurpose(item["purpose"]),
                    capability_id=item["capability_id"],
                    property_count=item["property_count"],
                    required_count=item["required_count"],
                    closed_object=item["closed_object"],
                    semantically_complete=item["semantically_complete"],
                )
                for item in row.schemas
            ),
            findings=tuple(
                SchemaSemanticsFinding(
                    rule_code=item["rule_code"],
                    kind=SchemaSemanticsFindingKind(item["kind"]),
                    severity=SchemaSemanticsSeverity(item["severity"]),
                    relative_path=item["relative_path"],
                    json_pointer=item["json_pointer"],
                    evidence_fingerprint=item["evidence_fingerprint"],
                    summary=item["summary"],
                    remediation=item["remediation"],
                )
                for item in row.findings
            ),
            checks=tuple(
                SchemaSemanticsCheck(
                    code=item["code"],
                    state=SchemaSemanticsCheckState(item["state"]),
                    severity=SchemaSemanticsSeverity(item["severity"]),
                    summary=item["summary"],
                    evidence_paths=tuple(item["evidence_paths"]),
                    remediation=item["remediation"],
                )
                for item in row.checks
            ),
            limitations=tuple(row.limitations),
        )


class PackageSchemaSemanticsValidationServicePayload:
    @staticmethod
    def schemas(items: tuple[SchemaSemanticsSummary, ...]) -> list[dict[str, object]]:
        return [
            {
                "relative_path": item.relative_path,
                "digest": item.digest,
                "purpose": item.purpose.value,
                "capability_id": item.capability_id,
                "property_count": item.property_count,
                "required_count": item.required_count,
                "closed_object": item.closed_object,
                "semantically_complete": item.semantically_complete,
            }
            for item in items
        ]

    @staticmethod
    def findings(items: tuple[SchemaSemanticsFinding, ...]) -> list[dict[str, object]]:
        return [
            {
                "rule_code": item.rule_code,
                "kind": item.kind.value,
                "severity": item.severity.value,
                "relative_path": item.relative_path,
                "json_pointer": item.json_pointer,
                "evidence_fingerprint": item.evidence_fingerprint,
                "summary": item.summary,
                "remediation": item.remediation,
            }
            for item in items
        ]

    @staticmethod
    def checks(items: tuple[SchemaSemanticsCheck, ...]) -> list[dict[str, object]]:
        return [
            {
                "code": item.code,
                "state": item.state.value,
                "severity": item.severity.value,
                "summary": item.summary,
                "evidence_paths": list(item.evidence_paths),
                "remediation": item.remediation,
            }
            for item in items
        ]
