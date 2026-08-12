from __future__ import annotations

from typing import Protocol

from atlas.modules.connectors.domain.upgrade_approval import (
    ConnectorUpgradeApprovalDecision,
    ConnectorUpgradeApprovalPolicySnapshot,
    ConnectorUpgradeApprovalRequest,
    ConnectorUpgradeApprovalRevalidation,
    ConnectorUpgradeAuditReadinessEvidence,
    ConnectorUpgradeChangeContextDraft,
    ConnectorUpgradeItsmChangeEvidence,
    ConnectorUpgradeMaintenanceWindowEvidence,
)
from atlas.modules.connectors.domain.upgrade_evidence_authenticity import (
    ConnectorUpgradeSigningProviderConformanceAssessment,
    ConnectorUpgradeSigningProviderOnboardingEvidence,
    ConnectorUpgradeSigningProviderOnboardingPolicySnapshot,
)


class ConnectorUpgradeApprovalError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ConnectorUpgradeApprovalPolicySource(Protocol):
    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorUpgradeApprovalPolicySnapshot, ...]: ...


class ConnectorUpgradeAuditReadinessSource(Protocol):
    async def get_current(
        self, *, organization_id: str, environment_id: str, request_id: str
    ) -> ConnectorUpgradeAuditReadinessEvidence | None: ...


class ConnectorUpgradeItsmChangeEvidenceSource(Protocol):
    async def get_current(
        self, *, organization_id: str, environment_id: str, request_id: str
    ) -> ConnectorUpgradeItsmChangeEvidence | None: ...


class ConnectorUpgradeMaintenanceWindowEvidenceSource(Protocol):
    async def get_current(
        self, *, organization_id: str, environment_id: str, request_id: str
    ) -> ConnectorUpgradeMaintenanceWindowEvidence | None: ...


class ConnectorUpgradeSigningProviderOnboardingEvidenceSource(Protocol):
    async def get_current(
        self, *, organization_id: str, environment_id: str, provider_class: str
    ) -> ConnectorUpgradeSigningProviderOnboardingEvidence | None: ...


class ConnectorUpgradeSigningProviderOnboardingPolicySource(Protocol):
    async def list_scope(
        self, *, organization_id: str, environment_id: str
    ) -> tuple[ConnectorUpgradeSigningProviderOnboardingPolicySnapshot, ...]: ...


class ConnectorUpgradeApprovalRepository(Protocol):
    @property
    def durable(self) -> bool: ...

    async def get(self, *, request_id: str) -> ConnectorUpgradeApprovalRequest | None: ...

    async def get_by_plan(self, *, plan_digest: str) -> ConnectorUpgradeApprovalRequest | None: ...

    async def get_by_create_key(
        self, *, requested_by: str, idempotency_key: str
    ) -> ConnectorUpgradeApprovalRequest | None: ...

    async def add(self, request: ConnectorUpgradeApprovalRequest) -> bool: ...

    async def get_decision(self, *, request_id: str) -> ConnectorUpgradeApprovalDecision | None: ...

    async def get_decision_by_key(
        self, *, decided_by: str, idempotency_key: str
    ) -> ConnectorUpgradeApprovalDecision | None: ...

    async def add_decision(self, decision: ConnectorUpgradeApprovalDecision) -> bool: ...

    async def get_revalidation(
        self, *, revalidation_id: str
    ) -> ConnectorUpgradeApprovalRevalidation | None: ...

    async def get_latest_revalidation(
        self, *, request_id: str
    ) -> ConnectorUpgradeApprovalRevalidation | None: ...

    async def get_revalidation_by_key(
        self, *, revalidated_by: str, idempotency_key: str
    ) -> ConnectorUpgradeApprovalRevalidation | None: ...

    async def add_revalidation(
        self, revalidation: ConnectorUpgradeApprovalRevalidation
    ) -> bool: ...

    async def get_latest_change_context_draft(
        self, *, request_id: str
    ) -> ConnectorUpgradeChangeContextDraft | None: ...

    async def get_change_context_draft_by_key(
        self, *, created_by: str, idempotency_key: str
    ) -> ConnectorUpgradeChangeContextDraft | None: ...

    async def add_change_context_draft(self, draft: ConnectorUpgradeChangeContextDraft) -> bool: ...

    async def get_latest_signing_provider_conformance(
        self, *, organization_id: str, environment_id: str
    ) -> ConnectorUpgradeSigningProviderConformanceAssessment | None: ...

    async def get_signing_provider_conformance_by_key(
        self, *, assessed_by: str, idempotency_key: str
    ) -> ConnectorUpgradeSigningProviderConformanceAssessment | None: ...

    async def add_signing_provider_conformance(
        self, assessment: ConnectorUpgradeSigningProviderConformanceAssessment
    ) -> bool: ...

    async def close(self) -> None: ...
