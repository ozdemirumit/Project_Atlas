from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorPackageAuthorityBehaviorValidationModel
from atlas.modules.connectors.domain.authority_behavior_validation import (
    AuthorityBehaviorCheck,
    AuthorityBehaviorCheckState,
    AuthorityBehaviorFinding,
    AuthorityBehaviorLifecycle,
    AuthorityBehaviorOutcome,
    AuthorityBehaviorSeverity,
    BehaviorCategory,
    CapabilityBehaviorSummary,
    ConnectorPackageAuthorityBehaviorValidation,
)


class PostgreSQLPackageAuthorityBehaviorValidationRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLPackageAuthorityBehaviorValidationRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get_by_id(
        self, *, validation_id: str
    ) -> ConnectorPackageAuthorityBehaviorValidation | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorPackageAuthorityBehaviorValidationModel, validation_id)
            return self._to_domain(row) if row is not None else None

    async def get_by_source_validation(
        self, *, source_schema_semantics_validation_id: str
    ) -> ConnectorPackageAuthorityBehaviorValidation | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageAuthorityBehaviorValidationModel).where(
                    ConnectorPackageAuthorityBehaviorValidationModel.source_schema_semantics_validation_id
                    == source_schema_semantics_validation_id
                )
            )
            return self._to_domain(row) if row is not None else None

    async def get_by_create_key(
        self, *, validated_by: str, idempotency_key: str
    ) -> ConnectorPackageAuthorityBehaviorValidation | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageAuthorityBehaviorValidationModel).where(
                    ConnectorPackageAuthorityBehaviorValidationModel.validated_by == validated_by,
                    ConnectorPackageAuthorityBehaviorValidationModel.idempotency_key
                    == idempotency_key,
                )
            )
            return self._to_domain(row) if row is not None else None

    async def add(self, validation: ConnectorPackageAuthorityBehaviorValidation) -> bool:
        try:
            async with self._sessions.begin() as session:
                session.add(
                    ConnectorPackageAuthorityBehaviorValidationModel(**self._values(validation))
                )
        except IntegrityError:
            return False
        return True

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _values(validation: ConnectorPackageAuthorityBehaviorValidation) -> dict[str, object]:
        excluded = {"lifecycle", "outcome", "capabilities", "findings", "checks", "limitations"}
        scalar_fields = (
            column.name
            for column in ConnectorPackageAuthorityBehaviorValidationModel.__table__.columns
            if column.name not in excluded
        )
        return {
            **{field: getattr(validation, field) for field in scalar_fields},
            "lifecycle": validation.lifecycle.value,
            "outcome": validation.outcome.value,
            "capabilities": AuthorityBehaviorPayload.capabilities(validation.capabilities),
            "findings": AuthorityBehaviorPayload.findings(validation.findings),
            "checks": AuthorityBehaviorPayload.checks(validation.checks),
            "limitations": list(validation.limitations),
        }

    @staticmethod
    def _to_domain(
        row: ConnectorPackageAuthorityBehaviorValidationModel,
    ) -> ConnectorPackageAuthorityBehaviorValidation:
        excluded = {"lifecycle", "outcome", "capabilities", "findings", "checks", "limitations"}
        values = {
            column.name: getattr(row, column.name)
            for column in ConnectorPackageAuthorityBehaviorValidationModel.__table__.columns
            if column.name not in excluded
        }
        return ConnectorPackageAuthorityBehaviorValidation(
            **values,
            lifecycle=AuthorityBehaviorLifecycle(row.lifecycle),
            outcome=AuthorityBehaviorOutcome(row.outcome),
            capabilities=tuple(
                CapabilityBehaviorSummary(
                    capability_id=item["capability_id"],
                    declared_class=item["declared_class"],
                    required_permission=item["required_permission"],
                    module_path=item["module_path"],
                    source_digest=item["source_digest"],
                    observed_categories=tuple(
                        BehaviorCategory(value) for value in item["observed_categories"]
                    ),
                    network_call_count=item["network_call_count"],
                    mutation_call_count=item["mutation_call_count"],
                    declaration_matches=item["declaration_matches"],
                    permission_matches=item["permission_matches"],
                    behavior_compatible=item["behavior_compatible"],
                    statically_resolved=item["statically_resolved"],
                )
                for item in row.capabilities
            ),
            findings=tuple(
                AuthorityBehaviorFinding(
                    rule_code=item["rule_code"],
                    category=BehaviorCategory(item["category"]),
                    severity=AuthorityBehaviorSeverity(item["severity"]),
                    relative_path=item["relative_path"],
                    line_number=item["line_number"],
                    evidence_fingerprint=item["evidence_fingerprint"],
                    summary=item["summary"],
                    remediation=item["remediation"],
                )
                for item in row.findings
            ),
            checks=tuple(
                AuthorityBehaviorCheck(
                    code=item["code"],
                    state=AuthorityBehaviorCheckState(item["state"]),
                    severity=AuthorityBehaviorSeverity(item["severity"]),
                    summary=item["summary"],
                    evidence_paths=tuple(item["evidence_paths"]),
                    remediation=item["remediation"],
                )
                for item in row.checks
            ),
            limitations=tuple(row.limitations),
        )


class AuthorityBehaviorPayload:
    @staticmethod
    def capabilities(items: tuple[CapabilityBehaviorSummary, ...]) -> list[dict[str, object]]:
        return [
            {
                "capability_id": item.capability_id,
                "declared_class": item.declared_class,
                "required_permission": item.required_permission,
                "module_path": item.module_path,
                "source_digest": item.source_digest,
                "observed_categories": [value.value for value in item.observed_categories],
                "network_call_count": item.network_call_count,
                "mutation_call_count": item.mutation_call_count,
                "declaration_matches": item.declaration_matches,
                "permission_matches": item.permission_matches,
                "behavior_compatible": item.behavior_compatible,
                "statically_resolved": item.statically_resolved,
            }
            for item in items
        ]

    @staticmethod
    def findings(items: tuple[AuthorityBehaviorFinding, ...]) -> list[dict[str, object]]:
        return [
            {
                "rule_code": item.rule_code,
                "category": item.category.value,
                "severity": item.severity.value,
                "relative_path": item.relative_path,
                "line_number": item.line_number,
                "evidence_fingerprint": item.evidence_fingerprint,
                "summary": item.summary,
                "remediation": item.remediation,
            }
            for item in items
        ]

    @staticmethod
    def checks(items: tuple[AuthorityBehaviorCheck, ...]) -> list[dict[str, object]]:
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
