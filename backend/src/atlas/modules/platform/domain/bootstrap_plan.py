from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from atlas.modules.identity.domain.models import validate_stable_identifier
from atlas.modules.platform.domain.release_preflight import DeploymentProfile

DIGEST_PATTERN = re.compile(r"^[a-f0-9]{64}$")


class BootstrapPlanState(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"


class BootstrapPhaseState(StrEnum):
    READY = "ready"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class BootstrapPlanRequest:
    schema_version: str
    release_id: str
    profile: DeploymentProfile
    organization_id: str
    environment_id: str
    site_id: str
    preflight_report_id: str
    manifest_digest: str
    preflight_state: str
    configuration_preview_id: str
    configuration_digest: str
    configuration_state: str

    def __post_init__(self) -> None:
        if self.schema_version != "atlas.bootstrap-plan-request.v1":
            raise ValueError("bootstrap plan request schema is unsupported")
        for value, label in (
            (self.release_id, "release_id"),
            (self.organization_id, "organization_id"),
            (self.environment_id, "environment_id"),
            (self.site_id, "site_id"),
            (self.preflight_report_id, "preflight_report_id"),
            (self.configuration_preview_id, "configuration_preview_id"),
        ):
            validate_stable_identifier(value, label)
        if not DIGEST_PATTERN.fullmatch(self.manifest_digest) or not DIGEST_PATTERN.fullmatch(
            self.configuration_digest
        ):
            raise ValueError("bootstrap plan input digest is invalid")
        if self.preflight_state not in {"passed", "failed", "warning", "unchecked"}:
            raise ValueError("preflight state is invalid")
        if self.configuration_state not in {"passed", "failed"}:
            raise ValueError("configuration state is invalid")


@dataclass(frozen=True, slots=True)
class BootstrapPhase:
    phase_id: str
    sequence: int
    title: str
    dependencies: tuple[str, ...]
    state: BootstrapPhaseState
    resumable: bool
    input_references: tuple[str, ...]
    stop_guidance: str


@dataclass(frozen=True, slots=True)
class BootstrapPlan:
    plan_id: str
    schema_version: str
    release_id: str
    profile: DeploymentProfile
    organization_id: str
    environment_id: str
    site_id: str
    state: BootstrapPlanState
    plan_digest: str
    resume_key: str
    phases: tuple[BootstrapPhase, ...]
    generated_at: datetime
    correlation_id: str
    mutation_authorized: bool = False
    execution_authorized: bool = False
