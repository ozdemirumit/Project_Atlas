from __future__ import annotations

from typing import Protocol

from atlas.modules.itsm.domain.models import (
    ItsmIntegrationProfile,
    ItsmProfileLifecycle,
    ItsmSandboxConformanceAssessment,
    ItsmSandboxDiagnostic,
    ItsmSandboxOnboardingEvidence,
    ItsmSandboxOnboardingPolicy,
    ItsmSandboxOnboardingPolicyProvenance,
    ItsmSandboxOnboardingPolicyTrustKey,
)


class ItsmIntegrationProfileRepository(Protocol):
    durable: bool

    async def get(self, *, profile_id: str) -> ItsmIntegrationProfile | None: ...

    async def get_by_scope_key(
        self, *, organization_id: str, environment_id: str, profile_key: str
    ) -> ItsmIntegrationProfile | None: ...

    async def get_by_create_key(
        self, *, created_by: str, idempotency_key: str
    ) -> ItsmIntegrationProfile | None: ...

    async def get_by_retirement_key(
        self, *, retired_by: str, idempotency_key: str
    ) -> ItsmIntegrationProfile | None: ...

    async def list_scope(
        self,
        *,
        organization_id: str,
        environment_id: str,
        lifecycle: ItsmProfileLifecycle | None,
        limit: int,
    ) -> tuple[ItsmIntegrationProfile, ...]: ...

    async def add(self, profile: ItsmIntegrationProfile) -> bool: ...

    async def update(self, profile: ItsmIntegrationProfile, *, expected_version: int) -> bool: ...

    async def get_latest_sandbox_conformance(
        self,
        *,
        organization_id: str,
        environment_id: str,
        site_id: str,
        profile_id: str,
    ) -> ItsmSandboxConformanceAssessment | None: ...

    async def get_sandbox_conformance_by_key(
        self, *, assessed_by: str, idempotency_key: str
    ) -> ItsmSandboxConformanceAssessment | None: ...

    async def add_sandbox_conformance(
        self, assessment: ItsmSandboxConformanceAssessment
    ) -> bool: ...

    async def close(self) -> None: ...


class ItsmSandboxConformanceAdapter(Protocol):
    async def assess(
        self,
        *,
        profile: ItsmIntegrationProfile,
        challenge_digest: str,
        diagnostic_contract_version: str,
    ) -> ItsmSandboxDiagnostic: ...


class ItsmSandboxOnboardingEvidenceSource(Protocol):
    async def get(
        self,
        *,
        profile: ItsmIntegrationProfile,
        assessment: ItsmSandboxConformanceAssessment | None,
    ) -> ItsmSandboxOnboardingEvidence | None: ...


class ItsmSandboxOnboardingPolicySource(Protocol):
    async def list_scope(
        self,
        *,
        organization_id: str,
        environment_id: str,
        site_id: str,
    ) -> tuple[ItsmSandboxOnboardingPolicy, ...]: ...


class ItsmSandboxOnboardingPolicyProvenanceSource(Protocol):
    async def list_scope(
        self,
        *,
        organization_id: str,
        environment_id: str,
        site_id: str,
        policy_id: str,
    ) -> tuple[ItsmSandboxOnboardingPolicyProvenance, ...]: ...


class ItsmSandboxOnboardingPolicyTrustSource(Protocol):
    async def list_scope(
        self,
        *,
        organization_id: str,
        environment_id: str,
        site_id: str,
        issuer: str,
    ) -> tuple[ItsmSandboxOnboardingPolicyTrustKey, ...]: ...


class ItsmSandboxOnboardingPolicyVerifier(Protocol):
    @property
    def supported_algorithms(self) -> tuple[str, ...]: ...

    async def verify(
        self,
        *,
        provenance: ItsmSandboxOnboardingPolicyProvenance,
        trust_key: ItsmSandboxOnboardingPolicyTrustKey,
    ) -> bool: ...
