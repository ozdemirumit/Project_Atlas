from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, cast

from atlas.modules.itsm.domain.models import (
    ItsmIntegrationProfile,
    ItsmSandboxConformanceAssessment,
    ItsmSandboxOnboardingEvidence,
)


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
