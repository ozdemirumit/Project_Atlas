from __future__ import annotations

from atlas.modules.itsm.domain.models import (
    ItsmIntegrationProfile,
    ItsmSandboxConformanceState,
    ItsmSandboxDiagnostic,
)


class UnavailableItsmSandboxConformanceAdapter:
    async def assess(
        self,
        *,
        profile: ItsmIntegrationProfile,
        challenge_digest: str,
        diagnostic_contract_version: str,
    ) -> ItsmSandboxDiagnostic:
        del diagnostic_contract_version
        return ItsmSandboxDiagnostic(
            adapter_id="adapter.itsm.unavailable",
            adapter_version="version.1",
            organization_id=profile.organization_id,
            environment_id=profile.environment_id,
            site_id=profile.site_id,
            profile_id=profile.profile_id,
            profile_version=profile.version,
            challenge_digest=challenge_digest,
            state=ItsmSandboxConformanceState.UNAVAILABLE,
            reason_code="itsm.sandbox-conformance.adapter_unavailable",
        )


class DeterministicNoNetworkItsmSandboxConformanceAdapter:
    """Exercises the bounded adapter contract without contacting an ITSM system."""

    def __init__(
        self,
        *,
        state: ItsmSandboxConformanceState = ItsmSandboxConformanceState.CONFORMANT,
    ) -> None:
        self._state = state

    async def assess(
        self,
        *,
        profile: ItsmIntegrationProfile,
        challenge_digest: str,
        diagnostic_contract_version: str,
    ) -> ItsmSandboxDiagnostic:
        del diagnostic_contract_version
        reason = {
            ItsmSandboxConformanceState.CONFORMANT: "synthetic_contract_conformant",
            ItsmSandboxConformanceState.UNAVAILABLE: "adapter_unavailable",
            ItsmSandboxConformanceState.PROFILE_BLOCKED: "profile_blocked",
            ItsmSandboxConformanceState.TRUST_FAILED: "trust_failed",
            ItsmSandboxConformanceState.CREDENTIAL_FAILED: "credential_failed",
            ItsmSandboxConformanceState.PERMISSION_FAILED: "permission_failed",
            ItsmSandboxConformanceState.MAPPING_FAILED: "mapping_failed",
            ItsmSandboxConformanceState.ROUND_TRIP_FAILED: "round_trip_failed",
        }[self._state]
        return ItsmSandboxDiagnostic(
            adapter_id="adapter.itsm.synthetic-no-network",
            adapter_version="version.1",
            organization_id=profile.organization_id,
            environment_id=profile.environment_id,
            site_id=profile.site_id,
            profile_id=profile.profile_id,
            profile_version=profile.version,
            challenge_digest=challenge_digest,
            state=self._state,
            reason_code=f"itsm.sandbox-conformance.{reason}",
        )
