from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from atlas.api.schemas import ResponseMeta
from atlas.modules.platform.domain.release_preflight import ReleasePreflightReport


class PreflightCheckData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    category: str
    state: str
    mandatory: bool
    summary: str
    evidence: str
    remediation: str | None


class ReleasePreflightData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    report_id: str
    release_id: str
    release_version: str
    build_id: str
    manifest_digest: str
    mode: str
    profile: str
    state: str
    checks: list[PreflightCheckData]
    generated_at: datetime
    correlation_id: str
    mutation_authorized: bool
    execution_authorized: bool

    @classmethod
    def from_domain(cls, report: ReleasePreflightReport) -> ReleasePreflightData:
        return cls(
            report_id=report.report_id,
            release_id=report.release_id,
            release_version=report.release_version,
            build_id=report.build_id,
            manifest_digest=report.manifest_digest,
            mode=report.mode.value,
            profile=report.profile.value,
            state=report.state.value,
            checks=[
                PreflightCheckData(
                    code=item.code,
                    category=item.category,
                    state=item.state.value,
                    mandatory=item.mandatory,
                    summary=item.summary,
                    evidence=item.evidence,
                    remediation=item.remediation,
                )
                for item in report.checks
            ],
            generated_at=report.generated_at,
            correlation_id=report.correlation_id,
            mutation_authorized=report.mutation_authorized,
            execution_authorized=report.execution_authorized,
        )


class ReleasePreflightResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: ReleasePreflightData
    meta: ResponseMeta
