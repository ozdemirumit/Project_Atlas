from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from atlas.core.persistence.models import ConnectorPackageFinalValidationModel
from atlas.modules.connectors.application.final_validation import PackageFinalValidationService
from atlas.modules.connectors.domain.final_validation import (
    ConnectorPackageFinalValidation,
    FinalRiskClassification,
    FinalRiskSummary,
    FinalStageEvidence,
    FinalValidationCheck,
    FinalValidationCheckState,
    FinalValidationOutcome,
    FinalValidationSeverity,
)


class PostgreSQLPackageFinalValidationRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._sessions = async_sessionmaker(engine, expire_on_commit=False)

    @classmethod
    def from_url(cls, database_url: str) -> PostgreSQLPackageFinalValidationRepository:
        return cls(create_async_engine(database_url, pool_pre_ping=True, pool_recycle=300))

    @property
    def durable(self) -> bool:
        return True

    async def get_by_id(self, *, validation_id: str) -> ConnectorPackageFinalValidation | None:
        async with self._sessions() as session:
            row = await session.get(ConnectorPackageFinalValidationModel, validation_id)
            return self._to_domain(row.payload) if row is not None else None

    async def get_by_source_self_test(
        self, *, source_lab_self_test_id: str
    ) -> ConnectorPackageFinalValidation | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageFinalValidationModel).where(
                    ConnectorPackageFinalValidationModel.source_lab_self_test_id
                    == source_lab_self_test_id
                )
            )
            return self._to_domain(row.payload) if row is not None else None

    async def get_by_create_key(
        self, *, validated_by: str, idempotency_key: str
    ) -> ConnectorPackageFinalValidation | None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(ConnectorPackageFinalValidationModel).where(
                    ConnectorPackageFinalValidationModel.validated_by == validated_by,
                    ConnectorPackageFinalValidationModel.idempotency_key == idempotency_key,
                )
            )
            return self._to_domain(row.payload) if row is not None else None

    async def add(self, validation: ConnectorPackageFinalValidation) -> bool:
        payload = PackageFinalValidationService._normalize(asdict(validation))
        assert isinstance(payload, dict)
        try:
            async with self._sessions.begin() as session:
                session.add(
                    ConnectorPackageFinalValidationModel(
                        validation_id=validation.validation_id,
                        source_lab_self_test_id=validation.source_lab_self_test_id,
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
    def _to_domain(raw: dict[str, object]) -> ConnectorPackageFinalValidation:
        payload = dict(raw)
        payload["validated_at"] = datetime.fromisoformat(str(payload["validated_at"]))
        payload["outcome"] = FinalValidationOutcome(str(payload["outcome"]))
        stage_rows = payload.pop("stage_evidence")
        risk_rows = payload.pop("risks")
        check_rows = payload.pop("checks")
        limitations = payload.pop("limitations")
        assert isinstance(stage_rows, list)
        assert isinstance(risk_rows, list)
        assert isinstance(check_rows, list)
        assert isinstance(limitations, list)
        return ConnectorPackageFinalValidation(
            **cast(Any, payload),
            stage_evidence=tuple(
                FinalStageEvidence(
                    stage_code=str(item["stage_code"]),
                    evidence_id=str(item["evidence_id"]),
                    evidence_digest=str(item["evidence_digest"]),
                    observed_at=datetime.fromisoformat(str(item["observed_at"])),
                    outcome=str(item["outcome"]),
                    promotion_blocked=bool(item["promotion_blocked"]),
                    finding_count=int(item["finding_count"]),
                    limitation_count=int(item["limitation_count"]),
                )
                for item in stage_rows
                if isinstance(item, dict)
            ),
            risks=tuple(
                FinalRiskSummary(
                    code=str(item["code"]),
                    source_stage=str(item["source_stage"]),
                    source_evidence_id=str(item["source_evidence_id"]),
                    source_evidence_digest=str(item["source_evidence_digest"]),
                    classification=FinalRiskClassification(str(item["classification"])),
                    severity=FinalValidationSeverity(str(item["severity"])),
                    blocking=bool(item["blocking"]),
                    occurrence_count=int(item["occurrence_count"]),
                    next_step=str(item["next_step"]),
                )
                for item in risk_rows
                if isinstance(item, dict)
            ),
            checks=tuple(
                FinalValidationCheck(
                    code=str(item["code"]),
                    state=FinalValidationCheckState(str(item["state"])),
                    severity=FinalValidationSeverity(str(item["severity"])),
                    summary=str(item["summary"]),
                    remediation=str(item["remediation"]),
                )
                for item in check_rows
                if isinstance(item, dict)
            ),
            limitations=tuple(str(item) for item in limitations),
        )
