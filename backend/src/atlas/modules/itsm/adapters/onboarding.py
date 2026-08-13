from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from hashlib import sha256
from typing import Any, cast

from atlas.modules.itsm.domain.models import (
    ITSM_SANDBOX_ONBOARDING_REQUIREMENTS,
    ItsmIntegrationProfile,
    ItsmSandboxConformanceAssessment,
    ItsmSandboxOnboardingAdapterRule,
    ItsmSandboxOnboardingEvidence,
    ItsmSandboxOnboardingPolicy,
)


def _normalize(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return _normalize(asdict(value))
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def _digest(value: object) -> str:
    return sha256(
        json.dumps(_normalize(value), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class EmptyItsmSandboxOnboardingEvidenceSource:
    async def get(
        self,
        *,
        profile: ItsmIntegrationProfile,
        assessment: ItsmSandboxConformanceAssessment | None,
    ) -> None:
        return None


class DeterministicDevelopmentItsmSandboxOnboardingEvidenceSource:
    async def get(
        self,
        *,
        profile: ItsmIntegrationProfile,
        assessment: ItsmSandboxConformanceAssessment | None,
    ) -> ItsmSandboxOnboardingEvidence | None:
        if assessment is None:
            return None
        values = {
            "schema_version": "atlas.itsm-sandbox-onboarding-evidence.v1",
            "version": 1,
            "organization_id": profile.organization_id,
            "environment_id": profile.environment_id,
            "site_id": profile.site_id,
            "profile_id": profile.profile_id,
            "profile_version": profile.version,
            "profile_digest": profile.canonical_digest,
            "mapping_version": profile.mapping_version,
            "adapter_id": assessment.adapter_id,
            "adapter_version": assessment.adapter_version,
            "adapter_registered": True,
            "adapter_sandbox_approved": False,
            "workload_identity_configured": True,
            "credential_reference_owned": True,
            "network_trust_approved": True,
            "mapping_change_control_configured": True,
            "rate_limit_and_backpressure_configured": True,
            "audit_routing_configured": True,
            "availability_and_recovery_configured": True,
            "security_approval_reference": None,
            "deployment_approval_reference": None,
            "observed_at": assessment.observed_at,
            "valid_until": assessment.valid_until,
            "production_eligible": False,
        }
        digest_payload = {
            key: value.isoformat() if hasattr(value, "isoformat") else value
            for key, value in values.items()
        }
        canonical_digest = sha256(
            json.dumps(digest_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return ItsmSandboxOnboardingEvidence(
            **cast(dict[str, Any], values), canonical_digest=canonical_digest
        )


class InMemoryItsmSandboxOnboardingPolicySource:
    def __init__(self, policies: tuple[ItsmSandboxOnboardingPolicy, ...] = ()) -> None:
        self._policies = policies

    async def list_scope(
        self,
        *,
        organization_id: str,
        environment_id: str,
        site_id: str,
    ) -> tuple[ItsmSandboxOnboardingPolicy, ...]:
        del organization_id, environment_id, site_id
        return self._policies


def build_development_itsm_sandbox_onboarding_policy(
    *,
    organization_id: str,
    environment_id: str,
    site_id: str,
    now: datetime | None = None,
) -> ItsmSandboxOnboardingPolicy:
    issued_at = now or datetime.now(UTC)
    values = {
        "schema_version": "atlas.itsm-sandbox-onboarding-policy.v1",
        "policy_id": "policy.itsm-sandbox-onboarding.development",
        "version": 1,
        "organization_id": organization_id,
        "environment_id": environment_id,
        "site_id": site_id,
        "issuer": "issuer.atlas-development",
        "requirement_ids": ITSM_SANDBOX_ONBOARDING_REQUIREMENTS,
        "adapter_rules": (
            ItsmSandboxOnboardingAdapterRule(
                adapter_id="adapter.itsm.synthetic-no-network",
                adapter_version="version.1",
            ),
        ),
        "max_conformance_age_seconds": 600,
        "max_evidence_age_seconds": 600,
        "issued_at": issued_at,
        "effective_at": issued_at,
        "expires_at": issued_at + timedelta(days=30),
    }
    digest = _digest(_normalize(values))
    return ItsmSandboxOnboardingPolicy(**cast(dict[str, Any], values), canonical_digest=digest)


def onboarding_policy_payload(policy: ItsmSandboxOnboardingPolicy) -> dict[str, object]:
    payload = cast(dict[str, object], asdict(policy))
    payload.pop("canonical_digest")
    return cast(dict[str, object], _normalize(payload))
